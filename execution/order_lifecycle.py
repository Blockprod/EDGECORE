"""
Order lifecycle management with timeout protection for EDGECORE.

Prevents:
- Stale orders from hanging indefinitely
- Position leaks due to unfilled orders
- Capital lock-up in pending orders
- Temporal anomalies (future timestamps)

Main Features:
- Order creation with explicit timeouts
- Periodic timeout checks
- Force-close logic with fallback actions
- Event logging for order lifecycle
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from structlog import get_logger
from enum import Enum
import math

logger = get_logger(__name__)


class OrderStatus(Enum):
    """Order lifecycle status — aligned with execution.base.OrderStatus."""
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


class OrderLifecycleEvent(Enum):
    """Order lifecycle event types."""
    CREATED = "created"
    UPDATED = "updated"
    FILLED = "filled"
    TIMEOUT = "timeout"
    FORCE_CLOSED = "force_closed"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class OrderLifecycle:
    """Complete order lifecycle record."""
    order_id: str
    symbol: str
    status: OrderStatus
    created_at: datetime
    timeout_at: datetime
    last_update: datetime
    filled_quantity: float = 0.0
    initial_quantity: float = 0.0
    price: float = 0.0
    events: List[Tuple[OrderLifecycleEvent, datetime, str]] = field(default_factory=list)
    
    def add_event(self, event: OrderLifecycleEvent, message: str = "") -> None:
        """Record an event in the order lifecycle."""
        self.events.append((event, datetime.utcnow(), message))
        self.last_update = datetime.utcnow()
    
    def is_expired(self) -> bool:
        """Check if order has exceeded timeout."""
        return datetime.utcnow() > self.timeout_at
    
    def time_remaining_seconds(self) -> float:
        """Get seconds remaining before timeout."""
        remaining = (self.timeout_at - datetime.utcnow()).total_seconds()
        return max(0, remaining)
    
    def get_event_count(self, event_type: OrderLifecycleEvent) -> int:
        """Count how many times a specific event occurred."""
        return sum(1 for evt, _, _ in self.events if evt == event_type)


class OrderLifecycleManager:
    """
    Manages order creation, tracking, and timeout enforcement.
    
    Responsibilities:
    1. Track order lifecycle with timestamps
    2. Enforce timeout limits
    3. Detect stale orders
    4. Force-close expired orders
    5. Log all lifecycle events
    6. Provide remediation suggestions
    """
    
    def __init__(
        self,
        default_timeout_seconds: float = 300.0,
        check_interval_seconds: float = 10.0,
        max_retries: int = 3
    ):
        """
        Initialize order lifecycle manager.
        
        Args:
            default_timeout_seconds: Default timeout for all orders (5 min)
            check_interval_seconds: How often to check for timeouts
            max_retries: Max force-close retry attempts per order
        
        Raises:
            ValueError: If parameters are invalid
        """
        if default_timeout_seconds <= 0:
            raise ValueError(f"Timeout must be positive, got {default_timeout_seconds}")
        if check_interval_seconds <= 0:
            raise ValueError(f"Check interval must be positive, got {check_interval_seconds}")
        if max_retries < 1:
            raise ValueError(f"Must allow at least 1 retry, got {max_retries}")
        
        self.default_timeout_seconds = default_timeout_seconds
        self.check_interval_seconds = check_interval_seconds
        self.max_retries = max_retries
        
        self.orders: Dict[str, OrderLifecycle] = {}
        self.last_timeout_check = datetime.utcnow()
        self.force_close_attempts: Dict[str, int] = {}
        
        logger.info(
            "order_lifecycle_manager_initialized",
            default_timeout=default_timeout_seconds,
            check_interval=check_interval_seconds,
            max_retries=max_retries
        )
    
    def create_order(
        self,
        order_id: str,
        symbol: str,
        quantity: float,
        price: float,
        timeout_seconds: Optional[float] = None
    ) -> OrderLifecycle:
        """
        Create a new tracked order.
        
        Args:
            order_id: Unique order identifier
            symbol: Trading symbol (e.g., "AAPL")
            quantity: Order quantity
            price: Order price
            timeout_seconds: Custom timeout (defaults to default_timeout_seconds)
        
        Returns:
            OrderLifecycle object
        
        Raises:
            ValueError: If inputs are invalid
            RuntimeError: If order_id already exists
        """
        if order_id in self.orders:
            raise RuntimeError(f"Order {order_id} already exists")
        
        import re as _re
        if not symbol:
            raise ValueError(f"Invalid symbol: {symbol}")
        # Accept equity tickers (1-5 uppercase letters) or BASE/QUOTE pairs
        is_equity = _re.match(r'^[A-Za-z]{1,5}$', symbol) is not None
        is_pair = '/' in symbol
        if not is_equity and not is_pair:
            raise ValueError(f"Invalid symbol: {symbol}")
        
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {quantity}")
        
        if price <= 0:
            raise ValueError(f"Price must be positive, got {price}")
        
        timeout = timeout_seconds or self.default_timeout_seconds
        if timeout <= 0:
            raise ValueError(f"Timeout must be positive, got {timeout}")
        
        now = datetime.utcnow()
        timeout_at = now + timedelta(seconds=timeout)
        
        lifecycle = OrderLifecycle(
            order_id=order_id,
            symbol=symbol,
            status=OrderStatus.PENDING,
            created_at=now,
            timeout_at=timeout_at,
            last_update=now,
            initial_quantity=quantity,
            price=price
        )
        
        lifecycle.add_event(OrderLifecycleEvent.CREATED, f"Order {order_id} created")
        self.orders[order_id] = lifecycle
        self.force_close_attempts[order_id] = 0
        
        logger.info(
            "order_created",
            order_id=order_id,
            symbol=symbol,
            quantity=quantity,
            price=price,
            timeout_seconds=timeout
        )
        
        return lifecycle
    
    def update_order(
        self,
        order_id: str,
        filled_quantity: float,
        status: OrderStatus,
        message: str = ""
    ) -> OrderLifecycle:
        """
        Update order status.
        
        Args:
            order_id: Order identifier
            filled_quantity: Quantity filled so far
            status: New order status
            message: Optional status message
        
        Returns:
            Updated OrderLifecycle
        
        Raises:
            KeyError: If order_id not found
            ValueError: If update is invalid
        """
        if order_id not in self.orders:
            raise KeyError(f"Order {order_id} not found")
        
        if filled_quantity < 0:
            raise ValueError(f"Filled quantity cannot be negative: {filled_quantity}")
        
        lifecycle = self.orders[order_id]
        
        if filled_quantity > lifecycle.initial_quantity:
            raise ValueError(
                f"Filled quantity ({filled_quantity}) exceeds initial ({lifecycle.initial_quantity})"
            )
        
        lifecycle.status = status
        lifecycle.filled_quantity = filled_quantity
        lifecycle.add_event(OrderLifecycleEvent.UPDATED, message)
        
        if status == OrderStatus.FILLED:
            lifecycle.add_event(OrderLifecycleEvent.FILLED, f"Order fully filled")
        elif status == OrderStatus.CANCELLED:
            lifecycle.add_event(OrderLifecycleEvent.CANCELLED, "Order cancelled")
        
        logger.info(
            "order_updated",
            order_id=order_id,
            status=status.value,
            filled_quantity=filled_quantity,
            message=message
        )
        
        return lifecycle
    
    def check_for_timeouts(self) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Check for expired orders and generate remediation actions.
        
        Returns:
            Tuple of (expired_order_ids: List[str], remediation_actions: List[Dict])
        
        Raises:
            ValueError: If check encounters invalid state
        """
        now = datetime.utcnow()
        expired_orders = []
        remediation_actions = []
        
        # Only check if enough time has elapsed
        time_since_check = (now - self.last_timeout_check).total_seconds()
        if time_since_check < self.check_interval_seconds:
            return [], []
        
        self.last_timeout_check = now
        
        for order_id, lifecycle in self.orders.items():
            # Skip already resolved orders
            if lifecycle.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.TIMEOUT]:
                continue
            
            # Check if expired
            if lifecycle.is_expired():
                remaining = lifecycle.time_remaining_seconds()
                
                if remaining <= 0:
                    # Mark as timed out
                    lifecycle.status = OrderStatus.TIMEOUT
                    lifecycle.add_event(OrderLifecycleEvent.TIMEOUT, "Order timeout exceeded")
                    expired_orders.append(order_id)
                    
                    logger.warning(
                        "order_timeout_detected",
                        order_id=order_id,
                        symbol=lifecycle.symbol,
                        timeout_at=lifecycle.timeout_at
                    )
                    
                    # Suggest remediation
                    action = {
                        "order_id": order_id,
                        "symbol": lifecycle.symbol,
                        "action": "force_close",
                        "reason": f"Order expired {abs(remaining):.1f}s ago",
                        "filled_quantity": lifecycle.filled_quantity,
                        "outstanding_quantity": lifecycle.initial_quantity - lifecycle.filled_quantity
                    }
                    remediation_actions.append(action)
        
        if expired_orders:
            logger.info(
                "timeout_check_complete",
                expired_count=len(expired_orders),
                expired_orders=expired_orders
            )
        
        return expired_orders, remediation_actions
    
    def force_close_order(
        self,
        order_id: str,
        close_price: float,
        close_quantity: float,
        reason: str = "timeout"
    ) -> Tuple[bool, str]:
        """
        Force-close an expired order.
        
        Args:
            order_id: Order to close
            close_price: Price at which to close
            close_quantity: Quantity to close
            reason: Reason for force-close
        
        Returns:
            Tuple of (success: bool, message: str)
        
        Raises:
            KeyError: If order not found
            ValueError: If parameters invalid
        """
        if order_id not in self.orders:
            raise KeyError(f"Order {order_id} not found")
        
        if close_price <= 0:
            raise ValueError(f"Close price must be positive: {close_price}")
        
        if close_quantity <= 0:
            raise ValueError(f"Close quantity must be positive: {close_quantity}")
        
        lifecycle = self.orders[order_id]
        
        # Track retry attempts
        self.force_close_attempts[order_id] = self.force_close_attempts.get(order_id, 0) + 1
        attempt = self.force_close_attempts[order_id]
        
        if attempt > self.max_retries:
            error_msg = f"Force-close exceeded max retries ({self.max_retries})"
            lifecycle.status = OrderStatus.ERROR
            lifecycle.add_event(OrderLifecycleEvent.ERROR, error_msg)
            logger.error("force_close_max_retries", order_id=order_id, attempts=attempt)
            return False, error_msg
        
        # Update order as force-closed
        lifecycle.status = OrderStatus.CANCELLED
        lifecycle.filled_quantity += close_quantity
        lifecycle.add_event(
            OrderLifecycleEvent.FORCE_CLOSED,
            f"Force-closed: {close_quantity} @ {close_price}, reason={reason}, attempt {attempt}/{self.max_retries}"
        )
        
        logger.info(
            "order_force_closed",
            order_id=order_id,
            symbol=lifecycle.symbol,
            close_price=close_price,
            close_quantity=close_quantity,
            reason=reason,
            attempt=attempt
        )
        
        return True, f"Force-closed {close_quantity} units @ {close_price}"
    
    def get_stale_orders(self, stale_threshold_seconds: float = 60.0) -> List[str]:
        """
        Get list of orders that are close to timeout.
        
        Args:
            stale_threshold_seconds: Consider stale if timeout in < this many seconds
        
        Returns:
            List of stale order IDs
        
        Raises:
            ValueError: If threshold is negative
        """
        if stale_threshold_seconds < 0:
            raise ValueError(f"Threshold cannot be negative: {stale_threshold_seconds}")
        
        stale_orders = []
        now = datetime.utcnow()
        
        for order_id, lifecycle in self.orders.items():
            if lifecycle.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.TIMEOUT]:
                continue
            
            time_to_timeout = (lifecycle.timeout_at - now).total_seconds()
            
            if 0 < time_to_timeout < stale_threshold_seconds:
                stale_orders.append(order_id)
        
        return stale_orders
    
    def get_order_statistics(self) -> Dict[str, Any]:
        """
        Get statistics on tracked orders.
        
        Returns:
            Dict with count statistics by status
        """
        stats = {
            "total_orders": len(self.orders),
            "by_status": {},
            "stale_count": 0,
            "expired_count": 0
        }
        
        # Count by status
        for status in OrderStatus:
            count = sum(1 for o in self.orders.values() if o.status == status)
            stats["by_status"][status.value] = count
        
        # Count stale and expired
        stale = self.get_stale_orders(60.0)
        stats["stale_count"] = len(stale)
        stats["expired_count"] = sum(1 for o in self.orders.values() if o.is_expired())
        
        return stats
    
    def cleanup_resolved_orders(self, older_than_seconds: float = 3600.0) -> int:
        """
        Remove resolved orders older than threshold (cleanup).
        
        Args:
            older_than_seconds: Remove if resolved > this many seconds ago
        
        Returns:
            Number of orders removed
        
        Raises:
            ValueError: If threshold is negative
        """
        if older_than_seconds < 0:
            raise ValueError(f"Threshold cannot be negative: {older_than_seconds}")
        
        cutoff_time = datetime.utcnow() - timedelta(seconds=older_than_seconds)
        orders_to_remove = []
        
        for order_id, lifecycle in self.orders.items():
            # Only remove if resolved and old
            if lifecycle.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.TIMEOUT]:
                if lifecycle.last_update < cutoff_time:
                    orders_to_remove.append(order_id)
        
        # Remove old resolved orders
        for order_id in orders_to_remove:
            del self.orders[order_id]
            del self.force_close_attempts[order_id]
        
        if orders_to_remove:
            logger.info("orders_cleanup", removed_count=len(orders_to_remove))
        
        return len(orders_to_remove)
