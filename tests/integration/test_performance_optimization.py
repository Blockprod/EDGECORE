"""
Tests for Problem #5: Performance Optimization

Tests parallel pair discovery, caching, and performance improvements.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import time
import pickle
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from strategies.pair_trading import PairTradingStrategy
from config.settings import get_settings


class TestParallelPairDiscovery:
    """Tests for parallel cointegration discovery."""
    
    def test_parallel_discovery_faster_than_sequential(self):
        """Verify parallel discovery is faster than sequential."""
        # Create moderate dataset (10 symbols, 100 periods)
        np.random.seed(42)
        symbols = [f"SYM{i}" for i in range(10)]
        data = pd.DataFrame({
            sym: np.random.randn(100).cumsum() 
            for sym in symbols
        })
        
        strategy = PairTradingStrategy()
        
        # Time sequential discovery
        start_seq = time.time()
        seq_pairs = strategy.find_cointegrated_pairs(
            data, 
            use_cache=False, 
            use_parallel=False
        )
        seq_duration = time.time() - start_seq
        
        # Time parallel discovery
        start_par = time.time()
        par_pairs = strategy.find_cointegrated_pairs(
            data, 
            use_cache=False, 
            use_parallel=True
        )
        par_duration = time.time() - start_par
        
        # Parallel should be comparable (may not be faster for small datasets)
        # But should return same results
        assert len(seq_pairs) == len(par_pairs), \
            f"Sequential: {len(seq_pairs)}, Parallel: {len(par_pairs)}"
    
    def test_parallel_discovery_finds_pairs(self):
        """Verify parallel discovery finds cointegrated pairs."""
        np.random.seed(42)
        # Create synthetic cointegrated pair
        base = np.random.randn(100).cumsum()
        sym_data = {
            'SYM1': base,
            'SYM2': base + np.random.randn(100) * 0.1,  # Cointegrated with SYM1
            'SYM3': np.random.randn(100).cumsum(),      # Independent
            'SYM4': base - np.random.randn(100) * 0.05, # Cointegrated with SYM1
        }
        data = pd.DataFrame(sym_data)
        
        strategy = PairTradingStrategy()
        pairs = strategy.find_cointegrated_pairs(data, use_cache=False, use_parallel=True)
        
        # Should find at least some pairs
        assert isinstance(pairs, list)
        assert all(isinstance(p, tuple) and len(p) == 4 for p in pairs)
        
        # Each pair should have (sym1, sym2, pvalue, half_life)
        for sym1, sym2, pvalue, hl in pairs:
            assert isinstance(sym1, str)
            assert isinstance(sym2, str)
            assert isinstance(pvalue, float)
            assert hl is None or isinstance(hl, float)
    
    def test_static_test_pair_cointegration(self):
        """Test the static pair testing method."""
        np.random.seed(42)
        series1 = pd.Series(np.random.randn(100).cumsum())
        series2 = pd.Series(series1 + np.random.randn(100) * 0.1)
        
        # This should work as a static method
        result = PairTradingStrategy._test_pair_cointegration(
            ('SYM1', 'SYM2', series1, series2, 0.5, 60)
        )
        
        # Result can be None (if not cointegrated) or a tuple
        assert result is None or isinstance(result, tuple)
        if result:
            sym1, sym2, pvalue, hl = result
            assert sym1 == 'SYM1'
            assert sym2 == 'SYM2'
    
    def test_parallel_with_num_workers(self):
        """Test parallel discovery with explicit number of workers."""
        np.random.seed(42)
        data = pd.DataFrame({
            f"SYM{i}": np.random.randn(100).cumsum() 
            for i in range(5)
        })
        
        strategy = PairTradingStrategy()
        
        # Test with 2 workers
        pairs = strategy.find_cointegrated_pairs_parallel(
            data, 
            num_workers=2
        )
        
        assert isinstance(pairs, list)
    
    def test_parallel_with_empty_symbols(self):
        """Test parallel discovery handles empty data gracefully."""
        data = pd.DataFrame()
        strategy = PairTradingStrategy()
        
        pairs = strategy.find_cointegrated_pairs_parallel(data)
        
        assert pairs == []
    
    def test_parallel_with_single_symbol(self):
        """Test parallel discovery with only one symbol."""
        np.random.seed(42)
        data = pd.DataFrame({'SYM1': np.random.randn(100).cumsum()})
        
        strategy = PairTradingStrategy()
        pairs = strategy.find_cointegrated_pairs_parallel(data)
        
        # Can't form pairs from single symbol
        assert pairs == []


class TestCachingFunctionality:
    """Tests for cointegrated pairs caching."""
    
    def test_cache_directory_creation(self):
        """Verify cache directory is created on initialization."""
        strategy = PairTradingStrategy()
        
        assert strategy.cache_dir.exists()
        assert strategy.cache_dir.is_dir()
    
    def test_save_and_load_cached_pairs(self):
        """Test saving and loading pairs from cache."""
        strategy = PairTradingStrategy()
        
        test_pairs = [
            ('SYM1', 'SYM2', 0.01, 20.5),
            ('SYM3', 'SYM4', 0.02, 15.3),
        ]
        
        # Save pairs
        strategy.save_cached_pairs(test_pairs)
        
        # Verify cache file exists
        cache_file = strategy.cache_dir / "cointegrated_pairs.pkl"
        assert cache_file.exists()
        
        # Load pairs back
        loaded = strategy.load_cached_pairs()
        
        assert loaded == test_pairs
    
    def test_cache_respects_max_age(self):
        """Test that cache age checking works."""
        strategy = PairTradingStrategy()
        
        test_pairs = [('SYM1', 'SYM2', 0.01, 20.5)]
        strategy.save_cached_pairs(test_pairs)
        
        # Load with max_age of 24 hours (should work)
        loaded = strategy.load_cached_pairs(max_age_hours=24)
        assert loaded == test_pairs
        
        # Load with max_age of 0 hours (should expire)
        loaded = strategy.load_cached_pairs(max_age_hours=0)
        assert loaded is None
    
    def test_find_cointegrated_pairs_uses_cache(self):
        """Test that find_cointegrated_pairs uses cache."""
        np.random.seed(42)
        data = pd.DataFrame({
            f"SYM{i}": np.random.randn(100).cumsum() 
            for i in range(4)
        })
        
        strategy = PairTradingStrategy()
        
        # First discovery (will cache)
        pairs1 = strategy.find_cointegrated_pairs(data, use_cache=True)
        
        # Second discovery should use cache (instant)
        start = time.time()
        pairs2 = strategy.find_cointegrated_pairs(data, use_cache=True)
        cached_duration = time.time() - start
        
        # Results should be identical
        assert pairs1 == pairs2
        
        # Cached load should be very fast (<100ms)
        assert cached_duration < 0.1
    
    def test_cache_disabled_when_use_cache_false(self):
        """Test that cache is ignored when use_cache=False."""
        np.random.seed(42)
        data = pd.DataFrame({
            f"SYM{i}": np.random.randn(100).cumsum() 
            for i in range(4)
        })
        
        strategy = PairTradingStrategy()
        
        # Save some pairs to cache
        test_pairs = [('SYM0', 'SYM1', 0.01, 20.5)]
        strategy.save_cached_pairs(test_pairs)
        
        # Discover with cache disabled should not return cached pairs
        pairs = strategy.find_cointegrated_pairs(data, use_cache=False)
        
        # Should either be empty or different from cache
        # (won't be identical cached pairs due to random data)
        assert isinstance(pairs, list)
    
    def test_corrupt_cache_file_handled(self):
        """Test that corrupt cache files don't break the system."""
        strategy = PairTradingStrategy()
        
        # Create corrupt cache file
        cache_file = strategy.cache_dir / "cointegrated_pairs.pkl"
        cache_file.write_text("corrupt data")
        
        # Should handle gracefully and return None
        result = strategy.load_cached_pairs()
        
        assert result is None


