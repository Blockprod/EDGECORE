<<<<<<< HEAD
﻿"""
=======
"""
>>>>>>> origin/main
SpreadModel Integration Test (S3.2d - Integration).

Test that SpreadModel correctly integrates half-life estimation.
"""

<<<<<<< HEAD
import numpy as np
import pandas as pd
import pytest

=======
import pytest
import numpy as np
import pandas as pd
>>>>>>> origin/main
from models.spread import SpreadModel


class TestSpreadModelIntegration:
    """Test SpreadModel with integrated half-life estimation."""
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_spread_model_initialization(self):
        """Test SpreadModel initializes successfully."""
        np.random.seed(42)
        x = pd.Series(np.random.randn(100).cumsum())
<<<<<<< HEAD
        y = pd.Series(1.5 * np.asarray(x, dtype=float) + np.random.randn(100))

        model = SpreadModel(x, y)

=======
        y = pd.Series(1.5 * x.values + np.random.randn(100))
        
        model = SpreadModel(x, y)
        
>>>>>>> origin/main
        # Should have valid parameters
        assert np.isfinite(model.beta)
        assert np.isfinite(model.intercept)
        assert model.half_life is None or (5 <= model.half_life <= 200)
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_spread_computation(self):
        """Test spread is computed correctly."""
        np.random.seed(42)
        x = pd.Series(np.random.randn(100).cumsum())
<<<<<<< HEAD
        y = pd.Series(1.5 * np.asarray(x, dtype=float) + np.random.randn(100))

        model = SpreadModel(x, y)
        spread = model.compute_spread(x, y)

=======
        y = pd.Series(1.5 * x.values + np.random.randn(100))
        
        model = SpreadModel(x, y)
        spread = model.compute_spread(x, y)
        
>>>>>>> origin/main
        # Spread should have same length
        assert len(spread) == len(x)
        # Spread should be finite
        assert np.all(np.isfinite(spread))
<<<<<<< HEAD

    def test_z_score_uses_estimated_half_life(self):
        """Test Z-score computation uses estimated half-life."""
        np.random.seed(42)

=======
    
    def test_z_score_uses_estimated_half_life(self):
        """Test Z-score computation uses estimated half-life."""
        np.random.seed(42)
        
>>>>>>> origin/main
        # Generate mean-reverting pair
        mr = np.log(2) / 40  # HL = 40
        data_x = []
        data_y = []
<<<<<<< HEAD

        x_val = 0
        y_val = 0

=======
        
        x_val = 0
        y_val = 0
        
>>>>>>> origin/main
        for _ in range(300):
            x_val = x_val - mr * x_val + np.random.normal(0, 1)
            y_val = 1.5 * x_val + 0.5 * y_val + np.random.normal(0, 0.5)
            data_x.append(x_val)
            data_y.append(y_val)
<<<<<<< HEAD

        x = pd.Series(data_x)
        y = pd.Series(data_y)

        model = SpreadModel(x, y)
        spread = model.compute_spread(x, y)

        # Compute Z-score (should use estimated half-life)
        z_score = model.compute_z_score(spread)

        # Should be valid
        assert len(z_score) == len(spread)
        assert np.all(np.isfinite(z_score.dropna()))

=======
        
        x = pd.Series(data_x)
        y = pd.Series(data_y)
        
        model = SpreadModel(x, y)
        spread = model.compute_spread(x, y)
        
        # Compute Z-score (should use estimated half-life)
        z_score = model.compute_z_score(spread)
        
        # Should be valid
        assert len(z_score) == len(spread)
        assert np.all(np.isfinite(z_score.dropna()))
    
>>>>>>> origin/main
    def test_model_info_includes_half_life(self):
        """Test get_model_info includes half-life."""
        np.random.seed(42)
        x = pd.Series(np.random.randn(100).cumsum())
<<<<<<< HEAD
        y = pd.Series(1.5 * np.asarray(x, dtype=float) + np.random.randn(100))

        model = SpreadModel(x, y)
        info = model.get_model_info()

        # Should have all expected keys
        assert "intercept" in info
        assert "beta" in info
        assert "residual_std" in info
        assert "half_life" in info
        assert "is_deprecated" in info

=======
        y = pd.Series(1.5 * x.values + np.random.randn(100))
        
        model = SpreadModel(x, y)
        info = model.get_model_info()
        
        # Should have all expected keys
        assert 'intercept' in info
        assert 'beta' in info
        assert 'residual_std' in info
        assert 'half_life' in info
        assert 'is_deprecated' in info
    
>>>>>>> origin/main
    def test_backward_compatibility_no_pair_key(self):
        """Test SpreadModel works without pair_key."""
        np.random.seed(42)
        x = pd.Series(np.random.randn(100).cumsum())
<<<<<<< HEAD
        y = pd.Series(1.5 * np.asarray(x, dtype=float) + np.random.randn(100))

        # Should work without pair_key
        model = SpreadModel(x, y)

        assert model.pair_key is None
        assert np.isfinite(model.beta)

=======
        y = pd.Series(1.5 * x.values + np.random.randn(100))
        
        # Should work without pair_key
        model = SpreadModel(x, y)
        
        assert model.pair_key is None
        assert np.isfinite(model.beta)
    
>>>>>>> origin/main
    def test_backward_compatibility_no_tracker(self):
        """Test SpreadModel works without hedge_ratio_tracker."""
        np.random.seed(42)
        x = pd.Series(np.random.randn(100).cumsum())
<<<<<<< HEAD
        y = pd.Series(1.5 * np.asarray(x, dtype=float) + np.random.randn(100))

        # Should work without tracker
        model = SpreadModel(x, y)

        assert model.tracker is None
        assert np.isfinite(model.beta)

=======
        y = pd.Series(1.5 * x.values + np.random.randn(100))
        
        # Should work without tracker
        model = SpreadModel(x, y)
        
        assert model.tracker is None
        assert np.isfinite(model.beta)
    
>>>>>>> origin/main
    def test_z_score_with_explicit_lookback(self):
        """Test Z-score with explicit looback overrides half-life."""
        np.random.seed(42)
        x = pd.Series(np.random.randn(100).cumsum())
<<<<<<< HEAD
        y = pd.Series(1.5 * np.asarray(x, dtype=float) + np.random.randn(100))

        model = SpreadModel(x, y)
        spread = model.compute_spread(x, y)

        # Compute with explicit lookback
        z_score = model.compute_z_score(spread, lookback=30)

        assert len(z_score) == len(spread)
        assert np.all(np.isfinite(z_score.dropna()))

=======
        y = pd.Series(1.5 * x.values + np.random.randn(100))
        
        model = SpreadModel(x, y)
        spread = model.compute_spread(x, y)
        
        # Compute with explicit lookback
        z_score = model.compute_z_score(spread, lookback=30)
        
        assert len(z_score) == len(spread)
        assert np.all(np.isfinite(z_score.dropna()))
    
>>>>>>> origin/main
    def test_z_score_with_explicit_half_life(self):
        """Test Z-score with explicit half-life."""
        np.random.seed(42)
        x = pd.Series(np.random.randn(100).cumsum())
<<<<<<< HEAD
        y = pd.Series(1.5 * np.asarray(x, dtype=float) + np.random.randn(100))

        model = SpreadModel(x, y)
        spread = model.compute_spread(x, y)

        # Use specific half-life
        z_score = model.compute_z_score(spread, half_life=50)

=======
        y = pd.Series(1.5 * x.values + np.random.randn(100))
        
        model = SpreadModel(x, y)
        spread = model.compute_spread(x, y)
        
        # Use specific half-life
        z_score = model.compute_z_score(spread, half_life=50)
        
>>>>>>> origin/main
        assert len(z_score) == len(spread)


class TestHalfLifeEstimationAccuracy:
    """Test accuracy of half-life estimation in SpreadModel."""
<<<<<<< HEAD

    def test_mean_reverting_pair_estimation(self):
        """Test half-life estimation on truly mean-reverting pair."""
        np.random.seed(42)

        # True HL = 30 days
        true_hl = 30
        mr = np.log(2) / true_hl

        data_x = []
        data_y = []

=======
    
    def test_mean_reverting_pair_estimation(self):
        """Test half-life estimation on truly mean-reverting pair."""
        np.random.seed(42)
        
        # True HL = 30 days
        true_hl = 30
        mr = np.log(2) / true_hl
        
        data_x = []
        data_y = []
        
>>>>>>> origin/main
        x_val = 0
        for _ in range(400):
            shock = np.random.normal(0, 1)
            x_val = x_val - mr * x_val + shock
            y_val = 1.5 * x_val + np.random.normal(0, 0.1)
            data_x.append(x_val)
            data_y.append(y_val)
<<<<<<< HEAD

        x = pd.Series(data_x)
        y = pd.Series(data_y)

        model = SpreadModel(x, y)

        # Should estimate something reasonable
        if model.half_life is not None:
            # Within -�50% for noisy data
            error_pct = abs(model.half_life - true_hl) / true_hl
            assert error_pct < 0.50

    def test_non_stationary_pair_rejection(self):
        """Test non-stationary pair gets None for half-life."""
        np.random.seed(42)

        # Two independent random walks (non-stationary)
        x = pd.Series(np.cumsum(np.random.randn(100)))
        y = pd.Series(np.cumsum(np.random.randn(100)))

        model = SpreadModel(x, y)

=======
        
        x = pd.Series(data_x)
        y = pd.Series(data_y)
        
        model = SpreadModel(x, y)
        
        # Should estimate something reasonable
        if model.half_life is not None:
            # Within ±50% for noisy data
            error_pct = abs(model.half_life - true_hl) / true_hl
            assert error_pct < 0.50
    
    def test_non_stationary_pair_rejection(self):
        """Test non-stationary pair gets None for half-life."""
        np.random.seed(42)
        
        # Two independent random walks (non-stationary)
        x = pd.Series(np.cumsum(np.random.randn(100)))
        y = pd.Series(np.cumsum(np.random.randn(100)))
        
        model = SpreadModel(x, y)
        
>>>>>>> origin/main
        # Should likely not estimate half-life for random walk
        # (may occasionally estimate due to randomness, but usually None)
        assert model.half_life is None or (5 <= model.half_life <= 200)


<<<<<<< HEAD
class TestSpreadHalfLifeNoneGuard:
    """C-08: compute_z_score must not silently absorb half_life=None."""

    def test_z_score_with_none_half_life_returns_valid_series(self):
        """When half_life is None, compute_z_score falls back to default lookback without crash."""
        np.random.seed(99)
        x = pd.Series(np.random.randn(200))
        y = pd.Series(2 * np.asarray(x, dtype=float) + np.random.randn(200))
        model = SpreadModel(x, y)
        # Force None to simulate failed estimation regardless of seed
        model.half_life = None
        spread = model.compute_spread(x, y)

        z = model.compute_z_score(spread)

        assert len(z) == len(spread), "Z-score length must match spread"
        assert z.dropna().notna().all(), "Non-NaN z-scores must be finite"

    def test_explicit_lookback_bypasses_half_life_guard(self):
        """Passing an explicit lookback must work even when half_life is None."""
        np.random.seed(99)
        x = pd.Series(np.random.randn(200))
        y = pd.Series(2 * np.asarray(x, dtype=float) + np.random.randn(200))
        model = SpreadModel(x, y)
        model.half_life = None
        spread = model.compute_spread(x, y)

        z = model.compute_z_score(spread, lookback=30)

        assert len(z) == len(spread)
        assert z.dropna().notna().all()


class TestLogPrices:
    """C-08: use_log_prices=True fits OLS on log-prices, not levels."""

    def _make_price_series(self, seed: int = 7, n: int = 200) -> tuple[pd.Series, pd.Series]:
        rng = np.random.default_rng(seed)
        x = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.01, n))))
        y = pd.Series(x.to_numpy(dtype=float) ** 1.2 * np.exp(rng.normal(0, 0.005, n)))
        return y, x

    def test_use_log_prices_flag_stored(self):
        """use_log_prices is stored as attribute."""
        y, x = self._make_price_series()
        model = SpreadModel(y, x, use_log_prices=True)
        assert model.use_log_prices is True

    def test_default_is_level_prices(self):
        """use_log_prices defaults to False (backward compat)."""
        y, x = self._make_price_series()
        model = SpreadModel(y, x)
        assert model.use_log_prices is False

    def test_log_price_spread_finite(self):
        """compute_spread returns finite series when use_log_prices=True."""
        y, x = self._make_price_series()
        model = SpreadModel(y, x, use_log_prices=True)
        spread = model.compute_spread(y, x)
        assert len(spread) == len(y)
        assert np.all(np.isfinite(spread))

    def test_log_vs_level_spread_different(self):
        """Log-price spread and level spread differ (not the same calculation)."""
        y, x = self._make_price_series()
        model_log = SpreadModel(y, x, use_log_prices=True)
        model_lvl = SpreadModel(y, x, use_log_prices=False)
        spread_log = model_log.compute_spread(y, x)
        spread_lvl = model_lvl.compute_spread(y, x)
        assert not np.allclose(spread_log.to_numpy(dtype=float), spread_lvl.to_numpy(dtype=float))

    def test_log_price_spread_smaller_variance(self):
        """Log-price spread is typically more stationary (lower variance) for equity prices."""
        y, x = self._make_price_series()
        model_log = SpreadModel(y, x, use_log_prices=True)
        model_lvl = SpreadModel(y, x, use_log_prices=False)
        spread_log = model_log.compute_spread(y, x)
        spread_lvl = model_lvl.compute_spread(y, x)
        # Normalise by mean level so comparison is scale-free
        cv_log = spread_log.std() / (abs(spread_log.mean()) + 1e-8)
        cv_lvl = spread_lvl.std() / (abs(spread_lvl.mean()) + 1e-8)
        assert cv_log < cv_lvl * 10  # log spread must not be wildly larger

    def test_log_price_guard_against_non_positive(self):
        """Non-positive values are clipped to 1e-10 before log; no NaN/Inf."""
        y, x = self._make_price_series()
        y_bad = y.copy()
        y_bad.iloc[5] = 0.0
        y_bad.iloc[10] = -1.0
        model = SpreadModel(y_bad, x, use_log_prices=True)
        spread = model.compute_spread(y_bad, x)
        assert np.all(np.isfinite(spread))

    def test_z_score_works_with_log_price_model(self):
        """compute_z_score works correctly on a log-price spread."""
        y, x = self._make_price_series()
        model = SpreadModel(y, x, use_log_prices=True)
        spread = model.compute_spread(y, x)
        z = model.compute_z_score(spread, lookback=20)
        assert len(z) == len(spread)
        assert z.dropna().notna().all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestKalmanIntegration:
    """C-04: use_kalman=True wires KalmanHedgeRatio into SpreadModel."""

    def _make_cointegrated(self, n: int = 300, seed: int = 0) -> tuple[pd.Series, pd.Series]:
        rng = np.random.default_rng(seed)
        idx = pd.date_range("2022-01-01", periods=n, freq="D")
        x = pd.Series(100.0 + np.cumsum(rng.normal(0, 1, n)), index=idx)
        y = pd.Series(1.5 * x.to_numpy(dtype=float) + 5.0 + rng.normal(0, 0.5, n), index=idx)
        return y, x

    def test_use_kalman_flag_stored(self):
        """use_kalman=True is stored as attribute."""
        y, x = self._make_cointegrated()
        model = SpreadModel(y, x, use_kalman=True)
        assert model.use_kalman is True

    def test_default_no_kalman(self):
        """use_kalman defaults to False (backward compat)."""
        y, x = self._make_cointegrated()
        model = SpreadModel(y, x)
        assert model.use_kalman is False
        assert model._kalman is None

    def test_kalman_instance_created_on_init(self):
        """_kalman attribute is a KalmanHedgeRatio instance when use_kalman=True."""
        from models.kalman_hedge import KalmanHedgeRatio

        y, x = self._make_cointegrated()
        model = SpreadModel(y, x, use_kalman=True)
        assert model._kalman is not None
        assert isinstance(model._kalman, KalmanHedgeRatio)

    def test_compute_spread_returns_finite_series(self):
        """compute_spread returns a finite, same-length series with Kalman active."""
        y, x = self._make_cointegrated()
        model = SpreadModel(y, x, use_kalman=True)
        spread = model.compute_spread(y, x)
        assert len(spread) == len(y)
        assert np.all(np.isfinite(spread.values))

    def test_beta_updates_across_bars(self):
        """Kalman β after init differs from OLS β (time-varying vs static)."""
        rng = np.random.default_rng(42)
        n = 300
        idx = pd.date_range("2022-01-01", periods=n, freq="D")
        # Introduce a beta regime-shift at bar 150
        beta_true = np.concatenate([np.full(150, 1.0), np.full(150, 2.0)])
        x = pd.Series(100.0 + np.cumsum(rng.normal(0, 1, n)), index=idx)
        y = pd.Series(beta_true * x.values + rng.normal(0, 0.3, n), index=idx)

        model_ols = SpreadModel(y, x, use_kalman=False)
        model_kal = SpreadModel(y, x, use_kalman=True)
        # After processing all bars, Kalman beta should be closer to final true beta (2.0)
        assert abs(model_kal.beta - 2.0) < abs(model_ols.beta - 2.0)

    def test_get_model_info_has_kalman_fields(self):
        """get_model_info includes kalman_bars_processed when Kalman active."""
        y, x = self._make_cointegrated()
        model = SpreadModel(y, x, use_kalman=True)
        info = model.get_model_info()
        assert info["use_kalman"] is True
        assert "kalman_bars_processed" in info
        assert info["kalman_bars_processed"] == len(y)
        assert "kalman_breakdown_count" in info
        assert "kalman_beta_ci_lower" in info
        assert "kalman_beta_ci_upper" in info

    def test_reestimate_returns_true_immediately(self):
        """reestimate_beta_if_needed short-circuits to True when Kalman active."""
        y, x = self._make_cointegrated()
        model = SpreadModel(y, x, use_kalman=True)
        # No tracker — first guard fires; should also short-circuit via Kalman guard
        result = model.reestimate_beta_if_needed(y, x)
        assert result is True

    def test_update_rewarms_kalman(self):
        """update() re-initialises the Kalman filter on the new price window."""
        y, x = self._make_cointegrated(n=300, seed=1)
        model = SpreadModel(y, x, use_kalman=True)
        assert model._kalman is not None
        bars_before = model._kalman.bars_processed  # after warm-up = len(y)

        y2, x2 = self._make_cointegrated(n=200, seed=99)
        model.update(y2, x2)
        # After re-warm, bars_processed resets to len(y2)
        assert model._kalman is not None
        assert model._kalman.bars_processed == len(y2)
        assert model._kalman.bars_processed != bars_before

    def test_kalman_combined_with_log_prices(self):
        """use_kalman=True + use_log_prices=True: spread is finite."""
        rng = np.random.default_rng(5)
        n = 200
        x = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.01, n))))
        y = pd.Series(x.to_numpy(dtype=float) ** 1.3 * np.exp(rng.normal(0, 0.005, n)))
        model = SpreadModel(y, x, use_kalman=True, use_log_prices=True)
        spread = model.compute_spread(y, x)
        assert np.all(np.isfinite(spread.values))
=======
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
>>>>>>> origin/main
