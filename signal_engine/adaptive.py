"""
Adaptive Threshold Engine ÔÇö Regime-aware entry/exit thresholds.

Wraps the proven ``models.adaptive_thresholds.AdaptiveThresholdCalculator``
and ``models.regime_detector.RegimeDetector`` into a unified interface.

Provides a single ``get_thresholds()`` call that returns the optimal
entry and exit z-score thresholds for the current market regime and
pair characteristics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd
from structlog import get_logger

from models.adaptive_thresholds import (
    AdaptiveThresholdCalculator,
    ThresholdConfig,
)
from models.regime_detector import VolatilityRegime

logger = get_logger(__name__)


@dataclass
class ThresholdResult:
    """Adaptive threshold recommendation for a single pair."""

    entry_threshold: float
    exit_threshold: float
    regime: VolatilityRegime
    adjustments: dict[str, float]


class AdaptiveThresholdEngine:
    """
    Unified adaptive threshold calculation.

    Combines:
        - Spread volatility percentile assessment
        - Half-life based adjustment
        - Volatility regime overlay

    Usage::

        engine = AdaptiveThresholdEngine()
        result = engine.get_thresholds(
            spread=spread_series,
            half_life=25.0,
            regime=VolatilityRegime.NORMAL,
        )
        # result.entry_threshold ÔåÆ 2.0 (adjusted)
        # result.exit_threshold  ÔåÆ 0.0 (adjusted)
    """

    def __init__(
        self,
        base_entry: float = 2.0,
        base_exit: float = 0.5,
        min_entry: float = 1.0,
        max_entry: float = 3.5,
        config: ThresholdConfig | None = None,
    ):
        self._config = config or ThresholdConfig(
            base_entry_threshold=base_entry,
            base_exit_threshold=base_exit,
            min_entry_threshold=min_entry,
            max_entry_threshold=max_entry,
        )
        self._calculator = AdaptiveThresholdCalculator(self._config)

    def get_thresholds(
        self,
        spread: pd.Series,
        half_life: float | None = None,
        regime: VolatilityRegime | None = None,
    ) -> ThresholdResult:
        """
        Calculate adaptive entry/exit thresholds.

        Args:
            spread: Historical spread series (used for vol assessment).
            half_life: Pair half-life in days.
            regime: Current volatility regime.  If *None*, regime is
                not used for adjustment.

        Returns:
            ThresholdResult with entry/exit thresholds and diagnostics.
        """
        entry, exit_t, details = self._calculator.calculate_threshold(
            spread=spread,
            half_life=half_life,
        )

        # Regime overlay
        if regime is not None:
            regime_adj = self._regime_adjustment(regime)
            entry += regime_adj
            details["regime_adjustment"] = regime_adj
            details["regime"] = regime.value

        # Enforce bounds
        entry = max(self._config.min_entry_threshold, min(entry, self._config.max_entry_threshold))

        detected_regime = regime or VolatilityRegime.NORMAL

        return ThresholdResult(
            entry_threshold=entry,
            exit_threshold=exit_t,
            regime=detected_regime,
            adjustments=details,
        )

    @staticmethod
    def _regime_adjustment(regime: VolatilityRegime) -> float:
        """
        Regime-based threshold shift.

        LOW vol  ÔåÆ lower entry (spreads revert fast)  ÔåÆ -0.3
        NORMAL   ÔåÆ no adjustment                      ÔåÆ  0.0
        HIGH vol ÔåÆ higher entry (wider excursions)     ÔåÆ +0.5
        """
        if regime == VolatilityRegime.LOW:
            return -0.3
        elif regime == VolatilityRegime.HIGH:
            return 0.5
        return 0.0

    def apply_dispersion_adjustment(
        self,
        result: ThresholdResult,
        disp_idx: float,
        ideal_disp: float = 0.30,
        min_disp: float = 0.15,
        max_adj: float = 0.50,
    ) -> ThresholdResult:
        """C-09: Raise entry threshold when market dispersion is sub-ideal.

        Maps the dispersion index to a z-score penalty:
        - disp >= ideal_disp  → no adjustment
        - min_disp <= disp < ideal_disp → linear ramp 0 → max_adj
        - disp < min_disp     → should already be blocked by C-02

        Args:
            result: Base ThresholdResult from get_thresholds().
            disp_idx: Current pairwise correlation std (dispersion index).
            ideal_disp: Dispersion above which no adjustment applies.
            min_disp: Dispersion floor (C-02 blocking threshold).
            max_adj: Maximum z-score raise applied at min_disp boundary.

        Returns:
            New ThresholdResult with adjusted entry_threshold.
        """
        if disp_idx >= ideal_disp or ideal_disp <= min_disp:
            return result

        # Linear ramp: 0 at ideal_disp, max_adj at min_disp
        t = (ideal_disp - disp_idx) / (ideal_disp - min_disp)
        adj = max_adj * max(0.0, min(1.0, t))
        new_entry = max(
            self._config.min_entry_threshold,
            min(result.entry_threshold + adj, self._config.max_entry_threshold),
        )

        new_adjustments = dict(result.adjustments)
        new_adjustments["dispersion_adj"] = round(adj, 4)
        new_adjustments["dispersion_idx"] = round(disp_idx, 4)

        logger.debug(
            "adaptive_threshold_dispersion_adj",
            disp_idx=round(disp_idx, 4),
            adj=round(adj, 4),
            entry_before=round(result.entry_threshold, 4),
            entry_after=round(new_entry, 4),
        )

        return ThresholdResult(
            entry_threshold=new_entry,
            exit_threshold=result.exit_threshold,
            regime=result.regime,
            adjustments=new_adjustments,
        )
