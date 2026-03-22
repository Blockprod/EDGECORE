"""
Simulated order-book for bar-by-bar backtesting.

Provides :class:`SimulatedOrderBook`, a typed wrapper around the raw
``positions`` dictionary used throughout :mod:`backtests.strategy_simulator`.

Why a dedicated module?
- Centralises all position P&L utilities (unrealised PnL, portfolio heat,
  weakest-positions ranking) that were previously scattered as private methods
  on ``StrategyBacktestSimulator``.
- Makes the positions contract explicit: every entry goes through :meth:`open`,
  every close through :meth:`close` (or the backward-compatible :meth:`pop`).
- Enables independent unit-testing of position accounting logic.
"""

from __future__ import annotations

from typing import Iterator

import pandas as pd

# ---------------------------------------------------------------------------
# Module-level P&L utilities (used by SimulatedOrderBook and importable
# directly by other modules without creating an OrderBook instance).
# ---------------------------------------------------------------------------


def unrealized_pnl(pos: dict, prices_df: pd.DataFrame, bar_idx: int) -> float:
    """Return mark-to-market unrealised P&L for a single pair position.

    Args:
        pos: Position dict as stored in :class:`SimulatedOrderBook`.
        prices_df: Full price DataFrame (columns = symbols).
        bar_idx: Current bar index into *prices_df*.

    Returns:
        Signed P&L in portfolio currency (same units as ``pos["notional"]``).
    """
    sym1, sym2 = pos["sym1"], pos["sym2"]
    cur_p1 = prices_df[sym1].iloc[bar_idx]
    cur_p2 = prices_df[sym2].iloc[bar_idx]
    ep1, ep2 = pos["entry_price_1"], pos["entry_price_2"]
    n1 = pos.get("notional_1", pos["notional"] / 2.0)
    n2 = pos.get("notional_2", pos["notional"] / 2.0)
    if pos["side"] == "long":
        r1 = (cur_p1 - ep1) / ep1 if ep1 else 0.0
        r2 = (ep2 - cur_p2) / ep2 if ep2 else 0.0
    else:
        r1 = (ep1 - cur_p1) / ep1 if ep1 else 0.0
        r2 = (cur_p2 - ep2) / ep2 if ep2 else 0.0
    return n1 * r1 + n2 * r2


# ---------------------------------------------------------------------------
# SimulatedOrderBook
# ---------------------------------------------------------------------------


class SimulatedOrderBook:
    """
    Tracks open pair positions for bar-by-bar backtest simulation.

    This is a typed, dict-compatible wrapper around ``positions: Dict[str, dict]``.
    It exposes the same interface as a plain dict (``__getitem__``,
    ``__setitem__``, ``pop``, ``keys``, ``values``, ``items``, ``__contains__``,
    ``__len__``, ``__iter__``) so it can be used as a drop-in replacement with
    minimal changes to existing code.

    New semantic methods (preferred in new code):
    - :meth:`open`  – record a new position.
    - :meth:`close` – remove and return a closed position.
    - :meth:`portfolio_heat` – aggregate risk budget consumed.
    - :meth:`weakest_positions` – rank positions by unrealised P&L.
    """

    def __init__(self) -> None:
        self._positions: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Semantic position lifecycle API
    # ------------------------------------------------------------------

    def open(self, pair_key: str, position: dict) -> None:
        """Record a new open position."""
        self._positions[pair_key] = position

    def close(self, pair_key: str) -> dict:
        """Remove and return a closed position.

        Raises:
            KeyError: if *pair_key* is not currently open.
        """
        return self._positions.pop(pair_key)

    def get(self, pair_key: str) -> dict | None:
        """Return a position without removing it, or ``None`` if absent."""
        return self._positions.get(pair_key)

    # ------------------------------------------------------------------
    # P&L utilities
    # ------------------------------------------------------------------

    def position_unrealized_pnl(self, pair_key: str, prices_df: pd.DataFrame, bar_idx: int) -> float:
        """Unrealised P&L for a single named position (0.0 if absent)."""
        pos = self._positions.get(pair_key)
        if pos is None:
            return 0.0
        return unrealized_pnl(pos, prices_df, bar_idx)

    def portfolio_heat(self, portfolio_value: float) -> float:
        """Return aggregate position notional / portfolio value.

        A value of 0.20 means 20 % of the portfolio is currently exposed as
        gross notional.  Returns 0.0 when the portfolio has no value or there
        are no open positions.
        """
        if portfolio_value <= 0.0 or not self._positions:
            return 0.0
        total_notional = sum(p["notional"] for p in self._positions.values())
        return total_notional / portfolio_value

    def weakest_positions(
        self,
        prices_df: pd.DataFrame,
        bar_idx: int,
        n: int,
    ) -> list[str]:
        """Return pair keys of the *n* positions with the lowest unrealised P&L.

        Used by the drawdown-manager tier-2 handler to close the weakest
        positions first.
        """
        return sorted(
            self._positions.keys(),
            key=lambda pk: unrealized_pnl(self._positions[pk], prices_df, bar_idx),
        )[:n]

    # ------------------------------------------------------------------
    # Backward-compatible dict interface
    # ------------------------------------------------------------------

    def pop(self, pair_key: str) -> dict:
        """Remove and return a position (backward-compatible alias for :meth:`close`)."""
        return self._positions.pop(pair_key)

    def keys_list(self) -> list[str]:
        return list(self._positions.keys())

    def values_list(self) -> list[dict]:
        return list(self._positions.values())

    def items_list(self) -> list[tuple[str, dict]]:
        return list(self._positions.items())

    def __len__(self) -> int:
        return len(self._positions)

    def __contains__(self, pair_key: object) -> bool:
        return pair_key in self._positions

    def __iter__(self) -> Iterator[str]:
        return iter(list(self._positions.keys()))

    def __getitem__(self, pair_key: str) -> dict:
        return self._positions[pair_key]

    def __setitem__(self, pair_key: str, position: dict) -> None:
        """Backward-compatible direct assignment (prefer :meth:`open`)."""
        self._positions[pair_key] = position

    def __bool__(self) -> bool:
        return bool(self._positions)


__all__ = ["SimulatedOrderBook", "unrealized_pnl"]
