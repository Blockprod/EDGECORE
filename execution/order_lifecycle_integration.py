"""
Order lifecycle integration with main trading loop.

Bridges OrderLifecycleManager with execution engine to:
- Track submitted orders
- Detect timeouts
- Cancel expired orders
- Log timeout events
"""

from datetime import UTC, datetime

from structlog import get_logger

from execution.base import BaseExecutionEngine
from execution.order_lifecycle import OrderLifecycleManager, OrderStatus

logger = get_logger(__name__)


class OrderLifecycleIntegration:
    """
    Integration layer connecting OrderLifecycleManager with execution engine.

    Responsibilities:
    - Track orders submitted to execution engine
    - Check for timeouts every iteration
    - Cancel timed-out orders
    - Log events
    """

    def __init__(self, execution_engine: BaseExecutionEngine, timeout_seconds: float = 30.0):
        """
        Initialize order lifecycle integration.

        Args:
            execution_engine: Execution engine for cancellations
            timeout_seconds: Default timeout for all orders
        """
        self.order_mgr = OrderLifecycleManager(
            default_timeout_seconds=timeout_seconds,
            check_interval_seconds=5.0,  # Check every 5s
        )
        self.execution_engine = execution_engine
        self.orders_by_symbol: dict[str, list[str]] = {}  # symbol -> order_ids

        logger.info("order_lifecycle_integration_initialized", timeout_seconds=timeout_seconds)

    def track_order(self, order_id: str, symbol: str, quantity: float = 0.0, price: float = 0.0) -> None:
        """
        Register order for timeout tracking.

        Args:
            order_id: Unique order identifier
            symbol: Trading pair
            quantity: Order quantity (optional)
            price: Order price (optional)

        Raises:
            ValueError: If order_id already tracked
        """
        try:
            # Track in manager
            self.order_mgr.create_order(
                order_id=order_id,
                symbol=symbol,
                quantity=quantity or 1.0,  # Default to 1 if not specified
                price=price or 1.0,  # Default to 1 if not specified
                timeout_seconds=None,  # Use default
            )

            # Track by symbol for quick lookup
            if symbol not in self.orders_by_symbol:
                self.orders_by_symbol[symbol] = []
            self.orders_by_symbol[symbol].append(order_id)

            logger.info("order_tracked_for_timeout", order_id=order_id, symbol=symbol, quantity=quantity, price=price)
        except Exception as e:
            logger.error("order_tracking_failed", order_id=order_id, symbol=symbol, error=str(e))
            raise

    def mark_filled(self, order_id: str, filled_quantity: float = 0.0) -> None:
        """
        Mark order as filled (removes from timeout tracking).

        Args:
            order_id: Order identifier
            filled_quantity: Quantity that was filled
        """
        try:
            if order_id in self.order_mgr.orders:
                self.order_mgr.update_order(
                    order_id=order_id,
                    filled_quantity=filled_quantity or self.order_mgr.orders[order_id].initial_quantity,
                    status=OrderStatus.FILLED,
                    message="Order filled",
                )
                logger.debug("order_marked_filled", order_id=order_id)
        except Exception as e:
            logger.error("mark_filled_failed", order_id=order_id, error=str(e))

    def process_timeouts(self) -> int:
        """
        Check for timed-out orders and cancel them.

        Returns:
            Number of orders cancelled due to timeout
        """
        try:
            expired_orders, _remediation_actions = self.order_mgr.check_for_timeouts()

            if not expired_orders:
                return 0

            cancelled_count = 0

            for order_id in expired_orders:
                try:
                    symbol = self.order_mgr.orders[order_id].symbol
                    age_seconds = (datetime.now(UTC) - self.order_mgr.orders[order_id].created_at).total_seconds()

                    # Cancel order on exchange
                    self.execution_engine.cancel_order(order_id)

                    # Mark as cancelled
                    self.order_mgr.update_order(
                        order_id=order_id,
                        filled_quantity=self.order_mgr.orders[order_id].filled_quantity,
                        status=OrderStatus.CANCELLED,
                        message="Auto-cancelled due to timeout",
                    )

                    logger.warning(
                        "order_timeout_cancelled",
                        order_id=order_id,
                        symbol=symbol,
                        age_seconds=age_seconds,
                        timeout_seconds=self.order_mgr.default_timeout_seconds,
                    )

                    cancelled_count += 1

                except Exception as e:
                    logger.error("timeout_cancellation_failed", order_id=order_id, error=str(e))

            if cancelled_count > 0:
                logger.warning(
                    "orders_auto_cancelled_due_to_timeout", cancelled_count=cancelled_count, order_ids=expired_orders
                )

            return cancelled_count

        except Exception as e:
            logger.error("timeout_processing_failed", error=str(e))
            return 0

    def get_pending_orders_for_symbol(self, symbol: str) -> list[str]:
        """
        Get list of pending orders for a symbol.

        Args:
            symbol: Trading pair

        Returns:
            List of pending order IDs
        """
        if symbol not in self.orders_by_symbol:
            return []

        return [
            oid
            for oid in self.orders_by_symbol[symbol]
            if oid in self.order_mgr.orders and self.order_mgr.orders[oid].status == OrderStatus.PENDING
        ]

    def get_order_age_seconds(self, order_id: str) -> float | None:
        """
        Get age of order in seconds.

        Args:
            order_id: Order identifier

        Returns:
            Age in seconds, or None if order not tracked
        """
        if order_id not in self.order_mgr.orders:
            return None

        lifecycle = self.order_mgr.orders[order_id]
        age = (datetime.now(UTC) - lifecycle.created_at).total_seconds()
        return max(0, age)
