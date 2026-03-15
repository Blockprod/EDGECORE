#!/usr/bin/env python
"""EDGECORE Backtest v24 ÔÇö Moderately Aggressive post-audit backtest.

Same audited infrastructure as v23 but with tuned parameters:
  - entry_z_score: 1.8 (vs 2.0 ÔÇö catches more opportunities)
  - exit_z_score: 0.5 (unchanged ÔÇö no whipsaw)
  - allocation: 35% per pair (vs 20% ÔÇö more capital deployed)
  - max_portfolio_heat: 1.50 (vs 0.95 ÔÇö allows modest leverage)
  - stop: 8% per position (vs 10% ÔÇö tighter risk control)
  - min_correlation: 0.65 (vs 0.70 ÔÇö wider net)
  - Bonferroni + Johansen + Newey-West: enabled (unchanged)
  - Spread correlation guard: rho_max=0.40 (R-6, unchanged)

Data source: IBKR Gateway (port 4002) ÔÇö real historical data.
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

# ÔöÇÔöÇ v24 Parameter Changes vs v23 ÔöÇÔöÇ
ENTRY_Z = 1.8       # v23: 2.0  ÔåÆ More entry opportunities
EXIT_Z = 0.5        # unchanged
ALLOC_PCT = 35.0    # v23: 20%  ÔåÆ More capital per trade
HEAT = 1.50         # v23: 0.95 ÔåÆ Allows modest leverage (150%)
STOP_PCT = 0.08     # v23: 10%  ÔåÆ Tighter stop (8%)
MIN_CORR = 0.65     # v23: 0.70 ÔåÆ Wider pair net
MAX_HALF_LIFE = 60  # unchanged


def main():
    import argparse

    parser = argparse.ArgumentParser(description="EDGECORE Backtest v24 (Moderate Aggressive)")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2026-01-01")
    parser.add_argument("--capital", type=float, default=100_000)
    args = parser.parse_args()

    runner = BacktestRunner()
    runner.config.initial_capital = args.capital

    from config.settings import get_settings
    settings = get_settings()

    # Audited infrastructure (unchanged)
    settings.strategy.lookback_window = 252
    settings.strategy.additional_lookback_windows = [126]
    settings.strategy.use_kalman = True
    settings.strategy.bonferroni_correction = True
    settings.strategy.johansen_confirmation = True
    settings.strategy.newey_west_consensus = True
    settings.strategy.internal_max_drawdown_pct = 0.20  # Tier 3

    # v24 tuned parameters
    settings.strategy.entry_z_score = ENTRY_Z
    settings.strategy.exit_z_score = EXIT_Z
    settings.strategy.z_score_stop = 3.5
    settings.strategy.min_correlation = MIN_CORR
    settings.strategy.max_half_life = MAX_HALF_LIFE
    settings.strategy.max_position_loss_pct = STOP_PCT

    n_intra = sum(
        1 for i, s1 in enumerate(SYMBOLS)
        for s2 in SYMBOLS[i + 1:]
        if SECTOR_MAP.get(s1) == SECTOR_MAP.get(s2)
    )

    print("=" * 70)
    print("  EDGECORE BACKTEST v24 ÔÇö Moderate Aggressive Parameters")
    print("=" * 70)
    print(f"  Symbols:      {len(SYMBOLS)} across 6 sectors")
    print(f"  Pairs:        {n_intra} intra-sector (Bonferroni + BH-FDR)")
    print(f"  Period:       {args.start} -> {args.end}")
    print(f"  Capital:      ${args.capital:,.0f}")
    print(f"  Alloc/pair:   {ALLOC_PCT}%  (v23: 20%)")
    print(f"  Heat limit:   {HEAT*100:.0f}% max capital  (v23: 95%)")
    print(f"  Stop:         {STOP_PCT*100:.0f}% per position  (v23: 10%)")
    print(f"  Z-score:      entry={ENTRY_Z}, exit={EXIT_Z}  (v23: 2.0/0.5)")
    print(f"  Correlation:  min={MIN_CORR}  (v23: 0.70)")
    print(f"  Half-life:    max={MAX_HALF_LIFE} days")
    print(f"  Hedge ratio:  Kalman filter")
    print(f"  Statistics:   Bonferroni + Johansen + Newey-West")
    print(f"  Lookback:     252 + [126]")
    print(f"  Rediscovery:  every 5 bar(s)")
    print("=" * 70)
    print()

    t0 = time.time()
    print("[EDGECORE] Loading IBKR data + running backtest v24...")
    print("[EDGECORE] Data source: IBKR Gateway 127.0.0.1:4002")
    print()

    metrics = runner.run_unified(
        symbols=SYMBOLS,
        start_date=args.start,
        end_date=args.end,
        sector_map=SECTOR_MAP,
        pair_rediscovery_interval=5,
        allocation_per_pair_pct=ALLOC_PCT,
        max_position_loss_pct=STOP_PCT,
        max_portfolio_heat=HEAT,
    )

    elapsed = time.time() - t0
    print(f"\n[EDGECORE] Backtest v24 completed in {elapsed:.1f}s")
    print()
    print(metrics.summary())
    print(f"\nUniverse: {len(SYMBOLS)} symbols | Intra-sector pairs: {n_intra}")

    # Save results
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    summary = metrics.summary()
    out_path = os.path.join(_ROOT, "results", "bt_results_v24_moderate_aggressive.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Backtest v24 ÔÇö Moderate Aggressive\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Period: {args.start} -> {args.end}\n")
        f.write(f"Capital: ${args.capital:,.0f}\n")
        f.write(f"Alloc: {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%\n")
        f.write(f"Z-score: entry={ENTRY_Z}, exit={EXIT_Z}\n")
        f.write(f"Stop: {STOP_PCT*100:.0f}% | Corr min: {MIN_CORR}\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write(summary)
        f.write(f"\n\n--- v24 vs v23 Parameter Changes ---\n")
        f.write(f"  entry_z: 2.0 -> {ENTRY_Z}\n")
        f.write(f"  alloc:   20% -> {ALLOC_PCT}%\n")
        f.write(f"  heat:    95% -> {HEAT*100:.0f}%\n")
        f.write(f"  stop:    10% -> {STOP_PCT*100:.0f}%\n")
        f.write(f"  corr:    0.70 -> {MIN_CORR}\n")
    print(f"\n[Saved] {out_path}")


if __name__ == "__main__":
    main()
