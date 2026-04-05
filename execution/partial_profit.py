"""
<<<<<<< HEAD
Partial profit-taking (Phase 3 ��� addresses audit -�4.4).
=======
Partial profit-taking (Phase 3 – addresses audit §4.4).
>>>>>>> origin/main

Problem
-------
The strategy exits positions in an all-or-nothing fashion.
When the spread reverts to mean, the full position is closed.
This forfeits potential continuation and does not lock in gains.

Solution
--------
A two-stage exit:

1. **First take-profit**: When unrealised profit reaches ``first_tp_pct``
   of notional, close ``first_tp_fraction`` of the position.
2. **Remainder**: Continues with a tighter trailing stop.  The remaining
   position is closed when the normal exit signal fires *or* when
   profit falls back to ``remainder_stop_pct`` of the peak profit.

This is modelled as a **position overlay** that the simulator queries
on every bar *before* processing exit signals.
"""

from __future__ import annotations

from dataclasses import dataclass
<<<<<<< HEAD

=======
from typing import Dict, Optional, Tuple
>>>>>>> origin/main
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class PartialProfitConfig:
    """Configuration for partial profit-taking."""

    first_tp_pct: float = 0.015
    """Unrealised profit as fraction of notional to trigger the first
    take-profit (default 1.5 %)."""

    first_tp_fraction: float = 0.50
<<<<<<< HEAD
    """Fraction of the position to close at first take-profit (0���1)."""
=======
    """Fraction of the position to close at first take-profit (0↓1)."""
>>>>>>> origin/main

    remainder_stop_pct: float = 0.005
    """If remaining position profit falls below this fraction of notional
    (measured from peak profit), force-close the remainder.  Set to 0
    to disable (rely on normal exit signals only)."""

    enabled: bool = True
    """Master switch."""


@dataclass
class _PositionTPState:
    """Internal tracking state for a single position."""

    first_tp_done: bool = False
    """Whether the first take-profit has been triggered."""

    peak_profit_pct: float = 0.0
    """Highest observed unrealised profit as fraction of notional."""

    realized_from_partial: float = 0.0
    """Cumulative P&L realised from partial closes (not yet accounted
    for in the main portfolio)."""


class PartialProfitManager:
    """
    Manages staged profit-taking across all open positions.

    On every bar the simulator calls :pymeth:`check` for each position.
    The return value tells the simulator:

<<<<<<< HEAD
    * ``(0.0, False)`` ��� do nothing.
    * ``(fraction, False)`` ��� close *fraction* of the position and keep
      the remainder open.
    * ``(1.0, True)`` ��� close the *entire* remaining position (remainder
      stop triggered).
    """

    def __init__(self, config: PartialProfitConfig | None = None):
        self.config = config or PartialProfitConfig()
        self._states: dict[str, _PositionTPState] = {}
=======
    * ``(0.0, False)`` – do nothing.
    * ``(fraction, False)`` – close *fraction* of the position and keep
      the remainder open.
    * ``(1.0, True)`` – close the *entire* remaining position (remainder
      stop triggered).
    """

    def __init__(self, config: Optional[PartialProfitConfig] = None):
        self.config = config or PartialProfitConfig()
        self._states: Dict[str, _PositionTPState] = {}
>>>>>>> origin/main

    def register(self, pair_key: str) -> None:
        """Register a new position."""
        self._states[pair_key] = _PositionTPState()

    def remove(self, pair_key: str) -> None:
        """Remove tracking for a closed position."""
        self._states.pop(pair_key, None)

    def check(
        self,
        pair_key: str,
        unrealised_pnl: float,
        notional: float,
<<<<<<< HEAD
    ) -> tuple[float, bool]:
=======
    ) -> Tuple[float, bool]:
>>>>>>> origin/main
        """
        Check whether a partial (or full remainder) close should happen.

        Args:
            pair_key: Position identifier.
            unrealised_pnl: Current gross unrealised P&L for the position.
            notional: Current position notional (may have been reduced by
                a previous partial close).

        Returns:
            (close_fraction, force_close_all)
<<<<<<< HEAD
            - close_fraction: fraction of current position to close (0���1).
=======
            - close_fraction: fraction of current position to close (0↓1).
>>>>>>> origin/main
            - force_close_all: if True, close the entire remaining position.
        """
        if not self.config.enabled or notional <= 0:
            return (0.0, False)

        state = self._states.get(pair_key)
        if state is None:
            return (0.0, False)

        profit_pct = unrealised_pnl / notional

        # Track peak profit
        if profit_pct > state.peak_profit_pct:
            state.peak_profit_pct = profit_pct

        # --- Stage 1: first take-profit ---------------------------------
        if not state.first_tp_done and profit_pct >= self.config.first_tp_pct:
            state.first_tp_done = True
            logger.debug(
                "partial_profit_first_tp",
                pair=pair_key,
                profit_pct=f"{profit_pct:.3%}",
                close_fraction=self.config.first_tp_fraction,
            )
            return (self.config.first_tp_fraction, False)

        # --- Stage 2: remainder trailing stop ---------------------------
        if (
            state.first_tp_done
            and self.config.remainder_stop_pct > 0
            and state.peak_profit_pct > 0
        ):
            # If profit has decayed below the remainder stop threshold
            if profit_pct <= self.config.remainder_stop_pct:
                logger.debug(
                    "partial_profit_remainder_stop",
                    pair=pair_key,
                    profit_pct=f"{profit_pct:.3%}",
                    peak_pct=f"{state.peak_profit_pct:.3%}",
                    stop_pct=f"{self.config.remainder_stop_pct:.3%}",
                )
                return (1.0, True)

        return (0.0, False)

    def is_first_tp_done(self, pair_key: str) -> bool:
        """Check if first take-profit has already been executed."""
        state = self._states.get(pair_key)
        return state.first_tp_done if state else False

    def reset(self) -> None:
        """Clear all state."""
        self._states.clear()


__all__ = [
    "PartialProfitConfig",
    "PartialProfitManager",
]
<<<<<<< HEAD

=======
>>>>>>> origin/main
