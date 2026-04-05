"""
Cache layer for expensive dashboard operations.

Provides:
- TTL-based caching with configurable expiration
- LRU (Least Recently Used) eviction policy
- Automatic invalidation on data changes
- Performance statistics (hit rate, evictions, memory)
- Thread-safe operations
"""

import time
from typing import Dict, Any, Optional, Callable
from collections import OrderedDict
import threading
import time
from collections import OrderedDict
from typing import Any, Callable


class CacheEntry:
    """Represents a single cache entry with metadata."""

    def __init__(self, key: str, value: Any, ttl_seconds: float = 300):
        self.key = key
        self.value = value
        self.ttl_seconds = ttl_seconds
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.access_count = 0

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() - self.created_at > self.ttl_seconds

    def touch(self) -> None:
        """Update last access time."""
        self.last_accessed = time.time()
        self.access_count += 1


class CacheManager:
    """Thread-safe cache manager with TTL and LRU eviction."""

    def __init__(self, max_size: int = 100, default_ttl: float = 300):
        """
        Initialize cache manager.

        Args:
            max_size: Maximum number of entries (LRU eviction after)
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0

    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        """
        Set cache entry.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Optional TTL (uses default if not specified)
        """
        with self._lock:
            ttl = ttl_seconds or self.default_ttl

            # Remove old entry if exists
            if key in self._cache:
                del self._cache[key]

            # Add new entry (OrderedDict maintains insertion order)
            entry = CacheEntry(key, value, ttl)
            self._cache[key] = entry

            # Evict LRU if over capacity
            if len(self._cache) > self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._eviction_count += 1

    def get(self, key: str, bypass: bool = False) -> Any | None:
        """
        Get cache entry.

        Args:
            key: Cache key
            bypass: If True, bypass cache (force miss)

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if bypass or key not in self._cache:
                self._miss_count += 1
                return None

            entry = self._cache[key]

            # Check expiration
            if entry.is_expired():
                del self._cache[key]
                self._miss_count += 1
                return None

            # Hit - update access time and move to end (most recently used)
            entry.touch()
            # Move to end to maintain LRU order
            self._cache.move_to_end(key)
            self._hit_count += 1

            return entry.value

    def invalidate(self, pattern: str | None = None) -> int:
        """
        Invalidate cache entries.

        Args:
            pattern: Optional pattern to match keys (e.g., 'dashboard_*')
                    If None, invalidates all entries

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            if pattern is None:
                # Invalidate all
                count = len(self._cache)
                self._cache.clear()
                return count

            # Invalidate matching pattern
            keys_to_delete = [k for k in self._cache.keys() if self._pattern_matches(k, pattern)]

            for key in keys_to_delete:
                del self._cache[key]

            return len(keys_to_delete)

    def invalidate_key(self, key: str) -> bool:
        """
        Invalidate specific cache key.

        Args:
            key: Cache key to invalidate

        Returns:
            True if key was removed, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        with self._lock:
            if key not in self._cache:
                return False

            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                return False

            return True

    def clear(self) -> int:
        """Clear all cache entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total_requests * 100 if total_requests > 0 else 0

            total_ttl = sum(entry.ttl_seconds for entry in self._cache.values())
            avg_ttl = total_ttl / len(self._cache) if self._cache else 0

            return {
                "entries": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hit_count,
                "misses": self._miss_count,
                "hit_rate_percent": hit_rate,
                "evictions": self._eviction_count,
                "avg_ttl_seconds": avg_ttl,
            }

    def get_details(self) -> dict[str, Any]:
        """Get detailed cache entry information."""
        with self._lock:
            details = {}
            for key, entry in self._cache.items():
                age = time.time() - entry.created_at
                remaining_ttl = entry.ttl_seconds - age

                details[key] = {
                    "value_size": len(str(entry.value)),
                    "age_seconds": age,
                    "remaining_ttl_seconds": max(0, remaining_ttl),
                    "access_count": entry.access_count,
                    "is_expired": entry.is_expired(),
                }

            return details

    @staticmethod
    def _pattern_matches(key: str, pattern: str) -> bool:
        """Check if key matches pattern (simple wildcard matching)."""
        import fnmatch

        return fnmatch.fnmatch(key, pattern)


class CachedFunction:
    """Decorator for caching function results."""

    def __init__(self, cache_manager: CacheManager, ttl: float | None = None):
        """
        Initialize cached function decorator.

        Args:
            cache_manager: CacheManager instance
            ttl: Time-to-live for cached results
        """
        self.cache_manager = cache_manager
        self.ttl = ttl

    def __call__(self, func: Callable) -> Callable:
        """Wrap function with caching."""

        def wrapper(*args, bypass: bool = False, **kwargs) -> Any:
            # Generate cache key from function name and arguments
            cache_key = self._generate_key(func.__name__, args, kwargs)

            # Try to get from cache
            cached_value = self.cache_manager.get(cache_key, bypass=bypass)
            if cached_value is not None:
                return cached_value

            # Cache miss - call function
            result = func(*args, **kwargs)

            # Store in cache
            self.cache_manager.set(cache_key, result, self.ttl)

            return result

        _wrapper_any: Any = wrapper
        _wrapper_any._cache_key_func = self._generate_key
        _wrapper_any._cache_manager = self.cache_manager
        return wrapper

    @staticmethod
    def _generate_key(func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate cache key from function and arguments."""
        arg_str = "_".join(str(arg) for arg in args)
        kwarg_str = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))

        parts = [func_name, arg_str, kwarg_str]
        return ":".join(p for p in parts if p)


class DashboardCache:
    """Specialized cache for dashboard operations."""

    def __init__(self, max_size: int = 50):
        """Initialize dashboard cache."""
        self._manager = CacheManager(max_size=max_size, default_ttl=30)
        self._lock = threading.RLock()

    def cache_dashboard(self, dashboard_data: dict[str, Any]) -> None:
        """Cache complete dashboard snapshot."""
        self._manager.set("dashboard_full", dashboard_data, ttl_seconds=30)

    def get_cached_dashboard(self, bypass: bool = False) -> dict[str, Any] | None:
        """Get cached dashboard snapshot."""
        return self._manager.get("dashboard_full", bypass=bypass)

    def cache_metrics(self, metric_type: str, data: dict[str, Any]) -> None:
        """Cache specific metric type."""
        key = f"metrics_{metric_type}"
        self._manager.set(key, data, ttl_seconds=30)

    def get_cached_metric(self, metric_type: str, bypass: bool = False) -> dict[str, Any] | None:
        """Get cached metric."""
        key = f"metrics_{metric_type}"
        return self._manager.get(key, bypass=bypass)

    def invalidate_dashboard(self) -> int:
        """Invalidate all dashboard caches."""
        return self._manager.invalidate()

    def invalidate_metric(self, metric_type: str) -> bool:
        """Invalidate specific metric cache."""
        return self._manager.invalidate_key(f"metrics_{metric_type}")

    def get_stats(self) -> dict:
        """Get cache statistics."""
        return self._manager.get_stats()

    def get_hit_rate(self) -> float:
        """Get cache hit rate as percentage."""
        stats = self.get_stats()
        return stats["hit_rate_percent"]


# Global dashboard cache instance
_dashboard_cache = DashboardCache(max_size=50)


def get_dashboard_cache() -> DashboardCache:
    """Get global dashboard cache instance."""
    return _dashboard_cache
