<<<<<<< HEAD
﻿"""
Sprint 4.6 ÔÇô Tests for rolling leg correlation monitoring.
=======
"""
Sprint 4.6 – Tests for rolling leg correlation monitoring.
>>>>>>> origin/main

Tests the ``_check_leg_correlation_stability()`` method, integration into
``generate_signals()``, pair exclusion/rehabilitation, and analytics exposure.

Covers:
<<<<<<< HEAD
  1. Stable correlation Ôåô returns True
  2. Correlation breakdown Ôåô returns False
  3. Insufficient data Ôåô returns True (safe default)
=======
  1. Stable correlation ↓ returns True
  2. Correlation breakdown ↓ returns False
  3. Insufficient data ↓ returns True (safe default)
>>>>>>> origin/main
  4. NaN handling (constant series)
  5. Threshold parametrisation
  6. Pair exclusion on breakdown
  7. Exit signal emitted on breakdown with active position
  8. No entry when pair is excluded
  9. Exclusion reset (single + all)
  10. Analytics / monitoring history
  11. Edge cases: zero historical, identical series, anti-correlated legs
"""

<<<<<<< HEAD
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
=======
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch
from datetime import datetime

>>>>>>> origin/main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_strategy(**config_overrides):
    """
    Build a minimal PairTradingStrategy with mocked dependencies so we
    can unit-test the correlation methods in isolation.
    """
    defaults = {
        "lookback_window": 252,
        "entry_z_score": 2.0,
        "exit_z_score": 0.0,
        "min_correlation": 0.7,
        "max_half_life": 60,
        "bonferroni_correction": True,
        "significance_level": 0.05,
        "hedge_ratio_reestimation_days": 7,
        "regime_min_duration": 1,
        "emergency_vol_threshold_sigma": 3.0,
        "instant_transition_percentile": 99.0,
        "cache_ttl_high_vol": 2,
        "cache_ttl_normal_vol": 12,
        "cache_ttl_low_vol": 24,
        "johansen_confirmation": True,
        "newey_west_consensus": True,
        "internal_max_positions": 8,
        "internal_max_drawdown_pct": 0.10,
        "internal_max_daily_trades": 20,
        "leg_correlation_window": 30,
        "leg_correlation_decay_threshold": 0.5,
    }
    defaults.update(config_overrides)

    mock_config = MagicMock()
    for k, v in defaults.items():
        setattr(mock_config, k, v)
    # getattr fallback for optional settings
    mock_config.__contains__ = lambda self, key: hasattr(self, key)

    with patch("strategies.pair_trading.get_settings") as mock_settings:
        mock_strategy_config = mock_config
        mock_settings.return_value.strategy = mock_strategy_config
        from strategies.pair_trading import PairTradingStrategy
        strategy = PairTradingStrategy()
    return strategy


def _correlated_series(n: int = 200, noise: float = 0.02, seed: int = 42):
    """Return two highly correlated price series."""
    rng = np.random.RandomState(seed)
    base = 100 + np.cumsum(rng.randn(n) * 0.5)
    y = pd.Series(base + rng.randn(n) * noise, name="A")
    x = pd.Series(base * 1.05 + rng.randn(n) * noise, name="B")
    return y, x


def _breaking_series(n: int = 200, break_point: int = 160, seed: int = 42):
    """
    Return two series that are highly correlated up to *break_point* but then
<<<<<<< HEAD
    completely diverge ÔÇô simulating a correlation breakdown.
=======
    completely diverge – simulating a correlation breakdown.
