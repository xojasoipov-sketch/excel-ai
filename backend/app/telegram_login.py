"""Telegram Login Widget for the website: "Telegram orqali kirish" next to Google.

Flow:
  1. The frontend embeds Telegram's own widget (telegram.org/js/telegram-widget.js),
     configured for our bot. The bot's domain must be registered once via
     @BotFather -> /setdomain (a manual step only the bot owner can do — there is
     no API for it).
  2. Telegram authenticates the user and hands the widget signed payload back
     (id, first_name, username, photo_url, auth_date, hash).
  3. The frontend POSTs that payload here. We verify the HMAC signature (Telegram's
     documented algorithm: https://core.telegram.org/widgets/login#checking-authorization)
     so a request can't be forged with an arbitrary Telegram id.
  4. We resolve/create the same `profiles` row the bot itself uses
     (app/telegram_identity.py) — a user is the same account whether they signed
     up via the bot or via this website button.
  5. Supabase has no "log this user in without a password" primitive exposed to
     the client, so the backend mints a real session itself: generate_link(type=
     "magiclink") returns a token_hash without emailing anything (this call never
     sends mail — that's the whole point of the Admin API version), then
     verify_otp() exchanges it for a genuine access_token/refresh_token pair,
     indistinguishable from a normal login. Verified end-to-end before shipping.
"""
import hashlib
import hmac
import os
import time
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel

from .db import get_db
from .telegram_identity import get_or_create_telegram_profile

MAX_AUTH_AGE_SECONDS = 24 * 60 * 60  # reject stale/replayed widget payloads


class TelegramAuthPayload(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


def _bot_token() -> str:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="Telegram orqali kirish hali sozlanmagan.")
    return token


def _verify_signature(payload: TelegramAuthPayload) -> None:
    data = payload.model_dump(exclude_none=True, exclude={"hash"})
    check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret_key = hashlib.sha256(_bot_token().encode()).digest()
    computed = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, payload.hash):
        raise HTTPException(status_code=401, detail="Telegram imzosi noto'g'ri.")
    if time.time() - payload.auth_date > MAX_AUTH_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="Telegram login muddati o'tgan. Qaytadan urinib ko'ring.")


def sign_in_with_telegram(payload: TelegramAuthPayload) -> dict:
    """Verify the widget payload, then return a real Supabase session for the
    matching (or newly created) profile — same shape a normal password/OAuth
    login returns, so the frontend just calls supabase.auth.setSession() with it."""
    _verify_signature(payload)

    display_name = payload.username or payload.first_name or str(payload.id)
    profile = get_or_create_telegram_profile(payload.id, display_name)

    db = get_db()
    link = db.auth.admin.generate_link({"type": "magiclink", "email": profile["email"]})
    verified = db.auth.verify_otp({"token_hash": link.properties.hashed_token, "type": "magiclink"})
    if not verified.session:
        raise HTTPException(status_code=500, detail="Sessiya yaratib bo'lmadi. Qaytadan urinib ko'ring.")

    return {
        "access_token": verified.session.access_token,
        "refresh_token": verified.session.refresh_token,
    }
