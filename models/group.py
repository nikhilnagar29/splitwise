"""
models/group.py — Group dataclass.

Maps 1-to-1 with the `groups` table (AI_CONTEXT.md § 9).
No business logic — pure data container.

Fields:
  id         — auto-assigned by DB on insert; None before first save.
  name       — display name of the group.
  created_by — user_id of the group creator (automatically set as admin).
  created_at — ISO-8601 string from SQLite DEFAULT CURRENT_TIMESTAMP.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Group:
    name:       str
    created_by: int               # FK → users.id
    id:         Optional[int] = field(default=None)
    created_at: Optional[str] = field(default=None)

    def __repr__(self) -> str:
        return f"Group(id={self.id}, name={self.name!r}, created_by={self.created_by})"
