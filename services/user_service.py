"""
services/user_service.py — User registration and authentication.

Stage 1 uses hashlib.pbkdf2_hmac (stdlib) for password hashing.
Stage 2 (FastAPI) will swap this for bcrypt via passlib.

All functions accept an open sqlite3.Connection from get_connection().
Errors are raised as ValueError with descriptive messages.
"""

import hashlib
import os
import sqlite3
from typing import Optional

from models.user import User


# ── Password hashing ───────────────────────────────────────────────────────────

_HASH_ALGO      = "sha256"
_ITERATIONS     = 260_000   # NIST-recommended minimum as of 2023
_SALT_BYTES     = 32
_SEPARATOR      = "$"       # separates salt and hash in the stored string


def _hash_password(password: str) -> str:
    """Return a salted hash string: '<hex_salt>$<hex_hash>'."""
    salt = os.urandom(_SALT_BYTES)
    key  = hashlib.pbkdf2_hmac(_HASH_ALGO, password.encode(), salt, _ITERATIONS)
    return salt.hex() + _SEPARATOR + key.hex()


def _verify_password(password: str, stored: str) -> bool:
    """Verify a plaintext password against a stored '<hex_salt>$<hex_hash>' string."""
    try:
        salt_hex, key_hex = stored.split(_SEPARATOR, 1)
        salt = bytes.fromhex(salt_hex)
        key  = hashlib.pbkdf2_hmac(_HASH_ALGO, password.encode(), salt, _ITERATIONS)
        return key.hex() == key_hex
    except Exception:
        return False


# ── Public API ─────────────────────────────────────────────────────────────────

def register(
    name:     str,
    email:    str,
    password: str,
    conn:     sqlite3.Connection,
) -> User:
    """
    Register a new user.

    Args:
        name:     Display name (non-empty).
        email:    Unique login email (non-empty).
        password: Plaintext password — hashed before storage.
        conn:     Open DB connection.

    Returns:
        User with id and created_at filled in.

    Raises:
        ValueError: If name/email/password are blank, or email already exists.
    """
    name     = name.strip()
    email    = email.strip().lower()
    password = password.strip()

    if not name:
        raise ValueError("Name cannot be blank.")
    if not email:
        raise ValueError("Email cannot be blank.")
    if not password:
        raise ValueError("Password cannot be blank.")

    existing = conn.execute(
        "SELECT id FROM users WHERE email = %s", (email,)
    ).fetchone()
    if existing:
        raise ValueError(f"Email '{email}' is already registered.")

    hashed = _hash_password(password)
    row = conn.execute(
        "INSERT INTO users (name, email, hashed_password) VALUES (%s, %s, %s) RETURNING id, created_at",
        (name, email, hashed),
    ).fetchone()

    return User(
        id=row["id"],
        name=name,
        email=email,
        hashed_password=hashed,
        created_at=row["created_at"],
    )


def authenticate(
    email:    str,
    password: str,
    conn:     sqlite3.Connection,
) -> User:
    """
    Verify credentials and return the User.

    Raises:
        ValueError: If email not found or password is incorrect.
                    (Intentionally same message to avoid email enumeration.)
    """
    email = email.strip().lower()
    row   = conn.execute(
        "SELECT id, name, email, hashed_password, created_at FROM users WHERE email = %s",
        (email,),
    ).fetchone()

    if not row or not _verify_password(password, row["hashed_password"]):
        raise ValueError("Invalid email or password.")

    return User(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        hashed_password=row["hashed_password"],
        created_at=row["created_at"],
    )


def get_by_id(user_id: int, conn: sqlite3.Connection) -> Optional[User]:
    """Return a User by ID, or None if not found."""
    row = conn.execute(
        "SELECT id, name, email, hashed_password, created_at FROM users WHERE id = %s",
        (user_id,),
    ).fetchone()
    if not row:
        return None
    return User(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        hashed_password=row["hashed_password"],
        created_at=row["created_at"],
    )


def get_by_email(email: str, conn: sqlite3.Connection) -> Optional[User]:
    """Return a User by email, or None if not found."""
    email = email.strip().lower()
    row   = conn.execute(
        "SELECT id, name, email, hashed_password, created_at FROM users WHERE email = %s",
        (email,),
    ).fetchone()
    if not row:
        return None
    return User(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        hashed_password=row["hashed_password"],
        created_at=row["created_at"],
    )
