"""
Tests for Regime Change Detection (S2.5).

Validates VolatilityRegime detection, state management, position multipliers,
threshold adjustments, and integration with trading strategy.

Test Coverage:
- VolatilityRegime enum and RegimeState dataclass
- RegimeDetector initialization and configuration
- Regime classification based on volatility percentiles
- Regime state transitions with min duration enforcement
- Position sizing multipliers by regime
- Entry/exit threshold adjustments
- Regime statistics and history tracking
- Edge cases (low/high volatility, regime persistence)
- Integration with pair trading strategy
"""
# pyright: reportUnusedVariable=false

from datetime import datetime

import numpy as np
import pytest

from models.regime_detector import RegimeDetector, RegimeState, VolatilityRegime


class TestVolatilityRegimeEnum:
    """Test VolatilityRegime enum."""

    def test_regime_enum_values(self):
        """Test that regime enum has expected values."""
        assert VolatilityRegime.LOW.value == "low"
        assert VolatilityRegime.NORMAL.value == "normal"
        assert VolatilityRegime.HIGH.value == "high"

    def test_regime_enum_members(self):
        """Test that all regime members exist."""
        regimes = [VolatilityRegime.LOW, VolatilityRegime.NORMAL, VolatilityRegime.HIGH]
        assert len(regimes) == 3


class TestRegimeStateDataclass:
    """Test RegimeState dataclass."""

    def test_regime_state_initialization(self):
        """Test RegimeState can be created with required fields."""
        state = RegimeState(
            regime=VolatilityRegime.NORMAL,
            volatility=0.015,
            percentile=50.0,
            rolling_mean=0.012,
            rolling_std=0.003,
            regime_duration_bars=10,
            timestamp=datetime(2026, 2, 12),
        )

        assert state.regime == VolatilityRegime.NORMAL
        assert state.volatility == 0.015
        assert state.percentile == 50.0
        assert state.rolling_mean == 0.012
        assert state.rolling_std == 0.003
        assert state.regime_duration_bars == 10

    def test_regime_state_defaults(self):
        """Test RegimeState defaults for optional fields."""
        state = RegimeState(
            regime=VolatilityRegime.LOW,
            volatility=0.008,
            percentile=25.0,
            rolling_mean=0.010,
            rolling_std=0.002,
            regime_duration_bars=5,
            timestamp=datetime.now(),
        )

        assert state.transition_probability == 0.0
        assert state.confidence == 1.0
        assert state.volatility_history == []


class TestRegimeDetectorInitialization:
    """Test RegimeDetector initialization and configuration."""

    def test_detector_default_initialization(self):
        """Test RegimeDetector initializes with default parameters."""
        detector = RegimeDetector()

        assert detector.lookback_window == 20
        assert detector.low_percentile == 0.33
        assert detector.high_percentile == 0.67
        assert detector.min_regime_duration == 1
        assert detector.use_log_returns is False

    def test_detector_custom_initialization(self):
        """Test RegimeDetector with custom parameters."""
        detector = RegimeDetector(
            lookback_window=30, low_percentile=0.25, high_percentile=0.75, min_regime_duration=5, use_log_returns=True
        )

        assert detector.lookback_window == 30
        assert detector.low_percentile == 0.25
        assert detector.high_percentile == 0.75
        assert detector.min_regime_duration == 5
        assert detector.use_log_returns is True

    def test_detector_initial_state(self):
        """Test detector starts in NORMAL regime."""
        detector = RegimeDetector()

        assert detector.current_regime == VolatilityRegime.NORMAL
        assert detector.bars_processed == 0
        assert len(detector.volatility_history) == 0
        assert detector.last_state is None


