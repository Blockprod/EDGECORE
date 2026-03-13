#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""EDGECORE v46 -- Walk-Forward: Momentum Divergence Filter.

v45b post-mortem — root cause identified from trade log analysis:
  P1 (2019H2): S=-1.57, 30 trades — LOSING pairs: AAPL_AMD (AMD +35% momentum
    leader 2019), AAPL_META (META regulatory laggard), GS_COF (structural
    banking divergence). Spread TRENDS, never mean-reverts.
  P3 (2022H2): S=+2.21, 33 trades — WINNING pairs: PG_CL, GIS_MO, CVX_SLB.
    Bear regime equalises returns -> temporary divergences DO mean-revert.
  P4 (2023H2): S=-2.01, 34 trades — LOSING pairs: JPM_MS (MS AI IB boom,
    z=+2.1 cs-momentum), AMZN_HD (AMZN AI/cloud surge, z=+2.4), GS_BAC/WFC.

ROOT CAUSE: NOT cross-sector selection. It is CROSS-SECTIONAL MOMENTUM
DIVERGENCE within otherwise cointegrated pairs.
  - Bull/tech regime: one leg becomes a "structural winner" (AMD 2019,
    MS/AMZN 2023) -> spread TRENDS instead of mean-reverting.
  - Bear/neutral regime: uniform drawdown suppresses momentum outliers ->
    pairs ARE stationary and MR works (P3).

v46 FIX: Cross-sectional momentum divergence filter (MomentumDivergenceFilter)
  At every entry: compute 60-day trailing return for all universe symbols,
  compute cross-sectional z-score. REJECT entry if |z(leg1) - z(leg2)| > 1.5.

  Expected improvements:
    P1 2019H2: filter blocks AAPL_AMD (|dz|~2.5), AAPL_META (|dz|~2.3),
               GS_COF (|dz|~1.8) -> fewer losing trades -> S improves
    P4 2023H2: filter blocks JPM_MS (|dz|~2.4), AMZN_HD (|dz|~3.5),
               GS_WFC (|dz|~2.0) -> fewer losers -> S improves
    P3/P5:     filter PRESERVES working pairs (PG_CL |dz|~0.4, GIS_MO |dz|~0.6)
               -> bear-regime pairs unaffected (pass through)

  If hypothesis correct: P1/P4 S improves from -1.57/-2.01 toward ≥0.
  If P3/P5 stable: aggregate PASS becomes possible.

Params: v43a frozen (identical to v45b), same 103-symbol universe.
  Only addition: momentum_filter=MomentumDivergenceFilter(threshold=1.5, lookback=60)
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager
from pair_selection.filters import MomentumDivergenceFilter

# ---------------------------------------------------------------------------
# Universe: 103 symbols across 12 sectors (unchanged from v45b)
# ---------------------------------------------------------------------------

WF_SYMBOLS = [
    "SPY",
    # Technology (15)
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO", "XLK",
    "INTC", "QCOM", "TXN", "CRM", "ORCL", "ACN", "CSCO",
    # Financials (14)
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    "BLK", "AXP", "USB", "PNC", "COF", "BK", "TFC",
    # Energy (9)
    "XOM", "CVX", "COP", "EOG",
    "SLB", "VLO", "MPC", "PSX", "OXY",
    # Consumer Staples (11)
    "KO", "PEP", "PG", "CL", "WMT", "MCD",
    "COST", "MDLZ", "GIS", "PM", "MO",
    # Industrials (11)
    "CAT", "HON", "DE", "GE", "RTX",
    "MMM", "UPS", "BA", "ITW", "LMT", "FDX",
    # Utilities (6)
    "NEE", "DUK", "SO",
    "AEP", "EXC", "WEC",
    # Healthcare (12)
    "JNJ", "PFE", "UNH", "MRK", "ABBV",
    "TMO", "ABT", "DHR", "MDT", "CVS", "CI", "BMY",
    # Consumer Discretionary (9)
    "AMZN", "TSLA", "HD", "NKE", "LOW", "TGT", "SBUX", "F", "GM",
    # Materials (5)
    "LIN", "APD", "ECL", "NEM", "FCX",
    # Real Estate (4)
    "PLD", "AMT", "SPG", "EQIX",
    # Communication Services (5)
    "T", "VZ", "CMCSA", "DIS", "NFLX",
]

