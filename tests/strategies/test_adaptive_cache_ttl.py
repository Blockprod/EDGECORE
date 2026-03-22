"""
Sprint 3.5 ÔÇô Adaptive cache TTL based on volatility regime.

Faille: ­ƒƒí m-05 ÔÇô Cache de 24h trop long
Fix: TTL adapts to regime: HIGHÔåô2h, NORMALÔåô12h, LOWÔåô24h

Tests:
- get_cache_ttl_hours returns correct TTL per regime
- load_cached_pairs uses adaptive TTL when max_age_hours=None
- HIGH regime expires cache after 3h (2h TTL)
- NORMAL regime keeps cache fresh for 10h (12h TTL)
- LOW regime keeps cache fresh for 20h (24h TTL)
- Explicit max_age_hours overrides adaptive TTL
- find_cointegrated_pairs uses adaptive TTL (no more hardcoded 24h)
- Config values are respected when present
"""

import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np
import pandas as pd

from models.regime_detector import VolatilityRegime
from strategies.pair_trading import PairTradingStrategy


class TestGetCacheTtlHours:
    """Test the regime-based TTL calculation logic."""

    def test_high_regime_returns_2h(self):
        """HIGH volatility Ôåô 2h TTL (frequent re-discovery)."""
        strategy = PairTradingStrategy()
        strategy.regime_detector.current_regime = VolatilityRegime.HIGH
        assert strategy.get_cache_ttl_hours() == 2

    def test_normal_regime_returns_12h(self):
        """NORMAL volatility Ôåô 12h TTL (moderate)."""
        strategy = PairTradingStrategy()
        strategy.regime_detector.current_regime = VolatilityRegime.NORMAL
        assert strategy.get_cache_ttl_hours() == 12

    def test_low_regime_returns_24h(self):
        """LOW volatility Ôåô 24h TTL (stable market, long cache)."""
        strategy = PairTradingStrategy()
        strategy.regime_detector.current_regime = VolatilityRegime.LOW
        assert strategy.get_cache_ttl_hours() == 24

    def test_ttl_matches_config_when_set(self):
        """Config values should override defaults."""
        strategy = PairTradingStrategy()
        # Use mock to avoid polluting the shared singleton config
        with patch.object(strategy.config, 'cache_ttl_high_vol', 1), \
             patch.object(strategy.config, 'cache_ttl_normal_vol', 6), \
             patch.object(strategy.config, 'cache_ttl_low_vol', 48):

            strategy.regime_detector.current_regime = VolatilityRegime.HIGH
            assert strategy.get_cache_ttl_hours() == 1

            strategy.regime_detector.current_regime = VolatilityRegime.NORMAL
            assert strategy.get_cache_ttl_hours() == 6

            strategy.regime_detector.current_regime = VolatilityRegime.LOW
            assert strategy.get_cache_ttl_hours() == 48


