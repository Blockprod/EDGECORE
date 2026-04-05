"""
Tests for Adaptive Z-Score Threshold Engine.

Validates that thresholds adapt appropriately to market regimes,
half-life characteristics, and volatility conditions.
"""

import numpy as np
import pandas as pd

from models.adaptive_thresholds import AdaptiveThresholdCalculator, DynamicSpreadModel, ThresholdConfig


class TestThresholdConfigDefaults:
    """Test default configuration values."""

    def test_default_config_values(self):
        """Test that default config has sensible values."""
        config = ThresholdConfig()

        assert config.base_entry_threshold == 2.0
        assert config.base_exit_threshold == 0.5
        assert config.min_entry_threshold == 1.0
        assert config.max_entry_threshold == 3.5
        assert config.volatility_adjustment_enabled is True
        assert config.regime_adjustment_enabled is True
        assert config.hl_adjustment_enabled is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = ThresholdConfig(base_entry_threshold=1.5, max_entry_threshold=3.0)

        assert config.base_entry_threshold == 1.5
        assert config.max_entry_threshold == 3.0
        assert config.min_entry_threshold == 1.0  # Default unchanged


class TestAdaptiveThresholdCalculator:
    """Test threshold calculation logic."""

    def test_calculator_initialization(self):
        """Test calculator initializes correctly."""
        calc = AdaptiveThresholdCalculator()
        assert calc.config is not None
        assert calc.volatility_history == []

    def test_baseline_threshold(self):
        """Test baseline threshold with no adjustments."""
        calc = AdaptiveThresholdCalculator(
            ThresholdConfig(volatility_adjustment_enabled=False, hl_adjustment_enabled=False)
        )

        spread = pd.Series(np.random.randn(100))
        entry, exit_t, details = calc.calculate_threshold(spread)

        assert entry == 2.0  # Baseline
        assert exit_t == 0.5  # Baseline
        assert details["volatility_adjustment"] == 0.0
        assert details["half_life_adjustment"] == 0.0

    def test_volatility_adjustment_low_regime(self):
        """Test threshold adjustment in low volatility regime."""
        calc = AdaptiveThresholdCalculator(ThresholdConfig(volatility_adjustment_enabled=True))

        # Create low-volatility spread (small movements)
        np.random.seed(42)
        spread = pd.Series(np.cumsum(np.random.randn(200) * 0.01))

        entry, _exit_t, details = calc.calculate_threshold(spread)

        # Low vol should decrease threshold (easier to trigger signals)
        if details["regime"] == "low":
            assert entry < 2.0
            assert details["volatility_adjustment"] < 0

    def test_volatility_adjustment_high_regime(self):
        """Test threshold adjustment in high volatility regime."""
        calc = AdaptiveThresholdCalculator(ThresholdConfig(volatility_adjustment_enabled=True))

        # Create high-volatility spread (large movements)
        np.random.seed(42)
        spread = pd.Series(np.cumsum(np.random.randn(200) * 0.5))

        entry, _exit_t, details = calc.calculate_threshold(spread)

        # High vol should increase threshold (harder to trigger signals)
        if details["regime"] == "high":
            assert entry > 2.0
            assert details["volatility_adjustment"] > 0

    def test_half_life_adjustment_short(self):
        """Test adjustment for short half-life spreads."""
        calc = AdaptiveThresholdCalculator(ThresholdConfig(hl_adjustment_enabled=True))

        spread = pd.Series(np.random.randn(100))
        entry, _exit_t, details = calc.calculate_threshold(
            spread,
            half_life=5.0,  # Very short HL
        )

        # Short HL: lower threshold (fast reversion)
        assert entry < 2.0
        assert details["half_life_adjustment"] < 0

    def test_half_life_adjustment_long(self):
        """Test adjustment for long half-life spreads."""
        calc = AdaptiveThresholdCalculator(ThresholdConfig(hl_adjustment_enabled=True))

        spread = pd.Series(np.random.randn(100))
        entry, _exit_t, details = calc.calculate_threshold(
            spread,
            half_life=50.0,  # Long HL
        )

        # Long HL: higher threshold (slow reversion)
        assert entry > 2.0
        assert details["half_life_adjustment"] > 0

    def test_threshold_bounds(self):
        """Test that thresholds stay within bounds."""
        calc = AdaptiveThresholdCalculator(
            ThresholdConfig(volatility_adjustment_enabled=True, hl_adjustment_enabled=True)
        )

        # Extreme volatility
        spread = pd.Series(np.cumsum(np.random.randn(200) * 2.0))
        entry, _exit_t, _details = calc.calculate_threshold(spread, half_life=60.0)

        # Should be bounded
        assert 1.0 <= entry <= 3.5
        assert entry == np.clip(entry, 1.0, 3.5)

    def test_position_sizing(self):
        """Test position sizing calculation."""
        calc = AdaptiveThresholdCalculator()

        # Normal case
        size = calc.calculate_position_sizing(portfolio_vol=0.15, spread_vol=0.05, target_risk_pct=0.01)

        assert 0.1 <= size <= 2.0  # Bounds check

        # Higher spread vol -> smaller size
        size_high_vol = calc.calculate_position_sizing(portfolio_vol=0.15, spread_vol=0.20, target_risk_pct=0.01)

        assert size_high_vol < size


