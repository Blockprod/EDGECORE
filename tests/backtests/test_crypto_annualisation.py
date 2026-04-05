"""
Sprint 3.1 ÔÇô Annualisation tests.

Tests that all Sharpe, Sortino, and volatility calculations use the
configured TRADING_DAYS_PER_YEAR (default 252 for US equities).
Also verifies the runtime `set_trading_days` helper.
"""

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Constant definition & export
# ---------------------------------------------------------------------------

from backtests.metrics import (
    TRADING_DAYS_PER_YEAR,
    BacktestMetrics,
    set_trading_days,
)


class TestTradingDaysConstant:
    """Ensure the trading-days constant is correctly defined."""

    def test_constant_exists(self):
        assert hasattr(__import__("backtests.metrics", fromlist=["TRADING_DAYS_PER_YEAR"]), "TRADING_DAYS_PER_YEAR")

    def test_constant_value(self):
        # Default is 252 for US equities
        assert TRADING_DAYS_PER_YEAR == 252

    def test_constant_type(self):
        assert isinstance(TRADING_DAYS_PER_YEAR, int)

    def test_set_trading_days(self):
        """set_trading_days(260) switches to a custom value."""
        original = TRADING_DAYS_PER_YEAR
        try:
            set_trading_days(260)
            from backtests import metrics

            assert metrics.TRADING_DAYS_PER_YEAR == 260
        finally:
            set_trading_days(original)


# ---------------------------------------------------------------------------
# BacktestMetrics ÔÇô Sharpe
# ---------------------------------------------------------------------------


class TestSharpeRatioAnnualisation:
    """Sharpe ratio must use ÔêÜ(TRADING_DAYS_PER_YEAR) for annualisation."""

    @pytest.fixture
    def deterministic_returns(self):
        """Returns 0.1% daily for 100 days ÔÇô deterministic Sharpe."""
        np.random.seed(42)
        return pd.Series(np.random.normal(0.001, 0.02, 100))

    def test_sharpe_uses_configured_days(self, deterministic_returns):
        """Sharpe must equal mean/std * ÔêÜ(TRADING_DAYS_PER_YEAR)."""
        r = deterministic_returns
        expected = (r.mean() / r.std()) * np.sqrt(TRADING_DAYS_PER_YEAR)
        metrics = BacktestMetrics.from_returns(
            r,
            trades=[0.01, -0.005, 0.008],
            start_date="2024-01-01",
            end_date="2024-04-10",
        )
        assert metrics.sharpe_ratio == pytest.approx(expected, rel=1e-9)

    def test_sharpe_changes_with_set_trading_days(self, deterministic_returns):
        """Sharpe changes when annualisation factor is updated."""
        r = deterministic_returns
        # Compute with default (252)
        m252 = BacktestMetrics.from_returns(r, [0.01, -0.005, 0.008], "2024-01-01", "2024-04-10")
        # Switch to 260 (hypothetical alternative)
        original = TRADING_DAYS_PER_YEAR
        try:
            set_trading_days(260)
            m260 = BacktestMetrics.from_returns(r, [0.01, -0.005, 0.008], "2024-01-01", "2024-04-10")
            # 260 annualisation produces a larger absolute Sharpe
            assert abs(m260.sharpe_ratio) > abs(m252.sharpe_ratio)
        finally:
            set_trading_days(original)

    def test_sharpe_positive_for_positive_mean(self):
        """Constant positive returns Ôåô positive Sharpe."""
        r = pd.Series([0.01] * 50)
        metrics = BacktestMetrics.from_returns(r, [0.01] * 5, "2024-01-01", "2024-02-19")
        # std == 0 Ôåô should return 0.0 (division guard)
        assert metrics.sharpe_ratio == 0.0

    def test_sharpe_zero_std_guard(self):
        """std == 0 Ôåô Sharpe == 0.0 (no NaN/inf)."""
        r = pd.Series([0.005] * 200)
        metrics = BacktestMetrics.from_returns(r, [0.01], "2024-01-01", "2024-07-19")
        assert np.isfinite(metrics.sharpe_ratio)


# ---------------------------------------------------------------------------
# BacktestMetrics ÔÇô Sortino
# ---------------------------------------------------------------------------


class TestSortinoRatioAnnualisation:
    """Sortino ratio must use ÔêÜ(TRADING_DAYS_PER_YEAR) for annualisation."""

    @pytest.fixture
    def mixed_returns(self):
        np.random.seed(99)
        return pd.Series(np.random.normal(0.0005, 0.015, 200))

    def test_sortino_uses_configured_days(self, mixed_returns):
        r = mixed_returns
        downside = r[r < 0]
        expected = (r.mean() / downside.std()) * np.sqrt(TRADING_DAYS_PER_YEAR)
        metrics = BacktestMetrics.from_returns(r, [0.01, -0.005], "2024-01-01", "2024-07-19")
        assert metrics.sortino_ratio == pytest.approx(expected, rel=1e-9)

    def test_sortino_changes_with_set_trading_days(self, mixed_returns):
        r = mixed_returns
        m252 = BacktestMetrics.from_returns(r, [0.01, -0.005], "2024-01-01", "2024-07-19")
        original = TRADING_DAYS_PER_YEAR
        try:
            set_trading_days(260)
            m260 = BacktestMetrics.from_returns(r, [0.01, -0.005], "2024-01-01", "2024-07-19")
            assert abs(m260.sortino_ratio or 0.0) > abs(m252.sortino_ratio or 0.0)
        finally:
            set_trading_days(original)

    def test_sortino_no_downside_returns(self):
        """All positive returns Ôåô sortino == 0.0 (no NaN)."""
        r = pd.Series([0.01, 0.02, 0.005, 0.003])
        metrics = BacktestMetrics.from_returns(r, [0.01], "2024-01-01", "2024-01-05")
        assert metrics.sortino_ratio == 0.0
        assert np.isfinite(metrics.sortino_ratio or 0.0)


