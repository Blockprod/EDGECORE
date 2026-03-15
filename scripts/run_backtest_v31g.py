#!/usr/bin/env python
"""EDGECORE Backtest v31g -- v31d params + FIXED TimeStop (1.5├ùHL, cap=30).

ITERATION HISTORY:
  v30b: +5.25%, Sharpe 0.74,  25 trades, WR 60%,  PF 2.63, DD -2.6%
  v31d: -0.69%, Sharpe -0.03, 50 trades, WR 60%,  PF 0.96, DD -9.4%
  v31e: -1.44%, Sharpe -0.09, 50 trades, WR 60%,  PF 0.91, DD -9.0%
       (exit_z=0.3 HURT. time_stop BUG: 2.0├ùHL not 1.5├ùHL)
  v31f: (running) -- same as v31e but with FIXED time_stop

v31g = v31d params EXACTLY + only the time_stop fix:
  - Restores exit_z=0.5 (v31d value ÔÇö exit_z=0.3 proved worse)
  - Restores stop_pct=0.07 (v31d value ÔÇö 6% was too tight)
  - Restores max_half_life=60 (v31d value)
  - ONLY CHANGE: time_stop=1.5├ùHL, cap=30 (properly injected)

This isolates the TIME STOP impact from other parameter changes.

Period: 2023-03-04 to 2026-03-04 (3 years).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

# == Curated Universe (same as v31d - 74 symbols) ==========================
SYMBOLS = [
    "SPY",
    # Technology (Mega Cap)
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "INTC", "AVGO",
    "CRM", "ADBE",
    # Technology (Semiconductors)
    "MRVL", "ON", "MCHP", "QCOM", "TXN", "AMAT", "LRCX", "KLAC",
    # Financials (Mega Cap)
    "JPM", "BAC", "GS", "MS", "WFC", "C", "BLK", "SCHW",
    # Healthcare (Mega Cap Pharma Only)
    "JNJ", "UNH", "MRK", "ABBV", "LLY", "TMO", "ABT",
    # Consumer Staples
    "KO", "PEP", "PG", "CL", "WMT", "COST",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG", "VLO", "MPC", "PSX", "DVN",
    "HAL", "BKR",
    # Industrials
    "CAT", "DE", "HON", "GE", "RTX", "LMT", "MMM", "EMR", "ITW",
    "ROK", "CMI", "PH",
    # Utilities
    "NEE", "DUK", "SO", "D",
    # Sector ETFs
    "XLK", "SMH", "XLF", "XLE", "XLI", "XLU", "XLP",
]

SECTOR_MAP = {
    "AAPL": "technology", "MSFT": "technology",
    "GOOGL": "technology", "META": "technology",
    "NVDA": "technology", "AMD": "technology",
    "INTC": "technology", "AVGO": "technology",
    "CRM": "technology", "ADBE": "technology",
    "MRVL": "technology", "ON": "technology",
    "MCHP": "technology", "QCOM": "technology",
    "TXN": "technology", "AMAT": "technology",
    "LRCX": "technology", "KLAC": "technology",
    "XLK": "technology", "SMH": "technology",
    "JPM": "financials", "BAC": "financials",
    "GS": "financials", "MS": "financials",
    "WFC": "financials", "C": "financials",
    "BLK": "financials", "SCHW": "financials",
    "XLF": "financials",
    "JNJ": "healthcare", "UNH": "healthcare",
    "MRK": "healthcare", "ABBV": "healthcare",
    "LLY": "healthcare", "TMO": "healthcare",
    "ABT": "healthcare",
    "KO": "consumer_staples", "PEP": "consumer_staples",
    "PG": "consumer_staples", "CL": "consumer_staples",
    "WMT": "consumer_staples", "COST": "consumer_staples",
    "XLP": "consumer_staples",
    "XOM": "energy", "CVX": "energy",
    "COP": "energy", "SLB": "energy",
    "EOG": "energy", "VLO": "energy",
    "MPC": "energy", "PSX": "energy",
    "DVN": "energy", "HAL": "energy",
    "BKR": "energy", "XLE": "energy",
    "CAT": "industrials", "DE": "industrials",
    "HON": "industrials", "GE": "industrials",
    "RTX": "industrials", "LMT": "industrials",
    "MMM": "industrials", "EMR": "industrials",
    "ITW": "industrials", "ROK": "industrials",
    "CMI": "industrials", "PH": "industrials",
    "XLI": "industrials",
    "NEE": "utilities", "DUK": "utilities",
    "SO": "utilities", "D": "utilities",
    "XLU": "utilities",
}

# == v31g Parameters: v31d EXACT + time_stop fix only =======================
ENTRY_Z = 1.8           # v30b/v31d
EXIT_Z = 0.5            # RESTORED from v31d (exit_z=0.3 was worse)
ALLOC_PCT = 50.0        # v30b/v31d
HEAT = 3.0              # v30b/v31d
STOP_PCT = 0.07         # RESTORED from v31d (6% was too tight)
MIN_CORR = 0.65         # v30b/v31d
MAX_HALF_LIFE = 60      # RESTORED from v31d
FDR_Q = 0.25            # v30b/v31d
REDISCOVERY = 2         # v30b/v31d
MIN_SPREAD = 0.30       # v31d
Z_SCORE_STOP = 3.0      # v31d

# Adaptive regime (v31d)
TREND_FAVORABLE_SIZING = 1.0
NEUTRAL_SIZING = 0.70
REGIME_NEUTRAL_BAND = 0.02
REGIME_VOL_THRESHOLD = 0.18

# Legacy (OFF)
REGIME_DIRECTIONAL = False
TREND_LONG_SIZING = 0.75
SHORT_MULT = 0.50
DISABLE_SHORTS_BULL = False

# Time stop ÔÇö ONLY CHANGE from v31d
TIME_STOP_MULT = 1.5    # was 2.0 in v31d default
MAX_HOLD_DAYS = 30       # was 60 in v31d default

# Blacklist
BL_MAX_LOSSES = 5
BL_COOLDOWN = 10

# Weekly gate
WEEKLY_Z_GATE = 0.3

# Momentum: STRICT
MOM_MIN_STRENGTH = 1.0


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="EDGECORE Backtest v31g -- v31d + TimeStop Fix"
    )
    parser.add_argument("--start", default="2023-03-04")
    parser.add_argument("--end", default="2026-03-04")
    parser.add_argument("--capital", type=float, default=100_000)
    args = parser.parse_args()

    from config.settings import get_settings
    settings = get_settings()

    # Strategy ÔÇö v31d params exactly
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

    # == TIME STOP: Properly instantiate (FIXED) ==
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
    print("  EDGECORE BACKTEST v31g -- v31d + TimeStop Fix Only")
    print("=" * 70)
    print(f"  Symbols:      {len(SYMBOLS)} ({len(SYMBOLS)-1} trading + SPY)")
    print(f"  Pairs:        {n_intra} intra-sector")
    print(f"  Period:       {args.start} -> {args.end}")
    print(f"  Capital:      ${args.capital:,.0f}")
    print(f"  Alloc/pair:   {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%")
    print(f"  Z-score:      entry={ENTRY_Z}, exit={EXIT_Z}")
    print(f"  Stop:         {STOP_PCT*100:.0f}% | z_stop={Z_SCORE_STOP}")
    print("  --- v31g: v31d + FIXED TimeStop ---")
    print(f"  time_stop:    {TIME_STOP_MULT}x HL, cap={MAX_HOLD_DAYS}d (FIXED)")
    print(f"  All other params: identical to v31d")
    print(f"  Momentum:     STRICT (blocks ALL contra-momentum)")
    print("=" * 70)
    print()

    t0 = time.time()
    print("[EDGECORE] Loading IBKR data + running backtest v31g...")
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
    print(f"\n[EDGECORE] Backtest v31g completed in {elapsed:.1f}s")
    print()
    summary = metrics.summary()
    print(summary)
    print(f"\nUniverse: {len(SYMBOLS)} symbols | Intra-sector pairs: {n_intra}")

    # Save
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    out_path = os.path.join(_ROOT, "results", "bt_results_v31g.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Backtest v31g -- v31d + TimeStop Fix Only\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Period: {args.start} -> {args.end}\n")
        f.write(f"Capital: ${args.capital:,.0f}\n")
        f.write(f"Symbols: {len(SYMBOLS)} | Pairs: {n_intra}\n")
        f.write(f"Alloc: {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%\n")
        f.write(f"entry_z={ENTRY_Z}, exit_z={EXIT_Z}, min_spread=${MIN_SPREAD}\n")
        f.write(f"stop={STOP_PCT} | max_HL={MAX_HALF_LIFE} | corr={MIN_CORR} | FDR q={FDR_Q}\n")
        f.write(f"time_stop={TIME_STOP_MULT}x HL, cap={MAX_HOLD_DAYS}d (FIXED)\n")
        f.write(f"Momentum: STRICT (blocks ALL contra-momentum)\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write(summary)
    print(f"\n[Saved] {out_path}")


if __name__ == "__main__":
    main()