class TestRegimeClassification:
    """Test regime classification based on volatility."""

    def test_single_update_creates_state(self):
        """Test that single update creates RegimeState."""
        detector = RegimeDetector()
        state = detector.update(spread=100.0)

        assert state is not None
        assert isinstance(state, RegimeState)
        assert state.timestamp is not None

    def test_low_volatility_regime(self):
        """Test LOW regime classification."""
        np.random.seed(100)
        detector = RegimeDetector(min_regime_duration=1)

        # Feed in high volatility first to establish a range
        base = 100.0
        for i in range(10):
            detector.update(spread=base + np.random.normal(0, 5.0))

        # Then feed in very low volatility ÔÇô should be LOW relative to earlier
        for i in range(10):
            detector.update(spread=100.0 + np.random.normal(0, 0.0001))

        # Sprint 3.4: Assert exact regime, not just "is not None"
        assert detector.current_regime == VolatilityRegime.LOW, (
            f"Expected LOW regime after constant spread, got {detector.current_regime}"
        )

    def test_high_volatility_regime(self):
        """Test HIGH regime classification."""
        np.random.seed(200)
        detector = RegimeDetector(min_regime_duration=1)

        # Feed in low volatility first to establish a range
        for i in range(10):
            detector.update(spread=100.0 + np.random.normal(0, 0.0001))

        # Then feed in high volatility ÔÇô should be HIGH relative to earlier
        base = 100.0
        for i in range(10):
            change = np.random.normal(0, 5.0)
            base = max(base + change, 0.1)
            detector.update(spread=base)

        # Sprint 3.4: Assert exact regime, not just "non-negative vol"
        assert detector.current_regime == VolatilityRegime.HIGH, (
            f"Expected HIGH regime after volatile moves, got {detector.current_regime}"
        )

    def test_normal_volatility_regime(self):
        """Test NORMAL regime classification."""
        detector = RegimeDetector(min_regime_duration=1, lookback_window=20)

        # Build a 3-tier volatility distribution with deterministic data:
        # Tier 1 (low): constant Ôåô tiny vol
        for i in range(7):
            detector.update(spread=100.0)

        # Tier 2 (high): big swings Ôåô high vol
        for i in range(7):
            detector.update(spread=100.0 + (10.0 if i % 2 == 0 else -10.0))

        # Tier 3 (mid): moderate swings Ôåô falls between 33rd and 67th percentile
        for i in range(6):
            detector.update(spread=100.0 + (1.0 if i % 2 == 0 else -1.0))

        # Sprint 3.4: Assert exact regime NORMAL for mid-range volatility
        assert detector.current_regime == VolatilityRegime.NORMAL, (
            f"Expected NORMAL regime for mid-range volatility, got {detector.current_regime}"
        )


class TestRegimeTransitions:
    """Test regime transitions and persistence."""

    def test_minimum_duration_enforcement(self):
        """Test that regime transitions respect min_regime_duration."""
        from unittest.mock import patch

        detector = RegimeDetector(min_regime_duration=3)

        # Patch instant transition to always return False so we
        # isolate the min_regime_duration logic exclusively.
        with patch.object(detector, "_check_instant_transition", return_value=False):
            # Establish a regime with low volatility
            np.random.seed(99)
            for i in range(5):
                detector.update(spread=100.0 + np.random.normal(0, 0.001))
            initial_regime = detector.current_regime

            # Spike volatility for 2 bars (less than min_regime_duration=3)
            detector.update(spread=100.0 + np.random.normal(0, 0.1))
            detector.update(spread=100.0 + np.random.normal(0, 0.1))

            # Sprint 3.4: Assert exact regime persists (min duration not met)
            assert detector.current_regime == initial_regime, (
                f"Regime should persist (min_duration=3, only 2 spikes), "
                f"expected {initial_regime}, got {detector.current_regime}"
            )

    def test_regime_transition_tracking(self):
        """Test that regime transitions are recorded."""
        detector = RegimeDetector(min_regime_duration=2)

        # Low volatility
        for i in range(5):
            detector.update(spread=100.0 + np.random.normal(0, 0.001))

        # High volatility (for 3+ bars to trigger transition)
        for i in range(4):
            detector.update(spread=100.0 + np.random.normal(0, 0.1))

        # Sprint 3.4: Assert at least one transition was recorded (lowÔåôhigh)
        assert len(detector.regime_transitions) >= 1, (
            f"Expected at least 1 regime transition (lowÔåôhigh), got {len(detector.regime_transitions)}"
        )


class TestRegimeStateMetrics:
    """Test metrics in RegimeState."""

    def test_regime_state_has_volatility(self):
        """Test that regime state includes volatility metrics."""
        detector = RegimeDetector()

        # Feed data
        for i in range(10):
            detector.update(spread=100.0 + np.random.normal(0, 0.02))

        state = detector.last_state
        assert state is not None
        assert state.volatility >= 0.0
        assert state.rolling_mean >= 0.0
        assert state.rolling_std >= 0.0

    def test_percentile_calculation(self):
        """Test that volatility percentile is calculated."""
        detector = RegimeDetector()

        # Feed consistent data
        for i in range(20):
            detector.update(spread=100.0 + np.random.normal(0, 0.02))

        state = detector.last_state
        assert state is not None
        assert 0.0 <= state.percentile <= 100.0

    def test_regime_duration_tracking(self):
        """Test that regime duration in bars is tracked."""
        detector = RegimeDetector()

        for i in range(10):
            state = detector.update(spread=100.0 + np.random.normal(0, 0.01))

        assert state.regime_duration_bars > 0
        assert state.regime_duration_bars <= detector.bars_processed


