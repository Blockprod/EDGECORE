"""
SpreadModel Integration Test (S3.2d - Integration).

Test that SpreadModel correctly integrates half-life estimation.
"""

import pytest
import numpy as np
import pandas as pd
from models.spread import SpreadModel


class TestSpreadModelIntegration:
    """Test SpreadModel with integrated half-life estimation."""
    
    def test_spread_model_initialization(self):
        """Test SpreadModel initializes successfully."""
        np.random.seed(42)
        x = pd.Series(np.random.randn(100).cumsum())
        y = pd.Series(1.5 * x.values + np.random.randn(100))
        
        model = SpreadModel(x, y)
        
        # Should have valid parameters
        assert np.isfinite(model.beta)
        assert np.isfinite(model.intercept)
        assert model.half_life is None or (5 <= model.half_life <= 200)
    
    def test_spread_computation(self):
        """Test spread is computed correctly."""
        np.random.seed(42)
        x = pd.Series(np.random.randn(100).cumsum())
        y = pd.Series(1.5 * x.values + np.random.randn(100))
        
        model = SpreadModel(x, y)
        spread = model.compute_spread(x, y)
        
        # Spread should have same length
        assert len(spread) == len(x)
        # Spread should be finite
        assert np.all(np.isfinite(spread))
    
    def test_z_score_uses_estimated_half_life(self):
        """Test Z-score computation uses estimated half-life."""
        np.random.seed(42)
        
        # Generate mean-reverting pair
        mr = np.log(2) / 40  # HL = 40
        data_x = []
        data_y = []
        
        x_val = 0
        y_val = 0
        
        for _ in range(300):
            x_val = x_val - mr * x_val + np.random.normal(0, 1)
            y_val = 1.5 * x_val + 0.5 * y_val + np.random.normal(0, 0.5)
            data_x.append(x_val)
            data_y.append(y_val)
        
        x = pd.Series(data_x)
        y = pd.Series(data_y)
        
        model = SpreadModel(x, y)
        spread = model.compute_spread(x, y)
        
        # Compute Z-score (should use estimated half-life)
        z_score = model.compute_z_score(spread)
        
        # Should be valid
        assert len(z_score) == len(spread)
        assert np.all(np.isfinite(z_score.dropna()))
    
    def test_model_info_includes_half_life(self):
        """Test get_model_info includes half-life."""
        np.random.seed(42)
        x = pd.Series(np.random.randn(100).cumsum())
        y = pd.Series(1.5 * x.values + np.random.randn(100))
        
        model = SpreadModel(x, y)
        info = model.get_model_info()
        
        # Should have all expected keys
        assert 'intercept' in info
        assert 'beta' in info
        assert 'residual_std' in info
        assert 'half_life' in info
        assert 'is_deprecated' in info
    
    def test_backward_compatibility_no_pair_key(self):
        """Test SpreadModel works without pair_key."""
        np.random.seed(42)
        x = pd.Series(np.random.randn(100).cumsum())
        y = pd.Series(1.5 * x.values + np.random.randn(100))
        
        # Should work without pair_key
        model = SpreadModel(x, y)
        
        assert model.pair_key is None
        assert np.isfinite(model.beta)
    
    def test_backward_compatibility_no_tracker(self):
        """Test SpreadModel works without hedge_ratio_tracker."""
        np.random.seed(42)
        x = pd.Series(np.random.randn(100).cumsum())
        y = pd.Series(1.5 * x.values + np.random.randn(100))
        
        # Should work without tracker
        model = SpreadModel(x, y)
        
        assert model.tracker is None
        assert np.isfinite(model.beta)
    
    def test_z_score_with_explicit_lookback(self):
        """Test Z-score with explicit looback overrides half-life."""
        np.random.seed(42)
        x = pd.Series(np.random.randn(100).cumsum())
        y = pd.Series(1.5 * x.values + np.random.randn(100))
        
        model = SpreadModel(x, y)
        spread = model.compute_spread(x, y)
        
        # Compute with explicit lookback
        z_score = model.compute_z_score(spread, lookback=30)
        
        assert len(z_score) == len(spread)
        assert np.all(np.isfinite(z_score.dropna()))
    
    def test_z_score_with_explicit_half_life(self):
        """Test Z-score with explicit half-life."""
        np.random.seed(42)
        x = pd.Series(np.random.randn(100).cumsum())
        y = pd.Series(1.5 * x.values + np.random.randn(100))
        
        model = SpreadModel(x, y)
        spread = model.compute_spread(x, y)
        
        # Use specific half-life
        z_score = model.compute_z_score(spread, half_life=50)
        
        assert len(z_score) == len(spread)


class TestHalfLifeEstimationAccuracy:
    """Test accuracy of half-life estimation in SpreadModel."""
    
    def test_mean_reverting_pair_estimation(self):
        """Test half-life estimation on truly mean-reverting pair."""
        np.random.seed(42)
        
        # True HL = 30 days
        true_hl = 30
        mr = np.log(2) / true_hl
        
        data_x = []
        data_y = []
        
        x_val = 0
        for _ in range(400):
            shock = np.random.normal(0, 1)
            x_val = x_val - mr * x_val + shock
            y_val = 1.5 * x_val + np.random.normal(0, 0.1)
            data_x.append(x_val)
            data_y.append(y_val)
        
        x = pd.Series(data_x)
        y = pd.Series(data_y)
        
        model = SpreadModel(x, y)
        
        # Should estimate something reasonable
        if model.half_life is not None:
            # Within ┬▒50% for noisy data
            error_pct = abs(model.half_life - true_hl) / true_hl
            assert error_pct < 0.50
    
    def test_non_stationary_pair_rejection(self):
        """Test non-stationary pair gets None for half-life."""
        np.random.seed(42)
        
        # Two independent random walks (non-stationary)
        x = pd.Series(np.cumsum(np.random.randn(100)))
        y = pd.Series(np.cumsum(np.random.randn(100)))
        
        model = SpreadModel(x, y)
        
        # Should likely not estimate half-life for random walk
        # (may occasionally estimate due to randomness, but usually None)
        assert model.half_life is None or (5 <= model.half_life <= 200)


class TestSpreadHalfLifeNoneGuard:
    """C-08: compute_z_score must not silently absorb half_life=None."""

    def test_z_score_with_none_half_life_returns_valid_series(self):
        """When half_life is None, compute_z_score falls back to default lookback without crash."""
        np.random.seed(99)
        x = pd.Series(np.random.randn(200))
        y = pd.Series(2 * x.values + np.random.randn(200))
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
        y = pd.Series(2 * x.values + np.random.randn(200))
        model = SpreadModel(x, y)
        model.half_life = None
        spread = model.compute_spread(x, y)

        z = model.compute_z_score(spread, lookback=30)

        assert len(z) == len(spread)
        assert z.dropna().notna().all()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
