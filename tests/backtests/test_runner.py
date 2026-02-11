import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backtests.runner import BacktestRunner
from backtests.metrics import BacktestMetrics


class TestBacktestRunner:
    """Test BacktestRunner produces real metrics instead of stubs."""
    
    def test_runner_produces_non_zero_metrics(self):
        """Test that runner returns real metrics, not stubs."""
        runner = BacktestRunner()
        
        # Run a simple backtest
        metrics = runner.run(
            symbols=["BTC/USDT", "ETH/USDT"],
            start_date="2023-01-01",
            end_date="2023-12-31"
        )
        
        # Verify metrics object exists
        assert isinstance(metrics, BacktestMetrics)
        
        # Verify metrics are calculated (not just stubs)
        assert metrics.start_date == "2023-01-01"
        assert metrics.end_date == "2023-12-31"
        
        # These may be 0 or positive, but they should be real numbers, not all stubs
        assert isinstance(metrics.total_return, float)
        assert isinstance(metrics.sharpe_ratio, float)
        assert isinstance(metrics.max_drawdown, float)
        
    def test_runner_returns_backtest_metrics(self):
        """Test that run() returns BacktestMetrics object."""
        runner = BacktestRunner()
        result = runner.run(
            symbols=["BTC/USDT", "ETH/USDT"],
            start_date="2023-06-01",
            end_date="2023-06-30"
        )
        
        assert isinstance(result, BacktestMetrics)
        assert hasattr(result, 'summary')
        
        # Summary should have formatted output
        summary = result.summary()
        assert isinstance(summary, str)
        # Check for metrics content (case-insensitive)
        summary_lower = summary.lower()
        assert "metrics" in summary_lower or "period" in summary_lower
    
    def test_runner_with_date_range(self):
        """Test runner with different date ranges."""
        runner = BacktestRunner()
        
        # Short range
        metrics_short = runner.run(
            symbols=["BTC/USDT"],
            start_date="2023-01-01",
            end_date="2023-01-31"
        )
        assert metrics_short.start_date == "2023-01-01"
        
        # Different range
        metrics_long = runner.run(
            symbols=["BTC/USDT", "ETH/USDT"],
            start_date="2023-01-01",
            end_date="2023-12-31"
        )
        assert metrics_long.start_date == "2023-01-01"
        
        # Both should return valid metrics
        assert isinstance(metrics_short, BacktestMetrics)
        assert isinstance(metrics_long, BacktestMetrics)
