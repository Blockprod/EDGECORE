"""
Position-level stops comprehensive test suite.

Tests for:
- Stop loss triggering
- Take profit triggering  
- Trailing stops
- Hard exit time limits
- Breakeven protection
- Multiple position management
"""

import pytest
from datetime import datetime, timedelta
from execution.position_stops import (
    PositionStop, PositionStopManager, 
    get_stop_manager, reset_stop_manager
)
from common.types import PositionStopConfig, StopType, PositionID, Symbol, Price


class TestPositionStopBasics:
    """Test basic position stop functionality."""
    
    def test_position_stop_initialization(self):
        """Verify position stop initializes correctly."""
        stop = PositionStop(
            position_id="pos_001",
            symbol="AAPL",
            entry_price=50000.0,
            side="long"
        )
        
        assert stop.position_id == "pos_001"
        assert stop.symbol == "AAPL"
        assert stop.entry_price == 50000.0
        assert stop.side == "long"
        assert stop.stop_loss_price is None
        assert stop.take_profit_price is None
    
    def test_position_stop_short_side(self):
        """Verify short position initialization."""
        stop = PositionStop(
            position_id="pos_002",
            symbol="MSFT",
            entry_price=3000.0,
            side="short"
        )
        
        assert stop.side == "short"
        assert stop.entry_price == 3000.0
        assert stop.stop_loss_price is None
    
    def test_position_stop_invalid_side(self):
        """Verify invalid side raises error."""
        with pytest.raises(ValueError):
            PositionStop(
                position_id="pos_003",
                symbol="AAPL",
                entry_price=50000.0,
                side="invalid"
            )
    
    def test_position_stop_with_config(self):
        """Verify position stop with configuration."""
        config: PositionStopConfig = {
            "stop_loss_price": 45000.0,
            "take_profit_price": 60000.0
        }
        
        stop = PositionStop(
            position_id="pos_004",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            stop_loss_price=45000.0,
            take_profit_price=60000.0
        )
        
        assert stop.stop_loss_price == 45000.0
        assert stop.take_profit_price == 60000.0


class TestStopLossTrigger:
    """Test stop loss triggering."""
    
    def test_stop_loss_long_position(self):
        """Verify stop loss triggers on long position."""
        stop = PositionStop(
            position_id="pos_101",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            stop_loss_price=45000.0
        )
        
        # Price above stop - no trigger
        result = stop.update(48000.0)
        assert result["triggered_stops"] == []
        
        # Price touches stop - trigger
        result = stop.update(45000.0)
        assert StopType.STOP_LOSS.value in result["triggered_stops"]
        
        # Price below stop - trigger
        result = stop.update(44000.0)
        assert StopType.STOP_LOSS.value in result["triggered_stops"]
    
    def test_stop_loss_short_position(self):
        """Verify stop loss triggers on short position."""
        stop = PositionStop(
            position_id="pos_102",
            symbol="MSFT",
            entry_price=3000.0,
            side="short",
            stop_loss_price=3500.0
        )
        
        # Price below stop - no trigger
        result = stop.update(3200.0)
        assert result["triggered_stops"] == []
        
        # Price touches stop - trigger
        result = stop.update(3500.0)
        assert StopType.STOP_LOSS.value in result["triggered_stops"]
        
        # Price above stop - trigger
        result = stop.update(3600.0)
        assert StopType.STOP_LOSS.value in result["triggered_stops"]
    
    def test_stop_loss_no_limit(self):
        """Verify position without stop loss never triggers."""
        stop = PositionStop(
            position_id="pos_103",
            symbol="AAPL",
            entry_price=50000.0,
            side="long"
        )
        
        # Update with various prices
        for price in [45000.0, 40000.0, 30000.0]:
            result = stop.update(price)
            assert StopType.STOP_LOSS.value not in result["triggered_stops"]


