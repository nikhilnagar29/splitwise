"""
factory.py — SplitFactory: maps SplitType → SplitStrategy instance.

Factory pattern: the caller passes a SplitType enum value and receives
the correct strategy object, ready to call .calculate() on.

Usage:
    strategy = SplitFactory.get(SplitType.EQUAL)
    splits   = strategy.calculate(expense_id, amount, user_ids, values)
"""

from models.enums import SplitType
from strategies.base import SplitStrategy
from strategies.equal import EqualSplit
from strategies.exact import ExactSplit
from strategies.percentage import PercentageSplit


class SplitFactory:
    """Returns the correct SplitStrategy instance for a given SplitType."""

    _registry: dict = {
        SplitType.EQUAL:      EqualSplit,
        SplitType.EXACT:      ExactSplit,
        SplitType.PERCENTAGE: PercentageSplit,
    }

    @classmethod
    def get(cls, split_type: SplitType) -> SplitStrategy:
        """
        Return a SplitStrategy instance for the given SplitType.

        Args:
            split_type: A SplitType enum member.

        Returns:
            A concrete SplitStrategy instance.

        Raises:
            ValueError: If split_type is not a recognised SplitType.
                        (Guards against future enum changes.)
        """
        strategy_class = cls._registry.get(split_type)
        if strategy_class is None:
            raise ValueError(
                f"SplitFactory: unknown SplitType '{split_type}'. "
                f"Supported types: {[t.value for t in cls._registry]}"
            )
        return strategy_class()
