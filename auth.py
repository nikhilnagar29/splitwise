"""
auth.py — JWT creation, verification, and FastAPI dependency.

Stage 2 upgrades password hashing from pbkdf2 (Stage 1 stdlib)
to bcrypt via passlib — bcrypt is the standard for production APIs.

Services (user_service.py) still use pbkdf2 for Stage 1 compatibility.
This module is the ONLY place bcrypt is used — for the API layer only.

JWT:
  - Algorithm: HS256
  - Payload:   {"sub": str(user_id), "exp": datetime}
  - Expiry:    24 hours
  - Secret:    JWT_SECRET env-var (falls back to a dev-only default)

Usage as a FastAPI dependency:
    @router.get("/protected")
    def route(current_user: User = Depends(get_current_user)):
        ...
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from dependencies import _get_pg_connection
from models.user import User

# ── Config ─────────────────────────────────────────────────────────────────────

JWT_SECRET    = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

# ── Password hashing (bcrypt direct) ─────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plaintext against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT ────────────────────────────────────────────────────────────────────────

def create_token(user_id: int) -> str:
    """Create a signed JWT for the given user_id. Expires in JWT_EXPIRE_HOURS."""
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[int]:
    """
    Decode a JWT and return the user_id (int).
    Returns None if token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        return int(sub) if sub else None
    except JWTError:
        return None


# ── FastAPI dependency ─────────────────────────────────────────────────────────

_bearer = HTTPBearer()

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token.",
    headers={"WWW-Authenticate": "Bearer"},
)


from fastapi import Request

def get_current_user(
    request: Request,
) -> User:
    """
    FastAPI dependency: decode the token and return the User.
    Accepts token from Authorization header OR %stoken= query parameter.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token_str = auth_header.split(" ")[1]
    else:
        token_str = request.query_params.get("token")
        
    if not token_str:
        raise _CREDENTIALS_EXCEPTION

    user_id = decode_token(token_str)
    if user_id is None:
        raise _CREDENTIALS_EXCEPTION

    with _get_pg_connection() as conn:
        row = conn.execute(
            "SELECT id, name, email, hashed_password, created_at FROM users WHERE id = %s",
            (user_id,),
        ).fetchone()

    if not row:
        raise _CREDENTIALS_EXCEPTION

    return User(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        hashed_password=row["hashed_password"],
        created_at=row["created_at"],
    )
