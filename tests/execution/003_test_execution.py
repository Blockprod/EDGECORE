import pytest
import os
from unittest.mock import patch, MagicMock
from execution.ccxt_engine import CCXTExecutionEngine
from execution.base import Order, OrderSide, OrderStatus


def test_ccxt_engine_requires_credentials():
    """Test that CCXT engine requires API credentials."""
    
    # Clear credentials
    with patch.dict(os.environ, {'EXCHANGE_API_KEY': '', 'EXCHANGE_API_SECRET': ''}, clear=False):
        with pytest.raises(ValueError, match="EXCHANGE_API_KEY and EXCHANGE_API_SECRET"):
            engine = CCXTExecutionEngine()


def test_ccxt_engine_loads_from_env():
    """Test that CCXT engine loads credentials from .env."""
    
    with patch.dict(os.environ, {
        'EXCHANGE_API_KEY': 'test_key_12345',
        'EXCHANGE_API_SECRET': 'test_secret_67890'
    }, clear=False):
        # Mock ccxt.binance to avoid actual connection
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange
            
            engine = CCXTExecutionEngine()
            
            # Verify credentials were passed to exchange
            call_args = mock_binance.call_args
            assert call_args[0][0]['apiKey'] == 'test_key_12345'
            assert call_args[0][0]['secret'] == 'test_secret_67890'


def test_ccxt_engine_initialization():
    """Test CCXT engine initializes correctly."""
    with patch.dict(os.environ, {
        'EXCHANGE_API_KEY': 'test_key',
        'EXCHANGE_API_SECRET': 'test_secret'
    }, clear=False):
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange
            
            engine = CCXTExecutionEngine()
            assert engine.exchange is not None
            assert isinstance(engine.order_map, dict)


def test_submit_order():
    """Test order submission."""
    with patch.dict(os.environ, {
        'EXCHANGE_API_KEY': 'test_key',
        'EXCHANGE_API_SECRET': 'test_secret'
    }, clear=False):
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange
            mock_exchange.create_limit_order.return_value = {'id': '123456'}
            
            engine = CCXTExecutionEngine()
            engine.exchange = mock_exchange
            
            order = Order(
                order_id='test_1',
                symbol='BTC/USDT',
                side=OrderSide.BUY,
                quantity=0.1,
                limit_price=29000
            )
            
            broker_order_id = engine.submit_order(order)
            
            assert broker_order_id == '123456'
            mock_exchange.create_limit_order.assert_called_once()


def test_get_account_balance():
    """Test account balance fetch."""
    with patch.dict(os.environ, {
        'EXCHANGE_API_KEY': 'test_key',
        'EXCHANGE_API_SECRET': 'test_secret'
    }, clear=False):
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange
            mock_exchange.fetch_balance.return_value = {'USDT': {'free': 1000, 'used': 100}}
            
            engine = CCXTExecutionEngine()
            engine.exchange = mock_exchange
            
            balance = engine.get_account_balance()
            
            assert balance == 1000


def test_get_positions():
    """Test positions fetch."""
    with patch.dict(os.environ, {
        'EXCHANGE_API_KEY': 'test_key',
        'EXCHANGE_API_SECRET': 'test_secret'
    }, clear=False):
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange
            mock_exchange.fetch_balance.return_value = {
                'BTC': {'free': 0.5, 'used': 0.1},
                'ETH': {'free': 2.0, 'used': 0.5},
                'USDT': {'free': 1000, 'used': 0}
            }
            
            engine = CCXTExecutionEngine()
            engine.exchange = mock_exchange
            
            positions = engine.get_positions()
            
            assert 'BTC' in positions
            assert 'ETH' in positions
            assert positions['BTC'] == 0.6  # free + used


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
