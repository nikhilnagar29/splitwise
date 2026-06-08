"""
strategies/percentage.py — Percentage split strategy.

Each participant's share is specified as a percentage (0–100).
The actual amount owed is computed as (percentage / 100) * total_amount.

Validation (raises ValueError):
  - len(values) must equal len(user_ids).
  - Every percentage must be >= 0 and <= 100.
  - sum(percentages) must equal 100.0 (within ±0.01 tolerance to handle
    rounding in user input, e.g. 33.33 + 33.33 + 33.34 = 100.00).

Rounding:
  Each computed share = round(pct / 100 * amount, 2).
  The last participant absorbs any ±1-cent residual so shares sum
  exactly to the total amount.
"""

from typing import List
from models.split import Split
from strategies.base import SplitStrategy

_TOLERANCE = 0.01   # maximum allowed sum-of-percentages deviation from 100.0


class PercentageSplit(SplitStrategy):
    """Split where each user's share is given as a percentage of the total."""

    def calculate(
        self,
        expense_id: int,
        amount:     float,
        user_ids:   List[int],
        values:     List[float],   # values[i] = percentage (0–100) for user_ids[i]
    ) -> List[Split]:
        # ── Structural validation ──────────────────────────────────────────
        if not user_ids:
            raise ValueError("PercentageSplit requires at least one participant.")

        if len(values) != len(user_ids):
            raise ValueError(
                f"PercentageSplit: number of percentages ({len(values)}) must "
                f"match number of participants ({len(user_ids)})."
            )

        # ── Per-value validation ───────────────────────────────────────────
        for i, pct in enumerate(values):
            if pct < 0 or pct > 100:
                raise ValueError(
                    f"PercentageSplit: percentage at index {i} is {pct}. "
                    "Each percentage must be between 0 and 100."
                )

        # ── Sum validation ─────────────────────────────────────────────────
        total_pct = round(sum(values), 4)
        if abs(total_pct - 100.0) > _TOLERANCE:
            raise ValueError(
                f"PercentageSplit: percentages sum to {total_pct:.4f}% but "
                f"must sum to 100.0%. Difference of {abs(total_pct - 100.0):.4f}% "
                f"exceeds tolerance of {_TOLERANCE}%."
            )

        # ── Compute amounts ────────────────────────────────────────────────
        n = len(user_ids)
        splits = []
        running_total = 0.0

        for i, (uid, pct) in enumerate(zip(user_ids, values)):
            if i < n - 1:
                share = round(pct / 100.0 * amount, 2)
            else:
                # Last person absorbs rounding residual.
                share = round(amount - running_total, 2)

            splits.append(Split(expense_id=expense_id, user_id=uid, amount_owed=share))
            running_total += share

        return splits
