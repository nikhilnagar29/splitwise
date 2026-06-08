"""
strategies/exact.py — Exact split strategy.

Each participant's share is provided as an explicit currency amount.

Validation (raises ValueError):
  - len(values) must equal len(user_ids).
  - Every value must be >= 0.
  - sum(values) must equal the total expense amount (within ±0.01 tolerance
    to accommodate cent-level rounding in caller input).
"""

from typing import List
from models.split import Split
from strategies.base import SplitStrategy

_TOLERANCE = 0.01   # maximum allowed rounding difference (1 cent)


class ExactSplit(SplitStrategy):
    """Split where each user's exact owed amount is specified explicitly."""

    def calculate(
        self,
        expense_id: int,
        amount:     float,
        user_ids:   List[int],
        values:     List[float],   # values[i] = exact amount user_ids[i] owes
    ) -> List[Split]:
        # ── Structural validation ──────────────────────────────────────────
        if not user_ids:
            raise ValueError("ExactSplit requires at least one participant.")

        if len(values) != len(user_ids):
            raise ValueError(
                f"ExactSplit: number of values ({len(values)}) must match "
                f"number of participants ({len(user_ids)})."
            )

        # ── Per-value validation ───────────────────────────────────────────
        for i, v in enumerate(values):
            if v < 0:
                raise ValueError(
                    f"ExactSplit: value at index {i} is negative ({v}). "
                    "All amounts must be >= 0."
                )

        # ── Sum validation ─────────────────────────────────────────────────
        total = round(sum(values), 2)
        if abs(total - amount) > _TOLERANCE:
            raise ValueError(
                f"ExactSplit: values sum to {total:.2f} but expense amount "
                f"is {amount:.2f}. Difference of {abs(total - amount):.4f} "
                f"exceeds tolerance of {_TOLERANCE}."
            )

        # ── Build splits ───────────────────────────────────────────────────
        return [
            Split(expense_id=expense_id, user_id=uid, amount_owed=round(v, 2))
            for uid, v in zip(user_ids, values)
        ]
