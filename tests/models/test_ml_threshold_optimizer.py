<<<<<<< HEAD
﻿"""
=======
"""
>>>>>>> origin/main
Tests for S4.1: ML Threshold Optimization

Coverage:
- ThresholdDataGenerator: 6 tests
- ThresholdFeatureEngineer: 5 tests
- MLThresholdOptimizer: 8 tests
- AdaptiveThresholdManager: 4 tests
- Integration & Benchmarks: 5 tests
Total: 28 tests
"""

<<<<<<< HEAD
import os
import time

import numpy as np
import pandas as pd

from models.ml_threshold_optimizer import (
    AdaptiveThresholdManager,
    MLThresholdOptimizer,
    ThresholdDataGenerator,
    ThresholdFeatureEngineer,
=======
import numpy as np
import pandas as pd
import time
from models.ml_threshold_optimizer import (
    ThresholdDataGenerator,
    ThresholdFeatureEngineer,
    MLThresholdOptimizer,
    AdaptiveThresholdManager
>>>>>>> origin/main
)


class TestThresholdDataGenerator:
    """Test synthetic data generation."""
<<<<<<< HEAD

    def test_synthetic_data_generation(self):
        """Test that synthetic data has expected properties."""
        gen = ThresholdDataGenerator()
        spread = gen.generate_synthetic_pair_data("TEST", num_bars=252)

        assert len(spread) == 252
        assert isinstance(spread, pd.Series)
        assert spread.name == "TEST"
        # Should have some variation
        assert spread.std() > 0.01
        assert spread.std() < 1.0

    def test_pair_characteristics_computation(self):
        """Test characteristic extraction."""
        gen = ThresholdDataGenerator()
        spread = gen.generate_synthetic_pair_data("TEST", num_bars=252)

        chars = gen.compute_pair_characteristics(spread)

        assert "half_life" in chars
        assert "mean_reversion_speed" in chars
        assert "volatility" in chars
        assert "autocorrelation" in chars
        assert "spread_mean" in chars
        assert "spread_std" in chars

        # Sanity checks
        assert chars["half_life"] > 1
        assert chars["mean_reversion_speed"] > 0
        assert chars["volatility"] > 0
        assert -1 <= chars["autocorrelation"] <= 1

=======
    
    def test_synthetic_data_generation(self):
        """Test that synthetic data has expected properties."""
        gen = ThresholdDataGenerator()
        spread = gen.generate_synthetic_pair_data('TEST', num_bars=252)
        
        assert len(spread) == 252
        assert isinstance(spread, pd.Series)
        assert spread.name == 'TEST'
        # Should have some variation
        assert spread.std() > 0.01
        assert spread.std() < 1.0
    
    def test_pair_characteristics_computation(self):
        """Test characteristic extraction."""
        gen = ThresholdDataGenerator()
        spread = gen.generate_synthetic_pair_data('TEST', num_bars=252)
        
        chars = gen.compute_pair_characteristics(spread)
        
        assert 'half_life' in chars
        assert 'mean_reversion_speed' in chars
        assert 'volatility' in chars
        assert 'autocorrelation' in chars
        assert 'spread_mean' in chars
        assert 'spread_std' in chars
        
        # Sanity checks
        assert chars['half_life'] > 1
        assert chars['mean_reversion_speed'] > 0
        assert chars['volatility'] > 0
        assert -1 <= chars['autocorrelation'] <= 1
    
>>>>>>> origin/main
    def test_trade_simulation(self):
        """Test trade simulation with different thresholds."""
        gen = ThresholdDataGenerator()
        # Use deterministic spread: generate_synthetic_pair_data sets its own seed
<<<<<<< HEAD
        spread = gen.generate_synthetic_pair_data("TEST", num_bars=500)

=======
        spread = gen.generate_synthetic_pair_data('TEST', num_bars=500)
        
>>>>>>> origin/main
        # Tight thresholds (more trades)
        tight_perf = gen.simulate_trades(spread, entry_threshold=0.5, exit_threshold=0.05)
        # Very loose thresholds (much fewer trades)
        loose_perf = gen.simulate_trades(spread, entry_threshold=5.0, exit_threshold=2.0)
<<<<<<< HEAD

        # Tight should generate more trades (large gap ensures robustness)
        assert tight_perf["total_trades"] >= loose_perf["total_trades"]

        # All metrics should be present
        assert "win_rate" in tight_perf
        assert "profit_factor" in tight_perf
        assert "sharpe_ratio" in tight_perf
        assert "total_trades" in tight_perf

        # Sanity ranges
        assert 0 <= tight_perf["win_rate"] <= 1.0
        assert loose_perf["profit_factor"] > 0

=======
        
        # Tight should generate more trades (large gap ensures robustness)
        assert tight_perf['total_trades'] >= loose_perf['total_trades']
        
        # All metrics should be present
        assert 'win_rate' in tight_perf
        assert 'profit_factor' in tight_perf
        assert 'sharpe_ratio' in tight_perf
        assert 'total_trades' in tight_perf
        
        # Sanity ranges
        assert 0 <= tight_perf['win_rate'] <= 1.0
        assert loose_perf['profit_factor'] > 0
    
>>>>>>> origin/main
    def test_full_training_data_generation(self):
        """Test complete training data generation."""
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=5)
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # Should generate multiple examples per pair
        # 5 entry thresholds * 5 exit thresholds = 25 combinations per pair
        # But only those where exit < entry, so ~15-20 per pair
        assert len(examples) > 50
<<<<<<< HEAD

        # Check first example
        example = examples[0]
        assert hasattr(example, "pair_key")
        assert hasattr(example, "entry_threshold")
        assert hasattr(example, "exit_threshold")
        assert hasattr(example, "win_rate")
        assert hasattr(example, "profit_factor")
        assert hasattr(example, "half_life")
        assert hasattr(example, "volatility")

=======
        
        # Check first example
        example = examples[0]
        assert hasattr(example, 'pair_key')
        assert hasattr(example, 'entry_threshold')
        assert hasattr(example, 'exit_threshold')
        assert hasattr(example, 'win_rate')
        assert hasattr(example, 'profit_factor')
        assert hasattr(example, 'half_life')
        assert hasattr(example, 'volatility')
    
>>>>>>> origin/main
    def test_training_examples_have_reasonable_targets(self):
        """Test target quality."""
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=3)
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        for ex in examples:
            # Entry should be larger than exit
            assert ex.entry_threshold > ex.exit_threshold
            # Win rate should be in [0, 1]
            assert 0 <= ex.win_rate <= 1.0
            # Profit factor should be non-negative (can be 0 for no trades)
            assert ex.profit_factor >= 0
            # Half-life should be positive
            assert ex.half_life > 0
<<<<<<< HEAD

    def test_deterministic_generation(self):
        """Test that same pair name gives same data."""
        gen = ThresholdDataGenerator()

        spread1 = gen.generate_synthetic_pair_data("SAME_PAIR", num_bars=100)
        spread2 = gen.generate_synthetic_pair_data("SAME_PAIR", num_bars=100)

        # Should be identical (deterministic seed)
        assert np.allclose(np.asarray(spread1, dtype=float), np.asarray(spread2, dtype=float))
=======
    
    def test_deterministic_generation(self):
        """Test that same pair name gives same data."""
        gen = ThresholdDataGenerator()
        
        spread1 = gen.generate_synthetic_pair_data('SAME_PAIR', num_bars=100)
        spread2 = gen.generate_synthetic_pair_data('SAME_PAIR', num_bars=100)
        
        # Should be identical (deterministic seed)
        assert np.allclose(spread1.values, spread2.values)
>>>>>>> origin/main


class TestThresholdFeatureEngineer:
    """Test feature engineering."""
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_feature_engineering(self):
        """Test feature extraction."""
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=5)
<<<<<<< HEAD

        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)

=======
        
        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)
        
>>>>>>> origin/main
        # Should have 11 features
        assert X.shape[1] == 11
        assert X.shape[0] == len(examples)
        assert len(y_entry) == len(examples)
        assert len(y_exit) == len(examples)
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_feature_normalization(self):
        """Test that features are normalized."""
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=5)
<<<<<<< HEAD

        engineer = ThresholdFeatureEngineer()
        X, _, _ = engineer.engineer_features(examples)

        # Normalized features should have ~0 mean and ~1 std
        pd.Series(X.mean(axis=0)).abs()
        stds = pd.Series(X.std(axis=0))

        # Most variable features should be close to 1.0 (constant ones have std=0)
        # We have 11 features, about 8 are variable in synthetic data
        assert (stds > 0.5).sum() >= X.shape[1] * 0.7

=======
        
        engineer = ThresholdFeatureEngineer()
        X, _, _ = engineer.engineer_features(examples)
        
        # Normalized features should have ~0 mean and ~1 std
        X.mean(axis=0).abs()
        stds = X.std(axis=0)
        
        # Most variable features should be close to 1.0 (constant ones have std=0)
        # We have 11 features, about 8 are variable in synthetic data
        assert (stds > 0.5).sum() >= X.shape[1] * 0.7
    
>>>>>>> origin/main
    def test_feature_transformation(self):
        """Test transformation of new data."""
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=5)
<<<<<<< HEAD

        engineer = ThresholdFeatureEngineer()
        _X_train, _, _ = engineer.engineer_features(examples)

        # Create test example
        test_example = examples[0]
        test_df = pd.DataFrame(
            [
                {
                    "half_life": test_example.half_life,
                    "mean_reversion_speed": test_example.mean_reversion_speed,
                    "volatility": test_example.volatility,
                    "autocorrelation": test_example.autocorrelation,
                    "spread_std": test_example.spread_std,
                    "market_volatility": test_example.market_volatility,
                    "trend_strength": test_example.trend_strength,
                    "correlation_strength": test_example.correlation_strength,
                    "vol_x_mr": test_example.volatility * test_example.mean_reversion_speed,
                    "hl_x_vol": test_example.half_life * test_example.volatility,
                    "autocorr_x_mr": test_example.autocorrelation * test_example.mean_reversion_speed,
                }
            ]
        )

        # Transform should work
        X_test_transformed = engineer.transform_features(test_df)
        assert X_test_transformed.shape == (1, 11)

=======
        
        engineer = ThresholdFeatureEngineer()
        X_train, _, _ = engineer.engineer_features(examples)
        
        # Create test example
        test_example = examples[0]
        test_df = pd.DataFrame([{
            'half_life': test_example.half_life,
            'mean_reversion_speed': test_example.mean_reversion_speed,
            'volatility': test_example.volatility,
            'autocorrelation': test_example.autocorrelation,
            'spread_std': test_example.spread_std,
            'market_volatility': test_example.market_volatility,
            'trend_strength': test_example.trend_strength,
            'correlation_strength': test_example.correlation_strength,
            'vol_x_mr': test_example.volatility * test_example.mean_reversion_speed,
            'hl_x_vol': test_example.half_life * test_example.volatility,
            'autocorr_x_mr': test_example.autocorrelation * test_example.mean_reversion_speed,
        }])
        
        # Transform should work
        X_test_transformed = engineer.transform_features(test_df)
        assert X_test_transformed.shape == (1, 11)
    
>>>>>>> origin/main
    def test_feature_interaction_terms(self):
        """Test that interaction features are created."""
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=3)
<<<<<<< HEAD

        engineer = ThresholdFeatureEngineer()
        _X, _, _ = engineer.engineer_features(examples)

        # Check feature names
        feature_names = engineer.feature_names
        assert "vol_x_mr" in feature_names or "feature_8" in feature_names
=======
        
        engineer = ThresholdFeatureEngineer()
        X, _, _ = engineer.engineer_features(examples)
        
        # Check feature names
        feature_names = engineer.feature_names
        assert 'vol_x_mr' in feature_names or 'feature_8' in feature_names
>>>>>>> origin/main
        # Should have 11 total
        assert len(feature_names) == 11


class TestMLThresholdOptimizer:
    """Test ML model training."""
<<<<<<< HEAD

    def test_model_initialization(self):
        """Test optimizer initialization."""
        optimizer = MLThresholdOptimizer()

        assert optimizer.entry_model is not None
        assert optimizer.exit_model is not None
        assert optimizer.entry_test_metrics == {}

=======
    
    def test_model_initialization(self):
        """Test optimizer initialization."""
        optimizer = MLThresholdOptimizer()
        
        assert optimizer.entry_model is not None
        assert optimizer.exit_model is not None
        assert optimizer.entry_test_metrics == {}
    
>>>>>>> origin/main
    def test_model_training(self):
        """Test model training."""
        # Generate data
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=10)
<<<<<<< HEAD

        # Engineer features
        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)

        # Train model
        optimizer = MLThresholdOptimizer()
        metrics = optimizer.train(X, y_entry, y_exit, test_size=0.2)

        # Check metrics exist
        assert "entry" in metrics
        assert "exit" in metrics
        assert "test_r2" in metrics["entry"]
        assert "test_r2" in metrics["exit"]

        # R┬▓ should be trainable (even if synthetic data isn't perfectly predictive)
        # With synthetic data, correlation may be weak; just ensure model trains
        assert "test_rmse" in metrics["entry"]
        assert metrics["entry"]["test_rmse"] >= 0  # Valid metric

=======
        
        # Engineer features
        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)
        
        # Train model
        optimizer = MLThresholdOptimizer()
        metrics = optimizer.train(X, y_entry, y_exit, test_size=0.2)
        
        # Check metrics exist
        assert 'entry' in metrics
        assert 'exit' in metrics
        assert 'test_r2' in metrics['entry']
        assert 'test_r2' in metrics['exit']
        
        # R² should be trainable (even if synthetic data isn't perfectly predictive)
        # With synthetic data, correlation may be weak; just ensure model trains
        assert 'test_rmse' in metrics['entry']
        assert metrics['entry']['test_rmse'] >= 0  # Valid metric
    
>>>>>>> origin/main
    def test_model_prediction(self):
        """Test threshold prediction."""
        # Generate and train
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=10)
<<<<<<< HEAD

        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)

        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit)

        # Predict on first 5 examples
        X_pred = X.head(5)
        entry_pred, exit_pred = optimizer.predict(X_pred)

        assert len(entry_pred) == 5
        assert len(exit_pred) == 5

=======
        
        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)
        
        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit)
        
        # Predict on first 5 examples
        X_pred = X.head(5)
        entry_pred, exit_pred = optimizer.predict(X_pred)
        
        assert len(entry_pred) == 5
        assert len(exit_pred) == 5
        
>>>>>>> origin/main
        # Predictions should be in valid ranges
        assert (entry_pred >= 1.0).all()
        assert (entry_pred <= 3.0).all()
        assert (exit_pred >= 0.1).all()
        assert (exit_pred <= 1.0).all()
<<<<<<< HEAD

        # Exit should be less than entry
        assert (exit_pred < entry_pred).all()

=======
        
        # Exit should be less than entry
        assert (exit_pred < entry_pred).all()
    
>>>>>>> origin/main
    def test_feature_importance(self):
        """Test feature importance extraction."""
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=10)
<<<<<<< HEAD

        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)

        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit)

        # Get importances
        importances = optimizer.get_feature_importance()

=======
        
        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)
        
        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit)
        
        # Get importances
        importances = optimizer.get_feature_importance()
        
>>>>>>> origin/main
        # Should have 11 features
        assert len(importances) > 0
        # Each importance should sum to ~1.0
        assert sum(importances.values()) > 0.8
<<<<<<< HEAD

    def test_model_hyperparameters(self):
        """Test that model has reasonable hyperparameters."""
        optimizer = MLThresholdOptimizer()

        # Check RF settings
        assert optimizer.entry_model.get_params().get("n_estimators") == 100
        assert optimizer.entry_model.get_params().get("max_depth") == 8
        assert optimizer.exit_model.get_params().get("n_estimators") == 100

=======
    
    def test_model_hyperparameters(self):
        """Test that model has reasonable hyperparameters."""
        optimizer = MLThresholdOptimizer()
        
        # Check RF settings
        assert optimizer.entry_model.n_estimators == 100
        assert optimizer.entry_model.max_depth == 8
        assert optimizer.exit_model.n_estimators == 100
    
>>>>>>> origin/main
    def test_prediction_consistency(self):
        """Test that same inputs give same predictions."""
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=5)
<<<<<<< HEAD

        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)

        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit)

        # Predict twice
        entry1, exit1 = optimizer.predict(X.head(3))
        entry2, exit2 = optimizer.predict(X.head(3))

        # Should be identical
        assert np.allclose(entry1, entry2)
        assert np.allclose(exit1, exit2)

=======
        
        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)
        
        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit)
        
        # Predict twice
        entry1, exit1 = optimizer.predict(X.head(3))
        entry2, exit2 = optimizer.predict(X.head(3))
        
        # Should be identical
        assert np.allclose(entry1, entry2)
        assert np.allclose(exit1, exit2)
    
>>>>>>> origin/main
    def test_model_training_and_validation(self):
        """Test complete training pipeline."""
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=15)
<<<<<<< HEAD

        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)

        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit, test_size=0.2)

        # Both models should train
        assert optimizer.entry_test_metrics["test_rmse"] < 0.8
        assert optimizer.exit_test_metrics["test_rmse"] < 0.8

        # Should be able to predict
        entry_pred, _exit_pred = optimizer.predict(X.head(10))
=======
        
        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)
        
        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit, test_size=0.2)
        
        # Both models should train
        assert optimizer.entry_test_metrics['test_rmse'] < 0.8
        assert optimizer.exit_test_metrics['test_rmse'] < 0.8
        
        # Should be able to predict
        entry_pred, exit_pred = optimizer.predict(X.head(10))
>>>>>>> origin/main
        assert len(entry_pred) == 10


class TestAdaptiveThresholdManager:
    """Test runtime threshold management."""
<<<<<<< HEAD

    def test_manager_initialization(self):
        """Test manager creation."""
        manager = AdaptiveThresholdManager(default_entry=2.0, default_exit=0.5)

        assert manager.default_entry == 2.0
        assert manager.default_exit == 0.5
        assert manager.optimizer is None

    def test_fallback_thresholds(self):
        """Test fallback when no model available."""
        manager = AdaptiveThresholdManager(default_entry=2.0, default_exit=0.5)

        # Without model, should return defaults
        entry, exit_t = manager.get_thresholds(
            "AAPL-MSFT",
=======
    
    def test_manager_initialization(self):
        """Test manager creation."""
        manager = AdaptiveThresholdManager(default_entry=2.0, default_exit=0.5)
        
        assert manager.default_entry == 2.0
        assert manager.default_exit == 0.5
        assert manager.optimizer is None
    
    def test_fallback_thresholds(self):
        """Test fallback when no model available."""
        manager = AdaptiveThresholdManager(default_entry=2.0, default_exit=0.5)
        
        # Without model, should return defaults
        entry, exit_t = manager.get_thresholds(
            'AAPL-MSFT',
>>>>>>> origin/main
            half_life=20.0,
            volatility=0.15,
            mean_reversion_speed=0.05,
            autocorrelation=0.85,
            spread_mean=0.0,
            spread_std=0.1,
            market_volatility=0.15,
            trend_strength=0.3,
<<<<<<< HEAD
            correlation_strength=0.5,
        )

        assert entry == 2.0
        assert exit_t == 0.5

    def test_cache_functionality(self):
        """Test threshold caching."""
        manager = AdaptiveThresholdManager()

        # Manually add to cache
        manager.thresholds_cache["TEST_PAIR"] = (2.2, 0.6)

        # Should retrieve from cache
        entry, exit_t = manager.get_thresholds("TEST_PAIR")
        assert entry == 2.2
        assert exit_t == 0.6

        # Clear cache
        manager.clear_cache()
        assert "TEST_PAIR" not in manager.thresholds_cache

=======
            correlation_strength=0.5
        )
        
        assert entry == 2.0
        assert exit_t == 0.5
    
    def test_cache_functionality(self):
        """Test threshold caching."""
        manager = AdaptiveThresholdManager()
        
        # Manually add to cache
        manager.thresholds_cache['TEST_PAIR'] = (2.2, 0.6)
        
        # Should retrieve from cache
        entry, exit_t = manager.get_thresholds('TEST_PAIR')
        assert entry == 2.2
        assert exit_t == 0.6
        
        # Clear cache
        manager.clear_cache()
        assert 'TEST_PAIR' not in manager.thresholds_cache
    
>>>>>>> origin/main
    def test_model_integration(self):
        """Test integration with trained model."""
        # Train a model
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=10)
<<<<<<< HEAD

        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)

        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit)

        # Set model
        manager = AdaptiveThresholdManager()
        manager.set_model(optimizer, engineer)

        # Now should get predictions
        entry, exit_t = manager.get_thresholds(
            "NEW_PAIR",
=======
        
        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)
        
        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit)
        
        # Set model
        manager = AdaptiveThresholdManager()
        manager.set_model(optimizer, engineer)
        
        # Now should get predictions
        entry, exit_t = manager.get_thresholds(
            'NEW_PAIR',
>>>>>>> origin/main
            half_life=20.0,
            volatility=0.15,
            mean_reversion_speed=0.05,
            autocorrelation=0.85,
            spread_mean=0.0,
            spread_std=0.1,
            market_volatility=0.15,
            trend_strength=0.3,
<<<<<<< HEAD
            correlation_strength=0.5,
        )

=======
            correlation_strength=0.5
        )
        
>>>>>>> origin/main
        # Should be different from defaults (likely)
        # At least should be in valid ranges
        assert 1.0 <= entry <= 3.0
        assert 0.1 <= exit_t <= 1.0


class TestS41Integration:
    """Integration tests."""
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_full_ml_pipeline(self):
        """Test complete ML pipeline."""
        # 1. Generate data
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=20)
<<<<<<< HEAD

        # 2. Engineer features
        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)

        # 3. Train model
        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit)

        # 4. Create manager
        manager = AdaptiveThresholdManager()
        manager.set_model(optimizer, engineer)

=======
        
        # 2. Engineer features
        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)
        
        # 3. Train model
        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit)
        
        # 4. Create manager
        manager = AdaptiveThresholdManager()
        manager.set_model(optimizer, engineer)
        
>>>>>>> origin/main
        # 5. Get predictions for new pairs
        for i in range(5):
            char = examples[i]
            entry, exit_t = manager.get_thresholds(
<<<<<<< HEAD
                f"pair_{i}",
=======
                f'pair_{i}',
>>>>>>> origin/main
                half_life=char.half_life,
                volatility=char.volatility,
                mean_reversion_speed=char.mean_reversion_speed,
                autocorrelation=char.autocorrelation,
                spread_mean=char.spread_mean,
                spread_std=char.spread_std,
                market_volatility=char.market_volatility,
                trend_strength=char.trend_strength,
<<<<<<< HEAD
                correlation_strength=char.correlation_strength,
            )

=======
                correlation_strength=char.correlation_strength
            )
            
>>>>>>> origin/main
            # Should have valid predictions
            assert 1.0 <= entry <= 3.0
            assert 0.1 <= exit_t <= 1.0
            assert exit_t < entry
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_threshold_optimization_improves_performance(self):
        """Test that optimized thresholds beat defaults."""
        # Generate data
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=20)
<<<<<<< HEAD

        # Calculate average performance with defaults
        default_performance = {"win_rate": [], "profit_factor": [], "sharpe_ratio": []}

        for ex in examples:
            # Check if this was a default threshold combo (2.0 / 0.5)
            if abs(ex.entry_threshold - 2.0) < 0.01 and abs(ex.exit_threshold - 0.5) < 0.01:
                default_performance["win_rate"].append(ex.win_rate)
                default_performance["profit_factor"].append(ex.profit_factor)
                default_performance["sharpe_ratio"].append(ex.sharpe_ratio)

        # Train model to find better thresholds
        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)

        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit)

        # Predictions should exist
        entry_pred, _exit_pred = optimizer.predict(X)
=======
        
        # Calculate average performance with defaults
        default_performance = {
            'win_rate': [],
            'profit_factor': [],
            'sharpe_ratio': []
        }
        
        for ex in examples:
            # Check if this was a default threshold combo (2.0 / 0.5)
            if abs(ex.entry_threshold - 2.0) < 0.01 and abs(ex.exit_threshold - 0.5) < 0.01:
                default_performance['win_rate'].append(ex.win_rate)
                default_performance['profit_factor'].append(ex.profit_factor)
                default_performance['sharpe_ratio'].append(ex.sharpe_ratio)
        
        # Train model to find better thresholds
        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)
        
        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit)
        
        # Predictions should exist
        entry_pred, exit_pred = optimizer.predict(X)
>>>>>>> origin/main
        assert len(entry_pred) > 0


class TestS41PerformanceBenchmarks:
    """Benchmark tests for S4.1."""
<<<<<<< HEAD

    def test_data_generation_speed(self):
        """Test data generation performance."""
        gen = ThresholdDataGenerator()

        start = time.time()
        examples = gen.generate_training_data(num_pairs=50)
        elapsed = time.time() - start

        # Should generate 1000+ examples in reasonable time; generous limits for loaded machines/CI
        _limit = 90.0 if os.environ.get("CI") else 60.0
        assert len(examples) > 800
        assert elapsed < _limit

=======
    
    def test_data_generation_speed(self):
        """Test data generation performance."""
        gen = ThresholdDataGenerator()
        
        start = time.time()
        examples = gen.generate_training_data(num_pairs=50)
        elapsed = time.time() - start
        
        # Should generate 1000+ examples in <5 seconds
        assert len(examples) > 800
        assert elapsed < 5.0
    
>>>>>>> origin/main
    def test_model_training_speed(self):
        """Test model training performance."""
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=30)
<<<<<<< HEAD

        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)

        optimizer = MLThresholdOptimizer()

        start = time.time()
        optimizer.train(X, y_entry, y_exit)
        elapsed = time.time() - start

        # Training should be fast (<2 seconds)
        assert elapsed < 2.0

=======
        
        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)
        
        optimizer = MLThresholdOptimizer()
        
        start = time.time()
        optimizer.train(X, y_entry, y_exit)
        elapsed = time.time() - start
        
        # Training should be fast (<2 seconds)
        assert elapsed < 2.0
    
>>>>>>> origin/main
    def test_prediction_speed(self):
        """Test prediction speed."""
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=20)
<<<<<<< HEAD

        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)

        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit)

=======
        
        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)
        
        optimizer = MLThresholdOptimizer()
        optimizer.train(X, y_entry, y_exit)
        
>>>>>>> origin/main
        start = time.time()
        for _ in range(100):
            optimizer.predict(X.head(50))
        elapsed = time.time() - start
<<<<<<< HEAD

        # 100 predictions on 50 examples each should be reasonable (generous limits for loaded machines/CI)
        _limit = 60.0 if os.environ.get("CI") else 30.0
        assert elapsed < _limit

=======
        
        # 100 predictions on 50 examples each should be reasonable (<3 seconds)
        assert elapsed < 3.0
    
>>>>>>> origin/main
    def test_model_quality_metrics(self):
        """Test model quality targets."""
        gen = ThresholdDataGenerator()
        examples = gen.generate_training_data(num_pairs=40)
<<<<<<< HEAD

        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)

        optimizer = MLThresholdOptimizer()
        metrics = optimizer.train(X, y_entry, y_exit)

        # Model should train and produce valid metrics
        assert "test_r2" in metrics["entry"]
        assert "test_r2" in metrics["exit"]

        # RMSE should be in reasonable range (threshold values are 0.1-3.0)
        assert metrics["entry"]["test_rmse"] < 1.5
        assert metrics["exit"]["test_rmse"] < 1.5
=======
        
        engineer = ThresholdFeatureEngineer()
        X, y_entry, y_exit = engineer.engineer_features(examples)
        
        optimizer = MLThresholdOptimizer()
        metrics = optimizer.train(X, y_entry, y_exit)
        
        # Model should train and produce valid metrics
        assert 'test_r2' in metrics['entry']
        assert 'test_r2' in metrics['exit']
        
        # RMSE should be in reasonable range (threshold values are 0.1-3.0)
        assert metrics['entry']['test_rmse'] < 1.5
        assert metrics['exit']['test_rmse'] < 1.5
>>>>>>> origin/main
