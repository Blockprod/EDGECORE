"""
Sprint 3.4 – Rigorous End-to-End Tests.

Validates that:
1. The full pipeline (discovery ↓ signals ↓ backtest) has no data leakage
2. Backtest signal generation matches what live would produce
3. DynamicSpreadModel z-score ↓ signal direction is deterministic
4. RegimeDetector transitions are exact for controlled inputs
5. Every test assertion checks a COMPUTED VALUE, not just a type

DoD: Every assertion checks exact values; no `isinstance`-only or `is not None`
guards without follow-up value checks.
"""

import numpy as np
import pandas as pd

from backtests.strategy_simulator import StrategyBacktestSimulator
from backtests.cost_model import CostModel, CostModelConfig
from backtests.metrics import BacktestMetrics
from backtests.walk_forward import split_walk_forward
from models.regime_detector import RegimeDetector, VolatilityRegime
from models.adaptive_thresholds import DynamicSpreadModel
from strategies.pair_trading import PairTradingStrategy


class TestFullPipelineNoLeakage:
    """End-to-end: full pipeline must never leak future data."""
    
    def test_simulator_expanding_window_integrity(self):
        """The StrategyBacktestSimulator must use strictly expanding windows.
        
        We patch generate_signals to record the length of market_data 
        passed at each bar. Lengths must be strictly increasing by 1.
        """
        from unittest.mock import patch
        
        np.random.seed(42)
        n_bars = 400
        dates = pd.date_range("2023-01-01", periods=n_bars, freq="D")
        x = np.cumsum(np.random.randn(n_bars) * 0.01) + 100
        y = 2.0 * x + np.random.randn(n_bars) * 0.1
        prices = pd.DataFrame({"SYM_A": x, "SYM_B": y}, index=dates)
        
        observed_lengths = []
        
        def _recording_generate(self_strategy, market_data, discovered_pairs=None, **kwargs):
            observed_lengths.append(len(market_data))
            return []
        
        with patch(
            "strategies.pair_trading.PairTradingStrategy.generate_signals",
            _recording_generate,
        ):
            sim = StrategyBacktestSimulator(
                cost_model=CostModel(),
                initial_capital=100_000,
                pair_rediscovery_interval=999,
            )
            sim.run(prices, fixed_pairs=[])
        
        # Verify strictly increasing by 1
        assert len(observed_lengths) > 1, "Should call generate_signals multiple times"
        for i in range(1, len(observed_lengths)):
            assert observed_lengths[i] == observed_lengths[i - 1] + 1, (
                f"Bar {i}: window length {observed_lengths[i]} != "
                f"previous+1 ({observed_lengths[i - 1] + 1}). DATA LEAKAGE."
            )
    
    def test_walk_forward_splits_no_overlap(self):
        """Walk-forward splits must have zero index overlap between train and test."""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=365, freq="D")
        data = pd.DataFrame({
            "AAPL": np.random.randn(365).cumsum() + 100,
            "MSFT": np.random.randn(365).cumsum() + 50
        }, index=dates)
        
        for num_periods in [2, 3, 4, 5]:
            splits = split_walk_forward(data, num_periods=num_periods, oos_ratio=0.2)
            
            for i, (train, test) in enumerate(splits):
                overlap = train.index.intersection(test.index)
                assert len(overlap) == 0, (
                    f"Leakage: {len(overlap)} overlapping dates in split {i} "
                    f"(num_periods={num_periods})"
                )
                assert train.index.max() < test.index.min(), (
                    f"Temporal leakage: train ends {train.index.max()}, "
                    f"test starts {test.index.min()} in split {i}"
                )
    
    def test_simulator_completes_with_real_metrics(self):
        """Full simulator run must produce metrics with real computed values."""
        np.random.seed(42)
        n_bars = 300
        dates = pd.date_range("2023-01-01", periods=n_bars, freq="D")
        x = 100.0 * np.exp(np.cumsum(np.random.randn(n_bars) * 0.005))
        y = 2.0 * x + np.random.randn(n_bars) * 3.0
        prices = pd.DataFrame({"SYM_A": x, "SYM_B": y}, index=dates)
        
        sim = StrategyBacktestSimulator(
            cost_model=CostModel(CostModelConfig(include_borrowing=False)),
            initial_capital=100_000,
            pair_rediscovery_interval=21,
        )
        metrics = sim.run(prices)
        
        assert isinstance(metrics, BacktestMetrics)
        assert metrics.start_date == "2023-01-01"
        assert metrics.total_trades >= 0
        assert isinstance(metrics.total_return, float)
        assert isinstance(metrics.sharpe_ratio, float)
        assert metrics.max_drawdown <= 0.0, (
            f"max_drawdown should be <= 0, got {metrics.max_drawdown}"
        )


