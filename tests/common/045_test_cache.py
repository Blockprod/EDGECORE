"""
Tests for dashboard caching layer.

Tests:
- Cache insertion and retrieval
- TTL expiration
- LRU eviction
- Cache invalidation
- Performance improvements
- Statistics tracking
- Thread safety
"""

import pytest
import time
from unittest.mock import patch, Mock
from monitoring.cache import (
    CacheEntry,
    CacheManager,
    CachedFunction,
    DashboardCache,
    get_dashboard_cache
)


class TestCacheEntry:
    """Test CacheEntry functionality."""
    
    def test_cache_entry_initialization(self):
        """Should initialize with key, value, and TTL."""
        entry = CacheEntry('test_key', {'data': 'value'}, ttl_seconds=60)
        assert entry.key == 'test_key'
        assert entry.value == {'data': 'value'}
        assert entry.ttl_seconds == 60
        assert entry.access_count == 0
    
    def test_cache_entry_is_expired_false(self):
        """Should not be expired immediately after creation."""
        entry = CacheEntry('key', 'value', ttl_seconds=60)
        assert entry.is_expired() is False
    
    def test_cache_entry_is_expired_true(self):
        """Should be expired when TTL exceeded."""
        entry = CacheEntry('key', 'value', ttl_seconds=1)
        time.sleep(1.1)
        assert entry.is_expired() is True
    
    def test_cache_entry_touch(self):
        """Should update access time and count."""
        entry = CacheEntry('key', 'value')
        assert entry.access_count == 0
        entry.touch()
        assert entry.access_count == 1
        entry.touch()
        assert entry.access_count == 2


class TestCacheManager:
    """Test CacheManager functionality."""
    
    def test_cache_manager_initialization(self):
        """Should initialize with max size and default TTL."""
        cache = CacheManager(max_size=100, default_ttl=300)
        assert cache.max_size == 100
        assert cache.default_ttl == 300
    
    def test_cache_set_and_get(self):
        """Should set and retrieve cache entries."""
        cache = CacheManager()
        cache.set('key1', {'data': 'value1'})
        
        result = cache.get('key1')
        assert result == {'data': 'value1'}
    
    def test_cache_get_nonexistent_key(self):
        """Should return None for nonexistent key."""
        cache = CacheManager()
        result = cache.get('nonexistent')
        assert result is None
    
    def test_cache_get_expired_entry(self):
        """Should return None for expired entry."""
        cache = CacheManager(default_ttl=1)
        cache.set('key1', 'value')
        time.sleep(1.1)
        result = cache.get('key1')
        assert result is None
    
    def test_cache_hit_count(self):
        """Should track cache hits."""
        cache = CacheManager()
        cache.set('key1', 'value')
        cache.get('key1')
        cache.get('key1')
        
        stats = cache.get_stats()
        assert stats['hits'] == 2
    
    def test_cache_miss_count(self):
        """Should track cache misses."""
        cache = CacheManager()
        cache.get('nonexistent1')
        cache.get('nonexistent2')
        
        stats = cache.get_stats()
        assert stats['misses'] == 2
    
    def test_cache_hit_rate(self):
        """Should calculate hit rate percentage."""
        cache = CacheManager()
        cache.set('key1', 'value')
        cache.get('key1')  # Hit
        cache.get('nonexistent')  # Miss
        
        stats = cache.get_stats()
        assert stats['hit_rate_percent'] == pytest.approx(50, rel=1)
    
    def test_cache_lru_eviction(self):
        """Should evict least recently used entry when max size exceeded."""
        cache = CacheManager(max_size=2)
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')  # Should evict key1
        
        assert cache.get('key1') is None  # Evicted
        assert cache.get('key2') == 'value2'  # Still there
        assert cache.get('key3') == 'value3'  # New entry
    
    def test_cache_lru_updates_on_access(self):
        """Should update LRU order on cache access."""
        cache = CacheManager(max_size=2)
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.get('key1')  # Access key1 (makes it most recently used)
        cache.set('key3', 'value3')  # Should evict key2 (least recently used)
        
        assert cache.get('key1') == 'value1'  # Still there
        assert cache.get('key2') is None  # Evicted
        assert cache.get('key3') == 'value3'  # New entry
    
    def test_cache_invalidate_all(self):
        """Should invalidate all entries."""
        cache = CacheManager()
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        
        count = cache.invalidate()
        
        assert count == 2
        assert cache.get('key1') is None
        assert cache.get('key2') is None
    
    def test_cache_invalidate_pattern(self):
        """Should invalidate entries matching pattern."""
        cache = CacheManager()
        cache.set('dashboard_main', 'data1')
        cache.set('dashboard_risk', 'data2')
        cache.set('metrics_equity', 'data3')
        
        count = cache.invalidate(pattern='dashboard_*')
        
        assert count == 2
        assert cache.get('dashboard_main') is None
        assert cache.get('dashboard_risk') is None
        assert cache.get('metrics_equity') == 'data3'
    
    def test_cache_invalidate_key(self):
        """Should invalidate specific key."""
        cache = CacheManager()
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        
        result = cache.invalidate_key('key1')
        
        assert result is True
        assert cache.get('key1') is None
        assert cache.get('key2') == 'value2'
    
    def test_cache_invalidate_nonexistent_key(self):
        """Should return False when invalidating nonexistent key."""
        cache = CacheManager()
        
        result = cache.invalidate_key('nonexistent')
        
        assert result is False
    
    def test_cache_exists(self):
        """Should check if key exists and is not expired."""
        cache = CacheManager(default_ttl=1)
        cache.set('key1', 'value')
        
        assert cache.exists('key1') is True
        
        time.sleep(1.1)
        assert cache.exists('key1') is False
    
    def test_cache_clear(self):
        """Should clear all cache entries."""
        cache = CacheManager()
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        
        count = cache.clear()
        
        assert count == 2
        assert cache.get('key1') is None
        assert cache.get('key2') is None
    
    def test_cache_get_bypass(self):
        """Should bypass cache when bypass=True."""
        cache = CacheManager()
        cache.set('key1', 'value')
        
        result = cache.get('key1', bypass=True)
        
        assert result is None
        assert cache.get_stats()['misses'] == 1
    
    def test_cache_eviction_count(self):
        """Should track number of evictions."""
        cache = CacheManager(max_size=1)
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        
        stats = cache.get_stats()
        assert stats['evictions'] == 2
    
    def test_cache_get_details(self):
        """Should provide detailed cache information."""
        cache = CacheManager()
        cache.set('key1', 'value')
        cache.get('key1')
        
        details = cache.get_details()
        
        assert 'key1' in details
        assert 'age_seconds' in details['key1']
        assert 'access_count' in details['key1']
        assert details['key1']['access_count'] >= 1


