"""
Momentum Overlay — Relative strength signal for pair trading.

Computes cross-sectional relative strength between pair legs and adjusts
signal strength accordingly.  When momentum *confirms* the z-score signal
(convergence play), the signal is boosted.  When momentum *contradicts*
the z-score (divergence play), the signal is reduced.

This acts as a second alpha source, decorrelated from the cointegration
z-score, and feeds into the SignalCombiner (Etape 3).

v31 — Phase 1, Etape 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MomentumResult:
    """Output of the momentum overlay computation."""
    relative_strength: float       # RS = ret_A - ret_B over lookback
    momentum_score: float          # Normalised score in [-1, 1]
    confirms_signal: bool          # True if momentum agrees with z-score side
    adjusted_strength: float       # Final signal strength after adjustment
    raw_strength: float            # Original z-score-based strength


# ---------------------------------------------------------------------------
# MomentumOverlay
# ---------------------------------------------------------------------------

class MomentumOverlay:
    """
    Relative momentum overlay for pair signals.

    Calculates cross-sectional relative strength between pair legs
    and adjusts signal strength accordingly.

    Config params (from MomentumConfig):
        enabled:      bool  = True
        lookback:     int   = 20   — Rolling return window (bars)
        weight:       float = 0.30 — Momentum weight in composite score
        min_strength: float = 0.30 — Floor for contra-momentum signals
        max_boost:    float = 1.00 — Cap for momentum-confirmed signals
    """

    def __init__(
        self,
        lookback: int = 20,
        weight: float = 0.30,
        min_strength: float = 0.30,
        max_boost: float = 1.0,
    ):
        if lookback < 2:
            raise ValueError(f"lookback must be >= 2, got {lookback}")
        if not 0.0 <= weight <= 1.0:
            raise ValueError(f"weight must be in [0, 1], got {weight}")
        if not 0.0 <= min_strength <= 1.0:
            raise ValueError(f"min_strength must be in [0, 1], got {min_strength}")
        if not 0.0 <= max_boost <= 1.0:
            raise ValueError(f"max_boost must be in [0, 1], got {max_boost}")

        self.lookback = lookback
        self.weight = weight
        self.min_strength = min_strength
        self.max_boost = max_boost

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_relative_strength(
        self,
        prices_a: pd.Series,
        prices_b: pd.Series,
        lookback: Optional[int] = None,
    ) -> float:
        """
        Compute relative strength: RS = return_A(lookback) - return_B(lookback).

        A positive RS means A outperformed B over the lookback window.

        Args:
            prices_a: Price series for leg A.
            prices_b: Price series for leg B.
            lookback: Override lookback (default: self.lookback).

        Returns:
            Float RS value.  Returns 0.0 if insufficient data.
        """
        lb = lookback or self.lookback

        if len(prices_a) < lb + 1 or len(prices_b) < lb + 1:
            return 0.0

        # Use log returns for better numerical properties
        ret_a = float(np.log(prices_a.iloc[-1] / prices_a.iloc[-lb - 1]))
        ret_b = float(np.log(prices_b.iloc[-1] / prices_b.iloc[-lb - 1]))

        return ret_a - ret_b

    def compute_momentum_score(
        self,
        prices_a: pd.Series,
        prices_b: pd.Series,
        lookback: Optional[int] = None,
    ) -> float:
        """
        Compute normalised momentum score in [-1, 1].

        Uses tanh to smoothly bound the relative strength.

        Args:
            prices_a: Price series for leg A.
            prices_b: Price series for leg B.
            lookback: Override lookback.

        Returns:
            Score in [-1, 1] where positive = A outperforms B.
        """
        rs = self.compute_relative_strength(prices_a, prices_b, lookback)
        # Scale RS by 10 to get reasonable tanh sensitivity
        # (typical RS for equities over 20 days is +-0.05 to +-0.15)
        return float(np.tanh(rs * 10.0))

    def adjust_signal_strength(
        self,
        side: str,
        raw_strength: float,
        prices_a: pd.Series,
        prices_b: pd.Series,
        lookback: Optional[int] = None,
    ) -> MomentumResult:
        """
        Adjust signal strength based on relative momentum.

        Logic:
            For a LONG signal (long A, short B):
                - RS < 0 (A underperformed) -> WITH momentum -> boost
                - RS > 0 (A outperformed)   -> CONTRA momentum -> reduce

            For a SHORT signal (short A, long B):
                - RS > 0 (A outperformed)   -> WITH momentum -> boost
                - RS < 0 (A underperformed) -> CONTRA momentum -> reduce

            For EXIT signals: no adjustment (pass-through).

        Args:
            side: "long", "short", or "exit".
            raw_strength: Original signal strength (0-1).
            prices_a: Prices for leg A (the first symbol in the pair).
            prices_b: Prices for leg B (the second symbol in the pair).
            lookback: Override lookback window.

        Returns:
            MomentumResult with adjusted strength.
        """
        rs = self.compute_relative_strength(prices_a, prices_b, lookback)
        m_score = float(np.tanh(rs * 10.0))

        # Exit signals: pass-through unchanged
        if side == "exit":
            return MomentumResult(
                relative_strength=rs,
                momentum_score=m_score,
                confirms_signal=True,
                adjusted_strength=raw_strength,
                raw_strength=raw_strength,
            )

        # Determine if momentum confirms the signal
        if side == "long":
            # Long A, short B: want A to *underperform* (RS < 0) for convergence
            confirms = rs < 0
        elif side == "short":
            # Short A, long B: want A to *outperform* (RS > 0) for convergence
            confirms = rs > 0
        else:
            # Unknown side: pass-through
            return MomentumResult(
                relative_strength=rs,
                momentum_score=m_score,
                confirms_signal=False,
                adjusted_strength=raw_strength,
                raw_strength=raw_strength,
            )

        # Compute adjustment factor
        abs_score = abs(m_score)

        if confirms:
            # Momentum confirms -> boost strength toward max_boost
            boost = self.weight * abs_score
            adjusted = min(raw_strength + boost, self.max_boost)
        else:
            # Momentum contradicts -> reduce strength toward min_strength
            penalty = self.weight * abs_score
            adjusted = max(raw_strength - penalty, self.min_strength)

        adjusted = float(np.clip(adjusted, 0.0, 1.0))

        logger.debug(
            "momentum_adjustment",
            side=side,
            rs=f"{rs:.4f}",
            m_score=f"{m_score:.3f}",
            confirms=confirms,
            raw=f"{raw_strength:.3f}",
            adjusted=f"{adjusted:.3f}",
        )

        return MomentumResult(
            relative_strength=rs,
            momentum_score=m_score,
            confirms_signal=confirms,
            adjusted_strength=adjusted,
            raw_strength=raw_strength,
        )
