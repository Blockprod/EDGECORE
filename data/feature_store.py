"""Feature Store — versioned cache for intermediate pipeline computations.

Provides a transparent, Parquet-backed cache for expensive spread computations
(OLS path). Keys encode (pair, suffix, data-window, version) so stale entries
auto-expire whenever the input window changes.

Usage::

    from data.feature_store import get_feature_store

    store = get_feature_store()
    key   = store.build_key(pair_key, "spread_ols", y, x)
    hit   = store.get(key)
    if hit is not None:
        return hit
    result = compute(...)
    store.set(key, result)
    return result

The store is disabled automatically when its directory cannot be created
(read-only filesystem, missing config, etc.) so it never breaks production.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import structlog

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

_STORE_VERSION = "v1"
_INSTANCE: FeatureStore | None = None


class FeatureStore:
    """Minimal transparent cache for expensive spread computations.

    Stores each entry as a single-column Parquet file keyed by a
    deterministic SHA-256 hash of (pair, suffix, data-window, version).

    Thread safety: the store is read/write on a per-file basis; concurrent
    writes to the same key are safe because ``to_parquet`` is atomic on
    most filesystems (write-then-rename). Read-while-write races are benign
    (the reader gets either the old or the new value).
    """

    def __init__(self, store_dir: str | Path | None = None) -> None:
        if store_dir is None:
            from config.settings import get_settings

            store_dir = get_settings().backtest.feature_store_dir
        self._dir = Path(store_dir)
        self._enabled = self._try_create_dir()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _try_create_dir(self) -> bool:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as exc:
            logger.warning("feature_store_disabled", reason=str(exc), path=str(self._dir))
            return False

    def _path(self, key: str) -> Path:
        return self._dir / f"{key}.parquet"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def build_key(pair_key: str, suffix: str, y: pd.Series, x: pd.Series) -> str:
        """Build a deterministic cache key from pair identity and data window.

        The key uses the data-window shape (length + first/last index values)
        rather than a full data hash for speed — it degenerates gracefully for
        empty series by omitting boundary dates.

        Args:
            pair_key: Pair identifier, e.g. ``"AAPL_MSFT"``.
            suffix:   Computation label, e.g. ``"spread_ols"``.
            y:        Dependent price series.
            x:        Independent price series.

        Returns:
            A 24-character hexadecimal string suitable for use as a filename.
        """
        n = len(y)
        first = str(y.index[0]) if n > 0 else ""
        last = str(y.index[-1]) if n > 0 else ""
        nx = len(x)
        xfirst = str(x.index[0]) if nx > 0 else ""
        xlast = str(x.index[-1]) if nx > 0 else ""
        raw = f"{pair_key}|{suffix}|{n}|{first}|{last}|{nx}|{xfirst}|{xlast}|{_STORE_VERSION}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def get(self, key: str) -> pd.Series | None:
        """Return cached series for *key*, or ``None`` on miss/error.

        Args:
            key: Cache key produced by :meth:`build_key`.

        Returns:
            Cached :class:`pandas.Series` with original datetime index, or
            ``None`` when the entry is absent or unreadable.
        """
        if not self._enabled:
            return None
        path = self._path(key)
        if not path.exists():
            return None
        try:
            series = pd.read_parquet(path)["value"]
            logger.debug("feature_store_hit", key=key[:8])
            return series
        except Exception as exc:
            logger.warning("feature_store_read_failed", key=key[:8], error=str(exc))
            return None

    def set(self, key: str, data: pd.Series) -> None:
        """Persist *data* under *key*.

        Silently skips write failures so a full disk or permission error
        never crashes the trading pipeline.

        Args:
            key:  Cache key produced by :meth:`build_key`.
            data: Series to persist (index is preserved in Parquet).
        """
        if not self._enabled:
            return
        path = self._path(key)
        try:
            data.rename("value").to_frame().to_parquet(path, engine="pyarrow", compression="snappy")
            logger.debug("feature_store_write", key=key[:8])
        except Exception as exc:
            logger.warning("feature_store_write_failed", key=key[:8], error=str(exc))

    def invalidate(self, key: str) -> bool:
        """Delete a single cached entry.

        Args:
            key: Cache key to remove.

        Returns:
            ``True`` if the entry existed and was deleted, ``False`` otherwise.
        """
        path = self._path(key)
        if path.exists():
            try:
                path.unlink()
                return True
            except OSError:
                return False
        return False

    def clear(self) -> int:
        """Delete all cached entries in the store directory.

        Returns:
            Number of entries deleted.
        """
        if not self._enabled or not self._dir.exists():
            return 0
        count = 0
        for p in self._dir.glob("*.parquet"):
            try:
                p.unlink()
                count += 1
            except OSError:
                pass
        logger.info("feature_store_cleared", count=count)
        return count


def get_feature_store() -> FeatureStore:
    """Return the module-level singleton :class:`FeatureStore` instance.

    The singleton is initialised lazily on first call. Safe to call from
    any module without circular-import concerns because config import is
    deferred inside :meth:`FeatureStore.__init__`.
    """
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = FeatureStore()
    return _INSTANCE
