#!/usr/bin/env python
"""EDGECORE Backtest v31d -- Curated Universe + Strict Momentum + Proven Params.

ITERATION HISTORY:
  v30b: +5.25%, Sharpe 0.74, 25 trades, WR 60%,  PF 2.63, DD -2.63% (37 sym)
  v31:  -2.53%, Sharpe -0.28, 63 trades, WR 52%,  PF 0.80, DD -7.62% (117 sym, mom=OFF)
  v31b: -5.14%, Sharpe -0.40, 65 trades, WR 54%,  PF 0.74, DD -11.8% (117 sym, mom=lenient)
  v31c: -1.63%, Sharpe -0.14, 47 trades, WR 59.6%, PF 0.87, DD -7.86% (117 sym, mom=STRICT)

LESSONS LEARNED:
  1. Momentum overlay must be ACTIVE in backtest path (fixed in v31b+)
  2. Strict momentum gate (block contra-momentum) recovers WR to ~60%
  3. But avg_loss($661) >> avg_win($390) ÔÇö noisy sectors add large-loss pairs
  4. BH-FDR severity: 20 tech symbols = 190 pair tests, threshold much tighter
     than v30b's 7 symbols = 21 tests. Quality pairs get FDR-killed.

v31d APPROACH: "Curated quality universe"
  - REMOVE noisy sectors: regional banks, biotech, healthcare services,
    communication/media, consumer discretionary, REITs
  - KEEP mean-reverting sectors: technology(18), financials mega(8),
    healthcare mega(7), staples(6), energy(11), industrials(12), utilities(4)
  - Sector ETFs for covered sectors only (7 ETFs)
  - Total: 74 symbols ÔåÆ ~420 intra-sector pairs (vs 806 in v31c)
  - BH-FDR pressure reduced per sector
  - v30b-proven parameters + strict momentum gate
  - Allocation 50% = v30b level (proven sizing for quality trades)

Period: 2023-03-04 to 2026-03-04 (3 years).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

# == Curated Universe (74 symbols) =========================================
# Only sectors with proven mean-reverting pair behavior
SYMBOLS = [
    "SPY",
    # Technology (Mega Cap) ÔÇö tight structural relationships
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "INTC", "AVGO",
    "CRM", "ADBE",
    # Technology (Semiconductors) ÔÇö commodity-cycle driven
    "MRVL", "ON", "MCHP", "QCOM", "TXN", "AMAT", "LRCX", "KLAC",
    # Financials (Mega Cap) ÔÇö rate-driven, similar exposures
    "JPM", "BAC", "GS", "MS", "WFC", "C", "BLK", "SCHW",
    # Healthcare (Mega Cap Pharma Only) ÔÇö stable, no biotech noise
    "JNJ", "UNH", "MRK", "ABBV", "LLY", "TMO", "ABT",
    # Consumer Staples ÔÇö defensive, stable relationships
    "KO", "PEP", "PG", "CL", "WMT", "COST",
    # Energy ÔÇö commodity-driven, tight correlations
    "XOM", "CVX", "COP", "SLB", "EOG", "VLO", "MPC", "PSX", "DVN",
    "HAL", "BKR",
    # Industrials ÔÇö cyclical, similar macro exposure
    "CAT", "DE", "HON", "GE", "RTX", "LMT", "MMM", "EMR", "ITW",
    "ROK", "CMI", "PH",
    # Utilities ÔÇö rate-sensitive, stable pairs
    "NEE", "DUK", "SO", "D",
    # Sector ETFs (covered sectors only)
    "XLK", "SMH",    # Technology
    "XLF",           # Financials
    "XLE",           # Energy
    "XLI",           # Industrials
    "XLU",           # Utilities
    "XLP",           # Consumer Staples
]

# REMOVED from v31 universe (40 noisy symbols):
# Regional banks (USB,PNC,TFC,RF,CFG,HBAN,KEY) ÔÇö post-SVB structural divergence
# Biotech (GILD,REGN,BIIB,VRTX,BMY,ZTS,MCK) ÔÇö binary events, not mean-reverting
# Healthcare services (CVS,CI,HUM,ELV,CNC) ÔÇö regulation/M&A driven
# Communication (CMCSA,DIS,NFLX,FOXA,VZ,T) ÔÇö secular cord-cutting trends
# Consumer discretionary (TGT,LOW,HD,ROST,TJX,DLTR,DG) ÔÇö post-COVID structural
# REITs (PLD,AMT,SPG) ÔÇö rate-sensitive, only 3 symbols = trivial FDR
# PFE ÔÇö patent cliff (COVID vaccine revenue -90%)
# Sector ETFs for removed sectors (XLV,XBI,IBB,XLB,XLC,XLRE,IYR,KRE)

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
    "XLK": "technology", "SMH": "technology",
    # Financials (Mega Cap only)
    "JPM": "financials", "BAC": "financials",
    "GS": "financials", "MS": "financials",
    "WFC": "financials", "C": "financials",
    "BLK": "financials", "SCHW": "financials",
    "XLF": "financials",
    # Healthcare (Mega Cap Pharma only)
    "JNJ": "healthcare", "UNH": "healthcare",
    "MRK": "healthcare", "ABBV": "healthcare",
    "LLY": "healthcare", "TMO": "healthcare",
    "ABT": "healthcare",
    # Consumer Staples
    "KO": "consumer_staples", "PEP": "consumer_staples",
    "PG": "consumer_staples", "CL": "consumer_staples",
    "WMT": "consumer_staples", "COST": "consumer_staples",
    "XLP": "consumer_staples",
    # Energy
    "XOM": "energy", "CVX": "energy",
    "COP": "energy", "SLB": "energy",
    "EOG": "energy", "VLO": "energy",
    "MPC": "energy", "PSX": "energy",
    "DVN": "energy", "HAL": "energy",
    "BKR": "energy", "XLE": "energy",
    # Industrials
    "CAT": "industrials", "DE": "industrials",
    "HON": "industrials", "GE": "industrials",
    "RTX": "industrials", "LMT": "industrials",
    "MMM": "industrials", "EMR": "industrials",
    "ITW": "industrials", "ROK": "industrials",
    "CMI": "industrials", "PH": "industrials",
    "XLI": "industrials",
    # Utilities
    "NEE": "utilities", "DUK": "utilities",
    "SO": "utilities", "D": "utilities",
    "XLU": "utilities",
}

# == v31d Parameters: v30b-PROVEN + curated universe + strict momentum =====
ENTRY_Z = 1.8           # v30b proven
EXIT_Z = 0.5            # Unchanged
ALLOC_PCT = 50.0        # v30b proven ÔÇö full conviction sizing
HEAT = 3.0              # v30b proven
STOP_PCT = 0.07         # 7% P&L stop
MIN_CORR = 0.65         # v30b proven
MAX_HALF_LIFE = 60      # v30b proven
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

# Time stop
TIME_STOP_MULT = 2.0
MAX_HOLD_DAYS = 40

# Blacklist (v30b proven)
BL_MAX_LOSSES = 5
BL_COOLDOWN = 10

# Weekly gate (v30b proven)
WEEKLY_Z_GATE = 0.3

# Momentum: STRICT gate
MOM_LOOKBACK = 20
MOM_WEIGHT = 0.30
MOM_MIN_STRENGTH = 1.0   # Blocks ALL contra-momentum
MOM_MAX_BOOST = 1.0


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="EDGECORE Backtest v31d -- Curated Universe + Strict Momentum"
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

    # Momentum: STRICT gate
    settings.momentum.enabled = True
    settings.momentum.lookback = MOM_LOOKBACK
    settings.momentum.weight = MOM_WEIGHT
    settings.momentum.min_strength = MOM_MIN_STRENGTH
    settings.momentum.max_boost = MOM_MAX_BOOST

    # Blacklist
    settings.pair_blacklist.enabled = True
    settings.pair_blacklist.max_consecutive_losses = BL_MAX_LOSSES
    settings.pair_blacklist.cooldown_days = BL_COOLDOWN

    # Risk
    settings.risk.max_concurrent_positions = 10

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
    print("  EDGECORE BACKTEST v31d -- Curated Universe + Strict Momentum")
    print("=" * 70)
    print(f"  Symbols:      {len(SYMBOLS)} ({len(SYMBOLS)-1} trading + SPY)")
    print(f"  Pairs:        {n_intra} intra-sector")
    print(f"  Period:       {args.start} -> {args.end}")
    print(f"  Capital:      ${args.capital:,.0f}")
    print(f"  Alloc/pair:   {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%")
    print(f"  Z-score:      entry={ENTRY_Z}, exit={EXIT_Z}")
    print(f"  Corr min:     {MIN_CORR} | FDR q={FDR_Q} | HL max={MAX_HALF_LIFE}")
    print("  --- v31d Approach ---")
    print(f"  Curated universe: removed regional banks, biotech, healthcare svc,")
    print(f"    communication, consumer discretionary, REITs, PFE")
    print(f"  Kept: tech(20), fin(9), health(7), staples(7), energy(12),")
    print(f"    industrials(13), utilities(5)")
    print(f"  Momentum:     STRICT (blocks ALL contra-momentum)")
    print(f"  All params:   v30b-proven baseline")
    print(f"  Alloc:        {ALLOC_PCT}% (v30b proven)")
    print("=" * 70)
    print()

    t0 = time.time()
    print("[EDGECORE] Loading IBKR data + running backtest v31d...")
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
    print(f"\n[EDGECORE] Backtest v31d completed in {elapsed:.1f}s")
    print()
    summary = metrics.summary()
    print(summary)
    print(f"\nUniverse: {len(SYMBOLS)} symbols | Intra-sector pairs: {n_intra}")

    # Save
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    out_path = os.path.join(_ROOT, "results", "bt_results_v31d.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Backtest v31d -- Curated Universe + Strict Momentum\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Period: {args.start} -> {args.end}\n")
        f.write(f"Capital: ${args.capital:,.0f}\n")
        f.write(f"Symbols: {len(SYMBOLS)} | Pairs: {n_intra}\n")
        f.write(f"Alloc: {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%\n")
        f.write(f"entry_z={ENTRY_Z}, exit_z={EXIT_Z}, min_spread=${MIN_SPREAD}\n")
        f.write(f"max_HL={MAX_HALF_LIFE} | corr={MIN_CORR} | FDR q={FDR_Q}\n")
        f.write(f"Momentum: STRICT (blocks ALL contra-momentum)\n")
        f.write(f"Curated: removed noisy sectors (regional banks, biotech, etc.)\n")
        f.write(f"Adaptive regime: favorable={TREND_FAVORABLE_SIZING}, neutral={NEUTRAL_SIZING}\n")
        f.write(f"Rediscovery={REDISCOVERY} | weekly_z_gate={WEEKLY_Z_GATE}\n")
        f.write(f"Blacklist: {BL_MAX_LOSSES} losses / {BL_COOLDOWN}d cooldown\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write(summary)
    print(f"\n[Saved] {out_path}")

    # Performance check
    print("\n" + "=" * 70)
    print("  v31d PERFORMANCE CHECK")
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
        print("  >>> ALL CRITERIA MET -- v31d VALIDATED!")
    else:
        print(f"  >>> {passed}/{len(checks)} criteria met.")
    print("=" * 70)

    # Comparison
    print("\n--- Full Iteration History ---")
    print("  v30b: +5.25% | Sharpe 0.74 | 25 trades | WR 60.0% | PF 2.63 | DD -2.6% | 37 sym")
    print("  v31:  -2.53% | Sharpe -0.28 | 63 trades | WR 52.4% | PF 0.80 | DD -7.6% | 117 sym, mom=OFF")
    print("  v31b: -5.14% | Sharpe -0.40 | 65 trades | WR 53.9% | PF 0.74 | DD -11.8% | 117 sym, mom=lenient")
    print("  v31c: -1.63% | Sharpe -0.14 | 47 trades | WR 59.6% | PF 0.87 | DD -7.9% | 117 sym, mom=STRICT")
    if total_return is not None:
        pnl = args.capital * total_return
        print(f"  v31d: {total_return:+.2%} | Sharpe {sharpe:.2f} | {total_trades} trades | WR {win_rate:.1%} | PF {profit_factor:.2f} | DD {max_dd:.1%} | 74 sym, curated")
        print(f"  PnL:  ${pnl:,.0f}")


if __name__ == "__main__":
    main()
