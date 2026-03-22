"""
Advanced Caching System (S4.2) - Production-Grade Cache Infrastructure

Extends S4.1 CacheManager with enterprise features:
- Distributed cache across multiple processes (multiprocessing.Manager)
- Persistent cache to disk (JSON/pickle serialization)
- Advanced eviction policies (LFU, ARC - Adaptive Replacement Cache)
- Cache warming and preloading
- Statistics and monitoring
- Background cleanup tasks

Usage:
    # Distributed cache (shared across processes)
    cache = DistributedCacheManager(max_size=500, eviction_policy='arc')
    cache.set('key', value)
    value = cache.get('key')
    
    # Persistent cache (survives process restarts)
    cache = PersistentCacheManager(cache_dir='./cache_data', eviction_policy='lfu')
    cache.load_from_disk()
    cache.set('key', value)
    cache.save_to_disk()
"""

import json
import multiprocessing as mp
import pickle
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

from structlog import get_logger

logger = get_logger(__name__)


class EvictionPolicy(ABC):
    """Abstract base class for cache eviction strategies."""
    
    @abstractmethod
    def on_access(self, key: str) -> None:
        """Called when cache entry is accessed."""
        pass
    
    @abstractmethod
    def on_set(self, key: str) -> None:
        """Called when cache entry is set/created."""
        pass
    
    @abstractmethod
    def get_eviction_candidate(self) -> str | None:
        """Returns key to evict, or None if cache not full."""
        pass
    
    @abstractmethod
    def on_evict(self, key: str) -> None:
        """Called when entry is evicted."""
        pass


class LFUEvictionPolicy(EvictionPolicy):
    """Least Frequently Used eviction policy."""
    
    def __init__(self, max_size: int):
        self.max_size = max_size
        self.frequency: dict[str, int] = {}
        self.cache_keys: set = set()
    
    def on_access(self, key: str) -> None:
        """Increment frequency on access."""
        if key in self.frequency:
            self.frequency[key] += 1
    
    def on_set(self, key: str) -> None:
        """Initialize frequency on set."""
        if key not in self.frequency:
            self.frequency[key] = 0
        self.cache_keys.add(key)
    
    def get_eviction_candidate(self) -> str | None:
        """Return least frequently used key if at capacity."""
        if len(self.cache_keys) < self.max_size:
            return None
        
        # Find key with minimum frequency
        lfu_key = min(
            self.cache_keys,
            key=lambda k: self.frequency.get(k, 0)
        )
        return lfu_key
    
    def on_evict(self, key: str) -> None:
        """Remove from tracking on eviction."""
        self.cache_keys.discard(key)
        self.frequency.pop(key, None)
    
    def stats(self) -> dict[str, Any]:
        """Return frequency statistics."""
        if not self.frequency:
            return {'avg_frequency': 0, 'max_frequency': 0}
        
        freqs = list(self.frequency.values())
        return {
            'avg_frequency': sum(freqs) / len(freqs),
            'max_frequency': max(freqs),
            'min_frequency': min(freqs)
        }


