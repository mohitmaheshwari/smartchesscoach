"""
Razorpay billing routes.

Two-step checkout:

    1. POST /billing/create-order
        Creates a Razorpay order on the server, returns the order_id +
        amount + key_id. Frontend hands these to Razorpay Checkout.js.

    2. POST /billing/verify-payment
        After Checkout completes, frontend posts back the
        razorpay_payment_id + razorpay_order_id + razorpay_signature.
        We verify the HMAC signature against our key_secret to confirm
        the payment is real, then mark the user as Pro.

The signature check is what makes this secure: anyone can hit
/verify-payment with arbitrary IDs, but only Razorpay can produce a
signature that validates against our secret. Skip this check and a
user could fake an upgrade with a curl call.

Test mode: while RAZORPAY_KEY_ID starts with "rzp_test_", every order
is in Razorpay's sandbox. Use card `4111 1111 1111 1111` with any
future expiry and any CVV during checkout. Real money never moves.
"""

import os
import hmac
import hashlib
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from routes.auth import get_current_user, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing"])

db = None

def set_db(database):
    global db
    db = database


# ==================== CONFIG ====================

# Pro plan price. Razorpay amounts are in paise (1 INR = 100 paise).
# Tune via env if/when pricing changes.
PRO_PLAN_PRICE_PAISE = int(os.environ.get("PRO_PLAN_PRICE_PAISE", "49900"))  # ₹499
PRO_PLAN_CURRENCY = "INR"
PRO_PLAN_NAME = "ChessGuru Pro — Monthly"


def _client():
    """Lazy-construct the Razorpay client so the import doesn't break in
    environments without the keys (e.g., dev)."""
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    if not key_id or not key_secret:
        raise HTTPException(
            status_code=503,
            detail="Payments are not configured on this environment.",
        )
    import razorpay
    return razorpay.Client(auth=(key_id, key_secret)), key_id, key_secret


# ==================== MODELS ====================

class CreateOrderRequest(BaseModel):
    plan: str = "pro_monthly"


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str
    plan_name: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


# ==================== ROUTES ====================

@router.get("/config")
async def billing_config():
    """Lightweight endpoint the frontend can call to know whether
    payments are wired up before it shows the Pay button."""
    enabled = bool(os.environ.get("RAZORPAY_KEY_ID")) and bool(
        os.environ.get("RAZORPAY_KEY_SECRET")
    )
    return {
        "enabled": enabled,
        "currency": PRO_PLAN_CURRENCY,
        "amount": PRO_PLAN_PRICE_PAISE,
        "plan_name": PRO_PLAN_NAME,
        "test_mode": (os.environ.get("RAZORPAY_KEY_ID", "").startswith("rzp_test_")),
    }


@router.post("/create-order", response_model=CreateOrderResponse)
async def create_order(
    req: CreateOrderRequest,
    user: User = Depends(get_current_user),
):
    """Create a Razorpay order and return the handoff payload."""
    client, key_id, _ = _client()

    # Razorpay receipt is a free-form string; useful for our reconciliation.
    receipt = f"u_{user.user_id[:24]}"

    try:
        order = client.order.create({
            "amount": PRO_PLAN_PRICE_PAISE,
            "currency": PRO_PLAN_CURRENCY,
            "receipt": receipt,
            "notes": {
                "user_id": user.user_id,
                "email": user.email,
                "plan": req.plan,
            },
        })
    except Exception as e:
        logger.error(f"Razorpay order creation failed for {user.user_id}: {e}")
        raise HTTPException(status_code=502, detail="Could not initiate payment. Please try again.")

    # Persist a payment-intent record so /verify-payment can correlate
    # the signature back to the user without trusting the client-sent
    # user_id.
    await db.payment_intents.insert_one({
        "order_id": order["id"],
        "user_id": user.user_id,
        "email": user.email,
        "amount": PRO_PLAN_PRICE_PAISE,
        "currency": PRO_PLAN_CURRENCY,
        "plan": req.plan,
        "status": "created",
        "created_at": order.get("created_at"),
    })

    logger.info(f"Razorpay order created: {order['id']} for {user.user_id}")

    return CreateOrderResponse(
        order_id=order["id"],
        amount=PRO_PLAN_PRICE_PAISE,
        currency=PRO_PLAN_CURRENCY,
        key_id=key_id,
        plan_name=PRO_PLAN_NAME,
    )


def _verify_signature(order_id: str, payment_id: str, signature: str, secret: str) -> bool:
    """Razorpay's documented HMAC-SHA256 check.

    Body = "{order_id}|{payment_id}", key = key_secret. Signature is
    hex-encoded and compared in constant time.
    """
    body = f"{order_id}|{payment_id}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/verify-payment")
async def verify_payment(
    req: VerifyPaymentRequest,
    user: User = Depends(get_current_user),
):
    """Confirm payment, then upgrade the user to Pro."""
    _, _, key_secret = _client()

    if not _verify_signature(
        req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature, key_secret
    ):
        logger.warning(
            f"Signature mismatch on order {req.razorpay_order_id} from user {user.user_id}"
        )
        raise HTTPException(status_code=400, detail="Payment verification failed.")

    # Cross-check the order belongs to this user before upgrading.
    intent = await db.payment_intents.find_one(
        {"order_id": req.razorpay_order_id},
        {"_id": 0},
    )
    if not intent or intent.get("user_id") != user.user_id:
        logger.warning(
            f"Order {req.razorpay_order_id} not found or owner mismatch (user={user.user_id})"
        )
        raise HTTPException(status_code=400, detail="Order does not match this user.")

    # Idempotent: if we've already marked this order paid, return success.
    if intent.get("status") == "paid":
        return {"status": "already_paid", "plan": "pro"}

    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    await db.payment_intents.update_one(
        {"order_id": req.razorpay_order_id},
        {"$set": {
            "status": "paid",
            "payment_id": req.razorpay_payment_id,
            "paid_at": now_iso,
        }},
    )

    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {
            "plan": "pro",
            "plan_start_date": now_iso,
            "monthly_analyses_used": 0,
            "analyses_reset_date": now_iso,
        }},
    )

    logger.info(f"User {user.user_id} upgraded to Pro via order {req.razorpay_order_id}")
    return {"status": "ok", "plan": "pro"}
