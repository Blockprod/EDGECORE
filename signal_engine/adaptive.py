"""
Adaptive Threshold Engine — Regime-aware entry/exit thresholds.

Wraps the proven ``models.adaptive_thresholds.AdaptiveThresholdCalculator``
and ``models.regime_detector.RegimeDetector`` into a unified interface.

Provides a single ``get_thresholds()`` call that returns the optimal
entry and exit z-score thresholds for the current market regime and
pair characteristics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pandas as pd
from structlog import get_logger

from models.adaptive_thresholds import (
    AdaptiveThresholdCalculator,
    ThresholdConfig,
)
from models.regime_detector import RegimeDetector, VolatilityRegime

logger = get_logger(__name__)


@dataclass
class ThresholdResult:
    """Adaptive threshold recommendation for a single pair."""
    entry_threshold: float
    exit_threshold: float
    regime: VolatilityRegime
    adjustments: Dict[str, float]


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
        # result.entry_threshold → 2.0 (adjusted)
        # result.exit_threshold  → 0.0 (adjusted)
    """

    def __init__(
        self,
        base_entry: float = 2.0,
        base_exit: float = 0.5,
        min_entry: float = 1.0,
        max_entry: float = 3.5,
        config: Optional[ThresholdConfig] = None,
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
        half_life: Optional[float] = None,
        regime: Optional[VolatilityRegime] = None,
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

        LOW vol  → lower entry (spreads revert fast)  → -0.3
        NORMAL   → no adjustment                      →  0.0
        HIGH vol → higher entry (wider excursions)     → +0.5
        """
        if regime == VolatilityRegime.LOW:
            return -0.3
        elif regime == VolatilityRegime.HIGH:
            return 0.5
        return 0.0
