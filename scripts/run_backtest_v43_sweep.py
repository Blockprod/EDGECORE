#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""EDGECORE v43 -- Regime Filter Sweep over Walk-Forward Windows.

Diagnostic from v42 OOS FAIL:
  P1: 0 trades   (FDR too strict -- no pairs found in 2019H2)
  P2: S=0.10     (bull run Jul-2020 -- Jan-2021, MR fights trend)
  P3: S=1.03     (rate-hike volatility -- MR works)
  P4: S=-1.85    (AI bull Jul-2023 -- Jan-2024, NVDA/META explode)
  P5: S=1.11     (consolidation 2024H2 -- MR works)

Root cause: regime_directional_filter=False -> trades both sides in
strong bull runs -> pertes massives P2 et P4.

Correctifs a tester (v43 sweep, 3 configs):
  v43a: regime ON  + fdr_q=0.30  (relax pair discovery + block bad side)
  v43b: regime ON  + fdr_q=0.25  (regime ON, keep current FDR)
  v43c: regime OFF + fdr_q=0.30  (baseline + more pairs, no regime block)

Params de base geles (v41a) pour toutes les configs:
  entry_z=1.6, exit_z=0.2, rediscovery=2, leverage=2.5x, TimeStop=20

Critere de validation OOS:
  PASS   = Sharpe OOS >= 1.2 sur >= 4/5 fenetres
  S-PASS = Sharpe OOS >= 0.8 sur >= 4/5 fenetres
  FAIL   = < 0.8 sur >= 2 fenetres
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

# -- Sweep configs -----------------------------------------------------------
# Each config overrides only what's different from v41a baseline.
#
# Key insight from v42 FAIL diagnosis:
# - vol_threshold=0.18 is TOO LOW: post-COVID 2020H2 vol (~25% ann) triggers
#   MEAN_REVERTING -> shorts not blocked -> losses in bull run (P2, P4)
# - Fix: raise vol_threshold to 0.35 so only true panic vols (>35% ann,
#   VIX>35) bypass the trend gate. Normal "elevated" vol still respects trend.
# - fdr_q=0.30: relaxes pair discovery to fix P1 (0 trades in 2019H2)
#
# Columns: (label, regime_on, fdr_q, trend_fav_sz, vol_threshold, description)
SWEEP_CONFIGS = [
    # label     regime_on  fdr_q   tfz   vol_thresh  description
    ("v43a", True,   0.30, 0.80, 0.35, "Regime ON + fdr_q=0.30 + vol_th=0.35 (primary fix)"),
    ("v43b", True,   0.25, 0.80, 0.35, "Regime ON + fdr_q=0.25 + vol_th=0.35 (no FDR relax)"),
    ("v43c", True,   0.30, 0.80, 0.25, "Regime ON + fdr_q=0.30 + vol_th=0.25 (moderate thresh)"),
    ("v43d", False,  0.30, 1.00, 0.18, "Regime OFF+ fdr_q=0.30 (baseline + more pairs only)"),
]

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
    """Run 5 OOS windows with given config. Return list of (label, sh, verdict, elapsed)."""
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
    print("  EDGECORE v43 -- Regime Filter Sweep (Walk-Forward OOS)")
    print()
    print("  Base (v41a): entry_z=1.6  exit_z=0.2  rediscovery=2  leverage=2.5x  TimeStop=20")
    print("  5 fenetres rolling (Train 18 mois / OOS 6 mois)")
    print()
    print("  v42 baseline (regime OFF, fdr_q=0.25) :")
    print("    PASS=0/5  S-PASS=2/5  FAIL=3/5  Sharpe avg=0.08  -> FAIL")
    print("    Probleme: P2+P4 faibles (bull trends) + P1 vide (0 trades)")
    print()
    print("  Configs a tester:")
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

    all_summaries = []
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
    print("  TABLEAU COMPARATIF v43 SWEEP")
    print("=" * 95)
    print()
    print("  %-6s  %-8s  %-8s  %-5s  %-6s  %-6s  %-6s  %-8s" % (
        "Config", "AvgShrp", "MinShrp", "Pass", "S-Pass", "Fail", "Errors", "Verdict"))
    print("  " + "-" * 75)
    best_cfg = None
    best_avg = -999.0
    for cfg_label, avg_sh, min_sh, passes, spasses, fails, verdict in all_summaries:
        errs = 5 - passes - spasses - fails
        print("  %-6s  %8.2f  %8.2f  %5d  %6d  %6d  %6d  %-8s" % (
            cfg_label, avg_sh, min_sh, passes, spasses, fails, errs, verdict))
        if avg_sh > best_avg:
            best_avg = avg_sh
            best_cfg = cfg_label
    print()
    print("  Meilleure config OOS : %s  (Sharpe moyen = %.2f)" % (best_cfg, best_avg))
    print()

    # Determine overall verdict
    best = next((s for s in all_summaries if s[0] == best_cfg), None)
    if best:
        _, avg_sh, min_sh, passes, spasses, fails, verdict = best
        print("  VERDICT [%s] : %s" % (best_cfg, verdict))
        if verdict == "PASS":
            print("  PROCHAINE ETAPE : Phase 5 -- Expansion Europe (CAC40/DAX ~100 sym)")
            print("  Geler les params de %s comme v43_frozen." % best_cfg)
        elif verdict == "S-PASS":
            print("  PROCHAINE ETAPE : Tester leverage reduit (2.0x) ou fenetres plus larges.")
            print("  Geler %s comme candidat v43_frozen avec note de degradation OOS." % best_cfg)
        else:
            print("  PROCHAINE ETAPE : Revoir entry_z (tester 1.8) ou allonger train window")
            print("  Hypothese: 18 mois train insuffisant pour des periodes volatiles.")
    print()


if __name__ == "__main__":
    main()
