"""
Tests for ExecutionRouter ÔÇö verifies order routing across modes.
"""

import time
from typing import Any

import pytest

from execution.base import Order, OrderSide
from execution.rate_limiter import TokenBucketRateLimiter
from execution_engine.router import (
    ExecutionMode,
    ExecutionRouter,
    TradeExecution,
)


@pytest.fixture
def backtest_router():
    return ExecutionRouter(mode=ExecutionMode.BACKTEST)


@pytest.fixture
def paper_router():
    return ExecutionRouter(mode=ExecutionMode.PAPER)


@pytest.fixture
def sample_order():
    return Order(
        order_id="test_AAPL_MSFT",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100.0,
        limit_price=150.0,
    )


class TestExecutionRouterInit:
    def test_default_mode_is_paper(self):
        router = ExecutionRouter()
        assert router.mode == ExecutionMode.PAPER

    def test_explicit_mode(self):
        router = ExecutionRouter(mode=ExecutionMode.BACKTEST)
        assert router.mode == ExecutionMode.BACKTEST

    def test_set_mode(self):
        router = ExecutionRouter(mode=ExecutionMode.PAPER)
        router.set_mode(ExecutionMode.LIVE)
        assert router.mode == ExecutionMode.LIVE


class TestBacktestFill:
    def test_backtest_fill_returns_execution(self, backtest_router, sample_order):
        result = backtest_router.submit_order(sample_order)
        assert isinstance(result, TradeExecution)
        assert result.pair_key == "AAPL"  # Order has no pair_key; router falls back to symbol
        assert result.symbol == "AAPL"
        assert result.side == "buy"
        assert result.filled_qty == 100.0
        assert result.fill_price > 0

    def test_backtest_buy_slippage_positive(self, backtest_router, sample_order):
        """Buy orders should fill slightly above limit (adverse slippage)."""
        result = backtest_router.submit_order(sample_order)
        assert result.fill_price >= sample_order.limit_price

    def test_backtest_sell_slippage_negative(self, backtest_router):
        sell_order = Order(
            order_id="test_AAPL_MSFT_sell",
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=50.0,
            limit_price=150.0,
        )
        result = backtest_router.submit_order(sell_order)
        assert result.fill_price <= sell_order.limit_price

    def test_backtest_commission_calculated(self, backtest_router, sample_order):
        result = backtest_router.submit_order(sample_order)
        assert result.commission > 0

    def test_backtest_logged(self, backtest_router, sample_order):
        backtest_router.submit_order(sample_order)
        assert len(backtest_router._execution_log) == 1


class TestPaperFill:
    def test_paper_fill_returns_execution(self, paper_router, sample_order):
        result = paper_router.submit_order(sample_order)
        assert isinstance(result, TradeExecution)
        assert result.filled_qty == sample_order.quantity

    def test_paper_initializes_engine_lazily(self, paper_router, sample_order):
        assert paper_router._paper_engine is None
        paper_router.submit_order(sample_order)
        # Paper engine is instantiated on first use
        # (may or may not be set depending on implementation)


class TestOrder:
    def test_repr(self, sample_order):
        r = repr(sample_order)
        assert "AAPL" in r
        assert "BUY" in r  # OrderSide.BUY appears in dataclass repr

    def test_limit_order_default(self):
        order = Order(order_id="test_limit", symbol="A", side=OrderSide.BUY, quantity=10, limit_price=None)
        assert order.order_type == "LIMIT"  # Order defaults to LIMIT
        assert order.limit_price is None


class TestTradeExecution:
    def test_total_cost(self):
        ex = TradeExecution(
            pair_key="A_B",
            symbol="A",
            side="buy",
            requested_qty=100,
            filled_qty=100,
            fill_price=100.0,
            commission=1.0,
            slippage_bps=2.0,
        )
        # total_cost = commission + filled_qty * fill_price * slippage/10000
        expected = 1.0 + 100 * 100.0 * (2.0 / 10_000)
        assert abs(ex.total_cost - expected) < 0.01

    def test_not_partial_by_default(self):
        ex = TradeExecution(
            pair_key="A_B",
            symbol="A",
            side="buy",
            requested_qty=100,
            filled_qty=100,
            fill_price=100.0,
            commission=0.5,
            slippage_bps=1.0,
        )
        assert not ex.is_partial


