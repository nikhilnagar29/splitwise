# AI_CONTEXT.md — Splitwise Clone (Source of Truth)

> Last Updated: 2026-06-08 (Stage 1 COMPLETE — Stage 2 COMPLETE — Stage 3 IN PROGRESS)
> Status: STAGE 3 IN PROGRESS — Next.js Frontend + Azure Deployment

---

## 0. Stage Rules

We are working in **3 strict stages**. Do NOT jump ahead.

| Stage | Scope | Status |
|-------|-------|--------|
| **Stage 1** | DB schema + Python LLD classes + PostgreSQL (Aiven Cloud) - Migrated from SQLite. | ✅ COMPLETE |
| **Stage 2** | FastAPI REST API layer | ✅ COMPLETE |
| **Stage 3** | Next.js frontend + Azure deployment | 🔄 IN PROGRESS |

---

## 1. Product Vision

**Single Most Important Feature:**
Let a group of people add shared expenses and always know who owes whom how much.

**5-Minute User Journey:**
1. Log in → 2. Join or create a group → 3. Add an expense → 4. See clear balance summary

---

## 2. Timeline & Philosophy

- **Target Build Time:** 1 day
- **Philosophy:** Working features over polish. No over-engineering. Fast decisions.

---

## 3. Success Criteria (Definition of Done)

- [ ] User can register and log in
- [ ] User can create a group and add other registered users
- [ ] User can add an expense with any of the 3 split types
- [ ] App shows correct balances in group view and individual account view
- [ ] User can chat on an expense and see messages update in real time (SSE)
- [ ] User can settle a debt (full amount only) and see balances update
- [ ] Debt simplification runs automatically on every balance change
- [ ] App is live on Azure with public URL
- [ ] GitHub repo with README.md, BUILD_PLAN.md, AI_CONTEXT.md

---

## 4. User Personas

- Roommates splitting rent/utilities
- Friends on a trip
- Coworkers splitting a lunch bill
- Scope: Small groups

---

## 5. Tech Stack (Locked)

| Layer | Choice |
|-------|--------|
| Backend | Python / FastAPI |
| Frontend | Next.js |
| Database (Stage 1) | SQLite |
| Database (Stage 3) | ✅ SQLite → PostgreSQL migration completed (db.py, dependencies.py, typecaster). |
| Deployment | Azure |
| API Style | REST |
| Auth | JWT (stateless) |
| Real-Time | Server-Sent Events (SSE) |

---

## 6. Authentication (Locked)

- **Mechanism:** JWT — email + password login, return JWT token to frontend
- **Stateless:** No server-side sessions
- **User fields:** `id`, `name`, `email`, `hashed_password`, `created_at`
- **Group membership:** Only existing registered users can be added to a group. No email invites.

---

## 7. Core Features (Locked)

### In Scope
- User registration & login (JWT)
- Group management: create, add members, remove members
- Expense management: 3 split types (EQUAL, EXACT, PERCENTAGE)
- Real-time chat per expense (SSE, messages persisted in DB)
- Group-wise balance view + individual balance summary
- Settle debts (full amount only, recorded in separate payments table)
- Debt simplification (runs automatically on every balance change)

### Out of Scope
- SHARE split type (removed entirely from enum and codebase)
- Recurring expenses
- Currency conversion
- Receipt scanning
- Activity feed
- Friend requests outside groups
- Partial payments
- Email invites

---

## 8. Split Types (Locked)

```python
class SplitType(Enum):
    EQUAL = "equal"
    EXACT = "exact"
    PERCENTAGE = "percentage"
```

No SHARE type. Only these 3.

---

## 9. Database Schema (LOCKED ✅)

### Design Decisions (All Locked)
- **Balance tracking:** Per group, per user-pair. Raw pairwise debts only. Source of truth.
- **Splits:** Pre-computed and stored in `splits` table at expense creation time.
- **Settlements:** Stored in a separate `payments` table. NOT as expense records.
- **Messages:** Persisted in DB. No delete. History loads on expense open.
- **Expense edit:** Delete + Recreate internally. Reverse old deltas → delete old splits → apply new splits → recalculate balances.
- **Expense delete:** Hard delete splits rows, reverse balance deltas, re-run debt simplification.
- **Debt simplification:** Computed output only. Never overwrites `balances` table.
- **Payment settles:** Raw pairwise balance row directly. Then simplification re-runs.
- **Cross-group summary:** Derived live at query time. No separate cache table.

---

### Tables (Final)

#### `users`
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| name | TEXT | NOT NULL |
| email | TEXT | NOT NULL, UNIQUE |
| hashed_password | TEXT | NOT NULL |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

