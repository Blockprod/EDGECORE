"""
Tests for signal_engine.momentum — MomentumOverlay (v31 Etape 2).

Covers:
    - Relative strength computation
    - Momentum score normalisation
    - Signal strength adjustment (long/short/exit)
    - Edge cases (insufficient data, zero RS, boundary configs)
    - Config validation
"""

import numpy as np
import pandas as pd
import pytest

from signal_engine.momentum import MomentumOverlay, MomentumResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prices(start: float, end: float, n: int = 30) -> pd.Series:
    """Generate a linearly interpolated price series."""
    return pd.Series(np.linspace(start, end, n))


def _make_flat_prices(price: float, n: int = 30) -> pd.Series:
    """Generate a flat price series."""
    return pd.Series([price] * n)


# ---------------------------------------------------------------------------
# TestRelativeStrength
# ---------------------------------------------------------------------------

class TestRelativeStrength:
    """Tests for compute_relative_strength()."""

    def test_positive_rs_when_a_outperforms(self):
        """RS > 0 when A appreciates and B is flat."""
        overlay = MomentumOverlay(lookback=20)
        prices_a = _make_prices(100, 120, 30)  # A goes up 20%
        prices_b = _make_flat_prices(100, 30)   # B flat
        rs = overlay.compute_relative_strength(prices_a, prices_b)
        assert rs > 0, f"Expected positive RS, got {rs}"

    def test_negative_rs_when_a_underperforms(self):
        """RS < 0 when A declines and B is flat."""
        overlay = MomentumOverlay(lookback=20)
        prices_a = _make_prices(100, 80, 30)   # A goes down 20%
        prices_b = _make_flat_prices(100, 30)   # B flat
        rs = overlay.compute_relative_strength(prices_a, prices_b)
        assert rs < 0, f"Expected negative RS, got {rs}"

    def test_zero_rs_when_equal_performance(self):
        """RS ~= 0 when both move identically."""
        overlay = MomentumOverlay(lookback=20)
        prices_a = _make_prices(100, 110, 30)
        prices_b = _make_prices(100, 110, 30)
        rs = overlay.compute_relative_strength(prices_a, prices_b)
        assert abs(rs) < 1e-10, f"Expected ~0 RS, got {rs}"

    def test_insufficient_data_returns_zero(self):
        """Returns 0.0 when not enough data for lookback."""
        overlay = MomentumOverlay(lookback=20)
        short_prices = pd.Series([100, 101, 102])
        rs = overlay.compute_relative_strength(short_prices, short_prices)
        assert rs == 0.0

    def test_custom_lookback(self):
        """Override lookback via parameter."""
        overlay = MomentumOverlay(lookback=20)
        prices_a = _make_prices(100, 120, 30)
        prices_b = _make_flat_prices(100, 30)
        rs_default = overlay.compute_relative_strength(prices_a, prices_b)
        rs_short = overlay.compute_relative_strength(prices_a, prices_b, lookback=5)
        # Shorter lookback captures less of the move
        assert rs_short != rs_default


# ---------------------------------------------------------------------------
# TestMomentumScore
# ---------------------------------------------------------------------------

class TestMomentumScore:
    """Tests for compute_momentum_score()."""

    def test_score_bounded_minus_one_to_one(self):
        """Score must be in [-1, 1] range."""
        overlay = MomentumOverlay(lookback=20)
        prices_a = _make_prices(100, 200, 30)  # Extreme +100%
        prices_b = _make_flat_prices(100, 30)
        score = overlay.compute_momentum_score(prices_a, prices_b)
        assert -1.0 <= score <= 1.0

    def test_positive_score_for_a_outperformance(self):
        """Positive score when A outperforms."""
        overlay = MomentumOverlay(lookback=20)
        prices_a = _make_prices(100, 115, 30)
        prices_b = _make_flat_prices(100, 30)
        score = overlay.compute_momentum_score(prices_a, prices_b)
        assert score > 0

    def test_negative_score_for_a_underperformance(self):
        """Negative score when A underperforms."""
        overlay = MomentumOverlay(lookback=20)
        prices_a = _make_prices(100, 85, 30)
        prices_b = _make_flat_prices(100, 30)
        score = overlay.compute_momentum_score(prices_a, prices_b)
        assert score < 0

    def test_zero_score_for_flat(self):
        """Score ~= 0 for identical performance."""
        overlay = MomentumOverlay(lookback=20)
        prices_a = _make_flat_prices(100, 30)
        prices_b = _make_flat_prices(100, 30)
        score = overlay.compute_momentum_score(prices_a, prices_b)
        assert abs(score) < 1e-10


# ---------------------------------------------------------------------------
# TestSignalAdjustment
# ---------------------------------------------------------------------------

