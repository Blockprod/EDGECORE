"""
Test suite for MarketRegimeFilter (v30 adaptive bidirectional).

Verifies:
  1. Classification logic (BULL_TRENDING / BEAR_TRENDING / MEAN_REVERTING / NEUTRAL)
  2. Disabled mode returns MEAN_REVERTING always
  3. Insufficient data returns NEUTRAL
  4. Regime transitions are detected
  5. High-vol periods classified as MEAN_REVERTING
  6. Bull market classified as BULL_TRENDING (longs only)
  7. Bear market (low vol) classified as BEAR_TRENDING (shorts only)
  8. Per-side sizing multipliers (long_sizing, short_sizing)
  9. Legacy TRENDING alias still valid
"""

import numpy as np
import pandas as pd
import pytest

from signal_engine.market_regime import (
    MarketRegime,
    MarketRegimeFilter,
    MarketRegimeState,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_spy_series(
    n: int = 300,
    start_price: float = 400.0,
    daily_return: float = 0.0005,
    volatility: float = 0.01,
    seed: int = 42,
) -> pd.Series:
    """Generate a synthetic SPY price series."""
    rng = np.random.RandomState(seed)
    returns = rng.normal(daily_return, volatility, n)
    prices = start_price * np.cumprod(1 + returns)
    idx = pd.bdate_range("2023-01-01", periods=n)
    return pd.Series(prices, index=idx, name="SPY")


def _make_bull_market(n: int = 300) -> pd.Series:
    """Strong uptrend, low volatility -> BULL_TRENDING."""
    return _make_spy_series(
        n=n,
        start_price=400.0,
        daily_return=0.001,  # Strong positive drift
        volatility=0.005,  # Very low vol
        seed=42,
    )


def _make_bear_market_high_vol(n: int = 300) -> pd.Series:
    """Downtrend + high vol -> MEAN_REVERTING (vol overrides trend)."""
    return _make_spy_series(
        n=n,
        start_price=400.0,
        daily_return=-0.001,  # Negative drift
        volatility=0.025,  # High vol
        seed=42,
    )


def _make_bear_market_low_vol(n: int = 300) -> pd.Series:
    """Sustained downtrend, low volatility -> BEAR_TRENDING."""
    return _make_spy_series(
        n=n,
        start_price=400.0,
        daily_return=-0.0008,  # Negative drift (grinding bear)
        volatility=0.005,  # Very low vol
        seed=99,
    )


def _make_sideways_market(n: int = 300) -> pd.Series:
    """Flat, moderate vol -> NEUTRAL."""
    return _make_spy_series(
        n=n,
        start_price=400.0,
        daily_return=0.00005,  # Nearly zero drift
        volatility=0.012,  # Moderate vol (~19% annualized, near threshold)
        seed=42,
    )


# ── Tests ────────────────────────────────────────────────────────────────


class TestMarketRegimeFilter:
    """Core classification tests."""

    def test_bull_market_classified_as_bull_trending(self):
        """Strong uptrend + low vol -> BULL_TRENDING, longs allowed, shorts blocked."""
        mrf = MarketRegimeFilter(ma_fast=50, ma_slow=200, vol_threshold=0.18)
        spy = _make_bull_market(n=300)
        state = mrf.classify(spy)
        assert state.regime == MarketRegime.BULL_TRENDING
        assert state.long_sizing > 0  # Longs allowed
        assert state.short_sizing == 0.0  # Shorts blocked
        assert state.sizing_multiplier == 0.0  # Legacy compat

    def test_bear_market_high_vol_classified_as_mean_reverting(self):
        """Downtrend + high vol -> MEAN_REVERTING, both sides at 100%."""
        mrf = MarketRegimeFilter(ma_fast=50, ma_slow=200, vol_threshold=0.18)
        spy = _make_bear_market_high_vol(n=300)
        state = mrf.classify(spy)
        assert state.regime == MarketRegime.MEAN_REVERTING
        assert state.sizing_multiplier == 1.0
        assert state.long_sizing == 1.0
        assert state.short_sizing == 1.0

    def test_bear_market_low_vol_classified_as_bear_trending(self):
        """Grinding downtrend + low vol -> BEAR_TRENDING, shorts only."""
        mrf = MarketRegimeFilter(ma_fast=50, ma_slow=200, vol_threshold=0.18)
        spy = _make_bear_market_low_vol(n=300)
        state = mrf.classify(spy)
        assert state.regime == MarketRegime.BEAR_TRENDING
        assert state.long_sizing == 0.0  # Longs blocked
        assert state.short_sizing > 0  # Shorts allowed

    def test_sideways_market_classified_as_neutral_or_mean_reverting(self):
        """Flat market -> NEUTRAL or MEAN_REVERTING (depends on exact vol)."""
        mrf = MarketRegimeFilter(ma_fast=50, ma_slow=200, vol_threshold=0.18)
        spy = _make_sideways_market(n=300)
        state = mrf.classify(spy)
        assert state.regime in (MarketRegime.NEUTRAL, MarketRegime.MEAN_REVERTING)
        assert state.long_sizing > 0
        assert state.short_sizing > 0

    def test_disabled_returns_mean_reverting(self):
        """When disabled, always return MEAN_REVERTING with full sizing."""
        mrf = MarketRegimeFilter(enabled=False)
        spy = _make_bull_market(n=300)
        state = mrf.classify(spy)
        assert state.regime == MarketRegime.MEAN_REVERTING
        assert state.sizing_multiplier == 1.0
        assert state.long_sizing == 1.0
        assert state.short_sizing == 1.0

    def test_insufficient_data_returns_neutral(self):
        """Less than ma_slow bars -> NEUTRAL (cautious default)."""
        mrf = MarketRegimeFilter(ma_fast=50, ma_slow=200)
        spy = _make_spy_series(n=100)  # < 200
        state = mrf.classify(spy)
        assert state.regime == MarketRegime.NEUTRAL
        # Both sides at neutral_sizing
        assert state.long_sizing == state.short_sizing


class TestMarketRegimeState:
    """State object tests."""

    def test_state_fields_populated(self):
        """All fields in MarketRegimeState should be populated."""
        mrf = MarketRegimeFilter()
        spy = _make_bull_market(n=300)
        state = mrf.classify(spy)

        assert isinstance(state, MarketRegimeState)
        assert isinstance(state.regime, MarketRegime)
        assert state.ma_fast > 0
        assert state.ma_slow > 0
        assert isinstance(state.ma_spread_pct, float)
        assert state.realized_vol >= 0
        assert state.vol_threshold == 0.18
        # v30: per-side sizing
        assert hasattr(state, 'long_sizing')
        assert hasattr(state, 'short_sizing')

    def test_last_state_property(self):
        """last_state should reflect the most recent classify() call."""
        mrf = MarketRegimeFilter()
        assert mrf.last_state is None

        spy = _make_bull_market(n=300)
        state = mrf.classify(spy)
        assert mrf.last_state is state

    def test_sizing_values_bounded_0_1(self):
        """Per-side sizing multipliers should be in [0.0, 1.0]."""
        mrf = MarketRegimeFilter()
        for factory in [_make_bull_market, _make_bear_market_high_vol,
                        _make_bear_market_low_vol, _make_sideways_market]:
            spy = factory(n=300)
            state = mrf.classify(spy)
            assert 0.0 <= state.long_sizing <= 1.0
            assert 0.0 <= state.short_sizing <= 1.0
            assert 0.0 <= state.sizing_multiplier <= 1.0

    def test_legacy_trending_enum_still_valid(self):
        """MarketRegime.TRENDING should still be a valid enum value."""
        assert MarketRegime.TRENDING.value == "trending"


class TestRegimeTransitions:
    """Test regime transition detection."""

    def test_transition_from_bull_to_bear(self):
        """Feeding bull then bear data should trigger a transition."""
        mrf = MarketRegimeFilter(ma_fast=50, ma_slow=200, vol_threshold=0.18)

        # Classify bull
        spy_bull = _make_bull_market(n=300)
        state1 = mrf.classify(spy_bull)

        # Classify bear (high vol)
        spy_bear = _make_bear_market_high_vol(n=300)
        state2 = mrf.classify(spy_bear)

        # They should be different regimes
        assert state1.regime != state2.regime

    def test_repeated_classify_same_data_no_transition(self):
        """Multiple calls with same data should not trigger transition."""
        mrf = MarketRegimeFilter()
        spy = _make_bull_market(n=300)

        state1 = mrf.classify(spy)
        state2 = mrf.classify(spy)
        assert state1.regime == state2.regime


class TestAdaptiveBidirectional:
    """v30: Test adaptive bidirectional per-side sizing."""

    def test_bull_trending_blocks_shorts_allows_longs(self):
        """BULL_TRENDING: long_sizing > 0, short_sizing == 0."""
        mrf = MarketRegimeFilter(trend_favorable_sizing=0.80)
        spy = _make_bull_market(n=300)
        state = mrf.classify(spy)
        assert state.regime == MarketRegime.BULL_TRENDING
        assert state.long_sizing == 0.80
        assert state.short_sizing == 0.0

    def test_bear_trending_blocks_longs_allows_shorts(self):
        """BEAR_TRENDING: short_sizing > 0, long_sizing == 0."""
        mrf = MarketRegimeFilter(trend_favorable_sizing=0.80)
        spy = _make_bear_market_low_vol(n=300)
        state = mrf.classify(spy)
        assert state.regime == MarketRegime.BEAR_TRENDING
        assert state.long_sizing == 0.0
        assert state.short_sizing == 0.80

    def test_mean_reverting_both_sides_full(self):
        """MEAN_REVERTING: both sides at 1.0."""
        mrf = MarketRegimeFilter()
        spy = _make_bear_market_high_vol(n=300)
        state = mrf.classify(spy)
        assert state.regime == MarketRegime.MEAN_REVERTING
        assert state.long_sizing == 1.0
        assert state.short_sizing == 1.0

    def test_neutral_both_sides_reduced(self):
        """NEUTRAL: both sides at neutral_sizing."""
        mrf = MarketRegimeFilter(neutral_sizing=0.65)
        spy = _make_spy_series(n=100)  # Not enough data -> NEUTRAL
        state = mrf.classify(spy)
        assert state.regime == MarketRegime.NEUTRAL
        assert state.long_sizing == 0.65
        assert state.short_sizing == 0.65

    def test_custom_trend_favorable_sizing(self):
        """Custom trend_favorable_sizing should propagate to per-side values."""
        mrf = MarketRegimeFilter(trend_favorable_sizing=0.90)
        spy = _make_bull_market(n=300)
        state = mrf.classify(spy)
        assert state.long_sizing == 0.90

    def test_custom_neutral_sizing(self):
        """Custom neutral_sizing should propagate to per-side values."""
        mrf = MarketRegimeFilter(neutral_sizing=0.50)
        spy = _make_spy_series(n=100)  # NEUTRAL
        state = mrf.classify(spy)
        assert state.long_sizing == 0.50
        assert state.short_sizing == 0.50


class TestRegimeConfig:
    """Test RegimeConfig integration with settings."""

    def test_regime_config_exists(self):
        """RegimeConfig dataclass should be importable."""
        from config.settings import RegimeConfig

        cfg = RegimeConfig()
        assert cfg.enabled is True
        assert cfg.ma_fast == 50
        assert cfg.ma_slow == 200
        assert cfg.vol_threshold == 0.18
        assert cfg.vol_window == 20
        assert cfg.neutral_band_pct == 0.02

    def test_regime_config_v30_fields(self):
        """RegimeConfig should have v30 adaptive fields."""
        from config.settings import RegimeConfig

        cfg = RegimeConfig()
        assert cfg.trend_favorable_sizing == 0.80
        assert cfg.neutral_sizing == 0.65

    def test_custom_thresholds(self):
        """Custom thresholds should change classification."""
        # With very high vol_threshold, even low-vol bull -> BULL_TRENDING
        mrf_default = MarketRegimeFilter(vol_threshold=0.18)
        mrf_high = MarketRegimeFilter(vol_threshold=0.50)

        spy = _make_bull_market(n=300)
        state_d = mrf_default.classify(spy)
        state_h = mrf_high.classify(spy)

        # Both should detect bull trend
        assert state_d.regime == MarketRegime.BULL_TRENDING
        assert state_h.regime == MarketRegime.BULL_TRENDING

    def test_very_low_vol_threshold_makes_mean_reverting(self):
        """Very low vol_threshold -> vol always exceeds it -> MEAN_REVERTING."""
        mrf = MarketRegimeFilter(vol_threshold=0.01)  # 1% -- everything exceeds this
        spy = _make_bull_market(n=300)
        state = mrf.classify(spy)
        assert state.regime == MarketRegime.MEAN_REVERTING
        assert state.sizing_multiplier == 1.0