class TestLoadCachedPairsAdaptive:
    """Test that load_cached_pairs uses adaptive TTL."""

    def _save_cache_with_age(self, strategy, pairs, age_hours):
        """Helper: save cache file and backdate its mtime."""
        cache_file = strategy.cache_dir / "cointegrated_pairs.json"
        with open(cache_file, 'w') as f:
            json.dump([list(p) for p in pairs], f)
        # Backdate the file modification time
        target_time = datetime.now() - timedelta(hours=age_hours)
        ts = target_time.timestamp()
        os.utime(cache_file, (ts, ts))

    def test_high_regime_expires_after_3h(self):
        """Cache saved 3h ago should expire in HIGH regime (TTL=2h)."""
        strategy = PairTradingStrategy()
        strategy.regime_detector.current_regime = VolatilityRegime.HIGH
        test_pairs = [('AAPL', 'GOOGL', 0.01, 10.0)]
        self._save_cache_with_age(strategy, test_pairs, age_hours=3)

        result = strategy.load_cached_pairs()  # adaptive TTL Ôåô 2h
        assert result is None, "Cache 3h old should expire with HIGH regime (TTL=2h)"

    def test_high_regime_keeps_fresh_cache(self):
        """Cache saved 1h ago should be valid in HIGH regime (TTL=2h)."""
        strategy = PairTradingStrategy()
        strategy.regime_detector.current_regime = VolatilityRegime.HIGH
        test_pairs = [('AAPL', 'GOOGL', 0.01, 10.0)]
        self._save_cache_with_age(strategy, test_pairs, age_hours=1)

        result = strategy.load_cached_pairs()  # adaptive TTL Ôåô 2h
        assert result == test_pairs, "Cache 1h old should be valid with HIGH regime (TTL=2h)"

    def test_normal_regime_keeps_10h_old_cache(self):
        """Cache saved 10h ago should be valid in NORMAL regime (TTL=12h)."""
        strategy = PairTradingStrategy()
        strategy.regime_detector.current_regime = VolatilityRegime.NORMAL
        test_pairs = [('AAPL', 'GOOGL', 0.01, 10.0)]
        self._save_cache_with_age(strategy, test_pairs, age_hours=10)

        result = strategy.load_cached_pairs()  # adaptive TTL Ôåô 12h
        assert result == test_pairs, "Cache 10h old should be valid with NORMAL regime (TTL=12h)"

    def test_normal_regime_expires_after_13h(self):
        """Cache saved 13h ago should expire in NORMAL regime (TTL=12h)."""
        strategy = PairTradingStrategy()
        strategy.regime_detector.current_regime = VolatilityRegime.NORMAL
        test_pairs = [('AAPL', 'GOOGL', 0.01, 10.0)]
        self._save_cache_with_age(strategy, test_pairs, age_hours=13)

        result = strategy.load_cached_pairs()  # adaptive TTL Ôåô 12h
        assert result is None, "Cache 13h old should expire with NORMAL regime (TTL=12h)"

    def test_low_regime_keeps_20h_old_cache(self):
        """Cache saved 20h ago should be valid in LOW regime (TTL=24h)."""
        strategy = PairTradingStrategy()
        strategy.regime_detector.current_regime = VolatilityRegime.LOW
        test_pairs = [('AAPL', 'GOOGL', 0.01, 10.0)]
        self._save_cache_with_age(strategy, test_pairs, age_hours=20)

        result = strategy.load_cached_pairs()  # adaptive TTL Ôåô 24h
        assert result == test_pairs, "Cache 20h old should be valid with LOW regime (TTL=24h)"

    def test_low_regime_expires_after_25h(self):
        """Cache saved 25h ago should expire in LOW regime (TTL=24h)."""
        strategy = PairTradingStrategy()
        strategy.regime_detector.current_regime = VolatilityRegime.LOW
        test_pairs = [('AAPL', 'GOOGL', 0.01, 10.0)]
        self._save_cache_with_age(strategy, test_pairs, age_hours=25)

        result = strategy.load_cached_pairs()  # adaptive TTL Ôåô 24h
        assert result is None, "Cache 25h old should expire with LOW regime (TTL=24h)"


class TestExplicitMaxAgeOverride:
    """Test that explicit max_age_hours overrides adaptive TTL."""

    def _save_cache_with_age(self, strategy, pairs, age_hours):
        """Helper: save cache file and backdate its mtime."""
        cache_file = strategy.cache_dir / "cointegrated_pairs.json"
        with open(cache_file, 'w') as f:
            json.dump([list(p) for p in pairs], f)
        target_time = datetime.now() - timedelta(hours=age_hours)
        ts = target_time.timestamp()
        os.utime(cache_file, (ts, ts))

    def test_explicit_max_age_ignores_regime(self):
        """Passing max_age_hours explicitly should bypass regime logic."""
        strategy = PairTradingStrategy()
        strategy.regime_detector.current_regime = VolatilityRegime.HIGH  # TTL=2h
        test_pairs = [('AAPL', 'GOOGL', 0.01, 10.0)]
        self._save_cache_with_age(strategy, test_pairs, age_hours=5)

        # Adaptive would expire (2h TTL < 5h age), but explicit 24h keeps it
        result = strategy.load_cached_pairs(max_age_hours=24)
        assert result == test_pairs, (
            "Explicit max_age_hours=24 should override adaptive TTL=2h"
        )

    def test_explicit_zero_always_expires(self):
        """max_age_hours=0 should always return None."""
        strategy = PairTradingStrategy()
        test_pairs = [('AAPL', 'GOOGL', 0.01, 10.0)]
        strategy.save_cached_pairs(test_pairs)

        result = strategy.load_cached_pairs(max_age_hours=0)
        assert result is None, "max_age_hours=0 should always expire cache"