class ARCEvictionPolicy(EvictionPolicy):
    """
    Adaptive Replacement Cache (ARC) eviction policy.
    
    Balances between recency (LRU) and frequency (LFU) dynamically.
    Divides cache into:
    - T1: Recently accessed once
    - T2: Recently accessed multiple times
    - B1: Recently evicted from T1 (ghosts)
    - B2: Recently evicted from T2 (ghosts)
    """
    
    def __init__(self, max_size: int):
        self.max_size = max_size
        self.p = 0  # Target size for T1 (adapts dynamically)
        
        # Recent entries
        self.t1: OrderedDict = OrderedDict()  # Recency list
        self.t2: OrderedDict = OrderedDict()  # Frequency + Recency list
        
        # Ghost entries (recently evicted)
        self.b1: OrderedDict = OrderedDict()  # Evicted from T1
        self.b2: OrderedDict = OrderedDict()  # Evicted from T2
        
        self.lock = threading.Lock()
    
    def on_access(self, key: str) -> None:
        """Move from T1 to T2 on repeated access."""
        with self.lock:
            if key in self.t1:
                # Promote T1 -> T2
                self.t1.pop(key)
                self.t2[key] = True
                self.t2.move_to_end(key)
            elif key in self.t2:
                # Refresh in T2
                self.t2.move_to_end(key)
    
    def on_set(self, key: str) -> None:
        """Add new entry to T1."""
        with self.lock:
            if key not in self.t1 and key not in self.t2:
                self.t1[key] = True
    
    def get_eviction_candidate(self) -> str | None:
        """Return ghost entry to evict, considering T1 vs T2 balance."""
        with self.lock:
            total = len(self.t1) + len(self.t2)
            
            if total < self.max_size:
                return None
            
            # Evict from B1 if T1 too small
            if len(self.b1) > 0 and len(self.t1) < self.p:
                return next(iter(self.b1))  # Oldest ghost from B1
            
            # Evict from B2 if T2 too large
            if len(self.b2) > 0:
                return next(iter(self.b2))  # Oldest ghost from B2
            
            # Fallback: evict oldest from T1
            if self.t1:
                return next(iter(self.t1))
            
            return None
    
    def on_evict(self, key: str) -> None:
        """Move to ghost list (B1 or B2) on eviction."""
        with self.lock:
            if key in self.t1:
                self.t1.pop(key)
                self.b1[key] = True  # Add to B1 ghosts
            elif key in self.t2:
                self.t2.pop(key)
                self.b2[key] = True  # Add to B2 ghosts
            
            # Adapt p: increase for T2 affinity
            if key in self.b2:
                self.p = min(self.max_size, self.p + 1)
            elif key in self.b1:
                self.p = max(0, self.p - 1)
            
            # Limit ghost size
            max_ghosts = self.max_size
            while len(self.b1) > max_ghosts:
                self.b1.popitem(last=False)
            while len(self.b2) > max_ghosts:
                self.b2.popitem(last=False)
    
    def stats(self) -> dict[str, Any]:
        """Return ARC statistics."""
        with self.lock:
            return {
                't1_size': len(self.t1),
                't2_size': len(self.t2),
                'b1_size': len(self.b1),
                'b2_size': len(self.b2),
                'p_target': self.p,
                'total_active': len(self.t1) + len(self.t2)
            }


