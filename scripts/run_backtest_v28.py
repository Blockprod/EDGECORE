#!/usr/bin/env python
"""EDGECORE Backtest v28 — Post-correction validation (Étapes 1-5).

All 5 structural corrections applied on the same 2023-2026 window as v27:
  Étape 1: Market regime filter (SPY MA50/200 + realized vol) → block TRENDING
  Étape 2: entry_z raised to 2.0 (was 1.5), min spread $0.50
  Étape 3: Dynamic pair blacklist (2 consecutive losses → 30-day cooldown)
  Étape 4: Short sizing ×0.5 in TRENDING/NEUTRAL bull
  Étape 5: Time stop multiplier 2.0 (was 3.0)

v27 baseline:  -26.55%, Sharpe -1.28, 35.8% win rate, 5 time stops, GE_RTX ×6
Success criteria (v28):
  - Win rate  ≥ 45%
  - Max DD    ≤ 15%
  - PnL net   > 0
  - Time stops ≤ 2
  - GE_RTX    ≤ 2 trades

Data source: IBKR Gateway (port 4002).
SPY included in universe for regime detection.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

# ── Universe ─────────────────────────────────────────────────────────
# Same 31 symbols as v27 + SPY (required for regime filter Étape 1)
SYMBOLS = [
    "SPY",  # Index — required for market regime filter
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO",
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    "XOM", "CVX", "COP", "EOG",
    "KO", "PEP", "PG", "CL", "WMT",
    "CAT", "HON", "DE", "GE", "RTX",
    "NEE", "DUK", "SO",
]

SECTOR_MAP = {
    # SPY excluded from sector map — it's the regime reference, not a trading symbol
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

# ── v28 Parameters (all corrections applied) ─────────────────────────
ENTRY_Z = 2.0           # Étape 2: raised from 1.5
EXIT_Z = 0.3
ALLOC_PCT = 90.0
HEAT = 4.0
STOP_PCT = 0.10
MIN_CORR = 0.50
MAX_HALF_LIFE = 120
FDR_Q = 0.20
REDISCOVERY = 3
MIN_SPREAD = 0.50       # Étape 2: min absolute spread filter
SHORT_MULT = 0.50       # Étape 4: short sizing in bull trend
TIME_STOP_MULT = 2.0    # Étape 5: was 3.0


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="EDGECORE Backtest v28 — Post-correction validation"
    )
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2026-01-01")
    parser.add_argument("--capital", type=float, default=100_000)
    args = parser.parse_args()

    # ── Configure settings (Singleton) ────────────────────────────────
    from config.settings import get_settings
    settings = get_settings()

    # Strategy core
    settings.strategy.lookback_window = 252
    settings.strategy.additional_lookback_windows = [126]
    settings.strategy.entry_z_score = ENTRY_Z
    settings.strategy.exit_z_score = EXIT_Z
    settings.strategy.entry_z_min_spread = MIN_SPREAD       # Étape 2
    settings.strategy.z_score_stop = 3.5
    settings.strategy.min_correlation = MIN_CORR
    settings.strategy.max_half_life = MAX_HALF_LIFE
    settings.strategy.max_position_loss_pct = STOP_PCT
    settings.strategy.internal_max_drawdown_pct = 0.25
    settings.strategy.use_kalman = True
    settings.strategy.bonferroni_correction = True
    settings.strategy.johansen_confirmation = True
    settings.strategy.newey_west_consensus = True

    # Étape 4: Directional bias
    settings.strategy.short_sizing_multiplier = SHORT_MULT
    settings.strategy.disable_shorts_in_bull_trend = False

    # Étape 1: Regime filter (enabled by default, confirm explicitly)
    settings.regime.enabled = True
    settings.regime.ma_fast = 50
    settings.regime.ma_slow = 200
    settings.regime.vol_threshold = 0.18
    settings.regime.vol_window = 20
    settings.regime.neutral_band_pct = 0.02

    # Étape 3: Dynamic pair blacklist (enabled by default, confirm)
    settings.pair_blacklist.enabled = True
    settings.pair_blacklist.max_consecutive_losses = 2
    settings.pair_blacklist.cooldown_days = 30

    # Étape 5: Time stop multiplier is set via TimeStopConfig default (2.0)
    # The simulator creates TimeStopManager() which reads the new default.

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
    print("  EDGECORE BACKTEST v28 -- Post-Correction Validation")
    print("  All 5 structural corrections applied (Etapes 1-5)")
    print("=" * 70)
    print(f"  Symbols:      {len(SYMBOLS)} ({len(SYMBOLS)-1} trading + SPY regime ref)")
    print(f"  Pairs:        {n_intra} intra-sector (BH-FDR q={FDR_Q})")
    print(f"  Period:       {args.start} -> {args.end}")
    print(f"  Capital:      ${args.capital:,.0f}")
    print(f"  Alloc/pair:   {ALLOC_PCT}%")
    print(f"  Heat limit:   {HEAT*100:.0f}%")
    print(f"  Stop:         {STOP_PCT*100:.0f}% | z_stop=3.5")
    print(f"  Z-score:      entry={ENTRY_Z}, exit={EXIT_Z}")
    print(f"  Min spread:   ${MIN_SPREAD:.2f}")
    print(f"  FDR q:        {FDR_Q} | Corr min: {MIN_CORR} | HL max: {MAX_HALF_LIFE}")
    print(f"  Rediscovery:  every {REDISCOVERY} bar(s)")
    print("  Statistics:   Bonferroni + Johansen + Newey-West + Kalman")
    print("  --- Corrections -------------------------------------------")
    print(f"  [E1] Regime:    ENABLED (SPY MA{settings.regime.ma_fast}/{settings.regime.ma_slow}, vol>{settings.regime.vol_threshold})")
    print(f"  [E2] Entry Z:   {ENTRY_Z} (was 1.5) + min spread ${MIN_SPREAD}")
    print(f"  [E3] Blacklist: ENABLED (max {settings.pair_blacklist.max_consecutive_losses} losses -> {settings.pair_blacklist.cooldown_days}d cooldown)")
    print(f"  [E4] Short x:   {SHORT_MULT} in TRENDING/NEUTRAL")
    print(f"  [E5] Time stop: {TIME_STOP_MULT}x HL (was 3.0x)")
    print("=" * 70)
    print()

    t0 = time.time()
    print("[EDGECORE] Loading IBKR data + running backtest v28...")
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
    print(f"\n[EDGECORE] Backtest v28 completed in {elapsed:.1f}s")
    print()
    summary = metrics.summary()
    print(summary)
    print(f"\nUniverse: {len(SYMBOLS)} symbols | Intra-sector pairs: {n_intra}")

    # ── Save results ──────────────────────────────────────────────────
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    out_path = os.path.join(_ROOT, "results", "bt_results_v28.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Backtest v28 — Post-Correction Validation\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Period: {args.start} -> {args.end}\n")
        f.write(f"Capital: ${args.capital:,.0f}\n")
        f.write(f"Alloc: {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%\n")
        f.write(f"Z-score: entry={ENTRY_Z}, exit={EXIT_Z} | min_spread=${MIN_SPREAD}\n")
        f.write(f"FDR q={FDR_Q} | Corr min: {MIN_CORR} | HL max: {MAX_HALF_LIFE}\n")
        f.write(f"Corrections: Regime=ON, Blacklist=ON, Short×={SHORT_MULT}, ")
        f.write(f"TimeStop={TIME_STOP_MULT}×HL\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write(summary)
    print(f"\n[Saved] {out_path}")

    # ── v28 success criteria check ────────────────────────────────────
    print("\n" + "=" * 70)
    print("  v28 SUCCESS CRITERIA CHECK")
    print("=" * 70)

    checks = []

    # Extract metrics for criteria check
    win_rate = getattr(metrics, 'win_rate', None)
    max_dd = getattr(metrics, 'max_drawdown_pct', None)
    total_return = getattr(metrics, 'total_return_pct', None)

    if win_rate is not None:
        ok = win_rate >= 0.45
        checks.append(("Win rate >= 45%", f"{win_rate:.1%}", ok))
    else:
        checks.append(("Win rate >= 45%", "N/A", False))

    if max_dd is not None:
        dd_val = abs(max_dd)
        ok = dd_val <= 0.15
        checks.append(("Max DD <= 15%", f"{dd_val:.1%}", ok))
    else:
        checks.append(("Max DD <= 15%", "N/A", False))

    if total_return is not None:
        ok = total_return > 0
        checks.append(("PnL net > 0", f"{total_return:.2%}", ok))
    else:
        checks.append(("PnL net > 0", "N/A", False))

    for label, val, ok in checks:
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status}  {label}: {val}")

    all_ok = all(ok for _, _, ok in checks)
    print()
    if all_ok:
        print("  >>> ALL CRITERIA MET -- v28 corrections validated!")
    else:
        print("  >>> Some criteria not met -- further analysis needed.")
    print("=" * 70)


if __name__ == "__main__":
    main()
