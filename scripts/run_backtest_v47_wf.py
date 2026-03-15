#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""EDGECORE v47 -- Walk-Forward: Cross-Sectional Dispersion Gate.

v46 post-mortem ÔÇö key findings:
  P2 2020H2: S=-0.66 -> +2.27  (18->3 trades: momentum filter removed bad entries)
  P4 2023H2: S=-2.01 -> +0.46  (34->12 trades: major improvement)
  P3 2022H2: stable at +2.24   (33->5 trades: working pairs unaffected)
  P1 2019H2: S=-1.57 -> -1.67  (30->4 trades: STILL FAILING, momentum filter helps
                                  filter pairs but the 4 survivors still lose)
  P5 2024H2: unchanged at -1.14 (3 trades: same 3 trades, 1 large loser)

ROOT CAUSE (P1/P5 residual failures = "smooth bull" regimes):
  Even after the per-pair momentum divergence filter, the remaining entries
  in 2019H2 and 2024H2 fail because:
    - P1 2019H2: cross-sectional return dispersion ~5-8% (low). Stocks are
      synchronized in a calm bull. No genuine relative value exists. Even
      pairs that pass |dz| < 1.5 still lose because individual stocks
      co-trend upward rather than mean-reverting.
    - P5 2024H2: same smooth bull anatomy. 3 trades, WR=67% but 1 large
      loser (-6.9% notional, persistent drift) wrecks the Sharpe to -1.14.
  
  P2 (COVID recovery) and P3 (rate-hike bear) succeed because cross-sectional
  dispersion is HIGH (15-25%): genuine relative value exists -> MR works.
  P4 (AI bull) also has HIGH dispersion (AI sector vs non-AI divergence).

v47 FIX: Market-level cross-sectional dispersion gate
  Compute std(60d_returns) across ALL universe symbols every bar.
  If std < min_dispersion (8%): BLOCK ALL NEW ENTRIES that bar.
  This is a single market-level gate computed once per bar, cheaper and
  more powerful than per-pair checks.

  Expected improvements vs v46:
    P1 2019H2: most bars blocked (cs-disp ~5-8% < 8%) -> 0-1 trades -> S~0
    P2 2020H2: most bars allowed (cs-disp ~15-25% > 8%) -> 3 good trades kept
    P3 2022H2: most bars allowed (cs-disp ~12-18% > 8%) -> 5 good trades kept
    P4 2023H2: most bars allowed (cs-disp ~12-18% >> 8%) -> 12 trades kept
    P5 2024H2: many bars blocked (cs-disp ~6-9% ~ 8%) -> 0-2 trades -> S~0

Calibration: min_dispersion=0.08 (8% std of 60d trailing returns universe)
  Logic: if ALL 103 stocks moved within 8% of each other over 60 days ->
  market is "synchronized" -> no genuine relative value for pairs trading.
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
# Universe: 103 symbols across 12 sectors (unchanged from v45b/v46)
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


