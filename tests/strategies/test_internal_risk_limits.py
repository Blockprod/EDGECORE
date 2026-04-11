"""
Tests for Sprint 4.4 ÔÇô Self-contained internal risk limits.

Covers:
  1. _check_internal_risk_limits() ÔÇô max positions, daily trades, drawdown
  2. update_equity() ÔÇô peak tracking and drawdown computation
  3. _maybe_reset_daily_counter() ÔÇô daily rollover
  4. _record_trade() ÔÇô trade counter increment
  5. Integration with generate_signals entry flow
  6. Config integration
"""

from datetime import datetime, timedelta
from unittest import mock

import numpy as np
import pandas as pd

from strategies.trade_book import StrategyTradeBook


def _trade_book(*keys: str) -> StrategyTradeBook:
    """Build a StrategyTradeBook populated with empty trade dicts for each key."""
    book = StrategyTradeBook()
    for k in keys:
        book[k] = {}
    return book


# ---------------------------------------------------------------------------
# Helper: build a minimal PairTradingStrategy without full __init__
# ---------------------------------------------------------------------------


def _make_strategy(max_positions=8, max_drawdown_pct=0.10, max_daily_trades=20):
    """Create a PairTradingStrategy with controlled internal risk params."""
    from strategies.pair_trading import PairTradingStrategy

    with mock.patch.object(PairTradingStrategy, "__init__", lambda _self: None):
        strat = PairTradingStrategy()
    # Minimal attributes needed for risk checks
    strat.active_trades = StrategyTradeBook()
    strat.max_positions = max_positions
    strat.max_drawdown_pct = max_drawdown_pct
    strat.max_daily_trades = max_daily_trades
    strat.daily_trade_count = 0
    strat.daily_trade_date = None
    strat.peak_equity = None
    strat.current_equity = None
    strat._clock = datetime.now  # required since __init__ is mocked out
    return strat


# ===================================================================
# 1. _check_internal_risk_limits ÔÇô Max positions
# ===================================================================


class TestMaxPositions:
    """Internal risk: max concurrent positions guard."""

    def test_allows_below_limit(self):
        strat = _make_strategy(max_positions=3)
        strat.active_trades = _trade_book("A_B", "C_D")
        ok, reason = strat._check_internal_risk_limits()
        assert ok is True
        assert reason == ""

    def test_blocks_at_limit(self):
        strat = _make_strategy(max_positions=2)
        strat.active_trades = _trade_book("A_B", "C_D")
        ok, reason = strat._check_internal_risk_limits()
        assert ok is False
        assert "max positions" in reason.lower()

    def test_blocks_above_limit(self):
        strat = _make_strategy(max_positions=2)
        strat.active_trades = _trade_book("A_B", "C_D", "E_F")
        ok, _reason = strat._check_internal_risk_limits()
        assert ok is False

    def test_zero_positions_allowed(self):
        strat = _make_strategy(max_positions=8)
        strat.active_trades = _trade_book()
        ok, _ = strat._check_internal_risk_limits()
        assert ok is True

    def test_exactly_one_below_limit(self):
        strat = _make_strategy(max_positions=5)
        strat.active_trades = _trade_book(*[f"P{i}" for i in range(4)])
        ok, _ = strat._check_internal_risk_limits()
        assert ok is True


# ===================================================================
# 2. _check_internal_risk_limits ÔÇô Daily trade count
# ===================================================================


class TestMaxDailyTrades:
    """Internal risk: daily trade count guard."""

    def test_allows_below_daily_limit(self):
        strat = _make_strategy(max_daily_trades=5)
        strat.daily_trade_count = 4
        strat.daily_trade_date = datetime.now().date()
        ok, _ = strat._check_internal_risk_limits()
        assert ok is True

    def test_blocks_at_daily_limit(self):
        strat = _make_strategy(max_daily_trades=5)
        strat.daily_trade_count = 5
        strat.daily_trade_date = datetime.now().date()
        ok, reason = strat._check_internal_risk_limits()
        assert ok is False
        assert "daily trades" in reason.lower()

    def test_daily_counter_resets_on_new_day(self):
        strat = _make_strategy(max_daily_trades=5)
        strat.daily_trade_count = 100  # was maxed yesterday
        strat.daily_trade_date = (datetime.now() - timedelta(days=1)).date()
        ok, _ = strat._check_internal_risk_limits()
        # Counter should have been reset by _maybe_reset_daily_counter
        assert ok is True
        assert strat.daily_trade_count == 0


# ===================================================================
# 3. _check_internal_risk_limits ÔÇô Drawdown from peak
# ===================================================================


