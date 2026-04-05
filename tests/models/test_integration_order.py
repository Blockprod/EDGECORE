<<<<<<< HEAD
﻿"""
Tests for Sprint 2.7 ÔÇô I(1) pre-test before Engle-Granger (M-07).

Coverage:
  - verify_integration_order() on I(1) random walk Ôåô accepted
  - verify_integration_order() on I(0) stationary series Ôåô rejected
  - verify_integration_order() on I(2) series Ôåô rejected
=======
"""
Tests for Sprint 2.7 – I(1) pre-test before Engle-Granger (M-07).

Coverage:
  - verify_integration_order() on I(1) random walk ↓ accepted
  - verify_integration_order() on I(0) stationary series ↓ rejected
  - verify_integration_order() on I(2) series ↓ rejected
>>>>>>> origin/main
  - engle_granger_test() rejects pair where one series is I(0)
  - engle_granger_test() accepts I(1) pair
  - engle_granger_test_cpp_optimized() same behaviour
  - check_integration_order=False bypass
  - Insufficient data edge case
  - Performance: ADF+KPSS < 10ms per series
"""

import time
<<<<<<< HEAD

=======
>>>>>>> origin/main
import numpy as np
import pandas as pd

from models.cointegration import (
<<<<<<< HEAD
    engle_granger_test,
    engle_granger_test_cpp_optimized,
    verify_integration_order,
)

# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
# Helpers
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

def _random_walk(n: int = 500, seed: int = 42) -> pd.Series:
    """Generate a pure random walk ÔÇô I(1)."""
=======
    verify_integration_order,
    engle_granger_test,
    engle_granger_test_cpp_optimized,
)


# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
# Helpers
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ

def _random_walk(n: int = 500, seed: int = 42) -> pd.Series:
    """Generate a pure random walk – I(1)."""
>>>>>>> origin/main
    rng = np.random.RandomState(seed)
    return pd.Series(np.cumsum(rng.normal(0, 1, n)))


def _stationary_series(n: int = 500, seed: int = 42) -> pd.Series:
<<<<<<< HEAD
    """Generate a mean-reverting AR(1) ÔÇô I(0)."""
=======
    """Generate a mean-reverting AR(1) – I(0)."""
>>>>>>> origin/main
    rng = np.random.RandomState(seed)
    s = np.zeros(n)
    for i in range(1, n):
        s[i] = 0.3 * s[i - 1] + rng.normal(0, 1)
    return pd.Series(s)


def _cointegrated_pair(n: int = 500, seed: int = 42):
    """Two I(1) series that are cointegrated: y = 2*x + I(0) noise."""
    rng = np.random.RandomState(seed)
    x = pd.Series(np.cumsum(rng.normal(0, 1, n)))
    noise = pd.Series(rng.normal(0, 0.5, n))
    y = 2 * x + noise
    return y, x


<<<<<<< HEAD
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
# verify_integration_order()
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
=======
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
# verify_integration_order()
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
>>>>>>> origin/main

class TestVerifyIntegrationOrder:
    """Unit tests for the I(1) check function."""

    def test_random_walk_is_I1(self):
        """A random walk should be classified as I(1)."""
        rw = _random_walk(n=500)
        result = verify_integration_order(rw, name="rw")
        assert result['is_I1'], f"Random walk misclassified: {result}"
        assert result['error'] is None

    def test_stationary_series_not_I1(self):
<<<<<<< HEAD
        """A stationary AR(1) should NOT be I(1) ÔÇô it's I(0)."""
=======
        """A stationary AR(1) should NOT be I(1) – it's I(0)."""
>>>>>>> origin/main
        s = _stationary_series(n=500)
        result = verify_integration_order(s, name="stationary")
        assert not result['is_I1'], f"Stationary series misclassified: {result}"

    def test_result_keys(self):
        """Result dict should have all expected keys."""
        rw = _random_walk()
        result = verify_integration_order(rw, name="test")
        expected_keys = {
            'series_name', 'is_I1',
            'adf_level_pvalue', 'kpss_level_pvalue', 'adf_diff_pvalue',
            'error',
        }
        assert expected_keys.issubset(result.keys())
        assert result['series_name'] == "test"

    def test_insufficient_data(self):
