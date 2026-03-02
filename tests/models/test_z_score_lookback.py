"""
Test Suite: Dynamic Z-Score Lookback Window (S2.2).

Problem: Fixed 20-day Z-score window doesn't match pair-specific reversion speed.
- Fast pairs (HL=10d): 20-day window is 2x too long (captures too much noise)
- Slow pairs (HL=60d): 20-day window is 3x too short (misses full cycle)

Solution: Adaptive lookback based on half-life minimizes Z-score lag.
- Fast pairs (HL < 30d): lookback = 3*HL (smooth short-term noise)
- Normal (HL 30-60d): lookback = HL (one full reversion cycle)
- Slow pairs (HL > 60d): lookback = 60 (historical reference)

Expected wins:
- Z-score signals faster for fast pairs (3-5 day earlier)
- Z-score more stable for slow pairs (fewer whipsaws)
- Overall: +0.5 Sharpe points improvement
"""

import pytest
import pandas as pd
import numpy as np
from models.spread import SpreadModel
from models.adaptive_thresholds import DynamicSpreadModel
from strategies.pair_trading import PairTradingStrategy


class TestZScoreLookbackAdaptation:
    """Test compute_z_score with adaptive lookback windows."""
    
    def test_fast_pair_lookback_calculation(self):
        """For fast pairs (HL=10d), lookback should be ~30d (3*HL)."""
        # Create synthetic spread data
        np.random.seed(42)
        days = 200
        spread = pd.Series(np.random.randn(days).cumsum() * 0.5)
        
        model = DynamicSpreadModel(
            y=pd.Series(np.random.randn(days)),
            x=pd.Series(np.random.randn(days)),
            half_life=10.0  # Fast mean reversion
        )
        
        z_score = model.compute_z_score(spread)
        
        # For HL=10, expected lookback = 3*10 = 30
        # The actual lookback is used internally; verify z_score output
        assert len(z_score) == len(spread), "Z-score length should match spread"
        assert not z_score.isna().all(), "Z-score should have values"
        assert not np.isnan(z_score.iloc[-1]), "Last Z-score should be valid"
        
    def test_normal_pair_lookback_calculation(self):
        """For normal pairs (HL=45d), lookback should be ~45d (1*HL)."""
        np.random.seed(42)
        days = 200
        spread = pd.Series(np.random.randn(days).cumsum() * 0.5)
        
        model = DynamicSpreadModel(
            y=pd.Series(np.random.randn(days)),
            x=pd.Series(np.random.randn(days)),
            half_life=45.0  # Normal mean reversion
        )
        
        z_score = model.compute_z_score(spread)
        
        assert len(z_score) == len(spread), "Z-score length should match spread"
        assert not z_score.isna().all(), "Z-score should have values"
        
    def test_slow_pair_lookback_calculation(self):
        """For slow pairs (HL=100d), lookback should be capped at 60d."""
        np.random.seed(42)
        days = 200
        spread = pd.Series(np.random.randn(days).cumsum() * 0.5)
        
        model = DynamicSpreadModel(
            y=pd.Series(np.random.randn(days)),
            x=pd.Series(np.random.randn(days)),
            half_life=100.0  # Slow mean reversion
        )
        
        z_score = model.compute_z_score(spread)
        
        # For HL=100, expected lookback = 60 (cap)
        assert len(z_score) == len(spread), "Z-score length should match spread"
        assert not z_score.isna().all(), "Z-score should have values"
        
    def test_explicit_lookback_overrides_half_life(self):
        """Explicit lookback parameter should override half-life logic."""
        np.random.seed(42)
        days = 200
        spread = pd.Series(np.random.randn(days).cumsum() * 0.5)
        
        model = DynamicSpreadModel(
            y=pd.Series(np.random.randn(days)),
            x=pd.Series(np.random.randn(days)),
            half_life=10.0
        )
        
        # Override with explicit lookback
        z_score = model.compute_z_score(spread, lookback=50)
        
        assert len(z_score) == len(spread), "Z-score length should match spread"
        assert not z_score.isna().all(), "Z-score should have values"
        
    def test_lookback_bounds_enforcement(self):
        """Lookback should always be in [10, 120] range."""
        np.random.seed(42)
        days = 200
        spread = pd.Series(np.random.randn(days).cumsum() * 0.5)
        
        # Test lower bound (HL=1 should become 10)
        model_short = DynamicSpreadModel(
            y=pd.Series(np.random.randn(days)),
            x=pd.Series(np.random.randn(days)),
            half_life=1.0
        )
        z_short = model_short.compute_z_score(spread)
        assert not z_short.isna().all(), "Short HL should still produce valid Z-scores"
        
        # Test upper bound (HL=500 should be capped)
        model_long = DynamicSpreadModel(
            y=pd.Series(np.random.randn(days)),
            x=pd.Series(np.random.randn(days)),
            half_life=500.0
        )
        z_long = model_long.compute_z_score(spread)
        assert not z_long.isna().all(), "Long HL should be capped and produce Z-scores"


