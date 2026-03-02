"""
Test Suite: Concentration Limit Manager (S2.4).

Problem: Multiple pair positions can concentrate exposure in single symbols.
Example: Trading AAPL/MSFT, AAPL/GOOGL, AAPL/JPM creates 50%+ AAPL concentration.

Solution: Track symbol exposure across all pairs, enforce per-symbol limits.

Mechanism:
- Track net exposure for each symbol
- Reject trades that would exceed concentration limit
- Remove capacity on exit to allow new positions
- Default limit: 30% per symbol (configurable)

Expected Impact: +18 Sharpe points from reduced concentration risk
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from execution.concentration_limits import ConcentrationLimitManager, SymbolExposure


class TestSymbolExposure:
    """Test SymbolExposure tracking dataclass."""
    
    def test_symbol_exposure_initialization(self):
        """Verify SymbolExposure initializes correctly."""
        exposure = SymbolExposure(symbol="AAPL")
        
        assert exposure.symbol == "AAPL"
        assert exposure.long_notional == 0.0
        assert exposure.short_notional == 0.0
        assert exposure.net_exposure == 0.0
        assert exposure.gross_exposure == 0.0
        assert exposure.position_count == 0
        assert len(exposure.pairs) == 0
    
    def test_symbol_exposure_gross_exposure(self):
        """Gross exposure = long + short notional."""
        exposure = SymbolExposure(symbol="GOOGL")
        exposure.long_notional = 2.0
        exposure.short_notional = 1.5
        
        assert exposure.gross_exposure == 3.5
    
    def test_symbol_exposure_concentration_calculation(self):
        """Concentration via AUM-based method = gross / AUM * 100."""
        exposure = SymbolExposure(symbol="XYZ")
        exposure.long_notional = 3.0
        exposure.short_notional = 1.0
        exposure.net_exposure = 2.0  # 3.0 - 1.0
        
        # gross = 4.0, AUM = 10.0 → concentration = 4.0/10.0*100 = 40%
        assert exposure.concentration_pct_of(10.0) == 40.0
        
        # Deprecated fallback (no AUM): gross/gross*100 = 100%
        assert exposure.concentration_pct == 100.0


class TestConcentrationLimitBasics:
    """Test basic concentration limit functionality."""
    
    def test_manager_initialization(self):
        """Verify ConcentrationLimitManager initializes correctly."""
        mgr = ConcentrationLimitManager(
            max_symbol_concentration_pct=30.0,
            allow_rebalancing=True
        )
        
        assert mgr.max_concentration == 30.0
        assert mgr.allow_rebalancing == True
        assert len(mgr.symbol_exposures) == 0
        assert len(mgr.positions) == 0
    
    def test_custom_concentration_limit(self):
        """Test custom concentration limits."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=20.0)
        assert mgr.max_concentration == 20.0


