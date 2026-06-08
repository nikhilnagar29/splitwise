"""
models/message.py — Message dataclass.

Maps 1-to-1 with the `messages` table (AI_CONTEXT.md § 9).
No business logic — pure data container.

Real-time chat per expense. Messages are:
  - Persisted permanently — no delete operation exists anywhere in the codebase.
  - Preserved during expense EDIT (only splits are deleted/recreated; the expense
    row is UPDATEd in-place, so ON DELETE CASCADE is never triggered).
  - Removed via ON DELETE CASCADE only when the parent expense is hard-deleted.

Fields:
  id         — auto-assigned by DB on insert; None before first save.
  expense_id — FK → expenses.id (ON DELETE CASCADE).
  user_id    — FK → users.id; the author.
  content    — message body; max 500 chars (enforced in service + DB CHECK).
  created_at — ISO-8601 string from SQLite DEFAULT CURRENT_TIMESTAMP.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Message:
    expense_id: int
    user_id:    int         # FK → users.id
    content:    str         # max 500 chars
    id:         Optional[int] = field(default=None)
    created_at: Optional[str] = field(default=None)

    def __repr__(self) -> str:
        preview = self.content[:40] + "..." if len(self.content) > 40 else self.content
        return f"Message(id={self.id}, user_id={self.user_id}, content={preview!r})"