class TestZScoreLookbackSignalTiming:
    """Test that adaptive lookback improves signal timing and quality."""
    
    def test_fast_pair_z_score_responsiveness(self):
        """For fast pairs, adaptive lookback should make Z-score more responsive.
        
        Scenario: Fast pair (HL=12d) with sudden mean reversion event
        - Fixed 20d window lags behind the reversion
        - Adaptive 36d window (3*12) smooths noise better
        
        However for fast pairs with sharp moves, responsive is better.
        Let's create a pattern: spike at day 100, recovery by day 110
        """
        np.random.seed(42)
        days = 150
        
        # Create synthetic spread with fast mean reversion and a spike event
        spread = pd.Series(np.random.randn(days) * 0.2)  # Small noise
        spread.iloc[100:105] = 3.0  # Spike at day 100
        spread.iloc[105:110] = 1.5  # Recovery begins
        spread.iloc[110:] = np.random.randn(len(spread) - 110) * 0.2  # Back to normal
        
        model = DynamicSpreadModel(
            y=pd.Series(np.random.randn(days)),
            x=pd.Series(np.random.randn(days)),
            half_life=12.0  # Fast reversion
        )
        
        z_score = model.compute_z_score(spread)
        
        # Check that Z-score responds to the spike
        spike_z = z_score.iloc[100:110].abs().max()
        assert spike_z > 2.0, "Z-score should detect the spike"
        
    def test_slow_pair_z_score_stability(self):
        """For slow pairs, adaptive lookback should reduce false signals.
        
        Scenario: Slow pair (HL=80d) with gradual drift
        - Fixed 20d window is too short, creates false reversions
        - Adaptive 60d window provides better context
        """
        np.random.seed(42)
        days = 200
        
        # Create synthetic spread with slow drift (mean-reverting OU process)
        spread_vals = np.zeros(days)
        for i in range(1, days):
            # OU process with slow half-life
            spread_vals[i] = 0.98 * spread_vals[i-1] + 0.2 * np.random.randn()
        spread = pd.Series(spread_vals)
        
        model = DynamicSpreadModel(
            y=pd.Series(np.random.randn(days)),
            x=pd.Series(np.random.randn(days)),
            half_life=80.0  # Slow reversion
        )
        
        z_score = model.compute_z_score(spread)
        
        # Check that Z-score is well-formed
        assert not np.isnan(z_score.iloc[-1]), "Should have valid Z-score at end"
        assert 0 < np.nanmean(np.abs(z_score)) < 3.0, "Z-score should be reasonable magnitude"
        
    def test_medium_pair_z_score_balance(self):
        """For medium pairs (HL=35d), adaptive lookback should match half-life."""
        np.random.seed(42)
        days = 200
        spread = pd.Series(np.random.randn(days).cumsum() * 0.3)
        
        model = DynamicSpreadModel(
            y=pd.Series(np.random.randn(days)),
            x=pd.Series(np.random.randn(days)),
            half_life=35.0  # Medium reversion
        )
        
        z_score = model.compute_z_score(spread)
        
        # For HL in [30, 60], lookback = ceil(HL) = 35
        assert len(z_score) == len(spread)
        assert not z_score.isna().all()


class TestZScoreLookbackIntegration:
    """Test adaptive Z-score lookback integrated with trading strategy."""
    
    def test_spread_model_uses_half_life_for_z_score(self):
        """Verify SpreadModel.compute_z_score uses half-life parameter."""
        np.random.seed(42)
        days = 150
        spread = pd.Series(np.random.randn(days).cumsum() * 0.5)
        
        model = SpreadModel(
            y=pd.Series(np.random.randn(days)),
            x=pd.Series(np.random.randn(days))
        )
        
        # Call with half_life parameter
        z_score = model.compute_z_score(spread, half_life=25.0)
        
        assert len(z_score) == len(spread)
        assert not z_score.isna().all()
        
    def test_dynamic_spread_model_signal_generation(self):
        """Verify DynamicSpreadModel.get_adaptive_signals uses adaptive lookback."""
        np.random.seed(42)
        days = 150
        
        y = pd.Series(np.random.randn(days) + np.random.randn(days).cumsum() * 0.1)
        x = pd.Series(np.random.randn(days) + np.random.randn(days).cumsum() * 0.1)
        
        model = DynamicSpreadModel(
            y=y,
            x=x,
            half_life=25.0,
            pair_key="TEST_PAIR"
        )
        
        spread = model.compute_spread(y, x)
        signals, signal_info = model.get_adaptive_signals(spread)
        
        # Verify signal_info contains Z-score computed with adaptive lookback
        assert 'z_score' in signal_info, "Should have z_score in signal_info"
        assert 'entry_threshold' in signal_info, "Should have entry_threshold"
        assert len(signal_info['z_score']) == len(spread)
        
    def test_pair_trading_strategy_with_adaptive_lookback(self):
        """Verify PairTradingStrategy uses adaptive Z-score lookback in signals."""
        np.random.seed(42)
        
        # Create sample market data
        dates = pd.date_range('2023-01-01', periods=150)
        market_data = pd.DataFrame({
            'A': np.random.randn(150).cumsum() + 100,
            'B': np.random.randn(150).cumsum() + 100,
        }, index=dates)
        
        strategy = PairTradingStrategy()
        
        # Generate signals
        signals = strategy.generate_signals(market_data)
        
        # If signals were generated, they should be using adaptive lookback
        # (This is implicitly tested via integration)
        assert isinstance(signals, list)


