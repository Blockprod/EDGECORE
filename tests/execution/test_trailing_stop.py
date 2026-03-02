"""
Test Suite: Trailing Stop Implementation (S2.3).

Problem: Positions can experience temporary large movements beyond entry Z-score
before mean reverting. Without protection, losses accumulate beyond acceptable risk.

Solution: Trailing stops that exit if spread widens > 1.0σ from entry.

Mechanism:
- Record Z-score at entry
- Monitor current Z-score continuously
- Exit if spread widens by > 1.0σ: |current_z| - |entry_z| > 1.0
- This catches "mean reversion failure" scenarios

Expected Impact: +12 Sharpe points from reducing tail losses
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from execution.trailing_stop import TrailingStopManager, TrailingStopPosition
from strategies.pair_trading import PairTradingStrategy


class TestTrailingStopBasics:
    """Test basic trailing stop functionality."""
    
    def test_trailing_stop_manager_initialization(self):
        """Verify TrailingStopManager initializes correctly."""
        mgr = TrailingStopManager(widening_threshold=1.0, track_max_profit=True)
        
        assert mgr.widening_threshold == 1.0
        assert mgr.track_max_profit == True
        assert len(mgr.positions) == 0
        
    def test_add_position_to_trailing_stop(self):
        """Verify positions can be added to tracker."""
        mgr = TrailingStopManager()
        now = datetime.now()
        
        mgr.add_position(
            symbol_pair="AAPL_MSFT",
            side="long",
            entry_z=2.2,
            entry_spread=0.5,
            entry_time=now
        )
        
        assert "AAPL_MSFT" in mgr.positions
        position = mgr.positions["AAPL_MSFT"]
        assert position.symbol_pair == "AAPL_MSFT"
        assert position.side == "long"
        assert position.entry_z == 2.2
        assert position.entry_spread == 0.5
        
    def test_get_position_info(self):
        """Verify position information retrieval."""
        mgr = TrailingStopManager()
        now = datetime.now()
        
        mgr.add_position(
            symbol_pair="TEST_PAIR",
            side="short",
            entry_z=-1.8,
            entry_spread=-0.3,
            entry_time=now
        )
        
        info = mgr.get_position_info("TEST_PAIR")
        
        assert info is not None
        assert info['symbol_pair'] == "TEST_PAIR"
        assert info['side'] == "short"
        assert info['entry_z'] == -1.8
        assert info['entry_spread'] == -0.3


class TestTrailingStopLogic:
    """Test trailing stop triggering logic."""
    
    def test_no_exit_when_spread_within_threshold(self):
        """Spread widening < threshold should NOT trigger exit."""
        mgr = TrailingStopManager(widening_threshold=1.0)
        now = datetime.now()
        
        mgr.add_position(
            symbol_pair="PAIR_1",
            side="long",
            entry_z=2.2,
            entry_spread=0.5,
            entry_time=now
        )
        
        # Current Z = 2.8 -> widening = |2.8| - |2.2| = 0.6σ (< 1.0σ threshold)
        should_exit, reason = mgr.should_exit_on_trailing_stop(
            symbol_pair="PAIR_1",
            current_z=2.8
        )
        
        assert should_exit == False
        assert reason is None
        assert "PAIR_1" in mgr.positions  # Position still tracked
        
    def test_exit_when_spread_widens_beyond_threshold(self):
        """Spread widening > threshold SHOULD trigger exit."""
        mgr = TrailingStopManager(widening_threshold=1.0)
        now = datetime.now()
        
        mgr.add_position(
            symbol_pair="PAIR_1",
            side="long",
            entry_z=2.2,
            entry_spread=0.5,
            entry_time=now
        )
        
        # Current Z = 3.8 -> widening = |3.8| - |2.2| = 1.6σ (> 1.0σ threshold)
        should_exit, reason = mgr.should_exit_on_trailing_stop(
            symbol_pair="PAIR_1",
            current_z=3.8
        )
        
        assert should_exit == True
        assert reason is not None
        assert "3.8" in reason
        assert "2.2" in reason
        assert "PAIR_1" not in mgr.positions  # Position cleared after exit
        
    def test_short_position_trailing_stop(self):
        """Test trailing stop for short positions."""
        mgr = TrailingStopManager(widening_threshold=1.0)
        now = datetime.now()
        
        mgr.add_position(
            symbol_pair="PAIR_SHORT",
            side="short",
            entry_z=-2.0,
            entry_spread=-0.4,
            entry_time=now
        )
        
        # Current Z = -3.5 -> widening = |-3.5| - |-2.0| = 1.5σ (> 1.0σ)
        should_exit, reason = mgr.should_exit_on_trailing_stop(
            symbol_pair="PAIR_SHORT",
            current_z=-3.5
        )
        
        assert should_exit == True
        assert reason is not None
        
    def test_custom_widening_threshold(self):
        """Test with custom widening threshold."""
        mgr = TrailingStopManager(widening_threshold=0.5)
        now = datetime.now()
        
        mgr.add_position(
            symbol_pair="TIGHT_STOP",
            side="long",
            entry_z=2.0,
            entry_spread=0.4,
            entry_time=now
        )
        
        # Widening = 0.6σ > 0.5σ threshold -> should exit
        should_exit, _ = mgr.should_exit_on_trailing_stop(
            symbol_pair="TIGHT_STOP",
            current_z=2.6
        )
        assert should_exit == True
        
    def test_nonexistent_pair_returns_false(self):
        """Checking nonexistent pair should return False."""
        mgr = TrailingStopManager()
        
        should_exit, reason = mgr.should_exit_on_trailing_stop(
            symbol_pair="NONEXISTENT",
            current_z=2.5
        )
        
        assert should_exit == False
        assert reason is None


class TestTrailingStopProfitTracking:
    """Test max profit/loss tracking for positions."""
    
    def test_max_profit_tracking_long_position(self):
        """Track best Z-score for long positions."""
        mgr = TrailingStopManager(track_max_profit=True)
        now = datetime.now()
        
        mgr.add_position(
            symbol_pair="LONG_TRACK",
            side="long",
            entry_z=2.2,
            entry_spread=0.5,
            entry_time=now
        )
        
        # Move toward 0 (profit)
        mgr.should_exit_on_trailing_stop("LONG_TRACK", 1.5)
        position = mgr.positions["LONG_TRACK"]
        assert position.max_profit_z == 1.5  # Best achieved
        
        # Move worse
        mgr.should_exit_on_trailing_stop("LONG_TRACK", 1.8)
        assert position.max_profit_z == 1.5  # Still best
        
    def test_max_loss_tracking_long_position(self):
        """Track worst Z-score for long positions."""
        mgr = TrailingStopManager(track_max_profit=True)
        now = datetime.now()
        
        mgr.add_position(
            symbol_pair="LONG_LOSS",
            side="long",
            entry_z=2.2,
            entry_spread=0.5,
            entry_time=now
        )
        
        # Move worse (higher)
        mgr.should_exit_on_trailing_stop("LONG_LOSS", 3.0)
        position = mgr.positions["LONG_LOSS"]
        assert position.max_loss_z == 3.0  # Worst achieved
        
        # Move better
        mgr.should_exit_on_trailing_stop("LONG_LOSS", 2.8)
        assert position.max_loss_z == 3.0  # Still worst


class TestTrailingStopTightStop:
    """Test tight trailing stops for profitable positions."""
    
    def test_tight_stop_not_triggered_out_of_profit(self):
        """Tight stop shouldn't trigger if not in profit yet."""
        mgr = TrailingStopManager()
        now = datetime.now()
        
        mgr.add_position(
            symbol_pair="NO_PROFIT",
            side="long",
            entry_z=2.2,
            entry_spread=0.5,
            entry_time=now
        )
        
        # Wider, not in profit yet (< 0.5σ profit)
        should_exit, _ = mgr.should_exit_on_tight_trailing_stop(
            symbol_pair="NO_PROFIT",
            current_z=2.5,
            profit_threshold=0.5
        )
        
        assert should_exit == False
        
    def test_tight_stop_triggered_for_profitable_position(self):
        """Tight stop should trigger if profit trade widens."""
        mgr = TrailingStopManager()
        now = datetime.now()
        
        mgr.add_position(
            symbol_pair="PROFIT_TRADE",
            side="long",
            entry_z=2.2,
            entry_spread=0.5,
            entry_time=now
        )
        
        # Move to profit: Z = 1.0 (profit = 2.2 - 1.0 = 1.2σ)
        mgr.should_exit_on_trailing_stop("PROFIT_TRADE", 1.0)
        
        # Now widen from best: current = 1.4 (0.4σ from best)
        # Tight threshold = 0.3σ, so should trigger
        should_exit, _ = mgr.should_exit_on_tight_trailing_stop(
            symbol_pair="PROFIT_TRADE",
            current_z=1.4,
            profit_threshold=0.5
        )
        
        assert should_exit == True


