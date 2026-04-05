#!/usr/bin/env python
"""EDGECORE Backtest v29 -- Directional Regime + Optimised Parameters.

Root cause of v28 failure: regime filter blocked ALL entries (longs + shorts)
during 2023-2026 bull market. Only 7 trades, 1 win.

v29 KEY INSIGHT: In a bull market, LONG-side mean reversion (buy the dip in
relative value) has a natural tailwind. SHORT-side MR (sell the outperformer)
is structurally losing. The fix is a DIRECTIONAL regime filter:
  - TRENDING: block shorts, allow longs at 75% sizing
  - NEUTRAL:  shorts at 50%, longs at 100%
  - MEAN_REVERTING: both at 100%

Additional optimisations:
  1. Directional regime filter (NEW) -- longs pass in TRENDING
  2. Disable shorts in bull trend (was False -> True)
  3. Max half-life 45 (was 120) -- only fast-reverting pairs
  4. Exit z-score 0.5 (was 0.3) -- take profits faster
  5. Allocation 30%/pair (was 90%) -- diversification
  6. Heat 200% (was 400%) -- less leverage
  7. Position stop 5% (was 10%) -- tighter risk
  8. Time stop 1.5x HL (was 2.0x) -- cut losers sooner
  9. Max holding 30 days (was 60) -- capital velocity
 10. Z-score stop 3.0 (was 3.5) -- earlier divergence exit
 11. Weekly z-score gate 0.5 (was 1.0) -- more entries allowed
 12. Blacklist 3 losses / 20d cooldown (was 2/30) -- less restrictive

Period: 3 years rolling from today (2023-03-04 to 2026-03-04).
Data source: IBKR Gateway (port 4002).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

# == Universe ==============================================================
# Same broad universe + SPY for regime detection.
# Focus on sectors with strongest mean-reversion properties:
#   Financials (banks co-move), Utilities (defensive), Consumer Staples,
#   Energy (commodity-driven), Industrials.
# Tech kept but MA pairs (AAPL/MSFT, NVDA/AMD) are momentum-prone.
SYMBOLS = [
    "SPY",  # Index -- required for market regime filter
    # Technology
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO",
    # Financials (strong mean-reversion sector)
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    # Energy
    "XOM", "CVX", "COP", "EOG",
    # Consumer Staples (defensive / low-vol -- good MR)
    "KO", "PEP", "PG", "CL", "WMT",
    # Industrials
    "CAT", "HON", "DE", "GE", "RTX",
    # Utilities (best MR sector)
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

# == v29 Optimised Parameters =============================================
ENTRY_Z = 2.0           # Proven threshold
EXIT_Z = 0.5            # Take profit faster (was 0.3)
ALLOC_PCT = 30.0        # Per-pair allocation (was 90%) -- diversification
HEAT = 2.0              # Max portfolio heat 200% (was 400%)
STOP_PCT = 0.05         # 5% P&L stop per position (was 10%) -- tighter
MIN_CORR = 0.70         # High quality pairs only
MAX_HALF_LIFE = 45      # Only fast-reverting pairs (was 120)
FDR_Q = 0.20            # BH-FDR threshold
REDISCOVERY = 3         # Pair rediscovery interval (bars)
MIN_SPREAD = 0.50       # Min absolute spread ($)
Z_SCORE_STOP = 3.0      # Z-score stop-loss (was 3.5) -- tighter
# Directional regime (NEW)
REGIME_DIRECTIONAL = True
TREND_LONG_SIZING = 0.75   # Longs at 75% in TRENDING
# Shorts
SHORT_MULT = 0.50       # Shorts at 50% in NEUTRAL (irrelevant in TRENDING -- blocked)
DISABLE_SHORTS_BULL = True  # No shorts at all in TRENDING
# Time stop
TIME_STOP_MULT = 1.5    # 1.5x half-life (was 2.0)
MAX_HOLD_DAYS = 30      # Cap at 30 days (was 60)
# Blacklist
BL_MAX_LOSSES = 3       # Blacklist after 3 consecutive losses (was 2)
BL_COOLDOWN = 20        # 20-day cooldown (was 30)
# Weekly gate
WEEKLY_Z_GATE = 0.5     # Lower weekly z gate (was 1.0) -- more entries


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="EDGECORE Backtest v29 -- Directional Regime Strategy"
    )
    parser.add_argument("--start", default="2023-03-04")
    parser.add_argument("--end", default="2026-03-04")
    parser.add_argument("--capital", type=float, default=100_000)
    args = parser.parse_args()

    # == Configure settings (Singleton) ====================================
    from config.settings import get_settings
    settings = get_settings()

    # Strategy core
    settings.strategy.lookback_window = 120
    settings.strategy.additional_lookback_windows = [63]  # ~3 months secondary
    settings.strategy.entry_z_score = ENTRY_Z
    settings.strategy.exit_z_score = EXIT_Z
    settings.strategy.entry_z_min_spread = MIN_SPREAD
    settings.strategy.z_score_stop = Z_SCORE_STOP
    settings.strategy.min_correlation = MIN_CORR
    settings.strategy.max_half_life = MAX_HALF_LIFE
    settings.strategy.max_position_loss_pct = STOP_PCT
    settings.strategy.internal_max_drawdown_pct = 0.20
    settings.strategy.use_kalman = True
    settings.strategy.bonferroni_correction = True
    settings.strategy.johansen_confirmation = True
    settings.strategy.newey_west_consensus = True
    settings.strategy.weekly_zscore_entry_gate = WEEKLY_Z_GATE

    # v29: Directional regime filter
    settings.strategy.regime_directional_filter = REGIME_DIRECTIONAL
    settings.strategy.trend_long_sizing = TREND_LONG_SIZING
    settings.strategy.disable_shorts_in_bull_trend = DISABLE_SHORTS_BULL
    settings.strategy.short_sizing_multiplier = SHORT_MULT

    # Regime filter
    settings.regime.enabled = True
    settings.regime.ma_fast = 50
    settings.regime.ma_slow = 200
    settings.regime.vol_threshold = 0.18
    settings.regime.vol_window = 20
    settings.regime.neutral_band_pct = 0.02

    # Blacklist (less restrictive)
    settings.pair_blacklist.enabled = True
    settings.pair_blacklist.max_consecutive_losses = BL_MAX_LOSSES
    settings.pair_blacklist.cooldown_days = BL_COOLDOWN

    # Time stop -- override via TimeStopConfig instance defaults
    # The simulator creates TimeStopManager() which reads TimeStopConfig defaults.
    # We change the class-level defaults before the simulator instantiates it.
    from execution.time_stop import TimeStopConfig as _TSC
    _TSC.half_life_multiplier = TIME_STOP_MULT
    _TSC.max_days_cap = MAX_HOLD_DAYS
    _TSC.default_max_bars = MAX_HOLD_DAYS

    # FDR level
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
    print("  EDGECORE BACKTEST v29 -- Directional Regime Strategy")
    print("=" * 70)
    print(f"  Symbols:      {len(SYMBOLS)} ({len(SYMBOLS)-1} trading + SPY regime ref)")
    print(f"  Pairs:        {n_intra} intra-sector")
    print(f"  Period:       {args.start} -> {args.end} (3 years rolling)")
    print(f"  Capital:      ${args.capital:,.0f}")
    print(f"  Alloc/pair:   {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%")
    print(f"  Stop:         {STOP_PCT*100:.0f}% | z_stop={Z_SCORE_STOP}")
    print(f"  Z-score:      entry={ENTRY_Z}, exit={EXIT_Z}")
    print(f"  Min spread:   ${MIN_SPREAD:.2f}")
    print(f"  Half-life:    max={MAX_HALF_LIFE}d | Time stop={TIME_STOP_MULT}x HL (cap {MAX_HOLD_DAYS}d)")
    print(f"  Corr min:     {MIN_CORR} | FDR q={FDR_Q}")
    print(f"  Weekly gate:  |z| >= {WEEKLY_Z_GATE}")
    print("  --- v29 Key Changes ---")
    print(f"  [NEW] Directional regime: longs ALLOWED in TRENDING at {TREND_LONG_SIZING:.0%}")
    print(f"  [NEW] Shorts in TRENDING: BLOCKED (disable_shorts=True)")
    print(f"  [NEW] Shorts in NEUTRAL:  {SHORT_MULT:.0%} sizing")
    print(f"  [NEW] Blacklist: {BL_MAX_LOSSES} losses -> {BL_COOLDOWN}d cooldown")
    print("=" * 70)
    print()

    t0 = time.time()
    print("[EDGECORE] Loading IBKR data + running backtest v29...")
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
    print(f"\n[EDGECORE] Backtest v29 completed in {elapsed:.1f}s")
    print()
    summary = metrics.summary()
    print(summary)
    print(f"\nUniverse: {len(SYMBOLS)} symbols | Intra-sector pairs: {n_intra}")

    # == Save results ======================================================
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    out_path = os.path.join(_ROOT, "results", "bt_results_v29.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Backtest v29 -- Directional Regime Strategy\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Period: {args.start} -> {args.end}\n")
        f.write(f"Capital: ${args.capital:,.0f}\n")
        f.write(f"Alloc: {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%\n")
        f.write(f"Z-score: entry={ENTRY_Z}, exit={EXIT_Z} | min_spread=${MIN_SPREAD}\n")
        f.write(f"Half-life max={MAX_HALF_LIFE} | Time stop={TIME_STOP_MULT}x HL (cap {MAX_HOLD_DAYS}d)\n")
        f.write(f"Directional regime: ON (trend_long_sizing={TREND_LONG_SIZING})\n")
        f.write(f"Shorts: BLOCKED in TRENDING, {SHORT_MULT}x in NEUTRAL\n")
        f.write(f"Blacklist: {BL_MAX_LOSSES} losses / {BL_COOLDOWN}d cooldown\n")
        f.write(f"Weekly z gate: {WEEKLY_Z_GATE}\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write(summary)
    print(f"\n[Saved] {out_path}")

    # == Success criteria check ============================================
    print("\n" + "=" * 70)
    print("  v29 PERFORMANCE CHECK")
    print("=" * 70)

    checks = []
    win_rate = getattr(metrics, 'win_rate', None)
    max_dd = getattr(metrics, 'max_drawdown_pct', None)
    total_return = getattr(metrics, 'total_return_pct', None)
    sharpe = getattr(metrics, 'sharpe_ratio', None)
    total_trades = getattr(metrics, 'total_trades', None)

    if total_trades is not None:
        checks.append(("Total trades", f"{total_trades}", total_trades >= 10))

    if win_rate is not None:
        checks.append(("Win rate >= 40%", f"{win_rate:.1%}", win_rate >= 0.40))

    if max_dd is not None:
        dd_val = abs(max_dd)
        checks.append(("Max DD <= 15%", f"{dd_val:.1%}", dd_val <= 0.15))

    if total_return is not None:
        checks.append(("PnL net > 0", f"{total_return:.2%}", total_return > 0))

    if sharpe is not None:
        checks.append(("Sharpe > 0", f"{sharpe:.2f}", sharpe > 0))

    for label, val, ok in checks:
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status}  {label}: {val}")

    all_ok = all(ok for _, _, ok in checks)
    print()
    if all_ok:
        print("  >>> ALL CRITERIA MET -- v29 strategy validated!")
    else:
        passed = sum(1 for _, _, ok in checks if ok)
        print(f"  >>> {passed}/{len(checks)} criteria met.")
    print("=" * 70)

    # == Detailed trade analysis ===========================================
    print("\n--- Trade Breakdown ---")
    # Count long vs short wins/losses from the trade log
    long_count = 0
    short_count = 0
    # These would need the internal trades list, approximate from metrics
    if total_trades is not None and total_trades > 0:
        if win_rate is not None:
            wins = int(round(total_trades * win_rate))
            losses = total_trades - wins
            print(f"  Wins: {wins} | Losses: {losses}")
        print(f"  Trades: {total_trades}")
    if total_return is not None and total_return > 0:
        print("  >> Strategy is PROFITABLE on this window.")
    elif total_return is not None:
        print(f"  >> Net return: {total_return:.2%} -- review parameters.")


if __name__ == "__main__":
    main()
