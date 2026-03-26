"""
Bar-by-bar simulation loop infrastructure.

Provides lightweight helpers used by :class:`~backtests.strategy_simulator.StrategyBacktestSimulator`
to manage the walk-forward OOS window and accumulate per-run statistics.
Extracting these here keeps the simulator focused on strategy logic rather
than loop bookkeeping.

Classes
-------
OOSTracker
    Identifies Out-of-Sample bars, gates OOS daily-return collection, and
    records the trade index at which the OOS window begins.

LoopState
    Mutable container for the per-run accumulators: portfolio values,
    daily returns, and round-trip trade P&L.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import pandas as pd


@dataclass
class OOSTracker:
    """
    Tracks which bars belong to the Out-of-Sample window.

    When *oos_start_date* is ``None`` the whole run is treated as in-sample
    and no OOS collection takes place.

    Usage::

        tracker = OOSTracker(oos_start_date="2024-01-01")
        tracker.initialize(prices_df, lookback_min=60)

        for bar_idx in range(lookback_min, len(prices_df)):
            # ... simulation logic ...
            tracker.record(bar_idx, len(trades_pnl), daily_ret)

        # Post-run: use tracker.daily_returns, tracker.start_bar_idx, etc.
    """

    oos_start_date: str | None = None

    _start_bar_idx: int | None = field(default=None, init=False, repr=False)
    _trade_start_idx: int | None = field(default=None, init=False, repr=False)
    daily_returns: list[float] = field(default_factory=list, init=False)

    def initialize(self, prices_df: pd.DataFrame, lookback_min: int) -> None:
        """Locate the first OOS bar index from the price DataFrame.

        Must be called once before the simulation loop begins.

        Args:
            prices_df: Full price DataFrame with DatetimeIndex.
            lookback_min: Minimum warm-up bars required before any trading.
        """
        if self.oos_start_date is None:
            return
        _ts = cast(pd.Timestamp, pd.Timestamp(self.oos_start_date))
        candidates = [i for i, ts in enumerate(prices_df.index) if cast(pd.Timestamp, pd.Timestamp(ts)) >= _ts]
        if candidates:
            self._start_bar_idx = max(lookback_min, candidates[0])

    def is_oos(self, bar_idx: int) -> bool:
        """Return ``True`` when *bar_idx* falls inside (or after) the OOS window."""
        return self._start_bar_idx is not None and bar_idx >= self._start_bar_idx

    def record(self, bar_idx: int, trade_count: int, daily_return: float) -> None:
        """Append *daily_return* to OOS statistics when inside the OOS window.

        Also captures the trade-list index at which the OOS window begins so
        that the metrics builder can slice ``trades_pnl`` correctly.

        Args:
            bar_idx: Current bar index.
            trade_count: Current length of ``trades_pnl`` list.
            daily_return: Daily return for this bar.
        """
        if not self.is_oos(bar_idx):
            return
        if self._trade_start_idx is None:
            self._trade_start_idx = trade_count
        self.daily_returns.append(daily_return)

    # ------------------------------------------------------------------
    # Read-only properties (consumed by the metrics builder)
    # ------------------------------------------------------------------

    @property
    def start_bar_idx(self) -> int | None:
        """Index of the first OOS bar, or ``None`` when OOS is disabled."""
        return self._start_bar_idx

    @property
    def trade_start_idx(self) -> int | None:
        """Index into ``trades_pnl`` at which OOS trades begin, or ``None``."""
        return self._trade_start_idx


@dataclass
class LoopState:
    """
    Mutable accumulators for a single backtest run.

    Passed by reference to helpers so they can append without returning the
    lists.

    Attributes:
        portfolio_values: Portfolio value at the close of each bar
            (first element = initial capital).
        daily_returns: Fractional daily return for each bar.
        trades_pnl: Round-trip net P&L for each closed trade.
    """

    initial_capital: float

    portfolio_values: list[float] = field(init=False)
    daily_returns: list[float] = field(default_factory=list, init=False)
    trades_pnl: list[float] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.portfolio_values = [self.initial_capital]

    @property
    def last_portfolio_value(self) -> float:
        """Most recent portfolio value (convenient alias)."""
        return self.portfolio_values[-1]


__all__ = ["OOSTracker", "LoopState"]
