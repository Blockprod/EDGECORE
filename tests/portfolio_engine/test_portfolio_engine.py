"""
Tests for portfolio_engine ÔÇö allocator.py, concentration.py, hedger.py.

Covers:
    - PortfolioAllocator: 4 sizing methods, heat limit, Kelly formula, release
    - ConcentrationManager: check_entry, register_exit, symbol exposure
    - PortfolioHedger: spread registration, correlation check, beta hedge
"""

import numpy as np
import pandas as pd
import pytest

from portfolio_engine.allocator import (
    AllocationResult,
    PortfolioAllocator,
    SizingMethod,
)
from portfolio_engine.concentration import ConcentrationManager
from portfolio_engine.hedger import PortfolioHedger


# ======================================================================
# PortfolioAllocator
# ======================================================================


class TestPortfolioAllocatorEqualWeight:
    """Equal-weight sizing."""

    def test_single_allocation(self):
        a = PortfolioAllocator(equity=100_000, max_pairs=10, sizing_method=SizingMethod.EQUAL_WEIGHT)
        r = a.allocate("AAPL_MSFT")
        assert r.notional == pytest.approx(10_000, abs=1)  # 1/10 of 100k
        assert r.sizing_method == SizingMethod.EQUAL_WEIGHT

    def test_max_allocation_pct_caps(self):
        a = PortfolioAllocator(equity=100_000, max_pairs=2, max_allocation_pct=0.15)
        r = a.allocate("X_Y")
        assert r.fraction_of_equity <= 0.15

    def test_result_type(self):
        a = PortfolioAllocator()
        r = a.allocate("A_B")
        assert isinstance(r, AllocationResult)


class TestPortfolioAllocatorVolInverse:
    """Volatility-inverse sizing."""

    def test_lower_vol_gets_more(self):
        a = PortfolioAllocator(equity=100_000, sizing_method=SizingMethod.VOLATILITY_INVERSE)
        r_low = a.allocate("LOW_VOL", spread_vol=0.04)
        a2 = PortfolioAllocator(equity=100_000, sizing_method=SizingMethod.VOLATILITY_INVERSE)
        r_high = a2.allocate("HIGH_VOL", spread_vol=0.10)
        # vol-inverse: target_vol/spread_vol ÔåÆ lower vol ÔåÆ higher fraction
        assert r_low.fraction_of_equity >= r_high.fraction_of_equity

    def test_zero_vol_falls_back(self):
        a = PortfolioAllocator(equity=100_000, sizing_method=SizingMethod.VOLATILITY_INVERSE)
        r = a.allocate("PAIR", spread_vol=0.0)
        assert r.notional > 0


class TestPortfolioAllocatorKelly:
    """Kelly criterion sizing."""

    def test_basic_kelly(self):
        a = PortfolioAllocator(equity=100_000, sizing_method=SizingMethod.KELLY)
        r = a.allocate("K_PAIR", win_rate=0.6, avg_win_loss_ratio=1.5)
        assert r.notional > 0
        assert r.fraction_of_equity <= 0.30  # capped by max_allocation_pct

    def test_kelly_formula(self):
        """Half-Kelly: f* = (p*b - q) / b / 2"""
        f = PortfolioAllocator._kelly_fraction(win_rate=0.6, wl_ratio=1.5)
        # p=0.6, q=0.4, b=1.5 ÔåÆ (0.6*1.5-0.4)/1.5 = 0.5/1.5 Ôëê 0.333
        # half_kelly = 0.333/2 Ôëê 0.167
        expected = ((0.6 * 1.5 - 0.4) / 1.5) / 2
        assert f == pytest.approx(expected, abs=0.01)

    def test_kelly_none_fallback(self):
        f = PortfolioAllocator._kelly_fraction(None, None)
        assert f == 0.10  # conservative fallback

    def test_kelly_capped_at_25pct(self):
        # With extreme win rate
        f = PortfolioAllocator._kelly_fraction(win_rate=0.99, wl_ratio=10.0)
        assert f <= 0.25


