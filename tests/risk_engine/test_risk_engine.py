"""
Tests for risk_engine — KillSwitch, PositionRiskManager, PortfolioRiskManager.
"""

import os
import pytest
from risk_engine.kill_switch import KillSwitch, KillSwitchConfig, KillReason
from risk_engine.position_risk import PositionRiskManager, PositionRiskConfig
from risk_engine.portfolio_risk import PortfolioRiskManager, PortfolioRiskConfig


@pytest.fixture(autouse=True)
def _clean_kill_switch_state():
    """Remove persisted kill switch state between tests."""
    state_path = "data/kill_switch_state.json"
    if os.path.exists(state_path):
        os.remove(state_path)
    yield
    if os.path.exists(state_path):
        os.remove(state_path)


# ── KillSwitch tests ─────────────────────────────────────────────────────


class TestKillSwitch:
    def test_init_inactive(self):
        ks = KillSwitch()
        assert not ks.is_active

    def test_activate_manually(self):
        ks = KillSwitch()
        ks.activate(KillReason.MANUAL, "test halt")
        assert ks.is_active
        assert ks.reason == KillReason.MANUAL

    def test_reset_clears_active(self):
        ks = KillSwitch()
        ks.activate(KillReason.MANUAL, "halt")
        ks.reset()
        assert not ks.is_active

    def test_check_returns_false_when_safe(self):
        """check() returns True when active (danger), False when safe."""
        ks = KillSwitch()
        is_active = ks.check(drawdown_pct=0.01, daily_loss_pct=0.005)
        assert is_active is False

    def test_check_activates_on_drawdown(self):
        cfg = KillSwitchConfig(max_drawdown_pct=0.05)
        ks = KillSwitch(config=cfg)
        is_active = ks.check(drawdown_pct=0.10)
        assert is_active is True
        assert ks.is_active

    def test_check_activates_on_daily_loss(self):
        cfg = KillSwitchConfig(max_daily_loss_pct=0.02)
        ks = KillSwitch(config=cfg)
        is_active = ks.check(daily_loss_pct=0.05)
        assert is_active is True

    def test_check_activates_on_consecutive_losses(self):
        cfg = KillSwitchConfig(max_consecutive_losses=3)
        ks = KillSwitch(config=cfg)
        is_active = ks.check(consecutive_losses=5)
        assert is_active is True
        assert ks.reason == KillReason.CONSECUTIVE_LOSSES

    def test_callback_on_activate(self):
        called = {}

        def cb(reason, msg):
            called['reason'] = reason

        ks = KillSwitch(on_activate=cb)
        ks.activate(KillReason.MANUAL, "test")
        assert 'reason' in called
        assert called['reason'] == KillReason.MANUAL

    def test_get_state_when_inactive(self):
        ks = KillSwitch()
        state = ks.get_state()
        assert state.is_active is False

    def test_get_state_when_active(self):
        ks = KillSwitch()
        ks.activate(KillReason.MANUAL, "halt")
        state = ks.get_state()
        assert state.is_active is True

    def test_activation_history_records(self):
        ks = KillSwitch()
        ks.activate(KillReason.MANUAL, "first")
        assert len(ks.activation_history) == 1
        # Second activation while already active is a no-op
        ks.activate(KillReason.DRAWDOWN, "second")
        assert len(ks.activation_history) == 1
        # After reset, can activate again
        ks.reset()
        ks.activate(KillReason.DRAWDOWN, "third")
        assert len(ks.activation_history) == 2


# ── PositionRiskManager tests ────────────────────────────────────────────


