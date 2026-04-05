<<<<<<< HEAD
﻿"""Test Cython module availability and functionality.
=======
"""Test Cython module availability and functionality.
>>>>>>> origin/main

Verifies that:
1. Cython cointegration_fast module is compiled and importable
2. The .pyd file exists on Windows
3. Core functions are callable and performant
4. Cython provides expected speedup vs pure Python
"""

<<<<<<< HEAD
import importlib
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Try to import Cython module - skip all tests if not available
try:
    cointegration_fast = importlib.import_module("models.cointegration_fast")
=======
import pytest
import time
import numpy as np
import pandas as pd
from pathlib import Path

# Try to import Cython module - skip all tests if not available
try:
    from models import cointegration_fast
>>>>>>> origin/main
    CYTHON_AVAILABLE = True
    CYTHON_IMPORT_ERROR = None
except (ImportError, ModuleNotFoundError) as e:
    CYTHON_AVAILABLE = False
    CYTHON_IMPORT_ERROR = str(e)


class TestCythonModuleAvailability:
    """Test that Cython module is properly compiled and available."""
<<<<<<< HEAD

    def test_cython_pyd_file_exists(self):
        """Verify the compiled Cython extension file exists on disk."""
        # Resolve models/ relative to this test file (avoids cwd dependency)
        models_dir = Path(__file__).parent.parent.parent / "models"

        # Windows: .pyd — Linux/macOS: .so
        compiled_files = list(models_dir.glob("cointegration_fast*.pyd")) + list(
            models_dir.glob("cointegration_fast*.so")
        )

        if not compiled_files:
            if not CYTHON_AVAILABLE:
                pytest.skip("Cython not compiled — run: python setup.py build_ext --inplace")
            raise AssertionError("Cython module not compiled! Expected cointegration_fast.cp*.pyd/.so " "in models/ directory. Run: python setup.py build_ext --inplace")

        # Verify the file is readable
        assert compiled_files[0].exists()
        assert compiled_files[0].stat().st_size > 0

=======
    
    def test_cython_pyd_file_exists(self):
        """Verify the compiled Cython .pyd file exists on disk."""
        # Look for the compiled Cython module
        models_dir = Path("models")
        
        # On Windows, Cython compiles to .pyd files
        pyd_files = list(models_dir.glob("cointegration_fast*.pyd"))
        
        assert len(pyd_files) > 0, (
            "Cython module not compiled! Expected cointegration_fast.cp*.pyd "
            "in models/ directory. Run: python setup.py build_ext --inplace"
        )
        
        # Verify the file is readable
        assert pyd_files[0].exists()
        assert pyd_files[0].stat().st_size > 0
    
>>>>>>> origin/main
    def test_cython_module_importable(self):
        """Verify the Cython module can be imported directly."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
<<<<<<< HEAD

        assert cointegration_fast is not None

=======
        
        assert cointegration_fast is not None
    
>>>>>>> origin/main
    def test_cython_functions_exist(self):
        """Verify core Cython functions are exported."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
<<<<<<< HEAD

        assert hasattr(cointegration_fast, "engle_granger_fast"), "Missing engle_granger_fast function"
        assert hasattr(cointegration_fast, "half_life_fast"), "Missing half_life_fast function"
        assert callable(cointegration_fast.engle_granger_fast), "engle_granger_fast is not callable"
        assert callable(cointegration_fast.half_life_fast), "half_life_fast is not callable"

=======
        
        assert hasattr(cointegration_fast, 'engle_granger_fast'), \
            "Missing engle_granger_fast function"
        assert hasattr(cointegration_fast, 'half_life_fast'), \
            "Missing half_life_fast function"
        assert callable(cointegration_fast.engle_granger_fast), \
            "engle_granger_fast is not callable"
        assert callable(cointegration_fast.half_life_fast), \
            "half_life_fast is not callable"
    
>>>>>>> origin/main
    def test_cython_function_signature(self):
        """Verify Cython function has correct signature."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
<<<<<<< HEAD

        # Create test data
        y = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
        x = np.array([1.0, 1.5, 2.0, 2.5, 3.0], dtype=np.float64)

        # Should accept 2 float arrays
        result = cointegration_fast.engle_granger_fast(y, x)

        # Should return dict with expected keys
        assert isinstance(result, dict)
        assert "adf_pvalue" in result
        assert "beta" in result
