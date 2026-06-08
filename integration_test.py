"""
integration_test.py — Full Stage 2 API integration test.
Run: python3 integration_test.py  (server must be running on port 8000)
"""

import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8000"


def req(method, path, body=None, token=None, expected_status=None):
    url     = BASE + path
    data    = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r)
        status = resp.status
        body_data = resp.read()
        body_out = json.loads(body_data) if body_data else {}
    except urllib.error.HTTPError as e:
        status   = e.code
        body_out = json.loads(e.read())
    if expected_status and status != expected_status:
        print(f"  FAIL {method} {path} → {status} (expected {expected_status})")
        print(f"       {body_out}")
        sys.exit(1)
    return status, body_out


print("=" * 60)
print("STAGE 2 INTEGRATION TEST")
print("=" * 60)

# ── Auth ───────────────────────────────────────────────────
print("\n── Auth ──")
_, alice = req("POST", "/auth/register", {"name": "Alice", "email": "alice@t.com", "password": "pass123"}, expected_status=201)
_, bob   = req("POST", "/auth/register", {"name": "Bob",   "email": "bob@t.com",   "password": "pass123"}, expected_status=201)
_, carol = req("POST", "/auth/register", {"name": "Carol", "email": "carol@t.com", "password": "pass123"}, expected_status=201)
AT, BT = alice["access_token"], bob["access_token"]
AID, BID, CID = alice["user_id"], bob["user_id"], carol["user_id"]
print(f"  Registered: Alice={AID}, Bob={BID}, Carol={CID} ✅")

_, login = req("POST", "/auth/login", {"email": "alice@t.com", "password": "pass123"}, expected_status=200)
assert login["user_id"] == AID
print("  Login ✅")

status, _ = req("POST", "/auth/login", {"email": "alice@t.com", "password": "WRONG"})
assert status == 401
print("  Wrong password → 401 ✅")

# ── Groups ─────────────────────────────────────────────────
print("\n── Groups ──")
_, grp = req("POST", "/groups", {"name": "Trip to Goa"}, token=AT, expected_status=201)
GID = grp["id"]
assert grp["members"][0]["role"] == "admin"
print(f"  Created group {GID} with Alice as admin ✅")

req("POST", f"/groups/{GID}/members", {"email": "bob@t.com"},   token=AT, expected_status=201)
req("POST", f"/groups/{GID}/members", {"email": "carol@t.com"}, token=AT, expected_status=201)
print("  Added Bob and Carol ✅")

_, g_detail = req("GET", f"/groups/{GID}", token=AT, expected_status=200)
assert len(g_detail["members"]) == 3
print(f"  Group detail has {len(g_detail['members'])} members ✅")

_, g_list = req("GET", "/groups", token=AT, expected_status=200)
assert any(g["id"] == GID for g in g_list)
print("  Group list ✅")

_, renamed = req("PATCH", f"/groups/{GID}", {"name": "Goa 2024"}, token=AT, expected_status=200)
assert renamed["name"] == "Goa 2024"
print("  Rename ✅")

status, _ = req("PATCH", f"/groups/{GID}", {"name": "Hacked"}, token=BT)
assert status == 403
print("  Non-admin rename → 403 ✅")

# ── Expenses ───────────────────────────────────────────────
print("\n── Expenses ──")
_, e1 = req("POST", f"/groups/{GID}/expenses", {
    "description": "Hotel", "amount": 300, "paid_by": AID,
    "split_type": "equal", "user_ids": [AID, BID, CID], "values": []
}, token=AT, expected_status=201)
EID1 = e1["id"]
assert len(e1["splits"]) == 3
assert abs(e1["splits"][0]["amount_owed"] - 100.0) < 0.01
print(f"  EQUAL expense {EID1}, splits={[(s['user_id'], s['amount_owed']) for s in e1['splits']]} ✅")

_, e2 = req("POST", f"/groups/{GID}/expenses", {
    "description": "Dinner", "amount": 100, "paid_by": BID,
    "split_type": "exact", "user_ids": [AID, BID], "values": [60, 40]
}, token=BT, expected_status=201)
EID2 = e2["id"]
print(f"  EXACT expense {EID2} ✅")

