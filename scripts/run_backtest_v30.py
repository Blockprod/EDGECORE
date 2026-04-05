#!/usr/bin/env python
"""EDGECORE Backtest v30 -- Adaptive Bidirectional Regime Filter.

v29 result: +2.08%, Sharpe +0.64, 21 trades, 52.4% WR.
But only exploited BULL trends (longs allowed, shorts blocked).
In bear markets v29 would block longs AND shorts = dead capital.

v30 KEY INSIGHT: The regime filter should be SYMMETRIC / ADAPTIVE.
The trend direction tells us WHICH SIDE has a mean-reversion tailwind:
  - BULL TRENDING: longs ride the updraft (buy the dip works)  -> longs only
  - BEAR TRENDING: shorts ride the downdraft (sell the rally)  -> shorts only
  - MEAN REVERTING: high vol = volatility clustering, both sides profitable
  - NEUTRAL: near crossover, uncertain direction -> both sides at reduced sizing

Four-state detection on SPY (MA50 vs MA200 + realized vol):
  1. Vol > threshold              -> MEAN_REVERTING  (both 100%)
  2. MA50 >> MA200  + low vol     -> BULL_TRENDING   (longs at 80%, shorts 0%)
  3. MA50 << MA200  + low vol     -> BEAR_TRENDING   (shorts at 80%, longs 0%)
  4. |spread| < neutral_band      -> NEUTRAL         (both at 65%)

Optimisations over v29:
  - Adaptive bidirectional regime (NEW) -- profits in BOTH bull AND bear markets
  - Allocation 40%/pair (was 30%) -- more capital per winner
  - Heat 250% (was 200%) -- moderate leverage to capture more setups
  - Max half-life 50 (was 45) -- slightly more pairs qualify
  - Position stop 7% (was 5%) -- avoid premature stops
  - Time stop 2.0x HL (was 1.5x) -- give reverting pairs more time
  - Max holding 40d (was 30d) -- accommodate slower-reverting pairs
  - Blacklist 4 losses / 15d cooldown -- tighter blacklist on repeat losers
  - trend_favorable_sizing 0.85 (default 0.80) -- stronger conviction trades
  - neutral_sizing 0.60 -- cautious in uncertain direction

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
SYMBOLS = [
    "SPY",  # Index -- required for market regime filter
    # Technology
    "AAPL",
    "MSFT",
    "GOOGL",
    "META",
    "NVDA",
    "AMD",
    "AVGO",
    # Financials (strong mean-reversion sector)
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
    # Consumer Staples (defensive / low-vol -- good MR)
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
    # Utilities (best MR sector)
    "NEE",
    "DUK",
    "SO",
    # Healthcare (added for v30 -- better diversification)
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

# == v30 Optimised Parameters =============================================
ENTRY_Z = 2.0  # Proven threshold (unchanged)
EXIT_Z = 0.5  # Take profit at 0.5 sigma (unchanged)
ALLOC_PCT = 40.0  # Per-pair allocation (was 30%) -- more capital per winner
HEAT = 2.5  # Max portfolio heat 250% (was 200%) -- more setups
STOP_PCT = 0.07  # 7% P&L stop per position (was 5%) -- avoid premature stops
MIN_CORR = 0.70  # High quality pairs only (unchanged)
MAX_HALF_LIFE = 50  # Slightly broader (was 45) -- more pairs qualify
FDR_Q = 0.20  # BH-FDR threshold (unchanged)
REDISCOVERY = 3  # Pair rediscovery interval (bars, unchanged)
MIN_SPREAD = 0.50  # Min absolute spread ($, unchanged)
Z_SCORE_STOP = 3.0  # Z-score stop-loss (unchanged)

# v30: Adaptive bidirectional regime
TREND_FAVORABLE_SIZING = 0.85  # Favorable side gets 85% sizing in trends
NEUTRAL_SIZING = 0.60  # Both sides at 60% in NEUTRAL (cautious)
REGIME_NEUTRAL_BAND = 0.02  # MA spread band for NEUTRAL detection
REGIME_VOL_THRESHOLD = 0.18  # Vol threshold for MEAN_REVERTING

# Legacy directional filter (now superseded by adaptive regime)
REGIME_DIRECTIONAL = False  # OFF -- v30 adaptive handles this natively
TREND_LONG_SIZING = 0.75  # Legacy, unused by v30 regime
SHORT_MULT = 0.50  # Legacy, unused by v30 adaptive gate
DISABLE_SHORTS_BULL = False  # Legacy, v30 regime gate handles gating

# Time stop
TIME_STOP_MULT = 2.0  # 2.0x half-life (was 1.5x) -- give MR pairs time
MAX_HOLD_DAYS = 40  # Cap at 40 days (was 30)

# Blacklist
BL_MAX_LOSSES = 4  # Blacklist after 4 consecutive losses (was 3)
BL_COOLDOWN = 15  # 15-day cooldown (was 20) -- faster recycling

# Weekly gate
WEEKLY_Z_GATE = 0.5  # Lower weekly z gate (unchanged)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="EDGECORE Backtest v30 -- Adaptive Bidirectional Regime")
    parser.add_argument("--start", default="2023-03-04")
    parser.add_argument("--end", default="2026-03-04")
    parser.add_argument("--capital", type=float, default=100_000)
    args = parser.parse_args()

    # == Configure settings (Singleton) ====================================
    from config.settings import get_settings

    settings = get_settings()

    # Strategy core
    settings.strategy.lookback_window = 120
    settings.strategy.additional_lookback_windows = [63]
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

    # Legacy directional filter (OFF -- v30 adaptive regime handles it)
    settings.strategy.regime_directional_filter = REGIME_DIRECTIONAL
    settings.strategy.trend_long_sizing = TREND_LONG_SIZING
    settings.strategy.disable_shorts_in_bull_trend = DISABLE_SHORTS_BULL
    settings.strategy.short_sizing_multiplier = SHORT_MULT

    # v30: Adaptive bidirectional regime filter
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

    # FDR level
    if hasattr(settings.strategy, "fdr_q_level"):
        settings.strategy.fdr_q_level = FDR_Q

    runner = BacktestRunner()
    runner.config.initial_capital = args.capital

    n_intra = sum(
        1 for i, s1 in enumerate(SYMBOLS) for s2 in SYMBOLS[i + 1 :] if SECTOR_MAP.get(s1) == SECTOR_MAP.get(s2)
    )

    print("=" * 70)
    print("  EDGECORE BACKTEST v30 -- Adaptive Bidirectional Regime")
    print("=" * 70)
    print(f"  Symbols:      {len(SYMBOLS)} ({len(SYMBOLS) - 1} trading + SPY regime ref)")
    print(f"  Pairs:        {n_intra} intra-sector")
    print(f"  Period:       {args.start} -> {args.end} (3 years rolling)")
    print(f"  Capital:      ${args.capital:,.0f}")
    print(f"  Alloc/pair:   {ALLOC_PCT}% | Heat: {HEAT * 100:.0f}%")
    print(f"  Stop:         {STOP_PCT * 100:.0f}% | z_stop={Z_SCORE_STOP}")
    print(f"  Z-score:      entry={ENTRY_Z}, exit={EXIT_Z}")
    print(f"  Min spread:   ${MIN_SPREAD:.2f}")
    print(f"  Half-life:    max={MAX_HALF_LIFE}d | Time stop={TIME_STOP_MULT}x HL (cap {MAX_HOLD_DAYS}d)")
    print(f"  Corr min:     {MIN_CORR} | FDR q={FDR_Q}")
    print(f"  Weekly gate:  |z| >= {WEEKLY_Z_GATE}")
    print("  --- v30 Key Changes ---")
    print("  [NEW] Adaptive regime: 4-state (BULL/BEAR/MR/NEUTRAL)")
    print(f"  [NEW] Trend favorable sizing: {TREND_FAVORABLE_SIZING:.0%}")
    print(f"  [NEW] Neutral sizing: {NEUTRAL_SIZING:.0%}")
    print(f"  [v30] Alloc: {ALLOC_PCT}% (was 30%)")
    print(f"  [v30] Heat: {HEAT * 100:.0f}% (was 200%)")
    print(f"  [v30] Stop: {STOP_PCT * 100:.0f}% (was 5%)")
    print(f"  [v30] Time stop: {TIME_STOP_MULT}x HL / cap {MAX_HOLD_DAYS}d")
    print(f"  [v30] Blacklist: {BL_MAX_LOSSES} losses -> {BL_COOLDOWN}d cooldown")
    print("  [v30] Healthcare sector added (+5 symbols)")
    print("=" * 70)
    print()

    t0 = time.time()
    print("[EDGECORE] Loading IBKR data + running backtest v30...")
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
    print(f"\n[EDGECORE] Backtest v30 completed in {elapsed:.1f}s")
    print()
    summary = metrics.summary()
    print(summary)
    print(f"\nUniverse: {len(SYMBOLS)} symbols | Intra-sector pairs: {n_intra}")

    # == Save results ======================================================
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    out_path = os.path.join(_ROOT, "results", "bt_results_v30.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Backtest v30 -- Adaptive Bidirectional Regime\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Period: {args.start} -> {args.end}\n")
        f.write(f"Capital: ${args.capital:,.0f}\n")
        f.write(f"Alloc: {ALLOC_PCT}% | Heat: {HEAT * 100:.0f}%\n")
        f.write(f"Z-score: entry={ENTRY_Z}, exit={EXIT_Z} | min_spread=${MIN_SPREAD}\n")
        f.write(f"Half-life max={MAX_HALF_LIFE} | Time stop={TIME_STOP_MULT}x HL (cap {MAX_HOLD_DAYS}d)\n")
        f.write(f"Adaptive regime: 4-state (favorable_sizing={TREND_FAVORABLE_SIZING}, neutral={NEUTRAL_SIZING})\n")
        f.write(f"Blacklist: {BL_MAX_LOSSES} losses / {BL_COOLDOWN}d cooldown\n")
        f.write(f"Weekly z gate: {WEEKLY_Z_GATE}\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write(summary)
    print(f"\n[Saved] {out_path}")

    # == Success criteria check ============================================
    print("\n" + "=" * 70)
    print("  v30 PERFORMANCE CHECK")
    print("=" * 70)

    checks = []
    win_rate = getattr(metrics, "win_rate", None)
    max_dd = getattr(metrics, "max_drawdown_pct", None)
    total_return = getattr(metrics, "total_return_pct", None)
    sharpe = getattr(metrics, "sharpe_ratio", None)
    total_trades = getattr(metrics, "total_trades", None)
    profit_factor = getattr(metrics, "profit_factor", None)

    if total_trades is not None:
        checks.append(("Total trades >= 15", f"{total_trades}", total_trades >= 15))

    if win_rate is not None:
        checks.append(("Win rate >= 45%", f"{win_rate:.1%}", win_rate >= 0.45))

    if max_dd is not None:
        dd_val = abs(max_dd)
        checks.append(("Max DD <= 10%", f"{dd_val:.1%}", dd_val <= 0.10))

    if total_return is not None:
        checks.append(("Return > +3%", f"{total_return:.2%}", total_return > 0.03))

    if sharpe is not None:
        checks.append(("Sharpe > +0.5", f"{sharpe:.2f}", sharpe > 0.5))

    if profit_factor is not None:
        checks.append(("Profit Factor > 1.5", f"{profit_factor:.2f}", profit_factor > 1.5))

    for label, val, ok in checks:
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status}  {label}: {val}")

    all_ok = all(ok for _, _, ok in checks)
    print()
    if all_ok:
        print("  >>> ALL CRITERIA MET -- v30 strategy VALIDATED!")
    else:
        passed = sum(1 for _, _, ok in checks if ok)
        print(f"  >>> {passed}/{len(checks)} criteria met.")
    print("=" * 70)

    # == Detailed trade analysis ===========================================
    print("\n--- Trade Breakdown ---")
    if total_trades is not None and total_trades > 0:
        if win_rate is not None:
            wins = int(round(total_trades * win_rate))
            losses = total_trades - wins
            print(f"  Wins: {wins} | Losses: {losses}")
        print(f"  Trades: {total_trades}")
    if total_return is not None:
        pnl_dollar = args.capital * total_return
        print(f"  PnL: ${pnl_dollar:,.0f} ({total_return:+.2%})")
    if total_return is not None and total_return > 0:
        print("  >> Strategy is PROFITABLE on this window.")
    elif total_return is not None:
        print(f"  >> Net return: {total_return:.2%} -- review parameters.")

    # v30 vs v29 comparison
    print("\n--- v30 vs v29 Comparison ---")
    v29_return = 0.0208
    v29_sharpe = 0.64
    v29_trades = 21
    v29_wr = 0.524
    print(f"  v29: +{v29_return:.2%} | Sharpe {v29_sharpe} | {v29_trades} trades | WR {v29_wr:.1%}")
    if total_return is not None and sharpe is not None:
        print(f"  v30: {total_return:+.2%} | Sharpe {sharpe:.2f} | {total_trades} trades | WR {win_rate:.1%}")
        delta_ret = total_return - v29_return
        delta_sharpe = sharpe - v29_sharpe
        print(
            f"  Delta: Return {delta_ret:+.2%} | Sharpe {delta_sharpe:+.2f} | Trades {(total_trades or 0) - v29_trades:+d}"
        )


if __name__ == "__main__":
    main()