=======
        
        # Create test data
        y = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
        x = np.array([1.0, 1.5, 2.0, 2.5, 3.0], dtype=np.float64)
        
        # Should accept 2 float arrays
        result = cointegration_fast.engle_granger_fast(y, x)
        
        # Should return dict with expected keys
        assert isinstance(result, dict)
        assert 'adf_pvalue' in result
        assert 'beta' in result
>>>>>>> origin/main


class TestCythonFunctionality:
    """Test that Cython implementation produces correct results."""
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_engle_granger_cointegrated_pair(self):
        """Test EG test on cointegrated series via Cython."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
<<<<<<< HEAD

        np.random.seed(42)
        n = 252

        # Create known cointegrated pair
        x = np.cumsum(np.random.randn(n))
        y = 2 * x + np.random.randn(n) * 0.1

        result = cointegration_fast.engle_granger_fast(y, x)

        # Should return a valid result dict
        assert isinstance(result, dict)
        assert "adf_pvalue" in result
        assert "beta" in result
        assert "is_cointegrated" in result

        # Beta should be close to true value (2.0)
        if not np.isnan(result["beta"]):
            assert 0.5 < result["beta"] < 2.5, f"Beta {result['beta']} should be near 2.0"

=======
        
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
    
>>>>>>> origin/main
    def test_engle_granger_non_cointegrated_pair(self):
        """Test EG test on independent random walks via Cython."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
<<<<<<< HEAD

        np.random.seed(42)
        n = 252

        # Create independent I(1) random walks (non-cointegrated)
        x = np.cumsum(np.random.randn(n))
        y = np.cumsum(np.random.randn(n))

        result = cointegration_fast.engle_granger_fast(y, x)

        # Should NOT detect cointegration in independent random walks
        assert result["adf_pvalue"] > 0.05, (
            f"Should not detect cointegration in independent random walks (p={result['adf_pvalue']})"
        )

=======
        
        np.random.seed(42)
        n = 252
        
        # Create independent I(1) random walks (non-cointegrated)
        x = np.cumsum(np.random.randn(n))
        y = np.cumsum(np.random.randn(n))
        
        result = cointegration_fast.engle_granger_fast(y, x)
        
        # Should NOT detect cointegration in independent random walks
        assert result['adf_pvalue'] > 0.05, \
            f"Should not detect cointegration in independent random walks (p={result['adf_pvalue']})"
    
>>>>>>> origin/main
    def test_cython_half_life_calculation(self):
        """Test half-life calculation via Cython's separate function."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
<<<<<<< HEAD

        np.random.seed(42)

        # Create mean-reverting AR(1) with known half-life
        rho = 0.95  # Half-life = -ln(2)/ln(0.95) Ôëê 13.5
        n = 500
        spread = np.zeros(n, dtype=np.float64)
        spread[0] = np.random.randn()

        for t in range(1, n):
            spread[t] = rho * spread[t - 1] + 0.05 * np.random.randn()

        # Test the half_life_fast function directly
        hl = cointegration_fast.half_life_fast(spread)

        # Half-life should be positive
        assert hl > 0, f"Half-life should be positive, got {hl}"

        # Half-life should be in reasonable range for rhoÔëê0.95
        assert 5 <= hl <= 25, f"Half-life {hl} outside expected range for rho=0.95 (theory Ôëê 13.5)"
=======
        
        np.random.seed(42)
        
        # Create mean-reverting AR(1) with known half-life
        rho = 0.95  # Half-life = -ln(2)/ln(0.95) ≈ 13.5
        n = 500
        spread = np.zeros(n, dtype=np.float64)
        spread[0] = np.random.randn()
        
        for t in range(1, n):
            spread[t] = rho * spread[t-1] + 0.05 * np.random.randn()
        
        # Test the half_life_fast function directly
        hl = cointegration_fast.half_life_fast(spread)
        
        # Half-life should be positive
        assert hl > 0, f"Half-life should be positive, got {hl}"
        
        # Half-life should be in reasonable range for rho≈0.95
        assert 5 <= hl <= 25, \
            f"Half-life {hl} outside expected range for rho=0.95 (theory ≈ 13.5)"
>>>>>>> origin/main


class TestCythonPerformance:
    """Test that Cython provides performance benefits."""
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_cython_faster_than_pure_python(self):
        """Verify Cython implementation is faster than pure Python."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
<<<<<<< HEAD

        from models.cointegration import engle_granger_test as python_version

=======
        
        from models.cointegration import engle_granger_test as python_version
        