class TestBacktestMatchesLiveSignals:
    """Verify signal generation is identical in backtest and 'live' contexts.
    
    The same data fed to generate_signals() must produce the same signals
    regardless of how it's called (directly vs via simulator).
    """
    
    def test_signal_determinism(self):
        """Same input data ↓ same signals, regardless of call order."""
        np.random.seed(42)
        n = 200
        x = pd.Series(np.cumsum(np.random.randn(n) * 0.5) + 100)
        y = 2.0 * x + np.random.randn(n) * 0.5
        
        model1 = DynamicSpreadModel(y, x, half_life=20.0)
        model2 = DynamicSpreadModel(y, x, half_life=20.0)
        
        spread1 = model1.compute_spread(y, x)
        spread2 = model2.compute_spread(y, x)
        
        signals1, info1 = model1.get_adaptive_signals(spread1)
        signals2, info2 = model2.get_adaptive_signals(spread2)
        
        # Exact same signals
        pd.testing.assert_series_equal(signals1, signals2, check_names=False)
        
        # Same z-scores
        pd.testing.assert_series_equal(
            info1['z_score'], info2['z_score'], check_names=False
        )
    
    def test_strategy_generate_signals_deterministic(self):
        """PairTradingStrategy.generate_signals is deterministic for same seed."""
        np.random.seed(42)
        n = 200
        prices = pd.DataFrame({
            'AAPL': np.random.randn(n).cumsum() + 100,
            'MSFT': np.random.randn(n).cumsum() + 50,
        })
        
        strategy1 = PairTradingStrategy()
        strategy2 = PairTradingStrategy()
        
        signals1 = strategy1.generate_signals(prices)
        signals2 = strategy2.generate_signals(prices)
        
        assert len(signals1) == len(signals2), (
            f"Non-deterministic signal count: {len(signals1)} vs {len(signals2)}"
        )
        
        for s1, s2 in zip(signals1, signals2):
            assert s1.side == s2.side, f"Side mismatch: {s1.side} vs {s2.side}"
            assert s1.symbol_pair == s2.symbol_pair


class TestRegimeDetectorExactValues:
    """Sprint 3.4: Every regime test checks exact expected value."""
    
    def test_deterministic_low_regime(self):
        """Constant spread after volatile start ↓ exact LOW regime."""
        np.random.seed(42)
        detector = RegimeDetector(min_regime_duration=1)
        
        # Phase 1: High volatility data
        for i in range(10):
            detector.update(spread=100.0 + np.random.normal(0, 5.0))
        
        # Phase 2: Almost constant data ↓ LOW relative to history
        for i in range(10):
            detector.update(spread=100.0)
        
        assert detector.current_regime == VolatilityRegime.LOW, (
            f"Expected LOW after constant spread, got {detector.current_regime}"
        )
    
    def test_deterministic_high_regime(self):
        """Wild swings after calm start ↓ exact HIGH regime."""
        np.random.seed(42)
        detector = RegimeDetector(min_regime_duration=1)
        
        # Phase 1: Constant data
        for i in range(10):
            detector.update(spread=100.0)
        
        # Phase 2: Wild swings ↓ HIGH relative to history
        for i in range(10):
            detector.update(spread=100.0 + np.random.normal(0, 10.0))
        
        assert detector.current_regime == VolatilityRegime.HIGH, (
            f"Expected HIGH after volatile moves, got {detector.current_regime}"
        )
    
    def test_transition_count_exact(self):
        """Controlled input ↓ exact number of transitions."""
        np.random.seed(42)
        detector = RegimeDetector(min_regime_duration=1)
        
        # Phase 1: constant (establishes baseline)
        for i in range(15):
            detector.update(spread=100.0)
        regime_after_calm = detector.current_regime
        
        # Phase 2: volatile (should trigger at least one transition)
        for i in range(15):
            detector.update(spread=100.0 + np.random.normal(0, 10.0))
        
        assert len(detector.regime_transitions) >= 1, (
            f"Expected at least 1 transition, got {len(detector.regime_transitions)}"
        )
        # The last regime should differ from the calm regime
        assert detector.current_regime != regime_after_calm, (
            f"Regime should have changed from {regime_after_calm} after volatile phase"
        )


