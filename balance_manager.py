"""
balance_manager.py — BalanceManager: all reads and writes to the `balances` table.

The `balances` table is the source of truth for raw pairwise debts.
This class is the ONLY layer allowed to modify it.

Key invariants (AI_CONTEXT.md § 11):
  - Single row per (group, debtor, creditor) pair — no mirrored rows.
  - amount > 0 always; zero-balance rows are deleted, never stored.
  - Debt simplification is NOT done here — see simplifier.py.

Internal helpers
────────────────
  _net_offset(group_id, debtor_id, creditor_id, delta, conn)
      Core arithmetic engine.  Adjusts the net debt that debtor_id owes
      creditor_id by `delta` (positive = more debt, negative = less debt).
      Handles all edge cases: existing direct row, existing reverse row,
      netting to zero, netting to opposite direction.

Public API
──────────
  BalanceManager.apply_expense(expense, splits, conn)
      Called after INSERT of new splits.

  BalanceManager.reverse_expense(expense_id, conn)
      Called BEFORE deleting splits (reads them to undo their deltas).
      Used by both edit_expense and delete_expense.

  BalanceManager.apply_payment(payment, conn)
      Called after INSERT of a payment record.

  BalanceManager.get_group_balances(group_id, conn) → dict
      Returns {(debtor_id, creditor_id): amount} for one group.
      Passed to DebtSimplifier.simplify() by the caller.

  BalanceManager.get_user_summary(user_id, conn) → dict
      Cross-group net per counterparty.
      {other_user_id: net_amount}  (positive = owed to user, negative = user owes)
"""

import sqlite3
from typing import Dict, List, Tuple

from models.expense import Expense
from models.payment import Payment
from models.split import Split

_EPSILON = 1e-6   # treat as zero below this threshold


# ── Internal helper ────────────────────────────────────────────────────────────

def _net_offset(
    group_id:    int,
    debtor_id:   int,
    creditor_id: int,
    delta:       float,
    conn:        sqlite3.Connection,
) -> None:
    """
    Adjust the net balance: debtor_id owes creditor_id `delta` more (delta > 0)
    or `|delta|` less (delta < 0).

    Handles all cases:
      - existing direct row  (debtor → creditor)
      - existing reverse row (creditor → debtor)
      - netting to zero (row deleted)
      - netting to opposite direction (new row inserted for the other side)
    """
    if abs(delta) < _EPSILON:
        return

    # Negative delta means we're reducing debt — flip roles and recurse.
    if delta < 0:
        _net_offset(group_id, creditor_id, debtor_id, -delta, conn)
        return

    # delta > 0: debtor owes creditor more.

    # Check if a reverse row already exists (creditor owes debtor).
    rev_row = conn.execute(
        "SELECT amount FROM balances "
        "WHERE group_id = %s AND user_id = %s AND owes_user_id = %s",
        (group_id, creditor_id, debtor_id),
    ).fetchone()

    if rev_row:
        rev_amt = rev_row["amount"]
        # Cancel out the reverse row entirely.
        conn.execute(
            "DELETE FROM balances "
            "WHERE group_id = %s AND user_id = %s AND owes_user_id = %s",
            (group_id, creditor_id, debtor_id),
        )
        net = delta - rev_amt

        if net > _EPSILON:
            # debtor still owes creditor the net remainder.
            _upsert_direct(group_id, debtor_id, creditor_id, net, conn)
        elif net < -_EPSILON:
            # creditor now owes debtor the net remainder.
            _upsert_direct(group_id, creditor_id, debtor_id, -net, conn)
        # if |net| < _EPSILON: fully settled, nothing to insert.
    else:
        # No reverse row — simply add to (or create) the direct row.
        _upsert_direct(group_id, debtor_id, creditor_id, delta, conn)


def _upsert_direct(
    group_id:    int,
    debtor_id:   int,
    creditor_id: int,
    amount:      float,
    conn:        sqlite3.Connection,
) -> None:
    """
    Add `amount` to the direct (debtor → creditor) balance row,
    creating the row if it does not exist.
    Deletes the row if the resulting amount drops to zero or below.
    """
    existing = conn.execute(
        "SELECT amount FROM balances "
        "WHERE group_id = %s AND user_id = %s AND owes_user_id = %s",
        (group_id, debtor_id, creditor_id),
    ).fetchone()

    if existing:
        new_amount = existing["amount"] + amount
        if new_amount < _EPSILON:
            conn.execute(
                "DELETE FROM balances "
                "WHERE group_id = %s AND user_id = %s AND owes_user_id = %s",
                (group_id, debtor_id, creditor_id),
            )
        else:
            conn.execute(
                "UPDATE balances SET amount = %s "
                "WHERE group_id = %s AND user_id = %s AND owes_user_id = %s",
                (round(new_amount, 2), group_id, debtor_id, creditor_id),
            )
    else:
        conn.execute(
            "INSERT INTO balances (group_id, user_id, owes_user_id, amount) "
            "VALUES (%s, %s, %s, %s)",
            (group_id, debtor_id, creditor_id, round(amount, 2)),
        )