class TestTakeProfitTrigger:
    """Test take profit triggering."""
    
    def test_take_profit_long_position(self):
        """Verify take profit triggers on long position."""
        stop = PositionStop(
            position_id="pos_201",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            take_profit_price=60000.0
        )
        
        # Price below target - no trigger
        result = stop.update(55000.0)
        assert StopType.TAKE_PROFIT.value not in result["triggered_stops"]
        
        # Price touches target - trigger
        result = stop.update(60000.0)
        assert StopType.TAKE_PROFIT.value in result["triggered_stops"]
        
        # Price above target - trigger
        result = stop.update(65000.0)
        assert StopType.TAKE_PROFIT.value in result["triggered_stops"]
    
    def test_take_profit_short_position(self):
        """Verify take profit triggers on short position."""
        stop = PositionStop(
            position_id="pos_202",
            symbol="MSFT",
            entry_price=3000.0,
            side="short",
            take_profit_price=2500.0
        )
        
        # Price above target - no trigger
        result = stop.update(2800.0)
        assert StopType.TAKE_PROFIT.value not in result["triggered_stops"]
        
        # Price touches target - trigger
        result = stop.update(2500.0)
        assert StopType.TAKE_PROFIT.value in result["triggered_stops"]
        
        # Price below target - trigger
        result = stop.update(2000.0)
        assert StopType.TAKE_PROFIT.value in result["triggered_stops"]
    
    def test_both_stops_triggered(self):
        """Verify can trigger both stop and profit simultaneously."""
        stop = PositionStop(
            position_id="pos_203",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            stop_loss_price=45000.0,
            take_profit_price=60000.0
        )
        
        # Profit trigger recorded
        result = stop.update(60000.0)
        assert StopType.TAKE_PROFIT.value in result["triggered_stops"]
        
        # Create new position, test stop loss
        stop2 = PositionStop(
            position_id="pos_204",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            stop_loss_price=45000.0,
            take_profit_price=60000.0
        )
        
        result = stop2.update(45000.0)
        assert StopType.STOP_LOSS.value in result["triggered_stops"]


class TestTrailingStops:
    """Test trailing stop functionality."""
    
    def test_trailing_stop_percent_long(self):
        """Verify trailing stop percent on long position."""
        stop = PositionStop(
            position_id="pos_301",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            trailing_stop_percent=5.0  # 5% trailing stop
        )
        
        # Price up to 55000 - SL moves to 52250 (55000 * 0.95)
        result = stop.update(55000.0)
        assert stop.stop_loss_price == pytest.approx(52250.0, rel=0.01)
        assert stop.trailing_high == 55000.0
        
        # Price down to 54000 - SL stays at 52250
        result = stop.update(54000.0)
        assert stop.stop_loss_price == pytest.approx(52250.0, rel=0.01)
        assert stop.trailing_high == 55000.0
        
        # Price moves back up to 56000 - SL moves to 53200
        result = stop.update(56000.0)
        assert stop.stop_loss_price == pytest.approx(53200.0, rel=0.01)
        assert stop.trailing_high == 56000.0
    
    def test_trailing_stop_percent_short(self):
        """Verify trailing stop percent on short position."""
        stop = PositionStop(
            position_id="pos_302",
            symbol="MSFT",
            entry_price=3000.0,
            side="short",
            trailing_stop_percent=5.0
        )
        
        # Price down to 2850 - SL moves to 2992.5 (2850 * 1.05)
        result = stop.update(2850.0)
        assert stop.stop_loss_price == pytest.approx(2992.5, rel=0.01)
        assert stop.trailing_low == 2850.0
        
        # Price up - SL stays in place
        result = stop.update(2900.0)
        assert stop.stop_loss_price == pytest.approx(2992.5, rel=0.01)
        
        # Price down further - SL tightens
        result = stop.update(2800.0)
        assert stop.stop_loss_price == pytest.approx(2940.0, rel=0.01)
        assert stop.trailing_low == 2800.0
    
    def test_trailing_stop_distance_long(self):
        """Verify trailing stop distance on long position."""
        stop = PositionStop(
            position_id="pos_303",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            trailing_stop_distance=2000.0  # $2000 trailing distance
        )
        
        # Price up to 55000 - SL at 53000
        result = stop.update(55000.0)
        assert stop.stop_loss_price == 53000.0
        assert stop.trailing_high == 55000.0
        
        # Price to 57000 - SL at 55000
        result = stop.update(57000.0)
        assert stop.stop_loss_price == 55000.0
        assert stop.trailing_high == 57000.0
    
    def test_trailing_stop_execution(self):
        """Verify trailing stop can execute."""
        stop = PositionStop(
            position_id="pos_304",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            trailing_stop_percent=5.0
        )
        
        # Price goes up
        stop.update(55000.0)
        assert stop.stop_loss_price == pytest.approx(52250.0, rel=0.01)
        
        # Price drops below trailing stop
        result = stop.update(52000.0)
        assert StopType.STOP_LOSS.value in result["triggered_stops"]


class TestHardExitTime:
    """Test hard exit time limit functionality."""
    
    def test_hard_exit_not_triggered(self):
        """Verify hard exit doesn't trigger before time limit."""
        stop = PositionStop(
            position_id="pos_401",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            hard_exit_time_minutes=60,
            entry_time=datetime.utcnow()
        )
        
        assert stop.check_hard_exit() is False
    
    def test_hard_exit_triggered(self):
        """Verify hard exit triggers after time limit."""
        # Create with old entry time
        old_time = datetime.utcnow() - timedelta(minutes=65)
        stop = PositionStop(
            position_id="pos_402",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            hard_exit_time_minutes=60,
            entry_time=old_time
        )
        
        assert stop.check_hard_exit() is True
    
    def test_hard_exit_at_boundary(self):
        """Verify hard exit at exact time limit."""
        # Create with entry time exactly 60 minutes ago
        old_time = datetime.utcnow() - timedelta(minutes=60)
        stop = PositionStop(
            position_id="pos_403",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            hard_exit_time_minutes=60,
            entry_time=old_time
        )
        
        assert stop.check_hard_exit() is True
    
    def test_no_hard_exit_without_limit(self):
        """Verify position without hard exit limit never triggers."""
        old_time = datetime.utcnow() - timedelta(days=100)
        stop = PositionStop(
            position_id="pos_404",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            entry_time=old_time
        )
        
        assert stop.check_hard_exit() is False


