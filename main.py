"""
main.py — FastAPI application entry point.

Startup:
  - lifespan context calls SplitwiseApp.startup() → init_db() once.

Route groups:
  /auth        → auth_router      (register, login)
  /groups      → group_router     (CRUD + membership)
  /groups/…    → expense_router   (expenses nested under groups)
  /groups/…    → balance_router   (balances nested under groups)
  /groups/…    → payment_router   (payments nested under groups)
  /users/…     → balance_router   (user summary — same router, no prefix)
  /expenses/…  → message_router   (messages nested under expenses)

Run:
  uvicorn main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import init_db
from splitwise_app import SplitwiseApp
from routers import (
    auth_router,
    balance_router,
    expense_router,
    group_router,
    message_router,
    payment_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the DB before the first request."""
    init_db()  # ← explicit call to create all tables
    SplitwiseApp.get_instance().startup()
    yield


app = FastAPI(
    title="Splitwise Clone",
    description="A group expense splitting API built for an internship assignment.",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
# We use JWT in the Authorization header — NOT cookies — so allow_credentials
# is not needed. allow_origins=["*"] + allow_credentials=True is an invalid
# combination that browsers actively block (CORS spec §3.2).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
        "http://localhost:3000",   # Next.js dev server
        "http://127.0.0.1:3000",

    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


from fastapi.responses import JSONResponse
from fastapi import HTTPException
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    if isinstance(exc, HTTPException):
        # Let FastAPI's default HTTPException handler deal with 401, 403, etc.
        from fastapi.exception_handlers import http_exception_handler
        return await http_exception_handler(request, exc)
        
    print(f"Backend Crash on {request.url.path}: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"}
    )

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)     # /auth/*
app.include_router(group_router.router)    # /groups/*
app.include_router(expense_router.router)  # /groups/{id}/expenses/*
app.include_router(balance_router.router)  # /groups/{id}/balances/* + /users/me/summary
app.include_router(payment_router.router)  # /groups/{id}/payments/*
app.include_router(message_router.router)  # /expenses/{id}/messages/*


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
