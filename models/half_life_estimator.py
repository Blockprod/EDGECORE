<<<<<<< HEAD
﻿"""
=======
"""
>>>>>>> origin/main
Half-Life Estimation Module (S3.2b - Refinement).

Improved half-life estimation from spread directly (not residuals).
Validates OU process mean-reversion assumptions.
"""

<<<<<<< HEAD
import logging

import numpy as np
import pandas as pd
=======
import numpy as np
import pandas as pd
from typing import Optional
import logging
>>>>>>> origin/main

logger = logging.getLogger(__name__)


class SpreadHalfLifeEstimator:
    """Estimate half-life from spread mean reversion."""
<<<<<<< HEAD

    def __init__(self, lookback: int = 252):
        """
        Initialize estimator.

=======
    
    def __init__(self, lookback: int = 252):
        """
        Initialize estimator.
        
>>>>>>> origin/main
        Args:
            lookback: Historical window for AR(1) estimation
        """
        self.lookback = lookback
<<<<<<< HEAD

    def estimate_half_life_from_spread(self, spread: pd.Series, validate: bool = True) -> float | None:
        """
        Estimate half-life of spread mean reversion.

        Uses AR(1) model on the spread directly:
        spread_t = ╬╝ + ¤ü * (spread_{t-1} - ╬╝) + ╬Á_t

        If ¤ü < 1: spread is mean-reverting
        Half-life = -ln(2) / ln(¤ü)

        Args:
            spread: Price spread series
            validate: Whether to validate bounds

=======
    
    def estimate_half_life_from_spread(
        self, 
        spread: pd.Series,
        validate: bool = True
    ) -> Optional[float]:
        """
        Estimate half-life of spread mean reversion.
        
        Uses AR(1) model on the spread directly:
        spread_t = μ + ρ * (spread_{t-1} - μ) + ε_t
        
        If ρ < 1: spread is mean-reverting
        Half-life = -ln(2) / ln(ρ)
        
        Args:
            spread: Price spread series
            validate: Whether to validate bounds
            
>>>>>>> origin/main
        Returns:
            Half-life in days, or None if not mean-reverting
        """
        if isinstance(spread, np.ndarray):
            spread = pd.Series(spread)
<<<<<<< HEAD

        # Use recent window for stability
        if len(spread) < self.lookback:
            return None

        data = spread.iloc[-self.lookback :].copy()

=======
        
        # Use recent window for stability
        if len(spread) < self.lookback:
            return None
        
        data = spread.iloc[-self.lookback:].copy()
        
>>>>>>> origin/main
        # STAT-4: Use exponentially-weighted mean to avoid look-ahead bias.
        # The full-window arithmetic mean includes future data relative to
        # earlier observations in the window.  An EWM with span ~ 2/3 of
        # lookback centres the spread causally while remaining smooth enough
        # for reliable AR(1) estimation.
        ewm_span = max(int(self.lookback * 2 / 3), 20)
        ewm_mean = data.ewm(span=ewm_span).mean()
        data_centered = data - ewm_mean
<<<<<<< HEAD

        # AR(1) regression: X_t = ¤ü * X_{t-1}
        # Align X (lagged) and y on the same index (drop first row).
        lag = data_centered.shift(1)
        mask = lag.notna()
        X = np.asarray(lag[mask], dtype=float).reshape(-1, 1)
        y = np.asarray(data_centered[mask], dtype=float)

        if len(X) < 10:
            return None

        try:
            # OLS: y = ¤ü * X (no intercept)
            rho = np.linalg.lstsq(X, y, rcond=None)[0][0]

            if np.isnan(rho) or np.isinf(rho):
                return None

            # Check mean-reversion condition
            if rho >= 1.0 or rho <= 0.0:
                return None  # Not mean-reverting

            # Calculate half-life
            half_life = -np.log(2) / np.log(rho)

            if np.isnan(half_life) or np.isinf(half_life):
                return None

            # Validation: HL should be in reasonable range
            if validate:
                if half_life < 5 or half_life > 200:
                    logger.debug(f"half_life_out_of_bounds: half_life={half_life}, rho={rho}")
                    return None

            return half_life

        except Exception as e:
            logger.debug(f"half_life_estimation_error: {e}")
            return None

    def estimate_half_life_from_spread_array(self, spread: np.ndarray, validate: bool = True) -> float | None:
        """Convenience method for numpy arrays."""
        return self.estimate_half_life_from_spread(pd.Series(spread), validate=validate)

    def compute_ou_process_parameters(self, spread: pd.Series) -> dict:
        """
        Compute full OU process parameters.

        Returns dict with:
        - half_life: Mean reversion half-life
        - ar1_coeff: AR(1) coefficient ¤ü
        - mean_reversion_speed: ╬╗ = -ln(¤ü)
