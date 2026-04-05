"""
Phase 3.2 ÔÇö Intraday Signal Generators.

Three complementary intraday alpha sources for pair-trading:
1. IntradayMeanReversionSignal ÔÇö fast z-score on 5-min spread bars.
2. GapReversionSignal         ÔÇö overnight gap detection + reversion.
3. VolumeProfileSignal        ÔÇö volume-weighted spread confirmation.

Each returns a score in [-1, 1] compatible with SignalCombiner.

Target: augment daily signals with intraday timing,
        increasing trade count to ÔëÑ 200/year.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 3.2.1 ÔÇö Intraday Mean-Reversion Signal (fast z-score)
# ---------------------------------------------------------------------------

class IntradayMeanReversionSignal:
    """Fast z-score on 5-min spread for intraday timing.

    Uses a short lookback (12-20 bars = 1-1.6 hours) to detect
    short-lived spread dislocations that revert within the session.

    Score = -z_score / scale, clamped to [-1, 1].
    Negative z ÔåÆ positive score (buy spread), and vice-versa.
    """

    def __init__(
        self,
        lookback: int = 15,
        scale: float = 2.5,
    ):
        if lookback < 5:
            raise ValueError(f"lookback must be >= 5, got {lookback}")
        self.lookback = lookback
        self.scale = scale

    def compute_score(self, spread: pd.Series) -> float:
        """Compute intraday mean-reversion score.

        Args:
            spread: Spread series (at least ``lookback`` bars).

        Returns:
            Score in [-1, 1].  Positive = buy spread, negative = sell spread.
        """
        s = spread.dropna()
        if len(s) < self.lookback:
            return 0.0

        window = s.iloc[-self.lookback:]
        mu = window.mean()
        sigma = window.std()
        if sigma < 1e-10:
            return 0.0

        z = (s.iloc[-1] - mu) / sigma
        score = -z / self.scale
        return float(np.clip(score, -1.0, 1.0))


# ---------------------------------------------------------------------------
# 3.2.2 ÔÇö Gap Reversion Signal
# ---------------------------------------------------------------------------

class GapReversionSignal:
    """Overnight gap detection and mean-reversion signal.

    Detects the opening gap between previous session close and current
    session open.  Large gaps tend to partially revert during the first
    2 hours of trading (15-24 bars at 5-min).

    Score:
      - Large positive gap (spread opens higher) ÔåÆ negative score (sell)
      - Large negative gap (spread opens lower)  ÔåÆ positive score (buy)
    """

    def __init__(
        self,
        gap_threshold: float = 0.005,
        reversion_bars: int = 24,
        scale: float = 0.02,
    ):
        """
        Args:
            gap_threshold: Minimum gap % to generate a signal.
            reversion_bars: Window (in 5-min bars) for gap to revert
                            (24 bars = 2 hours).
            scale: Normalisation denominator for gap magnitude.
        """
        self.gap_threshold = gap_threshold
        self.reversion_bars = reversion_bars
        self.scale = scale

    def compute_score(
        self,
        spread: pd.Series,
        bars_since_open: int,
    ) -> float:
        """Compute gap reversion score.

        Args:
            spread: Intraday spread series for *today* (from market open).
            bars_since_open: How many 5-min bars since today's open.

        Returns:
            Score in [-1, 1], or 0.0 outside the reversion window.
        """
        if len(spread) < 2 or bars_since_open > self.reversion_bars:
            return 0.0  # Outside reversion window

        open_val = spread.iloc[0]
        if abs(open_val) < 1e-10:
            return 0.0

        # Gap between yesterday's close and today's open
        # Approximation: use first bar as "open", detect deviation from mean
        gap_pct = (spread.iloc[0] - spread.mean()) / abs(spread.mean()) if abs(spread.mean()) > 1e-10 else 0.0

        if abs(gap_pct) < self.gap_threshold:
            return 0.0

        # Decay: signal weakens as we move through the reversion window
        decay = max(0.0, 1.0 - bars_since_open / self.reversion_bars)

        score = -(gap_pct / self.scale) * decay
        return float(np.clip(score, -1.0, 1.0))


# ---------------------------------------------------------------------------
# 3.2.3 ÔÇö Volume Profile Signal
# ---------------------------------------------------------------------------

class VolumeProfileSignal:
    """Volume-weighted spread confirmation signal.

    Compares volume at the current spread level to normal volume.
    High volume at extreme spread levels confirms mean-reversion
    opportunities (institutional flow absorbing dislocation).

    Score:
      - High volume at low spread ÔåÆ positive (buy confirmation)
      - High volume at high spread ÔåÆ negative (sell confirmation)
    """

    def __init__(
        self,
        lookback: int = 20,
        volume_threshold: float = 1.5,
    ):
        """
        Args:
            lookback: Rolling window for volume average.
            volume_threshold: Volume multiple to consider "high".
        """
        self.lookback = lookback
        self.volume_threshold = volume_threshold

    def compute_score(
        self,
        spread: pd.Series,
        volume_a: pd.Series,
        volume_b: pd.Series,
    ) -> float:
        """Compute volume-weighted spread confirmation score.

        Args:
            spread: Spread series (intraday 5-min).
            volume_a: Volume of leg A.
            volume_b: Volume of leg B.

        Returns:
            Score in [-1, 1].
        """
        if len(spread) < self.lookback or len(volume_a) < self.lookback:
            return 0.0

        # Combined volume
        vol_combined = (volume_a + volume_b).iloc[-self.lookback:]
        vol_mean = vol_combined.mean()
        if vol_mean < 1e-10:
            return 0.0

        current_vol = vol_combined.iloc[-1]
        vol_ratio = current_vol / vol_mean

        # Spread z-score
        s = spread.iloc[-self.lookback:]
        mu = s.mean()
        sigma = s.std()
        if sigma < 1e-10:
            return 0.0

        z = (spread.iloc[-1] - mu) / sigma

        # Signal: if volume is above threshold AND spread is dislocated
        if vol_ratio < self.volume_threshold:
            return 0.0  # Not enough volume confirmation

        # High vol at extreme spread ÔåÆ confirmation of reversion opportunity
        # Large negative z + high volume ÔåÆ buy; large positive z + high volume ÔåÆ sell
        score = -z * min(vol_ratio / self.volume_threshold, 2.0) / 3.0
        return float(np.clip(score, -1.0, 1.0))


# ---------------------------------------------------------------------------
# Composite intraday signal wrapper
# ---------------------------------------------------------------------------

@dataclass
class IntradaySignalResult:
    """Aggregated intraday signal output."""
    intraday_mr_score: float = 0.0
    gap_score: float = 0.0
    volume_score: float = 0.0
    composite_intraday: float = 0.0


class IntradaySignalEngine:
    """Wraps all three intraday signals into a single interface.

    Produces a single ``intraday_mr`` score for the SignalCombiner
    by blending the three sub-signals.

    Default sub-weights:
        - Intraday MR:  0.50  (primary)
        - Gap reversion: 0.25
        - Volume profile: 0.25
    """

    def __init__(
        self,
        mr_weight: float = 0.50,
        gap_weight: float = 0.25,
        vol_weight: float = 0.25,
        mr_lookback: int = 15,
        gap_threshold: float = 0.005,
        gap_reversion_bars: int = 24,
        vol_lookback: int = 20,
    ):
        self.mr = IntradayMeanReversionSignal(lookback=mr_lookback)
        self.gap = GapReversionSignal(gap_threshold=gap_threshold, reversion_bars=gap_reversion_bars)
        self.vol = VolumeProfileSignal(lookback=vol_lookback)

        self.mr_weight = mr_weight
        self.gap_weight = gap_weight
        self.vol_weight = vol_weight

    def compute(
        self,
        spread: pd.Series,
        bars_since_open: int = 0,
        volume_a: pd.Series | None = None,
        volume_b: pd.Series | None = None,
    ) -> IntradaySignalResult:
        """Compute composite intraday signal.

        Args:
            spread: Intraday spread series (5-min bars).
            bars_since_open: Bars since session open (for gap reversion).
            volume_a: Volume series for leg A (optional).
            volume_b: Volume series for leg B (optional).

        Returns:
            IntradaySignalResult with individual and composite scores.
        """
        mr_score = self.mr.compute_score(spread)
        gap_score = self.gap.compute_score(spread, bars_since_open)

        vol_score = 0.0
        active_weight = self.mr_weight + self.gap_weight
        if volume_a is not None and volume_b is not None:
            vol_score = self.vol.compute_score(spread, volume_a, volume_b)
            active_weight += self.vol_weight

        if active_weight < 1e-10:
            composite = 0.0
        else:
            composite = (
                self.mr_weight * mr_score
                + self.gap_weight * gap_score
                + (self.vol_weight * vol_score if volume_a is not None else 0.0)
            ) / active_weight

        composite = float(np.clip(composite, -1.0, 1.0))

        return IntradaySignalResult(
            intraday_mr_score=mr_score,
            gap_score=gap_score,
            volume_score=vol_score,
            composite_intraday=composite,
        )


__all__ = [
    "IntradayMeanReversionSignal",
    "GapReversionSignal",
    "VolumeProfileSignal",
    "IntradaySignalEngine",
    "IntradaySignalResult",
]
