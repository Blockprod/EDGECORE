#!/usr/bin/env python3
"""
Benchmark Cython vs Pure Python Cointegration Testing.
Shows performance improvement with Cython acceleration.
"""

import sys
import time
import numpy as np
import pandas as pd
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.cointegration import (
    engle_granger_test,
    engle_granger_test_cpp_optimized,
    CYTHON_COINTEGRATION_AVAILABLE
)

def create_synthetic_pairs(num_pairs: int = 100, n_periods: int = 250) -> list:
    """Create synthetic cointegrated pairs for benchmarking."""
    pairs = []
    np.random.seed(42)
    
    for _ in range(num_pairs):
        # Create common factor
        common = np.cumsum(np.random.randn(n_periods))
        
        # Create two series sharing the common factor
        x = common + np.random.randn(n_periods) * 0.5
        y = common + np.random.randn(n_periods) * 0.5
        
        pairs.append((
            pd.Series(y, name='y'),
            pd.Series(x, name='x')
        ))
    
    return pairs

def benchmark_pure_python(pairs: list) -> dict:
    """Benchmark pure Python implementation."""
    print("\n[BENCH] Pure Python Implementation")
    print("-" * 50)
    
    times = []
    cointegrated_count = 0
    
    start_total = time.time()
    
    for y, x in pairs:
        start = time.perf_counter()
        result = engle_granger_test(y, x)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        
        if result.get('is_cointegrated', False):
            cointegrated_count += 1
    
    total_time = time.time() - start_total
    times = np.array(times)
    
    print(f"Total Pairs Tested: {len(pairs)}")
    print(f"Cointegrated Pairs: {cointegrated_count}")
    print(f"Total Time: {total_time:.3f}s")
    print(f"Avg Per Pair: {np.mean(times)*1000:.2f}ms")
    print(f"Min/Max Per Pair: {np.min(times)*1000:.2f}ms / {np.max(times)*1000:.2f}ms")
    print(f"Throughput: {len(pairs)/total_time:.1f} pairs/sec")
    
    return {
        'name': 'Pure Python',
        'total_time': total_time,
        'per_pair': np.mean(times),
        'pairs_per_sec': len(pairs) / total_time,
        'cointegrated': cointegrated_count
    }

def benchmark_optimized(pairs: list) -> dict:
    """Benchmark Cython-optimized implementation."""
    if not CYTHON_COINTEGRATION_AVAILABLE:
        print("\n[SKIP] Cython Acceleration NOT Available")
        print("-" * 50)
        return {'name': 'Cython (Not Available)', 'total_time': None}
    
    print("\n[BENCH] Cython-Optimized Implementation")
    print("-" * 50)
    
    times = []
    cointegrated_count = 0
    
    start_total = time.time()
    
    for y, x in pairs:
        start = time.perf_counter()
        result = engle_granger_test_cpp_optimized(y, x)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        
        if result.get('is_cointegrated', False):
            cointegrated_count += 1
    
    total_time = time.time() - start_total
    times = np.array(times)
    
    print(f"Total Pairs Tested: {len(pairs)}")
    print(f"Cointegrated Pairs: {cointegrated_count}")
    print(f"Total Time: {total_time:.3f}s")
    print(f"Avg Per Pair: {np.mean(times)*1000:.2f}ms")
    print(f"Min/Max Per Pair: {np.min(times)*1000:.2f}ms / {np.max(times)*1000:.2f}ms")
    print(f"Throughput: {len(pairs)/total_time:.1f} pairs/sec")
    
    return {
        'name': 'Cython',
        'total_time': total_time,
        'per_pair': np.mean(times),
        'pairs_per_sec': len(pairs) / total_time,
        'cointegrated': cointegrated_count
    }

def print_summary(results: list):
    """Print benchmark summary and speedup comparison."""
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    
    for r in results:
        if r['total_time'] is None:
            continue
        print(f"\n{r['name']}:")
        print(f"  Total Time: {r['total_time']:.3f}s")
        print(f"  Per Pair: {r['per_pair']*1000:.2f}ms")
        print(f"  Throughput: {r['pairs_per_sec']:.1f} pairs/sec")
        print(f"  Cointegrated: {r['cointegrated']} pairs")
    
    # Calculate speedup
    valid_results = [r for r in results if r['total_time'] is not None]
    if len(valid_results) >= 2:
        python_time = valid_results[0]['total_time']
        cython_time = valid_results[1]['total_time']
        speedup = python_time / cython_time
        
        print(f"\n{'-' * 60}")
        print(f"SPEEDUP: {speedup:.1f}x faster with Cython")
        print(f"  Python:  {python_time:.3f}s")
        print(f"  Cython:  {cython_time:.3f}s")
        print(f"  Saved:   {python_time - cython_time:.3f}s per {len(valid_results[0])} pairs")
        print(f"{'-' * 60}")

def main():
    """Run benchmarks."""
    print("\n" + "=" * 60)
    print("CYTHON ACCELERATION BENCHMARK")
    print("=" * 60)
    
    # Create test data
    print("\nGenerating 100 synthetic cointegrated pairs...")
    pairs = create_synthetic_pairs(num_pairs=100, n_periods=250)
    print(f"Generated {len(pairs)} pairs with 250 periods each")
    
    # Run benchmarks
    results = []
    results.append(benchmark_pure_python(pairs))
    results.append(benchmark_optimized(pairs))
    
    # Print summary
    print_summary(results)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