#### `groups`
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| name | TEXT | NOT NULL |
| created_by | INTEGER | NOT NULL, FK → users.id |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

#### `group_members`
| Column | Type | Constraints |
|--------|------|-------------|
| group_id | INTEGER | NOT NULL, FK → groups.id, PK part 1 |
| user_id | INTEGER | NOT NULL, FK → users.id, PK part 2 |
| role | TEXT | NOT NULL, DEFAULT 'member', CHECK(role IN ('admin','member')) |
| joined_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

**PK:** Composite `(group_id, user_id)`

**Role rules:**
- Creator → `admin` automatically
- One admin per group
- `admin`: remove members, delete any expense, rename group
- `member`: add expenses, view balances, chat — cannot remove others or delete others' expenses

#### `expenses`
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| group_id | INTEGER | NOT NULL, FK → groups.id |
| description | TEXT | NOT NULL |
| amount | REAL | NOT NULL, CHECK(amount > 0) |
| paid_by | INTEGER | NOT NULL, FK → users.id |
| split_type | TEXT | NOT NULL, CHECK(split_type IN ('equal','exact','percentage')) |
| created_by | INTEGER | NOT NULL, FK → users.id |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

#### `splits`
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL (PostgreSQL) | PRIMARY KEY |
| expense_id | INTEGER | NOT NULL, FK → expenses.id ON DELETE CASCADE |
| user_id | INTEGER | NOT NULL, FK → users.id |
| amount_owed | REAL | NOT NULL, CHECK(amount_owed >= 0) |

#### `balances`
| Column | Type | Constraints |
|--------|------|-------------|
| group_id | INTEGER | NOT NULL, FK → groups.id, PK part 1 |
| user_id | INTEGER | NOT NULL, FK → users.id (debtor), PK part 2 |
| owes_user_id | INTEGER | NOT NULL, FK → users.id (creditor), PK part 3 |
| amount | REAL | NOT NULL, CHECK(amount > 0) |

**PK:** Composite `(group_id, user_id, owes_user_id)`
**Direction:** Single row. `(group, Alice, Bob, 10)` = Alice owes Bob $10. Zero-amount rows are deleted.

#### `payments`
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL | PRIMARY KEY |
| group_id | INTEGER | NOT NULL, FK → groups.id |
| from_user_id | INTEGER | NOT NULL, FK → users.id (payer) |
| to_user_id | INTEGER | NOT NULL, FK → users.id (receiver) |
| amount | REAL | NOT NULL, CHECK(amount > 0) |
| notes | TEXT | NULLABLE, CHECK(length(notes) <= 200) |
| created_at | TIMESTAMP | DEFAULT NOW() |

#### `messages`
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL | PRIMARY KEY |
| expense_id | INTEGER | NOT NULL, FK → expenses.id ON DELETE CASCADE |
| user_id | INTEGER | NOT NULL, FK → users.id |
| content | TEXT | NOT NULL, CHECK(length(content) <= 500) |
| created_at | TIMESTAMP | DEFAULT NOW() |

---

## 10. LLD Class Design (from User's Diagram + Confirmed Decisions)

### Pattern Map
| Pattern | Used For |
|---------|----------|
| Strategy | Split calculation (Equal / Exact / Percentage) |
| Factory | SplitFactory creates strategy instances |
| Singleton | Splitwise central manager |
| Observer | User subscribes to Group notifications |

### Core Classes (Python — Draft)
- `User` — maps to users table
- `Group` — maps to groups table, holds member list, balance logic
- `Expense` — maps to expenses table
- `Split` — maps to splits table
- `Payment` — maps to payments table
- `Message` — maps to messages table
- `SplitStrategy` (ABC) — interface for split calculation
- `EqualSplit`, `ExactSplit`, `PercentageSplit` — concrete strategies
- `SplitFactory` — returns correct strategy by SplitType
- `DebtSimplifier` — simplifyDebt(balances: dict) → list of simplified transactions
- `BalanceManager` — updates balances table on expense add/edit/delete/payment

---

## 11. Balance & Debt Logic (Locked ✅)

