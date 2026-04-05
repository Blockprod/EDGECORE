<<<<<<< HEAD
﻿#!/usr/bin/env python
=======
#!/usr/bin/env python
>>>>>>> origin/main
"""
Benchmark: C++ Cointegration Engine vs Pure Python
Shows the performance improvement from using C++ acceleration.
"""

import time
import numpy as np
import pandas as pd
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.cointegration import engle_granger_test, engle_granger_test_cpp_optimized

def generate_synthetic_data(n_periods=252, n_pairs=10):
    """Generate synthetic price data for benchmarking."""
    np.random.seed(42)
    
    # Create synthetic time series
    returns = np.random.randn(n_periods, n_pairs) * 0.01
    prices = np.cumprod(1 + returns, axis=0) * 100
    
    return prices, [f"SYM{i}" for i in range(n_pairs)]

def benchmark_cointegration(prices, symbols, use_cpp=True):
    """Benchmark cointegration testing on all pairs."""
    
    prices_df = pd.DataFrame(prices, columns=symbols)
    test_func = engle_granger_test_cpp_optimized if use_cpp else engle_granger_test
    
    start_time = time.time()
    
    num_tests = 0
    num_cointegrated = 0
    
    for i, sym1 in enumerate(symbols):
        for sym2 in symbols[i+1:]:
            series1 = prices_df[sym1]
            series2 = prices_df[sym2]
            
            result = test_func(series1, series2)
            num_tests += 1
            
            if result.get('is_cointegrated', False):
                num_cointegrated += 1
    
    elapsed = time.time() - start_time
    
    return {
        'elapsed': elapsed,
        'num_tests': num_tests,
        'num_cointegrated': num_cointegrated,
        'tests_per_second': num_tests / elapsed if elapsed > 0 else 0
    }

if __name__ == '__main__':
    print("=" * 80)
    print("  C++ COINTEGRATION ENGINE BENCHMARK")
    print("=" * 80)
    print()
    
    # Test configurations
    configs = [
        {'n_periods': 252, 'n_pairs': 5,  'name': 'Small (5 symbols)'},
        {'n_periods': 252, 'n_pairs': 10, 'name': 'Medium (10 symbols)'},
        {'n_periods': 252, 'n_pairs': 20, 'name': 'Large (20 symbols)'},
    ]
    
    for config in configs:
        print(f"\nBenchmark: {config['name']}")
        print(f"  Periods: {config['n_periods']}, Pairs to test: {config['n_pairs'] * (config['n_pairs']-1) // 2}")
        print("-" * 80)
        
        prices, symbols = generate_synthetic_data(
            n_periods=config['n_periods'],
            n_pairs=config['n_pairs']
        )
        
        # Benchmark Python version
        python_result = benchmark_cointegration(prices, symbols, use_cpp=False)
        print("\n  Pure Python Implementation:")
        print(f"    Total time:        {python_result['elapsed']:.3f} seconds")
        print(f"    Tests completed:   {python_result['num_tests']}")
        print(f"    Cointegrated:      {python_result['num_cointegrated']}")
        print(f"    Tests/second:      {python_result['tests_per_second']:.1f}")
        
        # Benchmark C++ version
        cpp_result = benchmark_cointegration(prices, symbols, use_cpp=True)
        print("\n  C++ Optimized Implementation:")
        print(f"    Total time:        {cpp_result['elapsed']:.3f} seconds")
        print(f"    Tests completed:   {cpp_result['num_tests']}")
        print(f"    Cointegrated:      {cpp_result['num_cointegrated']}")
        print(f"    Tests/second:      {cpp_result['tests_per_second']:.1f}")
        
        # Calculate speedup
        if python_result['elapsed'] > 0:
            speedup = python_result['elapsed'] / cpp_result['elapsed']
            print(f"\n  Speedup (C++ vs Python): {speedup:.1f}x faster")
        
        print()
    
    print("=" * 80)
    print("\nNotes:")
    print("  - Speedup depends on C++ module availability and compilation")
    print("  - C++ falls back to Python if module is not available")
    print("  - Real-world speedup is higher with larger datasets")
    print("  - For 119 symbols (7,021 pair tests), expect 5-10x overall speedup")
    print("=" * 80)
