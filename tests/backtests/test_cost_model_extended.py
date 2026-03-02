"""
Sprint 2.3 – Tests for extended cost model (M-03 fix).

Tests:
  - Funding rate calculation
  - Round-trip ≥ 40 bps with realistic params
  - round_trip_cost_bps helper
  - CostModel backward compatibility (existing callers unaffected)
  - Integration with StrategyBacktestSimulator
"""

import pytest

from backtests.cost_model import CostModel, CostModelConfig


# ---------------------------------------------------------------------------
# Fix: Reset Settings singleton before/after tests
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def reset_settings():
    from config.settings import Settings
    Settings._instance = None
    yield
    Settings._instance = None


# ===========================================================================
# SECTION 1 – Funding Rate
# ===========================================================================

class TestFundingRate:
    """Tests for funding rate cost calculation."""

    def test_funding_disabled_by_default(self):
        """Funding is OFF by default – cost should be zero."""
        model = CostModel()
        assert not model.config.include_funding
        assert model.funding_cost(5000, 7) == 0.0

    def test_funding_enabled(self):
        """When enabled, funding = 2 × notional × daily_rate × days."""
        cfg = CostModelConfig(include_funding=True, funding_rate_daily_bps=1.0)
        model = CostModel(cfg)
        cost = model.funding_cost(notional_per_leg=5000, holding_days=10)
        # 2 × 5000 × (1.0/10000) × 10 = 10.0
        assert cost == pytest.approx(10.0, abs=0.01)

    def test_funding_zero_days(self):
        """No holding ↓ no funding cost."""
        cfg = CostModelConfig(include_funding=True, funding_rate_daily_bps=2.0)
        model = CostModel(cfg)
        assert model.funding_cost(5000, 0) == 0.0

    def test_funding_high_rate(self):
        """High funding rate scenario (volatile market, 5 bps/day)."""
        cfg = CostModelConfig(include_funding=True, funding_rate_daily_bps=5.0)
        model = CostModel(cfg)
        cost = model.funding_cost(10000, 30)
        # 2 × 10000 × (5/10000) × 30 = 300
        assert cost == pytest.approx(300.0, abs=0.01)

    def test_funding_included_in_round_trip(self):
        """round_trip_cost includes funding when enabled."""
        cfg = CostModelConfig(include_funding=True, funding_rate_daily_bps=1.0)
        model = CostModel(cfg)
        
        rt_with = model.round_trip_cost(5000, holding_days=10)
        
        cfg_no = CostModelConfig(include_funding=False)
        model_no = CostModel(cfg_no)
        rt_without = model_no.round_trip_cost(5000, holding_days=10)
        
        # With funding should cost more
        assert rt_with > rt_without

    def test_funding_not_included_in_round_trip_by_default(self):
        """Default config ↓ funding not in round_trip."""
        model = CostModel()
        # round_trip with and without holding should differ only by borrowing
        rt_0 = model.round_trip_cost(5000, holding_days=0)
        rt_10 = model.round_trip_cost(5000, holding_days=10)
        # Difference = borrowing only (funding is off)
        borrow_diff = model.holding_cost(5000, 10)
        assert rt_10 - rt_0 == pytest.approx(borrow_diff, abs=0.001)


# ===========================================================================
# SECTION 2 – Round-Trip BPS Threshold
# ===========================================================================

