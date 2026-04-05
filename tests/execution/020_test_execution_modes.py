"""
Tests for unified execution engine with pluggable modes.

Covers:
- Paper trading mode
- Live trading mode
- Backtest mode
- Order lifecycle
- Position management
- Account equity tracking
- Mode-agnostic execution interface
"""

from datetime import UTC, datetime

import pytest

# C-09: execution/modes.py renamed to modes_legacy.py (archived).
# This test file covers the legacy architecture; pending migration to ExecutionRouter.
from execution.modes_legacy import (
    BacktestMode,
    ExecutionContext,
    ExecutionEngine,
    LiveTradingMode,
    ModeType,
    Order,
    OrderStatus,
    PaperTradingMode,
    Position,
)


class TestOrder:
    """Test Order data structure."""

    def test_order_creation(self):
        """Test creating an order."""
        order = Order(order_id="TEST-001", symbol="AAPL", side="buy", quantity=1.0, price=50000.0, order_type="limit")

        assert order.order_id == "TEST-001"
        assert order.symbol == "AAPL"
        assert order.side == "buy"
        assert order.status == OrderStatus.PENDING

    def test_order_is_complete(self):
        """Test order completion detection."""
        order = Order(
            order_id="TEST-001",
            symbol="AAPL",
            side="buy",
            quantity=1.0,
            price=50000.0,
            order_type="limit",
            status=OrderStatus.FILLED,
        )

        assert order.is_complete is True

        order.status = OrderStatus.PENDING
        assert order.is_complete is False

    def test_order_fill_ratio(self):
        """Test order fill ratio calculation."""
        order = Order(
            order_id="TEST-001",
            symbol="AAPL",
            side="buy",
            quantity=10.0,
            price=50000.0,
            order_type="limit",
            filled_quantity=7.0,
        )

        assert order.fill_ratio == 0.7

    def test_order_full_fill_ratio(self):
        """Test 100% filled order."""
        order = Order(
            order_id="TEST-001",
            symbol="AAPL",
            side="buy",
            quantity=10.0,
            price=50000.0,
            order_type="limit",
            filled_quantity=10.0,
        )

        assert order.fill_ratio == 1.0


class TestPosition:
    """Test Position data structure."""

    def test_position_long(self):
        """Test long position."""
        position = Position(
            symbol="AAPL",
            quantity=1.0,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            current_price=51000.0,
        )

        assert position.side == "long"
        assert position.quantity == 1.0

    def test_position_short(self):
        """Test short position."""
        position = Position(
            symbol="AAPL",
            quantity=-1.0,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            current_price=49000.0,
        )

        assert position.side == "short"
        assert position.quantity == -1.0

    def test_position_pnl_long(self):
        """Test long position P&L calculation."""
        position = Position(
            symbol="AAPL",
            quantity=1.0,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            current_price=51000.0,
        )

        assert position.pnl == 1000.0

    def test_position_pnl_short(self):
        """Test short position P&L calculation."""
        position = Position(
            symbol="AAPL",
            quantity=-1.0,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            current_price=49000.0,
        )

        assert position.pnl == 1000.0  # Short profit

    def test_position_pnl_pct(self):
        """Test P&L percentage calculation."""
        position = Position(
            symbol="AAPL",
            quantity=1.0,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            current_price=55000.0,
        )

        expected_pnl_pct = ((55000 - 50000) / 50000) * 100
        assert abs(position.pnl_pct - expected_pnl_pct) < 0.01


