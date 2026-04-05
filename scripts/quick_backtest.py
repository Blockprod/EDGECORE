#!/usr/bin/env python
"""Quick backtest test"""

import sys
import traceback

print("\nquick test...")

try:
    from backtests.runner import BacktestRunner
    from config.settings import get_settings
    
    settings = get_settings()
    runner = BacktestRunner()
    
    print("Running backtest...")
    metrics = runner.run(
        settings.trading_universe.symbols[:5],  # Use first 5 symbols only
        start_date='2023-06-01',
        end_date='2024-01-01'
    )
    
    print("\n" + metrics.summary())
    
    # Check if metrics are at least non-zero
    if metrics.total_trades > 0:
        print("Ô£à Backtest produced trades!")
    else:
        print("ÔÜá´©Å  Backtest had zero trades")
    
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)
