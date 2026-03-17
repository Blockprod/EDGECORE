"""
Tests for Directional Bias & Adaptive Regime Gate.

Etape 4 (legacy): short sizing reduction in bull trend.
v30 (adaptive): per-side regime gate using long_sizing / short_sizing.

This module validates:
  1. Config fields exist with correct defaults
  2. Schema validates short_sizing_multiplier in [0, 1]
  3. Legacy: short sizing bias in TRENDING/NEUTRAL regimes
  4. Legacy: shorts blocked when disable_shorts_in_bull_trend = True + TRENDING
  5. Longs are unaffected in all regimes
  6. MEAN_REVERTING regime leaves shorts unchanged
  7. v30: adaptive per-side gate (BULL_TRENDING, BEAR_TRENDING, NEUTRAL)
"""

import pytest


# ÔöÇÔöÇ 1. Config defaults ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

class TestDirectionalBiasConfigDefaults:
    """Verify StrategyConfig has the new fields with correct defaults."""

    def test_short_sizing_multiplier_default(self):
        from config.settings import StrategyConfig
        cfg = StrategyConfig()
        assert cfg.short_sizing_multiplier == 0.50

    def test_disable_shorts_default_false(self):
        from config.settings import StrategyConfig
        cfg = StrategyConfig()
        assert cfg.disable_shorts_in_bull_trend is False

    def test_short_sizing_multiplier_custom(self):
        from config.settings import StrategyConfig
        cfg = StrategyConfig(short_sizing_multiplier=0.25)
        assert cfg.short_sizing_multiplier == 0.25

    def test_disable_shorts_custom(self):
        from config.settings import StrategyConfig
        cfg = StrategyConfig(disable_shorts_in_bull_trend=True)
        assert cfg.disable_shorts_in_bull_trend is True


# ÔöÇÔöÇ 2. YAML has the parameters ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

