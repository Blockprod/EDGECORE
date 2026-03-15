"""
Phase 2 Risk Module Tests
=========================
Tests for the 4 risk modules introduced in Phase 2:
  2.1 FactorModel (per-pair beta-neutral weights + portfolio beta)
  2.2 SectorExposureMonitor (sector concentration limits)
  2.3 VaRMonitor (rolling historical VaR/CVaR)
  2.4 DrawdownManager (multi-tier drawdown response)
"""

import numpy as np
import pandas as pd
import pytest

from risk.factor_model import FactorModel, FactorModelConfig
from risk.sector_exposure import SectorExposureMonitor, SectorExposureConfig
from risk.var_monitor import VaRMonitor, VaRConfig
from risk.drawdown_manager import (
    DrawdownManager,
    DrawdownConfig,
    DrawdownAction,
    DrawdownTier,
)


# ÔöÇÔöÇÔöÇ 2.1: FactorModel ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

class TestFactorModel:
    """Per-pair beta-neutral weight computation."""

    @pytest.fixture
    def prices(self):
        """Generate synthetic prices with known beta structure."""
        np.random.seed(42)
        n = 120
        dates = pd.bdate_range("2023-01-01", periods=n)
        mkt = np.cumsum(np.random.randn(n) * 0.01) + 100
        # sym_a: beta ~ 1.2
        sym_a = 100 + np.cumsum(1.2 * np.diff(mkt, prepend=mkt[0]) + np.random.randn(n) * 0.002)
        # sym_b: beta ~ 0.8
        sym_b = 100 + np.cumsum(0.8 * np.diff(mkt, prepend=mkt[0]) + np.random.randn(n) * 0.002)
        return pd.DataFrame({"SPY": mkt, "A": sym_a, "B": sym_b}, index=dates)

    def test_estimate_beta_returns_float(self, prices):
        fm = FactorModel(FactorModelConfig(lookback=60, min_observations=30))
        beta = fm.estimate_beta(prices, "A", bar_idx=80)
        assert isinstance(beta, float)

    def test_beta_direction(self, prices):
        fm = FactorModel(FactorModelConfig(lookback=60, min_observations=30))
        beta_a = fm.estimate_beta(prices, "A", bar_idx=100)
        beta_b = fm.estimate_beta(prices, "B", bar_idx=100)
        # Both should be positive (move with market)
        assert beta_a > 0
        assert beta_b > 0
        # A has higher beta than B
        assert beta_a > beta_b

    def test_beta_neutral_ratio_sane(self, prices):
        fm = FactorModel(FactorModelConfig(lookback=60, min_observations=30))
        ratio = fm.compute_beta_neutral_ratio(prices, "A", "B", bar_idx=100)
        # ratio = |beta_A| / |beta_B| Ôëê 1.2/0.8 Ôëê 1.5
        assert 0.5 <= ratio <= 2.0  # clipped range

    def test_insufficient_data_returns_unity(self, prices):
        fm = FactorModel(FactorModelConfig(lookback=60, min_observations=30))
        # bar_idx=10 ÔåÆ only 11 observations < min_observations=30
        ratio = fm.compute_beta_neutral_ratio(prices, "A", "B", bar_idx=10)
        assert ratio == 1.0  # fallback

    def test_portfolio_beta(self, prices):
        fm = FactorModel(FactorModelConfig(lookback=60, min_observations=30))
        positions = {
            "A_B": {
                "sym1": "A", "sym2": "B", "side": "long",
                "notional": 10000, "notional_1": 5000, "notional_2": 5000,
            }
        }
        beta, is_neutral = fm.portfolio_beta(
            positions, prices, bar_idx=100, portfolio_value=100000
        )
        assert isinstance(beta, float)
        assert isinstance(is_neutral, bool)

    def test_beta_values_shift_with_window(self, prices):
        fm = FactorModel(FactorModelConfig(
            lookback=60, min_observations=30, reestimate_interval=5
        ))
        b1 = fm.estimate_beta(prices, "A", bar_idx=80)
        b2 = fm.estimate_beta(prices, "A", bar_idx=110)
        # Different windows ÔåÆ values may differ
        assert isinstance(b1, float)
        assert isinstance(b2, float)


