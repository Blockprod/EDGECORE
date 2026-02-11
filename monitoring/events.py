from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Optional

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
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    z_score: Optional[float] = None
    pnl: Optional[float] = None
    reason: Optional[str] = None
    
    def to_dict(self):
        """Convert event to dictionary for logging."""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['timestamp'] = self.timestamp.isoformat()
        return data
