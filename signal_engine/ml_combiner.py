"""
Phase 4.4 ÔÇö ML Signal Combiner (Walk-Forward).

Replaces equal-weight ``SignalCombiner`` with a learned model that
optimally combines all signal sources to predict trade outcome.

Model: GradientBoostingClassifier (sklearn) with optional LightGBM.
Training: Walk-forward (train on 504 bars Ôëê 2y, test on 126 bars Ôëê 6m, roll).
Anti-overfitting:
  - Purified cross-validation (gap between train/test).
  - Feature importance monitoring.
  - Minimum sample threshold for training.
  - Prediction clipping to avoid extreme bets.

The ML combiner is designed as a **drop-in replacement** for the
equal-weight combiner.  It exposes the same ``combine()`` interface
but uses learned weights instead of fixed ones.

Fallback: if insufficient training data, falls back to equal-weight.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from structlog import get_logger

logger = get_logger(__name__)

# Try LightGBM first, fall back to sklearn
try:
    from lightgbm import LGBMClassifier as _TreeModel  # pyright: ignore[reportMissingImports]

    _ML_BACKEND = "lightgbm"
except ImportError:
    from sklearn.ensemble import GradientBoostingClassifier as _TreeModel

    _ML_BACKEND = "sklearn"


@dataclass
class MLPrediction:
    """Output of the ML signal combiner."""

    composite_score: float  # Predicted score [-1, 1]
    direction: str  # "long" | "short" | "exit" | "none"
    confidence: float  # Model confidence [0, 1]
    feature_importance: dict[str, float] = field(default_factory=dict)
    source_scores: dict[str, float] = field(default_factory=dict)
    source_weights: dict[str, float] = field(default_factory=dict)
    model_trained: bool = False  # Whether a trained model was used


@dataclass
class _TrainingBar:
    """One row of training data collected during backtest."""

    bar_idx: int
    features: dict[str, float]
    label: float  # future return label (+1 win, -1 loss, 0 flat)


class MLSignalCombiner:
    """
    Machine-learning signal combiner for pair trading.

    Collects feature vectors (signal scores) and outcome labels during
    the backtest, then periodically retrains a walk-forward model.

    Feature set (all in [-1, 1]):
        zscore, momentum, ou, vol_regime, cross_sectional,
        intraday_mr, earnings, options_flow, sentiment

    Usage::

        ml = MLSignalCombiner()
        # During backtest:
        ml.record_trade(bar_idx, features, outcome)
        pred = ml.predict(features)  # returns MLPrediction

    The combiner auto-retrains every ``retrain_interval`` bars when
    enough labelled samples have accumulated.
    """

    FEATURE_NAMES = [
        "zscore",
        "momentum",
        "ou",
        "vol_regime",
        "cross_sectional",
        "intraday_mr",
        "earnings",
        "options_flow",
        "sentiment",
    ]

    def __init__(
        self,
        train_window: int = 504,
        test_window: int = 126,
        purge_gap: int = 10,
        min_samples: int = 30,
        retrain_interval: int = 63,
        entry_threshold: float = 0.35,
        exit_threshold: float = 0.15,
        enabled: bool = True,
    ):
        """
        Args:
            train_window: Training window in bars (~2 years).
            test_window: Out-of-sample test window (~6 months).
            purge_gap: Gap between train and test to avoid leakage.
            min_samples: Minimum labelled trades before first training.
            retrain_interval: Bars between model retraining.
            entry_threshold: Threshold for entry signals.
            exit_threshold: Threshold for exit signals.
            enabled: Master switch. When False, falls back to equal-weight.
        """
        self.train_window = train_window
        self.test_window = test_window
        self.purge_gap = purge_gap
        self.min_samples = min_samples
        self.retrain_interval = retrain_interval
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.enabled = enabled

        self._model: Any | None = None
        self._training_data: list[_TrainingBar] = []
        self._last_train_bar: int = -999
        self._feature_importance: dict[str, float] = {}
        self._n_trainings: int = 0

        # C-09: PSI drift monitor
        from monitoring.ml_drift import MLFeatureDriftMonitor

        self._drift_monitor = MLFeatureDriftMonitor(
            feature_names=self.FEATURE_NAMES,
            check_interval_bars=252,
        )

        # Equal-weight fallback weights
        self._fallback_weights = {name: 1.0 for name in self.FEATURE_NAMES}

    def record_trade(
        self,
        bar_idx: int,
        features: dict[str, float],
        outcome: float,
    ) -> None:
        """Record a completed trade for training.

        Args:
            bar_idx: Bar index when trade was entered.
            features: Signal scores at entry time.
            outcome: Trade P&L as fraction (positive = win).
        """
        # Classify: win (+1), loss (-1)
        label = 1.0 if outcome > 0 else -1.0

        self._training_data.append(
            _TrainingBar(
                bar_idx=bar_idx,
                features={k: features.get(k, 0.0) for k in self.FEATURE_NAMES},
                label=label,
            )
        )

    def _should_retrain(self, current_bar: int) -> bool:
        """Check if model should be retrained."""
        if not self.enabled:
            return False
        if len(self._training_data) < self.min_samples:
            return False
        if current_bar - self._last_train_bar < self.retrain_interval:
            return False
        return True

    def _retrain(self, current_bar: int) -> bool:
        """Retrain the model using walk-forward methodology.

        Uses only data up to ``current_bar - purge_gap`` to avoid leakage.

        Returns:
            True if training succeeded, False otherwise.
        """
        # Filter training data: only use bars before purge boundary
        purge_boundary = current_bar - self.purge_gap
        valid_data = [d for d in self._training_data if d.bar_idx < purge_boundary]

        if len(valid_data) < self.min_samples:
            return False

        # Use most recent train_window samples
        if len(valid_data) > self.train_window:
            valid_data = valid_data[-self.train_window :]

        # Build feature matrix
        X = np.array([[d.features.get(f, 0.0) for f in self.FEATURE_NAMES] for d in valid_data])
        y = np.array([d.label for d in valid_data])

        # Check class balance
        n_pos = (y > 0).sum()
        n_neg = (y < 0).sum()
        if n_pos < 3 or n_neg < 3:
            logger.debug(
                "ml_combiner_skip_train",
                reason="insufficient class balance",
                n_pos=n_pos,
                n_neg=n_neg,
            )
            return False

        try:
            if _ML_BACKEND == "lightgbm":
                _lgbm_kwargs: dict[str, Any] = {
                    "n_estimators": 100,
                    "max_depth": 3,
                    "learning_rate": 0.05,
                    "min_child_samples": max(5, len(valid_data) // 10),
                    "subsample": 0.8,
                    "colsample_bytree": 0.8,
                    "reg_alpha": 0.1,
                    "reg_lambda": 1.0,
                    "verbose": -1,
                    "random_state": 42,
                }
                model: Any = _TreeModel(**_lgbm_kwargs)
            else:
                model = _TreeModel(
                    n_estimators=100,
                    max_depth=3,
                    learning_rate=0.05,
                    min_samples_leaf=max(5, len(valid_data) // 10),
                    subsample=0.8,
                    random_state=42,
                )

            model.fit(X, y)
            self._model = model
            self._last_train_bar = current_bar
            self._n_trainings += 1

            # Extract feature importance
            importances = model.feature_importances_
            self._feature_importance = {
                name: float(imp) for name, imp in zip(self.FEATURE_NAMES, importances, strict=False)
            }

            # C-09: Store training distribution statistics for drift monitoring
            X_by_feature = {name: X[:, i].tolist() for i, name in enumerate(self.FEATURE_NAMES)}
            train_stats = {
                name: {
                    "mean": float(np.mean(vals)),
                    "std": float(np.std(vals)),
                    "samples": vals,
                }
                for name, vals in X_by_feature.items()
            }
            self._drift_monitor.set_reference(train_stats)

            logger.info(
                "ml_combiner_trained",
                n_samples=len(valid_data),
                n_trainings=self._n_trainings,
                backend=_ML_BACKEND,
                top_features=sorted(
                    self._feature_importance.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:3],
            )
            return True

        except Exception as e:
            logger.warning("ml_combiner_train_failed", error=str(e))
            return False

    def predict(
        self,
        features: dict[str, float],
        current_bar: int = 0,
        in_position: bool = False,
    ) -> MLPrediction:
        """Predict trade direction using the ML model.

        If no trained model is available, falls back to equal-weight
        averaging of all feature scores.

        Args:
            features: Signal scores {name: score}.
            current_bar: Current bar index (for auto-retrain check).
            in_position: Whether currently in a position (for exit logic).

        Returns:
            MLPrediction with score, direction, and metadata.
        """
        # Auto-retrain check
        if self._should_retrain(current_bar):
            self._retrain(current_bar)

        source_scores = {k: features.get(k, 0.0) for k in self.FEATURE_NAMES}

        if self._model is not None and self.enabled:
            return self._predict_ml(source_scores, in_position)
        else:
            return self._predict_fallback(source_scores, in_position)

    def _predict_ml(
        self,
        scores: dict[str, float],
        in_position: bool,
    ) -> MLPrediction:
        """Use the trained ML model for prediction."""
        X = np.array([[scores.get(f, 0.0) for f in self.FEATURE_NAMES]])

        try:
            # Get probability of positive class
            _model = self._model
            assert _model is not None
            _model_typed: Any = _model
            proba = _model_typed.predict_proba(X)[0]
            # proba[1] = P(win), proba[0] = P(loss)
            # Map to [-1, 1]: 2 * P(win) - 1
            if len(proba) >= 2:
                raw_score = 2.0 * proba[1] - 1.0
            else:
                raw_score = 0.0

            # Clip to prevent extreme predictions
            composite = float(np.clip(raw_score, -1.0, 1.0))
            confidence = float(max(proba))

        except Exception:
            # Fallback if predict_proba fails
            return self._predict_fallback(scores, in_position)

        # Determine direction
        direction = self._resolve_direction(composite, in_position)

        return MLPrediction(
            composite_score=composite,
            direction=direction,
            confidence=confidence,
            feature_importance=dict(self._feature_importance),
            source_scores=scores,
            source_weights=self._feature_importance,
            model_trained=True,
        )

    def _predict_fallback(
        self,
        scores: dict[str, float],
        in_position: bool,
    ) -> MLPrediction:
        """Equal-weight fallback when no model is trained."""
        active_scores = {k: v for k, v in scores.items() if abs(v) > 1e-10}

        if active_scores:
            composite = sum(active_scores.values()) / len(active_scores)
            composite = float(np.clip(composite, -1.0, 1.0))
            confidence = len(active_scores) / len(self.FEATURE_NAMES)
        else:
            composite = 0.0
            confidence = 0.0

        direction = self._resolve_direction(composite, in_position)

        return MLPrediction(
            composite_score=composite,
            direction=direction,
            confidence=confidence,
            source_scores=scores,
            source_weights=self._fallback_weights,
            model_trained=False,
        )

    def _resolve_direction(self, score: float, in_position: bool) -> str:
        """Map composite score to direction string."""
        if score > self.entry_threshold:
            return "long"
        elif score < -self.entry_threshold:
            return "short"
        elif in_position and abs(score) < self.exit_threshold:
            return "exit"
        return "none"

    # --- Combine interface (compatible with SignalCombiner) ---

    def combine(
        self,
        scores: dict[str, float],
        in_position: bool = False,
        current_bar: int = 0,
    ) -> MLPrediction:
        """Drop-in replacement for ``SignalCombiner.combine()``.

        Returns an MLPrediction that has the same key attributes as
        ``CompositeSignal`` (composite_score, direction, confidence,
        source_scores).
        """
        # C-09: Record live features for drift monitoring
        self._drift_monitor.record(scores)
        return self.predict(scores, current_bar=current_bar, in_position=in_position)

    def check_drift(self, current_bar: int):
        """Run PSI drift check. Returns FeatureDriftReport or None if interval not elapsed."""
        return self._drift_monitor.maybe_check(current_bar)

    @property
    def feature_importance(self) -> dict[str, float]:
        """Return current feature importance (empty if untrained)."""
        return dict(self._feature_importance)

    @property
    def n_trainings(self) -> int:
        """Number of times the model has been retrained."""
        return self._n_trainings

    @property
    def backend(self) -> str:
        """ML backend in use ('lightgbm' or 'sklearn')."""
        return _ML_BACKEND

    def save(self, path: str | Path) -> None:
        """Persist the trained model and metadata to disk via joblib.

        Creates parent directories as needed.  No-op if no model has been
        trained yet (avoids writing an empty file).

        Args:
            path: Destination file path (e.g. ``data/models/ml_combiner_AAPL_MSFT.joblib``).
        """
        if self._model is None:
            logger.debug("ml_combiner_save_skipped", reason="no_trained_model", path=str(path))
            return

        try:
            import joblib  # lazy import — only needed when persisting

            dest = Path(path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "model": self._model,
                "feature_importance": self._feature_importance,
                "last_train_bar": self._last_train_bar,
                "n_trainings": self._n_trainings,
            }
            joblib.dump(payload, dest)
            logger.info("ml_combiner_saved", path=str(dest), n_trainings=self._n_trainings)
        except Exception as exc:
            logger.warning("ml_combiner_save_failed", path=str(path), error=str(exc))

    def load(self, path: str | Path) -> bool:
        """Restore a previously persisted model from disk.

        Args:
            path: Source file path.

        Returns:
            ``True`` if loading succeeded, ``False`` if file absent or invalid.
        """
        dest = Path(path)
        if not dest.exists():
            logger.debug("ml_combiner_load_skipped", reason="file_not_found", path=str(dest))
            return False

        try:
            import joblib  # lazy import

            payload = joblib.load(dest)
            self._model = payload["model"]
            self._feature_importance = payload.get("feature_importance", {})
            self._last_train_bar = payload.get("last_train_bar", -999)
            self._n_trainings = payload.get("n_trainings", 0)
            logger.info("ml_combiner_loaded", path=str(dest), n_trainings=self._n_trainings)
            return True
        except Exception as exc:
            logger.warning("ml_combiner_load_failed", path=str(dest), error=str(exc))
            return False

    def reset(self) -> None:
        """Clear model and training data."""
        self._model = None
        self._training_data.clear()
        self._last_train_bar = -999
        self._feature_importance.clear()
        self._n_trainings = 0