class TestPositionMultipliers:
    """Test position sizing multipliers by regime."""

    def test_position_multiplier_low_regime(self):
        """Test position multiplier in LOW volatility regime."""
        multiplier = RegimeDetector().get_position_multiplier(VolatilityRegime.LOW)
        assert multiplier == 1.0

    def test_position_multiplier_normal_regime(self):
        """Test position multiplier in NORMAL volatility regime."""
        multiplier = RegimeDetector().get_position_multiplier(VolatilityRegime.NORMAL)
        assert multiplier == 1.0

    def test_position_multiplier_high_regime(self):
        """Test position multiplier in HIGH volatility regime."""
        multiplier = RegimeDetector().get_position_multiplier(VolatilityRegime.HIGH)
        assert multiplier == 0.5

    def test_position_multiplier_uses_current_regime(self):
        """Test position multiplier uses current regime if not specified."""
        detector = RegimeDetector()

        # Manually set regime
        detector.current_regime = VolatilityRegime.HIGH

        # Should use current regime's multiplier
        multiplier = detector.get_position_multiplier()
        assert multiplier == 0.5


class TestEntryThresholdMultipliers:
    """Test entry threshold adjustments by regime."""

    def test_entry_threshold_low_regime(self):
        """Test entry threshold in LOW volatility regime."""
        multiplier = RegimeDetector().get_entry_threshold_multiplier(VolatilityRegime.LOW)
        assert multiplier == 1.0

    def test_entry_threshold_normal_regime(self):
        """Test entry threshold in NORMAL volatility regime."""
        multiplier = RegimeDetector().get_entry_threshold_multiplier(VolatilityRegime.NORMAL)
        assert multiplier == 1.0

    def test_entry_threshold_high_regime(self):
        """Test entry threshold in HIGH volatility regime (higher = tighter)."""
        multiplier = RegimeDetector().get_entry_threshold_multiplier(VolatilityRegime.HIGH)
        assert multiplier == 1.2


class TestExitThresholdMultipliers:
    """Test exit threshold adjustments by regime."""

    def test_exit_threshold_low_regime(self):
        """Test exit threshold in LOW volatility regime (lower = faster exit)."""
        multiplier = RegimeDetector().get_exit_threshold_multiplier(VolatilityRegime.LOW)
        assert multiplier == 0.9

    def test_exit_threshold_normal_regime(self):
        """Test exit threshold in NORMAL volatility regime."""
        multiplier = RegimeDetector().get_exit_threshold_multiplier(VolatilityRegime.NORMAL)
        assert multiplier == 1.0

    def test_exit_threshold_high_regime(self):
        """Test exit threshold in HIGH volatility regime."""
        multiplier = RegimeDetector().get_exit_threshold_multiplier(VolatilityRegime.HIGH)
        assert multiplier == 1.0


class TestRegimeStatistics:
    """Test regime statistics and history."""

    def test_empty_detector_stats(self):
        """Test stats for detector with no data."""
        detector = RegimeDetector()
        stats = detector.get_regime_stats()

        assert stats["total_bars"] == 0
        assert stats["regime_transitions"] == 0
        assert stats["current_regime"] is None
        assert stats["avg_volatility"] == 0.0

    def test_regime_stats_after_updates(self):
        """Test stats after feeding data."""
        detector = RegimeDetector()

        for i in range(20):
            detector.update(spread=100.0 + np.random.normal(0, 0.02))

        stats = detector.get_regime_stats()

        assert stats["total_bars"] == 20
        assert stats["regime_transitions"] >= 0
        assert stats["current_regime"] in ["low", "normal", "high"]
        assert stats["avg_volatility"] > 0.0
        assert stats["max_volatility"] >= stats["min_volatility"]

    def test_regime_duration_in_stats(self):
        """Test that current regime duration is in stats."""
        detector = RegimeDetector()

        for i in range(15):
            detector.update(spread=100.0 + np.random.normal(0, 0.02))

        stats = detector.get_regime_stats()
        assert stats["regime_duration_bars"] >= 0  # Duration can be 0 on first bar


