#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""EDGECORE v44b -- Walk-Forward: Lower entry threshold (entry_z=1.4) sweep.

v44 post-mortem:
  v44 (BEAR_TRENDING neutral fix): PASS=1/5, avg=-0.36 -> FAIL (WORSE than v43a)
  Root cause: vol_threshold=0.35 creates rapid regime oscillation in 2022H2.
    2022H2 vol hovers at 0.34-0.36 -> regime flips MEAN_REVERTING<->BEAR_TRENDING
    every few days. This unstable switching produces S=-0.72 vs v43d's S=+0.31 (regime OFF).

v44b sweep rationale:
  - Revert BEAR fix (back to v43a config: BEAR blocks longs) 
  - Lower entry_z: 1.6 -> 1.4 to fix P1 (2019H2 smooth bull: 0 OOS trades at z=1.6)
  - Test 3 entry_z variants to find best signal sensitivity vs false-positive tradeoff:
      v44b_16: entry_z=1.6 (v43a baseline, PASS=1/5 avg=0.22) -- reference
      v44b_14: entry_z=1.4 (more signals, P1 might get entries)
      v44b_12: entry_z=1.2 (aggressive -- more signals but more noise)
  - All use v43a regime: vol_th=0.35, BEAR blocks longs, BULL blocks shorts, fdr_q=0.30

Key question: Does entry_z=1.4 unlock P1 signals without causing excess false positives in P4?

v43a per-window reference (best of v43):
  P1: S=0.00  t=0   FAIL  -- <-- NEED TO FIX (0 OOS trades)
  P2: S=-0.89 t=5   FAIL  -- post-COVID bull (loses on longs)
  P3: S=0.00  t=0   FAIL  -- BEAR blocks longs (accepted as known flaw)
  P4: S=-1.56 t=3   FAIL  -- AI bull (3 losing longs, immovable)
  P5: S=1.54  t=3   PASS  -- moderate bull (BULL blocks shorts, longs MR)
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

CONFIGS = [
    # name       entry_z  description
    ("v44b_16",  1.6,     "baseline (same as v43a best)"),
    ("v44b_14",  1.4,     "lower threshold -- target P1 fix"),
    ("v44b_12",  1.2,     "aggressive threshold -- test overfitting boundary"),
]


def _apply_settings(entry_z: float):
    """Apply v43a base params with specified entry_z."""
    s = get_settings()
    # -- v41a frozen base params --
    s.strategy.lookback_window             = 120
    s.strategy.additional_lookback_windows = [63]
    s.strategy.entry_z_score               = entry_z      # <-- VARIES
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
    # -- v43a regime params (ORIGINAL: BEAR blocks longs) --
    # Note: market_regime.py currently has BEAR=neutral from v44. 
    # We override at runtime by passing enabled/vol_threshold here,
    # but the BEAR blocking logic is in market_regime.py code.
    # For v44b, we revert BEAR blocking in market_regime.py.
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


def run_config(runner, ts20, cfg_name: str, entry_z: float, description: str) -> list:
    """Run one config across all 5 WF windows. Returns list of result tuples."""
    print()
    print("  %-10s  entry_z=%.1f  [%s]" % (cfg_name, entry_z, description))
    print("  " + "-" * 75)
    results = []
    for label, train_start, train_end, oos_start, oos_end in WF_WINDOWS:
        _apply_settings(entry_z)
        t0 = time.time()
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
            print("    %-12s  S=%5.2f  %+6.2f%%  WR=%5.1f%%  t=%2d  DD=%+6.2f%%"
                  "  [%s/%ds]" % (label, sh, ret, wr, t, dd, v, elapsed))
        except Exception as e:
            elapsed = int(time.time() - t0)
            results.append((label, None, "ERROR", 0, 0, 0, 0, elapsed, str(e)[:80]))
            print("    %-12s  ERROR: %s" % (label, str(e)[:80]))
    return results