class TestSignalAdjustment:
    """Tests for adjust_signal_strength()."""

    def test_long_signal_boosted_when_a_underperforms(self):
        """Long A/short B: A underperforming = momentum confirms = boost."""
        overlay = MomentumOverlay(lookback=20, weight=0.30, min_strength=0.3, max_boost=1.0)
        prices_a = _make_prices(100, 85, 30)   # A down
        prices_b = _make_flat_prices(100, 30)   # B flat
        result = overlay.adjust_signal_strength("long", 0.6, prices_a, prices_b)
        assert isinstance(result, MomentumResult)
        assert result.confirms_signal is True
        assert result.adjusted_strength > result.raw_strength

    def test_long_signal_reduced_when_a_outperforms(self):
        """Long A/short B: A outperforming = contra-momentum = reduce."""
        overlay = MomentumOverlay(lookback=20, weight=0.30, min_strength=0.3, max_boost=1.0)
        prices_a = _make_prices(100, 115, 30)   # A up
        prices_b = _make_flat_prices(100, 30)    # B flat
        result = overlay.adjust_signal_strength("long", 0.6, prices_a, prices_b)
        assert result.confirms_signal is False
        assert result.adjusted_strength < result.raw_strength

    def test_short_signal_boosted_when_a_outperforms(self):
        """Short A/long B: A outperforming = momentum confirms = boost."""
        overlay = MomentumOverlay(lookback=20, weight=0.30, min_strength=0.3, max_boost=1.0)
        prices_a = _make_prices(100, 115, 30)   # A up
        prices_b = _make_flat_prices(100, 30)    # B flat
        result = overlay.adjust_signal_strength("short", 0.6, prices_a, prices_b)
        assert result.confirms_signal is True
        assert result.adjusted_strength > result.raw_strength

    def test_short_signal_reduced_when_a_underperforms(self):
        """Short A/long B: A underperforming = contra-momentum = reduce."""
        overlay = MomentumOverlay(lookback=20, weight=0.30, min_strength=0.3, max_boost=1.0)
        prices_a = _make_prices(100, 85, 30)    # A down
        prices_b = _make_flat_prices(100, 30)    # B flat
        result = overlay.adjust_signal_strength("short", 0.6, prices_a, prices_b)
        assert result.confirms_signal is False
        assert result.adjusted_strength < result.raw_strength

    def test_exit_signal_passthrough(self):
        """Exit signals should not be adjusted."""
        overlay = MomentumOverlay(lookback=20, weight=0.30)
        prices_a = _make_prices(100, 150, 30)
        prices_b = _make_flat_prices(100, 30)
        result = overlay.adjust_signal_strength("exit", 1.0, prices_a, prices_b)
        assert result.adjusted_strength == 1.0
        assert result.confirms_signal is True

    def test_strength_floor_at_min_strength(self):
        """Strength should never go below min_strength for contra-momentum."""
        overlay = MomentumOverlay(lookback=20, weight=0.50, min_strength=0.30, max_boost=1.0)
        prices_a = _make_prices(100, 200, 30)   # Extreme outperformance
        prices_b = _make_flat_prices(100, 30)
        result = overlay.adjust_signal_strength("long", 0.4, prices_a, prices_b)
        assert result.adjusted_strength >= 0.30

    def test_strength_cap_at_max_boost(self):
        """Strength should never exceed max_boost for confirmed momentum."""
        overlay = MomentumOverlay(lookback=20, weight=0.50, min_strength=0.3, max_boost=0.85)
        prices_a = _make_prices(100, 60, 30)    # Extreme underperformance
        prices_b = _make_flat_prices(100, 30)
        result = overlay.adjust_signal_strength("long", 0.8, prices_a, prices_b)
        assert result.adjusted_strength <= 0.85

    def test_unknown_side_passthrough(self):
        """Unknown side string returns raw_strength unchanged."""
        overlay = MomentumOverlay(lookback=20)
        prices_a = _make_prices(100, 120, 30)
        prices_b = _make_flat_prices(100, 30)
        result = overlay.adjust_signal_strength("hold", 0.5, prices_a, prices_b)
        assert result.adjusted_strength == 0.5
        assert result.confirms_signal is False


# ---------------------------------------------------------------------------
# TestConfigValidation
# ---------------------------------------------------------------------------

class TestConfigValidation:
    """Tests for constructor parameter validation."""

    def test_lookback_too_small(self):
        with pytest.raises(ValueError, match="lookback"):
            MomentumOverlay(lookback=1)

    def test_weight_out_of_range(self):
        with pytest.raises(ValueError, match="weight"):
            MomentumOverlay(weight=1.5)

    def test_min_strength_out_of_range(self):
        with pytest.raises(ValueError, match="min_strength"):
            MomentumOverlay(min_strength=-0.1)

    def test_max_boost_out_of_range(self):
        with pytest.raises(ValueError, match="max_boost"):
            MomentumOverlay(max_boost=1.5)

    def test_valid_defaults(self):
        """Default construction should not raise."""
        overlay = MomentumOverlay()
        assert overlay.lookback == 20
        assert overlay.weight == 0.30
        assert overlay.min_strength == 0.30
        assert overlay.max_boost == 1.0


# ---------------------------------------------------------------------------
# TestMomentumConfig
# ---------------------------------------------------------------------------

class TestMomentumConfig:
    """Tests for MomentumConfig in settings."""

    def test_momentum_config_exists(self):
        """MomentumConfig dataclass should be importable."""
        from config.settings import MomentumConfig
        cfg = MomentumConfig()
        assert cfg.enabled is True
        assert cfg.lookback == 20
        assert cfg.weight == 0.30

    def test_settings_has_momentum(self):
        """Settings singleton should have .momentum attribute."""
        from config.settings import Settings
        # Reset singleton for test isolation
        Settings._instance = None
        Settings._instance = None
        s = Settings()
        assert hasattr(s, 'momentum')
        assert s.momentum.enabled is True
        # Cleanup
        Settings._instance = None
