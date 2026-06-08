"""
dependencies.py — Shared FastAPI dependencies.

get_db: yields an open psycopg2 connection for the duration of a request,
then commits (or rolls back on exception) when the route handler returns.

IMPORTANT — psycopg2 vs sqlite3 differences handled here:
  - Rows are RealDictRow (accessed by name via row['column']) — same as before.
  - Placeholders are %s instead of ? — handled in every SQL statement.
  - cursor.lastrowid does NOT exist in psycopg2.
    Use RETURNING id in INSERT statements and cursor.fetchone()['id'] instead.
  - conn.execute() does NOT exist — must use conn.cursor() then cursor.execute().
    To keep the existing codebase minimal-change, we attach a thin .execute()
    shim to the connection so all services continue to call conn.execute().

Usage in any router:
    from dependencies import get_db
    import psycopg2

    @router.get("/something")
    def route(conn = Depends(get_db)):
        ...
"""

import contextlib
from typing import Generator
import psycopg2
import psycopg2.extras

from fastapi import Depends

from db import get_connection


class _PgConn:
    """
    Thin wrapper around a psycopg2 connection that adds:
      - conn.execute(sql, params)  → returns a cursor (like sqlite3)
      - conn.commit() / conn.rollback() forwarded to real connection

    This lets all existing service code call conn.execute(...).fetchone()
    without modification.
    """

    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, sql: str, params=None):
        cur = self._conn.cursor()
        cur.execute(sql, params or ())
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    # Allow direct attribute access for anything else (e.g. conn.cursor())
    def __getattr__(self, name):
        return getattr(self._conn, name)


@contextlib.contextmanager
def _get_pg_connection():
    """Open a psycopg2 connection wrapped in _PgConn, commit on exit."""
    raw = psycopg2.connect(
        __import__("db").DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    conn = _PgConn(raw)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db() -> Generator:
    """
    FastAPI dependency: yield a _PgConn for one HTTP request.
    Commits on clean exit, rolls back on exception.
    """
    with _get_pg_connection() as conn:
        yield conn


def service_call(fn, *args, **kwargs):
    """
    Call a service function and translate ValueError into the correct HTTPException.

      ValueError containing "does not exist"          → 404 Not Found
      ValueError containing "not an admin" /
        "permission" / "not a member of group"        → 403 Forbidden
      All other ValueErrors                           → 400 Bad Request

    Keeps route handlers free of error-translation logic.
    """
    from fastapi import HTTPException  # local import to avoid circular at module level

    try:
        return fn(*args, **kwargs)
    except ValueError as e:
        msg  = str(e)
        low  = msg.lower()
        if "does not exist" in low:
            raise HTTPException(status_code=404, detail=msg)
        if any(w in low for w in ["not an admin", "not have permission", "permission", "not a member of group"]):
            raise HTTPException(status_code=403, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
