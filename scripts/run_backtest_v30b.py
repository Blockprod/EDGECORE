#!/usr/bin/env python
"""EDGECORE Backtest v30b -- Adaptive Regime + Aggressive Trade Volume.

v30 result: +2.09%, Sharpe 0.57, 19 trades.
Problem: Only 19 trades in 3 years (6/year) -- too few to compound.
The adaptive regime is correct but the strict filters starve the strategy.

v30b APPROACH: Keep the adaptive bidirectional regime AND boost trade volume:
  1. Entry z-score 1.8 (was 2.0) -- more signal triggers
  2. Allocation 50%/pair (was 40%) -- deploy more capital per winner
  3. Heat 300% (was 250%) -- allow more concurrent positions
  4. Max half-life 60 (was 50) -- broader pair universe
  5. Min spread $0.30 (was $0.50) -- more entries pass
  6. FDR q=0.25 (was 0.20) -- more pairs survive FDR
  7. Rediscovery every 2 bars (was 3) -- find opportunities faster
  8. trend_favorable_sizing 1.0 -- full confidence in trend-aligned trades
  9. neutral_sizing 0.70 -- less penalty in uncertain direction
 10. Weekly z gate 0.3 (was 0.5) -- more entries allowed
 11. Blacklist 5 losses / 10d cooldown -- only penalize serial losers

Period: 2023-03-04 to 2026-03-04 (3 years).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

# == Universe ==============================================================
SYMBOLS = [
    "SPY",
    # Technology
    "AAPL",
    "MSFT",
    "GOOGL",
    "META",
    "NVDA",
    "AMD",
    "AVGO",
    # Financials
    "JPM",
    "GS",
    "BAC",
    "MS",
    "WFC",
    "C",
    "SCHW",
    # Energy
    "XOM",
    "CVX",
    "COP",
    "EOG",
    # Consumer Staples
    "KO",
    "PEP",
    "PG",
    "CL",
    "WMT",
    # Industrials
    "CAT",
    "HON",
    "DE",
    "GE",
    "RTX",
    # Utilities
    "NEE",
    "DUK",
    "SO",
    # Healthcare
    "JNJ",
    "PFE",
    "UNH",
    "MRK",
    "ABBV",
]

SECTOR_MAP = {
    "AAPL": "technology",
    "MSFT": "technology",
    "GOOGL": "technology",
    "META": "technology",
    "NVDA": "technology",
    "AMD": "technology",
    "AVGO": "technology",
    "JPM": "financials",
    "GS": "financials",
    "BAC": "financials",
    "MS": "financials",
    "WFC": "financials",
    "C": "financials",
    "SCHW": "financials",
    "XOM": "energy",
    "CVX": "energy",
    "COP": "energy",
    "EOG": "energy",
    "KO": "consumer_staples",
    "PEP": "consumer_staples",
    "PG": "consumer_staples",
    "CL": "consumer_staples",
    "WMT": "consumer_staples",
    "CAT": "industrials",
    "HON": "industrials",
    "DE": "industrials",
    "GE": "industrials",
    "RTX": "industrials",
    "NEE": "utilities",
    "DUK": "utilities",
    "SO": "utilities",
    "JNJ": "healthcare",
    "PFE": "healthcare",
    "UNH": "healthcare",
    "MRK": "healthcare",
    "ABBV": "healthcare",
}

# == v30b Aggressive Parameters ============================================
ENTRY_Z = 1.8  # Lower threshold -> more trades (was 2.0)
EXIT_Z = 0.5  # Unchanged
ALLOC_PCT = 50.0  # 50% per pair (was 40%)
HEAT = 3.0  # 300% heat (was 250%)
STOP_PCT = 0.07  # 7% P&L stop
MIN_CORR = 0.65  # Slightly looser (was 0.70)
MAX_HALF_LIFE = 60  # Broader (was 50)
FDR_Q = 0.25  # More lenient FDR (was 0.20)
REDISCOVERY = 2  # Faster pair discovery (was 3)
MIN_SPREAD = 0.30  # Lower threshold (was 0.50) -- more entries
Z_SCORE_STOP = 3.0  # Unchanged

# Adaptive regime (same v30 logic)
TREND_FAVORABLE_SIZING = 1.0  # Full sizing on trend-aligned side
NEUTRAL_SIZING = 0.70  # Less penalty in neutral
REGIME_NEUTRAL_BAND = 0.02  # Unchanged
REGIME_VOL_THRESHOLD = 0.18  # Unchanged

# Legacy (OFF)
REGIME_DIRECTIONAL = False
TREND_LONG_SIZING = 0.75
SHORT_MULT = 0.50
DISABLE_SHORTS_BULL = False

# Time stop
TIME_STOP_MULT = 2.0  # Unchanged
MAX_HOLD_DAYS = 40  # Unchanged

# Blacklist (very lenient)
BL_MAX_LOSSES = 5  # More forgiving (was 4)
BL_COOLDOWN = 10  # Fast recycling (was 15)

# Weekly gate
WEEKLY_Z_GATE = 0.3  # Very low gate (was 0.5) -- almost all entries pass


def main():
    import argparse

    parser = argparse.ArgumentParser(description="EDGECORE Backtest v30b -- Aggressive Adaptive Regime")
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

    # Legacy directional filter (OFF)
    settings.strategy.regime_directional_filter = REGIME_DIRECTIONAL
    settings.strategy.trend_long_sizing = TREND_LONG_SIZING
    settings.strategy.disable_shorts_in_bull_trend = DISABLE_SHORTS_BULL
    settings.strategy.short_sizing_multiplier = SHORT_MULT

    # v30 Adaptive regime
    settings.regime.enabled = True
    settings.regime.ma_fast = 50
    settings.regime.ma_slow = 200
    settings.regime.vol_threshold = REGIME_VOL_THRESHOLD
    settings.regime.vol_window = 20
    settings.regime.neutral_band_pct = REGIME_NEUTRAL_BAND
    settings.regime.trend_favorable_sizing = TREND_FAVORABLE_SIZING
    settings.regime.neutral_sizing = NEUTRAL_SIZING

    # Blacklist
    settings.pair_blacklist.enabled = True
    settings.pair_blacklist.max_consecutive_losses = BL_MAX_LOSSES
    settings.pair_blacklist.cooldown_days = BL_COOLDOWN

    # Time stop
    from execution.time_stop import TimeStopConfig as _TSC

    _TSC.half_life_multiplier = TIME_STOP_MULT
    _TSC.max_days_cap = MAX_HOLD_DAYS
    _TSC.default_max_bars = MAX_HOLD_DAYS

    if hasattr(settings.strategy, "fdr_q_level"):
        settings.strategy.fdr_q_level = FDR_Q

    runner = BacktestRunner()
    runner.config.initial_capital = args.capital

    n_intra = sum(
        1 for i, s1 in enumerate(SYMBOLS) for s2 in SYMBOLS[i + 1 :] if SECTOR_MAP.get(s1) == SECTOR_MAP.get(s2)
    )

    print("=" * 70)
    print("  EDGECORE BACKTEST v30b -- Aggressive Adaptive Regime")
    print("=" * 70)
    print(f"  Symbols:      {len(SYMBOLS)} ({len(SYMBOLS) - 1} trading + SPY)")
    print(f"  Pairs:        {n_intra} intra-sector")
    print(f"  Period:       {args.start} -> {args.end}")
    print(f"  Capital:      ${args.capital:,.0f}")
    print(f"  Alloc/pair:   {ALLOC_PCT}% | Heat: {HEAT * 100:.0f}%")
    print(f"  Stop:         {STOP_PCT * 100:.0f}% | z_stop={Z_SCORE_STOP}")
    print(f"  Z-score:      entry={ENTRY_Z}, exit={EXIT_Z}")
    print(f"  Min spread:   ${MIN_SPREAD:.2f}")
    print(f"  Half-life:    max={MAX_HALF_LIFE}d | Time stop={TIME_STOP_MULT}x HL (cap {MAX_HOLD_DAYS}d)")
    print(f"  Corr min:     {MIN_CORR} | FDR q={FDR_Q}")
    print(f"  Weekly gate:  |z| >= {WEEKLY_Z_GATE}")
    print("  --- v30b Aggressive Changes ---")
    print(f"  Entry z:      {ENTRY_Z} (was 2.0)")
    print(f"  Alloc:        {ALLOC_PCT}% (was 40%)")
    print(f"  Heat:         {HEAT * 100:.0f}% (was 250%)")
    print(f"  Min spread:   ${MIN_SPREAD} (was $0.50)")
    print(f"  FDR q:        {FDR_Q} (was 0.20)")
    print(f"  Min corr:     {MIN_CORR} (was 0.70)")
    print(f"  Half-life:    {MAX_HALF_LIFE}d (was 50d)")
    print(f"  Weekly gate:  {WEEKLY_Z_GATE} (was 0.5)")
    print(f"  Rediscovery:  every {REDISCOVERY} bars (was 3)")
    print(f"  Favorable sz: {TREND_FAVORABLE_SIZING:.0%} (was 85%)")
    print(f"  Neutral sz:   {NEUTRAL_SIZING:.0%} (was 60%)")
    print("=" * 70)
    print()

    t0 = time.time()
    print("[EDGECORE] Loading IBKR data + running backtest v30b...")
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
    print(f"\n[EDGECORE] Backtest v30b completed in {elapsed:.1f}s")
    print()
    summary = metrics.summary()
    print(summary)
    print(f"\nUniverse: {len(SYMBOLS)} symbols | Intra-sector pairs: {n_intra}")

    # Save
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    out_path = os.path.join(_ROOT, "results", "bt_results_v30b.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Backtest v30b -- Aggressive Adaptive Regime\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Period: {args.start} -> {args.end}\n")
        f.write(f"Capital: ${args.capital:,.0f}\n")
        f.write(f"Alloc: {ALLOC_PCT}% | Heat: {HEAT * 100:.0f}%\n")
        f.write(f"entry_z={ENTRY_Z}, exit_z={EXIT_Z}, min_spread=${MIN_SPREAD}\n")
        f.write(f"max_HL={MAX_HALF_LIFE} | corr={MIN_CORR} | FDR q={FDR_Q}\n")
        f.write(f"Adaptive regime: favorable={TREND_FAVORABLE_SIZING}, neutral={NEUTRAL_SIZING}\n")
        f.write(f"Rediscovery={REDISCOVERY} | weekly_z_gate={WEEKLY_Z_GATE}\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write(summary)
    print(f"\n[Saved] {out_path}")

    # Performance check
    print("\n" + "=" * 70)
    print("  v30b PERFORMANCE CHECK")
    print("=" * 70)

    checks = []
    win_rate = getattr(metrics, "win_rate", None)
    total_return = getattr(metrics, "total_return_pct", None)
    sharpe = getattr(metrics, "sharpe_ratio", None)
    total_trades = getattr(metrics, "total_trades", None)
    profit_factor = getattr(metrics, "profit_factor", None)

    if total_trades is not None:
        checks.append(("Trades >= 25", f"{total_trades}", total_trades >= 25))
    if win_rate is not None:
        checks.append(("Win rate >= 45%", f"{win_rate:.1%}", win_rate >= 0.45))
    if sharpe is not None:
        checks.append(("Sharpe > 0.5", f"{sharpe:.2f}", sharpe > 0.5))
    if profit_factor is not None:
        checks.append(("PF > 1.5", f"{profit_factor:.2f}", profit_factor > 1.5))

    for label, val, ok in checks:
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status}  {label}: {val}")

    all_ok = all(ok for _, _, ok in checks)
    passed = sum(1 for _, _, ok in checks if ok)
    print()
    if all_ok:
        print("  >>> ALL CRITERIA MET -- v30b VALIDATED!")
    else:
        print(f"  >>> {passed}/{len(checks)} criteria met.")
    print("=" * 70)

    # Comparison
    print("\n--- v30b vs v30 vs v29 ---")
    print("  v29: +2.08% | Sharpe 0.64 | 21 trades | WR 52.4% | PF 2.94")
    print("  v30: +2.09% | Sharpe 0.57 | 19 trades | WR 47.4% | PF 2.02")
    if total_return is not None:
        pnl = args.capital * total_return
        print(
            f"  v30b: {total_return:+.2%} | Sharpe {sharpe:.2f} | {total_trades} trades | WR {win_rate:.1%} | PF {profit_factor:.2f}"
        )
        print(f"  PnL: ${pnl:,.0f}")


if __name__ == "__main__":
    main()
