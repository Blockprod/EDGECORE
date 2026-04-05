"""Tests for ML-based market impact prediction."""

import numpy as np
from pathlib import Path
import tempfile
from pathlib import Path
from typing import cast

import numpy as np

from common.types import ImpactFeatures
from execution.ml_impact import (
    MLImpactPredictor,
    NeuralNetworkModel,
)


class TestNeuralNetworkModel:
    """Test NeuralNetworkModel class."""

    def test_model_creation(self):
        """Test creating neural network model."""
        model = NeuralNetworkModel(
            input_size=8,
            hidden_size_1=64,
            hidden_size_2=32,
        )

        assert model.input_size == 8
        assert model.hidden_size_1 == 64
        assert model.hidden_size_2 == 32
        assert model.W1 is not None
        assert model.feature_mean is not None
        assert len(model.feature_mean) == 8

    def test_forward_pass(self):
        """Test forward pass through network."""
        model = NeuralNetworkModel(
            input_size=8,
            hidden_size_1=64,
            hidden_size_2=32,
        )

        X = np.random.randn(10, 8).astype(np.float32)
        predictions, _cache = model.forward(X)

        assert predictions.shape == (10, 1)
        assert all(p >= 0 and p <= 200 for p in predictions.flatten())  # Clipped

    def test_predict(self):
        """Test prediction."""
        model = NeuralNetworkModel(
            input_size=8,
            hidden_size_1=64,
            hidden_size_2=32,
        )

        X = np.array(
            [
                [0.001, 0.1, 0.0002, 3.0, 0.5, 0.3, 0.0, 0.5],  # Passive order
                [0.01, 0.2, 0.0005, 2.5, 0.2, 0.7, 1.0, 1.0],  # Aggressive order
            ],
            dtype=np.float32,
        )

        predictions = model.predict(X)

        assert predictions.shape == (2, 1)
        # Both predictions should be in valid range
        assert all(0 <= p <= 200 for p in predictions.flatten())


class TestMLImpactPredictor:
    """Test MLImpactPredictor class."""

    def test_predictor_creation(self):
        """Test creating predictor."""
        predictor = MLImpactPredictor()

        assert predictor.model is None
        assert predictor.fallback_impact_bps == 2.0
        assert not predictor.is_trained

    def test_predictor_with_model(self):
        """Test creating predictor with model."""
        model = NeuralNetworkModel(
            input_size=8,
            hidden_size_1=64,
            hidden_size_2=32,
        )

        predictor = MLImpactPredictor(model=model)

        assert predictor.model is not None

    def test_encode_features(self):
        """Test feature encoding."""
        predictor = MLImpactPredictor()

        features = {
            "order_size_pct": 0.001,
            "volatility_annual_pct": 15.0,
            "bid_ask_spread_bps": 2.0,
            "market_volume_24h": 1e9,
            "time_of_day_factor": 0.5,
            "day_of_week": 2,
            "recent_volatility_spike": False,
            "order_urgency": "normal",
        }

        encoded = predictor._encode_features(cast(ImpactFeatures, features))

        assert encoded.shape == (8,)
        assert all(isinstance(x, (float, np.floating)) for x in encoded)

    def test_encode_urgency(self):
        """Test urgency encoding."""
        predictor = MLImpactPredictor()

        passive = predictor._encode_urgency("passive")
        normal = predictor._encode_urgency("normal")
        aggressive = predictor._encode_urgency("aggressive")

        assert passive == 0.0
        assert normal == 0.5
        assert aggressive == 1.0

    def test_parametric_fallback(self):
        """Test parametric fallback model."""
        predictor = MLImpactPredictor(fallback_impact_bps=2.0)

        features = {
            "order_size_pct": 0.001,
            "volatility_annual_pct": 15.0,
            "bid_ask_spread_bps": 2.0,
            "market_volume_24h": 1e9,
            "time_of_day_factor": 0.5,
            "day_of_week": 2,
            "recent_volatility_spike": False,
            "order_urgency": "normal",
        }

        impact = predictor._parametric_fallback(cast(ImpactFeatures, features))

        assert impact > 0
        assert impact < 100.0

    def test_predict_fallback(self):
        """Test prediction with fallback model."""
        predictor = MLImpactPredictor(fallback_impact_bps=2.0)

        features = {
            "order_size_pct": 0.001,
            "volatility_annual_pct": 15.0,
            "bid_ask_spread_bps": 2.0,
            "market_volume_24h": 1e9,
            "time_of_day_factor": 0.5,
            "day_of_week": 2,
            "recent_volatility_spike": False,
            "order_urgency": "passive",
        }

        prediction = predictor.predict(features)  # type: ignore[arg-type]

        assert "predicted_impact_bps" in prediction
        assert "confidence_interval_lower" in prediction
        assert "confidence_interval_upper" in prediction
        assert prediction["predicted_impact_bps"] > 0

    def test_predict_with_model(self):
        """Test prediction with trained model."""
        # Create and train a simple model
        model = NeuralNetworkModel(
            input_size=8,
            hidden_size_1=64,
            hidden_size_2=32,
        )

        predictor = MLImpactPredictor(model=model)

        features = {
            "order_size_pct": 0.005,
            "volatility_annual_pct": 20.0,
            "bid_ask_spread_bps": 3.0,
            "market_volume_24h": 5e8,
            "time_of_day_factor": 0.7,
            "day_of_week": 4,
            "recent_volatility_spike": True,
            "order_urgency": "aggressive",
        }

        prediction = predictor.predict(features)  # type: ignore[arg-type]

        # Untrained model should still produce valid predictions
        assert 0 <= prediction["predicted_impact_bps"] <= 200