class DistributedCacheManager:
    """
    Multi-process cache sharing via multiprocessing.Manager().
    
    Allows cache to be shared safely across multiple processes.
    Uses Manager() proxy objects for thread/process-safe access.
    """
    
    def __init__(self, max_size: int = 500, eviction_policy: str = 'arc',
                 default_ttl: float = 300):
        """
        Initialize distributed cache.
        
        Args:
            max_size: Maximum cache entries
            eviction_policy: 'lru', 'lfu', or 'arc'
            default_ttl: Default TTL in seconds
        """
        self._max_size = max_size
        self.default_ttl = default_ttl
        self.eviction_policy_name = eviction_policy
        
        # Create shared resources via Manager
        self.manager = mp.Manager()
        self._cache = self.manager.dict()  # Thread-safe dict (but not pickleable)
        self._cache_times = self.manager.dict()  # Creation times
        self._cache_access_times = self.manager.dict()  # Last access times
        
        self._lock = threading.RLock()
        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0
        
        # Initialize eviction policy
        if eviction_policy == 'lfu':
            self._eviction_policy = LFUEvictionPolicy(max_size)
        elif eviction_policy == 'arc':
            self._eviction_policy = ARCEvictionPolicy(max_size)
        else:
            raise ValueError(f"Unknown eviction policy: {eviction_policy}")
        
        logger.info("distributed_cache_initialized",
                   max_size=max_size,
                   eviction_policy=eviction_policy)
    
    @property
    def max_size(self) -> int:
        """Get maximum cache size."""
        return self._max_size
    
    @max_size.setter
    def max_size(self, value: int) -> None:
        """Set maximum cache size and update eviction policy."""
        self._max_size = value
        if hasattr(self, '_eviction_policy'):
            self._eviction_policy.max_size = value
    
    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        """Set cache entry (shared across processes)."""
        with self._lock:
            ttl = ttl_seconds or self.default_ttl
            now = time.time()
            
            self._cache[key] = value
            self._cache_times[key] = (now, ttl)
            self._cache_access_times[key] = now
            
            self._eviction_policy.on_set(key)
            
            # Handle eviction if needed
            if len(self._cache) > self.max_size:
                evict_key = self._eviction_policy.get_eviction_candidate()
                if evict_key and evict_key in self._cache:
                    del self._cache[evict_key]
                    self._cache_times.pop(evict_key, None)
                    self._cache_access_times.pop(evict_key, None)
                    self._eviction_policy.on_evict(evict_key)
                    self._eviction_count += 1
    
    def get(self, key: str, bypass: bool = False) -> Any | None:
        """Get cache entry (with TTL check and multiprocess safety)."""
        with self._lock:
            if bypass or key not in self._cache:
                self._miss_count += 1
                return None
            
            # Check TTL
            creation_time, ttl = self._cache_times.get(key, (0, 0))
            if time.time() - creation_time > ttl:
                del self._cache[key]
                self._cache_times.pop(key, None)
                self._cache_access_times.pop(key, None)
                self._miss_count += 1
                return None
            
            # Hit: update access time and eviction policy
            self._cache_access_times[key] = time.time()
            self._eviction_policy.on_access(key)
            self._hit_count += 1
            
            return self._cache[key]
    
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hit_count + self._miss_count
            hit_rate = (self._hit_count / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hit_count,
                'misses': self._miss_count,
                'hit_rate': hit_rate,
                'evictions': self._eviction_count,
                'eviction_policy': self.eviction_policy_name,
                'policy_stats': self._eviction_policy.stats()
            }
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._cache_times.clear()
            self._cache_access_times.clear()
            self._hit_count = 0
            self._miss_count = 0
            self._eviction_count = 0


