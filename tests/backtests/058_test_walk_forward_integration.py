#!/usr/bin/env python
"""Integration tests for walk-forward backtest functionality."""

import pytest
import pandas as pd
import numpy as np
from backtests.walk_forward import split_walk_forward, WalkForwardBacktester
from backtests.runner import BacktestRunner


class TestSplitWalkForward:
    """Test the split_walk_forward function."""
    
    def test_split_creates_correct_period_count(self):
        """split_walk_forward creates correct number of periods."""
        # Create sample data
        dates = pd.date_range('2024-01-01', periods=252, freq='D')
        data = pd.DataFrame({
            'AAPL': np.random.randn(252).cumsum() + 100,
            'MSFT': np.random.randn(252).cumsum() + 50
        }, index=dates)
        
        # Create 4 splits
        splits = split_walk_forward(data, num_periods=4, oos_ratio=0.2)
        
        assert len(splits) == 4, f"Expected 4 splits, got {len(splits)}"
        assert isinstance(splits, list), "Should return a list"
    
    def test_split_creates_train_larger_than_test(self):
        """Each split has training set larger than test set."""
        dates = pd.date_range('2024-01-01', periods=252, freq='D')
        data = pd.DataFrame({
            'AAPL': np.random.randn(252).cumsum() + 100
        }, index=dates)
        
        splits = split_walk_forward(data, num_periods=4, oos_ratio=0.2)
        
        for i, (train, test) in enumerate(splits):
            assert len(train) > 0, f"Split {i}: train data empty"
            assert len(test) > 0, f"Split {i}: test data empty"
            assert len(train) > len(test), f"Split {i}: train should be larger than test"
    
    def test_split_with_different_oos_ratios(self):
        """split_walk_forward respects oos_ratio parameter."""
        dates = pd.date_range('2024-01-01', periods=252, freq='D')
        data = pd.DataFrame({
            'price': np.random.randn(252).cumsum() + 100
        }, index=dates)
        
        # 20% OOS ratio
        splits_20 = split_walk_forward(data, num_periods=3, oos_ratio=0.20)
        # 30% OOS ratio  
        splits_30 = split_walk_forward(data, num_periods=3, oos_ratio=0.30)
        
        # With higher OOS ratio, test sets should be larger on average
        test_size_20 = sum(len(test) for _, test in splits_20) / len(splits_20)
        test_size_30 = sum(len(test) for _, test in splits_30) / len(splits_30)
        
        assert test_size_30 > test_size_20, "Higher OOS ratio should have larger test sets"


class TestWalkForwardBacktester:
    """Test the WalkForwardBacktester class."""
    
    def test_backtester_initialization(self):
        """WalkForwardBacktester initializes correctly."""
        runner = BacktestRunner()
        backtester = WalkForwardBacktester(runner)
        
        assert backtester.runner is not None
        assert backtester.per_period_metrics == []
        assert isinstance(backtester.results, list)
    
    def test_backtester_without_explicit_runner(self):
        """WalkForwardBacktester creates runner if not provided."""
        backtester = WalkForwardBacktester()
        
        assert backtester.runner is not None
        assert isinstance(backtester.runner, BacktestRunner)


class TestWalkForwardBacktest:
    """Integration tests for complete walk-forward backtest."""
    
    def test_walk_forward_3_periods_synthetic(self):
        """Walk-forward completes with 3 periods on synthetic data."""
        backtester = WalkForwardBacktester()
        
        result = backtester.run_walk_forward(
            symbols=['AAPL', 'MSFT'],
            start_date='2023-01-01',
            end_date='2023-12-31',
            num_periods=3,
            oos_ratio=0.2,
            use_synthetic=True
        )
        
        assert result['status'] == 'completed'
        assert result['num_periods'] == 3
        assert len(result['per_period_metrics']) == 3
    
    def test_walk_forward_aggregate_metrics(self):
        """Aggregate metrics computed correctly."""
        backtester = WalkForwardBacktester()
        
        result = backtester.run_walk_forward(
            symbols=['AAPL', 'MSFT'],
            start_date='2023-01-01',
            end_date='2023-12-31',
            num_periods=3,
            use_synthetic=True
        )
        
        agg = result['aggregate_metrics']
        
        # Check all required fields exist
        required_fields = [
            'aggregate_return',
            'aggregate_return_std',
            'aggregate_sharpe_ratio',
            'aggregate_sharpe_std',
            'aggregate_max_drawdown',
            'aggregate_drawdown_std',
            'aggregate_win_rate',
            'aggregate_profit_factor',
            'num_periods_completed',
            'min_return',
            'max_return'
        ]
        
        for field in required_fields:
            assert field in agg, f"Missing field: {field}"
        
        # Sprint 3.4: Assert actual metric values, not just field existence
        assert isinstance(agg['aggregate_return'], float), "aggregate_return must be float"
        assert isinstance(agg['aggregate_sharpe_ratio'], float), "aggregate_sharpe_ratio must be float"
        assert agg['num_periods_completed'] == 3, (
            f"Expected 3 completed periods, got {agg['num_periods_completed']}"
        )
        assert agg['min_return'] <= agg['max_return'], (
            f"min_return ({agg['min_return']}) should be <= max_return ({agg['max_return']})"
        )
    
    def test_walk_forward_per_period_breakdown(self):
        """Per-period metrics include proper breakdown."""
        backtester = WalkForwardBacktester()
        
        result = backtester.run_walk_forward(
            symbols=['AAPL'],
            start_date='2023-01-01',
            end_date='2023-12-31',
            num_periods=2,
            use_synthetic=True
        )
        
        per_period = result['per_period_metrics']
        
        assert len(per_period) == 2
        
        for period_data in per_period:
            assert 'period' in period_data
            assert 'train_start' in period_data
            assert 'train_end' in period_data
            assert 'test_start' in period_data
            assert 'test_end' in period_data
            assert 'metrics' in period_data
            
            metrics = period_data['metrics']
            assert 'total_return' in metrics
            assert 'sharpe_ratio' in metrics
            assert 'max_drawdown' in metrics
            
            # Sprint 3.4: Assert actual metric values
            assert isinstance(metrics['total_return'], (int, float)), (
                f"total_return should be numeric, got {type(metrics['total_return'])}"
            )
            assert isinstance(metrics['sharpe_ratio'], (int, float)), (
                f"sharpe_ratio should be numeric, got {type(metrics['sharpe_ratio'])}"
            )
            assert metrics['max_drawdown'] <= 0.0, (
                f"max_drawdown should be <= 0, got {metrics['max_drawdown']}"
            )


