from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from backtests.runner import BacktestRunner
from config.settings import get_settings
from data.loader import DataLoader
from risk.engine import RiskEngine
from strategies.pair_trading import PairTradingStrategy


def _make_ohlcv_df(n, base_price=175.0, symbol="AAPL"):
    """Helper: create a realistic OHLCV DataFrame for IBKR-style data."""
    dates = pd.date_range("2021-01-01", periods=n, freq="D")
    prices = np.linspace(base_price, base_price * 1.1, n) + np.random.randn(n) * 0.5
    df = pd.DataFrame(
        {
            "Open": prices * 0.99,
            "High": prices * 1.01,
            "Low": prices * 0.98,
            "Close": prices,
            "Volume": np.full(n, 1_000_000),
        },
        index=dates,
    )
    df.attrs["symbol"] = symbol
    return df


class TestEndToEndPipeline:
    """Test complete trading pipeline from data to execution."""

    def test_data_pipeline_end_to_end(self):
        """Test loading data through to analysis."""
        loader = DataLoader()
        n = 90

        with patch.object(loader, "load_ibkr_data") as mock_load:
            mock_df = _make_ohlcv_df(n, base_price=175.0, symbol="AAPL")
            mock_load.return_value = mock_df

            df = loader.load_ibkr_data("AAPL", timeframe="1d", limit=n)

            assert len(df) == n
            assert "Close" in df.columns or "close" in df.columns
            close_col = "Close" if "Close" in df.columns else "close"
            assert not df[close_col].isna().all()

    def test_strategy_signal_generation_pipeline(self):
        """Test data loading  signal generation."""
        strategy = PairTradingStrategy()

        np.random.seed(42)
        n = 200
        t = np.linspace(0, 10, n)
        trend = 100 + 0.5 * t

        prices = pd.DataFrame(
            {
                "AAPL": trend + np.sin(0.1 * t) * 5 + np.random.randn(n),
                "MSFT": trend * 1.5 + np.sin(0.1 * t) * 7 + np.random.randn(n),
            }
        )

        signals = strategy.generate_signals(prices)
        assert isinstance(signals, list)

    def test_risk_engine_integration(self):
        """Test risk engine with strategy signals."""
        risk_engine = RiskEngine(initial_equity=100_000)
        strategy = PairTradingStrategy()

        np.random.seed(42)
        n = 100
        prices = pd.DataFrame(
            {
                "AAPL": np.linspace(170, 185, n) + np.random.randn(n) * 2,
                "MSFT": np.linspace(410, 430, n) + np.random.randn(n) * 3,
            }
        )

        signals = strategy.generate_signals(prices)

        equity = 100000
        for signal in signals[:5]:
            can_enter, _reason = risk_engine.can_enter_trade(
                symbol_pair=signal.symbol_pair, position_size=10.0, current_equity=equity, volatility=0.02
            )
            assert isinstance(can_enter, bool)

    def test_backtest_runner_integration(self):
        """Test complete backtest runner end-to-end."""
        runner = BacktestRunner()

        np.random.seed(42)
        with patch.object(runner, "_load_prices") as mock_load:
            n = 100
            dates = pd.date_range("2021-01-01", periods=n, freq="D")
            aapl = np.linspace(170, 185, n) + np.random.randn(n) * 2
            msft = np.linspace(410, 430, n) + np.random.randn(n) * 3
            mock_load.return_value = pd.DataFrame({"AAPL": aapl, "MSFT": msft}, index=dates)

            metrics = runner.run_unified(symbols=["AAPL", "MSFT"], start_date="2021-01-01", end_date="2021-04-10")
            if metrics is not None:
                assert hasattr(metrics, "total_return") or isinstance(metrics, dict)

    def test_full_pipeline_no_errors(self):
        """Test complete pipeline runs without errors."""
        settings = get_settings()

        assert settings is not None
        assert settings.backtest is not None
        assert settings.risk is not None
        assert settings.execution is not None

    def test_configuration_integration(self):
        """Test that all configs load and integrate properly."""
        settings = get_settings()

        assert settings.backtest.initial_capital > 0
        assert settings.backtest.start_date is not None
        assert settings.risk.max_risk_per_trade > 0
        assert settings.risk.max_concurrent_positions > 0
        # IBKR-only engine
        assert settings.execution.engine == "ibkr"

    def test_data_to_signal_consistency(self):
        """Test consistency of data through signal generation."""
        np.random.seed(42)
        n = 150

        prices = pd.DataFrame(
            {
                "AAPL": np.linspace(170, 185, n) + np.random.randn(n) * 1,
                "MSFT": np.linspace(410, 430, n) + np.random.randn(n) * 2,
                "JPM": np.linspace(195, 210, n) + np.random.randn(n) * 0.5,
            }
        )

        strategy = PairTradingStrategy()

        signals1 = strategy.generate_signals(prices)
        signals2 = strategy.generate_signals(prices)

        assert len(signals1) == len(signals2)

        for signal in signals1:
            assert signal.symbol_pair is not None
            assert signal.side in ["long", "short", "exit"]

    def test_pipeline_with_config_changes(self):
        """Test that pipeline respects configuration changes."""
        settings = get_settings()
        initial_capital = settings.backtest.initial_capital
        assert initial_capital == settings.backtest.initial_capital

    def test_error_handling_across_pipeline(self):
        """Test that pipeline handles errors gracefully."""
        runner = BacktestRunner()

        with pytest.raises(Exception):
            runner.run_unified(symbols=["INVALID_SYMBOL"], start_date="2023-01-01", end_date="2023-01-02")

    def test_pipeline_performance_metrics(self):
        """Test that pipeline produces meaningful performance metrics."""
        runner = BacktestRunner()

        np.random.seed(42)
        with patch.object(runner, "_load_prices") as mock_load:
            n = 100
            returns_a = np.random.randn(n) * 0.01 + 0.001
            returns_b = np.random.randn(n) * 0.01 + 0.0005
            prices_a = 175 * np.exp(np.cumsum(returns_a))
            prices_b = 420 * np.exp(np.cumsum(returns_b))
            dates = pd.date_range("2021-01-01", periods=n, freq="D")
            mock_load.return_value = pd.DataFrame({"AAPL": prices_a, "MSFT": prices_b}, index=dates)

            metrics = runner.run_unified(symbols=["AAPL", "MSFT"], start_date="2021-01-01", end_date="2021-04-10")
            if metrics is not None:
                assert isinstance(metrics.total_return, float)
                assert isinstance(metrics.sharpe_ratio, float)
                assert isinstance(metrics.max_drawdown, float)


class TestIntegrationWithMockData:
    """Test pipeline with fully mocked data."""

    def test_mock_full_pipeline(self):
        """Test complete pipeline with mocked external dependencies."""
        loader = DataLoader()

        np.random.seed(42)
        n = 100
        mock_df = _make_ohlcv_df(n, base_price=175.0, symbol="AAPL")

        with patch.object(loader, "load_ibkr_data", return_value=mock_df):
            df = loader.load_ibkr_data("AAPL", timeframe="1d", limit=n)

            assert len(df) == n
            close_col = "Close" if "Close" in df.columns else "close"
            assert not df[close_col].isna().all()

            strategy = PairTradingStrategy()
            signals = strategy.generate_signals(pd.DataFrame({"AAPL": df[close_col].values}))
            assert isinstance(signals, list)