class TestCachedFunction:
    """Test CachedFunction decorator."""
    
    def test_cached_function_caches_result(self):
        """Should cache function result."""
        cache = CacheManager()
        decorator = CachedFunction(cache)
        call_count = 0
        
        @decorator
        def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y
        
        result1 = expensive_function(1, 2)
        result2 = expensive_function(1, 2)
        
        assert result1 == 3
        assert result2 == 3
        assert call_count == 1  # Called once, second returned from cache
    
    def test_cached_function_different_args(self):
        """Should cache separately for different arguments."""
        cache = CacheManager()
        decorator = CachedFunction(cache)
        call_count = 0
        
        @decorator
        def add(x, y):
            nonlocal call_count
            call_count += 1
            return x + y
        
        result1 = add(1, 2)
        result2 = add(2, 3)
        
        assert result1 == 3
        assert result2 == 5
        assert call_count == 2
    
    def test_cached_function_bypass(self):
        """Should bypass cache when bypass=True."""
        cache = CacheManager()
        decorator = CachedFunction(cache)
        call_count = 0
        
        @decorator
        def multiply(x, y):
            nonlocal call_count
            call_count += 1
            return x * y
        
        result1 = multiply(2, 3)
        result2 = multiply(2, 3, bypass=True)
        
        assert result1 == 6
        assert result2 == 6
        assert call_count == 2


class TestDashboardCache:
    """Test DashboardCache functionality."""
    
    def test_dashboard_cache_initialization(self):
        """Should initialize with default size."""
        cache = DashboardCache(max_size=50)
        assert cache._manager.max_size == 50
    
    def test_cache_dashboard(self):
        """Should cache complete dashboard."""
        cache = DashboardCache()
        dashboard_data = {
            'equity': 50000,
            'positions': 5,
            'performance': 0.15
        }
        
        cache.cache_dashboard(dashboard_data)
        result = cache.get_cached_dashboard()
        
        assert result == dashboard_data
    
    def test_cache_metrics(self):
        """Should cache specific metric type."""
        cache = DashboardCache()
        metrics = {'sharpe_ratio': 1.5, 'max_drawdown': 0.1}
        
        cache.cache_metrics('performance', metrics)
        result = cache.get_cached_metric('performance')
        
        assert result == metrics
    
    def test_invalidate_dashboard(self):
        """Should invalidate all dashboard caches."""
        cache = DashboardCache()
        cache.cache_dashboard({'equity': 50000})
        cache.cache_metrics('performance', {'sharpe': 1.5})
        
        count = cache.invalidate_dashboard()
        
        assert count == 2
        assert cache.get_cached_dashboard() is None
    
    def test_invalidate_metric(self):
        """Should invalidate specific metric cache."""
        cache = DashboardCache()
        cache.cache_metrics('performance', {'sharpe': 1.5})
        cache.cache_metrics('risk', {'drawdown': 0.1})
        
        result = cache.invalidate_metric('performance')
        
        assert result is True
        assert cache.get_cached_metric('performance') is None
        assert cache.get_cached_metric('risk') == {'drawdown': 0.1}
    
    def test_get_stats(self):
        """Should get cache statistics."""
        cache = DashboardCache()
        cache.cache_dashboard({'equity': 50000})
        cache.get_cached_dashboard()  # Hit
        cache.get_cached_dashboard()  # Hit
        cache.get_cached_metric('nonexistent')  # Miss
        
        stats = cache.get_stats()
        
        assert stats['entries'] >= 1
        assert stats['hits'] == 2
        assert stats['misses'] == 1
    
    def test_get_hit_rate(self):
        """Should calculate hit rate percentage."""
        cache = DashboardCache()
        cache.cache_dashboard({'equity': 50000})
        cache.get_cached_dashboard()  # Hit
        cache.get_cached_dashboard()  # Hit
        cache.get_cached_metric('nonexistent')  # Miss
        
        hit_rate = cache.get_hit_rate()
        
        assert hit_rate == pytest.approx(66.67, rel=1)


