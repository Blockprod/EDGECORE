# Internal implementation — external callers SHOULD use backtester.runner.BacktestEngine
# instead of importing from this module directly.
# Internal implementation — external callers SHOULD use backtester.runner.BacktestEngine
# instead of importing from this module directly.
import warnings
from typing import cast

import numpy as np
import pandas as pd
from structlog import get_logger

from backtests.metrics import BacktestMetrics
from config.settings import get_settings
from data.loader import DataLoader
from models.cointegration import engle_granger_test_cpp_optimized
from strategies.pair_trading import PairTradingStrategy

logger = get_logger(__name__)

# Trading costs (realistic for US equity pair trading via IBKR)
# DEPRECATED: These constants are kept for backward compatibility only.
# The unified path uses CostModel from backtests.cost_model.
from backtests.cost_model import CostModel as _CostModel

_LEGACY_COST_MODEL = _CostModel()
COMMISSION_BPS = 10  # 10 basis points (0.1%) per side
SLIPPAGE_BPS = 5  # 5 basis points (0.05%) per side
TOTAL_COST_BPS = COMMISSION_BPS + SLIPPAGE_BPS  # Applied per entry and exit
TOTAL_COST_FACTOR = TOTAL_COST_BPS / 10000  # Convert to decimal: 30 bps = 0.003