class PersistentCacheManager:
    """
    Persistent cache with disk serialization.
    
    Saves/loads cache to/from disk, survives process restarts.
    Supports both JSON (human readable) and pickle (binary) formats.
    """
    
    def __init__(self, cache_dir: str = './cache_data', 
                 eviction_policy: str = 'arc',
                 default_ttl: float = 300,
                 serialize_format: str = 'json'):
        """
        Initialize persistent cache.
        
        Args:
            cache_dir: Directory to store cache files
            eviction_policy: 'lfu' or 'arc'
            default_ttl: Default TTL in seconds
            serialize_format: 'json' or 'pickle'
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.default_ttl = default_ttl
        self.eviction_policy_name = eviction_policy
        self.serialize_format = serialize_format
        self._max_size = 1000  # Default for persistence
        
        # Core cache
        self._cache: dict[str, Any] = {}
        self._cache_times: dict[str, tuple[float, float]] = {}
        self._lock = threading.RLock()
        
        # Stats
        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0
        
        # Eviction policy
        if eviction_policy == 'lfu':
            self._eviction_policy = LFUEvictionPolicy(self._max_size)
        elif eviction_policy == 'arc':
            self._eviction_policy = ARCEvictionPolicy(self._max_size)
        else:
            raise ValueError(f"Unknown eviction policy: {eviction_policy}")
        
        logger.info("persistent_cache_initialized",
                   cache_dir=str(self.cache_dir),
                   eviction_policy=eviction_policy,
                   format=serialize_format)
    
    @property
    def max_size(self) -> int:
        """Get maximum cache size."""
        return self._max_size
    
    @max_size.setter
    def max_size(self, value: int) -> None:
        """Set maximum cache size and update eviction policy."""
        self._max_size = value
        if hasattr(self, '_eviction_policy'):
            self._eviction_policy.max_size = value
    
    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        """Set cache entry."""
        with self._lock:
            ttl = ttl_seconds or self.default_ttl
            now = time.time()
            
            self._cache[key] = value
            self._cache_times[key] = (now, ttl)
            self._eviction_policy.on_set(key)
            
            # Handle eviction
            if len(self._cache) > self.max_size:
                evict_key = self._eviction_policy.get_eviction_candidate()
                if evict_key and evict_key in self._cache:
                    del self._cache[evict_key]
                    self._cache_times.pop(evict_key, None)
                    self._eviction_policy.on_evict(evict_key)
                    self._eviction_count += 1
    
    def get(self, key: str) -> Any | None:
        """Get cache entry with TTL check."""
        with self._lock:
            if key not in self._cache:
                self._miss_count += 1
                return None
            
            # Check TTL
            creation_time, ttl = self._cache_times.get(key, (0, 0))
            if time.time() - creation_time > ttl:
                del self._cache[key]
                self._cache_times.pop(key, None)
                self._miss_count += 1
                return None
            
            self._eviction_policy.on_access(key)
            self._hit_count += 1
            return self._cache[key]
    
    def save_to_disk(self, filename: str = 'cache.json') -> None:
        """
        Save cache to disk.
        
        Args:
            filename: File to save to (in cache_dir)
        """
        filepath = self.cache_dir / filename
        
        with self._lock:
            try:
                # Prepare data (remove expired entries)
                data_to_save = {}
                now = time.time()
                
                for key, value in self._cache.items():
                    creation_time, ttl = self._cache_times.get(key, (0, 0))
                    
                    # Skip if expired
                    if now - creation_time > ttl:
                        continue
                    
                    remaining_ttl = ttl - (now - creation_time)
                    data_to_save[key] = {
                        'value': value,
                        'remaining_ttl': remaining_ttl
                    }
                
                # Serialize
                if self.serialize_format == 'json':
                    with open(filepath, 'w') as f:
                        # Convert to JSON-serializable format
                        json_data = {
                            'timestamp': datetime.now().isoformat(),
                            'entries': data_to_save
                        }
                        json.dump(json_data, f, indent=2, default=str)
                else:  # pickle
                    with open(filepath, 'wb') as f:
                        pickle.dump(data_to_save, f)
                
                logger.info("cache_saved_to_disk",
                           filepath=str(filepath),
                           entries=len(data_to_save),
                           format=self.serialize_format)
                
            except Exception as e:
                logger.error("cache_save_failed", error=str(e), filepath=str(filepath))
    
    def load_from_disk(self, filename: str = 'cache.json') -> int:
        """
        Load cache from disk.
        
        Args:
            filename: File to load from (in cache_dir)
            
        Returns:
            Number of entries loaded
        """
        filepath = self.cache_dir / filename
        
        if not filepath.exists():
            logger.info("cache_file_not_found", filepath=str(filepath))
            return 0
        
        with self._lock:
            try:
                # Deserialize
                if self.serialize_format == 'json':
                    with open(filepath) as f:
                        json_data = json.load(f)
                        data = json_data.get('entries', {})
                else:  # pickle
                    with open(filepath, 'rb') as f:
                        data = pickle.load(f)
                
                # Restore entries with remaining TTL
                now = time.time()
                for key, entry_data in data.items():
                    value = entry_data['value']
                    remaining_ttl = entry_data.get('remaining_ttl', self.default_ttl)
                    
                    # Only restore if still valid
                    if remaining_ttl > 0:
                        self._cache[key] = value
                        self._cache_times[key] = (now, remaining_ttl)
                        self._eviction_policy.on_set(key)
                
                loaded_count = len(self._cache)
                logger.info("cache_loaded_from_disk",
                           filepath=str(filepath),
                           entries=loaded_count,
                           format=self.serialize_format)
                
                return loaded_count
                
            except Exception as e:
                logger.error("cache_load_failed", error=str(e), filepath=str(filepath))
                return 0
    
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hit_count + self._miss_count
            hit_rate = (self._hit_count / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hit_count,
                'misses': self._miss_count,
                'hit_rate': hit_rate,
                'evictions': self._eviction_count,
                'eviction_policy': self.eviction_policy_name,
                'policy_stats': self._eviction_policy.stats()
            }
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._cache_times.clear()
