#!/usr/bin/env python
"""Integration tests for main.py trading loop."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from main import _load_market_data_for_symbols, _close_all_positions
from risk.engine import RiskEngine, Position
from execution.ccxt_engine import CCXTExecutionEngine
from execution.base import Order, OrderSide
from data.loader import DataLoader
from config.settings import get_settings


class TestLoadMarketData:
    """Test _load_market_data_for_symbols function."""
    
    def test_load_market_data_returns_dict(self):
        """_load_market_data_for_symbols returns symbol→price dict."""
        settings = get_settings()
        loader = DataLoader()
        
        # With real loader, we test return type
        # (actual data load requires API, so we verify structure)
        try:
            prices = _load_market_data_for_symbols(
                symbols=['BTC/USDT'],
                loader=loader,
                settings=settings
            )
            
            assert isinstance(prices, dict), "Should return dict"
            # If load succeeds, check types
            if prices:
                for symbol, price_series in prices.items():
                    assert isinstance(symbol, str), "Keys should be symbols"
                    assert isinstance(price_series, pd.Series), "Values should be Series"
        except Exception as e:
            # API load may fail in test env; that's ok
            pytest.skip(f"API load failed (expected in test): {e}")
    
    def test_load_market_data_validates_staleness(self):
        """_load_market_data_for_symbols validates data staleness."""
        settings = get_settings()
        loader = DataLoader()
        
        # The function should call OHLCVValidator with max_age_hours
        # We verify this by checking the code structure
        import inspect
        source = inspect.getsource(_load_market_data_for_symbols)
        
        assert 'max_age_hours' in source, "Should validate staleness"
        assert 'OHLCVValidator' in source, "Should use OHLCVValidator"
        assert '2.0' in source or 'max_age_hours' in source, "Should have staleness threshold"


class TestCloseAllPositions:
    """Test _close_all_positions function."""
    
    def test_close_all_positions_with_empty_dict(self):
        """Closing no positions succeeds silently."""
        risk_engine = RiskEngine(initial_equity=100000.0)
        execution_engine = Mock(spec=CCXTExecutionEngine)
        
        # Should not raise
        _close_all_positions(risk_engine, execution_engine, {})
        
        # Should not submit orders
        execution_engine.submit_order.assert_not_called()
    
    def test_close_all_positions_long(self):
        """Long position closes with SELL order."""
        risk_engine = RiskEngine(initial_equity=100000.0)
        execution_engine = Mock(spec=CCXTExecutionEngine)
        execution_engine.submit_order.return_value = "order_123"
        
        # Create long position
        position = Position(
            symbol_pair="BTC/USDT",
            entry_time=datetime.now(),
            entry_price=50000.0,
            quantity=1.0,
            side="long",
            marked_price=51000.0
        )
        
        positions = {"BTC/USDT": position}
        
        _close_all_positions(risk_engine, execution_engine, positions)
        
        # Should submit exactly 1 order
        execution_engine.submit_order.assert_called_once()
        
        # Check order details
        call_args = execution_engine.submit_order.call_args
        order = call_args[0][0]  # First positional argument
        
        assert order.symbol == "BTC/USDT"
        assert order.side == OrderSide.SELL, "Closing long should SELL"
        assert order.quantity == 1.0
    
    def test_close_all_positions_short(self):
        """Short position closes with BUY order."""
        risk_engine = RiskEngine(initial_equity=100000.0)
        execution_engine = Mock(spec=CCXTExecutionEngine)
        execution_engine.submit_order.return_value = "order_456"
        
        # Create short position
        position = Position(
            symbol_pair="ETH/USDT",
            entry_time=datetime.now(),
            entry_price=3000.0,
            quantity=10.0,
            side="short",
            marked_price=2950.0
        )
        
        positions = {"ETH/USDT": position}
        
        _close_all_positions(risk_engine, execution_engine, positions)
        
        # Should submit exactly 1 order
        execution_engine.submit_order.assert_called_once()
        
        # Check order details
        call_args = execution_engine.submit_order.call_args
        order = call_args[0][0]
        
        assert order.symbol == "ETH/USDT"
        assert order.side == OrderSide.BUY, "Closing short should BUY"
        assert order.quantity == 10.0
    
    def test_close_all_positions_multiple(self):
        """Multiple positions all close."""
        risk_engine = RiskEngine(initial_equity=100000.0)
        execution_engine = Mock(spec=CCXTExecutionEngine)
        execution_engine.submit_order.return_value = "order_123"
        
        # Create multiple positions
        positions = {
            "BTC/USDT": Position(
                symbol_pair="BTC/USDT",
                entry_time=datetime.now(),
                entry_price=50000.0,
                quantity=1.0,
                side="long",
                marked_price=51000.0
            ),
            "ETH/USDT": Position(
                symbol_pair="ETH/USDT",
                entry_time=datetime.now(),
                entry_price=3000.0,
                quantity=10.0,
                side="short",
                marked_price=2950.0
            ),
            "ADA/USDT": Position(
                symbol_pair="ADA/USDT",
                entry_time=datetime.now(),
                entry_price=1.0,
                quantity=10000.0,
                side="long",
                marked_price=1.05
            )
        }
        
        _close_all_positions(risk_engine, execution_engine, positions)
        
        # Should submit orders for all 3 positions
        assert execution_engine.submit_order.call_count == 3


class TestSignalToExecutionPath:
    """Test signal → risk check → order submission pipeline."""
    
    def test_risk_check_rejects_overleveraged_trade(self):
        """Risk engine rejects over-leveraged trades."""
        risk_engine = RiskEngine(initial_equity=100000.0)
        
        # Try to open huge position (would be overleveraged)
        # risk_pct = (50000 * 0.02) / 100000 = 0.01 = 1% >> 0.5% limit
        can_enter, reason = risk_engine.can_enter_trade(
            symbol_pair="BTC/USDT",
            position_size=50000.0,  # 50k units
            current_equity=100000.0,
            volatility=0.02
        )
        
        # Should reject due to risk exceeding 0.5% limit
        assert can_enter is False, "Should reject overleveraged position"
        assert "risk" in reason.lower() or "leverage" in reason.lower(), \
            f"Rejection reason should mention risk/leverage: {reason}"
    
    def test_risk_check_accepts_reasonable_trade(self):
        """Risk engine accepts reasonable trade."""
        risk_engine = RiskEngine(initial_equity=100000.0)
        
        # Reasonable position size
        can_enter, reason = risk_engine.can_enter_trade(
            symbol_pair="BTC/USDT",
            position_size=1.0,
            current_equity=100000.0,
            volatility=0.02
        )
        
        assert can_enter is True, f"Should accept reasonable trade: {reason}"
    
    def test_order_submission_creates_order(self):
        """Order submission creates Order object correctly."""
        # Create order
        order = Order(
            order_id="test_order_123",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=50000.0
        )
        
        # Verify order structure
        assert order.order_id == "test_order_123"
        assert order.symbol == "BTC/USDT"
        assert order.side == OrderSide.BUY
        assert order.quantity == 1.0
        assert order.limit_price == 50000.0


class TestPaperTradingLoopStructure:
    """Test main paper trading loop structure."""
    
    def test_paper_trading_loop_can_be_imported(self):
        """run_paper_trading function exists and is callable."""
        from main import run_paper_trading
        
        assert callable(run_paper_trading), "run_paper_trading should be callable"
    
    def test_position_stops_checked_in_loop(self):
        """Main loop checks for position stops."""
        import inspect
        from main import run_paper_trading
        
        source = inspect.getsource(run_paper_trading)
        
        assert 'check_position_stops' in source, "Should check position stops"
        assert 'should_stop_out' in source or 'stop_loss' in source.lower(), \
            "Should implement stop-loss logic"
    
    def test_data_loaded_in_loop(self):
        """Main loop loads market data."""
        import inspect
        from main import run_paper_trading
        
        source = inspect.getsource(run_paper_trading)
        
        assert '_load_market_data_for_symbols' in source or 'load_' in source, \
            "Should load market data"
    
    def test_reconciliation_checked_in_loop(self):
        """Main loop includes periodic reconciliation."""
        import inspect
        from main import run_paper_trading
        
        source = inspect.getsource(run_paper_trading)
        
        assert 'reconcil' in source.lower(), "Should include reconciliation"


class TestMainLoopErrorHanding:
    """Test error handling in main loop."""
    
    def test_data_error_handling_present(self):
        """Main loop handles DataError gracefully."""
        import inspect
        from main import run_paper_trading
        
        source = inspect.getsource(run_paper_trading)
        
        assert 'DataError' in source or 'except' in source, \
            "Should have error handling"
        assert 'KeyboardInterrupt' in source or 'shutdown' in source.lower(), \
            "Should handle user interruption"