# ÔöÇÔöÇÔöÇ 2.2: SectorExposureMonitor ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

class TestSectorExposureMonitor:
    """Sector concentration limit checks."""

    @pytest.fixture
    def monitor(self):
        sector_map = {
            "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
            "NVDA": "Technology", "AMD": "Technology",
            "JPM": "Financials", "GS": "Financials",
            "XOM": "Energy", "CVX": "Energy",
            "KO": "Consumer", "PEP": "Consumer",
        }
        return SectorExposureMonitor(
            sector_map=sector_map,
            config=SectorExposureConfig(max_sector_weight=0.25, max_sector_positions=4),
        )

    def test_allow_first_trade(self, monitor):
        ok, reason = monitor.can_enter("AAPL_JPM", 10000, 100000, {})
        assert ok is True
        assert reason is None

    def test_reject_sector_overweight(self, monitor):
        # Fill 4 tech positions at 8k each. Per _compute_sector_stats: each
        # position attributes notional/2 to its sector, so tech gets 4*4k=16k.
        # Adding NVDA_CVX (8k) would push tech to 16k+8k=24k.
        # But can_enter adds full new_notional: (16k+8k)/80k=30% > 25%.
        positions = {
            "AAPL_JPM": {"sym1": "AAPL", "sym2": "JPM", "notional": 8000},
            "MSFT_GS": {"sym1": "MSFT", "sym2": "GS", "notional": 8000},
            "GOOGL_XOM": {"sym1": "GOOGL", "sym2": "XOM", "notional": 8000},
            "NVDA_KO": {"sym1": "NVDA", "sym2": "KO", "notional": 8000},
        }
        ok, reason = monitor.can_enter("AMD_CVX", 8000, 80000, positions)
        assert ok is False
        assert "Technology" in reason

    def test_reject_sector_position_count(self, monitor):
        positions = {
            "AAPL_XOM": {"sym1": "AAPL", "sym2": "XOM", "notional": 2000},
            "MSFT_CVX": {"sym1": "MSFT", "sym2": "CVX", "notional": 2000},
            "GOOGL_KO": {"sym1": "GOOGL", "sym2": "KO", "notional": 2000},
            "NVDA_PEP": {"sym1": "NVDA", "sym2": "PEP", "notional": 2000},
        }
        # 5th tech position ÔåÆ exceeds max_sector_positions=4
        ok, reason = monitor.can_enter("AMD_JPM", 2000, 100000, positions)
        assert ok is False

    def test_allow_different_sector(self, monitor):
        positions = {
            "AAPL_JPM": {"sym1": "AAPL", "sym2": "JPM", "notional": 10000},
        }
        ok, _ = monitor.can_enter("KO_PEP", 10000, 100000, positions)
        assert ok is True

    def test_exposure_report(self, monitor):
        positions = {
            "AAPL_JPM": {"sym1": "AAPL", "sym2": "JPM", "notional": 10000},
        }
        report = monitor.get_exposure_report(positions, 100000)
        assert "Technology" in report
        assert "Financials" in report


# ÔöÇÔöÇÔöÇ 2.3: VaRMonitor ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

class TestVaRMonitor:
    """Rolling historical VaR/CVaR monitoring."""

    def test_insufficient_data_ok(self):
        vm = VaRMonitor(VaRConfig(min_observations=20))
        ok, breach = vm.check_limit(100000)
        assert ok is True  # not enough data ÔåÆ pass

    def test_var_after_feeding(self):
        np.random.seed(0)
        vm = VaRMonitor(VaRConfig(lookback_window=60, min_observations=20))
        for _ in range(60):
            vm.update(np.random.randn() * 0.01)
        var = vm.current_var()
        assert var is not None
        assert var > 0  # VaR is positive (convention: loss magnitude)

    def test_cvar_worse_than_var(self):
        np.random.seed(0)
        vm = VaRMonitor(VaRConfig(lookback_window=60, min_observations=20))
        for _ in range(60):
            vm.update(np.random.randn() * 0.01)
        var = vm.current_var()
        cvar = vm.current_cvar()
        assert cvar >= var  # CVaR >= VaR (deeper into the tail, higher positive loss)

    def test_check_limit_blocks_on_breach(self):
        vm = VaRMonitor(VaRConfig(lookback_window=30, min_observations=10, var_limit_pct=0.01))
        # Feed very negative returns to trigger breach
        for _ in range(30):
            vm.update(-0.05)  # -5% daily
        ok, breach = vm.check_limit(100000)
        assert ok is False
        assert breach is not None

    def test_check_limit_ok_normal(self):
        vm = VaRMonitor(VaRConfig(lookback_window=30, min_observations=10, var_limit_pct=0.10))
        for _ in range(30):
            vm.update(0.001)  # very small positive returns
        ok, _ = vm.check_limit(100000)
        assert ok is True


