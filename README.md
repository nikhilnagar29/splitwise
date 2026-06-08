# splitwise
# Splitwise Clone

A simplified Splitwise-inspired expense splitting app built as an internship assignment.

Built with **FastAPI** (backend) + **Next.js** (frontend) + **PostgreSQL** (database).

---

## Live Demo

- **Frontend:** https://splitwise-frontend.onrender.com
- **Backend API:** https://splitwise-api.onrender.com
- **API Docs:** https://splitwise-api.onrender.com/docs

---

## AI Tool Used

This project was built using **Claude (Anthropic)** as the primary AI development collaborator.

Claude was used as a junior engineer that:
- Asked detailed questions before writing any code
- Maintained `AI_CONTEXT.md` as the source of truth
- Built the project in 3 strict stages (LLD → API → Frontend)
- Never assumed requirements — all decisions were made explicitly

---

## Features

- User registration and login (JWT authentication)
- Create and manage groups (invite members, remove members)
- Add expenses with 3 split types:
  - **Equal** — split evenly among all members
  - **Exact** — specify exact amount per person
  - **Percentage** — specify percentage per person
- Real-time chat on each expense (Server-Sent Events)
- Group-wise balance summary and individual balance summary
- Debt simplification (automatic, runs on every balance change)
- Settle debts (full amount only)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 / FastAPI |
| Frontend | Next.js 14 |
| Database | PostgreSQL (SQLite for local dev) |
| Auth | JWT (python-jose) |
| Password Hashing | bcrypt (passlib) |
| Real-time | Server-Sent Events (SSE) |
| Deployment | Render |

---

## Project Structure

```
splitwise/
├── main.py                  # FastAPI app entry point
├── db.py                    # DB connection + schema DDL
├── auth.py                  # JWT encode/decode
├── dependencies.py          # FastAPI dependencies (get_current_user)
├── splitwise_app.py         # Singleton — wires all services
├── balance_manager.py       # Owns balances table — all read/write
├── simplifier.py            # Debt simplification algorithm
├── factory.py               # SplitFactory — SplitType → SplitStrategy
├── keep_alive.py            # Self-ping script (merged into main.py)
├── requirements.txt
├── models/
│   ├── enums.py             # SplitType, Role
│   ├── user.py
│   ├── group.py
│   ├── expense.py
│   ├── split.py
│   ├── payment.py
│   └── message.py
├── strategies/
│   ├── base.py              # SplitStrategy ABC
│   ├── equal.py
│   ├── exact.py
│   └── percentage.py
├── services/
│   ├── user_service.py
│   ├── group_service.py
│   ├── expense_service.py
│   ├── payment_service.py
│   └── message_service.py
├── routers/
│   ├── auth_router.py
│   ├── group_router.py
│   ├── expense_router.py
│   ├── balance_router.py
│   ├── payment_router.py
│   └── message_router.py
├── schemas/                 # Pydantic request/response models
└── frontend/                # Next.js app
    ├── src/
    │   ├── app/
    │   │   ├── login/       # Login + Register
    │   │   ├── dashboard/   # Group list
    │   │   ├── groups/[id]/ # Group detail + expenses + balances
    │   │   └── expenses/[id]/ # Expense detail + chat
    │   └── lib/
    │       ├── api.js       # Central API client (all endpoints)
    │       └── auth.js      # JWT storage helpers
    └── package.json
```

---

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL (or use SQLite for quick local testing)

### Backend Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/splitwise.git
cd splitwise

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env and fill in your values

# Run the backend
uvicorn main:app --reload
```

Backend runs at: http://localhost:8000
API docs at: http://localhost:8000/docs

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Run the frontend
npm run dev
```

Frontend runs at: http://localhost:3000

---

## Environment Variables

Create a `.env` file in the project root:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/splitwise

# JWT
SECRET_KEY=your-super-secret-key-here

# Keep-alive (for Render free tier — leave empty for local dev)
PING_URL=https://your-app-name.onrender.com/health
PING_INTERVAL=840
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login, returns JWT |
| POST | `/groups` | Create group |
| GET | `/groups` | List user's groups |
| GET | `/groups/{id}` | Group detail + members |
| PATCH | `/groups/{id}` | Rename group (admin only) |
| POST | `/groups/{id}/members` | Add member by email |
| DELETE | `/groups/{id}/members/{uid}` | Remove member (admin only) |
| POST | `/groups/{id}/expenses` | Add expense |
| GET | `/groups/{id}/expenses` | List expenses |
| GET | `/groups/{id}/expenses/{eid}` | Expense detail + splits |
| PUT | `/groups/{id}/expenses/{eid}` | Edit expense |
| DELETE | `/groups/{id}/expenses/{eid}` | Delete expense |
| GET | `/groups/{id}/balances` | Raw pairwise balances |
| GET | `/groups/{id}/balances/simplified` | Simplified debts |
| GET | `/users/me/summary` | Cross-group balance summary |
| POST | `/groups/{id}/payments` | Record settlement |
| GET | `/groups/{id}/payments` | List payments |
| POST | `/expenses/{id}/messages` | Post chat message |
| GET | `/expenses/{id}/messages` | Get message history |
| GET | `/expenses/{id}/messages/stream` | SSE stream (real-time) |

---

## Key Design Decisions

- **Balance table is source of truth** — raw pairwise debts only. Debt simplification is a computed view, never written to DB.
- **Edit expense = UPDATE in place** — splits are deleted and recreated but chat messages survive.
- **Full settlement only** — no partial payments to keep logic simple.
- **Debt simplification** — uses min-cash-flow greedy algorithm, runs per group on every balance change.
- **SSE for real-time chat** — simpler than WebSockets, sufficient for this use case.

---

## Running Tests

```bash
# Stage 1 — LLD logic tests
python test_stage1.py

# Stage 2 — API integration tests (server must be running)
uvicorn main:app --reload &
python integration_test.py
```

---

## Deployment (Render)

1. Push code to GitHub
2. Create PostgreSQL database on Render → copy Internal Database URL
3. Create Web Service → connect GitHub repo
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Add env vars: `DATABASE_URL`, `SECRET_KEY`, `PING_URL`
4. Create Web Service for frontend → root dir: `frontend`
   - Build: `npm install && npm run build`
   - Start: `npm start`
   - Add env var: `NEXT_PUBLIC_API_URL`

---

## Known Limitations

- No email verification or password reset
- Single admin per group — no admin transfer
- No partial payments
- No pagination on expense or message lists
- SSE reconnection not handled if connection drops
- Free Render tier spins down after inactivity (keep-alive thread mitigates this)

---

## Files for Evaluators

| File | Purpose |
|------|---------|
| `AI_CONTEXT.md` | Full context used to build the app — source of truth |
| `BUILD_PLAN.md` | Architecture, research, AI collaboration process |
| `README.md` | This file — setup and overview |