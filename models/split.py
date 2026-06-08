"""
models/split.py — Split dataclass.

Maps 1-to-1 with the `splits` table (AI_CONTEXT.md § 9).
No business logic — pure data container.

A Split represents one user's pre-computed share of a single expense.
Rows are hard-deleted when the parent expense is deleted (ON DELETE CASCADE).
Rows are manually deleted and recreated when an expense is edited —
the expense row itself is only UPDATEd, so messages are not affected.

Fields:
  id           — auto-assigned by DB on insert; None before first save.
  expense_id   — FK → expenses.id (ON DELETE CASCADE).
  user_id      — FK → users.id; the user who owes this share.
  amount_owed  — the pre-computed amount this user owes (>= 0).
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Split:
    expense_id:  int
    user_id:     int        # FK → users.id
    amount_owed: float      # >= 0; validated by the strategy before creation
    id:          Optional[int] = field(default=None)

    def __repr__(self) -> str:
        return (
            f"Split(id={self.id}, expense_id={self.expense_id}, "
            f"user_id={self.user_id}, amount_owed={self.amount_owed})"
        )
