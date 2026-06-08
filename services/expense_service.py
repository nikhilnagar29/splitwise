"""
services/expense_service.py — Expense creation, editing, and deletion.

Core logic (AI_CONTEXT.md § 11):
  add_expense:
    1. Validate all participants are group members.
    2. Validate paid_by and created_by are group members.
    3. Compute splits via SplitFactory + strategy (raises ValueError on bad input).
    4. INSERT expense row.
    5. INSERT split rows.
    6. BalanceManager.apply_expense(expense, splits, conn).

  edit_expense:
    1. Fetch expense; verify it exists.
    2. Check permission: requesting user is creator OR group admin.
    3. BalanceManager.reverse_expense(expense_id, conn)  ← reads splits BEFORE deletion.
    4. DELETE FROM splits WHERE expense_id = X          ← splits only; expense row stays.
       Messages are NOT deleted — they survive edits permanently.
    5. Compute new splits via strategy.
    6. UPDATE expense row in-place.
    7. INSERT new split rows.
    8. BalanceManager.apply_expense(updated_expense, new_splits, conn).

  delete_expense:
    1. Fetch expense; verify it exists.
    2. Check permission: requesting user is creator OR group admin.
    3. BalanceManager.reverse_expense(expense_id, conn)  ← reads splits BEFORE deletion.
    4. DELETE expense row  → CASCADE deletes splits + messages.

All functions accept an open sqlite3.Connection.
Errors are raised as ValueError with descriptive messages.
"""

import sqlite3
from typing import List, Optional

from models.enums import Role, SplitType
from models.expense import Expense
from models.split import Split
from balance_manager import BalanceManager
from factory import SplitFactory
from services.group_service import _get_role


# ── Internal helpers ───────────────────────────────────────────────────────────

