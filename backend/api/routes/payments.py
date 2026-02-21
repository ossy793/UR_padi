# backend/api/routes/payments.py
"""
Demo Paystack payment integration.
Paystack docs: https://paystack.com/docs/api/
"""
import uuid
import httpx

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.user import User, Payment
from schemas.user import PaymentInitiate, PaymentVerify
from api.deps import get_current_user
from core.config import settings

router = APIRouter(prefix="/payments", tags=["Payments"])

PAYSTACK_BASE = "https://api.paystack.co"


@router.post("/initiate")
async def initiate_payment(
    payload: PaymentInitiate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate a Paystack transaction.
    Returns the authorization_url for the user to complete payment.
    """
    reference = f"hp-{current_user.id}-{uuid.uuid4().hex[:8]}"

    # ── Demo mode: skip Paystack entirely if no live key is configured ────────
    is_demo = (
        not settings.PAYSTACK_SECRET_KEY
        or settings.PAYSTACK_SECRET_KEY.startswith("sk_test_your")
    )

    if is_demo:
        # Record pending payment so verify endpoint can find it
        payment = Payment(
            user_id=current_user.id,
            reference=reference,
            amount=payload.amount,
            status="pending",
        )
        db.add(payment)
        await db.commit()
        return {
            "status": "demo",
            "reference": reference,
            "authorization_url": f"https://checkout.paystack.com/demo/{reference}",
            "message": "Demo mode — set PAYSTACK_SECRET_KEY for live transactions",
        }

    # ── Live mode: call Paystack API ──────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{PAYSTACK_BASE}/transaction/initialize",
                headers={
                    "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "email": current_user.email,
                    "amount": int(payload.amount * 100),   # Paystack uses kobo
                    "reference": reference,
                    "callback_url": "http://localhost:8000/api/payments/verify",
                    "metadata": {
                        "user_id": current_user.id,
                        "plan": "premium",
                    },
                },
            )
    except (httpx.ConnectTimeout, httpx.ConnectError):
        raise HTTPException(503, "Could not reach Paystack. Check your internet connection.")

    if resp.status_code != 200:
        raise HTTPException(400, f"Paystack error: {resp.text}")

    data = resp.json()
    # Record pending payment
    payment = Payment(
        user_id=current_user.id,
        reference=reference,
        amount=payload.amount,
        status="pending",
    )
    db.add(payment)
    await db.commit()

    return {
        "reference": reference,
        "authorization_url": data["data"]["authorization_url"],
        "access_code": data["data"]["access_code"],
    }


@router.post("/verify")
async def verify_payment(
    payload: PaymentVerify,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify a Paystack transaction and activate premium if successful.
    """
    from sqlalchemy import select, update

    result = await db.execute(
        select(Payment).where(
            Payment.reference == payload.reference,
            Payment.user_id == current_user.id,
        )
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Payment record not found.")

    # Verify with Paystack
    is_demo = (
        not settings.PAYSTACK_SECRET_KEY
        or settings.PAYSTACK_SECRET_KEY.startswith("sk_test_your")
    )

    if is_demo:
        # Demo: auto-approve without calling Paystack
        payment.status = "success"
        current_user.is_premium = True
        await db.commit()
        return {"status": "success", "message": "Demo: Premium activated!", "is_premium": True}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{PAYSTACK_BASE}/transaction/verify/{payload.reference}",
                headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
            )
    except (httpx.ConnectTimeout, httpx.ConnectError):
        raise HTTPException(503, "Could not reach Paystack. Check your internet connection.")

    data = resp.json()
    if data["data"]["status"] == "success":
        payment.status = "success"
        payment.paystack_data = data["data"]
        current_user.is_premium = True
        await db.commit()
        return {"status": "success", "message": "Premium activated!", "is_premium": True}

    payment.status = "failed"
    await db.commit()
    raise HTTPException(400, "Payment verification failed.")