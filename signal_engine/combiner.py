"""
Signal Combiner ÔÇö Weighted ensemble of multiple signal sources.

Provides infrastructure to combine N alpha sources (z-score, momentum,
intraday MR, options skew, etc.) into a single composite score that
drives entry/exit decisions.

Extensible design: add a new signal source by appending a SignalSource
to the combiner's source list.  No existing code needs to change.

v31 ÔÇö Phase 1, Etape 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from structlog import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SignalSource:
    """
    Definition of a single signal source in the ensemble.

    Attributes:
        name:    Unique identifier (e.g. "zscore", "momentum").
        weight:  Contribution to the composite score (>= 0).
        enabled: Whether this source is active.
    """
    name: str
    weight: float
    enabled: bool = True

    def __post_init__(self):
        if self.weight < 0:
            raise ValueError(f"SignalSource weight must be >= 0, got {self.weight}")


@dataclass
class CompositeSignal:
    """
    Output of the signal combiner.

    Attributes:
        composite_score: Weighted average score in [-1, 1].
        direction:       "long" | "short" | "exit" | "none".
        source_scores:   Individual source contributions {name: score}.
        source_weights:  Weights used {name: weight}.
        confidence:      How much of the total weight was available (0-1).
    """
    composite_score: float
    direction: str
    source_scores: dict[str, float] = field(default_factory=dict)
    source_weights: dict[str, float] = field(default_factory=dict)
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# SignalCombiner
# ---------------------------------------------------------------------------

class SignalCombiner:
    """
    Weighted ensemble of multiple signal sources.

    Computes a composite score in [-1, 1] from N sources, where:
        > entry_threshold   -> LONG
        < -entry_threshold  -> SHORT
        |.| < exit_threshold -> EXIT (only when in position)
        otherwise            -> NONE

    Default sources (v31):
        - zscore:   weight 0.70  (primary alpha)
        - momentum: weight 0.30  (confirmation alpha)

    Future sources (v32/v33):
        - intraday_mr: weight TBD
        - options_skew: weight TBD

    Usage::

        combiner = SignalCombiner(
            sources=[
                SignalSource("zscore", weight=0.70),
                SignalSource("momentum", weight=0.30),
            ],
        )
        result = combiner.combine({"zscore": -0.8, "momentum": -0.5})
        # result.direction = "long" (if composite < -entry_threshold)
    """

    def __init__(
        self,
        sources: list[SignalSource] | None = None,
        entry_threshold: float = 0.6,
        exit_threshold: float = 0.2,
    ):
        if entry_threshold <= 0:
            raise ValueError(f"entry_threshold must be > 0, got {entry_threshold}")
        if exit_threshold < 0:
            raise ValueError(f"exit_threshold must be >= 0, got {exit_threshold}")
        if exit_threshold >= entry_threshold:
            raise ValueError(
                f"exit_threshold ({exit_threshold}) must be < entry_threshold ({entry_threshold})"
            )

        self.sources = sources or [
            SignalSource("zscore", weight=0.70),
            SignalSource("momentum", weight=0.30),
        ]
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

        # Build lookup dict
        self._source_map: dict[str, SignalSource] = {
            s.name: s for s in self.sources
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def combine(
        self,
        scores: dict[str, float],
        in_position: bool = False,
    ) -> CompositeSignal:
        """
        Combine raw scores from multiple sources into a composite signal.

        Args:
            scores:      Dict mapping source name to raw score.
                         Scores should be in [-1, 1] where:
                             positive = bullish on leg A (long A / short B)
                             negative = bearish on leg A (short A / long B)
            in_position: Whether currently holding a position (enables exit).

        Returns:
            CompositeSignal with direction and composite_score.

        Note:
            Sources not present in *scores* are skipped (their weight is
            excluded from the denominator).  This allows graceful degradation
            when a source has no data.
        """
        total_weight = 0.0
        weighted_sum = 0.0
        used_scores: dict[str, float] = {}
        used_weights: dict[str, float] = {}

        for source in self.sources:
            if not source.enabled:
                continue
            if source.name not in scores:
                continue

            raw_score = scores[source.name]
            # Clamp to [-1, 1]
            clamped = float(np.clip(raw_score, -1.0, 1.0))

            weighted_sum += source.weight * clamped
            total_weight += source.weight
            used_scores[source.name] = clamped
            used_weights[source.name] = source.weight

        # No active sources -> no signal
        if total_weight == 0:
            return CompositeSignal(
                composite_score=0.0,
                direction="none",
                source_scores=used_scores,
                source_weights=used_weights,
                confidence=0.0,
            )

        composite = weighted_sum / total_weight
        # Clamp final score
        composite = float(np.clip(composite, -1.0, 1.0))

        # Confidence = fraction of total configured weight that was available
        max_weight = sum(s.weight for s in self.sources if s.enabled)
        confidence = total_weight / max_weight if max_weight > 0 else 0.0

        # Direction logic
        direction = self._resolve_direction(composite, in_position)

        logger.debug(
            "signal_combined",
            composite=f"{composite:.3f}",
            direction=direction,
            confidence=f"{confidence:.2f}",
            sources=used_scores,
        )

        return CompositeSignal(
            composite_score=composite,
            direction=direction,
            source_scores=used_scores,
            source_weights=used_weights,
            confidence=confidence,
        )

    def add_source(self, source: SignalSource) -> None:
        """Add a new signal source to the ensemble."""
        self.sources.append(source)
        self._source_map[source.name] = source

    def remove_source(self, name: str) -> bool:
        """Remove a signal source by name.  Returns True if found."""
        if name in self._source_map:
            del self._source_map[name]
            self.sources = [s for s in self.sources if s.name != name]
            return True
        return False

    def set_source_enabled(self, name: str, enabled: bool) -> None:
        """Enable or disable a source by name."""
        if name in self._source_map:
            self._source_map[name].enabled = enabled

    @property
    def active_sources(self) -> list[str]:
        """Return names of enabled sources."""
        return [s.name for s in self.sources if s.enabled]

    @property
    def total_weight(self) -> float:
        """Sum of enabled source weights."""
        return sum(s.weight for s in self.sources if s.enabled)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_direction(self, composite: float, in_position: bool) -> str:
        """Map composite score to directional signal."""
        abs_score = abs(composite)

        # EXIT: composite near zero while in position
        if in_position and abs_score <= self.exit_threshold:
            return "exit"

        # ENTRY: composite exceeds threshold
        if composite > self.entry_threshold:
            return "long"
        if composite < -self.entry_threshold:
            return "short"

        return "none"
