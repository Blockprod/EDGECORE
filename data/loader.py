import pandas as pd
from typing import Dict, List, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from structlog import get_logger
from data.validators import OHLCVValidator, DataValidationError
import threading

logger = get_logger(__name__)


def load_price_data(
    symbols: List[str],
    timeframe: str = "1d",
    limit: int = 252,
) -> pd.DataFrame:
    """Convenience function for live/paper trading: load latest prices.

    Returns a DataFrame with columns = symbols, values = close prices.
    Uses IBGatewaySync (port 4002) with a single sequential connection.
    """
    from execution.ibkr_engine import IBGatewaySync
    import time as _time

    bar_size_map = {"1d": "1 day", "1h": "1 hour", "4h": "4 hours"}
    bar_size = bar_size_map.get(timeframe, "1 day")
    duration = f"{max(1, limit // 252)} Y" if timeframe == "1d" else f"{limit} D"

    engine = IBGatewaySync(
        host="127.0.0.1", port=4002, client_id=_next_client_id(), timeout=30
    )
    engine.connect()

    frames: Dict[str, pd.Series] = {}
    try:
        for sym in symbols:
            try:
                bars = engine.get_historical_data(
                    symbol=sym, duration=duration,
                    bar_size=bar_size, what_to_show="ADJUSTED_LAST",
                )
                if bars:
                    s = pd.Series(
                        [b.close for b in bars],
                        index=pd.DatetimeIndex([b.date for b in bars]),
                        name=sym,
                    )
                    frames[sym] = s
                    logger.debug("load_price_data_ok", symbol=sym, bars=len(bars))
                else:
                    logger.warning("load_price_data_empty", symbol=sym)
                _time.sleep(0.5)  # IBKR rate limiting
            except Exception as exc:
                logger.error("load_price_data_failed", symbol=sym, error=str(exc)[:120])
    finally:
        engine.disconnect()

    if not frames:
        return pd.DataFrame()
    return pd.DataFrame(frames).dropna(how="all")

# Fixed pool of IBKR client IDs for data workers (cycles, never grows unbounded)
_IBKR_CLIENT_ID_POOL = list(range(2001, 2009))  # 2001–2008
_ibkr_client_id_index = 0
_ibkr_client_id_lock = threading.Lock()

def _next_client_id() -> int:
    global _ibkr_client_id_index
    with _ibkr_client_id_lock:
        client_id = _IBKR_CLIENT_ID_POOL[_ibkr_client_id_index % len(_IBKR_CLIENT_ID_POOL)]
        _ibkr_client_id_index += 1
        return client_id