class TestBreakevenProtection:
    """Test breakeven protection activation."""
    
    def test_breakeven_activates_on_long(self):
        """Verify breakeven protection activates on long."""
        stop = PositionStop(
            position_id="pos_501",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            stop_loss_price=45000.0,
            breakeven_trigger_percent=5.0  # 5% profit triggers it
        )
        
        # Not profitable yet
        assert stop.check_breakeven_protection(50500.0) is False
        assert stop.stop_loss_price == 45000.0
        
        # At 5% profit - trigger breakeven
        assert stop.check_breakeven_protection(52500.0) is True
        assert stop.stop_loss_price == 50000.0  # Moved to entry price
    
    def test_breakeven_activates_on_short(self):
        """Verify breakeven protection activates on short."""
        stop = PositionStop(
            position_id="pos_502",
            symbol="MSFT",
            entry_price=3000.0,
            side="short",
            stop_loss_price=3500.0,
            breakeven_trigger_percent=5.0
        )
        
        # Not profitable yet
        assert stop.check_breakeven_protection(2990.0) is False
        
        # At 5% profit - trigger breakeven
        assert stop.check_breakeven_protection(2850.0) is True
        assert stop.stop_loss_price == 3000.0
    
    def test_breakeven_not_overwrite_higher_stop(self):
        """Verify breakeven doesn't move stop if already higher."""
        stop = PositionStop(
            position_id="pos_503",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            stop_loss_price=49500.0,  # Already tight stop
            breakeven_trigger_percent=5.0
        )
        
        # At 5% profit with existing tight stop
        result = stop.check_breakeven_protection(52500.0)
        assert result is True
        assert stop.stop_loss_price == 50000.0  # Moved to breakeven


class TestPositionStopStatus:
    """Test position stop status reporting."""
    
    def test_status_with_no_stops(self):
        """Verify status for position with no stops."""
        stop = PositionStop(
            position_id="pos_601",
            symbol="AAPL",
            entry_price=50000.0,
            side="long"
        )
        
        status = stop.get_status()
        assert status["position_id"] == "pos_601"
        assert status["symbol"] == "AAPL"
        assert status["active_stops"] == []
    
    def test_status_with_stops(self):
        """Verify status with multiple active stops."""
        stop = PositionStop(
            position_id="pos_602",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            stop_loss_price=45000.0,
            take_profit_price=60000.0,
            trailing_stop_percent=5.0
        )
        
        status = stop.get_status()
        assert StopType.STOP_LOSS.value in status["active_stops"]
        assert StopType.TAKE_PROFIT.value in status["active_stops"]
        assert StopType.TRAILING_STOP.value in status["active_stops"]
        assert status["stop_loss_price"] == 45000.0
        assert status["take_profit_price"] == 60000.0
    
    def test_status_with_hard_exit(self):
        """Verify status includes time to hard exit."""
        stop = PositionStop(
            position_id="pos_603",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            hard_exit_time_minutes=60,
            entry_time=datetime.utcnow() - timedelta(minutes=30)
        )
        
        status = stop.get_status()
        assert status["time_to_hard_exit"] is not None
        assert 0 < status["time_to_hard_exit"] <= 1800  # Between 0-30 min


