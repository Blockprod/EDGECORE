<<<<<<< HEAD
﻿"""
Sprint 2.3 ÔÇô Tests for extended cost model (M-03 fix).

Tests:
  - Funding rate calculation
  - Round-trip ÔëÑ 40 bps with realistic params
=======
"""
Sprint 2.3 – Tests for extended cost model (M-03 fix).

Tests:
  - Funding rate calculation
  - Round-trip ≥ 40 bps with realistic params
>>>>>>> origin/main
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
<<<<<<< HEAD

=======
>>>>>>> origin/main
    Settings._instance = None
    yield
    Settings._instance = None


# ===========================================================================
<<<<<<< HEAD
# SECTION 1 ÔÇô Funding Rate
# ===========================================================================


=======
# SECTION 1 – Funding Rate
# ===========================================================================

>>>>>>> origin/main
class TestFundingRate:
    """Tests for funding rate cost calculation."""

    def test_funding_disabled_by_default(self):
<<<<<<< HEAD
        """Funding is OFF by default ÔÇô cost should be zero."""
=======
        """Funding is OFF by default – cost should be zero."""
>>>>>>> origin/main
        model = CostModel()
        assert not model.config.include_funding
        assert model.funding_cost(5000, 7) == 0.0

    def test_funding_enabled(self):
<<<<<<< HEAD
        """When enabled, funding = 2 ├ù notional ├ù daily_rate ├ù days."""
        cfg = CostModelConfig(include_funding=True, funding_rate_daily_bps=1.0)
        model = CostModel(cfg)
        cost = model.funding_cost(notional_per_leg=5000, holding_days=10)
        # 2 ├ù 5000 ├ù (1.0/10000) ├ù 10 = 10.0
        assert cost == pytest.approx(10.0, abs=0.01)

    def test_funding_zero_days(self):
        """No holding Ôåô no funding cost."""
=======
        """When enabled, funding = 2 × notional × daily_rate × days."""
        cfg = CostModelConfig(include_funding=True, funding_rate_daily_bps=1.0)
        model = CostModel(cfg)
        cost = model.funding_cost(notional_per_leg=5000, holding_days=10)
        # 2 × 5000 × (1.0/10000) × 10 = 10.0
        assert cost == pytest.approx(10.0, abs=0.01)

    def test_funding_zero_days(self):
        """No holding ↓ no funding cost."""
>>>>>>> origin/main
        cfg = CostModelConfig(include_funding=True, funding_rate_daily_bps=2.0)
        model = CostModel(cfg)
        assert model.funding_cost(5000, 0) == 0.0

    def test_funding_high_rate(self):
        """High funding rate scenario (volatile market, 5 bps/day)."""
        cfg = CostModelConfig(include_funding=True, funding_rate_daily_bps=5.0)
        model = CostModel(cfg)
        cost = model.funding_cost(10000, 30)
<<<<<<< HEAD
        # 2 ├ù 10000 ├ù (5/10000) ├ù 30 = 300
=======
        # 2 × 10000 × (5/10000) × 30 = 300
>>>>>>> origin/main
        assert cost == pytest.approx(300.0, abs=0.01)

    def test_funding_included_in_round_trip(self):
        """round_trip_cost includes funding when enabled."""
        cfg = CostModelConfig(include_funding=True, funding_rate_daily_bps=1.0)
        model = CostModel(cfg)
<<<<<<< HEAD

        rt_with = model.round_trip_cost(5000, holding_days=10)

        cfg_no = CostModelConfig(include_funding=False)
        model_no = CostModel(cfg_no)
        rt_without = model_no.round_trip_cost(5000, holding_days=10)

=======
        
        rt_with = model.round_trip_cost(5000, holding_days=10)
        
        cfg_no = CostModelConfig(include_funding=False)
        model_no = CostModel(cfg_no)
        rt_without = model_no.round_trip_cost(5000, holding_days=10)
        
>>>>>>> origin/main
        # With funding should cost more
        assert rt_with > rt_without

    def test_funding_not_included_in_round_trip_by_default(self):
<<<<<<< HEAD
        """Default config Ôåô funding not in round_trip."""
=======
        """Default config ↓ funding not in round_trip."""