def _row_to_expense(row: sqlite3.Row) -> Expense:
    return Expense(
        id=row["id"],
        group_id=row["group_id"],
        description=row["description"],
        amount=row["amount"],
        paid_by=row["paid_by"],
        split_type=SplitType(row["split_type"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def _check_expense_permission(
    expense:            Expense,
    requesting_user_id: int,
    conn:               sqlite3.Connection,
) -> None:
    """Raise ValueError if requesting_user is neither the creator nor a group admin."""
    if requesting_user_id == expense.created_by:
        return
    role = _get_role(expense.group_id, requesting_user_id, conn)
    if role == Role.ADMIN:
        return
    raise ValueError(
        f"User {requesting_user_id} does not have permission to modify expense {expense.id}. "
        "Only the expense creator or group admin can do this."
    )


def _validate_participants(
    group_id:  int,
    user_ids:  List[int],
    paid_by:   int,
    conn:      sqlite3.Connection,
) -> None:
    """Raise ValueError if any participant (including paid_by) is not a group member."""
    all_ids = set(user_ids) | {paid_by}
    for uid in all_ids:
        role = _get_role(group_id, uid, conn)
        if role is None:
            raise ValueError(
                f"User {uid} is not a member of group {group_id} "
                "and cannot be part of this expense."
            )


# ── Public API ─────────────────────────────────────────────────────────────────

def add_expense(
    group_id:    int,
    description: str,
    amount:      float,
    paid_by:     int,
    split_type:  SplitType,
    user_ids:    List[int],   # participants in the split
    values:      List[float], # strategy-specific input
    created_by:  int,
    conn:        sqlite3.Connection,
) -> Expense:
    """
    Add a new expense and update balances.

    Args:
        group_id:    Group this expense belongs to.
        description: Human-readable label.
        amount:      Total amount (> 0).
        paid_by:     User who fronted the money.
        split_type:  How to divide the expense.
        user_ids:    Participants (including payer if they share the cost).
        values:      Strategy-specific; see SplitStrategy.calculate() docstring.
        created_by:  User entering the expense.
        conn:        Open DB connection.

    Returns:
        Expense with id and created_at filled in.

    Raises:
        ValueError: Invalid amount, participants not in group, bad split values.
    """
    description = description.strip()
    if not description:
        raise ValueError("Expense description cannot be blank.")
    if amount <= 0:
        raise ValueError(f"Expense amount must be positive, got {amount}.")
    if not user_ids:
        raise ValueError("Expense must have at least one participant.")

    _validate_participants(group_id, user_ids, paid_by, conn)

    # Strategy raises ValueError if values are invalid.
    strategy = SplitFactory.get(split_type)
    # Temporary expense_id=0 for split computation; real id assigned after INSERT.
    proto_splits = strategy.calculate(0, amount, user_ids, values)

    # INSERT expense row — RETURNING id, created_at avoids a second query.
    row = conn.execute(
        """
        INSERT INTO expenses (group_id, description, amount, paid_by, split_type, created_by)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, created_at
        """,
        (group_id, description, amount, paid_by, split_type.value, created_by),
    ).fetchone()
    expense_id = row["id"]

    # INSERT split rows with real expense_id.
    splits: List[Split] = []
    for ps in proto_splits:
        conn.execute(
            "INSERT INTO splits (expense_id, user_id, amount_owed) VALUES (%s, %s, %s)",
            (expense_id, ps.user_id, ps.amount_owed),
        )
        splits.append(Split(expense_id=expense_id, user_id=ps.user_id, amount_owed=ps.amount_owed))

    expense = Expense(
        id=row["id"],
        group_id=group_id,
        description=description,
        amount=amount,
        paid_by=paid_by,
        split_type=split_type,
        created_by=created_by,
        created_at=row["created_at"],
    )

    BalanceManager.apply_expense(expense, splits, conn)
    return expense


def edit_expense(
    expense_id:         int,
    description:        str,
    amount:             float,
    paid_by:            int,
    split_type:         SplitType,
    user_ids:           List[int],
    values:             List[float],
    requesting_user_id: int,
    conn:               sqlite3.Connection,
) -> Expense:
    """
    Edit an existing expense.

    Messages on the expense are preserved — the expense row is UPDATEd in-place,
    not deleted, so ON DELETE CASCADE on messages is never triggered.

    Raises:
        ValueError: Expense not found, permission denied, or invalid split values.
    """
    description = description.strip()
    if not description:
        raise ValueError("Expense description cannot be blank.")
    if amount <= 0:
        raise ValueError(f"Expense amount must be positive, got {amount}.")
    if not user_ids:
        raise ValueError("Expense must have at least one participant.")

    expense_row = conn.execute(
        "SELECT * FROM expenses WHERE id = %s", (expense_id,)
    ).fetchone()
    if not expense_row:
        raise ValueError(f"Expense {expense_id} does not exist.")

    old_expense = _row_to_expense(expense_row)
    _check_expense_permission(old_expense, requesting_user_id, conn)
    _validate_participants(old_expense.group_id, user_ids, paid_by, conn)

    # Step 1: reverse old balance deltas (reads splits before deletion).
    BalanceManager.reverse_expense(expense_id, conn)

    # Step 2: delete old splits ONLY — not the expense row (preserves messages).
    conn.execute("DELETE FROM splits WHERE expense_id = %s", (expense_id,))

    # Step 3: compute new splits (raises ValueError on bad input).
    strategy    = SplitFactory.get(split_type)
    proto_splits = strategy.calculate(expense_id, amount, user_ids, values)

    # Step 4: update expense row in-place.
    conn.execute(
        """
        UPDATE expenses
        SET description = %s, amount = %s, paid_by = %s, split_type = %s
        WHERE id = %s
        """,
        (description, amount, paid_by, split_type.value, expense_id),
    )

    # Step 5: insert new splits.
    new_splits: List[Split] = []
    for ps in proto_splits:
        conn.execute(
            "INSERT INTO splits (expense_id, user_id, amount_owed) VALUES (%s, %s, %s)",
            (expense_id, ps.user_id, ps.amount_owed),
        )
        new_splits.append(Split(expense_id=expense_id, user_id=ps.user_id, amount_owed=ps.amount_owed))

    updated_expense = Expense(
        id=expense_id,
        group_id=old_expense.group_id,
        description=description,
        amount=amount,
        paid_by=paid_by,
        split_type=split_type,
        created_by=old_expense.created_by,
        created_at=old_expense.created_at,
    )

    # Step 6: apply new balance deltas.
    BalanceManager.apply_expense(updated_expense, new_splits, conn)
    return updated_expense


def delete_expense(
    expense_id:         int,
    requesting_user_id: int,
    conn:               sqlite3.Connection,
) -> None:
    """
    Delete an expense. Cascade-deletes its splits and messages.

    Permission: expense creator OR group admin.

    Raises:
        ValueError: Expense not found or permission denied.
    """
    expense_row = conn.execute(
        "SELECT * FROM expenses WHERE id = %s", (expense_id,)
    ).fetchone()
    if not expense_row:
        raise ValueError(f"Expense {expense_id} does not exist.")

    expense = _row_to_expense(expense_row)
    _check_expense_permission(expense, requesting_user_id, conn)

    # Reverse balance deltas BEFORE deleting (reads splits from DB).
    BalanceManager.reverse_expense(expense_id, conn)

    # Hard delete — ON DELETE CASCADE removes splits and messages.
    conn.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))


def get_expense(expense_id: int, conn: sqlite3.Connection) -> Optional[Expense]:
    """Return an Expense by ID, or None if not found."""
    row = conn.execute("SELECT * FROM expenses WHERE id = %s", (expense_id,)).fetchone()
    return _row_to_expense(row) if row else None


def list_group_expenses(group_id: int, conn: sqlite3.Connection) -> List[Expense]:
    """Return all expenses for a group, ordered by created_at descending."""
    rows = conn.execute(
        "SELECT * FROM expenses WHERE group_id = %s ORDER BY created_at DESC",
        (group_id,),
    ).fetchall()
    return [_row_to_expense(r) for r in rows]


def get_expense_splits(expense_id: int, conn: sqlite3.Connection) -> List[Split]:
    """Return all splits for an expense, ordered by user_id."""
    rows = conn.execute(
        "SELECT id, expense_id, user_id, amount_owed FROM splits WHERE expense_id = %s ORDER BY user_id",
        (expense_id,),
    ).fetchall()
    return [
        Split(id=r["id"], expense_id=r["expense_id"], user_id=r["user_id"], amount_owed=r["amount_owed"])
        for r in rows
    ]

def list_user_expenses(user_id: int, conn: sqlite3.Connection) -> List[Expense]:
    """Return all expenses in all groups the user is a member of, ordered by created_at descending."""
    rows = conn.execute(
        """
        SELECT e.id, e.group_id, e.description, e.amount, e.paid_by, 
               e.split_type, e.created_by, e.created_at
        FROM expenses e
        JOIN group_members gm ON e.group_id = gm.group_id
        WHERE gm.user_id = %s
        ORDER BY e.created_at DESC
        """,
        (user_id,),
    ).fetchall()
    return [_row_to_expense(r) for r in rows]