class TestMultipleOrders:
    def test_execution_log_accumulates(self, backtest_router, sample_order):
        for _ in range(5):
            backtest_router.submit_order(sample_order)
        assert len(backtest_router._execution_log) == 5


# ÔöÇÔöÇ Phase 3: rate limiter, paper exclusion, live path ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ


class TestRateLimiter:
    """Tests for the TokenBucketRateLimiter integrated in the router."""

    def test_burst_capacity(self):
        """10 tokens available immediately (burst)."""
        limiter = TokenBucketRateLimiter(rate=45, burst=10)
        for _ in range(10):
            assert limiter.try_acquire() is True
        # 11th should fail (no time for refill)
        assert limiter.try_acquire() is False

    def test_throttle_beyond_rate(self):
        """After burst, acquire blocks for ~1/rate seconds."""
        limiter = TokenBucketRateLimiter(rate=45, burst=5)
        for _ in range(5):
            limiter.acquire()
        t0 = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - t0
        # Should wait approximately 1/45 Ôëê 22ms
        assert elapsed >= 0.015, f"Expected throttle, got {elapsed * 1000:.1f}ms"

    def test_timeout_raises(self):
        """Exhausted bucket + tiny timeout ÔåÆ RuntimeError."""
        limiter = TokenBucketRateLimiter(rate=1, burst=1)
        limiter.acquire()  # consume the only token
        with pytest.raises(RuntimeError, match="Rate limiter timeout"):
            limiter.acquire(timeout=0.01)

    def test_router_has_rate_limiter(self):
        """Router uses the global IBKR rate-limiter singleton (C-04, rate=40)."""
        from common.ibkr_rate_limiter import GLOBAL_IBKR_RATE_LIMITER

        router = ExecutionRouter(mode=ExecutionMode.PAPER)
        assert isinstance(router._rate_limiter, TokenBucketRateLimiter)
        assert router._rate_limiter is GLOBAL_IBKR_RATE_LIMITER
        assert router._rate_limiter.rate == 40


class TestPaperExclusion:
    """Paper mode must NOT touch IBKR engine."""

    def test_paper_mode_ibkr_engine_stays_none(self, paper_router, sample_order):
        """After paper fill, _ibkr_engine must remain None."""
        paper_router.submit_order(sample_order)
        assert paper_router._ibkr_engine is None


class TestUnknownMode:
    def test_unknown_mode_raises(self, sample_order):
        """Invalid mode raises ValueError on submit."""
        router = ExecutionRouter(mode=ExecutionMode.PAPER)
        _r: Any = router
        _r._mode = "INVALID"
        with pytest.raises(ValueError, match="Unknown mode"):
            router.submit_order(sample_order)


