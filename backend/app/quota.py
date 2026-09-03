"""Free-plan metering. Only AI calls are metered — the Formula Library and the
Formula Test panel run entirely in the browser and cost nothing, so they stay
unlimited and don't even reach this module.
"""
import os
from datetime import datetime, timezone

from fastapi import HTTPException

from .db import get_db

FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", "5"))


def has_unlimited_access(user: dict) -> bool:
    if user.get("is_owner"):
        return True
    if user.get("plan") == "pro":
        return True
    pro_until = user.get("pro_until")
    if pro_until:
        try:
            expiry = datetime.fromisoformat(str(pro_until).replace("Z", "+00:00"))
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            return expiry > datetime.now(timezone.utc)
        except ValueError:
            return False
    return False


def usage_today(user_id: str) -> int:
    start_of_day = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")
    response = (
        get_db()
        .table("usage_events")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .gte("created_at", start_of_day)
        .execute()
    )
    return response.count or 0


def record_usage(user_id: str) -> None:
    get_db().table("usage_events").insert({"user_id": user_id}).execute()


def enforce_ai_quota(user: dict) -> None:
    """Raises 402 with `upgrade_required` once a free user is out of daily calls.
    Records the usage event on success, so callers must invoke this immediately
    before making the AI request."""
    if has_unlimited_access(user):
        record_usage(user["user_id"])
        return

    used = usage_today(user["user_id"])
    if used >= FREE_DAILY_LIMIT:
        raise HTTPException(
            status_code=402,
            detail={
                "upgrade_required": True,
                "limit": FREE_DAILY_LIMIT,
                "message": (
                    f"Kunlik bepul limit tugadi ({FREE_DAILY_LIMIT} ta so'rov). "
                    "Cheksiz foydalanish uchun Pro obunaga o'ting yoki promokod kiriting."
                ),
            },
        )
    record_usage(user["user_id"])


def quota_status(user: dict) -> dict:
    """Shape the frontend uses to render the remaining-calls badge."""
    if has_unlimited_access(user):
        return {"unlimited": True, "used": 0, "limit": None, "remaining": None}
    used = usage_today(user["user_id"])
    return {
        "unlimited": False,
        "used": used,
        "limit": FREE_DAILY_LIMIT,
        "remaining": max(0, FREE_DAILY_LIMIT - used),
    }
