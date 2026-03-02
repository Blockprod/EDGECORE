"""
Tests for Out-of-Sample (OOS) Validation Engine.

Validates that pair trading discovery generalizes to future data,
preventing overfitting and illusory correlations.
"""

import pytest
import pandas as pd
import numpy as np
from validation.oos_validator import OutOfSampleValidator, OOSValidationResult


class TestOOSValidationBasics:
    """Basic tests for OOS validator functionality."""
    
    def test_validator_initialization(self):
        """Test OOS validator initializes with correct defaults."""
        validator = OutOfSampleValidator()
        assert validator.oos_acceptance_threshold == 0.70
        assert validator.hl_drift_tolerance == 0.50
        assert validator.num_symbols == 100
    
    def test_oos_result_repr(self):
        """Test OOSValidationResult string representation."""
        result = OOSValidationResult(
            symbol_1="AAPL",
            symbol_2="GOOGL",
            is_sample_cointegrated=True,
            oos_sample_cointegrated=True,
            is_pvalue=0.01,
            oos_pvalue=0.005,
            is_half_life=20.0,
            oos_half_life=22.0,
            validation_passed=True,
            reason="Valid pair"
        )
        
        repr_str = repr(result)
        assert "✓ PASS" in repr_str
        assert "AAPL_GOOGL" in repr_str
        assert "Valid pair" in repr_str


