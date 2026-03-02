import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from datetime import datetime, date, timedelta
from pathlib import Path
from structlog import get_logger
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import cpu_count
import pickle

from strategies.base import BaseStrategy, Signal
from models.cointegration import engle_granger_test, half_life_mean_reversion, newey_west_consensus as _newey_west_consensus, verify_integration_order
from models.spread import SpreadModel
from models.adaptive_thresholds import DynamicSpreadModel
from data.preprocessing import remove_outliers
from config.settings import get_settings
from statsmodels.tsa.stattools import adfuller

logger = get_logger(__name__)

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
    def _cfg_val(config, name: str, default):
        """Safe config accessor – returns *default* when the attribute is absent
        or is a mock auto-attribute (MagicMock)."""
        val = getattr(config, name, default)
        if isinstance(val, (int, float, bool, str, type(None))):
            return val
        return default
    
    def __init__(self):
        self.config = get_settings().strategy
        self.spread_models: Dict[str, SpreadModel] = {}
        self.active_trades: Dict[str, dict] = {}
        self.historical_spreads: Dict[str, pd.Series] = {}
        self.use_cache: bool = True
        
        # Initialize cache directory
        self.cache_dir = Path("cache/pairs")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        _c = self.config  # shorthand

        # ── Sprint components ──
        from models.regime_detector import RegimeDetector
        from models.hedge_ratio_tracker import HedgeRatioTracker
        from models.stationarity_monitor import StationarityMonitor
        from data.liquidity_filter import LiquidityFilter
        from data.delisting_guard import DelistingGuard
        from execution.trailing_stop import TrailingStopManager
        from execution.concentration_limits import ConcentrationLimitManager

        self.regime_detector = RegimeDetector(
            lookback_window=self._cfg_val(_c, 'regime_lookback_window', 20),
            min_regime_duration=self._cfg_val(_c, 'regime_min_duration', 1),
            instant_transition_percentile=self._cfg_val(_c, 'instant_transition_percentile', 99.0),
        )
        self.hedge_ratio_tracker = HedgeRatioTracker(
            reestimation_frequency_days=self._cfg_val(_c, 'hedge_ratio_reestimation_days', 7),
            emergency_vol_sigma=self._cfg_val(_c, 'emergency_vol_threshold_sigma', 3.0),
        )
        self.stationarity_monitor = StationarityMonitor()
        self.liquidity_filter = LiquidityFilter()
        self.delisting_guard = DelistingGuard()
        self.trailing_stop_manager = TrailingStopManager(
            widening_threshold=self._cfg_val(_c, 'trailing_stop_widening', 1.0),
        )
        self.concentration_limits = ConcentrationLimitManager(
            max_symbol_concentration_pct=self._cfg_val(_c, 'max_symbol_concentration_pct', 30.0),
            allow_rebalancing=True,
        )

        from models.model_retraining import ModelRetrainingManager
        self.model_retrainer = ModelRetrainingManager()
        self.pair_regime_states: Dict[str, object] = {}

        # ── Leg-correlation monitoring state ──
        self._excluded_pairs_correlation: set = set()
        self._correlation_exclusions: Dict[str, datetime] = {}
        self._leg_correlation_history: Dict[str, dict] = {}
        self.leg_correlation_window: int = self._cfg_val(_c, 'leg_correlation_window', 30)
        self.leg_correlation_decay_threshold: float = self._cfg_val(_c, 'leg_correlation_decay_threshold', 0.3)

        # ── Internal risk limits ──
        self.max_positions: int = self._cfg_val(_c, 'internal_max_positions', 10)
        self.max_daily_trades: int = self._cfg_val(_c, 'internal_max_daily_trades', 50)
        self.max_drawdown_pct: float = self._cfg_val(_c, 'internal_max_drawdown_pct', 20.0)
        self.daily_trade_count: int = 0
        self.daily_trade_date: date = date.today()
        self.peak_equity: float = self._cfg_val(_c, 'initial_capital', 100_000.0)
        self.current_equity: float = self.peak_equity

    # ── Cache control methods ──
    def disable_cache(self) -> None:
        """Disable pair-cache reads/writes (used by walk-forward to avoid leakage)."""
        self.use_cache = False

    def enable_cache(self) -> None:
        """Re-enable pair caching."""
        self.use_cache = True

    def clear_cache(self) -> None:
        """Delete all cached pair files."""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Adaptive cache TTL ──
    def get_cache_ttl_hours(self) -> int:
        """Return cache TTL in hours based on current volatility regime."""
        from models.regime_detector import VolatilityRegime
        regime = self.regime_detector.current_regime
        if regime == VolatilityRegime.HIGH:
            return int(self._cfg_val(self.config, 'cache_ttl_high_vol', 2))
        elif regime == VolatilityRegime.LOW:
            return int(self._cfg_val(self.config, 'cache_ttl_low_vol', 24))
        else:
            return int(self._cfg_val(self.config, 'cache_ttl_normal_vol', 12))

    # ── Leg-correlation stability ──
    def _check_leg_correlation_stability(
        self,
        y: pd.Series,
        x: pd.Series,
        pair_key: str,
        window: Optional[int] = None,
    ) -> bool:
        """Check if the rolling correlation between pair legs is stable.

        Returns True (safe) when data is insufficient or correlation is above
        the decay threshold.  Returns False on breakdown.
        """
        win = window or self.leg_correlation_window
        threshold = self.leg_correlation_decay_threshold

        if len(y) < 2 * win or len(x) < 2 * win:
            self._leg_correlation_history[pair_key] = {
                'stable': True, 'recent_corr': None, 'reason': 'insufficient_data',
                'window': win,
            }
            return True

        if y.std() < 1e-12 or x.std() < 1e-12:
            self._leg_correlation_history[pair_key] = {
                'stable': True, 'recent_corr': None, 'reason': 'constant_series',
                'window': win,
            }
            return True

        recent_corr = float(y.tail(win).corr(x.tail(win)))
        historical_corr = getattr(self, '_pair_historical_corr', {}).get(pair_key, None)
        if historical_corr is None:
            historical_corr = float(y.corr(x))

        stable = abs(recent_corr) >= threshold
        self._leg_correlation_history[pair_key] = {
            'stable': stable,
            'recent_corr': recent_corr,
            'historical_corr': historical_corr,
            'threshold': threshold,
            'window': win,
        }

        if not stable:
            self._excluded_pairs_correlation.add(pair_key)
            self._correlation_exclusions[pair_key] = datetime.now()

        return stable

    def get_excluded_pairs_correlation(self) -> set:
        """Return the set of pairs excluded due to correlation breakdown."""
        return set(self._excluded_pairs_correlation)

    def get_correlation_exclusions(self) -> Dict[str, datetime]:
        """Return currently excluded pairs with timestamps."""
        return dict(self._correlation_exclusions)

    def reset_correlation_exclusion(self, pair_key: Optional[str] = None) -> None:
        """Remove a single pair or all pairs from the exclusion set."""
        if pair_key is None:
            self._excluded_pairs_correlation.clear()
            self._correlation_exclusions.clear()
        else:
            self._excluded_pairs_correlation.discard(pair_key)
            self._correlation_exclusions.pop(pair_key, None)

    def reset_all_correlation_exclusions(self) -> None:
        """Remove all correlation exclusions."""
        self._excluded_pairs_correlation.clear()
        self._correlation_exclusions.clear()

    def get_correlation_analytics(self) -> Dict[str, dict]:
        """Return correlation monitoring analytics."""
        return dict(self._leg_correlation_history)

    def get_leg_correlation_history(self) -> Dict[str, dict]:
        """Return leg correlation monitoring history."""
        return dict(self._leg_correlation_history)

    # ── Internal risk limits ──
    def _maybe_reset_daily_counter(self) -> None:
        today = date.today()
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

    def _check_internal_risk_limits(self) -> Tuple[bool, str]:
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
                return False, f"max drawdown ({dd_display:.1f}%) breached – limit {self.max_drawdown_pct * 100:.0f}%"
        return True, ""
    
    def load_cached_pairs(self, max_age_hours: Optional[int] = None) -> Optional[List[Tuple]]:
        """
        Load cached cointegrated pairs if recent.
        
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
            mod_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            age = datetime.now() - mod_time
            
            if age < timedelta(hours=max_age_hours):
                try:
                    import json
                    with open(cache_file, 'r') as f:
                        pairs = json.load(f)
                    # pairs are stored as list of [sym1, sym2, ...] lists
                    pairs = [tuple(p) for p in pairs]
                    logger.info(
                        "loaded_cached_pairs", 
                        pairs_count=len(pairs), 
                        age_hours=round(age.total_seconds()/3600, 2)
                    )
                    return pairs
                except Exception as e:
                    logger.warning("cache_load_failed", error=str(e))
        
        return None
    
    def save_cached_pairs(self, pairs: List[Tuple]) -> None:
        """Save cointegrated pairs to cache."""
        try:
            import json
            cache_file = self.cache_dir / "cointegrated_pairs.json"
            # Write to temporary file first, then rename (atomic operation)
            temp_file = cache_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump([list(p) for p in pairs], f, indent=2)
            # Atomic rename
            temp_file.replace(cache_file)
            logger.info("saved_cointegrated_pairs", count=len(pairs))
        except Exception as e:
            logger.warning("cache_save_failed", error=str(e))
    
    @staticmethod
    def _test_pair_cointegration(args: Tuple) -> Optional[Tuple[str, str, float, float]]:
        """
        Test cointegration for a single pair (runs in worker process).

        Args:
            args: Tuple of (sym1, sym2, series1, series2, min_corr, max_hl,
                            num_symbols, johansen_flag, nw_consensus_flag)
                  -- 6-element legacy tuples are also supported.

        Returns:
            (sym1, sym2, pvalue, half_life) tuple or None if not cointegrated
        """
        # Support both 6-element (legacy) and 9-element tuples
        if len(args) == 9:
            sym1, sym2, series1, series2, min_corr, max_hl, num_symbols, johansen_flag, nw_consensus_flag = args
        else:
            sym1, sym2, series1, series2, min_corr, max_hl = args[:6]
            num_symbols = None
            johansen_flag = False
            nw_consensus_flag = False

        # Determine Bonferroni flag: apply when num_symbols is provided
        apply_bonferroni = num_symbols is not None and num_symbols > 1

        try:
            # Check correlation threshold first (fast filter)
            corr = series1.corr(series2)
            if abs(corr) < min_corr:
                return None

            # Run Engle-Granger test with Bonferroni correction
            result = engle_granger_test(
                series1, series2,
                apply_bonferroni=apply_bonferroni,
                num_symbols=num_symbols,
            )

            if result['is_cointegrated']:
                # Newey-West consensus gate
                if nw_consensus_flag:
                    cons = _newey_west_consensus(series1, series2)
                    if not cons['consensus']:
                        return None

                # Calculate half-life of mean reversion
                hl = half_life_mean_reversion(pd.Series(result['residuals']))

                # Filter by half-life
                if hl and hl <= max_hl:
                    return (sym1, sym2, result['adf_pvalue'], hl)

        except Exception:
            pass

        return None

    @staticmethod
    def _test_pair_candidate(args: Tuple) -> Optional[Tuple[str, str, float, float]]:
        """
        Test cointegration and return candidate with raw p-value (for BH-FDR).

        Unlike ``_test_pair_cointegration``, this does NOT apply any
        multiple-testing correction.  The caller is responsible for
        applying BH-FDR on the collected p-values.

        Returns:
            (sym1, sym2, raw_pvalue, half_life) or None if fails
            correlation or half-life checks.
        """
        if len(args) >= 9:
            sym1, sym2, series1, series2, min_corr, max_hl, num_symbols, johansen_flag, nw_consensus_flag = args[:9]
        else:
            sym1, sym2, series1, series2, min_corr, max_hl = args[:6]
            johansen_flag = False
            nw_consensus_flag = False

        try:
            # Fast filter: correlation threshold
            corr = series1.corr(series2)
            if abs(corr) < min_corr:
                return None

            # Run EG test WITHOUT any multiple-testing correction
            # check_integration_order=False because the caller
            # pre-filters symbols via I(1) cache.
            result = engle_granger_test(
                series1, series2,
                apply_bonferroni=False,
                check_integration_order=False,
            )

            pvalue = result.get('adf_pvalue', 1.0)

            # Pre-filter: skip clearly insignificant pairs
            if pvalue >= 0.20 or np.isnan(pvalue):
                return None

            # Newey-West consensus gate (if enabled)
            if nw_consensus_flag:
                cons = _newey_west_consensus(series1, series2)
                if not cons['consensus']:
                    return None

            # Calculate half-life of mean reversion
            hl = half_life_mean_reversion(pd.Series(result['residuals']))
            if not hl or hl > max_hl:
                return None

            return (sym1, sym2, pvalue, hl)

        except Exception:
            return None
    
    def find_cointegrated_pairs_parallel(
        self,
        price_data: pd.DataFrame,
        lookback: int = None,
        num_workers: int = None,
        sector_map: Optional[Dict[str, str]] = None,
    ) -> List[Tuple[str, str, float, float]]:
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
            sector_map: Optional dict mapping symbol → sector name.
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
            sector_map = getattr(self, 'sector_map', None)

        # ── Pre-compute I(1) status per symbol (cache) ──────────────
        # This avoids repeated ADF/KPSS calls when the same symbol
        # appears in multiple pairs.  Saves ~67% of statsmodels calls.
        i1_cache: Dict[str, bool] = {}
        for sym in symbols:
            io = verify_integration_order(data[sym], name=sym)
            i1_cache[sym] = io['is_I1']

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
        # pre-filter to avoid O(N²) cointegration tests.
        # For small universes, use the full double-loop to preserve exact
        # pair composition and BH-FDR m values.
        from universe.correlation_prefilter import CorrelationPreFilter

        nw_flag = self._cfg_val(self.config, 'newey_west_consensus', False)
        joh_flag = self._cfg_val(self.config, 'johansen_confirmation', False)

        use_prefilter = len(symbols) >= 50

        if use_prefilter:
            corr_prefilter = CorrelationPreFilter(
                min_correlation=self.config.min_correlation,
                min_data_points=max(60, lookback // 4),
                require_same_sector=(sector_map is not None),
                max_pairs_per_sector=500,
            )
            candidate_pairs = corr_prefilter.filter_pairs(
                data[symbols], sector_map=sector_map,
            )
        else:
            # Original O(N²) loop — preserves v18 behavior for small universes
            candidate_pairs = []
            for i, sym1 in enumerate(symbols):
                for sym2 in symbols[i + 1:]:
                    if sector_map and sector_map.get(sym1) != sector_map.get(sym2):
                        continue
                    candidate_pairs.append((sym1, sym2))

        pairs_to_test = []
        for sym1, sym2 in candidate_pairs:
            pairs_to_test.append((
                sym1, 
                sym2, 
                data[sym1], 
                data[sym2],
                self.config.min_correlation,
                self.config.max_half_life,
                len(symbols),
                joh_flag,
                nw_flag,
            ))
        
        if not pairs_to_test:
            logger.warning("no_pairs_to_test")
            return []
        
        # ── Build sector → pair-index map for per-sector FDR ────────
        pair_sector_map: Dict[int, str] = {}
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
        
        # ── BH-FDR path: per-sector correction ──────────────────────
        # Applying BH-FDR per sector is statistically more appropriate
        # because each sector constitutes an independent hypothesis
        # family.  Pooling all sectors inflates m and makes the
        # correction ~3-5× too conservative for smaller sectors.
        cointegrated_pairs = []
        candidates_total = 0
        try:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                results = list(executor.map(
                    self._test_pair_candidate, pairs_to_test
                ))
            
            q = self._cfg_val(self.config, 'fdr_q_level', 0.10)

            # Group results and test counts by sector
            from collections import defaultdict
            sector_candidates: Dict[str, list] = defaultdict(list)
            sector_m: Dict[str, int] = defaultdict(int)

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
        
        return cointegrated_pairs
    
    def find_cointegrated_pairs(
        self,
        price_data: pd.DataFrame,
        lookback: int = None,
        use_cache: bool = True,
        use_parallel: bool = True,
        volume_data: dict = None,
        weekly_prices: Optional[pd.DataFrame] = None,
    ) -> List[Tuple[str, str, float, float]]:
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
            volume_data: Optional dict mapping symbol → 24h volume USD.
                         Symbols below liquidity_filter.min_volume_24h_usd are excluded.
            weekly_prices: Optional weekly close prices for MTF confirmation.
        
        Returns:
            List of (symbol1, symbol2, pvalue, half_life) tuples
        """
        # Filter out illiquid symbols if volume_data provided
        if volume_data is not None:
            min_vol = getattr(self.liquidity_filter, 'min_volume_24h_usd', 5_000_000)
            liquid_symbols = [s for s in price_data.columns if volume_data.get(s, 0) >= min_vol]
            price_data = price_data[liquid_symbols]

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

        # ── Multi-lookback discovery: run additional windows & merge ──
        extra_windows = getattr(self.config, 'additional_lookback_windows', [])
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
        
        # ── Multi-Timeframe weekly confirmation ──────────────────────
        # When weekly prices are available and weekly_confirmation is
        # enabled in config, filter pairs that don't hold on weekly.
        weekly_conf = self._cfg_val(self.config, 'weekly_confirmation', False)
        if weekly_conf and weekly_prices is not None and not weekly_prices.empty:
            from data.multi_timeframe import MultiTimeframeEngine, MTFConfig
            mtf = MultiTimeframeEngine(MTFConfig(
                weekly_coint_weight=self._cfg_val(self.config, 'weekly_coint_weight', 0.40),
                weekly_max_pvalue=self._cfg_val(self.config, 'weekly_max_pvalue', 0.10),
                weekly_lookback_bars=self._cfg_val(self.config, 'weekly_lookback_bars', 104),
                weekly_confirmation_required=True,
            ))
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
        self,
        price_data: pd.DataFrame,
        lookback: int = None
    ) -> List[Tuple[str, str, float, float]]:
        """
        Find cointegrated pairs sequentially (original implementation).
        
        Kept for fallback and testing purposes.
        """
        if lookback is None:
            lookback = self.config.lookback_window
        
        data = price_data.tail(lookback)
        symbols = data.columns.tolist()
        cointegrated_pairs = []
        
        for i, sym1 in enumerate(symbols):
            for j, sym2 in enumerate(symbols[i+1:], start=i+1):
                try:
                    # Normalize prices for correlation
                    corr = data[sym1].corr(data[sym2])
                    
                    if abs(corr) < self.config.min_correlation:
                        continue
                    
                    result = engle_granger_test(
                        data[sym1], data[sym2],
                        apply_bonferroni=getattr(self.config, 'bonferroni_correction', False),
                        num_symbols=len(symbols),
                    )
                    
                    if result['is_cointegrated']:
                        hl = half_life_mean_reversion(
                            pd.Series(result['residuals'])
                        )
                        
                        if hl and hl <= self.config.max_half_life:
                            cointegrated_pairs.append((
                                sym1, sym2, result['adf_pvalue'], hl
                            ))
                            
                            logger.info(
                                "pair_cointegrated",
                                pair=f"{sym1}_{sym2}",
                                pvalue=result['adf_pvalue'],
                                half_life=hl
                            )
                
                except Exception as e:
                    logger.debug("coint_test_failed", sym1=sym1, sym2=sym2, error=str(e))
                    continue
        
        return cointegrated_pairs
    
    def generate_signals(
        self,
        market_data: pd.DataFrame,
        discovered_pairs: Optional[List[Tuple]] = None,
        weekly_prices: Optional[pd.DataFrame] = None,
    ) -> List[Signal]:
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
        
        for sym1, sym2, pvalue, hl in cointegrated:
            pair_key = f"{sym1}_{sym2}"

            # Skip pairs excluded due to correlation breakdown
            excluded = getattr(self, '_excluded_pairs_correlation', set())
            if pair_key in excluded:
                continue
            
            try:
                y = market_data[sym1]
                x = market_data[sym2]

                # Leg-correlation stability check
                corr_ok = self._check_leg_correlation_stability(y, x, pair_key)
                if not corr_ok:
                    # Mark pair as excluded
                    self._excluded_pairs_correlation.add(pair_key)
                    # Emit exit signal if there's an active trade
                    if pair_key in self.active_trades:
                        hist = self._leg_correlation_history.get(pair_key, {})
                        signals.append(Signal(
                            symbol_pair=pair_key,
                            side="exit",
                            strength=1.0,
                            reason=(
                                f"Correlation breakdown: recent_corr="
                                f"{hist.get('recent_corr', '?'):.2f}"
                            ),
                        ))
                        del self.active_trades[pair_key]
                    continue
                
                # Build/update spread model
                model = SpreadModel(y, x)
                self.spread_models[pair_key] = model

                # Hedge ratio drift monitoring
                hr_beta, hr_stable = self.hedge_ratio_tracker.reestimate_if_needed(
                    pair_key=pair_key,
                    new_beta=model.beta,
                )
                if not hr_stable:
                    logger.warning("hedge_ratio_unstable", pair=pair_key, beta=model.beta)
                    if pair_key in self.active_trades:
                        signals.append(Signal(
                            symbol_pair=pair_key,
                            side="exit",
                            strength=1.0,
                            reason=f"Hedge ratio drift — pair deprecated",
                        ))
                        del self.active_trades[pair_key]
                    continue
                
                # Compute spread
                spread = model.compute_spread(y, x)

                # ADF stationarity guard: reject entry if spread is non-stationary
                _adf_window = min(len(spread), 120)
                _adf_spread = spread.iloc[-_adf_window:]
                if len(_adf_spread.dropna()) >= 20:
                    try:
                        _adf_p = adfuller(_adf_spread.dropna().values, autolag='AIC')[1]
                    except Exception:
                        _adf_p = 1.0
                    if _adf_p > 0.10:
                        # Spread is non-stationary — skip pair and emit exit if active
                        if pair_key in self.active_trades:
                            signals.append(Signal(
                                symbol_pair=pair_key,
                                side="exit",
                                strength=1.0,
                                reason=f"Spread non-stationary (ADF p={_adf_p:.3f})",
                            ))
                            del self.active_trades[pair_key]
                        continue

                # Adaptive Z-score lookback based on half-life (no hardcoded 20)
                z_score = model.compute_z_score(spread)
                
                self.historical_spreads[pair_key] = spread
                
                # Current Z-score
                current_z = z_score.iloc[-1]

                # Internal risk limits check for new entries
                risk_ok, risk_reason = self._check_internal_risk_limits()

                # ── Weekly z-score gate ──────────────────────────────
                # Block entry if weekly z-score doesn't confirm the
                # divergence.  This prevents noise entries that only
                # appear on daily but not on the higher timeframe.
                weekly_gate_ok = True
                if weekly_prices is not None and not weekly_prices.empty:
                    weekly_zgate = self._cfg_val(
                        self.config, 'weekly_zscore_entry_gate', 0.0
                    )
                    if weekly_zgate > 0 and pair_key not in self.active_trades:
                        from data.multi_timeframe import MultiTimeframeEngine
                        _mtf = MultiTimeframeEngine()
                        _wz = _mtf.compute_weekly_zscore(weekly_prices, sym1, sym2)
                        if _wz is not None and abs(_wz) < weekly_zgate:
                            weekly_gate_ok = False
                
                # Entry signals
                if risk_ok and weekly_gate_ok and current_z > self.config.entry_z_score and pair_key not in self.active_trades:
                    signals.append(Signal(
                        symbol_pair=pair_key,
                        side="short",
                        strength=min(abs(current_z) / 3.0, 1.0),
                        reason=f"Z-score={current_z:.2f} > entry threshold"
                    ))
                    self.active_trades[pair_key] = {
                        'entry_z': current_z,
                        'entry_time': datetime.now(),
                        'side': 'short'
                    }
                    self._record_trade()
                
                elif risk_ok and weekly_gate_ok and current_z < -self.config.entry_z_score and pair_key not in self.active_trades:
                    signals.append(Signal(
                        symbol_pair=pair_key,
                        side="long",
                        strength=min(abs(current_z) / 3.0, 1.0),
                        reason=f"Z-score={current_z:.2f} < -entry threshold"
                    ))
                    self.active_trades[pair_key] = {
                        'entry_z': current_z,
                        'entry_time': datetime.now(),
                        'side': 'long'
                    }
                    self._record_trade()
                
                # Exit signals (mean reversion)
                if pair_key in self.active_trades:
                    trade = self.active_trades[pair_key]
                    if abs(current_z) <= self.config.exit_z_score:
                        signals.append(Signal(
                            symbol_pair=pair_key,
                            side="exit",
                            strength=1.0,
                            reason=f"Mean reversion at Z={current_z:.2f}"
                        ))
                        del self.active_trades[pair_key]
                
                logger.info(
                    "pair_signal_generated",
                    pair=pair_key,
                    z_score=current_z,
                    active_trades=len(self.active_trades)
                )
            
            except Exception as e:
                logger.error("signal_generation_failed", pair=pair_key, error=str(e))
                continue
        
        return signals
    
    def get_state(self) -> dict:
        """Return strategy state."""
        return {
            'active_trades': len(self.active_trades),
            'pairs_monitored': len(self.spread_models),
            'active_trade_details': self.active_trades
        }