<<<<<<< HEAD
        """Very short series Ôåô error, not I(1)."""
=======
        """Very short series ↓ error, not I(1)."""
>>>>>>> origin/main
        short = pd.Series([1, 2, 3, 4, 5])
        result = verify_integration_order(short, name="short")
        assert not result['is_I1']
        assert result['error'] is not None
        assert "Insufficient" in result['error']

    def test_nan_values_handled(self):
        """Series with NaN leading values should be cleaned and processed."""
        rw = _random_walk(n=500)
        rw.iloc[:10] = np.nan
        result = verify_integration_order(rw, name="rw_nan")
        # Should still work after dropna (490 observations)
        assert result['error'] is None
        assert result['is_I1']

    def test_all_pvalues_populated(self):
        """All p-values should be finite floats."""
        rw = _random_walk(n=500)
        result = verify_integration_order(rw)
        assert np.isfinite(result['adf_level_pvalue'])
        assert np.isfinite(result['kpss_level_pvalue'])
        assert np.isfinite(result['adf_diff_pvalue'])

    def test_random_walk_adf_level_high(self):
        """For a random walk, ADF level p-value should be high (non-stationary)."""
        rw = _random_walk(n=500)
        result = verify_integration_order(rw)
        assert result['adf_level_pvalue'] > 0.05

    def test_stationary_adf_level_low(self):
        """For a stationary series, ADF level p-value should be low."""
        s = _stationary_series(n=500)
        result = verify_integration_order(s)
        assert result['adf_level_pvalue'] < 0.05

    def test_performance_under_10ms(self):
        """ADF+KPSS should execute in < 10ms per series (DoD)."""
        rw = _random_walk(n=500)
        # Warm up
        verify_integration_order(rw)
        # Time it
        start = time.perf_counter()
        for _ in range(10):
            verify_integration_order(rw)
        elapsed = (time.perf_counter() - start) / 10
        # Allow generous margin (10x) for CI/slow machines
        assert elapsed < 0.1, f"verify_integration_order took {elapsed*1000:.1f}ms (target: <10ms)"


<<<<<<< HEAD
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
# engle_granger_test() with I(1) pre-check
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
=======
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
# engle_granger_test() with I(1) pre-check
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
>>>>>>> origin/main

class TestEngleGrangerIntegrationCheck:
    """Tests that the I(1) gate works inside engle_granger_test()."""

    def test_cointegrated_I1_pair_accepted(self):
<<<<<<< HEAD
        """Two cointegrated I(1) series Ôåô passes I(1) check, may be cointegrated."""
=======
        """Two cointegrated I(1) series ↓ passes I(1) check, may be cointegrated."""
>>>>>>> origin/main
        y, x = _cointegrated_pair(n=500)
        result = engle_granger_test(y, x, check_integration_order=True)
        # Should NOT be rejected by integration order check
        assert result.get('error') is None or 'Series not I(1)' not in result.get('error', '')

    def test_stationary_series_rejected(self):
        """If one series is I(0), the pair should be rejected before OLS."""
        y = _random_walk(n=500)
        x = _stationary_series(n=500, seed=99)
        result = engle_granger_test(y, x, check_integration_order=True)
        assert not result['is_cointegrated']
        assert 'Series not I(1)' in result.get('error', '')
        assert 'integration_order' in result

    def test_both_stationary_rejected(self):
<<<<<<< HEAD
        """Both I(0) Ôåô rejected."""
=======
        """Both I(0) ↓ rejected."""
