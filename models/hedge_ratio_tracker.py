"""
Dynamic hedge ratio reestimation tracking.

Monitors ╬▓ (hedge ratio) stability over time and flags pairs when ╬▓ drifts
significantly, indicating the cointegration relationship has degraded.

Key Concept:
- Initial ╬▓ estimated once during pair discovery
- Monthly reestimation checks if ╬▓ has stayed stable
- If ╬▓ drifts > 10%, pair is flagged as unstable/deprecated
- This prevents trading pairs with broken relationships
"""

import numpy as np
from datetime import datetime
from structlog import get_logger
from typing import Dict, Tuple, Optional, List

logger = get_logger(__name__)


class HedgeRatioTracker:
    """
    Track hedge ratio (╬▓) stability over time for each pair.
    
    Purpose:
    - Monitor ╬▓ changes at configurable frequency (default 7 days)
    - Emergency reestimation when spread volatility exceeds 3¤â
    - Flag pairs when ╬▓ drifts > 10% (indicating relationship breakdown)
    - Prevent trading degraded pairs
    - Log all changes for monitoring
    """
    
    def __init__(
        self,
        reestimation_frequency_days: int = 7,
        emergency_vol_sigma: float = 3.0
    ):
        """
        Initialize hedge ratio tracker.
        
        Args:
            reestimation_frequency_days: Check for reestimation every N days (default 7)
            emergency_vol_sigma: Trigger emergency reestimation if spread vol > N sigma (default 3.0)
        """
        self.reestimation_frequency_days = reestimation_frequency_days
        self.emergency_vol_sigma = emergency_vol_sigma
        
        # Track ╬▓ estimates: {pair_key: [(timestamp, beta, is_stable)]}
        self.pair_betas: Dict[str, List[Tuple]] = {}
        
        # Track deprecations: {pair_key: reason}
        self.deprecated_pairs: Dict[str, str] = {}
        
        # Emergency reestimation counters
        self.emergency_reestimation_count: int = 0
        
        logger.info(
            "hedge_ratio_tracker_initialized",
            reestimation_frequency_days=reestimation_frequency_days,
            emergency_vol_sigma=emergency_vol_sigma
        )
    
    def record_initial_beta(self, pair_key: str, beta: float, bar_time: Optional[datetime] = None) -> None:
        """
        Record initial ╬▓ estimate for a pair.  Idempotent: if pair already
        has a recorded ╬▓ history, this is a no-op so that per-bar model
        reconstruction does not pollute the tracker.
        
        Args:
            pair_key: Pair identifier (e.g., "AAPL_MSFT")
            beta: Initial hedge ratio
            bar_time: Timestamp of the current bar (uses datetime.now() if None, for live trading)
        """
        if pair_key not in self.pair_betas:
            self.pair_betas[pair_key] = []
        
        # Only record if this pair has no history yet (idempotent guard).
        # DynamicSpreadModel is reconstructed every bar ÔÇô without this guard
        # the tracker would see every bar as a fresh "initialisation".
        if len(self.pair_betas[pair_key]) > 0:
            return
        
        ts = bar_time if bar_time is not None else datetime.now()
        self.pair_betas[pair_key].append((
            ts,
            beta,
            True,  # Initial estimate is assumed stable
            None   # No drift for initial
        ))
        
        logger.info(
            "hedge_ratio_recorded_initial",
            pair=pair_key,
            beta=round(beta, 4)
        )
    
    def reestimate_if_needed(
        self,
        pair_key: str,
        new_beta: float,
        drift_tolerance_pct: float = 10.0,
        bar_time: Optional[datetime] = None
    ) -> Tuple[float, bool]:
        """
        Check if ╬▓ needs reestimation and handle if it does.
        
        Args:
            pair_key: Pair identifier
            new_beta: Newly computed ╬▓ from recent data
            drift_tolerance_pct: Maximum allowed drift before flagging (default: 10%)
            bar_time: Timestamp of the current bar (uses datetime.now() if None, for live trading)
        
        Returns:
            Tuple of (beta_to_use, is_stable)
            - beta_to_use: The ╬▓ to use for spread calculation
            - is_stable: Whether the relationship is still stable
        """
        # If pair is deprecated, don't reestimate
        if pair_key in self.deprecated_pairs:
            reason = self.deprecated_pairs[pair_key]
            logger.debug(
                "pair_skipped_deprecated",
                pair=pair_key,
                reason=reason
            )
            return None, False
        
        ts = bar_time if bar_time is not None else datetime.now()
        
        # If pair not yet tracked, initialize it
        if pair_key not in self.pair_betas:
            self.record_initial_beta(pair_key, new_beta, bar_time=ts)
            return new_beta, True
        
        # Get last recorded ╬▓
        last_record = self.pair_betas[pair_key][-1]
        last_datetime, last_beta, last_is_stable, last_drift = last_record
        
        # Check if enough time has passed for reestimation
        # Uses bar_time (not wall-clock) so backtest respects simulated dates
        days_elapsed = (ts - last_datetime).days
        
        if days_elapsed < self.reestimation_frequency_days:
            # Too soon to reestimate
            return last_beta, last_is_stable
        
        # Calculate drift
        drift_pct = abs(new_beta - last_beta) / abs(last_beta) * 100
        
        # Determine stability
        is_stable = drift_pct <= drift_tolerance_pct
        
        # Record new estimate
        self.pair_betas[pair_key].append((
            ts,
            new_beta,
            is_stable,
            drift_pct
        ))
        
        # Log the reestimation
        logger.info(
            "hedge_ratio_reestimated",
            pair=pair_key,
            old_beta=round(last_beta, 4),
            new_beta=round(new_beta, 4),
            drift_pct=round(drift_pct, 2),
            days_since_last=days_elapsed,
            is_stable=is_stable
        )
        
        # If drift exceeds tolerance, deprecate the pair
        if not is_stable:
            deprecation_reason = (
                f"Hedge ratio drift {drift_pct:.1f}% exceeds tolerance "
                f"({drift_tolerance_pct}%)"
            )
            self.deprecated_pairs[pair_key] = deprecation_reason
            
            logger.warning(
                "hedge_ratio_unstable_pair_deprecated",
                pair=pair_key,
                drift_pct=round(drift_pct, 2),
                tolerance_pct=drift_tolerance_pct,
                reason=deprecation_reason,
                action="STOP_TRADING"
            )
        
        return new_beta, is_stable
    
    def emergency_reestimate(
        self,
        pair_key: str,
        new_beta: float,
        spread_vol: float,
        spread_vol_mean: float,
        spread_vol_std: float,
        drift_tolerance_pct: float = 10.0,
        bar_time: Optional[datetime] = None
    ) -> Tuple[float, bool, bool]:
        """
        Emergency reestimation if spread volatility exceeds threshold (3¤â).
        
        Bypasses the time-based check and immediately reestimates ╬▓ when
        spread volatility spikes above emergency_vol_sigma ├ù ¤â.
        
        Args:
            pair_key: Pair identifier
            new_beta: Newly computed ╬▓ from recent data
            spread_vol: Current spread volatility
            spread_vol_mean: Mean of historical spread volatility
            spread_vol_std: Std of historical spread volatility
            drift_tolerance_pct: Maximum allowed drift before flagging (default 10%)
            bar_time: Timestamp of the current bar (uses datetime.now() if None, for live trading)
            
        Returns:
            Tuple of (beta_to_use, is_stable, emergency_triggered)
        """
        # Check if emergency threshold is breached
        if spread_vol_std < 1e-10:
            return None, True, False
            
        vol_z = (spread_vol - spread_vol_mean) / spread_vol_std
        
        if vol_z <= self.emergency_vol_sigma:
            # No emergency ÔÇô use normal path
            return None, True, False
        
        # Emergency triggered ÔÇô force reestimation regardless of time
        self.emergency_reestimation_count += 1
        
        ts = bar_time if bar_time is not None else datetime.now()
        
        # If pair not yet tracked, initialize
        if pair_key not in self.pair_betas or not self.pair_betas[pair_key]:
            self.record_initial_beta(pair_key, new_beta, bar_time=ts)
            logger.warning(
                "emergency_reestimate_new_pair",
                pair=pair_key,
                vol_z=round(vol_z, 2),
                threshold=self.emergency_vol_sigma,
                count=self.emergency_reestimation_count
            )
            return new_beta, True, True
        
        # Get last ╬▓
        last_record = self.pair_betas[pair_key][-1]
        _, last_beta, _, _ = last_record
        
        # Calculate drift
        drift_pct = abs(new_beta - last_beta) / abs(last_beta) * 100 if abs(last_beta) > 1e-10 else 0.0
        is_stable = drift_pct <= drift_tolerance_pct
        
        # Record emergency reestimation
        self.pair_betas[pair_key].append((
            ts,
            new_beta,
            is_stable,
            drift_pct
        ))
        
        logger.warning(
            "emergency_reestimate_triggered",
            pair=pair_key,
            vol_z=round(vol_z, 2),
            threshold=self.emergency_vol_sigma,
            old_beta=round(last_beta, 4),
            new_beta=round(new_beta, 4),
            drift_pct=round(drift_pct, 2),
            is_stable=is_stable,
            count=self.emergency_reestimation_count
        )
        
        # Deprecate if unstable
        if not is_stable:
            deprecation_reason = (
                f"Emergency reestimate: drift {drift_pct:.1f}% exceeds tolerance "
                f"({drift_tolerance_pct}%) after vol spike ({vol_z:.1f}¤â)"
            )
            self.deprecated_pairs[pair_key] = deprecation_reason
            
            logger.warning(
                "emergency_reestimate_pair_deprecated",
                pair=pair_key,
                reason=deprecation_reason,
                action="STOP_TRADING"
            )
        
        return new_beta, is_stable, True
    
    def is_pair_deprecated(self, pair_key: str) -> bool:
        """Check if a pair has been deprecated due to ╬▓ instability."""
        return pair_key in self.deprecated_pairs
    
    def get_deprecation_reason(self, pair_key: str) -> Optional[str]:
        """Get reason why a pair was deprecated, if applicable."""
        return self.deprecated_pairs.get(pair_key)
    
    def get_pair_history(self, pair_key: str) -> List[Dict]:
        """
        Get full ╬▓ history for a pair.
        
        Returns:
            List of dicts with timestamp, beta, is_stable, drift_pct
        """
        if pair_key not in self.pair_betas:
            return []
        
        return [
            {
                'timestamp': record[0],
                'beta': record[1],
                'is_stable': record[2],
                'drift_pct': record[3]
            }
            for record in self.pair_betas[pair_key]
        ]
    
    def get_summary(self) -> Dict:
        """Get summary statistics of tracked pairs."""
        total_pairs = len(self.pair_betas)
        deprecated_count = len(self.deprecated_pairs)
        active_count = total_pairs - deprecated_count
        
        # Calculate average drift for active pairs
        active_drifts = []
        for pair_key, records in self.pair_betas.items():
            if not self.is_pair_deprecated(pair_key):
                drifts = [r[3] for r in records if r[3] is not None]
                if drifts:
                    active_drifts.extend(drifts)
        
        avg_drift = np.mean(active_drifts) if active_drifts else 0.0
        max_drift = np.max(active_drifts) if active_drifts else 0.0
        
        return {
            'total_pairs_tracked': total_pairs,
            'active_pairs': active_count,
            'deprecated_pairs': deprecated_count,
            'average_drift_active_pct': round(avg_drift, 2),
            'max_drift_active_pct': round(max_drift, 2),
            'deprecated_pair_keys': list(self.deprecated_pairs.keys())
        }
    
    def reset_pair(self, pair_key: str) -> None:
        """
        Reset a pair's history (use with caution).
        
        Args:
            pair_key: Pair to reset
        """
        if pair_key in self.deprecated_pairs:
            del self.deprecated_pairs[pair_key]
        
        if pair_key in self.pair_betas:
            # Keep only the initial estimate
            if self.pair_betas[pair_key]:
                initial = self.pair_betas[pair_key][0]
                self.pair_betas[pair_key] = [initial]
        
        logger.info("hedge_ratio_pair_reset", pair=pair_key)
    
    def reset_all(self) -> None:
        """Reset all tracking (start fresh)."""
        self.pair_betas.clear()
        self.deprecated_pairs.clear()
        logger.info("hedge_ratio_tracker_reset_all")
