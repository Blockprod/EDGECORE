"""
Sprint 2.1 – Stationarity Monitor tests.

Proves M-01 fix:
  - StationarityMonitor detects stationary vs non-stationary spread
  - Rolling ADF on last ``window`` observations
  - Insufficient data returns stationary=True (conservative)
  - Random walk correctly flagged as non-stationary
  - Integrated into PairTradingStrategy (stationarity_monitor attribute)

Run: pytest tests/test_stationarity_monitor.py -v
"""

import pytest
import numpy as np
import pandas as pd

from models.stationarity_monitor import (
    StationarityMonitor,
    StationarityConfig,
)


# ========================================================================
# Helpers
# ========================================================================

def _make_stationary_spread(n=200, seed=42):
    """Mean-reverting OU-like spread (stationary)."""
    np.random.seed(seed)
    spread = np.zeros(n)
    for t in range(1, n):
        spread[t] = 0.7 * spread[t - 1] + np.random.normal(0, 1)
    return pd.Series(spread)


def _make_random_walk(n=200, seed=42):
    """Pure random walk (non-stationary)."""
    np.random.seed(seed)
    return pd.Series(np.cumsum(np.random.normal(0, 1, n)))


def _make_regime_break(n=300, break_at=200, seed=42):
    """Stationary for first `break_at` bars, then random walk."""
    np.random.seed(seed)
    part1 = np.zeros(break_at)
    for t in range(1, break_at):
        part1[t] = 0.7 * part1[t - 1] + np.random.normal(0, 1)
    part2 = part1[-1] + np.cumsum(np.random.normal(0, 1, n - break_at))
    return pd.Series(np.concatenate([part1, part2]))


# ========================================================================
# Unit tests – StationarityMonitor
# ========================================================================

class TestStationarityMonitorBasic:
    """Core logic tests."""

    def test_stationary_spread_passes(self):
        """OU-like spread should be detected as stationary."""
        mon = StationarityMonitor()
        spread = _make_stationary_spread(200)
        is_ok, pval = mon.check(spread)
        assert is_ok is True
        assert pval < 0.10

    def test_random_walk_fails(self):
        """Random walk should be detected as non-stationary."""
        mon = StationarityMonitor()
        spread = _make_random_walk(200)
        is_ok, pval = mon.check(spread)
        assert is_ok is False
        assert pval >= 0.10

    def test_insufficient_data_returns_stationary(self):
        """Short series ↓ conservatively returns stationary."""
        mon = StationarityMonitor()
        spread = pd.Series([1.0, 2.0, 3.0])
        is_ok, pval = mon.check(spread)
        assert is_ok is True
        assert pval == 0.0

    def test_zero_variance_returns_non_stationary(self):
        """Constant spread (zero variance) ↓ non-stationary."""
        mon = StationarityMonitor()
        spread = pd.Series(np.ones(100))
        is_ok, pval = mon.check(spread)
        assert is_ok is False
        assert pval == 1.0


class TestStationarityConfig:
    """Configuration tests."""

    def test_default_config(self):
        mon = StationarityMonitor()
        assert mon.config.window == 60
        assert mon.config.alert_pvalue == 0.10

    def test_custom_window(self):
        cfg = StationarityConfig(window=30)
        mon = StationarityMonitor(config=cfg)
        assert mon.config.window == 30

    def test_strict_pvalue(self):
        """Stricter p-value threshold (0.05) may reject borderline cases."""
        cfg = StationarityConfig(alert_pvalue=0.05)
        mon = StationarityMonitor(config=cfg)
        spread = _make_stationary_spread(200)
        is_ok, pval = mon.check(spread)
        # For a strong OU process, should still pass at 0.05
        assert is_ok is True

    def test_very_loose_pvalue(self):
        """Very loose threshold (0.50): even random walks might pass."""
        cfg = StationarityConfig(alert_pvalue=0.50)
        mon = StationarityMonitor(config=cfg)
        # Some random walks will have p < 0.50
        spread = _make_random_walk(200, seed=99)
        is_ok, pval = mon.check(spread)
        # We don't assert the outcome – just that it runs
        assert isinstance(is_ok, bool)
        assert 0.0 <= pval <= 1.0


class TestRegimeBreakDetection:
    """Key test from DoD: regime break ↓ stationarity loss detected."""

    def test_regime_break_detected_after_bar_200(self):
        """Stationary spread for 200 bars, then random walk.
        Monitor should detect non-stationarity AFTER the break."""
        spread = _make_regime_break(n=300, break_at=200, seed=42)
        mon = StationarityMonitor(config=StationarityConfig(window=60))

        # Before break: check at bar 199 (using first 200 obs)
        is_ok_before, pval_before = mon.check(spread.iloc[:200])
        assert is_ok_before is True, f"Before break should be stationary, p={pval_before}"

        # After break: check at bar 299 (last 60 obs are all random walk)
        is_ok_after, pval_after = mon.check(spread)
        assert is_ok_after is False, f"After break should be non-stationary, p={pval_after}"

    def test_early_break_detection(self):
        """The monitor should flag non-stationarity as early as possible
        after the structural break (ideally within ~window bars)."""
        spread = _make_regime_break(n=300, break_at=150, seed=42)
        mon = StationarityMonitor(config=StationarityConfig(window=60))

        # Scan bar-by-bar after break to find first non-stationary signal
        first_alarm = None
        for bar in range(160, 300):
            is_ok, _pval = mon.check(spread.iloc[: bar + 1])
            if not is_ok:
                first_alarm = bar
                break

        assert first_alarm is not None, "Monitor never raised alarm after break"
        # Should fire within window bars after the break
        assert first_alarm <= 150 + 60 + 20, (
            f"Alarm at bar {first_alarm}, expected within ~80 bars after break at 150"
        )


class TestStationarityMonitorPerformance:
    """Check ADF test runs fast enough for bar-by-bar use."""

    def test_adf_speed(self):
        """ADF on 60 observations should take < 10ms."""
        import time

        mon = StationarityMonitor()
        spread = _make_stationary_spread(200)

        start = time.time()
        for _ in range(100):
            mon.check(spread)
        elapsed = time.time() - start

        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 10, f"Average ADF check: {avg_ms:.2f}ms (must be < 10ms)"


class TestStrategyIntegration:
    """Verify PairTradingStrategy has the stationarity monitor wired."""

    def test_strategy_has_stationarity_monitor(self):
        from strategies.pair_trading import PairTradingStrategy

        strategy = PairTradingStrategy()
        assert hasattr(strategy, "stationarity_monitor")
        assert isinstance(strategy.stationarity_monitor, StationarityMonitor)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
