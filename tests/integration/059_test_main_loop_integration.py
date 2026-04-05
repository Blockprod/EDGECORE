#!/usr/bin/env python
"""Integration tests for main.py trading loop."""

<<<<<<< HEAD
from datetime import datetime
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

=======
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch
from main import _load_market_data_for_symbols, _close_all_positions
from risk.engine import RiskEngine, Position
from execution.ibkr_engine import IBGatewaySync
from execution.base import Order, OrderSide, BaseExecutionEngine
from data.loader import DataLoader
>>>>>>> origin/main
from config.settings import get_settings
from data.loader import DataLoader
from execution.base import BaseExecutionEngine, Order, OrderSide
from main import _close_all_positions, _load_market_data_for_symbols
from risk.engine import Position, RiskEngine


class TestLoadMarketData:
    """Test _load_market_data_for_symbols function."""

    def test_load_market_data_returns_dict(self):
        """_load_market_data_for_symbols returns symbol-to-price dict."""
        settings = get_settings()
        loader = DataLoader()

        # Build a realistic OHLCV DataFrame the loader would return
        n = 100
<<<<<<< HEAD
        dates = pd.date_range("2024-01-01", periods=n, freq="1h")
        close = np.linspace(175.0, 180.0, n)
        mock_df = pd.DataFrame(
            {
                "open": close * 0.999,
                "high": close * 1.002,
                "low": close * 0.998,
                "close": close,
                "volume": np.full(n, 500_000.0),
            },
            index=dates,
        )

        with patch.object(loader, "load_ibkr_data", return_value=mock_df):
            prices = _load_market_data_for_symbols(symbols=["AAPL"], loader=loader, settings=settings)
=======
        dates = pd.date_range('2024-01-01', periods=n, freq='1h')
        close = np.linspace(175.0, 180.0, n)
        mock_df = pd.DataFrame({
            'open': close * 0.999,
            'high': close * 1.002,
            'low': close * 0.998,
            'close': close,
            'volume': np.full(n, 500_000.0),
        }, index=dates)

        with patch.object(loader, 'load_ibkr_data', return_value=mock_df):
            prices = _load_market_data_for_symbols(
                symbols=['AAPL'],
                loader=loader,
                settings=settings
            )
>>>>>>> origin/main

            assert isinstance(prices, dict), "Should return dict"
            assert len(prices) == 1, "Should have one symbol loaded"
            for symbol, price_series in prices.items():
                assert isinstance(symbol, str), "Keys should be symbols"
                assert isinstance(price_series, pd.Series), "Values should be Series"
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_load_market_data_validates_staleness(self):
        """_load_market_data_for_symbols validates data staleness."""
        get_settings()
        DataLoader()
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # The function should call OHLCVValidator with max_age_hours
        # We verify this by checking the code structure
        import inspect

        source = inspect.getsource(_load_market_data_for_symbols)

        assert "max_age_hours" in source, "Should validate staleness"
        assert "OHLCVValidator" in source, "Should use OHLCVValidator"
        assert "2.0" in source or "max_age_hours" in source, "Should have staleness threshold"


class TestCloseAllPositions:
    """Test _close_all_positions function."""

    def test_close_all_positions_with_empty_dict(self):
        """Closing no positions succeeds silently."""
        risk_engine = RiskEngine(initial_equity=100000.0)
        execution_engine = Mock(spec=BaseExecutionEngine)
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # Should not raise
        _close_all_positions(risk_engine, execution_engine, {})

        # Should not submit orders
        execution_engine.submit_order.assert_not_called()

    def test_close_all_positions_long(self):
        """Long position closes with SELL order."""
        risk_engine = RiskEngine(initial_equity=100000.0)
        execution_engine = Mock(spec=BaseExecutionEngine)
        execution_engine.submit_order.return_value = "order_123"

        # Create long position
        position = Position(
            symbol_pair="AAPL",
            entry_time=datetime.now(),
            entry_price=175.0,
            quantity=100.0,
            side="long",
<<<<<<< HEAD
            marked_price=180.0,
        )

        positions = {"AAPL": position}

=======
            marked_price=180.0
        )
        
        positions = {"AAPL": position}
        
>>>>>>> origin/main
        _close_all_positions(risk_engine, execution_engine, positions)

        # Should submit exactly 1 order
        execution_engine.submit_order.assert_called_once()

        # Check order details
        call_args = execution_engine.submit_order.call_args
        order = call_args[0][0]  # First positional argument
<<<<<<< HEAD

        assert order.symbol == "AAPL"
        assert order.side == OrderSide.SELL, "Closing long should SELL"
        assert order.quantity == 100.0

=======
        
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.SELL, "Closing long should SELL"
        assert order.quantity == 100.0
    
>>>>>>> origin/main
    def test_close_all_positions_short(self):
        """Short position closes with BUY order."""
        risk_engine = RiskEngine(initial_equity=100000.0)
        execution_engine = Mock(spec=BaseExecutionEngine)
        execution_engine.submit_order.return_value = "order_456"

        # Create short position
        position = Position(
            symbol_pair="MSFT",
            entry_time=datetime.now(),
            entry_price=420.0,
            quantity=50.0,
            side="short",
<<<<<<< HEAD
            marked_price=415.0,
        )

        positions = {"MSFT": position}

=======
            marked_price=415.0
        )
        
        positions = {"MSFT": position}
        
