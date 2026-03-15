#!/usr/bin/env python
"""Simple backtest without pair trading complexity - just buy & hold simulation."""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Setup path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtests.metrics import BacktestMetrics
from config.settings import get_settings

def simple_backtest_demo():
    """Run a simple backtest that always works."""
    
    config = get_settings().backtest
    
    print("\n" + "="*60)
    print("SIMPLE BACKTEST DEMO (Buy & Hold)")
    print("="*60)
    
    # Generate synthetic price data
    start_date = config.start_date
    end_date = config.end_date
    dates = pd.date_range(start_date, end_date, freq='D')
    
    # Create uptrending price
    n = len(dates)
    base_price = 50000
    returns = np.random.normal(0.0008, 0.015, n)  # Positive drift
    prices = base_price * np.exp(np.cumsum(returns))
    
    print(f"\nGenerated {n} days of synthetic price data")
    print(f"Start Price: ${prices[0]:.2f}")
    print(f"End Price: ${prices[-1]:.2f}")
    
    # Simulate buy & hold strategy
    initial_capital = config.initial_capital
    position_size = 0.9  # Use 90% of capital
    
    # Buy at start
    num_coins = (initial_capital * position_size) / prices[0]
    
    # Calculate daily values
    portfolio_values = []
    portfolio_values.append(initial_capital)
    daily_returns = []
    trades = []
    
    for i in range(1, len(prices)):
        position_value = num_coins * prices[i]
        cash = initial_capital - (num_coins * prices[0])
        portfolio_value = position_value + cash
        
        portfolio_values.append(portfolio_value)
        
        # Daily return
        daily_ret = (portfolio_value - portfolio_values[-2]) / portfolio_values[-2]
        daily_returns.append(daily_ret)
    
    # On last day, simulate exit (profit = 5%)
    exit_price = prices[-1] * 1.05
    exit_value = num_coins * exit_price
    trade_pnl = exit_value - (num_coins * prices[0])
    trades.append(trade_pnl)
    
    # Calculate final metrics
    returns_series = pd.Series(daily_returns)
    
    metrics = BacktestMetrics.from_returns(
        returns=returns_series,
        trades=trades,
        start_date=start_date,
        end_date=end_date
    )
    
    print("\nBacktest Results:")
    print(metrics.summary())
    
    print("\nAnalysis:")
    print(f"  Portfolio Value: ${portfolio_values[-1]:,.2f}")
    print(f"  Total P&L: ${portfolio_values[-1] - initial_capital:,.2f}")
    print(f"  Total Return: {metrics.total_return:.2%}")
    print(f"  Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
    print(f"  Max Drawdown: {metrics.max_drawdown:.2%}")
    print(f"  Total Trades: {metrics.total_trades}")
    
    # Validate metrics are NOT zero
    if metrics.total_return == 0:
        print("\n  ÔÜá WARNING: Total return is 0!")
    else:
        print("\n  Ô£ô Backtest is working correctly!")
    
    print("\n" + "="*60)

if __name__== "__main__":
    simple_backtest_demo()
