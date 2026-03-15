#!/usr/bin/env python
"""EDGECORE Backtest v31h -- v30b Universe + Momentum + TimeStop Fix.

ITERATION HISTORY:
  v30b: +5.25%, Sharpe 0.74,  25 trades, WR 60%,  PF 2.63, DD -2.6%
  v31d: -0.69%  (74 sym curated, strict momentum, PF 0.96)
  v31e: -1.44%  (exit_z=0.3 hurt, time_stop bug)
  v31f: -2.54%  (exit_z=0.3 + time_stop=1.5x -- conflicting changes)
  v31g: (running) v31d + time_stop fix only

v31h = v30b EXACT params + STRICT momentum + FIXED time_stop:
  - Original v30b 37-symbol universe (proven profitable)
  - v30b parameters exactly (entry_z=1.8, exit_z=0.5, etc.)
  - ADD: MomentumOverlay STRICT (min_strength=1.0 blocks contra-momentum)
  - ADD: TimeStop 1.5├ùHL, cap=30d (properly injected)

Hypothesis: v30b's universe has PROVEN edge. Adding momentum filter
should INCREASE win rate and PF by blocking bad entries.
TimeStop fix should cut stale losers sooner.
Expected: Return > +5.25%, PF > 2.63 (improve on v30b baseline)

Period: 2023-03-04 to 2026-03-04 (3 years).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

# == v30b Universe (37 symbols ÔÇö PROVEN profitable) =========================
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

# == v30b Parameters EXACTLY ================================================
ENTRY_Z = 1.8
EXIT_Z = 0.5
ALLOC_PCT = 50.0
HEAT = 3.0
STOP_PCT = 0.07
MIN_CORR = 0.65
MAX_HALF_LIFE = 60
FDR_Q = 0.25
REDISCOVERY = 2
MIN_SPREAD = 0.30
Z_SCORE_STOP = 3.0

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

# Time stop ÔÇö IMPROVED (properly injected)
TIME_STOP_MULT = 1.5
MAX_HOLD_DAYS = 30

# Blacklist (v30b)
BL_MAX_LOSSES = 5
BL_COOLDOWN = 10

# Weekly gate (v30b)
WEEKLY_Z_GATE = 0.3

# Momentum: STRICT ÔÇö NEW vs v30b
MOM_MIN_STRENGTH = 1.0


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="EDGECORE Backtest v31h -- v30b + Momentum + TimeStop"
    )
    parser.add_argument("--start", default="2023-03-04")
    parser.add_argument("--end", default="2026-03-04")
    parser.add_argument("--capital", type=float, default=100_000)
    args = parser.parse_args()

    from config.settings import get_settings
    settings = get_settings()

    # Strategy ÔÇö v30b params exactly
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

    # Momentum: STRICT ÔÇö new addition to v30b
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
    print("  EDGECORE BACKTEST v31h -- v30b Universe + Momentum + TimeStop")
    print("=" * 70)
    print(f"  Symbols:      {len(SYMBOLS)} ({len(SYMBOLS)-1} trading + SPY)")
    print(f"  Pairs:        {n_intra} intra-sector")
    print(f"  Period:       {args.start} -> {args.end}")
    print(f"  Capital:      ${args.capital:,.0f}")
    print(f"  Alloc/pair:   {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%")
    print(f"  Z-score:      entry={ENTRY_Z}, exit={EXIT_Z}")
    print(f"  Stop:         {STOP_PCT*100:.0f}% | z_stop={Z_SCORE_STOP}")
    print("  --- v31h: v30b + NEW Momentum + TimeStop ---")
    print(f"  time_stop:    {TIME_STOP_MULT}x HL, cap={MAX_HOLD_DAYS}d (FIXED)")
    print(f"  momentum:     STRICT (min_strength={MOM_MIN_STRENGTH})")
    print(f"  Universe:     v30b original {len(SYMBOLS)} symbols")
    print("=" * 70)
    print()

    t0 = time.time()
    print("[EDGECORE] Loading IBKR data + running backtest v31h...")
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
    print(f"\n[EDGECORE] Backtest v31h completed in {elapsed:.1f}s")
    print()
    summary = metrics.summary()
    print(summary)
    print(f"\nUniverse: {len(SYMBOLS)} symbols | Intra-sector pairs: {n_intra}")

    # Save
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    out_path = os.path.join(_ROOT, "results", "bt_results_v31h.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Backtest v31h -- v30b + Momentum + TimeStop\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Period: {args.start} -> {args.end}\n")
        f.write(f"Capital: ${args.capital:,.0f}\n")
        f.write(f"Symbols: {len(SYMBOLS)} | Pairs: {n_intra}\n")
        f.write(f"Alloc: {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%\n")
        f.write(f"entry_z={ENTRY_Z}, exit_z={EXIT_Z}, min_spread=${MIN_SPREAD}\n")
        f.write(f"stop={STOP_PCT} | max_HL={MAX_HALF_LIFE} | corr={MIN_CORR} | FDR q={FDR_Q}\n")
        f.write(f"time_stop={TIME_STOP_MULT}x HL, cap={MAX_HOLD_DAYS}d (FIXED)\n")
        f.write(f"Momentum: STRICT (min_strength={MOM_MIN_STRENGTH})\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write(summary)
    print(f"\n[Saved] {out_path}")


if __name__ == "__main__":
    main()