=======
        
        # AR(1) regression: X_t = ρ * X_{t-1}
        # Align X (lagged) and y on the same index (drop first row).
        lag = data_centered.shift(1)
        mask = lag.notna()
        X = lag[mask].values.reshape(-1, 1)
        y = data_centered[mask].values
        
        if len(X) < 10:
            return None
        
        try:
            # OLS: y = ρ * X (no intercept)
            rho = np.linalg.lstsq(X, y, rcond=None)[0][0]
            
            if np.isnan(rho) or np.isinf(rho):
                return None
            
            # Check mean-reversion condition
            if rho >= 1.0 or rho <= 0.0:
                return None  # Not mean-reverting
            
            # Calculate half-life
            half_life = -np.log(2) / np.log(rho)
            
            if np.isnan(half_life) or np.isinf(half_life):
                return None
            
            # Validation: HL should be in reasonable range
            if validate:
                if half_life < 5 or half_life > 200:
                    logger.debug(
                        "half_life_out_of_bounds",
                        half_life=half_life,
                        rho=rho
                    )
                    return None
            
            return half_life
        
        except Exception as e:
            logger.debug(f"half_life_estimation_error: {e}")
            return None
    
    def estimate_half_life_from_spread_array(
        self,
        spread: np.ndarray,
        validate: bool = True
    ) -> Optional[float]:
        """Convenience method for numpy arrays."""
        return self.estimate_half_life_from_spread(
            pd.Series(spread),
            validate=validate
        )
    
    def compute_ou_process_parameters(
        self,
        spread: pd.Series
    ) -> dict:
        """
        Compute full OU process parameters.
        
        Returns dict with:
        - half_life: Mean reversion half-life
        - ar1_coeff: AR(1) coefficient ρ
        - mean_reversion_speed: λ = -ln(ρ)
>>>>>>> origin/main
        - half_life_days: Half-life in trading days
        """
        if isinstance(spread, np.ndarray):
            spread = pd.Series(spread)
<<<<<<< HEAD

        if len(spread) < self.lookback:
            return {"half_life": None, "ar1_coeff": None, "mean_reversion_speed": None, "half_life_days": None}

        data = spread.iloc[-self.lookback :].copy()
        data_centered = data - data.mean()

        lag = data_centered.shift(1)
        mask = lag.notna()
        X = np.asarray(lag[mask], dtype=float).reshape(-1, 1)
        y = np.asarray(data_centered[mask], dtype=float)

        try:
            rho = np.linalg.lstsq(X, y, rcond=None)[0][0]

            if rho >= 1.0 or rho <= 0.0 or np.isnan(rho):
                return {"half_life": None, "ar1_coeff": rho, "mean_reversion_speed": None, "half_life_days": None}

            mean_reversion_speed = -np.log(rho)
            half_life = -np.log(2) / np.log(rho)

            return {
                "half_life": half_life,
                "ar1_coeff": rho,
                "mean_reversion_speed": mean_reversion_speed,
                "half_life_days": int(np.round(half_life)),
            }
        except Exception as exc:
            logger.warning(f"compute_ou_process_parameters_failed: {exc}")
            return {"half_life": None, "ar1_coeff": None, "mean_reversion_speed": None, "half_life_days": None}

    def validate_mean_reversion(self, spread: pd.Series, threshold_rho: float = 0.98) -> bool:
        """
        Check if spread exhibits mean-reversion.

        Args:
            spread: Price spread
            threshold_rho: AR(1) coefficient must be < threshold

=======
        
        if len(spread) < self.lookback:
            return {
                'half_life': None,
                'ar1_coeff': None,
                'mean_reversion_speed': None,
                'half_life_days': None
            }
        
        data = spread.iloc[-self.lookback:].copy()
        data_centered = data - data.mean()
        
        lag = data_centered.shift(1)
        mask = lag.notna()
        X = lag[mask].values.reshape(-1, 1)
        y = data_centered[mask].values
        
        try:
            rho = np.linalg.lstsq(X, y, rcond=None)[0][0]
            
            if rho >= 1.0 or rho <= 0.0 or np.isnan(rho):
                return {
                    'half_life': None,
                    'ar1_coeff': rho,
                    'mean_reversion_speed': None,
                    'half_life_days': None
                }
            
            mean_reversion_speed = -np.log(rho)
            half_life = -np.log(2) / np.log(rho)
            
            return {
                'half_life': half_life,
                'ar1_coeff': rho,
                'mean_reversion_speed': mean_reversion_speed,
                'half_life_days': int(np.round(half_life))
            }
        except:
            return {
                'half_life': None,
                'ar1_coeff': None,
                'mean_reversion_speed': None,
                'half_life_days': None
            }
    
    def validate_mean_reversion(
        self,
        spread: pd.Series,
        threshold_rho: float = 0.98
    ) -> bool:
        """
        Check if spread exhibits mean-reversion.
        
        Args:
            spread: Price spread
            threshold_rho: AR(1) coefficient must be < threshold
            