>>>>>>> origin/main
        model = CostModel()
        # round_trip with and without holding should differ only by borrowing
        rt_0 = model.round_trip_cost(5000, holding_days=0)
        rt_10 = model.round_trip_cost(5000, holding_days=10)
        # Difference = borrowing only (funding is off)
        borrow_diff = model.holding_cost(5000, 10)
        assert rt_10 - rt_0 == pytest.approx(borrow_diff, abs=0.001)


# ===========================================================================
<<<<<<< HEAD
# SECTION 2 ÔÇô Round-Trip BPS Threshold
# ===========================================================================


=======
# SECTION 2 – Round-Trip BPS Threshold
# ===========================================================================

>>>>>>> origin/main
class TestRoundTripRealistic:
    """Verify realistic fee levels match DoD requirements."""

    def test_round_trip_ge_40bps_with_borrowing(self):
<<<<<<< HEAD
        """RT costs ÔëÑ 8 bps with standard IBKR equity config and 15-day hold."""
        model = CostModel()
        bps = model.round_trip_cost_bps(5000, holding_days=15)
        # IBKR equity: ~2 bps fee + ~2 bps slippage per leg ├ù 4 legs + borrowing
        assert bps >= 8, f"RT should be ÔëÑ 8 bps with 15d hold, got {bps:.1f}"

    def test_round_trip_ge_40bps_with_funding(self):
        """RT costs ÔëÑ 14 bps with funding enabled and 7-day hold."""
        cfg = CostModelConfig(include_funding=True, funding_rate_daily_bps=1.0)
        model = CostModel(cfg)
        bps = model.round_trip_cost_bps(5000, holding_days=7)
        # Execution ~8 bps + funding 2├ù5000├ù1bps├ù7d = 7 bps ÔåÆ ~15 bps
=======
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
>>>>>>> origin/main
        assert bps >= 14

    def test_round_trip_execution_only_is_30bps(self):
        """Pure execution (no holding) with Almgren-Chriss 3-component model.

<<<<<<< HEAD
        Components per leg (calibrated v32j defaults: ╬À=0.05, delay=0.01):
          - Fee: 2 bps
          - Spread (bid-ask): 2 bps
          - Market impact: ╬À├ù¤â├ùÔêÜ(Q/ADV) Ôëê negligible at $5K/$1B
          - Timing cost: ¤â├ùÔêÜ(T/252) Ôëê 1.3 bps (¤â=2%, T=0.01 day)
        Round trip = 4 legs ├ù ~5.3 bps Ôëê 11 bps
=======
        Components per leg (calibrated v32j defaults: η=0.05, delay=0.01):
          - Fee: 2 bps
          - Spread (bid-ask): 2 bps
          - Market impact: η×σ×√(Q/ADV) ≈ negligible at $5K/$1B
          - Timing cost: σ×√(T/252) ≈ 1.3 bps (σ=2%, T=0.01 day)
        Round trip = 4 legs × ~5.3 bps ≈ 11 bps
>>>>>>> origin/main
        """
        cfg = CostModelConfig(include_borrowing=False, include_funding=False)
        model = CostModel(cfg)
        bps = model.round_trip_cost_bps(
            5000,
            holding_days=0,
            volume_24h_sym1=1e9,
            volume_24h_sym2=1e9,
        )
<<<<<<< HEAD
        # Almgren-Chriss with calibrated v32j defaults (╬À=0.05, delay=0.01)
=======
        # Almgren-Chriss with calibrated v32j defaults (η=0.05, delay=0.01)
>>>>>>> origin/main
        assert 8 <= bps <= 18, f"Expected ~11 bps (Almgren-Chriss v32j), got {bps:.1f}"

    def test_round_trip_cost_bps_helper(self):
        """Verify round_trip_cost_bps matches manual calculation."""
        model = CostModel()
        rt_dollar = model.round_trip_cost(5000, holding_days=0)
        rt_bps = model.round_trip_cost_bps(5000, holding_days=0)
        manual = rt_dollar / (2 * 5000) * 10_000
        assert rt_bps == pytest.approx(manual, abs=0.01)

    def test_round_trip_cost_bps_zero_notional(self):
<<<<<<< HEAD
        """Zero notional Ôåô 0 bps (avoid division by zero)."""
