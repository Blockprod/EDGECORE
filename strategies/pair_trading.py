import pandas as pd
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from pathlib import Path
from structlog import get_logger
from multiprocessing import Pool, cpu_count
import pickle

from strategies.base import BaseStrategy, Signal
from models.cointegration import engle_granger_test, half_life_mean_reversion
from models.spread import SpreadModel
from config.settings import get_settings

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
    
    def __init__(self):
        self.config = get_settings().strategy
        self.spread_models: Dict[str, SpreadModel] = {}
        self.active_trades: Dict[str, dict] = {}
        self.historical_spreads: Dict[str, pd.Series] = {}
        
        # Initialize cache directory
        self.cache_dir = Path("cache/pairs")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def load_cached_pairs(self, max_age_hours: int = 24) -> Optional[List[Tuple]]:
        """
        Load cached cointegrated pairs if recent.
        
        Args:
            max_age_hours: Maximum cache age in hours
        
        Returns:
            Cached pairs list or None if cache is stale/missing
        """
        cache_file = self.cache_dir / "cointegrated_pairs.pkl"
        
        if cache_file.exists():
            mod_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            age = datetime.now() - mod_time
            
            if age < timedelta(hours=max_age_hours):
                try:
                    with open(cache_file, 'rb') as f:
                        pairs = pickle.load(f)
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
            cache_file = self.cache_dir / "cointegrated_pairs.pkl"
            # Write to temporary file first, then rename (atomic operation)
            temp_file = cache_file.with_suffix('.tmp')
            with open(temp_file, 'wb') as f:
                pickle.dump(pairs, f)
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
            args: Tuple of (sym1, sym2, series1, series2, min_corr, max_hl)
        
        Returns:
            (sym1, sym2, pvalue, half_life) tuple or None if not cointegrated
        """
        sym1, sym2, series1, series2, min_corr, max_hl = args
        
        try:
            # Check correlation threshold first (fast filter)
            corr = series1.corr(series2)
            if abs(corr) < min_corr:
                return None
            
            # Run Engle-Granger test
            result = engle_granger_test(series1, series2)
            
            if result['is_cointegrated']:
                # Calculate half-life of mean reversion
                hl = half_life_mean_reversion(pd.Series(result['residuals']))
                
                # Filter by half-life
                if hl and hl <= max_hl:
                    return (sym1, sym2, result['adf_pvalue'], hl)
        
        except Exception:
            pass
        
        return None
    
    def find_cointegrated_pairs_parallel(
        self,
        price_data: pd.DataFrame,
        lookback: int = None,
        num_workers: int = None
    ) -> List[Tuple[str, str, float, float]]:
        """
        Find cointegrated pairs using multiprocessing.
        
        5-10x faster than sequential version for large symbol sets.
        
        Args:
            price_data: DataFrame with multiple price series
            lookback: Lookback window (uses config if None)
            num_workers: Number of worker processes (uses cpu_count-1 if None)
        
        Returns:
            List of (symbol1, symbol2, pvalue, half_life) tuples
        """
        if lookback is None:
            lookback = self.config.lookback_window
        
        if num_workers is None:
            num_workers = max(1, cpu_count() - 1)  # Leave 1 core free
        
        data = price_data.tail(lookback)
        symbols = data.columns.tolist()
        
        # Generate all pairs to test
        pairs_to_test = []
        for i, sym1 in enumerate(symbols):
            for j, sym2 in enumerate(symbols[i+1:], start=i+1):
                pairs_to_test.append((
                    sym1, 
                    sym2, 
                    data[sym1], 
                    data[sym2],
                    self.config.min_correlation,
                    self.config.max_half_life
                ))
        
        if not pairs_to_test:
            logger.warning("no_pairs_to_test")
            return []
        
        logger.info(
            "pair_discovery_parallel_starting",
            total_pairs=len(pairs_to_test),
            workers=num_workers
        )
        
        # Test pairs in parallel
        cointegrated_pairs = []
        try:
            with Pool(num_workers) as pool:
                results = pool.map(self._test_pair_cointegration, pairs_to_test)
            
            # Filter out None results
            cointegrated_pairs = [r for r in results if r is not None]
        
        except Exception as e:
            logger.error("parallel_discovery_failed", error=str(e))
            return []
        
        logger.info(
            "pair_discovery_parallel_complete",
            cointegrated_count=len(cointegrated_pairs),
            total_tested=len(pairs_to_test)
        )
        
        return cointegrated_pairs
    
    def find_cointegrated_pairs(
        self,
        price_data: pd.DataFrame,
        lookback: int = None,
        use_cache: bool = True,
        use_parallel: bool = True
    ) -> List[Tuple[str, str, float, float]]:
        """
        Find cointegrated pairs in price data.
        
        Uses caching and multiprocessing for performance.
        
        Args:
            price_data: DataFrame with multiple price series
            lookback: Lookback window (uses config if None)
            use_cache: Whether to use cached pairs (default: True)
            use_parallel: Whether to use parallel discovery (default: True)
        
        Returns:
            List of (symbol1, symbol2, pvalue, half_life) tuples
        """
        # Try cache first if enabled
        if use_cache:
            cached = self.load_cached_pairs(max_age_hours=24)
            if cached is not None:
                return cached
        
        # Use parallel discovery if enabled, otherwise sequential
        if use_parallel:
            pairs = self.find_cointegrated_pairs_parallel(price_data, lookback)
        else:
            pairs = self._find_cointegrated_pairs_sequential(price_data, lookback)
        
        # Save to cache
        if use_cache and pairs:
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
                    
                    result = engle_granger_test(data[sym1], data[sym2])
                    
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
    
    def generate_signals(self, market_data: pd.DataFrame) -> List[Signal]:
        """
        Generate pair trading signals based on spread Z-scores.
        
        Args:
            market_data: DataFrame with OHLCV data (multi-level columns or dict of series)
        
        Returns:
            List of Signal objects
        """
        signals = []
        
        # Find cointegrated pairs (rerun periodically)
        cointegrated = self.find_cointegrated_pairs(market_data, self.config.lookback_window)
        
        for sym1, sym2, pvalue, hl in cointegrated:
            pair_key = f"{sym1}_{sym2}"
            
            try:
                y = market_data[sym1]
                x = market_data[sym2]
                
                # Build/update spread model
                model = SpreadModel(y, x)
                self.spread_models[pair_key] = model
                
                # Compute spread
                spread = model.compute_spread(y, x)
                z_score = model.compute_z_score(spread, lookback=20)
                
                self.historical_spreads[pair_key] = spread
                
                # Current Z-score
                current_z = z_score.iloc[-1]
                
                # Entry signals
                if current_z > self.config.entry_z_score and pair_key not in self.active_trades:
                    signals.append(Signal(
                        symbol_pair=pair_key,
                        side="short",  # Short spread (sell high, buy low)
                        strength=min(abs(current_z) / 3.0, 1.0),
                        reason=f"Z-score={current_z:.2f} > entry threshold"
                    ))
                    self.active_trades[pair_key] = {
                        'entry_z': current_z,
                        'entry_time': datetime.now(),
                        'side': 'short'
                    }
                
                elif current_z < -self.config.entry_z_score and pair_key not in self.active_trades:
                    signals.append(Signal(
                        symbol_pair=pair_key,
                        side="long",  # Long spread
                        strength=min(abs(current_z) / 3.0, 1.0),
                        reason=f"Z-score={current_z:.2f} < -entry threshold"
                    ))
                    self.active_trades[pair_key] = {
                        'entry_z': current_z,
                        'entry_time': datetime.now(),
                        'side': 'long'
                    }
                
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
