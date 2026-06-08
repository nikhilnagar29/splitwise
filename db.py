"""
db.py — PostgreSQL connection manager and schema initialisation.

Migrated from SQLite to PostgreSQL (Aiven cloud).

Responsibilities:
  - Provide a context-managed database connection (get_connection).
  - Use psycopg2 with RealDictCursor so rows are accessed by column name.
  - Create all 7 tables (if not exist) on first call to init_db().

Connection string is read from the DATABASE_URL environment variable.
Falls back to the Aiven development DSN if the env-var is not set.

The DDL here must be kept in sync with AI_CONTEXT.md § 9.
"""

import os
import contextlib
import psycopg2
import psycopg2.extensions
import psycopg2.extras  # RealDictCursor
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Keep SQLite timestamp behavior: return ISO strings instead of datetime objects.
_STR_TIMESTAMP = psycopg2.extensions.new_type((1114, 1184), "STR_TIMESTAMP", lambda v, c: v)
psycopg2.extensions.register_type(_STR_TIMESTAMP)

# ── Connection string ───────────────────────────────────────────────────────────
# 1. Tries to read DATABASE_URL from system environment variables (e.g., Azure)
# 2. Falls back to the local .env file configuration
# 3. Falls back to a local Docker/native instance if absolutely nothing is provided
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgres://user:password@localhost:5432/splitwise"
)

import contextlib
import psycopg2
import psycopg2.extras  # RealDictCursor

# ── Connection string ───────────────────────────────────────────────────────────
# Override at runtime via DATABASE_URL env-var for Azure deployment.



@contextlib.contextmanager
def get_connection():
    """
    Yield a psycopg2 connection with RealDictCursor.
    Rows can be accessed by column name: row['id'], row['name'], etc.
    Auto-commits on clean exit, rolls back on exception.

    Usage:
        with get_connection() as conn:
            conn.execute("SELECT ...")
    """
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
        
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── DDL ────────────────────────────────────────────────────────────────────────
# PostgreSQL syntax:
#   - SERIAL replaces INTEGER PRIMARY KEY AUTOINCREMENT
#   - TIMESTAMP replaces DATETIME
#   - char_length() replaces length() for TEXT columns
#   - ? placeholders replaced by %s (psycopg2 style)

_DDL = """
-- ── users ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL       PRIMARY KEY,
    name            TEXT         NOT NULL,
    email           TEXT         NOT NULL UNIQUE,
    hashed_password TEXT         NOT NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- ── groups ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS groups (
    id         SERIAL    PRIMARY KEY,
    name       TEXT      NOT NULL,
    created_by INTEGER   NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ── group_members ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS group_members (
    group_id  INTEGER   NOT NULL REFERENCES groups(id),
    user_id   INTEGER   NOT NULL REFERENCES users(id),
    role      TEXT      NOT NULL DEFAULT 'member'
                        CHECK (role IN ('admin', 'member')),
    joined_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (group_id, user_id)
);

-- ── expenses ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS expenses (
    id          SERIAL    PRIMARY KEY,
    group_id    INTEGER   NOT NULL REFERENCES groups(id),
    description TEXT      NOT NULL,
    amount      REAL      NOT NULL CHECK (amount > 0),
    paid_by     INTEGER   NOT NULL REFERENCES users(id),
    split_type  TEXT      NOT NULL
                          CHECK (split_type IN ('equal', 'exact', 'percentage')),
    created_by  INTEGER   NOT NULL REFERENCES users(id),
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ── splits ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS splits (
    id          SERIAL  PRIMARY KEY,
    expense_id  INTEGER NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    amount_owed REAL    NOT NULL CHECK (amount_owed >= 0)
);

-- ── balances ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS balances (
    group_id     INTEGER NOT NULL REFERENCES groups(id),
    user_id      INTEGER NOT NULL REFERENCES users(id),
    owes_user_id INTEGER NOT NULL REFERENCES users(id),
    amount       REAL    NOT NULL CHECK (amount > 0),
    PRIMARY KEY (group_id, user_id, owes_user_id)
);

-- ── payments ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS payments (
    id           SERIAL    PRIMARY KEY,
    group_id     INTEGER   NOT NULL REFERENCES groups(id),
    from_user_id INTEGER   NOT NULL REFERENCES users(id),
    to_user_id   INTEGER   NOT NULL REFERENCES users(id),
    amount       REAL      NOT NULL CHECK (amount > 0),
    notes        TEXT               CHECK (char_length(notes) <= 200),
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ── messages ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id         SERIAL    PRIMARY KEY,
    expense_id INTEGER   NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    user_id    INTEGER   NOT NULL REFERENCES users(id),
    content    TEXT      NOT NULL CHECK (char_length(content) <= 500),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""


def init_db() -> None:
    """
    Create all tables (IF NOT EXISTS).
    Safe to call multiple times — idempotent.
    Call once at application startup before any service is used.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_DDL)


# ── CLI helper ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("Database initialised successfully on PostgreSQL.")
