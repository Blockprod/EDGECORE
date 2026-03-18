"""
Position-level stop loss and take profit management.

Provides:
- Stop level configuration for positions
- Stop triggering detection
- Trailing stop calculations
- Hard exit time limits
- Breakeven protection logic
"""

from typing import Any, Dict, Optional, Tuple, List
from datetime import datetime, timezone
from dataclasses import dataclass, field
from structlog import get_logger
from common.types import (
    PositionID, Symbol, Price, PositionStopConfig, PositionStopStatus, StopType
)

logger = get_logger(__name__)


@dataclass
class PositionStop:
    """Manages stop levels for a single position."""
    
    position_id: PositionID
    symbol: Symbol
    entry_price: Price
    side: str  # "long" or "short"
    entry_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    stop_loss_price: Optional[Price] = None
    take_profit_price: Optional[Price] = None
    trailing_stop_percent: Optional[float] = None
    trailing_stop_distance: Optional[Price] = None
    hard_exit_time_minutes: Optional[int] = None
    breakeven_trigger_percent: Optional[float] = None
    
    # Tracking state
    trailing_high: Optional[Price] = None  # For long positions
    trailing_low: Optional[Price] = None   # For short positions
    highest_profit: float = 0.0
    max_price: Optional[Price] = None
    min_price: Optional[Price] = None
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __post_init__(self) -> None:
        """Validate and initialize stop configuration."""
        if self.side not in ["long", "short"]:
            raise ValueError(f"Invalid side: {self.side}")
        
        # Initialize trailing high/low
        if self.trailing_stop_percent or self.trailing_stop_distance:
            self.trailing_high = self.entry_price if self.side == "long" else None
            self.trailing_low = self.entry_price if self.side == "short" else None
        
        logger.info(
            "position_stop_initialized",
            position_id=self.position_id,
            symbol=self.symbol,
            entry_price=self.entry_price,
            side=self.side,
            stop_loss=self.stop_loss_price,
            take_profit=self.take_profit_price
        )
    
    def update(self, current_price: Price) -> Dict[str, Any]:
        """
        Update stops based on current price.
        
        Args:
            current_price: Current market price
        
        Returns:
            Dict with update details (triggered stops, etc)
        """
        self.last_update = datetime.now(timezone.utc)
        self.max_price = max(self.max_price or current_price, current_price)
        self.min_price = min(self.min_price or current_price, current_price)
        
        # Calculate current profit
        if self.side == "long":
            current_profit = ((current_price - self.entry_price) / self.entry_price) * 100
        else:  # short
            current_profit = ((self.entry_price - current_price) / self.entry_price) * 100
        
        self.highest_profit = max(self.highest_profit, current_profit)
        
        # Update trailing stops
        if self.trailing_stop_percent or self.trailing_stop_distance:
            self._update_trailing_stops(current_price)
        
        # Check for stop triggers
        triggered_stops = self._check_stop_triggers(current_price)
        
        return {
            "current_price": current_price,
            "current_profit_pct": current_profit,
            "highest_profit_pct": self.highest_profit,
            "triggered_stops": triggered_stops,
            "update_time": self.last_update
        }
    
    def _update_trailing_stops(self, current_price: Price) -> None:
        """Update trailing stop levels based on price movement."""
        if self.side == "long":
            # Trailing stop follows price up
            if self.trailing_stop_percent:
                # Trailing stop is at current_price - (current_price * trailing_percent)
                trailing_level = current_price * (1 - self.trailing_stop_percent / 100)
                # Only move up, never down
                if self.trailing_high is None or current_price > self.trailing_high:
                    self.trailing_high = current_price
                    self.stop_loss_price = trailing_level
                    logger.debug(
                        "trailing_stop_updated_long",
                        position_id=self.position_id,
                        trailing_high=self.trailing_high,
                        new_stop_loss=self.stop_loss_price
                    )
            
            elif self.trailing_stop_distance:
                # Trailing stop at fixed distance below current price
                if self.trailing_high is None or current_price > self.trailing_high:
                    self.trailing_high = current_price
                    self.stop_loss_price = current_price - self.trailing_stop_distance
                    logger.debug(
                        "trailing_stop_distance_updated_long",
                        position_id=self.position_id,
                        distance=self.trailing_stop_distance,
                        new_stop_loss=self.stop_loss_price
                    )
        
        else:  # short
            # Trailing stop follows price down
            if self.trailing_stop_percent:
                # Trailing stop is at current_price + (current_price * trailing_percent)
                trailing_level = current_price * (1 + self.trailing_stop_percent / 100)
                # Only move down, never up
                if self.trailing_low is None or current_price < self.trailing_low:
                    self.trailing_low = current_price
                    self.stop_loss_price = trailing_level
                    logger.debug(
                        "trailing_stop_updated_short",
                        position_id=self.position_id,
                        trailing_low=self.trailing_low,
                        new_stop_loss=self.stop_loss_price
                    )
            
            elif self.trailing_stop_distance:
                # Trailing stop at fixed distance above current price
                if self.trailing_low is None or current_price < self.trailing_low:
                    self.trailing_low = current_price
                    self.stop_loss_price = current_price + self.trailing_stop_distance
                    logger.debug(
                        "trailing_stop_distance_updated_short",
                        position_id=self.position_id,
                        distance=self.trailing_stop_distance,
                        new_stop_loss=self.stop_loss_price
                    )
    
    def _check_stop_triggers(self, current_price: Price) -> List[str]:
        """
        Check if any stops are triggered.
        
        Args:
            current_price: Current market price
        
        Returns:
            List of triggered stop types
        """
        triggered = []
        
        if self.side == "long":
            # Stop loss trigger (below stop price)
            if self.stop_loss_price and current_price <= self.stop_loss_price:
                triggered.append(StopType.STOP_LOSS.value)
                logger.warning(
                    "stop_loss_triggered",
                    position_id=self.position_id,
                    symbol=self.symbol,
                    stop_price=self.stop_loss_price,
                    current_price=current_price
                )
            
            # Take profit trigger (above target price)
            if self.take_profit_price and current_price >= self.take_profit_price:
                triggered.append(StopType.TAKE_PROFIT.value)
                logger.info(
                    "take_profit_triggered",
                    position_id=self.position_id,
                    symbol=self.symbol,
                    target_price=self.take_profit_price,
                    current_price=current_price,
                    profit_pct=self.highest_profit
                )
        
        else:  # short
            # Stop loss trigger (above stop price)
            if self.stop_loss_price and current_price >= self.stop_loss_price:
                triggered.append(StopType.STOP_LOSS.value)
                logger.warning(
                    "stop_loss_triggered_short",
                    position_id=self.position_id,
                    symbol=self.symbol,
                    stop_price=self.stop_loss_price,
                    current_price=current_price
                )
            
            # Take profit trigger (below target price)
            if self.take_profit_price and current_price <= self.take_profit_price:
                triggered.append(StopType.TAKE_PROFIT.value)
                logger.info(
                    "take_profit_triggered_short",
                    position_id=self.position_id,
                    symbol=self.symbol,
                    target_price=self.take_profit_price,
                    current_price=current_price,
                    profit_pct=self.highest_profit
                )
        
        return triggered
    
    def check_hard_exit(self) -> bool:
        """
        Check if hard exit time limit has been reached.
        
        Returns:
            True if position should exit due to time limit
        """
        if not self.hard_exit_time_minutes:
            return False
        
        elapsed = datetime.now(timezone.utc) - self.entry_time
        elapsed_minutes = elapsed.total_seconds() / 60
        
        if elapsed_minutes >= self.hard_exit_time_minutes:
            logger.warning(
                "hard_exit_triggered",
                position_id=self.position_id,
                symbol=self.symbol,
                hold_time_minutes=elapsed_minutes,
                limit_minutes=self.hard_exit_time_minutes
            )
            return True
        
        return False
    
    def check_breakeven_protection(self, current_price: Price) -> bool:
        """
        Check if breakeven protection should activate.
        
        Args:
            current_price: Current market price
        
        Returns:
            True if breakeven protection activated
        """
        if not self.breakeven_trigger_percent:
            return False
        
        # Calculate current profit
        if self.side == "long":
            profit_pct = ((current_price - self.entry_price) / self.entry_price) * 100
        else:  # short
            profit_pct = ((self.entry_price - current_price) / self.entry_price) * 100
        
        # Activate breakeven stop if profit exceeds trigger
        if profit_pct >= self.breakeven_trigger_percent:
            if self.stop_loss_price is None or \
               (self.side == "long" and self.stop_loss_price < self.entry_price) or \
               (self.side == "short" and self.stop_loss_price > self.entry_price):
                
                # Move stop to breakeven
                self.stop_loss_price = self.entry_price
                logger.info(
                    "breakeven_protection_activated",
                    position_id=self.position_id,
                    symbol=self.symbol,
                    profit_pct=profit_pct,
                    trigger_pct=self.breakeven_trigger_percent
                )
                return True
        
        return False
    
    def get_status(self) -> PositionStopStatus:
        """Get current stop status."""
        active_stops = []
        if self.stop_loss_price:
            active_stops.append(StopType.STOP_LOSS.value)
        if self.take_profit_price:
            active_stops.append(StopType.TAKE_PROFIT.value)
        if self.trailing_stop_percent or self.trailing_stop_distance:
            active_stops.append(StopType.TRAILING_STOP.value)
        
        # Calculate distance to nearest stop
        distances = []
        if self.stop_loss_price:
            if self.side == "long":
                distances.append(self.stop_loss_price)  # Distance to SL
            else:
                distances.append(self.stop_loss_price)  # Distance to SL
        
        distance_from_stop = min(distances) if distances else 0.0
        
        # Time to hard exit
        time_to_exit = None
        if self.hard_exit_time_minutes:
            elapsed = datetime.now(timezone.utc) - self.entry_time
            remaining = (self.hard_exit_time_minutes * 60) - elapsed.total_seconds()
            time_to_exit = max(0, int(remaining))
        
        return PositionStopStatus(
            position_id=self.position_id,
            symbol=self.symbol,
            active_stops=active_stops,
            stop_loss_price=self.stop_loss_price,
            take_profit_price=self.take_profit_price,
            trailing_high=self.trailing_high,
            distance_from_stop=distance_from_stop,
            time_to_hard_exit=time_to_exit,
            last_updated=self.last_update
        )


