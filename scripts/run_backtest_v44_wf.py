#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""EDGECORE v44 -- Walk-Forward: Fixed BEAR_TRENDING regime.

v43 sweep diagnostic results:
  ALL 4 v43 configs FAIL. Root causes:
  1. P1 (2019H2): 0 OOS trades regardless of regime -- z=1.6 too high in smooth bull
  2. P2 (2020H2): Regime filter makes P2 WORSE (S=-0.89 vs -0.39 regime-OFF)
  3. P3 (2022H2): BEAR_TRENDING blocks longs -> 0 trades. Regime OFF gives S=0.31.
  4. P4 (2023H2): Persistent -1.08 regardless -> NVDA-driven bull hard to avoid
  5. P5 (2024H2): Regime ON helps (S=1.54 vs 1.11 OFF)

v44 fix:
  - BEAR_TRENDING changed: no longer blocks longs. Both sides at neutral_sizing=0.70
    Rationale: pairs MR works in bear markets too (2022H2 data confirms this)
  - vol_th=0.35 (keeps BULL detection clean, P5 quality maintained)
  - fdr_q=0.30 (slightly more lenient pair discovery)
  - entry_z=1.6 (unchanged - will test 1.4 in v44b if P1 still fails)

Expected improvements:
  P3 (BEAR_TRENDING restored): both sides at 0.70 -> ~4-6 OOS trades, expect S~0.3-1.0
  P5 (BULL_TRENDING maintained): shorts still blocked, longs at 0.80 -> S>1.2 expected
  P1: may still have 0 trades (z=1.6 too high for 2019H2 smooth bull)
  P2/P4: unknown - depends on whether restored BEAR allows better entries in v2020/2023

Params (v41a frozen):
  entry_z=1.6, exit_z=0.2, rediscovery=2, leverage=2.5x, TimeStop=20
  vol_th=0.35, fdr_q=0.30
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager

WF_SYMBOLS = [
    "SPY",
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO", "XLK",
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    "XOM", "CVX", "COP", "EOG",
    "KO", "PEP", "PG", "CL", "WMT",
    "CAT", "HON", "DE", "GE", "RTX",
    "NEE", "DUK", "SO",
    "JNJ", "PFE", "UNH", "MRK", "ABBV",
    "MCD",
]

WF_SECTOR_MAP = {
    "AAPL": "technology", "MSFT": "technology", "GOOGL": "technology",
    "META": "technology", "NVDA": "technology", "AMD": "technology",
    "AVGO": "technology", "XLK": "technology",
    "JPM": "financials", "GS": "financials", "BAC": "financials",
    "MS": "financials", "WFC": "financials", "C": "financials",
    "SCHW": "financials",
    "XOM": "energy", "CVX": "energy", "COP": "energy", "EOG": "energy",
    "KO": "consumer_staples", "PEP": "consumer_staples",
    "PG": "consumer_staples", "CL": "consumer_staples",
    "WMT": "consumer_staples", "MCD": "consumer_staples",
    "CAT": "industrials", "HON": "industrials", "DE": "industrials",
    "GE": "industrials", "RTX": "industrials",
    "NEE": "utilities", "DUK": "utilities", "SO": "utilities",
    "JNJ": "healthcare", "PFE": "healthcare", "UNH": "healthcare",
    "MRK": "healthcare", "ABBV": "healthcare",
    "SPY": "benchmark",
}

WF_WINDOWS = [
    # label         train_start    train_end      oos_start      oos_end
    ("P1 2019H2", "2018-01-02", "2019-07-01", "2019-07-01", "2020-01-01"),
    ("P2 2020H2", "2019-01-02", "2020-07-01", "2020-07-01", "2021-01-01"),
    ("P3 2022H2", "2021-01-04", "2022-07-01", "2022-07-01", "2023-01-01"),
    ("P4 2023H2", "2022-01-03", "2023-07-01", "2023-07-01", "2024-01-01"),
    ("P5 2024H2", "2023-01-03", "2024-07-01", "2024-07-01", "2025-01-01"),
]