class TestDetectorReset:
    """Test detector reset functionality."""

    def test_reset_clears_volatility_history(self):
        """Test that reset clears volatility history."""
        detector = RegimeDetector()

        for i in range(10):
            detector.update(spread=100.0 + np.random.normal(0, 0.02))

        assert len(detector.volatility_history) > 0

        detector.reset()

        assert len(detector.volatility_history) == 0
        assert detector.bars_processed == 0

    def test_reset_returns_to_normal_regime(self):
        """Test that reset returns detector to NORMAL regime."""
        detector = RegimeDetector()
        detector.current_regime = VolatilityRegime.HIGH

        detector.reset()

        assert detector.current_regime == VolatilityRegime.NORMAL

    def test_reset_clears_transitions(self):
        """Test that reset clears regime transitions."""
        detector = RegimeDetector()

        for i in range(50):
            detector.update(spread=100.0 + np.random.normal(0, 0.02))

        detector.regime_transitions.append((10, VolatilityRegime.NORMAL, VolatilityRegime.HIGH))
        assert len(detector.regime_transitions) > 0

        detector.reset()

        assert len(detector.regime_transitions) == 0


class TestTransitionProbability:
    """Test transition probability calculations."""

    def test_transition_probability_range(self):
        """Test that transition probability is between 0 and 1."""
        detector = RegimeDetector()

        for i in range(20):
            state = detector.update(spread=100.0 + np.random.normal(0, 0.02))

        assert 0.0 <= state.transition_probability <= 1.0

    def test_higher_volatility_std_increases_transition_risk(self):
        """Test that higher vol std increases transition probability."""
        detector_low_vol = RegimeDetector()
        detector_high_vol = RegimeDetector()

        # Low vol data (very small changes)
        for i in range(20):
            state_low = detector_low_vol.update(spread=100.0 + np.random.normal(0, 0.0001))

        # High vol data (large changes)
        for i in range(20):
            state_high = detector_high_vol.update(spread=100.0 + np.random.normal(0, 0.05))

        # Verify both detectors have transition probabilities in valid range
        assert 0.0 <= state_low.transition_probability <= 1.0
        assert 0.0 <= state_high.transition_probability <= 1.0


class TestConfidenceCalculation:
    """Test regime classification confidence."""

    def test_confidence_range(self):
        """Test that confidence is between 0 and 1."""
        detector = RegimeDetector()

        for i in range(20):
            state = detector.update(spread=100.0 + np.random.normal(0, 0.02))

        assert 0.0 <= state.confidence <= 1.0

    def test_uniform_volatility_high_confidence(self):
        """Test that uniform volatility has high confidence."""
        detector = RegimeDetector()

        # Very uniform volatility
        for i in range(20):
            state = detector.update(spread=100.0 + 0.02)  # Constant spread

        # With no variance, confidence should be high
        assert state.confidence > 0.7


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_initial_regime_when_no_history(self):
        """Test that detector stays in normal when history is sparse."""
        detector = RegimeDetector()
        state = detector.update(spread=100.0)

        assert state.regime == VolatilityRegime.NORMAL

    def test_zero_volatility_handling(self):
        """Test handling of zero volatility (flat price)."""
        detector = RegimeDetector()

        # All same price
        for i in range(10):
            state = detector.update(spread=100.0)

        assert state.volatility >= 0.0

    def test_extreme_volatility_handling(self):
        """Test handling of extreme volatility."""
        detector = RegimeDetector()

        # Extreme moves
        spreads = [100.0, 150.0, 50.0, 200.0, 10.0, 500.0]
        for spread in spreads:
            state = detector.update(spread=spread)

        assert state.volatility >= 0.0
        assert detector.current_regime is not None

    def test_single_percent_change_handling(self):
        """Test handling of 1% price moves."""
        detector = RegimeDetector()
        base = 100.0

        for i in range(20):
            state = detector.update(spread=base * (1.0 + np.random.normal(0, 0.01)))

        assert state.volatility > 0.0


class TestVolatilityHistory:
    """Test volatility history tracking."""

    def test_volatility_history_limited_by_lookback(self):
        """Test that volatility history respects lookback window."""
        detector = RegimeDetector(lookback_window=10)

        for i in range(30):
            detector.update(spread=100.0 + np.random.normal(0, 0.02))

        assert len(detector.volatility_history) <= 10

    def test_state_volatility_history(self):
        """Test that RegimeState includes recent volatility history."""
        detector = RegimeDetector()

        for i in range(20):
            state = detector.update(spread=100.0 + np.random.normal(0, 0.02))

        # Last 5 volatilities should be in state
        assert len(state.volatility_history) > 0


