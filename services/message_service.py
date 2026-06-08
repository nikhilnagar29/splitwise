"""
services/message_service.py — Expense chat messages.

Rules (AI_CONTEXT.md § 9, messages):
  - Max 500 characters per message (enforced here AND by DB CHECK).
  - No delete operation — messages are permanent once posted.
  - Messages survive expense edits (expense row is UPDATEd, not deleted).
  - Messages are removed only via ON DELETE CASCADE when an expense is
    hard-deleted through delete_expense().
  - The user posting must be a member of the group that owns the expense.

All functions accept an open sqlite3.Connection.
Errors are raised as ValueError with descriptive messages.
"""

import sqlite3
from typing import List

from models.message import Message
from services.group_service import _get_role

_MAX_CONTENT_LENGTH = 500


# ── Public API ─────────────────────────────────────────────────────────────────

def post_message(
    expense_id: int,
    user_id:    int,
    content:    str,
    conn:       sqlite3.Connection,
) -> Message:
    """
    Post a chat message on an expense.

    Args:
        expense_id: Expense to comment on (must exist).
        user_id:    Author (must be a member of the expense's group).
        content:    Message body (non-empty, max 500 chars).
        conn:       Open DB connection.

    Returns:
        Message with id and created_at filled in.

    Raises:
        ValueError: Expense not found, user not in group, content blank or too long.
    """
    content = content.strip()
    if not content:
        raise ValueError("Message content cannot be blank.")
    if len(content) > _MAX_CONTENT_LENGTH:
        raise ValueError(
            f"Message content exceeds {_MAX_CONTENT_LENGTH} characters "
            f"(got {len(content)})."
        )

    # Verify expense exists and get its group_id.
    expense_row = conn.execute(
        "SELECT group_id FROM expenses WHERE id = %s", (expense_id,)
    ).fetchone()
    if not expense_row:
        raise ValueError(f"Expense {expense_id} does not exist.")

    group_id = expense_row["group_id"]

    # Verify user is a group member.
    if _get_role(group_id, user_id, conn) is None:
        raise ValueError(
            f"User {user_id} is not a member of group {group_id} "
            "and cannot post on this expense."
        )

    row = conn.execute(
        "INSERT INTO messages (expense_id, user_id, content) VALUES (%s, %s, %s) RETURNING id, created_at",
        (expense_id, user_id, content),
    ).fetchone()

    return Message(
        id=row["id"],
        expense_id=expense_id,
        user_id=user_id,
        content=content,
        created_at=row["created_at"],
    )


def get_messages(expense_id: int, conn: sqlite3.Connection) -> List[Message]:
    """
    Return all messages for an expense, ordered by created_at ascending
    (chronological order for chat display).

    Args:
        expense_id: Expense whose chat history to load.
        conn:       Open DB connection.

    Returns:
        List[Message] — empty list if no messages or expense doesn't exist.
    """
    rows = conn.execute(
        """
        SELECT id, expense_id, user_id, content, created_at
        FROM messages
        WHERE expense_id = %s
        ORDER BY created_at ASC
        """,
        (expense_id,),
    ).fetchall()

    return [
        Message(
            id=row["id"],
            expense_id=row["expense_id"],
            user_id=row["user_id"],
            content=row["content"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
