from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass
class Signal:
    """Trading signal."""
    symbol_pair: str
    side: str  # "long" or "short"
    strength: float  # 0.0 to 1.0
    reason: str

class BaseStrategy(ABC):
    """Abstract base strategy."""
    
    @abstractmethod
    def generate_signals(self, market_data: pd.DataFrame) -> list[Signal]:
        """Generate trading signals from market data."""
        pass
    
    @abstractmethod
    def get_state(self) -> dict:
        """Return strategy state for inspection."""
        pass