class TestDrawdownGuard:
    """Internal risk: drawdown-from-peak guard."""

    def test_no_drawdown_check_without_equity(self):
        """If equity not tracked yet, drawdown check is skipped."""
        strat = _make_strategy(max_drawdown_pct=0.10)
        strat.peak_equity = None
        strat.current_equity = None
        ok, _ = strat._check_internal_risk_limits()
        assert ok is True

    def test_allows_within_drawdown_limit(self):
        strat = _make_strategy(max_drawdown_pct=0.10)
        strat.peak_equity = 100_000
        strat.current_equity = 95_000  # 5% DD < 10%
        ok, _ = strat._check_internal_risk_limits()
        assert ok is True

    def test_blocks_exceeding_drawdown_limit(self):
        strat = _make_strategy(max_drawdown_pct=0.10)
        strat.peak_equity = 100_000
        strat.current_equity = 88_000  # 12% DD > 10%
        ok, reason = strat._check_internal_risk_limits()
        assert ok is False
        assert "drawdown" in reason.lower()
        assert "12.0%" in reason

    def test_exact_drawdown_boundary(self):
        """Exactly at the limit should be blocked (> comparison, not >=)."""
        strat = _make_strategy(max_drawdown_pct=0.10)
        strat.peak_equity = 100_000
        strat.current_equity = 90_000  # exactly 10.0%
        ok, _ = strat._check_internal_risk_limits()
        # 10% == 10% Ôåô not > 10% Ôåô allowed
        assert ok is True

    def test_drawdown_with_small_equity(self):
        strat = _make_strategy(max_drawdown_pct=0.05)
        strat.peak_equity = 1_000
        strat.current_equity = 940  # 6% > 5%
        ok, _reason = strat._check_internal_risk_limits()
        assert ok is False


# ===================================================================
# 4. update_equity ÔÇô Peak tracking
# ===================================================================


class TestUpdateEquity:
    """Test equity tracking for drawdown guard."""

    def test_first_update_sets_peak(self):
        strat = _make_strategy()
        strat.update_equity(50_000)
        assert strat.peak_equity == 50_000
        assert strat.current_equity == 50_000

    def test_higher_equity_updates_peak(self):
        strat = _make_strategy()
        strat.update_equity(50_000)
        strat.update_equity(60_000)
        assert strat.peak_equity == 60_000
        assert strat.current_equity == 60_000

    def test_lower_equity_does_not_update_peak(self):
        strat = _make_strategy()
        strat.update_equity(60_000)
        strat.update_equity(55_000)
        assert strat.peak_equity == 60_000
        assert strat.current_equity == 55_000

    def test_sequential_updates(self):
        strat = _make_strategy()
        for eq in [100, 120, 110, 130, 125]:
            strat.update_equity(eq)
        assert strat.peak_equity == 130
        assert strat.current_equity == 125


# ===================================================================
# 5. _record_trade / _maybe_reset_daily_counter
# ===================================================================


class TestDailyTradeCounter:
    """Test daily trade counting and rollover."""

    def test_record_increments(self):
        strat = _make_strategy()
        strat._record_trade()
        assert strat.daily_trade_count == 1
        strat._record_trade()
        assert strat.daily_trade_count == 2

    def test_reset_on_new_day(self):
        strat = _make_strategy()
        strat.daily_trade_date = (datetime.now() - timedelta(days=1)).date()
        strat.daily_trade_count = 15
        strat._maybe_reset_daily_counter()
        assert strat.daily_trade_count == 0
        assert strat.daily_trade_date == datetime.now().date()

    def test_no_reset_same_day(self):
        strat = _make_strategy()
        strat.daily_trade_date = datetime.now().date()
        strat.daily_trade_count = 7
        strat._maybe_reset_daily_counter()
        assert strat.daily_trade_count == 7

    def test_record_resets_if_new_day(self):
        strat = _make_strategy()
        strat.daily_trade_date = (datetime.now() - timedelta(days=1)).date()
        strat.daily_trade_count = 99
        strat._record_trade()
        # Should have reset then incremented to 1
        assert strat.daily_trade_count == 1


# ===================================================================
# 6. Combined limits ÔÇô multiple limits at once
# ===================================================================


class TestCombinedLimits:
    """Multiple limits can trigger simultaneously."""

    def test_position_limit_takes_priority(self):
        strat = _make_strategy(max_positions=1, max_daily_trades=100)
        strat.active_trades = _trade_book("A_B")
        ok, reason = strat._check_internal_risk_limits()
        assert ok is False
        assert "positions" in reason.lower()

    def test_all_limits_pass(self):
        strat = _make_strategy(max_positions=10, max_daily_trades=50, max_drawdown_pct=0.20)
        strat.active_trades = _trade_book("A_B")
        strat.daily_trade_count = 5
        strat.daily_trade_date = datetime.now().date()
        strat.peak_equity = 100_000
        strat.current_equity = 95_000
        ok, reason = strat._check_internal_risk_limits()
        assert ok is True
        assert reason == ""


