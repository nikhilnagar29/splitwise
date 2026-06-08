"""
routers/expense_router.py — Expense management endpoints.

POST   /groups/{group_id}/expenses                       add expense
GET    /groups/{group_id}/expenses                       list expenses in group
GET    /groups/{group_id}/expenses/{expense_id}          expense detail + splits
PUT    /groups/{group_id}/expenses/{expense_id}          edit expense (creator or admin)
DELETE /groups/{group_id}/expenses/{expense_id}          delete expense (creator or admin)
"""

import sqlite3
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from auth import get_current_user
from dependencies import get_db, service_call
from models.enums import SplitType
from models.user import User
from schemas.expense_schema import AddExpenseRequest, EditExpenseRequest, ExpenseOut, SplitOut
from services import expense_service

router = APIRouter(tags=["expenses"])


def _expense_to_out(expense, splits=None) -> ExpenseOut:
    splits_out = None
    if splits is not None:
        splits_out = [SplitOut(user_id=s.user_id, amount_owed=s.amount_owed) for s in splits]
    return ExpenseOut(
        id=expense.id,
        group_id=expense.group_id,
        description=expense.description,
        amount=expense.amount,
        paid_by=expense.paid_by,
        split_type=expense.split_type.value,
        created_by=expense.created_by,
        created_at=expense.created_at,
        splits=splits_out,
    )


# ── POST /groups/{group_id}/expenses ──────────────────────────────────────────

@router.post(
    "/groups/{group_id}/expenses",
    response_model=ExpenseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new expense",
)
def add_expense(
    group_id:     int,
    body:         AddExpenseRequest,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> ExpenseOut:
    expense = service_call(
        expense_service.add_expense,
        group_id,
        body.description,
        body.amount,
        body.paid_by,
        body.split_type,
        body.user_ids,
        body.values,
        current_user.id,
        conn,
    )
    splits = expense_service.get_expense_splits(expense.id, conn)
    return _expense_to_out(expense, splits)


# ── GET /groups/{group_id}/expenses ───────────────────────────────────────────

@router.get(
    "/groups/{group_id}/expenses",
    response_model=List[ExpenseOut],
    summary="List all expenses in a group",
)
def list_expenses(
    group_id:     int,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> List[ExpenseOut]:
    expenses = service_call(expense_service.list_group_expenses, group_id, conn)
    return [_expense_to_out(e) for e in expenses]


# ── GET /groups/{group_id}/expenses/{expense_id} ──────────────────────────────

@router.get(
    "/groups/{group_id}/expenses/{expense_id}",
    response_model=ExpenseOut,
    summary="Get expense detail with splits",
)
def get_expense(
    group_id:     int,
    expense_id:   int,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> ExpenseOut:
    expense = expense_service.get_expense(expense_id, conn)
    if expense is None or expense.group_id != group_id:
        raise HTTPException(status_code=404, detail=f"Expense {expense_id} does not exist.")
    splits = expense_service.get_expense_splits(expense_id, conn)
    return _expense_to_out(expense, splits)


# ── PUT /groups/{group_id}/expenses/{expense_id} ──────────────────────────────

@router.put(
    "/groups/{group_id}/expenses/{expense_id}",
    response_model=ExpenseOut,
    summary="Edit an expense (creator or admin only)",
)
def edit_expense(
    group_id:     int,
    expense_id:   int,
    body:         EditExpenseRequest,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> ExpenseOut:
    expense = service_call(
        expense_service.edit_expense,
        expense_id,
        body.description,
        body.amount,
        body.paid_by,
        body.split_type,
        body.user_ids,
        body.values,
        current_user.id,
        conn,
    )
    splits = expense_service.get_expense_splits(expense_id, conn)
    return _expense_to_out(expense, splits)


# ── DELETE /groups/{group_id}/expenses/{expense_id} ───────────────────────────

@router.delete(
    "/groups/{group_id}/expenses/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an expense (creator or admin only)",
)
def delete_expense(
    group_id:     int,
    expense_id:   int,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> None:
    service_call(expense_service.delete_expense, expense_id, current_user.id, conn)


# ── GET /users/me/expenses ────────────────────────────────────────────────────

@router.get(
    "/users/me/expenses",
    response_model=List[ExpenseOut],
    summary="List all expenses for the logged-in user across all groups",
)
def list_user_expenses(
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> List[ExpenseOut]:
    expenses = expense_service.list_user_expenses(current_user.id, conn)
    return [_expense_to_out(e) for e in expenses]