class TestPositionStopManager:
    """Test multi-position stop manager."""
    
    def test_manager_initialization(self):
        """Verify manager initializes correctly."""
        reset_stop_manager()
        manager = get_stop_manager()
        assert len(manager.positions) == 0
    
    def test_add_position(self):
        """Verify adding position to manager."""
        manager = PositionStopManager()
        
        pos_stop = manager.add_position(
            position_id="pos_501",
            symbol="AAPL",
            entry_price=50000.0,
            side="long"
        )
        
        assert "pos_501" in manager.positions
        assert pos_stop.position_id == "pos_501"
    
    def test_add_position_with_config(self):
        """Verify adding position with stop configuration."""
        manager = PositionStopManager()
        
        config: PositionStopConfig = {
            "stop_loss_price": 45000.0,
            "take_profit_price": 60000.0
        }
        
        pos_stop = manager.add_position(
            position_id="pos_502",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            stop_config=config
        )
        
        assert pos_stop.stop_loss_price == 45000.0
        assert pos_stop.take_profit_price == 60000.0
    
    def test_update_price(self):
        """Verify updating price for position."""
        manager = PositionStopManager()
        
        manager.add_position(
            position_id="pos_503",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            stop_config={"stop_loss_price": 45000.0}
        )
        
        result = manager.update_price("pos_503", 52000.0)
        assert result["current_price"] == 52000.0
    
    def test_check_exits_no_exit(self):
        """Verify check exits returns False when no stop triggered."""
        manager = PositionStopManager()
        
        manager.add_position(
            position_id="pos_504",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            stop_config={"stop_loss_price": 45000.0, "take_profit_price": 60000.0}
        )
        
        should_exit, reason = manager.check_exits("pos_504", 52000.0)
        assert should_exit is False
    
    def test_check_exits_stop_triggered(self):
        """Verify check exits returns True when stop triggered."""
        manager = PositionStopManager()
        
        manager.add_position(
            position_id="pos_505",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            stop_config={"stop_loss_price": 45000.0}
        )
        
        should_exit, reason = manager.check_exits("pos_505", 44000.0)
        assert should_exit is True
        assert "stop_loss" in reason.lower()
    
    def test_remove_position(self):
        """Verify removing position from manager."""
        manager = PositionStopManager()
        
        manager.add_position(
            position_id="pos_506",
            symbol="AAPL",
            entry_price=50000.0,
            side="long"
        )
        
        assert manager.remove_position("pos_506") is True
        assert "pos_506" not in manager.positions
        assert manager.remove_position("pos_506") is False
    
    def test_get_status(self):
        """Verify getting status for position."""
        manager = PositionStopManager()
        
        manager.add_position(
            position_id="pos_507",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            stop_config={"stop_loss_price": 45000.0}
        )
        
        status = manager.get_status("pos_507")
        assert status is not None
        assert status["position_id"] == "pos_507"
    
    def test_get_all_statuses(self):
        """Verify getting all position statuses."""
        manager = PositionStopManager()
        
        for i in range(3):
            manager.add_position(
                position_id=f"pos_{i}",
                symbol="AAPL",
                entry_price=50000.0,
                side="long"
            )
        
        statuses = manager.get_all_statuses()
        assert len(statuses) == 3
    
    def test_multiple_positions_independent(self):
        """Verify multiple positions operate independently."""
        manager = PositionStopManager()
        
        # Add two positions with different stops
        manager.add_position(
            position_id="pos_101",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            stop_config={"stop_loss_price": 45000.0}
        )
        
        manager.add_position(
            position_id="pos_102",
            symbol="MSFT",
            entry_price=3000.0,
            side="short",
            stop_config={"stop_loss_price": 3500.0}
        )
        
        # Update first position - shouldn't affect second
        should_exit_1, _ = manager.check_exits("pos_101", 44000.0)
        should_exit_2, _ = manager.check_exits("pos_102", 2900.0)
        
        assert should_exit_1 is True  # AAPL stop triggered
        assert should_exit_2 is False  # MSFT stops not triggered


class TestPositionStopIntegration:
    """Integration tests for position stops."""
    
    def test_stop_workflow_long_stop_loss(self):
        """Verify complete workflow triggering stop loss."""
        stop = PositionStop(
            position_id="pos_w001",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            stop_loss_price=45000.0,
            take_profit_price=60000.0
        )
        
        # Simulate price movements
        movements = [51000.0, 52000.0, 51500.0, 48000.0, 44000.0]
        
        for price in movements:
            result = stop.update(price)
            if 44000.0 == price:
                assert StopType.STOP_LOSS.value in result["triggered_stops"]
                break
    
    def test_stop_workflow_long_take_profit(self):
        """Verify complete workflow triggering take profit."""
        stop = PositionStop(
            position_id="pos_w002",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            stop_loss_price=45000.0,
            take_profit_price=60000.0
        )
        
        # Simulate price movements
        movements = [51000.0, 52000.0, 55000.0, 58000.0, 60000.0]
        
        for price in movements:
            result = stop.update(price)
            if 60000.0 == price:
                assert StopType.TAKE_PROFIT.value in result["triggered_stops"]
                break
    
    def test_stop_workflow_with_trailing_and_profit_target(self):
        """Verify workflow with both trailing stop and profit target."""
        stop = PositionStop(
            position_id="pos_w003",
            symbol="AAPL",
            entry_price=50000.0,
            side="long",
            trailing_stop_percent=5.0,
            take_profit_price=62000.0
        )
        
        # Move up - trailing stop follows
        stop.update(55000.0)
        assert stop.stop_loss_price == pytest.approx(52250.0, rel=0.01)
        
        # Continue up to profit target
        result = stop.update(62000.0)
        assert StopType.TAKE_PROFIT.value in result["triggered_stops"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
