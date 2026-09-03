"""Stripe subscription billing for the $5/month Pro plan.

Everything here degrades gracefully when Stripe keys aren't configured yet: the
endpoints return a clear 503 instead of crashing, so the site (and 100%-off promo
codes, which never touch Stripe) works before billing is switched on.
"""
import os
from typing import Optional

import stripe
from fastapi import HTTPException

from . import promo
from .db import get_db

PRICE_ID = os.getenv("STRIPE_PRICE_ID", "").strip()
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
SITE_URL = (os.getenv("SITE_URL") or "http://localhost:5173").rstrip("/")
PLAN_PRICE_USD = float(os.getenv("PLAN_PRICE_USD", "5"))


def _api_key() -> str:
    return (os.getenv("STRIPE_SECRET_KEY") or "").strip()


def is_configured() -> bool:
    return bool(_api_key() and PRICE_ID)


def _require_configured() -> None:
    if not is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Karta orqali to'lov hali sozlanmagan. Admin STRIPE_SECRET_KEY va "
                "STRIPE_PRICE_ID ni kiritishi kerak. Promokod bilan Pro'ni hozir ham ochish mumkin."
            ),
        )
    stripe.api_key = _api_key()


def _ensure_customer(user: dict) -> str:
    if user.get("stripe_customer_id"):
        return user["stripe_customer_id"]

    customer = stripe.Customer.create(
        email=user.get("email") or None,
        metadata={"user_id": user["user_id"]},
    )
    get_db().table("profiles").update(
        {"stripe_customer_id": customer.id}
    ).eq("user_id", user["user_id"]).execute()
    return customer.id


def _coupon_for(discount_percent: int, duration: str) -> str:
    """Reuse one Stripe coupon per (percent, duration) pair rather than creating a
    new one per redemption. `repeating`/12 months mirrors our 'year' duration."""
    coupon_id = f"uz-{discount_percent}off-{duration}"
    try:
        return stripe.Coupon.retrieve(coupon_id).id
    except stripe.error.InvalidRequestError:
        pass

    params = {
        "id": coupon_id,
        "percent_off": discount_percent,
        "name": f"{discount_percent}% chegirma ({'1 yil' if duration == 'year' else '1 oy'})",
    }
    if duration == "year":
        params.update({"duration": "repeating", "duration_in_months": 12})
    else:
        params.update({"duration": "once"})
    return stripe.Coupon.create(**params).id


def create_checkout_session(user: dict) -> dict:
    _require_configured()
    customer_id = _ensure_customer(user)

    session_args = {
        "mode": "subscription",
        "customer": customer_id,
        # Explicit rather than relying on the Stripe dashboard's default payment
        # methods list, which is empty until the account finishes activation.
        "payment_method_types": ["card"],
        "line_items": [{"price": PRICE_ID, "quantity": 1}],
        "success_url": f"{SITE_URL}/billing?checkout=success",
        "cancel_url": f"{SITE_URL}/billing?checkout=cancelled",
        "metadata": {"user_id": user["user_id"]},
        "allow_promotion_codes": True,
    }

    # If they redeemed a partial promo code on our side, attach it as a real
    # Stripe discount. Stripe rejects `discounts` + `allow_promotion_codes`
    # together, so the manual coupon wins when one is pending.
    pending = promo.pending_discount(user["user_id"])
    if pending:
        try:
            coupon_id = _coupon_for(pending["discount_percent"], pending["duration"])
            session_args["discounts"] = [{"coupon": coupon_id}]
            session_args.pop("allow_promotion_codes", None)
            session_args["metadata"]["promo_redemption_id"] = str(pending["id"])
        except stripe.error.StripeError as exc:
            print(f"Promo coupon could not be applied, continuing without it: {exc}")

    session = stripe.checkout.Session.create(**session_args)
    return {"url": session.url}


def create_portal_session(user: dict) -> dict:
    _require_configured()
    if not user.get("stripe_customer_id"):
        raise HTTPException(status_code=400, detail="Sizda hali karta orqali obuna mavjud emas.")

    session = stripe.billing_portal.Session.create(
        customer=user["stripe_customer_id"],
        return_url=f"{SITE_URL}/billing",
    )
    return {"url": session.url}


def _profile_by_customer(customer_id: Optional[str]) -> Optional[dict]:
    if not customer_id:
        return None
    response = (
        get_db()
        .table("profiles")
        .select("user_id")
        .eq("stripe_customer_id", customer_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def handle_webhook(payload: bytes, signature: Optional[str]) -> dict:
    if not WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="STRIPE_WEBHOOK_SECRET sozlanmagan.")
    stripe.api_key = _api_key()

    try:
        event = stripe.Webhook.construct_event(payload, signature, WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Webhook imzosi noto'g'ri.")

    db = get_db()
    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        plan = "pro" if obj.get("status") in ("active", "trialing") else "free"
        db.table("profiles").update({
            "plan": plan,
            "stripe_subscription_id": obj.get("id"),
        }).eq("stripe_customer_id", obj.get("customer")).execute()

    elif event_type == "customer.subscription.deleted":
        db.table("profiles").update({
            "plan": "free",
            "stripe_subscription_id": None,
        }).eq("stripe_customer_id", obj.get("customer")).execute()

    elif event_type == "checkout.session.completed":
        redemption_id = (obj.get("metadata") or {}).get("promo_redemption_id")
        if redemption_id:
            try:
                promo.mark_consumed(int(redemption_id))
            except (TypeError, ValueError):
                pass

    elif event_type in ("invoice.paid", "invoice.payment_failed"):
        profile = _profile_by_customer(obj.get("customer"))
        # Upsert on the unique stripe_event_id so Stripe's webhook retries don't
        # insert the same payment twice.
        db.table("payments").upsert({
            "user_id": profile["user_id"] if profile else None,
            "stripe_event_id": event["id"],
            "type": event_type,
            "amount_cents": obj.get("amount_paid") if event_type == "invoice.paid" else obj.get("amount_due"),
            "currency": obj.get("currency"),
            "status": "paid" if event_type == "invoice.paid" else "failed",
        }, on_conflict="stripe_event_id").execute()

    return {"received": True, "type": event_type}
