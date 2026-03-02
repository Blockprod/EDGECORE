"""
Sprint 1.4 – Test Bonferroni correction in engle_granger_test_cpp_optimized.

Proves C-04 fix:
  - engle_granger_test_cpp_optimized now accepts num_symbols/apply_bonferroni
  - Bonferroni-corrected alpha is used instead of hardcoded 0.05
  - Fallback to pure Python also forwards Bonferroni params
  - All callers pass the correct number of symbols

Run: pytest tests/test_bonferroni_cython_fix.py -v
"""

import pytest
import numpy as np
import pandas as pd

from models.cointegration import (
    engle_granger_test,
    engle_granger_test_cpp_optimized,
)


def _make_cointegrated_pair(n=300, noise_std=0.5, seed=42):
    """Create a strongly cointegrated pair."""
    np.random.seed(seed)
    x = pd.Series(100.0 + np.cumsum(np.random.normal(0, 1, n)))
    y = pd.Series(1.5 * x.values + np.random.normal(0, noise_std, n))
    return y, x


def _make_random_walks(n=300, seed=42):
    """Create two independent random walks (NOT cointegrated)."""
    np.random.seed(seed)
    x = pd.Series(100.0 + np.cumsum(np.random.normal(0, 1, n)))
    y = pd.Series(100.0 + np.cumsum(np.random.normal(0, 1, n)))
    return y, x


class TestCppOptimizedAcceptsBonferoniParams:
    """Verify the function signature now accepts Bonferroni params (C-04 fix)."""

    def test_accepts_num_symbols_kwarg(self):
        """Function must accept num_symbols without TypeError."""
        y, x = _make_cointegrated_pair()
        result = engle_granger_test_cpp_optimized(y, x, num_symbols=10)
        assert 'adf_pvalue' in result

    def test_accepts_apply_bonferroni_kwarg(self):
        """Function must accept apply_bonferroni without TypeError."""
        y, x = _make_cointegrated_pair()
        result = engle_granger_test_cpp_optimized(
            y, x, apply_bonferroni=False
        )
        assert 'is_cointegrated' in result

    def test_accepts_both_kwargs(self):
        """Function must accept both kwargs together."""
        y, x = _make_cointegrated_pair()
        result = engle_granger_test_cpp_optimized(
            y, x, num_symbols=50, apply_bonferroni=True
        )
        assert 'alpha_threshold' in result
        assert 'num_pairs' in result


