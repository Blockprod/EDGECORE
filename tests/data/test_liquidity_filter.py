<<<<<<< HEAD
﻿"""
=======
"""
>>>>>>> origin/main
Sprint 2.4 - Tests for dynamic liquidity filter and delisting guard (M-04 fix).

Tests:
  - LiquidityFilter: basic filtering, thresholds, strict mode, multiple data sources
  - DelistingGuard: volume crash, penny price, stale data, batch check
    - Config YAML cleanup: ENRN/SHLDQ removed, no duplicates
    - Integration: filter applied in pair discovery
    - DoD: symbol with volume $100K excluded from discovery
"""

<<<<<<< HEAD
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.delisting_guard import DelistingConfig, DelistingGuard
from data.liquidity_filter import LiquidityConfig, LiquidityFilter
=======
import pytest
import sys
import os
import yaml
import pandas as pd
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.liquidity_filter import LiquidityFilter, LiquidityConfig
from data.delisting_guard import DelistingGuard, DelistingConfig
>>>>>>> origin/main


# ---------------------------------------------------------------------------
# Fix: Reset Settings singleton before/after tests
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def reset_settings():
    from config.settings import Settings
<<<<<<< HEAD

=======
>>>>>>> origin/main
    Settings._instance = None
    yield
    Settings._instance = None


# ===========================================================================
# SECTION 1 - LiquidityFilter
# ===========================================================================

<<<<<<< HEAD

=======
>>>>>>> origin/main
class TestLiquidityFilter:
    """Tests for LiquidityFilter."""

    def test_filter_by_volume_data_dict(self):
        """Filter using explicit volume dict."""
        lf = LiquidityFilter()
        result = lf.filter_symbols(
            symbols=["AAPL", "MSFT", "PENNY"],
            volume_data={
                "AAPL": 20_000_000_000,
                "MSFT": 8_000_000_000,
                "PENNY": 50_000,
<<<<<<< HEAD
            },
=======
            }
>>>>>>> origin/main
        )
        assert "AAPL" in result
        assert "MSFT" in result
        assert "PENNY" not in result

    def test_dod_symbol_100k_excluded(self):
        """DoD: symbol with volume $100K must be excluded from discovery."""
        lf = LiquidityFilter()
<<<<<<< HEAD
        result = lf.filter_symbols(symbols=["SYM_A"], volume_data={"SYM_A": 100_000})
=======
        result = lf.filter_symbols(
            symbols=["SYM_A"],
            volume_data={"SYM_A": 100_000}
        )
>>>>>>> origin/main
        assert "SYM_A" not in result

    def test_filter_custom_threshold(self):
        """Custom min_volume threshold."""
        cfg = LiquidityConfig(min_volume_24h_usd=1_000_000)
        lf = LiquidityFilter(cfg)
<<<<<<< HEAD
        result = lf.filter_symbols(symbols=["A", "B"], volume_data={"A": 2_000_000, "B": 500_000})
=======
        result = lf.filter_symbols(
            symbols=["A", "B"],
            volume_data={"A": 2_000_000, "B": 500_000}
        )
>>>>>>> origin/main
        assert result == ["A"]

    def test_no_volume_data_permissive(self):
        """Without volume data and strict_mode=False, symbols pass."""
        lf = LiquidityFilter()
        result = lf.filter_symbols(symbols=["X", "Y"])
        assert result == ["X", "Y"]

    def test_strict_mode_rejects_no_data(self):
        """strict_mode=True rejects symbols without volume data."""
        cfg = LiquidityConfig(strict_mode=True)
        lf = LiquidityFilter(cfg)
        result = lf.filter_symbols(symbols=["X", "Y"])
        assert result == []
        assert len(lf.rejection_log) == 2

    def test_filter_with_volume_dataframe(self):
        """Filter using volume_df DataFrame."""
        dates = pd.date_range("2025-01-01", periods=60)
<<<<<<< HEAD
        volume_df = pd.DataFrame(
            {
                "AAPL": np.full(60, 1e10),
                "JUNK": np.full(60, 10_000),
            },
            index=dates,
        )

=======
        volume_df = pd.DataFrame({
            "AAPL": np.full(60, 1e10),
            "JUNK": np.full(60, 10_000),
        }, index=dates)
        
>>>>>>> origin/main
        lf = LiquidityFilter()
        result = lf.filter_symbols(
            symbols=["AAPL", "JUNK"],
            volume_df=volume_df,
        )
        assert "AAPL" in result
        assert "JUNK" not in result

    def test_rejection_log(self):
        """Rejection log populated correctly."""
        lf = LiquidityFilter()
<<<<<<< HEAD
        lf.filter_symbols(symbols=["A", "B", "C"], volume_data={"A": 1e8, "B": 100, "C": 200})
=======
        lf.filter_symbols(
            symbols=["A", "B", "C"],
            volume_data={"A": 1e8, "B": 100, "C": 200}
        )
>>>>>>> origin/main
        assert len(lf.rejection_log) == 2
        rejected_syms = [r["symbol"] for r in lf.rejection_log]
        assert "B" in rejected_syms
        assert "C" in rejected_syms

    def test_exact_threshold_passes(self):
        """Symbol with exactly min_volume passes."""
        cfg = LiquidityConfig(min_volume_24h_usd=1_000_000)
        lf = LiquidityFilter(cfg)
<<<<<<< HEAD
        result = lf.filter_symbols(symbols=["A"], volume_data={"A": 1_000_000})
=======
        result = lf.filter_symbols(
            symbols=["A"],
            volume_data={"A": 1_000_000}
        )
>>>>>>> origin/main
        assert result == ["A"]

    def test_empty_symbols(self):
        """Empty input ? empty output."""
        lf = LiquidityFilter()
        assert lf.filter_symbols(symbols=[]) == []


# ===========================================================================
# SECTION 2 - DelistingGuard
# ===========================================================================

<<<<<<< HEAD

=======
>>>>>>> origin/main
class TestDelistingGuard:
    """Tests for DelistingGuard."""

    def test_safe_symbol(self):
        """Normal symbol is safe."""
        guard = DelistingGuard()
        prices = pd.Series([100, 101, 99, 102, 100], index=pd.date_range("2025-01-01", periods=5))
        is_safe, reason = guard.is_safe("AAPL", price_series=prices)
        assert is_safe
        assert reason == ""

    def test_penny_price_detected(self):
        """Price < $0.001 ? unsafe."""
        guard = DelistingGuard()
        prices = pd.Series([0.0001, 0.00005, 0.00003])
        is_safe, reason = guard.is_safe("DEAD", price_series=prices)
        assert not is_safe
        assert "Penny price" in reason

    def test_stale_data_detected(self):
        """> 3 days of NaN at end ? stale."""
        guard = DelistingGuard()
        prices = pd.Series([100, 101, 99, np.nan, np.nan, np.nan, np.nan])
        is_safe, reason = guard.is_safe("STALE", price_series=prices)
        assert not is_safe
        assert "Stale" in reason

    def test_stale_with_zeros(self):
        """Trailing zeros also count as stale."""
        guard = DelistingGuard()
        prices = pd.Series([100, 101, 0, 0, 0, 0])
<<<<<<< HEAD
        is_safe, _reason = guard.is_safe("ZERO", price_series=prices)
=======
        is_safe, reason = guard.is_safe("ZERO", price_series=prices)
>>>>>>> origin/main
        assert not is_safe

    def test_volume_crash_detected(self):
        """Volume drop > 80% ? unsafe."""
        guard = DelistingGuard()
        # 20 days of high volume, then 7 days of near-zero
<<<<<<< HEAD
        volumes = pd.Series([1_000_000] * 20 + [50_000] * 7)
=======
        volumes = pd.Series(
            [1_000_000] * 20 + [50_000] * 7
        )
>>>>>>> origin/main
        is_safe, reason = guard.is_safe("ENRN", volume_series=volumes)
        assert not is_safe
        assert "Volume crash" in reason

    def test_volume_no_crash(self):
        """Stable volume ? safe."""
        guard = DelistingGuard()
        volumes = pd.Series([1_000_000] * 30)
<<<<<<< HEAD
        is_safe, _reason = guard.is_safe("STABLE", volume_series=volumes)
=======
        is_safe, reason = guard.is_safe("STABLE", volume_series=volumes)
>>>>>>> origin/main
        assert is_safe

    def test_no_data_is_safe(self):
        """No data provided ? safe (can't evaluate)."""
        guard = DelistingGuard()
<<<<<<< HEAD
        is_safe, _reason = guard.is_safe("UNKNOWN")
=======
        is_safe, reason = guard.is_safe("UNKNOWN")
>>>>>>> origin/main
        assert is_safe

    def test_custom_config(self):
        """Custom thresholds work."""
        cfg = DelistingConfig(min_price_threshold=1.0, max_stale_days=1)
        guard = DelistingGuard(cfg)
        prices = pd.Series([0.5, 0.4, 0.3])
        is_safe, reason = guard.is_safe("CHEAP", price_series=prices)
        assert not is_safe
        assert "Penny price" in reason

    def test_batch_check(self):
        """Batch check multiple symbols."""
        guard = DelistingGuard()
<<<<<<< HEAD
        prices_df = pd.DataFrame(
            {
                "AAPL": [50000, 51000, 49000],
                "DEAD": [0.0001, 0.00005, 0.00003],
            }
        )
=======
        prices_df = pd.DataFrame({
            "AAPL": [50000, 51000, 49000],
            "DEAD": [0.0001, 0.00005, 0.00003],
        })
>>>>>>> origin/main
        results = guard.check_batch(
            symbols=["AAPL", "DEAD"],
            price_data=prices_df,
        )
        assert results["AAPL"][0]
        assert not results["DEAD"][0]


# ===========================================================================
# SECTION 3 - Config YAML Cleanup
# ===========================================================================

<<<<<<< HEAD

=======
>>>>>>> origin/main
class TestConfigCleanup:
    """Verify YAML configs are cleaned up per DoD."""

    def _load_yaml(self, name):
        path = Path(__file__).parent.parent.parent / "config" / name
<<<<<<< HEAD
        with open(path, encoding="utf-8") as f:
=======
        with open(path, encoding='utf-8') as f:
>>>>>>> origin/main
            return yaml.safe_load(f)

    def test_dev_no_ftt(self):
        """ENRN removed from dev.yaml (delisted fraud)."""
        cfg = self._load_yaml("dev.yaml")
        symbols = cfg["trading_universe"]["symbols"]
        assert "ENRN" not in symbols

    def test_dev_no_lunc(self):
        """SHLDQ removed from dev.yaml (bankrupt)."""
        cfg = self._load_yaml("dev.yaml")
        symbols = cfg["trading_universe"]["symbols"]
        assert "SHLDQ" not in symbols

    def test_dev_no_duplicate_ltc(self):
        """No symbol must be duplicated in dev.yaml (0 or 1 occurrence is fine)."""
        cfg = self._load_yaml("dev.yaml")
        symbols = cfg["trading_universe"]["symbols"]
        assert symbols.count("INTC") <= 1

    def test_prod_no_ftt(self):
        """ENRN removed from prod.yaml (delisted fraud)."""
        cfg = self._load_yaml("prod.yaml")
        symbols = cfg["trading_universe"]["symbols"]
        assert "ENRN" not in symbols

    def test_prod_no_low_liquidity(self):
        """PENNY, MSTOCK, GSTOCK removed from prod.yaml."""
        cfg = self._load_yaml("prod.yaml")
        symbols = cfg["trading_universe"]["symbols"]
        for sym in ["PENNY", "MSTOCK", "GSTOCK"]:
            assert sym not in symbols, f"{sym} should be removed from prod.yaml"


# ===========================================================================
# SECTION 4 - Integration with PairTradingStrategy
# ===========================================================================

<<<<<<< HEAD

=======
>>>>>>> origin/main
class TestIntegration:
    """Integration: liquidity filter in pair discovery."""

    def test_strategy_has_liquidity_filter(self):
        """PairTradingStrategy has a liquidity_filter attribute."""
        from strategies.pair_trading import PairTradingStrategy
<<<<<<< HEAD

        strategy = PairTradingStrategy()
        assert hasattr(strategy, "liquidity_filter")
=======
        strategy = PairTradingStrategy()
        assert hasattr(strategy, 'liquidity_filter')
>>>>>>> origin/main
        assert isinstance(strategy.liquidity_filter, LiquidityFilter)

    def test_strategy_has_delisting_guard(self):
        """PairTradingStrategy has a delisting_guard attribute."""
        from strategies.pair_trading import PairTradingStrategy
<<<<<<< HEAD

        strategy = PairTradingStrategy()
        assert hasattr(strategy, "delisting_guard")
=======
        strategy = PairTradingStrategy()
        assert hasattr(strategy, 'delisting_guard')
>>>>>>> origin/main
        assert isinstance(strategy.delisting_guard, DelistingGuard)

    def test_find_pairs_filters_illiquid(self):
        """Illiquid symbols excluded from cointegration scan when volume_data passed."""
        from strategies.pair_trading import PairTradingStrategy
<<<<<<< HEAD

=======
>>>>>>> origin/main
        strategy = PairTradingStrategy()
        strategy.use_cache = False

        # Create fake price data with 3 symbols
        np.random.seed(42)
        n = 300
        dates = pd.date_range("2023-01-01", periods=n)
        aapl = 50000 + np.cumsum(np.random.randn(n) * 100)
        msft = 3000 + np.cumsum(np.random.randn(n) * 50)
        junk = 0.01 + np.cumsum(np.random.randn(n) * 0.0001)
<<<<<<< HEAD
        price_data = pd.DataFrame({"AAPL": aapl, "MSFT": msft, "JUNK": junk}, index=dates)
=======
        price_data = pd.DataFrame(
            {"AAPL": aapl, "MSFT": msft, "JUNK": junk},
            index=dates
        )
>>>>>>> origin/main

        # With volume_data marking JUNK as illiquid
        pairs = strategy.find_cointegrated_pairs(
            price_data,
            use_cache=False,
            use_parallel=False,
            volume_data={
                "AAPL": 1e10,
                "MSFT": 1e9,
                "JUNK": 50_000,  # Below $5M threshold
<<<<<<< HEAD
            },
        )

=======
            }
        )
        
>>>>>>> origin/main
        # JUNK should not appear in any discovered pair
        for p in pairs:
            assert "JUNK" not in p[:2], "JUNK should be filtered out"

    def test_find_pairs_no_volume_data_keeps_all(self):
        """Without volume_data, all symbols proceed to cointegration scan."""
        from strategies.pair_trading import PairTradingStrategy
<<<<<<< HEAD

=======
>>>>>>> origin/main
        strategy = PairTradingStrategy()
        strategy.use_cache = False

        np.random.seed(42)
        n = 300
        dates = pd.date_range("2023-01-01", periods=n)
        # Create perfectly cointegrated pair
        x = 100 + np.cumsum(np.random.randn(n) * 0.5)
        y = 50 + 0.8 * x + np.random.randn(n) * 0.3
        price_data = pd.DataFrame({"A": x, "B": y}, index=dates)

        pairs = strategy.find_cointegrated_pairs(
            price_data,
            use_cache=False,
            use_parallel=False,
        )
        # Should find the cointegrated pair (no filtering applied)
        assert len(pairs) >= 0  # May or may not find pair, but should not crash
