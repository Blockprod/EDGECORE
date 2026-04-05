#!/usr/bin/env python
"""EDGECORE Backtest v31i -- v31h + More Trades (lower barriers).

ITERATION HISTORY:
  v30b: +5.25%, Sharpe 0.74,  25 trades, WR 60%,  PF 2.63, DD -2.6%
  v31h: +8.17%, Sharpe 1.31,  24 trades, WR 62.5%, PF 3.88, DD -1.79%
       (v30b universe + strict momentum + time_stop=1.5×HL)

v31i = v31h + lower barriers for more trade generation:
  - SAME v30b 37-symbol universe
  - SAME strict momentum
  - SAME time_stop=1.5×HL, cap=30d
  - LOWER entry_z=1.5 (was 1.8) — more frequent entries
  - HIGHER FDR_q=0.30 (was 0.25) — more pairs survive FDR
  - LOWER min_spread=0.20 (was 0.30) — accept tighter spreads

Expected: More trades (target: 50+) with modest PF/Sharpe reduction.
The momentum filter should still block bad entries even with lower barriers.

Period: 2023-03-04 to 2026-03-04 (3 years).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

# == v30b Universe (37 symbols) =============================================
SYMBOLS = [
    "SPY",
    # Technology
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO",
    # Financials
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    # Energy
    "XOM", "CVX", "COP", "EOG",
    # Consumer Staples
    "KO", "PEP", "PG", "CL", "WMT",
    # Industrials
    "CAT", "HON", "DE", "GE", "RTX",
    # Utilities
    "NEE", "DUK", "SO",
    # Healthcare
    "JNJ", "PFE", "UNH", "MRK", "ABBV",
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
    "JNJ": "healthcare", "PFE": "healthcare", "UNH": "healthcare",
    "MRK": "healthcare", "ABBV": "healthcare",
}

# == v31i Parameters: Lower barriers for more trades ========================
ENTRY_Z = 1.5           # LOWER — more entries (was 1.8)
EXIT_Z = 0.5            # v30b
ALLOC_PCT = 50.0        # v30b
HEAT = 3.0              # v30b
STOP_PCT = 0.07         # v30b
MIN_CORR = 0.60         # SLIGHTLY LOOSER (was 0.65)
MAX_HALF_LIFE = 60      # v30b
FDR_Q = 0.30            # MORE LENIENT (was 0.25)
REDISCOVERY = 2         # v30b
MIN_SPREAD = 0.20       # LOWER — accept tighter spreads (was 0.30)
Z_SCORE_STOP = 3.0      # v30b

# Adaptive regime (v30b)
TREND_FAVORABLE_SIZING = 1.0
NEUTRAL_SIZING = 0.70
REGIME_NEUTRAL_BAND = 0.02
REGIME_VOL_THRESHOLD = 0.18

# Legacy (OFF)
REGIME_DIRECTIONAL = False
TREND_LONG_SIZING = 0.75
SHORT_MULT = 0.50
DISABLE_SHORTS_BULL = False

# Time stop (properly injected)
TIME_STOP_MULT = 1.5
MAX_HOLD_DAYS = 30

# Blacklist
BL_MAX_LOSSES = 5
BL_COOLDOWN = 10

# Weekly gate — LOWER to allow more entries
WEEKLY_Z_GATE = 0.2     # was 0.3

# Momentum: STRICT
MOM_MIN_STRENGTH = 1.0


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="EDGECORE Backtest v31i -- v31h + More Trades"
    )
    parser.add_argument("--start", default="2023-03-04")
    parser.add_argument("--end", default="2026-03-04")
    parser.add_argument("--capital", type=float, default=100_000)
    args = parser.parse_args()

    from config.settings import get_settings
    settings = get_settings()

    # Strategy
    settings.strategy.lookback_window = 120
    settings.strategy.additional_lookback_windows = [63]
    settings.strategy.entry_z_score = ENTRY_Z
    settings.strategy.exit_z_score = EXIT_Z
    settings.strategy.entry_z_min_spread = MIN_SPREAD
    settings.strategy.z_score_stop = Z_SCORE_STOP
    settings.strategy.min_correlation = MIN_CORR
    settings.strategy.max_half_life = MAX_HALF_LIFE
    settings.strategy.max_position_loss_pct = STOP_PCT
    settings.strategy.internal_max_drawdown_pct = 0.25
    settings.strategy.use_kalman = True
    settings.strategy.bonferroni_correction = True
    settings.strategy.johansen_confirmation = True
    settings.strategy.newey_west_consensus = True
    settings.strategy.weekly_zscore_entry_gate = WEEKLY_Z_GATE

    # Legacy (OFF)
    settings.strategy.regime_directional_filter = REGIME_DIRECTIONAL
    settings.strategy.trend_long_sizing = TREND_LONG_SIZING
    settings.strategy.disable_shorts_in_bull_trend = DISABLE_SHORTS_BULL
    settings.strategy.short_sizing_multiplier = SHORT_MULT

    # Adaptive regime
    settings.regime.enabled = True
    settings.regime.ma_fast = 50
    settings.regime.ma_slow = 200
    settings.regime.vol_threshold = REGIME_VOL_THRESHOLD
    settings.regime.vol_window = 20
    settings.regime.neutral_band_pct = REGIME_NEUTRAL_BAND
    settings.regime.trend_favorable_sizing = TREND_FAVORABLE_SIZING
    settings.regime.neutral_sizing = NEUTRAL_SIZING

    # Momentum: STRICT
    settings.momentum.enabled = True
    settings.momentum.lookback = 20
    settings.momentum.weight = 0.30
    settings.momentum.min_strength = MOM_MIN_STRENGTH
    settings.momentum.max_boost = 1.0

    # Blacklist
    settings.pair_blacklist.enabled = True
    settings.pair_blacklist.max_consecutive_losses = BL_MAX_LOSSES
    settings.pair_blacklist.cooldown_days = BL_COOLDOWN

    # Risk
    settings.risk.max_concurrent_positions = 10

    if hasattr(settings.strategy, 'fdr_q_level'):
        settings.strategy.fdr_q_level = FDR_Q

    # == TIME STOP: Properly instantiate ==
    from execution.time_stop import TimeStopConfig, TimeStopManager
    time_stop = TimeStopManager(TimeStopConfig(
        half_life_multiplier=TIME_STOP_MULT,
        max_days_cap=MAX_HOLD_DAYS,
        default_max_bars=MAX_HOLD_DAYS,
    ))

    runner = BacktestRunner()
    runner.config.initial_capital = args.capital

    n_intra = sum(
        1 for i, s1 in enumerate(SYMBOLS)
        for s2 in SYMBOLS[i + 1:]
        if SECTOR_MAP.get(s1) == SECTOR_MAP.get(s2)
    )

    print("=" * 70)
    print("  EDGECORE BACKTEST v31i -- v31h + More Trades")
    print("=" * 70)
    print(f"  Symbols:      {len(SYMBOLS)} ({len(SYMBOLS)-1} trading + SPY)")
    print(f"  Pairs:        {n_intra} intra-sector")
    print(f"  Period:       {args.start} -> {args.end}")
    print(f"  Capital:      ${args.capital:,.0f}")
    print(f"  Alloc/pair:   {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%")
    print(f"  Z-score:      entry={ENTRY_Z}, exit={EXIT_Z}")
    print(f"  Stop:         {STOP_PCT*100:.0f}% | z_stop={Z_SCORE_STOP}")
    print("  --- v31i: Lower barriers for more trades ---")
    print(f"  entry_z:      {ENTRY_Z} (was 1.8)")
    print(f"  FDR_q:        {FDR_Q} (was 0.25)")
    print(f"  min_spread:   {MIN_SPREAD} (was 0.30)")
    print(f"  min_corr:     {MIN_CORR} (was 0.65)")
    print(f"  time_stop:    {TIME_STOP_MULT}x HL, cap={MAX_HOLD_DAYS}d")
    print(f"  momentum:     STRICT")
    print("=" * 70)
    print()

    t0 = time.time()
    print("[EDGECORE] Loading IBKR data + running backtest v31i...")
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
        time_stop=time_stop,
    )

    elapsed = time.time() - t0
    print(f"\n[EDGECORE] Backtest v31i completed in {elapsed:.1f}s")
    print()
    summary = metrics.summary()
    print(summary)
    print(f"\nUniverse: {len(SYMBOLS)} symbols | Intra-sector pairs: {n_intra}")

    # Save
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    out_path = os.path.join(_ROOT, "results", "bt_results_v31i.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Backtest v31i -- v31h + More Trades\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Period: {args.start} -> {args.end}\n")
        f.write(f"Capital: ${args.capital:,.0f}\n")
        f.write(f"Symbols: {len(SYMBOLS)} | Pairs: {n_intra}\n")
        f.write(f"Alloc: {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%\n")
        f.write(f"entry_z={ENTRY_Z}, exit_z={EXIT_Z}, min_spread=${MIN_SPREAD}\n")
        f.write(f"stop={STOP_PCT} | max_HL={MAX_HALF_LIFE} | corr={MIN_CORR} | FDR q={FDR_Q}\n")
        f.write(f"time_stop={TIME_STOP_MULT}x HL, cap={MAX_HOLD_DAYS}d\n")
        f.write(f"Momentum: STRICT\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write(summary)
    print(f"\n[Saved] {out_path}")


if __name__ == "__main__":
    main()
