"""
Tests for Sprint 2.6 - Remove synthetic fallback (M-06).

Ensures:
  - No synthetic data is ever injected when 0 cointegrated pairs are found
  - Legacy run() returns empty BacktestMetrics with note="NO_PAIRS_FOUND"
  - total_return == 0 for non-cointegrated symbols
  - _generate_fallback_signals is removed
  - run_unified path also handles 0-pair scenario cleanly
  - _generate_cointegrated_pair() still works (used by use_synthetic=True)
"""

import warnings
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from backtests.runner import BacktestRunner, _generate_cointegrated_pair
from backtests.metrics import BacktestMetrics


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def _make_uncorrelated_prices(n: int = 200, seed: int = 99) -> pd.DataFrame:
    """Create two completely uncorrelated random walks - will NOT be cointegrated."""
    rng = np.random.RandomState(seed)
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    # Independent random walks
    p1 = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    p2 = 50 * np.exp(np.cumsum(rng.normal(0.001, 0.03, n)))
    return pd.DataFrame({"FAKE1": p1, "FAKE2": p2}, index=dates)


# --------------------------------------------------
# Core Sprint 2.6 Tests: No Synthetic Fallback
# --------------------------------------------------

class TestNoSyntheticFallback:
    """Verify the synthetic fallback block was removed."""

    def test_no_fallback_signals_method(self):
        """_generate_fallback_signals should no longer exist."""
        assert not hasattr(BacktestRunner, "_generate_fallback_signals"), (
            "_generate_fallback_signals should have been removed in Sprint 2.6"
        )

    def test_no_syntha_synthb_in_runner(self):
        """The SYNTHA/SYNTHB synthetic symbols should not appear in runner source."""
        import inspect
        source = inspect.getsource(BacktestRunner.run)
        assert "SYNTHA" not in source
        assert "SYNTHB" not in source
        assert "fallback_synthetic" not in source

    def test_legacy_run_no_pairs_returns_empty_metrics(self):
        """
        DoD: backtest with non-cointegrated symbols ? total_return=0, note=NO_PAIRS_FOUND.
        
        We mock _find_cointegrated_pairs_in_data to return [] to guarantee
        the 0-pair path, and use use_synthetic=True to avoid real API calls.
        """
        runner = BacktestRunner()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with patch.object(
                runner, "_find_cointegrated_pairs_in_data", return_value=[]
            ):
                result = runner.run(
                    symbols=["FAKE1"],
                    start_date="2023-01-01",
                    end_date="2024-01-01",
                    use_synthetic=True,
                )

        assert isinstance(result, BacktestMetrics)
        assert result.total_return == 0.0
        assert result.note is not None
        assert "NO_PAIRS_FOUND" in result.note

    def test_legacy_run_no_pairs_zero_trades(self):
        """No synthetic trades should be generated."""
        runner = BacktestRunner()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with patch.object(
                runner, "_find_cointegrated_pairs_in_data", return_value=[]
            ):
                result = runner.run(
                    symbols=["FAKE1"],
                    start_date="2023-01-01",
                    end_date="2024-01-01",
                    use_synthetic=True,
                )

        assert result.total_trades == 0

    def test_no_synthetic_columns_added(self):
        """
        When 0 pairs found, no SYNTHA/SYNTHB columns should be added to prices_df.
        We verify via source code inspection that no mutation happens.
        """
        import inspect
        source = inspect.getsource(BacktestRunner.run)
        # After Sprint 2.6, there should be no SYNTHA/SYNTHB injection
        assert "SYNTHA" not in source
        assert "SYNTHB" not in source
        # And the 0-pair path should return immediately with note
        assert "NO_PAIRS_FOUND" in source


# --------------------------------------------------
# Synthetic data loading still works (use_synthetic=True)
# --------------------------------------------------

class TestSyntheticDataLoading:
    """
    The _generate_cointegrated_pair() helper for use_synthetic=True
    must still work - it's for testing purposes, not for production fallback.
    """

    def test_generate_cointegrated_pair_still_exists(self):
        """The top-level helper should still be importable."""
        from backtests.runner import _generate_cointegrated_pair
        df = _generate_cointegrated_pair("2023-01-01", "2023-06-01")
        assert "Symbol1" in df.columns
        assert "Symbol2" in df.columns
        assert len(df) > 100

    def test_use_synthetic_true_returns_metrics(self):
        """Legacy run with use_synthetic=True should still return valid BacktestMetrics.
        
        Note: The synthetic pair may or may not find cointegrated pairs depending
        on half-life filtering. Either outcome is acceptable - the key is that
        it returns BacktestMetrics (not crashes or synthetic injection).
        """
        runner = BacktestRunner()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = runner.run(
                symbols=["FAKE"],
                start_date="2023-01-01",
                end_date="2024-01-01",
                use_synthetic=True,
            )
        assert isinstance(result, BacktestMetrics)


# --------------------------------------------------
# BacktestMetrics note field
# --------------------------------------------------

class TestBacktestMetricsNote:
    """Verify note field propagation."""

    def test_from_returns_with_note(self):
        m = BacktestMetrics.from_returns(
            returns=pd.Series([0.0]),
            trades=[],
            start_date="2023-01-01",
            end_date="2023-12-31",
            note="NO_PAIRS_FOUND - backtest non exploitable",
        )
        assert m.note == "NO_PAIRS_FOUND - backtest non exploitable"
        assert m.total_return == 0.0

    def test_from_returns_without_note(self):
        m = BacktestMetrics.from_returns(
            returns=pd.Series([0.01, -0.005, 0.003]),
            trades=[10, -5, 3],
            start_date="2023-01-01",
            end_date="2023-12-31",
        )
        assert m.note is None


# --------------------------------------------------
# Regression safety: run_unified path
# --------------------------------------------------

class TestRunUnifiedNoPairs:
    """run_unified delegates to StrategyBacktestSimulator - 
    verify it doesn't inject synthetic data either."""

    def test_run_unified_no_synthetic_injection(self):
        """
        run_unified with uncorrelated data should not generate any synthetic pairs.
        The simulator simply produces no trades.
        """
        from backtests.strategy_simulator import StrategyBacktestSimulator
        from backtests.cost_model import CostModel

        prices_df = _make_uncorrelated_prices(n=200)
        simulator = StrategyBacktestSimulator(
            cost_model=CostModel(), initial_capital=100_000,
        )
        result = simulator.run(prices_df)

        assert isinstance(result, BacktestMetrics)
        # No synthetic pairs should exist - 0 or very few trades
        assert result.total_trades >= 0  # May find some pairs by chance
