"""
routers/payment_router.py — Debt settlement endpoints.

POST /groups/{group_id}/payments   record a full settlement
GET  /groups/{group_id}/payments   list all payments in a group
"""

import sqlite3
from typing import List

from fastapi import APIRouter, Depends, status

from auth import get_current_user
from dependencies import get_db, service_call
from models.user import User
from schemas.payment_schema import PaymentOut, RecordPaymentRequest
from services import payment_service

router = APIRouter(tags=["payments"])


# ── POST /groups/{group_id}/payments ─────────────────────────────────────────

@router.post(
    "/groups/{group_id}/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record a full debt settlement",
)
def record_payment(
    group_id:     int,
    body:         RecordPaymentRequest,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> PaymentOut:
    payment = service_call(
        payment_service.record_payment,
        group_id,
        body.from_user_id,
        body.to_user_id,
        body.amount,
        conn,
        body.notes,
    )
    return PaymentOut(
        id=payment.id,
        group_id=payment.group_id,
        from_user_id=payment.from_user_id,
        to_user_id=payment.to_user_id,
        amount=payment.amount,
        notes=payment.notes,
        created_at=payment.created_at,
    )


# ── GET /groups/{group_id}/payments ──────────────────────────────────────────

@router.get(
    "/groups/{group_id}/payments",
    response_model=List[PaymentOut],
    summary="List all payments in a group",
)
def list_payments(
    group_id:     int,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> List[PaymentOut]:
    payments = payment_service.list_group_payments(group_id, conn)
    return [
        PaymentOut(
            id=p.id,
            group_id=p.group_id,
            from_user_id=p.from_user_id,
            to_user_id=p.to_user_id,
            amount=p.amount,
            notes=p.notes,
            created_at=p.created_at,
        )
        for p in payments
    ]
