#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P5 2024H2 standalone ÔÇö v45b params (same as run_backtest_v45_wf.py).

Re-runs only P5 to get the final v45b result that was lost (output file >50MB).
Uses cached data (no IBKR re-fetch needed).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager

# Same universe as v45b (103 symbols)
WF_SYMBOLS = [
    "SPY",
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO", "XLK",
    "INTC", "QCOM", "TXN", "CRM", "ORCL", "ACN", "CSCO",
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    "BLK", "AXP", "USB", "PNC", "COF", "BK", "TFC",
    "XOM", "CVX", "COP", "EOG",
    "SLB", "VLO", "MPC", "PSX", "OXY",
    "KO", "PEP", "PG", "CL", "WMT", "MCD",
    "COST", "MDLZ", "GIS", "PM", "MO",
    "CAT", "HON", "DE", "GE", "RTX",
    "MMM", "UPS", "BA", "ITW", "LMT", "FDX",
    "NEE", "DUK", "SO",
    "AEP", "EXC", "WEC",
    "JNJ", "PFE", "UNH", "MRK", "ABBV",
    "TMO", "ABT", "DHR", "MDT", "CVS", "CI", "BMY",
    "AMZN", "TSLA", "HD", "NKE", "LOW", "TGT", "SBUX", "F", "GM",
    "LIN", "APD", "ECL", "NEM", "FCX",
    "PLD", "AMT", "SPG", "EQIX",
    "T", "VZ", "CMCSA", "DIS", "NFLX",
]

WF_SECTOR_MAP = {
    "AAPL": "technology", "MSFT": "technology", "GOOGL": "technology",
    "META": "technology", "NVDA": "technology", "AMD": "technology",
    "AVGO": "technology", "XLK": "technology",
    "INTC": "technology", "QCOM": "technology", "TXN": "technology",
    "CRM": "technology", "ORCL": "technology", "ACN": "technology",
    "CSCO": "technology",
    "JPM": "financials", "GS": "financials", "BAC": "financials",
    "MS": "financials", "WFC": "financials", "C": "financials",
    "SCHW": "financials",
    "BLK": "financials", "AXP": "financials", "USB": "financials",
    "PNC": "financials", "COF": "financials", "BK": "financials",
    "TFC": "financials",
    "XOM": "energy", "CVX": "energy", "COP": "energy", "EOG": "energy",
    "SLB": "energy", "VLO": "energy", "MPC": "energy",
    "PSX": "energy", "OXY": "energy",
    "KO": "consumer_staples", "PEP": "consumer_staples",
    "PG": "consumer_staples", "CL": "consumer_staples",
    "WMT": "consumer_staples", "MCD": "consumer_staples",
    "COST": "consumer_staples", "MDLZ": "consumer_staples",
    "GIS": "consumer_staples", "PM": "consumer_staples",
    "MO": "consumer_staples",
    "CAT": "industrials", "HON": "industrials", "DE": "industrials",
    "GE": "industrials", "RTX": "industrials",
    "MMM": "industrials", "UPS": "industrials", "BA": "industrials",
    "ITW": "industrials", "LMT": "industrials", "FDX": "industrials",
    "NEE": "utilities", "DUK": "utilities", "SO": "utilities",
    "AEP": "utilities", "EXC": "utilities", "WEC": "utilities",
    "JNJ": "healthcare", "PFE": "healthcare", "UNH": "healthcare",
    "MRK": "healthcare", "ABBV": "healthcare",
    "TMO": "healthcare", "ABT": "healthcare", "DHR": "healthcare",
    "MDT": "healthcare", "CVS": "healthcare", "CI": "healthcare",
    "BMY": "healthcare",
    "AMZN": "consumer_discretionary", "TSLA": "consumer_discretionary",
    "HD": "consumer_discretionary", "NKE": "consumer_discretionary",
    "LOW": "consumer_discretionary", "TGT": "consumer_discretionary",
    "SBUX": "consumer_discretionary", "F": "consumer_discretionary",
    "GM": "consumer_discretionary",
    "LIN": "materials", "APD": "materials", "ECL": "materials",
    "NEM": "materials", "FCX": "materials",
    "PLD": "real_estate", "AMT": "real_estate",
    "SPG": "real_estate", "EQIX": "real_estate",
    "T": "communication", "VZ": "communication", "CMCSA": "communication",
    "DIS": "communication", "NFLX": "communication",
    "SPY": "benchmark",
}


def _apply_v45_settings():
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
    print("=" * 80)
    print("  v45b P5 2024H2 -- standalone re-run")
    print("  train 2023-01-03 -> 2024-07-01 | OOS 2024-07-01 -> 2025-01-01")
    print("  (P1-P4 already confirmed: S=-1.57/-0.66/+2.21/-2.01)")
    print("=" * 80)

    _apply_v45_settings()

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000
    ts20 = TimeStopManager(TimeStopConfig(
        half_life_multiplier=1.2,
        max_days_cap=20,
        default_max_bars=20,
    ))

    t0 = time.time()
    print()
    print("  Running P5 2024H2 ...")
    try:
        metrics = runner.run_unified(
            symbols=WF_SYMBOLS,
            start_date="2023-01-03",
            end_date="2025-01-01",
            oos_start_date="2024-07-01",
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

        print()
        print("  P5 2024H2  S=%5.2f  %+6.2f%%  WR=%5.1f%%  t=%2d  DD=%+6.2f%%  [%s/%ds]" % (
            sh, ret, wr, t, dd, v, elapsed))
        print()

        # Full v45b summary
        known = [
            ("P1 2019H2", -1.57, "FAIL",  -5.60, 0.0, 30, -7.09),
            ("P2 2020H2", -0.66, "FAIL",  -2.03, 0.0, 18, -4.27),
            ("P3 2022H2", +2.21, "PASS", +10.62, 0.0, 33, -2.71),
            ("P4 2023H2", -2.01, "FAIL",  -4.14, 0.0, 34, -4.07),
        ]
        print("  v45b COMPLETE RESULTS:")
        print("  " + "-" * 65)
        for lbl, s, vv, r, w, nt, d in known:
            print("    %-12s  S=%5.2f  %+6.2f%%  t=%2d  DD=%+6.2f%%  [%s]" % (
                lbl, s, r, nt, d, vv))
        print("    %-12s  S=%5.2f  %+6.2f%%  t=%2d  DD=%+6.2f%%  [%s]" % (
            "P5 2024H2", sh, ret, t, dd, v))
        print("  " + "-" * 65)
        all_s = [-1.57, -0.66, 2.21, -2.01, sh]
        avg = sum(all_s) / len(all_s)
        passes_total = sum(1 for x in all_s if x >= 1.2)
        spasses_total = sum(1 for x in all_s if 0.8 <= x < 1.2)
        overall = "PASS" if passes_total >= 4 else ("S-PASS" if passes_total + spasses_total >= 4 else "FAIL")
        print("  avg=%.2f  PASS=%d/5  -> %s" % (avg, passes_total, overall))
        print()

    except Exception as e:
        print("  ERROR: %s" % e)
        raise


if __name__ == "__main__":
    main()
