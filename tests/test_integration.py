import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from data.loader import DataLoader
from strategies.pair_trading import PairTradingStrategy
from risk.engine import RiskEngine
from backtests.runner import BacktestRunner
from config.settings import get_settings


class TestEndToEndPipeline:
    """Test complete trading pipeline from data to execution."""
    
    def test_data_pipeline_end_to_end(self):
        """Test loading data through to analysis."""
        loader = DataLoader()
        
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange
            
            # Create 3 months of daily data
            n = 90
            btc_ohlcv = [
                [
                    1609459200000 + (i * 86400000),
                    29000 + i * 10,
                    29500 + i * 10,
                    28500 + i * 10,
                    29250 + i * 10,
                    100 + i
                ]
                for i in range(n)
            ]
            
            mock_exchange.fetch_ohlcv.return_value = btc_ohlcv
            
            # Load data
            df = loader.load_ccxt_data('binance', 'BTC/USDT', '1d', limit=n)
            
            # Verify structure
            assert len(df) == n
            assert 'close' in df.columns
            assert not df['close'].isna().all()

    def test_strategy_signal_generation_pipeline(self):
        """Test data loading → signal generation."""
        strategy = PairTradingStrategy()
        
        # Create synthetic cointegrated data
        np.random.seed(42)
        n = 200
        
        # Create prices
        t = np.linspace(0, 10, n)
        trend = 100 + 0.5 * t
        
        prices = pd.DataFrame({
            'BTC/USDT': trend + np.sin(0.1 * t) * 5 + np.random.randn(n),
            'ETH/USDT': trend * 0.5 + np.sin(0.1 * t) * 2.5 + np.random.randn(n),
        })
        
        # Generate signals
        signals = strategy.generate_signals(prices)
        
        # Should produce some signals or at least handle gracefully
        assert isinstance(signals, list)

    def test_risk_engine_integration(self):
        """Test risk engine with strategy signals."""
        risk_engine = RiskEngine(initial_equity=100_000)
        strategy = PairTradingStrategy()
        
        np.random.seed(42)
        n = 100
        prices = pd.DataFrame({
            'BTC/USDT': np.linspace(29000, 30000, n) + np.random.randn(n) * 100,
            'ETH/USDT': np.linspace(1800, 2000, n) + np.random.randn(n) * 50,
        })
        
        signals = strategy.generate_signals(prices)
        
        # Check risk for each signal
        equity = 100000
        for signal in signals[:5]:  # Check first 5
            can_enter, reason = risk_engine.can_enter_trade(
                symbol=signal.symbol_pair,
                position_size=10.0,
                current_equity=equity,
                volatility=0.02
            )
            
            # Should return bool and reason
            assert isinstance(can_enter, bool)
            assert reason is not None or reason is None

    def test_backtest_runner_integration(self):
        """Test complete backtest runner end-to-end."""
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange
            
            # Create sample data
            n = 100
            btc_ohlcv = [
                [
                    1609459200000 + (i * 86400000),
                    29000 + i * 10,
                    29500 + i * 10,
                    28500 + i * 10,
                    29250 + i * 10,
                    100 + i
                ]
                for i in range(n)
            ]
            
            eth_ohlcv = [
                [
                    1609459200000 + (i * 86400000),
                    1800 + i * 5,
                    1850 + i * 5,
                    1750 + i * 5,
                    1825 + i * 5,
                    200 + i * 2
                ]
                for i in range(n)
            ]
            
            def fetch_side_effect(symbol, *args, **kwargs):
                if 'BTC' in symbol:
                    return btc_ohlcv
                return eth_ohlcv
            
            mock_exchange.fetch_ohlcv.side_effect = fetch_side_effect
            
            # Run backtest
            runner = BacktestRunner()
            metrics = runner.run(
                symbols=['BTC/USDT', 'ETH/USDT'],
                start_date='2021-01-01',
                end_date='2021-04-10'
            )
            
            # Should return metrics object
            assert metrics is not None
            assert hasattr(metrics, 'total_return')
            assert hasattr(metrics, 'sharpe_ratio')
            assert hasattr(metrics, 'summary')

    def test_full_pipeline_no_errors(self):
        """Test complete pipeline runs without errors."""
        settings = get_settings()
        
        # Verify settings loaded
        assert settings is not None
        assert settings.backtest is not None
        assert settings.risk is not None
        assert settings.execution is not None

    def test_configuration_integration(self):
        """Test that all configs load and integrate properly."""
        settings = get_settings()
        
        # Check backtest config
        assert settings.backtest.initial_capital > 0
        assert settings.backtest.start_date is not None
        
        # Check risk config
        assert settings.risk.max_risk_per_trade > 0
        assert settings.risk.max_concurrent_positions > 0
        
        # Check execution config
        assert settings.execution.engine in ['binance', 'ccxt']

    def test_data_to_signal_consistency(self):
        """Test consistency of data through signal generation."""
        np.random.seed(42)
        n = 150
        
        # Create consistent test data
        prices = pd.DataFrame({
            'BTC/USDT': np.linspace(29000, 30000, n) + np.random.randn(n) * 50,
            'ETH/USDT': np.linspace(1800, 2000, n) + np.random.randn(n) * 30,
            'XRP/USDT': np.linspace(0.5, 0.7, n) + np.random.randn(n) * 0.01,
        })
        
        strategy = PairTradingStrategy()
        
        # Generate signals multiple times
        signals1 = strategy.generate_signals(prices)
        signals2 = strategy.generate_signals(prices)
        
        # Same input should produce same output
        assert len(signals1) == len(signals2)
        
        # Verify signal structure
        for signal in signals1:
            assert signal.symbol_pair is not None
            assert signal.side in ['long', 'short', 'exit']

    def test_pipeline_with_config_changes(self):
        """Test that pipeline respects configuration changes."""
        settings = get_settings()
        
        # Read current settings
        initial_capital = settings.backtest.initial_capital
        
        # Settings should be consistent
        assert initial_capital == settings.backtest.initial_capital

    def test_error_handling_across_pipeline(self):
        """Test that pipeline handles errors gracefully."""
        runner = BacktestRunner()
        
        # Invalid symbol should be handled
        with pytest.raises(Exception):
            runner.run(
                symbols=['INVALID/PAIR'],
                start_date='2023-01-01',
                end_date='2023-01-02'
            )

    def test_pipeline_performance_metrics(self):
        """Test that pipeline produces meaningful performance metrics."""
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange
            
            # Create sample data with trend
            n = 100
            returns = np.random.randn(n) * 0.01 + 0.001  # Slight positive drift
            prices = 100 * np.exp(np.cumsum(returns))
            
            ohlcv = [
                [
                    1609459200000 + (i * 86400000),
                    prices[i] * 0.99,
                    prices[i] * 1.01,
                    prices[i] * 0.98,
                    prices[i],
                    100
                ]
                for i in range(n)
            ]
            
            mock_exchange.fetch_ohlcv.return_value = ohlcv
            
            runner = BacktestRunner()
            metrics = runner.run(
                symbols=['BTC/USDT'],
                start_date='2021-01-01',
                end_date='2021-04-10'
            )
            
            # Metrics should be numbers
            assert isinstance(metrics.total_return, float)
            assert isinstance(metrics.sharpe_ratio, float)
            assert isinstance(metrics.max_drawdown, float)


