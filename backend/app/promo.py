"""Promo codes.

Two behaviours, depending on the percentage:
  * 100% — pure DB grant. `profiles.pro_until` is pushed forward by a month or a
    year and the user has Pro immediately, with no Stripe involvement at all
    (so these work even before Stripe keys are configured).
  * 1-99% — recorded as an unconsumed redemption; the discount is then applied
    to that user's next Stripe Checkout session (see app/billing.py), because a
    partial discount only means anything against a real charge.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException

from .db import get_db

CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,31}$")


def normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def duration_delta(duration: str) -> timedelta:
    # Calendar-month precision isn't worth a dateutil dependency here; 30/365 days
    # is what the admin UI promises ("1 oy" / "1 yil").
    return timedelta(days=365) if duration == "year" else timedelta(days=30)


def _parse_ts(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def load_code(code: str) -> Optional[dict]:
    response = get_db().table("promo_codes").select("*").eq("code", code).limit(1).execute()
    return response.data[0] if response.data else None


def _assert_redeemable(promo: dict, user: dict) -> None:
    if not promo.get("active"):
        raise HTTPException(status_code=400, detail="Bu promokod faolsizlantirilgan.")

    expires_at = _parse_ts(promo.get("expires_at"))
    if expires_at and expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Bu promokodning muddati tugagan.")

    max_redemptions = promo.get("max_redemptions")
    if max_redemptions is not None and (promo.get("redemption_count") or 0) >= max_redemptions:
        raise HTTPException(status_code=400, detail="Bu promokod ishlatilish limitiga yetgan.")

    already = (
        get_db()
        .table("promo_redemptions")
        .select("id")
        .eq("code", promo["code"])
        .eq("user_id", user["user_id"])
        .limit(1)
        .execute()
    )
    if already.data:
        raise HTTPException(status_code=400, detail="Siz bu promokoddan allaqachon foydalangansiz.")


def redeem(raw_code: str, user: dict) -> dict:
    code = normalize_code(raw_code)
    if not code:
        raise HTTPException(status_code=400, detail="Promokodni kiriting.")

    promo = load_code(code)
    if not promo:
        raise HTTPException(status_code=404, detail="Bunday promokod topilmadi.")

    _assert_redeemable(promo, user)

    db = get_db()
    percent = promo["discount_percent"]
    duration = promo["duration"]
    grants_until = None

    if percent >= 100:
        # Extend from the later of "now" and any Pro time the user already has,
        # so stacking codes never shortens existing access.
        current = _parse_ts(user.get("pro_until"))
        base = max(datetime.now(timezone.utc), current) if current else datetime.now(timezone.utc)
        grants_until = base + duration_delta(duration)
        db.table("profiles").update(
            {"pro_until": grants_until.isoformat()}
        ).eq("user_id", user["user_id"]).execute()

    db.table("promo_redemptions").insert({
        "code": code,
        "user_id": user["user_id"],
        "discount_percent": percent,
        "duration": duration,
        "grants_until": grants_until.isoformat() if grants_until else None,
        "consumed": percent >= 100,
    }).execute()

    db.table("promo_codes").update(
        {"redemption_count": (promo.get("redemption_count") or 0) + 1}
    ).eq("code", code).execute()

    if percent >= 100:
        human_duration = "1 yil" if duration == "year" else "1 oy"
        return {
            "status": "granted",
            "discount_percent": percent,
            "duration": duration,
            "pro_until": grants_until.isoformat(),
            "message": f"Tabriklaymiz! Pro obuna {human_duration} muddatga bepul faollashtirildi.",
        }

    return {
        "status": "discount_pending",
        "discount_percent": percent,
        "duration": duration,
        "message": (
            f"Promokod qabul qilindi: {percent}% chegirma. "
            "To'lovga o'tganingizda chegirma avtomatik qo'llanadi."
        ),
    }


def pending_discount(user_id: str) -> Optional[dict]:
    """The unconsumed partial-discount redemption to apply at checkout, if any."""
    response = (
        get_db()
        .table("promo_redemptions")
        .select("*")
        .eq("user_id", user_id)
        .eq("consumed", False)
        .order("redeemed_at", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def mark_consumed(redemption_id: int) -> None:
    get_db().table("promo_redemptions").update({"consumed": True}).eq("id", redemption_id).execute()


# ─── Admin-side management ────────────────────────────────────────────────────

def create_code(
    code: str,
    discount_percent: int,
    duration: str,
    max_redemptions: Optional[int] = None,
    expires_at: Optional[str] = None,
    note: Optional[str] = None,
) -> dict:
    normalized = normalize_code(code)
    if not CODE_PATTERN.match(normalized):
        raise HTTPException(
            status_code=400,
            detail="Promokod 3-32 belgidan iborat bo'lishi va faqat harf, raqam, _ yoki - dan tashkil topishi kerak.",
        )
    if not 1 <= discount_percent <= 100:
        raise HTTPException(status_code=400, detail="Chegirma 1 dan 100 foizgacha bo'lishi kerak.")
    if duration not in ("month", "year"):
        raise HTTPException(status_code=400, detail="Muddat 'month' yoki 'year' bo'lishi kerak.")
    if max_redemptions is not None and max_redemptions < 1:
        raise HTTPException(status_code=400, detail="Limit kamida 1 bo'lishi kerak.")

    if load_code(normalized):
        raise HTTPException(status_code=409, detail="Bu promokod allaqachon mavjud.")

    inserted = (
        get_db()
        .table("promo_codes")
        .insert({
            "code": normalized,
            "discount_percent": discount_percent,
            "duration": duration,
            "max_redemptions": max_redemptions,
            "expires_at": expires_at,
            "note": note,
        })
        .execute()
    )
    return inserted.data[0]


def list_codes() -> list:
    response = (
        get_db()
        .table("promo_codes")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def set_active(code: str, active: bool) -> dict:
    normalized = normalize_code(code)
    updated = (
        get_db()
        .table("promo_codes")
        .update({"active": active})
        .eq("code", normalized)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=404, detail="Promokod topilmadi.")
    return updated.data[0]


def delete_code(code: str) -> None:
    normalized = normalize_code(code)
    get_db().table("promo_codes").delete().eq("code", normalized).execute()
