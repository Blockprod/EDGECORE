from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum, StrEnum
from typing import Any, Protocol, runtime_checkable


class OrderSide(Enum):
    """Order direction."""

    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(StrEnum):
    """Canonical order state ��� single source of truth for the project."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass
class Order:
    """Order object (immutable once created)."""

    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    limit_price: float | None
    order_type: str = "LIMIT"  # LIMIT or MARKET
    created_at: datetime | None = None
    filled_at: datetime | None = None
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(UTC)


class BaseExecutionEngine(ABC):
    """Abstract base for execution engines."""

    @abstractmethod
    def submit_order(self, order: Order) -> str:
        """
        Submit order to broker.

        Returns:
            Order ID from broker
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order. Returns True if successful."""
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderStatus:
        """Get current order status."""
        pass

    @abstractmethod
    def get_positions(self) -> dict[str, float]:
        """
        Get all open positions.

        Returns:
            dict of {symbol: net_quantity}
        """
        pass

    @abstractmethod
    def get_account_balance(self) -> float:
        """Get current account balance."""
        pass


# ---------------------------------------------------------------------------
# Structural sub-typing Protocols (PEP 544)
# Enables testing via injection without inheriting from concrete classes.
# ---------------------------------------------------------------------------


@runtime_checkable
class SignalGeneratorProtocol(Protocol):
    """Structural interface for signal generators.

    Any object with a ``generate()`` method matching this signature satisfies
    the protocol � no inheritance required.  Enables mock injection in tests.
    """

    def generate(
        self,
        market_data: Any,
        active_pairs: list[Any],
        active_positions: dict[str, Any],
    ) -> list[Any]:
        """Generate trading signals from market data."""
        ...


@runtime_checkable
class AllocatorProtocol(Protocol):
    """Structural interface for position allocators."""

    def allocate(
        self,
        pair_key: str,
        signal_strength: float,
        spread_vol: float,
        half_life: float,
        win_rate: float,
        avg_win_loss_ratio: float,
    ) -> Any:
        """Compute position size for a pair signal."""
        ...

    def release(self, pair_key: str) -> None:
        """Release allocation for a closed pair."""
        ...

    def update_equity(self, equity: float) -> None:
        """Update current equity for heat calculations."""
        ...


@runtime_checkable
class DataLoaderProtocol(Protocol):
    """Structural interface for market data loaders."""

    def bulk_load(
        self,
        symbols: list[str],
        timeframe: str,
        limit: int,
        max_workers: int,
        use_cache: bool,
        rate_limiter: Any,
    ) -> dict[str, Any]:
        """Load OHLCV data for a list of symbols."""
        ...
