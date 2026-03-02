"""
Test dynamic hedge ratio reestimation tracking.

Validates that:
1. - (hedge ratio) is tracked per pair over time
2. Monthly reestimation is triggered correctly
3. - drift > 10% flags pair as deprecated
4. Deprecated pairs are properly skipped in signal generation
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from models.hedge_ratio_tracker import HedgeRatioTracker
from models.spread import SpreadModel
from models.adaptive_thresholds import DynamicSpreadModel


class TestHedgeRatioTracker:
    """Test hedge ratio tracking and drift detection."""
    
    def test_tracker_initialization(self):
        """Test tracker initializes correctly."""
        tracker = HedgeRatioTracker(reestimation_frequency_days=30)
        
        assert tracker.reestimation_frequency_days == 30
        assert len(tracker.pair_betas) == 0
        assert len(tracker.deprecated_pairs) == 0
    
    def test_record_initial_beta(self):
        """Test recording initial - estimate."""
        tracker = HedgeRatioTracker()
        
        tracker.record_initial_beta("AAPL_MSFT", 2.5)
        
        assert "AAPL_MSFT" in tracker.pair_betas
        assert len(tracker.pair_betas["AAPL_MSFT"]) == 1
        
        record = tracker.pair_betas["AAPL_MSFT"][0]
        assert record[1] == 2.5  # beta value
        assert record[2] is True  # is_stable
    
    def test_reestimate_too_soon(self):
        """Test that reestimation is skipped if not enough time has passed."""
        tracker = HedgeRatioTracker(reestimation_frequency_days=30)
        
        # Record initial -
        tracker.record_initial_beta("AAPL_MSFT", 2.5)
        
        # Reestimate immediately (same day) - should skip
        new_beta, is_stable = tracker.reestimate_if_needed("AAPL_MSFT", 2.6)
        
        assert new_beta == 2.5  # Should return old -
        assert is_stable is True  # Should report as stable
        assert len(tracker.pair_betas["AAPL_MSFT"]) == 1  # No new record
    
    def test_reestimate_stable_drift(self):
        """Test reestimation when - drift is within tolerance."""
        tracker = HedgeRatioTracker(reestimation_frequency_days=1)
        
        tracker.record_initial_beta("AAPL_MSFT", 2.5)
        
        # Simulate 40 days elapsed + small drift (5%)
        tracker.pair_betas["AAPL_MSFT"][0] = (
            datetime.now() - timedelta(days=40),
            2.5,
            True,
            None
        )
        
        new_beta = 2.625  # 5% drift
        returned_beta, is_stable = tracker.reestimate_if_needed("AAPL_MSFT", new_beta, drift_tolerance_pct=10.0)
        
        assert returned_beta == new_beta  # Updated -
        assert is_stable is True  # Within tolerance
        assert len(tracker.pair_betas["AAPL_MSFT"]) == 2  # New record added
    
    def test_reestimate_unstable_drift(self):
        """Test that pair is deprecated when - drifts beyond tolerance."""
        tracker = HedgeRatioTracker(reestimation_frequency_days=1)
        
        tracker.record_initial_beta("AAPL_MSFT", 2.5)
        
        # Simulate 40 days elapsed + high drift (15%)
        tracker.pair_betas["AAPL_MSFT"][0] = (
            datetime.now() - timedelta(days=40),
            2.5,
            True,
            None
        )
        
        new_beta = 2.875  # 15% drift (too high)
        returned_beta, is_stable = tracker.reestimate_if_needed("AAPL_MSFT", new_beta, drift_tolerance_pct=10.0)
        
        assert returned_beta == new_beta  # Return new - for reference
        assert is_stable is False  # Beyond tolerance
        assert tracker.is_pair_deprecated("AAPL_MSFT")  # Pair flagged deprecated
    
    def test_skip_deprecated_pair(self):
        """Test that reestimation skips deprecated pairs."""
        tracker = HedgeRatioTracker()
        
        # Manually deprecate a pair
        tracker.deprecated_pairs["AAPL_MSFT"] = "Test deprecation"
        
        # Try to reestimate
        new_beta, is_stable = tracker.reestimate_if_needed("AAPL_MSFT", 3.0)
        
        assert new_beta is None  # Skipped
        assert is_stable is False  # Not stable


class TestHedgeRatioTrackerIntegration:
    """Test hedge ratio tracking integration with spread models."""
    
    def test_spread_model_with_tracker(self):
        """Test SpreadModel integration with tracker."""
        tracker = HedgeRatioTracker()
        
        # Generate synthetic cointegrated data
        np.random.seed(42)
        n = 100
        x_vals = np.cumsum(np.random.normal(0, 1, n)) + 100
        y_vals = 2 * x_vals + np.random.normal(0, 1, n)  # - = 2
        
        x = pd.Series(x_vals, name='X')
        y = pd.Series(y_vals, name='Y')
        
        # Create spread model with tracker
        model = SpreadModel(y, x, pair_key='X_Y', hedge_ratio_tracker=tracker)
        
        # Check that initial - was recorded
        assert tracker.pair_betas['X_Y'][0][1] == pytest.approx(model.beta, abs=0.01)
    
    def test_dynamic_spread_model_with_tracker(self):
        """Test DynamicSpreadModel integration with hedge ratio tracking."""
        tracker = HedgeRatioTracker()
        
        # Generate synthetic data
        np.random.seed(42)
        n = 100
        x_vals = np.cumsum(np.random.normal(0, 1, n)) + 100
        y_vals = 1.5 * x_vals + np.random.normal(0, 1, n)  # - = 1.5
        
        x = pd.Series(x_vals, name='X')
        y = pd.Series(y_vals, name='Y')
        
        # Create dynamic spread model with tracker
        DynamicSpreadModel(
            y, x,
            half_life=20.0,
            pair_key='X_Y',
            hedge_ratio_tracker=tracker
        )
        
        # Verify tracking
        assert not tracker.is_pair_deprecated('X_Y')
        assert 'X_Y' in tracker.pair_betas
    
    def test_tracker_summary(self):
        """Test tracker summary generation."""
        tracker = HedgeRatioTracker()
        
        # Record several pairs
        tracker.record_initial_beta("AAPL_MSFT", 2.5)
        tracker.record_initial_beta("AAPL_XOM", 1.8)
        tracker.record_initial_beta("GOOGL_WFC", 1.2)
        
        # Deprecate one
        tracker.deprecated_pairs["AAPL_XOM"] = "Beta drift"
        
        summary = tracker.get_summary()
        
        assert summary['total_pairs_tracked'] == 3
        assert summary['active_pairs'] == 2
        assert summary['deprecated_pairs'] == 1
        assert 'AAPL_XOM' in summary['deprecated_pair_keys']


class TestHedgeRatioDriftScenarios:
    """Test realistic - drift scenarios."""
    
    def test_stable_pair_over_months(self):
        """Test tracking a stable pair over multiple reestimation periods."""
        tracker = HedgeRatioTracker(reestimation_frequency_days=1)
        
        # Initial - = 2.0
        tracker.record_initial_beta("AAPL_MSFT", 2.0)
        
        # Month 1: - reestimated to 2.02 (1% drift)
        tracker.pair_betas["AAPL_MSFT"][0] = (
            datetime.now() - timedelta(days=30),
            2.0,
            True,
            None
        )
        b1, s1 = tracker.reestimate_if_needed("AAPL_MSFT", 2.02, drift_tolerance_pct=10.0)
        assert s1 is True
        
        # Month 2: - reestimated to 2.04 (2% drift from previous)
        tracker.pair_betas["AAPL_MSFT"][-1] = (
            datetime.now() - timedelta(days=30),
            2.02,
            True,
            1.0  # Approximate drift
        )
        b2, s2 = tracker.reestimate_if_needed("AAPL_MSFT", 2.04, drift_tolerance_pct=10.0)
        assert s2 is True
        
        # Monitor that pair has not been deprecated
        assert not tracker.is_pair_deprecated("AAPL_MSFT")
    
    def test_degrading_pair(self):
        """Test detection of pair relationship degradation."""
        tracker = HedgeRatioTracker(reestimation_frequency_days=1)
        
        # Initial - = 2.0
        tracker.record_initial_beta("AAPL_MSFT", 2.0)
        
        # Month 1: Slight drift (3%)
        tracker.pair_betas["AAPL_MSFT"][0] = (
            datetime.now() - timedelta(days=30),
            2.0,
            True,
            None
        )
        b1, s1 = tracker.reestimate_if_needed("AAPL_MSFT", 2.06)
        assert s1 is True
        
        # Month 2: Larger drift (12% total) - relationship breaking down
        tracker.pair_betas["AAPL_MSFT"][-1] = (
            datetime.now() - timedelta(days=30),
            2.06,
            True,
            3.0  # 3% drift from month 1
        )
        b2, s2 = tracker.reestimate_if_needed("AAPL_MSFT", 2.31, drift_tolerance_pct=10.0)
        
        # Should be flagged as unstable (12% drift > 10% tolerance)
        assert s2 is False
        assert tracker.is_pair_deprecated("AAPL_MSFT")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