=======
        """Zero notional ↓ 0 bps (avoid division by zero)."""
>>>>>>> origin/main
        model = CostModel()
        assert model.round_trip_cost_bps(0) == 0.0


# ===========================================================================
<<<<<<< HEAD
# SECTION 3 ÔÇô Low-Liquidity Scenario (DoD requirement)
# ===========================================================================


class TestLowLiquidityScenario:
    """DoD: $1000 trade on low-volume stock with volume=$50K Ôåô slippage > 20 bps."""
=======
# SECTION 3 – Low-Liquidity Scenario (DoD requirement)
# ===========================================================================

class TestLowLiquidityScenario:
    """DoD: $1000 trade on low-volume stock with volume=$50K ↓ slippage > 20 bps."""
>>>>>>> origin/main

    def test_low_liquidity_slippage_exceeds_20bps(self):
        """Low-liquidity stock: slippage must exceed 20 bps."""
        model = CostModel()
        # For one leg: participation = 1000/50000 = 2%
<<<<<<< HEAD
        # impact_bps = 5 + 100├ù0.02 = 7 bps Ôåô decimal = 0.0007
=======
        # impact_bps = 5 + 100×0.02 = 7 bps ↓ decimal = 0.0007
>>>>>>> origin/main
        # But that's per single leg. Entry = 2 legs slippage.
        # The key metric: total slippage cost in the round-trip
        slippage_decimal = model._slippage(1000, 50_000)
        slippage_bps = slippage_decimal * 10_000
<<<<<<< HEAD
        # participation = 1000/50000 = 2%, impact = 2 + 100├ù0.02 = 4 bps
        assert slippage_bps > 3, f"Per-leg slippage should be > 3 bps, got {slippage_bps:.1f}"

=======
        # participation = 1000/50000 = 2%, impact = 2 + 100×0.02 = 4 bps
        assert slippage_bps > 3, f"Per-leg slippage should be > 3 bps, got {slippage_bps:.1f}"
        
>>>>>>> origin/main
        # Total round-trip with POPCAT-like liquidity
        rt = model.round_trip_cost(
            notional_per_leg=1000,
            volume_24h_sym1=50_000,
            volume_24h_sym2=50_000,
            holding_days=0,
        )
        rt_bps = rt / (2 * 1000) * 10_000
<<<<<<< HEAD
        # 4 legs ├ù (2 bps fee + 4 bps slippage) Ôëê 12 bps total
=======
        # 4 legs × (2 bps fee + 4 bps slippage) ≈ 12 bps total
>>>>>>> origin/main
        assert rt_bps > 10, f"Low-liq RT should be > 10 bps, got {rt_bps:.1f}"

    def test_low_liq_vs_high_liq_cost_comparison(self):
        """Low-volume stock should be significantly more expensive than large-cap."""
        model = CostModel()
        rt_low_liq = model.round_trip_cost(1000, volume_24h_sym1=50_000, volume_24h_sym2=50_000)
        rt_high_liq = model.round_trip_cost(1000, volume_24h_sym1=1e9, volume_24h_sym2=1e9)
        assert rt_low_liq > rt_high_liq * 1.1  # At least 10% more expensive

    def test_zero_volume_worst_case(self):
<<<<<<< HEAD
        """Zero volume Ôåô 50 bps slippage (worst case)."""
=======
        """Zero volume ↓ 50 bps slippage (worst case)."""
>>>>>>> origin/main
        model = CostModel()
        slip = model._slippage(1000, 0)
        assert slip == pytest.approx(50 / 10_000)


# ===========================================================================
<<<<<<< HEAD
# SECTION 4 ÔÇô Backward Compatibility
# ===========================================================================


=======
# SECTION 4 – Backward Compatibility
# ===========================================================================

