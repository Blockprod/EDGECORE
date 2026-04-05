"""
Adaptive Z-Score Threshold Engine.

Dynamically adjusts entry/exit thresholds based on market regime and pair characteristics.
This replaces the static threshold (2.0) with a regime-aware system.

Key Insight:
  In low-volatility regimes: Spread mean-reverts quickly Ôåô Use lower threshold (1.5)
  In high-volatility regimes: Spread has wider excursions Ôåô Use higher threshold (2.5)
  Mid-trade: Adapt exit threshold to actual half-life and volatility drift
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class ThresholdConfig:
    """Configuration for adaptive threshold calculation."""

    base_entry_threshold: float = 2.0  # Default Z-score entry level
    base_exit_threshold: float = 0.5  # Default Z-score exit level (was 0.0 ÔÇö unreachable in float)
    min_entry_threshold: float = 1.0  # Lower bound (don't go too permissive)
    max_entry_threshold: float = 3.5  # Upper bound (don't go too strict)
    volatility_adjustment_enabled: bool = True
    regime_adjustment_enabled: bool = True
    hl_adjustment_enabled: bool = True

    # Volatility percentile ranges for regime classification
    low_vol_percentile: float = 0.25  # Bottom 25% = low volatility
    high_vol_percentile: float = 0.75  # Top 25% = high volatility

    # Half-life adjustment factors
    short_hl_threshold: float = 10.0  # Days
    long_hl_threshold: float = 40.0  # Days


class AdaptiveThresholdCalculator:
    """
    Calculates adaptive Z-score thresholds that adjust to market conditions.

    Problem Statement:
      - Fixed threshold (e.g., 2.0) is suboptimal across regimes
      - In calm periods: Threshold too high Ôåô miss good trades
      - In volatile periods: Threshold too low Ôåô false signals

    Solution:
      - Monitor spread volatility percentile in rolling window
      - Classify regime: low/normal/high volatility
      - Adjust threshold dynamically: 1.5 Ôåô 2.0 Ôåô 2.5
      - Also consider half-life of mean reversion
    """

    def __init__(self, config: ThresholdConfig | None = None):
        """
        Initialize threshold calculator.

        Args:
            config: ThresholdConfig with adjustment parameters
        """
        self.config = config or ThresholdConfig()
        self.volatility_history: list[float] = []

    def calculate_threshold(
        self, spread: pd.Series, half_life: float | None = None, lookback_vol: int = 60
    ) -> tuple[float, float, dict[str, Any]]:
        """
        Calculate adaptive entry and exit thresholds.

        Args:
            spread: Current and historical spread series
            half_life: Half-life of mean reversion in days (optional)
            lookback_vol: Lookback window for volatility assessment

        Returns:
            Tuple of (entry_threshold, exit_threshold, adjustment_details)
        """
        # Start with baseline thresholds
        entry_threshold = self.config.base_entry_threshold
        exit_threshold = self.config.base_exit_threshold

        adjustments = {
            "base_entry": entry_threshold,
            "volatility_adjustment": 0.0,
            "half_life_adjustment": 0.0,
            "regime": "normal",
            "spread_volatility_percentile": None,
            "spread_std": None,
        }

        # Adjustment 1: Volatility-based
        if self.config.volatility_adjustment_enabled and len(spread) >= lookback_vol:
            vol_adjustment, regime, vol_pctl = self._calculate_volatility_adjustment(spread, lookback_vol)
            entry_threshold += vol_adjustment
            adjustments["volatility_adjustment"] = vol_adjustment
            adjustments["regime"] = regime
            adjustments["spread_volatility_percentile"] = vol_pctl
            adjustments["spread_std"] = spread.tail(lookback_vol).std()

        # Adjustment 2: Half-life based
        if self.config.hl_adjustment_enabled and half_life is not None:
            hl_adjustment = self._calculate_half_life_adjustment(half_life)
            entry_threshold += hl_adjustment
            adjustments["half_life_adjustment"] = hl_adjustment
            adjustments["half_life_days"] = half_life

        # Clamp to valid bounds
        entry_threshold = np.clip(entry_threshold, self.config.min_entry_threshold, self.config.max_entry_threshold)

        return entry_threshold, exit_threshold, adjustments

    def _calculate_volatility_adjustment(self, spread: pd.Series, lookback: int = 60) -> tuple[float, str, float]:
        """
        Adjust threshold based on spread volatility regime.

        Returns:
            (adjustment_amount, regime_label, volatility_percentile)
        """
        # Calculate rolling volatility
        recent_volatility = spread.tail(lookback).std()

        # Get historical volatility percentiles from this series
        if len(spread) >= lookback * 2:
            # Use longer history for percentile calculation
            historical_vols = []
            for i in range(lookback, len(spread) - lookback):
                window_vol = spread.iloc[i : i + lookback].std()
                historical_vols.append(window_vol)

            if historical_vols:
                # Percentile rank of recent volatility in the historical distribution
                vol_pctl = float(100.0 * np.mean(np.array(historical_vols) < recent_volatility))

                # Classification logic
                low_vol_threshold = np.percentile(historical_vols, self.config.low_vol_percentile * 100)
                high_vol_threshold = np.percentile(historical_vols, self.config.high_vol_percentile * 100)

                if recent_volatility < low_vol_threshold:
                    regime = "low"
                    # Low volatility: mean-revert is fast, use LOWER threshold
                    adjustment = -0.4  # 2.0 Ôåô 1.6
                elif recent_volatility > high_vol_threshold:
                    regime = "high"
                    # High volatility: larger excursions, use HIGHER threshold
                    adjustment = +0.5  # 2.0 Ôåô 2.5
                else:
                    regime = "normal"
                    adjustment = 0.0

                # vol_pctl already computed above
            else:
                vol_pctl = 50.0
                adjustment = 0.0
                regime = "normal"
        else:
            # Not enough history, default
            vol_pctl = 50.0
            adjustment = 0.0
            regime = "normal"

        return adjustment, regime, vol_pctl

    def _calculate_half_life_adjustment(self, half_life: float) -> float:
        """
        Adjust threshold based on half-life of mean reversion.

        Logic:
          - Very short HL (< 10d): Fast reversion, use tighter entry (lower threshold)
          - Normal HL (10-40d): Standard reversion, no adjustment
          - Long HL (> 40d): Slow reversion, use looser entry (higher threshold)
        """
        if half_life < self.config.short_hl_threshold:
            # Fast mean reversion: we can be aggressive
            return -0.3
        elif half_life > self.config.long_hl_threshold:
            # Slow mean reversion: be conservative
            return +0.3
        else:
            # Normal range: no adjustment
            return 0.0

    def calculate_position_sizing(
        self, portfolio_vol: float, spread_vol: float, target_risk_pct: float = 0.01
    ) -> float:
        """
        Calculate position size based on volatility.

        Args:
            portfolio_vol: Portfolio volatility (e.g., 0.15 for 15% annualized)
            spread_vol: Current spread volatility
            target_risk_pct: Target risk per trade (e.g., 0.01 for 1%)

        Returns:
            Position size multiplier (0.0 to 2.0)
        """
        if spread_vol == 0:
            return 1.0
        if portfolio_vol <= 0:
            logger.warning("invalid_portfolio_vol", portfolio_vol=portfolio_vol)
            return 1.0

        # Position size inversely proportional to volatility
        size = target_risk_pct / max(spread_vol, 0.001)
        size = np.clip(size, 0.1, 2.0)  # Bounds: 10%-200% of base

        return size


class DynamicSpreadModel:
    """
    Enhanced spread model with adaptive thresholds and lookback windows.
    Includes hedge ratio tracking for detecting relationship degradation.

    Sprint 4.2: Supports optional Kalman filter for dynamic ╬▓ estimation.
    When use_kalman=True, ╬▓ adapts bar-by-bar instead of being fixed from OLS.
    """

    def __init__(
        self,
        y: pd.Series,
        x: pd.Series,
        half_life: float | None = None,
        pair_key: str | None = None,
        hedge_ratio_tracker=None,
        use_kalman: bool = True,
        kalman_delta: float = 1e-4,
        kalman_ve: float = 1e-3,
        bar_time=None,
    ):
        """
        Initialize dynamic spread model.

        Args:
            y: Dependent series
            x: Independent series
            half_life: Half-life of mean reversion (optional)
            pair_key: Pair identifier for tracking (optional)
            hedge_ratio_tracker: HedgeRatioTracker instance for ╬▓ monitoring (optional)
            use_kalman: If True, use Kalman filter for dynamic ╬▓ (Sprint 4.2)
            kalman_delta: Kalman state noise variance (adaptation speed)
            kalman_ve: Kalman observation noise variance
            bar_time: Timestamp of the current bar for tracker (optional, defaults to datetime.now())
        """
        self.use_kalman = use_kalman
        self.kalman_filter = None

        # OLS regression (always compute as baseline reference)
        X = np.column_stack([np.ones(len(x)), np.asarray(x, dtype=float)])
        beta = np.linalg.lstsq(X, np.asarray(y, dtype=float), rcond=None)[0]

        self.intercept = beta[0]
        self.beta = beta[1]
        self.y = y
        self.x = x
        self.half_life = half_life
        self.pair_key = pair_key
        self.tracker = hedge_ratio_tracker
        self.is_deprecated = False
        self.residuals = np.asarray(y, dtype=float) - X @ beta
        self.std_residuals = float(np.std(self.residuals))

        # Sprint 4.2: Initialize Kalman filter and run it on historical data
        if use_kalman:
            from models.kalman_hedge import KalmanHedgeRatio

            self.kalman_filter = KalmanHedgeRatio(delta=kalman_delta, ve=kalman_ve)
            kf_results = self.kalman_filter.run_filter(y, x)
            # Use Kalman's final β as the model β
            self.beta = self.kalman_filter.beta
            # Kalman spread series (for residual stats)
            self.residuals = kf_results["spread"].values
            self.std_residuals = float(np.std(np.asarray(self.residuals[1:], dtype=float)))  # skip first (0)
            # C-07: alert when the filter accumulated too many anomalous innovations
            if self.kalman_filter.is_broken:
                logger.warning(
                    "kalman_filter_broken_after_init",
                    pair=pair_key,
                    breakdown_count=self.kalman_filter.breakdown_count,
                    bars_processed=self.kalman_filter.bars_processed,
                )

        # Initialize adaptive threshold calculator
        self.threshold_config = ThresholdConfig()
        self.threshold_calculator = AdaptiveThresholdCalculator(self.threshold_config)

        # Record initial ╬▓ if tracker is available
        if self.tracker is not None and self.pair_key is not None:
            self.tracker.record_initial_beta(self.pair_key, self.beta, bar_time=bar_time)

    def reestimate_beta_if_needed(self, y: pd.Series, x: pd.Series, bar_time=None) -> bool:
        """
        Reestimate ╬▓ if enough time has passed, using recent data.

        Checks with tracker if reestimation is needed, and updates the model
        if so.  When Kalman is active, uses the Kalman-estimated ╬▓; otherwise
        falls back to OLS.

        Args:
            y: Recent dependent series
            x: Recent independent series
            bar_time: Timestamp of the current bar (optional, passed to tracker)

        Returns:
            is_stable: Whether the relationship remains stable
        """
        if self.tracker is None or self.pair_key is None:
            return True

        # Compute a fresh ╬▓ from recent data
        if self.use_kalman and self.kalman_filter is not None:
            new_beta = self.beta  # Kalman already updated in __init__
        else:
            X = np.column_stack([np.ones(len(x)), np.asarray(x, dtype=float)])
            try:
                beta_coef = np.linalg.lstsq(X, np.asarray(y, dtype=float), rcond=None)[0]
                new_beta = beta_coef[1]
            except Exception as e:
                logger.warning("beta_reestimation_failed", pair=self.pair_key, error=str(e))
                return True

        current_beta, is_stable = self.tracker.reestimate_if_needed(
            self.pair_key,
            new_beta,
            drift_tolerance_pct=10.0,
            bar_time=bar_time,
        )

        if current_beta is not None:
            self.beta = current_beta

        if not is_stable:
            self.is_deprecated = True

        return is_stable

    def compute_spread(self, y: pd.Series, x: pd.Series) -> pd.Series:
        """
        Compute spread: y - (intercept + beta*x).

        When Kalman is enabled, uses the Kalman filter's dynamic ╬▓.
        """
        if self.use_kalman and self.kalman_filter is not None:
            return self.compute_spread_kalman(y, x)
        return y - (self.intercept + (self.beta or 0.0) * x)

    def compute_spread_kalman(self, y: pd.Series, x: pd.Series) -> pd.Series:
        """
        Sprint 4.2: Compute spread using Kalman filter's time-varying ╬▓.

        Each bar uses the ╬▓ estimated up to that point, producing a
        spread series that adapts to structural changes.

        Args:
            y: Dependent price series
            x: Independent price series

        Returns:
            Spread series with dynamic ╬▓
        """
        if self.kalman_filter is None:
            from models.kalman_hedge import KalmanHedgeRatio

            self.kalman_filter = KalmanHedgeRatio()

        kf_results = self.kalman_filter.run_filter(y, x)
        self.beta = self.kalman_filter.beta  # Update to latest β
        # C-07: warn if Kalman is broken so callers can suppress signals
        if self.kalman_filter.is_broken:
            logger.warning(
                "kalman_filter_broken_during_spread",
                pair=getattr(self, "pair_key", None),
                breakdown_count=self.kalman_filter.breakdown_count,
                bars_processed=self.kalman_filter.bars_processed,
            )
        return kf_results["spread"]

    def compute_z_score(self, spread: pd.Series, lookback: int | None = None) -> pd.Series:
        """
        Compute rolling Z-score with adaptive lookback window (S2.2).

        Adaptive lookback based on half-life ensures Z-score captures the right
        frequency of mean reversion:
        - Fast pairs (HL < 30d): lookback = 3*HL (smooth short-term noise)
        - Normal (HL 30-60d): lookback = HL (capture full reversion cycle)
        - Slow pairs (HL > 60d): lookback = 60 (historical reference)

        This replaces the fixed 20-day window with pair-specific timing.

        Args:
            spread: Spread series
            lookback: Explicit rolling window (overrides half-life logic if provided)

        Returns:
            Z-score series
        """
        # Determine lookback window
        if lookback is None:
            if self.half_life is not None:
                # Smooth adaptive lookback (no discontinuity at HL=30):
                # Multiplier linearly interpolates from 3.0 at HLÔëñ10
                # down to 1.0 at HLÔëÑ60, capped at 60 for HL>60.
                if self.half_life <= 10:
                    multiplier = 3.0
                elif self.half_life >= 60:
                    multiplier = 1.0
                else:
                    # Linear interpolation: 3.0 at HL=10 Ôåô 1.0 at HL=60
                    multiplier = 3.0 - 2.0 * (self.half_life - 10) / (60 - 10)
                lookback = int(np.ceil(multiplier * self.half_life))
                # Cap at 60 for very slow reversion
                lookback = min(lookback, 60)
            else:
                # Default fallback
                lookback = 20

        # Enforce bounds: [10, 120]
        lookback = max(10, min(lookback, 120))

        rolling_mean = spread.rolling(window=lookback).mean()
        rolling_std = spread.rolling(window=lookback).std()
        z_score = (spread - rolling_mean) / (rolling_std + 1e-8)
        # Sprint 2.8 (M-08): Clamp Z-score to [-6, +6] to prevent
        # residual outliers from generating aberrant signals
        z_score = z_score.clip(-6.0, 6.0)
        return z_score

    def get_adaptive_signals(
        self, spread: pd.Series, config: ThresholdConfig | None = None
    ) -> tuple[pd.Series, dict[str, Any]]:
        """
        Generate trading signals with adaptive thresholds.

        Args:
            spread: Spread series
            config: Threshold configuration

        Returns:
            (signals, thresholds_info)
        """
        z_score = self.compute_z_score(spread)

        # Use caller-supplied config to override threshold calculation if provided
        calculator = AdaptiveThresholdCalculator(config=config) if config is not None else self.threshold_calculator

        # Calculate adaptive thresholds
        entry_thresh, exit_thresh, adj_details = calculator.calculate_threshold(spread, half_life=self.half_life)

        # Generate signals: 1 (long), 0 (hold), -1 (short)
        signals = pd.Series(0, index=z_score.index)

        # Long signal: z_score < -entry_threshold (spread below mean)
        signals[z_score < -entry_thresh] = 1

        # Short signal: z_score > entry_threshold (spread above mean)
        signals[z_score > entry_thresh] = -1

        # Exit signal: near zero
        signals[np.abs(z_score) < exit_thresh + 0.5] = 0

        return signals, {
            "entry_threshold": entry_thresh,
            "exit_threshold": exit_thresh,
            "z_score": z_score,
            "adjustments": adj_details,
        }

    def get_model_info(self) -> dict:
        """Return all model parameters."""
        return {
            "intercept": self.intercept,
            "beta": self.beta,
            "residual_std": self.std_residuals,
            "residual_mean": float(np.mean(np.asarray(self.residuals, dtype=float))),
            "half_life": self.half_life,
        }
