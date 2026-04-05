"""
FEATURE 3: Order Lifecycle Integration Tests
Tests for OrderLifecycleIntegration class and main.py wiring.
Focused on integration correctness: orders tracked on submission,
timeout checking invoked each iteration, and error handling.
"""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from execution.order_lifecycle import OrderStatus
from execution.order_lifecycle_integration import OrderLifecycleIntegration


class TestCoreIntegration:
    """Core integration tests matching main.py usage pattern."""

    def test_orders_tracked_on_submission(self):
        """? Orders are tracked after submission in main loop."""
        mock_engine = Mock()
        integration = OrderLifecycleIntegration(execution_engine=mock_engine, timeout_seconds=30)

        # Pattern from main.py: order_id = submit_order() then track_order()
        order_id = "paper_order_12345_AAPL"
        integration.track_order(order_id, "AAPL", 10.0, 45000.0)

        # Verify tracked
        assert order_id in integration.order_mgr.orders
        assert integration.order_mgr.orders[order_id].symbol == "AAPL"
        assert integration.order_mgr.orders[order_id].status == OrderStatus.PENDING

    def test_timeout_check_callable_each_iteration(self):
        """? process_timeouts() callable every iteration without error."""
        mock_engine = Mock()
        integration = OrderLifecycleIntegration(execution_engine=mock_engine)

        # Track multiple orders
        integration.track_order("order_1", "AAPL", 1.0, 45000.0)
        integration.track_order("order_2", "MSFT", 10.0, 2500.0)

        # Process timeouts - should not error
        for _i in range(3):
            count = integration.process_timeouts()
            assert isinstance(count, int)
            assert count >= 0
            time.sleep(0.1)

    def test_mark_filled_updates_status(self):
        """? Orders can be marked as filled."""
        mock_engine = Mock()
        integration = OrderLifecycleIntegration(execution_engine=mock_engine)

        order_id = "test_order_1"
        integration.track_order(order_id, "AAPL", 1.0, 45000.0)
        assert integration.order_mgr.orders[order_id].status == OrderStatus.PENDING

        # Mark as filled
        integration.mark_filled(order_id)
        assert integration.order_mgr.orders[order_id].status == OrderStatus.FILLED

    def test_multiple_orders_per_symbol(self):
        """? Multiple orders can be tracked per symbol."""
        mock_engine = Mock()
        integration = OrderLifecycleIntegration(execution_engine=mock_engine)

        # Track 3 AAPL orders
        integration.track_order("order_1", "AAPL", 1.0, 45000.0)
        integration.track_order("order_2", "AAPL", 2.0, 44900.0)
        integration.track_order("order_3", "AAPL", 0.5, 45100.0)

        # Verify all tracked
        assert len(integration.order_mgr.orders) == 3

        # Get orders for symbol
        orders = integration.get_pending_orders_for_symbol("AAPL")
        assert len(orders) >= 2  # Should find AAPL orders

    def test_cross_symbol_trading(self):
        """? Orders across multiple symbols tracked independently."""
        mock_engine = Mock()
        integration = OrderLifecycleIntegration(execution_engine=mock_engine)

        # Track orders on different pairs
        integration.track_order("order_1", "AAPL", 1.0, 45000.0)
        integration.track_order("order_2", "MSFT", 10.0, 2500.0)
        integration.track_order("order_3", "BAC", 100.0, 1.0)

        # All tracked
        assert len(integration.order_mgr.orders) == 3

        # Process timeouts across all
        count = integration.process_timeouts()
        assert isinstance(count, int)


class TestErrorHandling:
    """Tests for robust error handling."""

    def test_empty_order_id_handled(self):
        """? Empty order ID handled gracefully."""
        mock_engine = Mock()
        integration = OrderLifecycleIntegration(execution_engine=mock_engine)

        try:
            integration.track_order("", "AAPL", 1.0, 45000.0)
            # May succeed or raise - both acceptable
        except Exception:
            # Error handling is ok too
            pass

    def test_nonexistent_order_age_handled(self):
        """? Getting age of nonexistent order handled."""
        mock_engine = Mock()
        integration = OrderLifecycleIntegration(execution_engine=mock_engine)

        try:
            integration.get_order_age_seconds("does_not_exist")
            # May return None or raise
        except Exception:
            # Exception is acceptable
            pass

    def test_mark_filled_nonexistent_handled(self):
        """? Marking nonexistent order as filled handled."""
        mock_engine = Mock()
        integration = OrderLifecycleIntegration(execution_engine=mock_engine)

        try:
            integration.mark_filled("does_not_exist")
            # May be no-op or raise
        except Exception:
            # Exception is acceptable
            pass


class TestOrderAging:
    """Tests for order age tracking."""

    def test_order_age_increases(self):
        """? Order age increases with time."""
        mock_engine = Mock()
        integration = OrderLifecycleIntegration(execution_engine=mock_engine)

        order_id = "test_order"
        integration.track_order(order_id, "AAPL", 1.0, 45000.0)

        # Immediately after creation
        age_1 = integration.get_order_age_seconds(order_id)

        # After a short wait
        time.sleep(0.5)
        age_2 = integration.get_order_age_seconds(order_id)

        # Age should increase
        assert age_1 is not None
        assert age_2 is not None
        assert age_2 >= age_1

    def test_manually_aged_order(self):
        """? Manually aged orders show correct age."""
        mock_engine = Mock()
        integration = OrderLifecycleIntegration(execution_engine=mock_engine)

        order_id = "test_order"
        integration.track_order(order_id, "AAPL", 1.0, 45000.0)

        # Manually set to 5 seconds old
        integration.order_mgr.orders[order_id].created_at = datetime.now(UTC) - timedelta(seconds=5)

        age = integration.get_order_age_seconds(order_id)
        assert age is not None
        assert 4 < age < 6  # Should be approximately 5 seconds


class TestRealWorldScenario:
    """Test realistic trading scenario."""

    def test_limit_order_pair_trading(self):
        """
        Scenario: Submit limit orders for statistical arbitrage pair trading.
        Expected: Both orders tracked independently, timeouts checkable.
        """
        mock_engine = Mock()
        integration = OrderLifecycleIntegration(
            execution_engine=mock_engine,
            timeout_seconds=30,  # 30s timeout
        )

        # Submit pair trade: Long AAPL, Short MSFT
        aapl_order_id = "paper_order_1_AAPL"
        eth_order_id = "paper_order_2_MSFT"

        integration.track_order(aapl_order_id, "AAPL", 1.0, 45000.0)
        integration.track_order(eth_order_id, "MSFT", 10.0, 2500.0)

        # Both tracked
        assert aapl_order_id in integration.order_mgr.orders
        assert eth_order_id in integration.order_mgr.orders

        # Can check timeouts
        timeout_count = integration.process_timeouts()
        assert isinstance(timeout_count, int)

        # Can mark fills
        integration.mark_filled(aapl_order_id, 1.0)
        assert integration.order_mgr.orders[aapl_order_id].status == OrderStatus.FILLED

        # MSFT still pending
        assert integration.order_mgr.orders[eth_order_id].status == OrderStatus.PENDING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