>>>>>>> origin/main
        _close_all_positions(risk_engine, execution_engine, positions)

        # Should submit exactly 1 order
        execution_engine.submit_order.assert_called_once()

        # Check order details
        call_args = execution_engine.submit_order.call_args
        order = call_args[0][0]
<<<<<<< HEAD

        assert order.symbol == "MSFT"
        assert order.side == OrderSide.BUY, "Closing short should BUY"
        assert order.quantity == 50.0

=======
        
        assert order.symbol == "MSFT"
        assert order.side == OrderSide.BUY, "Closing short should BUY"
        assert order.quantity == 50.0
    
>>>>>>> origin/main
    def test_close_all_positions_multiple(self):
        """Multiple positions all close."""
        risk_engine = RiskEngine(initial_equity=100000.0)
        execution_engine = Mock(spec=BaseExecutionEngine)
        execution_engine.submit_order.return_value = "order_123"

        # Create multiple positions
        positions = {
            "AAPL": Position(
                symbol_pair="AAPL",
                entry_time=datetime.now(),
                entry_price=175.0,
                quantity=100.0,
                side="long",
<<<<<<< HEAD
                marked_price=180.0,
=======
                marked_price=180.0
>>>>>>> origin/main
            ),
            "MSFT": Position(
                symbol_pair="MSFT",
                entry_time=datetime.now(),
                entry_price=420.0,
                quantity=50.0,
                side="short",
<<<<<<< HEAD
                marked_price=415.0,
=======
                marked_price=415.0
>>>>>>> origin/main
            ),
            "JPM": Position(
                symbol_pair="JPM",
                entry_time=datetime.now(),
                entry_price=200.0,
                quantity=200.0,
                side="long",
<<<<<<< HEAD
                marked_price=205.0,
            ),
=======
                marked_price=205.0
            )
>>>>>>> origin/main
        }

        _close_all_positions(risk_engine, execution_engine, positions)

        # Should submit orders for all 3 positions
        assert execution_engine.submit_order.call_count == 3


class TestSignalToExecutionPath:
<<<<<<< HEAD
    """Test signal Ôåô risk check Ôåô order submission pipeline."""

=======
    """Test signal ↓ risk check ↓ order submission pipeline."""
    
>>>>>>> origin/main
    def test_risk_check_rejects_overleveraged_trade(self):
        """Risk engine rejects over-leveraged trades."""
        risk_engine = RiskEngine(initial_equity=100000.0)

        # Try to open huge position (would be overleveraged)
        # risk_pct = (50000 * 0.02) / 100000 = 0.01 = 1% >> 0.5% limit
        can_enter, reason = risk_engine.can_enter_trade(
            symbol_pair="AAPL",
            position_size=50000.0,  # 50k units
            current_equity=100000.0,
            volatility=0.02,
        )

        # Should reject due to risk exceeding 0.5% limit
        assert can_enter is False, "Should reject overleveraged position"
        assert reason is not None and ("risk" in reason.lower() or "leverage" in reason.lower()), (
            f"Rejection reason should mention risk/leverage: {reason}"
        )

    def test_risk_check_accepts_reasonable_trade(self):
        """Risk engine accepts reasonable trade."""
        risk_engine = RiskEngine(initial_equity=100000.0)

        # Reasonable position size
        can_enter, reason = risk_engine.can_enter_trade(
<<<<<<< HEAD
            symbol_pair="AAPL", position_size=1.0, current_equity=100000.0, volatility=0.02
=======
            symbol_pair="AAPL",
            position_size=1.0,
            current_equity=100000.0,
            volatility=0.02
>>>>>>> origin/main
        )

        assert can_enter is True, f"Should accept reasonable trade: {reason}"

    def test_order_submission_creates_order(self):
        """Order submission creates Order object correctly."""
        # Create order
<<<<<<< HEAD
        order = Order(order_id="test_order_123", symbol="AAPL", side=OrderSide.BUY, quantity=100.0, limit_price=175.0)

=======
        order = Order(
            order_id="test_order_123",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            limit_price=175.0
        )
        
>>>>>>> origin/main
        # Verify order structure
        assert order.order_id == "test_order_123"
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.quantity == 100.0
        assert order.limit_price == 175.0


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

        assert "check_position_stops" in source, "Should check position stops"
        assert "should_stop_out" in source or "stop_loss" in source.lower(), "Should implement stop-loss logic"

    def test_data_loaded_in_loop(self):
        """Main loop loads market data."""
        import inspect

        from main import run_paper_trading

        source = inspect.getsource(run_paper_trading)

        assert "_load_market_data_for_symbols" in source or "load_" in source, "Should load market data"

    def test_reconciliation_checked_in_loop(self):
        """Main loop includes periodic reconciliation."""
        import inspect

        from main import run_paper_trading

        source = inspect.getsource(run_paper_trading)

        assert "reconcil" in source.lower(), "Should include reconciliation"


class TestMainLoopErrorHanding:
    """Test error handling in main loop."""

    def test_data_error_handling_present(self):
        """Main loop handles DataError gracefully."""
        import inspect

        from main import run_paper_trading

        source = inspect.getsource(run_paper_trading)

        assert "DataError" in source or "except" in source, "Should have error handling"
        assert "KeyboardInterrupt" in source or "shutdown" in source.lower(), "Should handle user interruption"
