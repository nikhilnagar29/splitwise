"""
models/user.py — User dataclass.

Maps 1-to-1 with the `users` table (AI_CONTEXT.md § 9).
No business logic here — pure data container.

Fields:
  id              — auto-assigned by DB on insert; None before first save.
  name            — display name.
  email           — unique login identifier.
  hashed_password — bcrypt hash; never store plaintext.
  created_at      — ISO-8601 string from SQLite DEFAULT CURRENT_TIMESTAMP.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class User:
    name:             str
    email:            str
    hashed_password:  str
    id:               Optional[int] = field(default=None)
    created_at:       Optional[str] = field(default=None)

    def __repr__(self) -> str:
        return f"User(id={self.id}, name={self.name!r}, email={self.email!r})"
