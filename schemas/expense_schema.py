"""schemas/expense_schema.py — Pydantic models for expense endpoints."""

from typing import List, Optional
from pydantic import BaseModel, field_validator
from models.enums import SplitType


class AddExpenseRequest(BaseModel):
    description: str
    amount:      float
    paid_by:     int
    split_type:  SplitType
    user_ids:    List[int]
    values:      List[float] = []

    @field_validator("description")
    @classmethod
    def desc_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Description cannot be blank.")
        return v.strip()

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Amount must be positive.")
        return v


class EditExpenseRequest(BaseModel):
    description: str
    amount:      float
    paid_by:     int
    split_type:  SplitType
    user_ids:    List[int]
    values:      List[float] = []

    @field_validator("description")
    @classmethod
    def desc_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Description cannot be blank.")
        return v.strip()

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Amount must be positive.")
        return v


class SplitOut(BaseModel):
    user_id:     int
    amount_owed: float


class ExpenseOut(BaseModel):
    id:          int
    group_id:    int
    description: str
    amount:      float
    paid_by:     int
    split_type:  str
    created_by:  int
    created_at:  str
    splits:      Optional[List[SplitOut]] = None
