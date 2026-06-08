"""
splitwise_app.py — Singleton application entry point.

Responsibilities:
  - Call init_db() exactly once on startup.
  - Expose a single, clean access point to all services and the DB
    connection factory.
  - Contain NO business logic — only wiring.

Pattern: Singleton via __new__, initialised on first instantiation.

Usage (Stage 1 / Stage 2 startup):
    app = SplitwiseApp.get_instance()
    app.startup()

    with app.connection() as conn:
        user = app.users.register("Alice", "alice@test.com", "pass123", conn)
        group = app.groups.create_group("Trip to Goa", user.id, conn)
        ...
"""

from db import init_db, get_connection

# ── Service modules (stateless — each function takes a conn) ──────────────────
import services.user_service    as user_service
import services.group_service   as group_service
import services.expense_service as expense_service
import services.payment_service as payment_service
import services.message_service as message_service

# ── Core utilities ────────────────────────────────────────────────────────────
from balance_manager import BalanceManager
from simplifier      import DebtSimplifier
from factory         import SplitFactory


class SplitwiseApp:
    """
    Singleton that wires all Stage 1 components together.
    No business logic lives here.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._started = False
        return cls._instance

    @classmethod
    def get_instance(cls) -> "SplitwiseApp":
        """Return (or create) the singleton instance."""
        return cls()

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def startup(self) -> None:
        """
        Initialise the database.
        Idempotent — safe to call multiple times; init_db uses IF NOT EXISTS.
        """
        if not self._started:
            init_db()
            self._started = True

    # ── DB connection factory ──────────────────────────────────────────────────

    @staticmethod
    def connection():
        """
        Return a context-managed DB connection.

        Usage:
            with app.connection() as conn:
                ...
        """
        return get_connection()

    # ── Service namespaces ─────────────────────────────────────────────────────
    # Each property returns the service module directly.
    # Callers invoke: app.users.register(..., conn)

    @property
    def users(self):
        """User registration and authentication."""
        return user_service

    @property
    def groups(self):
        """Group creation, membership, and renaming."""
        return group_service

    @property
    def expenses(self):
        """Expense creation, editing, and deletion."""
        return expense_service

    @property
    def payments(self):
        """Debt settlement recording."""
        return payment_service

    @property
    def messages(self):
        """Expense chat messages."""
        return message_service

    # ── Core utilities ─────────────────────────────────────────────────────────

    @property
    def balance_manager(self) -> BalanceManager:
        """Raw pairwise balance reads and writes."""
        return BalanceManager

    @property
    def simplifier(self) -> DebtSimplifier:
        """Debt simplification (computed view — never writes to DB)."""
        return DebtSimplifier

    @property
    def split_factory(self) -> SplitFactory:
        """Strategy factory — maps SplitType → SplitStrategy."""
        return SplitFactory

    # ── Repr ───────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        status = "started" if self._started else "not started"
        return f"SplitwiseApp(singleton, {status})"