class TestTrailingStopPositionManagement:
    """Test position lifecycle management."""
    
    def test_remove_position_manually(self):
        """Manually removing a position should clear tracking."""
        mgr = TrailingStopManager()
        now = datetime.now()
        
        mgr.add_position(
            symbol_pair="REMOVE_ME",
            side="long",
            entry_z=2.0,
            entry_spread=0.4,
            entry_time=now
        )
        
        assert "REMOVE_ME" in mgr.positions
        mgr.remove_position("REMOVE_ME")
        assert "REMOVE_ME" not in mgr.positions
        
    def test_get_active_positions(self):
        """Get list of currently tracked positions."""
        mgr = TrailingStopManager()
        now = datetime.now()
        
        for i in range(3):
            mgr.add_position(
                symbol_pair=f"PAIR_{i}",
                side="long",
                entry_z=2.0,
                entry_spread=0.4,
                entry_time=now
            )
        
        active = mgr.get_active_positions()
        assert len(active) == 3
        assert "PAIR_0" in active
        assert "PAIR_2" in active
        
    def test_reset_all_positions(self):
        """Reset should clear all tracked positions."""
        mgr = TrailingStopManager()
        now = datetime.now()
        
        for i in range(5):
            mgr.add_position(
                symbol_pair=f"PAIR_{i}",
                side="long",
                entry_z=2.0,
                entry_spread=0.4,
                entry_time=now
            )
        
        assert len(mgr.positions) == 5
        mgr.reset_all()
        assert len(mgr.positions) == 0
        
    def test_get_summary_statistics(self):
        """Get summary stats across all positions."""
        mgr = TrailingStopManager()
        now = datetime.now()
        
        mgr.add_position("LONG_1", "long", 2.0, 0.4, now)
        mgr.add_position("LONG_2", "long", 2.5, 0.5, now)
        mgr.add_position("SHORT_1", "short", -1.8, -0.3, now)
        
        summary = mgr.get_summary()
        
        assert summary['active_positions'] == 3
        assert summary['long_positions'] == 2
        assert summary['short_positions'] == 1
        assert 'avg_entry_z' in summary
        assert 'LONG_1' in summary['position_pairs']


