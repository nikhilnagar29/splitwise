"""schemas/balance_schema.py — Pydantic models for balance endpoints."""

from typing import Dict, List
from pydantic import BaseModel


class BalanceEntry(BaseModel):
    debtor_id:   int
    creditor_id: int
    amount:      float


class RawBalancesOut(BaseModel):
    group_id: int
    balances: List[BalanceEntry]


class SimplifiedTransaction(BaseModel):
    payer_id:    int
    receiver_id: int
    amount:      float


class SimplifiedBalancesOut(BaseModel):
    group_id:     int
    transactions: List[SimplifiedTransaction]


class UserSummaryEntry(BaseModel):
    other_user_id: int
    net_amount:    float   # positive = owed to me, negative = I owe them


class UserSummaryOut(BaseModel):
    user_id: int
    summary: List[UserSummaryEntry]
