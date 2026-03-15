"""
Tests for signal_engine.combiner ÔÇö SignalCombiner + SignalSource (v31 Etape 3).

Covers:
    - SignalSource validation
    - Composite score computation (weighted average)
    - Direction resolution (long/short/exit/none)
    - Multi-source combining
    - Source management (add/remove/enable/disable)
    - Edge cases (empty, single source, missing scores, all disabled)
    - Confidence calculation
    - Config integration
"""

import pytest

from signal_engine.combiner import SignalCombiner, SignalSource, CompositeSignal


# ---------------------------------------------------------------------------
# TestSignalSource
# ---------------------------------------------------------------------------

class TestSignalSource:
    """Tests for SignalSource dataclass."""

    def test_valid_creation(self):
        s = SignalSource(name="zscore", weight=0.70)
        assert s.name == "zscore"
        assert s.weight == 0.70
        assert s.enabled is True

    def test_disabled_source(self):
        s = SignalSource(name="momentum", weight=0.30, enabled=False)
        assert s.enabled is False

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError, match="weight"):
            SignalSource(name="bad", weight=-0.1)

    def test_zero_weight_allowed(self):
        s = SignalSource(name="placeholder", weight=0.0)
        assert s.weight == 0.0


# ---------------------------------------------------------------------------
# TestCompositeScore
# ---------------------------------------------------------------------------

class TestCompositeScore:
    """Tests for composite score computation."""

    def test_single_source_passthrough(self):
        """Single source -> composite equals the raw score."""
        combiner = SignalCombiner(
            sources=[SignalSource("zscore", weight=1.0)],
            entry_threshold=0.5,
        )
        result = combiner.combine({"zscore": 0.8})
        assert abs(result.composite_score - 0.8) < 1e-10

    def test_two_sources_weighted_average(self):
        """Two sources -> weighted average."""
        combiner = SignalCombiner(
            sources=[
                SignalSource("zscore", weight=0.70),
                SignalSource("momentum", weight=0.30),
            ],
            entry_threshold=0.5,
        )
        result = combiner.combine({"zscore": 1.0, "momentum": 0.0})
        # Expected: (0.70 * 1.0 + 0.30 * 0.0) / 1.0 = 0.70
        assert abs(result.composite_score - 0.70) < 1e-10

    def test_equal_weight_average(self):
        """Equal weights -> simple average."""
        combiner = SignalCombiner(
            sources=[
                SignalSource("a", weight=1.0),
                SignalSource("b", weight=1.0),
            ],
            entry_threshold=0.5,
        )
        result = combiner.combine({"a": 0.6, "b": 0.4})
        assert abs(result.composite_score - 0.5) < 1e-10

    def test_score_clamped_to_range(self):
        """Scores outside [-1, 1] are clamped."""
        combiner = SignalCombiner(
            sources=[SignalSource("zscore", weight=1.0)],
            entry_threshold=0.5,
        )
        result = combiner.combine({"zscore": 5.0})
        assert result.composite_score == 1.0

        result = combiner.combine({"zscore": -3.0})
        assert result.composite_score == -1.0

    def test_missing_source_excluded(self):
        """Missing source is skipped, not counted in denominator."""
        combiner = SignalCombiner(
            sources=[
                SignalSource("zscore", weight=0.70),
                SignalSource("momentum", weight=0.30),
            ],
            entry_threshold=0.5,
        )
        # Only provide zscore
        result = combiner.combine({"zscore": 0.8})
        # Composite = 0.80 (only zscore counted)
        assert abs(result.composite_score - 0.8) < 1e-10
        assert "momentum" not in result.source_scores

    def test_opposing_signals_cancel(self):
        """Opposing signals with equal weight cancel out."""
        combiner = SignalCombiner(
            sources=[
                SignalSource("a", weight=1.0),
                SignalSource("b", weight=1.0),
            ],
            entry_threshold=0.5,
        )
        result = combiner.combine({"a": 0.8, "b": -0.8})
        assert abs(result.composite_score) < 1e-10


# ---------------------------------------------------------------------------
# TestDirection
# ---------------------------------------------------------------------------