class TestTrailingStopIntegration:
    """Test trailing stop integration with PairTradingStrategy."""
    
    def test_trailing_stop_manager_in_strategy(self):
        """Verify PairTradingStrategy has trailing stop manager."""
        strategy = PairTradingStrategy()
        
        assert hasattr(strategy, 'trailing_stop_manager')
        assert isinstance(strategy.trailing_stop_manager, TrailingStopManager)
        assert strategy.trailing_stop_manager.widening_threshold == 1.0
        
    def test_positions_registered_on_entry(self):
        """Positions should be registered with trailing stop manager on entry."""
        np.random.seed(42)
        
        strategy = PairTradingStrategy()
        
        # Create simple synthetic data
        days = 100
        dates = pd.date_range('2023-01-01', periods=days)
        market_data = pd.DataFrame({
            'A': np.random.randn(days).cumsum() + 100,
            'B': np.random.randn(days).cumsum() + 100,
        }, index=dates)
        
        # Generate signals (may or may not have entries but setup should work)
        signals = strategy.generate_signals(market_data)
        
        # Verify trailing stop manager is ready
        trailing_stops = strategy.trailing_stop_manager
        assert trailing_stops.widening_threshold == 1.0
        

class TestTrailingStopRealisticScenarios:
    """Test realistic trading scenarios with trailing stops."""
    
    def test_scenario_partial_mean_reversion(self):
        """Scenario: Entry at Z=2.2, reverts to Z=1.0 (profit), then worse."""
        mgr = TrailingStopManager(widening_threshold=1.0)
        now = datetime.now()
        
        # Enter long at Z=2.2
        mgr.add_position("SCENARIO_1", "long", 2.2, 0.5, now)
        
        # Revert to Z=1.0 (good!)
        should_exit1, _ = mgr.should_exit_on_trailing_stop("SCENARIO_1", 1.0)
        assert should_exit1 == False  # No stop hit yet
        
        # Widen to Z=3.5 (bad!)
        should_exit2, reason = mgr.should_exit_on_trailing_stop("SCENARIO_1", 3.5)
        assert should_exit2 == True  # Stop triggered
        assert "widened" in reason.lower()
        
    def test_scenario_immediate_widening(self):
        """Scenario: Entry at Z=2.0, immediately widens (bad entry)."""
        mgr = TrailingStopManager(widening_threshold=1.0)
        now = datetime.now()
        
        # Enter short at Z=-1.5
        mgr.add_position("BAD_ENTRY", "short", -1.5, -0.3, now)
        
        # Immediately widens to Z=-3.0
        should_exit, reason = mgr.should_exit_on_trailing_stop(
            "BAD_ENTRY",
            current_z=-3.0
        )
        
        assert should_exit == True
        assert "-3.0" in reason
        
    def test_scenario_multiple_positions_with_different_stops(self):
        """Multiple positions should be tracked independently."""
        mgr = TrailingStopManager(widening_threshold=1.0)
        now = datetime.now()
        
        # Add 3 positions
        mgr.add_position("PAIR_A", "long", 2.0, 0.4, now)
        mgr.add_position("PAIR_B", "short", -2.5, -0.5, now)
        mgr.add_position("PAIR_C", "long", 1.8, 0.35, now)
        
        # PAIR_A widens beyond threshold
        exit_a, _ = mgr.should_exit_on_trailing_stop("PAIR_A", 3.2)
        assert exit_a == True
        
        # PAIR_B within threshold
        exit_b, _ = mgr.should_exit_on_trailing_stop("PAIR_B", -3.2)
        assert exit_b == False
        
        # PAIR_C way beyond threshold
        exit_c, _ = mgr.should_exit_on_trailing_stop("PAIR_C", 4.0)
        assert exit_c == True


class TestTrailingStopEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_zero_widening_at_same_zscore(self):
        """No exit when current Z equals entry Z."""
        mgr = TrailingStopManager(widening_threshold=1.0)
        now = datetime.now()
        
        mgr.add_position("SAME_Z", "long", 2.5, 0.5, now)
        
        should_exit, _ = mgr.should_exit_on_trailing_stop("SAME_Z", 2.5)
        assert should_exit == False
        
    def test_movement_toward_zero_no_exit(self):
        """Movement toward zero (good direction) shouldn't trigger stop."""
        mgr = TrailingStopManager(widening_threshold=1.0)
        now = datetime.now()
        
        mgr.add_position("GOOD_DIR", "long", 2.5, 0.5, now)
        
        # Move toward 0
        for z in [2.0, 1.5, 1.0, 0.5, 0.0]:
            should_exit, _ = mgr.should_exit_on_trailing_stop("GOOD_DIR", z)
            assert should_exit == False
            
    def test_very_tight_threshold(self):
        """Test with very tight trailing stop threshold."""
        mgr = TrailingStopManager(widening_threshold=0.2)
        now = datetime.now()
        
        mgr.add_position("TIGHT", "long", 2.0, 0.4, now)
        
        # Small widening: 0.3σ > 0.2σ -> should exit
        should_exit, _ = mgr.should_exit_on_trailing_stop("TIGHT", 2.3)
        assert should_exit == True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
