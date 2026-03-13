#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""EDGECORE v43 -- Continuation: run v43b, v43c, v43d only.

v43a already completed:
  P1 2019H2     S= 0.00   +0.00%  WR=  0.0%  t= 0    [FAIL]
  P2 2020H2     S=-0.89   -2.40%  WR= 40.0%  t= 5    [FAIL]
  P3 2022H2     S= 0.00   +0.09%  WR=  0.0%  t= 0    [FAIL] (corrected: 0 trades = 0 Sharpe)
  P4 2023H2     S=-1.56   -2.08%  WR= 33.3%  t= 3    [FAIL]
  P5 2024H2     S= 1.54   +6.80%  WR= 66.7%  t= 3    [PASS]
  Summary (corrected): PASS=1/5  S-PASS=0/5  FAIL=4/5  avg=0.22(raw)  -> FAIL

This script runs v43b, v43c, v43d and prints the full comparison table
including the v43a result above (hardcoded from previous run).

Note: metrics.py now guards 0-trade Sharpe: if trades==0 -> Sharpe=0.0
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager

# -- Universe (identical to v41a) --------------------------------------------
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

# -- Sweep configs: ONLY v43b, v43c, v43d (v43a already done) ----------------
# Columns: (label, regime_on, fdr_q, trend_fav_sz, vol_threshold, description)
SWEEP_CONFIGS = [
    ("v43b", True,   0.25, 0.80, 0.35, "Regime ON + fdr_q=0.25 + vol_th=0.35 (no FDR relax)"),
    ("v43c", True,   0.30, 0.80, 0.25, "Regime ON + fdr_q=0.30 + vol_th=0.25 (moderate thresh)"),
    ("v43d", False,  0.30, 1.00, 0.18, "Regime OFF+ fdr_q=0.30 (baseline + more pairs only)"),
]

# -- v43a result (hardcoded from previous run, after 0-trade Sharpe fix) ------
# Original: P3 S=1.41 with t=0 was FP noise. Corrected to S=0.00.
V43A_RESULT = ("v43a", 0.22, -1.56, 1, 0, 4, "FAIL",
               "Regime ON + fdr_q=0.30 + vol_th=0.35 (primary fix)")
# Note: avg_sh=0.22 = (0+(-0.89)+0+(-1.56)+1.54)/5 after correcting P3 to S=0

# -- Walk-forward windows (same as v42) --------------------------------------
WF_WINDOWS = [
    # label         train_start    train_end      oos_start      oos_end
    ("P1 2019H2", "2018-01-02", "2019-07-01", "2019-07-01", "2020-01-01"),
    ("P2 2020H2", "2019-01-02", "2020-07-01", "2020-07-01", "2021-01-01"),
    ("P3 2022H2", "2021-01-04", "2022-07-01", "2022-07-01", "2023-01-01"),
    ("P4 2023H2", "2022-01-03", "2023-07-01", "2023-07-01", "2024-01-01"),
    ("P5 2024H2", "2023-01-03", "2024-07-01", "2024-07-01", "2025-01-01"),
]


def _apply_settings(regime_on, fdr_q, trend_fav_sz, vol_threshold):
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
    # -- Regime config (sweep variable) --
    s.strategy.regime_directional_filter = regime_on
    s.regime.enabled          = True
    s.regime.ma_fast          = 50
    s.regime.ma_slow          = 200
    s.regime.vol_threshold    = vol_threshold
    s.regime.vol_window       = 20
    s.regime.neutral_band_pct = 0.02
    s.regime.trend_favorable_sizing = trend_fav_sz
    s.regime.neutral_sizing   = 0.70
    # -- FDR q-level (sweep variable) --
    if hasattr(s.strategy, 'fdr_q_level'):
        s.strategy.fdr_q_level = fdr_q


def _run_all_windows(runner, ts20, regime_on, fdr_q, trend_fav_sz, vol_threshold):
    """Run 5 OOS windows with given config. Return list of result tuples."""
    results = []
    for label, train_start, train_end, oos_start, oos_end in WF_WINDOWS:
        _apply_settings(regime_on, fdr_q, trend_fav_sz, vol_threshold)
        runner.config.initial_capital = 100_000
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
        except Exception as e:
            elapsed = int(time.time() - t0)
            results.append((label, None, "ERROR", 0, 0, 0, 0, elapsed, str(e)[:60]))
    return results