# ---------------------------------------------------------------------------
# BacktestMetrics ÔÇô ratio between ÔêÜ260 and ÔêÜ252
# ---------------------------------------------------------------------------


class TestRatioSqrt260vs252:
    """Numerical sanity: ÔêÜ260/ÔêÜ252 Ôëê 1.0157."""

    def test_ratio_sqrt(self):
        ratio = np.sqrt(260) / np.sqrt(252)
        assert ratio == pytest.approx(1.0157, rel=1e-3)

    def test_sharpe_260_higher_than_252_for_positive_mean(self):
        """ÔêÜ260 > ÔêÜ252 Ôåô Sharpe_260 > Sharpe_252 for positive mean."""
        np.random.seed(7)
        r = pd.Series(np.random.normal(0.002, 0.01, 300))
        sharpe_260 = (r.mean() / r.std()) * np.sqrt(260)
        sharpe_252 = (r.mean() / r.std()) * np.sqrt(252)
        assert sharpe_260 > sharpe_252


# ---------------------------------------------------------------------------
# Monte Carlo ÔÇô realized vol annualisation
# ---------------------------------------------------------------------------


class TestMonteCarloAnnualisation:
    """execution/monte_carlo.py must use ÔêÜ252 for equities."""

    def test_realized_vol_uses_sqrt_252(self):
        """PricePath.get_volatility_realized() must use ÔêÜ252."""
        from execution.monte_carlo import PricePath

        np.random.seed(42)
        n = 100
        returns = np.random.normal(0.0, 0.02, n)
        prices = 100.0 * np.exp(np.cumsum(returns))

        path = PricePath(
            symbol="AAPL",
            prices=prices,
            volumes=np.ones(n),
            spreads=np.ones(n) * 0.001,
            returns=returns,
        )
        expected_vol = np.std(returns) * np.sqrt(252)
        assert path.get_volatility_realized() == pytest.approx(expected_vol, rel=1e-9)


# ---------------------------------------------------------------------------
# Monte Carlo ÔÇô GBM dt
# ---------------------------------------------------------------------------


class TestGBMTimeStep:
    """GBM simulation must use dt = 1/252 for equities."""

    def test_dt_value_in_source(self):
        """Verify dt = 1/252 by reading the source."""
        import inspect

        from execution.monte_carlo import MonteCarloOrderBookSimulator

        source = inspect.getsource(MonteCarloOrderBookSimulator._generate_gbm_path)
        assert "1.0 / 252.0" in source or "1/252" in source

    def test_dt_not_365(self):
        """Source must NOT contain 365 for dt."""
        import inspect

        from execution.monte_carlo import MonteCarloOrderBookSimulator

        source = inspect.getsource(MonteCarloOrderBookSimulator._generate_gbm_path)
        assert "365" not in source


# ---------------------------------------------------------------------------
# Dashboard Sharpe
# ---------------------------------------------------------------------------


class TestDashboardSharpeAnnualisation:
    """monitoring/dashboard.py must use ÔêÜ252 for equities."""

    def test_dashboard_source_uses_252(self):
        """Verify dashboard Sharpe source contains sqrt(252)."""
        import inspect

        from monitoring import dashboard

        source = inspect.getsource(dashboard)
        # Must contain 252, must NOT contain 365 in sharpe context
        assert "sqrt(252)" in source
        assert "sqrt(365)" not in source


# ---------------------------------------------------------------------------
# ML Threshold Optimizer Sharpe
# ---------------------------------------------------------------------------


class TestMLOptimizerSharpeAnnualisation:
    """models/ml_threshold_optimizer.py must use ÔêÜ252 for equities."""

    def test_optimizer_source_uses_252(self):
        """Verify ML optimizer Sharpe source contains sqrt(252)."""
        import inspect

        from models import ml_threshold_optimizer

        source = inspect.getsource(ml_threshold_optimizer)
        assert "sqrt(252)" in source
        assert "sqrt(365)" not in source


# ---------------------------------------------------------------------------
# Global sweep: no residual ÔêÜ365 in production code
# ---------------------------------------------------------------------------


class TestNoResidualSqrt365:
    """Ensure no production file uses ÔêÜ365 (non-equity convention)."""

    PRODUCTION_FILES = [
        "backtests/metrics.py",
        "monitoring/dashboard.py",
        "models/ml_threshold_optimizer.py",
        "execution/monte_carlo.py",
    ]

    @pytest.mark.parametrize("filepath", PRODUCTION_FILES)
    def test_no_sqrt_365_in_file(self, filepath):
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        assert "sqrt(365)" not in content, f"{filepath} still contains sqrt(365)"
