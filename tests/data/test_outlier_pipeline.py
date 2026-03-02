"""
Tests for Sprint 2.8 – Outlier pipeline pre-signal (M-08).

Coverage:
  - remove_outliers(threshold=4σ) applied before spread computation
  - Z-score clamped to [-6, +6] in SpreadModel & DynamicSpreadModel
  - Spike injection (+50%) ↓ no aberrant signal
  - Non-regression: clean data ↓ identical results (4σ threshold preserves normal data)
  - Edge cases: all NaN, constant series, single spike
"""

import numpy as np
import pandas as pd

from data.preprocessing import remove_outliers
from models.spread import SpreadModel
from models.adaptive_thresholds import DynamicSpreadModel


# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
# Helpers
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ

def _make_clean_prices(n: int = 200, seed: int = 42):
    """Two cointegrated price series with no outliers."""
    rng = np.random.RandomState(seed)
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    x = pd.Series(100 + np.cumsum(rng.normal(0, 0.5, n)), index=dates)
    y = 2 * x + rng.normal(0, 1, n)
    y = pd.Series(y, index=dates)
    return y, x


def _inject_spike(series: pd.Series, idx: int, factor: float = 1.5) -> pd.Series:
    """Inject a single +factor spike at the given index."""
    s = series.copy()
    s.iloc[idx] = s.iloc[idx] * factor
    return s


# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
# remove_outliers() tests
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ

class TestRemoveOutliers:
    """Tests for the price-level outlier removal."""

    def test_zscore_4sigma_preserves_normal_data(self):
        """Normal data within 4σ should be untouched."""
        rng = np.random.RandomState(42)
        series = pd.Series(rng.normal(100, 2, 500))
        cleaned = remove_outliers(series, method="zscore", threshold=4.0)
        # At 4σ, normal data should have ~0 outliers removed
        n_nan = cleaned.isna().sum()
        assert n_nan <= 2, f"4σ threshold removed {n_nan} points from normal data"

    def test_zscore_4sigma_removes_extreme_spike(self):
        """A +50% spike on a price series should be flagged as NaN."""
        y, x = _make_clean_prices(n=200)
        y_spiked = _inject_spike(y, idx=100, factor=1.5)
        cleaned = remove_outliers(y_spiked, method="zscore", threshold=4.0)
        assert cleaned.isna().any(), "50% spike should be removed by 4σ filter"
        # The spike index should be NaN
        assert pd.isna(cleaned.iloc[100])

    def test_ffill_bfill_restores_continuity(self):
        """After removing outlier and filling, no NaN should remain."""
        y, x = _make_clean_prices(n=200)
        y_spiked = _inject_spike(y, idx=100, factor=1.5)
        cleaned = remove_outliers(y_spiked, method="zscore", threshold=4.0)
        filled = cleaned.ffill().bfill()
        assert not filled.isna().any()
        assert len(filled) == len(y)

    def test_iqr_method_works(self):
        """IQR method should also function."""
        rng = np.random.RandomState(42)
        series = pd.Series(rng.normal(100, 2, 500))
        series.iloc[250] = 200  # Big outlier
        cleaned = remove_outliers(series, method="iqr", threshold=1.5)
        assert pd.isna(cleaned.iloc[250])

    def test_empty_series(self):
        """Empty series should return empty."""
        s = pd.Series(dtype=float)
        cleaned = remove_outliers(s, method="zscore", threshold=4.0)
        assert len(cleaned) == 0


# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
# Z-score clamping – SpreadModel
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ

class TestSpreadModelZScoreClamp:
    """Tests for Z-score clamping in the legacy SpreadModel."""

    def test_z_score_clamped_at_6(self):
        """Z-score values should never exceed ±6."""
        y, x = _make_clean_prices(n=200)
        # Inject a massive spike to produce extreme z-score
        y_spiked = _inject_spike(y, idx=100, factor=3.0)
        
        model = SpreadModel(y_spiked, x)
        spread = model.compute_spread(y_spiked, x)
        z = model.compute_z_score(spread)
        
        valid_z = z.dropna()
        assert valid_z.max() <= 6.0, f"Z-score max {valid_z.max()} exceeds 6.0"
        assert valid_z.min() >= -6.0, f"Z-score min {valid_z.min()} below -6.0"

    def test_clean_data_z_score_unchanged(self):
        """On clean data, z-score should be well within [-6, 6] – clamp is a no-op."""
        y, x = _make_clean_prices(n=200)
        model = SpreadModel(y, x)
        spread = model.compute_spread(y, x)
        z = model.compute_z_score(spread)
        
        valid_z = z.dropna()
        # Normal z should be comfortably within [-4, 4]
        assert valid_z.max() < 5.0
        assert valid_z.min() > -5.0

    def test_z_score_bounds_with_different_lookbacks(self):
        """Clamping should work regardless of lookback window."""
        y, x = _make_clean_prices(n=300)
        y_spiked = _inject_spike(y, idx=150, factor=5.0)
        
        model = SpreadModel(y_spiked, x)
        spread = model.compute_spread(y_spiked, x)
        
        for lookback in [10, 20, 60, 120]:
            z = model.compute_z_score(spread, lookback=lookback)
            valid_z = z.dropna()
            assert valid_z.max() <= 6.0
            assert valid_z.min() >= -6.0


# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
# Z-score clamping – DynamicSpreadModel
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ

class TestDynamicSpreadModelZScoreClamp:
    """Tests for Z-score clamping in DynamicSpreadModel."""

    def test_z_score_clamped_at_6(self):
        """Z-score values should never exceed ±6."""
        y, x = _make_clean_prices(n=200)
        y_spiked = _inject_spike(y, idx=100, factor=3.0)
        
        model = DynamicSpreadModel(y_spiked, x, half_life=20)
        spread = model.compute_spread(y_spiked, x)
        z = model.compute_z_score(spread)
        
        valid_z = z.dropna()
        assert valid_z.max() <= 6.0
        assert valid_z.min() >= -6.0

    def test_adaptive_signals_respect_clamp(self):
        """Adaptive signal z-scores should also be clamped."""
        y, x = _make_clean_prices(n=200)
        y_spiked = _inject_spike(y, idx=100, factor=3.0)
        
        model = DynamicSpreadModel(y_spiked, x, half_life=20)
        spread = model.compute_spread(y_spiked, x)
        _, info = model.get_adaptive_signals(spread)
        
        z = info['z_score'].dropna()
        assert z.max() <= 6.0
        assert z.min() >= -6.0


# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
# Integration: Spike ↓ no aberrant signal
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ

class TestSpikeNoAberrantSignal:
    """
    DoD: inject a +50% spike on one bar ↓ no aberrant entry signal.
    The outlier pipeline (remove_outliers + clamp) must suppress it.
    """

    def test_spike_cleaned_before_spread(self):
        """Full pipeline: clean ↓ spread ↓ z-score stays bounded."""
        y, x = _make_clean_prices(n=200)
        y_spiked = _inject_spike(y, idx=100, factor=1.5)
        
        # Apply outlier cleaning (as done in generate_signals)
        y_clean = remove_outliers(y_spiked, method="zscore", threshold=4.0).ffill().bfill()
        x_clean = x.copy()  # x is clean
        
        model = DynamicSpreadModel(y_clean, x_clean, half_life=20)
        spread = model.compute_spread(y_clean, x_clean)
        signals, info = model.get_adaptive_signals(spread)
        
        z = info['z_score']
        # Around the spike bar (100), z-score should be well-behaved
        z_around_spike = z.iloc[95:105].dropna()
        assert z_around_spike.abs().max() <= 6.0, (
            f"Z-score near spike: max |z|={z_around_spike.abs().max()}"
        )

    def test_spike_without_cleaning_would_be_extreme(self):
        """Without cleaning, a +50% spike would create extreme z-score (pre-clamp baseline)."""
        y, x = _make_clean_prices(n=200)
        y_spiked = _inject_spike(y, idx=100, factor=1.5)
        
        # Raw spread without outlier removal
        model = DynamicSpreadModel(y_spiked, x, half_life=20)
        spread = model.compute_spread(y_spiked, x)
        
        # Compute raw z-score manually (unclamped) to show impact
        lookback = 60  # 3 * 20
        rolling_mean = spread.rolling(window=lookback).mean()
        rolling_std = spread.rolling(window=lookback).std()
        z_raw = (spread - rolling_mean) / (rolling_std + 1e-8)
        
        # The spike should produce a large deviation in the raw z-score
        max_z_around_spike = z_raw.iloc[95:105].dropna().abs().max()
        # With clamping, it'd be ≤ 6. Without, it should be larger
        # (exact value depends on data, but spike effect should be visible)
        assert max_z_around_spike > 2.0, (
            f"Expected visible spike effect in raw z, got {max_z_around_spike}"
        )


# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
# Non-regression: clean data unchanged
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ

class TestNonRegression:
    """Verify that 4σ threshold doesn't alter clean data."""

    def test_clean_data_signals_identical(self):
        """On clean data, signals before/after outlier pipeline are the same."""
        y, x = _make_clean_prices(n=200)
        
        # Without cleaning
        model1 = DynamicSpreadModel(y, x, half_life=20)
        spread1 = model1.compute_spread(y, x)
        signals1, _ = model1.get_adaptive_signals(spread1)
        
        # With cleaning (should be no-op on clean data)
        y_clean = remove_outliers(y, method="zscore", threshold=4.0).ffill().bfill()
        x_clean = remove_outliers(x, method="zscore", threshold=4.0).ffill().bfill()
        model2 = DynamicSpreadModel(y_clean, x_clean, half_life=20)
        spread2 = model2.compute_spread(y_clean, x_clean)
        signals2, _ = model2.get_adaptive_signals(spread2)
        
        # Signals should be identical (or nearly so)
        match_pct = (signals1 == signals2).mean()
        assert match_pct > 0.95, f"Signal match: {match_pct:.1%}, expected >95%"

    def test_clean_data_remove_outliers_no_nans(self):
        """On clean data, remove_outliers(threshold=4) should introduce 0 NaNs."""
        y, x = _make_clean_prices(n=500)
        y_cleaned = remove_outliers(y, method="zscore", threshold=4.0)
        x_cleaned = remove_outliers(x, method="zscore", threshold=4.0)
        
        # Allow at most 1-2 NaNs from random chance
        assert y_cleaned.isna().sum() <= 2
        assert x_cleaned.isna().sum() <= 2


# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
# Edge cases
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ

class TestOutlierEdgeCases:
    """Edge cases and boundary conditions."""

    def test_multiple_spikes(self):
        """Multiple spikes should all be cleaned."""
        y, x = _make_clean_prices(n=300)
        y_spiked = _inject_spike(y, idx=50, factor=2.0)
        y_spiked = _inject_spike(y_spiked, idx=150, factor=2.0)
        y_spiked = _inject_spike(y_spiked, idx=250, factor=0.3)  # Negative spike
        
        cleaned = remove_outliers(y_spiked, method="zscore", threshold=4.0)
        assert pd.isna(cleaned.iloc[50])
        assert pd.isna(cleaned.iloc[150])
        assert pd.isna(cleaned.iloc[250])

    def test_constant_series_no_crash(self):
        """Constant series ↓ std=0 ↓ should not crash."""
        const = pd.Series(np.ones(100))
        # std = 0, z-score = inf, all flagged as NaN
        cleaned = remove_outliers(const, method="zscore", threshold=4.0)
        # Either all NaN (div by zero) or all kept – just no crash
        assert len(cleaned) == 100

    def test_series_with_nans(self):
        """Series with existing NaNs should be handled gracefully."""
        y, _ = _make_clean_prices(n=200)
        y.iloc[50:55] = np.nan
        cleaned = remove_outliers(y, method="zscore", threshold=4.0)
        filled = cleaned.ffill().bfill()
        assert not filled.isna().any()

    def test_z_clamp_exactly_at_boundary(self):
        """Z-score of exactly 6.0 or -6.0 should not be clipped further."""
        # Manually construct a spread that would produce z=6
        spread = pd.Series([0.0] * 50 + [6.0])
        model = SpreadModel(
            pd.Series(range(51)),
            pd.Series(range(51)),
        )
        z = model.compute_z_score(spread, lookback=50)
        valid_z = z.dropna()
        # After clip, z should be ≤ 6
        assert valid_z.max() <= 6.0
        assert valid_z.min() >= -6.0