class TestDirection:
    """Tests for direction resolution."""

    def test_long_above_threshold(self):
        combiner = SignalCombiner(
            sources=[SignalSource("z", weight=1.0)],
            entry_threshold=0.5,
        )
        result = combiner.combine({"z": 0.7})
        assert result.direction == "long"

    def test_short_below_negative_threshold(self):
        combiner = SignalCombiner(
            sources=[SignalSource("z", weight=1.0)],
            entry_threshold=0.5,
        )
        result = combiner.combine({"z": -0.7})
        assert result.direction == "short"

    def test_none_within_thresholds(self):
        combiner = SignalCombiner(
            sources=[SignalSource("z", weight=1.0)],
            entry_threshold=0.5,
            exit_threshold=0.2,
        )
        result = combiner.combine({"z": 0.3}, in_position=False)
        assert result.direction == "none"

    def test_exit_near_zero_in_position(self):
        combiner = SignalCombiner(
            sources=[SignalSource("z", weight=1.0)],
            entry_threshold=0.5,
            exit_threshold=0.2,
        )
        result = combiner.combine({"z": 0.1}, in_position=True)
        assert result.direction == "exit"

    def test_no_exit_when_not_in_position(self):
        combiner = SignalCombiner(
            sources=[SignalSource("z", weight=1.0)],
            entry_threshold=0.5,
            exit_threshold=0.2,
        )
        result = combiner.combine({"z": 0.1}, in_position=False)
        assert result.direction == "none"

    def test_threshold_boundary_long(self):
        """Exactly at entry_threshold should NOT trigger (strictly >)."""
        combiner = SignalCombiner(
            sources=[SignalSource("z", weight=1.0)],
            entry_threshold=0.5,
        )
        result = combiner.combine({"z": 0.5})
        assert result.direction == "none"

    def test_threshold_boundary_exit(self):
        """At exit_threshold boundary should trigger exit."""
        combiner = SignalCombiner(
            sources=[SignalSource("z", weight=1.0)],
            entry_threshold=0.5,
            exit_threshold=0.2,
        )
        result = combiner.combine({"z": 0.2}, in_position=True)
        assert result.direction == "exit"


# ---------------------------------------------------------------------------
# TestSourceManagement
# ---------------------------------------------------------------------------

