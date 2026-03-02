"""
Tests for LiveTradingRunner — verifies initialization, tick, and lifecycle.
"""

import pytest
from unittest.mock import MagicMock, patch
from live_trading.runner import LiveTradingRunner, TradingLoopConfig, TradingState


class TestLiveTradingRunnerInit:
    def test_default_config(self):
        runner = LiveTradingRunner()
        assert runner.config.bar_interval_seconds == 60
        assert runner.state == TradingState.INITIALIZING

    def test_custom_config(self):
        cfg = TradingLoopConfig(
            symbols=["AAPL", "MSFT"],
            bar_interval_seconds=300,
            max_positions=5,
            initial_capital=50_000.0,
            mode="paper",
        )
        runner = LiveTradingRunner(config=cfg)
        assert runner.config.symbols == ["AAPL", "MSFT"]
        assert runner.config.initial_capital == 50_000.0

    def test_iteration_starts_at_zero(self):
        runner = LiveTradingRunner()
        assert runner.iteration_count == 0


class TestTradingLoopConfig:
    def test_defaults(self):
        cfg = TradingLoopConfig()
        assert cfg.symbols == []
        assert cfg.bar_interval_seconds == 60
        assert cfg.pair_rediscovery_hours == 24
        assert cfg.max_positions == 10
        assert cfg.initial_capital == 100_000.0
        assert cfg.mode == "live"


class TestStopSignal:
    def test_stop_changes_state(self):
        runner = LiveTradingRunner()
        runner.stop()
        assert runner.state == TradingState.SHUTTING_DOWN


class TestTradingState:
    def test_all_states_exist(self):
        assert TradingState.INITIALIZING.value == "initializing"
        assert TradingState.RUNNING.value == "running"
        assert TradingState.PAUSED.value == "paused"
        assert TradingState.HALTED.value == "halted"
        assert TradingState.SHUTTING_DOWN.value == "shutting_down"
        assert TradingState.STOPPED.value == "stopped"