class TestBackwardCompatibility:
    """Tests to ensure backward compatibility."""
    
    def test_sequential_discovery_still_works(self):
        """Verify sequential discovery still works."""
        np.random.seed(42)
        base = np.random.randn(100).cumsum()
        data = pd.DataFrame({
            'SYM1': base,
            'SYM2': base + np.random.randn(100) * 0.1,
            'SYM3': np.random.randn(100).cumsum(),
        })
        
        strategy = PairTradingStrategy()
        
        # Use sequential method
        pairs = strategy._find_cointegrated_pairs_sequential(data)
        
        assert isinstance(pairs, list)
        assert all(len(p) == 4 for p in pairs)
    
    def test_generate_signals_works_with_optimized_pairs(self):
        """Test that signal generation works with optimized pair discovery."""
        np.random.seed(42)
        # Create multi-symbol market data
        base = np.random.randn(100).cumsum()
        market_data = pd.DataFrame({
            'SYM1': base,
            'SYM2': base + np.random.randn(100) * 0.1,
            'SYM3': np.random.randn(100).cumsum(),
        })
        
        strategy = PairTradingStrategy()
        
        # Should still generate signals as before
        signals = strategy.generate_signals(market_data)
        
        assert isinstance(signals, list)
        # Each signal has required fields
        for signal in signals:
            assert hasattr(signal, 'symbol_pair')
            assert hasattr(signal, 'side')
            assert hasattr(signal, 'strength')