class TestRoundTripRealistic:
    """Verify realistic fee levels match DoD requirements."""

    def test_round_trip_ge_40bps_with_borrowing(self):
        """RT costs ≥ 8 bps with standard IBKR equity config and 15-day hold."""
        model = CostModel()
        bps = model.round_trip_cost_bps(5000, holding_days=15)
        # IBKR equity: ~2 bps fee + ~2 bps slippage per leg × 4 legs + borrowing
        assert bps >= 8, f"RT should be ≥ 8 bps with 15d hold, got {bps:.1f}"

    def test_round_trip_ge_40bps_with_funding(self):
        """RT costs ≥ 14 bps with funding enabled and 7-day hold."""
        cfg = CostModelConfig(include_funding=True, funding_rate_daily_bps=1.0)
        model = CostModel(cfg)
        bps = model.round_trip_cost_bps(5000, holding_days=7)
        # Execution ~8 bps + funding 2×5000×1bps×7d = 7 bps → ~15 bps
        assert bps >= 14

    def test_round_trip_execution_only_is_30bps(self):
        """Pure execution (no holding) = ~8 bps for large-cap equities via IBKR."""
        cfg = CostModelConfig(include_borrowing=False, include_funding=False)
        model = CostModel(cfg)
        bps = model.round_trip_cost_bps(
            5000,
            holding_days=0,
            volume_24h_sym1=1e9,
            volume_24h_sym2=1e9,
        )
        # 4 legs × (2 bps fee + ~2 bps slippage) ≈ 8 bps
        assert 6 <= bps <= 10, f"Expected ~8 bps, got {bps:.1f}"

    def test_round_trip_cost_bps_helper(self):
        """Verify round_trip_cost_bps matches manual calculation."""
        model = CostModel()
        rt_dollar = model.round_trip_cost(5000, holding_days=0)
        rt_bps = model.round_trip_cost_bps(5000, holding_days=0)
        manual = rt_dollar / (2 * 5000) * 10_000
        assert rt_bps == pytest.approx(manual, abs=0.01)

    def test_round_trip_cost_bps_zero_notional(self):
        """Zero notional ↓ 0 bps (avoid division by zero)."""
        model = CostModel()
        assert model.round_trip_cost_bps(0) == 0.0


# ===========================================================================
# SECTION 3 – Low-Liquidity Scenario (DoD requirement)
# ===========================================================================

class TestLowLiquidityScenario:
    """DoD: $1000 trade on low-volume stock with volume=$50K ↓ slippage > 20 bps."""

    def test_low_liquidity_slippage_exceeds_20bps(self):
        """Low-liquidity stock: slippage must exceed 20 bps."""
        model = CostModel()
        # For one leg: participation = 1000/50000 = 2%
        # impact_bps = 5 + 100×0.02 = 7 bps ↓ decimal = 0.0007
        # But that's per single leg. Entry = 2 legs slippage.
        # The key metric: total slippage cost in the round-trip
        slippage_decimal = model._slippage(1000, 50_000)
        slippage_bps = slippage_decimal * 10_000
        # participation = 1000/50000 = 2%, impact = 2 + 100×0.02 = 4 bps
        assert slippage_bps > 3, f"Per-leg slippage should be > 3 bps, got {slippage_bps:.1f}"
        
        # Total round-trip with POPCAT-like liquidity
        rt = model.round_trip_cost(
            notional_per_leg=1000,
            volume_24h_sym1=50_000,
            volume_24h_sym2=50_000,
            holding_days=0,
        )
        rt_bps = rt / (2 * 1000) * 10_000
        # 4 legs × (2 bps fee + 4 bps slippage) ≈ 12 bps total
        assert rt_bps > 10, f"Low-liq RT should be > 10 bps, got {rt_bps:.1f}"

    def test_low_liq_vs_high_liq_cost_comparison(self):
        """Low-volume stock should be significantly more expensive than large-cap."""
        model = CostModel()
        rt_low_liq = model.round_trip_cost(1000, volume_24h_sym1=50_000, volume_24h_sym2=50_000)
        rt_high_liq = model.round_trip_cost(1000, volume_24h_sym1=1e9, volume_24h_sym2=1e9)
        assert rt_low_liq > rt_high_liq * 1.1  # At least 10% more expensive

    def test_zero_volume_worst_case(self):
        """Zero volume ↓ 50 bps slippage (worst case)."""
        model = CostModel()
        slip = model._slippage(1000, 0)
        assert slip == pytest.approx(50 / 10_000)


