"""
Z-Score Calculator — Spread z-score with adaptive lookback.

Computes rolling z-scores for pair trading spreads with:
    - Half-life adaptive lookback window
    - EWMA smoothing option
    - Bounded z-score output for robustness

The adaptive lookback logic:
    - Fast mean-reversion (HL ≤ 10d):  lookback = 3 × HL
    - Normal (10d < HL ≤ 60d):         lookback = linear interpolation → HL
    - Slow (HL > 60d):                 capped at 60

This ensures the z-score window captures the correct frequency
of mean reversion for each pair.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


class ZScoreCalculator:
    """
    Compute rolling z-scores for spread series.

    Usage::

        calc = ZScoreCalculator()
        z = calc.compute(spread, half_life=25.0)
        current_z = z.iloc[-1]
    """

    def __init__(
        self,
        default_lookback: int = 20,
        use_ewma: bool = False,
        max_z_score: float = 10.0,
    ):
        """
        Args:
            default_lookback: Fallback lookback if half-life is unavailable.
            use_ewma: Use EWMA-based z-score instead of SMA.
            max_z_score: Clip z-scores beyond this absolute value.
        """
        self.default_lookback = default_lookback
        self.use_ewma = use_ewma
        self.max_z_score = max_z_score

    def compute(
        self,
        spread: pd.Series,
        half_life: Optional[float] = None,
        lookback: Optional[int] = None,
    ) -> pd.Series:
        """
        Compute rolling z-score of *spread*.

        Args:
            spread: Spread time series.
            half_life: Half-life in bars/days (used to adapt lookback).
            lookback: Explicit lookback (overrides half-life logic).

        Returns:
            Z-score series (same index as *spread*).
        """
        window = self._resolve_lookback(half_life, lookback)

        if self.use_ewma:
            span = max(2, window)
            mean = spread.ewm(span=span, min_periods=max(1, window // 2)).mean()
            std = spread.ewm(span=span, min_periods=max(1, window // 2)).std()
        else:
            mean = spread.rolling(window=window, min_periods=max(1, window // 2)).mean()
            std = spread.rolling(window=window, min_periods=max(1, window // 2)).std()

        # Avoid division by zero
        std = std.replace(0, np.nan)
        z = (spread - mean) / std
        z = z.fillna(0.0)

        # Clip extreme values
        z = z.clip(-self.max_z_score, self.max_z_score)

        return z

    def _resolve_lookback(
        self,
        half_life: Optional[float],
        explicit: Optional[int],
    ) -> int:
        """Determine lookback window from half-life or explicit override."""
        if explicit is not None:
            return max(2, explicit)

        if half_life is None or half_life <= 0:
            return self.default_lookback

        # Smooth adaptive mapping
        hl = half_life
        if hl <= 10:
            window = int(3.0 * hl)
        elif hl <= 60:
            # Linear interpolation: multiplier goes from 3.0 at HL=10
            # down to 1.0 at HL=60
            multiplier = 3.0 - 2.0 * (hl - 10) / 50
            window = int(multiplier * hl)
        else:
            window = 60

        return max(2, min(window, 252))

    @staticmethod
    def current_z(spread: pd.Series, lookback: int = 20) -> float:
        """Convenience: return the latest z-score as a scalar."""
        if len(spread) < lookback:
            return 0.0
        window = spread.iloc[-lookback:]
        std = window.std()
        if std < 1e-12:
            return 0.0
        return float((spread.iloc[-1] - window.mean()) / std)
