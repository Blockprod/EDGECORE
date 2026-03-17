"""
E2E tests for LiveTradingRunner._tick().

Verifies the full tick pipeline with mocked infrastructure:
    1. Happy path: data ÔåÆ signals ÔåÆ risk ÔåÆ order submission
    2. IBKR disconnect mid-tick: graceful error recovery
    3. Kill-switch activation: halts loop immediately
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import numpy as np

from live_trading.runner import LiveTradingRunner, TradingLoopConfig, TradingState


def _mock_market_data(n=200, symbols=None):
    """Create deterministic market data DataFrame."""
    symbols = symbols or ["AAPL", "MSFT"]
    np.random.seed(42)
    data = {}
    for s in symbols:
        data[s] = np.random.randn(n).cumsum() + 100
    return pd.DataFrame(data, index=pd.date_range("2024-01-01", periods=n))


class TestTickHappyPath:
    """Full tick cycle: data ÔåÆ signals ÔåÆ order."""

    def _make_runner(self):
        cfg = TradingLoopConfig(
            symbols=["AAPL", "MSFT"],
            mode="paper",
            initial_capital=100_000.0,
        )
        runner = LiveTradingRunner(config=cfg)
        return runner

    def _setup_mocks(self, runner):
        """Wire mocks into a runner without calling _initialize."""
        runner._state = TradingState.RUNNING
        runner._kill_switch = MagicMock()
        runner._kill_switch.is_active = False

        runner._universe_mgr = MagicMock()
        runner._pair_engine = MagicMock()
        runner._signal_gen = MagicMock()
        runner._position_risk = MagicMock()
        runner._portfolio_risk = MagicMock()
        runner._allocator = MagicMock()
        runner._router = MagicMock()
        runner._trailing_stop = None
        runner._time_stop = None
        runner._partial_profit = None
        runner._shutdown_mgr = None
        runner._correlation_monitor = None
        runner._reconciler = None
        runner._last_reconciliation = None
        runner._reconciliation_interval = timedelta(minutes=5)

        # Risk facade & metrics
        runner._risk_facade = MagicMock()
        from monitoring.metrics import SystemMetrics
        runner._metrics = SystemMetrics(equity=100_000)

        runner._active_pairs = [("AAPL", "MSFT", 0.01, 25.0)]
        runner._last_discovery = datetime.now()

        # Signal gen returns one signal
        mock_signal = MagicMock()
        mock_signal.pair_key = "AAPL_MSFT"
        mock_signal.side = "long"
        mock_signal.strength = 0.8
        runner._signal_gen.generate.return_value = [mock_signal]

        # Risk checks pass
        runner._position_risk.check.return_value = True
        runner._portfolio_risk.check.return_value = True

        # Allocator returns the signal
        runner._allocator.size.return_value = mock_signal

        # Router returns order ID
        runner._router.submit_order.return_value = "ORD-001"
        runner._router.get_account_balance.return_value = 100_000.0

        return runner

    def test_tick_submits_order_on_signal(self):
        runner = self._setup_mocks(self._make_runner())

        with patch.object(runner, '_fetch_market_data', return_value=_mock_market_data()):
            runner._tick()

        assert runner._router.submit_order.called
        assert runner._iteration == 1

    def test_tick_increments_iteration(self):
        runner = self._setup_mocks(self._make_runner())
        with patch.object(runner, '_fetch_market_data', return_value=_mock_market_data()):
            runner._tick()
            runner._tick()
        assert runner._iteration == 2

    def test_tick_no_order_when_risk_rejects(self):
        runner = self._setup_mocks(self._make_runner())
        runner._position_risk.check.return_value = False

        with patch.object(runner, '_fetch_market_data', return_value=_mock_market_data()):
            runner._tick()

        runner._router.submit_order.assert_not_called()

    def test_tick_updates_metrics(self):
        runner = self._setup_mocks(self._make_runner())
        with patch.object(runner, '_fetch_market_data', return_value=_mock_market_data()):
            runner._tick()
        assert runner._metrics.trades_total >= 1


class TestTickDisconnect:
    """IBKR disconnect / data fetch failure during tick."""

    def test_data_fetch_exception_recovers(self):
        cfg = TradingLoopConfig(symbols=["AAPL", "MSFT"], mode="paper")
        runner = LiveTradingRunner(config=cfg)
        runner._state = TradingState.RUNNING
        runner._kill_switch = MagicMock()
        runner._kill_switch.is_active = False
        runner._active_pairs = []
        runner._last_discovery = datetime.now()
        runner._signal_gen = MagicMock()
        runner._position_risk = None
        runner._portfolio_risk = None
        runner._allocator = None
        runner._router = None
        runner._trailing_stop = None
        runner._time_stop = None
        runner._partial_profit = None
        runner._shutdown_mgr = None
        runner._correlation_monitor = None
        runner._reconciler = None
        runner._last_reconciliation = None
        runner._reconciliation_interval = timedelta(minutes=5)
        runner._risk_facade = MagicMock()
        from monitoring.metrics import SystemMetrics
        runner._metrics = SystemMetrics(equity=100_000)

        with patch.object(runner, '_fetch_market_data', side_effect=ConnectionError("IBKR down")):
            runner._tick()  # should not raise

        assert runner._state == TradingState.RUNNING

    def test_empty_data_skips_safely(self):
        cfg = TradingLoopConfig(symbols=["AAPL", "MSFT"], mode="paper")
        runner = LiveTradingRunner(config=cfg)
        runner._state = TradingState.RUNNING
        runner._kill_switch = MagicMock()
        runner._kill_switch.is_active = False
        runner._active_pairs = []
        runner._last_discovery = datetime.now()
        runner._signal_gen = MagicMock()
        runner._reconciler = None
        runner._last_reconciliation = None
        runner._reconciliation_interval = timedelta(minutes=5)
        runner._trailing_stop = None
        runner._time_stop = None
        runner._partial_profit = None
        runner._shutdown_mgr = None
        runner._correlation_monitor = None
        runner._risk_facade = MagicMock()
        from monitoring.metrics import SystemMetrics
        runner._metrics = SystemMetrics(equity=100_000)

        with patch.object(runner, '_fetch_market_data', return_value=pd.DataFrame()):
            runner._tick()

        assert runner._state == TradingState.RUNNING


class TestTickKillSwitch:
    """Kill-switch activation halts the loop."""

    def test_kill_switch_halts_immediately(self):
        cfg = TradingLoopConfig(symbols=["AAPL"], mode="paper")
        runner = LiveTradingRunner(config=cfg)
        runner._state = TradingState.RUNNING
        runner._kill_switch = MagicMock()
        runner._kill_switch.is_active = True
        runner._reconciler = None
        runner._last_reconciliation = None
        runner._reconciliation_interval = timedelta(minutes=5)
        runner._signal_gen = MagicMock()
        runner._risk_facade = MagicMock()
        from monitoring.metrics import SystemMetrics
        runner._metrics = SystemMetrics(equity=100_000)

        runner._tick()

        assert runner._state == TradingState.HALTED
        runner._signal_gen.generate.assert_not_called()

    def test_halted_state_persists(self):
        cfg = TradingLoopConfig(mode="paper")
        runner = LiveTradingRunner(config=cfg)
        runner._state = TradingState.RUNNING
        runner._kill_switch = MagicMock()
        runner._kill_switch.is_active = True
        runner._reconciler = None
        runner._last_reconciliation = None
        runner._reconciliation_interval = timedelta(minutes=5)
        runner._risk_facade = MagicMock()
        from monitoring.metrics import SystemMetrics
        runner._metrics = SystemMetrics(equity=100_000)

        runner._tick()
        assert runner.state == TradingState.HALTED
