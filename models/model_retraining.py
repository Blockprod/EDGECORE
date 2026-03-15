"""
Model Retraining and Pair Discovery Management (S2.6).

Periodically re-discovers cointegrated pairs and re-estimates hedge ratios to adapt
to market regime changes and detect when historical pairs lose cointegration.

Includes:
- Pair discovery engine (cointegration testing with filter criteria)
- Hedge ratio re-estimation and stability validation
- Pair lifecycle tracking (discovery date, last re-estimate, stability metrics)
- Scheduled retraining with walk-forward validation
- Impact analysis: Which existing pairs improved/degraded

Example:
    retrainer = ModelRetrainingManager(
        discovery_lookback_days=252,
        reestimation_frequency_days=14,
        cointegration_threshold=0.05
    )
    
    # Re-discover pairs from recent data
    new_pairs = retrainer.discover_cointegrated_pairs(
        price_data=df_prices,
        symbols=all_symbols
    )
    
    # Re-estimate hedge ratios for existing pairs
    updated_pairs = retrainer.reestimate_hedge_ratios(
        price_data=df_prices,
        existing_pairs=current_pairs
    )
    
    # Get retraining report
    report = retrainer.get_retraining_report()
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from structlog import get_logger

from models.cointegration import engle_granger_test_cpp_optimized as engle_granger_test

logger = get_logger(__name__)


@dataclass
class PairDiscoveryMetadata:
    """Metadata for discovered/tracked pair."""
    
    pair_key: str
    """Unique identifier: symbol1-symbol2"""
    
    discovery_date: datetime
    """When this pair was first discovered"""
    
    last_reestimate_date: datetime
    """When hedge ratio was last re-estimated"""
    
    discovery_p_value: float
    """P-value from cointegration test at discovery"""
    
    current_p_value: Optional[float] = None
    """Current p-value (updated on re-estimation)"""
    
    current_hedge_ratio: Optional[float] = None
    """Current hedge ratio ╬▓ estimate"""
    
    initial_hedge_ratio: Optional[float] = None
    """Original hedge ratio at discovery"""
    
    hedge_ratio_drift: Optional[float] = None
    """| current - initial | / initial (percent change)"""
    
    reestimation_count: int = 0
    """Number of times this pair has been re-estimated"""
    
    is_valid: bool = True
    """Whether pair still meets cointegration criteria"""
    
    stability_score: float = 0.9
    """Score 0-1: How statistically sound the pair remains (1.0 = perfect)"""
    
    days_since_discovery: int = 0
    """Elapsed time since initial discovery"""
    
    metadata: Dict = field(default_factory=dict)
    """Additional tracking info (reason for invalidation, etc.)"""


@dataclass
class RetrainingReport:
    """Summary of model retraining session."""
    
    retraining_date: datetime
    """When retraining was performed"""
    
    discovery_lookback_days: int
    """Window used for discovering new pairs"""
    
    pairs_total: int
    """Total pairs tracked"""
    
    pairs_valid: int
    """Pairs still cointegrated"""
    
    pairs_degraded: int
    """Pairs that lost cointegration"""
    
    pairs_newly_discovered: int
    """New pairs found in this retraining"""
    
    pairs_stable: int
    """Pairs with stable hedge ratios (drift < 10%)"""
    
    pairs_drifting: int
    """Pairs with significant ╬▓ drift (drift >= 10%)"""
    
    avg_hedge_ratio_drift: float
    """Average hedge ratio change across pairs"""
    
    avg_p_value: float
    """Average cointegration p-value"""
    
    new_pairs: List[str] = field(default_factory=list)
    """Newly discovered pair keys"""
    
    invalidated_pairs: List[str] = field(default_factory=list)
    """Pairs that failed cointegration test"""
    
    drifting_pairs: List[Tuple[str, float]] = field(default_factory=list)
    """(pair_key, drift_pct) for high-drift pairs"""
    
    summary: str = ""
    """Human-readable summary"""


class ModelRetrainingManager:
    """
    Manages periodic re-discovery and re-estimation of pair trading models.
    
    Handles:
    - Re-discovering cointegrated pairs from market data
    - Re-estimating hedge ratios for existing pairs
    - Validating pair stability and detecting degradation
    - Scheduling periodic retraining sessions
    - Tracking pair lifecycle and metadata
    
    Attributes:
        discovery_lookback_days: Historical data window for pair discovery (default 252)
        reestimation_frequency_days: How often to re-estimate (default 14)
        cointegration_threshold: Max p-value for cointegration (default 0.05)
        hedge_ratio_drift_threshold: Max acceptable ╬▓ change % (default 0.10 = 10%)
        min_pair_age_days: Minimum days before consideration for removal (default 30)
    """
    
    def __init__(
        self,
        discovery_lookback_days: int = 252,
        reestimation_frequency_days: int = 14,
        cointegration_threshold: float = 0.05,
        hedge_ratio_drift_threshold: float = 0.10,
        min_pair_age_days: int = 30
    ):
        """
        Initialize retraining manager.
        
        Args:
            discovery_lookback_days: Window for pair discovery (default 252 = 1 year)
            reestimation_frequency_days: How often to update (default 14 = 2 weeks)
            cointegration_threshold: P-value threshold for acceptance (default 0.05)
            hedge_ratio_drift_threshold: Max acceptable ╬▓ change (default 0.10 = 10%)
            min_pair_age_days: Min age before eligible for removal (default 30)
        """
        self.discovery_lookback_days = discovery_lookback_days
        self.reestimation_frequency_days = reestimation_frequency_days
        self.cointegration_threshold = cointegration_threshold
        self.hedge_ratio_drift_threshold = hedge_ratio_drift_threshold
        self.min_pair_age_days = min_pair_age_days
        
        # Pair tracking
        self.tracked_pairs: Dict[str, PairDiscoveryMetadata] = {}
        self.retraining_history: List[RetrainingReport] = []
        self.last_retraining_date: Optional[datetime] = None
    
    def discover_cointegrated_pairs(
        self,
        price_data: pd.DataFrame,
        symbols: List[str],
        exclude_existing: bool = True
    ) -> List[Tuple[str, float, float]]:
        """
        Discover cointegrated pairs from price data.
        
        .. deprecated:: 2026.03
            Use ``PairTradingStrategy.find_cointegrated_pairs()`` as the
            single canonical pair discovery path.  This method will be
            removed in a future release.
        
        Uses Engle-Granger cointegration test to find statistically significant spreads.
        Tests all symbol pairs and returns those passing cointegration test.
        
        Args:
            price_data: DataFrame with columns for each symbol, datetime index
            symbols: List of symbols to test for pairs
            exclude_existing: Skip pairs already tracked (default True)
            
        Returns:
            List of (pair_key, p_value, hedge_ratio) for discovered pairs
        """
        import warnings
        warnings.warn(
            "ModelRetrainingManager.discover_cointegrated_pairs() is deprecated. "
            "Use PairTradingStrategy.find_cointegrated_pairs() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        discovered = []
        tested_count = 0
        cointegrated_count = 0
        
        # Filter data to lookback window
        cutoff_date = datetime.now() - timedelta(days=self.discovery_lookback_days)
        if isinstance(price_data.index, pd.DatetimeIndex):
            recent_data = price_data[price_data.index >= cutoff_date]
        else:
            recent_data = price_data.tail(self.discovery_lookback_days)
        
        # Test all pairs
        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i + 1:]:
                pair_key = f"{sym1}-{sym2}"
                
                # Skip if already tracked and flagged to exclude
                if exclude_existing and pair_key in self.tracked_pairs:
                    continue
                
                # Get price series
                if sym1 not in recent_data.columns or sym2 not in recent_data.columns:
                    continue
                
                y = recent_data[sym1].values
                x = recent_data[sym2].values
                
                # Test cointegration
                try:
                    eg_result = engle_granger_test(y, x)
                    p_value = eg_result['adf_pvalue']
                    tested_count += 1
                    
                    if p_value < self.cointegration_threshold:
                        # Cointegrated - extract hedge ratio from regression
                        hedge_ratio = eg_result.get('beta', np.nan)
                        if not np.isnan(hedge_ratio):
                            discovered.append((pair_key, p_value, hedge_ratio))
                            cointegrated_count += 1
                            logger.debug(
                                "pair_discovered",
                                pair=pair_key,
                                p_value=f"{p_value:.4f}",
                                hedge_ratio=f"{hedge_ratio:.4f}"
                            )
                
                except Exception as e:
                    logger.debug("pair_test_failed", pair=pair_key, error=str(e))
                    continue
        
        logger.info(
            "pair_discovery_complete",
            tested_count=tested_count,
            cointegrated_count=cointegrated_count,
            cointegration_rate=f"{cointegrated_count / max(tested_count, 1) * 100:.1f}%",
            new_pairs_found=len(discovered)
        )
        
        return discovered
    
    def reestimate_hedge_ratios(
        self,
        price_data: pd.DataFrame,
        paired_symbols: List[Tuple[str, str]]
    ) -> Dict[str, Tuple[float, float]]:
        """
        Re-estimate hedge ratios for existing pair models.
        
        Updates ╬▓ estimates for tracked pairs using recent data window, checking for
        statistical degradation or significant drift from original values.
        
        Args:
            price_data: DataFrame with price data
            paired_symbols: List of (symbol1, symbol2) tuples to re-estimate
            
        Returns:
            Dict of pair_key -> (new_hedge_ratio, p_value)
        """
        reestimated = {}
        
        # Filter data to lookback window
        cutoff_date = datetime.now() - timedelta(days=self.discovery_lookback_days)
        if isinstance(price_data.index, pd.DatetimeIndex):
            recent_data = price_data[price_data.index >= cutoff_date]
        else:
            recent_data = price_data.tail(self.discovery_lookback_days)
        
        for sym1, sym2 in paired_symbols:
            pair_key = f"{sym1}-{sym2}"
            
            # Get price series
            if sym1 not in recent_data.columns or sym2 not in recent_data.columns:
                continue
            
            y = recent_data[sym1].values
            x = recent_data[sym2].values
            
            try:
                # Test cointegration with recent data
                eg_result = engle_granger_test(y, x)
                p_value = eg_result['adf_pvalue']
                new_hedge_ratio = eg_result.get('beta', np.nan)
                
                if not np.isnan(new_hedge_ratio):
                    reestimated[pair_key] = (new_hedge_ratio, p_value)
                    
                    # Update tracking metadata if pair is tracked
                    if pair_key in self.tracked_pairs:
                        metadata = self.tracked_pairs[pair_key]
                        old_hedge = metadata.current_hedge_ratio or metadata.initial_hedge_ratio
                        
                        # Calculate drift
                        if old_hedge is not None and old_hedge != 0:
                            drift = abs(new_hedge_ratio - old_hedge) / abs(old_hedge)
                        else:
                            drift = 0.0
                        
                        metadata.current_hedge_ratio = new_hedge_ratio
                        metadata.current_p_value = p_value
                        metadata.hedge_ratio_drift = drift
                        metadata.reestimation_count += 1
                        metadata.last_reestimate_date = datetime.now()
                        
                        # Check if still valid
                        if p_value >= self.cointegration_threshold:
                            metadata.is_valid = False
                            metadata.metadata['invalidated_date'] = datetime.now().isoformat()
                            metadata.metadata['invalidation_reason'] = f"p_value {p_value:.4f} > threshold {self.cointegration_threshold}"
                            logger.warning(
                                "pair_lost_cointegration",
                                pair=pair_key,
                                p_value=f"{p_value:.4f}",
                                threshold=f"{self.cointegration_threshold:.4f}"
                            )
                        else:
                            metadata.is_valid = True
                        
                        # Flag for high drift
                        if drift > self.hedge_ratio_drift_threshold:
                            logger.warning(
                                "pair_hedge_ratio_drift",
                                pair=pair_key,
                                old_hedge=f"{old_hedge:.4f}",
                                new_hedge=f"{new_hedge_ratio:.4f}",
                                drift_pct=f"{drift * 100:.2f}%"
                            )
                
            except Exception as e:
                logger.debug("pair_reestimation_failed", pair=pair_key, error=str(e))
                continue
        
        logger.info(
            "pair_reestimation_complete",
            pairs_reestimated=len(reestimated)
        )
        
        return reestimated
    
    def register_pair(
        self,
        pair_key: str,
        symbol1: str,
        symbol2: str,
        p_value: float,
        hedge_ratio: float,
        discovery_date: Optional[datetime] = None
    ) -> None:
        """
        Register a pair for tracking and future re-estimation.
        
        Args:
            pair_key: Pair identifier (symbol1-symbol2)
            symbol1: First symbol
            symbol2: Second symbol
            p_value: Cointegration p-value
            hedge_ratio: Initial hedge ratio estimate
            discovery_date: When pair was discovered (uses now if None)
        """
        if pair_key in self.tracked_pairs:
            return  # Already tracked
        
        discovery_date = discovery_date or datetime.now()
        
        metadata = PairDiscoveryMetadata(
            pair_key=pair_key,
            discovery_date=discovery_date,
            last_reestimate_date=discovery_date,
            discovery_p_value=p_value,
            current_p_value=p_value,
            current_hedge_ratio=hedge_ratio,
            initial_hedge_ratio=hedge_ratio,
            hedge_ratio_drift=0.0,
            reestimation_count=1,
            is_valid=True,
            stability_score=1.0 if p_value < self.cointegration_threshold else 0.0
        )
        
        self.tracked_pairs[pair_key] = metadata
        
        logger.info(
            "pair_registered",
            pair=pair_key,
            discovery_date=discovery_date.isoformat(),
            p_value=f"{p_value:.4f}",
            hedge_ratio=f"{hedge_ratio:.4f}"
        )
    
    def get_pair_stability_score(self, pair_key: str) -> float:
        """
        Calculate stability score for a pair (0-1, higher = better).
        
        Composite score based on:
        - Cointegration p-value (lower is better)
        - Hedge ratio drift (lower is better)
        - Time since discovery (longer = more validated)
        
        Args:
            pair_key: Pair to score
            
        Returns:
            Stability score 0-1
        """
        if pair_key not in self.tracked_pairs:
            return 0.0
        
        metadata = self.tracked_pairs[pair_key]
        
        if not metadata.is_valid:
            return 0.0
        
        # P-value component (0.4 weight)
        p_val_score = 1.0 - min(metadata.current_p_value or metadata.discovery_p_value, 0.05) / 0.05
        p_val_component = p_val_score * 0.4
        
        # Drift component (0.3 weight)
        drift = metadata.hedge_ratio_drift or 0.0
        drift_score = 1.0 - min(drift, self.hedge_ratio_drift_threshold) / max(self.hedge_ratio_drift_threshold, 0.01)
        drift_component = drift_score * 0.3
        
        # Age component (0.3 weight) - older validated pairs are more trusted
        age_days = (datetime.now() - metadata.discovery_date).days
        age_score = min(age_days / 252, 1.0)  # Maxes at 1 year
        age_component = age_score * 0.3
        
        total_score = p_val_component + drift_component + age_component
        return max(0.0, min(1.0, total_score))
    
    def validate_all_pairs(self) -> Dict[str, bool]:
        """
        Validate all tracked pairs (check age, stability, etc.).
        
        Returns:
            Dict of pair_key -> is_valid
        """
        validation_results = {}
        
        for pair_key, metadata in self.tracked_pairs.items():
            age_days = (datetime.now() - metadata.discovery_date).days
            
            # Fresh pair (< min age): keep if cointegrated
            if age_days < self.min_pair_age_days:
                is_valid = metadata.is_valid and metadata.current_p_value < self.cointegration_threshold
            else:
                # Mature pair: must maintain cointegration and not degrade too much
                is_valid = (
                    metadata.is_valid and
                    metadata.current_p_value < self.cointegration_threshold and
                    (metadata.hedge_ratio_drift or 0.0) < self.hedge_ratio_drift_threshold * 2  # 2x threshold for mature
                )
            
            validation_results[pair_key] = is_valid
            
            if not is_valid and metadata.is_valid:
                # Just became invalid
                metadata.is_valid = False
                logger.warning("pair_invalidated", pair=pair_key, age_days=age_days)
        
        return validation_results
    
    def schedule_retraining_check(self) -> bool:
        """
        Check if retraining is due based on schedule.
        
        Returns:
            True if retraining should be performed now
        """
        if self.last_retraining_date is None:
            return True
        
        days_since = (datetime.now() - self.last_retraining_date).days
        return days_since >= self.reestimation_frequency_days
    
    def generate_retraining_report(
        self,
        new_pairs: List[Tuple[str, float, float]] = None,
        reestimated_pairs: Dict[str, Tuple[float, float]] = None
    ) -> RetrainingReport:
        """
        Generate comprehensive retraining report.
        
        Args:
            new_pairs: Newly discovered pairs from discovery run
            reestimated_pairs: Re-estimated pairs from reestimation run
            
        Returns:
            RetrainingReport with full summary
        """
        new_pairs = new_pairs or []
        reestimated_pairs = reestimated_pairs or {}
        
        # Count valid vs invalid
        valid_count = sum(1 for m in self.tracked_pairs.values() if m.is_valid)
        invalid_count = len(self.tracked_pairs) - valid_count
        
        # Identify drifting pairs
        drifting = []
        for pair_key, metadata in self.tracked_pairs.items():
            if metadata.is_valid and (metadata.hedge_ratio_drift or 0.0) >= self.hedge_ratio_drift_threshold:
                drifting.append((pair_key, metadata.hedge_ratio_drift * 100))
        
        # Calculate average metrics
        if self.tracked_pairs:
            avg_drift = np.mean([(m.hedge_ratio_drift or 0.0) for m in self.tracked_pairs.values()])
            avg_p_value = np.mean([(m.current_p_value or m.discovery_p_value) for m in self.tracked_pairs.values()])
        else:
            avg_drift = 0.0
            avg_p_value = 1.0
        
        # Build report
        report = RetrainingReport(
            retraining_date=datetime.now(),
            discovery_lookback_days=self.discovery_lookback_days,
            pairs_total=len(self.tracked_pairs),
            pairs_valid=valid_count,
            pairs_degraded=invalid_count,
            pairs_newly_discovered=len(new_pairs),
            pairs_stable=sum(1 for m in self.tracked_pairs.values() if m.is_valid and (m.hedge_ratio_drift or 0.0) < self.hedge_ratio_drift_threshold),
            pairs_drifting=len(drifting),
            avg_hedge_ratio_drift=avg_drift,
            avg_p_value=avg_p_value,
            new_pairs=[pair[0] for pair in new_pairs],
            invalidated_pairs=[pair_key for pair_key, m in self.tracked_pairs.items() if not m.is_valid],
            drifting_pairs=drifting
        )
        
        # Build summary
        report.summary = (
            f"Retraining Report {report.retraining_date.strftime('%Y-%m-%d %H:%M')}\n"
            f"ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ\n"
            f"Total Pairs: {report.pairs_total} (Valid: {report.pairs_valid}, Degraded: {report.pairs_degraded})\n"
            f"New Discoveries: {report.pairs_newly_discovered}\n"
            f"Stable (drift < {self.hedge_ratio_drift_threshold * 100:.0f}%): {report.pairs_stable}\n"
            f"Drifting (drift >= {self.hedge_ratio_drift_threshold * 100:.0f}%): {report.pairs_drifting}\n"
            f"Avg Hedge Ratio Drift: {report.avg_hedge_ratio_drift * 100:.2f}%\n"
            f"Avg Cointegration P-value: {report.avg_p_value:.4f}\n"
        )
        
        self.retraining_history.append(report)
        self.last_retraining_date = datetime.now()
        
        return report
    
    def reset_all(self):
        """Reset all tracking data."""
        self.tracked_pairs.clear()
        self.retraining_history.clear()
        self.last_retraining_date = None
        logger.info("model_retraining_manager_reset")


__all__ = [
    "PairDiscoveryMetadata",
    "RetrainingReport",
    "ModelRetrainingManager"
]
