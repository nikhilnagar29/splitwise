"""
routers/balance_router.py — Balance and debt simplification endpoints.

GET /groups/{group_id}/balances            raw pairwise balances
GET /groups/{group_id}/balances/simplified debt-simplified view
GET /users/me/summary                      cross-group individual summary
"""

import sqlite3
from typing import List

from fastapi import APIRouter, Depends

from auth import get_current_user
from balance_manager import BalanceManager
from dependencies import get_db
from models.user import User
from schemas.balance_schema import (
    BalanceEntry,
    RawBalancesOut,
    SimplifiedBalancesOut,
    SimplifiedTransaction,
    UserSummaryEntry,
    UserSummaryOut,
)
from simplifier import DebtSimplifier

router = APIRouter(tags=["balances"])


# ── GET /groups/{group_id}/balances ───────────────────────────────────────────

@router.get(
    "/groups/{group_id}/balances",
    response_model=RawBalancesOut,
    summary="Raw pairwise balances for a group",
)
def get_group_balances(
    group_id:     int,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> RawBalancesOut:
    raw = BalanceManager.get_group_balances(group_id, conn)
    entries = [
        BalanceEntry(debtor_id=debtor, creditor_id=creditor, amount=amount)
        for (debtor, creditor), amount in raw.items()
    ]
    return RawBalancesOut(group_id=group_id, balances=entries)


# ── GET /groups/{group_id}/balances/simplified ────────────────────────────────

@router.get(
    "/groups/{group_id}/balances/simplified",
    response_model=SimplifiedBalancesOut,
    summary="Debt-simplified transactions for a group",
)
def get_simplified_balances(
    group_id:     int,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> SimplifiedBalancesOut:
    raw          = BalanceManager.get_group_balances(group_id, conn)
    transactions = DebtSimplifier.simplify(raw)
    return SimplifiedBalancesOut(
        group_id=group_id,
        transactions=[
            SimplifiedTransaction(payer_id=p, receiver_id=r, amount=a)
            for p, r, a in transactions
        ],
    )


# ── GET /users/me/summary ─────────────────────────────────────────────────────

@router.get(
    "/users/me/summary",
    response_model=UserSummaryOut,
    summary="Cross-group individual balance summary for the logged-in user",
)
def get_user_summary(
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> UserSummaryOut:
    summary = BalanceManager.get_user_summary(current_user.id, conn)
    return UserSummaryOut(
        user_id=current_user.id,
        summary=[
            UserSummaryEntry(other_user_id=uid, net_amount=amt)
            for uid, amt in summary.items()
        ],
    )