class TestPositionRiskManager:
    def test_init(self):
        mgr = PositionRiskManager()
        assert mgr.position_count == 0

    def test_register_and_count(self):
        mgr = PositionRiskManager()
        mgr.register_position(
            pair_key="AAPL_MSFT", side="long",
            entry_z=2.0, entry_price=150.0,
            entry_bar=0, half_life=10.0,
            notional=10000.0,
        )
        assert mgr.position_count == 1
        assert "AAPL_MSFT" in mgr.active_positions

    def test_remove_position(self):
        mgr = PositionRiskManager()
        mgr.register_position(
            pair_key="A_B", side="long",
            entry_z=2.0, entry_price=100.0,
            entry_bar=0, half_life=10.0,
            notional=5000.0,
        )
        mgr.remove_position("A_B")
        assert mgr.position_count == 0

    def test_check_returns_tuple(self):
        """check() returns (should_exit: bool, reason: str)."""
        mgr = PositionRiskManager()
        mgr.register_position(
            pair_key="A_B", side="long",
            entry_z=2.0, entry_price=100.0,
            entry_bar=0, half_life=20.0,
            notional=5000.0,
        )
        result = mgr.check(
            pair_key="A_B",
            current_z=1.8,  # close to entry, should be safe
            current_bar=1,  # very early
            pnl_pct=0.0,
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_check_pnl_stop_triggers(self):
        """When loss exceeds max, should_exit is True."""
        cfg = PositionRiskConfig(max_position_loss_pct=0.05)
        mgr = PositionRiskManager(config=cfg)
        mgr.register_position(
            pair_key="A_B", side="long",
            entry_z=2.0, entry_price=100.0,
            entry_bar=0, half_life=20.0,
            notional=5000.0,
        )
        should_exit, reason = mgr.check(
            pair_key="A_B",
            current_z=2.0,  # same as entry (no trailing stop)
            current_bar=1,  # early (no time stop)
            pnl_pct=-0.08,  # exceeds 5% threshold
        )
        assert should_exit is True
        assert "loss" in reason.lower() or "stop" in reason.lower() or "p&l" in reason.lower()

    def test_check_nonexistent_position(self):
        mgr = PositionRiskManager()
        should_exit, reason = mgr.check(
            pair_key="NONEXISTENT",
            current_z=1.0,
            current_bar=0,
            pnl_pct=0.0,
        )
        assert should_exit is False
        assert reason == ""


# ── PortfolioRiskManager tests ───────────────────────────────────────────


class TestPortfolioRiskManager:
    def test_init_equity(self):
        mgr = PortfolioRiskManager(initial_equity=200_000.0)
        assert mgr.drawdown_pct == 0.0

    def test_update_equity_drawdown(self):
        mgr = PortfolioRiskManager(initial_equity=100_000.0)
        mgr.update_equity(95_000.0)
        assert mgr.drawdown_pct > 0

    def test_can_open_position_when_healthy(self):
        mgr = PortfolioRiskManager(initial_equity=100_000.0)
        ok, reason = mgr.can_open_position()
        assert ok is True

    def test_cannot_open_when_max_positions(self):
        cfg = PortfolioRiskConfig(max_concurrent_positions=2)
        mgr = PortfolioRiskManager(initial_equity=100_000.0, config=cfg)
        mgr.set_open_positions(3)
        ok, reason = mgr.can_open_position()
        assert ok is False

    def test_consecutive_losses_tracked(self):
        mgr = PortfolioRiskManager(initial_equity=100_000.0)
        mgr.record_trade_result(-500.0)
        mgr.record_trade_result(-300.0)
        state = mgr.get_state()
        assert state.consecutive_losses >= 2

    def test_winning_trade_resets_streak(self):
        mgr = PortfolioRiskManager(initial_equity=100_000.0)
        mgr.record_trade_result(-500.0)
        mgr.record_trade_result(1000.0)
        state = mgr.get_state()
        assert state.consecutive_losses == 0

    def test_drawdown_increases_on_equity_drop(self):
        mgr = PortfolioRiskManager(initial_equity=100_000.0)
        mgr.update_equity(90_000.0)
        assert mgr.drawdown_pct >= 0.09  # ~10%

    def test_get_state_returns_state(self):
        mgr = PortfolioRiskManager()
        state = mgr.get_state()
        assert hasattr(state, 'current_equity')
        assert hasattr(state, 'is_halted')
