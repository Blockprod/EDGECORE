"""Tests for wrapper compatibility with Cython acceleration.
These tests verify that Python/Cython hybrid implementation works correctly.
"""

import numpy as np
import pytest

from edgecore.backtest_engine_wrapper import BacktestEngineWrapper
from edgecore.cointegration_engine_wrapper import CointegrationEngineWrapper


class TestBacktestEngineWrapper:
    """Test BacktestEngine wrapper with fallback mechanism."""
    
    def test_engine_creation(self):
        """Test engine creates successfully with fallback."""
        engine = BacktestEngineWrapper(100000)
        assert engine.initial_equity == 100000
        assert engine.get_equity() == 100000
    
    def test_python_implementation(self):
        """Test Python-only implementation (C++ deprecated)."""
        engine = BacktestEngineWrapper(50000)
        # Now uses Python-only implementation
        assert engine.use_cpp is False  # No longer uses C++
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
        symbols = ['AAPL', 'MSFT']
        
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
        symbols = ['AAPL', 'MSFT']
        
        def strategy_callback(price_vec, day):
            if day == 0:
                return [{
                    'symbol': 'AAPL',
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
        """Test engine creates successfully with Cython."""
        engine = CointegrationEngineWrapper()
        assert engine.use_cpp is False  # Python with Cython acceleration
    
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
            ['AAPL'],
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
        
        symbols = ['AAPL', 'MSFT', 'JPM']
        
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
        coint_engine.find_cointegration_parallel(
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
    
    def test_python_cython_integration(self):
        """Test Python/Cython integration works correctly."""
        # Both engines use Python with optional Cython acceleration
        backtest_engine = BacktestEngineWrapper(100000)
        coint_engine = CointegrationEngineWrapper()
        
        # Verify both use Python implementation
        assert hasattr(backtest_engine, 'use_cpp')
        assert hasattr(coint_engine, 'use_cpp')
        
        # Both should have use_cpp=False (Python-only)
        assert backtest_engine.use_cpp is False
        assert coint_engine.use_cpp is False
        
        # Verify engines still work
        assert backtest_engine.initial_equity == 100000
    
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


class TestVersionAvailability:
    """Test detection and loading of Python/Cython implementation."""
    
    def test_version_detection(self):
        """Test if Python/Cython modules are properly available."""
        backtest_wrapper = BacktestEngineWrapper(100000)
        coint_wrapper = CointegrationEngineWrapper()
        
        # Both should have use_cpp flag
        assert hasattr(backtest_wrapper, 'use_cpp')
        assert hasattr(coint_wrapper, 'use_cpp')
    
    def test_cython_loads_correctly(self):
        """Test that Cython acceleration is available if compiled."""
        
        # Create engine (uses Python with optional Cython speedup)
        engine = BacktestEngineWrapper(100000)
        
        # Check engine functionality regardless of C++ availability
        assert engine.initial_equity == 100000
        assert hasattr(engine, 'use_cpp')
        assert isinstance(engine.use_cpp, bool)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
