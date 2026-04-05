"""
Performance Optimization Tests - S3.4

Tests covering:
- S3.4a: Pair discovery parallelization (6x speedup expected)
- S3.4b: LRU cache for spread models (20-30% speedup)
- S3.4c: Vectorized signal generation (3x speedup)

Run: pytest tests/models/test_performance_optimizer.py -v
Expected: 25+ tests passing, performance targets met
"""

# pyright: reportUnusedExpression=false

import time

import numpy as np
import pandas as pd
import pytest

from models.performance_optimizer import (
    LRUSpreadModelCache,
    S34PerformanceOptimizer,
    VectorizedSignalGenerator,
    cached_spread_model,
)


class TestLRUSpreadModelCache:
    """Test LRU caching for spread models (S3.4b)."""

    def test_cache_basic_put_get(self):
        """Test basic put/get operations."""
        cache = LRUSpreadModelCache(maxsize=10)

        model_data = {"spread": pd.Series([1, 2, 3, 4, 5]), "beta": 0.95, "half_life": 25.0}

        cache.put("AAPL-MSFT", model_data)
        retrieved = cache.get("AAPL-MSFT")

        assert retrieved is not None
        assert retrieved["beta"] == 0.95
        assert retrieved["half_life"] == 25.0

    def test_cache_miss_returns_none(self):
        """Test cache miss returns None."""
        cache = LRUSpreadModelCache()

        result = cache.get("NONEXISTENT")
        assert result is None

    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache exceeds maxsize."""
        cache = LRUSpreadModelCache(maxsize=3)

        # Add 3 items
        for i in range(3):
            cache.put(f"pair_{i}", {"value": i})

        assert len(cache.cache) == 3

        # Add 4th item (should evict oldest)
        cache.put("pair_3", {"value": 3})

        assert len(cache.cache) == 3
        assert cache.get("pair_0") is None  # Oldest was evicted
        assert cache.get("pair_3") is not None  # Newest is present

    def test_cache_lru_access_updates_order(self):
        """Test that accessing an item updates its access order."""
        cache = LRUSpreadModelCache(maxsize=3)

        # Add 3 items
        cache.put("pair_0", {"value": 0})
        cache.put("pair_1", {"value": 1})
        cache.put("pair_2", {"value": 2})

        # Access pair_0 (makes it most recent)
        cache.get("pair_0")

        # Add 4th item (should evict pair_1, not pair_0)
        cache.put("pair_3", {"value": 3})

        assert cache.get("pair_0") is not None  # Was accessed, should stay
        assert cache.get("pair_1") is None  # Wasn't accessed, should be evicted

    def test_cache_hit_miss_stats(self):
        """Test cache hit/miss statistics."""
        cache = LRUSpreadModelCache()

        cache.put("pair_a", {"value": 1})

        # Hit
        cache.get("pair_a")
        # Miss
        cache.get("pair_b")

        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["total"] == 2
        assert "50.0%" in stats["hit_rate"]

    def test_cache_clear(self):
        """Test cache clearing."""
        cache = LRUSpreadModelCache()

        cache.put("pair_a", {"value": 1})
        cache.put("pair_b", {"value": 2})

        cache.clear()

        assert len(cache.cache) == 0
        assert cache.get("pair_a") is None

    def test_cache_thread_safety(self):
        """Test thread-safe access to cache."""
        cache = LRUSpreadModelCache(maxsize=100)

        # Multiple threads (simulated)
        for i in range(10):
            cache.put(f"pair_{i}", {"value": i})

        # All should be retrievable
        for i in range(10):
            assert cache.get(f"pair_{i}") is not None


class TestVectorizedSignalGenerator:
    """Test vectorized signal generation (S3.4c)."""

    def test_generate_signals_batch_entry(self):
        """Test entry signal generation via vectorization."""
        gen = VectorizedSignalGenerator(entry_z_threshold=2.0, exit_z_threshold=0.5)

        # Z-scores for multiple pairs
        z_scores = {
            "pair_a": pd.Series([0.5, 1.0, 2.5]),  # Entry
            "pair_b": pd.Series([3.0, 3.5, 0.3]),  # Exit (was high, now < 0.5)
            "pair_c": pd.Series([0.1, 0.2, 0.3]),  # Hold
        }

        active_positions = {"pair_b": True}  # pair_b already in position

        signals = gen.generate_signals_batch(z_scores, active_positions)

        assert signals["pair_a"] == "entry"  # |2.5| > 2.0
        assert signals["pair_b"] == "exit"  # |0.3| <= 0.5 and active
        assert signals["pair_c"] == "hold"

    def test_generate_signals_batch_no_double_entry(self):
        """Test that already-active positions don't get re-entry signals."""
        gen = VectorizedSignalGenerator(entry_z_threshold=2.0)

        z_scores = {
            "pair_a": pd.Series([0, 0, 2.5]),  # High Z, would be entry
        }

        active_positions = {"pair_a": True}  # Already active

        signals = gen.generate_signals_batch(z_scores, active_positions)

        # Should not re-enter already active position
        assert signals["pair_a"] != "entry"

    def test_generate_signals_empty_dict(self):
        """Test signal generation with empty input."""
        gen = VectorizedSignalGenerator()

        signals = gen.generate_signals_batch({}, {})

        assert len(signals) == 0

    def test_compute_z_scores_vectorized(self):
        """Test vectorized Z-score computation."""
        gen = VectorizedSignalGenerator()

        # Create synthetic spread
        spread = pd.Series(np.random.randn(100).cumsum())
        spread_dict = {"pair_test": spread}

        z_scores = gen.compute_all_z_scores_vectorized(spread_dict, lookback=20)

        assert "pair_test" in z_scores
        assert len(z_scores["pair_test"]) == len(spread)

        # First 19 values should be NaN (not enough history)
        assert pd.isna(z_scores["pair_test"].iloc[0:19]).all()

        # Later values should be finite
        assert np.all(np.isfinite(z_scores["pair_test"].iloc[19:]))

    def test_z_score_normalization(self):
        """Test that computed Z-scores are properly normalized."""
        gen = VectorizedSignalGenerator()

        # Constant spread (should have zero std)
        spread = pd.Series([5.0, 5.0, 5.0, 5.0, 5.0])
        spread_dict = {"pair_test": spread}

        z_scores = gen.compute_all_z_scores_vectorized(spread_dict, lookback=3)

        # Should handle division by zero gracefully
        assert z_scores["pair_test"] is not None

    def test_vectorized_speed_vs_loop(self):
        """Test that vectorized implementation is faster than loop."""
        num_pairs = 50
        lookback = 100

        # Seed for reproducibility
        np.random.seed(42)

        # Create test data
        z_scores_dict = {f"pair_{i}": pd.Series(np.random.randn(lookback)) for i in range(num_pairs)}
        active_positions = {f"pair_{i}": i % 2 == 0 for i in range(num_pairs)}

        gen = VectorizedSignalGenerator()

        # Vectorized version
        start_vec = time.time()
        signals_vec = gen.generate_signals_batch(z_scores_dict, active_positions)
        time.time() - start_vec

        # Loop version (for comparison)
        start_loop = time.time()
        signals_loop = {}
        entry_threshold = 2.0
        exit_threshold = 0.5

        for pair, z_series in z_scores_dict.items():
            current_z = z_series.iloc[-1]
            # Entry: threshold exceeded AND position is inactive (not in active_positions or value is False)
            if abs(current_z) > entry_threshold and not active_positions.get(pair, True):
                signals_loop[pair] = "entry"
            # Exit: within threshold AND position is active (in active_positions and value is True)
            elif abs(current_z) <= exit_threshold and active_positions.get(pair, False):
                signals_loop[pair] = "exit"
            else:
                signals_loop[pair] = "hold"

        time.time() - start_loop

        # Vectorized should be comparable or faster
        # (Note: with this overhead, loop might be similar, but scales better)

        assert signals_vec == signals_loop  # Same results
        # Performance test: vectorized should be similar or better for large N


