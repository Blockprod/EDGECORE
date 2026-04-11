import time as _time_module
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from multiprocessing import cpu_count
from pathlib import Path
from typing import Any, Callable, cast

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller
from structlog import get_logger

from config.settings import get_settings
from models.cointegration import (
    engle_granger_test,
    half_life_mean_reversion,
    is_cointegration_stable,
    verify_integration_order,
)
from models.cointegration import (
    newey_west_consensus as _newey_west_consensus,  # noqa: F401 — re-exported for test patching  # pyright: ignore[reportUnusedImport]
)
from models.spread import SpreadModel
from signal_engine.combiner import SignalCombiner, SignalSource
from signal_engine.cross_sectional import CrossSectionalMomentum
from signal_engine.earnings_signal import EarningsSurpriseSignal
from signal_engine.momentum import MomentumOverlay
from signal_engine.options_flow import OptionsFlowSignal
from signal_engine.ou_signal import OUSignalGenerator
from signal_engine.sentiment import SentimentSignal
from signal_engine.vol_signal import VolatilityRegimeSignal
from strategies.base import BaseStrategy, Signal
from strategies.correlation_monitor import CorrelationMonitor
from strategies.pair_cache_manager import PairCacheManager
from strategies.pair_validator import PairValidator
from strategies.trade_book import StrategyTradeBook

logger = get_logger(__name__)


# Type alias for injectable clock function (REPR-1)
ClockFn = Callable[[], datetime]