>>>>>>> origin/main
class TestBackwardCompatibility:
    """Ensure existing callers (strategy_simulator, runner) are not broken."""

    def test_default_config_unchanged_for_execution(self):
        """Default CostModel (Almgren-Chriss) returns realistic equity execution costs.

<<<<<<< HEAD
        With calibrated v32j defaults (¤â_default=2%, T_exec=0.01d, ╬À=0.05):
          Per leg: $5000 ├ù (fee 2bps + spread 2bps + timing ~1.3bps + impact ~0bps)
          = $5000 ├ù ~0.00053 Ôëê $2.64 per leg
          2 legs Ôëê $5.3
=======
        With calibrated v32j defaults (σ_default=2%, T_exec=0.01d, η=0.05):
          Per leg: $5000 × (fee 2bps + spread 2bps + timing ~1.3bps + impact ~0bps)
          = $5000 × ~0.00053 ≈ $2.64 per leg
          2 legs ≈ $5.3
>>>>>>> origin/main
        """
        model = CostModel()
        # entry_cost for $5000 per leg, high volume (negligible market impact)
        e = model.entry_cost(5000, 1e9, 1e9)
<<<<<<< HEAD
        # Almgren-Chriss with calibrated v32j params ÔåÆ ~$5.3
=======
        # Almgren-Chriss with calibrated v32j params → ~$5.3
>>>>>>> origin/main
        assert 3 < e < 9

    def test_exit_equals_entry_cost(self):
        """Exit cost = entry cost (same fee structure)."""
        model = CostModel()
        assert model.entry_cost(3000) == model.exit_cost(3000)

    def test_holding_cost_borrowing_only(self):
        """Default config: holding cost = borrowing only (funding off)."""
        model = CostModel()
        h = model.holding_cost(10000, 30)
<<<<<<< HEAD
        # 10000 ├ù (0.5/100/365) ├ù 30 Ôëê 4.11 (0.5% annual ETB rate)
=======
        # 10000 × (0.5/100/365) × 30 ≈ 4.11 (0.5% annual ETB rate)
>>>>>>> origin/main
        assert 3.5 < h < 4.5

    def test_cost_model_config_has_all_fields(self):
        """Config has all required fields including new ones."""
        cfg = CostModelConfig()
<<<<<<< HEAD
        assert hasattr(cfg, "funding_rate_daily_bps")
        assert hasattr(cfg, "include_funding")
        assert hasattr(cfg, "maker_fee_bps")
        assert hasattr(cfg, "taker_fee_bps")
        assert hasattr(cfg, "base_slippage_bps")
        assert hasattr(cfg, "borrowing_cost_annual_pct")
        assert hasattr(cfg, "include_borrowing")
        assert hasattr(cfg, "slippage_model")
        assert hasattr(cfg, "htb_symbols")
        assert isinstance(cfg.htb_symbols, dict)


# ===========================================================================
# SECTION 5 ÔÇô Integration
# ===========================================================================


=======
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

>>>>>>> origin/main
class TestIntegration:
    """Integration tests with StrategyBacktestSimulator."""

    def test_simulator_uses_funding_cost_model(self):
        """Simulator can accept CostModel with funding enabled."""
        from backtests.strategy_simulator import StrategyBacktestSimulator
<<<<<<< HEAD

=======
>>>>>>> origin/main
        cfg = CostModelConfig(include_funding=True, funding_rate_daily_bps=2.0)
        model = CostModel(cfg)
        sim = StrategyBacktestSimulator(cost_model=model, initial_capital=100000)
        assert sim.cost_model.config.include_funding

    def test_runner_imports_cost_model(self):
        """runner.py should import CostModel without error."""
        from backtests.runner import _LEGACY_COST_MODEL
<<<<<<< HEAD

=======
>>>>>>> origin/main
        assert _LEGACY_COST_MODEL is not None


# ===========================================================================
<<<<<<< HEAD
# SECTION 6 ÔÇô Edge Cases
# ===========================================================================


=======
# SECTION 6 – Edge Cases
# ===========================================================================

>>>>>>> origin/main
class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_negative_holding_days(self):
<<<<<<< HEAD
        """Negative holding days Ôåô zero costs."""
=======
        """Negative holding days ↓ zero costs."""
>>>>>>> origin/main
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
<<<<<<< HEAD


# ===========================================================================
# SECTION 7 — HTB Premium Cost Model (C-05)
# ===========================================================================


