"""
routers/group_router.py — Group management endpoints.

POST   /groups                            create group
GET    /groups                            list logged-in user's groups
GET    /groups/{group_id}                 group detail + member list
PATCH  /groups/{group_id}                 rename group (admin only)
POST   /groups/{group_id}/members         add member by email (admin only)
DELETE /groups/{group_id}/members/{uid}   remove member (admin only)
"""

import sqlite3
from typing import List

from fastapi import APIRouter, Depends, status

from auth import get_current_user
from dependencies import get_db, service_call
from models.user import User
from schemas.group_schema import (
    AddMemberRequest,
    CreateGroupRequest,
    GroupMemberOut,
    GroupOut,
    RenameGroupRequest,
)
from services import group_service

router = APIRouter(tags=["groups"])


def _build_group_out(group, conn: sqlite3.Connection, include_members: bool = False) -> GroupOut:
    members_out = None
    if include_members:
        members = group_service.get_members(group.id, conn)
        members_out = [
            GroupMemberOut(user_id=u.id, name=u.name, email=u.email, role=r.value)
            for u, r in members
        ]
    return GroupOut(
        id=group.id,
        name=group.name,
        created_by=group.created_by,
        created_at=group.created_at,
        members=members_out,
    )


# ── POST /groups ───────────────────────────────────────────────────────────────

@router.post(
    "/groups",
    response_model=GroupOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new group",
)
def create_group(
    body:         CreateGroupRequest,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> GroupOut:
    group = service_call(group_service.create_group, body.name, current_user.id, conn)
    return _build_group_out(group, conn, include_members=True)


# ── GET /groups ────────────────────────────────────────────────────────────────

@router.get(
    "/groups",
    response_model=List[GroupOut],
    summary="List all groups for the logged-in user",
)
def list_groups(
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> List[GroupOut]:
    groups = group_service.list_user_groups(current_user.id, conn)
    return [_build_group_out(g, conn, include_members=False) for g in groups]


# ── GET /groups/{group_id} ─────────────────────────────────────────────────────

@router.get(
    "/groups/{group_id}",
    response_model=GroupOut,
    summary="Get group details and member list",
)
def get_group(
    group_id:     int,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> GroupOut:
    group = service_call(group_service.get_group, group_id, conn)
    if group is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Group {group_id} does not exist.")
    # Verify the requesting user is a member.
    service_call(group_service._require_member, group_id, current_user.id, conn)
    return _build_group_out(group, conn, include_members=True)


# ── PATCH /groups/{group_id} ───────────────────────────────────────────────────

@router.patch(
    "/groups/{group_id}",
    response_model=GroupOut,
    summary="Rename a group (admin only)",
)
def rename_group(
    group_id:     int,
    body:         RenameGroupRequest,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> GroupOut:
    group = service_call(group_service.rename_group, group_id, body.name, current_user.id, conn)
    return _build_group_out(group, conn, include_members=True)


# ── POST /groups/{group_id}/members ───────────────────────────────────────────

@router.post(
    "/groups/{group_id}/members",
    status_code=status.HTTP_201_CREATED,
    summary="Add a member by email (admin only)",
)
def add_member(
    group_id:     int,
    body:         AddMemberRequest,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> dict:
    service_call(group_service.add_member_by_email, group_id, body.email, current_user.id, conn)
    return {"detail": f"User with email '{body.email}' added to group {group_id}."}


# ── DELETE /groups/{group_id}/members/{user_id} ────────────────────────────────

@router.delete(
    "/groups/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member (admin only)",
)
def remove_member(
    group_id:     int,
    user_id:      int,
    current_user: User               = Depends(get_current_user),
    conn:         sqlite3.Connection = Depends(get_db),
) -> None:
    service_call(group_service.remove_member, group_id, user_id, current_user.id, conn)
