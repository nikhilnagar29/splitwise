"""schemas/message_schema.py — Pydantic models for message endpoints."""

from pydantic import BaseModel, field_validator


class PostMessageRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_valid(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message content cannot be blank.")
        if len(v) > 500:
            raise ValueError("Message content must be 500 characters or fewer.")
        return v


class MessageOut(BaseModel):
    id:         int
    expense_id: int
    user_id:    int
    content:    str
    created_at: str