- Balance is **per group, per user-pair**
- `balances` table is the **source of truth** — raw pairwise debts only
- Updated **automatically** on every: expense creation, expense edit, expense delete, payment
- **Expense edit** = reverse old balance deltas → DELETE splits only → UPDATE expense row in-place → compute new splits → INSERT new splits → apply new balance deltas. **Messages are NOT deleted during edit — they survive permanently.**
- **Expense delete** = hard delete expense row (CASCADE deletes splits + messages), reverse balance deltas, re-run simplification.
- **Payment** = reduces raw `(group, payer, receiver, amount)` row directly. Zero rows are deleted.
- **Debt simplification** = computed output only. Never writes to `balances`. Runs after every balance change. **Scope is per-group only — never cross-group.**
- **Cross-group summary** = derived live at query time. No cache table.
- **Full settlement only** — no partial payments.
- **Validation** enforced in Python service layer. Split strategies **raise explicit named exceptions** (not silent failures) that bubble up to the service layer. DB CHECK constraints are a secondary safety net.
  - `EqualSplit`: no input validation needed
  - `ExactSplit`: raises `InvalidSplitError` if `sum(values) != expense.amount`
  - `PercentageSplit`: raises `InvalidSplitError` if `sum(values) != 100.0`

---

## 12. All Q&A Resolved ✅

| Question | Decision |
|----------|----------|
| `balances` PK | Composite `(group_id, user_id, owes_user_id)` |
| `balances` direction | Single row. Flip handled in query logic. |
| `group_members` role | `admin` / `member`. Creator = admin. One admin per group. |
| Expense editing | Allowed. DELETE splits only + UPDATE expense in-place. **Messages survive edits.** |
| Expense deletion | Allowed. Creator OR admin can delete. Hard delete expense (CASCADE: splits+messages) + reverse deltas. |
| Payments notes | Optional text field. Max 200 chars. |
| Message length | Max 500 chars. |
| Message deletion | Not allowed. No delete at all. |
| Validation layer | Python service layer. Explicit exceptions (`InvalidSplitError`) bubble up. DB CHECK as safety net. |
| Debt simplification | Computed output only. Never overwrites `balances`. **Per-group scope only.** |
| Payment settles against | Raw pairwise balance row. Then simplification re-runs. |
| Cross-group summary | Derived live at query time. No cache table. |

---

## 13. Observed Design Patterns (from User's LLD Diagram)

Entities from user's whiteboard diagram:
- `Splitwise` (Singleton): central manager with users, groups, expenses maps
- `Group`: groupId, name, members[], expenses[], balances[]
- `User`: userId, name, email, balances{otherId → amount}
- `Expense`: id, desc, amt, paidById, splits[], groupId
- `Split` (model): userId, amount
- `DebtSimplifier`: simplifyDebt(map<> balances)
- `Observer` (abstract): update(msg)
- `SplitStrategy` (interface): calcSplit(totalAmt, userIds[], values[])
- `EqualSplit`, `ExactSplit`, `PercentageSplit` — concrete strategies
- `SplitFactory`: getSplitStrat(strategyType)

---

*This file is updated after every interview response. Do not write code until all Open Questions are resolved.*

---

## 14. Stage 2 — FastAPI REST API (IN PROGRESS)

### Tech Additions for Stage 2
| Concern | Choice |
|---------|--------|
| Framework | FastAPI |
| JWT library | `python-jose[cryptography]` |
| Password hashing | `passlib[bcrypt]` (replaces pbkdf2 from Stage 1) |
| Validation | Pydantic v2 (FastAPI built-in) |
| DB | SQLite (same as Stage 1 — migrates to Postgres in Stage 3) |
| Real-time | Server-Sent Events (SSE) for messages |

### Auth Design
- `POST /auth/register` — create user, return JWT
- `POST /auth/login` — verify credentials, return JWT
- JWT payload: `{"sub": user_id, "exp": ...}`
- All other endpoints require `Authorization: Bearer <token>` header
- FastAPI dependency `get_current_user` decodes token and injects User

### Endpoint Plan (build in this order, approved one group at a time)

| Group | Endpoints | Status |
|-------|-----------|--------|
| Auth | POST /auth/register, POST /auth/login | 🔄 NEXT |
| Groups | POST /groups, POST /groups/{id}/members, DELETE /groups/{id}/members/{uid}, PATCH /groups/{id}/name | 🔒 |
| Expenses | POST /groups/{id}/expenses, PATCH /expenses/{id}, DELETE /expenses/{id}, GET /groups/{id}/expenses | 🔒 |
| Balances | GET /groups/{id}/balances, GET /users/me/summary, GET /groups/{id}/balances/simplified | 🔒 |
| Payments | POST /groups/{id}/payments | 🔒 |
| Messages | POST /expenses/{id}/messages, GET /expenses/{id}/messages, GET /expenses/{id}/messages/stream (SSE) | 🔒 |

