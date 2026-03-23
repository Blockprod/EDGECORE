"""
Tests for LiveTradingRunner ÔÇö verifies initialization, tick, and lifecycle.
"""

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


class TestKillSwitchSharedInstance:
    """B2-02: runner._kill_switch and runner._risk_facade.kill_switch must be the same object."""

    def test_kill_switch_shared_after_initialize(self):
        """After _initialize(), kill_switch inside RiskFacade is the same object as runner._kill_switch."""
        runner = LiveTradingRunner()
        runner._initialize()
        assert runner._kill_switch is not None
        assert runner._risk_facade is not None
        assert runner._kill_switch is runner._risk_facade.kill_switch, (
            "B2-02 regression: _kill_switch and _risk_facade.kill_switch are different instances"
        )

    def test_facade_halted_when_kill_switch_activated(self):
        """Activating runner._kill_switch must immediately reflect in _risk_facade.is_halted."""
        from risk_engine.kill_switch import KillReason

        runner = LiveTradingRunner()
        runner._initialize()
        assert runner._kill_switch is not None
        runner._kill_switch.activate(KillReason.MANUAL, message="test")
        assert runner._risk_facade is not None
        assert runner._risk_facade.is_halted is True, (
            "B2-02 regression: _risk_facade.is_halted should be True after _kill_switch.activate()"
        )


class TestKillSwitchIBKRWiring:
    """C-03: kill-switch on_activate callback must cancel pending IBKR orders."""

    def test_on_activate_callback_wired(self):
        """KillSwitch must be initialized with on_activate pointing to runner method."""
        runner = LiveTradingRunner()
        runner._initialize()
        assert runner._kill_switch is not None
        assert runner._kill_switch._on_activate is not None, (
            "C-03: KillSwitch._on_activate must be set — callback not wired"
        )
        assert runner._kill_switch._on_activate == runner._on_kill_switch_activated, (
            "C-03: KillSwitch._on_activate must point to runner._on_kill_switch_activated"
        )

    def test_cancel_all_pending_called_on_kill(self):
        """When kill-switch activates, cancel_all_pending() must be called on IBKR engine."""
        from unittest.mock import MagicMock

        from risk_engine.kill_switch import KillReason

        runner = LiveTradingRunner()
        runner._initialize()

        # Inject a mock router with a mock IBKR engine
        mock_ibkr = MagicMock()
        mock_ibkr.cancel_all_pending.return_value = 3
        mock_router = MagicMock()
        mock_router._ibkr_engine = mock_ibkr
        runner._router = mock_router

        # Force a clean kill-switch state (prior tests may have persisted ACTIVE to disk)
        assert runner._kill_switch is not None
        runner._kill_switch._is_active = False

        runner._kill_switch.activate(KillReason.MANUAL, "test wiring")

        mock_ibkr.cancel_all_pending.assert_called_once()  # C-03 assertion

    def test_no_crash_when_router_is_none(self):
        """_on_kill_switch_activated must not crash when _router is None."""
        from risk_engine.kill_switch import KillReason

        runner = LiveTradingRunner()
        runner._initialize()
        runner._router = None  # simulate not-yet-initialized

        # Must not raise
        runner._on_kill_switch_activated(KillReason.MANUAL, "test no router")

    def test_no_crash_when_ibkr_engine_absent(self):
        """_on_kill_switch_activated must not crash when router has no IBKR engine (paper mode)."""
        from unittest.mock import MagicMock

        from risk_engine.kill_switch import KillReason

        runner = LiveTradingRunner()
        runner._initialize()

        mock_router = MagicMock(spec=[])  # spec=[] → no _ibkr_engine attribute
        runner._router = mock_router

        # Must not raise
        runner._on_kill_switch_activated(KillReason.MANUAL, "test paper mode")