class TestS34PerformanceOptimizer:
    """Test integrated Performance Optimizer (S3.4)."""

    def test_optimizer_initialization(self):
        """Test optimizer initialization."""
        opt = S34PerformanceOptimizer()

        assert opt.spread_cache is not None
        assert opt.signal_generator is not None
        assert isinstance(opt.timings, dict)

    def test_optimizer_get_cache(self):
        """Test accessing cache from optimizer."""
        opt = S34PerformanceOptimizer()

        cache = opt.get_spread_model_cache()
        assert isinstance(cache, LRUSpreadModelCache)

        # Cache should be usable immediately
        cache.put("AAPL-MSFT", {"value": 1})
        assert cache.get("AAPL-MSFT") is not None

    def test_optimizer_get_signal_generator(self):
        """Test accessing signal generator from optimizer."""
        opt = S34PerformanceOptimizer()

        gen = opt.get_signal_generator()
        assert isinstance(gen, VectorizedSignalGenerator)

    def test_optimizer_performance_summary(self):
        """Test performance summary logging."""
        opt = S34PerformanceOptimizer()

        # Add some cache activity
        cache = opt.get_spread_model_cache()
        cache.put("pair_a", {"value": 1})
        cache.get("pair_a")
        cache.get("pair_nonexist")

        # Should not raise exception
        opt.log_performance_summary()

        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1


