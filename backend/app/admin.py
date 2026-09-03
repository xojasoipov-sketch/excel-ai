"""Owner-only reporting: who signed up, who pays, how much came in, plus the
payout-card field. Every function here is reached through `require_owner`.
"""
from datetime import datetime, timedelta, timezone

from .billing import PLAN_PRICE_USD
from .db import get_db
from .quota import has_unlimited_access
from .security import decrypt_secret, encrypt_secret


def _iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def get_stats() -> dict:
    db = get_db()
    profiles = (
        db.table("profiles")
        .select("user_id,email,plan,is_owner,pro_until,created_at")
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )

    paying = [p for p in profiles if p.get("plan") == "pro" and not p.get("is_owner")]
    promo_pro = [
        p for p in profiles
        if not p.get("is_owner")
        and p.get("plan") != "pro"
        and has_unlimited_access(p)
    ]

    payments = (
        db.table("payments")
        .select("amount_cents,currency,status,created_at")
        .eq("status", "paid")
        .execute()
        .data
        or []
    )
    total_cents = sum((p.get("amount_cents") or 0) for p in payments)
    month_cents = sum(
        (p.get("amount_cents") or 0)
        for p in payments
        if (p.get("created_at") or "") >= _iso_days_ago(30)
    )

    ai_calls_today = (
        db.table("usage_events")
        .select("id", count="exact")
        .gte("created_at", datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00"))
        .execute()
        .count
        or 0
    )

    return {
        "total_users": len(profiles),
        "paying_users": len(paying),
        "promo_pro_users": len(promo_pro),
        "free_users": len(profiles) - len(paying) - len(promo_pro),
        "mrr_usd": round(len(paying) * PLAN_PRICE_USD, 2),
        "revenue_total_usd": round(total_cents / 100, 2),
        "revenue_30d_usd": round(month_cents / 100, 2),
        "ai_calls_today": ai_calls_today,
        "signups_7d": len([p for p in profiles if (p.get("created_at") or "") >= _iso_days_ago(7)]),
        "recent_users": profiles[:10],
    }


def list_users(limit: int = 100, offset: int = 0) -> dict:
    response = (
        get_db()
        .table("profiles")
        .select("user_id,email,plan,is_owner,pro_until,stripe_customer_id,created_at", count="exact")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return {"users": response.data or [], "total": response.count or 0}


def list_payments(limit: int = 50) -> list:
    return (
        get_db()
        .table("payments")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )


def get_payout_card() -> str:
    row = (
        get_db()
        .table("admin_settings")
        .select("payout_card_encrypted")
        .eq("id", True)
        .limit(1)
        .execute()
    )
    if not row.data or not row.data[0].get("payout_card_encrypted"):
        return ""
    return decrypt_secret(row.data[0]["payout_card_encrypted"])


def set_payout_card(card_number: str) -> None:
    cleaned = "".join(ch for ch in (card_number or "") if ch.isdigit())
    encrypted = encrypt_secret(cleaned) if cleaned else None
    get_db().table("admin_settings").update({
        "payout_card_encrypted": encrypted,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", True).execute()