# ── Public API ─────────────────────────────────────────────────────────────────

class BalanceManager:
    """
    Stateless manager — all methods are static.
    Every caller must pass an open sqlite3.Connection from get_connection().
    The connection's transaction is managed by the caller (usually a service).
    """

    @staticmethod
    def apply_expense(
        expense: Expense,
        splits:  List[Split],
        conn:    sqlite3.Connection,
    ) -> None:
        """
        Record balance deltas produced by a new (or re-created) expense.

        For each split where the user is NOT the payer:
          split.user_id owes expense.paid_by split.amount_owed.

        The payer's own split is skipped — you don't owe yourself.
        """
        for split in splits:
            if split.user_id == expense.paid_by:
                continue
            _net_offset(
                expense.group_id,
                split.user_id,     # debtor
                expense.paid_by,   # creditor
                split.amount_owed,
                conn,
            )

    @staticmethod
    def reverse_expense(expense_id: int, conn: sqlite3.Connection) -> None:
        """
        Undo all balance deltas that were created by a given expense.

        MUST be called BEFORE splits are deleted (reads splits from DB).
        Used by both edit_expense (reverse then recreate) and delete_expense.
        """
        expense_row = conn.execute(
            "SELECT group_id, paid_by FROM expenses WHERE id = %s",
            (expense_id,),
        ).fetchone()

        if not expense_row:
            # Expense already gone — nothing to reverse.
            return

        group_id = expense_row["group_id"]
        paid_by  = expense_row["paid_by"]

        split_rows = conn.execute(
            "SELECT user_id, amount_owed FROM splits WHERE expense_id = %s",
            (expense_id,),
        ).fetchall()

        for row in split_rows:
            if row["user_id"] == paid_by:
                continue
            # Reverse: reduce the debt that row["user_id"] owes paid_by.
            _net_offset(
                group_id,
                row["user_id"],   # debtor
                paid_by,          # creditor
                -row["amount_owed"],  # negative = reduce debt
                conn,
            )

    @staticmethod
    def apply_payment(payment: Payment, conn: sqlite3.Connection) -> None:
        """
        Reduce the raw pairwise balance after a full settlement.

        payment.from_user_id owes payment.to_user_id payment.amount less.
        The balance row is deleted if it reaches zero (full settlement).
        """
        _net_offset(
            payment.group_id,
            payment.from_user_id,   # debtor paying off
            payment.to_user_id,     # creditor receiving
            -payment.amount,        # negative = reduce debt
            conn,
        )

    @staticmethod
    def get_group_balances(
        group_id: int,
        conn:     sqlite3.Connection,
    ) -> Dict[Tuple[int, int], float]:
        """
        Return all raw pairwise balances for a single group.

        Returns:
            {(debtor_id, creditor_id): amount}
            Pass directly to DebtSimplifier.simplify().
        """
        rows = conn.execute(
            "SELECT user_id, owes_user_id, amount FROM balances WHERE group_id = %s",
            (group_id,),
        ).fetchall()
        return {(row["user_id"], row["owes_user_id"]): row["amount"] for row in rows}

    @staticmethod
    def get_user_summary(
        user_id: int,
        conn:    sqlite3.Connection,
    ) -> Dict[int, float]:
        """
        Cross-group net balance per counterparty for a single user.
        Derived live — no cache table.

        Returns:
            {other_user_id: net_amount}
              net_amount > 0 → other_user owes this user (this user is creditor)
              net_amount < 0 → this user owes other_user (this user is debtor)
        """
        summary: Dict[int, float] = {}

        # Rows where user_id is the debtor (user owes someone).
        for row in conn.execute(
            "SELECT owes_user_id, amount FROM balances WHERE user_id = %s",
            (user_id,),
        ).fetchall():
            other = row["owes_user_id"]
            summary[other] = summary.get(other, 0.0) - row["amount"]

        # Rows where user_id is the creditor (someone owes user).
        for row in conn.execute(
            "SELECT user_id, amount FROM balances WHERE owes_user_id = %s",
            (user_id,),
        ).fetchall():
            other = row["user_id"]
            summary[other] = summary.get(other, 0.0) + row["amount"]

        # Round final values to avoid floating-point noise.
        return {uid: round(amt, 2) for uid, amt in summary.items() if abs(amt) > _EPSILON}