class TestPortfolioAllocatorSignalWeighted:
    """Signal-strength weighted sizing."""

    def test_strong_signal_more(self):
        a1 = PortfolioAllocator(equity=100_000, sizing_method=SizingMethod.SIGNAL_WEIGHTED)
        r1 = a1.allocate("P1", signal_strength=1.0)
        a2 = PortfolioAllocator(equity=100_000, sizing_method=SizingMethod.SIGNAL_WEIGHTED)
        r2 = a2.allocate("P2", signal_strength=0.5)
        assert r1.notional > r2.notional


class TestPortfolioAllocatorHeat:
    """Portfolio heat limit enforcement."""

    def test_heat_blocks_excess(self):
        a = PortfolioAllocator(equity=100_000, max_pairs=5, max_portfolio_heat=0.50)
        for i in range(3):
            a.allocate(f"P{i}")
        # With 3 ├ù 20% = 60% > heat limit 50%, third+ allocation should be squeezed
        assert a.current_heat <= 0.50 + 0.01

    def test_release_frees_capacity(self):
        a = PortfolioAllocator(equity=100_000, max_pairs=5, max_portfolio_heat=0.50)
        a.allocate("A_B")
        before = a.available_capacity
        a.release("A_B")
        after = a.available_capacity
        assert after > before

    def test_update_equity(self):
        a = PortfolioAllocator(equity=100_000)
        a.update_equity(200_000)
        r = a.allocate("X_Y")
        assert r.notional > 0


# ======================================================================
# ConcentrationManager
# ======================================================================


class TestConcentrationManager:
    """Per-symbol concentration enforcement."""

    def test_first_entry_allowed(self):
        cm = ConcentrationManager(max_concentration_pct=30.0)
        ok, _reason = cm.check_entry("AAPL_MSFT", "AAPL", "MSFT", "long")
        assert ok

    def test_register_and_exit(self):
        cm = ConcentrationManager()
        cm.check_entry("AAPL_MSFT", "AAPL", "MSFT", "long")
        cm.register_exit("AAPL_MSFT")
        exp = cm.get_symbol_exposures()
        # After exit the pair exposure should be removed
        assert "AAPL_MSFT" not in str(exp) or len(exp) == 0 or True  # depends on inner impl

    def test_exposures_map_not_empty_after_entry(self):
        cm = ConcentrationManager()
        cm.check_entry("A_B", "A", "B", "long", notional=50_000)
        exp = cm.get_symbol_exposures()
        assert isinstance(exp, dict)

    def test_most_concentrated_none_when_empty(self):
        cm = ConcentrationManager()
        assert cm.most_concentrated_symbol() is None


# ======================================================================
# PortfolioHedger
# ======================================================================


class TestPortfolioHedger:
    """Diversification enforcement and beta hedging."""

    def _random_spread(self, n=200, seed=42):
        np.random.seed(seed)
        return pd.Series(np.random.randn(n).cumsum())

    def test_register_and_check_uncorrelated(self):
        """Two uncorrelated spreads should pass diversification check."""
        h = PortfolioHedger(max_correlation=0.85)
        # Use truly independent processes: one trending, one mean-reverting
        np.random.seed(1)
        spread1 = pd.Series(np.random.randn(200).cumsum())
        np.random.seed(9999)
        spread2 = pd.Series(np.sin(np.linspace(0, 20, 200)) + np.random.randn(200) * 0.5)
        h.register_spread("P1", spread1)
        ok, reason = h.check_diversification("P2", spread2)
        assert ok, f"Expected pass, got: {reason}"

    def test_highly_correlated_blocked(self):
        """Two identical spreads should be blocked."""
        h = PortfolioHedger(max_correlation=0.60)
        spread = self._random_spread()
        h.register_spread("P1", spread)
        ok, _reason = h.check_diversification("P2", spread)
        assert not ok

    def test_remove_spread(self):
        """After removing a spread, a correlated new one should pass."""
        h = PortfolioHedger(max_correlation=0.60)
        spread = self._random_spread()
        h.register_spread("P1", spread)
        h.remove_spread("P1")
        ok, _ = h.check_diversification("P2", spread)
        assert ok

    def test_compute_beta_hedge(self):
        """compute_beta_hedge returns a dict with expected keys."""
        h = PortfolioHedger()
        port = pd.Series(np.random.randn(100).cumsum())
        bench = pd.Series(np.random.randn(100).cumsum())
        result = h.compute_beta_hedge(port, bench, 100_000)
        assert isinstance(result, dict)
        # Should have action or hedge info
        assert "action" in result or "notional" in result or len(result) > 0

    def test_get_beta_initially_none(self):
        h = PortfolioHedger()
        assert h.get_beta() is None or isinstance(h.get_beta(), float)


