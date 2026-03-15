"""
Time Stop Manager ÔÇô Sprint 1.5 (fixes C-05: no max holding period).

Problem
-------
Without a time-based exit, positions that fail to mean-revert stay open
indefinitely, accumulating borrowing costs and opportunity cost.
Statistical arbitrage positions that haven't reverted by 2├ù half-life
have a high probability of regime change (broken cointegration).

Solution
--------
For each pair with estimated half-life *h*, the maximum holding period is::

    max_bars = min(half_life_multiplier * h, MAX_DAYS_CAP)

After ``max_bars`` the position is **force-closed regardless of P&L**.

Post-v27 fix (├ëtape 5): multiplier reduced from 3.0 ÔåÆ 2.0.  The 5 time
stops in v27 (avg 22-day holding) cost -$17,912.  Cutting earlier at 2├ù HL
limits exposure to divergent spreads.

   ============  ====  ========================
   half_life (h)  cap   max_holding_bars
   ============  ====  ========================
   15             60    30  (= 2 ├ù 15)
   40             60    60  (= min(80, 60))
   None           60    60  (fallback to cap)
   ============  ====  ========================

Expected Impact: prevents tail-end drag from zombie positions,
reduces average holding period, improves capital efficiency.
"""

from dataclasses import dataclass
from typing import Optional
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class TimeStopConfig:
    """Configuration for time-based stop."""

    half_life_multiplier: float = 2.0
    """Close after ``multiplier ├ù half_life`` bars.  Post-v27: 2.0 (was 3.0)."""

    max_days_cap: int = 60
    """Absolute ceiling regardless of half-life."""

    default_max_bars: int = 60
    """Fallback when half-life is ``None``."""


class TimeStopManager:
    """
    Decides whether a position has exceeded its time-based stop.

    Usage::

        tsm = TimeStopManager()
        max_bars = tsm.max_holding_bars(half_life=25)  # Ôåô 50
        # Each bar check:
        should_close, reason = tsm.should_exit(holding_bars=51, half_life=25)
    """

    def __init__(self, config: Optional[TimeStopConfig] = None):
        self.config = config or TimeStopConfig()
        logger.info(
            "time_stop_manager_initialized",
            multiplier=self.config.half_life_multiplier,
            cap=self.config.max_days_cap,
            default=self.config.default_max_bars,
        )

    def max_holding_bars(self, half_life: Optional[int] = None) -> int:
        """Return the maximum number of bars a position may be held.

        Args:
            half_life: Estimated half-life of mean reversion (bars/days).
                       ``None`` Ôåô use ``default_max_bars`` from config.

        Returns:
            int ÔÇô strict upper bound on holding period.
        """
        if half_life is None or half_life <= 0:
            return self.config.default_max_bars

        raw = int(self.config.half_life_multiplier * half_life)
        return min(raw, self.config.max_days_cap)

    def should_exit(
        self,
        holding_bars: int,
        half_life: Optional[int] = None,
    ) -> tuple:
        """Check whether the position should be force-closed.

        Args:
            holding_bars: How many bars the position has been open.
            half_life: Pair half-life (used to compute limit).

        Returns:
            (should_exit: bool, reason: str | None)
        """
        limit = self.max_holding_bars(half_life)

        if holding_bars >= limit:
            reason = (
                f"TIME_STOP: held {holding_bars} bars >= limit "
                f"{limit} (hl={half_life}, mult={self.config.half_life_multiplier}, "
                f"cap={self.config.max_days_cap})"
            )
            return True, reason

        return False, None
