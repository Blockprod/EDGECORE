#!/usr/bin/env python
"""EDGECORE Backtest v26 ÔÇö Institutional balanced parameters.

Middle ground between:
  - v22 (overfitted to 2020-2025: alloc=90%, heat=400%, entry=1.5)
  - v23 (too conservative: alloc=20%, heat=95%, entry=2.0)

Institutional stat-arb sizing:
  - allocation: 50% per pair (meaningful capital deployment)
  - heat: 200% (2x leverage ÔÇö standard for market-neutral stat-arb)
  - entry_z: 1.5 (enough opportunities)
  - exit_z: 0.3 (let winners revert closer to mean)
  - fdr_q: 0.15 (moderate filtering)
  - min_correlation: 0.60
  - max_half_life: 90 days
  - rediscovery: every 3 bars

Data source: IBKR Gateway (port 4002) ÔÇö real historical data.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

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

# ÔöÇÔöÇ v26 Institutional Balanced Parameters ÔöÇÔöÇ
ENTRY_Z = 1.5       # More entry signals (v22 proven)
EXIT_Z = 0.3        # Let winners run to mean (v22 proven)
ALLOC_PCT = 50.0    # 50% per pair ÔÇö meaningful but not all-in
HEAT = 2.0          # 200% ÔÇö standard institutional stat-arb leverage
STOP_PCT = 0.10     # 10% stop loss
MIN_CORR = 0.60     # Moderate pair quality filter
MAX_HALF_LIFE = 90  # Accept mid-speed reversion
FDR_Q = 0.15        # Moderate FDR filtering
REDISCOVERY = 3     # Frequent rediscovery (v22 proven)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="EDGECORE Backtest v26 (Institutional)")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2026-01-01")
    parser.add_argument("--capital", type=float, default=100_000)
    args = parser.parse_args()

    runner = BacktestRunner()
    runner.config.initial_capital = args.capital

    from config.settings import get_settings
    settings = get_settings()

    # Audited infrastructure
    settings.strategy.lookback_window = 252
    settings.strategy.additional_lookback_windows = [126]
    settings.strategy.use_kalman = True
    settings.strategy.bonferroni_correction = True
    settings.strategy.johansen_confirmation = True
    settings.strategy.newey_west_consensus = True
    settings.strategy.internal_max_drawdown_pct = 0.25

    # v26 balanced parameters
    settings.strategy.entry_z_score = ENTRY_Z
    settings.strategy.exit_z_score = EXIT_Z
    settings.strategy.z_score_stop = 3.5
    settings.strategy.fdr_q_level = FDR_Q
    settings.strategy.min_correlation = MIN_CORR
    settings.strategy.max_half_life = MAX_HALF_LIFE
    settings.strategy.max_position_loss_pct = STOP_PCT

    n_intra = sum(
        1 for i, s1 in enumerate(SYMBOLS)
        for s2 in SYMBOLS[i + 1:]
        if SECTOR_MAP.get(s1) == SECTOR_MAP.get(s2)
    )

    print("=" * 70)
    print("  EDGECORE BACKTEST v26 ÔÇö Institutional Balanced Parameters")
    print("=" * 70)
    print(f"  Symbols:      {len(SYMBOLS)} across 6 sectors")
    print(f"  Pairs:        {n_intra} intra-sector (BH-FDR q={FDR_Q})")
    print(f"  Period:       {args.start} -> {args.end} (8 years)")
    print(f"  Capital:      ${args.capital:,.0f}")
    print(f"  Alloc/pair:   {ALLOC_PCT}%")
    print(f"  Heat limit:   {HEAT*100:.0f}% (2x leverage)")
    print(f"  Stop:         {STOP_PCT*100:.0f}% per position | z_stop=3.5")
    print(f"  Z-score:      entry={ENTRY_Z}, exit={EXIT_Z}")
    print(f"  FDR q-level:  {FDR_Q}")
    print(f"  Correlation:  min={MIN_CORR}")
    print(f"  Half-life:    max={MAX_HALF_LIFE} days")
    print(f"  Hedge ratio:  Kalman filter")
    print(f"  Statistics:   Bonferroni + Johansen + Newey-West")
    print(f"  Lookback:     252 + [126]")
    print(f"  Rediscovery:  every {REDISCOVERY} bar(s)")
    print("=" * 70)
    print()

    t0 = time.time()
    print("[EDGECORE] Loading IBKR data + running backtest v26...")
    print("[EDGECORE] Data source: IBKR Gateway 127.0.0.1:4002")
    print()

    metrics = runner.run_unified(
        symbols=SYMBOLS,
        start_date=args.start,
        end_date=args.end,
        sector_map=SECTOR_MAP,
        pair_rediscovery_interval=REDISCOVERY,
        allocation_per_pair_pct=ALLOC_PCT,
        max_position_loss_pct=STOP_PCT,
        max_portfolio_heat=HEAT,
    )

    elapsed = time.time() - t0
    print(f"\n[EDGECORE] Backtest v26 completed in {elapsed:.1f}s")
    print()
    print(metrics.summary())
    print(f"\nUniverse: {len(SYMBOLS)} symbols | Intra-sector pairs: {n_intra}")

    # Save results
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    summary = metrics.summary()
    out_path = os.path.join(_ROOT, "results", "bt_results_v26_institutional.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Backtest v26 ÔÇö Institutional Balanced\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Period: {args.start} -> {args.end}\n")
        f.write(f"Capital: ${args.capital:,.0f}\n")
        f.write(f"Alloc: {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%\n")
        f.write(f"Z-score: entry={ENTRY_Z}, exit={EXIT_Z}\n")
        f.write(f"FDR q={FDR_Q} | Corr min: {MIN_CORR} | HL max: {MAX_HALF_LIFE}\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write(summary)
        f.write(f"\n\n--- Comparison ---\n")
        f.write(f"  v22 (2020-25): Return=+62.44% Sharpe=0.85 DD=-12.33%\n")
        f.write(f"  v25 (v22 8Y):  Return=-24.44% Sharpe=-0.50 DD=-26.52%\n")
        f.write(f"  v23 (conserv): Return=+2.58%  Sharpe=0.25 DD=-4.42%\n")
        f.write(f"  v24 (mod-agg): Return=+3.26%  Sharpe=0.17 DD=-9.58%\n")
    print(f"\n[Saved] {out_path}")


if __name__ == "__main__":
    main()