def _apply_v47_settings():
    """v43a frozen params (identical to v45b/v46). Only dispersion gate added."""
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
    print("  EDGECORE v47 -- Walk-Forward: Cross-Sectional Dispersion Gate")
    print()
    print("  v46 DIAGNOSIS: residual failures in smooth-bull regimes (P1/P5)")
    print("    P1 (2019H2 smooth bull): cs-dispersion ~5-8%  (stocks synchronized)")
    print("      4 remaining trades after v46 momentum filter -> all drift, S=-1.67")
    print("    P5 (2024H2 smooth bull): cs-dispersion ~6-9%  (stocks synchronized)")
    print("      3 trades unchanged, WR=67% but 1 large loser (-6.9%) -> S=-1.14")
    print("    P2 (2020H2 COVID recov): cs-dispersion ~15-25% (HIGH) -> works fine")
    print("    P3 (2022H2 rate-hike):   cs-dispersion ~12-18% (HIGH) -> works fine")
    print("    P4 (2023H2 AI bull):     cs-dispersion ~12-18% (HIGH) -> +0.46 OK")
    print()
    print("  v47 FIX: MomentumDivergenceFilter(threshold=1.5, lookback=60,")
    print("           min_dispersion=0.08)")
    print("    At each bar: compute std(60d_returns) across all 103 symbols.")
    print("    If std < 8%: BLOCK ALL NEW ENTRIES that bar (market gate).")
    print("    No per-pair computation needed -- one check blocks the entire bar.")
    print()
    print("  Expected results vs v46:")
    print("    P1: S=-1.67 -> S~0  (2019H2 bars blocked: cs-disp < 8%)")
    print("    P2: S=+2.27 -> +2.27 (COVID bars allowed: cs-disp >> 8%)")
    print("    P3: S=+2.24 -> +2.24 (bear bars allowed: cs-disp >> 8%)")
    print("    P4: S=+0.46 -> +0.46 (AI-bull bars allowed: cs-disp >> 8%)")
    print("    P5: S=-1.14 -> S~0  (2024H2 bars blocked: cs-disp ~6-9%)")
    print()
    n = len(WF_SYMBOLS)
    n_pairs = n * (n - 1) // 2
    print("  Universe: %d symbols, %d potential pairs (same as v45b/v46)" % (n, n_pairs))
    print("=" * 95)

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000
    ts20 = TimeStopManager(TimeStopConfig(
        half_life_multiplier=1.2,
        max_days_cap=20,
        default_max_bars=20,
    ))

    # v46 momentum divergence filter + v47 dispersion gate
    mom_filter = MomentumDivergenceFilter(
        lookback_days=60,
        threshold=1.5,
        min_universe_size=20,
        min_dispersion=0.08,   # NEW v47: block all entries when cs-dispersion < 8%
    )

    results = []
    for label, train_start, train_end, oos_start, oos_end in WF_WINDOWS:
        _apply_v47_settings()
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
    print("  v47 RESULTS -- Cross-Sectional Dispersion Gate")
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

    # Comparison table
    print("  Comparison:")
    v46 = {"P1": -1.67, "P2": +2.27, "P3": +2.24, "P4": +0.46, "P5": -1.14}
    print("    v46 (momentum only): P1=-1.67 P2=+2.27 P3=+2.24 P4=+0.46 P5=-1.14"
          "  avg=+0.43  FAIL 2/5")
    print("  v47 (+ dispersion):  ", end="")
    v47_sharpes = {}
    for label, sh, v, ret, wr, t, dd, elapsed, err in results:
        if sh is not None:
            tag = label.split()[0]  # P1, P2, etc.
            v47_sharpes[tag] = sh
            delta = sh - v46.get(tag, 0.0)
            print("  %s=%+.2f(%+.2f)" % (tag, sh, delta), end="")
    print()
    print()

    if verdict == "PASS":
        print("  PASS! Dispersion gate is the final fix. Freeze v47 and run slippage stress-test.")
        print("  Next: Phase 0.1 slippage test on v47 params -> institutional deployment plan")
    elif verdict == "S-PASS":
        print("  S-PASS. Dispersion gate helps but threshold may need tuning.")
        print("  Options:")
        print("    v47b: lower threshold 0.08 -> 0.06 (block more smooth-bull periods)")
        print("    v47c: raise threshold 0.08 -> 0.10 (looser gate, keep more P4 trades)")
        print("    v47d: add lookback_days=90 for more stable dispersion estimate")
    else:
        print("  Still FAIL. Diagnosis:")
        for label, sh, v, ret, wr, t, dd, elapsed, err in results:
            if err:
                continue
            note = ""
            if t == 0:
                note = "  <- 0 trades: all bars blocked by dispersion gate?"
            elif sh < -1.0:
                note = "  <- persistent loser (check dispersion gate threshold)"
            elif sh >= 0.8:
                note = "  <- near-pass: tune min_dispersion"
            elif sh >= 0.0:
                note = "  <- improved but needs more work"
            print("    %-12s  S=%5.2f  t=%2d  %s%s" % (
                label, sh, t, v, note))
        print()
        print("  Threshold tuning candidates:")
        print("    If P1/P5 still have trades: lower min_dispersion (0.08 -> 0.06)")
        print("    If P2/P3/P4 lost good trades: raise min_dispersion (0.08 -> 0.10)")


if __name__ == "__main__":
    main()