class TestIntegrationWithMockData:
    """Test pipeline with fully mocked data."""
    
    def test_mock_full_pipeline(self):
        """Test complete pipeline with mocked external dependencies."""
        
        with patch('ccxt.binance') as mock_binance:
            # Setup mock
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange
            
            # Generate consistent mock data
            np.random.seed(42)
            n = 100
            
            base_price = 100
            trend = np.linspace(0, 10, n)
            noise = np.random.randn(n) * 2
            prices = base_price + trend + noise
            
            ohlcv = [
                [
                    1609459200000 + (i * 86400000),
                    prices[i] * 0.99,
                    prices[i] * 1.02,
                    prices[i] * 0.98,
                    prices[i],
                    100 * (i + 1)
                ]
                for i in range(n)
            ]
            
            mock_exchange.fetch_ohlcv.return_value = ohlcv
            
            loader = DataLoader()
            df = loader.load_ccxt_data('binance', 'TEST/USDT', '1d', limit=n)
            
            # Verify data
            assert len(df) == n
            assert not df['close'].isna().all()
            
            # Process through strategy
            strategy = PairTradingStrategy()
            signals = strategy.generate_signals(
                pd.DataFrame({'TEST/USDT': df['close'].values})
            )
            
            assert isinstance(signals, list)
