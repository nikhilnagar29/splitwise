"""
services/group_service.py — Group creation, membership, and renaming.

Permission rules (AI_CONTEXT.md § 9, group_members):
  - Only admin can add a new member, remove a member, or rename the group.
  - Admin cannot remove themselves (one admin per group; no transfer).
  - Group creator is inserted as admin automatically on creation.

All functions accept an open sqlite3.Connection from get_connection().
Errors are raised as ValueError with descriptive messages.
"""

import sqlite3
from typing import List, Optional, Tuple

from models.enums import Role
from models.group import Group
from models.user import User


# ── Internal helpers ───────────────────────────────────────────────────────────

def _get_role(group_id: int, user_id: int, conn: sqlite3.Connection) -> Optional[Role]:
    """Return the Role of user_id in group_id, or None if not a member."""
    row = conn.execute(
        "SELECT role FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, user_id),
    ).fetchone()
    return Role(row["role"]) if row else None


def _require_member(group_id: int, user_id: int, conn: sqlite3.Connection) -> Role:
    """Return the role or raise ValueError if user is not in the group."""
    role = _get_role(group_id, user_id, conn)
    if role is None:
        raise ValueError(
            f"User {user_id} is not a member of group {group_id}."
        )
    return role


def _require_admin(group_id: int, user_id: int, conn: sqlite3.Connection) -> None:
    """Raise ValueError if user is not admin of the group."""
    role = _require_member(group_id, user_id, conn)
    if role != Role.ADMIN:
        raise ValueError(
            f"User {user_id} is not an admin of group {group_id}. "
            "Only admins can perform this action."
        )


# ── Public API ─────────────────────────────────────────────────────────────────

def create_group(
    name:       str,
    creator_id: int,
    conn:       sqlite3.Connection,
) -> Group:
    """
    Create a new group and insert the creator as admin.

    Raises:
        ValueError: If name is blank or creator does not exist.
    """
    name = name.strip()
    if not name:
        raise ValueError("Group name cannot be blank.")

    creator = conn.execute("SELECT id FROM users WHERE id = %s", (creator_id,)).fetchone()
    if not creator:
        raise ValueError(f"User {creator_id} does not exist.")

    row = conn.execute(
        "INSERT INTO groups (name, created_by) VALUES (%s, %s) RETURNING id, created_at",
        (name, creator_id),
    ).fetchone()
    group_id = row["id"]

    conn.execute(
        "INSERT INTO group_members (group_id, user_id, role) VALUES (%s, %s, %s)",
        (group_id, creator_id, Role.ADMIN.value),
    )

    return Group(id=row["id"], name=name, created_by=creator_id, created_at=row["created_at"])


