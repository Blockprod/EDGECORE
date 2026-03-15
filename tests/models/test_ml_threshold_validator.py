"""
Tests for ML Threshold OOS Validator ÔÇô Sprint 2.5 (M-05).

Coverage:
  - Walk-forward fold mechanics
  - Structured data Ôåô ML approved
  - Random/noise data Ôåô ML disabled
  - Degradation calculation
  - should_use_ml_thresholds() guard
  - Integration with AdaptiveThresholdManager
  - Insufficient data edge case
  - ValidationResult serialisation
"""

import numpy as np
import pandas as pd
import pytest

from models.ml_threshold_validator import (
    MLThresholdValidator,
    ValidationResult,
)
from models.ml_threshold_optimizer import (
    AdaptiveThresholdManager,
    MLThresholdOptimizer,
    ThresholdFeatureEngineer,
)


# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
# Helpers
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

def _make_structured_data(n: int = 300, seed: int = 42):
    """
    Create data where y is a deterministic function of X + small noise.
    ML should generalise well Ôåô OOS R┬▓ near IS R┬▓.
    """
    rng = np.random.RandomState(seed)
    X = pd.DataFrame({
        "half_life": rng.uniform(5, 50, n),
        "volatility": rng.uniform(0.01, 0.05, n),
        "autocorrelation": rng.uniform(-0.3, 0.8, n),
        "spread_mean": rng.uniform(-1, 1, n),
    })
    # Deterministic signal + tiny noise
    y_entry = 1.5 + 0.02 * X["half_life"] + 10 * X["volatility"] + rng.normal(0, 0.05, n)
    y_exit = 0.3 + 0.005 * X["half_life"] + 5 * X["volatility"] + rng.normal(0, 0.02, n)
    return X, pd.Series(y_entry), pd.Series(y_exit)


def _make_random_data(n: int = 300, seed: int = 42):
    """
    Pure noise: X has no relationship to y.
    ML will overfit IS Ôåô OOS degradation should be large.
    """
    rng = np.random.RandomState(seed)
    X = pd.DataFrame({
        "half_life": rng.uniform(5, 50, n),
        "volatility": rng.uniform(0.01, 0.05, n),
        "autocorrelation": rng.uniform(-0.3, 0.8, n),
        "spread_mean": rng.uniform(-1, 1, n),
    })
    y_entry = pd.Series(rng.uniform(1.0, 3.0, n))
    y_exit = pd.Series(rng.uniform(0.1, 0.8, n))
    return X, y_entry, y_exit


# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
# Basic Validator Tests
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

class TestMLThresholdValidator:
    """Core validator unit tests."""

    def test_init_defaults(self):
        v = MLThresholdValidator()
        assert v.n_folds == 5
        assert v.max_degradation_pct == 20.0
        assert v.min_oos_r2 == 0.0

    def test_init_custom(self):
        v = MLThresholdValidator(n_folds=3, max_degradation_pct=10.0, min_oos_r2=0.5)
        assert v.n_folds == 3
        assert v.max_degradation_pct == 10.0
        assert v.min_oos_r2 == 0.5

    def test_structured_data_ml_approved(self):
        """Structured data with real signal Ôåô ML should be approved."""
        X, y_entry, y_exit = _make_structured_data(n=300)
        v = MLThresholdValidator(n_folds=5, max_degradation_pct=20.0)
        result = v.validate_oos_performance(X, y_entry, y_exit)

        assert result.ml_approved
        assert result.rejection_reason == ""
        assert result.n_folds >= 3  # Should produce at least 3 valid folds
        assert len(result.fold_results) >= 3
        assert result.avg_oos_r2_entry > 0.5
        assert result.avg_oos_r2_exit > 0.5

    def test_random_data_ml_disabled(self):
        """
        DoD SCENARIO: Pure noise Ôåô ML auto-disabled.
        Random data should produce high IS R┬▓ (overfitting) but low OOS R┬▓.
        """
        X, y_entry, y_exit = _make_random_data(n=300)
        v = MLThresholdValidator(n_folds=5, max_degradation_pct=20.0)
        result = v.validate_oos_performance(X, y_entry, y_exit)

        # ML should be rejected ÔÇô OOS degradation should exceed 20%
        assert not result.ml_approved
        assert "ML thresholds disabled" in result.rejection_reason
        assert result.n_folds >= 3

    def test_fold_results_populated(self):
        """Fold results carry correct sizes and metrics."""
        X, y_entry, y_exit = _make_structured_data(n=180)
        v = MLThresholdValidator(n_folds=5)
        result = v.validate_oos_performance(X, y_entry, y_exit)

        for fold in result.fold_results:
            assert fold.train_size > 0
            assert fold.test_size > 0
            assert fold.is_rmse_entry >= 0
            assert fold.oos_rmse_entry >= 0
            assert fold.is_rmse_exit >= 0
            assert fold.oos_rmse_exit >= 0

    def test_expanding_window_train_grows(self):
        """Each successive fold should have >= the previous fold's train size."""
        X, y_entry, y_exit = _make_structured_data(n=300)
        v = MLThresholdValidator(n_folds=5)
        result = v.validate_oos_performance(X, y_entry, y_exit)

        sizes = [f.train_size for f in result.fold_results]
        for i in range(1, len(sizes)):
            assert sizes[i] >= sizes[i - 1], f"Fold {i} train_size should be >= fold {i-1}"

    def test_insufficient_data(self):
        """Very small dataset Ôåô rejected immediately."""
        X = pd.DataFrame({"a": [1, 2, 3]})
        y_entry = pd.Series([1, 2, 3])
        y_exit = pd.Series([0.5, 0.6, 0.7])
        
        v = MLThresholdValidator(n_folds=5)
        result = v.validate_oos_performance(X, y_entry, y_exit)

        assert not result.ml_approved
        assert "Insufficient data" in result.rejection_reason
        assert result.n_folds == 0


# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
# Degradation Calculation
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

class TestDegradation:
    """Unit tests for _calc_degradation static method."""

    def test_no_degradation(self):
        deg = MLThresholdValidator._calc_degradation(0.8, 0.8)
        assert deg == pytest.approx(0.0)

    def test_twenty_pct_degradation(self):
        deg = MLThresholdValidator._calc_degradation(0.8, 0.64)
        assert deg == pytest.approx(20.0)

    def test_full_degradation(self):
        deg = MLThresholdValidator._calc_degradation(0.8, 0.0)
        assert deg == pytest.approx(100.0)

    def test_oos_better_than_is(self):
        """OOS better than IS Ôåô 0% degradation, not negative."""
        deg = MLThresholdValidator._calc_degradation(0.8, 0.9)
        assert deg == pytest.approx(0.0)

    def test_zero_is_score(self):
        deg = MLThresholdValidator._calc_degradation(0.0, 0.5)
        assert deg == 0.0

    def test_negative_is_score(self):
        deg = MLThresholdValidator._calc_degradation(-0.2, -0.5)
        assert deg == 100.0  # OOS worse than IS, IS was already bad


# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
# should_use_ml_thresholds()
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

class TestShouldUseML:
    """Tests for the convenience guard method."""

    def test_good_model_returns_true(self):
        v = MLThresholdValidator()
        v.is_score = 0.8
        v.oos_score = 0.75  # 93.75% of IS Ôåô ok
        assert v.should_use_ml_thresholds()

    def test_bad_model_returns_false(self):
        v = MLThresholdValidator()
        v.is_score = 0.8
        v.oos_score = 0.5  # 62.5% of IS Ôåô too low
        assert not v.should_use_ml_thresholds()

    def test_exact_boundary(self):
        v = MLThresholdValidator()
        v.is_score = 1.0
        v.oos_score = 0.8  # Exactly 80% Ôåô should pass
        assert v.should_use_ml_thresholds()

    def test_zero_is_score_returns_false(self):
        v = MLThresholdValidator()
        v.is_score = 0.0
        v.oos_score = 0.5
        assert not v.should_use_ml_thresholds()

    def test_after_structured_validation(self):
        """After running structured validation, should_use should be True."""
        X, y_entry, y_exit = _make_structured_data(n=300)
        v = MLThresholdValidator(n_folds=5)
        v.validate_oos_performance(X, y_entry, y_exit)
        assert v.should_use_ml_thresholds()


# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
# ValidationResult serialisation
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_to_dict(self):
        result = ValidationResult(
            n_folds=3,
            avg_is_r2_entry=0.9123,
            avg_oos_r2_entry=0.7456,
            avg_is_r2_exit=0.8765,
            avg_oos_r2_exit=0.7101,
            entry_degradation_pct=18.3,
            exit_degradation_pct=19.0,
            ml_approved=True,
            rejection_reason="",
        )
        d = result.to_dict()
        assert d["n_folds"] == 3
        assert d["avg_is_r2_entry"] == 0.9123
        assert d["ml_approved"]
        assert d["rejection_reason"] == ""

    def test_default_values(self):
        result = ValidationResult(n_folds=0)
        assert not result.ml_approved
        assert result.rejection_reason == ""
        assert result.fold_results == []


# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
# Min OOS R┬▓ threshold
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

class TestMinOosR2:
    """Tests for the min_oos_r2 absolute floor."""

    def test_rejected_below_floor(self):
        """Even if degradation is low, OOS R┬▓ below floor Ôåô reject."""
        X, y_entry, y_exit = _make_random_data(n=300)
        v = MLThresholdValidator(
            n_folds=5,
            max_degradation_pct=100.0,  # Very permissive degradation
            min_oos_r2=0.5,             # Strict absolute floor
        )
        result = v.validate_oos_performance(X, y_entry, y_exit)
        assert not result.ml_approved
        assert "OOS R┬▓ too low" in result.rejection_reason


# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
# Integration with AdaptiveThresholdManager
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

