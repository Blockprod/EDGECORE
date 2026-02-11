#!/usr/bin/env python
"""Diagnose backtest data flow and signal generation."""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# Add project root to path (go up from scripts/)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

from backtests.runner import BacktestRunner
from data.loader import DataLoader
from strategies.pair_trading import PairTradingStrategy
from config.settings import get_settings
from structlog import get_logger

logger = get_logger(__name__)

def diagnose_backtest():
    """Diagnosis flow for backtest issues."""
    
    print("\n" + "="*60)
    print("EDGECORE BACKTEST DIAGNOSTICS")
    print("="*60)
    
    # 1. Check configuration
    print("\n[1] Configuration Check:")
    settings = get_settings()
    print(f"    Start Date: {settings.backtest.start_date}")
    print(f"    End Date: {settings.backtest.end_date}")
    print(f"    Initial Capital: ${settings.backtest.initial_capital:,.2f}")
    print(f"    Strategy Entry Z-Score: {settings.strategy.entry_z_score}")
    print(f"    Strategy Exit Z-Score: {settings.strategy.exit_z_score}")
    
    # 2. Try loading data manually
    print("\n[2] Data Loading Check:")
    loader = DataLoader()
    symbols = ["BTC/USDT", "ETH/USDT"]
    price_data = {}
    failed = []
    
    for symbol in symbols:
        try:
            print(f"    Loading {symbol}...", end=" ")
            df = loader.load_ccxt_data(
                exchange_name='binance',
                symbol=symbol,
                timeframe='1d',
                validate=False  # Skip validation for now
            )
            price_data[symbol] = df['close']
            print(f"✓ ({len(df)} rows)")
        except Exception as e:
            print(f"✗ ERROR: {str(e)[:50]}")
            failed.append((symbol, str(e)))
    
    if failed:
        print(f"\n    ⚠ {len(failed)} symbol(s) failed to load")
        print("    This is expected if CCXT cannot reach the exchange")
        print("    Continuing with synthetic test data...")
        
        # Create synthetic data for testing
        print("\n[3] Creating Synthetic Test Data:")
        dates = pd.date_range('2023-01-01', periods=365, freq='D')
        price_data = {}
        
        for symbol in symbols:
            # Generate correlated random walk
            np.random.seed(hash(symbol) % 2**32)
            returns = np.random.normal(0.0005, 0.02, len(dates))
            prices = 50000 * np.exp(np.cumsum(returns)) if 'BTC' in symbol else 3000 * np.exp(np.cumsum(returns))
            price_data[symbol] = pd.Series(prices, index=dates)
            print(f"    Generated {symbol}: {len(price_data[symbol])} points")
    
    # 3. Create DataFrame and check structure
    print("\n[4]DataFrame Structure:")
    if price_data:
        prices_df = pd.DataFrame(price_data)
        print(f"    Shape: {prices_df.shape}")
        print(f"    Columns: {list(prices_df.columns)}")
        print(f"    Date Range: {prices_df.index[0]} to {prices_df.index[-1]}")
        print(f"    Sample data:\n{prices_df.head(3)}")
    
    # 4. Test strategy signal generation
    print("\n[5] Strategy Signal Generation:")
    strategy = PairTradingStrategy()
    try:
        signals = strategy.generate_signals(prices_df)
        print(f"    Generated {len(signals)} signal(s)")
        for i, sig in enumerate(signals[:3]):
            print(f"      Signal {i+1}: {sig.symbol_pair} - {sig.side} (strength: {sig.strength:.2f})")
    except Exception as e:
        print(f"    ✗ Error: {str(e)[:100]}")
        signals = []
    
    # 5. Run full backtest
    print("\n[6] Full Backtest Run:")
    try:
        runner = BacktestRunner()
        metrics = runner.run(
            symbols,
            start_date=settings.backtest.start_date,
            end_date=settings.backtest.end_date
        )
        print(metrics.summary())
        print(f"\n    Total Return: {metrics.total_return:.2%}")
        print(f"    Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        print(f"    Max Drawdown: {metrics.max_drawdown:.2%}")
        print(f"    Win Rate: {metrics.win_rate:.2%}")
        print(f"    Total Trades: {metrics.total_trades}")
        
        # Check if metrics are all zeros
        if all([
            metrics.total_return == 0,
            metrics.sharpe_ratio == 0,
            metrics.max_drawdown == 0,
            metrics.win_rate == 0
        ]):
            print("\n    ⚠⚠⚠ WARNING: All metrics are zero ⚠⚠⚠")
            print("    This suggests NO trades were generated or P&L calculated")
            
    except Exception as e:
        print(f"    ✗ Backtest failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("DIAGNOSTICS COMPLETE")
    print("="*60 + "\n")

if __name__ == "__main__":
    diagnose_backtest()
