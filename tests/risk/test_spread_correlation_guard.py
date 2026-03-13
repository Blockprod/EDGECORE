"""
Sprint 1.6 – Spread Correlation Guard tests.

Proves C-06 fix:
  - SpreadCorrelationGuard correctly allows uncorrelated entries
  - Rejects entries whose spread correlates too highly with existing positions
  - Threshold is configurable
  - StrategyBacktestSimulator integrates the guard

Run: pytest tests/test_spread_correlation_guard.py -v
"""

import pytest
import numpy as np
import pandas as pd

from risk.spread_correlation import (
    SpreadCorrelationGuard,
    SpreadCorrelationConfig,
)
from backtests.strategy_simulator import StrategyBacktestSimulator


# ========================================================================
# Helpers
# ========================================================================

def _make_spread(n=100, seed=0, drift=0.0):
    """Create a synthetic spread (mean-reverting noise)."""
    np.random.seed(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    noise = np.random.normal(drift, 1.0, n)
    return pd.Series(np.cumsum(noise - noise.mean()), index=idx)


def _make_correlated_spread(base: pd.Series, rho=0.95, seed=42):
    """Create a spread correlated with *base* at approximately *rho*."""
    np.random.seed(seed)
    noise = np.random.normal(0, 1, len(base))
    corr_data = rho * base.values + np.sqrt(1 - rho**2) * noise
    return pd.Series(corr_data, index=base.index)


# ========================================================================
# Unit tests – SpreadCorrelationGuard
# ========================================================================

class TestSpreadCorrelationGuardBasic:
    """Core logic tests."""

    def test_first_entry_always_allowed(self):
        """No existing positions ↓ entry allowed."""
        guard = SpreadCorrelationGuard()
        spread = _make_spread(100, seed=1)
        allowed, reason = guard.check_entry("A_B", spread)
        assert allowed is True
        assert reason is None

    def test_uncorrelated_pair_allowed(self):
        """Two independent spreads ↓ allowed."""
        guard = SpreadCorrelationGuard()
        s1 = _make_spread(100, seed=10)
        s2 = _make_spread(100, seed=20)

        guard.register_spread("A_B", s1)
        allowed, reason = guard.check_entry("C_D", s2)
        assert allowed is True

    def test_highly_correlated_pair_rejected(self):
        """Spread with ρ > 0.60 ↓ rejected."""
        guard = SpreadCorrelationGuard()
        s1 = _make_spread(100, seed=10)
        s_corr = _make_correlated_spread(s1, rho=0.95)

        guard.register_spread("A_B", s1)
        allowed, reason = guard.check_entry("C_D", s_corr)
        assert allowed is False
        assert "SPREAD_CORR_GUARD" in reason

    def test_negatively_correlated_pair_rejected(self):
        """Spread with ρ < -0.60 ↓ also rejected (|ρ| used)."""
        guard = SpreadCorrelationGuard()
        s1 = _make_spread(100, seed=10)
        s_neg = _make_correlated_spread(s1, rho=0.95)
        s_neg = -s_neg  # flip sign ↓ strong negative corr

        guard.register_spread("A_B", s1)
        allowed, reason = guard.check_entry("C_D", s_neg)
        assert allowed is False

    def test_moderate_correlation_allowed(self):
        """Spread with |ρ| < 0.40 ↓ allowed."""
        guard = SpreadCorrelationGuard()
        s1 = _make_spread(100, seed=10)
        # ρ ≈ 0.15 → empirical |corr| < 0.40
        s_mod = _make_correlated_spread(s1, rho=0.15, seed=99)

        guard.register_spread("A_B", s1)
        allowed, _reason = guard.check_entry("C_D", s_mod)
        assert allowed is True

    def test_remove_spread_clears_tracking(self):
        """After remove_spread the guard no longer checks against it."""
        guard = SpreadCorrelationGuard()
        s1 = _make_spread(100, seed=10)
        s_corr = _make_correlated_spread(s1, rho=0.95)

        guard.register_spread("A_B", s1)
        # Should reject
        allowed, _ = guard.check_entry("C_D", s_corr)
        assert allowed is False

        # Remove existing ↓ now candidate should be allowed
        guard.remove_spread("A_B")
        allowed, _ = guard.check_entry("C_D", s_corr)
        assert allowed is True

    def test_clear_removes_all(self):
        guard = SpreadCorrelationGuard()
        guard.register_spread("A_B", _make_spread(100, seed=1))
        guard.register_spread("C_D", _make_spread(100, seed=2))
        assert guard.active_count == 2
        guard.clear()
        assert guard.active_count == 0


class TestSpreadCorrelationConfig:
    """Configuration tests."""

    def test_custom_threshold(self):
        """Tighter threshold (0.30) rejects moderate correlation."""
        cfg = SpreadCorrelationConfig(max_correlation=0.30)
        guard = SpreadCorrelationGuard(config=cfg)

        s1 = _make_spread(100, seed=10)
        s_mod = _make_correlated_spread(s1, rho=0.5, seed=99)

        guard.register_spread("A_B", s1)
        allowed, _ = guard.check_entry("C_D", s_mod)
        assert allowed is False  # 0.5 > 0.30

    def test_loose_threshold_allows_more(self):
        """Looser threshold (0.95) allows highly correlated spreads."""
        cfg = SpreadCorrelationConfig(max_correlation=0.95)
        guard = SpreadCorrelationGuard(config=cfg)

        s1 = _make_spread(100, seed=10)
        s_corr = _make_correlated_spread(s1, rho=0.80, seed=99)

        guard.register_spread("A_B", s1)
        allowed, _ = guard.check_entry("C_D", s_corr)
        assert allowed is True  # empirical |ρ| ≈ 0.93 < 0.95

    def test_insufficient_overlap_allows_entry(self):
        """If series too short, guard conservatively allows."""
        cfg = SpreadCorrelationConfig(min_overlap_bars=50)
        guard = SpreadCorrelationGuard(config=cfg)

        s1 = _make_spread(30, seed=10)  # Only 30 bars
        s2 = _make_correlated_spread(s1, rho=0.99)

        guard.register_spread("A_B", s1)
        allowed, _ = guard.check_entry("C_D", s2)
        assert allowed is True  # Can't compute correlation ↓ allow


class TestSpreadCorrelationMultiplePositions:
    """Guard with more than one existing position."""

    def test_rejects_if_any_existing_is_too_correlated(self):
        """Even if 2 out of 3 existing are fine, the 3rd rejects."""
        guard = SpreadCorrelationGuard()

        s_base = _make_spread(100, seed=10)
        s_indep1 = _make_spread(100, seed=20)
        s_indep2 = _make_spread(100, seed=30)
        s_corr = _make_correlated_spread(s_base, rho=0.95)

        guard.register_spread("A_B", s_base)
        guard.register_spread("C_D", s_indep1)
        guard.register_spread("E_F", s_indep2)

        allowed, reason = guard.check_entry("G_H", s_corr)
        assert allowed is False
        assert "A_B" in reason  # Should identify which pair conflicts


# ========================================================================
# Integration – Simulator
# ========================================================================

class TestSimulatorSpreadCorrelationIntegration:
    """Verify the simulator wires the guard correctly."""

    def test_simulator_has_guard_by_default(self):
        sim = StrategyBacktestSimulator()
        assert sim.spread_corr_guard is not None
        assert isinstance(sim.spread_corr_guard, SpreadCorrelationGuard)

    def test_custom_guard_injected(self):
        cfg = SpreadCorrelationConfig(max_correlation=0.80)
        guard = SpreadCorrelationGuard(config=cfg)
        sim = StrategyBacktestSimulator(spread_corr_guard=guard)
        assert sim.spread_corr_guard.config.max_correlation == 0.80

    def test_compute_spread_helper(self):
        """_compute_spread returns a valid series from price data."""
        np.random.seed(42)
        n = 100
        idx = pd.date_range("2023-01-01", periods=n, freq="B")
        x = pd.Series(100.0 + np.cumsum(np.random.normal(0, 1, n)), index=idx)
        y = pd.Series(1.5 * x.values + np.random.normal(0, 1, n), index=idx)
        prices = pd.DataFrame({"SYM1": y, "SYM2": x}, index=idx)

        spread = StrategyBacktestSimulator._compute_spread(prices, "SYM1", "SYM2")
        assert spread is not None
        assert len(spread) == n
        assert not spread.isna().all()

    def test_compute_spread_short_data_returns_none(self):
        """Not enough data ↓ None."""
        idx = pd.date_range("2023-01-01", periods=10, freq="B")
        prices = pd.DataFrame(
            {"A": np.arange(10, dtype=float) + 1, "B": np.arange(10, dtype=float) + 1},
            index=idx,
        )
        assert StrategyBacktestSimulator._compute_spread(prices, "A", "B") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