class PairTradingStrategy(BaseStrategy):
    """
    Statistical arbitrage via pair trading (mean reversion).

    Process:
    1. Identify cointegrated pairs
    2. Compute spread via OLS
    3. Generate Z-score signals
    4. Entry at |Z| > threshold
    5. Exit at Z = 0 (mean reversion)
    """

    @staticmethod
    def _cfg_val(config, name: str, default) -> Any:
        """Safe config accessor — returns *default* when the attribute is absent
        or is a mock auto-attribute (MagicMock)."""
        val = getattr(config, name, default)
        if isinstance(val, (int, float, bool, str, type(None))):
            return val
        return default

    def __init__(self, clock: ClockFn | None = None):
        self.config = get_settings().strategy
        self.spread_models: dict[str, SpreadModel] = {}
        self.active_trades = StrategyTradeBook()
        self.historical_spreads: dict[str, pd.Series] = {}
        self.use_cache: bool = True
        self.sector_map: dict[str, str] | None = None

        # REPR-1: Injectable clock — datetime.now in live, bar timestamp in backtest
        self._clock: ClockFn = clock or datetime.now

        # Initialize cache directory
        self.cache_dir = Path("cache/pairs")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        _c = self.config  # shorthand

        # ÔöÇÔöÇ Sprint components ÔöÇÔöÇ
        from data.delisting_guard import DelistingGuard
        from data.liquidity_filter import LiquidityFilter
        from execution.concentration_limits import ConcentrationLimitManager
        from execution.trailing_stop import TrailingStopManager
        from models.hedge_ratio_tracker import HedgeRatioTracker
        from models.regime_detector import RegimeDetector
        from models.stationarity_monitor import StationarityMonitor

        self.regime_detector = RegimeDetector(
            lookback_window=self._cfg_val(
                _c,
                "regime_lookback_window",
                self._cfg_val(get_settings().regime_detector_config, "regime_window", 60),
            ),
            min_regime_duration=self._cfg_val(_c, "regime_min_duration", 1),
            instant_transition_percentile=self._cfg_val(_c, "instant_transition_percentile", 99.0),
        )
        self.hedge_ratio_tracker = HedgeRatioTracker(
            reestimation_frequency_days=self._cfg_val(_c, "hedge_ratio_reestimation_days", 7),
            emergency_vol_sigma=self._cfg_val(_c, "emergency_vol_threshold_sigma", 3.0),
        )
        self.stationarity_monitor = StationarityMonitor()
        self.liquidity_filter = LiquidityFilter()
        self.delisting_guard = DelistingGuard()
        self.trailing_stop_manager = TrailingStopManager(
            widening_threshold=self._cfg_val(_c, "trailing_stop_widening", 1.0),
        )
        self.concentration_limits = ConcentrationLimitManager(
            max_symbol_concentration_pct=self._cfg_val(_c, "max_symbol_concentration_pct", 30.0),
            allow_rebalancing=True,
        )

        from models.model_retraining import ModelRetrainingManager

        self.model_retrainer = ModelRetrainingManager()
        self.pair_regime_states: dict[str, object] = {}

        # ÔöÇÔöÇ Momentum overlay (v31) ÔöÇÔöÇ
        try:
            _mom_cfg = get_settings().momentum
            self._momentum_enabled = bool(getattr(_mom_cfg, "enabled", False))
            if self._momentum_enabled:
                _lb = getattr(_mom_cfg, "lookback", 20)
                _wt = getattr(_mom_cfg, "weight", 0.30)
                _ms = getattr(_mom_cfg, "min_strength", 0.30)
                _mb = getattr(_mom_cfg, "max_boost", 1.0)
                # Guard against mocked / non-numeric config values
                if all(isinstance(v, (int, float)) for v in (_lb, _wt, _ms, _mb)):
                    self._momentum = MomentumOverlay(
                        lookback=int(_lb),
                        weight=float(_wt),
                        min_strength=float(_ms),
                        max_boost=float(_mb),
                    )
                else:
                    self._momentum_enabled = False
                    self._momentum = None
            else:
                self._momentum = None
        except Exception:
            self._momentum_enabled = False
            self._momentum = None

        # ÔöÇÔöÇ Phase 1 signal sources (v32) ÔöÇÔöÇ
        self._ou_signal = OUSignalGenerator(lookback=60)
        self._cross_sectional = CrossSectionalMomentum()
        self._vol_signal = VolatilityRegimeSignal()

        # ÔöÇÔöÇ Phase 4 signal sources (v37) ÔöÇÔöÇ
        self._earnings_signal = EarningsSurpriseSignal()
        self._options_flow = OptionsFlowSignal()
        self._sentiment_signal = SentimentSignal()

        # ── SignalCombiner with all 9 sources ──
        # C-02: read primary weights and thresholds from SignalCombinerConfig
        from config.settings import get_settings as _gs_pt

        _sc_cfg = _gs_pt().signal_combiner
        _sources = [
            SignalSource("zscore", weight=_sc_cfg.zscore_weight),
            SignalSource("momentum", weight=_sc_cfg.momentum_weight, enabled=self._momentum_enabled),
            SignalSource("ou", weight=0.15),
            SignalSource("vol_regime", weight=0.07),
            SignalSource("cross_sectional", weight=0.05),
            SignalSource("intraday_mr", weight=0.05),
            SignalSource("earnings", weight=0.10),
            SignalSource("options_flow", weight=0.07),
            SignalSource("sentiment", weight=0.08),
        ]
        self._signal_combiner = SignalCombiner(
            sources=_sources,
            entry_threshold=_sc_cfg.entry_threshold,
            exit_threshold=_sc_cfg.exit_threshold,
        )

        # ── Leg-correlation monitoring parameters ──
        self.leg_correlation_window: int = self._cfg_val(_c, "leg_correlation_window", 30)
        self.leg_correlation_decay_threshold: float = self._cfg_val(_c, "leg_correlation_decay_threshold", 0.3)

        # ── Internal risk limits ──
        self.max_positions: int = self._cfg_val(_c, "internal_max_positions", 10)
        self.max_daily_trades: int = self._cfg_val(_c, "internal_max_daily_trades", 50)
        self.max_drawdown_pct: float = self._cfg_val(_c, "internal_max_drawdown_pct", 20.0)
        self.daily_trade_count: int = 0
        self.daily_trade_date: date | None = date.today()
        self.peak_equity: float | None = self._cfg_val(_c, "initial_capital", 100_000.0)
        self.current_equity: float | None = self.peak_equity
        # P1-05: persistent I(1) verification cache — avoids re-running ADF/KPSS every discovery cycle
        # keys: symbol; values: (is_I1: bool, cached_at: float monotonic timestamp)
        self._i1_verification_cache: dict[str, tuple[bool, float]] = {}
        self._i1_cache_ttl_seconds: float = 86400.0  # 24 h default (one full market day)

        # ── Composed helpers (P2-04) ──
        # CorrelationMonitor owns the correlation state; @property bridges on this
        # class expose the underlying sets/dicts so tests that mutate them directly
        # (e.g. strategy._excluded_pairs_correlation.add(k)) keep working.
        self._correlation_monitor = CorrelationMonitor(
            window=self.leg_correlation_window,
            decay_threshold=self.leg_correlation_decay_threshold,
            clock=self._clock,
        )
        # PairCacheManager owns cache I/O; use_cache flag stays on this class.
        self._cache_manager = PairCacheManager(
            cache_dir=self.cache_dir,
            regime_detector=self.regime_detector,
            config=self.config,
            clock=self._clock,
        )

    # ── @property bridges for correlation state ──
    # These expose the CorrelationMonitor's live collections so callers that
    # directly mutate strategy._excluded_pairs_correlation (e.g. via .add())
    # continue to work without modification.
    @property
    def _excluded_pairs_correlation(self) -> set:
        return self._correlation_monitor._excluded_pairs_correlation

    @property
    def _correlation_exclusions(self) -> dict:
        return self._correlation_monitor._correlation_exclusions

    @property
    def _leg_correlation_history(self) -> dict:
        return self._correlation_monitor._leg_correlation_history

    # ── Cache control methods ──
    def disable_cache(self) -> None:
        """Disable pair-cache reads/writes (used by walk-forward to avoid leakage)."""
        self.use_cache = False

    def enable_cache(self) -> None:
        """Re-enable pair caching."""
        self.use_cache = True

    def clear_cache(self) -> None:
        """Delete all cached pair files."""
        self._cache_manager.clear()

    # ── Adaptive cache TTL ──
    def get_cache_ttl_hours(self) -> int:
        """Return cache TTL in hours based on current volatility regime."""
        return self._cache_manager.get_cache_ttl_hours()

    # ── Leg-correlation stability (delegated to CorrelationMonitor) ──
    def _check_leg_correlation_stability(
        self,
        y: pd.Series,
        x: pd.Series,
        pair_key: str,
        window: int | None = None,
    ) -> bool:
        """Check if the rolling correlation between pair legs is stable."""
        return self._correlation_monitor.check_stability(y, x, pair_key, window)

    def get_excluded_pairs_correlation(self) -> set:
        """Return the set of pairs excluded due to correlation breakdown."""
        return self._correlation_monitor.get_excluded_pairs()

    def get_correlation_exclusions(self) -> dict[str, datetime]:
        """Return currently excluded pairs with timestamps."""
        return self._correlation_monitor.get_exclusions()

    def reset_correlation_exclusion(self, pair_key: str | None = None) -> None:
        """Remove a single pair or all pairs from the exclusion set."""
        self._correlation_monitor.reset_exclusion(pair_key)

    def reset_all_correlation_exclusions(self) -> None:
        """Remove all correlation exclusions."""
        self._correlation_monitor.reset_all()

    def get_correlation_analytics(self) -> dict[str, dict]:
        """Return correlation monitoring analytics."""
        return self._correlation_monitor.get_analytics()

    def get_leg_correlation_history(self) -> dict[str, dict]:
        """Return leg correlation monitoring history."""
        return self._correlation_monitor.get_history()

    # ÔöÇÔöÇ Internal risk limits ÔöÇÔöÇ
    def _maybe_reset_daily_counter(self) -> None:
        # Use strategy clock so backtests advance per simulated bar date.
        # In live trading _clock == datetime.now, so .date() == date.today().
        today = self._clock().date()
        if self.daily_trade_date != today:
            self.daily_trade_count = 0
            self.daily_trade_date = today

    def _record_trade(self) -> None:
        self._maybe_reset_daily_counter()
        self.daily_trade_count += 1

    def update_equity(self, equity: float) -> None:
        """Update current equity and track peak for drawdown calculation."""
        self.current_equity = equity
        if self.peak_equity is None or equity > self.peak_equity:
            self.peak_equity = equity

    def _check_internal_risk_limits(self) -> tuple[bool, str]:
        """Check all internal risk limits. Returns (ok, reason)."""
        self._maybe_reset_daily_counter()
        if len(self.active_trades) >= self.max_positions:
            return False, f"max positions ({self.max_positions}) reached"
        if self.daily_trade_count >= self.max_daily_trades:
            return False, f"max daily trades ({self.max_daily_trades}) reached"
        if self.peak_equity is not None and self.peak_equity > 0 and self.current_equity is not None:
            dd_frac = (self.peak_equity - self.current_equity) / self.peak_equity
            if dd_frac > self.max_drawdown_pct:
                dd_display = dd_frac * 100
                return False, f"max drawdown ({dd_display:.1f}%) breached ÔÇô limit {self.max_drawdown_pct * 100:.0f}%"
        return True, ""

    def load_cached_pairs(self, max_age_hours: int | None = None) -> list[tuple] | None:
        """Load cached cointegrated pairs if recent (delegates to PairCacheManager)."""
        return self._cache_manager.load_cached_pairs(max_age_hours)

    def save_cached_pairs(self, pairs: list[tuple]) -> None:
        """Save cointegrated pairs to cache (delegates to PairCacheManager)."""
        self._cache_manager.save_cached_pairs(pairs)

    @staticmethod
    def _test_pair_cointegration(args: tuple) -> tuple[str, str, float, float] | None:
        """Delegates to PairValidator (backward-compatible alias)."""
        return PairValidator.test_pair_cointegration(args)

    @staticmethod
    def _test_pair_candidate(args: tuple) -> tuple[str, str, float, float] | None:
        """Delegates to PairValidator (backward-compatible alias)."""
        return PairValidator.test_pair_candidate(args)

    def set_clock(self, clock_fn: Callable[[], Any]) -> None:
        """Override the clock function (used by backtester for determinism)."""
        self._clock = cast(ClockFn, clock_fn)

    def find_cointegrated_pairs_parallel(
        self,
        price_data: pd.DataFrame,
        lookback: int | None = None,
        num_workers: int | None = None,
        sector_map: dict[str, str] | None = None,
    ) -> list[tuple[str, str, float, float]]:
        """
        Find cointegrated pairs using multiprocessing + BH-FDR correction.

        When ``sector_map`` is provided, only intra-sector pairs are tested
        and the Bonferroni denominator uses the sector size (not the full
        universe).  This is the standard institutional approach for pair
        trading.

        Multiple-testing correction uses Benjamini-Hochberg FDR (q=0.05)
        instead of plain Bonferroni, which is standard in quantitative
        finance and dramatically reduces Type-II errors while still
        controlling the false discovery rate.

        Args:
            price_data: DataFrame with multiple price series
            lookback: Lookback window (uses config if None)
            num_workers: Number of worker processes (uses cpu_count-1 if None)
            sector_map: Optional dict mapping symbol ÔåÆ sector name.
                        When provided, only intra-sector pairs are tested.

        Returns:
            List of (symbol1, symbol2, pvalue, half_life) tuples
        """
        if lookback is None:
            lookback = self.config.lookback_window

        if num_workers is None:
            num_workers = max(1, cpu_count() - 1)  # Leave 1 core free

        data = price_data.tail(lookback)
        symbols = data.columns.tolist()

        # Use instance-level sector_map if not passed explicitly
        if sector_map is None:
            sector_map = getattr(self, "sector_map", None)

        # ÔöÇÔöÇ Pre-compute I(1) status per symbol (cache) ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        # This avoids repeated ADF/KPSS calls when the same symbol
        # appears in multiple pairs.  Saves ~67% of statsmodels calls.
        i1_cache: dict[str, bool] = {}
        for sym in symbols:
            io = verify_integration_order(pd.Series(data[sym]), name=sym)
            i1_cache[sym] = io["is_I1"]

        i1_symbols = [s for s in symbols if i1_cache.get(s, False)]
        n_dropped = len(symbols) - len(i1_symbols)
        if n_dropped:
            logger.info(
                "pair_discovery_i1_filter",
                total=len(symbols),
                passed=len(i1_symbols),
                dropped=n_dropped,
            )
        symbols = i1_symbols

        # Generate pairs to test.
        # For large universes (>= 50 symbols), use vectorized correlation
        # pre-filter to avoid O(N┬▓) cointegration tests.
        # For small universes, use the full double-loop to preserve exact
        # pair composition and BH-FDR m values.
        from universe.correlation_prefilter import CorrelationPreFilter

        nw_flag = self._cfg_val(self.config, "newey_west_consensus", False)
        joh_flag = self._cfg_val(self.config, "johansen_confirmation", False)

        use_prefilter = len(symbols) >= 50

        if use_prefilter:
            corr_prefilter = CorrelationPreFilter(
                min_correlation=self.config.min_correlation,
                min_data_points=max(60, lookback // 4),
                require_same_sector=(sector_map is not None),
                max_pairs_per_sector=500,
            )
            candidate_pairs = corr_prefilter.filter_pairs(
                pd.DataFrame(data[symbols]),
                sector_map=sector_map,
            )
        else:
            # Original O(N┬▓) loop ÔÇö preserves v18 behavior for small universes
            candidate_pairs = []
            for i, sym1 in enumerate(symbols):
                for sym2 in symbols[i + 1 :]:
                    if sector_map and sector_map.get(sym1) != sector_map.get(sym2):
                        continue
                    candidate_pairs.append((sym1, sym2))

        pairs_to_test = []
        for sym1, sym2 in candidate_pairs:
            pairs_to_test.append(
                (
                    sym1,
                    sym2,
                    data[sym1],
                    data[sym2],
                    self.config.min_correlation,
                    self.config.max_half_life,
                    len(symbols),
                    joh_flag,
                    nw_flag,
                )
            )

        if not pairs_to_test:
            logger.warning("no_pairs_to_test")
            return []

        # ÔöÇÔöÇ Build sector ÔåÆ pair-index map for per-sector FDR ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        pair_sector_map: dict[int, str] = {}
        for idx, args in enumerate(pairs_to_test):
            sym1 = args[0]
            sec = sector_map.get(sym1, "__global__") if sector_map else "__global__"
            pair_sector_map[idx] = sec

        logger.info(
            "pair_discovery_parallel_starting",
            total_pairs=len(pairs_to_test),
            workers=num_workers,
            sector_restricted=sector_map is not None,
        )

        # ÔöÇÔöÇ BH-FDR path: per-sector correction ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        # Applying BH-FDR per sector is statistically more appropriate
        # because each sector constitutes an independent hypothesis
        # family.  Pooling all sectors inflates m and makes the
        # correction ~3-5├ù too conservative for smaller sectors.
        cointegrated_pairs = []
        candidates_total = 0
        try:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                results = list(executor.map(self._test_pair_candidate, pairs_to_test))

            q = self._cfg_val(self.config, "fdr_q_level", 0.10)

            # Group results and test counts by sector
            from collections import defaultdict

            sector_candidates: dict[str, list] = defaultdict(list)
            sector_m: dict[str, int] = defaultdict(int)

            for idx, res in enumerate(results):
                sec = pair_sector_map[idx]
                sector_m[sec] += 1
                if res is not None:
                    sector_candidates[sec].append(res)
                    candidates_total += 1

            # Apply BH-FDR independently per sector
            for sec, cands in sector_candidates.items():
                if not cands:
                    continue
                cands.sort(key=lambda x: x[2])  # sort by p-value ascending
                m = sector_m[sec]  # tests in THIS sector only
                for k in range(len(cands), 0, -1):
                    threshold = k / m * q
                    if cands[k - 1][2] <= threshold:
                        cointegrated_pairs.extend(cands[:k])
                        logger.debug(
                            "sector_fdr_pass",
                            sector=sec,
                            m=m,
                            candidates=len(cands),
                            survived=k,
                            q=q,
                        )
                        break

        except Exception as e:
            logger.error("parallel_discovery_failed", error=str(e))
            return []

        logger.info(
            "pair_discovery_parallel_complete",
            cointegrated_count=len(cointegrated_pairs),
            total_tested=len(pairs_to_test),
            candidates_pre_fdr=candidates_total,
            correction="BH-FDR-per-sector",
        )

        # ÔöÇÔöÇ Cointegration stability filter ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        # Only keep pairs that are stable across rolling windows
        stability_windows = [60, 120, 180]
        stability_threshold = self.config.cointegration_stability_threshold
        stable_pairs = []
        for sym1, sym2, pvalue, hl in cointegrated_pairs:
            if is_cointegration_stable(
                sym1, sym2, price_data, windows=stability_windows, threshold=stability_threshold
            ):
                stable_pairs.append((sym1, sym2, pvalue, hl))
            else:
                logger.info(
                    "pair_stability_failed",
                    pair=f"{sym1}_{sym2}",
                    windows=stability_windows,
                    threshold=stability_threshold,
                )
        logger.info(
            "stability_filter_applied",
            pre_stability=len(cointegrated_pairs),
            post_stability=len(stable_pairs),
            rejected=len(cointegrated_pairs) - len(stable_pairs),
        )
        return stable_pairs

    def find_cointegrated_pairs(
        self,
        price_data: pd.DataFrame,
        lookback: int | None = None,
        use_cache: bool = True,
        use_parallel: bool = True,
        volume_data: dict | None = None,
        weekly_prices: pd.DataFrame | None = None,
    ) -> list[tuple[str, str, float, float]]:
        """
        Find cointegrated pairs in price data.

        Uses caching and multiprocessing for performance.
        When ``weekly_prices`` is provided, applies multi-timeframe
        confirmation after daily BH-FDR discovery.

        Args:
            price_data: DataFrame with multiple price series
            lookback: Lookback window (uses config if None)
            use_cache: Whether to use cached pairs (default: True)
            use_parallel: Whether to use parallel discovery (default: True)
            volume_data: Optional dict mapping symbol ÔåÆ 24h volume USD.
                         Symbols below liquidity_filter.min_volume_24h_usd are excluded.
            weekly_prices: Optional weekly close prices for MTF confirmation.

        Returns:
            List of (symbol1, symbol2, pvalue, half_life) tuples
        """
        # Filter out illiquid symbols if volume_data provided
        if volume_data is not None:
            min_vol = getattr(self.liquidity_filter, "min_volume_24h_usd", 5_000_000)
            liquid_symbols = [s for s in price_data.columns if volume_data.get(s, 0) >= min_vol]
            price_data = pd.DataFrame(price_data[liquid_symbols])

        # Effective cache flag: explicit param AND instance setting
        _use_cache = use_cache and self.use_cache

        # Try cache first if enabled
        if _use_cache:
            cached = self.load_cached_pairs()
            if cached is not None:
                return cached

        # Use parallel discovery if enabled, otherwise sequential
        if use_parallel:
            pairs = self.find_cointegrated_pairs_parallel(price_data, lookback)
        else:
            pairs = self._find_cointegrated_pairs_sequential(price_data, lookback)

        # ÔöÇÔöÇ Multi-lookback discovery: run additional windows & merge ÔöÇÔöÇ
        extra_windows = getattr(self.config, "additional_lookback_windows", [])
        if extra_windows and len(price_data) > max(extra_windows):
            seen = {(p[0], p[1]): p for p in pairs}
            for lb in extra_windows:
                if lb == lookback or lb >= len(price_data):
                    continue
                if use_parallel:
                    extra = self.find_cointegrated_pairs_parallel(price_data, lb)
                else:
                    extra = self._find_cointegrated_pairs_sequential(price_data, lb)
                for ep in extra:
                    key = (ep[0], ep[1])
                    if key not in seen or ep[2] < seen[key][2]:
                        seen[key] = ep
            pairs = list(seen.values())
            logger.info(
                "multi_lookback_merge",
                primary_lb=lookback,
                extra_lbs=extra_windows,
                merged_pairs=len(pairs),
            )

        # ÔöÇÔöÇ Multi-Timeframe weekly confirmation ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        # When weekly prices are available and weekly_confirmation is
        # enabled in config, filter pairs that don't hold on weekly.
        weekly_conf = self._cfg_val(self.config, "weekly_confirmation", False)
        if weekly_conf and weekly_prices is not None and not weekly_prices.empty:
            from data.multi_timeframe import MTFConfig, MultiTimeframeEngine

            mtf = MultiTimeframeEngine(
                MTFConfig(
                    weekly_coint_weight=self._cfg_val(self.config, "weekly_coint_weight", 0.40),
                    weekly_max_pvalue=self._cfg_val(self.config, "weekly_max_pvalue", 0.10),
                    weekly_lookback_bars=self._cfg_val(self.config, "weekly_lookback_bars", 104),
                    weekly_confirmation_required=True,
                )
            )
            pre_mtf = len(pairs)
            confirmed = mtf.confirm_pairs(pairs, weekly_prices)
            # Keep only confirmed pairs, drop the MTF score from output
            pairs = [(s1, s2, pv, hl) for s1, s2, pv, hl, _score in confirmed]
            logger.info(
                "weekly_confirmation_applied",
                pre_mtf_pairs=pre_mtf,
                post_mtf_pairs=len(pairs),
                rejected=pre_mtf - len(pairs),
            )

        # Save to cache
        if _use_cache and pairs:
            self.save_cached_pairs(pairs)

        return pairs

    def _find_cointegrated_pairs_sequential(
        self, price_data: pd.DataFrame, lookback: int | None = None
    ) -> list[tuple[str, str, float, float]]:
        """
        Find cointegrated pairs sequentially (original implementation).

        Kept for fallback and testing purposes.
        """
        if lookback is None:
            lookback = self.config.lookback_window

        data = price_data.tail(lookback)
        symbols = data.columns.tolist()
        cointegrated_pairs = []

        # P1-05: I(1) pre-filter using persistent cache (mirrors parallel path)
        _now_mono = _time_module.monotonic()
        for sym in symbols:
            cached = self._i1_verification_cache.get(sym)
            if cached is None or (_now_mono - cached[1]) > self._i1_cache_ttl_seconds:
                io = verify_integration_order(pd.Series(data[sym]), name=sym)
                self._i1_verification_cache[sym] = (bool(io["is_I1"]), _now_mono)
        symbols = [s for s in symbols if self._i1_verification_cache.get(s, (False, 0.0))[0]]

        for i, sym1 in enumerate(symbols):
            for _j, sym2 in enumerate(symbols[i + 1 :], start=i + 1):
                try:
                    # Normalize prices for correlation
                    corr = pd.Series(data[sym1]).corr(pd.Series(data[sym2]))

                    if abs(corr) < self.config.min_correlation:
                        continue

                    result = engle_granger_test(
                        pd.Series(data[sym1]),
                        pd.Series(data[sym2]),
                        apply_bonferroni=getattr(self.config, "bonferroni_correction", False),
                        num_symbols=len(symbols),
                    )

                    if result["is_cointegrated"]:
                        hl = half_life_mean_reversion(pd.Series(result["residuals"]))

                        if hl and hl <= self.config.max_half_life:
                            cointegrated_pairs.append((sym1, sym2, result["adf_pvalue"], hl))

                            logger.info(
                                "pair_cointegrated", pair=f"{sym1}_{sym2}", pvalue=result["adf_pvalue"], half_life=hl
                            )

                except Exception as e:
                    logger.debug("coint_test_failed", sym1=sym1, sym2=sym2, error=str(e))
                    continue

        return cointegrated_pairs

    def generate_signals(
        self,
        market_data: pd.DataFrame,
        discovered_pairs: list[tuple] | None = None,
        weekly_prices: pd.DataFrame | None = None,
    ) -> list[Signal]:
        """
        Generate pair trading signals based on spread Z-scores.

        Args:
            market_data: DataFrame with price series as columns.
            discovered_pairs: Pre-computed cointegrated pairs.  Each element is
                              ``(sym1, sym2, pvalue, half_life)``.
            weekly_prices: Optional weekly close prices for z-score gate.

        Returns:
            List of Signal objects
        """

        signals = []

        # Find cointegrated pairs (rerun periodically) or use provided list
        if discovered_pairs is not None:
            cointegrated = discovered_pairs
        else:
            cointegrated = self.find_cointegrated_pairs(market_data, self.config.lookback_window)

        # --- DIAGNOSTIC LOG ---
        logger.debug("generate_signals_count", cointegrated_count=len(cointegrated))
        if hasattr(self, "_bar_counter"):
            self._bar_counter += 1
        else:
            self._bar_counter = 1
        if self._bar_counter <= 3:
            logger.debug("cointegrated_pairs_sample", pairs=[p[:2] for p in cointegrated])

        # ÔöÇÔöÇ Phase 1: Update cross-sectional rankings once per bar ÔöÇÔöÇ
        _csm = getattr(self, "_cross_sectional", None)
        if _csm is not None:
            _csm.update_rankings(market_data)

        # ÔöÇÔöÇ Phase 4: Update advanced signal generators once per bar ÔöÇÔöÇ
        _earn = getattr(self, "_earnings_signal", None)
        if _earn is not None:
            _earn.update(market_data)
        _opt = getattr(self, "_options_flow", None)
        if _opt is not None:
            _opt.update(market_data)
        _sent = getattr(self, "_sentiment_signal", None)
        if _sent is not None:
            _sent.update(market_data)

        for sym1, sym2, _pvalue, _hl in cointegrated:
            pair_key = f"{sym1}_{sym2}"

            # Skip pairs excluded due to correlation breakdown
            excluded = getattr(self, "_excluded_pairs_correlation", set())
            if pair_key in excluded:
                continue

            try:
                y = pd.Series(market_data[sym1])
                x = pd.Series(market_data[sym2])
                # Leg-correlation stability check
                corr_ok = self._check_leg_correlation_stability(y, x, pair_key)
                if not corr_ok:
                    self._excluded_pairs_correlation.add(pair_key)
                    if pair_key in self.active_trades:
                        hist = self._leg_correlation_history.get(pair_key, {})
                        signals.append(
                            Signal(
                                symbol_pair=pair_key,
                                side="exit",
                                strength=1.0,
                                reason=(f"Correlation breakdown: recent_corr={hist.get('recent_corr', '?'):.2f}"),
                            )
                        )
                        del self.active_trades[pair_key]
                    continue
                from config.settings import get_settings as _gs_pt2

                model = SpreadModel(y, x, kalman_delta=_gs_pt2().strategy.kalman_delta)
                self.spread_models[pair_key] = model
                _hr_beta, hr_stable = self.hedge_ratio_tracker.reestimate_if_needed(
                    pair_key=pair_key,
                    new_beta=model.beta,
                )
                if not hr_stable:
                    logger.warning("hedge_ratio_unstable", pair=pair_key, beta=model.beta)
                    if pair_key in self.active_trades:
                        signals.append(
                            Signal(
                                symbol_pair=pair_key,
                                side="exit",
                                strength=1.0,
                                reason="Hedge ratio drift ÔÇö pair deprecated",
                            )
                        )
                        del self.active_trades[pair_key]
                    continue
                try:
                    spread = model.compute_spread(y, x)
                except Exception:
                    continue
                # ADF stationarity guard (seuil configurable)
                _adf_window = min(len(spread), 120)
                _adf_spread = spread.iloc[-_adf_window:]
                if len(_adf_spread.dropna()) >= 20:
                    try:
                        _adf_p = adfuller(_adf_spread.dropna().values, autolag="AIC")[1]
                    except Exception:
                        _adf_p = 1.0
                    # Seuil configurable via config.strategy.adf_pvalue_threshold (default 0.10)
                    from config.settings import get_settings as _gs_adf

                    adf_threshold = _gs_adf().strategy.adf_pvalue_threshold
                    if _adf_p > adf_threshold:
                        if pair_key in self.active_trades:
                            signals.append(
                                Signal(
                                    symbol_pair=pair_key,
                                    side="exit",
                                    strength=1.0,
                                    reason=f"Spread non-stationary (ADF p={_adf_p:.3f})",
                                )
                            )
                            del self.active_trades[pair_key]
                        continue
                try:
                    z_score = model.compute_z_score(spread)
                    self.historical_spreads[pair_key] = spread
                    current_z = z_score.iloc[-1]
                    if pd.isna(current_z):
                        continue
                except Exception:
                    continue

                # RISK-3: Update regime detector with latest spread data
                try:
                    regime_state = self.regime_detector.update(
                        spread=float(current_z),
                        date=self._clock(),
                    )
                except Exception:
                    regime_state = None

                # RISK-2: Trailing stop check for active positions
                if pair_key in self.active_trades:
                    ts_exit, ts_reason = self.trailing_stop_manager.should_exit_on_trailing_stop(
                        symbol_pair=pair_key,
                        current_z=float(current_z),
                    )
                    if ts_exit:
                        signals.append(
                            Signal(
                                symbol_pair=pair_key,
                                side="exit",
                                strength=1.0,
                                reason=ts_reason or "Trailing stop triggered",
                            )
                        )
                        del self.active_trades[pair_key]
                        continue

                # Internal risk limits check for new entries
                risk_ok, _risk_reason = self._check_internal_risk_limits()

                # RISK-3: Widen entry threshold in volatile regimes
                effective_entry_z = self.config.entry_z_score
                if regime_state is not None:
                    regime_label = getattr(regime_state, "regime", None) or getattr(
                        regime_state, "current_regime", None
                    )
                    if regime_label is not None and str(regime_label).lower() in (
                        "crisis",
                        "high_volatility",
                        "volatile",
                    ):
                        effective_entry_z = self.config.entry_z_score * 1.5

                # ÔöÇÔöÇ Weekly z-score gate ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
                # Block entry if weekly z-score doesn't confirm the
                # divergence.  This prevents noise entries that only
                # appear on daily but not on the higher timeframe.
                weekly_gate_ok = True
                if weekly_prices is not None and not weekly_prices.empty:
                    weekly_zgate = self._cfg_val(self.config, "weekly_zscore_entry_gate", 0.0)
                    if weekly_zgate > 0 and pair_key not in self.active_trades:
                        from data.multi_timeframe import MultiTimeframeEngine

                        _mtf = MultiTimeframeEngine()
                        _wz = _mtf.compute_weekly_zscore(weekly_prices, sym1, sym2)
                        if _wz is not None and abs(_wz) < weekly_zgate:
                            weekly_gate_ok = False

                # P0 fix: Min-spread filter ÔÇö reject micro-deviations
                _min_spread = getattr(self.config, "entry_z_min_spread", 0.0)
                _abs_spread = abs(float(spread.iloc[-1])) if len(spread) > 0 else 0.0
                _spread_ok = _abs_spread >= _min_spread if _min_spread > 0 else True

                # ÔöÇÔöÇ Momentum overlay gate (v31) ÔöÇÔöÇ
                _mom_result = None
                _mom_gate = True  # default: allow entry
                _mom_score = 0.0
                if getattr(self, "_momentum_enabled", False) and self._momentum is not None:
                    _raw_str = min(abs(current_z) / 3.0, 1.0)
                    if current_z > effective_entry_z and pair_key not in self.active_trades:
                        _mom_result = self._momentum.adjust_signal_strength(
                            side="short",
                            raw_strength=_raw_str,
                            prices_a=y,
                            prices_b=x,
                        )
                        # Gate: block entry if momentum strongly contradicts
                        if (
                            not _mom_result.confirms_signal
                            and _mom_result.adjusted_strength <= self._momentum.min_strength
                        ):
                            _mom_gate = False
                        # Compute momentum score for combiner: RS > 0 means A outperforming
                        _rs = self._momentum.compute_relative_strength(y, x)
                        _mom_score = float(np.clip(_rs * 5.0, -1.0, 1.0))
                    elif current_z < -effective_entry_z and pair_key not in self.active_trades:
                        _mom_result = self._momentum.adjust_signal_strength(
                            side="long",
                            raw_strength=_raw_str,
                            prices_a=y,
                            prices_b=x,
                        )
                        if (
                            not _mom_result.confirms_signal
                            and _mom_result.adjusted_strength <= self._momentum.min_strength
                        ):
                            _mom_gate = False
                        _rs = self._momentum.compute_relative_strength(y, x)
                        _mom_score = float(np.clip(_rs * 5.0, -1.0, 1.0))

                # ÔöÇÔöÇ Phase 1 + Phase 4: Multi-signal combiner ÔöÇÔöÇ
                _ou_gen = getattr(self, "_ou_signal", None)
                _vol_gen = getattr(self, "_vol_signal", None)
                _csm_gen = getattr(self, "_cross_sectional", None)
                _earn_gen = getattr(self, "_earnings_signal", None)
                _opt_gen = getattr(self, "_options_flow", None)
                _sent_gen = getattr(self, "_sentiment_signal", None)
                _combiner = getattr(self, "_signal_combiner", None)
                _composite = None

                if _combiner is not None:
                    _z_norm = float(np.clip(-current_z / (effective_entry_z * 2), -1.0, 1.0))
                    _ou_score = _ou_gen.compute_score(spread) if _ou_gen else 0.0
                    _vol_raw = _vol_gen.compute_score(spread) if _vol_gen else 0.0
                    _z_dir = -1.0 if current_z > 0 else (1.0 if current_z < 0 else 0.0)
                    _vol_score = _vol_raw * _z_dir
                    _cs_raw = _csm_gen.compute_score(sym1, sym2) if _csm_gen else 0.0
                    _cs_score = -_cs_raw
                    _earn_score = _earn_gen.compute_score(sym1, sym2) if _earn_gen else 0.0
                    _opt_score = _opt_gen.compute_score(sym1, sym2) if _opt_gen else 0.0
                    _sent_score = _sent_gen.compute_score(sym1, sym2) if _sent_gen else 0.0

                    _combo_scores = {
                        "zscore": _z_norm,
                        "ou": _ou_score,
                        "vol_regime": _vol_score,
                        "cross_sectional": _cs_score,
                        "intraday_mr": _ou_score * 0.5 + _z_norm * 0.5,
                        "earnings": _earn_score,
                        "options_flow": _opt_score,
                        "sentiment": _sent_score,
                    }
                    if getattr(self, "_momentum_enabled", False):
                        _combo_scores["momentum"] = _mom_score

                    _composite = _combiner.combine(
                        _combo_scores,
                        in_position=pair_key in self.active_trades,
                    )
                    self._last_composite = _composite

                # Entry signals (z-score threshold + combiner confirmation)
                if (
                    current_z > effective_entry_z
                    and pair_key not in self.active_trades
                    and not (risk_ok and weekly_gate_ok and _spread_ok and _mom_gate)
                ):
                    logger.debug(
                        "entry_blocked_gate",
                        pair=pair_key,
                        z=round(current_z, 3),
                        risk_ok=risk_ok,
                        risk_reason=_risk_reason,
                        weekly_ok=weekly_gate_ok,
                        spread_ok=_spread_ok,
                        mom_ok=_mom_gate,
                    )
                if (
                    risk_ok
                    and weekly_gate_ok
                    and _spread_ok
                    and _mom_gate
                    and current_z > effective_entry_z
                    and pair_key not in self.active_trades
                ):
                    if _composite is not None and _composite.confidence > 0.3:
                        _entry_str = abs(_composite.composite_score)
                    else:
                        _entry_str = min(abs(current_z) / 3.0, 1.0)
                    _combo_tag = f" [C:{_composite.composite_score:.2f}]" if _composite else ""
                    _mom_tag = ""
                    if _mom_result:
                        _mom_tag = " [mom:C]" if _mom_result.confirms_signal else " [mom:X]"
                    signals.append(
                        Signal(
                            symbol_pair=pair_key,
                            side="short",
                            strength=_entry_str,
                            reason=f"Z-score={current_z:.2f} > entry threshold{_mom_tag}{_combo_tag}",
                        )
                    )
                    self.active_trades[pair_key] = {"entry_z": current_z, "entry_time": self._clock(), "side": "short"}
                    # RISK-2: Register position with trailing stop manager
                    self.trailing_stop_manager.add_position(
                        symbol_pair=pair_key,
                        side="short",
                        entry_z=float(current_z),
                        entry_spread=float(spread.iloc[-1]),
                        entry_time=cast(pd.Timestamp, pd.Timestamp(str(self._clock()))),
                    )
                    self._record_trade()
                elif (
                    risk_ok
                    and weekly_gate_ok
                    and _spread_ok
                    and _mom_gate
                    and current_z < -effective_entry_z
                    and pair_key not in self.active_trades
                ):
                    if _composite is not None and _composite.confidence > 0.3:
                        _entry_str = abs(_composite.composite_score)
                    else:
                        _entry_str = min(abs(current_z) / 3.0, 1.0)
                    _combo_tag = f" [C:{_composite.composite_score:.2f}]" if _composite else ""
                    _mom_tag = ""
                    if _mom_result:
                        _mom_tag = " [mom:C]" if _mom_result.confirms_signal else " [mom:X]"
                    signals.append(
                        Signal(
                            symbol_pair=pair_key,
                            side="long",
                            strength=_entry_str,
                            reason=f"Z-score={current_z:.2f} < -entry threshold{_mom_tag}{_combo_tag}",
                        )
                    )
                    self.active_trades[pair_key] = {"entry_z": current_z, "entry_time": self._clock(), "side": "long"}
                    # RISK-2: Register position with trailing stop manager
                    self.trailing_stop_manager.add_position(
                        symbol_pair=pair_key,
                        side="long",
                        entry_z=float(current_z),
                        entry_spread=float(spread.iloc[-1]),
                        entry_time=cast(pd.Timestamp, pd.Timestamp(str(self._clock()))),
                    )
                    self._record_trade()
                # Exit signals (mean reversion)
                if pair_key in self.active_trades:
                    self.active_trades[pair_key]
                    if abs(current_z) <= self.config.exit_z_score:
                        signals.append(
                            Signal(
                                symbol_pair=pair_key,
                                side="exit",
                                strength=1.0,
                                reason=f"Mean reversion at Z={current_z:.2f}",
                            )
                        )
                        del self.active_trades[pair_key]
                        # Clean up trailing stop state
                        if pair_key in self.trailing_stop_manager.positions:
                            del self.trailing_stop_manager.positions[pair_key]

                logger.info(
                    "pair_signal_generated", pair=pair_key, z_score=current_z, active_trades=len(self.active_trades)
                )

            except Exception as e:
                logger.error("signal_generation_failed", pair=pair_key, error=str(e))
                continue

        return signals

    def get_state(self) -> dict:
        """Return strategy state."""
        return {
            "active_trades": len(self.active_trades),
            "pairs_monitored": len(self.spread_models),
            "active_trade_details": self.active_trades.as_dict(),
        }