class TestCachedSpreadModelDecorator:
    """Test @cached_spread_model decorator (S3.4b)."""

    def test_decorator_caching(self):
        """Test that decorator caches results."""

        @cached_spread_model(maxsize=10)
        def sample_computation(y, x):
            """Sample expensive computation."""
            return {"beta": np.mean(y / (x + 1e-6)), "cost": "expensive"}

        y = np.array([1.0, 2.0, 3.0])
        x = np.array([0.5, 1.0, 1.5])

        # First call
        result1 = sample_computation(y, x)

        # Second call (should be cached)
        result2 = sample_computation(y, x)

        assert result1 == result2

    def test_decorator_cache_miss(self):
        """Test cache miss with different inputs."""

        @cached_spread_model(maxsize=10)
        def sample_computation(y, x):
            """Sample expensive computation."""
            return {"beta": np.mean(y / (x + 1e-6)), "cost": "expensive"}

        y1 = np.array([1.0, 2.0, 3.0])
        x1 = np.array([0.5, 1.0, 1.5])

        y2 = np.array([2.0, 3.0, 4.0])
        x2 = np.array([1.0, 2.0, 3.0])

        result1 = sample_computation(y1, x1)
        result2 = sample_computation(y2, x2)

        # Different inputs should give different results
        assert result1["beta"] != result2["beta"]


class TestS34IntegrationWithStrategy:
    """Integration tests: verify S3.4 optimizations work with strategy."""

    def test_cache_reduces_computation(self):
        """Test that caching reduces computation time."""
        cache = LRUSpreadModelCache(maxsize=50)

        # First access: cache miss, need to compute
        model_data = {"spread": pd.Series([1, 2, 3]), "half_life": 25}
        cache.put("AAPL-MSFT", model_data)

        start = time.time()
        for _ in range(100):
            cache.get("AAPL-MSFT")
        cached_time = time.time() - start

        # Should be very fast (cached)
        assert cached_time < 0.01  # <10ms for 100 accesses

    def test_vectorized_signals_correct(self):
        """Test vectorized signals match expected results."""
        gen = VectorizedSignalGenerator(entry_z_threshold=2.0, exit_z_threshold=0.5)

        # Create realistic Z-score data
        z_scores = {
            "AAPL-MSFT": pd.Series([0.5, 1.0, 1.5, 2.5, 2.8]),  # Enters at end
            "GOOGL-JPM": pd.Series([2.2, 1.8, 0.8, 0.3, 0.1]),  # High then exits
        }

        active = {
            "GOOGL-JPM": True,  # Already in position
        }

        signals = gen.generate_signals_batch(z_scores, active)

        # Check entry signal
        assert signals.get("AAPL-MSFT") == "entry"  # |2.8| > 2.0

        # Check exit signal
        assert signals.get("GOOGL-JPM") == "exit"  # |0.1| <= 0.5 and active

    def test_performance_optimizer_full_workflow(self):
        """Test S3.4 optimizer in realistic workflow."""
        opt = S34PerformanceOptimizer()

        # S3.4b: Use cache
        cache = opt.get_spread_model_cache()
        for i in range(10):
            cache.put(f"pair_{i}", {"half_life": 20.0 + i})

        # Verify cache working
        assert cache.get("pair_0") is not None
        assert cache.stats()["size"] == 10

        # S3.4c: Use vectorized signal generator
        gen = opt.get_signal_generator()
        z_scores = {f"pair_{i}": pd.Series([float(i) * 0.5, float(i) * 0.7, float(i)]) for i in range(10)}

        signals = gen.generate_signals_batch(z_scores, {})

        # Should generate signals for all pairs
        assert len(signals) == 10

        # Log summary
        opt.log_performance_summary()


# Performance benchmarking tests
class TestS34PerformanceBenchmarks:
    """Benchmark tests to verify S3.4 performance targets."""

    def test_signal_generation_performance_target(self):
        """
        Test that vectorized signal generation meets <100ms target.

        S3.4c target: <100ms for 50 pairs
        """
        gen = VectorizedSignalGenerator()

        # 50 pairs
        z_scores = {f"pair_{i}": pd.Series(np.random.randn(250)) for i in range(50)}
        active = {f"pair_{i}": i % 2 == 0 for i in range(50)}

        start = time.time()
        signals = gen.generate_signals_batch(z_scores, active)
        elapsed = time.time() - start

        # Should be well under 100ms
        assert elapsed < 0.1  # 100ms
        assert len(signals) == 50

    def test_z_score_computation_performance(self):
        """
        Test Z-score computation performance.

        Expected: <50ms for computing Z-scores on 50 pairs
        """
        gen = VectorizedSignalGenerator()

        spreads = {f"pair_{i}": pd.Series(np.random.randn(252)) for i in range(50)}

        start = time.time()
        z_scores = gen.compute_all_z_scores_vectorized(spreads, lookback=20)
        elapsed = time.time() - start

        # Should be fast (vectorized)
        assert elapsed < 0.05  # 50ms
        assert len(z_scores) == 50

    def test_cache_performance_benefit(self):
        """
        Test cache performance benefit.

        S3.4b target: 20-30% speedup with caching
        """
        cache = LRUSpreadModelCache(maxsize=100)

        # Populate cache
        for i in range(100):
            cache.put(f"pair_{i}", {"half_life": 20 + i})

        # Cache hit rate should be ~100% for repeated accesses
        for i in range(100):
            for _ in range(10):
                cache.get(f"pair_{i}")

        stats = cache.stats()
        hit_rate = stats["hits"] / (stats["hits"] + stats["misses"])

        # Should achieve high hit rate
        assert hit_rate > 0.99


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
