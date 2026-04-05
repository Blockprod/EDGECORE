<<<<<<< HEAD
﻿from backtests.runner import BacktestRunner
=======
from backtests.runner import BacktestRunner
>>>>>>> origin/main
from config.settings import get_settings
import sys
import traceback

settings = get_settings()
runner = BacktestRunner()

print("\n" + "="*50)
print("Testing Backtest Runner")
print("="*50)

try:
    print("[1] Loading data...")
    sys.stdout.flush()
    
    print("[2] Running backtest...")
    sys.stdout.flush()
    
    metrics = runner.run(['AAPL','MSFT'], start_date='2023-06-01', end_date='2024-01-01')
    
    print("[3] Got metrics")
    sys.stdout.flush()
    
    print(metrics.summary())
    print(f"Total Trades: {metrics.total_trades}")
    print(f"Total Return: {metrics.total_return}")
    
    print("[4] Done")
    sys.stdout.flush()
    
except Exception as e:
<<<<<<< HEAD
    print(f"\nÔØî ERROR: {e}", flush=True)
=======
    print(f"\n❌ ERROR: {e}", flush=True)
>>>>>>> origin/main
    traceback.print_exc()
    sys.exit(1)

