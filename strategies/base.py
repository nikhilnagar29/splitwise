"""
strategies/base.py — Abstract base class for all split strategies.

All concrete strategies (EqualSplit, ExactSplit, PercentageSplit) must
implement calculate(). Validation failures must raise ValueError with a
descriptive message — never fail silently (AI_CONTEXT.md § 11).
"""

from abc import ABC, abstractmethod
from typing import List
from models.split import Split


class SplitStrategy(ABC):
    """
    Interface for expense split calculation.

    Strategy pattern: the concrete class is chosen at runtime by SplitFactory
    based on the SplitType enum value on the expense.
    """

    @abstractmethod
    def calculate(
        self,
        expense_id: int,
        amount:     float,
        user_ids:   List[int],
        values:     List[float],
    ) -> List[Split]:
        """
        Compute per-user splits for an expense.

        Args:
            expense_id: ID of the expense being split.
            amount:     Total expense amount (> 0).
            user_ids:   Ordered list of user IDs sharing this expense.
                        Must be non-empty.
            values:     Strategy-specific inputs (see concrete classes).
                        - EQUAL:      ignored (pass [] or any list).
                        - EXACT:      values[i] = exact amount user_ids[i] owes.
                        - PERCENTAGE: values[i] = % share for user_ids[i] (0–100).

        Returns:
            List[Split] — one Split per user_id, in the same order.
            Splits for the payer are included (amount_owed = their share).
            The service layer skips the payer's own split when updating balances.

        Raises:
            ValueError: If values are invalid for this strategy.
                        Message must be descriptive enough for the caller to
                        surface to the user.
        """
        ...