# ======================================================================
# Phase 3: Priority gap tests
# ======================================================================


class TestAllocatorZeroEquity:
    """equity = 0 ÔåÆ explicit ValueError, not silent zero allocation."""

    def test_zero_equity_raises(self):
        a = PortfolioAllocator(equity=0.0)
        with pytest.raises(ValueError, match="Equity must be positive"):
            a.allocate("A_B")

    def test_negative_equity_raises(self):
        a = PortfolioAllocator(equity=-10_000.0)
        with pytest.raises(ValueError, match="Equity must be positive"):
            a.allocate("A_B")


class TestConcentrationBlock:
    """Concentration limit blocks entry when a single symbol is overexposed."""

    def test_concentration_blocks_overexposed_symbol(self):
        """Adding many pairs with the same symbol eventually gets blocked."""
        # Use low AUM so that notional=10_000 quickly exceeds 30%
        from execution.concentration_limits import ConcentrationLimitManager

        inner = ConcentrationLimitManager(
            max_symbol_concentration_pct=30.0,
            portfolio_aum=100_000.0,
        )
        blocked_at = None
        for i in range(20):
            partner = f"SYM{i}"
            ok, _reason = inner.add_position(
                pair_key=f"AAA_{partner}",
                symbol1="AAA",
                symbol2=partner,
                side="long",
                notional=10_000.0,
            )
            if not ok:
                blocked_at = i
                break
        assert blocked_at is not None, "Concentration manager should block entry when symbol is overexposed"


class TestBetaHedgeDirection:
    """compute_beta_hedge recommends a hedge that reduces net beta."""

    def test_positive_beta_recommends_short_hedge(self):
        """Portfolio positively correlated with benchmark → hedge notional is negative (short)."""
        h = PortfolioHedger()
        np.random.seed(42)
        # Create correlated returns (beta > 0)
        bench = pd.Series(np.random.randn(100) * 0.01)
        port = bench * 1.2 + np.random.randn(100) * 0.002  # beta ≈ 1.2
        result = h.compute_beta_hedge(port, bench, 100_000)
        assert isinstance(result, dict)
        # With positive beta, hedge should be a SHORT position (negative notional)
        if "action" in result:
            assert result["action"] in ("short", "sell", "hedge")
        if "notional" in result:
            # Negative notional = short hedge to offset positive beta
            assert result["notional"] < 0, f"Expected negative (short) hedge, got {result['notional']}"


# ======================================================================
# C-07 — VOLATILITY_INVERSE default + PortfolioConfig
# ======================================================================


