#!/usr/bin/env python
"""EDGECORE Backtest v31c -- Strict Momentum Gate + Proven Quality Params.

v31  result: -2.53%, Sharpe -0.28, 63 trades, WR 52.4%, PF 0.80 (momentum=OFF)
v31b result: -5.14%, Sharpe -0.40, 65 trades, WR 53.9%, PF 0.74 (momentum gate too lenient)
v30b result: +5.25%, Sharpe 0.74, 25 trades, WR 60%, PF 2.63 (37 symbols, proven)

ROOT CAUSE ANALYSIS v31/v31b:
  - v31: momentum was DEAD CODE — all loosened filters, no quality gate
  - v31b: momentum gate too lenient (min_strength=0.30 at z=1.7 → raw=0.567,
    max penalty=0.30 → adjusted=0.267 barely < 0.30 → barely blocks anything)
  - Higher alloc in v31b (35%) AMPLIFIED losses on bad trades
  - The extra symbols (regional banks, biotech, discretionary) add noise pairs

v31c APPROACH: "Proven quality + wide funnel + strict filter"
  1. Keep 117 symbols (8x wider opportunity funnel)
  2. Use v30b-PROVEN parameters (entry_z=1.8, corr=0.65, HL=60, FDR=0.25)
  3. STRICT momentum gate: min_strength=1.0 → blocks ALL contra-momentum entries
     At min_strength=1.0, the floor == ceiling → any contra-momentum signal
     has adjusted_strength=1.0 <= 1.0 → BLOCKED. Only momentum-confirmed
     trades pass. Expected ~40-50% of entries filtered out.
  4. Allocation 40% (9 fixes from v31b: not too diluted, not too concentrated)
  5. Heat 3.0 (v30b proven — conservative risk)

Expected: ~30-45 high-conviction trades at WR >= 60%, PF > 2.0

Period: 2023-03-04 to 2026-03-04 (3 years).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

# == Universe (117 symbols — unchanged) ====================================
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
    # Technology
    "AAPL": "technology", "MSFT": "technology",
    "GOOGL": "technology", "META": "technology",
    "NVDA": "technology", "AMD": "technology",
    "INTC": "technology", "AVGO": "technology",
    "CRM": "technology", "ADBE": "technology",
    "MRVL": "technology", "ON": "technology",
    "MCHP": "technology", "QCOM": "technology",
    "TXN": "technology", "AMAT": "technology",
    "LRCX": "technology", "KLAC": "technology",
    # Financials
    "JPM": "financials", "BAC": "financials",
    "GS": "financials", "MS": "financials",
    "WFC": "financials", "C": "financials",
    "BLK": "financials", "SCHW": "financials",
    "USB": "financials", "PNC": "financials",
    "TFC": "financials", "RF": "financials",
    "CFG": "financials", "HBAN": "financials",
    "KEY": "financials",
    # Healthcare
    "JNJ": "healthcare", "PFE": "healthcare",
    "UNH": "healthcare", "MRK": "healthcare",
    "ABBV": "healthcare", "LLY": "healthcare",
    "TMO": "healthcare", "ABT": "healthcare",
    "GILD": "healthcare", "REGN": "healthcare",
    "BIIB": "healthcare", "VRTX": "healthcare",
    "BMY": "healthcare", "ZTS": "healthcare",
    "MCK": "healthcare",
    "CVS": "healthcare", "CI": "healthcare",
    "HUM": "healthcare", "ELV": "healthcare",
    "CNC": "healthcare",
    # Consumer Staples
    "KO": "consumer_staples", "PEP": "consumer_staples",
    "PG": "consumer_staples", "CL": "consumer_staples",
    "WMT": "consumer_staples", "COST": "consumer_staples",
    # Consumer Discretionary
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
    # Communication
    "CMCSA": "communication", "DIS": "communication",
    "NFLX": "communication", "FOXA": "communication",
    "VZ": "communication", "T": "communication",
    # Utilities
    "NEE": "utilities", "DUK": "utilities",
    "SO": "utilities", "D": "utilities",
    # REITs
    "PLD": "reits", "AMT": "reits",
    "SPG": "reits",
    # Sector ETFs
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

# == v31c Parameters: v30b-PROVEN + strict momentum gate ===================
ENTRY_Z = 1.8           # v30b proven (NOT 1.6 or 1.7)
EXIT_Z = 0.5            # Unchanged
ALLOC_PCT = 40.0        # Balanced (v30b=50% too concentrated, v31=25% too thin)
HEAT = 3.0              # v30b proven — conservative
STOP_PCT = 0.07         # 7% P&L stop
MIN_CORR = 0.65         # v30b proven quality level
MAX_HALF_LIFE = 60      # v30b proven
FDR_Q = 0.25            # v30b proven
REDISCOVERY = 2         # v30b proven
MIN_SPREAD = 0.30       # Unchanged
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

# Blacklist (v30b proven)
BL_MAX_LOSSES = 5
BL_COOLDOWN = 10

# Weekly gate (v30b proven)
WEEKLY_Z_GATE = 0.3

# Momentum: STRICT gate — block ALL contra-momentum entries
# min_strength=1.0 means: floor == ceiling, so ANY contra-momentum signal
# gets adjusted_strength=1.0 (floor), and gate checks <=1.0 → BLOCKED
MOM_LOOKBACK = 20
MOM_WEIGHT = 0.30
MOM_MIN_STRENGTH = 1.0   # STRICT: blocks all contra-momentum
MOM_MAX_BOOST = 1.0


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="EDGECORE Backtest v31c -- Strict Momentum + Proven Quality"
    )
    parser.add_argument("--start", default="2023-03-04")
    parser.add_argument("--end", default="2026-03-04")
    parser.add_argument("--capital", type=float, default=100_000)
    args = parser.parse_args()

    from config.settings import get_settings
    settings = get_settings()

    # Strategy: v30b-proven params
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

    # Adaptive regime (v30 proven)
    settings.regime.enabled = True
    settings.regime.ma_fast = 50
    settings.regime.ma_slow = 200
    settings.regime.vol_threshold = REGIME_VOL_THRESHOLD
    settings.regime.vol_window = 20
    settings.regime.neutral_band_pct = REGIME_NEUTRAL_BAND
    settings.regime.trend_favorable_sizing = TREND_FAVORABLE_SIZING
    settings.regime.neutral_sizing = NEUTRAL_SIZING

    # Momentum: STRICT gate — only momentum-confirmed trades pass
    settings.momentum.enabled = True
    settings.momentum.lookback = MOM_LOOKBACK
    settings.momentum.weight = MOM_WEIGHT
    settings.momentum.min_strength = MOM_MIN_STRENGTH  # 1.0 = strict block
    settings.momentum.max_boost = MOM_MAX_BOOST

    # Blacklist (v30b proven)
    settings.pair_blacklist.enabled = True
    settings.pair_blacklist.max_consecutive_losses = BL_MAX_LOSSES
    settings.pair_blacklist.cooldown_days = BL_COOLDOWN

    # Risk
    settings.risk.max_concurrent_positions = 12

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
    print("  EDGECORE BACKTEST v31c -- Strict Momentum + Proven Quality")
    print("=" * 70)
    print(f"  Symbols:      {len(SYMBOLS)} ({len(SYMBOLS)-1} trading + SPY)")
    print(f"  Pairs:        {n_intra} intra-sector")
    print(f"  Period:       {args.start} -> {args.end}")
    print(f"  Capital:      ${args.capital:,.0f}")
    print(f"  Alloc/pair:   {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%")
    print(f"  Z-score:      entry={ENTRY_Z}, exit={EXIT_Z}")
    print(f"  Corr min:     {MIN_CORR} | FDR q={FDR_Q} | HL max={MAX_HALF_LIFE}")
    print(f"  Weekly gate:  {WEEKLY_Z_GATE} | Rediscovery: {REDISCOVERY}")
    print("  --- v31c: Strict Momentum Gate ---")
    print(f"  Momentum:     STRICT (min_strength={MOM_MIN_STRENGTH})")
    print("  -> ALL contra-momentum entries BLOCKED")
    print("  -> Only momentum-confirmed trades pass")
    print(f"  Lookback={MOM_LOOKBACK} | weight={MOM_WEIGHT}")
    print("  Params from: v30b-proven baseline")
    print(f"  Alloc:        {ALLOC_PCT}% (v30b=50%, v31b=35%)")
    print(f"  Blacklist:    {BL_MAX_LOSSES}/{BL_COOLDOWN}d")
    print("=" * 70)
    print()

    t0 = time.time()
    print("[EDGECORE] Loading IBKR data + running backtest v31c...")
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
    print(f"\n[EDGECORE] Backtest v31c completed in {elapsed:.1f}s")
    print()
    summary = metrics.summary()
    print(summary)
    print(f"\nUniverse: {len(SYMBOLS)} symbols | Intra-sector pairs: {n_intra}")

    # Save
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    out_path = os.path.join(_ROOT, "results", "bt_results_v31c.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Backtest v31c -- Strict Momentum + Proven Quality\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Period: {args.start} -> {args.end}\n")
        f.write(f"Capital: ${args.capital:,.0f}\n")
        f.write(f"Symbols: {len(SYMBOLS)} | Pairs: {n_intra}\n")
        f.write(f"Alloc: {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%\n")
        f.write(f"entry_z={ENTRY_Z}, exit_z={EXIT_Z}, min_spread=${MIN_SPREAD}\n")
        f.write(f"max_HL={MAX_HALF_LIFE} | corr={MIN_CORR} | FDR q={FDR_Q}\n")
        f.write(f"Momentum: STRICT (min_strength={MOM_MIN_STRENGTH})\n")
        f.write("All contra-momentum entries BLOCKED\n")
        f.write(f"Adaptive regime: favorable={TREND_FAVORABLE_SIZING}, neutral={NEUTRAL_SIZING}\n")
        f.write(f"Rediscovery={REDISCOVERY} | weekly_z_gate={WEEKLY_Z_GATE}\n")
        f.write(f"Blacklist: {BL_MAX_LOSSES} losses / {BL_COOLDOWN}d cooldown\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write(summary)
    print(f"\n[Saved] {out_path}")

    # Performance check
    print("\n" + "=" * 70)
    print("  v31c PERFORMANCE CHECK")
    print("=" * 70)

    checks = []
    win_rate = getattr(metrics, 'win_rate', None)
    max_dd = getattr(metrics, 'max_drawdown_pct', None)
    total_return = getattr(metrics, 'total_return_pct', None)
    sharpe = getattr(metrics, 'sharpe_ratio', None)
    total_trades = getattr(metrics, 'total_trades', None)
    profit_factor = getattr(metrics, 'profit_factor', None)

    if total_trades is not None:
        checks.append(("Trades >= 30", f"{total_trades}", total_trades >= 30))
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
        print("  >>> ALL CRITERIA MET -- v31c VALIDATED!")
    else:
        print(f"  >>> {passed}/{len(checks)} criteria met.")
    print("=" * 70)

    # Comparison
    print("\n--- v31c vs v31b vs v31 vs v30b ---")
    print("  v30b: +5.25% | Sharpe 0.74 | 25 trades | WR 60.0% | PF 2.63 | 37 sym")
    print("  v31:  -2.53% | Sharpe -0.28 | 63 trades | WR 52.4% | PF 0.80 | 117 sym, mom=OFF")
    print("  v31b: -5.14% | Sharpe -0.40 | 65 trades | WR 53.9% | PF 0.74 | 117 sym, mom=lenient")
    if total_return is not None:
        pnl = args.capital * total_return
        print(f"  v31c: {total_return:+.2%} | Sharpe {sharpe:.2f} | {total_trades} trades | WR {win_rate:.1%} | PF {profit_factor:.2f} | 117 sym, mom=STRICT")
        print(f"  PnL:  ${pnl:,.0f}")


if __name__ == "__main__":
    main()