class TestDirectionalBiasYAML:
    """Verify config.yaml and dev.yaml contain the new parameters."""

    def test_config_yaml_has_short_sizing(self):
        import yaml
        from pathlib import Path
        p = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
        with open(p, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        assert cfg["strategy"]["short_sizing_multiplier"] == 0.50

    def test_config_yaml_has_disable_shorts(self):
        import yaml
        from pathlib import Path
        p = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
        with open(p, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        assert cfg["strategy"]["disable_shorts_in_bull_trend"] is False

    def test_dev_yaml_has_short_sizing(self):
        import yaml
        from pathlib import Path
        p = Path(__file__).resolve().parents[1] / "config" / "dev.yaml"
        with open(p, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        assert cfg["strategy"]["short_sizing_multiplier"] == 0.50

    def test_dev_yaml_has_disable_shorts(self):
        import yaml
        from pathlib import Path
        p = Path(__file__).resolve().parents[1] / "config" / "dev.yaml"
        with open(p, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        assert cfg["strategy"]["disable_shorts_in_bull_trend"] is False


# ÔöÇÔöÇ 3. Schema validation ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

class TestDirectionalBiasSchema:
    """Verify Pydantic schema validates short_sizing_multiplier."""

    def test_valid_multiplier(self):
        from config.schemas import StrategyConfigSchema
        s = StrategyConfigSchema(
            entry_z_score=2.0, exit_z_score=0.5,
            short_sizing_multiplier=0.50,
        )
        assert s.short_sizing_multiplier == 0.50

    def test_multiplier_zero_valid(self):
        """0.0 means block all shorts ÔÇö valid."""
        from config.schemas import StrategyConfigSchema
        s = StrategyConfigSchema(
            entry_z_score=2.0, exit_z_score=0.5,
            short_sizing_multiplier=0.0,
        )
        assert s.short_sizing_multiplier == 0.0

    def test_multiplier_one_valid(self):
        """1.0 means full sizing ÔÇö valid."""
        from config.schemas import StrategyConfigSchema
        s = StrategyConfigSchema(
            entry_z_score=2.0, exit_z_score=0.5,
            short_sizing_multiplier=1.0,
        )
        assert s.short_sizing_multiplier == 1.0

    def test_multiplier_above_one_rejected(self):
        from config.schemas import StrategyConfigSchema
        with pytest.raises(Exception):
            StrategyConfigSchema(
                entry_z_score=2.0, exit_z_score=0.5,
                short_sizing_multiplier=1.5,
            )

    def test_multiplier_negative_rejected(self):
        from config.schemas import StrategyConfigSchema
        with pytest.raises(Exception):
            StrategyConfigSchema(
                entry_z_score=2.0, exit_z_score=0.5,
                short_sizing_multiplier=-0.1,
            )


# ÔöÇÔöÇ 4. Simulator directional bias logic ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

class TestSimulatorShortSizing:
    """
    Test the directional bias logic in isolation.
    We test the allocation adjustment math without running the full simulator.
    """

    def test_short_in_trending_gets_reduced(self):
        """Short signal in TRENDING regime ÔåÆ alloc ├ù short_sizing_multiplier."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        base_alloc = 10.0  # 10% allocation
        short_mult = 0.50
        regime_state = MarketRegimeState(
            regime=MarketRegime.TRENDING,
            ma_fast=450.0, ma_slow=400.0,
            ma_spread_pct=0.125,
            realized_vol=0.12,
            vol_threshold=0.18,
            sizing_multiplier=0.0,  # TRENDING blocks via regime gate
        )

        # Simulate the bias logic (from simulator)
        signal_side = "short"
        adjusted_alloc = base_alloc
        if signal_side == "short" and regime_state is not None:
            if regime_state.regime in (MarketRegime.TRENDING, MarketRegime.NEUTRAL):
                adjusted_alloc *= short_mult

        assert adjusted_alloc == pytest.approx(5.0)

    def test_short_in_neutral_gets_reduced(self):
        """Short signal in NEUTRAL regime ÔåÆ alloc ├ù short_sizing_multiplier."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        base_alloc = 10.0
        short_mult = 0.50
        regime_state = MarketRegimeState(
            regime=MarketRegime.NEUTRAL,
            ma_fast=410.0, ma_slow=405.0,
            ma_spread_pct=0.012,
            realized_vol=0.15,
            vol_threshold=0.18,
            sizing_multiplier=0.5,
        )

        signal_side = "short"
        adjusted_alloc = base_alloc
        if signal_side == "short" and regime_state is not None:
            if regime_state.regime in (MarketRegime.TRENDING, MarketRegime.NEUTRAL):
                adjusted_alloc *= short_mult

        assert adjusted_alloc == pytest.approx(5.0)

    def test_short_in_mean_reverting_unchanged(self):
        """Short signal in MEAN_REVERTING ÔåÆ no adjustment."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        base_alloc = 10.0
        short_mult = 0.50
        regime_state = MarketRegimeState(
            regime=MarketRegime.MEAN_REVERTING,
            ma_fast=380.0, ma_slow=400.0,
            ma_spread_pct=-0.05,
            realized_vol=0.25,
            vol_threshold=0.18,
            sizing_multiplier=1.0,
        )

        signal_side = "short"
        adjusted_alloc = base_alloc
        if signal_side == "short" and regime_state is not None:
            if regime_state.regime in (MarketRegime.TRENDING, MarketRegime.NEUTRAL):
                adjusted_alloc *= short_mult

        assert adjusted_alloc == pytest.approx(10.0)  # Unchanged

    def test_long_in_trending_unchanged(self):
        """Long signal in TRENDING ÔåÆ no directional bias applied."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        base_alloc = 10.0
        short_mult = 0.50
        regime_state = MarketRegimeState(
            regime=MarketRegime.TRENDING,
            ma_fast=450.0, ma_slow=400.0,
            ma_spread_pct=0.125,
            realized_vol=0.12,
            vol_threshold=0.18,
            sizing_multiplier=0.0,
        )

        signal_side = "long"
        adjusted_alloc = base_alloc
        if signal_side == "short" and regime_state is not None:
            if regime_state.regime in (MarketRegime.TRENDING, MarketRegime.NEUTRAL):
                adjusted_alloc *= short_mult

        assert adjusted_alloc == pytest.approx(10.0)  # Unchanged

    def test_long_in_neutral_unchanged(self):
        """Long signal in NEUTRAL ÔåÆ no directional bias applied."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        base_alloc = 10.0
        short_mult = 0.50
        regime_state = MarketRegimeState(
            regime=MarketRegime.NEUTRAL,
            ma_fast=410.0, ma_slow=405.0,
            ma_spread_pct=0.012,
            realized_vol=0.15,
            vol_threshold=0.18,
            sizing_multiplier=0.5,
        )

        signal_side = "long"
        adjusted_alloc = base_alloc
        if signal_side == "short" and regime_state is not None:
            if regime_state.regime in (MarketRegime.TRENDING, MarketRegime.NEUTRAL):
                adjusted_alloc *= short_mult

        assert adjusted_alloc == pytest.approx(10.0)  # Unchanged


class TestDisableShortsInBullTrend:
    """Test the disable_shorts_in_bull_trend flag."""

    def test_disable_shorts_blocks_in_trending(self):
        """When disable=True and TRENDING ÔåÆ short should be skipped (continue)."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        regime_state = MarketRegimeState(
            regime=MarketRegime.TRENDING,
            ma_fast=450.0, ma_slow=400.0,
            ma_spread_pct=0.125,
            realized_vol=0.12,
            vol_threshold=0.18,
            sizing_multiplier=0.0,
        )

        disable_shorts = True
        signal_side = "short"
        blocked = False

        if signal_side == "short" and regime_state is not None:
            if regime_state.regime in (MarketRegime.TRENDING, MarketRegime.NEUTRAL):
                if disable_shorts and regime_state.regime == MarketRegime.TRENDING:
                    blocked = True

        assert blocked is True

    def test_disable_shorts_allows_in_neutral(self):
        """When disable=True but NEUTRAL ÔåÆ short should NOT be blocked (only reduced)."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        regime_state = MarketRegimeState(
            regime=MarketRegime.NEUTRAL,
            ma_fast=410.0, ma_slow=405.0,
            ma_spread_pct=0.012,
            realized_vol=0.15,
            vol_threshold=0.18,
            sizing_multiplier=0.5,
        )

        disable_shorts = True
        signal_side = "short"
        blocked = False

        if signal_side == "short" and regime_state is not None:
            if regime_state.regime in (MarketRegime.TRENDING, MarketRegime.NEUTRAL):
                if disable_shorts and regime_state.regime == MarketRegime.TRENDING:
                    blocked = True

        assert blocked is False

    def test_disable_shorts_false_allows_in_trending(self):
        """When disable=False and TRENDING ÔåÆ short should NOT be blocked (only reduced)."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        regime_state = MarketRegimeState(
            regime=MarketRegime.TRENDING,
            ma_fast=450.0, ma_slow=400.0,
            ma_spread_pct=0.125,
            realized_vol=0.12,
            vol_threshold=0.18,
            sizing_multiplier=0.0,
        )

        disable_shorts = False
        signal_side = "short"
        blocked = False

        if signal_side == "short" and regime_state is not None:
            if regime_state.regime in (MarketRegime.TRENDING, MarketRegime.NEUTRAL):
                if disable_shorts and regime_state.regime == MarketRegime.TRENDING:
                    blocked = True

        assert blocked is False


# ÔöÇÔöÇ 5. Custom multiplier values ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

class TestCustomMultiplierValues:
    """Test edge cases for different multiplier values."""

    def test_multiplier_zero_blocks_shorts(self):
        """short_sizing_multiplier=0.0 ÔåÆ alloc becomes 0."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        base_alloc = 10.0
        short_mult = 0.0
        regime_state = MarketRegimeState(
            regime=MarketRegime.NEUTRAL,
            ma_fast=410.0, ma_slow=405.0,
            ma_spread_pct=0.012,
            realized_vol=0.15,
            vol_threshold=0.18,
            sizing_multiplier=0.5,
        )

        signal_side = "short"
        adjusted_alloc = base_alloc
        if signal_side == "short" and regime_state is not None:
            if regime_state.regime in (MarketRegime.TRENDING, MarketRegime.NEUTRAL):
                adjusted_alloc *= short_mult

        assert adjusted_alloc == pytest.approx(0.0)

    def test_multiplier_one_no_reduction(self):
        """short_sizing_multiplier=1.0 ÔåÆ no reduction at all."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        base_alloc = 10.0
        short_mult = 1.0
        regime_state = MarketRegimeState(
            regime=MarketRegime.NEUTRAL,
            ma_fast=410.0, ma_slow=405.0,
            ma_spread_pct=0.012,
            realized_vol=0.15,
            vol_threshold=0.18,
            sizing_multiplier=0.5,
        )

        signal_side = "short"
        adjusted_alloc = base_alloc
        if signal_side == "short" and regime_state is not None:
            if regime_state.regime in (MarketRegime.TRENDING, MarketRegime.NEUTRAL):
                adjusted_alloc *= short_mult

        assert adjusted_alloc == pytest.approx(10.0)


# ÔöÇÔöÇ 6. Settings singleton loads the params ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

class TestSettingsLoadsDirectionalBias:
    """Verify Settings singleton loads the directional bias params."""

    def test_settings_has_short_sizing_multiplier(self):
        from config.settings import Settings
        Settings._instance = None
        s = Settings()
        assert hasattr(s.strategy, 'short_sizing_multiplier')
        assert 0.0 <= s.strategy.short_sizing_multiplier <= 1.0
        Settings._instance = None

    def test_settings_has_disable_shorts(self):
        from config.settings import Settings
        Settings._instance = None
        s = Settings()
        assert hasattr(s.strategy, 'disable_shorts_in_bull_trend')
        assert isinstance(s.strategy.disable_shorts_in_bull_trend, bool)
        Settings._instance = None


# ÔöÇÔöÇ 7. v30 Adaptive Per-Side Regime Gate ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

class TestAdaptiveRegimeGate:
    """
    Test the v30 adaptive per-side regime gate logic.
    The simulator now uses long_sizing / short_sizing from MarketRegimeState
    to gate entries by side.
    """

    def test_bull_trending_blocks_short(self):
        """In BULL_TRENDING: short_sizing=0 -> short entry blocked."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        state = MarketRegimeState(
            regime=MarketRegime.BULL_TRENDING,
            ma_fast=450.0, ma_slow=400.0,
            ma_spread_pct=0.125,
            realized_vol=0.12,
            vol_threshold=0.18,
            sizing_multiplier=0.0,
            long_sizing=0.80,
            short_sizing=0.0,
        )

        signal_side = "short"
        side_sizing = state.long_sizing if signal_side == "long" else state.short_sizing
        blocked = side_sizing <= 0.0
        assert blocked is True

    def test_bull_trending_allows_long(self):
        """In BULL_TRENDING: long_sizing=0.80 -> long entry allowed."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        state = MarketRegimeState(
            regime=MarketRegime.BULL_TRENDING,
            ma_fast=450.0, ma_slow=400.0,
            ma_spread_pct=0.125,
            realized_vol=0.12,
            vol_threshold=0.18,
            sizing_multiplier=0.0,
            long_sizing=0.80,
            short_sizing=0.0,
        )

        signal_side = "long"
        side_sizing = state.long_sizing if signal_side == "long" else state.short_sizing
        blocked = side_sizing <= 0.0
        assert blocked is False
        assert side_sizing == pytest.approx(0.80)

    def test_bear_trending_blocks_long(self):
        """In BEAR_TRENDING: long_sizing=0 -> long entry blocked."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        state = MarketRegimeState(
            regime=MarketRegime.BEAR_TRENDING,
            ma_fast=380.0, ma_slow=420.0,
            ma_spread_pct=-0.095,
            realized_vol=0.12,
            vol_threshold=0.18,
            sizing_multiplier=0.0,
            long_sizing=0.0,
            short_sizing=0.80,
        )

        signal_side = "long"
        side_sizing = state.long_sizing if signal_side == "long" else state.short_sizing
        blocked = side_sizing <= 0.0
        assert blocked is True

    def test_bear_trending_allows_short(self):
        """In BEAR_TRENDING: short_sizing=0.80 -> short entry allowed."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        state = MarketRegimeState(
            regime=MarketRegime.BEAR_TRENDING,
            ma_fast=380.0, ma_slow=420.0,
            ma_spread_pct=-0.095,
            realized_vol=0.12,
            vol_threshold=0.18,
            sizing_multiplier=0.0,
            long_sizing=0.0,
            short_sizing=0.80,
        )

        signal_side = "short"
        side_sizing = state.long_sizing if signal_side == "long" else state.short_sizing
        blocked = side_sizing <= 0.0
        assert blocked is False
        assert side_sizing == pytest.approx(0.80)

    def test_mean_reverting_allows_both(self):
        """In MEAN_REVERTING: both sides at 1.0 -> nothing blocked."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        state = MarketRegimeState(
            regime=MarketRegime.MEAN_REVERTING,
            ma_fast=380.0, ma_slow=400.0,
            ma_spread_pct=-0.05,
            realized_vol=0.25,
            vol_threshold=0.18,
            sizing_multiplier=1.0,
            long_sizing=1.0,
            short_sizing=1.0,
        )

        for side in ("long", "short"):
            side_sizing = state.long_sizing if side == "long" else state.short_sizing
            assert side_sizing == 1.0

    def test_neutral_reduces_both_sides(self):
        """In NEUTRAL: both sides at neutral_sizing (< 1.0)."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        state = MarketRegimeState(
            regime=MarketRegime.NEUTRAL,
            ma_fast=405.0, ma_slow=400.0,
            ma_spread_pct=0.012,
            realized_vol=0.15,
            vol_threshold=0.18,
            sizing_multiplier=0.65,
            long_sizing=0.65,
            short_sizing=0.65,
        )

        for side in ("long", "short"):
            side_sizing = state.long_sizing if side == "long" else state.short_sizing
            blocked = side_sizing <= 0.0
            assert blocked is False
            assert side_sizing == pytest.approx(0.65)

    def test_adaptive_gate_allocation_scaling(self):
        """Per-side sizing multiplier should scale allocation correctly."""
        from signal_engine.market_regime import MarketRegime, MarketRegimeState

        state = MarketRegimeState(
            regime=MarketRegime.BULL_TRENDING,
            ma_fast=450.0, ma_slow=400.0,
            ma_spread_pct=0.125,
            realized_vol=0.12,
            vol_threshold=0.18,
            sizing_multiplier=0.0,
            long_sizing=0.80,
            short_sizing=0.0,
        )

        base_alloc = 10.0
        signal_side = "long"
        side_sizing = state.long_sizing if signal_side == "long" else state.short_sizing

        if side_sizing > 0.0 and side_sizing < 1.0:
            adjusted_alloc = base_alloc * side_sizing
        elif side_sizing >= 1.0:
            adjusted_alloc = base_alloc
        else:
            adjusted_alloc = 0.0  # Blocked

        assert adjusted_alloc == pytest.approx(8.0)  # 10 * 0.80

    def test_settings_has_regime_v30_fields(self):
        """RegimeConfig should have trend_favorable_sizing and neutral_sizing."""
        from config.settings import Settings
        Settings._instance = None
        s = Settings()
        assert hasattr(s.regime, 'trend_favorable_sizing')
        assert hasattr(s.regime, 'neutral_sizing')
        assert 0.0 < s.regime.trend_favorable_sizing <= 1.0
        assert 0.0 < s.regime.neutral_sizing <= 1.0
        Settings._instance = None