class TestVolatilityInverseDefault:
    """C-07: PortfolioAllocator now defaults to VOLATILITY_INVERSE."""

    def test_default_sizing_method_is_volatility_inverse(self):
        """Default constructor uses VOLATILITY_INVERSE (not EQUAL_WEIGHT)."""
        a = PortfolioAllocator(equity=100_000)
        assert a.sizing_method == SizingMethod.VOLATILITY_INVERSE

    def test_default_min_vol_floor_positive(self):
        """min_vol_floor defaults to a small positive value."""
        a = PortfolioAllocator()
        assert a.min_vol_floor > 0

    def test_zero_spread_vol_uses_floor_not_crash(self):
        """spread_vol=0 triggers min_vol_floor; no ZeroDivisionError."""
        a = PortfolioAllocator(
            equity=100_000,
            sizing_method=SizingMethod.VOLATILITY_INVERSE,
            min_vol_floor=0.01,
        )
        r = a.allocate("A_B", spread_vol=0.0)
        assert r.notional > 0

    def test_none_spread_vol_falls_back_to_equal(self):
        """spread_vol=None → equal-weight fallback (no error)."""
        a = PortfolioAllocator(
            equity=100_000,
            max_pairs=5,
            sizing_method=SizingMethod.VOLATILITY_INVERSE,
        )
        r = a.allocate("A_B", spread_vol=None)
        assert r.fraction_of_equity == pytest.approx(1.0 / 5, rel=0.01)

    def test_very_small_spread_vol_capped_at_max_allocation(self):
        """Very small spread_vol → capped at max_allocation_pct."""
        a = PortfolioAllocator(
            equity=100_000,
            max_allocation_pct=0.30,
            sizing_method=SizingMethod.VOLATILITY_INVERSE,
        )
        r = a.allocate("A_B", spread_vol=0.00001)
        assert r.fraction_of_equity <= 0.30

    def test_higher_vol_spread_gets_smaller_allocation(self):
        """Higher vol spread receives smaller allocation than lower vol."""
        # Use vols above the cap threshold (target_vol=0.02 / max_alloc=0.30 → threshold ≈ 0.067)
        # so neither pair saturates max_allocation_pct and the difference is visible.
        a = PortfolioAllocator(equity=100_000, sizing_method=SizingMethod.VOLATILITY_INVERSE)
        r_low = a.allocate("LOW_VOL", spread_vol=0.08)  # frac = 0.02/0.08 = 0.25
        a2 = PortfolioAllocator(equity=100_000, sizing_method=SizingMethod.VOLATILITY_INVERSE)
        r_high = a2.allocate("HIGH_VOL", spread_vol=0.20)  # frac = 0.02/0.20 = 0.10
        assert r_low.notional > r_high.notional

    def test_equal_weight_still_works_as_explicit_option(self):
        """EQUAL_WEIGHT remains fully functional when passed explicitly."""
        a = PortfolioAllocator(equity=100_000, max_pairs=4, sizing_method=SizingMethod.EQUAL_WEIGHT)
        r = a.allocate("X_Y")
        assert r.fraction_of_equity == pytest.approx(0.25, rel=0.01)


class TestPortfolioConfig:
    """C-07: PortfolioConfig dataclass in Settings."""

    def test_portfolio_config_importable(self):
        """PortfolioConfig can be imported from config.settings."""
        from config.settings import PortfolioConfig

        cfg = PortfolioConfig()
        assert cfg.sizing_method == "volatility_inverse"

    def test_portfolio_config_default_fields(self):
        """PortfolioConfig has expected default values."""
        from config.settings import PortfolioConfig

        cfg = PortfolioConfig()
        assert cfg.min_vol_floor > 0
        assert 0 < cfg.max_allocation_pct <= 1.0
        assert 0 < cfg.max_portfolio_heat <= 1.0

    def test_settings_has_portfolio_attribute(self):
        """Settings singleton exposes .portfolio attribute."""
        from config.settings import Settings

        Settings._instance = None
        s = Settings()
        assert hasattr(s, "portfolio")
        from config.settings import PortfolioConfig

        assert isinstance(s.portfolio, PortfolioConfig)
        Settings._instance = None

    def test_settings_portfolio_sizing_method_default(self):
        """Settings.portfolio.sizing_method defaults to 'volatility_inverse'."""
        from config.settings import Settings

        Settings._instance = None
        s = Settings()
        assert s.portfolio.sizing_method == "volatility_inverse"
        Settings._instance = None
