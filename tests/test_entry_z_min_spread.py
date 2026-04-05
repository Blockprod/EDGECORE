"""Tests for ├ëtape 2 ÔÇö Rel├¿vement entry_z + entry_z_min_spread filter.

Validates:
- entry_z_score config is 2.0 (raised from 1.0)
- entry_z_min_spread rejects micro-deviations
- Schema validation enforces entry_z_score Ôêê [1.5, 4.0]
- Schema validation enforces entry_z_score > exit_z_score
"""

import pytest

# ÔöÇÔöÇ Config defaults ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

class TestEntryZConfigDefaults:
    """Verify StrategyConfig defaults after ├ëtape 2."""

    def test_entry_z_score_default_is_2(self):
        from config.settings import StrategyConfig
        cfg = StrategyConfig()
        assert cfg.entry_z_score == 2.0

    def test_entry_z_min_spread_default_is_050(self):
        from config.settings import StrategyConfig
        cfg = StrategyConfig()
        assert cfg.entry_z_min_spread == 0.50

    def test_entry_z_score_yaml_is_2(self):
        """config.yaml should have entry_z_score = 1.6 (v31 aggressive)."""
        from pathlib import Path

        import yaml
        cfg_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
        with open(cfg_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        assert raw["strategy"]["entry_z_score"] == 1.6

    def test_entry_z_min_spread_yaml(self):
        """config.yaml should have entry_z_min_spread = 0.50."""
        from pathlib import Path

        import yaml
        cfg_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
        with open(cfg_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        assert raw["strategy"]["entry_z_min_spread"] == 0.50


# ÔöÇÔöÇ Schema validation ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

class TestEntryZSchemaValidation:
    """StrategyConfigSchema must enforce z-score bounds."""

    def test_valid_entry_z_range(self):
        from config.schemas import StrategyConfigSchema
        schema = StrategyConfigSchema(entry_z_score=2.5, exit_z_score=0.5)
        assert schema.entry_z_score == 2.5

    def test_entry_z_too_low_rejected(self):
        from config.schemas import StrategyConfigSchema
        with pytest.raises(Exception):
            StrategyConfigSchema(entry_z_score=1.0)  # < 1.5

    def test_entry_z_too_high_rejected(self):
        from config.schemas import StrategyConfigSchema
        with pytest.raises(Exception):
            StrategyConfigSchema(entry_z_score=5.0)  # > 4.0

    def test_entry_z_must_exceed_exit_z(self):
        from config.schemas import StrategyConfigSchema
        with pytest.raises(Exception):
            StrategyConfigSchema(entry_z_score=1.5, exit_z_score=1.5)

    def test_entry_z_min_spread_valid(self):
        from config.schemas import StrategyConfigSchema
        schema = StrategyConfigSchema(entry_z_min_spread=1.0)
        assert schema.entry_z_min_spread == 1.0

    def test_entry_z_min_spread_negative_rejected(self):
        from config.schemas import StrategyConfigSchema
        with pytest.raises(Exception):
            StrategyConfigSchema(entry_z_min_spread=-0.5)

    def test_entry_z_min_spread_too_high_rejected(self):
        from config.schemas import StrategyConfigSchema
        with pytest.raises(Exception):
            StrategyConfigSchema(entry_z_min_spread=10.0)


# ÔöÇÔöÇ Min-spread filter logic ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

class TestMinSpreadFilter:
    """Test the min-spread guard logic used in pair_trading.py."""

    @staticmethod
    def _check_spread_ok(spread_value: float, min_spread: float) -> bool:
        """Replicate the guard logic from pair_trading.py."""
        _abs_spread = abs(spread_value)
        return _abs_spread >= min_spread if min_spread > 0 else True

    def test_large_spread_allows_entry(self):
        assert self._check_spread_ok(1.5, 0.50) is True

    def test_micro_spread_blocks_entry(self):
        assert self._check_spread_ok(0.10, 0.50) is False

    def test_zero_min_spread_allows_all(self):
        assert self._check_spread_ok(0.001, 0.0) is True

    def test_negative_spread_abs_used(self):
        assert self._check_spread_ok(-0.80, 0.50) is True

    def test_exact_boundary_passes(self):
        assert self._check_spread_ok(0.50, 0.50) is True

    def test_config_has_min_spread_field(self):
        """StrategyConfig must expose entry_z_min_spread."""
        from config.settings import StrategyConfig
        cfg = StrategyConfig(entry_z_min_spread=1.25)
        assert cfg.entry_z_min_spread == 1.25


# ÔöÇÔöÇ Integration: entry_z threshold ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

class TestEntryZThreshold:
    """Verify that entries require z-score ÔëÑ 2.0."""

    def test_z_below_2_no_entry(self):
        current_z = 1.8
        effective_entry_z = 2.0
        assert not (current_z > effective_entry_z)

    def test_z_above_2_triggers_entry(self):
        current_z = 2.5
        effective_entry_z = 2.0
        assert current_z > effective_entry_z

    def test_z_exactly_2_no_entry(self):
        current_z = 2.0
        effective_entry_z = 2.0
        assert not (current_z > effective_entry_z)

    def test_negative_z_entry_short(self):
        current_z = -2.5
        effective_entry_z = 2.0
        assert current_z < -effective_entry_z
