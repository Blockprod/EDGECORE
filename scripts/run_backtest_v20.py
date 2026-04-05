#!/usr/bin/env python
"""EDGECORE Backtest v20 — Post-audit production run.

Uses the proven curated 31-symbol universe directly (no SEC/IBKR scan).
Same parameters as v19c (last successful run).

All Phase 0-3 corrections active:
  - Unified signal pipeline (no backtest/live divergence)
  - Per-sector BH-FDR correction
  - Z-score stop at 3.5σ
  - Atomic audit trail, RiskFacade, SystemMetrics
  - Trailing stop, time stop, partial profit
  - Spread correlation guard, PCA factor monitor
  - Portfolio heat limit, drawdown circuit breaker
"""

import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

# Curated universe: 31 symbols across 6 sectors (same as v19c)
SYMBOLS = [
    # Technology (7)
    "AAPL",
    "MSFT",
    "GOOGL",
    "META",
    "NVDA",
    "AMD",
    "AVGO",
    # Financials (7)
    "JPM",
    "GS",
    "BAC",
    "MS",
    "WFC",
    "C",
    "SCHW",
    # Energy (4)
    "XOM",
    "CVX",
    "COP",
    "EOG",
    # Consumer Staples (5)
    "KO",
    "PEP",
    "PG",
    "CL",
    "WMT",
    # Industrials (4)
    "CAT",
    "HON",
    "DE",
    "GE",
    "RTX",
    # Utilities (3)
    "NEE",
    "DUK",
    "SO",
]

SECTOR_MAP = {
    # Tech
    "AAPL": "technology",
    "MSFT": "technology",
    "GOOGL": "technology",
    "META": "technology",
    "NVDA": "technology",
    "AMD": "technology",
    "AVGO": "technology",
    # Financials
    "JPM": "financials",
    "GS": "financials",
    "BAC": "financials",
    "MS": "financials",
    "WFC": "financials",
    "C": "financials",
    "SCHW": "financials",
    # Energy
    "XOM": "energy",
    "CVX": "energy",
    "COP": "energy",
    "EOG": "energy",
    # Consumer Staples
    "KO": "consumer_staples",
    "PEP": "consumer_staples",
    "PG": "consumer_staples",
    "CL": "consumer_staples",
    "WMT": "consumer_staples",
    # Industrials
    "CAT": "industrials",
    "HON": "industrials",
    "DE": "industrials",
    "GE": "industrials",
    "RTX": "industrials",
    # Utilities
    "NEE": "utilities",
    "DUK": "utilities",
    "SO": "utilities",
}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="EDGECORE Backtest v20")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2026-01-01")
    parser.add_argument("--capital", type=float, default=100_000)
    parser.add_argument("--alloc", type=float, default=90.0)
    parser.add_argument("--stop", type=float, default=0.03)
    parser.add_argument("--heat", type=float, default=4.0)
    parser.add_argument("--rediscovery", type=int, default=3)
    args = parser.parse_args()

    runner = BacktestRunner()
    runner.config.initial_capital = args.capital

    # Strategy params (proven from v17f → v19c)
    from config.settings import get_settings

    settings = get_settings()
    settings.strategy.lookback_window = 252
    settings.strategy.additional_lookback_windows = [126]
    settings.strategy.fdr_q_level = 0.10
    settings.strategy.min_correlation = 0.65
    settings.strategy.entry_z_score = 2.0
    settings.strategy.exit_z_score = 0.5
    settings.strategy.max_half_life = 90
    settings.strategy.z_score_stop = 3.5

    n_intra = sum(
        1 for i, s1 in enumerate(SYMBOLS) for s2 in SYMBOLS[i + 1 :] if SECTOR_MAP.get(s1) == SECTOR_MAP.get(s2)
    )

    print("=" * 60)
    print("  EDGECORE BACKTEST v20 — Post-Audit Production Run")
    print("=" * 60)
    print(f"  Symbols:  {len(SYMBOLS)} across 6 sectors")
    print(f"  Pairs:    {n_intra} intra-sector (BH-FDR per-sector q=0.10)")
    print(f"  Period:   {args.start} -> {args.end}")
    print(f"  Capital:  {args.capital:,.0f} EUR")
    print(f"  Alloc:    {args.alloc}% per pair (2x leverage)")
    print(f"  Stop:     {args.stop * 100}% | Heat: {args.heat * 100}%")
    print(f"  Z-score:  entry=2.0, exit=0.5, z_stop=3.5")
    print(f"  Lookback: 252 + [126]")
    print(f"  Rediscovery: every {args.rediscovery} bar(s)")
    print("=" * 60)
    print()

    print("[EDGECORE] Backtest en cours...")
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

    print("[EDGECORE] Backtest terminé !")
    print()
    print(metrics.summary())
    print(f"Number of symbols in universe: {len(SYMBOLS)}")

    # Save results
    summary = metrics.summary()
    with open(os.path.join(_ROOT, "results", "bt_results_v20_summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary)
    print("\n[Saved] results/bt_results_v20_summary.txt")


if __name__ == "__main__":
    main()