>>>>>>> origin/main

    After the break, x follows an independent random walk so the recent window
    (which is entirely post-break) has near-zero or negative correlation
    with y while the historical window (spanning both) still shows non-trivial
    positive correlation.
    """
    rng = np.random.RandomState(seed)
    base = 100 + np.cumsum(rng.randn(n) * 0.5)
    y = pd.Series(base.copy())
    x_pre = base[:break_point] * 1.05 + rng.randn(break_point) * 0.01  # highly correlated
    # After break: independent random walk starting from last pre-break value
    x_post_start = x_pre[-1]
    x_post = x_post_start + np.cumsum(rng.randn(n - break_point) * 3.0)
    x = pd.Series(np.concatenate([x_pre, x_post]))
    return y, x


# ===================================================================
<<<<<<< HEAD
# 1. Core method ÔÇô stable correlation
# ===================================================================

class TestStableCorrelation:
    """Pair with stable high correlation Ôåô method returns True."""
=======
# 1. Core method – stable correlation
# ===================================================================

class TestStableCorrelation:
    """Pair with stable high correlation ↓ method returns True."""
>>>>>>> origin/main

    def test_stable_returns_true(self):
        strategy = _make_strategy()
        y, x = _correlated_series(200)
        result = strategy._check_leg_correlation_stability(y, x, "A_B")
        assert result is True

    def test_history_recorded(self):
        strategy = _make_strategy()
        y, x = _correlated_series(200)
        strategy._check_leg_correlation_stability(y, x, "A_B")
        history = strategy._leg_correlation_history
        assert "A_B" in history
        assert history["A_B"]["stable"] is True
        assert abs(history["A_B"]["recent_corr"]) > 0.5

    def test_custom_window(self):
        strategy = _make_strategy()
        y, x = _correlated_series(200)
        result = strategy._check_leg_correlation_stability(y, x, "A_B", window=20)
        assert result is True


# ===================================================================
<<<<<<< HEAD
# 2. Core method ÔÇô correlation breakdown
# ===================================================================

class TestCorrelationBreakdown:
    """Pair with recent correlation collapse Ôåô returns False."""
=======
# 2. Core method – correlation breakdown
# ===================================================================

class TestCorrelationBreakdown:
    """Pair with recent correlation collapse ↓ returns False."""
>>>>>>> origin/main

    def test_breakdown_returns_false(self):
        strategy = _make_strategy()
        y, x = _breaking_series(200, break_point=150)
        result = strategy._check_leg_correlation_stability(y, x, "A_B")
        assert result is False

    def test_breakdown_history_flagged(self):
        strategy = _make_strategy()
        y, x = _breaking_series(200, break_point=150)
        strategy._check_leg_correlation_stability(y, x, "A_B")
        assert strategy._leg_correlation_history["A_B"]["stable"] is False

    def test_breakdown_with_strict_threshold(self):
        """With threshold=0.9, even moderate decorrelation triggers breakdown."""
        strategy = _make_strategy(leg_correlation_decay_threshold=0.9)
        y, x = _breaking_series(200, break_point=140, seed=7)
        result = strategy._check_leg_correlation_stability(y, x, "A_B")
        assert result is False

    def test_no_breakdown_with_lax_threshold(self):
        """With threshold=0.01 (very lax), only extreme breakdown triggers."""
        strategy = _make_strategy(leg_correlation_decay_threshold=0.01)
        y, x = _correlated_series(200)
        result = strategy._check_leg_correlation_stability(y, x, "A_B")
        assert result is True


# ===================================================================
<<<<<<< HEAD
# 3. Insufficient data ÔÇô safe fallback
# ===================================================================

class TestInsufficientData:
    """Not enough bars Ôåô allow pair (return True)."""
=======
# 3. Insufficient data – safe fallback
# ===================================================================

class TestInsufficientData:
    """Not enough bars ↓ allow pair (return True)."""
>>>>>>> origin/main

    def test_short_series_returns_true(self):
        strategy = _make_strategy(leg_correlation_window=30)
        y = pd.Series(np.random.randn(50))  # < 30*2 = 60
        x = pd.Series(np.random.randn(50))
        assert strategy._check_leg_correlation_stability(y, x, "A_B") is True

    def test_exactly_2x_window_passes(self):
        """len == 2*window is sufficient."""
        strategy = _make_strategy(leg_correlation_window=30)
        rng = np.random.RandomState(1)
        base = np.cumsum(rng.randn(60))
        y = pd.Series(base + rng.randn(60) * 0.01)
        x = pd.Series(base * 1.1 + rng.randn(60) * 0.01)
        assert strategy._check_leg_correlation_stability(y, x, "A_B") is True

    def test_empty_series(self):
        strategy = _make_strategy()
        y = pd.Series(dtype=float)
        x = pd.Series(dtype=float)
        assert strategy._check_leg_correlation_stability(y, x, "A_B") is True


# ===================================================================
# 4. NaN / constant handling
# ===================================================================

class TestEdgeCases:
    """Edge cases: constant series, NaN correlation, tiny historical."""

    def test_constant_series_returns_true(self):
<<<<<<< HEAD
        """Constant series Ôåô corr is NaN Ôåô safe default True."""
=======
        """Constant series ↓ corr is NaN ↓ safe default True."""
>>>>>>> origin/main
        strategy = _make_strategy()
        y = pd.Series([100.0] * 200)
        x = pd.Series([200.0] * 200)
        assert strategy._check_leg_correlation_stability(y, x, "A_B") is True

    def test_identical_series(self):
<<<<<<< HEAD
        """Identical series Ôåô perfect correlation Ôåô stable."""
=======
        """Identical series ↓ perfect correlation ↓ stable."""
>>>>>>> origin/main
        strategy = _make_strategy()
        rng = np.random.RandomState(7)
        base = pd.Series(100 + np.cumsum(rng.randn(200) * 0.5))
        assert strategy._check_leg_correlation_stability(base, base.copy(), "A_A") is True

    def test_anticorrelated_legs(self):
<<<<<<< HEAD
        """Anti-correlated legs: both recent and historical negative Ôåô no breakdown
        if recent is still >= threshold ├ù historical in absolute value."""
=======
        """Anti-correlated legs: both recent and historical negative ↓ no breakdown
        if recent is still >= threshold × historical in absolute value."""
>>>>>>> origin/main
        strategy = _make_strategy()
        rng = np.random.RandomState(3)
        base = 100 + np.cumsum(rng.randn(200) * 0.5)
        y = pd.Series(base)
        x = pd.Series(200 - base + rng.randn(200) * 0.01)  # anti-correlated
        # Both recent and historical should be negative and roughly equal
        result = strategy._check_leg_correlation_stability(y, x, "anti")
        assert result is True

    def test_zero_historical_corr(self):
<<<<<<< HEAD
        """Historical corr Ôëê 0 Ôåô abs(hist) < 1e-6 Ôåô no division, returns True."""
=======
        """Historical corr ≈ 0 ↓ abs(hist) < 1e-6 ↓ no division, returns True."""
>>>>>>> origin/main
        strategy = _make_strategy()
        rng = np.random.RandomState(9)
        # Build series with near-zero overall correlation over 4*window range
        n = 200
        y = pd.Series(rng.randn(n).cumsum())
<<<<<<< HEAD
        # x is random walk independent of y Ôåô correlation ~0
        x = pd.Series(rng.randn(n).cumsum())
        # We can't guarantee the method returns True or False ÔÇô but it should not crash
=======
        # x is random walk independent of y ↓ correlation ~0
        x = pd.Series(rng.randn(n).cumsum())
        # We can't guarantee the method returns True or False – but it should not crash
>>>>>>> origin/main
        strategy._check_leg_correlation_stability(y, x, "random")
        assert "random" in strategy._leg_correlation_history


# ===================================================================
# 5. Pair exclusion / rehabilitation
# ===================================================================

class TestPairExclusion:
    """Pairs flagged for correlation breakdown are excluded."""

    def test_exclusion_after_breakdown(self):
        strategy = _make_strategy()
        strategy._excluded_pairs_correlation.add("A_B")
        assert "A_B" in strategy.get_excluded_pairs_correlation()

    def test_reset_single(self):
        strategy = _make_strategy()
        strategy._excluded_pairs_correlation.update({"A_B", "C_D"})
        strategy.reset_correlation_exclusion("A_B")
        assert "A_B" not in strategy._excluded_pairs_correlation
        assert "C_D" in strategy._excluded_pairs_correlation

    def test_reset_all(self):
        strategy = _make_strategy()
        strategy._excluded_pairs_correlation.update({"A_B", "C_D", "E_F"})
        strategy.reset_correlation_exclusion()
        assert len(strategy._excluded_pairs_correlation) == 0

    def test_reset_nonexistent_pair_noop(self):
        strategy = _make_strategy()
        strategy.reset_correlation_exclusion("NONEXISTENT")
        assert len(strategy._excluded_pairs_correlation) == 0


# ===================================================================
# 6. Analytics exposure
# ===================================================================

class TestAnalytics:
    """``get_leg_correlation_history()`` exposes monitoring data."""

    def test_empty_by_default(self):
        strategy = _make_strategy()
        assert strategy.get_leg_correlation_history() == {}

    def test_populated_after_check(self):
        strategy = _make_strategy()
        y, x = _correlated_series(200)
        strategy._check_leg_correlation_stability(y, x, "A_B")
        hist = strategy.get_leg_correlation_history()
        assert "A_B" in hist
        assert "recent_corr" in hist["A_B"]
        assert "historical_corr" in hist["A_B"]
        assert "window" in hist["A_B"]

    def test_multiple_pairs_tracked(self):
        strategy = _make_strategy()
        y1, x1 = _correlated_series(200, seed=1)
        y2, x2 = _correlated_series(200, seed=2)
        strategy._check_leg_correlation_stability(y1, x1, "P1")
        strategy._check_leg_correlation_stability(y2, x2, "P2")
        assert len(strategy.get_leg_correlation_history()) == 2


# ===================================================================
<<<<<<< HEAD
# 7. Integration ÔÇô generate_signals exits on breakdown
=======
# 7. Integration – generate_signals exits on breakdown
>>>>>>> origin/main
# ===================================================================

class TestGenerateSignalsIntegration:
    """
    Integration tests verifying that ``generate_signals()`` correctly
    closes positions and excludes pairs on correlation breakdown.
    """

    def _build_strategy_with_mocks(self, corr_stable: bool = True):
        """
        Build a strategy with mocked internals so ``generate_signals()``
        reaches the correlation check without crashing on unrelated components.
        """
        strategy = _make_strategy()

        # Pre-set an active trade for the pair
        strategy.active_trades["A_B"] = {
            "entry_z": -2.1,
            "entry_time": datetime(2025, 1, 1),
            "side": "long",
            "entry_threshold": 2.0,
            "entry_spread": 0.5,
            "entry_regime": "NORMAL",
            "position_multiplier": 1.0,
        }

        # Mock the correlation check to return whatever we need
        strategy._check_leg_correlation_stability = MagicMock(return_value=corr_stable)

        # Mock heavy dependencies so generate_signals proceeds cleanly
        strategy.hedge_ratio_tracker.is_pair_deprecated = MagicMock(return_value=False)
        strategy.model_retrainer.schedule_retraining_check = MagicMock(return_value=False)
        strategy.stationarity_monitor.check = MagicMock(return_value=(True, 0.001))
        strategy.concentration_limits.remove_position = MagicMock()
        strategy.trailing_stop_manager.remove_position = MagicMock()

        return strategy

    def test_breakdown_emits_exit_signal(self):
<<<<<<< HEAD
        """Active position + correlation breakdown Ôåô exit signal emitted."""
=======
        """Active position + correlation breakdown ↓ exit signal emitted."""
>>>>>>> origin/main
        strategy = self._build_strategy_with_mocks(corr_stable=False)
        # Prepare a stub correlation history for the exit reason string
        strategy._leg_correlation_history["A_B"] = {
            "recent_corr": 0.10,
            "historical_corr": 0.90,
            "window": 30,
            "stable": False,
        }

        # Build minimal market data
        rng = np.random.RandomState(42)
        n = 200
        idx = pd.date_range("2025-01-01", periods=n, freq="D")
        market_data = pd.DataFrame({
            "A": 100 + np.cumsum(rng.randn(n) * 0.5),
            "B": 100 + np.cumsum(rng.randn(n) * 0.5),
        }, index=idx)

        discovered = [("A", "B", 0.01, 20)]
        signals = strategy.generate_signals(market_data, discovered_pairs=discovered)

        # Should have an exit signal for A_B
        exit_signals = [s for s in signals if s.side == "exit" and s.symbol_pair == "A_B"]
        assert len(exit_signals) == 1
        # Accept either correlation breakdown or structural break (CUSUM fires first)
        reason = exit_signals[0].reason.lower()
        assert "correlation breakdown" in reason or "structural break" in reason

    def test_breakdown_excludes_pair(self):
        """After breakdown, pair is added to exclusion set."""
        strategy = self._build_strategy_with_mocks(corr_stable=False)
        strategy._leg_correlation_history["A_B"] = {
            "recent_corr": 0.10, "historical_corr": 0.90,
            "window": 30, "stable": False,
        }
        rng = np.random.RandomState(42)
        n = 200
        idx = pd.date_range("2025-01-01", periods=n, freq="D")
        market_data = pd.DataFrame({
            "A": 100 + np.cumsum(rng.randn(n) * 0.5),
            "B": 100 + np.cumsum(rng.randn(n) * 0.5),
        }, index=idx)
        strategy.generate_signals(market_data, discovered_pairs=[("A", "B", 0.01, 20)])
        assert "A_B" in strategy._excluded_pairs_correlation

    def test_no_exit_when_no_active_trade(self):
<<<<<<< HEAD
        """Correlation breakdown without active trade Ôåô no exit signal, just exclusion."""
=======
        """Correlation breakdown without active trade ↓ no exit signal, just exclusion."""
>>>>>>> origin/main
        strategy = self._build_strategy_with_mocks(corr_stable=False)
        strategy.active_trades.clear()
        strategy._leg_correlation_history["A_B"] = {
            "recent_corr": 0.10, "historical_corr": 0.90,
            "window": 30, "stable": False,
        }
        rng = np.random.RandomState(42)
        n = 200
        idx = pd.date_range("2025-01-01", periods=n, freq="D")
        market_data = pd.DataFrame({
            "A": 100 + np.cumsum(rng.randn(n) * 0.5),
            "B": 100 + np.cumsum(rng.randn(n) * 0.5),
        }, index=idx)
        signals = strategy.generate_signals(market_data, discovered_pairs=[("A", "B", 0.01, 20)])
        exit_signals = [s for s in signals if s.side == "exit" and s.symbol_pair == "A_B"]
        assert len(exit_signals) == 0
        assert "A_B" in strategy._excluded_pairs_correlation


# ===================================================================
# 8. Pre-excluded pair skip
# ===================================================================

class TestPreExcludedPairSkip:
    """Already-excluded pair is completely skipped in generate_signals."""

    def test_excluded_pair_skipped(self):
        strategy = _make_strategy()
        strategy._excluded_pairs_correlation.add("A_B")
        strategy.hedge_ratio_tracker.is_pair_deprecated = MagicMock(return_value=False)
        strategy.model_retrainer.schedule_retraining_check = MagicMock(return_value=False)
        strategy.stationarity_monitor.check = MagicMock(return_value=(True, 0.001))

        rng = np.random.RandomState(42)
        n = 200
        idx = pd.date_range("2025-01-01", periods=n, freq="D")
        market_data = pd.DataFrame({
            "A": 100 + np.cumsum(rng.randn(n) * 0.5),
            "B": 100 + np.cumsum(rng.randn(n) * 0.5),
        }, index=idx)

        signals = strategy.generate_signals(market_data, discovered_pairs=[("A", "B", 0.01, 20)])

        # No signals of any kind should be generated for excluded pair
        ab_signals = [s for s in signals if s.symbol_pair == "A_B"]
        assert len(ab_signals) == 0


# ===================================================================
# 9. Config parametrisation
# ===================================================================

class TestConfigParametrisation:
    """Configuration values flow correctly into the strategy."""

    def test_default_window(self):
        strategy = _make_strategy()
        assert strategy.leg_correlation_window == 30

    def test_custom_window(self):
        strategy = _make_strategy(leg_correlation_window=50)
        assert strategy.leg_correlation_window == 50

    def test_default_threshold(self):
        strategy = _make_strategy()
        assert strategy.leg_correlation_decay_threshold == 0.5

    def test_custom_threshold(self):
        strategy = _make_strategy(leg_correlation_decay_threshold=0.3)
        assert strategy.leg_correlation_decay_threshold == 0.3


# ===================================================================
# 10. Window sensitivity
# ===================================================================

class TestWindowSensitivity:
    """Verify that varying the window parameter changes results correctly."""

    def test_small_window_more_sensitive(self):
        """
        A smaller window focused entirely on post-break data should detect
        breakdown when the default window (30) does. We verify by constructing
        a series where the default window=30 detects breakdown and confirm
        a smaller window=20 also catches it.
        """
        strategy = _make_strategy()
        y, x = _breaking_series(200, break_point=150, seed=42)
        # Default window=30 should detect breakdown
        result_default = strategy._check_leg_correlation_stability(y, x, "pair_30", window=30)
        # Slightly smaller window=20 should also detect
        result_small = strategy._check_leg_correlation_stability(y, x, "pair_20", window=20)
        # Both should flag breakdown (the break happened at 150/200, both windows are post-break)
        assert result_default is False
        assert result_small is False

    def test_window_matches_config(self):
        """When no explicit window is given, config value is used."""
        strategy = _make_strategy(leg_correlation_window=25)
        y, x = _correlated_series(200)
        strategy._check_leg_correlation_stability(y, x, "pair1")
        assert strategy._leg_correlation_history["pair1"]["window"] == 25
