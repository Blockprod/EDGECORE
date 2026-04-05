#!/usr/bin/env python
"""EDGECORE Backtest v23 — Post-audit production backtest.

Uses the production-audited parameters from Phase 0-6:
  - entry_z_score: 2.0 (conservative, prod default)
  - exit_z_score: 0.5 (R-8 fix, no whipsaw)
  - allocation: 20% per pair (F-7: max_allocation_pct)
  - max_portfolio_heat: 0.95 (95% capital deployed max)
  - stop: 10% per position
  - min_correlation: 0.70 (config default)
  - Bonferroni + Johansen + Newey-West enabled
  - Spread correlation guard: rho_max=0.40 (R-6)

Data source: IBKR Gateway (port 4002) — real historical data.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

# Universe: 31 US large-cap equities across 6 sectors
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

    parser = argparse.ArgumentParser(description="EDGECORE Backtest v23 (Post-Audit)")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2026-01-01")
    parser.add_argument("--capital", type=float, default=100_000)
    parser.add_argument("--alloc", type=float, default=20.0)
    parser.add_argument("--stop", type=float, default=0.10)
    parser.add_argument("--heat", type=float, default=0.95)
    parser.add_argument("--rediscovery", type=int, default=5)
    args = parser.parse_args()

    runner = BacktestRunner()
    runner.config.initial_capital = args.capital

    from config.settings import get_settings
    settings = get_settings()

    # Production-audited parameters
    settings.strategy.lookback_window = 252
    settings.strategy.additional_lookback_windows = [126]
    settings.strategy.entry_z_score = 2.0       # Prod default (conservative)
    settings.strategy.exit_z_score = 0.5         # R-8 fix
    settings.strategy.z_score_stop = 3.5         # Protective stop
    settings.strategy.min_correlation = 0.70     # Config default
    settings.strategy.max_half_life = 60         # Config default
    settings.strategy.use_kalman = True
    settings.strategy.bonferroni_correction = True
    settings.strategy.johansen_confirmation = True
    settings.strategy.newey_west_consensus = True
    settings.strategy.max_position_loss_pct = 0.10
    settings.strategy.internal_max_drawdown_pct = 0.20  # Tier 3

    n_intra = sum(
        1 for i, s1 in enumerate(SYMBOLS)
        for s2 in SYMBOLS[i + 1:]
        if SECTOR_MAP.get(s1) == SECTOR_MAP.get(s2)
    )

    print("=" * 70)
    print("  EDGECORE BACKTEST v23 — Post-Audit Production Parameters")
    print("=" * 70)
    print(f"  Symbols:      {len(SYMBOLS)} across 6 sectors")
    print(f"  Pairs:        {n_intra} intra-sector (Bonferroni + BH-FDR)")
    print(f"  Period:       {args.start} -> {args.end} ({8 if '2018' in args.start else '?'}Y)")
    print(f"  Capital:      ${args.capital:,.0f}")
    print(f"  Alloc/pair:   {args.alloc}%")
    print(f"  Heat limit:   {args.heat*100:.0f}% max capital deployed")
    print(f"  Stop:         {args.stop*100:.0f}% per position | z_stop=3.5")
    print("  Z-score:      entry=2.0, exit=0.5 (prod config)")
    print("  Correlation:  min=0.70 | spread rho_max=0.40 (R-6)")
    print("  Half-life:    max=60 days")
    print("  Hedge ratio:  Kalman filter")
    print("  Statistics:   Bonferroni + Johansen + Newey-West")
    print("  Lookback:     252 + [126]")
    print(f"  Rediscovery:  every {args.rediscovery} bar(s)")
    print("=" * 70)
    print()

    t0 = time.time()
    print("[EDGECORE] Loading IBKR data + running backtest...")
    print("[EDGECORE] Data source: IBKR Gateway 127.0.0.1:4002")
    print()

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

    elapsed = time.time() - t0
    print(f"\n[EDGECORE] Backtest v23 completed in {elapsed:.1f}s")
    print()
    print(metrics.summary())
    print(f"\nUniverse: {len(SYMBOLS)} symbols | Intra-sector pairs: {n_intra}")

    # Save results
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    summary = metrics.summary()
    out_path = os.path.join(_ROOT, "results", "bt_results_v23_postaudit.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Backtest v23 — Post-Audit Production\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Period: {args.start} -> {args.end}\n")
        f.write(f"Capital: ${args.capital:,.0f}\n")
        f.write(f"Alloc: {args.alloc}% | Heat: {args.heat*100:.0f}%\n")
        f.write("Z-score: entry=2.0, exit=0.5\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write(summary)
    print(f"\n[Saved] {out_path}")


if __name__ == "__main__":
    main()