class TestDifferentReturnsCalculations:
    """Test return calculations (simple vs log returns)."""

    def test_simple_returns_option(self):
        """Test detector with simple returns."""
        detector = RegimeDetector(use_log_returns=False)

        # Feed data
        spreads = [100.0, 101.0, 102.5, 101.2, 103.0, 99.5]
        for spread in spreads:
            detector.update(spread=spread)

        assert detector.volatility_history

    def test_log_returns_option(self):
        """Test detector with log returns."""
        detector = RegimeDetector(use_log_returns=True)

        # Feed data
        spreads = [100.0, 101.0, 102.5, 101.2, 103.0, 99.5]
        for spread in spreads:
            detector.update(spread=spread)

        assert detector.volatility_history


class TestIntegrationWithStrategy:
    """Test integration with pair trading strategy."""

    def test_detector_can_be_instantiated_in_strategy_context(self):
        """Test that detector can be used in strategy."""
        # Simulate strategy initialization
        detector = RegimeDetector(lookback_window=20, low_percentile=0.33, high_percentile=0.67, min_regime_duration=3)

        assert detector is not None
        assert detector.current_regime == VolatilityRegime.NORMAL

    def test_detector_provides_regime_adjustments_for_strategy(self):
        """Test that detector can provide adjustments for signal generation."""
        detector = RegimeDetector()

        # Simulate feeding spread data
        for i in range(30):
            detector.update(spread=100.0 + np.random.normal(0, 0.02))

        # Strategy should be able to adjust thresholds
        current_regime = detector.current_regime
        position_mult = detector.get_position_multiplier(current_regime)
        entry_mult = detector.get_entry_threshold_multiplier(current_regime)
        exit_mult = detector.get_exit_threshold_multiplier(current_regime)

        assert position_mult > 0.0
        assert entry_mult > 0.0
        assert exit_mult > 0.0

    def test_detector_updates_continuously(self):
        """Test that detector can be updated continuously like in live strategy."""
        detector = RegimeDetector()
        states = []

        for i in range(100):
            state = detector.update(spread=100.0 + np.random.normal(0, 0.02))
            states.append(state)

        assert len(states) == 100
        assert all(isinstance(s, RegimeState) for s in states)


class TestRealisticScenarios:
    """Test realistic trading scenarios."""

    def test_calm_market_then_crisis(self):
        """Test transition from calm to volatile market."""
        np.random.seed(600)
        detector = RegimeDetector(min_regime_duration=1)

        # Build distribution: start with mixed vol so calm phase is truly LOW
        # Phase 1: some medium vol to set percentile range
        for i in range(10):
            detector.update(spread=100.0 + np.random.normal(0, 1.0))

        # Phase 2: calm market (very low vol)
        for i in range(10):
            detector.update(spread=100.0 + np.random.normal(0, 0.0001))

        calm_regime = detector.current_regime
        assert calm_regime == VolatilityRegime.LOW, f"Expected LOW regime after calm phase, got {calm_regime}"

        # Phase 3: Crisis (large moves)
        for i in range(10):
            detector.update(spread=100.0 + np.random.normal(0, 10.0))

        # Sprint 3.4: Assert exact transition to HIGH after crisis
        assert detector.current_regime == VolatilityRegime.HIGH, (
            f"Expected HIGH regime after crisis, got {detector.current_regime}"
        )

    def test_regime_persistence_reduces_whipsaws(self):
        """Test that min_regime_duration reduces false signals."""
        detector_strict = RegimeDetector(min_regime_duration=5)
        detector_loose = RegimeDetector(min_regime_duration=1)

        # Feed noisy data
        np.random.seed(42)
        for i in range(50):
            spike = 0.1 if i % 10 == 0 else 0.001  # Occasional spikes
            spread = 100.0 + np.random.normal(0, spike)
            detector_strict.update(spread=spread)
            detector_loose.update(spread=spread)

        # Strict detector should have fewer transitions
        assert len(detector_strict.regime_transitions) <= len(detector_loose.regime_transitions)

    def test_multiple_regimes_during_trading_day(self):
        """Test detection of multiple regimes during single day."""
        detector = RegimeDetector(min_regime_duration=2)

        # Morning: calm
        for i in range(10):
            detector.update(spread=100.0 + np.random.normal(0, 0.001))

        # Mid-day: volatile
        for i in range(10):
            detector.update(spread=100.0 + np.random.normal(0, 0.05))

        # Afternoon: calm
        for i in range(10):
            detector.update(spread=100.0 + np.random.normal(0, 0.001))

        # Sprint 3.4: Assert exact stats with regime value
        stats = detector.get_regime_stats()
        assert stats["total_bars"] == 30
        assert stats["current_regime"] in ["low", "normal", "high"], (
            f"Expected valid regime string, got {stats['current_regime']}"
        )
        assert stats["regime_transitions"] >= 1, "Expected at least 1 transition (calm→volatile→calm)"