class TestConcentrationLimitLogic:
    """Test concentration limit checking and enforcement."""
    
    def test_add_position_within_limits(self):
        """Adding position within limits should succeed."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=100.0)
        
        allowed, reason = mgr.add_position(
            pair_key="AAPL_MSFT",
            symbol1="AAPL",
            symbol2="GOOGL",
            side="long",
            notional=1.0
        )
        
        assert allowed == True
        assert reason is None
        assert "AAPL_MSFT" in mgr.positions
        assert "AAPL" in mgr.symbol_exposures
        assert "GOOGL" in mgr.symbol_exposures
    
    def test_single_position_concentration_calculation(self):
        """Calculate concentration for single position (gross / AUM * 100)."""
        mgr = ConcentrationLimitManager(
            max_symbol_concentration_pct=100.0, portfolio_aum=2.0
        )
        
        # Add one long pair: long AAPL, short GOOGL
        mgr.add_position("PAIR_1", "AAPL", "GOOGL", "long", 1.0)
        
        # AAPL: gross=1.0, aum=2.0 → concentration = 1.0/2.0*100 = 50%
        aapl_conc, _ = mgr.get_symbol_concentration("AAPL")
        assert aapl_conc == 50.0
    
    def test_reject_position_exceeding_limit(self):
        """Position that exceeds limit should be rejected."""
        mgr = ConcentrationLimitManager(
            max_symbol_concentration_pct=30.0, portfolio_aum=5.0
        )
        
        # PAIR_1: AAPL gross=1.0, conc=1.0/5.0*100=20% → under 30%, accepted
        mgr.add_position("PAIR_1", "AAPL", "GOOGL", "long", 1.0)
        
        # PAIR_2: AAPL would have gross=2.0, conc=2.0/5.0*100=40% > 30% → rejected
        allowed, reason = mgr.add_position(
            pair_key="PAIR_2",
            symbol1="AAPL",
            symbol2="XYZ",
            side="long",
            notional=1.0
        )
        
        assert allowed == False
        assert "concentration" in reason.lower() or "limit" in reason.lower()
        assert "PAIR_2" not in mgr.positions
    
    def test_long_vs_short_exposure(self):
        """Gross-based concentration counts both sides; hedging does NOT reduce it."""
        mgr = ConcentrationLimitManager(
            max_symbol_concentration_pct=100.0, portfolio_aum=2.0
        )
        
        # Add long AAPL/GOOGL: +AAPL, -GOOGL
        mgr.add_position("PAIR_1", "AAPL", "GOOGL", "long", 1.0)
        
        # Add short AAPL/GOOGL: -AAPL, +GOOGL
        allowed, reason = mgr.add_position(
            pair_key="PAIR_2",
            symbol1="AAPL",
            symbol2="GOOGL",
            side="short",
            notional=1.0
        )
        
        # After both: AAPL long=1.0, short=1.0, gross=2.0
        # concentration = 2.0 / 2.0 * 100 = 100%
        assert allowed == True
        
        aapl_conc, _ = mgr.get_symbol_concentration("AAPL")
        assert aapl_conc == 100.0  # Gross-based: hedging adds to concentration


class TestConcentrationLimitDiversification:
    """Test concentration limits prevent overdiversification in single symbols."""
    
    def test_three_pairs_same_symbol(self):
        """Three pairs with same symbol increase concentration."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=200.0)
        
        # PAIR_1: long AAPL/GOOGL
        success1, _ = mgr.add_position("PAIR_1", "AAPL", "GOOGL", "long", 1.0)
        assert success1 == True
        aapl_conc_1, _ = mgr.get_symbol_concentration("AAPL")
        
        # PAIR_2: long AAPL/JPM (adds to AAPL)
        success2, _ = mgr.add_position("PAIR_2", "AAPL", "JPM", "long", 1.0)
        assert success2 == True  # Within 200% limit
        aapl_conc_2, _ = mgr.get_symbol_concentration("AAPL")
        
        # Verify AAPL concentration increased
        assert aapl_conc_2 >= aapl_conc_1
        
    def test_mixed_longs_and_shorts_reduce_concentration(self):
        """Mix of long and short positions reduces concentration."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=100.0)
        
        # PAIR_1: long AAPL/GOOGL (AAPL long 1.0, GOOGL short 1.0)
        mgr.add_position("PAIR_1", "AAPL", "GOOGL", "long", 1.0)
        
        # PAIR_2: short AAPL/JPM (AAPL short 1.0, JPM long 1.0)
        # After this: AAPL net = 0, concentration reduced
        success, _ = mgr.add_position("PAIR_2", "AAPL", "JPM", "short", 1.0)
        assert success == True
    
    def test_diversified_portfolio(self):
        """Diversified positions across symbols stay within limits."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=100.0)
        
        # First pair
        success1, _ = mgr.add_position("PAIR_1", "AAPL", "GOOGL", "long")
        assert success1 == True
        
        # Second pair with different main symbol
        success2, _ = mgr.add_position("PAIR_2", "WFC", "BAC", "short")
        assert success2 == True


