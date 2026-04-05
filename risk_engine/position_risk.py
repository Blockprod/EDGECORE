"""
Position Risk Manager ÔÇö Per-position risk controls.

Consolidates all position-level risk checks into a single manager:
    1. Trailing stop (spread widening from entry)
    2. Time stop (max holding period based on half-life)
    3. P&L stop (max loss per position)
    4. Hedge ratio stability (╬▓ drift detection)

Each check returns a (should_exit, reason) tuple.  The manager runs
all checks and returns the first triggered exit, if any.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pandas as pd
from structlog import get_logger

from execution.time_stop import TimeStopManager
from execution.trailing_stop import TrailingStopManager
from models.hedge_ratio_tracker import HedgeRatioTracker
from models.stationarity_monitor import StationarityMonitor

logger = get_logger(__name__)


@dataclass
class PositionRiskConfig:
    """Configuration for position-level risk controls."""

    trailing_stop_sigma: float = 1.0
    time_stop_hl_multiplier: float = 3.0
    time_stop_max_bars: int = 60
    max_position_loss_pct: float = 0.10
    hedge_drift_tolerance_pct: float = 10.0
    hedge_reestimation_days: int = 7


@dataclass
class PositionRiskState:
    """Tracked state for a single open position."""

    pair_key: str
    side: str
    entry_z: float
    entry_price: float
    entry_bar: int
    half_life: float | None
    notional: float


class PositionRiskManager:
    """
    Unified per-position risk controls.

    Checks every bar:
        1. Has the spread widened beyond trailing stop threshold?
        2. Has the position exceeded its time-based holding limit?
        3. Has the position P&L breached the max loss limit?
        4. Has the hedge ratio drifted beyond tolerance?

    Usage::

        prm = PositionRiskManager()
        prm.register_position("AAPL_MSFT", "long", entry_z=2.1, ...)

        # Each bar:
        should_exit, reason = prm.check("AAPL_MSFT", current_z, current_bar, pnl_pct)
    """

    def __init__(self, config: PositionRiskConfig | None = None):
        self.config = config or PositionRiskConfig()

        self.trailing_stop = TrailingStopManager(
            widening_threshold=self.config.trailing_stop_sigma,
        )
        self.time_stop = TimeStopManager()
        self.hedge_tracker = HedgeRatioTracker(
            reestimation_frequency_days=self.config.hedge_reestimation_days,
        )
        self.stationarity = StationarityMonitor()

        # Active position states
        self._positions: dict[str, PositionRiskState] = {}

        logger.info(
            "position_risk_manager_initialized",
            trailing_sigma=self.config.trailing_stop_sigma,
            time_stop_max=self.config.time_stop_max_bars,
            max_loss=f"{self.config.max_position_loss_pct:.1%}",
        )

    # ------------------------------------------------------------------
    # Position lifecycle
    # ------------------------------------------------------------------

    def register_position(
        self,
        pair_key: str,
        side: str,
        entry_z: float,
        entry_price: float,
        entry_bar: int,
        half_life: float | None,
        notional: float,
        entry_spread: float = 0.0,
    ) -> None:
        """Register a new position for risk monitoring."""
        self._positions[pair_key] = PositionRiskState(
            pair_key=pair_key,
            side=side,
            entry_z=entry_z,
            entry_price=entry_price,
            entry_bar=entry_bar,
            half_life=half_life,
            notional=notional,
        )
        self.trailing_stop.add_position(
            symbol_pair=pair_key,
            side=side,
            entry_z=entry_z,
            entry_spread=entry_spread,
            entry_time=pd.Timestamp.now(),
        )
        logger.info(
            "position_risk_registered",
            pair=pair_key,
            side=side,
            entry_z=f"{entry_z:.2f}",
        )

    def remove_position(self, pair_key: str) -> None:
        """Remove a position from monitoring (after exit)."""
        self._positions.pop(pair_key, None)
        self.trailing_stop.positions.pop(pair_key, None)

    # ------------------------------------------------------------------
    # Risk check (called every bar)
    # ------------------------------------------------------------------

    def check(
        self,
        pair_key: str,
        current_z: float,
        current_bar: int,
        pnl_pct: float,
        spread: pd.Series | None = None,
    ) -> tuple[bool, str]:
        """
        Run all position-level risk checks.

        Args:
            pair_key: Position identifier.
            current_z: Current spread z-score.
            current_bar: Current bar index.
            pnl_pct: Unrealised P&L as fraction of notional.
            spread: Current spread series (for stationarity check).

        Returns:
            (should_exit, reason) ÔÇö first triggered check, or (False, "").
        """
        state = self._positions.get(pair_key)
        if state is None:
            return False, ""

        # 1. Trailing stop
        should_exit, reason = self.trailing_stop.should_exit_on_trailing_stop(
            symbol_pair=pair_key,
            current_z=current_z,
        )
        if should_exit:
            logger.warning("risk_trailing_stop", pair=pair_key, reason=reason)
            return True, reason or ""
        holding_bars = current_bar - state.entry_bar
        should_exit_t, reason_t = self.time_stop.should_exit(
            holding_bars=holding_bars,
            half_life=int(state.half_life) if state.half_life else None,
        )
        if should_exit_t:
            reason_ts = reason_t if isinstance(reason_t, str) else f"Time stop: {holding_bars} bars"
            logger.warning("risk_time_stop", pair=pair_key, bars=holding_bars)
            return True, reason_ts

        # 3. P&L stop
        if abs(pnl_pct) >= self.config.max_position_loss_pct and pnl_pct < 0:
            reason_pnl = f"P&L stop: {pnl_pct:.2%} loss exceeds {self.config.max_position_loss_pct:.1%}"
            logger.warning("risk_pnl_stop", pair=pair_key, pnl=f"{pnl_pct:.2%}")
            return True, reason_pnl

        # 4. Stationarity guard (if spread provided)
        if spread is not None and len(spread) >= 30:
            is_stationary, pval = self.stationarity.check(spread)
            if not is_stationary:
                reason_stat = f"Spread non-stationary (ADF p={pval:.3f})"
                logger.warning("risk_stationarity", pair=pair_key, pval=f"{pval:.3f}")
                return True, reason_stat

        return False, ""

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def active_positions(self) -> dict[str, PositionRiskState]:
        return dict(self._positions)

    @property
    def position_count(self) -> int:
        return len(self._positions)
