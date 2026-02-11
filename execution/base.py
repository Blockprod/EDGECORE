from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict
from datetime import datetime

class OrderSide(Enum):
    """Order direction."""
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(Enum):
    """Order state."""
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

@dataclass
class Order:
    """Order object (immutable once created)."""
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    limit_price: Optional[float]
    order_type: str = "LIMIT"  # LIMIT or MARKET
    created_at: datetime = None
    filled_at: Optional[datetime] = None
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

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
    def get_positions(self) -> Dict[str, float]:
        """
        Get all open positions.
        
        Returns:
            Dict of {symbol: net_quantity}
        """
        pass
    
    @abstractmethod
    def get_account_balance(self) -> float:
        """Get current account balance."""
        pass
