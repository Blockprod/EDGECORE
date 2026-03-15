"""
Walk-forward OOS validation for ML threshold optimizer.

Sprint 2.5 (M-05) ÔÇô Prevents overfitting by validating ML thresholds
out-of-sample using temporal walk-forward cross-validation.

Key rules:
  - 5-fold temporal walk-forward (expanding window)
  - If OOS R┬▓ < 80% of IS R┬▓ Ôåô disable ML, use fixed thresholds
  - Explicit logging of validation results
  - Automatic fallback to heuristic thresholds
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import logging

from sklearn.metrics import r2_score, mean_squared_error

logger = logging.getLogger(__name__)


@dataclass
class ValidationFoldResult:
    """Result of a single walk-forward fold."""
    fold_index: int
    train_size: int
    test_size: int
    is_r2_entry: float       # In-sample R┬▓ for entry model
    oos_r2_entry: float      # Out-of-sample R┬▓ for entry model
    is_r2_exit: float        # In-sample R┬▓ for exit model
    oos_r2_exit: float       # Out-of-sample R┬▓ for exit model
    is_rmse_entry: float
    oos_rmse_entry: float
    is_rmse_exit: float
    oos_rmse_exit: float


@dataclass
class ValidationResult:
    """Aggregate result of walk-forward validation."""
    n_folds: int
    fold_results: List[ValidationFoldResult] = field(default_factory=list)
    
    # Aggregate metrics
    avg_is_r2_entry: float = 0.0
    avg_oos_r2_entry: float = 0.0
    avg_is_r2_exit: float = 0.0
    avg_oos_r2_exit: float = 0.0
    
    # Degradation ratios (OOS / IS)
    entry_degradation_pct: float = 0.0  # % drop from IS to OOS
    exit_degradation_pct: float = 0.0
    
    # Decision
    ml_approved: bool = False
    rejection_reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_folds": self.n_folds,
            "avg_is_r2_entry": round(self.avg_is_r2_entry, 4),
            "avg_oos_r2_entry": round(self.avg_oos_r2_entry, 4),
            "avg_is_r2_exit": round(self.avg_is_r2_exit, 4),
            "avg_oos_r2_exit": round(self.avg_oos_r2_exit, 4),
            "entry_degradation_pct": round(self.entry_degradation_pct, 1),
            "exit_degradation_pct": round(self.exit_degradation_pct, 1),
            "ml_approved": self.ml_approved,
            "rejection_reason": self.rejection_reason,
        }


class MLThresholdValidator:
    """
    Walk-forward cross-validation for ML threshold optimizer.
    
    Process:
      1. Split data into N temporal folds (expanding window)
      2. For each fold: train on [0:fold_end], test on [fold_end:next_fold_end]
      3. Measure R┬▓ in-sample vs out-of-sample
      4. If avg OOS R┬▓ < 80% of avg IS R┬▓ Ôåô disable ML
    
    This prevents the ML threshold optimizer from overfitting to
    in-sample data and producing worse-than-fixed thresholds in production.
    
    Usage::
    
        validator = MLThresholdValidator()
        result = validator.validate_oos_performance(X, y_entry, y_exit)
        if not result.ml_approved:
            # Fall back to fixed thresholds
            ...
    """

    def __init__(
        self,
        n_folds: int = 5,
        max_degradation_pct: float = 20.0,
        min_oos_r2: float = 0.0,
    ):
        """
        Args:
            n_folds: Number of temporal walk-forward folds (default 5)
            max_degradation_pct: Max allowed OOS degradation vs IS (default 20%)
            min_oos_r2: Minimum acceptable OOS R┬▓ (default 0.0 ÔÇô no floor)
        """
        self.n_folds = n_folds
        self.max_degradation_pct = max_degradation_pct
        self.min_oos_r2 = min_oos_r2
        
        self.last_result: Optional[ValidationResult] = None
        
        # Track IS/OOS scores for should_use_ml_thresholds()
        self.is_score: float = 0.0
        self.oos_score: float = 0.0

    def validate_oos_performance(
        self,
        X: pd.DataFrame,
        y_entry: pd.Series,
        y_exit: pd.Series,
        model_factory=None,
    ) -> ValidationResult:
        """
        Run walk-forward cross-validation on the ML threshold optimizer.
        
        Args:
            X: Feature matrix (rows ordered temporally)
            y_entry: Entry threshold targets
            y_exit: Exit threshold targets
            model_factory: Callable returning a fresh sklearn model.
                           Default: RandomForestRegressor with standard params.
        
        Returns:
            ValidationResult with fold-by-fold and aggregate metrics
        """
        from sklearn.ensemble import RandomForestRegressor
        
        if model_factory is None:
            def model_factory():
                return RandomForestRegressor(
                    n_estimators=100,
                    max_depth=8,
                    min_samples_split=5,
                    min_samples_leaf=2,
                    random_state=42,
                )
        
        n_samples = len(X)
        if n_samples < self.n_folds + 1:
            logger.warning(
                "ml_validator_insufficient_data",
                extra={"n_samples": n_samples, "n_folds": self.n_folds}
            )
            result = ValidationResult(
                n_folds=0,
                ml_approved=False,
                rejection_reason=f"Insufficient data: {n_samples} samples for {self.n_folds} folds",
            )
            self.last_result = result
            return result
        
        # Temporal fold boundaries (expanding window)
        fold_size = n_samples // (self.n_folds + 1)
        fold_results: List[ValidationFoldResult] = []
        
        for fold_idx in range(self.n_folds):
            train_end = fold_size * (fold_idx + 1)
            test_end = min(fold_size * (fold_idx + 2), n_samples)
            
            if train_end >= n_samples or test_end <= train_end:
                continue
            
            X_train = X.iloc[:train_end]
            X_test = X.iloc[train_end:test_end]
            y_entry_train = y_entry.iloc[:train_end]
            y_entry_test = y_entry.iloc[train_end:test_end]
            y_exit_train = y_exit.iloc[:train_end]
            y_exit_test = y_exit.iloc[train_end:test_end]
            
            if len(X_test) == 0:
                continue
            
            # Train entry model
            entry_model = model_factory()
            entry_model.fit(X_train, y_entry_train)
            
            is_entry_pred = entry_model.predict(X_train)
            oos_entry_pred = entry_model.predict(X_test)
            
            is_r2_entry = r2_score(y_entry_train, is_entry_pred)
            oos_r2_entry = r2_score(y_entry_test, oos_entry_pred) if len(y_entry_test) > 1 else 0.0
            is_rmse_entry = float(np.sqrt(mean_squared_error(y_entry_train, is_entry_pred)))
            oos_rmse_entry = float(np.sqrt(mean_squared_error(y_entry_test, oos_entry_pred)))
            
            # Train exit model
            exit_model = model_factory()
            exit_model.fit(X_train, y_exit_train)
            
            is_exit_pred = exit_model.predict(X_train)
            oos_exit_pred = exit_model.predict(X_test)
            
            is_r2_exit = r2_score(y_exit_train, is_exit_pred)
            oos_r2_exit = r2_score(y_exit_test, oos_exit_pred) if len(y_exit_test) > 1 else 0.0
            is_rmse_exit = float(np.sqrt(mean_squared_error(y_exit_train, is_exit_pred)))
            oos_rmse_exit = float(np.sqrt(mean_squared_error(y_exit_test, oos_exit_pred)))
            
            fold_result = ValidationFoldResult(
                fold_index=fold_idx,
                train_size=len(X_train),
                test_size=len(X_test),
                is_r2_entry=float(is_r2_entry),
                oos_r2_entry=float(oos_r2_entry),
                is_r2_exit=float(is_r2_exit),
                oos_r2_exit=float(oos_r2_exit),
                is_rmse_entry=is_rmse_entry,
                oos_rmse_entry=oos_rmse_entry,
                is_rmse_exit=is_rmse_exit,
                oos_rmse_exit=oos_rmse_exit,
            )
            fold_results.append(fold_result)
        
        if len(fold_results) == 0:
            result = ValidationResult(
                n_folds=0,
                ml_approved=False,
                rejection_reason="No valid folds produced",
            )
            self.last_result = result
            return result
        
        # Aggregate metrics
        avg_is_r2_entry = float(np.mean([f.is_r2_entry for f in fold_results]))
        avg_oos_r2_entry = float(np.mean([f.oos_r2_entry for f in fold_results]))
        avg_is_r2_exit = float(np.mean([f.is_r2_exit for f in fold_results]))
        avg_oos_r2_exit = float(np.mean([f.oos_r2_exit for f in fold_results]))
        
        # Calculate degradation
        entry_degradation = self._calc_degradation(avg_is_r2_entry, avg_oos_r2_entry)
        exit_degradation = self._calc_degradation(avg_is_r2_exit, avg_oos_r2_exit)
        
        # Store for should_use_ml_thresholds()
        self.is_score = (avg_is_r2_entry + avg_is_r2_exit) / 2
        self.oos_score = (avg_oos_r2_entry + avg_oos_r2_exit) / 2
        
        # Decision
        max_deg = max(entry_degradation, exit_degradation)
        ml_approved = True
        rejection_reason = ""
        
        if max_deg > self.max_degradation_pct:
            ml_approved = False
            rejection_reason = (
                f"ML thresholds disabled: OOS degradation {max_deg:.0f}% "
                f"(entry: {entry_degradation:.0f}%, exit: {exit_degradation:.0f}%, "
                f"max allowed: {self.max_degradation_pct:.0f}%)"
            )
            logger.warning(rejection_reason)
        
        if avg_oos_r2_entry < self.min_oos_r2 or avg_oos_r2_exit < self.min_oos_r2:
            ml_approved = False
            rejection_reason = (
                f"ML thresholds disabled: OOS R┬▓ too low "
                f"(entry: {avg_oos_r2_entry:.3f}, exit: {avg_oos_r2_exit:.3f}, "
                f"min required: {self.min_oos_r2:.3f})"
            )
            logger.warning(rejection_reason)
        
        if ml_approved:
            logger.info(
                "ML thresholds approved: OOS performance acceptable "
                f"(entry degradation: {entry_degradation:.0f}%, "
                f"exit degradation: {exit_degradation:.0f}%)"
            )
        
        result = ValidationResult(
            n_folds=len(fold_results),
            fold_results=fold_results,
            avg_is_r2_entry=avg_is_r2_entry,
            avg_oos_r2_entry=avg_oos_r2_entry,
            avg_is_r2_exit=avg_is_r2_exit,
            avg_oos_r2_exit=avg_oos_r2_exit,
            entry_degradation_pct=entry_degradation,
            exit_degradation_pct=exit_degradation,
            ml_approved=ml_approved,
            rejection_reason=rejection_reason,
        )
        
        self.last_result = result
        return result

    def should_use_ml_thresholds(self) -> bool:
        """
        Whether ML thresholds should be used.
        
        Returns True if OOS score >= 80% of IS score.
        Anti-overfitting guard.
        """
        if self.is_score <= 0:
            return False
        return self.oos_score >= 0.8 * self.is_score

    @staticmethod
    def _calc_degradation(is_score: float, oos_score: float) -> float:
        """Calculate degradation percentage from IS to OOS.
        
        Returns 0 if IS score is <= 0 (can't compute meaningful ratio).
        """
        if is_score <= 0:
            return 100.0 if oos_score < is_score else 0.0
        degradation = (1 - oos_score / is_score) * 100
        return max(0.0, degradation)