class PositionStopManager:
    """Manages stops for multiple positions."""
    
    def __init__(self) -> None:
        """Initialize stop manager."""
        self.positions: Dict[PositionID, PositionStop] = {}
        logger.info("position_stop_manager_initialized")
    
    def add_position(
        self,
        position_id: PositionID,
        symbol: Symbol,
        entry_price: Price,
        side: str,
        stop_config: Optional[PositionStopConfig] = None,
    ) -> PositionStop:
        """
        Add a position with stop configuration.
        
        Args:
            position_id: Position ID
            symbol: Trading symbol
            entry_price: Entry price
            side: "long" or "short"
            stop_config: Stop configuration (optional)
        
        Returns:
            PositionStop instance
        """
        pos_stop = PositionStop(
            position_id=position_id,
            symbol=symbol,
            entry_price=entry_price,
            side=side,
            entry_time=datetime.now(timezone.utc),
            stop_loss_price=stop_config.get("stop_loss_price") if stop_config else None,
            take_profit_price=stop_config.get("take_profit_price") if stop_config else None,
            trailing_stop_percent=stop_config.get("trailing_stop_percent") if stop_config else None,
            trailing_stop_distance=stop_config.get("trailing_stop_distance") if stop_config else None,
            hard_exit_time_minutes=stop_config.get("hard_exit_time_minutes") if stop_config else None,
            breakeven_trigger_percent=stop_config.get("breakeven_trigger_percent") if stop_config else None,
        )
        
        self.positions[position_id] = pos_stop
        return pos_stop
    
    def update_price(self, position_id: PositionID, current_price: Price) -> Dict:
        """
        Update position with current price.
        
        Args:
            position_id: Position ID
            current_price: Current market price
        
        Returns:
            Update result with triggered stops
        """
        if position_id not in self.positions:
            return {"error": f"Position {position_id} not found"}
        
        pos_stop = self.positions[position_id]
        return pos_stop.update(current_price)
    
    def check_exits(
        self,
        position_id: PositionID,
        current_price: Price
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if position should exit (any stop triggered or hard exit).
        
        Args:
            position_id: Position ID
            current_price: Current market price
        
        Returns:
            (should_exit, exit_reason)
        """
        if position_id not in self.positions:
            return False, None
        
        pos_stop = self.positions[position_id]
        
        # Update with current price
        update_result = pos_stop.update(current_price)
        
        # Check for triggered stops
        if update_result["triggered_stops"]:
            reason = f"Stop triggered: {update_result['triggered_stops'][0]}"
            return True, reason
        
        # Check breakeven protection
        if pos_stop.check_breakeven_protection(current_price):
            return False, "Breakeven protection activated"
        
        # Check hard exit
        if pos_stop.check_hard_exit():
            return True, "Hard exit time limit reached"
        
        return False, None
    
    def remove_position(self, position_id: PositionID) -> bool:
        """
        Remove position from tracking.
        
        Args:
            position_id: Position ID
        
        Returns:
            True if removed, False if not found
        """
        if position_id in self.positions:
            del self.positions[position_id]
            logger.info("position_stop_removed", position_id=position_id)
            return True
        return False
    
    def get_status(self, position_id: PositionID) -> Optional[PositionStopStatus]:
        """Get status for a position."""
        if position_id in self.positions:
            return self.positions[position_id].get_status()
        return None
    
    def get_all_statuses(self) -> Dict[PositionID, PositionStopStatus]:
        """Get status for all positions."""
        return {
            pos_id: pos_stop.get_status()
            for pos_id, pos_stop in self.positions.items()
        }


# Global instance
_stop_manager: Optional[PositionStopManager] = None


def get_stop_manager() -> PositionStopManager:
    """Get or create global stop manager."""
    global _stop_manager
    if _stop_manager is None:
        _stop_manager = PositionStopManager()
    return _stop_manager


def reset_stop_manager() -> None:
    """Reset global stop manager (for testing)."""
    global _stop_manager
    _stop_manager = None


if __name__ == "__main__":
    print("Ô£à Position Stop Management module loaded")
    print("- PositionStop class for individual stops")
    print("- PositionStopManager for multi-position management")
    print("- Stop types: stop loss, take profit, trailing stop")
    print("- Features: hard exit, breakeven protection, trailing stops")