class TestExecutionContext:
    """Test ExecutionContext shared state."""

    def test_context_creation(self):
        """Test creating execution context."""
        context = ExecutionContext(mode=ModeType.PAPER)

        assert context.mode == ModeType.PAPER
        assert context.equity == 10000.0
        assert len(context.orders) == 0
        assert len(context.positions) == 0

    def test_add_and_get_position(self):
        """Test position management."""
        context = ExecutionContext(mode=ModeType.PAPER)

        position = Position(
            symbol="AAPL",
            quantity=1.0,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            current_price=50000.0,
        )

        context.add_position(position)
        retrieved = context.get_position("AAPL")

        assert retrieved is not None
        assert retrieved.symbol == "AAPL"

    def test_remove_position(self):
        """Test position removal."""
        context = ExecutionContext(mode=ModeType.PAPER)

        position = Position(
            symbol="AAPL",
            quantity=1.0,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            current_price=50000.0,
        )

        context.add_position(position)
        removed = context.remove_position("AAPL")

        assert removed is not None
        assert context.get_position("AAPL") is None

    def test_add_and_get_order(self):
        """Test order management."""
        context = ExecutionContext(mode=ModeType.PAPER)

        order = Order(order_id="TEST-001", symbol="AAPL", side="buy", quantity=1.0, price=50000.0, order_type="limit")

        context.add_order(order)
        retrieved = context.get_order("TEST-001")

        assert retrieved is not None
        assert retrieved.order_id == "TEST-001"

    def test_update_order_status(self):
        """Test order status updates."""
        context = ExecutionContext(mode=ModeType.PAPER)

        order = Order(order_id="TEST-001", symbol="AAPL", side="buy", quantity=1.0, price=50000.0, order_type="limit")

        context.add_order(order)
        context.update_order_status("TEST-001", OrderStatus.FILLED)

        updated = context.get_order("TEST-001")
        assert updated is not None
        assert updated.status == OrderStatus.FILLED

    def test_update_market_price(self):
        """Test market price updates."""
        context = ExecutionContext(mode=ModeType.PAPER)

        context.market_prices["AAPL"] = 50000.0
        context.update_market_price("AAPL", 51000.0)

        assert context.market_prices["AAPL"] == 51000.0

    def test_total_position_value(self):
        """Test total position value calculation."""
        context = ExecutionContext(mode=ModeType.PAPER)

        # Add two positions
        pos1 = Position(
            symbol="AAPL",
            quantity=1.0,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            current_price=50000.0,
        )

        pos2 = Position(
            symbol="MSFT",
            quantity=10.0,
            entry_price=3000.0,
            entry_time=datetime.now(UTC),
            current_price=3000.0,
        )

        context.add_position(pos1)
        context.add_position(pos2)

        total = context.get_total_position_value()
        expected = 50000.0 + 30000.0
        assert total == expected

    def test_total_pnl(self):
        """Test total P&L calculation."""
        context = ExecutionContext(mode=ModeType.PAPER)

        pos1 = Position(
            symbol="AAPL",
            quantity=1.0,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            current_price=51000.0,  # +1000
        )

        pos2 = Position(
            symbol="MSFT",
            quantity=10.0,
            entry_price=3000.0,
            entry_time=datetime.now(UTC),
            current_price=2900.0,  # -1000
        )

        context.add_position(pos1)
        context.add_position(pos2)

        total_pnl = context.get_total_pnl()
        assert total_pnl == 0.0  # +1000 - 1000


class TestPaperTradingMode:
    """Test paper trading mode."""

    def test_paper_submit_market_order(self):
        """Test market order in paper mode."""
        context = ExecutionContext(mode=ModeType.PAPER)
        context.market_prices["AAPL"] = 50000.0

        mode = PaperTradingMode(context)
        order_id = mode.submit_order(symbol="AAPL", side="buy", quantity=1.0, order_type="market")

        assert order_id is not None
        order = context.get_order(order_id)
        assert order is not None
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 1.0

    def test_paper_submit_limit_order(self):
        """Test limit order in paper mode."""
        context = ExecutionContext(mode=ModeType.PAPER)
        context.market_prices["AAPL"] = 50000.0

        mode = PaperTradingMode(context)
        order_id = mode.submit_order(symbol="AAPL", side="buy", quantity=1.0, price=49500.0, order_type="limit")

        assert order_id is not None
        order = context.get_order(order_id)
        assert order is not None
        assert order.status == OrderStatus.PENDING  # Limit orders stay pending until filled

    def test_paper_submit_order_no_price(self):
        """Test order submission without market price."""
        context = ExecutionContext(mode=ModeType.PAPER)

        mode = PaperTradingMode(context)

        with pytest.raises(ValueError):
            mode.submit_order(symbol="AAPL", side="buy", quantity=1.0, order_type="market")

    def test_paper_cancel_order(self):
        """Test order cancellation in paper mode."""
        context = ExecutionContext(mode=ModeType.PAPER)
        context.market_prices["AAPL"] = 50000.0

        mode = PaperTradingMode(context)
        order_id = mode.submit_order(symbol="AAPL", side="buy", quantity=1.0, price=49500.0, order_type="limit")

        cancelled = mode.cancel_order(order_id)
        assert cancelled is True
        assert context.get_order(order_id) is not None
        assert context.get_order(order_id).status == OrderStatus.CANCELLED  # type: ignore[union-attr]

    def test_paper_open_position(self):
        """Test opening position in paper mode."""
        context = ExecutionContext(mode=ModeType.PAPER)
        context.cash = 100000.0

        mode = PaperTradingMode(context)
        success = mode.open_position(symbol="AAPL", quantity=2.0, entry_price=50000.0)

        assert success is True
        position = context.get_position("AAPL")
        assert position is not None
        assert position.quantity == 2.0

    def test_paper_close_position(self):
        """Test closing position in paper mode."""
        context = ExecutionContext(mode=ModeType.PAPER)
        context.cash = 100000.0

        mode = PaperTradingMode(context)
        mode.open_position("AAPL", 1.0, 50000.0)

        success, pnl = mode.close_position("AAPL", 51000.0)

        assert success is True
        assert pnl is not None
        assert context.get_position("AAPL") is None

    def test_paper_get_equity(self):
        """Test equity calculation in paper mode."""
        context = ExecutionContext(mode=ModeType.PAPER)
        context.cash = 100000.0

        mode = PaperTradingMode(context)

        # Open position worth 50000
        mode.open_position("AAPL", 1.0, 50000.0)
        context.update_market_price("AAPL", 50000.0)

        equity = mode.get_account_equity()
        expected = 100000.0 - 50000.0 + 50000.0  # cash - position cost + position value
        assert equity == expected


