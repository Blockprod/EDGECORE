"""
Volatility Regime Signal ÔÇö Vol compression/expansion filter for pair trading.

Enters only when spread volatility is compressed (low risk), exits or
avoids entry when vol explodes (regime change likely).

    vol_ratio = spread_vol_fast / spread_vol_slow
    - vol_ratio < entry_threshold => compressed => safe to enter
    - vol_ratio > exit_threshold  => explosion => exit / avoid

Phase 1, Etape 1.3.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


class VolatilityRegimeSignal:
    """
    Volatility regime signal for pair trading spreads.

    Computes the ratio of short-term to long-term spread volatility
    and produces a score indicating whether conditions are favourable
    for mean-reversion entries.

    Score > 0 = vol compressed (favourable)
    Score < 0 = vol expanding (unfavourable)

    Usage::

        vol_sig = VolatilityRegimeSignal()
        score = vol_sig.compute_score(spread_series)
    """

    def __init__(
        self,
        fast_window: int = 20,
        slow_window: int = 60,
        entry_threshold: float = 0.8,
        exit_threshold: float = 1.5,
    ):
        """
        Args:
            fast_window: Rolling window for short-term vol (days).
            slow_window: Rolling window for long-term vol (days).
            entry_threshold: Vol ratio below this => compressed (bullish).
            exit_threshold: Vol ratio above this => explosion (bearish).
        """
        if fast_window < 5:
            raise ValueError(f"fast_window must be >= 5, got {fast_window}")
        if slow_window <= fast_window:
            raise ValueError(
                f"slow_window ({slow_window}) must be > fast_window ({fast_window})"
            )
        if entry_threshold <= 0:
            raise ValueError(f"entry_threshold must be > 0, got {entry_threshold}")
        if exit_threshold <= entry_threshold:
            raise ValueError(
                f"exit_threshold ({exit_threshold}) must be > entry_threshold ({entry_threshold})"
            )

        self.fast_window = fast_window
        self.slow_window = slow_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

    def compute_vol_ratio(self, spread: pd.Series) -> float | None:
        """Compute the ratio of fast to slow spread volatility.

        Returns:
            vol_ratio (float) or None if insufficient data.
        """
        s = spread.dropna()
        if len(s) < self.slow_window + 5:
            return None

        returns = s.diff().dropna()
        if len(returns) < self.slow_window:
            return None

        fast_vol = float(returns.iloc[-self.fast_window:].std())
        slow_vol = float(returns.rolling(self.slow_window).std().iloc[-1])

        if slow_vol < 1e-12:
            return None

        return fast_vol / slow_vol

    def compute_score(self, spread: pd.Series) -> float:
        """Compute volatility regime score for the spread.

        Returns:
            Score in [-1, 1].
            Positive: vol compressed (favourable for entry).
            Negative: vol expanding (avoid entry).
            0.0 if insufficient data.
        """
        vol_ratio = self.compute_vol_ratio(spread)
        if vol_ratio is None:
            return 0.0

        midpoint = (self.entry_threshold + self.exit_threshold) / 2.0

        # Map vol_ratio to [-1, 1]:
        #   vol_ratio << entry_threshold => strongly positive
        #   vol_ratio >> exit_threshold  => strongly negative
        raw = -(vol_ratio - midpoint) / (self.exit_threshold - self.entry_threshold)
        score = float(np.tanh(raw))

        return float(np.clip(score, -1.0, 1.0))

    def is_compressed(self, spread: pd.Series) -> bool:
        """Check if spread volatility is compressed (favourable for entry)."""
        ratio = self.compute_vol_ratio(spread)
        if ratio is None:
            return True  # Default: allow entry if insufficient data
        return ratio < self.entry_threshold

    def is_exploding(self, spread: pd.Series) -> bool:
        """Check if spread volatility is exploding (avoid entry / force exit)."""
        ratio = self.compute_vol_ratio(spread)
        if ratio is None:
            return False  # Default: no alarm if insufficient data
        return ratio > self.exit_threshold