### File Structure for Stage 2
```
splitwise/
├── main.py              # FastAPI app instance, router registration, lifespan
├── auth.py              # JWT encode/decode, get_current_user dependency
├── dependencies.py      # get_db() connection dependency
├── routers/
│   ├── auth_router.py
│   ├── group_router.py
│   ├── expense_router.py
│   ├── balance_router.py
│   ├── payment_router.py
│   └── message_router.py
├── schemas/             # Pydantic request/response models
│   ├── auth_schema.py
│   ├── group_schema.py
│   ├── expense_schema.py
│   ├── balance_schema.py
│   ├── payment_schema.py
│   └── message_schema.py
└── requirements.txt
```

---

## 15. Stage 3 — Next.js Frontend (IN PROGRESS)

### Folder Structure
```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.js                  # Root layout (font, global styles)
│   │   ├── globals.css                # Global reset and base styles
│   │   ├── page.js                    # Root redirect → /login
│   │   ├── login/
│   │   │   ├── page.js                # Screen 1a: Login form
│   │   │   └── login.module.css
│   │   ├── register/
│   │   │   ├── page.js                # Screen 1b: Register form
│   │   │   └── register.module.css
│   │   ├── dashboard/
│   │   │   ├── page.js                # Screen 2: My Groups + Recent Expenses
│   │   │   └── dashboard.module.css
│   │   ├── groups/
│   │   │   └── [id]/
│   │   │       ├── page.js            # Screen 3: Group Detail
│   │   │       └── group.module.css
│   │   └── expenses/
│   │       └── [id]/
│   │           ├── page.js            # Screen 4: Expense Detail + Chat
│   │           └── expense.module.css
│   └── lib/
│       ├── api.js                     # All API call functions
│       ├── auth.js                    # localStorage token helpers
│       └── hooks.js                   # useAuthGuard, useLogout
├── .env.local                         # NEXT_PUBLIC_API_URL=http://localhost:8000
└── package.json
```

### Pages Built
| Screen | Route | Description |
|--------|-------|-------------|
| Screen 1a | `/login` | Email + password login. Saves JWT to localStorage. Redirects to `/dashboard`. |
| Screen 1b | `/register` | Name + email + password registration. Auto-logs in after success. |
| Screen 2 | `/dashboard` | Shows all user groups + recent expenses across all groups. Create-group inline form. |
| Screen 3 | `/groups/[id]` | Group members, expense list, add-expense form, simplified debt balances, settle up. |
| Screen 4 | `/expenses/[id]` | Expense detail (amount, paid by, splits table) + real-time chat via SSE. |

### JWT Storage
- JWT token is stored in `localStorage` under key `sw_token`.
- Logged-in user object (`id`, `name`, `email`) is stored under key `sw_user`.
- All API calls read the token from localStorage and send it as `Authorization: Bearer <token>`.
- On 401/403 response, the app calls `clearAuth()` and redirects to `/login`.
- On logout button click, the app calls `clearAuth()` and redirects to `/login`.

### SSE (Real-Time Chat) Implementation
- Page: `/expenses/[id]`
- On page load, `openMessageStream(token, expenseId, callback)` in `api.js` is called.
- It creates a native browser `EventSource` connected to `GET /expenses/{id}/messages/stream?token=<jwt>`.
- **Why token in query string:** Native `EventSource` does not support custom headers. The backend `auth.py` dependency accepts the token from either `Authorization: Bearer` header OR the `?token=` query parameter.
- The backend polls the SQLite DB every 1 second for new messages and emits them as SSE frames.
- New messages are appended to the chat list in real time without page refresh.
- The `EventSource` is closed when the component unmounts (cleanup in `useEffect` return).
- Duplicate prevention: incoming SSE messages are checked against `msg.id` before appending.

### src/lib/api.js — All Endpoints (19 functions)
| Function | HTTP | Endpoint | Auth Required |
|----------|------|----------|---------------|
| `register` | POST | `/auth/register` | No |
| `login` | POST | `/auth/login` | No |
| `getGroups` | GET | `/groups` | Yes |
| `getGroup` | GET | `/groups/{id}` | Yes |
| `createGroup` | POST | `/groups` | Yes |
| `renameGroup` | PATCH | `/groups/{id}` | Yes (admin) |
| `addMember` | POST | `/groups/{id}/members` | Yes (admin) |
| `removeMember` | DELETE | `/groups/{id}/members/{uid}` | Yes (admin) |
| `getExpenses` | GET | `/groups/{id}/expenses` | Yes |
| `getExpense` | GET | `/groups/{id}/expenses/{eid}` | Yes |
| `getUserExpenses` | GET | `/users/me/expenses` | Yes |
| `addExpense` | POST | `/groups/{id}/expenses` | Yes |
| `editExpense` | PUT | `/groups/{id}/expenses/{eid}` | Yes |
| `deleteExpense` | DELETE | `/groups/{id}/expenses/{eid}` | Yes |
| `getGroupBalances` | GET | `/groups/{id}/balances` | Yes |
| `getSimplifiedBalances` | GET | `/groups/{id}/balances/simplified` | Yes |
| `getUserSummary` | GET | `/users/me/summary` | Yes |
| `recordPayment` | POST | `/groups/{id}/payments` | Yes |
| `getMessages` | GET | `/expenses/{id}/messages` | Yes |
| `postMessage` | POST | `/expenses/{id}/messages` | Yes |
| `openMessageStream` | SSE | `/expenses/{id}/messages/stream?token=` | Token in query |