class TestModelTraining:
    """Test model training."""

    def test_train_on_data(self):
        """Test training the model."""
        predictor = MLImpactPredictor()

        # Generate synthetic training data
        num_samples = 100
        features_list = []
        impacts_list = []

        for _i in range(num_samples):
            features = {
                "order_size_pct": np.random.uniform(0.0001, 0.01),
                "volatility_annual_pct": np.random.uniform(5.0, 50.0),
                "bid_ask_spread_bps": np.random.uniform(0.5, 10.0),
                "market_volume_24h": np.random.uniform(1e8, 1e10),
                "time_of_day_factor": np.random.uniform(0.0, 1.0),
                "day_of_week": np.random.randint(0, 5),
                "recent_volatility_spike": np.random.choice([True, False]),
                "order_urgency": np.random.choice(["passive", "normal", "aggressive"]),
            }
            features_list.append(features)

            # Generate impact based on features
            base = features["order_size_pct"] * 1000
            vol_adj = features["volatility_annual_pct"] * 0.05
            impact = base + vol_adj + np.random.normal(0, 0.5)
            impacts_list.append(max(impact, 0.1))

        # Train
        metrics = predictor.train_on_data(cast(list[ImpactFeatures], features_list), impacts_list, epochs=5)

        assert "mae" in metrics
        assert "r_squared" in metrics
        assert predictor.is_trained

    def test_model_save_after_training(self):
        """Test saving model after training."""
        predictor = MLImpactPredictor()

        # Generate and train
        features_list = [
            {
                "order_size_pct": 0.001,
                "volatility_annual_pct": 15.0,
                "bid_ask_spread_bps": 2.0,
                "market_volume_24h": 1e9,
                "time_of_day_factor": 0.5,
                "day_of_week": 2,
                "recent_volatility_spike": False,
                "order_urgency": "normal",
            }
            for _ in range(50)
        ]
        impacts_list = [1.0 + np.random.normal(0, 0.1) for _ in range(50)]

        predictor.train_on_data(features_list, impacts_list)  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "trained_model.pkl"
            predictor.save_model(filepath)

            # Load and verify
            loaded_predictor = MLImpactPredictor.load_model(filepath)
            assert loaded_predictor.model is not None