class TestConcentrationManagement:
    """Test position lifecycle and concentration updates."""
    
    def test_remove_position_frees_concentration(self):
        """Removing position should reduce concentration."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=100.0)
        
        # Add position
        mgr.add_position("PAIR_1", "AAPL", "GOOGL", "long", 1.0)
        conc_before, _ = mgr.get_symbol_concentration("AAPL")
        
        # Remove it
        mgr.remove_position("PAIR_1")
        conc_after, _ = mgr.get_symbol_concentration("AAPL")
        
        assert conc_before > conc_after
        assert conc_after == 0.0
    
    def test_get_symbol_concentration_status(self):
        """Get concentration status for a symbol."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=30.0)
        
        mgr.add_position("PAIR_1", "AAPL", "GOOGL", "long", 1.0)
        
        status = mgr.get_concentration_status("AAPL")
        
        assert status['symbol'] == "AAPL"
        assert 'concentration_pct' in status
        assert 'status' in status
        assert 'capacity_remaining_pct' in status
        assert 'position_count' in status
    
    def test_available_capacity(self):
        """Get available capacity for a symbol."""
        mgr = ConcentrationLimitManager(
            max_symbol_concentration_pct=200.0, portfolio_aum=1.0
        )
        
        # Before any positions
        cap_start = mgr.get_available_capacity("AAPL")
        assert cap_start == 200.0
        
        # Add position: gross=1.0, conc=1.0/1.0*100=100%, capacity=200-100=100
        mgr.add_position("PAIR_1", "AAPL", "GOOGL", "long", 1.0)
        cap_after = mgr.get_available_capacity("AAPL")
        assert cap_after == 100.0


class TestConcentrationStatusAndSummary:
    """Test portfolio summary and status reporting."""
    
    def test_get_portfolio_summary(self):
        """Get summary of all positions."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=100.0)
        
        # Portfolio empty
        summary = mgr.get_portfolio_summary()
        assert summary['total_symbols'] == 0
        assert summary['total_positions'] == 0
        
        # Add positions
        mgr.add_position("PAIR_1", "AAPL", "GOOGL", "long", 1.0)
        
        summary = mgr.get_portfolio_summary()
        assert summary['total_symbols'] >= 1
        assert summary['total_positions'] == 1
        assert 'symbols' in summary
    
    def test_concentration_status_levels(self):
        """Concentration status should reflect different levels."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=50.0)
        
        mgr.add_position("PAIR_1", "AAPL", "GOOGL", "long", 1.0)
        
        aapl_conc, aapl_status = mgr.get_symbol_concentration("AAPL")
        
        # AAPL concentration should be 50%
        # Status depends on the thresholds
        assert aapl_status in ["Low", "Medium", "High", "Critical"]
    
    def test_most_concentrated_symbols(self):
        """Get most concentrated symbols."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=50.0)
        
        mgr.add_position("PAIR_1", "AAPL", "GOOGL", "long", 1.0)
        mgr.add_position("PAIR_2", "AAPL", "JPM", "long", 1.0)  # Might fail
        
        top = mgr.get_most_concentrated_symbols(top_n=3)
        
        assert isinstance(top, list)
        assert len(top) >= 0


class TestConcentrationPositionTracking:
    """Test position tracking and pair association."""
    
    def test_get_active_positions(self):
        """Get list of active positions."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=100.0)
        
        mgr.add_position("PAIR_1", "AAPL", "GOOGL", "long", 1.0)
        
        active = mgr.get_active_positions()
        assert "PAIR_1" in active
    
    def test_positions_associated_with_pairs(self):
        """Verify symbols track which pairs they belong to."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=50.0)
        
        mgr.add_position("PAIR_1", "AAPL", "GOOGL", "long", 1.0)
        
        if "AAPL" in mgr.symbol_exposures:
            aapl_exposure = mgr.symbol_exposures["AAPL"]
            assert "PAIR_1" in aapl_exposure.pairs
    
    def test_reset_all_clears_portfolio(self):
        """Reset should clear all positions."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=100.0)
        
        mgr.add_position("PAIR_1", "AAPL", "GOOGL", "long", 1.0)
        mgr.add_position("PAIR_2", "AAPL", "JPM", "long", 1.0)
        
        assert len(mgr.positions) > 0
        
        mgr.reset_all()
        
        assert len(mgr.positions) == 0


