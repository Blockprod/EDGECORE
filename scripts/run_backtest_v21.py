#!/usr/bin/env python
"""EDGECORE Backtest v21 -- Optimized for capital utilization.

Key changes vs v20:
  - entry_z_score: 2.0 -> 1.5 (2.7x more entry signals)
  - fdr_q_level: 0.10 -> 0.20 (less aggressive FDR filtering)
  - rediscovery_interval: 3 -> 1 (fresh pairs every bar)
  - allocation_per_pair: 30% (allow ~3 concurrent positions)
  - max_portfolio_heat: 0.95 (use nearly all capital)
  - min_correlation: 0.65 -> 0.50 (wider pair pool)
  - max_half_life: 90 -> 120 (accept slower mean-reversion)
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

# Curated universe: 31 symbols across 6 sectors
SYMBOLS = [
    # Technology (7)
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO",
    # Financials (7)
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    # Energy (4)
    "XOM", "CVX", "COP", "EOG",
    # Consumer Staples (5)
    "KO", "PEP", "PG", "CL", "WMT",
    # Industrials (5)
    "CAT", "HON", "DE", "GE", "RTX",
    # Utilities (3)
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

    parser = argparse.ArgumentParser(description="EDGECORE Backtest v21")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2026-01-01")
    parser.add_argument("--capital", type=float, default=100_000)
    parser.add_argument("--alloc", type=float, default=30.0,
                        help="Allocation per pair %% (lower = more concurrent)")
    parser.add_argument("--stop", type=float, default=0.10)
    parser.add_argument("--heat", type=float, default=0.95,
                        help="Max portfolio heat (0.95 = 95%% capital deployed)")
    parser.add_argument("--rediscovery", type=int, default=1,
                        help="Bars between pair re-discovery (1 = every bar)")
    args = parser.parse_args()

    runner = BacktestRunner()
    runner.config.initial_capital = args.capital

    # ---- Optimized strategy params ----
    from config.settings import get_settings
    settings = get_settings()
    settings.strategy.lookback_window = 252
    settings.strategy.additional_lookback_windows = [126]

    # KEY CHANGES vs v20:
    settings.strategy.entry_z_score = 1.5       # was 2.0 -> 2.7x more entries
    settings.strategy.exit_z_score = 0.5         # keep
    settings.strategy.z_score_stop = 3.5         # keep protective stop
    settings.strategy.fdr_q_level = 0.20         # was 0.10 -> less FDR killing
    settings.strategy.min_correlation = 0.50     # was 0.65 -> wider pair pool
    settings.strategy.max_half_life = 120        # was 90 -> accept slower reversion
    settings.strategy.internal_max_drawdown_pct = 0.25  # was 0.20 -> less DD breaker

    n_intra = sum(
        1 for i, s1 in enumerate(SYMBOLS)
        for s2 in SYMBOLS[i + 1:]
        if SECTOR_MAP.get(s1) == SECTOR_MAP.get(s2)
    )

    print("=" * 60)
    print("  EDGECORE BACKTEST v21 -- Optimized Capital Utilization")
    print("=" * 60)
    print(f"  Symbols:  {len(SYMBOLS)} across 6 sectors")
    print(f"  Pairs:    {n_intra} intra-sector (BH-FDR per-sector q=0.20)")
    print(f"  Period:   {args.start} -> {args.end}")
    print(f"  Capital:  {args.capital:,.0f} EUR")
    print(f"  Alloc:    {args.alloc}% per pair (max ~3 concurrent)")
    print(f"  Heat:     {args.heat*100:.0f}% max portfolio utilization")
    print(f"  Stop:     {args.stop*100:.0f}% per position | z_stop=3.5")
    print(f"  Z-score:  entry=1.5, exit=0.5")
    print(f"  FDR:      q=0.20 (relaxed)")
    print(f"  Lookback: 252 + [126]")
    print(f"  Rediscovery: every {args.rediscovery} bar(s)")
    print("=" * 60)
    print()

    print("[EDGECORE] Backtest v21 en cours...")
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

    print("[EDGECORE] Backtest v21 termine !")
    print()
    print(metrics.summary())
    print(f"Number of symbols in universe: {len(SYMBOLS)}")

    # Save results
    summary = metrics.summary()
    with open(os.path.join(_ROOT, "results", "bt_results_v21_summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary)
    print("\n[Saved] results/bt_results_v21_summary.txt")


if __name__ == "__main__":
    main()