class TestBacktestMode:
    """Test backtest mode."""

    def test_backtest_submit_order(self):
        """Test order submission in backtest mode."""
        context = ExecutionContext(mode=ModeType.BACKTEST)
        context.market_prices["AAPL"] = 50000.0

        mode = BacktestMode(context)
        order_id = mode.submit_order(symbol="AAPL", side="buy", quantity=1.0, order_type="market")

        assert order_id is not None
        order = context.get_order(order_id)
        assert order is not None
        assert order.status == OrderStatus.FILLED

    def test_backtest_slippage(self):
        """Test slippage applied in backtest."""
        context = ExecutionContext(mode=ModeType.BACKTEST)
        context.market_prices["AAPL"] = 50000.0

        mode = BacktestMode(context)
        order_id = mode.submit_order(symbol="AAPL", side="buy", quantity=1.0, order_type="market")

        order = context.get_order(order_id)
        assert order is not None
        assert order.filled_price is not None
        # Buy slippage: price * (1 + slippage_pct / 100)
        expected_price = 50000.0 * (1 + 0.05 / 100)
        assert abs(order.filled_price - expected_price) < 0.01

    def test_backtest_open_position_with_commission(self):
        """Test position opening with commission in backtest."""
        context = ExecutionContext(mode=ModeType.BACKTEST)
        context.cash = 100000.0

        mode = BacktestMode(context)
        success = mode.open_position("AAPL", 1.0, 50000.0)

        assert success is True
        # Cash reduced by position cost + commission
        commission = 1.0 * 50000.0 * 0.1 / 100
        expected_cash = 100000.0 - 50000.0 - commission
        assert context.cash == expected_cash

    def test_backtest_close_position_with_commission(self):
        """Test position closing with commission in backtest."""
        context = ExecutionContext(mode=ModeType.BACKTEST)
        context.cash = 100000.0

        mode = BacktestMode(context)
        mode.open_position("AAPL", 1.0, 50000.0)
        context.update_market_price("AAPL", 51000.0)

        success, pnl_net = mode.close_position("AAPL", 51000.0)

        assert success is True
        # Gross P&L = 1000, minus commission
        commission = 1.0 * 51000.0 * 0.1 / 100
        expected_net = 1000.0 - commission
        assert pnl_net is not None
        assert abs(pnl_net - expected_net) < 0.01