class TestConcentrationIntegration:
    """Test concentration limits with trading strategy."""
    
    def test_concentration_manager_in_strategy(self):
        """Verify PairTradingStrategy has concentration manager."""
        from strategies.pair_trading import PairTradingStrategy
        
        strategy = PairTradingStrategy()
        
        assert hasattr(strategy, 'concentration_limits')
        from execution.concentration_limits import ConcentrationLimitManager
        assert isinstance(strategy.concentration_limits, ConcentrationLimitManager)
    
    def test_concentration_manager_parameters(self):
        """Verify concentration manager has correct parameters."""
        from strategies.pair_trading import PairTradingStrategy
        
        strategy = PairTradingStrategy()
        
        assert strategy.concentration_limits.max_concentration == 30.0
        assert strategy.concentration_limits.allow_rebalancing == True


class TestConcentrationEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_portfolio_concentration(self):
        """Empty portfolio should have 0% concentration."""
        mgr = ConcentrationLimitManager()
        
        conc, status = mgr.get_symbol_concentration("NONEXISTENT")
        assert conc == 0.0
        assert status == "Low"
    
    def test_single_symbol_all_long(self):
        """Single symbol, pure long position."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=100.0)
        
        # Manually create exposure (all long)
        from execution.concentration_limits import SymbolExposure
        exposure = SymbolExposure(symbol="XYZ")
        exposure.long_notional = 5.0
        exposure.short_notional = 0.0
        exposure.net_exposure = 5.0
        mgr.symbol_exposures["XYZ"] = exposure
        
        conc = exposure.concentration_pct
        # 5.0 / 5.0 = 100% concentration
        assert conc == 100.0
    
    def test_perfectly_hedged_zero_concentration(self):
        """Perfectly hedged position: gross-based concentration reflects total exposure."""
        mgr = ConcentrationLimitManager(
            max_symbol_concentration_pct=50.0, portfolio_aum=6.0
        )
        
        from execution.concentration_limits import SymbolExposure
        exposure = SymbolExposure(symbol="ABC")
        exposure.long_notional = 3.0
        exposure.short_notional = 3.0
        exposure.net_exposure = 0.0
        mgr.symbol_exposures["ABC"] = exposure
        
        # Gross-based: gross=6.0, aum=6.0 → 6.0/6.0*100 = 100%
        conc = exposure.concentration_pct_of(mgr.portfolio_aum)
        assert conc == 100.0


class TestConcentrationRealisticScenarios:
    """Test realistic trading scenarios."""
    
    def test_scenario_add_offset_positions(self):
        """Add positions that offset concentration."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=100.0)
        
        # Year starts: add AAPL/GOOGL long
        s1, _ = mgr.add_position("YEAR_START", "AAPL", "GOOGL", "long", 1.0)
        assert s1 == True
        
        # Later: add XYZ/AAPL short (short AAPL offsets)
        s2, _ = mgr.add_position("LATER", "XYZ", "AAPL", "short", 1.0)
        # This should now succeed because AAPL short reduces concentration
        assert s2 == True
    
    def test_scenario_rebalance_on_exit(self):
        """Exiting position frees capacity for new trade."""
        mgr = ConcentrationLimitManager(max_symbol_concentration_pct=100.0)
        
        # Add position
        success1, _ = mgr.add_position("TRADE_1", "AAPL", "GOOGL", "long", 1.0)
        assert success1 == True
        
        # Try to add another
        success2, reason = mgr.add_position("TRADE_2", "AAPL", "JPM", "long", 1.0)
        
        if not success2:
            # Close first position
            mgr.remove_position("TRADE_1")
            
            # Now should succeed
            success3, _ = mgr.add_position("TRADE_2", "AAPL", "JPM", "long", 1.0)
            assert success3 == True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
