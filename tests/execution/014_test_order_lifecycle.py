"""Tests for order lifecycle management."""

import pytest
from datetime import datetime, timedelta, timezone
from time import sleep
from execution.order_lifecycle import (
    OrderLifecycleManager,
    OrderStatus,
    OrderLifecycleEvent,
    OrderLifecycle
)


class TestOrderLifecycle:
    """Test OrderLifecycle record properties."""
    
    def test_create_order_lifecycle(self):
        """Test creating order lifecycle record."""
        now = datetime.now(timezone.utc)
        timeout = now + timedelta(seconds=300)
        
        lifecycle = OrderLifecycle(
            order_id="order_1",
            symbol="AAPL",
            status=OrderStatus.PENDING,
            created_at=now,
            timeout_at=timeout,
            last_update=now,
            initial_quantity=1.0,
            price=50000.0
        )
        
        assert lifecycle.order_id == "order_1"
        assert lifecycle.symbol == "AAPL"
        assert not lifecycle.is_expired()
    
    def test_order_lifecycle_is_expired(self):
        """Test expiration detection."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(seconds=60)  # 1 minute ago
        
        lifecycle = OrderLifecycle(
            order_id="order_1",
            symbol="AAPL",
            status=OrderStatus.PENDING,
            created_at=now,
            timeout_at=past,  # Already expired
            last_update=now
        )
        
        assert lifecycle.is_expired()
    
    def test_order_lifecycle_add_event(self):
        """Test adding events to lifecycle."""
        lifecycle = OrderLifecycle(
            order_id="order_1",
            symbol="AAPL",
            status=OrderStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            timeout_at=datetime.now(timezone.utc) + timedelta(seconds=300),
            last_update=datetime.now(timezone.utc)
        )
        
        lifecycle.add_event(OrderLifecycleEvent.CREATED, "Order created")
        lifecycle.add_event(OrderLifecycleEvent.UPDATED, "Price improved")
        
        assert len(lifecycle.events) == 2
        assert lifecycle.get_event_count(OrderLifecycleEvent.CREATED) == 1
    
    def test_order_lifecycle_time_remaining(self):
        """Test time remaining calculation."""
        now = datetime.now(timezone.utc)
        timeout = now + timedelta(seconds=100)
        
        lifecycle = OrderLifecycle(
            order_id="order_1",
            symbol="AAPL",
            status=OrderStatus.PENDING,
            created_at=now,
            timeout_at=timeout,
            last_update=now
        )
        
        remaining = lifecycle.time_remaining_seconds()
        assert 95 < remaining <= 100


class TestOrderLifecycleManagerInit:
    """Test manager initialization."""
    
    def test_init_with_defaults(self):
        """Test manager initialization with defaults."""
        manager = OrderLifecycleManager()
        
        assert manager.default_timeout_seconds == 300.0
        assert len(manager.orders) == 0
    
    def test_init_with_custom_values(self):
        """Test manager initialization with custom values."""
        manager = OrderLifecycleManager(
            default_timeout_seconds=600.0,
            check_interval_seconds=20.0,
            max_retries=5
        )
        
        assert manager.default_timeout_seconds == 600.0
        assert manager.check_interval_seconds == 20.0
        assert manager.max_retries == 5
    
    def test_init_with_invalid_timeout(self):
        """Test that invalid timeout raises error."""
        with pytest.raises(ValueError):
            OrderLifecycleManager(default_timeout_seconds=0)
    
    def test_init_with_invalid_check_interval(self):
        """Test that invalid check interval raises error."""
        with pytest.raises(ValueError):
            OrderLifecycleManager(check_interval_seconds=-1.0)
    
    def test_init_with_invalid_max_retries(self):
        """Test that invalid max retries raises error."""
        with pytest.raises(ValueError):
            OrderLifecycleManager(max_retries=0)


class TestOrderCreation:
    """Test order creation."""
    
    def test_create_order_basic(self):
        """Test creating a basic order."""
        manager = OrderLifecycleManager()
        
        lifecycle = manager.create_order(
            order_id="order_1",
            symbol="AAPL",
            quantity=1.0,
            price=50000.0
        )
        
        assert lifecycle.order_id == "order_1"
        assert lifecycle.symbol == "AAPL"
        assert lifecycle.initial_quantity == 1.0
        assert lifecycle.status == OrderStatus.PENDING
        assert lifecycle.order_id in manager.orders
    
    def test_create_order_with_custom_timeout(self):
        """Test creating order with custom timeout."""
        manager = OrderLifecycleManager()
        
        lifecycle = manager.create_order(
            order_id="order_1",
            symbol="AAPL",
            quantity=1.0,
            price=50000.0,
            timeout_seconds=600.0
        )
        
        remaining = lifecycle.time_remaining_seconds()
        assert 595 < remaining <= 600
    
    def test_create_order_invalid_symbol(self):
        """Test that invalid symbol raises error."""
        manager = OrderLifecycleManager()
        
        with pytest.raises(ValueError):
            manager.create_order(
                order_id="order_1",
                symbol="$$INVALID$$",  # Non-alphanumeric symbol
                quantity=1.0,
                price=50000.0
            )
        
        with pytest.raises(ValueError):
            manager.create_order(
                order_id="order_1",
                symbol="AAPL",
                quantity=-1.0,
                price=50000.0
            )
    
    def test_create_order_invalid_price(self):
        """Test that invalid price raises error."""
        manager = OrderLifecycleManager()
        
        with pytest.raises(ValueError):
            manager.create_order(
                order_id="order_1",
                symbol="AAPL",
                quantity=1.0,
                price=0.0
            )
    
    def test_create_order_duplicate_id(self):
        """Test that duplicate order ID raises error."""
        manager = OrderLifecycleManager()
        
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        
        with pytest.raises(RuntimeError):
            manager.create_order("order_1", "MSFT", 1.0, 2000.0)


class TestOrderUpdate:
    """Test order status updates."""
    
    def test_update_order_basic(self):
        """Test updating order status."""
        manager = OrderLifecycleManager()
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        
        lifecycle = manager.update_order(
            order_id="order_1",
            filled_quantity=0.5,
            status=OrderStatus.PARTIALLY_FILLED,
            message="Half filled"
        )
        
        assert lifecycle.filled_quantity == 0.5
        assert lifecycle.status == OrderStatus.PARTIALLY_FILLED
        assert lifecycle.get_event_count(OrderLifecycleEvent.UPDATED) == 1
    
    def test_update_order_to_filled(self):
        """Test updating order to filled status."""
        manager = OrderLifecycleManager()
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        
        lifecycle = manager.update_order(
            order_id="order_1",
            filled_quantity=1.0,
            status=OrderStatus.FILLED
        )
        
        assert lifecycle.status == OrderStatus.FILLED
        assert lifecycle.get_event_count(OrderLifecycleEvent.FILLED) == 1
    
    def test_update_order_filled_exceeds_quantity(self):
        """Test that filled > initial raises error."""
        manager = OrderLifecycleManager()
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        
        with pytest.raises(ValueError):
            manager.update_order(
                order_id="order_1",
                filled_quantity=1.5,
                status=OrderStatus.PARTIALLY_FILLED
            )
    
    def test_update_order_negative_filled(self):
        """Test that negative filled raises error."""
        manager = OrderLifecycleManager()
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        
        with pytest.raises(ValueError):
            manager.update_order(
                order_id="order_1",
                filled_quantity=-0.5,
                status=OrderStatus.PARTIALLY_FILLED
            )
    
    def test_update_nonexistent_order(self):
        """Test that updating nonexistent order raises error."""
        manager = OrderLifecycleManager()
        
        with pytest.raises(KeyError):
            manager.update_order("order_1", 0.5, OrderStatus.PARTIALLY_FILLED)


class TestTimeoutDetection:
    """Test timeout detection logic."""
    
    def test_check_for_timeouts_no_expired(self):
        """Test timeout check when no orders expired."""
        manager = OrderLifecycleManager(default_timeout_seconds=300.0)
        
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        
        expired, actions = manager.check_for_timeouts()
        
        assert len(expired) == 0
        assert len(actions) == 0
    
    def test_check_for_timeouts_order_expired(self):
        """Test timeout check when order has expired."""
        manager = OrderLifecycleManager(
            default_timeout_seconds=0.1,  # 100ms timeout
            check_interval_seconds=0.05
        )
        
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        
        # Wait for timeout
        sleep(0.2)
        
        expired, actions = manager.check_for_timeouts()
        
        assert len(expired) > 0
        assert "order_1" in expired
        assert len(actions) > 0
    
    def test_timeout_action_includes_remediation(self):
        """Test that timeout action includes remediation suggestions."""
        manager = OrderLifecycleManager(
            default_timeout_seconds=0.1,
            check_interval_seconds=0.05
        )
        
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        sleep(0.2)
        
        expired, actions = manager.check_for_timeouts()
        
        assert len(actions) > 0
        action = actions[0]
        assert action["action"] == "force_close"
        assert action["symbol"] == "AAPL"


class TestForceClose:
    """Test force-close functionality."""
    
    def test_force_close_order(self):
        """Test force-closing an order."""
        manager = OrderLifecycleManager()
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        
        success, message = manager.force_close_order(
            order_id="order_1",
            close_price=49900.0,
            close_quantity=1.0,
            reason="timeout"
        )
        
        assert success
        assert "Force-closed" in message
        assert manager.orders["order_1"].status == OrderStatus.CANCELLED
    
    def test_force_close_nonexistent_order(self):
        """Test force-closing nonexistent order raises error."""
        manager = OrderLifecycleManager()
        
        with pytest.raises(KeyError):
            manager.force_close_order("order_1", 49900.0, 1.0)
    
    def test_force_close_invalid_price(self):
        """Test that invalid close price raises error."""
        manager = OrderLifecycleManager()
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        
        with pytest.raises(ValueError):
            manager.force_close_order("order_1", 0.0, 1.0)
    
    def test_force_close_invalid_quantity(self):
        """Test that invalid close quantity raises error."""
        manager = OrderLifecycleManager()
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        
        with pytest.raises(ValueError):
            manager.force_close_order("order_1", 49900.0, -1.0)
    
    def test_force_close_max_retries_exceeded(self):
        """Test that exceeding max retries fails."""
        manager = OrderLifecycleManager(max_retries=2)
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        
        # Try 3 force closes (max is 2)
        manager.force_close_order("order_1", 49900.0, 0.3)
        manager.force_close_order("order_1", 49900.0, 0.3)
        
        success, message = manager.force_close_order("order_1", 49900.0, 0.4)
        
        assert not success
        assert "max retries" in message.lower()


class TestStaleOrders:
    """Test stale order detection."""
    
    def test_get_stale_orders_none_stale(self):
        """Test stale detection when no orders stale."""
        manager = OrderLifecycleManager()
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        
        stale = manager.get_stale_orders(stale_threshold_seconds=60.0)
        
        assert len(stale) == 0
    
    def test_get_stale_orders_upcoming_timeout(self):
        """Test stale detection for orders close to timeout."""
        manager = OrderLifecycleManager(default_timeout_seconds=50.0)
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        
        # This order will timeout in ~50s, within 60s threshold
        stale = manager.get_stale_orders(stale_threshold_seconds=60.0)
        
        assert len(stale) == 1
        assert "order_1" in stale
    
    def test_get_stale_orders_invalid_threshold(self):
        """Test that invalid threshold raises error."""
        manager = OrderLifecycleManager()
        
        with pytest.raises(ValueError):
            manager.get_stale_orders(stale_threshold_seconds=-1.0)


class TestOrderStatistics:
    """Test order statistics tracking."""
    
    def test_order_statistics_empty(self):
        """Test statistics with no orders."""
        manager = OrderLifecycleManager()
        
        stats = manager.get_order_statistics()
        
        assert stats["total_orders"] == 0
        assert stats["stale_count"] == 0
    
    def test_order_statistics_mixed_status(self):
        """Test statistics with various order statuses."""
        manager = OrderLifecycleManager()
        
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        manager.create_order("order_2", "MSFT", 10.0, 2000.0)
        
        manager.update_order("order_1", 1.0, OrderStatus.FILLED)
        
        stats = manager.get_order_statistics()
        
        assert stats["total_orders"] == 2
        assert stats["by_status"]["FILLED"] >= 1
        assert stats["by_status"]["PENDING"] >= 1


class TestOrderCleanup:
    """Test order cleanup."""
    
    def test_cleanup_resolved_orders(self):
        """Test cleanup of old resolved orders."""
        manager = OrderLifecycleManager()
        
        # Create and immediately mark as filled
        lifecycle = manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        manager.update_order("order_1", 1.0, OrderStatus.FILLED)
        
        # Manually set last_update to old time
        lifecycle.last_update = datetime.now(timezone.utc) - timedelta(seconds=3700)
        
        removed = manager.cleanup_resolved_orders(older_than_seconds=3600.0)
        
        assert removed >= 1
        assert "order_1" not in manager.orders
    
    def test_cleanup_keep_recent_orders(self):
        """Test that recent orders are not cleaned up."""
        manager = OrderLifecycleManager()
        
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        manager.update_order("order_1", 1.0, OrderStatus.FILLED)
        
        manager.cleanup_resolved_orders(older_than_seconds=3600.0)
        
        # Should not remove recent orders
        assert "order_1" in manager.orders
    
    def test_cleanup_invalid_threshold(self):
        """Test that invalid threshold raises error."""
        manager = OrderLifecycleManager()
        
        with pytest.raises(ValueError):
            manager.cleanup_resolved_orders(older_than_seconds=-1.0)


class TestOrderLifecycleIntegration:
    """Integration tests for complete workflows."""
    
    def test_typical_order_workflow(self):
        """Test typical order creation and fill workflow."""
        manager = OrderLifecycleManager()
        
        # Create order
        lifecycle = manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        assert lifecycle.status == OrderStatus.PENDING
        
        # Partial fill
        manager.update_order("order_1", 0.5, OrderStatus.PARTIALLY_FILLED, "Half filled")
        assert manager.orders["order_1"].filled_quantity == 0.5
        
        # Complete fill
        manager.update_order("order_1", 1.0, OrderStatus.FILLED, "Fully filled")
        assert manager.orders["order_1"].status == OrderStatus.FILLED
    
    def test_timeout_and_force_close_workflow(self):
        """Test timeout detection and force-close workflow."""
        manager = OrderLifecycleManager(
            default_timeout_seconds=0.1,
            check_interval_seconds=0.05
        )
        
        # Create order
        manager.create_order("order_1", "AAPL", 1.0, 50000.0)
        
        # Wait for timeout
        sleep(0.2)
        
        # Check for timeouts
        expired, actions = manager.check_for_timeouts()
        assert len(expired) > 0
        
        # Force close
        success, message = manager.force_close_order(
            "order_1",
            close_price=49900.0,
            close_quantity=0.5
        )
        assert success
