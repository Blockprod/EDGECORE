from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum


class EventType(Enum):
    """Trading event taxonomy."""

    TRADE_ENTRY = "TRADE_ENTRY"
    TRADE_EXIT = "TRADE_EXIT"
    RISK_VIOLATION = "RISK_VIOLATION"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    REBALANCE = "REBALANCE"
    DRAWDOWN_WARNING = "DRAWDOWN_WARNING"
    STRATEGY_SIGNAL = "STRATEGY_SIGNAL"


@dataclass
class TradingEvent:
    """Immutable trade event record."""

    event_type: EventType
    timestamp: datetime
    symbol_pair: str
    position_size: float
    entry_price: float | None = None
    exit_price: float | None = None
    z_score: float | None = None
    pnl: float | None = None
    reason: str | None = None
    hedge_ratio: float | None = None
    half_life: float | None = None
    momentum_score: float | None = None
    slippage_actual: float | None = None
    bid_ask_spread: float | None = None
    risk_tier: str | None = None

    def to_dict(self):
        """Convert event to dictionary for logging."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["timestamp"] = self.timestamp.isoformat()
        return data