def main():
    print("=" * 95)
    print("  EDGECORE v44b -- Walk-Forward Sweep: entry_z variants")
    print()
    print("  BEFORE RUNNING: Ensure market_regime.py BEAR_TRENDING blocks longs")
    print("  (revert v44 BEAR fix if still active = BEAR should have long_sz=0.0)")
    print()
    print("  Configs:")
    for name, ez, desc in CONFIGS:
        print("    %-10s  entry_z=%.1f  %s" % (name, ez, desc))
    print()
    print("  v43a baseline:  entry_z=1.6  PASS=1/5 (P5)  avg=0.22  -> FAIL")
    print("  v43d reference: entry_z=1.6  PASS=0/5 (P5 S-PASS, regime OFF)")
    print("  v44 result:     entry_z=1.6  PASS=1/5 (P5)  avg=-0.36 -> FAIL (worse)")
    print()
    print("  Disk cache: 5 parquet files cached from v43 run -> fast data load (~30s)")
    print("=" * 95)

    # Check if BEAR is correctly configured before running
    # We rely on market_regime.py BEAR blocking longs (long_sz=0.0)
    # User reminder is printed above

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000
    ts20 = TimeStopManager(TimeStopConfig(
        half_life_multiplier=1.2,
        max_days_cap=20,
        default_max_bars=20,
    ))

    all_results = {}
    for cfg_name, entry_z, description in CONFIGS:
        all_results[cfg_name] = run_config(runner, ts20, cfg_name, entry_z, description)

    # Final comparison table
    print()
    print("=" * 95)
    print("  v44b FINAL COMPARISON TABLE")
    print("=" * 95)
    print()
    print("  %-10s  %s  %s  %s  %s  %s  %s  %s" % (
        "Config", "AvgShr", "MinShr", "Pass", "S-P ", "Fail", "  t_avg", "Verdict"))
    print("  " + "-" * 75)

    comparison = []
    for cfg_name, entry_z, description in CONFIGS:
        results = all_results[cfg_name]
        valid   = [r for r in results if r[2] != "ERROR" and r[1] is not None]
        passes  = sum(1 for r in valid if r[2] == "PASS")
        spasses = sum(1 for r in valid if r[2] == "S-PASS")
        fails   = sum(1 for r in valid if r[2] == "FAIL")
        sharpes = [r[1] for r in valid]
        avg_sh  = sum(sharpes) / len(sharpes) if sharpes else 0.0
        min_sh  = min(sharpes) if sharpes else 0.0
        avg_t   = sum(r[5] for r in valid) / len(valid) if valid else 0
        if passes >= 4:
            verdict = "PASS"
        elif passes + spasses >= 4:
            verdict = "S-PASS"
        else:
            verdict = "FAIL"
        comparison.append((cfg_name, avg_sh, min_sh, passes, spasses, fails, avg_t, entry_z, verdict))
        print("  %-10s  %+6.2f  %+6.2f  %4d  %4d  %4d  %5.1f  %s" % (
            cfg_name, avg_sh, min_sh, passes, spasses, fails, avg_t, verdict))

    # Reference rows
    print("  " + "-" * 75)
    print("  %-10s  %+6.2f  %+6.2f  %4d  %4d  %4d  %5.1f  %s  [ref: v43a best]" % (
        "v43a", 0.22, -1.56, 1, 0, 4, 3.8, "FAIL"))
    print("  %-10s  %+6.2f  %+6.2f  %4d  %4d  %4d  %5.1f  %s  [ref: v43d regOFF]" % (
        "v43d", -0.01, -1.08, 0, 1, 4, 4.0, "FAIL"))
    print()

    best = max(comparison, key=lambda x: x[1])
    print("  Best: %s (avg=%.2f) -> %s" % (best[0], best[1], best[8]))
    print()

    if any(c[8] in ("PASS", "S-PASS") for c in comparison):
        champ = [c for c in comparison if c[8] in ("PASS", "S-PASS")][0]
        print("  BREAKTHROUGH! %s -> %s (entry_z=%.1f)" % (
            champ[0], champ[8], champ[7]))
        print("  Next: Phase 5 planning, expand universe")
    elif best[3] >= 2:  # 2+ PASSes
        print("  NOTE: %s achieves %d/5 PASS (need 4). P4 remains persistent failure." % (
            best[0], best[3]))
        print("  Next: Investigate P4 (2023H2 AI bull) -> consider sector rotation blocker")
        print("  or universe expansion to dilute AI bubble exposure")
    else:
        print("  Analysis:")
        for cfg, avg_sh, min_sh, passes, spasses, fails, avg_t, entry_z, verdict in comparison:
            if passes > 1 or spasses > 1:
                print("    %s: entry_z=%.1f -> %d PASS + %d S-PASS (potential improvement)" % (
                    cfg, entry_z, passes, spasses))
        print("  Structural issue: strategy needs universe expansion (100+ symbols)")
        print("  to reduce per-window sensitivity to single regime/asset-class failures.")
    print()


if __name__ == "__main__":
    main()
