"""
models/expense.py — Expense dataclass.

Maps 1-to-1 with the `expenses` table (AI_CONTEXT.md § 9).
No business logic — pure data container.

Fields:
  id          — auto-assigned by DB on insert; None before first save.
  group_id    — FK → groups.id.
  description — human-readable label (e.g. "Dinner at Zomato").
  amount      — total expense amount in the group's currency (> 0).
  paid_by     — FK → users.id; the person who fronted the money.
  split_type  — SplitType enum value stored as its .value string in DB.
  created_by  — FK → users.id; the person who entered the expense.
  created_at  — ISO-8601 string from SQLite DEFAULT CURRENT_TIMESTAMP.
"""

from dataclasses import dataclass, field
from typing import Optional
from models.enums import SplitType


@dataclass
class Expense:
    group_id:    int
    description: str
    amount:      float
    paid_by:     int        # FK → users.id
    split_type:  SplitType
    created_by:  int        # FK → users.id
    id:          Optional[int] = field(default=None)
    created_at:  Optional[str] = field(default=None)

    def __repr__(self) -> str:
        return (
            f"Expense(id={self.id}, description={self.description!r}, "
            f"amount={self.amount}, split_type={self.split_type.value!r})"
        )
