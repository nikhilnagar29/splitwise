"""
strategies/equal.py — Equal split strategy.

Divides the total expense amount equally among all participants.
No per-user input values needed or validated.

Rounding:
  Each share = round(amount / n, 2).
  The last user absorbs any residual (±1 cent) so the shares always
  sum exactly to the original amount.
"""

from typing import List
from models.split import Split
from strategies.base import SplitStrategy


class EqualSplit(SplitStrategy):
    """Split the total equally among all user_ids."""

    def calculate(
        self,
        expense_id: int,
        amount:     float,
        user_ids:   List[int],
        values:     List[float],   # ignored for EQUAL splits
    ) -> List[Split]:
        if not user_ids:
            raise ValueError("EqualSplit requires at least one participant.")

        n = len(user_ids)
        per_person = round(amount / n, 2)

        splits = []
        running_total = 0.0

        for i, uid in enumerate(user_ids):
            if i < n - 1:
                share = per_person
            else:
                # Last person gets the remainder to absorb floating-point rounding.
                share = round(amount - running_total, 2)

            splits.append(Split(expense_id=expense_id, user_id=uid, amount_owed=share))
            running_total += share

        return splits