class TestFindCointegratedPairsAdaptiveTTL:
    """Test that find_cointegrated_pairs uses adaptive TTL (no more hardcoded 24h)."""

    def test_discover_pairs_calls_load_without_hardcoded_24h(self):
        """
        Verify find_cointegrated_pairs calls load_cached_pairs() with
        no explicit max_age_hours (triggering adaptive TTL), not the old
        hardcoded max_age_hours=24.
        """
        strategy = PairTradingStrategy()
        np.random.seed(42)
        data = pd.DataFrame({
            f"SYM{i}": np.random.randn(100).cumsum()
            for i in range(3)
        })

        with patch.object(strategy, 'load_cached_pairs', return_value=None) as mock_load:
            strategy.find_cointegrated_pairs(data, use_cache=True, use_parallel=False)
            # Should call load_cached_pairs() with no args (adaptive TTL)
            mock_load.assert_called_once_with()


class TestRegimeTransitionChangesCache:
    """Test that regime transitions dynamically change cache behavior."""

    def _save_cache_with_age(self, strategy, pairs, age_hours):
        cache_file = strategy.cache_dir / "cointegrated_pairs.json"
        with open(cache_file, 'w') as f:
            json.dump([list(p) for p in pairs], f)
        target_time = datetime.now() - timedelta(hours=age_hours)
        ts = target_time.timestamp()
        os.utime(cache_file, (ts, ts))

    def test_same_cache_valid_then_expired_on_regime_change(self):
        """
        A 5h old cache should be valid in LOW regime but expired in HIGH regime.
        Simulates a regime transition changing cache behavior dynamically.
        """
        strategy = PairTradingStrategy()
        test_pairs = [('AAPL', 'GOOGL', 0.01, 10.0)]
        self._save_cache_with_age(strategy, test_pairs, age_hours=5)

        # In LOW regime (TTL=24h), 5h old cache is valid
        strategy.regime_detector.current_regime = VolatilityRegime.LOW
        result_low = strategy.load_cached_pairs()
        assert result_low == test_pairs, "5h cache should be valid in LOW regime (TTL=24h)"

        # Market spikes Ôåô HIGH regime (TTL=2h), same 5h old cache now expired
        strategy.regime_detector.current_regime = VolatilityRegime.HIGH
        result_high = strategy.load_cached_pairs()
        assert result_high is None, "5h cache should be expired in HIGH regime (TTL=2h)"

    def test_regime_aware_ttl_transitions_through_all_regimes(self):
        """Cache at 15h should be valid in LOW, expired in NORMAL and HIGH."""
        strategy = PairTradingStrategy()
        test_pairs = [('JPM', 'BAC', 0.02, 8.0)]
        self._save_cache_with_age(strategy, test_pairs, age_hours=15)

        # LOW (TTL=24h): 15h < 24h Ôåô valid
        strategy.regime_detector.current_regime = VolatilityRegime.LOW
        assert strategy.load_cached_pairs() == test_pairs

        # NORMAL (TTL=12h): 15h > 12h Ôåô expired
        strategy.regime_detector.current_regime = VolatilityRegime.NORMAL
        assert strategy.load_cached_pairs() is None

        # HIGH (TTL=2h): 15h > 2h Ôåô expired
        strategy.regime_detector.current_regime = VolatilityRegime.HIGH
        assert strategy.load_cached_pairs() is None


class TestDefaultConfigValues:
    """Test that default config values are correctly set."""

    def test_strategy_config_has_cache_ttl_fields(self):
        """Verify config fields exist with correct defaults."""
        from config.settings import StrategyConfig
        config = StrategyConfig()
        assert config.cache_ttl_high_vol == 2
        assert config.cache_ttl_normal_vol == 12
        assert config.cache_ttl_low_vol == 24

    def test_cache_ttl_monotonic_high_lt_normal_lt_low(self):
        """HIGH TTL < NORMAL TTL < LOW TTL (higher vol = shorter cache)."""
        from config.settings import StrategyConfig
        config = StrategyConfig()
        assert config.cache_ttl_high_vol < config.cache_ttl_normal_vol
        assert config.cache_ttl_normal_vol < config.cache_ttl_low_vol
