"""Authentication: every protected route resolves the caller to a row in `profiles`.

Access tokens are issued by Supabase Auth (Google OAuth or email/password) on the
frontend and sent here as `Authorization: Bearer <token>`. We validate them by
asking Supabase itself (`auth.get_user`) rather than verifying the JWT signature
locally — that way this works unchanged whether the project signs tokens with a
shared HS256 secret or with rotating asymmetric keys, and revoked sessions are
rejected immediately instead of staying valid until expiry.
"""
import os
from typing import Optional

from fastapi import Depends, Header, HTTPException, WebSocket

from .db import get_db

OWNER_EMAIL = (os.getenv("OWNER_EMAIL") or "").strip().lower()


def _load_or_create_profile(user_id: str, email: str) -> dict:
    """Profiles are created lazily on first authenticated request instead of via a
    DB trigger, so the owner flag stays driven by the OWNER_EMAIL env var."""
    db = get_db()
    existing = db.table("profiles").select("*").eq("user_id", user_id).limit(1).execute()
    if existing.data:
        profile = existing.data[0]
        # Keep the owner flag in sync if OWNER_EMAIL was set/changed after signup.
        should_own = bool(OWNER_EMAIL) and (profile.get("email") or "").strip().lower() == OWNER_EMAIL
        if should_own and not profile.get("is_owner"):
            updated = (
                db.table("profiles")
                .update({"is_owner": True})
                .eq("user_id", user_id)
                .execute()
            )
            if updated.data:
                return updated.data[0]
            profile["is_owner"] = True
        return profile

    is_owner = bool(OWNER_EMAIL) and email.strip().lower() == OWNER_EMAIL
    inserted = (
        db.table("profiles")
        .insert({
            "user_id": user_id,
            "email": email,
            "is_owner": is_owner,
        })
        .execute()
    )
    return inserted.data[0]


def _verify_token(token: str) -> dict:
    db = get_db()
    try:
        response = db.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Sessiya yaroqsiz yoki muddati tugagan. Qaytadan kiring.")

    user = getattr(response, "user", None)
    if user is None or not getattr(user, "id", None):
        raise HTTPException(status_code=401, detail="Sessiya yaroqsiz yoki muddati tugagan. Qaytadan kiring.")

    return _load_or_create_profile(user.id, getattr(user, "email", "") or "")


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bu amal uchun tizimga kirish kerak.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Bu amal uchun tizimga kirish kerak.")
    return _verify_token(token)


async def require_owner(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_owner"):
        raise HTTPException(status_code=403, detail="Bu bo'limga faqat admin kira oladi.")
    return user


async def authenticate_websocket(websocket: WebSocket) -> Optional[dict]:
    """WebSocket auth. Browsers can't set headers on a WS handshake, so the access
    token arrives as a `?token=` query param. Returns None (after closing the
    socket) when authentication fails."""
    token = websocket.query_params.get("token", "").strip()
    if not token:
        await websocket.close(code=4401, reason="Avtorizatsiya talab qilinadi")
        return None
    try:
        return _verify_token(token)
    except HTTPException:
        await websocket.close(code=4401, reason="Sessiya yaroqsiz")
        return None
