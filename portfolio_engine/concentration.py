<<<<<<< HEAD
﻿"""
Concentration Manager ÔÇö Per-symbol concentration enforcement.
=======
"""
Concentration Manager — Per-symbol concentration enforcement.
>>>>>>> origin/main

Wraps ``execution.concentration_limits.ConcentrationLimitManager``
into the modular portfolio engine with a cleaner interface.

Prevents excessive exposure to individual symbols across multiple
pair positions (e.g. AAPL_MSFT + AAPL_GOOGL + AAPL_AMZN
would create 50%+ AAPL concentration).
"""

from __future__ import annotations

<<<<<<< HEAD
=======
from typing import Dict, Optional, Tuple

>>>>>>> origin/main
from structlog import get_logger

from execution.concentration_limits import ConcentrationLimitManager

logger = get_logger(__name__)


class ConcentrationManager:
    """
    Portfolio-level symbol concentration enforcement.

    Delegates to the proven ``ConcentrationLimitManager`` while
    providing the portfolio engine's clean API contract.

    Usage::

        cm = ConcentrationManager(max_pct=30.0)
        ok, reason = cm.check_entry("AAPL_MSFT", "AAPL", "MSFT", "long")
        if ok:
            cm.register_entry(...)
    """

    def __init__(self, max_concentration_pct: float = 30.0):
        self._inner = ConcentrationLimitManager(
            max_symbol_concentration_pct=max_concentration_pct,
            allow_rebalancing=True,
        )

    def check_entry(
        self,
        pair_key: str,
        symbol1: str,
        symbol2: str,
        side: str,
        notional: float = 1.0,
<<<<<<< HEAD
    ) -> tuple[bool, str | None]:
=======
    ) -> Tuple[bool, Optional[str]]:
>>>>>>> origin/main
        """
        Check if a new position would breach concentration limits.

        Returns:
            (allowed, reason).
        """
        return self._inner.add_position(
            pair_key=pair_key,
            symbol1=symbol1,
            symbol2=symbol2,
            side=side,
            notional=notional,
        )

    def register_exit(self, pair_key: str) -> None:
        """Release concentration capacity on position exit."""
        self._inner.remove_position(pair_key)

<<<<<<< HEAD
    def get_symbol_exposures(self) -> dict:
        """Return current per-symbol exposure map."""
        return dict(self._inner.symbol_exposures)

    def most_concentrated_symbol(self) -> str | None:
=======
    def get_symbol_exposures(self) -> Dict:
        """Return current per-symbol exposure map."""
        return dict(self._inner.symbol_exposures)

    def most_concentrated_symbol(self) -> Optional[str]:
>>>>>>> origin/main
        """Return symbol with highest gross exposure, or None."""
        exposures = self._inner.symbol_exposures
        if not exposures:
            return None
        return max(exposures, key=lambda s: exposures[s].gross_exposure)