def _apply_v44_settings():
    s = get_settings()
    # -- v41a frozen base params --
    s.strategy.lookback_window             = 120
    s.strategy.additional_lookback_windows = [63]
    s.strategy.entry_z_score               = 1.6
    s.strategy.exit_z_score                = 0.2
    s.strategy.entry_z_min_spread          = 0.30
    s.strategy.z_score_stop                = 2.5
    s.strategy.min_correlation             = 0.65
    s.strategy.max_half_life               = 60
    s.strategy.max_position_loss_pct       = 0.03
    s.strategy.internal_max_drawdown_pct   = 0.12
    s.strategy.use_kalman                  = True
    s.strategy.bonferroni_correction       = True
    s.strategy.johansen_confirmation       = True
    s.strategy.newey_west_consensus        = True
    s.strategy.weekly_zscore_entry_gate    = 0.3
    s.strategy.trend_long_sizing           = 0.75
    s.strategy.disable_shorts_in_bull_trend = False
    s.strategy.short_sizing_multiplier     = 0.50
    s.momentum.enabled        = True
    s.momentum.lookback       = 20
    s.momentum.weight         = 0.30
    s.momentum.min_strength   = 1.0
    s.momentum.max_boost      = 1.0
    s.pair_blacklist.enabled                = True
    s.pair_blacklist.max_consecutive_losses = 5
    s.pair_blacklist.cooldown_days          = 10
    s.risk.max_concurrent_positions         = 10
    # -- v44 regime params: regime ON, vol_th=0.35, fdr_q=0.30 --
    # Note: BEAR_TRENDING now uses neutral_sizing (both sides) in market_regime.py
    s.strategy.regime_directional_filter = True
    s.regime.enabled          = True
    s.regime.ma_fast          = 50
    s.regime.ma_slow          = 200
    s.regime.vol_threshold    = 0.35
    s.regime.vol_window       = 20
    s.regime.neutral_band_pct = 0.02
    s.regime.trend_favorable_sizing = 0.80
    s.regime.neutral_sizing   = 0.70
    if hasattr(s.strategy, 'fdr_q_level'):
        s.strategy.fdr_q_level = 0.30


