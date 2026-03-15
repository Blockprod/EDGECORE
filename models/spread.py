from typing import Optional

import numpy as np
import pandas as pd
from structlog import get_logger

from models.half_life_estimator import SpreadHalfLifeEstimator

# Module-level Cython import ÔÇö avoids per-call dict lookup in hot path
try:
    from models.cointegration_fast import half_life_fast as _half_life_fast_cython
    _HALF_LIFE_CYTHON = True
except ImportError:
    _HALF_LIFE_CYTHON = False

logger = get_logger(__name__)

class SpreadModel:
    """Linear spread model for pair trading with hedge ratio tracking."""
    
    def __init__(
        self, 
        y: pd.Series, 
        x: pd.Series, 
        pair_key: str = None,
        hedge_ratio_tracker = None,
        eg_beta_raw: float = None,
    ):
        """
        Initialize spread model via OLS regression: y = alpha + beta * x + residuals
        
        Args:
            y: Dependent series (typically first asset price)
            x: Independent series (typically second asset price)
            pair_key: Identifier for tracking (e.g., "AAPL_MSFT")
            hedge_ratio_tracker: Optional HedgeRatioTracker instance for ╬▓ monitoring
            eg_beta_raw: Optional ╬▓ from the Engle-Granger test (de-normalised).
                If provided, a consistency check is performed against the
                OLS-on-raw-prices ╬▓.  Large divergences are logged as warnings.
        """
        X = np.column_stack([np.ones(len(x)), x.values])
        beta = np.linalg.lstsq(X, y.values, rcond=None)[0]
        
        self.intercept = beta[0]
        self.beta = beta[1]

        # C-03: verify EG ╬▓ vs SpreadModel ╬▓ consistency when available
        if eg_beta_raw is not None and abs(self.beta) > 1e-12:
            rel_diff = abs(self.beta - eg_beta_raw) / abs(self.beta)
            if rel_diff > 0.05:  # >5% divergence
                logger.warning(
                    "beta_divergence_eg_vs_spread",
                    pair=pair_key,
                    eg_beta_raw=round(eg_beta_raw, 6),
                    spread_beta=round(self.beta, 6),
                    relative_diff_pct=round(rel_diff * 100, 2),
                )
        self.y = y
        self.x = x
        self.pair_key = pair_key
        self.tracker = hedge_ratio_tracker
        self.is_deprecated = False
        self.residuals = y.values - X @ beta
        self.std_residuals = np.std(self.residuals)
        
        # Estimate half-life of spread mean reversion
        self.half_life = self._estimate_half_life(y, x)
        
        # Record initial ╬▓ if tracker is provided
        if self.tracker is not None and self.pair_key is not None:
            self.tracker.record_initial_beta(self.pair_key, self.beta)
    
    def _estimate_half_life(self, y: pd.Series, x: pd.Series) -> Optional[float]:
        """
        Estimate half-life of the spread using AR(1) model.

        Uses the Cython ``half_life_fast`` kernel when available (pure C AR(1),
        ~10├ù faster), falling back to ``SpreadHalfLifeEstimator`` when not.

        Args:
            y: Dependent series
            x: Independent series

        Returns:
            Half-life in days, or None if not mean-reverting
        """
        try:
            # self.residuals IS the spread (y - intercept - beta*x), already
            # computed in __init__ ÔÇö no need to call compute_spread() again.
            res = self.residuals.astype(np.float64)

            # ÔöÇÔöÇ Cython fast path ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
            if _HALF_LIFE_CYTHON:
                hl_int = _half_life_fast_cython(res)
                if 5 <= hl_int <= 200:
                    logger.debug("half_life_estimated", pair=self.pair_key, half_life=hl_int)
                    return float(hl_int)

            # ÔöÇÔöÇ Pure-Python fallback ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
            spread = pd.Series(res, index=y.index)
            estimator = SpreadHalfLifeEstimator(lookback=min(252, len(spread)))
            hl = estimator.estimate_half_life_from_spread(spread, validate=True)
            if hl is not None:
                logger.debug("half_life_estimated", pair=self.pair_key, half_life=hl)
            return hl
        except Exception as e:
            logger.debug(
                "half_life_estimation_failed",
                pair=self.pair_key,
                error=str(e)
            )
            return None
    
    def compute_spread(self, y: pd.Series, x: pd.Series) -> pd.Series:
        """
        Compute spread as: spread = y - (intercept + beta * x)
        
        Args:
            y: Dependent series
            x: Independent series
        
        Returns:
            Spread series
        """
        return y - (self.intercept + self.beta * x)
    
    def reestimate_beta_if_needed(self, y: pd.Series, x: pd.Series, bar_time=None) -> bool:
        """
        Reestimate ╬▓ if enough time has passed, using recent data.
        
        Checks with tracker if reestimation is needed, and updates the model
        if so. Returns whether the pair is still stable.
        
        Args:
            y: Recent dependent series
            x: Recent independent series
            bar_time: Timestamp of the current bar (optional, passed to tracker)
        
        Returns:
            is_stable: Whether the relationship remains stable
        """
        if self.tracker is None or self.pair_key is None:
            # No tracking, model stays as-is
            return True
        
        # Reestimate ╬▓ from recent data
        X = np.column_stack([np.ones(len(x)), x.values])
        try:
            beta_coef = np.linalg.lstsq(X, y.values, rcond=None)[0]
            new_beta = beta_coef[1]
        except Exception as e:
            logger.warning(
                "beta_reestimation_failed",
                pair=self.pair_key,
                error=str(e)
            )
            return True  # Assume stable if reestimation fails
        
        # Check with tracker if this represents a drift
        current_beta, is_stable = self.tracker.reestimate_if_needed(
            self.pair_key,
            new_beta,
            drift_tolerance_pct=10.0,
            bar_time=bar_time,
        )
        
        # Update model if reestimation occurred
        if current_beta is not None and not self.is_deprecated:
            self.beta = current_beta
            self.intercept = beta_coef[0]
            self.residuals = y.values - X @ beta_coef
            self.std_residuals = np.std(self.residuals)
        
        # Mark as deprecated if unstable
        if not is_stable:
            self.is_deprecated = True
            logger.warning(
                "spread_model_deprecated",
                pair=self.pair_key,
                reason="Hedge ratio instability"
            )
        
        return is_stable
    
    def compute_z_score(
        self, 
        spread: pd.Series, 
        lookback: int = None,
        half_life: float = None
    ) -> pd.Series:
        """
        Compute rolling Z-score of spread with optional adaptive lookback.
        
        If half_life is provided (or estimated from model), lookback window adapts:
        - Fast mean reversion (HL < 30d): lookback = 3 * HL (smooth short-term noise)
        - Normal (30-60d): lookback = HL (capture full cycle)
        - Slow reversion (HL > 60d): lookback = 60 (use max historical window)
        
        This ensures Z-score captures the right frequency of mean reversion.
        
        Args:
            spread: Spread series
            lookback: Explicit rolling window size (overrides half_life logic if provided)
            half_life: Half-life in days (used to infer optimal lookback). If None, uses self.half_life
        
        Returns:
            Z-score series
        """
        # Determine lookback window
        if lookback is None:
            # Use provided half_life, or fall back to estimated half_life
            hl = half_life if half_life is not None else self.half_life
            
            if hl is not None:
                # Smooth adaptive lookback (no discontinuity):
                # Multiplier linearly interpolates from 3.0 at HLÔëñ10
                # down to 1.0 at HLÔëÑ60, capped at 60 for HL>60.
                if hl <= 10:
                    multiplier = 3.0
                elif hl >= 60:
                    multiplier = 1.0
                else:
                    # Linear interpolation: 3.0 at HL=10 -> 1.0 at HL=60
                    multiplier = 3.0 - 2.0 * (hl - 10) / (60 - 10)
                lookback = int(np.ceil(multiplier * hl))
                # Cap at 60 for very slow reversion
                lookback = min(lookback, 60)
            else:
                # Default fallback (no half-life available)
                lookback = 20
        
        # Enforce bounds: [10, 120]
        lookback = max(10, min(lookback, 120))
        
        rolling_mean = spread.rolling(window=lookback).mean()
        rolling_std = spread.rolling(window=lookback).std()
        z_score = (spread - rolling_mean) / (rolling_std + 1e-8)
        # Sprint 2.8 (M-08): Clamp Z-score to [-6, +6]
        z_score = z_score.clip(-6.0, 6.0)
        return z_score
    
    def get_model_info(self) -> dict:
        """Return model parameters for inspection."""
        return {
            'intercept': self.intercept,
            'beta': self.beta,
            'residual_std': self.std_residuals,
            'residual_mean': np.mean(self.residuals),
            'half_life': self.half_life,
            'is_deprecated': self.is_deprecated
        }

    def update(self, y: pd.Series, x: pd.Series) -> None:
        """Re-fit the model with new price data *in place*.

        This preserves the object identity (and any attached
        HedgeRatioTracker state) while refreshing the OLS estimate,
        residuals, and half-life.
        """
        X = np.column_stack([np.ones(len(x)), x.values])
        try:
            beta_coef = np.linalg.lstsq(X, y.values, rcond=None)[0]
        except Exception as exc:
            logger.warning(
                "spread_model_update_failed",
                pair=self.pair_key,
                error=str(exc),
            )
            return

        self.intercept = beta_coef[0]
        self.beta = beta_coef[1]
        self.y = y
        self.x = x
        self.residuals = y.values - X @ beta_coef
        self.std_residuals = np.std(self.residuals)
        self.half_life = self._estimate_half_life(y, x)
