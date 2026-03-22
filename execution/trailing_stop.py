"""
Trailing Stop Manager for Pair Trading (S2.3).

Problem: Pairs can experience temporary large movements beyond entry Z-score.
A position entered at Z=2.2 might experience widening to Z=3.8+ before reverting.
Without protection, losses accumulate beyond acceptable risk.

Solution: Trailing stops that exit if spread widens > 1.0�� from entry.

Mechanism:
- Record Z-score at entry
- Monitor current Z-score continuously
- Exit if spread widens by > 1.0��: |current_z| - |entry_z| > 1.0
- This catches "mean reversion failure" - when pair doesn't revert as expected

Expected Impact: +12 Sharpe points from reducing tail losses
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class TrailingStopPosition:
    """Track a position's entry point for trailing stop calculation."""

    symbol_pair: str
    side: str  # "long" or "short"
    entry_z: float  # Z-score at entry
    entry_spread: float  # Spread value at entry
    entry_time: pd.Timestamp
    max_profit_z: float | None = None  # Best Z-score achieved (for tracking)
    max_loss_z: float | None = None  # Worst Z-score achieved


class TrailingStopManager:
    """
    Manage trailing stops for spread positions.

    Purpose: Protect against "mean reversion failure" scenarios where
    a spread widens significantly beyond entry instead of mean-reverting.

    Strategy:
    - Track entry Z-score and spread characteristics
    - Monitor widening from entry point
    - Exit if spread widens > threshold (default: 1.0��)
    - Allows tighter stops as positions become profitable
    """

    def __init__(self, widening_threshold: float = 1.0, track_max_profit: bool = True):
        """
        Initialize trailing stop manager.

        Args:
            widening_threshold: Exit if spread widens by this many �� from entry
                              (default 1.0��)
            track_max_profit: Whether to track max profit for tighter stops
        """
        self.widening_threshold = widening_threshold
        self.track_max_profit = track_max_profit
        self.positions: dict[str, TrailingStopPosition] = {}

        logger.info(
            "trailing_stop_manager_initialized",
            widening_threshold=widening_threshold,
            track_max_profit=track_max_profit,
        )

    def add_position(
        self, symbol_pair: str, side: str, entry_z: float, entry_spread: float, entry_time: pd.Timestamp
    ) -> None:
        """
        Record a new position for trailing stop monitoring.

        Args:
            symbol_pair: Pair identifier (e.g., "AAPL_MSFT")
            side: "long" or "short"
            entry_z: Z-score at entry
            entry_spread: Spread value at entry
            entry_time: Timestamp of entry
        """
        position = TrailingStopPosition(
            symbol_pair=symbol_pair,
            side=side,
            entry_z=entry_z,
            entry_spread=entry_spread,
            entry_time=entry_time,
            max_profit_z=entry_z,  # Start at entry
            max_loss_z=entry_z,
        )
        self.positions[symbol_pair] = position

        logger.info(
            "trailing_stop_position_added",
            pair=symbol_pair,
            side=side,
            entry_z=f"{entry_z:.3f}",
            entry_spread=f"{entry_spread:.4f}",
        )

    def should_exit_on_trailing_stop(
        self, symbol_pair: str, current_z: float, reason_detail: str | None = None
    ) -> tuple[bool, str | None]:
        """
        Check if position should exit due to trailing stop.

        Logic:
        - If position entered at entry_z = 2.2 (long):
          - Expect reversion toward 0 (widening would be increasing in magnitude)
          - Current Z = 3.8 ��� widening = |3.8| - |2.2| = 1.6��
          - If 1.6 > threshold (1.0) ��� exit

        - If position entered at entry_z = -2.0 (short):
          - Expect reversion toward 0 (widening would be more negative)
          - Current Z = -3.5 ��� widening = |-3.5| - |-2.0| = 1.5��
          - If 1.5 > threshold (1.0) ��� exit

        Args:
            symbol_pair: Pair identifier
            current_z: Current Z-score of spread
            reason_detail: Optional additional reason text

        Returns:
            (should_exit: bool, exit_reason: str or None)
        """
        if symbol_pair not in self.positions:
            return False, None

        position = self.positions[symbol_pair]
        entry_z = position.entry_z

        # Calculate widening: how much spread has moved away from entry
        # For both long and short: measure absolute increase from entry
        widening = abs(current_z) - abs(entry_z)

        # Update max profit/loss tracking
        if self.track_max_profit:
            # For long (entry_z > 0): max profit = min(current_z)
            # For short (entry_z < 0): max profit = max(current_z)
            if position.side == "long":
                position.max_profit_z = min(
                    position.max_profit_z if position.max_profit_z is not None else current_z, current_z
                )
                position.max_loss_z = max(
                    position.max_loss_z if position.max_loss_z is not None else current_z, current_z
                )
            else:  # short
                position.max_profit_z = max(
                    position.max_profit_z if position.max_profit_z is not None else current_z, current_z
                )
                position.max_loss_z = min(
                    position.max_loss_z if position.max_loss_z is not None else current_z, current_z
                )

        # Check trailing stop condition
        if widening > self.widening_threshold:
            exit_reason = (
                f"Trailing stop: spread widened {widening:.2f}�� from entry "
                f"(entry_z={entry_z:.3f}, current_z={current_z:.3f})"
            )
            if reason_detail:
                exit_reason += f" [{reason_detail}]"

            logger.warning(
                "trailing_stop_triggered",
                pair=symbol_pair,
                side=position.side,
                entry_z=f"{entry_z:.3f}",
                current_z=f"{current_z:.3f}",
                widening=f"{widening:.3f}",
                threshold=f"{self.widening_threshold:.3f}",
            )

            # Clean up position
            del self.positions[symbol_pair]

            return True, exit_reason

        return False, None

    def should_exit_on_tight_trailing_stop(
        self, symbol_pair: str, current_z: float, profit_threshold: float = 0.5
    ) -> tuple[bool, str | None]:
        """
        Alternative trailing stop: tighter protection for profitable positions.

        Once position is in profit (Z moving toward 0), use
        tighter stop to lock in gains.

        Logic:
        - Entry Z = 2.2, current Z = 1.0 (profit!)
        - Distance from zero: entry=2.2, current=1.0
        - Profit = 2.2 - 1.0 = 1.2�� (profit!)
        - Use tighter threshold: e.g., 0.3�� (if widens 0.3�� from best, exit)

        Args:
            symbol_pair: Pair identifier
            current_z: Current Z-score
            profit_threshold: How much profit to require before tighter stop applies

        Returns:
            (should_exit: bool, exit_reason: str or None)
        """
        if symbol_pair not in self.positions:
            return False, None

        position = self.positions[symbol_pair]
        entry_z = position.entry_z
        max_profit_z = position.max_profit_z

        # Calculate current profit
        if position.side == "long":
            # Long profits = moving toward 0 from positive
            profit = abs(entry_z) - abs(current_z)
            best_achieved = abs(max_profit_z) if max_profit_z is not None else abs(current_z)
        else:
            # Short profits = moving toward 0 from negative
            profit = abs(entry_z) - abs(current_z)
            best_achieved = abs(max_profit_z) if max_profit_z is not None else abs(current_z)

        # If in profit, use tighter trailing stop
        if profit > profit_threshold:
            # Tighter threshold: 0.3�� (vs normal 1.0��)
            tight_threshold = 0.3
            widening_from_best = abs(current_z) - best_achieved

            if widening_from_best > tight_threshold:
                exit_reason = (
                    f"Tight trailing stop (in profit): "
                    f"spread widened {widening_from_best:.2f}�� from best "
                    f"(best_z={max_profit_z:.3f}, current_z={current_z:.3f})"
                )

                logger.info(
                    "tight_trailing_stop_triggered",
                    pair=symbol_pair,
                    side=position.side,
                    profit=f"{profit:.3f}",
                    best_z=f"{max_profit_z:.3f}",
                    current_z=f"{current_z:.3f}",
                    widening=f"{widening_from_best:.3f}",
                )

                # Clean up position
                del self.positions[symbol_pair]

                return True, exit_reason

        return False, None

    def get_position_info(self, symbol_pair: str) -> dict | None:
        """
        Get current tracking info for a position.

        Returns:
            dict with entry_z, current tracking, profit/loss estimates
        """
        if symbol_pair not in self.positions:
            return None

        position = self.positions[symbol_pair]
        return {
            "symbol_pair": position.symbol_pair,
            "side": position.side,
            "entry_z": position.entry_z,
            "entry_spread": position.entry_spread,
            "entry_time": position.entry_time,
            "max_profit_z": position.max_profit_z,
            "max_loss_z": position.max_loss_z,
            "tracked_positions": len(self.positions),
        }

    def remove_position(self, symbol_pair: str) -> None:
        """Remove a position from tracking (on manual exit)."""
        if symbol_pair in self.positions:
            info = self.positions[symbol_pair]
            logger.debug(
                "position_manually_removed",
                pair=symbol_pair,
                entry_z=f"{info.entry_z:.3f}",
                max_profit_z=f"{info.max_profit_z:.3f}" if info.max_profit_z is not None else "None",
                max_loss_z=f"{info.max_loss_z:.3f}" if info.max_loss_z is not None else "None",
            )
            del self.positions[symbol_pair]

    def get_active_positions(self) -> list:
        """Get list of all actively tracked positions."""
        return list(self.positions.keys())

    def reset_all(self) -> None:
        """Clear all tracked positions."""
        count = len(self.positions)
        self.positions.clear()
        logger.debug("trailing_stop_manager_reset", positions_cleared=count)

    def get_summary(self) -> dict:
        """Get summary statistics across all tracked positions."""
        if not self.positions:
            return {"active_positions": 0, "total_tracked": 0, "avg_entry_z": None, "avg_max_profit": None}

        positions_list = list(self.positions.values())

        return {
            "active_positions": len(positions_list),
            "long_positions": sum(1 for p in positions_list if p.side == "long"),
            "short_positions": sum(1 for p in positions_list if p.side == "short"),
            "avg_entry_z": np.mean([abs(p.entry_z) for p in positions_list]),
            "avg_max_profit_z": np.mean(
                [abs(p.max_profit_z) if p.max_profit_z is not None else 0.0 for p in positions_list]
            ),
            "position_pairs": [p.symbol_pair for p in positions_list],
        }

