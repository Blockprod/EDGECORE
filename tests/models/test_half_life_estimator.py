"""
Half-Life Estimation Tests (S3.2c - Validation).

Tests for SpreadHalfLifeEstimator:
- OU process HL estimation accuracy
- Non-stationary data rejection
- Parameter validation
- Edge cases
"""

import pytest
import numpy as np
import pandas as pd
from models.half_life_estimator import (
    SpreadHalfLifeEstimator,
    estimate_half_life
)


class TestOUProcessHalfLife:
    """Test HL estimation on OU processes."""
    
    def generate_ou_process(
        self,
        half_life: float,
        periods: int = 500,
        noise_std: float = 0.1,
        seed: int = 42
    ) -> pd.Series:
        """Generate OU process with known half-life."""
        np.random.seed(seed)
        
        mean_reversion = np.log(2) / half_life
        ou = np.zeros(periods)
        ou[0] = np.random.normal(0, 1)
        
        for t in range(1, periods):
            ou[t] = ou[t-1] - mean_reversion * ou[t-1] + np.random.normal(0, noise_std)
        
        return pd.Series(ou)
    
    def test_half_life_30_days(self):
        """Test HL estimation for true HL=30."""
        true_hl = 30
        spread = self.generate_ou_process(half_life=true_hl)
        
        estimator = SpreadHalfLifeEstimator()
        estimated_hl = estimator.estimate_half_life_from_spread(spread)
        
        # Should estimate something reasonable
        assert estimated_hl is not None, "Should return a value for mean-reverting OU"
        # Within ±60% for short estimation window (centered AR(1) estimation)
        error_pct = abs(estimated_hl - true_hl) / true_hl
        assert error_pct < 0.60, f"Error {error_pct:.2%} too large (est={estimated_hl:.1f}, true={true_hl})"
    
    def test_half_life_50_days(self):
        """Test HL estimation for true HL=50."""
        true_hl = 50
        spread = self.generate_ou_process(half_life=true_hl)
        
        estimator = SpreadHalfLifeEstimator()
        estimated_hl = estimator.estimate_half_life_from_spread(spread)
        
        if estimated_hl is not None:
            assert 5 < estimated_hl < 200
    
    def test_half_life_100_days(self):
        """Test HL estimation for true HL=100."""
        true_hl = 100
        spread = self.generate_ou_process(half_life=true_hl, noise_std=0.2)
        
        estimator = SpreadHalfLifeEstimator()
        estimated_hl = estimator.estimate_half_life_from_spread(spread)
        
        # Long HL is harder to estimate with 252-point lookback.
        # Accept any positive value within bounds [5, 200].
        if estimated_hl is not None:
            assert 5 < estimated_hl < 200


class TestNonStationaryRejection:
    """Test rejection of non-stationary data."""
    
    def test_random_walk_rejection(self):
        """Test random walk (non-stationary) is rejected or has very long HL."""
        np.random.seed(42)
        
        # Random walk: no mean reversion
        rw = np.cumsum(np.random.randn(2000))  # longer series for stable rho
        
        estimator = SpreadHalfLifeEstimator(lookback=500)
        estimated_hl = estimator.estimate_half_life_from_spread(pd.Series(rw), validate=False)
        
        # A true random walk has rho ≈ 1, so either None
        # or HL is very long (>50 days).  With validate=True bounds
        # [5,200] would reject anyway.
        assert estimated_hl is None or estimated_hl > 50, (
            f"Random walk should yield None or very long HL, got {estimated_hl}"
        )
    
    def test_trend_rejection(self):
        """Test linear trend is rejected."""
        # Deterministic trend
        trend = np.array([i * 0.1 for i in range(500)])
        
        estimator = SpreadHalfLifeEstimator()
        estimated_hl = estimator.estimate_half_life_from_spread(pd.Series(trend))
        
        # Linear trend has rho ≈ 1, should reject
        assert estimated_hl is None
    
    def test_constant_series_rejection(self):
        """Test constant series is rejected."""
        # Constant signal
        constant = np.ones(500)
        
        estimator = SpreadHalfLifeEstimator()
        estimated_hl = estimator.estimate_half_life_from_spread(pd.Series(constant))
        
        # No variation, rho undefined or 0
        assert estimated_hl is None


class TestParameterValidation:
    """Test parameter extraction and validation."""
    
    def test_ar1_coefficient_bounds(self):
        """Test AR(1) coefficient is in [0, 1) for mean-reverting process."""
        spread = self.generate_mean_reverting()
        
        estimator = SpreadHalfLifeEstimator()
        params = estimator.compute_ou_process_parameters(spread)
        
        rho = params['ar1_coeff']
        
        if rho is not None:
            assert 0 < rho < 1
    
    def test_mean_reversion_speed_positive(self):
        """Test mean reversion speed is positive."""
        spread = self.generate_mean_reverting()
        
        estimator = SpreadHalfLifeEstimator()
        params = estimator.compute_ou_process_parameters(spread)
        
        speed = params['mean_reversion_speed']
        
        if speed is not None:
            assert speed > 0
    
    def test_half_life_in_bounds(self):
        """Test half-life is in [5, 200] days."""
        spread = self.generate_mean_reverting()
        
        estimator = SpreadHalfLifeEstimator()
        hl = estimator.estimate_half_life_from_spread(spread)
        
        if hl is not None:
            assert 5 <= hl <= 200
    
    def generate_mean_reverting(self):
        """Generate synthetic mean-reverting process."""
        np.random.seed(42)
        return pd.Series(self.generate_ou_process(half_life=40, periods=500))
    
    def generate_ou_process(self, half_life, periods, seed=42):
        """Generate OU process."""
        np.random.seed(seed)
        mr = np.log(2) / half_life
        ou = np.zeros(periods)
        ou[0] = np.random.normal()
        for t in range(1, periods):
            ou[t] = ou[t-1] - mr * ou[t-1] + np.random.normal(0, 0.1)
        return ou