class TestSourceManagement:
    """Tests for source add/remove/enable/disable."""

    def test_add_source(self):
        combiner = SignalCombiner(sources=[])
        combiner.add_source(SignalSource("x", weight=1.0))
        assert "x" in combiner.active_sources

    def test_remove_source(self):
        combiner = SignalCombiner(
            sources=[SignalSource("a", weight=1.0), SignalSource("b", weight=0.5)],
        )
        removed = combiner.remove_source("a")
        assert removed is True
        assert "a" not in combiner.active_sources

    def test_remove_nonexistent(self):
        combiner = SignalCombiner(sources=[])
        removed = combiner.remove_source("nope")
        assert removed is False

    def test_disable_source(self):
        combiner = SignalCombiner(
            sources=[SignalSource("a", weight=1.0)],
        )
        combiner.set_source_enabled("a", False)
        assert "a" not in combiner.active_sources
        # Disabled source ignored in computation
        result = combiner.combine({"a": 0.9})
        assert result.composite_score == 0.0
        assert result.direction == "none"

    def test_total_weight(self):
        combiner = SignalCombiner(
            sources=[
                SignalSource("a", weight=0.70),
                SignalSource("b", weight=0.30),
            ],
        )
        assert abs(combiner.total_weight - 1.0) < 1e-10


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge case tests."""

    def test_no_sources_returns_none(self):
        combiner = SignalCombiner(sources=[], entry_threshold=0.5)
        result = combiner.combine({"z": 0.9})
        assert result.direction == "none"
        assert result.confidence == 0.0

    def test_empty_scores_returns_none(self):
        combiner = SignalCombiner(
            sources=[SignalSource("z", weight=1.0)],
            entry_threshold=0.5,
        )
        result = combiner.combine({})
        assert result.direction == "none"
        assert result.confidence == 0.0

    def test_all_disabled_returns_none(self):
        combiner = SignalCombiner(
            sources=[SignalSource("z", weight=1.0, enabled=False)],
            entry_threshold=0.5,
        )
        result = combiner.combine({"z": 0.9})
        assert result.direction == "none"

    def test_entry_threshold_validation(self):
        with pytest.raises(ValueError, match="entry_threshold"):
            SignalCombiner(entry_threshold=0)

    def test_exit_threshold_validation(self):
        with pytest.raises(ValueError, match="exit_threshold"):
            SignalCombiner(exit_threshold=-1)

    def test_exit_gte_entry_validation(self):
        with pytest.raises(ValueError, match="exit_threshold"):
            SignalCombiner(entry_threshold=0.5, exit_threshold=0.5)


# ---------------------------------------------------------------------------
# TestConfidence
# ---------------------------------------------------------------------------

class TestConfidence:
    """Tests for confidence calculation."""

    def test_full_confidence_all_sources(self):
        combiner = SignalCombiner(
            sources=[
                SignalSource("a", weight=0.70),
                SignalSource("b", weight=0.30),
            ],
        )
        result = combiner.combine({"a": 0.5, "b": 0.5})
        assert abs(result.confidence - 1.0) < 1e-10

    def test_partial_confidence_missing_source(self):
        combiner = SignalCombiner(
            sources=[
                SignalSource("a", weight=0.70),
                SignalSource("b", weight=0.30),
            ],
        )
        result = combiner.combine({"a": 0.5})
        assert abs(result.confidence - 0.70) < 1e-10

    def test_confidence_reflects_weights(self):
        combiner = SignalCombiner(
            sources=[
                SignalSource("a", weight=0.50),
                SignalSource("b", weight=0.30),
                SignalSource("c", weight=0.20),
            ],
        )
        result = combiner.combine({"a": 0.5, "c": 0.5})
        # Available weight: 0.50 + 0.20 = 0.70 out of 1.0
        assert abs(result.confidence - 0.70) < 1e-10


# ---------------------------------------------------------------------------
# TestConfigIntegration
# ---------------------------------------------------------------------------

class TestConfigIntegration:
    """Tests for SignalCombinerConfig in settings."""

    def test_combiner_config_exists(self):
        from config.settings import SignalCombinerConfig
        cfg = SignalCombinerConfig()
        assert cfg.enabled is True
        assert cfg.zscore_weight == 0.70
        assert cfg.momentum_weight == 0.30
        assert cfg.entry_threshold == 0.6
        assert cfg.exit_threshold == 0.2

    def test_settings_has_signal_combiner(self):
        from config.settings import Settings
        Settings._instance = None
        s = Settings()
        assert hasattr(s, 'signal_combiner')
        assert s.signal_combiner.enabled is True
        Settings._instance = None


# ---------------------------------------------------------------------------
# TestDefaultSources
# ---------------------------------------------------------------------------

class TestDefaultSources:
    """Tests for default v31 source configuration."""

    def test_default_sources_zscore_momentum(self):
        """Default combiner has zscore (0.70) + momentum (0.30)."""
        combiner = SignalCombiner()
        names = combiner.active_sources
        assert "zscore" in names
        assert "momentum" in names
        assert abs(combiner.total_weight - 1.0) < 1e-10

    def test_strong_zscore_confirmed_by_momentum(self):
        """Both sources agree -> composite exceeds entry threshold."""
        combiner = SignalCombiner(entry_threshold=0.6)
        result = combiner.combine({"zscore": -0.9, "momentum": -0.7})
        # Composite = 0.70 * -0.9 + 0.30 * -0.7 = -0.84
        assert result.direction == "short"
        assert result.composite_score < -0.6

    def test_strong_zscore_contradicted_by_momentum(self):
        """Zscore strong but momentum disagrees -> might still enter."""
        combiner = SignalCombiner(entry_threshold=0.6)
        result = combiner.combine({"zscore": -0.9, "momentum": 0.5})
        # Composite = 0.70 * -0.9 + 0.30 * 0.5 = -0.48
        assert result.direction == "none"  # Below threshold

    def test_medium_zscore_boosted_by_momentum(self):
        """Medium zscore + confirming momentum crosses threshold."""
        combiner = SignalCombiner(entry_threshold=0.6)
        result = combiner.combine({"zscore": 0.7, "momentum": 0.8})
        # Composite = 0.70 * 0.7 + 0.30 * 0.8 = 0.73
        assert result.direction == "long"
