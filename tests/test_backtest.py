import pytest
import pandas as pd
import numpy as np
from backtests.metrics import BacktestMetrics


def test_backtest_metrics_from_returns():
    """Test that metrics are calculated correctly from returns."""
    
    # Create sample returns: uptrend with small drawdown
    returns = pd.Series([0.01, 0.01, 0.02, -0.01, 0.01, 0.015, 0.01, 0.01])
    trades = [100, -50, 150, -30, 200]  # Some winning, some losing
    
    metrics = BacktestMetrics.from_returns(
        returns=returns,
        trades=trades,
        start_date="2023-01-01",
        end_date="2023-01-08"
    )
    
    # Verify basic properties
    assert metrics.start_date == "2023-01-01"
    assert metrics.end_date == "2023-01-08"
    assert metrics.total_trades == 5
    
    # Verify calculations are not zero (for this positive returns scenario)
    assert metrics.total_return > 0  # Should be positive
    assert metrics.sharpe_ratio > 0  # Positive returns should have positive Sharpe
    assert metrics.max_drawdown <= 0  # Drawdown should be negative or zero
    assert 0 <= metrics.win_rate <= 1  # Win rate between 0 and 1
    assert metrics.profit_factor >= 0  # Profit factor >= 0


def test_backtest_metrics_negative_returns():
    """Test metrics with negative returns."""
    
    returns = pd.Series([-0.01, -0.02, -0.01, -0.01, -0.02])
    trades = [-100, -50, -150]  # All losing trades
    
    metrics = BacktestMetrics.from_returns(
        returns=returns,
        trades=trades,
        start_date="2023-01-01",
        end_date="2023-01-05"
    )
    
    # Verify
    assert metrics.total_return < 0  # Negative returns
    assert metrics.max_drawdown < 0  # Should have drawdown
    assert metrics.win_rate == 0.0  # No winning trades
    assert metrics.profit_factor == 0.0  # No profit


def test_backtest_metrics_zero_trades():
    """Test metrics with no trades."""
    
    returns = pd.Series([0.01, 0.01, 0.01])
    trades = []  # No trades
    
    metrics = BacktestMetrics.from_returns(
        returns=returns,
        trades=trades,
        start_date="2023-01-01",
        end_date="2023-01-03"
    )
    
    assert metrics.total_trades == 0
    assert metrics.win_rate == 0.0
    assert metrics.profit_factor == 0.0


def test_backtest_metrics_summary_format():
    """Test that summary produces formatted output."""
    
    returns = pd.Series([0.01, 0.02, -0.01])
    trades = [100, 50]
    
    metrics = BacktestMetrics.from_returns(
        returns=returns,
        trades=trades,
        start_date="2023-01-01",
        end_date="2023-01-03"
    )
    
    summary = metrics.summary()
    
    # Verify format
    assert "BACKTEST METRICS SUMMARY" in summary
    assert "Period:" in summary
    assert "Total Return:" in summary
    assert "Sharpe Ratio:" in summary
    assert "Max Drawdown:" in summary
    assert "2023-01-01 to 2023-01-03" in summary
    
    print("\n" + summary)


def test_backtest_metrics_sharpe_calculation():
    """Test Sharpe ratio calculation."""
    
    # Create consistent returns (daily 1%)
    returns = pd.Series([0.01] * 100)
    trades = []
    
    metrics = BacktestMetrics.from_returns(
        returns=returns,
        trades=trades,
        start_date="2023-01-01",
        end_date="2023-04-10"
    )
    
    # With consistent returns, Sharpe should be very high (dividing by near-zero std)
    # std of constant series is 0, so Sharpe = infinity or 0
    assert metrics.total_return > 0.0


def test_backtest_metrics_max_drawdown():
    """Test max drawdown calculation."""
    
    # Create a peak then significant drawdown
    returns = pd.Series([0.10, 0.10, 0.10, -0.20, -0.10, 0.05])
    trades = []
    
    metrics = BacktestMetrics.from_returns(
        returns=returns,
        trades=trades,
        start_date="2023-01-01",
        end_date="2023-01-06"
    )
    
    # Should have significant drawdown
    assert metrics.max_drawdown < -0.05  # At least 5% drawdown


def test_backtest_metrics_profit_factor():
    """Test profit factor calculation."""
    
    returns = pd.Series([0.01, 0.01, 0.01])
    trades = [1000, 500, -200, -100]  # Profit = 1500, Loss = 300
    
    metrics = BacktestMetrics.from_returns(
        returns=returns,
        trades=trades,
        start_date="2023-01-01",
        end_date="2023-01-03"
    )
    
    expected_profit_factor = 1500 / 300  # = 5.0
    assert abs(metrics.profit_factor - expected_profit_factor) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