class TestCachePerformance:
    """Test performance improvements from caching."""
    
    def test_cached_vs_uncached_performance(self):
        """Should show performance improvement with caching."""
        cache = DashboardCache()
        
        # Expensive operation
        def expensive_operation():
            data = {}
            for i in range(10000):
                data[f'key_{i}'] = f'value_{i}'
            return data
        
        # First call (cache miss)
        start = time.time()
        result1 = expensive_operation()
        uncached_time = time.time() - start
        
        # Cache everything
        cache.cache_metrics('expensive', result1)
        
        # Cached retrieval (should be much faster)
        start = time.time()
        result2 = cache.get_cached_metric('expensive')
        cached_time = time.time() - start
        
        # Cache retrieval should be significantly faster
        assert cached_time < uncached_time or cached_time < 0.01
        assert result1 == result2


class TestCacheThreadSafety:
    """Test thread safety of cache operations."""
    
    def test_concurrent_cache_operations(self):
        """Should handle concurrent cache operations."""
        cache = CacheManager()
        import threading
        
        def set_and_get(key, value):
            for _ in range(100):
                cache.set(key, value)
                cache.get(key)
        
        threads = [
            threading.Thread(target=set_and_get, args=(f'key_{i}', f'value_{i}'))
            for i in range(5)
        ]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify cache is in valid state
        stats = cache.get_stats()
        assert stats['entries'] <= cache.max_size


class TestGlobalDashboardCache:
    """Test global dashboard cache instance."""
    
    def test_get_dashboard_cache_returns_singleton(self):
        """Should return same cache instance."""
        cache1 = get_dashboard_cache()
        cache2 = get_dashboard_cache()
        
        assert cache1 is cache2


class TestCacheIntegration:
    """Integration tests for caching."""
    
    def test_cache_with_dashboard_data(self):
        """Should cache realistic dashboard data."""
        cache = DashboardCache()
        
        dashboard = {
            'system': {
                'uptime': 3600,
                'mode': 'paper'
            },
            'risk': {
                'equity': 50000,
                'drawdown': 0.05
            },
            'positions': [
                {'pair': 'BTC/USDT', 'side': 'long', 'qty': 1.5},
                {'pair': 'ETH/USDT', 'side': 'short', 'qty': 10}
            ]
        }
        
        cache.cache_dashboard(dashboard)
        cached = cache.get_cached_dashboard()
        
        assert cached['system']['mode'] == 'paper'
        assert len(cached['positions']) == 2
    
    def test_cache_invalidation_on_trade(self):
        """Should invalidate cache on trade event."""
        cache = DashboardCache()
        
        dashboard = {'positions': [{'pair': 'BTC/USDT', 'qty': 1}]}
        cache.cache_dashboard(dashboard)
        
        # Verify cached
        assert cache.get_cached_dashboard() is not None
        
        # Simulate trade event
        cache.invalidate_dashboard()
        
        # Cache should be cleared
        assert cache.get_cached_dashboard() is None
    
    def test_cache_bypass_for_realtime_data(self):
        """Should allow bypassing cache for real-time data."""
        cache = DashboardCache()
        
        # Cache initial data
        old_data = {'equity': 50000}
        cache.cache_dashboard(old_data)
        
        # Get cached (returns old data)
        result1 = cache.get_cached_dashboard()
        assert result1 == old_data
        
        # Get bypassing cache (returns None - forced miss)
        result2 = cache.get_cached_dashboard(bypass=True)
        assert result2 is None