def _print_config_results(cfg_label, description, results):
    """Print per-window results and verdict for one config."""
    print()
    print("  [%s]  %s" % (cfg_label, description))
    print("  " + "-" * 95)
    for label, sh, v, ret, wr, t, dd, elapsed, err in results:
        if err:
            print("    %-12s  ERROR: %s [%ds]" % (label, err, elapsed))
        else:
            tpy = t * 2
            print("    %-12s  S=%5.2f  %+6.2f%%  WR=%5.1f%%  t=%2d(~%2.0f)"
                  "  DD=%+6.2f%%  [%s/%ds]" % (
                      label, sh, ret, wr, t, tpy, dd, v, elapsed))
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
    print("  Summary: PASS=%d/5  S-PASS=%d/5  FAIL=%d/5 |"
          " Sharpe avg=%.2f  min=%.2f  -> %s" % (
              passes, spasses, fails, avg_sh, min_sh, verdict))
    return (cfg_label, avg_sh, min_sh, passes, spasses, fails, verdict)


def main():
    print("=" * 95)
    print("  EDGECORE v43 -- Continuation (v43b + v43c + v43d)")
    print()
    print("  v43a result (previous run, corrected 0-trade Sharpe):")
    print("    PASS=1/5  S-PASS=0/5  FAIL=4/5  Sharpe avg=0.22  -> FAIL")
    print("    [P5 only PASS, P1+P3 have 0 trades, P2+P4 bull losses]")
    print()
    print("  Configs running now:")
    for lbl, ron, fq, tfz, vth, desc in SWEEP_CONFIGS:
        regime_str = "ON " if ron else "OFF"
        print("    [%s] regime=%s  fdr_q=%.2f  trend_fav_sz=%.2f  vol_th=%.2f  -- %s" % (
            lbl, regime_str, fq, tfz, vth, desc))
    print("=" * 95)

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000
    ts20 = TimeStopManager(TimeStopConfig(
        half_life_multiplier=1.2,
        max_days_cap=20,
        default_max_bars=20,
    ))

    # Start with v43a pre-loaded result
    all_summaries = [
        # (cfg_label, avg_sh, min_sh, passes, spasses, fails, verdict)
        ("v43a", 0.22, -1.56, 1, 0, 4, "FAIL"),
    ]

    for cfg_label, regime_on, fdr_q, trend_fav_sz, vol_threshold, desc in SWEEP_CONFIGS:
        print()
        print("=" * 95)
        print("  Running %s ..." % cfg_label)
        print("=" * 95)
        results = _run_all_windows(runner, ts20, regime_on, fdr_q, trend_fav_sz, vol_threshold)
        summary = _print_config_results(cfg_label, desc, results)
        all_summaries.append(summary)

    # -- Final comparison table ---------------------------------------------
    print()
    print("=" * 95)
    print("  TABLEAU COMPARATIF v43 SWEEP (ALL CONFIGS)")
    print("=" * 95)
    print()
    print("  %-6s  %-8s  %-8s  %-5s  %-6s  %-6s  %-8s" % (
        "Config", "AvgShrp", "MinShrp", "Pass", "S-Pass", "Fail", "Verdict"))
    print("  " + "-" * 70)
    best_cfg = None
    best_avg = -999.0
    for cfg_label, avg_sh, min_sh, passes, spasses, fails, verdict in all_summaries:
        print("  %-6s  %8.2f  %8.2f  %5d  %6d  %6d  %-8s" % (
            cfg_label, avg_sh, min_sh, passes, spasses, fails, verdict))
        if avg_sh > best_avg:
            best_avg = avg_sh
            best_cfg = cfg_label
    print()
    print("  Meilleure config OOS : %s  (Sharpe moyen = %.2f)" % (best_cfg, best_avg))
    print()

    # Overall verdict
    best = next((s for s in all_summaries if s[0] == best_cfg), None)
    if best:
        _, avg_sh, min_sh, passes, spasses, fails, verdict = best
        print("  VERDICT [%s] : %s" % (best_cfg, verdict))
        if verdict == "PASS":
            print("  NEXT: Phase 5 -- Expand to Europe (CAC40/DAX ~100 sym)")
            print("  Freeze %s params as v43_frozen." % best_cfg)
        elif verdict == "S-PASS":
            print("  NEXT: Test lower leverage (2.0x) or wider train windows (24m).")
            print("  Freeze %s as v43_frozen candidate with OOS degradation note." % best_cfg)
        else:
            print("  ALL v43 CONFIGS FAIL. Proceeding to v44 investigation:")
            print("  Hypothesis A: P1 0-trades -- FDR too strict for 2018-2019 universe")
            print("  Hypothesis B: P2/P4 bull -- longs also fail, need full BULL block")
            print("  Hypothesis C: Train window 18m too short for lookback=120+FDR stability")
            print("  v44 plan: entry_z=1.4 + fdr_q=0.40 + BULL=block_all + train=24m")
    print()


if __name__ == "__main__":
    main()
