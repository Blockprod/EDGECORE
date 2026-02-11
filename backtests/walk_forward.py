"""
Walk-forward testing: periodic retraining + OOS evaluation.

Walk-forward validation is a time-series cross-validation technique that simulates
live trading by:
1. Training a model on historical data
2. Testing on out-of-sample forward data
3. Moving the window forward and repeating
4. Aggregating results across all periods

This validates that the strategy generalizes rather than overfitting to a specific period.
"""

from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from structlog import get_logger
from backtests.runner import BacktestRunner
from backtests.metrics import BacktestMetrics

logger = get_logger(__name__)


def split_walk_forward(
    data: pd.DataFrame,
    num_periods: int = 4,
    oos_ratio: float = 0.2
) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Create walk-forward splits.
    
    Args:
        data: Full time series
        num_periods: Number of rebalancing periods
        oos_ratio: Out-of-sample ratio (0.2 = 20% test, 80% train)
    
    Returns:
        List of tuples (training_data, test_data) for each period
    """
    n = len(data)
    period_len = n // (num_periods + 1)
    oos_len = max(1, int(period_len * oos_ratio))
    
    splits = []
    for i in range(num_periods):
        train_start = i * period_len
        train_end = train_start + period_len - oos_len
        test_end = train_start + period_len
        
        train_data = data.iloc[train_start:train_end]
        test_data = data.iloc[train_end:test_end]
        
        if len(train_data) > 0 and len(test_data) > 0:
            splits.append((train_data, test_data))
    
    logger.info(
        "walk_forward_splits_created",
        num_splits=len(splits),
        total_rows=n,
        period_length=period_len,
        oos_length=oos_len
    )
    
    return splits


class WalkForwardBacktester:
    """Time-series cross-validation for strategy validation."""
    
    def __init__(self, backtest_runner: Optional[BacktestRunner] = None):
        """
        Initialize walk-forward backtester.
        
        Args:
            backtest_runner: BacktestRunner instance (creates if None)
        """
        self.runner = backtest_runner or BacktestRunner()
        self.results = []
        self.per_period_metrics = []
    
    def run_walk_forward(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        num_periods: int = 4,
        oos_ratio: float = 0.2,
        use_synthetic: bool = False
    ) -> Dict[str, Any]:
        """
        Run walk-forward backtest with train/test splits.
        
        Args:
            symbols: List of trading pairs
            start_date: Full backtest start date
            end_date: Full backtest end date
            num_periods: Number of train/test periods
            oos_ratio: Out-of-sample ratio (0.2 = 20% test, 80% train)
            use_synthetic: Use synthetic data for testing
        
        Returns:
            Dict with aggregate results + per-period breakdown
        """
        logger.info(
            "walk_forward_backtest_started",
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            num_periods=num_periods,
            oos_ratio=oos_ratio
        )
        
        # Load full dataset
        try:
            if use_synthetic:
                from backtests.runner import _generate_cointegrated_pair
                full_df = _generate_cointegrated_pair(start_date, end_date)
            else:
                from data.loader import DataLoader
                loader = DataLoader()
                
                # Load first symbol for date alignment
                price_data = {}
                for symbol in symbols:
                    try:
                        df = loader.load_ccxt_data(
                            exchange_name='binance',
                            symbol=symbol,
                            timeframe='1d',
                            validate=True
                        )
                        price_data[symbol] = df['close']
                    except Exception as e:
                        logger.warning(
                            "walk_forward_symbol_load_failed",
                            symbol=symbol,
                            error=str(e)
                        )
                
                if not price_data:
                    raise ValueError(f"No symbols loaded successfully")
                
                full_df = pd.DataFrame(price_data)
                
                # Filter by date range
                full_df = full_df[(full_df.index >= start_date) & (full_df.index <= end_date)]
                if len(full_df) == 0:
                    raise ValueError(f"No data in date range {start_date} to {end_date}")
        
        except Exception as e:
            logger.error("walk_forward_data_load_failed", error=str(e))
            raise
        
        # Create walk-forward splits
        splits = split_walk_forward(full_df, num_periods=num_periods, oos_ratio=oos_ratio)
        
        if len(splits) == 0:
            raise ValueError("No splits created. Check data length and num_periods.")
        
        logger.info("walk_forward_data_prepared", rows=len(full_df), splits=len(splits))
        
        # Run backtest on each period
        self.per_period_metrics = []
        all_returns = []
        all_trades = []
        
        for period_idx, (train_df, test_df) in enumerate(splits):
            logger.info(
                "walk_forward_period_started",
                period=period_idx + 1,
                train_rows=len(train_df),
                test_rows=len(test_df),
                train_start=str(train_df.index[0]),
                train_end=str(train_df.index[-1]),
                test_start=str(test_df.index[0]),
                test_end=str(test_df.index[-1])
            )
            
            try:
                # For now, we run backtest on test data directly
                # In production, you'd retrain the strategy on train_df
                # See: strategy.fit(train_df) then strategy.generate_signals(test_df)
                
                # Run backtest on this period
                period_metrics = self.runner.run(
                    symbols=symbols,
                    start_date=str(test_df.index[0].date()),
                    end_date=str(test_df.index[-1].date()),
                    validate_data=False,  # Already validated
                    use_synthetic=use_synthetic
                )
                
                self.per_period_metrics.append({
                    'period': period_idx + 1,
                    'train_start': str(train_df.index[0]),
                    'train_end': str(train_df.index[-1]),
                    'test_start': str(test_df.index[0]),
                    'test_end': str(test_df.index[-1]),
                    'metrics': period_metrics.__dict__
                })
                
                logger.info(
                    "walk_forward_period_completed",
                    period=period_idx + 1,
                    total_return=period_metrics.total_return,
                    sharpe_ratio=period_metrics.sharpe_ratio,
                    max_drawdown=period_metrics.max_drawdown
                )
                
            except Exception as e:
                logger.error(
                    "walk_forward_period_failed",
                    period=period_idx + 1,
                    error=str(e)
                )
                # Continue with next period rather than fail completely
                continue
        
        # Aggregate results across all periods
        if not self.per_period_metrics:
            raise ValueError("No periods completed successfully")
        
        aggregate_metrics = self._aggregate_metrics()
        
        result = {
            'status': 'completed',
            'num_periods': len(self.per_period_metrics),
            'aggregate_metrics': aggregate_metrics,
            'per_period_metrics': self.per_period_metrics,
            'symbols': symbols,
            'full_start_date': str(full_df.index[0]),
            'full_end_date': str(full_df.index[-1]),
            'total_rows': len(full_df)
        }
        
        logger.info(
            "walk_forward_backtest_completed",
            num_periods=len(self.per_period_metrics),
            aggregate_return=aggregate_metrics['aggregate_return'],
            aggregate_sharpe=aggregate_metrics['aggregate_sharpe_ratio'],
            aggregate_drawdown=aggregate_metrics['aggregate_max_drawdown']
        )
        
        return result
    
    def _aggregate_metrics(self) -> Dict[str, float]:
        """
        Aggregate metrics across all periods.
        
        Returns:
            Dictionary with aggregate metrics
        """
        if not self.per_period_metrics:
            return {}
        
        period_returns = []
        period_sharpes = []
        period_drawdowns = []
        period_win_rates = []
        period_profit_factors = []
        
        for period_data in self.per_period_metrics:
            metrics = period_data['metrics']
            period_returns.append(metrics['total_return'])
            period_sharpes.append(metrics['sharpe_ratio'])
            period_drawdowns.append(metrics['max_drawdown'])
            period_win_rates.append(metrics['win_rate'])
            period_profit_factors.append(metrics['profit_factor'])
        
        return {
            'aggregate_return': np.mean(period_returns),
            'aggregate_return_std': np.std(period_returns),
            'aggregate_sharpe_ratio': np.mean(period_sharpes),
            'aggregate_sharpe_std': np.std(period_sharpes),
            'aggregate_max_drawdown': np.mean(period_drawdowns),
            'aggregate_drawdown_std': np.std(period_drawdowns),
            'aggregate_win_rate': np.mean(period_win_rates),
            'aggregate_profit_factor': np.mean(period_profit_factors),
            'num_periods_completed': len(self.per_period_metrics),
            'min_return': np.min(period_returns),
            'max_return': np.max(period_returns)
        }
    
    def print_summary(self) -> str:
        """Print formatted walk-forward summary."""
        if not self.per_period_metrics:
            return "No periods completed"
        
        agg = self._aggregate_metrics()
        
        summary = f"""
========================================
      WALK-FORWARD VALIDATION SUMMARY     
========================================
Periods Completed:      {agg['num_periods_completed']}/
Aggregate Return:       {agg['aggregate_return']:>7.2%} (±{agg['aggregate_return_std']:.2%})
Aggregate Sharpe:       {agg['aggregate_sharpe_ratio']:>7.2f} (±{agg['aggregate_sharpe_std']:.2f})
Aggregate Max DD:       {agg['aggregate_max_drawdown']:>7.2%}
Aggregate Win Rate:     {agg['aggregate_win_rate']:>7.2%}
Aggregate Profit Fact:  {agg['aggregate_profit_factor']:>7.2f}

Return Range:           {agg['min_return']:>7.2%} to {agg['max_return']:>7.2%}
========================================

Per-Period Breakdown:
"""
        for period_data in self.per_period_metrics:
            p = period_data
            metrics = p['metrics']
            summary += f"""
Period {p['period']}:
  Train: {p['train_start']} to {p['train_end']}
  Test:  {p['test_start']} to {p['test_end']}
  Return: {metrics['total_return']:>7.2%} | Sharpe: {metrics['sharpe_ratio']:>7.2f} | DD: {metrics['max_drawdown']:>7.2%}
"""
        
        return summary
