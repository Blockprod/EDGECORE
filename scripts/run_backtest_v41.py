#!/usr/bin/env python
"""EDGECORE v41 -- Phase 3 (Revised): Daily Data, Lower Entry Threshold.

Phase 3 post-mortem (v40/v40b):
  Hourly cointegration = structural failure.  Root causes:
  1. Cointegration is a DAILY phenomenon (20-60 day mean-reversion).
     Trading it at hourly scale with TimeStop=28 bars (4 days)
     cuts positions systematically before the spread reverts -> WR=17%.
  2. Regime signals (MA50/MA200) are bar-count based: at hourly scale
     MA50 = 7 calendar days (not 50). Regime detection is completely wrong.
  3. CONCLUSION: 200+ trades/year via hourly bars is NOT achievable with
     this daily cointegration architecture.

Phase 3 Revised Strategy -- v41:
  Keep proven daily architecture (v37 WR=65.2%, S=1.67).
  Increase trade frequency by LOWERING entry threshold:
    v37:  entry_z=1.8  -> 23 trades/3yr  (~8/yr)
    v41a: entry_z=1.4  -> target ~40-60/yr
    v41b: entry_z=1.2  -> target ~80-120/yr

  Additional frequency levers (all non-breaking):
    - pair_rediscovery_interval: 2d -> 1d (more frequent pair search)
    - exit_z_score: 0.2 -> 0.35 (exit closer to mean = faster cycle)
    - max_half_life: 60d -> 45d (require faster-reverting pairs)

  Leverage: 2.5x (v39 optimal, preserved).

Phase 3 Revised targets:
  Trades >= 50/year    (realistic with daily cointegration)
  Sharpe >= 1.5
  MaxDD  > -8%

v39 baseline: +42.55%  S=1.82  PF=9.06  WR=65.2%  23t  DD=-2.69%  (2.5x)
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager

# -- Universe: exact v37/v39 core (39 symbols) --------------------------------
V41_SYMBOLS = [
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

V41_SECTOR_MAP = {
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


def _run_case(runner, label, entry_z, exit_z, rediscovery, half_life_cap, time_stop, leverage):
    """Run one parameter configuration and return metrics."""
    s = get_settings()
    # Reset to v37 base
    s.strategy.lookback_window             = 120
    s.strategy.additional_lookback_windows = [63]
    s.strategy.entry_z_score               = entry_z
    s.strategy.exit_z_score                = exit_z
    s.strategy.entry_z_min_spread          = 0.30
    s.strategy.z_score_stop                = 2.5
    s.strategy.min_correlation             = 0.65
    s.strategy.max_half_life               = half_life_cap
    s.strategy.max_position_loss_pct       = 0.03
    s.strategy.internal_max_drawdown_pct   = 0.12
    s.strategy.use_kalman                  = True
    s.strategy.bonferroni_correction       = True
    s.strategy.johansen_confirmation       = True
    s.strategy.newey_west_consensus        = True
    s.strategy.weekly_zscore_entry_gate    = 0.3
    s.strategy.regime_directional_filter   = False
    s.strategy.trend_long_sizing           = 0.75
    s.strategy.disable_shorts_in_bull_trend = False
    s.strategy.short_sizing_multiplier     = 0.50
    s.regime.enabled           = True
    s.regime.ma_fast           = 50
    s.regime.ma_slow           = 200
    s.regime.vol_threshold     = 0.18
    s.regime.vol_window        = 20
    s.regime.neutral_band_pct  = 0.02
    s.regime.trend_favorable_sizing = 1.0
    s.regime.neutral_sizing    = 0.70
    s.momentum.enabled         = True
    s.momentum.lookback        = 20
    s.momentum.weight          = 0.30
    s.momentum.min_strength    = 1.0
    s.momentum.max_boost       = 1.0
    s.pair_blacklist.enabled                 = True
    s.pair_blacklist.max_consecutive_losses  = 5
    s.pair_blacklist.cooldown_days           = 10
    s.risk.max_concurrent_positions          = 10
    if hasattr(s.strategy, 'fdr_q_level'):
        s.strategy.fdr_q_level = 0.25

    runner.config.initial_capital = 100_000
    t0 = time.time()
    metrics = runner.run_unified(
        symbols=V41_SYMBOLS,
        start_date="2023-03-04",
        end_date="2026-03-04",
        sector_map=V41_SECTOR_MAP,
        pair_rediscovery_interval=rediscovery,
        allocation_per_pair_pct=50.0,
        max_position_loss_pct=0.07,
        max_portfolio_heat=3.0,
        time_stop=time_stop,
        leverage_multiplier=leverage,
    )
    elapsed = time.time() - t0

    ret = metrics.total_return * 100
    sh  = metrics.sharpe_ratio
    pf  = metrics.profit_factor
    wr  = metrics.win_rate * 100
    t   = metrics.total_trades
    dd  = metrics.max_drawdown * 100
    tpy = t / 3.0  # 3-year window

    print("  %-22s  %+6.2f%%  S=%5.2f  PF=%5.2f  WR=%4.1f%%  t=%2d (~%3.0f/yr)  DD=%5.2f%%  [%ds]" % (
        label, ret, sh, pf, wr, t, tpy, dd, int(elapsed)))
    return metrics, tpy


def main():
    print("=" * 90)
    print("  EDGECORE v41 -- Phase 3 Revised: Daily Data, Lower Entry Threshold")
    print("  Exploring entry_z sweep (1.0 -> 1.8) + pair_rediscovery sweep")
    print("  Universe: 39 symbols (v37 core) | Window: 2023-03-04 -> 2026-03-04")
    print("  Leverage: 2.5x (v39 optimal)")
    print()
    print("  Phase 3 post-mortem lessons:")
    print("    v40  (synthetic hourly): WR=16.7%  S=-1.38  FAIL (BB no MR)")
    print("    v40b (real IBKR hourly): WR=17.4%  S=-2.19  FAIL (daily coint != hourly)")
    print("    Root cause: cointegration is daily -> TimeStop 4d cuts before reversion")
    print()
    print("  Phase 3 Revised target: Trades >= 50/yr  Sharpe >= 1.5")
    print("  v39 baseline:            23t/3yr (~8/yr)  S=1.82  +42.55%  DD=-2.69%")
    print("=" * 90)
    print()

    runner = BacktestRunner()

    # Header
    print("  %-22s  %7s  %6s  %6s  %6s  %11s  %7s" % (
        "Config", "Return", "Sharpe", "PF", "WR", "Trades", "MaxDD"))
    print("  " + "-" * 86)

    # v39 baseline (reproduced for comparison)
    ts20 = TimeStopManager(TimeStopConfig(half_life_multiplier=1.2, max_days_cap=20, default_max_bars=20))
    ts15 = TimeStopManager(TimeStopConfig(half_life_multiplier=1.2, max_days_cap=15, default_max_bars=15))
    ts10 = TimeStopManager(TimeStopConfig(half_life_multiplier=1.2, max_days_cap=10, default_max_bars=10))

    results = []

    # v39 baseline (entry_z=1.8, rediscovery=2)
    m, tpy = _run_case(runner, "v39 baseline (1.8)", 1.8, 0.2, 2, 60, ts20, 2.5)
    results.append(("v39 baseline", m, tpy))

    # v41a: entry_z=1.6 (modest reduction)
    m, tpy = _run_case(runner, "v41a entry_z=1.6", 1.6, 0.2, 2, 60, ts20, 2.5)
    results.append(("v41a z=1.6", m, tpy))

    # v41b: entry_z=1.4
    m, tpy = _run_case(runner, "v41b entry_z=1.4", 1.4, 0.2, 2, 60, ts20, 2.5)
    results.append(("v41b z=1.4", m, tpy))

    # v41c: entry_z=1.2
    m, tpy = _run_case(runner, "v41c entry_z=1.2", 1.2, 0.2, 2, 60, ts20, 2.5)
    results.append(("v41c z=1.2", m, tpy))

    # v41d: entry_z=1.0 (very aggressive)
    m, tpy = _run_case(runner, "v41d entry_z=1.0", 1.0, 0.2, 2, 60, ts20, 2.5)
    results.append(("v41d z=1.0", m, tpy))

    # v41e: entry_z=1.4 + faster rediscovery (every 1 day)
    m, tpy = _run_case(runner, "v41e z=1.4 rd=1", 1.4, 0.2, 1, 60, ts20, 2.5)
    results.append(("v41e z=1.4 rd=1", m, tpy))

    # v41f: entry_z=1.4 + faster exit (0.35) + shorter TS
    m, tpy = _run_case(runner, "v41f z=1.4 ex=0.35 ts15", 1.4, 0.35, 1, 45, ts15, 2.5)
    results.append(("v41f z=1.4 fast", m, tpy))

    # v41g: entry_z=1.2 + faster exit + shorter TS
    m, tpy = _run_case(runner, "v41g z=1.2 ex=0.35 ts10", 1.2, 0.35, 1, 45, ts10, 2.5)
    results.append(("v41g z=1.2 fast", m, tpy))

    print()
    print("=" * 90)
    print("  PHASE 3 REVISED SUMMARY")
    print("=" * 90)
    print()

    # Find best Phase 3 candidate
    best = None
    for label, m, tpy in results:
        sh  = m.sharpe_ratio
        dd  = m.max_drawdown * 100
        wr  = m.win_rate * 100
        ret = m.total_return * 100
        p3_pass = (tpy >= 50 and sh >= 1.5 and dd > -8.0)
        p3_str  = "PASS" if p3_pass else "miss"
        if p3_pass and (best is None or sh > best[1].sharpe_ratio):
            best = (label, m, tpy)
        print("  %-22s  trades=~%.0f/yr  S=%.2f  WR=%.1f%%  ret=%+.2f%%  P3=%s" % (
            label, tpy, sh, wr, ret, p3_str))

    print()
    if best:
        label, m, tpy = best
        print("  >>> Best Phase 3 candidate: %s <<<" % label)
        print("       Trades ~%.0f/yr  Sharpe %.2f  WR %.1f%%  Return %+.2f%%" % (
            tpy, m.sharpe_ratio, m.win_rate * 100, m.total_return * 100))
        print("       -> Use this config as v42 baseline")
    else:
        print("  >>> No config passes all Phase 3 targets at once <<<")
        # Find best Sharpe with positive direction
        pos = [(l, m, t) for l, m, t in results if m.sharpe_ratio > 0]
        if pos:
            best_s = max(pos, key=lambda x: x[1].sharpe_ratio)
            print("  >>> Best positive Sharpe: %s  S=%.2f  trades=~%.0f/yr <<<" % (
                best_s[0], best_s[1].sharpe_ratio, best_s[2]))
            print("       -> Phase 3 target may need to be revised to: Trades>=30/yr")
        else:
            print("  >>> All configs negative Sharpe -- investigate pair quality <<<")
    print()


if __name__ == "__main__":
    main()