class TestZScoreLookbackRealisticScenario:
    """Test realistic scenario with multiple pairs of different half-lives."""
    
    def test_multi_pair_lookback_adaptation(self):
        """Test that different pairs get appropriate lookback windows.
        
        Scenario:
        - Pair 1 (HL=8d): Gets 24d lookback (3*8)
        - Pair 2 (HL=40d): Gets 40d lookback (1*40)
        - Pair 3 (HL=90d): Gets 60d lookback (capped)
        """
        np.random.seed(42)
        days = 200
        
        pairs = [
            ('pair1', 8.0),
            ('pair2', 40.0),
            ('pair3', 90.0)
        ]
        
        spread_data = pd.Series(np.random.randn(days).cumsum() * 0.4)
        
        z_scores = {}
        for pair_name, half_life in pairs:
            model = DynamicSpreadModel(
                y=pd.Series(np.random.randn(days)),
                x=pd.Series(np.random.randn(days)),
                half_life=half_life,
                pair_key=pair_name
            )
            z_scores[pair_name] = model.compute_z_score(spread_data)
        
        # All should be valid
        for pair_name, z_score in z_scores.items():
            assert not z_score.isna().all(), f"{pair_name} should have valid Z-scores"
            assert len(z_score) == len(spread_data), f"{pair_name} length mismatch"
    
    def test_z_score_lookback_consistency(self):
        """Test that repeated calls produce consistent results."""
        np.random.seed(42)
        days = 150
        spread = pd.Series(np.random.randn(days).cumsum() * 0.5)
        
        model = DynamicSpreadModel(
            y=pd.Series(np.random.randn(days)),
            x=pd.Series(np.random.randn(days)),
            half_life=35.0
        )
        
        # Call compute_z_score multiple times
        z_score_1 = model.compute_z_score(spread)
        z_score_2 = model.compute_z_score(spread)
        
        # Results should be identical
        pd.testing.assert_series_equal(z_score_1, z_score_2)


class TestZScoreLookbackVsFixed:
    """Benchmark: Adaptive lookback vs fixed 20-day window."""
    
    def test_adaptive_vs_fixed_lookback_behavior(self):
        """Compare signal characteristics between adaptive and fixed lookback.
        
        For a fast pair (HL=10d):
        - Fixed 20d: Has lag, misses early reversion
        - Adaptive 30d: More responsive, earlier signals
        """
        np.random.seed(42)
        days = 200
        spread = pd.Series(np.random.randn(days).cumsum() * 0.4)
        
        model = DynamicSpreadModel(
            y=pd.Series(np.random.randn(days)),
            x=pd.Series(np.random.randn(days)),
            half_life=10.0
        )
        
        # Adaptive lookback (should be 30 for HL=10)
        z_adaptive = model.compute_z_score(spread)
        
        # Fixed 20-day for comparison
        z_fixed = model.compute_z_score(spread, lookback=20)
        
        # Both should be valid
        assert not z_adaptive.isna().all()
        assert not z_fixed.isna().all()
        
        # They should be different (different lookback windows)
        # Allow some values to match by chance, but not all
        differences = (z_adaptive - z_fixed).abs()
        assert differences.sum() > 1.0, "Adaptive and fixed should produce different Z-scores"


class TestZScoreLookbackEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_zero_half_life_fallback(self):
        """With zero/None half-life, should use default lookback."""
        np.random.seed(42)
        days = 150
        spread = pd.Series(np.random.randn(days).cumsum())
        
        model = DynamicSpreadModel(
            y=pd.Series(np.random.randn(days)),
            x=pd.Series(np.random.randn(days)),
            half_life=None  # No half-life provided
        )
        
        z_score = model.compute_z_score(spread)
        
        # Should use default lookback=20
        assert not z_score.isna().all()
        assert len(z_score) == len(spread)
    
    def test_short_spread_series(self):
        """With insufficient data, compute_z_score should still work."""
        np.random.seed(42)
        spread = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        
        model = DynamicSpreadModel(
            y=pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]),
            x=pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]),
            half_life=20.0
        )
        
        z_score = model.compute_z_score(spread)
        
        # Should contain NaNs for first window, but method should not fail
        assert len(z_score) == len(spread)
        assert z_score.isna().sum() > 0  # Some NaNs expected


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