>>>>>>> origin/main
        np.random.seed(42)
        n = 500
        x = np.cumsum(np.random.randn(n))
        y = 2 * x + np.random.randn(n) * 0.5
<<<<<<< HEAD

        # Time Python version (uses Series)
        x_series = pd.Series(x)
        y_series = pd.Series(y)

=======
        
        # Time Python version (uses Series)
        x_series = pd.Series(x)
        y_series = pd.Series(y)
        
>>>>>>> origin/main
        start = time.perf_counter()
        for _ in range(10):
            python_version(y_series, x_series)
        python_time = time.perf_counter() - start
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # Time Cython version (uses numpy arrays directly)
        start = time.perf_counter()
        for _ in range(10):
            cointegration_fast.engle_granger_fast(y, x)
        cython_time = time.perf_counter() - start
<<<<<<< HEAD

        # Cython should be faster or comparable (allow some overhead)
        speedup = python_time / max(cython_time, 0.001)  # Avoid division by zero

=======
        
        # Cython should be faster or comparable (allow some overhead)
        speedup = python_time / max(cython_time, 0.001)  # Avoid division by zero
        
>>>>>>> origin/main
        print("\nPerformance comparison (10 iterations):")
        print(f"  Python: {python_time:.4f}s")
        print(f"  Cython: {cython_time:.4f}s")
        print(f"  Speedup: {speedup:.2f}x")
<<<<<<< HEAD

        # At minimum, should not be significantly slower
        assert speedup > 0.5, (
            f"Cython version {speedup:.2f}x slower than Python - consider recompilation or optimization"
        )

=======
        
        # At minimum, should not be significantly slower
        assert speedup > 0.5, (
            f"Cython version {speedup:.2f}x slower than Python - "
            "consider recompilation or optimization"
        )
    
>>>>>>> origin/main
    def test_cython_handles_large_arrays(self):
        """Test that Cython efficiently handles large datasets."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
<<<<<<< HEAD

        np.random.seed(42)

=======
        
        np.random.seed(42)
        
>>>>>>> origin/main
        # Large array: 5000 data points
        n = 5000
        x = np.cumsum(np.random.randn(n))
        y = 2 * x + np.random.randn(n) * 5
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # Should handle without error and in reasonable time
        start = time.perf_counter()
        result = cointegration_fast.engle_granger_fast(y, x)
        elapsed = time.perf_counter() - start
<<<<<<< HEAD

        assert result is not None
        assert elapsed < 1.0, f"Processing 5000 points took {elapsed:.2f}s (should be <1s)"

=======
        
        assert result is not None
        assert elapsed < 1.0, f"Processing 5000 points took {elapsed:.2f}s (should be <1s)"
        
>>>>>>> origin/main
        print(f"\nLarge array processing (5000 points): {elapsed:.4f}s")


class TestCythonIntegration:
    """Test Cython integration with main cointegration module."""
<<<<<<< HEAD

    def test_cointegration_module_uses_cython(self):
        """Verify cointegration module imports and uses Cython."""
        from models import cointegration

        # Check that the logger message confirms Cython is loaded
        # This would be logged during module import
        assert hasattr(cointegration, "engle_granger_test")

=======
    
    def test_cointegration_module_uses_cython(self):
        """Verify cointegration module imports and uses Cython."""
        from models import cointegration
        
        # Check that the logger message confirms Cython is loaded
        # This would be logged during module import
        assert hasattr(cointegration, 'engle_granger_test')
        
>>>>>>> origin/main
        # The main function should work
        np.random.seed(42)
        n = 100
        x = np.cumsum(np.random.randn(n))
        y = 2 * x + np.random.randn(n) * 0.1
<<<<<<< HEAD

        result = cointegration.engle_granger_test(pd.Series(y), pd.Series(x))

        assert result is not None
        assert "is_cointegrated" in result

=======
        
        result = cointegration.engle_granger_test(pd.Series(y), pd.Series(x))
        
        assert result is not None
        assert 'is_cointegrated' in result
    
>>>>>>> origin/main
    def test_cython_result_consistency(self):
        """Verify Cython results are consistent with wrapper."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")
<<<<<<< HEAD

        from models import cointegration

=======
        
        from models import cointegration
        
>>>>>>> origin/main
        np.random.seed(123)
        n = 200
        x = np.cumsum(np.random.randn(n))
        y = 2 * x + np.random.randn(n) * 0.5
