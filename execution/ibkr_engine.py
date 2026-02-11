"""
Interactive Brokers execution engine (STUB).

NOTE: This is a stub implementation. Production ib-insync integration includes:
- Order submission/cancellation via ib-insync
- Position tracking from account data
- Real-time balance updates
- Comprehensive error handling with exponential backoff

Scheduled for Phase 2 after CCXT stabilization.
"""

from execution.base import BaseExecutionEngine, Order, OrderStatus
from typing import Dict
from structlog import get_logger

logger = get_logger(__name__)

class IBKRExecutionEngine(BaseExecutionEngine):
    """
    Interactive Brokers execution via ib-insync.
    
    Not yet implemented. Requires:
    - TWS/Gateway running on localhost:7497
    - Account credentials configured in IB client
    """
    
    def __init__(self):
        logger.warning("ibkr_engine_not_implemented")
        raise NotImplementedError("IBKR engine is a stub. Use CCXT engine for now.")
    
    def submit_order(self, order: Order) -> str:
        pass
    
    def cancel_order(self, order_id: str) -> bool:
        pass
    
    def get_order_status(self, order_id: str) -> OrderStatus:
        pass
    
    def get_positions(self) -> Dict[str, float]:
        pass
    
    def get_account_balance(self) -> float:
        pass