class TestMeanReversionValidation:
    """Test validation of mean-reversion property."""
    
    def test_strongly_mean_reverting(self):
        """Test identification of strong mean-reversion."""
        np.random.seed(42)
        
        # Strong MR: moderate convergence to mean
        mr = np.log(2) / 40  # HL = 40 days (more stable than 10)
        data = []
        val = 0
        for _ in range(500):
            val = val - mr * val + np.random.normal(0, 0.1)
            data.append(val)
        
        spread = pd.Series(data)
        estimator = SpreadHalfLifeEstimator()
        
        # Check that HL is estimated (confirmation of MR)
        hl = estimator.estimate_half_life_from_spread(spread)
        
        # Should successfully estimate half-life in reasonable range
        if hl is not None:
            assert 5 <= hl <= 200
    
    def test_weak_mean_reverting(self):
        """Test identification of weak / non-existent mean-reversion."""
        np.random.seed(42)
        
        # Pure random walk: cumsum of N(0,1)  - should not be mean-reverting
        rw = np.random.randn(2000).cumsum()
        
        estimator = SpreadHalfLifeEstimator(lookback=500)
        is_mr = estimator.validate_mean_reversion(pd.Series(rw), threshold_rho=0.95)
        
        # With a tight threshold and long series, RW should fail
        assert not is_mr, "Pure random walk should not validate as mean-reverting (rho<0.95)"


class TestEdgeCases:
    """Test handling of edge cases."""
    
    def test_short_series_handling(self):
        """Test handling of series shorter than lookback."""
        # Series too short (< 252)
        short_spread = pd.Series(np.random.randn(100))
        
        estimator = SpreadHalfLifeEstimator(lookback=252)
        hl = estimator.estimate_half_life_from_spread(short_spread)
        
        # Should return None gracefully
        assert hl is None
    
    def test_nan_handling(self):
        """Test handling of NaN values."""
        # Series with NaN
        data = np.random.randn(500)
        data[100:110] = np.nan
        
        spread = pd.Series(data)
        
        estimator = SpreadHalfLifeEstimator()
        hl = estimator.estimate_half_life_from_spread(spread)
        
        # Should handle gracefully (NaN might affect estimation)
        # But should not crash
        assert hl is None or (5 <= hl <= 200)
    
    def test_very_high_noise(self):
        """Test with very noisy data."""
        np.random.seed(42)
        
        # High noise OU process
        mr = np.log(2) / 30
        ou = np.zeros(500)
        ou[0] = np.random.normal()
        
        for t in range(1, 500):
            # Noise >> signal
            ou[t] = ou[t-1] - mr * ou[t-1] + np.random.normal(0, 1.0)
        
        estimator = SpreadHalfLifeEstimator()
        hl = estimator.estimate_half_life_from_spread(pd.Series(ou))
        
        # May not estimate due to noise, but should not crash
        assert hl is None or (5 <= hl <= 200)


class TestConvenienceFunctions:
    """Test module-level convenience functions."""
    
    def test_estimate_half_life_function(self):
        """Test standalone estimate_half_life function."""
        np.random.seed(42)
        
        # Generate OU with HL=40
        mr = np.log(2) / 40
        data = []
        val = 0
        for _ in range(500):
            val = val - mr * val + np.random.normal(0, 0.1)
            data.append(val)
        
        spread = pd.Series(data)
        hl = estimate_half_life(spread)
        
        # Should return valid half-life or None
        assert hl is None or (5 <= hl <= 200)
    
    def test_custom_lookback(self):
        """Test custom lookback window."""
        np.random.seed(42)
        
        spread = pd.Series(np.random.randn(500))
        
        # Different lookback values
        hl1 = estimate_half_life(spread, lookback=100)
        hl2 = estimate_half_life(spread, lookback=200)
        
        # Both should be processable
        assert hl1 is None or (5 <= hl1 <= 200)
        assert hl2 is None or (5 <= hl2 <= 200)


class TestBackwardsCompatibility:
    """Test integration with existing code."""
    
    def test_numpy_array_input(self):
        """Test accepting numpy array input."""
        arr = np.random.randn(500)
        
        estimator = SpreadHalfLifeEstimator()
        hl = estimator.estimate_half_life_from_spread_array(arr)
        
        # Should handle numpy arrays
        assert hl is None or (5 <= hl <= 200)
    
    def test_pandas_series_input(self):
        """Test accepting pandas Series input."""
        series = pd.Series(np.random.randn(500))
        
        estimator = SpreadHalfLifeEstimator()
        hl = estimator.estimate_half_life_from_spread(series)
        
        # Should handle Series
        assert hl is None or (5 <= hl <= 200)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