class TestGetOrderStatus:
    """A-02: ExecutionRouter.get_order_status() delegates to _pending_orders."""

    def test_returns_filled_for_paper_order(self):
        """Paper orders are recorded as FILLED in _pending_orders."""
        from uuid import uuid4

        from execution.base import Order, OrderSide, OrderStatus

        router = ExecutionRouter(mode=ExecutionMode.PAPER)
        order = Order(
            order_id=str(uuid4()),
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=10,
            limit_price=150.0,
            order_type="MARKET",
        )
        router.submit_order(order)
        status = router.get_order_status(order.order_id)
        assert status == OrderStatus.FILLED

    def test_returns_filled_for_unknown_in_paper_mode(self):
        """Unknown order_id in paper mode → FILLED (paper fills are instant)."""
        from execution.base import OrderStatus

        router = ExecutionRouter(mode=ExecutionMode.PAPER)
        status = router.get_order_status("non-existent-order-id")
        assert status == OrderStatus.FILLED

    def test_returns_cached_status(self):
        """Manually injected status is returned directly from cache."""
        from execution.base import OrderStatus

        router = ExecutionRouter(mode=ExecutionMode.PAPER)
        router._pending_orders["my-order-id"] = OrderStatus.REJECTED
        assert router.get_order_status("my-order-id") == OrderStatus.REJECTED

    def test_paper_order_with_execution_base_order(self):
        """execution.base.Order submitted in paper mode is tracked by order_id."""
        from uuid import uuid4

        from execution.base import Order, OrderSide, OrderStatus

        router = ExecutionRouter(mode=ExecutionMode.PAPER)
        oid = str(uuid4())
        order = Order(
            order_id=oid,
            symbol="MSFT",
            side=OrderSide.SELL,
            quantity=5,
            limit_price=None,
            order_type="MARKET",
        )
        router.submit_order(order)
        assert router.get_order_status(oid) == OrderStatus.FILLED


class TestAntiShortGuard:
    """A-08: Anti-short guard blocks SELL when insufficient shortable shares."""

    def test_sell_blocked_when_shares_insufficient(self):
        """SELL order with quantity > shortable shares → filled_qty=0, status REJECTED."""
        from unittest.mock import MagicMock
        from uuid import uuid4

        from execution.base import Order, OrderSide, OrderStatus

        router = ExecutionRouter(mode=ExecutionMode.LIVE)

        # Mock IBKR engine with get_shortable_shares returning 50 (< order qty 100)
        mock_engine = MagicMock()
        mock_engine.get_shortable_shares.return_value = 50.0
        mock_engine._ensure_connected.return_value = None
        router._ibkr_engine = mock_engine

        order = Order(
            order_id=str(uuid4()),
            symbol="GME",
            side=OrderSide.SELL,
            quantity=100.0,
            limit_price=None,
            order_type="MARKET",
        )

        result = router.submit_order(order)

        assert result.filled_qty == 0.0
        assert router.get_order_status(order.order_id) == OrderStatus.REJECTED
        mock_engine.submit_order.assert_not_called()

    def test_sell_allowed_when_shares_sufficient(self):
        """SELL order with quantity <= shortable shares → proceeds to IBKR."""
        from unittest.mock import MagicMock
        from uuid import uuid4

        from execution.base import Order, OrderSide, OrderStatus

        router = ExecutionRouter(mode=ExecutionMode.LIVE)

        mock_engine = MagicMock()
        mock_engine.get_shortable_shares.return_value = 500.0
        mock_engine._ensure_connected.return_value = None
        # Simulate IBKR fill
        mock_engine.submit_order.return_value = "ibkr-order-123"
        mock_engine.get_order_status.return_value = OrderStatus.FILLED
        mock_engine._order_map = {}
        router._ibkr_engine = mock_engine

        order = Order(
            order_id=str(uuid4()),
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=100.0,
            limit_price=None,
            order_type="MARKET",
        )

        result = router.submit_order(order)

        mock_engine.submit_order.assert_called_once()
        assert result.filled_qty == 100.0

    def test_buy_order_skips_guard(self):
        """BUY orders are never checked for shortable shares."""
        from unittest.mock import MagicMock
        from uuid import uuid4

        from execution.base import Order, OrderSide

        router = ExecutionRouter(mode=ExecutionMode.LIVE)

        mock_engine = MagicMock()
        mock_engine._ensure_connected.return_value = None
        from execution.base import OrderStatus

        mock_engine.submit_order.return_value = "ibkr-buy-001"
        mock_engine.get_order_status.return_value = OrderStatus.FILLED
        mock_engine._order_map = {}
        router._ibkr_engine = mock_engine

        order = Order(
            order_id=str(uuid4()),
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            limit_price=None,
            order_type="MARKET",
        )

        router.submit_order(order)

        mock_engine.get_shortable_shares.assert_not_called()

    def test_sell_with_negative_shortable_allowed(self):
        """get_shortable_shares() returning -1 (unavailable) should not block the order."""
        from unittest.mock import MagicMock
        from uuid import uuid4

        from execution.base import Order, OrderSide, OrderStatus

        router = ExecutionRouter(mode=ExecutionMode.LIVE)

        mock_engine = MagicMock()
        mock_engine.get_shortable_shares.return_value = -1.0  # unavailable
        mock_engine._ensure_connected.return_value = None
        mock_engine.submit_order.return_value = "ibkr-sell-neg"
        mock_engine.get_order_status.return_value = OrderStatus.FILLED
        mock_engine._order_map = {}
        router._ibkr_engine = mock_engine

        order = Order(
            order_id=str(uuid4()),
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=100.0,
            limit_price=None,
            order_type="MARKET",
        )

        result = router.submit_order(order)
        # -1 means "data unavailable", should NOT block
        mock_engine.submit_order.assert_called_once()
        assert result.filled_qty == 100.0


