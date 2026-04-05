"""Test backtest with 2021 bull market data when equities were highly correlated"""

import sys

from backtests.runner import BacktestRunner
from config.settings import get_settings

settings = get_settings()
runner = BacktestRunner()

print("\n" + "=" * 60)
print("BACKTEST: 2021 Bull Market (Higher Correlation Period)")
print("=" * 60)

try:
    # 2021 Bull market period - when equities rose together
    metrics = runner.run(
        ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
        start_date="2021-01-01",  # Bull market start
        end_date="2021-12-31",  # Bull market through
    )

    print(metrics.summary())
    print("\nKey Metrics:")
    print(f"  Total Trades: {metrics.total_trades}")
    print(f"  Total Return: {metrics.total_return:+.2%}")
    print(f"  Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
    print(f"  Max Drawdown: {metrics.max_drawdown:.2%}")
    print(f"  Win Rate: {metrics.win_rate:.1%}")

    if metrics.total_trades > 10:
        print("\nÔ£à EXCELLENT! Found cointegrated pairs in 2021 bull market!")
    elif metrics.total_trades > 0:
        print("\n­ƒƒí Some trades found, but limited cointegration")
    else:
        print("\nÔØî Still no cointegrated pairs even in 2021")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