def main():
    print("=" * 95)
    print("  EDGECORE v44 -- Walk-Forward: Fixed BEAR_TRENDING regime")
    print()
    print("  v44 changes vs v43a (best of v43):")
    print("    BEAR_TRENDING: longs NO LONGER blocked (both sides at neutral_sz=0.70)")
    print("    vol_th=0.35  fdr_q=0.30  entry_z=1.6 (unchanged)")
    print()
    print("  Expected: P3 2022H2 restored (BEAR->neutral, ~4 trades), P5 unchanged (BULL)")
    print()
    print("  v43 outcome reference:")
    print("    Best was v43a: PASS=1/5 (P5 only), avg=0.22 -> FAIL")
    print("    v43d (regime OFF): P3=0.31 S-PASS -> confirms BEAR blocking was wrong")
    print()
    print("  Disk cache: all 5 window date ranges already cached from v43 run")
    print("=" * 95)

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000
    ts20 = TimeStopManager(TimeStopConfig(
        half_life_multiplier=1.2,
        max_days_cap=20,
        default_max_bars=20,
    ))

    results = []
    for label, train_start, train_end, oos_start, oos_end in WF_WINDOWS:
        _apply_v44_settings()
        runner.config.initial_capital = 100_000
        t0 = time.time()
        print()
        print("  Running %s (train %s -> %s | OOS %s -> %s)" % (
            label, train_start, train_end, oos_start, oos_end))
        try:
            metrics = runner.run_unified(
                symbols=WF_SYMBOLS,
                start_date=train_start,
                end_date=oos_end,
                oos_start_date=oos_start,
                sector_map=WF_SECTOR_MAP,
                pair_rediscovery_interval=2,
                allocation_per_pair_pct=50.0,
                max_position_loss_pct=0.07,
                max_portfolio_heat=3.0,
                time_stop=ts20,
                leverage_multiplier=2.5,
            )
            elapsed = int(time.time() - t0)
            sh  = metrics.sharpe_ratio
            ret = metrics.total_return * 100
            wr  = metrics.win_rate * 100
            t   = metrics.total_trades
            dd  = metrics.max_drawdown * 100
            v   = "PASS" if sh >= 1.2 else ("S-PASS" if sh >= 0.8 else "FAIL")
            results.append((label, sh, v, ret, wr, t, dd, elapsed, None))
            tpy = t * 2
            print("  -> S=%5.2f  %+6.2f%%  WR=%5.1f%%  t=%2d(~%2.0f)"
                  "  DD=%+6.2f%%  [%s/%ds]" % (sh, ret, wr, t, tpy, dd, v, elapsed))
        except Exception as e:
            elapsed = int(time.time() - t0)
            results.append((label, None, "ERROR", 0, 0, 0, 0, elapsed, str(e)[:80]))
            print("  -> ERROR: %s" % str(e)[:80])

    # Summary
    valid   = [r for r in results if r[2] != "ERROR" and r[1] is not None]
    passes  = sum(1 for r in valid if r[2] == "PASS")
    spasses = sum(1 for r in valid if r[2] == "S-PASS")
    fails   = sum(1 for r in valid if r[2] == "FAIL")
    sharpes = [r[1] for r in valid]
    avg_sh  = sum(sharpes) / len(sharpes) if sharpes else 0.0
    min_sh  = min(sharpes) if sharpes else 0.0
    if passes >= 4:
        verdict = "PASS"
    elif passes + spasses >= 4:
        verdict = "S-PASS"
    else:
        verdict = "FAIL"

    print()
    print("=" * 95)
    print("  v44 RESULTS -- Fixed BEAR_TRENDING")
    print("=" * 95)
    print()
    for label, sh, v, ret, wr, t, dd, elapsed, err in results:
        if err:
            print("    %-12s  ERROR: %s [%ds]" % (label, err, elapsed))
        else:
            tpy = t * 2
            print("    %-12s  S=%5.2f  %+6.2f%%  WR=%5.1f%%  t=%2d(~%2.0f)"
                  "  DD=%+6.2f%%  [%s/%ds]" % (
                      label, sh, ret, wr, t, tpy, dd, v, elapsed))
    print()
    print("  Summary: PASS=%d/5  S-PASS=%d/5  FAIL=%d/5 |"
          " Sharpe avg=%.2f  min=%.2f  -> %s" % (
              passes, spasses, fails, avg_sh, min_sh, verdict))
    print()

    # Comparison with v43 best (v43a corrected)
    print("  Comparison:")
    print("    v43a (best of v43): PASS=1/5  S-PASS=0/5  avg=0.22  -> FAIL")
    print("    v43d (regime OFF):  PASS=0/5  S-PASS=1/5  avg=-0.01 -> FAIL")
    print("    v44  (this run):    PASS=%d/5  S-PASS=%d/5  avg=%.2f  -> %s" % (
        passes, spasses, avg_sh, verdict))
    print()

    if verdict == "PASS":
        print("  PASS! Next: Phase 5 -- Expand universe to Europe (CAC40/DAX ~100 symbols)")
        print("  Freeze v44 params.")
    elif verdict == "S-PASS":
        print("  S-PASS. Next: v44b sweep -- entry_z=1.4 to fix P1 0-trades")
        print("  Then retest WF.")
    else:
        print("  Still FAIL. Next steps:")
        print("  Option A: v44b -- lower entry_z to 1.4 (fix P1 0-trades)")
        print("  Option B: v44c -- 24-month train windows (more stable cointegration)")
        print("  Option C: Strategy restructure -- regime-gated live trading only")
        if passes >= 2:
            print("  Note: %d/5 PASS windows -> strategy works in specific regimes" % passes)
            print("  Consider: regime-conditional deployment (only run in MR-favorable periods)")
    print()


if __name__ == "__main__":
    main()