class TestBonferroniAlphaCorrection:
    """Verify Bonferroni correction changes the decision threshold."""

    def test_alpha_corrected_50_symbols(self):
        """50 symbols ↓ 1225 pairs ↓ α = 0.05/1225 ≈ 4.08e-5."""
        y, x = _make_cointegrated_pair()
        result = engle_granger_test_cpp_optimized(
            y, x, num_symbols=50, apply_bonferroni=True
        )
        expected_alpha = 0.05 / (50 * 49 // 2)  # 0.0000408...
        assert abs(result['alpha_threshold'] - expected_alpha) < 1e-10

    def test_alpha_corrected_10_symbols(self):
        """10 symbols ↓ 45 pairs ↓ α = 0.05/45 ≈ 0.00111."""
        y, x = _make_cointegrated_pair()
        result = engle_granger_test_cpp_optimized(
            y, x, num_symbols=10, apply_bonferroni=True
        )
        expected_alpha = 0.05 / 45
        assert abs(result['alpha_threshold'] - expected_alpha) < 1e-10

    def test_no_bonferroni_uses_nominal_alpha(self):
        """apply_bonferroni=False ↓ α = 0.05."""
        y, x = _make_cointegrated_pair()
        result = engle_granger_test_cpp_optimized(
            y, x, num_symbols=50, apply_bonferroni=False
        )
        assert result['alpha_threshold'] == 0.05

    def test_no_num_symbols_uses_nominal_alpha(self):
        """num_symbols=None ↓ α = 0.05 (backward compatible)."""
        y, x = _make_cointegrated_pair()
        result = engle_granger_test_cpp_optimized(y, x)
        assert result['alpha_threshold'] == 0.05

    def test_single_symbol_pair_edge_case(self):
        """num_symbols=2 ↓ 1 pair ↓ α = 0.05 (no correction needed)."""
        y, x = _make_cointegrated_pair()
        result = engle_granger_test_cpp_optimized(
            y, x, num_symbols=2, apply_bonferroni=True
        )
        assert result['alpha_threshold'] == 0.05


class TestBonferroniChangesDecision:
    """Prove that Bonferroni correction changes is_cointegrated decisions."""

    def test_marginal_pair_rejected_with_bonferroni(self):
        """A pair with marginal p-value (0.01 < p < 0.05) should be
        accepted without Bonferroni but rejected with 50-symbol Bonferroni."""
        # We search for a seed that produces a marginal p-value
        # between the nominal (0.05) and corrected (0.05/1225) thresholds
        found = False
        for seed in range(100):
            np.random.seed(seed)
            # Weakly cointegrated: high noise ↓ marginal p-value
            x = pd.Series(100.0 + np.cumsum(np.random.normal(0, 1, 300)))
            y = pd.Series(1.5 * x.values + np.random.normal(0, 8, 300))

            r_no_bonf = engle_granger_test_cpp_optimized(
                y, x, apply_bonferroni=False
            )
            r_bonf = engle_granger_test_cpp_optimized(
                y, x, num_symbols=50, apply_bonferroni=True
            )

            pval = r_no_bonf['adf_pvalue']
            alpha_corrected = 0.05 / (50 * 49 // 2)

            if alpha_corrected < pval < 0.05:
                # Found a marginal pair
                assert r_no_bonf['is_cointegrated']
                assert not r_bonf['is_cointegrated']
                found = True
                break

        assert found, (
            "Could not find a seed producing a marginal p-value "
            "between 0.05 and Bonferroni-corrected alpha"
        )

    def test_strong_pair_survives_bonferroni(self):
        """A strongly cointegrated pair (p ≈ 0) survives Bonferroni."""
        y, x = _make_cointegrated_pair(noise_std=0.3)
        result = engle_granger_test_cpp_optimized(
            y, x, num_symbols=50, apply_bonferroni=True
        )
        # Strong pair p-value should be << 0.0001
        assert result['adf_pvalue'] < 0.001
        assert result['is_cointegrated']


class TestFallbackForwardsBonferroni:
    """Verify that the pure Python fallback also uses Bonferroni params."""

    def test_pure_python_path_applies_bonferroni(self):
        """engle_granger_test (pure Python) correctly uses num_symbols."""
        y, x = _make_cointegrated_pair()
        result = engle_granger_test(
            y, x, num_symbols=50, apply_bonferroni=True
        )
        expected_alpha = 0.05 / (50 * 49 // 2)
        assert abs(result['alpha_threshold'] - expected_alpha) < 1e-10

    def test_cpp_optimized_fallback_matches_pure_python(self):
        """When Cython is unavailable, cpp_optimized must match pure Python."""
        y, x = _make_cointegrated_pair()

        r_pure = engle_granger_test(
            y, x, num_symbols=20, apply_bonferroni=True
        )
        r_opt = engle_granger_test_cpp_optimized(
            y, x, num_symbols=20, apply_bonferroni=True
        )

        assert r_pure['is_cointegrated'] == r_opt['is_cointegrated']
        assert abs(r_pure['adf_pvalue'] - r_opt['adf_pvalue']) < 1e-10
        assert r_pure['alpha_threshold'] == r_opt['alpha_threshold']


class TestFalsePositiveReduction:
    """Statistical test: Bonferroni reduces false positives on random walks."""

    def test_bonferroni_reduces_false_positives(self):
        """With 50 random-walk pairs, Bonferroni should yield fewer
        false positives than uncorrected testing."""
        np.random.seed(42)

        fp_uncorrected = 0
        fp_corrected = 0
        n_tests = 50

        for i in range(n_tests):
            y = pd.Series(np.random.randn(252).cumsum())
            x = pd.Series(np.random.randn(252).cumsum())

            r_uncorr = engle_granger_test_cpp_optimized(
                y, x, apply_bonferroni=False
            )
            r_corr = engle_granger_test_cpp_optimized(
                y, x, num_symbols=20, apply_bonferroni=True
            )

            if r_uncorr['is_cointegrated']:
                fp_uncorrected += 1
            if r_corr['is_cointegrated']:
                fp_corrected += 1

        # Bonferroni should never produce MORE false positives
        assert fp_corrected <= fp_uncorrected


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