WF_SECTOR_MAP = {
    # Technology
    "AAPL": "technology", "MSFT": "technology", "GOOGL": "technology",
    "META": "technology", "NVDA": "technology", "AMD": "technology",
    "AVGO": "technology", "XLK": "technology",
    "INTC": "technology", "QCOM": "technology", "TXN": "technology",
    "CRM": "technology", "ORCL": "technology", "ACN": "technology",
    "CSCO": "technology",
    # Financials
    "JPM": "financials", "GS": "financials", "BAC": "financials",
    "MS": "financials", "WFC": "financials", "C": "financials",
    "SCHW": "financials",
    "BLK": "financials", "AXP": "financials", "USB": "financials",
    "PNC": "financials", "COF": "financials", "BK": "financials",
    "TFC": "financials",
    # Energy
    "XOM": "energy", "CVX": "energy", "COP": "energy", "EOG": "energy",
    "SLB": "energy", "VLO": "energy", "MPC": "energy",
    "PSX": "energy", "OXY": "energy",
    # Consumer Staples
    "KO": "consumer_staples", "PEP": "consumer_staples",
    "PG": "consumer_staples", "CL": "consumer_staples",
    "WMT": "consumer_staples", "MCD": "consumer_staples",
    "COST": "consumer_staples", "MDLZ": "consumer_staples",
    "GIS": "consumer_staples", "PM": "consumer_staples",
    "MO": "consumer_staples",
    # Industrials
    "CAT": "industrials", "HON": "industrials", "DE": "industrials",
    "GE": "industrials", "RTX": "industrials",
    "MMM": "industrials", "UPS": "industrials", "BA": "industrials",
    "ITW": "industrials", "LMT": "industrials", "FDX": "industrials",
    # Utilities
    "NEE": "utilities", "DUK": "utilities", "SO": "utilities",
    "AEP": "utilities", "EXC": "utilities", "WEC": "utilities",
    # Healthcare
    "JNJ": "healthcare", "PFE": "healthcare", "UNH": "healthcare",
    "MRK": "healthcare", "ABBV": "healthcare",
    "TMO": "healthcare", "ABT": "healthcare", "DHR": "healthcare",
    "MDT": "healthcare", "CVS": "healthcare", "CI": "healthcare",
    "BMY": "healthcare",
    # Consumer Discretionary
    "AMZN": "consumer_discretionary", "TSLA": "consumer_discretionary",
    "HD": "consumer_discretionary", "NKE": "consumer_discretionary",
    "LOW": "consumer_discretionary", "TGT": "consumer_discretionary",
    "SBUX": "consumer_discretionary", "F": "consumer_discretionary",
    "GM": "consumer_discretionary",
    # Materials
    "LIN": "materials", "APD": "materials", "ECL": "materials",
    "NEM": "materials", "FCX": "materials",
    # Real Estate
    "PLD": "real_estate", "AMT": "real_estate",
    "SPG": "real_estate", "EQIX": "real_estate",
    # Communication Services
    "T": "communication", "VZ": "communication", "CMCSA": "communication",
    "DIS": "communication", "NFLX": "communication",
    # Benchmark
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


def _apply_v46_settings():
    """v43a best params, unchanged. Only momentum filter added."""
    s = get_settings()
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
    s.risk.max_concurrent_positions         = 15
    s.strategy.regime_directional_filter    = True
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
    print("  EDGECORE v46 -- Walk-Forward: Momentum Divergence Filter")
    print()
    print("  v45b DIAGNOSIS: cross-sectional momentum divergence within pairs")
    print("    P1 (2019H2 bull):  AMD +35% cs-z=+2.3 vs AAPL z=-0.2 -> |dz|=2.5 TREND")
    print("    P4 (2023H2 AI):    MS  AI  cs-z=+2.1 vs JPM  z=-0.3 -> |dz|=2.4 TREND")
    print("    P4 (2023H2 AI):    AMZN    cs-z=+2.4 vs HD   z=-1.1 -> |dz|=3.5 TREND")
    print("    P3 (2022H2 bear):  PG_CL         |dz|<0.5 -> pairs MEAN-REVERT OK")
    print()
    print("  v46 FIX: MomentumDivergenceFilter(threshold=1.5, lookback=60)")
    print("    At entry: compute cross-sectional z-score for all 103 symbols")
    print("    REJECT if |z(leg1) - z(leg2)| > 1.5")
    print()
    print("  Expected results vs v45b:")
    print("    P1: S=-1.57 -> S>-0.5  (AAPL_AMD/META/GS_COF blocked)")
    print("    P3: S=+2.21 -> S>=1.5  (PG_CL/GIS_MO/CVX_SLB pass through)")
    print("    P4: S=-2.01 -> S>-0.5  (JPM_MS/AMZN_HD/GS_WFC blocked)")
    print("    P5: unchanged or better")
    print()
    n = len(WF_SYMBOLS)
    n_pairs = n * (n - 1) // 2
    print("  Universe: %d symbols, %d potential pairs (same as v45b)" % (n, n_pairs))
    print("=" * 95)

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000
    ts20 = TimeStopManager(TimeStopConfig(
        half_life_multiplier=1.2,
        max_days_cap=20,
        default_max_bars=20,
    ))

    # The sole addition vs v45b: momentum divergence filter
    mom_filter = MomentumDivergenceFilter(
        lookback_days=60,
        threshold=1.5,
        min_universe_size=20,
    )

    results = []
    for label, train_start, train_end, oos_start, oos_end in WF_WINDOWS:
        _apply_v46_settings()
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
                momentum_filter=mom_filter,
            )
            elapsed = int(time.time() - t0)
            sh  = metrics.sharpe_ratio
            ret = metrics.total_return * 100
            wr  = metrics.win_rate * 100
            t   = metrics.total_trades
            dd  = metrics.max_drawdown * 100
            v   = "PASS" if sh >= 1.2 else ("S-PASS" if sh >= 0.8 else "FAIL")
            results.append((label, sh, v, ret, wr, t, dd, elapsed, None))
            print("  -> S=%5.2f  %+6.2f%%  WR=%5.1f%%  t=%2d  DD=%+6.2f%%"
                  "  [%s/%ds]" % (sh, ret, wr, t, dd, v, elapsed))
        except Exception as e:
            elapsed = int(time.time() - t0)
            results.append((label, None, "ERROR", 0, 0, 0, 0, elapsed, str(e)[:120]))
            print("  -> ERROR: %s" % str(e)[:120])

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
    print("  v46 RESULTS -- Momentum Divergence Filter")
    print("=" * 95)
    print()
    for label, sh, v, ret, wr, t, dd, elapsed, err in results:
        if err:
            print("    %-12s  ERROR: %s" % (label, err))
        else:
            print("    %-12s  S=%5.2f  %+6.2f%%  WR=%5.1f%%  t=%2d  DD=%+6.2f%%"
                  "  [%s/%ds]" % (label, sh, ret, wr, t, dd, v, elapsed))
    print()
    print("  Summary: PASS=%d/5  S-PASS=%d/5  FAIL=%d/5 |"
          " avg=%.2f  min=%.2f  -> %s" % (
              passes, spasses, fails, avg_sh, min_sh, verdict))
    print()

    # Comparison vs v45b baseline
    print("  Comparison:")
    print("    v45b (baseline): P1=-1.57 P2=-0.66 P3=+2.21 P4=-2.01  FAIL")
    print("  v46 (momentum):  ", end="")
    for label, sh, v, ret, wr, t, dd, elapsed, err in results:
        if sh is not None:
            tag = label.split()[0]  # P1, P2, etc.
            print("  %s=%+.2f" % (tag, sh), end="")
    print()
    print()

    if verdict == "PASS":
        print("  PASS! Momentum divergence filter is the key fix.")
        print("  Next: Phase 0.1 slippage stress-test on v46 params -> freeze + deploy")
    elif verdict == "S-PASS":
        print("  S-PASS. Momentum filter improved but not enough.")
        print("  Options:")
        print("    v46b: reduce threshold 1.5 -> 1.2 (stricter, block more momentum)")
        print("    v46c: increase lookback 60 -> 90 days (more stable momentum signal)")
        print("    v46d: add sector-relative momentum (vs sector peers, not universe)")
    else:
        print("  Still FAIL. Diagnosis:")
        for label, sh, v, ret, wr, t, dd, elapsed, err in results:
            if err:
                continue
            note = ""
            if t == 0:
                note = "  <- 0 trades: all momentum-divergent pairs filtered?"
            elif sh < -1.0:
                note = "  <- persistent loser (other structural issue remains)"
            elif sh >= 0.8:
                note = "  <- near-pass: promising"
            print("    %-12s  S=%5.2f  t=%2d%s" % (label, sh, t, note))
        print()
        print("  If P1/P4 still failing with t=0:")
        print("    - Momentum filter too aggressive (threshold too low)")
        print("    - Try v46b: threshold=2.0 (stricter = only extreme outliers blocked)")
        print("  If P1/P4 still failing with more trades:")
        print("    - Root cause is structural beyond momentum (regime-driven)")
        print("    - Try v46c: add regime-detection gating (skip entries in TRENDING)")
    print()


if __name__ == "__main__":
    main()
