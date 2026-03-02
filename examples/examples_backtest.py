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
    
    print("\n" + "="*70)
    print("EDGECORE PAIR TRADING BACKTEST")
    print("="*70)
    
    # Configuration
    symbols = ["AAPL", "MSFT"]
    start_date = "2023-01-01"
    end_date = "2024-01-01"
    
    print(f"\n[*] Backtest Configuration:")
    print(f"    Symbols:    {symbols}")
    print(f"    Period:     {start_date} to {end_date}")
    print(f"    Strategy:   Pair Trading (Mean Reversion)")
    
    try:
        runner = BacktestRunner()
        
        print(f"\n[*] Running backtest...")
        metrics = runner.run(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date
        )
        
        # Display results
        print(metrics.summary())
        
        print("[✓] Backtest completed successfully")
        
        # Next steps
        print(f"\n[*] Next steps:")
        print(f"    1. Review metrics above")
        print(f"    2. Check logs in logs/ directory")
        print(f"    3. If Sharpe > 1.0 and max drawdown < 20%, consider paper trading")
        print(f"    4. Test live on small position size first")
        
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