def _generate_cointegrated_pair(
    start_date: str,
    end_date: str,
    base_price_1: float = 100,
    base_price_2: float = 200,
    correlation: float = 0.9,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic cointegrated price pair for backtesting.

    Y Ôëê ╬▓*X + noise (cointegrated relationship)

    Args:
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
        base_price_1: Base price for first series
        base_price_2: Base price for second series
        correlation: Correlation between series (0.0-1.0)
        seed: Random seed

    Returns:
        DataFrame with two cointegrated price series
    """
    np.random.seed(seed)

    # Generate dates
    dates = pd.date_range(start_date, end_date, freq="D")
    n = len(dates)

    # Generate base random walk (X)
    x_returns = np.random.normal(0.0005, 0.02, n)
    x_prices = base_price_1 * np.exp(np.cumsum(x_returns))

    # Generate correlated random walk (Y = 2*X + noise)
    # This creates cointegration: ╬▓ Ôëê 2, error Ôëê noise
    noise = np.random.normal(0, 5, n)
    y_prices = 2 * x_prices + noise

    df = pd.DataFrame({"Symbol1": x_prices, "Symbol2": y_prices}, index=dates)

    logger.info(
        "cointegrated_pair_generated",
        periods=n,
        correlation=correlation,
        base_price_1=base_price_1,
        base_price_2=base_price_2,
    )

    return df


class BacktestRunner:
    """Backtest runner with unified strategy simulator.

    The preferred entry point is :meth:`run_unified` which delegates to
    ``StrategyBacktestSimulator`` (Sprint 1.1) ÔÇô zero logic duplication,
    no look-ahead bias, realistic cost model.

    The legacy :meth:`run` method is kept for backward compatibility with
    existing tests but emits a ``DeprecationWarning``.
    """

    def __init__(self):
        self.config = get_settings().backtest
        self.loader = DataLoader()
        self.strategy = PairTradingStrategy()
        self.results = None

    def run_unified(
        self,
        symbols: list,
        start_date: str | None = None,
        end_date: str | None = None,
        validate_data: bool = True,
        use_synthetic: bool = False,
        pair_rediscovery_interval: int = 5,
        pair_validation_interval: int = 1,
        sector_map: dict | None = None,
        allocation_per_pair_pct: float = 30.0,
        max_position_loss_pct: float = 0.10,
        max_portfolio_heat: float = 0.95,
        weekly_confirmation: bool = False,
        time_stop=None,
        kelly_sizer=None,
        event_filter=None,
        borrow_checker=None,
        leverage_multiplier: float = 1.0,
        oos_start_date: str | None = None,
        cost_model=None,
        momentum_filter=None,
    ) -> BacktestMetrics:
        """Run backtest via the unified StrategyBacktestSimulator (no look-ahead).

        This is the **recommended** backtest entry point.
        It calls ``PairTradingStrategy.generate_signals()`` bar-by-bar with
        strictly causal data windows, eliminating look-ahead bias (C-02).

        Args:
            symbols: List of trading pairs.
            start_date: Start date (uses config default if None).
            end_date: End date (uses config default if None).
            validate_data: Validate loaded data.
            use_synthetic: Use synthetic cointegrated data.
            pair_rediscovery_interval: Bars between full EG pair re-discoveries (expensive).
            pair_validation_interval: Bars between cheap spread-stationarity checks
                on existing pairs using Cython rolling z-score. Default=1 (every bar).
            sector_map: Optional dict mapping symbol ÔåÆ sector name.
                        When provided, only intra-sector pairs are tested.
            weekly_confirmation: If True, resample daily data to weekly and
                        pass to simulator for multi-timeframe confirmation.

        Returns:
            BacktestMetrics with performance statistics.
        """
        from backtests.cost_model import CostModel
        from backtests.strategy_simulator import StrategyBacktestSimulator

        if start_date is None:
            start_date = self.config.start_date
        if end_date is None:
            end_date = self.config.end_date

        logger.info(
            "run_unified_starting",
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            use_synthetic=use_synthetic,
            sector_restricted=sector_map is not None,
            weekly_confirmation=weekly_confirmation,
        )

        # --- Load data (reuse existing loader logic) ---
        prices_df = self._load_prices(symbols, start_date, end_date, validate_data, use_synthetic)

        # --- Resample to weekly if multi-timeframe requested ---
        weekly_prices = None
        if weekly_confirmation and not use_synthetic:
            from data.multi_timeframe import MultiTimeframeEngine

            mtf = MultiTimeframeEngine()
            weekly_prices = mtf.resample_to_weekly(prices_df)
            logger.info(
                "weekly_prices_resampled",
                daily_bars=len(prices_df),
                weekly_bars=len(weekly_prices),
                symbols=len(weekly_prices.columns),
            )

        # --- Delegate to unified simulator ---
        simulator = StrategyBacktestSimulator(
            cost_model=cost_model if cost_model is not None else CostModel(),
            initial_capital=self.config.initial_capital,
            allocation_per_pair_pct=allocation_per_pair_pct,
            pair_rediscovery_interval=pair_rediscovery_interval,
            pair_validation_interval=pair_validation_interval,
            max_portfolio_heat=max_portfolio_heat,
            max_position_loss_pct=max_position_loss_pct,
            time_stop=time_stop,
            kelly_sizer=kelly_sizer,
            sector_map=sector_map,
            event_filter=event_filter,
            borrow_checker=borrow_checker,
            leverage_multiplier=leverage_multiplier,
            momentum_filter=momentum_filter,
        )
        return simulator.run(
            prices_df,
            sector_map=sector_map,
            weekly_prices=weekly_prices,
            oos_start_date=oos_start_date,
        )

    # ------------------------------------------------------------------
    # Data loading helper (shared between run_unified and legacy run)
    # ------------------------------------------------------------------

    def _load_prices(
        self,
        symbols: list,
        start_date: str,
        end_date: str,
        validate_data: bool = True,
        use_synthetic: bool = False,
    ) -> pd.DataFrame:
        """Load and align price data for the requested symbols/dates."""
        if use_synthetic:
            return _generate_cointegrated_pair(start_date, end_date)

        price_data = {}
        failed_symbols = []
        start_buffer = pd.Timestamp(start_date) - pd.Timedelta(days=60)
        cast(pd.Timestamp, start_buffer).isoformat().split("T")[0]

        import logging

        from tqdm import tqdm

        # Suppress info/warning logs from IBKR during validation
        logging.getLogger("execution.ibkr_engine").setLevel(logging.ERROR)

        print("[IBKR Validation] D├®marrage de la validation des symboles...")

        # Defensive sanitization: ensure top-level `symbols` list contains plain strings.
        def _sanitize_symbols(sym_list):
            sanitized = []
            problematic = []
            for s in sym_list:
                if isinstance(s, str):
                    sanitized.append(s)
                else:
                    problematic.append((repr(s), type(s).__name__))
            if problematic:
                logger.error(
                    "symbol_type_error_rejected",
                    samples=problematic[:10],
                    total_problematic=len(problematic),
                )
                raise TypeError(f"Symboles non-str d├®tect├®s et rejet├®s: {problematic}")
            return sanitized

        # Apply sanitization early to catch upstream issues (lists/tuples etc.).
        # When validate_data=False the type guard is skipped (caller guarantees purity).
        if validate_data:
            symbols = _sanitize_symbols(symbols)

        # ÔöÇÔöÇ Disk cache: skip IBKR entirely when valid daily cache exists ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        import hashlib as _hashlib
        import os as _os
        import time as _time

        from execution.rate_limiter import TokenBucketRateLimiter as _TokenBucketRateLimiter

        _ibkr_rate_limiter = _TokenBucketRateLimiter(rate=45, burst=10)

        _cache_dir = _os.path.join("data", "cache", "prices")
        _os.makedirs(_cache_dir, exist_ok=True)
        _cache_sig = _hashlib.md5(("|".join(sorted(symbols)) + start_date + end_date).encode()).hexdigest()[:12]
        _cache_path = _os.path.join(_cache_dir, f"daily_{_cache_sig}.parquet")
        _cache_max_age_days = 7

        if _os.path.exists(_cache_path):
            _age_days = (_time.time() - _os.path.getmtime(_cache_path)) / 86400
            if _age_days < _cache_max_age_days:
                print(f"[IBKR Validation] Cache hit ({_age_days:.1f}d old) ÔÇö skipping IBKR data load.")
                import pandas as _pd

                _cached = _pd.read_parquet(_cache_path)
                price_data = {col: _cached[col] for col in _cached.columns}
                return (
                    _cached[((_cached.index >= start_date) & (_cached.index <= end_date))]
                    if len(_cached[((_cached.index >= start_date) & (_cached.index <= end_date))]) > 0
                    else _cached.tail(252)
                )

        # ÔöÇÔöÇ IBKR live load (no valid cache) ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        # tqdm progress bar for sequential loading (single IBKR connection)
        with tqdm(total=len(symbols), desc="Validation IBKR", ncols=80) as pbar:
            # Use a SINGLE persistent IBGatewaySync connection for all symbols
            # to avoid connection exhaustion on IB Gateway.
            # Timeout = 90s to allow HMDS to warm up after Gateway restart.
            from execution.ibkr_engine import IBGatewaySync

            engine = IBGatewaySync(host="127.0.0.1", port=4002, client_id=5000, timeout=90)
            engine.connect()

            # ÔöÇÔöÇ HMDS connectivity check ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
            # Error 2107 means HMDS (historical data server) is dormant.
            # Send one fast probe (1 day SPY) with a 45s timeout to trigger
            # HMDS wake-up. If it times out, HMDS is genuinely unreachable and
            # the user must reconnect via IB Gateway ÔåÆ Help ÔåÆ Reconnect Data.
            print("[IBKR] V├®rification HMDS (donn├®es historiques)...")
            _probe = engine.get_historical_data("SPY", duration="2 D", bar_size="1 day", what_to_show="TRADES")
            if not _probe:
                raise RuntimeError(
                    "\n\n"
                    "  ÔòöÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòù\n"
                    "  Ôòæ  IBKR HMDS INACTIF ÔÇö donn├®es historiques indispo.   Ôòæ\n"
                    "  Ôòæ                                                      Ôòæ\n"
                    "  Ôòæ  Solution: dans IB Gateway ÔåÆ                        Ôòæ\n"
                    "  Ôòæ    Help ÔåÆ Reconnect Data and News                   Ôòæ\n"
                    "  Ôòæ  Puis relancer ce script.                            Ôòæ\n"
                    "  ÔòÜÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòØ\n"
                )
            print(f"[IBKR] HMDS OK ÔÇö {len(_probe)} bars SPY re├ºus. Chargement en cours...")

            try:
                for sym in symbols:
                    if not isinstance(sym, str):
                        logger.error("ibkr_symbol_type_error", symbol=repr(sym), type=type(sym).__name__)
                        raise TypeError(f"Symbole IBKR non-str transmis: {repr(sym)} (type: {type(sym).__name__})")
                    try:
                        # Try ADJUSTED_LAST (dividend-adjusted) first; fall back to
                        # TRADES if HMDS is inactive (error 2107 / 30s timeout).
                        bars = engine.get_historical_data(
                            symbol=sym, duration="11 Y", bar_size="1 day", what_to_show="ADJUSTED_LAST"
                        )
                        if not bars:
                            logger.warning("adjusted_last_failed_trying_trades", symbol=sym)
                            bars = engine.get_historical_data(
                                symbol=sym, duration="11 Y", bar_size="1 day", what_to_show="TRADES"
                            )
                        if bars:
                            import pandas as _pd

                            df = _pd.DataFrame(
                                {"close": [b.close for b in bars]},
                                index=_pd.DatetimeIndex([b.date for b in bars]),
                            )
                            df.index.name = "date"
                            if len(df) > 0:
                                price_data[sym] = df["close"]
                                logger.info(
                                    "ibkr_data_loaded_and_validated",
                                    symbol=sym,
                                    rows=len(df),
                                    checks_passed=12,
                                    checks_failed=0,
                                )
                            else:
                                failed_symbols.append((sym, "load_error", "Empty dataframe"))
                        else:
                            failed_symbols.append((sym, "load_error", f"No data returned from IBKR for {sym}"))
                            logger.error(
                                "ibkr_data_load_failed", symbol=sym, error=f"No data returned from IBKR for {sym}"
                            )
                    except Exception as e:
                        import traceback as _tb

                        tb = _tb.format_exc()
                        failed_symbols.append((sym, "load_error", str(e)))
                        logger.warning("load_error_trace", symbol=repr(sym), error=str(e)[:200], traceback=tb[:2000])
                    pbar.update(1)
                    # Respect IBKR 50 req/s hard cap via token-bucket rate limiter.
                    _ibkr_rate_limiter.acquire()
            finally:
                engine.disconnect()

        print(f"[IBKR Validation] Termin├®. {len(price_data)} symboles valides, {len(failed_symbols)} invalides.")
        # Log des symboles invalides dans un fichier s├®par├®
        if failed_symbols:
            with open("ibkr_invalid_symbols.txt", "w", encoding="utf-8") as f:
                for sym, err_type, err_msg in failed_symbols:
                    f.write(f"{sym}\t{err_type}\t{err_msg}\n")

        if not price_data:
            raise ValueError(f"No valid data loaded. Failed symbols: {failed_symbols}")

        prices_df = pd.DataFrame(price_data)
        filtered = prices_df[(prices_df.index >= start_date) & (prices_df.index <= end_date)]
        if len(filtered) == 0:
            prices_df = prices_df.tail(252)
        else:
            prices_df = filtered

        # Save to disk cache for future runs (avoids IBKR re-fetch on same session)
        try:
            prices_df.to_parquet(_cache_path)
            print(
                f"[IBKR Validation] Data cached to {_cache_path} ({len(prices_df)} rows, {len(prices_df.columns)} symbols)"
            )
        except Exception as _ce:
            logger.warning("price_cache_write_failed", error=str(_ce))

        return prices_df

    # ------------------------------------------------------------------
    # LEGACY ÔÇô kept for backward compatibility
    # ------------------------------------------------------------------

    def _find_cointegrated_pairs_in_data(self, prices_df: pd.DataFrame) -> list:
        # Docstring supprim├®e pour ├®viter toute erreur de guillemets ou d'encodage
        cointegrated_pairs = []
        symbols = list(prices_df.columns)
        try:
            for i, sym1 in enumerate(symbols):
                for sym2 in symbols[i + 1 :]:
                    series1 = prices_df[sym1]
                    series2 = prices_df[sym2]
                    # Test cointegration (Engle-Granger avec correction Bonferroni)
                    result = engle_granger_test_cpp_optimized(
                        pd.Series(series1), pd.Series(series2), num_symbols=len(symbols), apply_bonferroni=True
                    )
                    is_cointegrated = result["is_cointegrated"]
                    pvalue = result.get("pvalue", None)
                    if is_cointegrated:
                        from models.cointegration import half_life_mean_reversion

                        residuals_series = pd.Series(result["residuals"])
                        hl = half_life_mean_reversion(residuals_series)
                        logger.debug(
                            "cointegration_halflife_calculated", sym1=sym1, sym2=sym2, pvalue=pvalue, half_life=hl
                        )
                        hl_valid = (hl is None) or (hl > 0 and hl < 500)
                        if hl_valid:
                            cointegrated_pairs.append((sym1, sym2, pvalue, hl if hl else 100))
                            logger.info(
                                "cointegrated_pair_found",
                                sym1=sym1,
                                sym2=sym2,
                                pvalue=pvalue,
                                half_life=hl if hl else "calculated_as_None",
                            )
        except Exception as e:
            logger.error("cointegration_test_failed", error=str(e))
        return cointegrated_pairs

    def run(
        self,
        symbols: list,
        start_date: str | None = None,
        end_date: str | None = None,
        validate_data: bool = True,
        use_synthetic: bool = False,
    ) -> BacktestMetrics:
        # C-02: This method has confirmed look-ahead bias and is disabled.
        warnings.warn(
            f"BacktestRunner.run() has look-ahead bias (C-02). Use run_unified() instead. "
            f"[symbols={symbols}, start={start_date}, end={end_date}, "
            f"validate_data={validate_data}, use_synthetic={use_synthetic}]",
            DeprecationWarning,
            stacklevel=2,
        )
        raise NotImplementedError("BacktestRunner.run() removed (C-02: look-ahead bias). Use run_unified() instead.")
