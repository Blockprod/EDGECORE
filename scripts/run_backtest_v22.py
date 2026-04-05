#!/usr/bin/env python
"""EDGECORE Backtest v22 -- High conviction + capital utilization.

Key insight from v20 vs v21: 
  - v20 (z=2.0, alloc=90%): 12% return, 68 trades, but avg PnL/trade is decent
  - v21 (z=1.5, alloc=30%): 2.7% return, 142 trades, LOW avg PnL (position too small)
  
v22 strategy: Keep high allocation (90%) + lower z-entry (1.5) + relaxed FDR:
  - entry_z_score: 1.5 (more entries)
  - allocation: 90% (high conviction sizing)
  - fdr_q_level: 0.20 (less aggressive filtering)
  - rediscovery: 3 (balanced -- not too aggressive)
  - exit_z: 0.3 (let winners run closer to mean)
  - max_portfolio_heat: 4.0 (400% = 4 concurrent positions)
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO",
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    "XOM", "CVX", "COP", "EOG",
    "KO", "PEP", "PG", "CL", "WMT",
    "CAT", "HON", "DE", "GE", "RTX",
    "NEE", "DUK", "SO",
]

SECTOR_MAP = {
    "AAPL": "technology", "MSFT": "technology", "GOOGL": "technology",
    "META": "technology", "NVDA": "technology", "AMD": "technology",
    "AVGO": "technology",
    "JPM": "financials", "GS": "financials", "BAC": "financials",
    "MS": "financials", "WFC": "financials", "C": "financials",
    "SCHW": "financials",
    "XOM": "energy", "CVX": "energy", "COP": "energy", "EOG": "energy",
    "KO": "consumer_staples", "PEP": "consumer_staples",
    "PG": "consumer_staples", "CL": "consumer_staples",
    "WMT": "consumer_staples",
    "CAT": "industrials", "HON": "industrials", "DE": "industrials",
    "GE": "industrials", "RTX": "industrials",
    "NEE": "utilities", "DUK": "utilities", "SO": "utilities",
}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="EDGECORE Backtest v22")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2026-01-01")
    parser.add_argument("--capital", type=float, default=100_000)
    parser.add_argument("--alloc", type=float, default=90.0)
    parser.add_argument("--stop", type=float, default=0.10)
    parser.add_argument("--heat", type=float, default=4.0)
    parser.add_argument("--rediscovery", type=int, default=3)
    args = parser.parse_args()

    runner = BacktestRunner()
    runner.config.initial_capital = args.capital

    from config.settings import get_settings
    settings = get_settings()
    settings.strategy.lookback_window = 252
    settings.strategy.additional_lookback_windows = [126]

    # OPTIMIZED PARAMS:
    settings.strategy.entry_z_score = 1.5       # was 2.0 -> more entries
    settings.strategy.exit_z_score = 0.3         # was 0.5 -> let winners run
    settings.strategy.z_score_stop = 3.5         # keep protective stop
    settings.strategy.fdr_q_level = 0.20         # was 0.10 -> more pairs survive FDR
    settings.strategy.min_correlation = 0.50     # was 0.65 -> wider pair pool
    settings.strategy.max_half_life = 120        # was 90 -> accept slower reversion
    settings.strategy.internal_max_drawdown_pct = 0.25

    n_intra = sum(
        1 for i, s1 in enumerate(SYMBOLS)
        for s2 in SYMBOLS[i + 1:]
        if SECTOR_MAP.get(s1) == SECTOR_MAP.get(s2)
    )

    print("=" * 60)
    print("  EDGECORE BACKTEST v22 -- High Conviction + More Entries")
    print("=" * 60)
    print(f"  Symbols:  {len(SYMBOLS)} across 6 sectors")
    print(f"  Pairs:    {n_intra} intra-sector (BH-FDR q=0.20)")
    print(f"  Period:   {args.start} -> {args.end}")
    print(f"  Capital:  {args.capital:,.0f} EUR")
    print(f"  Alloc:    {args.alloc}% per pair (high conviction)")
    print(f"  Heat:     {args.heat*100:.0f}% max portfolio")
    print(f"  Stop:     {args.stop*100:.0f}% per position | z_stop=3.5")
    print(f"  Z-score:  entry=1.5, exit=0.3 (let winners run)")
    print(f"  FDR:      q=0.20 (relaxed)")
    print(f"  Lookback: 252 + [126]")
    print(f"  Rediscovery: every {args.rediscovery} bar(s)")
    print("=" * 60)
    print()

    print("[EDGECORE] Backtest v22 en cours...")
    metrics = runner.run_unified(
        symbols=SYMBOLS,
        start_date=args.start,
        end_date=args.end,
        sector_map=SECTOR_MAP,
        pair_rediscovery_interval=args.rediscovery,
        allocation_per_pair_pct=args.alloc,
        max_position_loss_pct=args.stop,
        max_portfolio_heat=args.heat,
    )

    print("[EDGECORE] Backtest v22 termine !")
    print()
    print(metrics.summary())
    print(f"Number of symbols in universe: {len(SYMBOLS)}")

    summary = metrics.summary()
    with open(os.path.join(_ROOT, "results", "bt_results_v22_summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary)
    print("\n[Saved] results/bt_results_v22_summary.txt")


if __name__ == "__main__":
    main()