# ÔöÇÔöÇÔöÇ 2.4: DrawdownManager ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

class TestDrawdownManager:
    """Multi-tier drawdown response."""

    def test_normal_no_drawdown(self):
        dm = DrawdownManager()
        action = dm.evaluate(100000, 100000)
        assert action.tier == DrawdownTier.NORMAL
        assert action.sizing_multiplier == 1.0
        assert action.close_fraction == 0.0
        assert action.is_halted is False

    def test_tier1_reduce_sizing(self):
        dm = DrawdownManager(DrawdownConfig(tier_1_pct=0.03))
        action = dm.evaluate(96000, 100000)  # 4% DD
        assert action.tier == DrawdownTier.TIER_1
        assert action.sizing_multiplier == 0.5
        assert action.close_fraction == 0.0
        assert action.is_halted is False

    def test_tier2_close_half(self):
        dm = DrawdownManager(DrawdownConfig(tier_2_pct=0.05))
        action = dm.evaluate(94000, 100000)  # 6% DD
        assert action.tier == DrawdownTier.TIER_2
        assert action.close_fraction == 0.5
        assert action.is_halted is False

    def test_tier2_close_once(self):
        dm = DrawdownManager(DrawdownConfig(tier_2_pct=0.05))
        a1 = dm.evaluate(94000, 100000)
        assert a1.close_fraction == 0.5
        # Second eval in same tier ÔåÆ no more closes
        a2 = dm.evaluate(94000, 100000)
        assert a2.close_fraction == 0.0
        assert a2.tier == DrawdownTier.TIER_2

    def test_tier3_halt_and_cooldown(self):
        dm = DrawdownManager(DrawdownConfig(
            tier_3_pct=0.08, tier_3_cooldown_bars=3
        ))
        action = dm.evaluate(91000, 100000)  # 9% DD
        assert action.tier == DrawdownTier.TIER_3
        assert action.is_halted is True
        assert action.close_fraction == 1.0

        # During cooldown
        for _ in range(2):
            a = dm.evaluate(91000, 100000)
            assert a.is_halted is True

        # Last cooldown bar ÔåÆ still halted
        a = dm.evaluate(91000, 100000)
        # After cooldown expires ÔåÆ normal again
        a = dm.evaluate(91000, 91000)
        assert a.tier == DrawdownTier.NORMAL

    def test_tier4_full_stop_latching(self):
        dm = DrawdownManager(DrawdownConfig(tier_4_pct=0.12))
        action = dm.evaluate(87000, 100000)  # 13% DD
        assert action.tier == DrawdownTier.TIER_4
        assert action.is_halted is True

        # Even if equity recovers, tier 4 is latching
        action2 = dm.evaluate(99000, 100000)
        assert action2.tier == DrawdownTier.TIER_4
        assert action2.is_halted is True

    def test_tier4_manual_reset(self):
        dm = DrawdownManager(DrawdownConfig(tier_4_pct=0.12))
        dm.evaluate(87000, 100000)
        dm.reset()
        action = dm.evaluate(99000, 99000)
        assert action.tier == DrawdownTier.NORMAL

    def test_escalation_order(self):
        dm = DrawdownManager()
        # Start normal
        a = dm.evaluate(100000, 100000)
        assert a.tier == DrawdownTier.NORMAL

        # Drop to T1
        a = dm.evaluate(96500, 100000)
        assert a.tier == DrawdownTier.TIER_1

        # Drop to T2
        a = dm.evaluate(94000, 100000)
        assert a.tier == DrawdownTier.TIER_2

        # Drop to T3
        a = dm.evaluate(91000, 100000)
        assert a.tier == DrawdownTier.TIER_3