### src/lib/auth.js — Token Helpers
| Function | Description |
|----------|-------------|
| `saveAuth(token, user)` | Writes JWT to `localStorage['sw_token']` and user object to `localStorage['sw_user']` |
| `getToken()` | Reads and returns the JWT string from localStorage. Returns `null` if not set. |
| `getUser()` | Reads and JSON-parses the user object from localStorage. Returns `null` on parse error. |
| `clearAuth()` | Removes both `sw_token` and `sw_user` from localStorage. |
| `isLoggedIn()` | Returns `true` if a token exists in localStorage; `false` otherwise. |

---

## 16. Deployment Plan (Azure)

### Step 1 — SQLite → PostgreSQL Migration
1. Provision an **Azure Database for PostgreSQL** (Flexible Server) instance.
2. Install `psycopg2-binary` and `asyncpg` in `requirements.txt`.
3. Replace `sqlite3` imports in `db.py` with `psycopg2` or SQLAlchemy.
4. Replace `PRAGMA foreign_keys = ON` and `PRAGMA journal_mode = WAL` with PostgreSQL equivalents.
5. Run the existing DDL against the new Postgres instance to create all 7 tables.
6. Set `DATABASE_URL` environment variable on the App Service.

### Step 2 — Backend Deployment (FastAPI → Azure App Service)
- **Service:** Azure App Service (Linux, Python 3.11+)
- **Start command:** `uvicorn main:app --host 0.0.0.0 --port 8000`
- **Environment variables required on Azure:**

| Variable | Description |
|----------|-------------|
| `JWT_SECRET` | Random secret string for signing JWTs. Generate with `openssl rand -hex 32`. |
| `DATABASE_URL` | PostgreSQL connection string: `postgresql://user:pass@host/dbname` |
| `ALLOWED_ORIGINS` | Comma-separated list of frontend URLs allowed for CORS (e.g., `https://yourapp.azurestaticapps.net`) |

### Step 3 — Frontend Deployment (Next.js → Azure Static Web Apps)
- **Service:** Azure Static Web Apps
- **Build command:** `npm run build`
- **Output directory:** `.next`
- **Environment variables required on Azure:**

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Full URL of the deployed FastAPI backend (e.g., `https://splitwise-api.azurewebsites.net`) |

### Step 4 — Final Checks Before Go-Live
- Update `allow_origins` in `main.py` CORS config to match the Azure Static Web App URL.
- Confirm SSE stream works end-to-end through Azure (some proxy configs may need `X-Accel-Buffering: no`).
- Test full user journey: Register → Create Group → Add Expense → Settle Up → Chat.

---

## 17. Known Limitations

| Limitation | Details |
|------------|---------|
| **SQLite in dev only** | SQLite is not suitable for concurrent production traffic. Migration to PostgreSQL is required before Azure deployment (see Section 16). |
| **No email verification** | Users can register with any email address. No verification email is sent. Email addresses are trusted as-is. |
| **No password reset** | There is no "Forgot Password" or reset flow. If a user forgets their password, they cannot recover the account. |
| **Single admin per group** | Each group has exactly one admin (the creator). There is no mechanism to transfer admin rights to another member. |
| **SSE reconnection not handled** | If the SSE connection to `/messages/stream` drops (network error, server restart), the `EventSource` does not automatically show an error or attempt to reconnect with backoff. The user must manually refresh the page. |
| **No pagination** | `GET /groups/{id}/expenses` and `GET /expenses/{id}/messages` return all records with no limit or cursor-based pagination. Large groups with many expenses or messages may cause slow loads. |
| **Token in SSE query string** | The JWT is passed as a URL query parameter for SSE connections because `EventSource` does not support custom headers. This is a known workaround; in production, consider a short-lived SSE ticket/token system instead. |
