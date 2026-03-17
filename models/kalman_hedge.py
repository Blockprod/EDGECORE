"""
Sprint 4.2 ÔÇô Kalman Filter for dynamic hedge ratio estimation.

Replaces static OLS ╬▓ with an adaptive bar-by-bar estimate:
- State: ╬▓_t (hedge ratio at time t)
- Observation: y_t = ╬▓_t ├ù x_t + ╬Á_t
- Transition: ╬▓_t = ╬▓_{t-1} + ╬À_t

Advantages over rolling OLS:
- No window parameter needed (adapts continuously)
- Detects breakdowns in real-time (normalized innovation > threshold)
- Produces ╬▓ with confidence interval (via state covariance P)
- Adapts faster to structural changes

Usage:
    kf = KalmanHedgeRatio()
    for y_val, x_val in zip(y_series, x_series):
        beta, spread, innovation = kf.update(y_val, x_val)
    print(kf.beta, kf.get_confidence_interval())
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, List
from structlog import get_logger

logger = get_logger(__name__)


class KalmanHedgeRatio:
    """
    Dynamic hedge ratio estimation via Kalman Filter.

    State-space model (with intercept):
        State: [╬▓_t, ╬▒_t]  (hedge ratio and intercept)
        Transition: ╬©_t = ╬©_{t-1} + ╬À_t,  ╬À ~ N(0, Q)
        Observation: y_t = ╬▓_t * x_t + ╬▒_t + ╬Á_t,  ╬Á ~ N(0, R)

    Parameters:
        delta: State noise variance ÔÇô controls adaptation speed.
               Higher delta ÔåÆ ╬▓ adapts faster but is noisier.
               Typical range: 1e-5 (slow) to 1e-3 (fast).
        ve: Initial observation variance estimate.
        innovation_threshold: Normalized innovation threshold for
            breakdown alerts (default 3.0 = 3¤â).
        r_smoothing: Exponential smoothing factor for adaptive R
            (0 = no adaptation, 0.98 = slow, 0.90 = fast).
    """

    def __init__(
        self,
        delta: float = 1e-4,
        ve: float = 1e-3,
        innovation_threshold: float = 3.0,
        r_smoothing: float = 0.97,
    ):
        if delta <= 0:
            raise ValueError(f"delta must be > 0, got {delta}")
        if ve <= 0:
            raise ValueError(f"ve must be > 0, got {ve}")

        self.delta = delta
        self.ve = ve
        self.innovation_threshold = innovation_threshold
        self.r_smoothing = r_smoothing

        # State: [beta, intercept]
        self.beta: Optional[float] = None
        self.intercept: float = 0.0
        # 2x2 state covariance matrix
        self.P: Optional[np.ndarray] = None
        self.R: float = ve            # Observation noise variance (adaptive)
        self.S: float = 0.0           # Innovation variance (for diagnostics)
        # State transition noise
        self.Q: np.ndarray = np.diag([delta, delta * 0.1])  # intercept changes slower

        # History
        self.beta_history: List[float] = []
        self.spread_history: List[float] = []
        self.innovation_history: List[float] = []
        self.P_history: List[float] = []

        # Breakdown tracking
        self.breakdown_count: int = 0
        self.bars_processed: int = 0

    def update(self, y: float, x: float) -> Tuple[float, float, float]:
        """
        Update hedge ratio with a new observation (y, x).

        Args:
            y: Dependent variable value (e.g., price of asset Y)
            x: Independent variable value (e.g., price of asset X)

        Returns:
            Tuple of (beta, spread, normalized_innovation):
                beta: Updated hedge ratio estimate
                spread: y - beta * x (current residual)
                normalized_innovation: Innovation / sqrt(S).
                    |innovation| > threshold Ôåô potential breakdown.
        """
        if abs(x) < 1e-12:
            # x Ôëê 0 ÔåÆ can't estimate ╬▓, return current state
            spread = y - (self.beta or 0.0) * x - self.intercept
            self.bars_processed += 1
            return self.beta or 0.0, spread, 0.0

        # --- Initialization (first observation) ---
        if self.beta is None:
            self.beta = y / x
            self.intercept = 0.0
            self.P = np.eye(2)  # 2x2 identity
            self.R = self.ve
            self.beta_history.append(self.beta)
            self.spread_history.append(0.0)
            self.innovation_history.append(0.0)
            self.P_history.append(self.P[0, 0])
            self.bars_processed = 1
            return self.beta, 0.0, 0.0

        # --- Prediction step ---
        theta_pred = np.array([self.beta, self.intercept])
        P_pred = self.P + self.Q

        # Observation vector: y_t = H @ theta + eps, where H = [x, 1]
        H = np.array([x, 1.0])

        # --- Innovation (observation residual) ---
        y_pred = H @ theta_pred
        innovation = y - y_pred
        self.S = float(H @ P_pred @ H) + self.R

        # --- Kalman gain (2x1 vector) ---
        K = (P_pred @ H) / self.S

        # --- Update step ---
        theta_new = theta_pred + K * innovation
        self.beta = float(theta_new[0])
        self.intercept = float(theta_new[1])
        self.P = P_pred - np.outer(K, H) @ P_pred

        # Ensure P stays positive semi-definite (numerical stability)
        self.P = (self.P + self.P.T) / 2.0
        np.fill_diagonal(self.P, np.maximum(np.diag(self.P), 1e-12))

        # --- Adaptive R: exponential smoothing of squared innovation ---
        if self.r_smoothing > 0 and self.bars_processed > 5:
            self.R = self.r_smoothing * self.R + (1 - self.r_smoothing) * (innovation ** 2)
            self.R = max(self.R, 1e-12)  # floor

        # Spread for downstream use
        spread = y - self.beta * x - self.intercept

        # --- Normalized innovation (for breakdown detection) ---
        normalized_innovation = innovation / np.sqrt(self.S) if self.S > 0 else 0.0

        # Check for breakdown
        if abs(normalized_innovation) > self.innovation_threshold:
            self.breakdown_count += 1
            logger.debug(
                "kalman_innovation_spike",
                innovation=round(normalized_innovation, 3),
                threshold=self.innovation_threshold,
                beta=round(self.beta, 6),
                bar=self.bars_processed,
            )

        # --- Record history ---
        self.beta_history.append(self.beta)
        self.spread_history.append(spread)
        self.innovation_history.append(normalized_innovation)
        self.P_history.append(float(self.P[0, 0]))

        self.bars_processed += 1
        return self.beta, spread, normalized_innovation

    def get_confidence_interval(self, z: float = 1.96) -> Tuple[float, float]:
        """
        Return (lower, upper) confidence interval for current ╬▓.

        Args:
            z: Z-score for CI (1.96 = 95%, 2.576 = 99%)

        Returns:
            (beta - z*sqrt(P), beta + z*sqrt(P))
        """
        if self.beta is None:
            return (0.0, 0.0)
        std = np.sqrt(self.P[0, 0]) if self.P is not None else 0.0
        return (self.beta - z * std, self.beta + z * std)

    def is_breakdown(self) -> bool:
        """Check if the latest innovation indicates a breakdown."""
        if not self.innovation_history:
            return False
        return bool(abs(self.innovation_history[-1]) > self.innovation_threshold)

    @property
    def is_broken(self) -> bool:
        """True if cumulative breakdown_count exceeds 10 % of observed bars.

        A Kalman filter with this many anomalous innovations is unreliable:
        callers should suspend signal generation and log a warning.
        """
        if self.bars_processed < 10:
            return False
        return self.breakdown_count >= max(int(self.bars_processed * 0.10), 5)

    def get_recent_breakdown_rate(self, window: int = 20) -> float:
        """
        Fraction of recent bars with normalized innovation > threshold.

        Args:
            window: Number of recent bars to check.

        Returns:
            Fraction in [0, 1].
        """
        if len(self.innovation_history) < 2:
            return 0.0
        recent = self.innovation_history[-window:]
        return sum(
            1 for inn in recent if abs(inn) > self.innovation_threshold
        ) / len(recent)

    def run_filter(
        self,
        y: pd.Series,
        x: pd.Series,
    ) -> pd.DataFrame:
        """
        Run the Kalman filter on full series and return a DataFrame.

        Args:
            y: Dependent price series
            x: Independent price series (same index as y)

        Returns:
            DataFrame with columns: beta, spread, innovation, P
        """
        if len(y) != len(x):
            raise ValueError(
                f"y and x must have same length, got {len(y)} vs {len(x)}"
            )

        # Reset state for a clean run
        self.beta = None
        self.P = 0.0
        self.R = self.ve
        self.beta_history = []
        self.spread_history = []
        self.innovation_history = []
        self.P_history = []
        self.breakdown_count = 0
        self.bars_processed = 0

        for y_val, x_val in zip(y.values, x.values):
            self.update(float(y_val), float(x_val))

        return pd.DataFrame(
            {
                "beta": self.beta_history,
                "spread": self.spread_history,
                "innovation": self.innovation_history,
                "P": self.P_history,
            },
            index=y.index if hasattr(y, "index") else range(len(y)),
        )

    def get_diagnostics(self) -> dict:
        """Return diagnostic summary of the filter state."""
        return {
            "bars_processed": self.bars_processed,
            "current_beta": self.beta,
            "current_P": self.P,
            "beta_95_ci": self.get_confidence_interval(),
            "breakdown_count": self.breakdown_count,
            "recent_breakdown_rate": self.get_recent_breakdown_rate(),
            "delta": self.delta,
            "ve": self.ve,
            "innovation_threshold": self.innovation_threshold,
        }