class TestHTBPremium:
    """Hard-to-borrow (HTB) per-symbol borrow rate overrides."""

    def test_default_htb_symbols_is_empty(self):
        """Default config has no HTB overrides (backward compat)."""
        cfg = CostModelConfig()
        assert cfg.htb_symbols == {}

    def test_gc_rate_when_symbol_not_in_htb(self):
        """Unknown symbol → falls back to borrowing_cost_annual_pct (GC rate)."""
        cfg = CostModelConfig(borrowing_cost_annual_pct=0.5)
        model = CostModel(cfg)
        cost_named = model.holding_cost(10_000, 30, symbol="AAPL")
        cost_unnamed = model.holding_cost(10_000, 30)
        assert cost_named == pytest.approx(cost_unnamed, rel=1e-9)

    def test_htb_rate_applied_for_known_symbol(self):
        """HTB symbol uses its own annual rate, not the GC fallback."""
        cfg = CostModelConfig(
            borrowing_cost_annual_pct=0.5,  # 0.5% GC
            htb_symbols={"GME": 25.0},  # 25% HTB
        )
        model = CostModel(cfg)
        gc_cost = model.holding_cost(10_000, 365, symbol="AAPL")
        htb_cost = model.holding_cost(10_000, 365, symbol="GME")
        # GME should cost approx 50× more than GC rate
        assert htb_cost == pytest.approx(10_000 * 25.0 / 100.0, rel=0.01)
        assert htb_cost > gc_cost * 40

    def test_htb_symbol_lookup_is_case_insensitive(self):
        """Lowercase symbol should match uppercase key in htb_symbols."""
        cfg = CostModelConfig(htb_symbols={"GME": 25.0})
        model = CostModel(cfg)
        cost_upper = model.holding_cost(10_000, 30, symbol="GME")
        cost_lower = model.holding_cost(10_000, 30, symbol="gme")
        assert cost_upper == pytest.approx(cost_lower, rel=1e-9)

    def test_round_trip_cost_with_htb_short_symbol(self):
        """round_trip_cost propagates short_symbol to holding_cost."""
        cfg = CostModelConfig(htb_symbols={"GME": 25.0})
        model = CostModel(cfg)
        rt_htb = model.round_trip_cost(5_000, holding_days=30, short_symbol="GME")
        rt_gc = model.round_trip_cost(5_000, holding_days=30)
        assert rt_htb > rt_gc

    def test_from_htb_csv(self, tmp_path):
        """CostModelConfig.from_htb_csv() loads rates from a well-formed CSV."""
        csv_file = tmp_path / "htb.csv"
        csv_file.write_text("symbol,annual_borrow_pct\nGME,25.0\nAMC,18.5\n")
        cfg = CostModelConfig.from_htb_csv(csv_file)
        assert cfg.htb_symbols == {"GME": 25.0, "AMC": 18.5}

    def test_from_htb_csv_headerless(self, tmp_path):
        """from_htb_csv() works even without a header row."""
        csv_file = tmp_path / "htb_no_header.csv"
        csv_file.write_text("GME,25.0\nAMC,18.5\n")
        cfg = CostModelConfig.from_htb_csv(csv_file)
        assert "GME" in cfg.htb_symbols
        assert "AMC" in cfg.htb_symbols

    def test_from_htb_csv_skips_malformed_rows(self, tmp_path):
        """Rows with non-numeric rates are silently skipped."""
        csv_file = tmp_path / "htb_bad.csv"
        csv_file.write_text("GME,25.0\nBAD,not_a_number\nAMC,18.5\n")
        cfg = CostModelConfig.from_htb_csv(csv_file)
        assert "BAD" not in cfg.htb_symbols
        assert len(cfg.htb_symbols) == 2

    def test_from_htb_csv_with_real_seed_file(self):
        """data/htb_rates.csv seed file loads without error."""
        from pathlib import Path

        import pytest

        seed = Path(__file__).parent.parent.parent / "data" / "htb_rates.csv"
        if not seed.exists():
            pytest.skip("data/htb_rates.csv absent (gitignored — local only)")
        cfg = CostModelConfig.from_htb_csv(seed)
        assert len(cfg.htb_symbols) >= 10
        # GME is always the canonical HTB example
        assert "GME" in cfg.htb_symbols
        assert cfg.htb_symbols["GME"] > 10.0  # Much higher than GC rate


# ===========================================================================
# SECTION 8 — Real ADV injection (C-06)
# ===========================================================================