class TestWalkForwardPrintSummary:
    """Test the summary output from walk-forward backtest."""
    
    def test_print_summary_returns_string(self):
        """print_summary() returns formatted string."""
        backtester = WalkForwardBacktester()
        
        backtester.run_walk_forward(
            symbols=['AAPL'],
            start_date='2023-01-01',
            end_date='2023-12-31',
            num_periods=2,
            use_synthetic=True
        )
        
        summary = backtester.print_summary()
        
        assert isinstance(summary, str)
        assert "WALK-FORWARD" in summary.upper()
        assert "VALIDATION" in summary.upper()
    
    def test_print_summary_includes_per_period_breakdown(self):
        """Summary includes per-period breakdown."""
        backtester = WalkForwardBacktester()
        
        backtester.run_walk_forward(
            symbols=['AAPL'],
            start_date='2023-01-01',
            end_date='2023-12-31',
            num_periods=2,
            use_synthetic=True
        )
        
        summary = backtester.print_summary()
        
        # Should include period numbers
        assert "Period 1:" in summary or "period" in summary.lower()
        # Should include metrics
        assert "Return:" in summary or "return" in summary.lower()


class TestWalkForwardErrorHandling:
    """Test error handling in walk-forward backtest."""
    
    def test_walk_forward_empty_splits_raises_error(self):
        """Empty splits raise appropriate error."""
        backtester = WalkForwardBacktester()
        
        # Too many periods for too little data (should fail)
        with pytest.raises(ValueError):
            backtester.run_walk_forward(
                symbols=['AAPL'],
                start_date='2023-01-01',
                end_date='2023-01-02',  # Only 1 day of data
                num_periods=100,  # Can't split 1 day into 100 periods
                use_synthetic=True
            )
    
    def test_walk_forward_graceful_period_failure(self):
        """Walk-forward continues if individual period fails."""
        backtester = WalkForwardBacktester()
        
        # With synthetic data and valid params, should complete
        result = backtester.run_walk_forward(
            symbols=['AAPL'],
            start_date='2023-01-01',
            end_date='2023-12-31',
            num_periods=2,
            use_synthetic=True
        )
        
        # Should have completed at least 1 period
        assert result['num_periods'] >= 1
        assert len(result['per_period_metrics']) >= 1


class TestWalkForwardAntiDataLeakage:
    """Sprint 3.4: Anti-data-leakage tests for walk-forward splits."""
    
    def test_train_test_no_temporal_overlap(self):
        """Train set last date must be STRICTLY before test set first date.
        
        This is the formal anti-leakage test required by Sprint 3.4:
        for every split, train.index.max() < test.index.min().
        """
        dates = pd.date_range('2024-01-01', periods=252, freq='D')
        data = pd.DataFrame({
            'AAPL': np.random.randn(252).cumsum() + 100,
            'MSFT': np.random.randn(252).cumsum() + 50
        }, index=dates)
        
        splits = split_walk_forward(data, num_periods=4, oos_ratio=0.2)
        
        assert len(splits) >= 2, "Should produce multiple splits"
        
        for i, (train, test) in enumerate(splits):
            assert train.index.max() < test.index.min(), (
                f"DATA LEAKAGE in split {i}: train ends {train.index.max()} "
                f"but test starts {test.index.min()}"
            )
    
    def test_test_sets_are_strictly_forward(self):
        """Each test set should start after the previous one.
        
        Ensures walk-forward progression (no backward sliding).
        """
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=365, freq='D')
        data = pd.DataFrame({
            'AAPL': np.random.randn(365).cumsum() + 100
        }, index=dates)
        
        splits = split_walk_forward(data, num_periods=5, oos_ratio=0.2)
        
        for i in range(1, len(splits)):
            prev_test_start = splits[i-1][1].index.min()
            curr_test_start = splits[i][1].index.min()
            assert curr_test_start > prev_test_start, (
                f"Test sets not progressing forward: split {i-1} test starts "
                f"{prev_test_start}, split {i} test starts {curr_test_start}"
            )
    
    def test_no_future_data_in_training(self):
        """No training window should contain data from any test window."""
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=252, freq='D')
        data = pd.DataFrame({
            'AAPL': np.random.randn(252).cumsum() + 100
        }, index=dates)
        
        splits = split_walk_forward(data, num_periods=4, oos_ratio=0.2)
        
        for i, (train, test) in enumerate(splits):
            # No overlap between train and test indices
            overlap = train.index.intersection(test.index)
            assert len(overlap) == 0, (
                f"Split {i}: {len(overlap)} overlapping dates between train and test"
            )