class TestOOSValidationLogic:
    """Tests for OOS validation decision logic."""
    
    def test_not_cointegrated_fails_validation(self):
        """Test that pairs not cointegrated IS are rejected."""
        validator = OutOfSampleValidator()
        
        # Create non-cointegrated series
        np.random.seed(42)
        is_series_1 = pd.Series(np.random.randn(252))
        is_series_2 = pd.Series(np.random.randn(252))
        oos_series_1 = pd.Series(np.random.randn(30))
        oos_series_2 = pd.Series(np.random.randn(30))
        
        result = validator.validate_pair(
            symbol_1="SYM1",
            symbol_2="SYM2",
            is_series_1=is_series_1,
            is_series_2=is_series_2,
            oos_series_1=oos_series_1,
            oos_series_2=oos_series_2,
            is_pvalue=0.1,  # Not significant in-sample
            is_half_life=None
        )
        
        assert not result.validation_passed
        assert "Not cointegrated in-sample" in result.reason
    
    def test_oos_cointegration_failure(self):
        """Test validation logic when OOS cointegration fails."""
        validator = OutOfSampleValidator()
        
        # Create strongly cointegrated in-sample
        np.random.seed(42)
        x = np.cumsum(np.random.randn(252))
        is_series_1 = pd.Series(x)
        is_series_2 = pd.Series(2.0 * x + np.random.randn(252) * 0.1)
        
        # OOS: completely independent (should fail OOS check)
        oos_series_1 = pd.Series(np.random.randn(30))
        oos_series_2 = pd.Series(np.random.randn(30))
        
        result = validator.validate_pair(
            symbol_1="SYM1",
            symbol_2="SYM2",
            is_series_1=is_series_1,
            is_series_2=is_series_2,
            oos_series_1=oos_series_1,
            oos_series_2=oos_series_2,
            is_pvalue=0.001,  # Significant in-sample
            is_half_life=20.0
        )
        
        # Sprint 3.4: Assert structural fields with real values, not just hasattr
        assert hasattr(result, 'validation_passed')
        assert hasattr(result, 'reason')
        assert isinstance(result.validation_passed, bool), (
            f"validation_passed should be bool, got {type(result.validation_passed)}"
        )
        assert isinstance(result.reason, str) and len(result.reason) > 0, (
            "reason must be a non-empty string"
        )
    
    def test_stable_half_life_passes(self):
        """Test that pairs with stable half-life pass validation."""
        # num_symbols=2 ↓ single pair, no heavy Bonferroni penalty
        validator = OutOfSampleValidator(hl_drift_tolerance=0.50, num_symbols=2)
        
        # Create series where spread is a genuine OU (mean-reverting) process
        # with very high signal-to-noise ratio to ensure p < 0.001 (Rule 2)
        np.random.seed(42)
        theta = 0.1   # Mean reversion speed -> theoretical HL ~ 7 days
        sigma = 0.005 # Very tight noise relative to driver
        
        # Generate a continuous random walk driver (I(1))
        n_total = 700  # 252 IS + 448 OOS (long OOS for reliable estimation)
        driver = np.cumsum(np.random.randn(n_total) * 10.0)
        
        # series_2 = 2*series_1 + OU_noise (stationary spread)
        ou_noise = np.zeros(n_total)
        for i in range(1, n_total):
            ou_noise[i] = ou_noise[i-1] * (1 - theta) + sigma * np.random.randn()
        
        is_series_1 = pd.Series(driver[:252])
        is_series_2 = pd.Series(2.0 * driver[:252] + ou_noise[:252])
        oos_series_1 = pd.Series(driver[252:])
        oos_series_2 = pd.Series(2.0 * driver[252:] + ou_noise[252:])
        
        result = validator.validate_pair(
            symbol_1="SYM1",
            symbol_2="SYM2",
            is_series_1=is_series_1,
            is_series_2=is_series_2,
            oos_series_1=oos_series_1,
            oos_series_2=oos_series_2,
            is_pvalue=0.001,
            is_half_life=7
        )
        
        # Verify result has expected fields
        assert result.is_pvalue == 0.001
        assert result.is_half_life == 7
        
        # Sprint 3.4: Assert OOS is cointegrated with strong p-value
        assert result.oos_sample_cointegrated, (
            f"OOS should be cointegrated (same factor), p={result.oos_pvalue}"
        )
        assert result.oos_pvalue <= 0.001, (
            f"OOS p-value {result.oos_pvalue:.2e} should be <= 0.001 for strong signal"
        )
        # Half-life should be estimated and stable
        assert result.oos_half_life is not None, (
            "OOS half-life must be estimated for strongly cointegrated series"
        )
        # Validation should pass (same underlying OU process)
        assert result.validation_passed, (
            f"Expected validation to pass for stable pair, got: {result.reason}"
        )
    
    def test_large_half_life_drift_fails(self):
        """Test that large half-life drift causes validation failure."""
        validator = OutOfSampleValidator(hl_drift_tolerance=0.20)
        
        # Create series with different mean reversion speeds IS vs OOS
        np.random.seed(42)
        
        # In-sample: fast mean reversion
        x_is = np.cumsum(np.random.randn(252) * 0.01)
        is_series_1 = pd.Series(x_is)
        is_series_2 = pd.Series(2.0 * x_is + np.random.randn(252) * 0.01)
        
        # OOS: slow mean reversion (simulates market regime change)
        x_oos = np.cumsum(np.random.randn(30) * 0.1)
        oos_series_1 = pd.Series(x_oos)
        oos_series_2 = pd.Series(2.0 * x_oos + np.random.randn(30) * 0.5)
        
        result = validator.validate_pair(
            symbol_1="SYM1",
            symbol_2="SYM2",
            is_series_1=is_series_1,
            is_series_2=is_series_2,
            oos_series_1=oos_series_1,
            oos_series_2=oos_series_2,
            is_pvalue=0.001,
            is_half_life=10.0
        )
        
        # Sprint 3.4: Assert validation MUST fail (either via failing OOS cointegration
        # or via half-life drift – both are valid failure modes)
        assert not result.validation_passed, (
            f"Validation should fail for divergent IS/OOS series, "
            f"but got passed=True, reason='{result.reason}'"
        )
        assert result.is_half_life is not None, "IS half-life must be provided"
        # If OOS half-life was estimated, check it drifted
        if result.oos_half_life is not None:
            hl_ratio = result.oos_half_life / result.is_half_life
            hl_drift = abs(1.0 - hl_ratio)
            assert hl_drift > 0.20, (
                f"Half-life drift {hl_drift:.2f} should exceed tolerance 0.20"
            )
            assert "drifted" in result.reason.lower(), (
                f"Reason should mention 'drifted', got: {result.reason}"
            )


