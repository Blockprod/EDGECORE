#!/usr/bin/env python
"""EDGECORE Backtest v31e -- Win/Loss Ratio Optimization.

ITERATION HISTORY:
  v30b: +5.25%, Sharpe 0.74,  25 trades, WR 60%,  PF 2.63, DD -2.6%
  v31d: -0.69%, Sharpe -0.03, 50 trades, WR 60%,  PF 0.96, DD -9.4%

v31d was NEARLY breakeven with curated universe + strict momentum.
WR matches v30b (60%), 2x more trades. But avg_loss($863) >> avg_win($552).

v31e targets the win/loss RATIO:
  1. exit_z = 0.3 (was 0.5) — let winners run 40% further toward mean
  2. time_stop = 1.5x HL (was 2.0) — exit stale trades 25% sooner
  3. max_half_life = 55 (was 60) — only fast-converging pairs
  4. stop_pct = 6% (was 7%) — tighter cap on tail losses
  5. max_hold_days = 30 (was 40) — absolute time cap tighter

Expected: avg_win increases (lower exit_z), avg_loss decreases (faster exits)
Target: PF > 1.5 by improving avg_win/avg_loss from 0.64 to > 1.0

Period: 2023-03-04 to 2026-03-04 (3 years).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

# == Curated Universe (same as v31d - 74 symbols) =========================
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

# == v31e Parameters: Win/Loss Ratio Optimization ==========================
ENTRY_Z = 1.8           # v30b proven
EXIT_Z = 0.3            # LOWER — let winners run further (was 0.5)
ALLOC_PCT = 50.0        # v30b proven
HEAT = 3.0              # v30b proven
STOP_PCT = 0.06         # TIGHTER — cap tail losses (was 0.07)
MIN_CORR = 0.65         # v30b proven
MAX_HALF_LIFE = 55      # TIGHTER — only fast-converging pairs (was 60)
FDR_Q = 0.25            # v30b proven
REDISCOVERY = 2         # v30b proven
MIN_SPREAD = 0.30       # Unchanged
Z_SCORE_STOP = 3.0      # Unchanged

# Adaptive regime
TREND_FAVORABLE_SIZING = 1.0
NEUTRAL_SIZING = 0.70
REGIME_NEUTRAL_BAND = 0.02
REGIME_VOL_THRESHOLD = 0.18

# Legacy (OFF)
REGIME_DIRECTIONAL = False
TREND_LONG_SIZING = 0.75
SHORT_MULT = 0.50
DISABLE_SHORTS_BULL = False

# Time stop — TIGHTER
TIME_STOP_MULT = 1.5    # FASTER exits (was 2.0) — cut stale trades 25% sooner
MAX_HOLD_DAYS = 30       # SHORTER cap (was 40)

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
        description="EDGECORE Backtest v31e -- Win/Loss Ratio Optimization"
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

    # Time stop — TIGHTER
    from execution.time_stop import TimeStopConfig as _TSC
    _TSC.half_life_multiplier = TIME_STOP_MULT
    _TSC.max_days_cap = MAX_HOLD_DAYS
    _TSC.default_max_bars = MAX_HOLD_DAYS

    if hasattr(settings.strategy, 'fdr_q_level'):
        settings.strategy.fdr_q_level = FDR_Q

    runner = BacktestRunner()
    runner.config.initial_capital = args.capital

    n_intra = sum(
        1 for i, s1 in enumerate(SYMBOLS)
        for s2 in SYMBOLS[i + 1:]
        if SECTOR_MAP.get(s1) == SECTOR_MAP.get(s2)
    )

    print("=" * 70)
    print("  EDGECORE BACKTEST v31e -- Win/Loss Ratio Optimization")
    print("=" * 70)
    print(f"  Symbols:      {len(SYMBOLS)} ({len(SYMBOLS)-1} trading + SPY)")
    print(f"  Pairs:        {n_intra} intra-sector")
    print(f"  Period:       {args.start} -> {args.end}")
    print(f"  Capital:      ${args.capital:,.0f}")
    print(f"  Alloc/pair:   {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%")
    print(f"  Z-score:      entry={ENTRY_Z}, exit={EXIT_Z}")
    print(f"  Stop:         {STOP_PCT*100:.0f}% | z_stop={Z_SCORE_STOP}")
    print("  --- v31e Win/Loss Optimization ---")
    print(f"  exit_z:       {EXIT_Z} (was 0.5 -- winners run 40% further)")
    print(f"  time_stop:    {TIME_STOP_MULT}x HL (was 2.0 -- cut losers 25% sooner)")
    print(f"  max_hold:     {MAX_HOLD_DAYS}d (was 40 -- absolute time cap tighter)")
    print(f"  max_HL:       {MAX_HALF_LIFE} (was 60 -- only fast-converging pairs)")
    print(f"  stop_pct:     {STOP_PCT*100:.0f}% (was 7% -- tighter tail cap)")
    print(f"  Momentum:     STRICT (blocks ALL contra-momentum)")
    print(f"  Universe:     curated {len(SYMBOLS)} symbols")
    print("=" * 70)
    print()

    t0 = time.time()
    print("[EDGECORE] Loading IBKR data + running backtest v31e...")
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
    print(f"\n[EDGECORE] Backtest v31e completed in {elapsed:.1f}s")
    print()
    summary = metrics.summary()
    print(summary)
    print(f"\nUniverse: {len(SYMBOLS)} symbols | Intra-sector pairs: {n_intra}")

    # Save
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    out_path = os.path.join(_ROOT, "results", "bt_results_v31e.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Backtest v31e -- Win/Loss Ratio Optimization\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Period: {args.start} -> {args.end}\n")
        f.write(f"Capital: ${args.capital:,.0f}\n")
        f.write(f"Symbols: {len(SYMBOLS)} | Pairs: {n_intra}\n")
        f.write(f"Alloc: {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%\n")
        f.write(f"entry_z={ENTRY_Z}, exit_z={EXIT_Z}, min_spread=${MIN_SPREAD}\n")
        f.write(f"stop={STOP_PCT} | max_HL={MAX_HALF_LIFE} | corr={MIN_CORR} | FDR q={FDR_Q}\n")
        f.write(f"time_stop={TIME_STOP_MULT}x HL, max_hold={MAX_HOLD_DAYS}d\n")
        f.write(f"Momentum: STRICT (blocks ALL contra-momentum)\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write(summary)
    print(f"\n[Saved] {out_path}")

    # Performance check
    print("\n" + "=" * 70)
    print("  v31e PERFORMANCE CHECK")
    print("=" * 70)

    checks = []
    win_rate = getattr(metrics, 'win_rate', None)
    max_dd = getattr(metrics, 'max_drawdown_pct', None)
    total_return = getattr(metrics, 'total_return_pct', None)
    sharpe = getattr(metrics, 'sharpe_ratio', None)
    total_trades = getattr(metrics, 'total_trades', None)
    profit_factor = getattr(metrics, 'profit_factor', None)

    if total_trades is not None:
        checks.append(("Trades >= 25", f"{total_trades}", total_trades >= 25))
    if total_return is not None:
        checks.append(("Return > +5%", f"{total_return:+.2%}", total_return > 0.05))
    if sharpe is not None:
        checks.append(("Sharpe > 0.7", f"{sharpe:.2f}", sharpe > 0.7))
    if win_rate is not None:
        checks.append(("Win Rate >= 55%", f"{win_rate:.1%}", win_rate >= 0.55))
    if max_dd is not None:
        checks.append(("Max DD <= 8%", f"{max_dd:.2%}", abs(max_dd) <= 0.08))
    if profit_factor is not None:
        checks.append(("PF > 1.5", f"{profit_factor:.2f}", profit_factor > 1.5))

    for label, val, ok in checks:
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status}  {label}: {val}")

    all_ok = all(ok for _, _, ok in checks)
    passed = sum(1 for _, _, ok in checks if ok)
    print()
    if all_ok:
        print("  >>> ALL CRITERIA MET -- v31e VALIDATED!")
    else:
        print(f"  >>> {passed}/{len(checks)} criteria met.")
    print("=" * 70)

    # Comparison
    print("\n--- Full Iteration History ---")
    print("  v30b: +5.25% | Sharpe 0.74 | 25 tr | WR 60% | PF 2.63 | DD -2.6%")
    print("  v31d: -0.69% | Sharpe -0.03 | 50 tr | WR 60% | PF 0.96 | DD -9.4%")
    if total_return is not None:
        pnl = args.capital * total_return
        print(f"  v31e: {total_return:+.2%} | Sharpe {sharpe:.2f} | {total_trades} tr | WR {win_rate:.1%} | PF {profit_factor:.2f} | DD {max_dd:.1%}")
        print(f"  PnL:  ${pnl:,.0f}")


if __name__ == "__main__":
    main()
