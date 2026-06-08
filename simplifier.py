"""
simplifier.py — DebtSimplifier: computes simplified transactions from raw balances.

Key constraints (AI_CONTEXT.md § 11):
  - Scope is ALWAYS per-group — never cross-group.
  - This class NEVER reads from or writes to the database.
  - It is a pure computation layer: in → out, no side effects.
  - The `balances` table is never modified by this class.

Algorithm: Minimum Cash Flow (greedy)
  1. Compute each person's net amount from the raw pairwise balances.
       net[person] > 0  → person is owed money (creditor).
       net[person] < 0  → person owes money (debtor).
  2. Use a max-heap on both creditors and debtors.
  3. Each iteration: match the largest creditor with the largest debtor.
     Settle min(credit, debt). Push back any remainder.
  4. Result: a minimal set of transactions that clears all debts.

Usage:
    raw = BalanceManager.get_group_balances(group_id, conn)
    # raw = {(debtor_id, creditor_id): amount, ...}
    simplified = DebtSimplifier.simplify(raw)
    # simplified = [(payer_id, receiver_id, amount), ...]
"""

import heapq
from typing import Dict, List, Tuple

_EPSILON = 1e-6   # threshold below which a balance is treated as zero


class DebtSimplifier:
    """
    Stateless utility class.  All methods are static.
    Per-group scope only — never pass balances from multiple groups.
    """

    @staticmethod
    def simplify(
        raw_balances: Dict[Tuple[int, int], float],
    ) -> List[Tuple[int, int, float]]:
        """
        Compute the minimum set of transactions to settle all debts.

        Args:
            raw_balances: {(debtor_id, creditor_id): amount}
                          All entries must belong to the SAME group.
                          Amount must be > 0 (zero rows are never stored per spec).

        Returns:
            List of (payer_id, receiver_id, amount) tuples.
            Empty list if everyone is settled.

        Does NOT modify the database.
        """
        if not raw_balances:
            return []

        # ── Step 1: compute net balance per person ─────────────────────────
        net: Dict[int, float] = {}
        for (debtor, creditor), amount in raw_balances.items():
            net[debtor]   = net.get(debtor, 0.0)   - amount
            net[creditor] = net.get(creditor, 0.0) + amount

        # ── Step 2: separate into creditors and debtors ────────────────────
        # Max-heap via negation (heapq is a min-heap in Python).
        creditors: List[Tuple[float, int]] = []  # (-amount, user_id)
        debtors:   List[Tuple[float, int]] = []  # (-amount, user_id)

        for user_id, net_amount in net.items():
            if net_amount > _EPSILON:
                heapq.heappush(creditors, (-net_amount, user_id))
            elif net_amount < -_EPSILON:
                heapq.heappush(debtors, (net_amount, user_id))   # already negative

        # ── Step 3: greedy matching ────────────────────────────────────────
        result: List[Tuple[int, int, float]] = []

        while creditors and debtors:
            max_credit_neg, creditor = heapq.heappop(creditors)
            max_credit = -max_credit_neg

            # Debtors stored with negative net; most negative = largest debt.
            max_debt_neg, debtor = heapq.heappop(debtors)
            max_debt = -max_debt_neg   # convert to positive magnitude

            settled = min(max_credit, max_debt)
            result.append((debtor, creditor, round(settled, 2)))

            remaining_credit = max_credit - settled
            remaining_debt   = max_debt   - settled

            if remaining_credit > _EPSILON:
                heapq.heappush(creditors, (-remaining_credit, creditor))
            if remaining_debt > _EPSILON:
                heapq.heappush(debtors, (-remaining_debt, debtor))

        return result
