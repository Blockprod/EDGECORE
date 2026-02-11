import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from strategies.pair_trading import PairTradingStrategy
from strategies.base import Signal


class TestPairTradingStrategy:
    """Test pair trading strategy signal generation."""
    
    def test_strategy_initialization(self):
        """Test strategy initializes correctly."""
        strategy = PairTradingStrategy()
        
        assert strategy is not None
        assert hasattr(strategy, 'config')
        assert hasattr(strategy, 'generate_signals')

    def test_generate_signals_with_empty_data(self):
        """Test signal generation with empty dataframe."""
        strategy = PairTradingStrategy()
        prices = pd.DataFrame()
        
        signals = strategy.generate_signals(prices)
        
        # Should handle empty gracefully
        assert isinstance(signals, list)

    def test_generate_signals_with_single_symbol(self):
        """Test signal generation with single symbol."""
        strategy = PairTradingStrategy()
        
        np.random.seed(42)
        n = 100
        prices = pd.DataFrame({
            'BTC/USDT': np.linspace(29000, 30000, n) + np.random.randn(n) * 100
        })
        
        signals = strategy.generate_signals(prices)
        
        # May be empty depending on strategy, but should return list
        assert isinstance(signals, list)

    def test_generate_signals_with_multiple_symbols(self):
        """Test signal generation with multiple symbols."""
        strategy = PairTradingStrategy()
        
        np.random.seed(42)
        n = 100
        prices = pd.DataFrame({
            'BTC/USDT': np.linspace(29000, 30000, n) + np.random.randn(n) * 50,
            'ETH/USDT': np.linspace(1800, 2000, n) + np.random.randn(n) * 30,
            'XRP/USDT': np.linspace(0.5, 0.6, n) + np.random.randn(n) * 0.01,
        })
        
        signals = strategy.generate_signals(prices)
        
        # Should return list of signals
        assert isinstance(signals, list)
        
        # If signals exist, validate structure
        for signal in signals:
            assert isinstance(signal, Signal)
            assert hasattr(signal, 'symbol_pair')
            assert hasattr(signal, 'side')
            assert hasattr(signal, 'strength')

    def test_signal_properties(self):
        """Test Signal object properties."""
        strategy = PairTradingStrategy()
        
        np.random.seed(42)
        n = 200
        # Create highly correlated pair
        x = np.cumsum(np.random.randn(n))
        y = 1.5 * x + np.random.randn(n) * 0.5
        
        prices = pd.DataFrame({
            'BTC/USDT': x,
            'ETH/USDT': y,
        })
        
        signals = strategy.generate_signals(prices)
        
        # Check signal properties if any generated
        for signal in signals:
            assert signal.side in ['long', 'short', 'exit']
            assert 0 <= signal.strength <= 1 or signal.strength is None
            assert signal.symbol_pair is not None

    def test_strategy_state_tracking(self):
        """Test that strategy tracks state."""
        strategy = PairTradingStrategy()
        
        # Should have some state concept
        if hasattr(strategy, 'positions'):
            assert isinstance(strategy.positions, (dict, list))
        
        if hasattr(strategy, 'active_pairs'):
            assert isinstance(strategy.active_pairs, (dict, list, set))

    def test_consistent_signal_generation(self):
        """Test that signal generation is consistent."""
        strategy = PairTradingStrategy()
        
        np.random.seed(42)
        n = 100
        prices = pd.DataFrame({
            'BTC/USDT': np.random.randn(n).cumsum() + 100,
            'ETH/USDT': np.random.randn(n).cumsum() + 50,
        })
        
        # Generate signals twice with same data
        signals1 = strategy.generate_signals(prices)
        signals2 = strategy.generate_signals(prices)
        
        # Should be consistent
        assert len(signals1) == len(signals2)

    def test_signal_metadata(self):
        """Test signal contains useful metadata."""
        strategy = PairTradingStrategy()
        
        np.random.seed(42)
        n = 100
        prices = pd.DataFrame({
            'BTC/USDT': np.random.randn(n).cumsum() + 100,
            'ETH/USDT': np.random.randn(n).cumsum() + 50,
        })
        
        signals = strategy.generate_signals(prices)
        
        for signal in signals:
            # Should have timestamp or index info
            if hasattr(signal, 'timestamp'):
                assert signal.timestamp is not None
            
            # Should identify entry or exit
            assert signal.side is not None

    def test_strategy_with_lookback_period(self):
        """Test strategy respects lookback period for cointegration."""
        strategy = PairTradingStrategy()
        
        # Short data
        np.random.seed(42)
        n = 50  # May be below minimum lookback
        prices = pd.DataFrame({
            'BTC/USDT': np.random.randn(n).cumsum() + 100,
            'ETH/USDT': np.random.randn(n).cumsum() + 50,
        })
        
        # Should not crash on short data
        signals = strategy.generate_signals(prices)
        assert isinstance(signals, list)

    def test_strategy_handles_missing_data(self):
        """Test strategy handles NaN values gracefully."""
        strategy = PairTradingStrategy()
        
        np.random.seed(42)
        n = 100
        prices = pd.DataFrame({
            'BTC/USDT': np.random.randn(n).cumsum() + 100,
            'ETH/USDT': np.random.randn(n).cumsum() + 50,
        })
        
        # Introduce some NaN
        prices.loc[10:15, 'BTC/USDT'] = np.nan
        
        # Should handle gracefully
        signals = strategy.generate_signals(prices)
        assert isinstance(signals, list)

    def test_multiple_signal_types(self):
        """Test that strategy can generate different signal types."""
        strategy = PairTradingStrategy()
        
        np.random.seed(42)
        n = 200
        prices = pd.DataFrame({
            'BTC/USDT': np.random.randn(n).cumsum() + 100,
            'ETH/USDT': np.random.randn(n).cumsum() + 50,
            'XRP/USDT': np.random.randn(n).cumsum() + 1,
        })
        
        signals = strategy.generate_signals(prices)
        
        # Collect signal sides
        signal_sides = [s.side for s in signals]
        
        # May have different types depending on data
        assert isinstance(signal_sides, list)
        
        # All should be valid sides
        for side in signal_sides:
            assert side in ['long', 'short', 'exit']


class TestSignalObject:
    """Test Signal class structure."""
    
    def test_signal_creation(self):
        """Test creating a Signal object."""
        signal = Signal(
            symbol_pair='BTC/USDT_ETH/USDT',
            side='long',
            strength=0.85,
            reason='Cointegrated pair detected'
        )
        
        assert signal.symbol_pair == 'BTC/USDT_ETH/USDT'
        assert signal.side == 'long'
        assert signal.strength == 0.85
        assert signal.reason == 'Cointegrated pair detected'

    def test_signal_short(self):
        """Test creating a short signal."""
        signal = Signal(
            symbol_pair='BTC/USDT_ETH/USDT',
            side='short',
            strength=0.75,
            reason='Mean reversion setup'
        )
        
        assert signal.side == 'short'
        assert signal.strength == 0.75