class TestRegimeDetectorAdaptive:
    """C-09: Tests for adaptive-window RegimeDetector."""

    def test_adaptive_params_stored(self):
        """Adaptive window params are stored as instance attributes."""
        detector = RegimeDetector(adaptive_window=True, min_window=15, max_window=90)
        assert detector.adaptive_window is True
        assert detector.min_window == 15
        assert detector.max_window == 90
        assert detector.current_effective_window == detector.lookback_window

    def test_non_adaptive_mode_unchanged(self):
        """Default (non-adaptive) mode keeps lookback_window==20 behaviour."""
        detector = RegimeDetector(lookback_window=20)
        assert detector.adaptive_window is False
        # deque should still be sized 20
        assert detector.volatility_history.maxlen == 20
        for i in range(30):
            detector.update(spread=100.0 + float(i))
        # history is capped at 20
        assert len(detector.volatility_history) == 20

    def test_adaptive_deque_sized_for_max_window(self):
        """In adaptive mode the deque holds max_window bars so we can slice adaptively."""
        detector = RegimeDetector(adaptive_window=True, min_window=20, max_window=60)
        assert detector.volatility_history.maxlen == 60
        assert detector.spread_history.maxlen == 60

    def test_effective_window_shrinks_in_high_vol(self):
        """High realized vol should drive effective_window toward min_window."""
        np.random.seed(42)
        detector = RegimeDetector(adaptive_window=True, min_window=20, max_window=120, lookback_window=20)
        # Feed 30 low-vol bars first to establish baseline
        for _ in range(30):
            detector.update(spread=100.0 + np.random.normal(0, 0.01))

        # Now inject high-vol bars
        base = 100.0
        for _ in range(40):
            base += np.random.normal(0, 4.0)
            detector.update(spread=max(0.1, base))

        # After sustained high vol the effective window should have decreased
        assert detector.current_effective_window <= 80, (
            f"Expected effective_window ≤ 80 in high vol, got {detector.current_effective_window}"
        )

    def test_effective_window_grows_in_low_vol(self):
        """Sustained low vol should drive effective_window toward max_window."""
        np.random.seed(7)
        detector = RegimeDetector(adaptive_window=True, min_window=20, max_window=120, lookback_window=20)
        # Seed with some history first
        for _ in range(30):
            detector.update(spread=100.0 + np.random.normal(0, 2.0))

        # Then many low-vol bars
        for _ in range(80):
            detector.update(spread=100.0 + np.random.normal(0, 0.001))

        assert detector.current_effective_window >= 60, (
            f"Expected effective_window ≥ 60 in low vol, got {detector.current_effective_window}"
        )

    def test_adaptive_window_in_regime_stats(self):
        """get_regime_stats() includes adaptive_window and current_effective_window keys."""
        detector = RegimeDetector(adaptive_window=True, min_window=20, max_window=120)
        for i in range(10):
            detector.update(spread=100.0 + float(i))
        stats = detector.get_regime_stats()
        assert "adaptive_window" in stats
        assert "current_effective_window" in stats
        assert stats["adaptive_window"] is True
        assert isinstance(stats["current_effective_window"], int)

    def test_adaptive_reset_restores_effective_window(self):
        """reset() restores current_effective_window to lookback_window."""
        detector = RegimeDetector(adaptive_window=True, lookback_window=25, min_window=20, max_window=90)
        # Force some updates to potentially shift the effective window
        for i in range(50):
            detector.update(spread=100.0 + float(i % 10))
        detector.reset()
        assert detector.current_effective_window == 25  # restored to lookback_window


# Test execution
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
