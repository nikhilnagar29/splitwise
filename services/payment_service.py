"""
services/payment_service.py — Recording full debt settlements.

Rules (AI_CONTEXT.md § 11):
  - Full settlement only — payment.amount must exactly equal the outstanding
    raw pairwise balance (within ±0.01 tolerance for float rounding).
  - Payment reduces the raw (group, from_user, to_user) balance row directly.
  - No partial payments.
  - Both parties must be members of the group.

All functions accept an open sqlite3.Connection.
Errors are raised as ValueError with descriptive messages.
"""

import sqlite3
from typing import List

from models.payment import Payment
from balance_manager import BalanceManager
from services.group_service import _get_role

_TOLERANCE = 0.01   # 1 cent tolerance for float comparison


# ── Public API ─────────────────────────────────────────────────────────────────

def record_payment(
    group_id:     int,
    from_user_id: int,
    to_user_id:   int,
    amount:       float,
    conn:         sqlite3.Connection,
    notes:        str = None,
) -> Payment:
    """
    Record a full debt settlement and update balances.

    Args:
        group_id:     Group scope of the settlement.
        from_user_id: Debtor — the user paying.
        to_user_id:   Creditor — the user receiving.
        amount:       Settlement amount (must equal outstanding balance).
        conn:         Open DB connection.
        notes:        Optional note, max 200 chars.

    Returns:
        Payment with id and created_at filled in.

    Raises:
        ValueError: Either user not in group, no outstanding debt in this
                    direction, or amount doesn't match outstanding balance.
    """
    if amount <= 0:
        raise ValueError(f"Payment amount must be positive, got {amount}.")

    if from_user_id == to_user_id:
        raise ValueError("A user cannot pay themselves.")

    # Validate notes length.
    if notes is not None:
        notes = notes.strip() or None
        if notes and len(notes) > 200:
            raise ValueError(f"Notes must be 200 characters or fewer (got {len(notes)}).")

    # Both users must be group members.
    if _get_role(group_id, from_user_id, conn) is None:
        raise ValueError(f"User {from_user_id} is not a member of group {group_id}.")
    if _get_role(group_id, to_user_id, conn) is None:
        raise ValueError(f"User {to_user_id} is not a member of group {group_id}.")

    # Check outstanding raw pairwise balance.
    balance_row = conn.execute(
        "SELECT amount FROM balances "
        "WHERE group_id = %s AND user_id = %s AND owes_user_id = %s",
        (group_id, from_user_id, to_user_id),
    ).fetchone()

    if not balance_row:
        raise ValueError(
            f"User {from_user_id} has no outstanding debt to user {to_user_id} "
            f"in group {group_id}."
        )

    outstanding = balance_row["amount"]
    if abs(outstanding - amount) > _TOLERANCE:
        raise ValueError(
            f"Full settlement required. Outstanding balance is {outstanding:.2f} "
            f"but payment amount is {amount:.2f}. "
            f"Difference of {abs(outstanding - amount):.4f} exceeds tolerance of {_TOLERANCE}."
        )

    # Build payment object.
    payment = Payment(
        group_id=group_id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        amount=amount,
        notes=notes,
    )

    # Apply to balances (will delete the row since it reaches zero).
    BalanceManager.apply_payment(payment, conn)

    # Persist payment record.
    row = conn.execute(
        """
        INSERT INTO payments (group_id, from_user_id, to_user_id, amount, notes)
        VALUES (%s, %s, %s, %s, %s) RETURNING id, created_at
        """,
        (group_id, from_user_id, to_user_id, amount, notes),
    ).fetchone()

    payment.id         = row["id"]
    payment.created_at = row["created_at"]
    return payment


def list_group_payments(group_id: int, conn: sqlite3.Connection) -> List[Payment]:
    """Return all payments for a group, ordered by created_at descending."""
    rows = conn.execute(
        """
        SELECT id, group_id, from_user_id, to_user_id, amount, notes, created_at
        FROM payments
        WHERE group_id = %s
        ORDER BY created_at DESC
        """,
        (group_id,),
    ).fetchall()

    return [
        Payment(
            id=row["id"],
            group_id=row["group_id"],
            from_user_id=row["from_user_id"],
            to_user_id=row["to_user_id"],
            amount=row["amount"],
            notes=row["notes"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
