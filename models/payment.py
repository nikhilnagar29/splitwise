"""
models/payment.py — Payment (settlement) dataclass.

Maps 1-to-1 with the `payments` table (AI_CONTEXT.md § 9).
No business logic — pure data container.

Represents a full settlement of a raw pairwise balance.
Partial payments are out of scope (AI_CONTEXT.md § 7).

Fields:
  id           — auto-assigned by DB on insert; None before first save.
  group_id     — FK → groups.id; scope of the settlement.
  from_user_id — FK → users.id; the person who paid (debtor settling up).
  to_user_id   — FK → users.id; the person who received (creditor).
  amount       — the settled amount (> 0, must equal outstanding balance).
  notes        — optional free-text note, max 200 chars (e.g. "Paid via UPI").
  created_at   — ISO-8601 string from SQLite DEFAULT CURRENT_TIMESTAMP.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Payment:
    group_id:     int
    from_user_id: int           # FK → users.id (payer / debtor)
    to_user_id:   int           # FK → users.id (receiver / creditor)
    amount:       float         # > 0
    notes:        Optional[str] = field(default=None)   # max 200 chars
    id:           Optional[int] = field(default=None)
    created_at:   Optional[str] = field(default=None)

    def __repr__(self) -> str:
        return (
            f"Payment(id={self.id}, from={self.from_user_id}, "
            f"to={self.to_user_id}, amount={self.amount})"
        )