class TestModelMetrics:
    """Test model metric reporting."""

    def test_get_model_metrics(self):
        """Test getting model metrics."""
        model = NeuralNetworkModel(
            input_size=8,
            hidden_size_1=64,
            hidden_size_2=32,
        )

        predictor = MLImpactPredictor(model=model)

        # Train first
        features_list = [
            {
                "order_size_pct": np.random.uniform(0.0001, 0.01),
                "volatility_annual_pct": np.random.uniform(5.0, 50.0),
                "bid_ask_spread_bps": np.random.uniform(0.5, 10.0),
                "market_volume_24h": np.random.uniform(1e8, 1e10),
                "time_of_day_factor": np.random.uniform(0.0, 1.0),
                "day_of_week": np.random.randint(0, 5),
                "recent_volatility_spike": np.random.choice([True, False]),
                "order_urgency": np.random.choice(["passive", "normal", "aggressive"]),
            }
            for _ in range(100)
        ]
        impacts_list = [1.0 + 0.5 * np.random.randn() for _ in range(100)]

        predictor.train_on_data(cast(list[ImpactFeatures], features_list), impacts_list)

        metrics = predictor.get_model_metrics()

        assert "model_version" in metrics
        assert "training_samples" in metrics
        assert "r_squared" in metrics
        assert "mean_absolute_error_bps" in metrics
        assert metrics["training_samples"] > 0


class TestPredictionQuality:
    """Test prediction quality and bounds."""

    def test_confidence_intervals(self):
        """Test that confidence intervals are reasonable."""
        predictor = MLImpactPredictor(fallback_impact_bps=2.0)

        features = {
            "order_size_pct": 0.001,
            "volatility_annual_pct": 15.0,
            "bid_ask_spread_bps": 2.0,
            "market_volume_24h": 1e9,
            "time_of_day_factor": 0.5,
            "day_of_week": 2,
            "recent_volatility_spike": False,
            "order_urgency": "normal",
        }

        prediction = predictor.predict(features)  # type: ignore[arg-type]

        # CI should be wider than point prediction
        mean = prediction["predicted_impact_bps"]
        ci_lower = prediction["confidence_interval_lower"]
        ci_upper = prediction["confidence_interval_upper"]

        assert ci_lower < mean < ci_upper
        assert ci_lower > 0
        assert ci_upper < 200  # Reasonable bounds

    def test_order_size_impact_correlation(self):
        """Test that larger orders have more impact."""
        predictor = MLImpactPredictor(fallback_impact_bps=2.0)

        small_features = {
            "order_size_pct": 0.0001,
            "volatility_annual_pct": 15.0,
            "bid_ask_spread_bps": 2.0,
            "market_volume_24h": 1e9,
            "time_of_day_factor": 0.5,
            "day_of_week": 2,
            "recent_volatility_spike": False,
            "order_urgency": "normal",
        }

        large_features = small_features.copy()
        large_features["order_size_pct"] = 0.01

        small_impact = predictor.predict(cast(ImpactFeatures, small_features))["predicted_impact_bps"]
        large_impact = predictor.predict(cast(ImpactFeatures, large_features))["predicted_impact_bps"]

        assert large_impact > small_impact

    def test_urgency_impact_correlation(self):
        """Test that aggressive orders have more impact."""
        predictor = MLImpactPredictor(fallback_impact_bps=2.0)

        base_features = {
            "order_size_pct": 0.001,
            "volatility_annual_pct": 15.0,
            "bid_ask_spread_bps": 2.0,
            "market_volume_24h": 1e9,
            "time_of_day_factor": 0.5,
            "day_of_week": 2,
            "recent_volatility_spike": False,
        }

        passive_features = base_features.copy()
        passive_features["order_urgency"] = "passive"

        aggressive_features = base_features.copy()
        aggressive_features["order_urgency"] = "aggressive"

        passive_impact = predictor.predict(cast(ImpactFeatures, passive_features))["predicted_impact_bps"]
        aggressive_impact = predictor.predict(cast(ImpactFeatures, aggressive_features))["predicted_impact_bps"]

        assert aggressive_impact > passive_impact
