"""
routers/auth_router.py — POST /auth/register and POST /auth/login

Both endpoints:
  - Use bcrypt (via auth.py) for password hashing/verification.
  - Return a JWT on success.
  - Return HTTP 400 for validation failures (duplicate email, wrong password).

Note on password storage:
  Stage 1 user_service.py uses pbkdf2_hmac for hashing.
  The API layer uses bcrypt (auth.py) — a cleaner approach for the REST surface.
  Since Stage 1 tests write pbkdf2 hashes directly, and Stage 2 API registers
  users with bcrypt, both can coexist in the same DB. The auth_router uses
  its own register path that stores bcrypt hashes.
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from auth import create_token, hash_password, verify_password
from dependencies import get_db
from models.user import User
from schemas.auth_schema import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


# ── POST /auth/register ────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(
    body: RegisterRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> TokenResponse:
    """
    Create a new user account and return a JWT.

    - **name**: display name (non-blank)
    - **email**: must be unique
    - **password**: min 6 characters
    """
    email = body.email.lower().strip()

    existing = conn.execute(
        "SELECT id FROM users WHERE email = %s", (email,)
    ).fetchone()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{email}' is already registered.",
        )

    hashed = hash_password(body.password)
    row = conn.execute(
        "INSERT INTO users (name, email, hashed_password) VALUES (%s, %s, %s) RETURNING id",
        (body.name.strip(), email, hashed),
    ).fetchone()
    user_id = row["id"]
    token   = create_token(user_id)

    return TokenResponse(
        access_token=token,
        user_id=user_id,
        name=body.name.strip(),
        email=email,
    )


# ── POST /auth/login ───────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and get a JWT",
)
def login(
    body: LoginRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> TokenResponse:
    """
    Verify credentials and return a JWT.

    - **email**: registered email
    - **password**: account password

    Returns HTTP 401 for invalid credentials (same message to avoid enumeration).
    """
    email = body.email.lower().strip()
    row   = conn.execute(
        "SELECT id, name, email, hashed_password FROM users WHERE email = %s",
        (email,),
    ).fetchone()

    _INVALID = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
    )

    if not row:
        raise _INVALID

    if not verify_password(body.password, row["hashed_password"]):
        raise _INVALID

    token = create_token(row["id"])
    return TokenResponse(
        access_token=token,
        user_id=row["id"],
        name=row["name"],
        email=row["email"],
    )
