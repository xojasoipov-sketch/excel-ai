"""Telegram bot for ExcelYordamchi AI — same brain as the website.

Runs two ways:
  - `python telegram_bot.py` — standalone polling process (local dev).
  - Embedded in the FastAPI app (see app/main.py's startup hook) as a background
    asyncio task on the *same* free Render web service, so no second paid
    background-worker instance is needed.

Feature parity with the website:
  - Fileless formula chat and file-upload + chat (unchanged from before).
  - The exact same free-plan daily quota, Pro/owner bypass, and `usage_events`
    table as the site (app/quota.py) — a Telegram user and a website user share
    one quota if they're the same account isn't required; each surface just
    plays by the same rules.
  - /library — search the same 24-template Formula Library (app/formula_lab.py).
  - /test — evaluate a library template against sample or custom cell values,
    the bot's answer to the website's Formula Test panel.
  - /upgrade — link to the site's Pro checkout.
  - /admin — owner-only, mirrors GET /api/admin/stats.
"""
import asyncio
import logging
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app import admin as admin_service
from app import formula_lab
from app.agent import ExcelAgent
from app.billing import PLAN_PRICE_USD, SITE_URL
from app.excel_utils import ExcelUtils
from app.quota import enforce_ai_quota, quota_status
from app.telegram_identity import get_or_create_telegram_profile

load_dotenv()
log = logging.getLogger("telegram_bot")

MAX_TELEGRAM_MESSAGE = 3500  # stay under Telegram's 4096-char hard limit


def _profile(update: Update) -> dict:
    user = update.effective_user
    return get_or_create_telegram_profile(user.id, user.username or "")


def _quota_denied_text(detail) -> str:
    message = detail.get("message") if isinstance(detail, dict) else str(detail)
    return f"{message}\n\nCheksiz foydalanish: {SITE_URL}/billing"


# ─── Commands ───────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = _profile(update)
    status = quota_status(profile)
    quota_line = (
        "Cheksiz so'rov huquqingiz bor. 🎉" if status["unlimited"]
        else f"Bugun qoldi: {status['remaining']} / {status['limit']} bepul so'rov."
    )
    await update.message.reply_text(
        "Salom! Men ExcelYordamchi AI botiman.\n\n"
        "Excel formulani o'zbekcha, ruscha yoki inglizcha yozing — masalan:\n"
        "\"A ustundagi sonlar yig'indisini hisobla\"\n\n"
        "Jadval faylini (XLSX/CSV) yuborsangiz, u haqida savol bera olasiz.\n\n"
        "Buyruqlar:\n"
        "/library — 24 ta tayyor formula shabloni\n"
        "/test — formulani namuna ma'lumot ustida sinash\n"
        "/upgrade — cheksiz Pro reja\n\n"
        f"{quota_line}"
    )