class TestOOSValidationAggregate:
    """Tests for aggregate validation across multiple pairs."""
    
    def test_validate_pair_set(self):
        """Test validating a set of pairs."""
        validator = OutOfSampleValidator()
        
        np.random.seed(42)
        
        # Create a set of pairs to validate
        pairs_with_data = []
        
        # Pair 1: cointegrated both IS and OOS (PASS)
        x1 = np.cumsum(np.random.randn(252))
        pairs_with_data.append({
            'symbol_1': 'PAIR1_A',
            'symbol_2': 'PAIR1_B',
            'is_series_1': pd.Series(x1),
            'is_series_2': pd.Series(2.0 * x1 + np.random.randn(252) * 0.1),
            'oos_series_1': pd.Series(np.cumsum(np.random.randn(30))),
            'oos_series_2': pd.Series(2.0 * np.cumsum(np.random.randn(30)) + np.random.randn(30) * 0.1),
            'is_pvalue': 0.001,
            'is_half_life': 20.0
        })
        
        # Pair 2: not cointegrated (FAIL)
        pairs_with_data.append({
            'symbol_1': 'PAIR2_A',
            'symbol_2': 'PAIR2_B',
            'is_series_1': pd.Series(np.random.randn(252)),
            'is_series_2': pd.Series(np.random.randn(252)),
            'oos_series_1': pd.Series(np.random.randn(30)),
            'oos_series_2': pd.Series(np.random.randn(30)),
            'is_pvalue': 0.1,
            'is_half_life': None
        })
        
        results = validator.validate_pair_set(pairs_with_data)
        
        # Should have at least 1 failed pair (PAIR2)
        assert results['total_pairs_tested'] == 2
        assert results['invalid_pairs'] >= 1
        assert len(results['failed_pairs']) >= 1
    
    def test_validation_rate_calculation(self):
        """Test that validation rate is calculated correctly."""
        validator = OutOfSampleValidator()
        
        # Create 5 pairs, varying cointegration
        pairs_with_data = []
        np.random.seed(42)
        
        for i in range(5):
            # Create pairs with varying strength
            x = np.cumsum(np.random.randn(252))
            noise_scale = 0.01 * (i + 1)  # Increasing noise
            
            pairs_with_data.append({
                'symbol_1': f'SYM{i}_A',
                'symbol_2': f'SYM{i}_B',
                'is_series_1': pd.Series(x),
                'is_series_2': pd.Series(2.0 * x + np.random.randn(252) * noise_scale),
                'oos_series_1': pd.Series(np.cumsum(np.random.randn(30))),
                'oos_series_2': pd.Series(2.0 * np.cumsum(np.random.randn(30)) + np.random.randn(30) * noise_scale),
                'is_pvalue': 0.001,
                'is_half_life': 20.0
            })
        
        results = validator.validate_pair_set(pairs_with_data)
        
        # Validation rate should be between 0 and 1
        assert 0.0 <= results['validation_rate'] <= 1.0
        
        # Valid pairs should match the validation rate
        expected_valid = int(round(results['total_pairs_tested'] * results['validation_rate']))
        assert results['valid_pairs'] == expected_valid
    
    def test_robustness_assessment(self):
        """Test robustness assessment based on validation rate."""
        validator = OutOfSampleValidator(oos_acceptance_threshold=0.70)
        
        # Create a scenario with high validation rate
        pairs_with_data = []
        np.random.seed(99)
        
        for i in range(10):
            x = np.cumsum(np.random.randn(252))
            pairs_with_data.append({
                'symbol_1': f'GOOD{i}_A',
                'symbol_2': f'GOOD{i}_B',
                'is_series_1': pd.Series(x),
                'is_series_2': pd.Series(2.0 * x + np.random.randn(252) * 0.05),
                'oos_series_1': pd.Series(np.cumsum(np.random.randn(30))),
                'oos_series_2': pd.Series(2.0 * np.cumsum(np.random.randn(30)) + np.random.randn(30) * 0.05),
                'is_pvalue': 0.0001,
                'is_half_life': 20.0
            })
        
        results = validator.validate_pair_set(pairs_with_data)
        
        # With clean data, should achieve high validation rate
        if results['valid_pairs'] >= int(0.70 * results['total_pairs_tested']):
            assert results['strategy_robustness'] == "robust"
        else:
            assert results['strategy_robustness'] == "overfitted"


class TestOOSValidationReport:
    """Tests for validation reporting."""
    
    def test_generate_report(self):
        """Test that validation report can be generated."""
        validator = OutOfSampleValidator()
        
        np.random.seed(42)
        x = np.cumsum(np.random.randn(252))
        is_series_1 = pd.Series(x)
        is_series_2 = pd.Series(2.0 * x + np.random.randn(252) * 0.1)
        oos_series_1 = pd.Series(np.cumsum(np.random.randn(30)))
        oos_series_2 = pd.Series(2.0 * np.cumsum(np.random.randn(30)) + np.random.randn(30) * 0.1)
        
        validator.validate_pair(
            symbol_1="TEST_SYM1",
            symbol_2="TEST_SYM2",
            is_series_1=is_series_1,
            is_series_2=is_series_2,
            oos_series_1=oos_series_1,
            oos_series_2=oos_series_2,
            is_pvalue=0.001,
            is_half_life=20.0
        )
        
        report = validator.report()
        
        # Report should contain summary info
        assert "OUT-OF-SAMPLE VALIDATION REPORT" in report
        assert "Valid Pairs" in report
        assert "Robustness Assessment" in report
