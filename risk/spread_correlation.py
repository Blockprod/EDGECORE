"""
Spread Correlation Guard – Sprint 1.6 (fixes C-06: correlated positions).

Problem
-------
When multiple pair-trading positions have highly correlated spreads,
risk is concentrated rather than diversified.  A single adverse move
(e.g. sector rotation) can hit ALL positions simultaneously, creating
outsized drawdowns that naive position sizing ignores.

Solution
--------
Before entering a new position, compute the Pearson correlation between
the *candidate pair's spread* and every *existing position's spread*
over a rolling window.  If **any** correlation exceeds the threshold
(default 0.60), the entry is **rejected**.

    ========================  ============
    max(|ρ| with existing)     Decision
    ========================  ============
    ≤ 0.60                     ALLOW entry
    > 0.60                     REJECT entry
    ========================  ============

Expected Impact: Ensures genuine portfolio diversification.  Prevents
concentrated drawdowns from correlated mean-reversion failures.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class SpreadCorrelationConfig:
    """Configuration for the spread correlation guard."""

    max_correlation: float = 0.70
    """Reject new positions whose spread correlates above this with any
    existing active spread (absolute value)."""

    min_overlap_bars: int = 30
    """Minimum number of overlapping observations required to compute
    a valid correlation.  Below this, the guard conservatively **allows**
    the entry (insufficient data to reject)."""


class SpreadCorrelationGuard:
    """
    Rejects new entries whose spread is too correlated with existing positions.

    Usage::

        guard = SpreadCorrelationGuard()
        guard.register_spread("AAPL_MSFT", spread_series)

        allowed, reason = guard.check_entry("JPM_BAC", candidate_spread)
        if not allowed:
            # skip entry
            ...

        # On exit:
        guard.remove_spread("AAPL_MSFT")
    """

    def __init__(self, config: Optional[SpreadCorrelationConfig] = None):
        self.config = config or SpreadCorrelationConfig()
        self._spreads: Dict[str, pd.Series] = {}
        logger.info(
            "spread_correlation_guard_initialized",
            max_correlation=self.config.max_correlation,
            min_overlap=self.config.min_overlap_bars,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_spread(self, pair_key: str, spread: pd.Series) -> None:
        """Record the spread series for an actively held position.

        Called at entry time (or updated each bar if spreads are
        recomputed).  The series should be the *full* historical spread
        up to the current bar.
        """
        self._spreads[pair_key] = spread

    def remove_spread(self, pair_key: str) -> None:
        """Remove a spread when a position is closed."""
        self._spreads.pop(pair_key, None)

    def check_entry(
        self,
        candidate_key: str,
        candidate_spread: pd.Series,
    ) -> Tuple[bool, Optional[str]]:
        """Decide whether *candidate_key* may enter.

        Args:
            candidate_key: Pair key for the proposed new position.
            candidate_spread: Spread series of the candidate pair.

        Returns:
            (allowed: bool, reject_reason: str | None)
        """
        if not self._spreads:
            return True, None  # No existing positions ↓ always allowed

        worst_corr = 0.0
        worst_pair = ""

        for existing_key, existing_spread in self._spreads.items():
            if existing_key == candidate_key:
                continue  # shouldn't happen, but guard

            corr = self._correlation(candidate_spread, existing_spread)

            if corr is None:
                continue  # insufficient overlap

            abs_corr = abs(corr)
            if abs_corr > worst_corr:
                worst_corr = abs_corr
                worst_pair = existing_key

        if worst_corr > self.config.max_correlation:
            reason = (
                f"SPREAD_CORR_GUARD: |rho|={worst_corr:.3f} with {worst_pair} "
                f"> threshold {self.config.max_correlation}"
            )
            logger.info(
                "spread_correlation_entry_rejected",
                candidate=candidate_key,
                worst_pair=worst_pair,
                correlation=round(worst_corr, 4),
                threshold=self.config.max_correlation,
            )
            return False, reason

        return True, None

    @property
    def active_count(self) -> int:
        """Number of actively tracked spreads."""
        return len(self._spreads)

    def clear(self) -> None:
        """Remove all tracked spreads (e.g. between walk-forward periods)."""
        self._spreads.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _correlation(
        self,
        s1: pd.Series,
        s2: pd.Series,
    ) -> Optional[float]:
        """Pearson correlation over the overlapping tail.

        Returns ``None`` if fewer than ``min_overlap_bars`` observations
        overlap or if either series has zero variance.
        """
        # Align by index if both have one, else use tail overlap by length
        if hasattr(s1, "index") and hasattr(s2, "index"):
            common = s1.index.intersection(s2.index)
            if len(common) < self.config.min_overlap_bars:
                return None
            a = s1.loc[common].values
            b = s2.loc[common].values
        else:
            n = min(len(s1), len(s2))
            if n < self.config.min_overlap_bars:
                return None
            a = np.asarray(s1[-n:], dtype=np.float64)
            b = np.asarray(s2[-n:], dtype=np.float64)

        # Check for NaN / zero variance
        a_clean = a[~np.isnan(a) & ~np.isnan(b)]
        b_clean = b[~np.isnan(a) & ~np.isnan(b)]

        if len(a_clean) < self.config.min_overlap_bars:
            return None

        std_a = np.std(a_clean)
        std_b = np.std(b_clean)
        if std_a < 1e-12 or std_b < 1e-12:
            return None

        corr = np.corrcoef(a_clean, b_clean)[0, 1]
        if np.isnan(corr):
            return None

        return float(corr)