def get_group(group_id: int, conn: sqlite3.Connection) -> Optional[Group]:
    """Return a Group by ID, or None if not found."""
    row = conn.execute(
        "SELECT id, name, created_by, created_at FROM groups WHERE id = %s",
        (group_id,),
    ).fetchone()
    if not row:
        return None
    return Group(
        id=row["id"],
        name=row["name"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def list_user_groups(user_id: int, conn: sqlite3.Connection) -> List[Group]:
    """Return all groups the user belongs to, ordered by created_at DESC."""
    rows = conn.execute(
        """
        SELECT g.id, g.name, g.created_by, g.created_at
        FROM groups g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE gm.user_id = %s
        ORDER BY g.created_at DESC
        """,
        (user_id,),
    ).fetchall()
    return [
        Group(id=r["id"], name=r["name"], created_by=r["created_by"], created_at=r["created_at"])
        for r in rows
    ]


def get_members(
    group_id: int,
    conn:     sqlite3.Connection,
) -> List[Tuple[User, Role]]:
    """Return all members of a group with their roles, ordered by joined_at ASC."""
    rows = conn.execute(
        """
        SELECT u.id, u.name, u.email, u.hashed_password, u.created_at,
               gm.role
        FROM group_members gm
        JOIN users u ON u.id = gm.user_id
        WHERE gm.group_id = %s
        ORDER BY gm.joined_at ASC
        """,
        (group_id,),
    ).fetchall()

    return [
        (
            User(
                id=row["id"],
                name=row["name"],
                email=row["email"],
                hashed_password=row["hashed_password"],
                created_at=row["created_at"],
            ),
            Role(row["role"]),
        )
        for row in rows
    ]


def get_member_role(
    group_id: int,
    user_id:  int,
    conn:     sqlite3.Connection,
) -> Optional[Role]:
    """Public accessor: return a user's role in a group, or None if not a member."""
    return _get_role(group_id, user_id, conn)


def add_member(
    group_id:           int,
    new_user_id:        int,
    requesting_user_id: int,
    conn:               sqlite3.Connection,
) -> None:
    """
    Add a registered user to a group. Admin only.

    Raises:
        ValueError: If requester is not admin, new user doesn't exist,
                    or new user is already a member.
    """
    _require_admin(group_id, requesting_user_id, conn)

    new_user = conn.execute("SELECT id FROM users WHERE id = %s", (new_user_id,)).fetchone()
    if not new_user:
        raise ValueError(f"User {new_user_id} does not exist.")

    already = _get_role(group_id, new_user_id, conn)
    if already is not None:
        raise ValueError(f"User {new_user_id} is already a member of group {group_id}.")

    conn.execute(
        "INSERT INTO group_members (group_id, user_id, role) VALUES (%s, %s, %s)",
        (group_id, new_user_id, Role.MEMBER.value),
    )


def add_member_by_email(
    group_id:           int,
    email:              str,
    requesting_user_id: int,
    conn:               sqlite3.Connection,
) -> None:
    """
    Add a user to a group by their email address. Admin only.
    User must already be registered — no email invites (AI_CONTEXT.md § 7).

    Raises:
        ValueError: Requester not admin, email not found, or already a member.
    """
    _require_admin(group_id, requesting_user_id, conn)

    email = email.strip().lower()
    user_row = conn.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()
    if not user_row:
        raise ValueError(
            f"No user with email '{email}' is registered. "
            "They must create an account first."
        )

    new_user_id = user_row["id"]
    already = _get_role(group_id, new_user_id, conn)
    if already is not None:
        raise ValueError(
            f"User with email '{email}' is already a member of group {group_id}."
        )

    conn.execute(
        "INSERT INTO group_members (group_id, user_id, role) VALUES (%s, %s, %s)",
        (group_id, new_user_id, Role.MEMBER.value),
    )


def remove_member(
    group_id:           int,
    target_user_id:     int,
    requesting_user_id: int,
    conn:               sqlite3.Connection,
) -> None:
    """
    Remove a member from a group. Admin only.

    Raises:
        ValueError: If requester is not admin, target is not a member,
                    or target is the admin.
    """
    _require_admin(group_id, requesting_user_id, conn)

    target_role = _get_role(group_id, target_user_id, conn)
    if target_role is None:
        raise ValueError(f"User {target_user_id} is not a member of group {group_id}.")

    if target_role == Role.ADMIN:
        raise ValueError(
            "Cannot remove the group admin. "
            "Admin transfer is not supported."
        )

    conn.execute(
        "DELETE FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, target_user_id),
    )


def rename_group(
    group_id:           int,
    new_name:           str,
    requesting_user_id: int,
    conn:               sqlite3.Connection,
) -> Group:
    """
    Rename a group. Admin only.

    Raises:
        ValueError: If requester is not admin or new name is blank.
    """
    _require_admin(group_id, requesting_user_id, conn)

    new_name = new_name.strip()
    if not new_name:
        raise ValueError("Group name cannot be blank.")

    conn.execute(
        "UPDATE groups SET name = %s WHERE id = %s",
        (new_name, group_id),
    )

    return get_group(group_id, conn)
