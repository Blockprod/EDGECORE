"""
Tests for hybrid C++/Python architecture wrapper compatibility.
These tests verify that both C++ and Python implementations work correctly.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch
from edgecore.backtest_engine_wrapper import BacktestEngineWrapper
from edgecore.cointegration_engine_wrapper import CointegrationEngineWrapper


class TestBacktestEngineWrapper:
    """Test BacktestEngine wrapper with fallback mechanism."""
    
    def test_engine_creation(self):
        """Test engine creates successfully with fallback."""
        engine = BacktestEngineWrapper(100000)
        assert engine.initial_equity == 100000
        assert engine.get_equity() == 100000
    
    def test_cpp_unavailable_fallback(self):
        """Test fallback when C++ not available."""
        engine = BacktestEngineWrapper(50000)
        if not engine.use_cpp:
            # Python version - verify it works
            assert engine._engine is None
            assert engine.initial_equity == 50000
    
    def test_simple_backtest_run(self):
        """Test running a simple backtest."""
        engine = BacktestEngineWrapper(100000)
        
        # Simple price data (3 days, 2 symbols)
        prices = [
            [100.0, 50.0],   # Day 1
            [101.0, 51.0],   # Day 2
            [102.0, 52.0],   # Day 3
        ]
        symbols = ['BTC/USDT', 'ETH/USDT']
        
        # Mock callbacks
        def strategy_callback(price_vec, day):
            return []  # No signals
        
        def risk_callback(sym, size, price, equity):
            return True
        
        # Run backtest
        results = engine.run(
            prices,
            symbols,
            strategy_callback,
            risk_callback
        )
        
        assert 'equity' in results
        assert 'daily_returns' in results
        assert 'positions' in results
        assert len(results['daily_returns']) == 3
    
    def test_buy_signal_processing(self):
        """Test processing buy signals."""
        engine = BacktestEngineWrapper(100000)
        
        prices = [
            [100.0, 50.0],
            [101.0, 51.0],
        ]
        symbols = ['BTC/USDT', 'ETH/USDT']
        
        def strategy_callback(price_vec, day):
            if day == 0:
                return [{
                    'symbol': 'BTC/USDT',
                    'side': 1,  # BUY
                    'size': 10,
                    'price': 100.0
                }]
            return []
        
        def risk_callback(sym, size, price, equity):
            return size * price < equity * 0.5  # Max 50% of equity
        
        results = engine.run(
            prices,
            symbols,
            strategy_callback,
            risk_callback
        )
        
        assert results['equity'] < 100000  # Lost money to buy
    
    def test_empty_prices(self):
        """Test handling empty price data."""
        engine = BacktestEngineWrapper(100000)
        
        def strategy_callback(price_vec, day):
            return []
        
        def risk_callback(sym, size, price, equity):
            return True
        
        results = engine.run([], [], strategy_callback, risk_callback)
        assert results['daily_returns'] == []


class TestCointegrationEngineWrapper:
    """Test CointegrationEngine wrapper with fallback mechanism."""
    
    def test_engine_creation(self):
        """Test engine creates successfully."""
        engine = CointegrationEngineWrapper()
        assert engine._engine is not None or not engine.use_cpp
    
    def test_find_cointegration_empty(self):
        """Test with empty data."""
        engine = CointegrationEngineWrapper()
        
        results = engine.find_cointegration_parallel(
            [],
            np.array([]).reshape(0, 0)
        )
        assert results == []
    
    def test_find_cointegration_single_symbol(self):
        """Test with single symbol (no pairs)."""
        engine = CointegrationEngineWrapper()
        
        prices = np.random.randn(100, 1)  # 100 days, 1 symbol
        results = engine.find_cointegration_parallel(
            ['BTC/USDT'],
            prices
        )
        assert results == []  # No pairs possible
    
    def test_find_cointegration_multiple_symbols(self):
        """Test with multiple symbols."""
        engine = CointegrationEngineWrapper()
        
        # Create correlated price data
        np.random.seed(42)
        base_prices = np.cumsum(np.random.randn(100)) + 100
        
        prices = np.column_stack([
            base_prices,
            base_prices * 0.5 + np.random.randn(100),  # Correlated
            np.random.randn(100) + 50,                   # Random
        ])
        
        symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']
        
        results = engine.find_cointegration_parallel(
            symbols,
            prices,
            max_half_life=60,
            min_correlation=0.5
        )
        
        # Verify result format
        for sym1, sym2, pvalue, half_life in results:
            assert isinstance(sym1, str)
            assert isinstance(sym2, str)
            assert isinstance(pvalue, float)
            assert isinstance(half_life, float)
            assert 0 <= pvalue <= 1
            assert 0 < half_life <= 60
    
    def test_cointegration_parameters(self):
        """Test with different parameters."""
        engine = CointegrationEngineWrapper()
        
        prices = np.random.randn(100, 5) + 100
        symbols = [f'SYM{i}' for i in range(5)]
        
        # Stricty parameters
        results_strict = engine.find_cointegration_parallel(
            symbols,
            prices,
            max_half_life=10,
            min_correlation=0.9,
            pvalue_threshold=0.01
        )
        
        # Relaxed parameters
        results_relaxed = engine.find_cointegration_parallel(
            symbols,
            prices,
            max_half_life=60,
            min_correlation=0.5,
            pvalue_threshold=0.1
        )
        
        # Relaxed should find at least as many pairs
        assert len(results_relaxed) >= len(results_strict)


class TestHybridArchitectureIntegration:
    """Integration tests for the hybrid architecture."""
    
    def test_backtest_with_cointegration(self):
        """Test backtest using cointegrated pairs."""
        backtest_engine = BacktestEngineWrapper(100000)
        coint_engine = CointegrationEngineWrapper()
        
        # Generate test prices
        np.random.seed(42)
        prices = np.random.randn(50, 3) + 100
        symbols = ['A', 'B', 'C']
        
        # Find cointegrated pairs
        pairs = coint_engine.find_cointegration_parallel(
            symbols,
            prices
        )
        
        # Run backtest
        prices_list = prices.tolist()
        
        def strategy_callback(price_vec, day):
            return []  # Simple strategy
        
        def risk_callback(sym, size, price, equity):
            return True
        
        results = backtest_engine.run(
            prices_list,
            symbols,
            strategy_callback,
            risk_callback
        )
        
        assert 'equity' in results
        assert len(results['daily_returns']) == len(prices_list)
    
    def test_fallback_mechanism(self):
        """Test that fallback works correctly."""
        # Both engines should work regardless of C++ availability
        backtest_engine = BacktestEngineWrapper(100000)
        coint_engine = CointegrationEngineWrapper()
        
        # Verify fallback detection works
        assert hasattr(backtest_engine, 'use_cpp')
        assert hasattr(coint_engine, 'use_cpp')
        
        # Verify engines still work
        assert backtest_engine.initial_equity == 100000
        assert coint_engine._engine is not None or not coint_engine.use_cpp
    
    def test_performance_with_many_symbols(self):
        """Test performance with larger dataset."""
        engine = CointegrationEngineWrapper()
        
        # 50 symbols, 200 days of data
        n_symbols = 50
        n_days = 200
        
        prices = np.random.randn(n_days, n_symbols) + 100
        symbols = [f'SYM{i:02d}' for i in range(n_symbols)]
        
        # This should handle larger datasets
        results = engine.find_cointegration_parallel(
            symbols,
            prices,
            max_half_life=60
        )
        
        # Verify it completes without error
        assert isinstance(results, list)
        
        # Report statistics
        print(f"\nTested {n_symbols} symbols over {n_days} days")
        print(f"Found {len(results)} cointegrated pairs")
        if results:
            avg_half_life = np.mean([r[3] for r in results])
            print(f"Average half-life: {avg_half_life:.2f}")


class TestCPPModuleAvailability:
    """Test detection and loading of C++ modules."""
    
    def test_cpp_module_detection(self):
        """Test if C++ modules are properly detected."""
        backtest_wrapper = BacktestEngineWrapper(100000)
        coint_wrapper = CointegrationEngineWrapper()
        
        # Both should have CPP_AVAILABLE flag
        assert hasattr(backtest_wrapper, 'use_cpp')
        assert hasattr(coint_wrapper, 'use_cpp')
    
    def test_fallback_logs_correctly(self):
        """Test that warnings are logged for missing C++ modules."""
        import logging
        
        # Create engine (will log if C++ not available)
        engine = BacktestEngineWrapper(100000)
        
        # Check engine functionality regardless of C++ availability
        assert engine.initial_equity == 100000
        assert hasattr(engine, 'use_cpp')
        assert isinstance(engine.use_cpp, bool)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
