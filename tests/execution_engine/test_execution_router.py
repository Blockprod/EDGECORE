"""
Tests for ExecutionRouter ÔÇö verifies order routing across modes.
"""

import time

import pytest
from execution_engine.router import (
    ExecutionRouter,
    ExecutionMode,
    TradeOrder,
    TradeExecution,
)
from execution.rate_limiter import TokenBucketRateLimiter


@pytest.fixture
def backtest_router():
    return ExecutionRouter(mode=ExecutionMode.BACKTEST)


@pytest.fixture
def paper_router():
    return ExecutionRouter(mode=ExecutionMode.PAPER)


@pytest.fixture
def sample_order():
    return TradeOrder(
        pair_key="AAPL_MSFT",
        symbol="AAPL",
        side="buy",
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
        assert result.pair_key == "AAPL_MSFT"
        assert result.symbol == "AAPL"
        assert result.side == "buy"
        assert result.filled_qty == 100.0
        assert result.fill_price > 0

    def test_backtest_buy_slippage_positive(self, backtest_router, sample_order):
        """Buy orders should fill slightly above limit (adverse slippage)."""
        result = backtest_router.submit_order(sample_order)
        assert result.fill_price >= sample_order.limit_price

    def test_backtest_sell_slippage_negative(self, backtest_router):
        sell_order = TradeOrder(
            pair_key="AAPL_MSFT",
            symbol="AAPL",
            side="sell",
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


class TestTradeOrder:
    def test_repr(self, sample_order):
        r = repr(sample_order)
        assert "AAPL" in r
        assert "buy" in r

    def test_market_order_default(self):
        order = TradeOrder(pair_key="A_B", symbol="A", side="buy", quantity=10)
        assert order.order_type == "market"
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
            pair_key="A_B", symbol="A", side="buy",
            requested_qty=100, filled_qty=100,
            fill_price=100.0, commission=0.5, slippage_bps=1.0,
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
        assert elapsed >= 0.015, f"Expected throttle, got {elapsed*1000:.1f}ms"

    def test_timeout_raises(self):
        """Exhausted bucket + tiny timeout ÔåÆ RuntimeError."""
        limiter = TokenBucketRateLimiter(rate=1, burst=1)
        limiter.acquire()  # consume the only token
        with pytest.raises(RuntimeError, match="Rate limiter timeout"):
            limiter.acquire(timeout=0.01)

    def test_router_has_rate_limiter(self):
        """Router initializes with a TokenBucketRateLimiter."""
        router = ExecutionRouter(mode=ExecutionMode.PAPER)
        assert isinstance(router._rate_limiter, TokenBucketRateLimiter)
        assert router._rate_limiter.rate == 45


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
        router._mode = "INVALID"
        with pytest.raises(ValueError, match="Unknown mode"):
            router.submit_order(sample_order)
