<<<<<<< HEAD
﻿"""Test backtest with highly correlated equity sector pairs."""

import sys

from backtests.runner import BacktestRunner
from config.settings import get_settings
=======
"""Test backtest with highly correlated equity sector pairs."""

from backtests.runner import BacktestRunner
from config.settings import get_settings
import sys
>>>>>>> origin/main

settings = get_settings()
runner = BacktestRunner()

<<<<<<< HEAD
print("\n" + "=" * 70)
print("BACKTEST: SECTOR PAIRS (Should Find Real Cointegration!)")
print("=" * 70)
=======
print("\n" + "="*70)
print("BACKTEST: SECTOR PAIRS (Should Find Real Cointegration!)")
print("="*70)
>>>>>>> origin/main
print("\nRationale: Stocks in the same sector share common drivers,")
print("creating cointegration. e.g., AAPL & MSFT (Big Tech),")
print("JPM & BAC (Banks), XOM & CVX (Energy)")
print()

try:
    # Sector pairs - stocks with shared drivers creating cointegration
    sector_pairs = [
<<<<<<< HEAD
        "AAPL",  # Apple ÔÇô Big Tech
        "MSFT",  # Microsoft ÔÇô Big Tech
        "JPM",  # JPMorgan ÔÇô Banking
        "BAC",  # Bank of America ÔÇô Banking
    ]

    metrics = runner.run(sector_pairs, start_date="2023-01-01", end_date="2024-12-31")

=======
        'AAPL',    # Apple – Big Tech
        'MSFT',    # Microsoft – Big Tech
        'JPM',     # JPMorgan – Banking
        'BAC',     # Bank of America – Banking
    ]
    
    metrics = runner.run(
        sector_pairs,
        start_date='2023-01-01',
        end_date='2024-12-31'
    )
    
>>>>>>> origin/main
    print(metrics.summary())
    print("\nDetailed Results:")
    print(f"  Total Trades: {metrics.total_trades}")
    print(f"  Total Return: {metrics.total_return:+.2%}")
    print(f"  Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
    print(f"  Max Drawdown: {metrics.max_drawdown:.2%}")
    print(f"  Win Rate: {metrics.win_rate:.1%}")
<<<<<<< HEAD

    # Interpretation
    print("\n" + "=" * 70)
    if metrics.total_trades > 50:
        print("Ô£à SUCCESS! Sector pairs ARE cointegrated!")
        print("   Ôåô Many trades generated Ôåô Good for mean-reversion pair trading")
    elif metrics.total_trades > 10:
        print("­ƒƒí PARTIAL: Some cointegration found")
        print("   Ôåô Limited pair trading opportunities")
    elif metrics.total_trades > 0:
        print("ÔÜá´©Å  Synthetic fallback only (no real pairs found)")
        print("   Ôåô Equity data may not be available in your data source")
    else:
        print("ÔØî No trades (check data availability)")

    print("=" * 70)

except Exception as e:
    print(f"ERROR: {e}")
    import traceback

=======
    
    # Interpretation
    print("\n" + "="*70)
    if metrics.total_trades > 50:
        print("✅ SUCCESS! Sector pairs ARE cointegrated!")
        print("   ↓ Many trades generated ↓ Good for mean-reversion pair trading")
    elif metrics.total_trades > 10:
        print("🟡 PARTIAL: Some cointegration found")
        print("   ↓ Limited pair trading opportunities")
    elif metrics.total_trades > 0:
        print("⚠️  Synthetic fallback only (no real pairs found)")
        print("   ↓ Equity data may not be available in your data source")
    else:
        print("❌ No trades (check data availability)")

    print("="*70)
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
>>>>>>> origin/main
    traceback.print_exc()
    sys.exit(1)