class TestRealADV:
    """CostModelConfig.default_adv_usd fallback and ADV injection into simulator."""

    def test_default_adv_usd_field_exists(self):
        """CostModelConfig has default_adv_usd with a sensible conservative default."""
        cfg = CostModelConfig()
        assert hasattr(cfg, "default_adv_usd")
        assert cfg.default_adv_usd == 10_000_000.0

    def test_custom_default_adv_usd(self):
        """Caller can override default_adv_usd (e.g. for mid-cap universe)."""
        cfg = CostModelConfig(default_adv_usd=5_000_000.0)
        assert cfg.default_adv_usd == 5_000_000.0

    def test_simulator_accepts_adv_by_symbol(self):
        """StrategyBacktestSimulator accepts adv_by_symbol without error."""
        from backtests.strategy_simulator import StrategyBacktestSimulator

        adv = {"AAPL": 500_000_000.0, "MSFT": 400_000_000.0}
        sim = StrategyBacktestSimulator(adv_by_symbol=adv)
        assert sim.adv_by_symbol == adv

    def test_simulator_default_adv_by_symbol_is_empty(self):
        """Default adv_by_symbol is an empty dict (backward compat)."""
        from backtests.strategy_simulator import StrategyBacktestSimulator

        sim = StrategyBacktestSimulator()
        assert sim.adv_by_symbol == {}

    def test_estimate_adv_uses_injected_value(self):
        """_estimate_adv() returns injected ADV when symbol is present."""
        import pandas as pd

        from backtests.strategy_simulator import StrategyBacktestSimulator

        sim = StrategyBacktestSimulator(adv_by_symbol={"XYZ": 8_000_000.0})
        dummy_df = pd.DataFrame({"XYZ": [100.0, 101.0]})
        result = sim._estimate_adv("XYZ", dummy_df, notional_per_leg=5_000)
        assert result == 8_000_000.0

    def test_estimate_adv_falls_back_to_tier_for_unknown_symbol(self):
        """_estimate_adv() falls back to tier table when symbol not in adv_by_symbol."""
        import pandas as pd

        from backtests.strategy_simulator import StrategyBacktestSimulator

        sim = StrategyBacktestSimulator(adv_by_symbol={})
        dummy_df = pd.DataFrame({"SO": [50.0, 51.0]})
        # SO is not in _MEGA_CAP_SYMBOLS → large-cap tier
        result = sim._estimate_adv("SO", dummy_df, notional_per_leg=5_000)
        assert result == StrategyBacktestSimulator._ADV_LARGE_CAP

    def test_estimate_adv_mega_cap_tier_without_injection(self):
        """Mega-cap symbols use _ADV_MEGA_CAP when not overridden."""
        import pandas as pd

        from backtests.strategy_simulator import StrategyBacktestSimulator

        sim = StrategyBacktestSimulator()
        dummy_df = pd.DataFrame({"AAPL": [170.0, 171.0]})
        result = sim._estimate_adv("AAPL", dummy_df, 5_000)
        assert result == StrategyBacktestSimulator._ADV_MEGA_CAP

    def test_estimate_adv_symbol_lookup_case_insensitive(self):
        """adv_by_symbol lookup normalises symbol to uppercase."""
        import pandas as pd

        from backtests.strategy_simulator import StrategyBacktestSimulator

        sim = StrategyBacktestSimulator(adv_by_symbol={"NVDA": 700_000_000.0})
        dummy_df = pd.DataFrame({"nvda": [800.0]})
        result = sim._estimate_adv("nvda", dummy_df, 5_000)
        assert result == 700_000_000.0

    def test_injected_adv_overrides_mega_cap_tier(self):
        """Injected ADV takes precedence even for mega-cap symbols."""
        import pandas as pd

        from backtests.strategy_simulator import StrategyBacktestSimulator

        custom_adv = 1_000_000.0  # much smaller than tier default
        sim = StrategyBacktestSimulator(adv_by_symbol={"AAPL": custom_adv})
        dummy_df = pd.DataFrame({"AAPL": [170.0]})
        result = sim._estimate_adv("AAPL", dummy_df, 5_000)
        assert result == custom_adv
=======
>>>>>>> origin/main