class TestExecutionEngine:
    """Test unified execution engine."""

    def test_engine_paper_mode(self):
        """Test engine in paper mode."""
        engine = ExecutionEngine(mode=ModeType.PAPER)

        assert engine.context.mode == ModeType.PAPER
        assert isinstance(engine.executor, PaperTradingMode)

    def test_engine_live_mode(self):
        """Test engine in live mode."""
        engine = ExecutionEngine(mode=ModeType.LIVE)

        assert engine.context.mode == ModeType.LIVE
        assert isinstance(engine.executor, LiveTradingMode)

    def test_engine_backtest_mode(self):
        """Test engine in backtest mode."""
        engine = ExecutionEngine(mode=ModeType.BACKTEST)

        assert engine.context.mode == ModeType.BACKTEST
        assert isinstance(engine.executor, BacktestMode)

    def test_engine_submit_order(self):
        """Test order submission through engine."""
        engine = ExecutionEngine(mode=ModeType.PAPER)
        engine.context.market_prices["AAPL"] = 50000.0

        order_id = engine.submit_order(symbol="AAPL", side="buy", quantity=1.0, order_type="market")

        assert order_id is not None

    def test_engine_cancel_order(self):
        """Test order cancellation through engine."""
        engine = ExecutionEngine(mode=ModeType.PAPER)
        engine.context.market_prices["AAPL"] = 50000.0

        order_id = engine.submit_order(symbol="AAPL", side="buy", quantity=1.0, price=49500.0, order_type="limit")

        cancelled = engine.cancel_order(order_id)
        assert cancelled is True

    def test_engine_open_position(self):
        """Test position opening through engine."""
        engine = ExecutionEngine(mode=ModeType.PAPER)
        engine.context.cash = 100000.0

        success = engine.open_position(symbol="AAPL", quantity=1.0, entry_price=50000.0)

        assert success is True

    def test_engine_close_position(self):
        """Test position closing through engine."""
        engine = ExecutionEngine(mode=ModeType.PAPER)
        engine.context.cash = 100000.0

        engine.open_position("AAPL", 1.0, 50000.0)

        success, pnl = engine.close_position("AAPL", 51000.0)

        assert success is True
        assert pnl is not None

    def test_engine_get_positions(self):
        """Test getting all positions through engine."""
        engine = ExecutionEngine(mode=ModeType.PAPER)
        engine.context.cash = 100000.0

        engine.open_position("AAPL", 1.0, 50000.0)
        engine.open_position("MSFT", 10.0, 3000.0)

        positions = engine.get_positions()

        assert len(positions) == 2
        assert "AAPL" in positions
        assert "MSFT" in positions

    def test_engine_update_prices(self):
        """Test market price updates through engine."""
        engine = ExecutionEngine(mode=ModeType.PAPER)

        prices = {"AAPL": 50000.0, "MSFT": 3000.0}

        engine.update_prices(prices)

        assert engine.context.market_prices["AAPL"] == 50000.0
        assert engine.context.market_prices["MSFT"] == 3000.0

    def test_engine_get_equity(self):
        """Test equity retrieval through engine."""
        engine = ExecutionEngine(mode=ModeType.PAPER)
        engine.context.cash = 100000.0
        engine.context.market_prices["AAPL"] = 50000.0

        engine.open_position("AAPL", 1.0, 50000.0)

        equity = engine.get_equity()

        assert equity > 0


class TestExecutionModeConsistency:
    """Test consistency across execution modes."""

    def test_all_modes_same_interface(self):
        """Test that all modes implement same interface."""
        context_paper = ExecutionContext(mode=ModeType.PAPER)
        context_paper.market_prices["AAPL"] = 50000.0

        context_backtest = ExecutionContext(mode=ModeType.BACKTEST)
        context_backtest.market_prices["AAPL"] = 50000.0

        mode_paper = PaperTradingMode(context_paper)
        mode_backtest = BacktestMode(context_backtest)

        # Both should have same methods
        assert hasattr(mode_paper, "submit_order")
        assert hasattr(mode_paper, "cancel_order")
        assert hasattr(mode_paper, "get_order_status")
        assert hasattr(mode_paper, "open_position")
        assert hasattr(mode_paper, "close_position")
        assert hasattr(mode_paper, "get_account_equity")

        assert hasattr(mode_backtest, "submit_order")
        assert hasattr(mode_backtest, "cancel_order")
        assert hasattr(mode_backtest, "get_order_status")
        assert hasattr(mode_backtest, "open_position")
        assert hasattr(mode_backtest, "close_position")
        assert hasattr(mode_backtest, "get_account_equity")


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
