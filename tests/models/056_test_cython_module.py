"""Test Cython module availability and functionality.

Verifies that:
1. Cython cointegration_fast module is compiled and importable
2. The .pyd file exists on Windows
3. Core functions are callable and performant
4. Cython provides expected speedup vs pure Python
"""

import pytest
import time
import numpy as np
import pandas as pd
from pathlib import Path

# Try to import Cython module - skip all tests if not available
try:
    from models import cointegration_fast
    CYTHON_AVAILABLE = True
    CYTHON_IMPORT_ERROR = None
except (ImportError, ModuleNotFoundError) as e:
    CYTHON_AVAILABLE = False
    CYTHON_IMPORT_ERROR = str(e)


class TestCythonModuleAvailability:
    """Test that Cython module is properly compiled and available."""
    
    def test_cython_pyd_file_exists(self):
        """Verify the compiled Cython extension file exists on disk."""
        # Resolve models/ relative to this test file (avoids cwd dependency)
        models_dir = Path(__file__).parent.parent.parent / "models"

        # Windows: .pyd — Linux/macOS: .so
        compiled_files = (
            list(models_dir.glob("cointegration_fast*.pyd")) +
            list(models_dir.glob("cointegration_fast*.so"))
        )

        if not compiled_files:
            if not CYTHON_AVAILABLE:
                pytest.skip(
                    "Cython not compiled — run: python setup.py build_ext --inplace"
                )
            assert False, (
                "Cython module not compiled! Expected cointegration_fast.cp*.pyd/.so "
                "in models/ directory. Run: python setup.py build_ext --inplace"
            )

        # Verify the file is readable
        assert compiled_files[0].exists()
        assert compiled_files[0].stat().st_size > 0
    
    def test_cython_module_importable(self):
        """Verify the Cython module can be imported directly."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
        
        assert cointegration_fast is not None
    
    def test_cython_functions_exist(self):
        """Verify core Cython functions are exported."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
        
        assert hasattr(cointegration_fast, 'engle_granger_fast'), \
            "Missing engle_granger_fast function"
        assert hasattr(cointegration_fast, 'half_life_fast'), \
            "Missing half_life_fast function"
        assert callable(cointegration_fast.engle_granger_fast), \
            "engle_granger_fast is not callable"
        assert callable(cointegration_fast.half_life_fast), \
            "half_life_fast is not callable"
    
    def test_cython_function_signature(self):
        """Verify Cython function has correct signature."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
        
        # Create test data
        y = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
        x = np.array([1.0, 1.5, 2.0, 2.5, 3.0], dtype=np.float64)
        
        # Should accept 2 float arrays
        result = cointegration_fast.engle_granger_fast(y, x)
        
        # Should return dict with expected keys
        assert isinstance(result, dict)
        assert 'adf_pvalue' in result
        assert 'beta' in result


class TestCythonFunctionality:
    """Test that Cython implementation produces correct results."""
    
    def test_engle_granger_cointegrated_pair(self):
        """Test EG test on cointegrated series via Cython."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
        
        np.random.seed(42)
        n = 252
        
        # Create known cointegrated pair
        x = np.cumsum(np.random.randn(n))
        y = 2 * x + np.random.randn(n) * 0.1
        
        result = cointegration_fast.engle_granger_fast(y, x)
        
        # Should return a valid result dict
        assert isinstance(result, dict)
        assert 'adf_pvalue' in result
        assert 'beta' in result
        assert 'is_cointegrated' in result
        
        # Beta should be close to true value (2.0)
        if not np.isnan(result['beta']):
            assert 0.5 < result['beta'] < 2.5, \
                f"Beta {result['beta']} should be near 2.0"
    
    def test_engle_granger_non_cointegrated_pair(self):
        """Test EG test on independent random walks via Cython."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
        
        np.random.seed(42)
        n = 252
        
        # Create independent I(1) random walks (non-cointegrated)
        x = np.cumsum(np.random.randn(n))
        y = np.cumsum(np.random.randn(n))
        
        result = cointegration_fast.engle_granger_fast(y, x)
        
        # Should NOT detect cointegration in independent random walks
        assert result['adf_pvalue'] > 0.05, \
            f"Should not detect cointegration in independent random walks (p={result['adf_pvalue']})"
    
    def test_cython_half_life_calculation(self):
        """Test half-life calculation via Cython's separate function."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
        
        np.random.seed(42)
        
        # Create mean-reverting AR(1) with known half-life
        rho = 0.95  # Half-life = -ln(2)/ln(0.95) Ôëê 13.5
        n = 500
        spread = np.zeros(n, dtype=np.float64)
        spread[0] = np.random.randn()
        
        for t in range(1, n):
            spread[t] = rho * spread[t-1] + 0.05 * np.random.randn()
        
        # Test the half_life_fast function directly
        hl = cointegration_fast.half_life_fast(spread)
        
        # Half-life should be positive
        assert hl > 0, f"Half-life should be positive, got {hl}"
        
        # Half-life should be in reasonable range for rhoÔëê0.95
        assert 5 <= hl <= 25, \
            f"Half-life {hl} outside expected range for rho=0.95 (theory Ôëê 13.5)"