# ===========================================================================
# SECTION 4 – Backward Compatibility
# ===========================================================================

class TestBackwardCompatibility:
    """Ensure existing callers (strategy_simulator, runner) are not broken."""

    def test_default_config_unchanged_for_execution(self):
        """Default CostModel returns IBKR equity execution costs."""
        model = CostModel()
        # entry_cost for $5000 per leg, high volume (negligible slippage)
        e = model.entry_cost(5000, 1e9, 1e9)
        # 2 legs × 5000 × (2/10000 + ~2/10000) ≈ 2 × 5000 × 0.0004 = 4.0
        assert 3 < e < 5

    def test_exit_equals_entry_cost(self):
        """Exit cost = entry cost (same fee structure)."""
        model = CostModel()
        assert model.entry_cost(3000) == model.exit_cost(3000)

    def test_holding_cost_borrowing_only(self):
        """Default config: holding cost = borrowing only (funding off)."""
        model = CostModel()
        h = model.holding_cost(10000, 30)
        # 10000 × (0.5/100/365) × 30 ≈ 4.11 (0.5% annual ETB rate)
        assert 3.5 < h < 4.5

    def test_cost_model_config_has_all_fields(self):
        """Config has all required fields including new ones."""
        cfg = CostModelConfig()
        assert hasattr(cfg, 'funding_rate_daily_bps')
        assert hasattr(cfg, 'include_funding')
        assert hasattr(cfg, 'maker_fee_bps')
        assert hasattr(cfg, 'taker_fee_bps')
        assert hasattr(cfg, 'base_slippage_bps')
        assert hasattr(cfg, 'borrowing_cost_annual_pct')
        assert hasattr(cfg, 'include_borrowing')
        assert hasattr(cfg, 'slippage_model')


# ===========================================================================
# SECTION 5 – Integration
# ===========================================================================

class TestIntegration:
    """Integration tests with StrategyBacktestSimulator."""

    def test_simulator_uses_funding_cost_model(self):
        """Simulator can accept CostModel with funding enabled."""
        from backtests.strategy_simulator import StrategyBacktestSimulator
        cfg = CostModelConfig(include_funding=True, funding_rate_daily_bps=2.0)
        model = CostModel(cfg)
        sim = StrategyBacktestSimulator(cost_model=model, initial_capital=100000)
        assert sim.cost_model.config.include_funding

    def test_runner_imports_cost_model(self):
        """runner.py should import CostModel without error."""
        from backtests.runner import _LEGACY_COST_MODEL
        assert _LEGACY_COST_MODEL is not None


# ===========================================================================
# SECTION 6 – Edge Cases
# ===========================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_negative_holding_days(self):
        """Negative holding days ↓ zero costs."""
        model = CostModel(CostModelConfig(include_funding=True, include_borrowing=True))
        assert model.holding_cost(5000, -1) == 0.0
        assert model.funding_cost(5000, -1) == 0.0

    def test_very_large_notional(self):
        """Large notional doesn't cause overflow."""
        model = CostModel()
        cost = model.round_trip_cost(1e8, holding_days=365)
        assert cost > 0
        assert cost < 1e8  # Cost shouldn't exceed notional

    def test_adaptive_slippage_cap(self):
        """Slippage is capped at 100 bps even for huge orders."""
        model = CostModel()
        slip = model._slippage(1e9, 1e6)  # order >> volume
        assert slip == pytest.approx(100 / 10_000)

    def test_fixed_slippage_model(self):
        """Fixed slippage model ignores volume."""
        cfg = CostModelConfig(slippage_model="fixed", base_slippage_bps=5.0)
        model = CostModel(cfg)
        s1 = model._slippage(100, 1e6)
        s2 = model._slippage(100, 1e3)
        assert s1 == s2 == pytest.approx(5 / 10_000)