class DataLoader:
    """Load and cache OHLCV data from multiple sources with validation."""
    
    def __init__(self, cache_dir: str = "data/cache", validator: Optional[OHLCVValidator] = None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # PHASE 2 FEATURE 3: Inject validator (default to OHLCVValidator if not provided)
        self.validator = validator or OHLCVValidator()
    
    def load_ibkr_data(
        self,
        symbol: str,
        timeframe: str = "1d",
        since: str = None,
        limit: int = 252,
        validate: bool = True
    ) -> pd.DataFrame:
        """
        Load OHLCV data for a US equity symbol via Interactive Brokers.

        Connects to TWS / IB Gateway via ib_insync and requests historical bars.

        Args:
            symbol: Equity ticker (e.g., "AAPL", "MSFT")
            timeframe: Bar interval ("1d", "1h", etc.)
            since: ISO 8601 start date (used to compute duration)
            limit: Number of bars (used as fallback to compute duration)
            validate: If True, validate OHLCV data (raises DataValidationError on failure)

        Returns:
            DataFrame with OHLCV data (columns: open, high, low, close, volume)

        Raises:
            DataValidationError: If validation fails and validate=True
        """
        # Patch: always ensure symbol is str
        if isinstance(symbol, list):
            symbol = ",".join([str(s) for s in symbol])
        elif not isinstance(symbol, str):
            symbol = str(symbol)

        try:
            from execution.ibkr_engine import IBGatewaySync

            # Map timeframe to IB bar size
            bar_size_map = {"1d": "1 day", "1h": "1 hour", "4h": "4 hours", "1m": "1 min"}
            bar_size = bar_size_map.get(timeframe, "1 day")

            # Calculate IB duration string from limit
            if timeframe in ("1d",):
                years = max(1, limit // 252)
                duration = f"{years} Y" if years >= 1 else f"{limit} D"
            elif timeframe in ("4h",):
                days = max(1, (limit * 4) // 24 + 10)
                duration = f"{days} D"
            elif timeframe in ("1h",):
                days = max(1, (limit) // 7 + 5)
                duration = f"{days} D"
            else:
                duration = f"{max(1, limit * 60)} S"

            engine = IBGatewaySync(host="127.0.0.1", port=4002, client_id=_next_client_id())
            engine.connect()
            try:
                bars = engine.get_historical_data(
                    symbol=symbol,
                    duration=duration,
                    bar_size=bar_size,
                    what_to_show="ADJUSTED_LAST"
                )
                if not bars:
                    df = pd.DataFrame()
                else:
                    df = pd.DataFrame(
                        {
                            'Open': [b.open for b in bars],
                            'High': [b.high for b in bars],
                            'Low': [b.low for b in bars],
                            'Close': [b.close for b in bars],
                            'Volume': [b.volume for b in bars],
                        },
                        index=pd.DatetimeIndex([b.date for b in bars]),
                    )
                    df.index.name = 'date'
            finally:
                engine.disconnect()

            if df is None or df.empty:
                raise RuntimeError(f"No data returned from IBKR for {symbol}")

            col_map = {"Open": "open", "High": "high", "Low": "low",
                        "Close": "close", "Volume": "volume"}
            df.rename(columns=col_map, inplace=True)
            expected_cols = ["open", "high", "low", "close", "volume"]
            df = df[[c for c in expected_cols if c in df.columns]].dropna()

            if validate and len(df) > 0:
                validation_result = self.validator.validate(df, raise_on_error=True)
                logger.info(
                    "ibkr_data_loaded_and_validated",
                    symbol=str(symbol),
                    rows=len(df),
                    checks_passed=validation_result.checks_passed,
                    checks_failed=validation_result.checks_failed
                )
            else:
                logger.info("ibkr_data_loaded_no_validation", symbol=str(symbol), rows=len(df))

            return df

        except DataValidationError as e:
            logger.error("data_validation_failed", symbol=str(symbol), error=str(e))
            raise
        except Exception as e:
            logger.error("ibkr_data_load_failed", symbol=str(symbol), error=str(e))
            raise
    
    def load_csv(self, filepath: str) -> pd.DataFrame:
        """Load OHLCV data from CSV file."""
        df = pd.read_csv(filepath, index_col=0, parse_dates=True)
        logger.info("csv_loaded", filepath=filepath, rows=len(df))
        return df
    
    def cache_data(self, df: pd.DataFrame, symbol: str, timeframe: str) -> None:
        """Cache DataFrame to disk."""
        # Defensive: ensure symbol is str
        if isinstance(symbol, list):
            symbol = ",".join([str(s) for s in symbol])
        elif not isinstance(symbol, str):
            symbol = str(symbol)
        cache_file = self.cache_dir / f"{symbol}_{timeframe}.parquet"
        df.to_parquet(cache_file)
        logger.info("data_cached", symbol=symbol, timeframe=timeframe, path=str(cache_file))
    
    def load_cached(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Load cached data if available."""
        # Defensive: ensure symbol is str
        if isinstance(symbol, list):
            symbol = ",".join([str(s) for s in symbol])
        elif not isinstance(symbol, str):
            symbol = str(symbol)
        cache_file = self.cache_dir / f"{symbol}_{timeframe}.parquet"
        if cache_file.exists():
            df = pd.read_parquet(cache_file)
            logger.info("cache_hit", symbol=symbol, timeframe=timeframe)
            return df
        logger.info("cache_miss", symbol=symbol, timeframe=timeframe)
        return None

    # ==================================================================
    # Bulk loading with rate limiting
    # ==================================================================

    def bulk_load(
        self,
        symbols: List[str],
        timeframe: str = "1d",
        limit: int = 252 * 6,
        max_workers: int = 3,
        use_cache: bool = True,
        rate_limiter=None,
    ) -> Dict[str, pd.DataFrame]:
        """
        Load OHLCV data for multiple symbols with caching and rate limiting.

        Loads from cache first, then fetches missing symbols from IBKR
        using a ThreadPoolExecutor with rate limiting.

        Args:
            symbols: List of ticker symbols.
            timeframe: Bar interval (e.g., "1d").
            limit: Number of bars per symbol.
            max_workers: Concurrent download threads (keep low for IBKR).
            use_cache: Use parquet cache when available.
            rate_limiter: Optional IBKRRateLimiter instance.

        Returns:
            Dict mapping symbol → OHLCV DataFrame.
        """
        results: Dict[str, pd.DataFrame] = {}
        to_fetch: List[str] = []

        # Phase 1: Load from cache
        if use_cache:
            for sym in symbols:
                # Defensive: ensure sym is str
                if isinstance(sym, list):
                    sym = ",".join([str(s) for s in sym])
                elif not isinstance(sym, str):
                    sym = str(sym)
                cached = self.load_cached(sym, timeframe)
                if cached is not None and len(cached) >= limit * 0.8:
                    results[sym] = cached
                else:
                    to_fetch.append(sym)
        else:
            to_fetch = [str(sym) if not isinstance(sym, str) else sym for sym in symbols]

        if not to_fetch:
            logger.info(
                "bulk_load_all_cached",
                symbols=len(results),
                timeframe=timeframe,
            )
            return results

        # Debug snapshot: write the to_fetch list types/reprs to disk for troubleshooting
        try:
            with open("debug_bulk_to_fetch_snapshot.txt", "w", encoding="utf-8") as df:
                df.write("idx\ttype\trepr\tsymbol\n")
                for i, sym in enumerate(to_fetch[:500]):
                    df.write(f"{i}\t{type(sym).__name__}\t{repr(sym)}\t{str(sym)}\n")
        except Exception:
            pass

        logger.info(
            "bulk_load_starting",
            cached=len(results),
            to_fetch=len(to_fetch),
            workers=max_workers,
            timeframe=timeframe,
        )

        # Phase 2: Fetch missing from IBKR with rate limiting
        # Persistent IBKR engine per worker
        from execution.ibkr_engine import IBKRExecutionEngine
        def _worker(symbols: List[str], idx: int) -> Dict[str, Optional[pd.DataFrame]]:
            results = {}
            client_id = 1000 + idx
            logger.info("ibkr_worker_start", worker_idx=idx, client_id=client_id, symbol_count=len(symbols))
            engine = IBKRExecutionEngine(client_id=client_id)
            logger.info("ibkr_worker_engine_actual_client_id", worker_idx=idx, client_id=engine.client_id)
            assert engine.client_id == client_id, f"Worker {idx}: IBKRExecutionEngine client_id mismatch! Got {engine.client_id}, expected {client_id}"
            print(f"[DEBUG] Worker {idx} assigned client_id={client_id}, engine.client_id={engine.client_id}")
            engine.connect()
            def _normalize_symbol(s):
                # Flatten lists/tuples and coerce to a deterministic string
                if isinstance(s, (list, tuple)):
                    flat = []
                    for el in s:
                        if isinstance(el, (list, tuple)):
                            flat.extend([str(x) for x in el])
                        else:
                            flat.append(str(el))
                    if len(flat) == 1:
                        return flat[0]
                    return ",".join(flat)
                return str(s)

            for sym in symbols:
                norm_sym = _normalize_symbol(sym)
                try:
                    if rate_limiter is not None:
                        rate_limiter.acquire("historical")
                    df = engine.get_historical_data(
                        symbol=norm_sym,
                        duration=None,
                        bar_size="1 day",
                        what_to_show="ADJUSTED_LAST",
                    )
                    if df is not None and not df.empty:
                        self.cache_data(df, norm_sym, timeframe)
                    results[norm_sym] = df
                except TypeError as tex:
                    import traceback as _tb
                    tb = _tb.format_exc()
                    logger.error(
                        "bulk_load_type_error",
                        symbol_repr=repr(sym),
                        symbol_type=str(type(sym)),
                        normalized=norm_sym,
                        error=str(tex),
                        traceback=tb[:2000],
                    )
                    results[norm_sym] = None
                except Exception as exc:
                    import traceback as _tb
                    tb = _tb.format_exc()
                    logger.warning(
                        "bulk_load_symbol_failed",
                        symbol=norm_sym,
                        error=str(exc)[:200],
                        traceback=tb[:2000],
                    )
                    results[norm_sym] = None
            engine.disconnect()
            return results

        # Split symbols among workers
        symbol_chunks = [
            to_fetch[i::max_workers] for i in range(max_workers)
        ]
        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_worker, chunk, idx): idx for idx, chunk in enumerate(symbol_chunks)
            }
            for future in as_completed(futures):
                worker_results = future.result()
                for sym, df in worker_results.items():
                    completed += 1
                    # ...existing code...

        completed = 0
        # Use only chunked worker logic (each worker gets a unique client_id)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_worker, chunk, idx): idx for idx, chunk in enumerate(symbol_chunks)
            }
            for future in as_completed(futures):
                worker_results = future.result()
                for sym, df in worker_results.items():
                    completed += 1
                    if df is not None and not df.empty:
                        results[sym] = df
                    if completed % 50 == 0 or completed == len(to_fetch):
                        logger.info(
                            "bulk_load_progress",
                            completed=completed,
                            total=len(to_fetch),
                            successful=len(results),
                            pct=round(100 * completed / len(to_fetch), 1),
                        )

        logger.info(
            "bulk_load_complete",
            requested=len(symbols),
            loaded=len(results),
            failed=len(symbols) - len(results),
        )
        return results