<<<<<<< HEAD

        # Results from wrapper (uses Cython)
        wrapper_result = cointegration.engle_granger_test(pd.Series(y), pd.Series(x))

        # Results from direct Cython call
        cython_result = cointegration_fast.engle_granger_fast(y, x)

        # Both should return valid dictionaries
        assert isinstance(wrapper_result, dict)
        assert isinstance(cython_result, dict)

        # Both should have returned a reasonable beta (both implementations exist and work)
        assert "beta" in wrapper_result
        assert "beta" in cython_result
        assert not np.isnan(wrapper_result["beta"])
        assert not np.isnan(cython_result["beta"])


class TestBrownianBridgeBatchFast:
    """Test brownian_bridge_batch_fast shape, dtype, and values (C-02)."""

    def test_brownian_bridge_output_shape(self):
        """Output shape must be (n_days-1)*bars_per_day × n_sym."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")

        n_days, n_sym, bars_per_day = 5, 3, 8
        closes = np.abs(np.random.randn(n_days, n_sym).astype(np.float64)) + 1.0
        noise = np.random.randn(n_days - 1, bars_per_day, n_sym).astype(np.float64)

        out = cointegration_fast.brownian_bridge_batch_fast(closes, noise, bars_per_day)

        expected_rows = (n_days - 1) * bars_per_day
        assert out.shape == (expected_rows, n_sym), (
            f"Expected shape ({expected_rows}, {n_sym}), got {out.shape}"
        )

    def test_brownian_bridge_no_nan_or_inf(self):
        """Output must contain no NaN or Inf values for valid inputs."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")

        np.random.seed(7)
        n_days, n_sym, bars_per_day = 10, 4, 6
        closes = np.abs(np.random.randn(n_days, n_sym).astype(np.float64)) + 10.0
        noise = np.random.randn(n_days - 1, bars_per_day, n_sym).astype(np.float64)

        out = cointegration_fast.brownian_bridge_batch_fast(closes, noise, bars_per_day)

        assert not np.any(np.isnan(out)), "Output contains NaN"
        assert not np.any(np.isinf(out)), "Output contains Inf"

    def test_brownian_bridge_dtype_float64(self):
        """Output dtype must be float64."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")

        n_days, n_sym, bars_per_day = 3, 2, 4
        closes = np.ones((n_days, n_sym), dtype=np.float64) * 100.0
        noise = np.random.randn(n_days - 1, bars_per_day, n_sym).astype(np.float64)

        out = cointegration_fast.brownian_bridge_batch_fast(closes, noise, bars_per_day)

        assert out.dtype == np.float64, f"Expected float64, got {out.dtype}"

    def test_brownian_bridge_minimum_days(self):
        """n_days=2 is the minimum valid input — should return (bars_per_day, n_sym)."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")

        n_sym, bars_per_day = 2, 5
        closes = np.array([[100.0, 50.0], [105.0, 52.0]], dtype=np.float64)
        noise = np.random.randn(1, bars_per_day, n_sym).astype(np.float64)

        out = cointegration_fast.brownian_bridge_batch_fast(closes, noise, bars_per_day)

        assert out.shape == (bars_per_day, n_sym)
        assert not np.any(np.isnan(out))

    def test_brownian_bridge_degenerate_n_days_1(self):
        """n_days=1 — degenerate case, function returns empty array."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")

        closes = np.ones((1, 2), dtype=np.float64) * 100.0
        noise = np.zeros((0, 4, 2), dtype=np.float64)

        out = cointegration_fast.brownian_bridge_batch_fast(closes, noise, 4)

        assert out.shape[0] == 0, f"Expected 0 rows for n_days=1, got {out.shape}"


class TestComputeZscoreLastFast:
    """Test compute_zscore_last_fast value, clamping, and edge cases (C-03)."""

    def test_zscore_nominal_value(self):
        """Z-score of last element of a standardised series should be close to known value."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")

        np.random.seed(42)
        lookback = 30
        # Build a spread whose last value is exactly +2 std above mean
        spread = np.zeros(lookback, dtype=np.float64)
        spread[:-1] = np.random.randn(lookback - 1) * 1.0
        mean_val = np.mean(spread[:-1])
        std_val = np.std(spread[:-1])
        spread[-1] = mean_val + 2.0 * std_val

        z = cointegration_fast.compute_zscore_last_fast(spread, lookback)

        # Should be close to 2.0 (with slight numeric diff due to welford vs batch)
        assert 1.5 < z < 2.5, f"Expected z near 2.0, got {z}"

    def test_zscore_clamp_upper(self):
        """Values beyond +6σ must be clamped to +6.0.

        With lookback=50 and a single +outlier, z = sqrt(49) = 7.0 -> clamped to 6.0.
        """
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")

        lookback = 50
        spread = np.zeros(lookback, dtype=np.float64)
        spread[-1] = 1.0  # z = sqrt(lookback-1) = 7 -> clamped to 6.0

        z = cointegration_fast.compute_zscore_last_fast(spread, lookback)

        assert z == 6.0, f"Expected clamp to 6.0, got {z}"

    def test_zscore_clamp_lower(self):
        """Values beyond -6σ must be clamped to -6.0.

        With lookback=50 and a single −outlier, z = -sqrt(49) = -7.0 -> clamped to -6.0.
        """
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")

        lookback = 50
        spread = np.zeros(lookback, dtype=np.float64)
        spread[-1] = -1.0  # z = -sqrt(lookback-1) = -7 -> clamped to -6.0

        z = cointegration_fast.compute_zscore_last_fast(spread, lookback)

        assert z == -6.0, f"Expected clamp to -6.0, got {z}"

    def test_zscore_insufficient_data_returns_zero(self):
        """lookback > len(spread) must return 0.0."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")

        spread = np.array([1.0, 2.0, 3.0], dtype=np.float64)

        z = cointegration_fast.compute_zscore_last_fast(spread, lookback=50)

        assert z == 0.0, f"Expected 0.0 for insufficient data, got {z}"

    def test_zscore_consistency_with_numpy(self):
        """Cython result should match numpy rolling computation on last bar."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")

        np.random.seed(99)
        lookback = 30
        spread = np.random.randn(100).astype(np.float64)

        z_cython = cointegration_fast.compute_zscore_last_fast(spread, lookback)

        window = spread[-lookback:]
        mean_v = np.mean(window)
        std_v = np.std(window) + 1e-8
        z_numpy = (spread[-1] - mean_v) / std_v
        z_numpy = float(np.clip(z_numpy, -6.0, 6.0))

        assert abs(z_cython - z_numpy) < 1e-6, (
            f"Cython z={z_cython} vs numpy z={z_numpy}"
        )