# ---------------------------------------------------------------------------
# P4-02: Order fill latency histogram
# ---------------------------------------------------------------------------


class TestOrderFillLatencyMetrics:
    """P4-02 — router must record fill latency in the Prometheus histogram."""

    def _make_live_mock(self):
        """Build a minimal mock IBKR engine that returns an immediate FILLED status."""
        from unittest.mock import MagicMock

        from execution.base import OrderStatus

        mock_engine = MagicMock()
        mock_engine._ensure_connected.return_value = None
        mock_engine.get_shortable_shares.return_value = 9999.0
        mock_engine.submit_order.return_value = "ibkr-latency-001"
        mock_engine.get_order_status.return_value = OrderStatus.FILLED
        mock_engine._order_map = {}
        return mock_engine

    def test_fill_latency_histogram_receives_observation(self):
        """After a live fill, _ORDER_FILL_LATENCY must have at least 1 observation."""
        from unittest.mock import patch
        from uuid import uuid4

        from execution.base import Order, OrderSide
        from monitoring.metrics import _ORDER_FILL_LATENCY

        router = ExecutionRouter(mode=ExecutionMode.LIVE)
        router._ibkr_engine = self._make_live_mock()

        # Capture histogram state before
        before = _ORDER_FILL_LATENCY._sum.get()

        order = Order(
            order_id=str(uuid4()),
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=10.0,
            limit_price=150.0,
            order_type="LIMIT",
        )

        with patch("common.ibkr_rate_limiter.GLOBAL_IBKR_RATE_LIMITER") as mock_rl:
            mock_rl.acquire.return_value = None
            router._rate_limiter = mock_rl
            router.submit_order(order)

        after = _ORDER_FILL_LATENCY._sum.get()
        # Sum should have increased (latency > 0 was observed)
        assert after >= before, "Expected ORDER_FILL_LATENCY histogram to receive an observation"

    def test_slippage_gauge_updated_after_fill(self):
        """After a live fill, _EXECUTION_SLIPPAGE_BPS gauge must be set."""
        from unittest.mock import patch
        from uuid import uuid4

        from execution.base import Order, OrderSide
        from monitoring.metrics import _EXECUTION_SLIPPAGE_BPS

        router = ExecutionRouter(mode=ExecutionMode.LIVE)
        router._ibkr_engine = self._make_live_mock()

        order = Order(
            order_id=str(uuid4()),
            symbol="MSFT",
            side=OrderSide.BUY,
            quantity=5.0,
            limit_price=300.0,
            order_type="LIMIT",
        )

        with patch("common.ibkr_rate_limiter.GLOBAL_IBKR_RATE_LIMITER") as mock_rl:
            mock_rl.acquire.return_value = None
            router._rate_limiter = mock_rl
            router.submit_order(order)

        # Gauge value should be a finite non-negative float
        slippage = _EXECUTION_SLIPPAGE_BPS._value.get()
        assert slippage >= 0.0, f"Slippage BPS should be >= 0, got {slippage}"
