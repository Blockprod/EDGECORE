#!/usr/bin/env python
"""EDGECORE Backtest v31 -- Universe Expansion + Momentum + Combiner + Aggressive Params.

v30b result: +5.25%, Sharpe 0.74, 25 trades, WR 60%, Max DD -2.63%.
Problem: Only 25 trades with 37 symbols -- not enough alpha harvest.

v31 APPROACH: Scale up on every axis while keeping adaptive regime:
  1. Universe: 117 symbols across 10 sectors + 15 ETFs (was 37)
  2. Momentum overlay: relative strength confirms/reduces z-score signals
  3. Signal combiner: weighted ensemble zscore(0.70) + momentum(0.30)
  4. entry_z = 1.6 (was 1.8) -- more signal triggers
  5. Allocation 25%/pair (was 50%) -- diversify across more pairs
  6. Heat 4.0 (was 3.0) -- 20 concurrent positions possible
  7. max_half_life = 70 (was 60) -- broader pair universe
  8. min_corr = 0.60 (was 0.65) -- more pairs qualify
  9. FDR q = 0.30 (was 0.25) -- more pairs survive FDR
 10. Weekly gate 0.2 (was 0.3) -- almost all entries pass
 11. pair_rediscovery = 1 (was 2) -- scan every bar
 12. Blacklist 6 losses / 7d cooldown -- very lenient recycling
 13. max_positions = 20 (was 10) -- more concurrent trades

Period: 2023-03-04 to 2026-03-04 (3 years).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

# == Universe (117 symbols) ================================================
SYMBOLS = [
    "SPY",
    # Technology (Mega Cap)
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "INTC", "AVGO",
    "CRM", "ADBE",
    # Technology / Semiconductors (Mid-Cap)
    "MRVL", "ON", "MCHP", "QCOM", "TXN", "AMAT", "LRCX", "KLAC",
    # Financials (Mega Cap)
    "JPM", "BAC", "GS", "MS", "WFC", "C", "BLK", "SCHW",
    # Financials - Regional Banks
    "USB", "PNC", "TFC", "RF", "CFG", "HBAN", "KEY",
    # Healthcare / Pharma (Mega Cap)
    "JNJ", "PFE", "UNH", "MRK", "ABBV", "LLY", "TMO", "ABT",
    # Healthcare / Biotech (Mid-Cap)
    "GILD", "REGN", "BIIB", "VRTX", "BMY", "ZTS", "MCK",
    # Healthcare Services
    "CVS", "CI", "HUM", "ELV", "CNC",
    # Consumer Staples
    "KO", "PEP", "PG", "CL", "WMT", "COST",
    # Consumer Discretionary / Retail
    "TGT", "LOW", "HD", "ROST", "TJX", "DLTR", "DG",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG", "VLO", "MPC", "PSX", "DVN",
    "HAL", "BKR",
    # Industrials
    "CAT", "DE", "HON", "GE", "RTX", "LMT", "MMM", "EMR", "ITW",
    "ROK", "CMI", "PH",
    # Communication / Media
    "CMCSA", "DIS", "NFLX", "FOXA", "VZ", "T",
    # Utilities
    "NEE", "DUK", "SO", "D",
    # REITs
    "PLD", "AMT", "SPG",
    # --- Sector ETFs ---
    "XLK", "SMH",       # Technology
    "XLF", "KRE",       # Financials
    "XLE",              # Energy
    "XLV", "XBI", "IBB",# Healthcare
    "XLI",              # Industrials
    "XLU",              # Utilities
    "XLP",              # Consumer Staples
    "XLB",              # Materials
    "XLC",              # Communication
    "XLRE", "IYR",      # REITs
]

SECTOR_MAP = {
    # Technology (Mega Cap)
    "AAPL": "technology", "MSFT": "technology",
    "GOOGL": "technology", "META": "technology",
    "NVDA": "technology", "AMD": "technology",
    "INTC": "technology", "AVGO": "technology",
    "CRM": "technology", "ADBE": "technology",
    # Technology / Semiconductors (Mid-Cap)
    "MRVL": "technology", "ON": "technology",
    "MCHP": "technology", "QCOM": "technology",
    "TXN": "technology", "AMAT": "technology",
    "LRCX": "technology", "KLAC": "technology",
    # Financials (Mega Cap)
    "JPM": "financials", "BAC": "financials",
    "GS": "financials", "MS": "financials",
    "WFC": "financials", "C": "financials",
    "BLK": "financials", "SCHW": "financials",
    # Financials - Regional Banks
    "USB": "financials", "PNC": "financials",
    "TFC": "financials", "RF": "financials",
    "CFG": "financials", "HBAN": "financials",
    "KEY": "financials",
    # Healthcare / Pharma (Mega Cap)
    "JNJ": "healthcare", "PFE": "healthcare",
    "UNH": "healthcare", "MRK": "healthcare",
    "ABBV": "healthcare", "LLY": "healthcare",
    "TMO": "healthcare", "ABT": "healthcare",
    # Healthcare / Biotech (Mid-Cap)
    "GILD": "healthcare", "REGN": "healthcare",
    "BIIB": "healthcare", "VRTX": "healthcare",
    "BMY": "healthcare", "ZTS": "healthcare",
    "MCK": "healthcare",
    # Healthcare Services
    "CVS": "healthcare", "CI": "healthcare",
    "HUM": "healthcare", "ELV": "healthcare",
    "CNC": "healthcare",
    # Consumer Staples
    "KO": "consumer_staples", "PEP": "consumer_staples",
    "PG": "consumer_staples", "CL": "consumer_staples",
    "WMT": "consumer_staples", "COST": "consumer_staples",
    # Consumer Discretionary / Retail
    "TGT": "consumer_discretionary", "LOW": "consumer_discretionary",
    "HD": "consumer_discretionary", "ROST": "consumer_discretionary",
    "TJX": "consumer_discretionary", "DLTR": "consumer_discretionary",
    "DG": "consumer_discretionary",
    # Energy
    "XOM": "energy", "CVX": "energy",
    "COP": "energy", "SLB": "energy",
    "EOG": "energy", "VLO": "energy",
    "MPC": "energy", "PSX": "energy",
    "DVN": "energy", "HAL": "energy",
    "BKR": "energy",
    # Industrials
    "CAT": "industrials", "DE": "industrials",
    "HON": "industrials", "GE": "industrials",
    "RTX": "industrials", "LMT": "industrials",
    "MMM": "industrials", "EMR": "industrials",
    "ITW": "industrials", "ROK": "industrials",
    "CMI": "industrials", "PH": "industrials",
    # Communication / Media
    "CMCSA": "communication", "DIS": "communication",
    "NFLX": "communication", "FOXA": "communication",
    "VZ": "communication", "T": "communication",
    # Utilities
    "NEE": "utilities", "DUK": "utilities",
    "SO": "utilities", "D": "utilities",
    # REITs
    "PLD": "reits", "AMT": "reits",
    "SPG": "reits",
    # --- Sector ETFs ---
    "XLK": "technology", "SMH": "technology",
    "XLF": "financials", "KRE": "financials",
    "XLE": "energy",
    "XLV": "healthcare", "XBI": "healthcare", "IBB": "healthcare",
    "XLI": "industrials",
    "XLU": "utilities",
    "XLP": "consumer_staples",
    "XLB": "materials",
    "XLC": "communication",
    "XLRE": "reits", "IYR": "reits",
}

# == v31 Parameters ========================================================
ENTRY_Z = 1.6           # Aggressive (was 1.8 v30b)
EXIT_Z = 0.5            # Unchanged
ALLOC_PCT = 25.0        # 25% per pair -- diversified (was 50%)
HEAT = 4.0              # 400% heat (was 300%)
STOP_PCT = 0.07         # 7% P&L stop
MIN_CORR = 0.60         # Looser (was 0.65)
MAX_HALF_LIFE = 70      # Broader (was 60)
FDR_Q = 0.30            # More lenient (was 0.25)
REDISCOVERY = 1         # Scan every bar (was 2)
MIN_SPREAD = 0.30       # Unchanged from v30b
Z_SCORE_STOP = 3.0      # Unchanged

# Adaptive regime (same v30 logic)
TREND_FAVORABLE_SIZING = 1.0
NEUTRAL_SIZING = 0.70
REGIME_NEUTRAL_BAND = 0.02
REGIME_VOL_THRESHOLD = 0.18

# Legacy (OFF)
REGIME_DIRECTIONAL = False
TREND_LONG_SIZING = 0.75
SHORT_MULT = 0.50
DISABLE_SHORTS_BULL = False

# Time stop
TIME_STOP_MULT = 2.0
MAX_HOLD_DAYS = 40

# Blacklist (very lenient)
BL_MAX_LOSSES = 6       # Was 5
BL_COOLDOWN = 7          # Fast recycling (was 10)

# Weekly gate
WEEKLY_Z_GATE = 0.2     # Very low (was 0.3)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="EDGECORE Backtest v31 -- Universe + Momentum + Combiner"
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

    # v31 Momentum overlay
    settings.momentum.enabled = True
    settings.momentum.lookback = 20
    settings.momentum.weight = 0.30
    settings.momentum.min_strength = 0.30
    settings.momentum.max_boost = 1.0

    # v31 Signal combiner
    settings.signal_combiner.enabled = True
    settings.signal_combiner.zscore_weight = 0.70
    settings.signal_combiner.momentum_weight = 0.30
    settings.signal_combiner.entry_threshold = 0.6
    settings.signal_combiner.exit_threshold = 0.2

    # Blacklist
    settings.pair_blacklist.enabled = True
    settings.pair_blacklist.max_consecutive_losses = BL_MAX_LOSSES
    settings.pair_blacklist.cooldown_days = BL_COOLDOWN

    # Max concurrent positions
    settings.risk.max_concurrent_positions = 20

    # Time stop
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
    print("  EDGECORE BACKTEST v31 -- Universe + Momentum + Combiner")
    print("=" * 70)
    print(f"  Symbols:      {len(SYMBOLS)} ({len(SYMBOLS)-1} trading + SPY)")
    print(f"  Pairs:        {n_intra} intra-sector")
    print(f"  Period:       {args.start} -> {args.end}")
    print(f"  Capital:      ${args.capital:,.0f}")
    print(f"  Alloc/pair:   {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%")
    print(f"  Stop:         {STOP_PCT*100:.0f}% | z_stop={Z_SCORE_STOP}")
    print(f"  Z-score:      entry={ENTRY_Z}, exit={EXIT_Z}")
    print(f"  Min spread:   ${MIN_SPREAD:.2f}")
    print(f"  Half-life:    max={MAX_HALF_LIFE}d | Time stop={TIME_STOP_MULT}x HL (cap {MAX_HOLD_DAYS}d)")
    print(f"  Corr min:     {MIN_CORR} | FDR q={FDR_Q}")
    print(f"  Weekly gate:  |z| >= {WEEKLY_Z_GATE}")
    print("  --- v31 New Features ---")
    print(f"  Universe:     117 symbols, 10 sectors + 15 ETFs")
    print(f"  Momentum:     lookback=20, weight=0.30, min_str=0.30")
    print(f"  Combiner:     zscore(0.70) + momentum(0.30)")
    print(f"  Entry z:      {ENTRY_Z} (was 1.8)")
    print(f"  Alloc:        {ALLOC_PCT}% (was 50%)")
    print(f"  Heat:         {HEAT*100:.0f}% (was 300%)")
    print(f"  Min corr:     {MIN_CORR} (was 0.65)")
    print(f"  Half-life:    {MAX_HALF_LIFE}d (was 60d)")
    print(f"  FDR q:        {FDR_Q} (was 0.25)")
    print(f"  Weekly gate:  {WEEKLY_Z_GATE} (was 0.3)")
    print(f"  Rediscovery:  every {REDISCOVERY} bar (was 2)")
    print(f"  Blacklist:    {BL_MAX_LOSSES} losses / {BL_COOLDOWN}d cooldown")
    print(f"  Max positions: 20 (was 10)")
    print(f"  Favorable sz: {TREND_FAVORABLE_SIZING:.0%}")
    print(f"  Neutral sz:   {NEUTRAL_SIZING:.0%}")
    print("=" * 70)
    print()

    t0 = time.time()
    print("[EDGECORE] Loading IBKR data + running backtest v31...")
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
    print(f"\n[EDGECORE] Backtest v31 completed in {elapsed:.1f}s")
    print()
    summary = metrics.summary()
    print(summary)
    print(f"\nUniverse: {len(SYMBOLS)} symbols | Intra-sector pairs: {n_intra}")

    # Save
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    out_path = os.path.join(_ROOT, "results", "bt_results_v31.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Backtest v31 -- Universe + Momentum + Combiner\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Period: {args.start} -> {args.end}\n")
        f.write(f"Capital: ${args.capital:,.0f}\n")
        f.write(f"Symbols: {len(SYMBOLS)} | Pairs: {n_intra}\n")
        f.write(f"Alloc: {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%\n")
        f.write(f"entry_z={ENTRY_Z}, exit_z={EXIT_Z}, min_spread=${MIN_SPREAD}\n")
        f.write(f"max_HL={MAX_HALF_LIFE} | corr={MIN_CORR} | FDR q={FDR_Q}\n")
        f.write(f"Momentum: lookback=20, weight=0.30\n")
        f.write(f"Combiner: zscore(0.70) + momentum(0.30)\n")
        f.write(f"Adaptive regime: favorable={TREND_FAVORABLE_SIZING}, neutral={NEUTRAL_SIZING}\n")
        f.write(f"Rediscovery={REDISCOVERY} | weekly_z_gate={WEEKLY_Z_GATE}\n")
        f.write(f"Blacklist: {BL_MAX_LOSSES} losses / {BL_COOLDOWN}d cooldown\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write(summary)
    print(f"\n[Saved] {out_path}")

    # Performance check
    print("\n" + "=" * 70)
    print("  v31 PERFORMANCE CHECK")
    print("=" * 70)

    checks = []
    win_rate = getattr(metrics, 'win_rate', None)
    max_dd = getattr(metrics, 'max_drawdown_pct', None)
    total_return = getattr(metrics, 'total_return_pct', None)
    sharpe = getattr(metrics, 'sharpe_ratio', None)
    total_trades = getattr(metrics, 'total_trades', None)
    profit_factor = getattr(metrics, 'profit_factor', None)

    if total_trades is not None:
        checks.append(("Trades >= 60", f"{total_trades}", total_trades >= 60))
    if total_return is not None:
        checks.append(("Return > +8%", f"{total_return:+.2%}", total_return > 0.08))
    if sharpe is not None:
        checks.append(("Sharpe > 0.9", f"{sharpe:.2f}", sharpe > 0.9))
    if win_rate is not None:
        checks.append(("Win Rate >= 50%", f"{win_rate:.1%}", win_rate >= 0.50))
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
        print("  >>> ALL CRITERIA MET -- v31 VALIDATED!")
    else:
        print(f"  >>> {passed}/{len(checks)} criteria met.")
    print("=" * 70)

    # Comparison
    print("\n--- v31 vs v30b vs v30 ---")
    print("  v30:  +2.09% | Sharpe 0.57 | 19 trades | WR 47.4% | PF 2.02")
    print("  v30b: +5.25% | Sharpe 0.74 | 25 trades | WR 60.0% | PF 2.63")
    if total_return is not None:
        pnl = args.capital * total_return
        print(f"  v31:  {total_return:+.2%} | Sharpe {sharpe:.2f} | {total_trades} trades | WR {win_rate:.1%} | PF {profit_factor:.2f}")
        print(f"  PnL:  ${pnl:,.0f}")


if __name__ == "__main__":
    main()