_, e3 = req("POST", f"/groups/{GID}/expenses", {
    "description": "Taxi", "amount": 200, "paid_by": carol["user_id"],
    "split_type": "percentage", "user_ids": [AID, BID, CID], "values": [50, 30, 20]
}, token=AT, expected_status=201)
print(f"  PERCENTAGE expense {e3['id']} ✅")

_, exp_list = req("GET", f"/groups/{GID}/expenses", token=AT, expected_status=200)
assert len(exp_list) == 3
print(f"  List expenses: {len(exp_list)} ✅")

_, exp_detail = req("GET", f"/groups/{GID}/expenses/{EID1}", token=AT, expected_status=200)
assert exp_detail["splits"] is not None
print(f"  Expense detail with splits ✅")

_, edited = req("PUT", f"/groups/{GID}/expenses/{EID1}", {
    "description": "Hotel (updated)", "amount": 360, "paid_by": AID,
    "split_type": "equal", "user_ids": [AID, BID, CID], "values": []
}, token=AT, expected_status=200)
assert edited["amount"] == 360
print(f"  Edit expense ✅")

status, _ = req("DELETE", f"/groups/{GID}/expenses/{EID2}", token=AT)
assert status == 204
print("  Delete expense ✅")

# ── Balances ───────────────────────────────────────────────
print("\n── Balances ──")
_, raw = req("GET", f"/groups/{GID}/balances", token=AT, expected_status=200)
print(f"  Raw balances: {raw['balances']} ✅")

_, simplified = req("GET", f"/groups/{GID}/balances/simplified", token=AT, expected_status=200)
print(f"  Simplified: {simplified['transactions']} ✅")

_, summary = req("GET", "/users/me/summary", token=AT, expected_status=200)
print(f"  User summary: {summary['summary']} ✅")

# ── Payments ───────────────────────────────────────────────
print("\n── Payments ──")
raw_balances = raw["balances"]
# Find a balance where Bob is debtor
bob_debt = next((b for b in raw_balances if b["debtor_id"] == BID), None)
if bob_debt:
    _, pmt = req("POST", f"/groups/{GID}/payments", {
        "from_user_id": BID, "to_user_id": bob_debt["creditor_id"],
        "amount": bob_debt["amount"], "notes": "Settled via UPI"
    }, token=BT, expected_status=201)
    print(f"  Payment recorded: {pmt['amount']} ✅")
else:
    print("  (No Bob debt to settle — balance state varies, skipping payment test)")

_, pmts = req("GET", f"/groups/{GID}/payments", token=AT, expected_status=200)
print(f"  Payment list: {len(pmts)} records ✅")

# ── Messages ───────────────────────────────────────────────
print("\n── Messages ──")
_, msg1 = req("POST", f"/expenses/{EID1}/messages", {"content": "Who booked the hotel?"}, token=AT, expected_status=201)
_, msg2 = req("POST", f"/expenses/{EID1}/messages", {"content": "Alice did!"}, token=BT, expected_status=201)
print(f"  Posted 2 messages ✅")

_, msgs = req("GET", f"/expenses/{EID1}/messages", token=AT, expected_status=200)
assert len(msgs) == 2
print(f"  Got {len(msgs)} messages ✅")

# Content too long → 400
status, _ = req("POST", f"/expenses/{EID1}/messages", {"content": "x" * 501}, token=AT)
assert status == 422   # Pydantic validation error
print("  Message > 500 chars → 422 ✅")

# ── Error cases ────────────────────────────────────────────
print("\n── Error cases ──")
status, _ = req("GET", "/groups/9999", token=AT)
assert status == 404
print("  Group not found → 404 ✅")

status, _ = req("GET", "/groups/1", token=None)
assert status in (401, 403)   # no token = 401 or 403 depending on HTTPBearer
print(f"  No token → {status} ✅")

print("\n" + "=" * 60)
print("ALL INTEGRATION TESTS PASSED ✅")
print("=" * 60)