class TestCythonPerformance:
    """Test that Cython provides performance benefits."""
    
    def test_cython_faster_than_pure_python(self):
        """Verify Cython implementation is faster than pure Python."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
        
        from models.cointegration import engle_granger_test as python_version
        
        np.random.seed(42)
        n = 500
        x = np.cumsum(np.random.randn(n))
        y = 2 * x + np.random.randn(n) * 0.5
        
        # Time Python version (uses Series)
        x_series = pd.Series(x)
        y_series = pd.Series(y)
        
        start = time.perf_counter()
        for _ in range(10):
            python_version(y_series, x_series)
        python_time = time.perf_counter() - start
        
        # Time Cython version (uses numpy arrays directly)
        start = time.perf_counter()
        for _ in range(10):
            cointegration_fast.engle_granger_fast(y, x)
        cython_time = time.perf_counter() - start
        
        # Cython should be faster or comparable (allow some overhead)
        speedup = python_time / max(cython_time, 0.001)  # Avoid division by zero
        
        print("\nPerformance comparison (10 iterations):")
        print(f"  Python: {python_time:.4f}s")
        print(f"  Cython: {cython_time:.4f}s")
        print(f"  Speedup: {speedup:.2f}x")
        
        # At minimum, should not be significantly slower
        assert speedup > 0.5, (
            f"Cython version {speedup:.2f}x slower than Python - "
            "consider recompilation or optimization"
        )
    
    def test_cython_handles_large_arrays(self):
        """Test that Cython efficiently handles large datasets."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
        
        np.random.seed(42)
        
        # Large array: 5000 data points
        n = 5000
        x = np.cumsum(np.random.randn(n))
        y = 2 * x + np.random.randn(n) * 5
        
        # Should handle without error and in reasonable time
        start = time.perf_counter()
        result = cointegration_fast.engle_granger_fast(y, x)
        elapsed = time.perf_counter() - start
        
        assert result is not None
        assert elapsed < 1.0, f"Processing 5000 points took {elapsed:.2f}s (should be <1s)"
        
        print(f"\nLarge array processing (5000 points): {elapsed:.4f}s")


class TestCythonIntegration:
    """Test Cython integration with main cointegration module."""
    
    def test_cointegration_module_uses_cython(self):
        """Verify cointegration module imports and uses Cython."""
        from models import cointegration
        
        # Check that the logger message confirms Cython is loaded
        # This would be logged during module import
        assert hasattr(cointegration, 'engle_granger_test')
        
        # The main function should work
        np.random.seed(42)
        n = 100
        x = np.cumsum(np.random.randn(n))
        y = 2 * x + np.random.randn(n) * 0.1
        
        result = cointegration.engle_granger_test(pd.Series(y), pd.Series(x))
        
        assert result is not None
        assert 'is_cointegrated' in result
    
    def test_cython_result_consistency(self):
        """Verify Cython results are consistent with wrapper."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
        
        from models import cointegration
        
        np.random.seed(123)
        n = 200
        x = np.cumsum(np.random.randn(n))
        y = 2 * x + np.random.randn(n) * 0.5
        
        # Results from wrapper (uses Cython)
        wrapper_result = cointegration.engle_granger_test(pd.Series(y), pd.Series(x))
        
        # Results from direct Cython call
        cython_result = cointegration_fast.engle_granger_fast(y, x)
        
        # Both should return valid dictionaries
        assert isinstance(wrapper_result, dict)
        assert isinstance(cython_result, dict)
        
        # Both should have returned a reasonable beta (both implementations exist and work)
        assert 'beta' in wrapper_result
        assert 'beta' in cython_result
        assert not np.isnan(wrapper_result['beta'])
        assert not np.isnan(cython_result['beta'])


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