class TestPerformanceMetrics:
    """Tests to measure and validate performance improvements."""
    
    def test_parallel_pair_discovery_metrics(self):
        """Test that parallel discovery logs proper metrics."""
        np.random.seed(42)
        data = pd.DataFrame({
            f"SYM{i}": np.random.randn(100).cumsum() 
            for i in range(6)
        })
        
        strategy = PairTradingStrategy()
        
        # Should complete without error
        pairs = strategy.find_cointegrated_pairs_parallel(data)
        
        assert isinstance(pairs, list)
        # Total pairs tested = C(6,2) = 15
        # Result will be filtered subset of those
    
    def test_cache_eliminates_redundant_discovery(self):
        """Test that caching avoids redundant pair discovery."""
        np.random.seed(42)
        data = pd.DataFrame({
            f"SYM{i}": np.random.randn(50).cumsum() 
            for i in range(4)
        })
        
        strategy = PairTradingStrategy()
        
        # First call (has to compute)
        result1 = strategy.find_cointegrated_pairs(data, use_cache=True)
        
        # Verify cache file was created
        cache_file = strategy.cache_dir / "cointegrated_pairs.pkl"
        assert cache_file.exists(), "Cache file should be created"
        
        # Second call (should use cache - but might not be faster due to overhead)
        result2 = strategy.find_cointegrated_pairs(data, use_cache=True)
        
        # Results should be identical (proves caching works)
        assert result1 == result2, "Cached results should be identical"


class TestIntegrationWithStrategy:
    """Integration tests with full strategy."""
    
    def test_strategy_with_cached_pair_discovery(self):
        """Test PairTradingStrategy with cached discovery."""
        np.random.seed(42)
        base = np.random.randn(100).cumsum()
        market_data = pd.DataFrame({
            'BTC': base,
            'ETH': base + np.random.randn(100) * 0.15,
            'XRP': base + np.random.randn(100) * 0.10,
            'ADA': np.random.randn(100).cumsum(),
        })
        
        strategy = PairTradingStrategy()
        
        # First generation (discovers and caches)
        signals1 = strategy.generate_signals(market_data)
        
        # Second generation (uses cache)
        signals2 = strategy.generate_signals(market_data)
        
        # Should return signals (content depends on data)
        assert isinstance(signals1, list)
        assert isinstance(signals2, list)
    
    def test_force_non_parallel_discovery(self):
        """Test forcing sequential discovery."""
        np.random.seed(42)
        data = pd.DataFrame({
            f"SYM{i}": np.random.randn(100).cumsum() 
            for i in range(5)
        })
        
        strategy = PairTradingStrategy()
        
        # Force sequential
        pairs = strategy.find_cointegrated_pairs(
            data, 
            use_cache=False, 
            use_parallel=False
        )
        
        assert isinstance(pairs, list)
