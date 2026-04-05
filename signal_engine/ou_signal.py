"""
Ornstein-Uhlenbeck Signal ÔÇö Expected reversion velocity for pair trading.

Instead of a static z-score threshold, this models the spread as an OU
process: dX = theta*(mu - X)*dt + sigma*dW

The signal is the *expected reversion velocity* normalised by volatility:
    signal = theta * (mu - X_current) / sigma_OU

High theta => fast mean-reversion => higher confidence in z-score entries.
High (mu - X) => large dislocation => larger expected profit.

Phase 1, Etape 1.1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class OUParams:
    """Estimated Ornstein-Uhlenbeck parameters."""

    theta: float  # Mean-reversion speed (1/days)
    mu: float  # Long-run mean
    sigma: float  # Diffusion coefficient
    half_life: float  # ln(2) / theta


class OUSignalGenerator:
    """
    Ornstein-Uhlenbeck signal generator for pair trading spreads.

    Estimates OU parameters via AR(1) regression on the spread:
        X_t - X_{t-1} = alpha + beta * X_{t-1} + eps
        theta = -beta,  mu = alpha / theta,  sigma = std(eps) / sqrt(dt)

    Signal: normalised expected reversion velocity in [-1, 1].

    Usage::

        ou = OUSignalGenerator()
        score = ou.compute_score(spread_series)
    """

    def __init__(
        self,
        lookback: int = 60,
        min_theta: float = 0.001,
        max_score: float = 1.0,
    ):
        """
        Args:
            lookback: Rolling window for OU parameter estimation.
            min_theta: Minimum theta to consider mean-reverting.
            max_score: Clip absolute score to this value.
        """
        if lookback < 10:
            raise ValueError(f"lookback must be >= 10, got {lookback}")
        self.lookback = lookback
        self.min_theta = min_theta
        self.max_score = max_score

    def estimate_params(self, spread: pd.Series) -> OUParams | None:
        """Estimate OU parameters from the spread series via AR(1) regression.

        Uses the last `self.lookback` observations.

        Returns:
            OUParams if mean-reverting (theta > min_theta), else None.
        """
        s = spread.dropna()
        if len(s) < max(20, self.lookback // 2):
            return None

        s = s.iloc[-self.lookback :]
        x_lag = s.values[:-1]
        dx = np.diff(np.asarray(s, dtype=float))

        # OLS: dx = alpha + beta * x_lag
        n = len(dx)
        if n < 10:
            return None

        x_mat = np.column_stack([np.ones(n), np.asarray(x_lag, dtype=float)])
        try:
            coeffs, _, _, _ = np.linalg.lstsq(x_mat, dx, rcond=None)
        except np.linalg.LinAlgError:
            return None

        alpha, beta = coeffs[0], coeffs[1]

        # theta = -beta (must be positive for mean-reversion)
        theta = -beta
        if theta < self.min_theta:
            return None

        mu = alpha / theta
        residuals = dx - x_mat @ coeffs
        sigma = float(np.std(residuals, ddof=1)) if n > 2 else float(np.std(residuals))

        if sigma < 1e-12:
            return None

        half_life = np.log(2) / theta

        return OUParams(theta=theta, mu=mu, sigma=sigma, half_life=half_life)

    def compute_score(self, spread: pd.Series) -> float:
        """Compute OU-based signal score for the current spread value.

        Returns:
            Score in [-1, 1]. Positive = spread below mu (expect up-reversion),
            negative = spread above mu (expect down-reversion).
            Returns 0.0 if OU estimation fails.
        """
        params = self.estimate_params(spread)
        if params is None:
            return 0.0

        current_x = float(spread.dropna().iloc[-1])

        # Expected reversion velocity: theta * (mu - X) / sigma
        raw_signal = params.theta * (params.mu - current_x) / params.sigma

        # Normalise to [-1, 1] using tanh-like compression
        # Scale factor: at raw_signal = 2, score ~ 0.76
        score = float(np.tanh(raw_signal / 2.0))

        return float(np.clip(score, -self.max_score, self.max_score))
