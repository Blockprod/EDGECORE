"""
Adaptive pair-cache with regime-aware TTL — extracted from PairTradingStrategy.

Handles loading, saving, and clearing the on-disk JSON cache of cointegrated
pairs.  The cache TTL adapts to the current volatility regime:

* HIGH vol  → short TTL (2 h default) — relationships shift faster
* LOW vol   → long TTL (24 h default)
* NORMAL    → 12 h default

``PairTradingStrategy`` keeps delegation wrappers so callers see no change.
The ``use_cache`` flag remains on ``PairTradingStrategy`` because it is checked
upstream (before calling load/save), so this class does not need it.
"""

from __future__ import annotations

import json
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable

from structlog import get_logger

logger = get_logger(__name__)


class PairCacheManager:
    """Manages on-disk JSON caching of cointegrated pairs.

    The TTL adapts to the current volatility regime via an injected
    ``regime_detector`` reference (shared with the owning strategy so that
    ``strategy.regime_detector.current_regime = X`` propagates instantly).

    Args:
        cache_dir: Directory for cache files.
        regime_detector: ``RegimeDetector`` instance — shared reference.
        config: ``StrategyConfig`` dataclass (for TTL overrides).
        clock: Callable returning current datetime (injectable for tests).
    """

    def __init__(
        self,
        cache_dir: Path,
        regime_detector: Any,
        config: Any,
        clock: Callable[[], Any],
    ) -> None:
        self.cache_dir = cache_dir
        self.regime_detector = regime_detector
        self.config = config
        self._clock = clock

    def clear(self) -> None:
        """Delete all cached pair files."""
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_ttl_hours(self) -> int:
        """Return cache TTL in hours based on current volatility regime."""
        from models.regime_detector import VolatilityRegime

        regime = self.regime_detector.current_regime
        if regime == VolatilityRegime.HIGH:
            return int(self._cfg_val(self.config, "cache_ttl_high_vol", 2))
        elif regime == VolatilityRegime.LOW:
            return int(self._cfg_val(self.config, "cache_ttl_low_vol", 24))
        else:
            return int(self._cfg_val(self.config, "cache_ttl_normal_vol", 12))

    def load_cached_pairs(self, max_age_hours: int | None = None) -> list[tuple] | None:
        """Load cached cointegrated pairs if recent.

        Args:
            max_age_hours: Maximum cache age in hours.  When *None* the
                           adaptive regime-based TTL is used.

        Returns:
            Cached pairs list or None if cache is stale/missing
        """
        if max_age_hours is None:
            max_age_hours = self.get_cache_ttl_hours()

        cache_file = self.cache_dir / "cointegrated_pairs.json"

        if cache_file.exists():
            from datetime import datetime as _dt

            mod_time = _dt.fromtimestamp(cache_file.stat().st_mtime)
            age = self._clock() - mod_time

            if age < timedelta(hours=max_age_hours):
                try:
                    with open(cache_file) as f:
                        pairs = json.load(f)
                    pairs = [tuple(p) for p in pairs]
                    logger.info(
                        "loaded_cached_pairs",
                        pairs_count=len(pairs),
                        age_hours=round(age.total_seconds() / 3600, 2),
                    )
                    return pairs
                except Exception as e:
                    logger.warning("cache_load_failed", error=str(e))

        return None

    def save_cached_pairs(self, pairs: list[tuple]) -> None:
        """Save cointegrated pairs to cache."""
        try:
            cache_file = self.cache_dir / "cointegrated_pairs.json"
            # Write to temporary file first, then rename (atomic operation)
            temp_file = cache_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump([list(p) for p in pairs], f, indent=2)
            # Atomic rename
            temp_file.replace(cache_file)
            logger.info("saved_cointegrated_pairs", count=len(pairs))
        except Exception as e:
            logger.warning("cache_save_failed", error=str(e))

    @staticmethod
    def _cfg_val(config: Any, name: str, default: Any) -> Any:
        """Safe config accessor — returns *default* when attribute is absent."""
        val = getattr(config, name, default)
        if isinstance(val, (int, float, bool, str, type(None))):
            return val
        return default
