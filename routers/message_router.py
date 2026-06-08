"""
routers/message_router.py — Expense chat message endpoints.

POST /expenses/{expense_id}/messages         post a message
GET  /expenses/{expense_id}/messages         get message history
GET  /expenses/{expense_id}/messages/stream  SSE stream for real-time updates

SSE stream design (SQLite — no broker):
  1. Verify access once at connection time.
  2. Emit all existing messages immediately.
  3. Poll the DB every 1 second for messages newer than last_id.
  4. Send each new message as a JSON-encoded SSE data frame.
  5. Client disconnect causes asyncio.CancelledError → generator exits cleanly.

SSE frame format:
  data: {"id": 1, "expense_id": 5, "user_id": 2, "content": "...", "created_at": "..."}
  (blank line)
"""

import asyncio
import json
import sqlite3
from typing import AsyncGenerator, List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from auth import get_current_user
from dependencies import _get_pg_connection, get_db, service_call
from models.user import User
from schemas.message_schema import MessageOut, PostMessageRequest
from services import message_service
from services.group_service import get_member_role

router = APIRouter(tags=["messages"])


# ── POST /expenses/{expense_id}/messages ──────────────────────────────────────

@router.post(
    "/expenses/{expense_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
    summary="Post a chat message on an expense",
)
def post_message(
    expense_id:   int,
    body:         PostMessageRequest,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> MessageOut:
    msg = service_call(
        message_service.post_message,
        expense_id,
        current_user.id,
        body.content,
        conn,
    )
    return MessageOut(
        id=msg.id,
        expense_id=msg.expense_id,
        user_id=msg.user_id,
        content=msg.content,
        created_at=msg.created_at,
    )


# ── GET /expenses/{expense_id}/messages ───────────────────────────────────────

@router.get(
    "/expenses/{expense_id}/messages",
    response_model=List[MessageOut],
    summary="Get chat history for an expense",
)
def get_messages(
    expense_id:   int,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> List[MessageOut]:
    msgs = message_service.get_messages(expense_id, conn)
    return [
        MessageOut(
            id=m.id,
            expense_id=m.expense_id,
            user_id=m.user_id,
            content=m.content,
            created_at=m.created_at,
        )
        for m in msgs
    ]


# ── GET /expenses/{expense_id}/messages/stream ────────────────────────────────

async def _sse_generator(expense_id: int) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE frames.
    Polls the DB every second for new messages after the last seen id.
    """
    last_id = 0

    # Emit all existing messages immediately on connect.
    with _get_pg_connection() as conn:
        rows = conn.execute(
            "SELECT id, expense_id, user_id, content, created_at "
            "FROM messages WHERE expense_id = %s ORDER BY created_at ASC",
            (expense_id,),
        ).fetchall()

    for row in rows:
        last_id = row["id"]
        payload = json.dumps({
            "id":         row["id"],
            "expense_id": row["expense_id"],
            "user_id":    row["user_id"],
            "content":    row["content"],
            "created_at": row["created_at"],
        })
        yield f"data: {payload}\n\n"

    # Poll for new messages until the client disconnects.
    while True:
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            return   # client disconnected cleanly

        with _get_pg_connection() as conn:
            rows = conn.execute(
                "SELECT id, expense_id, user_id, content, created_at "
                "FROM messages WHERE expense_id = %s AND id > %s ORDER BY created_at ASC",
                (expense_id, last_id),
            ).fetchall()

        for row in rows:
            last_id = row["id"]
            payload = json.dumps({
                "id":         row["id"],
                "expense_id": row["expense_id"],
                "user_id":    row["user_id"],
                "content":    row["content"],
                "created_at": row["created_at"],
            })
            yield f"data: {payload}\n\n"


@router.get(
    "/expenses/{expense_id}/messages/stream",
    summary="SSE stream for real-time expense chat updates",
    response_class=StreamingResponse,
)
async def stream_messages(
    expense_id:   int,
    current_user: User               = Depends(get_current_user),
) -> StreamingResponse:
    """
    Server-Sent Events stream.
    Connect with:
        EventSource('/expenses/{id}/messages/stream', {headers: {Authorization: 'Bearer <token>'}})

    Access check: user must be a member of the group that owns this expense.
    Check happens once at connection time — not re-validated per poll.
    """
    with _get_pg_connection() as conn:
        expense_row = conn.execute(
            "SELECT group_id FROM expenses WHERE id = %s", (expense_id,)
        ).fetchone()
        if not expense_row:
            raise HTTPException(status_code=404, detail=f"Expense {expense_id} does not exist.")

        role = get_member_role(expense_row["group_id"], current_user.id, conn)
        if role is None:
            raise HTTPException(
                status_code=403,
                detail="You are not a member of the group that owns this expense.",
            )

    return StreamingResponse(
        _sse_generator(expense_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx proxy buffering
            "Connection":       "keep-alive",
        },
    )