async def library(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args) if context.args else ""
    results = formula_lab.search_library(query)[:8]
    if not results:
        await update.message.reply_text("Hech narsa topilmadi. Masalan: /library sumif")
        return

    lines = [f"🔎 «{query}» bo'yicha natijalar:" if query else "📚 Formula kutubxonasi (birinchi 8 ta):"]
    for item in results:
        lines.append(f"\n*{item['name']}*\n`{item['formula']}`\n{item['description']}\n/test {item['id']}")
    lines.append("\n\nBoshqa mavzu qidirish uchun: /library <so'z>")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def test_formula(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Foydalanish: /test <formula_id> [A1=qiymat B1=qiymat ...]\n"
            "Shablon ID'larini ko'rish uchun: /library"
        )
        return

    formula_id = context.args[0]
    item = formula_lab.find_by_id(formula_id)
    if not item:
        await update.message.reply_text(f"«{formula_id}» topilmadi. /library orqali qidiring.")
        return

    cells = dict(item["sample"])
    overrides_used = False
    for token in context.args[1:]:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        cells[key.strip().upper()] = value.strip()
        overrides_used = True

    ok, result = formula_lab.evaluate(formula_id, cells)
    cells_line = ", ".join(f"{k}={v}" for k, v in cells.items()) or "(bo'sh)"
    status_line = "sizning qiymatlaringiz bilan" if overrides_used else "namuna qiymatlar bilan"
    if ok:
        await update.message.reply_text(
            f"*{item['name']}*\n`{item['formula']}`\n\n"
            f"Katakchalar ({status_line}): {cells_line}\n\n"
            f"✅ Natija: `{result}`\n\n"
            f"Boshqa qiymat bilan sinash: /test {formula_id} A1=... B1=...",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(f"Xato: {result}")


async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = _profile(update)
    if profile.get("is_owner") or profile.get("plan") == "pro":
        await update.message.reply_text("Sizda allaqachon cheksiz foydalanish huquqi bor. ✅")
        return
    await update.message.reply_text(
        f"Pro reja — ${PLAN_PRICE_USD:g}/oy: cheksiz AI formula so'rovlari va fayl tahlili.\n\n"
        f"Obuna bo'lish uchun saytga kiring: {SITE_URL}/billing\n"
        "(Google akkaunt bilan bir bosishda ro'yxatdan o'tasiz.)"
    )


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = _profile(update)
    if not profile.get("is_owner"):
        return  # silently ignore for non-owners, same as the website's 403
    s = admin_service.get_stats()
    await update.message.reply_text(
        "📊 *Admin statistikasi*\n\n"
        f"Jami foydalanuvchi: {s['total_users']}\n"
        f"To'laydigan (Pro): {s['paying_users']}\n"
        f"Promokod bilan Pro: {s['promo_pro_users']}\n"
        f"Bepul: {s['free_users']}\n\n"
        f"MRR: ${s['mrr_usd']:g}\n"
        f"Jami tushum: ${s['revenue_total_usd']:g}\n"
        f"So'nggi 30 kun: ${s['revenue_30d_usd']:g}\n\n"
        f"Bugungi AI so'rovlar: {s['ai_calls_today']}\n"
        f"So'nggi 7 kunlik ro'yxatdan o'tish: {s['signups_7d']}",
        parse_mode=ParseMode.MARKDOWN,
    )


# ─── Formula chat (fileless) ────────────────────────────────────────────────

async def answer_formula(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = _profile(update)
    try:
        enforce_ai_quota(profile)
    except HTTPException as limit_error:
        await update.message.reply_text(_quota_denied_text(limit_error.detail))
        return

    await update.message.chat.send_action("typing")
    agent: ExcelAgent = context.application.bot_data["agent"]
    try:
        response = await asyncio.to_thread(
            agent.quick_chat,
            [
                {"role": "system", "content": (
                    "You are ExcelYordamchi AI. Generate safe, exact Microsoft Excel formulas. "
                    "Reply in the user's language (Uzbek, Russian, or English). Put the formula alone "
                    "in an Excel code block, then give a very short explanation. Ask one question if "
                    "cell references, ranges, or conditions are essential but missing."
                )},
                {"role": "user", "content": update.message.text},
            ],
        )
        await update.message.reply_text(response[:MAX_TELEGRAM_MESSAGE])
    except Exception as error:
        log.exception("quick_chat failed")
        await update.message.reply_text(f"AI javob bera olmadi: {error}")


# ─── File upload + chat about it ────────────────────────────────────────────

async def handle_spreadsheet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    suffix = Path(document.file_name or "").suffix.lower()
    if suffix not in {".xlsx", ".xls", ".csv", ".tsv"}:
        await update.message.reply_text("Iltimos, XLSX, XLS, CSV yoki TSV fayl yuboring.")
        return
    if document.file_size and document.file_size > 10 * 1024 * 1024:
        await update.message.reply_text("Fayl 10 MB dan kichik bo'lishi kerak.")
        return

    upload_dir = Path(__file__).parent / "uploads" / "telegram"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{update.effective_chat.id}-{uuid.uuid4()}{suffix}"
    telegram_file = await document.get_file()
    await telegram_file.download_to_drive(custom_path=str(file_path))

    try:
        excel_utils = ExcelUtils(str(file_path))
        df = excel_utils.get_dataframe()
        context.chat_data["excel_utils"] = excel_utils
        context.chat_data["history"] = [{
            "role": "system",
            "content": f"""You are ExcelYordamchi AI. Reply in the user's language: Uzbek, Russian, or English.
The user uploaded a spreadsheet with {len(df)} rows and {len(df.columns)} columns.
Headers: {', '.join(map(str, df.columns))}. Preview:\n{df.head().to_string()}
Use the available tools to inspect the workbook before answering data questions. For a formula, put the exact Excel formula in a code block.""",
        }]
        await update.message.reply_text(
            f"{document.file_name} qabul qilindi. {len(df)} qator va {len(df.columns)} ustun topildi. "
            "Endi fayl haqida savol bering."
        )
    except Exception:
        file_path.unlink(missing_ok=True)
        await update.message.reply_text("Faylni o'qib bo'lmadi. Iltimos, fayl formatini tekshiring.")


async def answer_data_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if "excel_utils" not in context.chat_data:
        await answer_formula(update, context)
        return

    profile = _profile(update)
    try:
        enforce_ai_quota(profile)
    except HTTPException as limit_error:
        await update.message.reply_text(_quota_denied_text(limit_error.detail))
        return

    history = context.chat_data["history"]
    history.append({"role": "user", "content": update.message.text})
    await update.message.chat.send_action("typing")
    try:
        agent: ExcelAgent = context.application.bot_data["agent"]
        response, _ = await asyncio.to_thread(
            agent.call_agent, history, context.chat_data["excel_utils"],
        )
        history.append({"role": "assistant", "content": response})
        await update.message.reply_text(response[:MAX_TELEGRAM_MESSAGE])
    except Exception as error:
        log.exception("call_agent failed")
        await update.message.reply_text(f"So'rovni bajarib bo'lmadi: {error}")


# ─── Wiring ─────────────────────────────────────────────────────────────────

def build_application() -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in backend/.env first.")
    application = Application.builder().token(token).build()
    application.bot_data["agent"] = ExcelAgent()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("library", library))
    application.add_handler(CommandHandler("test", test_formula))
    application.add_handler(CommandHandler("upgrade", upgrade))
    application.add_handler(CommandHandler("admin", admin_stats))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_spreadsheet))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, answer_data_question))
    return application


# ─── Embedded mode: started/stopped from app/main.py's FastAPI lifespan ─────

_embedded_application: Application | None = None


async def start_in_background() -> None:
    """Start polling without blocking — call once from FastAPI's startup event."""
    global _embedded_application
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        log.info("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled.")
        return
    application = build_application()
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    _embedded_application = application
    log.info("Telegram bot started (embedded in the web service).")


async def stop_background() -> None:
    global _embedded_application
    if _embedded_application is None:
        return
    await _embedded_application.updater.stop()
    await _embedded_application.stop()
    await _embedded_application.shutdown()
    _embedded_application = None


# ─── Standalone mode: `python telegram_bot.py` ──────────────────────────────

def main() -> None:
    build_application().run_polling()


if __name__ == "__main__":
    main()
