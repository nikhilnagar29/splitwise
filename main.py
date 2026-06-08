"""
main.py — FastAPI application entry point.

Startup:
  - lifespan context calls SplitwiseApp.startup() → init_db() once.
  - Starts keep-alive background thread (pings /health every PING_INTERVAL seconds).

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

import os
import threading
import time
import traceback
import urllib.request
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


# ── Keep-alive background thread ───────────────────────────────────────────────
def _keep_alive():
    """
    Pings PING_URL every PING_INTERVAL seconds to prevent Render free-tier
    from spinning down the service.
    Runs as a daemon thread — dies automatically when the server stops.
    Controlled entirely by environment variables:
      PING_URL      — full URL to ping (e.g. https://splitwise-api.onrender.com/health)
      PING_INTERVAL — seconds between pings (default: 840 = 14 minutes)
    If PING_URL is not set, keep-alive is disabled silently.
    """
    url = os.environ.get("PING_URL", "").strip()
    interval = int(os.environ.get("PING_INTERVAL", "840"))

    if not url:
        print("Keep-alive: PING_URL not set — disabled.")
        return

    print(f"Keep-alive: started. Pinging {url} every {interval}s.")
    while True:
        time.sleep(interval)
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                print(f"Keep-alive: ping OK → {url} ({resp.status})")
        except Exception as exc:
            print(f"Keep-alive: ping FAILED → {exc}")


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DB and start keep-alive thread before first request."""
    init_db()
    SplitwiseApp.get_instance().startup()

    t = threading.Thread(target=_keep_alive, daemon=True, name="keep-alive")
    t.start()

    yield


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Splitwise Clone",
    description="A group expense splitting API built for an internship assignment.",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
# JWT is sent in Authorization header — NOT cookies — so allow_credentials=False.
# allow_origins=["*"] + allow_credentials=True is invalid per CORS spec §3.2.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global exception handler ───────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)
    print(f"Backend Crash on {request.url.path}: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"},
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