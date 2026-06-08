"""
models/enums.py — All enumerations used across the application.

Rules (from AI_CONTEXT.md):
  - SplitType has exactly 3 values: EQUAL, EXACT, PERCENTAGE.
  - SHARE is explicitly excluded — do not add it.
  - Role has exactly 2 values: ADMIN, MEMBER.
"""

from enum import Enum


class SplitType(Enum):
    """Determines how an expense is divided among group members."""
    EQUAL      = "equal"       # Divide total equally among all participants.
    EXACT      = "exact"       # Each participant's share is specified in absolute currency.
    PERCENTAGE = "percentage"  # Each participant's share is specified as a percentage (must sum to 100.0).


class Role(Enum):
    """Membership role within a group."""
    ADMIN  = "admin"   # Can remove members, delete any expense, rename group.
    MEMBER = "member"  # Can add expenses, view balances, chat on expenses.