>>>>>>> origin/main
        y = _stationary_series(n=500, seed=1)
        x = _stationary_series(n=500, seed=2)
        result = engle_granger_test(y, x, check_integration_order=True)
        assert not result['is_cointegrated']
        assert 'Series not I(1)' in result.get('error', '')

    def test_bypass_integration_check(self):
        """check_integration_order=False should skip the pre-check."""
        y = _stationary_series(n=500, seed=1)
        x = _stationary_series(n=500, seed=2)
        result = engle_granger_test(y, x, check_integration_order=False)
        # Should NOT have integration order error
        error = result.get('error', '')
        assert 'Series not I(1)' not in (error or '')

    def test_error_dict_structure(self):
        """Rejection result should have standard dict keys."""
        y = _random_walk(n=500)
        x = _stationary_series(n=500)
        result = engle_granger_test(y, x, check_integration_order=True)
        if 'Series not I(1)' in result.get('error', ''):
            assert 'beta' in result
            assert 'adf_pvalue' in result
            assert result['adf_pvalue'] == 1.0
            assert not result['is_cointegrated']


<<<<<<< HEAD
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
# engle_granger_test_cpp_optimized() with I(1) pre-check
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
=======
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
# engle_granger_test_cpp_optimized() with I(1) pre-check
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
>>>>>>> origin/main

class TestCppOptimizedIntegrationCheck:
    """Same tests for the Cython-optimized path."""

    def test_cointegrated_I1_pair_accepted(self):
        y, x = _cointegrated_pair(n=500)
        result = engle_granger_test_cpp_optimized(y, x, check_integration_order=True)
        assert result.get('error') is None or 'Series not I(1)' not in result.get('error', '')

    def test_stationary_series_rejected(self):
        y = _random_walk(n=500)
        x = _stationary_series(n=500, seed=99)
        result = engle_granger_test_cpp_optimized(y, x, check_integration_order=True)
        assert not result['is_cointegrated']
        assert 'Series not I(1)' in result.get('error', '')

    def test_bypass_integration_check(self):
        y = _stationary_series(n=500, seed=1)
        x = _stationary_series(n=500, seed=2)
        result = engle_granger_test_cpp_optimized(y, x, check_integration_order=False)
        error = result.get('error', '')
        assert 'Series not I(1)' not in (error or '')


<<<<<<< HEAD
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
# Edge cases
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
=======
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
# Edge cases
# ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
>>>>>>> origin/main

class TestEdgeCases:
    """Various edge cases for robustness."""

    def test_constant_series_not_I1(self):
<<<<<<< HEAD
        """Constant series Ôåô not I(1)."""
=======
        """Constant series ↓ not I(1)."""
>>>>>>> origin/main
        const = pd.Series(np.ones(200))
        result = verify_integration_order(const, name="constant")
        assert not result['is_I1']

    def test_trending_series(self):
        """Deterministic trend + noise is typically not I(1) by KPSS."""
        rng = np.random.RandomState(42)
        trend = pd.Series(np.arange(500) * 0.1 + rng.normal(0, 0.5, 500))
        # A deterministic trend may or may not be classified as I(1)
<<<<<<< HEAD
        # depending on noise magnitude ÔÇô just ensure no crash
=======
        # depending on noise magnitude – just ensure no crash
>>>>>>> origin/main
        result = verify_integration_order(trend, name="trend")
        assert result['error'] is None
        assert isinstance(result['is_I1'], (bool, np.bool_))

    def test_very_long_series(self):
        """Long series should still work."""
        rw = _random_walk(n=5000, seed=77)
        result = verify_integration_order(rw, name="long")
        assert result['is_I1']

    def test_multiple_seeds_random_walk(self):
        """Multiple random walks should all be classified I(1)."""
        for seed in [10, 20, 30, 40, 50]:
            rw = _random_walk(n=500, seed=seed)
            result = verify_integration_order(rw, name=f"rw_{seed}")
            assert result['is_I1'], f"Seed {seed} misclassified: {result}"

    def test_multiple_seeds_stationary(self):
        """Multiple stationary series should all be classified as NOT I(1)."""
        for seed in [10, 20, 30, 40, 50]:
            s = _stationary_series(n=500, seed=seed)
            result = verify_integration_order(s, name=f"ar1_{seed}")
            assert not result['is_I1'], f"Seed {seed} misclassified: {result}"
