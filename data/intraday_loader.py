"""
Phase 3.1 ÔÇö Intraday Data Loader.

Loads 5-minute bars from IBKR and caches them in Parquet format
partitioned by symbol and date.  Provides a clean interface for
the intraday backtest simulator.

Architecture
------------
- IBKR returns up to 1 year of 5-min bars per request
- Bars are cached per symbol in ``data/cache/intraday/{symbol}.parquet``
- Re-fetches only missing date ranges (incremental)
- Returns a DataFrame[symbols] of close prices with DatetimeIndex
  (same interface as daily ``load_price_data()``)
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)

# IBKR 5-min bars: max ~1 year history.  We request in 30-day chunks to
# respect IBKR pacing rules (Ôëñ60 requests / 10 min).
_CHUNK_DAYS = 30
_SLEEP_BETWEEN_SYMBOLS = 0.6  # seconds
_SLEEP_BETWEEN_CHUNKS = 1.0


class IntradayLoader:
    """Load and cache 5-minute intraday bars.

    Usage::

        loader = IntradayLoader()
        prices5m = loader.load(
            symbols=["AAPL", "MSFT"],
            start_date="2025-01-01",
            end_date="2025-06-01",
        )
        # prices5m: DataFrame with DatetimeIndex (5-min), one column per symbol
    """

    def __init__(self, cache_dir: str = "data/cache/intraday"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        bar_size: str = "5 mins",
    ) -> pd.DataFrame:
        """Load 5-min close prices for *symbols* over [start_date, end_date].

        Returns a DataFrame with DatetimeIndex (5-min frequency) and one
        column per symbol (close prices).  Missing bars are forward-filled
        to align all symbols.
        """
        frames: Dict[str, pd.Series] = {}
        for sym in symbols:
            try:
                df = self._load_symbol(sym, start_date, end_date, bar_size)
                if df is not None and not df.empty:
                    frames[sym] = df["close"]
            except Exception as exc:
                logger.warning(
                    "intraday_load_failed", symbol=sym, error=str(exc)[:200]
                )

        if not frames:
            logger.error("intraday_load_no_data", symbols=symbols)
            return pd.DataFrame()

        prices = pd.DataFrame(frames).sort_index()
        prices = prices.ffill().dropna(how="all")
        logger.info(
            "intraday_data_loaded",
            symbols=len(frames),
            bars=len(prices),
            start=str(prices.index[0])[:19],
            end=str(prices.index[-1])[:19],
        )
        return prices

    # ------------------------------------------------------------------
    # Per-symbol load with caching
    # ------------------------------------------------------------------

    def _load_symbol(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        bar_size: str,
    ) -> Optional[pd.DataFrame]:
        """Load from cache or fetch from IBKR."""
        cache_path = self.cache_dir / f"{symbol}.parquet"

        # Try cache first
        cached_df = self._read_cache(cache_path, start_date, end_date)
        if cached_df is not None:
            logger.debug("intraday_cache_hit", symbol=symbol, bars=len(cached_df))
            return cached_df

        # Fetch from IBKR
        df = self._fetch_ibkr(symbol, start_date, end_date, bar_size)
        if df is not None and not df.empty:
            self._write_cache(cache_path, df)
        return df

    def _read_cache(
        self, path: Path, start_date: str, end_date: str
    ) -> Optional[pd.DataFrame]:
        """Read cached Parquet and slice to requested range."""
        if not path.exists():
            return None
        try:
            df = pd.read_parquet(path)
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            mask = (df.index >= pd.Timestamp(start_date)) & (
                df.index <= pd.Timestamp(end_date) + pd.Timedelta(days=1)
            )
            sliced = df.loc[mask]
            if len(sliced) < 10:
                return None  # insufficient ÔÇö re-fetch
            return sliced
        except Exception:
            return None

    def _write_cache(self, path: Path, df: pd.DataFrame) -> None:
        """Append/merge data into the Parquet cache."""
        if path.exists():
            try:
                existing = pd.read_parquet(path)
                if not isinstance(existing.index, pd.DatetimeIndex):
                    existing.index = pd.to_datetime(existing.index)
                df = pd.concat([existing, df])
                df = df[~df.index.duplicated(keep="last")].sort_index()
            except Exception:
                pass  # overwrite on error
        df.to_parquet(path, engine="pyarrow")

    def _fetch_ibkr(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        bar_size: str,
    ) -> Optional[pd.DataFrame]:
        """Fetch 5-min bars from IBKR in chunks."""
        try:
            from execution.ibkr_engine import IBGatewaySync
        except ImportError:
            logger.error("ibkr_engine_not_available")
            return None

        from data.loader import _next_client_id

        engine = IBGatewaySync(
            host="127.0.0.1", port=4002, client_id=_next_client_id(), timeout=60
        )
        engine.connect()

        all_bars: list = []
        try:
            # IBKR pacing: 5-min bars come in max 30-day chunks
            chunk_start = pd.Timestamp(start_date)
            chunk_end = pd.Timestamp(end_date)

            while chunk_start < chunk_end:
                req_end = min(chunk_start + pd.Timedelta(days=_CHUNK_DAYS), chunk_end)
                duration = f"{(req_end - chunk_start).days} D"
                try:
                    bars = engine.get_historical_data(
                        symbol=symbol,
                        duration=duration,
                        bar_size=bar_size,
                        what_to_show="ADJUSTED_LAST",
                        end_date=req_end.strftime("%Y%m%d %H:%M:%S"),
                    )
                    if bars:
                        all_bars.extend(bars)
                except Exception as chunk_exc:
                    logger.warning(
                        "intraday_chunk_failed",
                        symbol=symbol,
                        chunk_start=str(chunk_start)[:10],
                        error=str(chunk_exc)[:120],
                    )
                chunk_start = req_end
                time.sleep(_SLEEP_BETWEEN_CHUNKS)
        finally:
            engine.disconnect()

        if not all_bars:
            return None

        df = pd.DataFrame(
            {
                "open": [b.open for b in all_bars],
                "high": [b.high for b in all_bars],
                "low": [b.low for b in all_bars],
                "close": [b.close for b in all_bars],
                "volume": [getattr(b, "volume", 0) for b in all_bars],
            },
            index=pd.DatetimeIndex([b.date for b in all_bars]),
        )
        df.index.name = "datetime"
        df = df[~df.index.duplicated(keep="last")].sort_index()
        logger.info(
            "intraday_ibkr_fetched",
            symbol=symbol,
            bars=len(df),
            start=str(df.index[0])[:19],
            end=str(df.index[-1])[:19],
        )
        time.sleep(_SLEEP_BETWEEN_SYMBOLS)
        return df

    # ------------------------------------------------------------------
    # Synthetic intraday data (for backtesting without IBKR connection)
    # ------------------------------------------------------------------

    @staticmethod
    def generate_synthetic_intraday(
        daily_prices: pd.DataFrame,
        bars_per_day: int = 78,
    ) -> pd.DataFrame:
        """Generate synthetic intraday bars from daily close prices.

        For each trading day, creates *bars_per_day* intraday bars using a
        Geometric Brownian bridge from previous close to current close.

        Uses the Cython-accelerated ``brownian_bridge_batch_fast`` when
        available (5-10x faster), with a pure-Python fallback.

        Args:
            daily_prices: DataFrame[symbols] with DatetimeIndex (daily).
            bars_per_day: Number of intraday bars per trading day.

        Returns:
            DataFrame[symbols] with DatetimeIndex and one bar per interval.
        """
        import numpy as np

        # ---- Cython fast path -------------------------------------------
        try:
            from models.cointegration_fast import brownian_bridge_batch_fast as _bb_fast
            _cython_bb = True
        except ImportError:
            _cython_bb = False

        if _cython_bb:
            syms = [s for s in daily_prices.columns if daily_prices[s].count() >= 2]
            if not syms:
                return pd.DataFrame()
            mat = daily_prices[syms].ffill().dropna(how='all')
            if len(mat) < 2:
                return pd.DataFrame()

            mat_vals = np.ascontiguousarray(mat.values, dtype=np.float64)
            n_days, n_sym = mat_vals.shape
            noise = np.ascontiguousarray(
                np.random.normal(0, 1, (n_days - 1, bars_per_day, n_sym)),
                dtype=np.float64,
            )
            # out shape: (n_days-1)*bars_per_day ├ù n_sym
            out = _bb_fast(mat_vals, noise, bars_per_day)

            # Build timestamp index once (same for all symbols)
            timestamps: list = []
            for day in mat.index[1:]:
                market_open = pd.Timestamp(day).replace(hour=9, minute=30, second=0)
                for j in range(bars_per_day):
                    timestamps.append(market_open + pd.Timedelta(minutes=5 * j))

            return pd.DataFrame(
                out,
                index=pd.DatetimeIndex(timestamps),
                columns=syms,
            ).sort_index()

        # ---- Python fallback (original, per-symbol loop) ----------------
        result_frames: Dict[str, pd.Series] = {}

        for sym in daily_prices.columns:
            closes = daily_prices[sym].dropna()
            if len(closes) < 2:
                continue

            all_times: list = []
            all_prices: list = []

            for i in range(1, len(closes)):
                prev_close = closes.iloc[i - 1]
                cur_close = closes.iloc[i]
                day = closes.index[i]

                t = np.linspace(0, 1, bars_per_day + 1)[1:]
                increments = np.random.normal(0, 1, bars_per_day)
                W = np.cumsum(increments) / np.sqrt(bars_per_day)
                bridge = W - t * W[-1]
                daily_ret = (cur_close - prev_close) / prev_close if prev_close > 0 else 0
                vol = max(abs(daily_ret) * 0.5, 0.002)
                path = prev_close * (1 + daily_ret * t + vol * bridge)

                market_open = pd.Timestamp(day).replace(hour=9, minute=30, second=0)
                timestamps = [
                    market_open + pd.Timedelta(minutes=5 * j)
                    for j in range(bars_per_day)
                ]
                all_times.extend(timestamps)
                all_prices.extend(path.tolist())

            result_frames[sym] = pd.Series(
                all_prices, index=pd.DatetimeIndex(all_times), name=sym
            )

        if not result_frames:
            return pd.DataFrame()

        return pd.DataFrame(result_frames).sort_index()


__all__ = ["IntradayLoader"]
