"""Maps a Telegram user onto the exact same `profiles` row shape the website
uses, so quota.py and admin.py work unmodified for bot users too.

Each Telegram user gets a *real* Supabase Auth user (created via the Admin API
with a synthetic @telegram.local email nobody ever logs in with) the first time
they message the bot. From then on `telegram_id` looks them back up. This means
a single free-daily-quota counter, the same is_owner/plan rules, and the same
admin dashboard cover both the website and the bot with zero duplicated logic.
"""
import os

from .db import get_db

OWNER_TELEGRAM_ID = (os.getenv("OWNER_TELEGRAM_ID") or "").strip()


def get_or_create_telegram_profile(telegram_id: int, username: str = "") -> tuple[dict, bool]:
    """Returns (profile, is_new) — is_new is True only the very first time this
    Telegram id is seen, so callers (the bot's /start handler) can show a real
    "you're registered" confirmation instead of silently creating the account."""
    db = get_db()
    is_owner_id = OWNER_TELEGRAM_ID and str(telegram_id) == OWNER_TELEGRAM_ID

    existing = db.table("profiles").select("*").eq("telegram_id", telegram_id).limit(1).execute()
    if existing.data:
        profile = existing.data[0]
        updates = {}
        if is_owner_id and not profile.get("is_owner"):
            updates["is_owner"] = True
        if username and profile.get("telegram_username") != username:
            updates["telegram_username"] = username
        if updates:
            updated = db.table("profiles").update(updates).eq("user_id", profile["user_id"]).execute()
            if updated.data:
                return updated.data[0], False
            profile.update(updates)
        return profile, False

    # First time this chat has talked to the bot: create a real auth user so
    # this profile can hold the FK relationships every other table expects.
    email = f"tg-{telegram_id}@telegram.local"
    created = db.auth.admin.create_user({
        "email": email,
        "email_confirm": True,
        "user_metadata": {"telegram_id": telegram_id, "telegram_username": username},
    })
    user_id = created.user.id

    inserted = db.table("profiles").insert({
        "user_id": user_id,
        "email": email,
        "is_owner": bool(is_owner_id),
        "telegram_id": telegram_id,
        "telegram_username": username or None,
    }).execute()
    return inserted.data[0], True