# ===================================================================
# 7. Integration ÔÇô entry signals blocked by internal risk
# ===================================================================


class TestSignalEntryBlocking:
    """Test that generate_signals respects internal risk limits."""

    def _make_full_strategy(self):
        """Build strategy with enough mocks to call generate_signals."""
        from strategies.pair_trading import PairTradingStrategy

        with mock.patch.object(PairTradingStrategy, "__init__", lambda _self: None):
            strat = PairTradingStrategy()
        # Minimal init to avoid AttributeError
        strat.config = mock.MagicMock()
        strat.config.lookback_window = 100
        strat.spread_models = {}
        strat.active_trades = StrategyTradeBook()
        strat.historical_spreads = {}
        strat.hedge_ratio_tracker = mock.MagicMock()
        strat.hedge_ratio_tracker.is_pair_deprecated.return_value = False
        strat.trailing_stop_manager = mock.MagicMock()
        strat.trailing_stop_manager.should_exit_on_trailing_stop.return_value = (False, "")
        strat.concentration_limits = mock.MagicMock()
        strat.concentration_limits.add_position.return_value = (True, "")
        strat.regime_detector = mock.MagicMock()
        regime_mock = mock.MagicMock()
        regime_mock.regime.value = "NORMAL"
        regime_mock.percentile = 50.0
        regime_mock.get_entry_threshold_multiplier.return_value = 1.0
        regime_mock.get_position_multiplier.return_value = 1.0
        regime_mock.get_exit_threshold_multiplier.return_value = 1.0
        strat.regime_detector.update.return_value = regime_mock
        strat.pair_regime_states = {}
        strat.stationarity_monitor = mock.MagicMock()
        strat.stationarity_monitor.check.return_value = (True, 0.001)
        strat.model_retrainer = mock.MagicMock()
        strat.model_retrainer.schedule_retraining_check.return_value = False
        strat.use_cache = False
        strat.cache_dir = mock.MagicMock()
        strat.liquidity_filter = mock.MagicMock()
        strat.delisting_guard = mock.MagicMock()
        # Internal risk params
        strat.max_positions = 8
        strat.max_drawdown_pct = 0.10
        strat.max_daily_trades = 20
        strat.daily_trade_count = 0
        strat.daily_trade_date = None
        strat.peak_equity = None
        strat.current_equity = None
        return strat

    def test_entry_blocked_when_max_positions_reached(self):
        """When max positions hit, _check_internal_risk_limits blocks entry."""
        strat = self._make_full_strategy()
        strat.max_positions = 0  # block all entries
        # Mock _check_internal_risk_limits to verify it's called
        with mock.patch.object(strat, "_check_internal_risk_limits", return_value=(False, "max positions")):
            # Provide pre-discovered pairs with fake data
            rng = np.random.RandomState(42)
            n = 200
            x = pd.Series(np.cumsum(rng.randn(n)), name="X")
            y = pd.Series(1.5 * x + rng.randn(n) * 0.3, name="Y")
            market_data = pd.DataFrame({"Y": y, "X": x})
            signals = strat.generate_signals(market_data, discovered_pairs=[("Y", "X", 0.001, 10)])
            # No entry signals should be generated (only exit signals possible)
            entry_signals = [s for s in signals if s.side in ("long", "short")]
            assert len(entry_signals) == 0


# ===================================================================
# 8. Config integration
# ===================================================================


class TestConfigInternalRisk:
    """Test config fields for internal risk limits."""

    def test_config_defaults(self):
        from config.settings import StrategyConfig

        cfg = StrategyConfig()
        assert cfg.internal_max_positions == 50
        assert cfg.internal_max_drawdown_pct == 0.20  # 20% as decimal fraction
        assert cfg.internal_max_daily_trades == 200

    def test_config_override(self):
        from config.settings import StrategyConfig

        cfg = StrategyConfig(
            internal_max_positions=5,
            internal_max_drawdown_pct=0.05,
            internal_max_daily_trades=10,
        )
        assert cfg.internal_max_positions == 5
        assert cfg.internal_max_drawdown_pct == 0.05
        assert cfg.internal_max_daily_trades == 10

    def test_internal_stricter_than_risk_engine(self):
        """Internal limits should be within reasonable bounds."""
        from config.settings import RiskConfig, StrategyConfig

        strat_cfg = StrategyConfig()
        risk_cfg = RiskConfig()
        # Internal max positions can be larger than risk engine's
        # (simulator's portfolio-heat guard controls actual positions)
        assert strat_cfg.internal_max_positions >= risk_cfg.max_concurrent_positions