>>>>>>> origin/main
        Returns:
            True if mean-reverting, False otherwise
        """
        if isinstance(spread, np.ndarray):
            spread = pd.Series(spread)
<<<<<<< HEAD

        if len(spread) < self.lookback:
            return False

        data = spread.iloc[-self.lookback :].copy()
        data_centered = data - data.mean()

        lag = data_centered.shift(1)
        mask = lag.notna()
        X = np.asarray(lag[mask], dtype=float).reshape(-1, 1)
        y = np.asarray(data_centered[mask], dtype=float)

        try:
            rho = np.linalg.lstsq(X, y, rcond=None)[0][0]

            # Mean-reverting if 0 < ¤ü < threshold
            return 0 < rho < threshold_rho
        except Exception as exc:
            logger.warning(f"validate_mean_reversion_failed: {exc}")
=======
        
        if len(spread) < self.lookback:
            return False
        
        data = spread.iloc[-self.lookback:].copy()
        data_centered = data - data.mean()
        
        lag = data_centered.shift(1)
        mask = lag.notna()
        X = lag[mask].values.reshape(-1, 1)
        y = data_centered[mask].values
        
        try:
            rho = np.linalg.lstsq(X, y, rcond=None)[0][0]
            
            # Mean-reverting if 0 < ρ < threshold
            return 0 < rho < threshold_rho
        except:
>>>>>>> origin/main
            return False


# Global estimator instance
_estimator = SpreadHalfLifeEstimator()


<<<<<<< HEAD
def estimate_half_life(spread: pd.Series, lookback: int = 252, validate: bool = True) -> float | None:
    """
    Convenience function for half-life estimation.

=======
def estimate_half_life(
    spread: pd.Series,
    lookback: int = 252,
    validate: bool = True
) -> Optional[float]:
    """
    Convenience function for half-life estimation.
    
>>>>>>> origin/main
    Args:
        spread: Price spread series
        lookback: Historical window (days)
        validate: Whether to validate bounds
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
    Returns:
        Half-life in days, or None
    """
    estimator = SpreadHalfLifeEstimator(lookback=lookback)
    return estimator.estimate_half_life_from_spread(spread, validate=validate)


<<<<<<< HEAD
if __name__ == "__main__":
    # Test with synthetic data
    np.random.seed(42)

=======
if __name__ == '__main__':
    # Test with synthetic data
    np.random.seed(42)
    
>>>>>>> origin/main
    # OU process with HL=30
    mean_reversion = np.log(2) / 30
    ou = np.zeros(500)
    ou[0] = np.random.normal(0, 1)
<<<<<<< HEAD

    for t in range(1, 500):
        ou[t] = ou[t - 1] - mean_reversion * ou[t - 1] + np.random.normal(0, 0.1)

    spread = pd.Series(ou)
    estimator = SpreadHalfLifeEstimator()

    hl = estimator.estimate_half_life_from_spread(spread)
    params = estimator.compute_ou_process_parameters(spread)

    hl_str = f"{hl:.1f}" if hl is not None else "None"
    logger.info("half_life_estimate: %s days, ou_params: %s", hl_str, params)
=======
    
    for t in range(1, 500):
        ou[t] = ou[t-1] - mean_reversion * ou[t-1] + np.random.normal(0, 0.1)
    
    spread = pd.Series(ou)
    estimator = SpreadHalfLifeEstimator()
    
    hl = estimator.estimate_half_life_from_spread(spread)
    params = estimator.compute_ou_process_parameters(spread)
    
    print(f"Estimated Half-Life: {hl:.1f} days")
    print(f"OU Parameters: {params}")
>>>>>>> origin/main
