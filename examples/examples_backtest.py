"""
Example: Run a basic backtest on pair trading strategy
"""

import sys

from backtests.runner import BacktestRunner
from monitoring.logger import setup_logger

logger = setup_logger("example_backtest")


def main():
    """
    Example backtest workflow.

    Steps:
    1. Initialize BacktestRunner
    2. Run backtest on equity pairs
    3. Display performance metrics
    """

    print("\n" + "=" * 70)
    print("EDGECORE PAIR TRADING BACKTEST")
    print("=" * 70)

    # Configuration
    symbols = ["AAPL", "MSFT"]
    start_date = "2023-01-01"
    end_date = "2024-01-01"
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    print("\n[*] Backtest Configuration:")
    print(f"    Symbols:    {symbols}")
    print(f"    Period:     {start_date} to {end_date}")
    print("    Strategy:   Pair Trading (Mean Reversion)")
<<<<<<< HEAD

    try:
        runner = BacktestRunner()

        print("\n[*] Running backtest...")
        metrics = runner.run(symbols=symbols, start_date=start_date, end_date=end_date)

=======
    
    try:
        runner = BacktestRunner()
        
        print("\n[*] Running backtest...")
        metrics = runner.run(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date
        )
        
>>>>>>> origin/main
        # Display results
        print(metrics.summary())

        print("[Ô£ô] Backtest completed successfully")

        # Next steps
        print("\n[*] Next steps:")
        print("    1. Review metrics above")
        print("    2. Check logs in logs/ directory")
        print("    3. If Sharpe > 1.0 and max drawdown < 20%, consider paper trading")
        print("    4. Test live on small position size first")
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
    except ImportError as e:
        print(f"\n[!] Missing dependency: {e}")
        print("    Run: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"\n[!] Backtest failed: {e}")
        logger.error("backtest_error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
