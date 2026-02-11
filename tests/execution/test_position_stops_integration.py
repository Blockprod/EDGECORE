"""
Position stops integration with execution engine.

Tests for:
- Position stops integrated into execution loop
- Stop-triggered exits
- Real-time stop monitoring during backtest
- Multiple symbol position management with stops
"""

import pytest
from datetime import datetime, timedelta
from execution.position_stops import get_stop_manager, reset_stop_manager
from common.types import PositionStopConfig


class TestExecutionIntegrationWithStops:
    """Test execution engine integration with position stops."""
    
    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Reset stop manager before each test."""
        reset_stop_manager()
        yield
        reset_stop_manager()
    
    def test_stop_manager_with_execution_context(self):
        """Verify stop manager can be used in execution context."""
        manager = get_stop_manager()
        
        # Add positions as if from execution engine
        pos1 = manager.add_position(
            position_id="exec_pos_001",
            symbol="BTC/USDT",
            entry_price=50000.0,
            side="long",
            stop_config={
                "stop_loss_price": 45000.0,
                "take_profit_price": 60000.0
            }
        )
        
        assert pos1 is not None
        assert manager.get_status("exec_pos_001") is not None
    
    def test_price_updates_trigger_stops(self):
        """Verify price updates correctly trigger stops."""
        manager = get_stop_manager()
        
        manager.add_position(
            position_id="exec_pos_002",
            symbol="ETH/USDT",
            entry_price=3000.0,
            side="long",
            stop_config={"stop_loss_price": 2700.0}
        )
        
        # Normal price - no exit
        should_exit, reason = manager.check_exits("exec_pos_002", 2900.0)
        assert should_exit is False
        
        # Price hits stop
        should_exit, reason = manager.check_exits("exec_pos_002", 2600.0)
        assert should_exit is True
        assert "stop" in reason.lower()
    
    def test_multi_symbol_stops(self):
        """Verify multiple symbols can have independent stops."""
        manager = get_stop_manager()
        
        # Add positions for different symbols
        manager.add_position(
            position_id="btc_long",
            symbol="BTC/USDT",
            entry_price=50000.0,
            side="long",
            stop_config={"stop_loss_price": 45000.0}
        )
        
        manager.add_position(
            position_id="eth_long",
            symbol="ETH/USDT",
            entry_price=3000.0,
            side="long",
            stop_config={"stop_loss_price": 2700.0}
        )
        
        # Only BTC stop triggered
        should_exit_btc, _ = manager.check_exits("btc_long", 44000.0)
        should_exit_eth, _ = manager.check_exits("eth_long", 2900.0)
        
        assert should_exit_btc is True
        assert should_exit_eth is False
    
    def test_trailing_stop_in_execution_flow(self):
        """Verify trailing stops work in execution flow."""
        manager = get_stop_manager()
        
        manager.add_position(
            position_id="trail_pos",
            symbol="BTC/USDT",
            entry_price=50000.0,
            side="long",
            stop_config={"trailing_stop_percent": 5.0}
        )
        
        # Price rises - trailing stop follows
        should_exit, _ = manager.check_exits("trail_pos", 55000.0)
        assert should_exit is False
        
        # Check position stop was updated
        pos_status = manager.get_status("trail_pos")
        assert pos_status is not None
        assert pos_status["stop_loss_price"] is not None
        
        # Price drops below trailing stop
        should_exit, reason = manager.check_exits("trail_pos", 52000.0)
        assert should_exit is True
    
    def test_position_removal_after_exit(self):
        """Verify removing positions after they exit."""
        manager = get_stop_manager()
        
        manager.add_position(
            position_id="exit_pos",
            symbol="BTC/USDT",
            entry_price=50000.0,
            side="long",
            stop_config={"stop_loss_price": 45000.0}
        )
        
        # Check initial position exists
        assert manager.get_status("exit_pos") is not None
        
        # Trigger exit
        should_exit, _ = manager.check_exits("exit_pos", 44000.0)
        assert should_exit is True
        
        # Remove position
        removed = manager.remove_position("exit_pos")
        assert removed is True
        assert manager.get_status("exit_pos") is None
    
    def test_stop_manager_persistence_across_updates(self):
        """Verify stop configuration persists across price updates."""
        manager = get_stop_manager()
        
        config: PositionStopConfig = {
            "stop_loss_price": 45000.0,
            "take_profit_price": 60000.0,
            "trailing_stop_percent": 3.0
        }
        
        manager.add_position(
            position_id="persist_pos",
            symbol="BTC/USDT",
            entry_price=50000.0,
            side="long",
            stop_config=config
        )
        
        # Multiple price updates
        for price in [51000, 52000, 53000, 54000, 55000]:
            status = manager.get_status("persist_pos")
            assert status["stop_loss_price"] is not None
            assert status["take_profit_price"] == 60000.0
            
            manager.update_price("persist_pos", float(price))
    
    def test_mixed_position_types(self):
        """Verify managing long and short positions with stops."""
        manager = get_stop_manager()
        
        # Long position
        manager.add_position(
            position_id="long_pos",
            symbol="BTC/USDT",
            entry_price=50000.0,
            side="long",
            stop_config={"stop_loss_price": 45000.0}
        )
        
        # Short position
        manager.add_position(
            position_id="short_pos",
            symbol="BTC/USDT",
            entry_price=50000.0,
            side="short",
            stop_config={"stop_loss_price": 55000.0}
        )
        
        # Long stops at lower price
        should_exit_long, _ = manager.check_exits("long_pos", 44000.0)
        assert should_exit_long is True
        
        # Short stops at higher price
        should_exit_short, _ = manager.check_exits("short_pos", 56000.0)
        assert should_exit_short is True
    
    def test_hard_exit_time_in_execution(self):
        """Verify hard exit time limit works in execution."""
        manager = get_stop_manager()
        
        # Create position with 1 minute hard exit
        manager.add_position(
            position_id="time_exit_pos",
            symbol="BTC/USDT",
            entry_price=50000.0,
            side="long",
            stop_config={"hard_exit_time_minutes": 1}
        )
        
        # Immediately after entry - no exit
        should_exit, reason = manager.check_exits("time_exit_pos", 50500.0)
        assert should_exit is False
        
        # Get the position and backdating entry time
        pos = manager.positions["time_exit_pos"]
        pos.entry_time = datetime.utcnow() - timedelta(minutes=2)
        
        # After hard exit time - should exit
        should_exit, reason = manager.check_exits("time_exit_pos", 50500.0)
        assert should_exit is True
        assert "time" in reason.lower()
    
    def test_breakeven_protection_in_execution(self):
        """Verify breakeven protection activates during execution."""
        manager = get_stop_manager()
        
        manager.add_position(
            position_id="breakeven_pos",
            symbol="BTC/USDT",
            entry_price=50000.0,
            side="long",
            stop_config={
                "stop_loss_price": 45000.0,
                "breakeven_trigger_percent": 5.0
            }
        )
        
        # At 2% profit - breakeven shouldn't activate
        pos = manager.positions["breakeven_pos"]
        assert pos.check_breakeven_protection(51000.0) is False
        assert pos.stop_loss_price == 45000.0
        
        # At 6% profit - breakeven should activate  
        assert pos.check_breakeven_protection(53000.0) is True
        assert pos.stop_loss_price == 50000.0
    
    def test_concurrent_position_exits(self):
        """Verify multiple positions can exit simultaneously."""
        manager = get_stop_manager()
        
        # Add 3 positions
        for i in range(3):
            manager.add_position(
                position_id=f"concurrent_pos_{i}",
                symbol="BTC/USDT",
                entry_price=50000.0,
                side="long",
                stop_config={"stop_loss_price": 45000.0}
            )
        
        # All should exit at same price
        exits = {}
        for i in range(3):
            should_exit, _ = manager.check_exits(f"concurrent_pos_{i}", 44000.0)
            exits[f"concurrent_pos_{i}"] = should_exit
        
        # All exited
        assert all(exits.values())
    
    def test_partial_exit_scenario(self):
        """Verify some positions exit while others continue."""
        manager = get_stop_manager()
        
        # Position 1: tight stop
        manager.add_position(
            position_id="tight_stop",
            symbol="BTC/USDT",
            entry_price=50000.0,
            side="long",
            stop_config={"stop_loss_price": 48000.0}
        )
        
        # Position 2: wide stop
        manager.add_position(
            position_id="wide_stop",
            symbol="BTC/USDT",
            entry_price=50000.0,
            side="long",
            stop_config={"stop_loss_price": 40000.0}
        )
        
        # Price drops to 47000 - only tight stop triggered
        exit_tight, _ = manager.check_exits("tight_stop", 47000.0)
        exit_wide, _ = manager.check_exits("wide_stop", 47000.0)
        
        assert exit_tight is True
        assert exit_wide is False


class TestStopExecutionWorkflow:
    """Test realistic execution workflow with stops."""
    
    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Reset stop manager before each test."""
        reset_stop_manager()
        yield
        reset_stop_manager()
    
    def test_complete_long_trade_workflow(self):
        """Simulate complete long trade workflow with stops."""
        manager = get_stop_manager()
        
        # Entry: Open position with stops
        entry_price = 50000.0
        pos = manager.add_position(
            position_id="workflow_pos_1",
            symbol="BTC/USDT",
            entry_price=entry_price,
            side="long",
            stop_config={
                "stop_loss_price": 48000.0,      # 4% below entry
                "take_profit_price": 55000.0,    # 10% above entry
                "trailing_stop_percent": 2.0
            }
        )
        
        # Simulate price movements
        price_movements = [
            50500.0,   # Slight up
            51000.0,   # More up
            52000.0,   # Continue up
            53000.0,   # Continue up - trailing stop activates
            54000.0,   # Even higher
            55000.0,   # Hit take profit
        ]
        
        exit_triggered = False
        for price in price_movements:
            should_exit, reason = manager.check_exits("workflow_pos_1", price)
            if should_exit:
                exit_triggered = True
                assert "take_profit" in reason.lower()
                break
        
        assert exit_triggered
    
    def test_complete_short_trade_workflow(self):
        """Simulate complete short trade workflow with stops."""
        manager = get_stop_manager()
        
        # Entry: Open short with stops
        entry_price = 50000.0
        manager.add_position(
            position_id="workflow_pos_2",
            symbol="BTC/USDT",
            entry_price=entry_price,
            side="short",
            stop_config={
                "stop_loss_price": 52000.0,      # 4% above entry
                "take_profit_price": 45000.0,    # 10% below entry
                "trailing_stop_percent": 2.0
            }
        )
        
        # Simulate price movements
        price_movements = [
            49500.0,   # Down - good
            49000.0,   # More down
            48000.0,   # Continue down
            47000.0,   # Continue down
            46000.0,   # Almost at profit
            45000.0,   # Hit take profit
        ]
        
        exit_triggered = False
        for price in price_movements:
            should_exit, reason = manager.check_exits("workflow_pos_2", price)
            if should_exit:
                exit_triggered = True
                assert "take_profit" in reason.lower()
                break
        
        assert exit_triggered


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