class TestAdaptiveThresholdManagerIntegration:
    """Tests that Sprint 2.5 OOS gate works in AdaptiveThresholdManager."""

    def test_ml_enabled_by_default(self):
        mgr = AdaptiveThresholdManager()
        assert mgr.ml_enabled
        assert mgr._oos_rejection_reason == ""

    def test_get_thresholds_returns_defaults_when_ml_disabled(self):
        """When ml_enabled=False, get_thresholds() returns fixed defaults."""
        mgr = AdaptiveThresholdManager(default_entry=2.0, default_exit=0.5)
        
        # Set a model manually
        optimizer = MLThresholdOptimizer()
        feature_engineer = ThresholdFeatureEngineer()
        mgr.set_model(optimizer, feature_engineer)
        
        # Force disable ML
        mgr.ml_enabled = False
        mgr._oos_rejection_reason = "test"
        
        entry, exit_ = mgr.get_thresholds("AAPL_MSFT")
        assert entry == 2.0
        assert exit_ == 0.5

    def test_get_thresholds_returns_defaults_when_no_model(self):
        """Without model, returns defaults regardless of ml_enabled."""
        mgr = AdaptiveThresholdManager(default_entry=1.8, default_exit=0.4)
        entry, exit_ = mgr.get_thresholds("AAPL_MSFT")
        assert entry == 1.8
        assert exit_ == 0.4

    def test_validate_and_set_model_structured(self):
        """
        Integration: validate_and_set_model with structured data 
        Ôåô ML enabled, thresholds from model.
        """
        mgr = AdaptiveThresholdManager(default_entry=2.0, default_exit=0.5)
        X, y_entry, y_exit = _make_structured_data(n=300)
        
        optimizer = MLThresholdOptimizer()
        feature_engineer = ThresholdFeatureEngineer()
        
        result = mgr.validate_and_set_model(
            optimizer, feature_engineer,
            X, y_entry, y_exit,
            n_folds=5, max_degradation_pct=20.0,
        )
        
        assert result.ml_approved
        assert mgr.ml_enabled
        assert mgr._oos_rejection_reason == ""
        assert mgr.optimizer is optimizer
        assert mgr.feature_engineer is feature_engineer

    def test_validate_and_set_model_random(self):
        """
        Integration: validate_and_set_model with random noise data
        Ôåô ML disabled, get_thresholds returns fixed defaults.
        """
        mgr = AdaptiveThresholdManager(default_entry=2.0, default_exit=0.5)
        X, y_entry, y_exit = _make_random_data(n=300)
        
        optimizer = MLThresholdOptimizer()
        feature_engineer = ThresholdFeatureEngineer()
        
        result = mgr.validate_and_set_model(
            optimizer, feature_engineer,
            X, y_entry, y_exit,
            n_folds=5, max_degradation_pct=20.0,
        )
        
        assert not result.ml_approved
        assert not mgr.ml_enabled
        assert "ML thresholds disabled" in mgr._oos_rejection_reason
        
        # Verify fallback to defaults
        entry, exit_ = mgr.get_thresholds("ANY_PAIR")
        assert entry == 2.0
        assert exit_ == 0.5

    def test_cache_still_works_when_ml_disabled(self):
        """Cached thresholds are returned even when ML is disabled."""
        mgr = AdaptiveThresholdManager(default_entry=2.0, default_exit=0.5)
        mgr.thresholds_cache["AAPL_MSFT"] = (1.7, 0.3)
        mgr.ml_enabled = False
        
        entry, exit_ = mgr.get_thresholds("AAPL_MSFT")
        assert entry == 1.7
        assert exit_ == 0.3

    def test_re_enable_ml_after_better_data(self):
        """
        If ML was disabled, then validated with better data Ôåô re-enabled.
        """
        mgr = AdaptiveThresholdManager(default_entry=2.0, default_exit=0.5)
        
        # First: disable with noise
        X_noise, y_entry_noise, y_exit_noise = _make_random_data(n=300)
        optimizer = MLThresholdOptimizer()
        feature_engineer = ThresholdFeatureEngineer()
        
        mgr.validate_and_set_model(
            optimizer, feature_engineer,
            X_noise, y_entry_noise, y_exit_noise,
        )
        assert not mgr.ml_enabled
        
        # Second: re-validate with structured data Ôåô should re-enable
        X_good, y_entry_good, y_exit_good = _make_structured_data(n=300)
        result2 = mgr.validate_and_set_model(
            optimizer, feature_engineer,
            X_good, y_entry_good, y_exit_good,
        )
        assert result2.ml_approved
        assert mgr.ml_enabled
        assert mgr._oos_rejection_reason == ""


# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
# Custom model factory
# ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

class TestCustomModelFactory:
    """Tests for providing a custom model factory."""

    def test_linear_model_factory(self):
        """Using LinearRegression (less overfitting prone)."""
        from sklearn.linear_model import LinearRegression

        X, y_entry, y_exit = _make_structured_data(n=300)
        v = MLThresholdValidator(n_folds=5, max_degradation_pct=20.0)
        result = v.validate_oos_performance(
            X, y_entry, y_exit,
            model_factory=lambda: LinearRegression(),
        )
        # Linear model on linear data Ôåô should pass easily
        assert result.ml_approved
        assert result.entry_degradation_pct < 10.0
