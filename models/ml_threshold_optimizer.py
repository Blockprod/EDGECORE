"""
S4.1: Machine Learning Threshold Optimization

Objective: Train ML models to optimize entry/exit thresholds for maximum performance.

Problem Statement:
- Current system uses fixed thresholds: entry=2.0σ, exit=0.5σ
- Fixed thresholds don't adapt to market conditions
- Different pairs have different optimal thresholds
- Manual tuning is time-consuming and error-prone

Solution:
- Generate synthetic trading data across threshold ranges
- Engineer features from pair characteristics and market conditions
- Train ML model to predict optimal thresholds
- Adapt thresholds per-pair based on market regime

Performance Target:
- Win rate: >55% (vs current 50%)
- Profit factor: >1.5 (vs current 1.2)
- Sharpe ratio: >1.5 (vs current 1.1)
- False signal ratio: <30% (vs current 40%)

Architecture:
1. ThresholdDataGenerator: Creates synthetic training data
2. ThresholdFeatureEngineer: Extracts predictive features
3. MLThresholdOptimizer: Trains and predicts optimal thresholds
4. AdaptiveThresholdManager: Runtime threshold adjustment

Time Allocation (16h):
- Data generation: 3h
- Feature engineering: 3h
- Model training & tuning: 5h
- Validation & integration: 5h
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, List, Optional, Any
from dataclasses import dataclass
import logging
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import pickle
import json
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ThresholdOptimizationResult:
    """Result of threshold optimization."""
    pair_key: str
    optimal_entry_threshold: float
    optimal_exit_threshold: float
    predicted_win_rate: float
    predicted_profit_factor: float
    predicted_sharpe_ratio: float
    confidence_score: float  # 0-1, higher = more confident
    recommendation: str  # 'use', 'review', 'reject'


@dataclass
class TrainingExample:
    """Single training example from a backtest."""
    pair_key: str
    entry_threshold: float
    exit_threshold: float
    # Pair characteristics
    half_life: float
    mean_reversion_speed: float
    volatility: float
    autocorrelation: float
    spread_mean: float
    spread_std: float
    # Trading performance metrics
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    total_trades: int
    avg_trade_duration: float
    false_signal_ratio: float
    # Market conditions
    market_volatility: float
    trend_strength: float
    correlation_strength: float


class ThresholdDataGenerator:
    """
    Generate synthetic training data by running backtests across threshold ranges.
    
    Motivation:
    - Need training data with (threshold, performance) pairs
    - Can't use real historical data (small sample)
    - Synthetic data covers reasonable threshold space
    
    Strategy:
    - Sample pairs from universe
    - Test each pair across 25 threshold combinations
    - Record performance metrics for each combination
    - Generate ~1000 training examples
    """
    
    def __init__(self, lookback: int = 252):
        """Initialize data generator."""
        self.lookback = lookback
        self.training_examples: List[TrainingExample] = []
    
    def generate_synthetic_pair_data(self, pair_key: str, num_bars: int = 252) -> pd.Series:
        """
        Generate synthetic mean-reverting pair data.
        
        Creates data with known mean-reversion characteristics:
        - Mean-reverting AR(1) process
        - Variable volatility
        - Trending periods
        
        Args:
            pair_key: Identifier for the pair
            num_bars: Number of bars to generate
            
        Returns:
            pd.Series of synthetic spread values
        """
        np.random.seed(hash(pair_key) % 2**32)  # Deterministic per pair
        
        # AR(1) mean-reverting process
        # spread_t = mean + rho * (spread_{t-1} - mean) + epsilon_t
        mean = np.random.uniform(-0.5, 0.5)  # Pair-specific mean
        rho = np.random.uniform(0.75, 0.95)  # Mean-reversion strength
        volatility = np.random.uniform(0.05, 0.20)  # Volatility (important feature)
        
        spread = np.zeros(num_bars)
        spread[0] = mean
        
        for i in range(1, num_bars):
            epsilon = np.random.normal(0, volatility)
            spread[i] = mean + rho * (spread[i-1] - mean) + epsilon
        
        return pd.Series(spread, name=pair_key)
    
    def compute_pair_characteristics(self, spread: pd.Series) -> Dict[str, float]:
        """
        Extract statistical characteristics from spread data.
        
        Features derived:
        - volatility: annualized std dev
        - autocorrelation: AR(1) coefficient
        - mean_reversion_speed: speed of reversion
        
        Args:
            spread: Spread series
            
        Returns:
            Dict with characteristic values
        """
        # Volatility: rolling standard deviation
        volatility = spread.rolling(20).std().mean()
        if np.isnan(volatility):
            volatility = spread.std()
        
        # Autocorrelation: correlation with lagged series
        if len(spread) > 1:
            autocorr = spread.corr(spread.shift(1))
            if np.isnan(autocorr):
                autocorr = 0.5
        else:
            autocorr = 0.5
        
        # Half-life (approximation from autocorr)
        if autocorr > 0 and autocorr < 1:
            half_life = -np.log(2) / np.log(autocorr)
        else:
            half_life = 20.0
        
        # Mean reversion speed (inverse of half-life)
        mr_speed = 1.0 / max(half_life, 1.0)
        
        return {
            'half_life': float(half_life),
            'mean_reversion_speed': float(mr_speed),
            'volatility': float(volatility) if not np.isnan(volatility) else 0.1,
            'autocorrelation': float(autocorr),
            'spread_mean': float(spread.mean()),
            'spread_std': float(spread.std())
        }
    
    def simulate_trades(
        self,
        spread: pd.Series,
        entry_threshold: float,
        exit_threshold: float,
        lookback: int = 20
    ) -> Dict[str, float]:
        """
        Simulate trades with given thresholds.
        
        Logic:
        - Compute rolling Z-score
        - Entry: |Z| > entry_threshold
        - Exit: |Z| <= exit_threshold
        - Calculate performance metrics
        
        Args:
            spread: Spread series
            entry_threshold: Entry Z-score threshold
            exit_threshold: Exit Z-score threshold
            lookback: Rolling window for mean/std
            
        Returns:
            Dict with performance metrics
        """
        # Compute Z-scores
        rolling_mean = spread.rolling(lookback).mean()
        rolling_std = spread.rolling(lookback).std()
        z_scores = (spread - rolling_mean) / (rolling_std + 1e-8)
        
        # Simulate trades
        in_position = False
        entry_prices = []
        exit_prices = []
        trades = []
        false_signals = 0
        
        for i in range(lookback, len(z_scores)):
            z = z_scores.iloc[i]
            
            # Entry signal
            if not in_position and abs(z) > entry_threshold:
                entry_prices.append(spread.iloc[i])
                in_position = True
            
            # Exit signal
            elif in_position and abs(z) <= exit_threshold:
                exit_prices.append(spread.iloc[i])
                trades.append({
                    'entry': entry_prices[-1],
                    'exit': exit_prices[-1],
                    'pnl': exit_prices[-1] - entry_prices[-1],
                    'duration': len(spread) - i  # Approximate
                })
                in_position = False
            
            # False signal if we're not in position and threshold is breached again
            if not in_position and len(entry_prices) > len(exit_prices):
                false_signals += 1
        
        # Calculate metrics
        if len(trades) == 0:
            return {
                'win_rate': 0.5,
                'profit_factor': 1.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'total_trades': 0,
                'avg_trade_duration': 0.0,
                'false_signal_ratio': 0.0
            }
        
        # Win rate
        winning_trades = [t for t in trades if t['pnl'] > 0]
        win_rate = len(winning_trades) / len(trades) if trades else 0.5
        
        # Profit factor
        gross_profit = sum([t['pnl'] for t in trades if t['pnl'] > 0])
        gross_loss = abs(sum([t['pnl'] for t in trades if t['pnl'] <= 0]))
        profit_factor = gross_profit / (gross_loss + 1e-8) if gross_loss > 0 else 1.0
        
        # Sharpe ratio (approximation – 252 trading days/year for equities)
        pnls = np.array([t['pnl'] for t in trades])
        if len(pnls) > 1 and pnls.std() > 0:
            sharpe = np.mean(pnls) / pnls.std() * np.sqrt(252)
        else:
            sharpe = 0.0
        
        # Max drawdown (approximation)
        cumulative_pnl = np.cumsum(pnls)
        if len(cumulative_pnl) > 0:
            running_max = np.maximum.accumulate(cumulative_pnl)
            max_drawdown = np.min(cumulative_pnl - running_max) / (abs(np.max(running_max)) + 1e-8)
        else:
            max_drawdown = 0.0
        
        # Average trade duration
        durations = [t['duration'] for t in trades]
        avg_duration = np.mean(durations) if durations else 0.0
        
        # False signal ratio
        total_signals = len(entry_prices)
        false_signal_ratio = false_signals / (total_signals + 1e-8) if total_signals > 0 else 0.0
        
        return {
            'win_rate': float(win_rate),
            'profit_factor': float(min(profit_factor, 5.0)),  # Cap at 5.0
            'sharpe_ratio': float(sharpe),
            'max_drawdown': float(max_drawdown),
            'total_trades': len(trades),
            'avg_trade_duration': float(avg_duration),
            'false_signal_ratio': float(false_signal_ratio)
        }
    
    def generate_training_data(self, num_pairs: int = 50) -> List[TrainingExample]:
        """
        Generate complete training dataset.
        
        Process:
        1. Generate synthetic pair data
        2. Extract characteristics
        3. Test across threshold combinations
        4. Record examples
        
        Args:
            num_pairs: Number of pairs to generate
            
        Returns:
            List of TrainingExample objects
        """
        examples = []
        
        # Threshold combinations to test
        entry_thresholds = np.linspace(1.0, 3.0, 5)  # [1.0, 1.5, 2.0, 2.5, 3.0]
        exit_thresholds = np.linspace(0.1, 1.0, 5)   # [0.1, 0.325, 0.55, 0.775, 1.0]
        
        logger.info(f"Generating training data for {num_pairs} pairs")
        
        for pair_idx in range(num_pairs):
            pair_key = f"pair_{pair_idx}"
            
            # Generate synthetic data
            spread = self.generate_synthetic_pair_data(pair_key)
            
            # Extract characteristics
            characteristics = self.compute_pair_characteristics(spread)
            
            # Test threshold combinations
            for entry_t in entry_thresholds:
                for exit_t in exit_thresholds:
                    if exit_t < entry_t:  # Only test sensible combinations
                        # Simulate trades
                        performance = self.simulate_trades(spread, entry_t, exit_t)
                        
                        # Create training example
                        example = TrainingExample(
                            pair_key=pair_key,
                            entry_threshold=float(entry_t),
                            exit_threshold=float(exit_t),
                            # Characteristics
                            half_life=characteristics['half_life'],
                            mean_reversion_speed=characteristics['mean_reversion_speed'],
                            volatility=characteristics['volatility'],
                            autocorrelation=characteristics['autocorrelation'],
                            spread_mean=characteristics['spread_mean'],
                            spread_std=characteristics['spread_std'],
                            # Performance
                            win_rate=performance['win_rate'],
                            profit_factor=performance['profit_factor'],
                            sharpe_ratio=performance['sharpe_ratio'],
                            max_drawdown=performance['max_drawdown'],
                            total_trades=performance['total_trades'],
                            avg_trade_duration=performance['avg_trade_duration'],
                            false_signal_ratio=performance['false_signal_ratio'],
                            # Market conditions (fixed for simplicity)
                            market_volatility=0.15,
                            trend_strength=0.3,
                            correlation_strength=0.5
                        )
                        
                        examples.append(example)
        
        self.training_examples = examples
        logger.info(f"Generated {len(examples)} training examples")
        
        return examples


class ThresholdFeatureEngineer:
    """
    Engineer features that predict optimal thresholds.
    
    Philosophy:
    - Features should capture pair characteristics
    - Features should capture market conditions
    - Features should enable threshold prediction
    
    Key Features:
    - Volatility-adjusted thresholds
    - Half-life-based features
    - Market regime indicators
    """
    
    def __init__(self):
        """Initialize feature engineer."""
        self.scaler = StandardScaler()
        self.feature_names = []
    
    def engineer_features(
        self,
        examples: List[TrainingExample]
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Engineer features from training examples.
        
        Features:
        1. Pair characteristics: half_life, volatility, mr_speed
        2. Normalized: standardize to 0-mean, 1-std
        3. Interactions: volatility * half_life, etc.
        4. Target: entry_threshold, exit_threshold
        
        Args:
            examples: List of training examples
            
        Returns:
            (X, y_entry, y_exit) - feature matrix and targets
        """
        data = []
        
        for ex in examples:
            # Feature vector
            row = {
                'half_life': ex.half_life,
                'mean_reversion_speed': ex.mean_reversion_speed,
                'volatility': ex.volatility,
                'autocorrelation': ex.autocorrelation,
                'spread_std': ex.spread_std,
                'market_volatility': ex.market_volatility,
                'trend_strength': ex.trend_strength,
                'correlation_strength': ex.correlation_strength,
                # Interactions
                'vol_x_mr': ex.volatility * ex.mean_reversion_speed,
                'hl_x_vol': ex.half_life * ex.volatility,
                'autocorr_x_mr': ex.autocorrelation * ex.mean_reversion_speed,
                # Performance targets
                'entry_threshold': ex.entry_threshold,
                'exit_threshold': ex.exit_threshold,
                'win_rate': ex.win_rate,
                'profit_factor': ex.profit_factor,
                'sharpe_ratio': ex.sharpe_ratio,
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # Feature columns (exclude targets)
        feature_cols = [
            'half_life', 'mean_reversion_speed', 'volatility', 'autocorrelation',
            'spread_std', 'market_volatility', 'trend_strength', 'correlation_strength',
            'vol_x_mr', 'hl_x_vol', 'autocorr_x_mr'
        ]
        
        self.feature_names = feature_cols
        
        # Extract features and targets
        X = df[feature_cols].copy()
        y_entry = df['entry_threshold'].copy()
        y_exit = df['exit_threshold'].copy()
        
        # Normalize features
        X_scaled = self.scaler.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=feature_cols)
        
        logger.info(f"Engineered {len(feature_cols)} features from {len(examples)} examples")
        
        return X_scaled, y_entry, y_exit
    
    def transform_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transform new features using fitted scaler.
        
        Args:
            X: Raw feature matrix
            
        Returns:
            Scaled feature matrix
        """
        return pd.DataFrame(
            self.scaler.transform(X),
            columns=self.feature_names
        )


class MLThresholdOptimizer:
    """
    Train ML models to predict optimal thresholds.
    
    Approach:
    - Use ensemble: RF + GB for robustness
    - Separate models for entry and exit
    - Hyperparameter tuning on validation set
    - Cross-validation for generalization
    
    Performance Target:
    - R² > 0.7 (70% of variance explained)
    - RMSE < 0.3 (within 0.3σ of true threshold)
    """
    
    def __init__(self):
        """Initialize optimizer."""
        self.entry_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=8,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42
        )
        self.exit_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=8,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42
        )
        
        self.entry_test_metrics = {}
        self.exit_test_metrics = {}
    
    def train(
        self,
        X: pd.DataFrame,
        y_entry: pd.Series,
        y_exit: pd.Series,
        test_size: float = 0.2
    ) -> Dict[str, Any]:
        """
        Train threshold prediction models.
        
        Args:
            X: Feature matrix
            y_entry: Entry threshold targets
            y_exit: Exit threshold targets
            test_size: Proportion for test set
            
        Returns:
            Dict with training metrics
        """
        # Split data — temporal (chronological) split to avoid look-ahead bias
        split_idx = int(len(X) * (1 - test_size))
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_entry_train, y_entry_test = y_entry[:split_idx], y_entry[split_idx:]
        y_exit_train, y_exit_test = y_exit[:split_idx], y_exit[split_idx:]
        
        # Train entry model
        logger.info("Training entry threshold model...")
        self.entry_model.fit(X_train, y_entry_train)
        
        y_entry_pred_train = self.entry_model.predict(X_train)
        y_entry_pred_test = self.entry_model.predict(X_test)
        
        entry_train_r2 = r2_score(y_entry_train, y_entry_pred_train)
        entry_test_r2 = r2_score(y_entry_test, y_entry_pred_test)
        entry_test_rmse = np.sqrt(mean_squared_error(y_entry_test, y_entry_pred_test))
        entry_test_mae = mean_absolute_error(y_entry_test, y_entry_pred_test)
        
        # Train exit model
        logger.info("Training exit threshold model...")
        self.exit_model.fit(X_train, y_exit_train)
        
        y_exit_pred_train = self.exit_model.predict(X_train)
        y_exit_pred_test = self.exit_model.predict(X_test)
        
        exit_train_r2 = r2_score(y_exit_train, y_exit_pred_train)
        exit_test_r2 = r2_score(y_exit_test, y_exit_pred_test)
        exit_test_rmse = np.sqrt(mean_squared_error(y_exit_test, y_exit_pred_test))
        exit_test_mae = mean_absolute_error(y_exit_test, y_exit_pred_test)
        
        # Store metrics
        self.entry_test_metrics = {
            'train_r2': float(entry_train_r2),
            'test_r2': float(entry_test_r2),
            'test_rmse': float(entry_test_rmse),
            'test_mae': float(entry_test_mae)
        }
        
        self.exit_test_metrics = {
            'train_r2': float(exit_train_r2),
            'test_r2': float(exit_test_r2),
            'test_rmse': float(exit_test_rmse),
            'test_mae': float(exit_test_mae)
        }
        
        logger.info(f"Entry model: train R²={entry_train_r2:.3f}, test R²={entry_test_r2:.3f}")
        logger.info(f"Exit model: train R²={exit_train_r2:.3f}, test R²={exit_test_r2:.3f}")
        
        return {
            'entry': self.entry_test_metrics,
            'exit': self.exit_test_metrics
        }
    
    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict optimal thresholds.
        
        Args:
            X: Feature matrix
            
        Returns:
            (entry_thresholds, exit_thresholds)
        """
        entry_pred = self.entry_model.predict(X)
        exit_pred = self.exit_model.predict(X)
        
        # Clip to reasonable ranges
        entry_pred = np.clip(entry_pred, 1.0, 3.0)
        exit_pred = np.clip(exit_pred, 0.1, 1.0)
        
        # Ensure exit < entry
        for i in range(len(entry_pred)):
            if exit_pred[i] >= entry_pred[i]:
                exit_pred[i] = entry_pred[i] * 0.25
        
        return entry_pred, exit_pred
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importances from entry model.
        
        Returns:
            Dict mapping feature names to importance scores
        """
        if not hasattr(self.entry_model, 'feature_importances_'):
            return {}
        
        importances = self.entry_model.feature_importances_
        feature_names = self.entry_model.feature_names_in_ if hasattr(
            self.entry_model, 'feature_names_in_'
        ) else [f'feature_{i}' for i in range(len(importances))]
        
        return dict(zip(feature_names, importances))


class AdaptiveThresholdManager:
    """
    Manage per-pair thresholds using ML predictions.
    
    Features:
    - Cache predicted thresholds
    - Per-pair customization
    - Market regime adjustment
    - Fallback to defaults
    - Sprint 2.5: OOS validation gate – ML auto-disabled if OOS degradation > 20%
    
    Integration:
    - Replaces fixed 2.0/0.5 thresholds in signal generation
    - Used in VectorizedSignalGenerator
    """
    
    def __init__(self, default_entry: float = 2.0, default_exit: float = 0.5):
        """
        Initialize threshold manager.
        
        Args:
            default_entry: Fallback entry threshold
            default_exit: Fallback exit threshold
        """
        self.default_entry = default_entry
        self.default_exit = default_exit
        self.thresholds_cache: Dict[str, Tuple[float, float]] = {}
        self.optimizer: Optional[MLThresholdOptimizer] = None
        self.feature_engineer: Optional[ThresholdFeatureEngineer] = None
        self.ml_enabled: bool = True  # Sprint 2.5: can be disabled by OOS validation
        self._oos_rejection_reason: str = ""
    
    def set_model(
        self,
        optimizer: MLThresholdOptimizer,
        feature_engineer: ThresholdFeatureEngineer
    ) -> None:
        """
        Set trained ML model.
        
        Args:
            optimizer: Trained MLThresholdOptimizer
            feature_engineer: Trained ThresholdFeatureEngineer
        """
        self.optimizer = optimizer
        self.feature_engineer = feature_engineer
    
    def validate_and_set_model(
        self,
        optimizer: MLThresholdOptimizer,
        feature_engineer: ThresholdFeatureEngineer,
        X: pd.DataFrame,
        y_entry: pd.Series,
        y_exit: pd.Series,
        n_folds: int = 5,
        max_degradation_pct: float = 20.0,
    ) -> 'ValidationResult':
        """
        Validate ML model OOS before enabling it.
        
        Sprint 2.5: If OOS degradation > max_degradation_pct, ML is disabled
        and fixed thresholds are used instead.
        
        Args:
            optimizer: Trained MLThresholdOptimizer
            feature_engineer: Trained ThresholdFeatureEngineer
            X: Feature matrix for validation
            y_entry: Entry threshold targets
            y_exit: Exit threshold targets
            n_folds: Walk-forward folds
            max_degradation_pct: Max OOS degradation before disabling ML
            
        Returns:
            ValidationResult from walk-forward CV
        """
        from models.ml_threshold_validator import MLThresholdValidator
        
        validator = MLThresholdValidator(
            n_folds=n_folds,
            max_degradation_pct=max_degradation_pct,
        )
        result = validator.validate_oos_performance(X, y_entry, y_exit)
        
        # Always store the model
        self.optimizer = optimizer
        self.feature_engineer = feature_engineer
        
        # But disable ML if validation fails
        if result.ml_approved:
            self.ml_enabled = True
            self._oos_rejection_reason = ""
            logger.info("ML thresholds enabled after OOS validation")
        else:
            self.ml_enabled = False
            self._oos_rejection_reason = result.rejection_reason
            logger.warning(
                f"ML thresholds DISABLED: {result.rejection_reason}. "
                f"Falling back to fixed thresholds "
                f"(entry={self.default_entry}, exit={self.default_exit})"
            )
        
        return result
    
    def get_thresholds(
        self,
        pair_key: str,
        **pair_characteristics
    ) -> Tuple[float, float]:
        """
        Get optimized thresholds for a pair.
        
        Args:
            pair_key: Identifier for the pair
            **pair_characteristics: Half-life, volatility, etc.
            
        Returns:
            (entry_threshold, exit_threshold)
        """
        # Check cache
        if pair_key in self.thresholds_cache:
            return self.thresholds_cache[pair_key]
        
        # If ML disabled by OOS validation, use defaults
        if not self.ml_enabled:
            return (self.default_entry, self.default_exit)
        
        # If no model, use defaults
        if self.optimizer is None or self.feature_engineer is None:
            return (self.default_entry, self.default_exit)
        
        # Build feature vector
        try:
            features_df = pd.DataFrame([pair_characteristics])
            features_scaled = self.feature_engineer.transform_features(features_df)
            
            # Predict thresholds
            entry_pred, exit_pred = self.optimizer.predict(features_scaled)
            
            entry_threshold = float(entry_pred[0])
            exit_threshold = float(exit_pred[0])
            
            # Cache result
            self.thresholds_cache[pair_key] = (entry_threshold, exit_threshold)
            
            return (entry_threshold, exit_threshold)
        
        except Exception as e:
            logger.warning(f"Failed to predict thresholds for {pair_key}: {e}")
            return (self.default_entry, self.default_exit)
    
    def clear_cache(self) -> None:
        """Clear cached thresholds."""
        self.thresholds_cache.clear()
    
    def save_model(self, filepath: str) -> None:
        """
        Save trained model to disk.
        
        Args:
            filepath: Path to save model
        """
        if self.optimizer is None:
            logger.warning("No model to save")
            return
        
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        model_data = {
            'optimizer': pickle.dumps(self.optimizer),
            'feature_engineer': pickle.dumps(self.feature_engineer),
            'timestamp': datetime.now().isoformat()
        }
        
        with open(path, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str) -> None:
        """
        Load trained model from disk.
        
        Args:
            filepath: Path to model file
        """
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
            
            self.optimizer = pickle.loads(model_data['optimizer'])
            self.feature_engineer = pickle.loads(model_data['feature_engineer'])
            
            logger.info(f"Model loaded from {filepath}")
        
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
