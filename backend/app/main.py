import asyncio
import json
import os
import uuid
from typing import Dict, List, Optional

import pandas as pd
import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import admin as admin_service
from . import billing, promo
from .agent import ExcelAgent
from .auth import authenticate_websocket, get_current_user, require_owner
from .excel_utils import ExcelUtils
from .quota import FREE_DAILY_LIMIT, enforce_ai_quota, quota_status

load_dotenv()

app = FastAPI(title="ExcelYordamchi AI API")

# In production the SPA is served from this same origin, so CORS only really
# matters for local development (Vite on :5173 / preview on :4173).
_default_origins = "http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173,http://127.0.0.1:4173"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",") if o.strip()]
if os.getenv("SITE_URL"):
    CORS_ORIGINS.append(os.getenv("SITE_URL").rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BACKEND_DIR, "uploads")
FRONTEND_DIST = os.path.normpath(os.path.join(BACKEND_DIR, "..", "frontend", "dist"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

SUPPORTED_FORMATS = ['.xlsx', '.xls', '.csv', '.tsv', '.ods', '.fods', '.xlsm', '.xltx', '.xltm']

# Live per-upload state (the parsed spreadsheet + chat history). This is an
# in-process cache keyed by upload id; ownership is also persisted in the
# `uploads` table so it survives for auditing, but the parsed dataframe itself
# is intentionally memory-only and is lost on restart.
active_connections: Dict[str, Dict] = {}

excel_agent = ExcelAgent()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_message(self, client_id: str, message: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)


manager = ConnectionManager()

QUICK_CHAT_SYSTEM_PROMPT = """You are ExcelYordamchi AI in "no file" chat mode.
The user has not uploaded a spreadsheet — they describe their columns and data in words.
Reply in the same language as the user: Uzbek, Russian, or English.
For formula requests, always return the exact formula in a separate Excel code block,
followed by a one-sentence explanation. Use English Excel function names and commas as
separators unless the user explicitly requests a localized Excel version.
Do not invent column names, sheet names, or sample data. If the columns, ranges, or
condition needed to write the formula are unclear, ask one concise question instead of
guessing. You cannot read or modify any file in this mode — if the user wants that,
suggest they upload their file first."""

MAX_QUICK_CHAT_HISTORY = 20  # keep recent turns only; this endpoint is stateless per request


# ─── Schemas ──────────────────────────────────────────────────────────────────

class QuickChatMessage(BaseModel):
    role: str
    content: str


class QuickChatRequest(BaseModel):
    messages: List[QuickChatMessage]


class PromoRedeemRequest(BaseModel):
    code: str


class PromoCreateRequest(BaseModel):
    code: str
    discount_percent: int
    duration: str  # 'month' | 'year'
    max_redemptions: Optional[int] = None
    expires_at: Optional[str] = None
    note: Optional[str] = None


class PromoActiveRequest(BaseModel):
    active: bool


class PayoutCardRequest(BaseModel):
    card_number: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def dataframe_to_payload(df: pd.DataFrame) -> dict:
    """Serialize a sheet for the frontend grid, coercing pandas/NumPy types that
    json.dumps can't handle on its own."""
    data = []
    for i in range(len(df)):
        row = {}
        for j in range(len(df.columns)):
            value = df.iloc[i, j]
            if pd.isna(value):
                value = None
            elif isinstance(value, pd.Timestamp) or hasattr(value, 'isoformat'):
                value = value.isoformat()
            elif hasattr(value, 'item'):
                try:
                    value = value.item()
                except (ValueError, TypeError):
                    value = str(value)
            elif not isinstance(value, (str, int, float, bool, type(None))):
                value = str(value)
            row[str(j)] = value
        data.append(row)

    rows, cols = df.shape
    return {"data": data, "metadata": {"rows": rows, "columns": cols}}


def require_owned_session(client_id: str, user: dict) -> dict:
    session = active_connections.get(client_id)
    if not session:
        raise HTTPException(status_code=404, detail="Fayl sessiyasi topilmadi. Faylni qaytadan yuklang.")
    if session.get("owner_id") != user["user_id"]:
        # Same response as "not found" so an upload id can't be probed for existence.
        raise HTTPException(status_code=404, detail="Fayl sessiyasi topilmadi. Faylni qaytadan yuklang.")
    return session


def build_sheet_system_prompt(df: pd.DataFrame, file_extension: str) -> str:
    from openpyxl.utils import get_column_letter

    num_rows, num_cols = df.shape
    num_rows += 1
    data_range = f"A1:{get_column_letter(num_cols)}{num_rows}"

    return f"""You are ExcelYordamchi AI, a careful Excel formula and data-analysis assistant.
        Reply in the same language as the user: Uzbek, Russian, or English. For formula requests, always return the exact formula in a separate Excel code block, followed by a one-sentence explanation. Use English Excel function names and commas as separators unless the user explicitly requests a localized Excel version.
        Do not invent column names or data. If an essential column or condition is unclear, ask one concise question. Never claim a formula has been applied unless a write tool was actually used.
        You have access to functions. Always use them when asked to read/update spreadsheet content.
        After inserting a row or column, always re-evaluate the sheet before updating it.
        Make sure the inserted index exists before trying to write to it.
        When inserting a total row, always find the last filled row index using tools. Never hardcode the index.


        Here's a preview of top 5 rows of the spreadsheet data structure it might contains header if not you can figure it out based on data:
        {df.head().to_string()}

        The spreadsheet contains data in the range {data_range} ({num_rows} rows × {num_cols} columns).
        File format: {file_extension[1:].upper()}"""


# ─── Public / health ──────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "stripe_configured": billing.is_configured(),
        "free_daily_limit": FREE_DAILY_LIMIT,
    }


@app.get("/api/plans")
async def plans():
    """Pricing shown on the landing page. Payme/Click are deliberately advertised
    as coming soon until merchant credentials exist."""
    return {
        "free": {"price_usd": 0, "daily_ai_calls": FREE_DAILY_LIMIT},
        "pro": {"price_usd": billing.PLAN_PRICE_USD, "daily_ai_calls": None},
        "methods": {
            "card": "active" if billing.is_configured() else "not_configured",
            "payme": "soon",
            "click": "soon",
        },
    }


# ─── Account ──────────────────────────────────────────────────────────────────

@app.get("/api/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "user_id": user["user_id"],
        "email": user.get("email"),
        "is_owner": bool(user.get("is_owner")),
        "plan": user.get("plan"),
        "pro_until": user.get("pro_until"),
        "quota": quota_status(user),
    }


# ─── AI: fileless chat ────────────────────────────────────────────────────────

@app.post("/chat/no-file")
async def quick_chat(payload: QuickChatRequest, user: dict = Depends(get_current_user)):
    """Fileless formula chat: the user describes their data in words, no upload needed."""
    if not payload.messages:
        return JSONResponse(status_code=400, content={"error": "Xabarlar ro'yxati bo'sh bo'lishi mumkin emas."})

    enforce_ai_quota(user)

    history = [{"role": "system", "content": QUICK_CHAT_SYSTEM_PROMPT}]
    history.extend(
        {"role": m.role, "content": m.content}
        for m in payload.messages[-MAX_QUICK_CHAT_HISTORY:]
    )

    try:
        response = await asyncio.to_thread(excel_agent.quick_chat, history)
    except Exception as e:
        print(f"Error in quick_chat: {str(e)}")
        return JSONResponse(status_code=502, content={"error": f"AI javob bera olmadi: {str(e)}"})

    return {"response": response, "quota": quota_status(user)}


# ─── AI: spreadsheet workspace ────────────────────────────────────────────────

@app.post("/upload")
async def upload_excel(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Upload a spreadsheet and get back the id used for /excel and the WebSocket."""
    file_extension = os.path.splitext(file.filename or "")[1].lower()
    if file_extension not in SUPPORTED_FORMATS:
        return JSONResponse(
            status_code=400,
            content={"error": f"Qo'llab-quvvatlanmaydigan format. Mumkin: {', '.join(SUPPORTED_FORMATS)}"},
        )

    client_id = str(uuid.uuid4())
    user_dir = os.path.join(UPLOAD_DIR, user["user_id"])
    os.makedirs(user_dir, exist_ok=True)
    file_path = os.path.join(user_dir, f"{client_id}{file_extension}")

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())

        excel_utils = ExcelUtils(file_path)
        df = excel_utils.get_dataframe()

        active_connections[client_id] = {
            "owner_id": user["user_id"],
            "file_path": file_path,
            "excel_utils": excel_utils,
            "message_history": [
                {"role": "system", "content": build_sheet_system_prompt(df, file_extension)}
            ],
        }

        from .db import get_db
        get_db().table("uploads").insert({
            "id": client_id,
            "user_id": user["user_id"],
            "file_path": file_path,
            "original_name": file.filename or f"upload{file_extension}",
        }).execute()

        return {"client_id": client_id}
    except Exception as e:
        print(f"Error in upload_excel: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"Faylni o'qib bo'lmadi: {str(e)}"})


@app.get("/excel/{client_id}")
async def get_excel_data(client_id: str, user: dict = Depends(get_current_user)):
    session = require_owned_session(client_id, user)
    return dataframe_to_payload(session["excel_utils"].get_dataframe())


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Live spreadsheet chat. The Supabase access token arrives as ?token=... since
    a browser can't attach headers to a WebSocket handshake."""
    user = await authenticate_websocket(websocket)
    if user is None:
        return

    session = active_connections.get(client_id)
    if not session or session.get("owner_id") != user["user_id"]:
        await websocket.close(code=4404, reason="Fayl sessiyasi topilmadi")
        return

    await manager.connect(websocket, client_id)

    try:
        while True:
            raw = await websocket.receive_text()
            user_message = json.loads(raw).get("message", "")

            try:
                enforce_ai_quota(user)
            except HTTPException as limit_error:
                detail = limit_error.detail if isinstance(limit_error.detail, dict) else {"message": str(limit_error.detail)}
                await manager.send_message(client_id, json.dumps({
                    "response": detail.get("message", "Limit tugadi."),
                    "excel_modified": False,
                    "upgrade_required": True,
                }))
                continue

            session["message_history"].append({"role": "user", "content": user_message})
            excel_utils = session["excel_utils"]

            try:
                # The agent call is blocking (sync SDK + tool loop), so it runs in a
                # worker thread — otherwise a long tool loop freezes the whole server.
                response, excel_modified = await asyncio.to_thread(
                    excel_agent.call_agent, session["message_history"], excel_utils
                )
                session["message_history"].append({"role": "assistant", "content": response})

                await manager.send_message(client_id, json.dumps({
                    "response": str(response),
                    "excel_modified": excel_modified,
                }))

                if excel_modified:
                    payload = dataframe_to_payload(excel_utils.get_dataframe())
                    await manager.send_message(client_id, json.dumps({
                        "type": "excel_update",
                        **payload,
                    }))
            except Exception as e:
                print(f"Error in agent processing: {str(e)}")
                await manager.send_message(client_id, json.dumps({
                    "response": f"Xatolik yuz berdi: {str(e)}",
                    "excel_modified": False,
                }))

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        manager.disconnect(client_id)


# ─── Billing & promo codes ────────────────────────────────────────────────────

@app.post("/api/billing/checkout")
async def billing_checkout(user: dict = Depends(get_current_user)):
    return billing.create_checkout_session(user)


@app.post("/api/billing/portal")
async def billing_portal(user: dict = Depends(get_current_user)):
    return billing.create_portal_session(user)


@app.post("/api/billing/webhook")
async def billing_webhook(request: Request, stripe_signature: Optional[str] = Header(None)):
    payload = await request.body()
    return billing.handle_webhook(payload, stripe_signature)


@app.post("/api/promo/redeem")
async def promo_redeem(payload: PromoRedeemRequest, user: dict = Depends(get_current_user)):
    result = promo.redeem(payload.code, user)
    from .db import get_db
    refreshed = get_db().table("profiles").select("*").eq("user_id", user["user_id"]).limit(1).execute()
    if refreshed.data:
        result["quota"] = quota_status(refreshed.data[0])
        result["profile"] = {
            "plan": refreshed.data[0].get("plan"),
            "pro_until": refreshed.data[0].get("pro_until"),
        }
    return result


# ─── Admin (owner only) ───────────────────────────────────────────────────────

@app.get("/api/admin/stats")
async def admin_stats(_: dict = Depends(require_owner)):
    return admin_service.get_stats()


@app.get("/api/admin/users")
async def admin_users(limit: int = 100, offset: int = 0, _: dict = Depends(require_owner)):
    return admin_service.list_users(limit=limit, offset=offset)


@app.get("/api/admin/payments")
async def admin_payments(limit: int = 50, _: dict = Depends(require_owner)):
    return {"payments": admin_service.list_payments(limit=limit)}


@app.get("/api/admin/promo-codes")
async def admin_list_promos(_: dict = Depends(require_owner)):
    return {"codes": promo.list_codes()}


@app.post("/api/admin/promo-codes")
async def admin_create_promo(payload: PromoCreateRequest, _: dict = Depends(require_owner)):
    return promo.create_code(
        code=payload.code,
        discount_percent=payload.discount_percent,
        duration=payload.duration,
        max_redemptions=payload.max_redemptions,
        expires_at=payload.expires_at,
        note=payload.note,
    )


@app.patch("/api/admin/promo-codes/{code}")
async def admin_toggle_promo(code: str, payload: PromoActiveRequest, _: dict = Depends(require_owner)):
    return promo.set_active(code, payload.active)


@app.delete("/api/admin/promo-codes/{code}")
async def admin_delete_promo(code: str, _: dict = Depends(require_owner)):
    promo.delete_code(code)
    return {"deleted": True}


@app.get("/api/admin/payout-card")
async def admin_get_payout_card(_: dict = Depends(require_owner)):
    return {"card_number": admin_service.get_payout_card()}


@app.put("/api/admin/payout-card")
async def admin_set_payout_card(payload: PayoutCardRequest, _: dict = Depends(require_owner)):
    admin_service.set_payout_card(payload.card_number)
    return {"saved": True}


# ─── Static SPA (must stay last: the catch-all swallows every unmatched path) ──

if os.path.isdir(FRONTEND_DIST):
    _assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve index.html for any non-API path so client-side routes
        (/login, /billing, /admin) survive a hard refresh."""
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
else:
    @app.get("/")
    async def root():
        return {"message": "Excel Agent API is running (frontend build not found)"}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