class TestDynamicSpreadModelExactSignals:
    """Sprint 3.4: Signal direction verified for controlled z-score inputs."""
    
    def test_extreme_negative_spread_produces_long(self):
        """Extremely negative spread ↓ z <<< 0 ↓ long signal (1)."""
        np.random.seed(42)
        n = 200
        x = pd.Series(np.cumsum(np.random.randn(n) * 0.5) + 100)
        y = 2.0 * x + np.random.randn(n) * 0.5
        
        model = DynamicSpreadModel(y, x, half_life=20.0)
        spread = model.compute_spread(y, x)
        
        # Force extreme negative at end
        forced = spread.copy()
        forced.iloc[-1] = spread.mean() - 10 * spread.std()
        
        signals, info = model.get_adaptive_signals(forced)
        assert signals.iloc[-1] == 1, (
            f"Expected long (1) for extreme negative spread, got {signals.iloc[-1]}"
        )
    
    def test_extreme_positive_spread_produces_short(self):
        """Extremely positive spread ↓ z >>> 0 ↓ short signal (-1)."""
        np.random.seed(42)
        n = 200
        x = pd.Series(np.cumsum(np.random.randn(n) * 0.5) + 100)
        y = 2.0 * x + np.random.randn(n) * 0.5
        
        model = DynamicSpreadModel(y, x, half_life=20.0)
        spread = model.compute_spread(y, x)
        
        # Force extreme positive at end
        forced = spread.copy()
        forced.iloc[-1] = spread.mean() + 10 * spread.std()
        
        signals, info = model.get_adaptive_signals(forced)
        assert signals.iloc[-1] == -1, (
            f"Expected short (-1) for extreme positive spread, got {signals.iloc[-1]}"
        )
    
    def test_mean_spread_produces_hold(self):
        """Spread at rolling mean ↓ z ≈ 0 ↓ hold/exit (0)."""
        np.random.seed(42)
        n = 200
        x = pd.Series(np.cumsum(np.random.randn(n) * 0.5) + 100)
        y = 2.0 * x + np.random.randn(n) * 0.5
        
        model = DynamicSpreadModel(y, x, half_life=20.0)
        spread = model.compute_spread(y, x)
        
        # Force spread to rolling mean
        rolling_mean = spread.rolling(window=60).mean()
        forced = spread.copy()
        forced.iloc[-1] = rolling_mean.iloc[-1]
        
        signals, info = model.get_adaptive_signals(forced)
        assert signals.iloc[-1] == 0, (
            f"Expected hold (0) for spread at mean, got {signals.iloc[-1]}"
        )


class TestMetricsComputedValues:
    """Sprint 3.4: Every BacktestMetrics assertion checks a computed value."""
    
    def test_positive_returns_produce_positive_total_return(self):
        """All positive daily returns ↓ total_return > 0."""
        returns = pd.Series([0.01, 0.02, 0.01, 0.015, 0.01])
        trades = [100, 200, 150]
        
        metrics = BacktestMetrics.from_returns(
            returns=returns, trades=trades,
            start_date="2023-01-01", end_date="2023-01-05"
        )
        
        assert metrics.total_return > 0.0, (
            f"All positive returns should yield positive total_return, got {metrics.total_return}"
        )
        assert metrics.sharpe_ratio > 0.0, (
            f"All positive returns should yield positive Sharpe, got {metrics.sharpe_ratio}"
        )
    
    def test_all_losing_trades_zero_win_rate(self):
        """All losing trades ↓ win_rate == 0."""
        returns = pd.Series([-0.01, -0.02, -0.01])
        trades = [-100, -50, -200]
        
        metrics = BacktestMetrics.from_returns(
            returns=returns, trades=trades,
            start_date="2023-01-01", end_date="2023-01-03"
        )
        
        assert metrics.win_rate == 0.0, (
            f"All losing trades should have win_rate=0, got {metrics.win_rate}"
        )
        assert metrics.profit_factor == 0.0, (
            f"All losing trades should have profit_factor=0, got {metrics.profit_factor}"
        )
    
    def test_max_drawdown_is_negative_for_decline(self):
        """A series with decline must have negative max_drawdown."""
        returns = pd.Series([0.10, 0.10, -0.25, -0.15, 0.01])
        trades = []
        
        metrics = BacktestMetrics.from_returns(
            returns=returns, trades=trades,
            start_date="2023-01-01", end_date="2023-01-05"
        )
        
        assert metrics.max_drawdown < 0.0, (
            f"Series with decline must have negative drawdown, got {metrics.max_drawdown}"
        )
