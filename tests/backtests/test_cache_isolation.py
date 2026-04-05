<<<<<<< HEAD
﻿"""
=======
"""
>>>>>>> origin/main
Test cache isolation in walk-forward validation.

Verifies that pair cache is properly disabled/enabled and cleared between
walk-forward periods, ensuring each period discovers pairs fresh from its data.
"""

<<<<<<< HEAD
import numpy as np
import pandas as pd
import pytest

from backtests.walk_forward import WalkForwardBacktester, split_walk_forward
from strategies.pair_trading import PairTradingStrategy
=======
import pytest
import pandas as pd
import numpy as np

from strategies.pair_trading import PairTradingStrategy
from backtests.walk_forward import WalkForwardBacktester, split_walk_forward
>>>>>>> origin/main


class TestCacheIsolation:
    """Test pair caching is properly isolated during walk-forward testing."""
<<<<<<< HEAD

    def test_cache_disable_enable(self):
        """Test cache can be disabled and enabled."""
        strategy = PairTradingStrategy()

        # Check initial state
        assert strategy.use_cache is True, "Cache should start enabled"

        # Disable cache
        strategy.disable_cache()
        assert strategy.use_cache is False, "Cache should be disabled"

        # Enable cache
        strategy.enable_cache()
        assert strategy.use_cache is True, "Cache should be re-enabled"

=======
    
    def test_cache_disable_enable(self):
        """Test cache can be disabled and enabled."""
        strategy = PairTradingStrategy()
        
        # Check initial state
        assert strategy.use_cache is True, "Cache should start enabled"
        
        # Disable cache
        strategy.disable_cache()
        assert strategy.use_cache is False, "Cache should be disabled"
        
        # Enable cache
        strategy.enable_cache()
        assert strategy.use_cache is True, "Cache should be re-enabled"
    
>>>>>>> origin/main
    def test_cache_clear(self):
        """Test cache file can be cleared."""
        strategy = PairTradingStrategy()
        cache_file = strategy.cache_dir / "cointegrated_pairs.pkl"
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # Create dummy cache file
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("dummy")
        assert cache_file.exists(), "Cache file should exist"
<<<<<<< HEAD

        # Clear cache
        strategy.clear_cache()
        assert not cache_file.exists(), "Cache file should be removed after clear_cache()"

=======
        
        # Clear cache
        strategy.clear_cache()
        assert not cache_file.exists(), "Cache file should be removed after clear_cache()"
    
>>>>>>> origin/main
    def test_walk_forward_disables_cache(self):
        """Test that walk-forward testing disables cache at start."""
        backtester = WalkForwardBacktester()
        strategy = backtester.runner.strategy
<<<<<<< HEAD

        # Verify cache starts enabled
        assert strategy.use_cache is True

        # Simulate walk-forward start (what run_walk_forward does)
        strategy.clear_cache()
        strategy.disable_cache()

        assert strategy.use_cache is False, "Cache should be disabled during walk-forward"
        assert not (strategy.cache_dir / "cointegrated_pairs.pkl").exists(), (
            "Cache file should be cleared before walk-forward"
        )

        # Simulate walk-forward end (what run_walk_forward does)
        strategy.enable_cache()

        assert strategy.use_cache is True, "Cache should be re-enabled after walk-forward"

    def test_find_cointegrated_pairs_respects_use_cache_flag(self):
        """Test that find_cointegrated_pairs respects use_cache flag."""
        strategy = PairTradingStrategy()

        # Generate synthetic cointegrated data
        np.random.seed(42)
        dates = pd.date_range("2025-01-01", periods=100, freq="D")
        x = pd.Series(np.random.normal(100, 2, 100), index=dates, name="X")
        y = pd.Series(2 * np.asarray(x, dtype=float) + np.random.normal(0, 1, 100), index=dates, name="Y")
        price_data = pd.DataFrame({"X": x, "Y": y})

        # Test with cache disabled
        strategy.use_cache = False
        strategy.find_cointegrated_pairs(price_data, use_cache=False)

        # Verify cache file wasn't created (because use_cache=False)
        cache_file = strategy.cache_dir / "cointegrated_pairs.pkl"
        assert not cache_file.exists(), "Cache file should not be created when use_cache=False"

    def test_find_cointegrated_pairs_explicit_override(self):
        """Test that explicit use_cache parameter overrides instance setting."""
        strategy = PairTradingStrategy()

        # Generate synthetic data
        np.random.seed(42)
        dates = pd.date_range("2025-01-01", periods=100, freq="D")
        x = pd.Series(np.random.normal(100, 2, 100), index=dates, name="X")
        y = pd.Series(2 * np.asarray(x, dtype=float) + np.random.normal(0, 1, 100), index=dates, name="Y")
        price_data = pd.DataFrame({"X": x, "Y": y})

        # Instance has cache enabled, but override with explicit False
        strategy.use_cache = True
        strategy.find_cointegrated_pairs(price_data, use_cache=False)

        # Verify cache file wasn't created
        cache_file = strategy.cache_dir / "cointegrated_pairs.pkl"
        assert not cache_file.exists(), "Explicit use_cache=False should override instance setting"

=======
        
        # Verify cache starts enabled
        assert strategy.use_cache is True
        
        # Simulate walk-forward start (what run_walk_forward does)
        strategy.clear_cache()
        strategy.disable_cache()
        
        assert strategy.use_cache is False, "Cache should be disabled during walk-forward"
        assert not (strategy.cache_dir / "cointegrated_pairs.pkl").exists(), \
            "Cache file should be cleared before walk-forward"
        
        # Simulate walk-forward end (what run_walk_forward does)
        strategy.enable_cache()
        
        assert strategy.use_cache is True, "Cache should be re-enabled after walk-forward"
    
    def test_find_cointegrated_pairs_respects_use_cache_flag(self):
        """Test that find_cointegrated_pairs respects use_cache flag."""
        strategy = PairTradingStrategy()
        
        # Generate synthetic cointegrated data
        np.random.seed(42)
        dates = pd.date_range('2025-01-01', periods=100, freq='D')
        x = pd.Series(np.random.normal(100, 2, 100), index=dates, name='X')
        y = pd.Series(2 * x.values + np.random.normal(0, 1, 100), index=dates, name='Y')
        price_data = pd.DataFrame({'X': x, 'Y': y})
        
        # Test with cache disabled
        strategy.use_cache = False
        strategy.find_cointegrated_pairs(price_data, use_cache=False)
        
        # Verify cache file wasn't created (because use_cache=False)
        cache_file = strategy.cache_dir / "cointegrated_pairs.pkl"
        assert not cache_file.exists(), "Cache file should not be created when use_cache=False"
    
    def test_find_cointegrated_pairs_explicit_override(self):
        """Test that explicit use_cache parameter overrides instance setting."""
        strategy = PairTradingStrategy()
        
        # Generate synthetic data
        np.random.seed(42)
        dates = pd.date_range('2025-01-01', periods=100, freq='D')
        x = pd.Series(np.random.normal(100, 2, 100), index=dates, name='X')
        y = pd.Series(2 * x.values + np.random.normal(0, 1, 100), index=dates, name='Y')
        price_data = pd.DataFrame({'X': x, 'Y': y})
        
        # Instance has cache enabled, but override with explicit False
        strategy.use_cache = True
        strategy.find_cointegrated_pairs(price_data, use_cache=False)
        
        # Verify cache file wasn't created
        cache_file = strategy.cache_dir / "cointegrated_pairs.pkl"
        assert not cache_file.exists(), "Explicit use_cache=False should override instance setting"
    
>>>>>>> origin/main
    def test_walk_forward_splits_isolation(self):
        """Test that walk-forward creates proper isolated splits."""
        # Generate synthetic data with clear trend
        np.random.seed(42)
<<<<<<< HEAD
        dates = pd.date_range("2025-01-01", periods=400, freq="D")
        values = 100 + np.cumsum(np.random.normal(0.5, 2, 400))
        data = pd.DataFrame({"price": values}, index=dates)

        # Create walk-forward splits
        splits = split_walk_forward(data, num_periods=4, oos_ratio=0.2)

        assert len(splits) == 4, "Should create 4 splits"

=======
        dates = pd.date_range('2025-01-01', periods=400, freq='D')
        values = 100 + np.cumsum(np.random.normal(0.5, 2, 400))
        data = pd.DataFrame({'price': values}, index=dates)
        
        # Create walk-forward splits
        splits = split_walk_forward(data, num_periods=4, oos_ratio=0.2)
        
        assert len(splits) == 4, "Should create 4 splits"
        
>>>>>>> origin/main
        # Verify test sets don't overlap with each other
        # (train sets DO overlap by design in expanding-window walk-forward)
        for i in range(len(splits) - 1):
            _, test_df = splits[i]
            _, next_test_df = splits[i + 1]
<<<<<<< HEAD

            # Current test end should be before or equal to next test start
            assert test_df.index[-1] < next_test_df.index[0], (
                f"Test sets should not overlap: period {i} test ends {test_df.index[-1]}, "
                f"period {i + 1} test starts {next_test_df.index[0]}"
            )

        # Verify no data leakage within each split (train ends before test starts)
        for i, (train_df, test_df) in enumerate(splits):
            assert train_df.index[-1] < test_df.index[0], (
                f"Split {i}: train ends {train_df.index[-1]} but test starts {test_df.index[0]} ÔÇô data leakage!"
            )

        # Verify coverage
        _first_train, _first_test = splits[0]
        _last_train, last_test = splits[-1]

        # Check that splits span a significant portion of the data
        assert splits[0][0].index[0] < last_test.index[-1], "Splits should span data range"
=======
            
            # Current test end should be before or equal to next test start
            assert test_df.index[-1] < next_test_df.index[0], \
                f"Test sets should not overlap: period {i} test ends {test_df.index[-1]}, " \
                f"period {i+1} test starts {next_test_df.index[0]}"
        
        # Verify no data leakage within each split (train ends before test starts)
        for i, (train_df, test_df) in enumerate(splits):
            assert train_df.index[-1] < test_df.index[0], \
                f"Split {i}: train ends {train_df.index[-1]} " \
                f"but test starts {test_df.index[0]} – data leakage!"
        
        # Verify coverage
        first_train, first_test = splits[0]
        last_train, last_test = splits[-1]
        
        # Check that splits span a significant portion of the data
        assert first_train.index[0] < last_test.index[-1], \
            "Splits should span data range"
>>>>>>> origin/main


class TestCacheIsolationIntegration:
    """Integration tests for cache isolation in realistic scenarios."""
<<<<<<< HEAD

    def test_pair_discovery_respects_cache_setting(self):
        """Test that pair discovery respects the cache setting."""
        strategy = PairTradingStrategy()

        # Generate synthetic data
        np.random.seed(42)
        dates = pd.date_range("2025-01-01", periods=100, freq="D")
        x = pd.Series(100 + np.cumsum(np.random.normal(0, 0.5, 100)), index=dates, name="X")
        y = pd.Series(200 + 2 * np.asarray(x, dtype=float) + np.random.normal(0, 1, 100), index=dates, name="Y")
        price_data = pd.DataFrame({"X": x, "Y": y})

        # First discovery: with cache disabled
        strategy.use_cache = False
        pairs1 = strategy.find_cointegrated_pairs(price_data, use_cache=False)

        # Verify cache wasn't written
        cache_file = strategy.cache_dir / "cointegrated_pairs.pkl"
        assert not cache_file.exists(), "Cache should not be written when use_cache=False"

=======
    
    def test_pair_discovery_respects_cache_setting(self):
        """Test that pair discovery respects the cache setting."""
        strategy = PairTradingStrategy()
        
        # Generate synthetic data 
        np.random.seed(42)
        dates = pd.date_range('2025-01-01', periods=100, freq='D')
        x = pd.Series(100 + np.cumsum(np.random.normal(0, 0.5, 100)), 
                     index=dates, name='X')
        y = pd.Series(200 + 2 * x.values + np.random.normal(0, 1, 100), 
                     index=dates, name='Y')
        price_data = pd.DataFrame({'X': x, 'Y': y})
        
        # First discovery: with cache disabled
        strategy.use_cache = False
        pairs1 = strategy.find_cointegrated_pairs(price_data, use_cache=False)
        
        # Verify cache wasn't written
        cache_file = strategy.cache_dir / "cointegrated_pairs.pkl"
        assert not cache_file.exists(), "Cache should not be written when use_cache=False"
        
>>>>>>> origin/main
        # Second discovery: with explicit use_cache=True, should use discovery logic
        # (won't create cache because first discovery returned empty list)
        strategy.use_cache = True
        pairs2 = strategy.find_cointegrated_pairs(price_data, use_cache=True)
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # Results should be same (based on data, not cache)
        assert len(pairs1) == len(pairs2), "Results should be consistent"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
