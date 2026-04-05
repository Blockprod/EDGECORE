#!/usr/bin/env python
"""EDGECORE Backtest v32 -- v31h + Phase 0 Institutional Upgrades.

v31h baseline: +8.17%, Sharpe 1.31, PF 3.88, WR 62.5%, 24 trades, DD -1.79%

Phase 0 additions:
  0.1 Almgren-Chriss slippage (spread + market_impact + timing)
  0.2 Kelly sizing (1/4 Kelly, max 10%/pair, 25%/sector, 2x leverage)
      + NAV-based stop-loss (0.75% of NAV per trade)
  0.3 Earnings/event filter (3σ gap detection, ±3 day blackout)
  0.4 Short borrow check (HTB gate, max 3% annual fee)

Period: 2023-03-04 to 2026-03-04 (3 years).
Criterion: PF > 1.5, Sharpe > 0.8 after realistic institutional costs.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

# == v30b Universe (37 symbols — PROVEN profitable) =========================
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

# == v30b Parameters EXACTLY (same as v31h) =================================
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

# Time stop
TIME_STOP_MULT = 1.5
MAX_HOLD_DAYS = 30

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
        description="EDGECORE Backtest v32 -- v31h + Phase 0"
    )
    parser.add_argument("--start", default="2023-03-04")
    parser.add_argument("--end", default="2026-03-04")
    parser.add_argument("--capital", type=float, default=100_000)
    args = parser.parse_args()

    from config.settings import get_settings
    settings = get_settings()

    # Strategy — v30b params exactly
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

    # == TIME STOP ==
    from execution.time_stop import TimeStopConfig, TimeStopManager
    time_stop = TimeStopManager(TimeStopConfig(
        half_life_multiplier=TIME_STOP_MULT,
        max_days_cap=MAX_HOLD_DAYS,
        default_max_bars=MAX_HOLD_DAYS,
    ))

    # == PHASE 0.2: Kelly Sizer ==
    from risk.kelly_sizing import KellySizer, KellySizerConfig
    kelly_sizer = KellySizer(KellySizerConfig(
        kelly_fraction=0.25,          # Quarter-Kelly (conservative)
        max_position_pct=10.0,        # Max 10% per pair
        min_position_pct=2.0,         # Min 2% per pair
        max_sector_pct=25.0,          # Max 25% per sector
        max_gross_leverage=2.0,       # Max 2x gross leverage
        max_loss_per_trade_nav_pct=0.75,  # NAV stop: 0.75% of NAV
        default_allocation_pct=8.0,   # Default if no history
    ))

    # == PHASE 0.3: Event Filter ==
    from data.event_filter import EventFilter, EventFilterConfig
    event_filter = EventFilter(EventFilterConfig(
        gap_sigma_threshold=3.0,      # 3σ overnight gap = earnings
        blackout_days_before=3,       # Block 3 days before
        blackout_days_after=3,        # Block 3 days after
        rolling_window=60,
        enabled=True,
    ))

    # == PHASE 0.4: Borrow Checker ==
    from execution.borrow_check import BorrowChecker, BorrowCheckerConfig
    borrow_checker = BorrowChecker(BorrowCheckerConfig(
        max_borrow_fee_pct=3.0,       # Reject if annual fee > 3%
        min_shortable_shares=1_000,
        htb_borrow_fee_pct=5.0,       # Assumed HTB fee
        default_borrow_fee_pct=0.5,   # General collateral ETB rate
        enabled=True,
    ))

    runner = BacktestRunner()
    runner.config.initial_capital = args.capital

    n_intra = sum(
        1 for i, s1 in enumerate(SYMBOLS)
        for s2 in SYMBOLS[i + 1:]
        if SECTOR_MAP.get(s1) == SECTOR_MAP.get(s2)
    )

    print("=" * 70)
    print("  EDGECORE BACKTEST v32 -- v31h + Phase 0 Institutional")
    print("=" * 70)
    print(f"  Symbols:      {len(SYMBOLS)} ({len(SYMBOLS)-1} trading + SPY)")
    print(f"  Pairs:        {n_intra} intra-sector")
    print(f"  Period:       {args.start} -> {args.end}")
    print(f"  Capital:      ${args.capital:,.0f}")
    print(f"  Alloc/pair:   {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%")
    print(f"  Z-score:      entry={ENTRY_Z}, exit={EXIT_Z}")
    print(f"  Stop:         {STOP_PCT*100:.0f}% | z_stop={Z_SCORE_STOP}")
    print("  --- Phase 0 Institutional Upgrades ---")
    print(f"  0.1 Slippage: Almgren-Chriss (spread+impact+timing)")
    print(f"  0.2 Kelly:    1/4 Kelly, max 10%/pair, 25%/sector, 2x lev")
    print(f"  0.2 NAV stop: 0.75% of NAV per trade")
    print(f"  0.3 Events:   3-sigma gap detection, +/-3d blackout")
    print(f"  0.4 Borrow:   HTB gate, max 3% annual fee")
    print(f"  time_stop:    {TIME_STOP_MULT}x HL, cap={MAX_HOLD_DAYS}d")
    print(f"  momentum:     STRICT (min_strength={MOM_MIN_STRENGTH})")
    print("=" * 70)
    print()

    t0 = time.time()
    print("[EDGECORE] Loading IBKR data + running backtest v32...")
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
        kelly_sizer=kelly_sizer,
        event_filter=event_filter,
        borrow_checker=borrow_checker,
    )

    elapsed = time.time() - t0
    print(f"\n[EDGECORE] Backtest v32 completed in {elapsed:.1f}s")
    print()
    summary = metrics.summary()
    print(summary)

    # == Comparison vs v31h baseline ==
    print()
    print("=" * 70)
    print("  COMPARISON: v32 (Phase 0) vs v31h (baseline)")
    print("=" * 70)
    print("  v31h baseline: +8.17%, Sharpe 1.31, PF 3.88, WR 62.5%")
    print(f"               24 trades, DD -1.79%, Calmar 4.56")
    print()
    print(f"  v32 result:   see metrics above")
    print(f"  Criterion:    PF > 1.5, Sharpe > 0.8")
    print("=" * 70)

    print(f"\nUniverse: {len(SYMBOLS)} symbols | Intra-sector pairs: {n_intra}")

    # Save
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    out_path = os.path.join(_ROOT, "results", "bt_results_v32.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Backtest v32 -- v31h + Phase 0 Institutional\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"Period: {args.start} -> {args.end}\n")
        f.write(f"Capital: ${args.capital:,.0f}\n")
        f.write(f"Symbols: {len(SYMBOLS)} | Pairs: {n_intra}\n")
        f.write(f"Alloc: {ALLOC_PCT}% | Heat: {HEAT*100:.0f}%\n")
        f.write(f"entry_z={ENTRY_Z}, exit_z={EXIT_Z}, min_spread=${MIN_SPREAD}\n")
        f.write(f"stop={STOP_PCT} | max_HL={MAX_HALF_LIFE} | corr={MIN_CORR} | FDR q={FDR_Q}\n")
        f.write(f"time_stop={TIME_STOP_MULT}x HL, cap={MAX_HOLD_DAYS}d\n")
        f.write(f"Momentum: STRICT (min_strength={MOM_MIN_STRENGTH})\n")
        f.write(f"Phase 0: Almgren-Chriss + Kelly 1/4 + EventFilter + BorrowCheck\n")
        f.write(f"Elapsed: {elapsed:.1f}s\n\n")
        f.write(summary)
        f.write(f"\n\n--- v31h baseline ---\n")
        f.write(f"+8.17%, Sharpe 1.31, PF 3.88, WR 62.5%, 24 trades, DD -1.79%\n")
    print(f"\n[Saved] {out_path}")


if __name__ == "__main__":
    main()
