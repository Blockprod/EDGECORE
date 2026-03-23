"""
Tests C-11 — OOS validation integration.

Validates that:
  - OOSValidationEngine returns an OOSReport on synthetic data.
  - strategy_validated is False when no pairs pass persistence.
  - BacktestEngine.run_oos_validation() delegates to OOSValidationEngine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtester.oos import OOSConfig, OOSReport, OOSValidationEngine
from backtester.runner import BacktestEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_price_df(n: int = 252, seed: int = 42) -> pd.DataFrame:
    """Build a simple synthetic OHLCV-like price DataFrame with two symbols."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    aapl = 150.0 + rng.standard_normal(n).cumsum()
    msft = 300.0 + rng.standard_normal(n).cumsum()
    return pd.DataFrame({"AAPL": aapl, "MSFT": msft}, index=dates)


# ---------------------------------------------------------------------------
# Group 1 — OOSValidationEngine basic behaviour
# ---------------------------------------------------------------------------


class TestOOSValidationEngineBasic:
    """OOSValidationEngine returns an OOSReport on synthetic price data."""

    def test_returns_oos_report(self):
        price_data = _make_price_df(n=252)
        engine = OOSValidationEngine()
        report = engine.validate(
            pairs=[("AAPL", "MSFT")],
            price_data=price_data,
            split_date="2023-07-01",
        )
        assert isinstance(report, OOSReport)

    def test_report_fields_populated(self):
        price_data = _make_price_df(n=252)
        engine = OOSValidationEngine()
        report = engine.validate(
            pairs=[("AAPL", "MSFT")],
            price_data=price_data,
            split_date="2023-07-01",
        )
        assert report.total_pairs >= 0
        assert 0.0 <= report.persistence_rate <= 1.0
        assert isinstance(report.strategy_validated, bool)

    def test_empty_pair_list_returns_report(self):
        price_data = _make_price_df(n=100)
        engine = OOSValidationEngine()
        report = engine.validate(
            pairs=[],
            price_data=price_data,
            split_date="2023-04-01",
        )
        # Empty pairs → 0 total, not validated
        assert report.total_pairs == 0
        assert report.strategy_validated is False


# ---------------------------------------------------------------------------
# Group 2 — strategy_validated reflects persistence_rate vs threshold
# ---------------------------------------------------------------------------


class TestStrategyValidatedFlag:
    """strategy_validated is False when no pairs pass the acceptance threshold."""

    def test_no_pairs_means_not_validated(self):
        engine = OOSValidationEngine(OOSConfig(acceptance_threshold=0.70))
        report = engine.validate(
            pairs=[],
            price_data=_make_price_df(n=100),
            split_date="2023-04-01",
        )
        assert report.strategy_validated is False
        assert report.persistence_rate == 0.0

    def test_missing_symbols_skipped_not_counted_as_passed(self):
        """Pairs whose symbols are absent from price_data should be skipped."""
        price_data = _make_price_df(n=252)  # only AAPL, MSFT
        engine = OOSValidationEngine()
        report = engine.validate(
            pairs=[("FOO", "BAR")],  # unknown symbols
            price_data=price_data,
            split_date="2023-07-01",
        )
        # All skipped → persistence_rate will be 0 or strategy not validated
        assert report.passed_pairs == 0

    def test_split_date_after_all_data_no_oos(self):
        """split_date after the last index → OOS data is empty → not validated."""
        price_data = _make_price_df(n=100)
        engine = OOSValidationEngine()
        report = engine.validate(
            pairs=[("AAPL", "MSFT")],
            price_data=price_data,
            split_date="2030-01-01",  # way after all data
        )
        assert report.strategy_validated is False


# ---------------------------------------------------------------------------
# Group 3 — BacktestEngine.run_oos_validation() delegation
# ---------------------------------------------------------------------------


class TestBacktestEngineOOSIntegration:
    """BacktestEngine exposes run_oos_validation() that delegates correctly."""

    def test_method_exists(self):
        engine = BacktestEngine()
        assert callable(getattr(engine, "run_oos_validation", None))

    def test_returns_oos_report(self):
        price_data = _make_price_df(n=252)
        engine = BacktestEngine()
        report = engine.run_oos_validation(
            pairs=[("AAPL", "MSFT")],
            price_data=price_data,
            split_date="2023-07-01",
        )
        assert isinstance(report, OOSReport)

    def test_accepts_custom_oos_config(self):
        price_data = _make_price_df(n=252)
        engine = BacktestEngine()
        cfg = OOSConfig(acceptance_threshold=0.50)
        report = engine.run_oos_validation(
            pairs=[("AAPL", "MSFT")],
            price_data=price_data,
            split_date="2023-07-01",
            oos_config=cfg,
        )
        assert report.config.acceptance_threshold == pytest.approx(0.50)
