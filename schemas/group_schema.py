"""schemas/group_schema.py — Pydantic models for group endpoints."""

from typing import List, Optional
from pydantic import BaseModel, field_validator


class CreateGroupRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Group name cannot be blank.")
        return v.strip()


class RenameGroupRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Group name cannot be blank.")
        return v.strip()


class AddMemberRequest(BaseModel):
    email: str   # add by email; user must already be registered


class GroupMemberOut(BaseModel):
    user_id:    int
    name:       str
    email:      str
    role:       str


class GroupOut(BaseModel):
    id:          int
    name:        str
    created_by:  int
    created_at:  str
    members:     Optional[List[GroupMemberOut]] = None