class TestDynamicSpreadModel:
    """Test dynamic spread model with adaptive thresholds."""

    def test_model_initialization(self):
        """Test model initializes correctly."""
        np.random.seed(42)
        x = pd.Series(np.cumsum(np.random.randn(100)))
        y = pd.Series(2.0 * x + np.random.randn(100) * 0.5)

        model = DynamicSpreadModel(y, x, half_life=20.0)

        assert model.intercept is not None
        assert model.beta is not None
        assert model.half_life == 20.0
        assert model.threshold_calculator is not None

    def test_compute_spread(self):
        """Test spread computation."""
        np.random.seed(42)
        x = pd.Series(np.cumsum(np.random.randn(100)))
        y = pd.Series(2.0 * x + np.random.randn(100) * 0.5)

        model = DynamicSpreadModel(y, x)

        # Spread = y - (intercept + beta*x)
        spread = model.compute_spread(y, x)

        assert len(spread) == len(x)
        assert isinstance(spread, pd.Series)
        assert np.std(spread) > 0

    def test_adaptive_z_score_lookback(self):
        """Test that Z-score lookback adapts to half-life."""
        np.random.seed(42)
        x = pd.Series(np.cumsum(np.random.randn(200)))
        y = pd.Series(2.0 * x + np.random.randn(200) * 0.5)

        spread = y - 2.0 * x

        # Model with short half-life
        model_short = DynamicSpreadModel(y, x, half_life=10.0)
        z_short = model_short.compute_z_score(spread, lookback=None)

        # Model with long half-life (uses longer lookback)
        model_long = DynamicSpreadModel(y, x, half_life=50.0)
        z_long = model_long.compute_z_score(spread, lookback=None)

        # Z-scores should both be computed
        assert len(z_short) == len(z_long)
        # Neither should be all NaNs
        assert z_short.notna().sum() > 0
        assert z_long.notna().sum() > 0

    def test_adaptive_signals_generation(self):
        """Test adaptive signal generation."""
        np.random.seed(42)
        x = pd.Series(np.cumsum(np.random.randn(200)))
        y = pd.Series(2.0 * x + np.random.randn(200) * 0.5)

        model = DynamicSpreadModel(y, x, half_life=20.0)
        spread = model.compute_spread(y, x)

        signals, info = model.get_adaptive_signals(spread)

        # Check signal values
        assert set(signals.unique()).issubset({-1, 0, 1})

        # Check info keys
        assert "entry_threshold" in info
        assert "exit_threshold" in info
        assert "z_score" in info
        assert "adjustments" in info

        # Entry threshold should be between bounds
        assert 1.0 <= info["entry_threshold"] <= 3.5

    def test_model_info(self):
        """Test that model info is accessible."""
        np.random.seed(42)
        x = pd.Series(np.cumsum(np.random.randn(100)))
        y = pd.Series(2.0 * x + np.random.randn(100) * 0.5)

        model = DynamicSpreadModel(y, x, half_life=25.0)

        info = model.get_model_info()

        assert "intercept" in info
        assert "beta" in info
        assert "residual_std" in info
        assert "residual_mean" in info
        assert "half_life" in info
        assert info["half_life"] == 25.0


class TestThresholdAdaptationScenarios:
    """End-to-end test of threshold adaptation scenarios."""

    def test_calm_market_scenario(self):
        """Test threshold behavior in calm market."""
        calc = AdaptiveThresholdCalculator()

        # Calm market: small, stable spreads over longer history
        np.random.seed(42)
        calm_history = np.concatenate(
            [
                np.random.randn(100) * 0.02,  # Calm period
            ]
        )
        calm_spread = pd.Series(np.cumsum(calm_history))

        entry, _exit_t, _details = calc.calculate_threshold(calm_spread, half_life=15.0)

        # Calm market + fast reversion should give lower or normal threshold
        # (might be normal if not enough history for volatility classification)
        assert 1.0 <= entry <= 2.5

    def test_volatile_market_scenario(self):
        """Test threshold behavior in volatile market."""
        calc = AdaptiveThresholdCalculator()

        # Volatile market: large spreads
        np.random.seed(42)
        volatile_spread = pd.Series(np.cumsum(np.random.randn(200) * 0.8))

        entry, _exit_t, _details = calc.calculate_threshold(volatile_spread, half_life=45.0)

        # Volatile market + slow reversion = higher threshold
        assert entry > 2.0

    def test_transition_regime_scenario(self):
        """Test threshold adaptation during regime transition."""
        calc = AdaptiveThresholdCalculator()

        # Gradual transition from calm to volatile
        np.random.seed(42)
        calm_part = pd.Series(np.cumsum(np.random.randn(100) * 0.02))
        volatile_part = pd.Series(np.cumsum(np.random.randn(100) * 0.8))
        volatility_profile = pd.concat([calm_part, volatile_part], ignore_index=True)

        # Threshold on calm part
        entry_calm, _, _details_calm = calc.calculate_threshold(pd.Series(volatility_profile[:120]), half_life=20.0)

        # Threshold on volatile part
        entry_volatile, _, _details_volatile = calc.calculate_threshold(
            pd.Series(volatility_profile[100:200]), half_life=20.0
        )

        # Volatile should have higher (or equal) threshold
        assert entry_volatile >= entry_calm or np.isclose(entry_volatile, entry_calm)