class TestCythonEdgeCases:
    """Test degenerate inputs for engle_granger_fast and half_life_fast (C-05)."""

    def test_engle_granger_insufficient_data(self):
        """n < 20 must return dict with 'error' key and is_cointegrated=False."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")

        y = np.arange(15, dtype=np.float64)
        x = np.arange(15, dtype=np.float64) * 0.5

        result = cointegration_fast.engle_granger_fast(y, x)

        assert "error" in result, "Expected 'error' key for n<20"
        assert result["error"] is not None and len(result["error"]) > 0
        assert result["is_cointegrated"] is False

    def test_engle_granger_nan_in_input(self):
        """NaN in input must return dict with 'error' key."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")

        np.random.seed(0)
        n = 50
        y = np.random.randn(n).astype(np.float64)
        x = np.random.randn(n).astype(np.float64)
        y[10] = np.nan

        result = cointegration_fast.engle_granger_fast(y, x)

        assert "error" in result, "Expected 'error' key for NaN input"
        assert result["error"] is not None
        assert result["is_cointegrated"] is False

    def test_half_life_too_short_returns_minus_one(self):
        """len(spread) < 3 must return -1."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")

        spread_short = np.array([1.0, 2.0], dtype=np.float64)

        hl = cointegration_fast.half_life_fast(spread_short)

        assert hl == -1, f"Expected -1 for len < 3, got {hl}"

    def test_half_life_single_element_returns_minus_one(self):
        """Single-element spread must return -1."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")

        spread_one = np.array([5.0], dtype=np.float64)

        hl = cointegration_fast.half_life_fast(spread_one)

        assert hl == -1, f"Expected -1 for single element, got {hl}"

    def test_zscore_lookback_one_returns_zero(self):
        """lookback=1 is below minimum (2) — must return 0.0."""
        if not CYTHON_AVAILABLE:
            pytest.skip(f"Cython module not available: {CYTHON_IMPORT_ERROR}")

        spread = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)

        z = cointegration_fast.compute_zscore_last_fast(spread, lookback=1)

        assert z == 0.0, f"Expected 0.0 for lookback=1, got {z}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
=======
        
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
>>>>>>> origin/main
