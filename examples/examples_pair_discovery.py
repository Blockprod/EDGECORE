"""
Example: Discover and screen cointegrated pairs
"""

import sys

from data.loader import DataLoader
from monitoring.logger import setup_logger
from research.pair_discovery import screen_pairs

logger = setup_logger("pair_discovery")


def main():
    """
    Example workflow to discover pairs from exchange data.

    Steps:
    1. Load price data for candidate symbols
    2. Screen for cointegrated pairs
    3. Filter by half-life of mean reversion
    4. Output ranked list of trading candidates
    """
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    # Example US equity symbols to analyze
    symbols = [
        "AAPL",
        "MSFT",
        "JPM",
        "GOOGL",
        "BAC",
    ]

    print(f"\n[*] Loading OHLCV data for {len(symbols)} symbols...")
    loader = DataLoader()

    try:
        import pandas as pd

        # Load 2 years of daily data for each symbol
        prices = {}
        for symbol in symbols:
<<<<<<< HEAD
            print(f"    Ôåô Loading {symbol}...")
=======
            print(f"    ↓ Loading {symbol}...")
>>>>>>> origin/main
            try:
                df = loader.load_ibkr_data(
                    symbol=symbol,
                    timeframe="1d",
                    limit=730,  # ~2 years
                )
                prices[symbol] = df["close"]
            except Exception as e:
<<<<<<< HEAD
                print(f"    Ô£ö Failed to load {symbol}: {e}")
=======
                print(f"    ✔ Failed to load {symbol}: {e}")
>>>>>>> origin/main
                continue

        if not prices:
            print("[!] No data loaded. Check API credentials and internet connection.")
            sys.exit(1)

        prices_df = pd.DataFrame(prices)
        print(f"\n[*] Loaded {len(prices_df)} observations for {len(prices)} symbols")

        # Screen for cointegrated pairs
        print("\n[*] Screening for cointegrated pairs...")
<<<<<<< HEAD
        candidates = screen_pairs(prices_df, min_corr=0.7, max_half_life=60)

=======
        candidates = screen_pairs(
            prices_df,
            min_corr=0.7,
            max_half_life=60
        )
        
>>>>>>> origin/main
        if not candidates:
            print("[!] No cointegrated pairs found. Try longer lookback or more symbols.")
            sys.exit(0)

        # Display results
        print(f"\n[Ô£ô] Found {len(candidates)} cointegrated pair(s):\n")
        print(f"{'Pair':<20} {'Correlation':<15} {'Coint P-Value':<20} {'Half-Life':<15}")
        print("-" * 70)

        for _i, pair in enumerate(candidates, 1):
            sym1 = pair["sym1"]
            sym2 = pair["sym2"]
            corr = pair["correlation"]
            pval = pair["coint_pvalue"]
            hl = pair["half_life"]
            beta = pair["beta"]

            print(f"{sym1}_{sym2:<15} {corr:>10.3f}      {pval:>10.6f}       {hl:>10} days")
<<<<<<< HEAD
            print(f"  -''ÔôÇ Spread model: {sym1} = {beta:.4f} ├ù {sym2} + constant")

        print(f"\n[*] Top candidate: {candidates[0]['sym1']}_{candidates[0]['sym2']}")
        print("    Ready for pair trading strategy deployment.")

=======
            print(f"  -''Ⓚ Spread model: {sym1} = {beta:.4f} × {sym2} + constant")
        
        print(f"\n[*] Top candidate: {candidates[0]['sym1']}_{candidates[0]['sym2']}")
        print("    Ready for pair trading strategy deployment.")
        
>>>>>>> origin/main
    except ImportError as e:
        print(f"[!] Missing dependency: {e}")
        print("    Run: pip install -r requirements.txt")
        sys.exit(1)


if __name__ == "__main__":
    main()
