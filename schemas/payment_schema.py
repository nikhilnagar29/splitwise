"""schemas/payment_schema.py — Pydantic models for payment endpoints."""

from typing import Optional
from pydantic import BaseModel, field_validator


class RecordPaymentRequest(BaseModel):
    from_user_id: int
    to_user_id:   int
    amount:       float
    notes:        Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Payment amount must be positive.")
        return v

    @field_validator("notes")
    @classmethod
    def notes_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.strip()) > 200:
            raise ValueError("Notes must be 200 characters or fewer.")
        return v.strip() if v else None


class PaymentOut(BaseModel):
    id:           int
    group_id:     int
    from_user_id: int
    to_user_id:   int
    amount:       float
    notes:        Optional[str]
    created_at:   str
