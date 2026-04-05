<<<<<<< HEAD
﻿#!/usr/bin/env python
"""Run v47 P4 + P5 only (P1/P2/P3 already completed)."""

=======
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run v47 P4 + P5 only (P1/P2/P3 already completed)."""
>>>>>>> origin/main
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager
from pair_selection.filters import MomentumDivergenceFilter

WF_SYMBOLS = [
    "SPY",
<<<<<<< HEAD
    "AAPL",
    "MSFT",
    "GOOGL",
    "META",
    "NVDA",
    "AMD",
    "AVGO",
    "XLK",
    "INTC",
    "QCOM",
    "TXN",
    "CRM",
    "ORCL",
    "ACN",
    "CSCO",
    "JPM",
    "GS",
    "BAC",
    "MS",
    "WFC",
    "C",
    "SCHW",
    "BLK",
    "AXP",
    "USB",
    "PNC",
    "COF",
    "BK",
    "TFC",
    "XOM",
    "CVX",
    "COP",
    "EOG",
    "SLB",
    "VLO",
    "MPC",
    "PSX",
    "OXY",
    "KO",
    "PEP",
    "PG",
    "CL",
    "WMT",
    "MCD",
    "COST",
    "MDLZ",
    "GIS",
    "PM",
    "MO",
    "CAT",
    "HON",
    "DE",
    "GE",
    "RTX",
    "MMM",
    "UPS",
    "BA",
    "ITW",
    "LMT",
    "FDX",
    "NEE",
    "DUK",
    "SO",
    "AEP",
    "EXC",
    "WEC",
    "JNJ",
    "PFE",
    "UNH",
    "MRK",
    "ABBV",
    "TMO",
    "ABT",
    "DHR",
    "MDT",
    "CVS",
    "CI",
    "BMY",
    "AMZN",
    "TSLA",
    "HD",
    "NKE",
    "LOW",
    "TGT",
    "SBUX",
    "F",
    "GM",
    "LIN",
    "APD",
    "ECL",
    "NEM",
    "FCX",
    "PLD",
    "AMT",
    "SPG",
    "EQIX",
    "T",
    "VZ",
    "CMCSA",
    "DIS",
    "NFLX",
]

WF_SECTOR_MAP = {
    "AAPL": "technology",
    "MSFT": "technology",
    "GOOGL": "technology",
    "META": "technology",
    "NVDA": "technology",
    "AMD": "technology",
    "AVGO": "technology",
    "XLK": "technology",
    "INTC": "technology",
    "QCOM": "technology",
    "TXN": "technology",
    "CRM": "technology",
    "ORCL": "technology",
    "ACN": "technology",
    "CSCO": "technology",
    "JPM": "financials",
    "GS": "financials",
    "BAC": "financials",
    "MS": "financials",
    "WFC": "financials",
    "C": "financials",
    "SCHW": "financials",
    "BLK": "financials",
    "AXP": "financials",
    "USB": "financials",
    "PNC": "financials",
    "COF": "financials",
    "BK": "financials",
    "TFC": "financials",
    "XOM": "energy",
    "CVX": "energy",
    "COP": "energy",
    "EOG": "energy",
    "SLB": "energy",
    "VLO": "energy",
    "MPC": "energy",
    "PSX": "energy",
    "OXY": "energy",
    "KO": "consumer_staples",
    "PEP": "consumer_staples",
    "PG": "consumer_staples",
    "CL": "consumer_staples",
    "WMT": "consumer_staples",
    "MCD": "consumer_staples",
    "COST": "consumer_staples",
    "MDLZ": "consumer_staples",
    "GIS": "consumer_staples",
    "PM": "consumer_staples",
    "MO": "consumer_staples",
    "CAT": "industrials",
    "HON": "industrials",
    "DE": "industrials",
    "GE": "industrials",
    "RTX": "industrials",
    "MMM": "industrials",
    "UPS": "industrials",
    "BA": "industrials",
    "ITW": "industrials",
    "LMT": "industrials",
    "FDX": "industrials",
    "NEE": "utilities",
    "DUK": "utilities",
    "SO": "utilities",
    "AEP": "utilities",
    "EXC": "utilities",
    "WEC": "utilities",
    "JNJ": "healthcare",
    "PFE": "healthcare",
    "UNH": "healthcare",
    "MRK": "healthcare",
    "ABBV": "healthcare",
    "TMO": "healthcare",
    "ABT": "healthcare",
    "DHR": "healthcare",
    "MDT": "healthcare",
    "CVS": "healthcare",
    "CI": "healthcare",
    "BMY": "healthcare",
    "AMZN": "consumer_discretionary",
    "TSLA": "consumer_discretionary",
    "HD": "consumer_discretionary",
    "NKE": "consumer_discretionary",
    "LOW": "consumer_discretionary",
    "TGT": "consumer_discretionary",
    "SBUX": "consumer_discretionary",
    "F": "consumer_discretionary",
    "GM": "consumer_discretionary",
    "LIN": "materials",
    "APD": "materials",
    "ECL": "materials",
    "NEM": "materials",
    "FCX": "materials",
    "PLD": "real_estate",
    "AMT": "real_estate",
    "SPG": "real_estate",
    "EQIX": "real_estate",
    "T": "communication",
    "VZ": "communication",
    "CMCSA": "communication",
    "DIS": "communication",
    "NFLX": "communication",
=======
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO", "XLK",
    "INTC", "QCOM", "TXN", "CRM", "ORCL", "ACN", "CSCO",
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    "BLK", "AXP", "USB", "PNC", "COF", "BK", "TFC",
    "XOM", "CVX", "COP", "EOG", "SLB", "VLO", "MPC", "PSX", "OXY",
    "KO", "PEP", "PG", "CL", "WMT", "MCD", "COST", "MDLZ", "GIS", "PM", "MO",
    "CAT", "HON", "DE", "GE", "RTX", "MMM", "UPS", "BA", "ITW", "LMT", "FDX",
    "NEE", "DUK", "SO", "AEP", "EXC", "WEC",
    "JNJ", "PFE", "UNH", "MRK", "ABBV", "TMO", "ABT", "DHR", "MDT", "CVS", "CI", "BMY",
    "AMZN", "TSLA", "HD", "NKE", "LOW", "TGT", "SBUX", "F", "GM",
    "LIN", "APD", "ECL", "NEM", "FCX",
    "PLD", "AMT", "SPG", "EQIX",
    "T", "VZ", "CMCSA", "DIS", "NFLX",
]

WF_SECTOR_MAP = {
    "AAPL": "technology", "MSFT": "technology", "GOOGL": "technology",
    "META": "technology", "NVDA": "technology", "AMD": "technology",
    "AVGO": "technology", "XLK": "technology", "INTC": "technology",
    "QCOM": "technology", "TXN": "technology", "CRM": "technology",
    "ORCL": "technology", "ACN": "technology", "CSCO": "technology",
    "JPM": "financials", "GS": "financials", "BAC": "financials",
    "MS": "financials", "WFC": "financials", "C": "financials",
    "SCHW": "financials", "BLK": "financials", "AXP": "financials",
    "USB": "financials", "PNC": "financials", "COF": "financials",
    "BK": "financials", "TFC": "financials",
    "XOM": "energy", "CVX": "energy", "COP": "energy", "EOG": "energy",
    "SLB": "energy", "VLO": "energy", "MPC": "energy", "PSX": "energy", "OXY": "energy",
    "KO": "consumer_staples", "PEP": "consumer_staples", "PG": "consumer_staples",
    "CL": "consumer_staples", "WMT": "consumer_staples", "MCD": "consumer_staples",
    "COST": "consumer_staples", "MDLZ": "consumer_staples", "GIS": "consumer_staples",
    "PM": "consumer_staples", "MO": "consumer_staples",
    "CAT": "industrials", "HON": "industrials", "DE": "industrials",
    "GE": "industrials", "RTX": "industrials", "MMM": "industrials",
    "UPS": "industrials", "BA": "industrials", "ITW": "industrials",
    "LMT": "industrials", "FDX": "industrials",
    "NEE": "utilities", "DUK": "utilities", "SO": "utilities",
    "AEP": "utilities", "EXC": "utilities", "WEC": "utilities",
    "JNJ": "healthcare", "PFE": "healthcare", "UNH": "healthcare",
    "MRK": "healthcare", "ABBV": "healthcare", "TMO": "healthcare",
    "ABT": "healthcare", "DHR": "healthcare", "MDT": "healthcare",
    "CVS": "healthcare", "CI": "healthcare", "BMY": "healthcare",
    "AMZN": "consumer_discretionary", "TSLA": "consumer_discretionary",
    "HD": "consumer_discretionary", "NKE": "consumer_discretionary",
    "LOW": "consumer_discretionary", "TGT": "consumer_discretionary",
    "SBUX": "consumer_discretionary", "F": "consumer_discretionary",
    "GM": "consumer_discretionary",
    "LIN": "materials", "APD": "materials", "ECL": "materials",
    "NEM": "materials", "FCX": "materials",
    "PLD": "real_estate", "AMT": "real_estate", "SPG": "real_estate", "EQIX": "real_estate",
    "T": "communication", "VZ": "communication", "CMCSA": "communication",
    "DIS": "communication", "NFLX": "communication",
>>>>>>> origin/main
    "SPY": "benchmark",
}

WINDOWS = [
    ("P4 2023H2", "2022-01-03", "2023-07-01", "2023-07-01", "2024-01-01"),
    ("P5 2024H2", "2023-01-03", "2024-07-01", "2024-07-01", "2025-01-01"),
]

<<<<<<< HEAD

def _apply_settings():
    s = get_settings()
    s.strategy.lookback_window = 120
    s.strategy.additional_lookback_windows = [63]
    s.strategy.entry_z_score = 1.6
    s.strategy.exit_z_score = 0.2
    s.strategy.entry_z_min_spread = 0.30
    s.strategy.z_score_stop = 2.5
    s.strategy.min_correlation = 0.65
    s.strategy.max_half_life = 60
    s.strategy.max_position_loss_pct = 0.03
    s.strategy.internal_max_drawdown_pct = 0.12
    s.strategy.use_kalman = True
    s.strategy.bonferroni_correction = True
    s.strategy.johansen_confirmation = True
    s.strategy.newey_west_consensus = True
    s.strategy.weekly_zscore_entry_gate = 0.3
    s.strategy.trend_long_sizing = 0.75
    s.strategy.disable_shorts_in_bull_trend = False
    s.strategy.short_sizing_multiplier = 0.50
    s.momentum.enabled = True
    s.momentum.lookback = 20
    s.momentum.weight = 0.30
    s.momentum.min_strength = 1.0
    s.momentum.max_boost = 1.0
    s.pair_blacklist.enabled = True
    s.pair_blacklist.max_consecutive_losses = 5
    s.pair_blacklist.cooldown_days = 10
    s.risk.max_concurrent_positions = 15
    s.strategy.regime_directional_filter = True
    s.regime.enabled = True
    s.regime.ma_fast = 50
    s.regime.ma_slow = 200
    s.regime.vol_threshold = 0.35
    s.regime.vol_window = 20
    s.regime.neutral_band_pct = 0.02
    s.regime.trend_favorable_sizing = 0.80
    s.regime.neutral_sizing = 0.70
    if hasattr(s.strategy, "fdr_q_level"):
        s.strategy.fdr_q_level = 0.30


=======
def _apply_settings():
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

>>>>>>> origin/main
def main():
    print("=" * 70)
    print("  v47 P4+P5 continuation run")
    print("  (P1=-1.57 FAIL | P2=+1.65 PASS | P3=+2.21 PASS already done)")
    print("=" * 70)

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000
<<<<<<< HEAD
    ts20 = TimeStopManager(
        TimeStopConfig(
            half_life_multiplier=1.2,
            max_days_cap=20,
            default_max_bars=20,
        )
    )
    mom_filter = MomentumDivergenceFilter(
        lookback_days=60,
        threshold=1.5,
        min_universe_size=20,
        min_dispersion=0.08,
=======
    ts20 = TimeStopManager(TimeStopConfig(
        half_life_multiplier=1.2, max_days_cap=20, default_max_bars=20,
    ))
    mom_filter = MomentumDivergenceFilter(
        lookback_days=60, threshold=1.5, min_universe_size=20, min_dispersion=0.08,
>>>>>>> origin/main
    )

    results = []
    for label, train_start, train_end, oos_start, oos_end in WINDOWS:
        _apply_settings()
        t0 = time.time()
<<<<<<< HEAD
        print(f"\n  Running {label} ({train_start} -> {train_end} | OOS {oos_start} -> {oos_end})")
=======
        print("\n  Running %s (%s -> %s | OOS %s -> %s)" % (
            label, train_start, train_end, oos_start, oos_end))
>>>>>>> origin/main
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
<<<<<<< HEAD
            sh = metrics.sharpe_ratio
            ret = metrics.total_return * 100
            wr = metrics.win_rate * 100
            t = metrics.total_trades
            dd = metrics.max_drawdown * 100
            v = "PASS" if sh >= 1.2 else ("S-PASS" if sh >= 0.8 else "FAIL")
            results.append((label, sh, v, ret, wr, t, dd, elapsed, None))
            print(f"  -> S={sh:5.2f}  {ret:+6.2f}%  WR={wr:5.1f}%  t={t:2d}  DD={dd:+6.2f}%  [{v}/{elapsed}s]")
        except Exception as e:
            elapsed = int(time.time() - t0)
            results.append((label, None, "ERROR", 0, 0, 0, 0, elapsed, str(e)[:120]))
            print(f"  -> ERROR: {str(e)[:120]}")
=======
            sh  = metrics.sharpe_ratio
            ret = metrics.total_return * 100
            wr  = metrics.win_rate * 100
            t   = metrics.total_trades
            dd  = metrics.max_drawdown * 100
            v   = "PASS" if sh >= 1.2 else ("S-PASS" if sh >= 0.8 else "FAIL")
            results.append((label, sh, v, ret, wr, t, dd, elapsed, None))
            print("  -> S=%5.2f  %+6.2f%%  WR=%5.1f%%  t=%2d  DD=%+6.2f%%  [%s/%ds]" % (
                sh, ret, wr, t, dd, v, elapsed))
        except Exception as e:
            elapsed = int(time.time() - t0)
            results.append((label, None, "ERROR", 0, 0, 0, 0, elapsed, str(e)[:120]))
            print("  -> ERROR: %s" % str(e)[:120])
>>>>>>> origin/main

    print("\n" + "=" * 70)
    print("  v47 FINAL SUMMARY (all 5 windows)")
    print("=" * 70)
    print("    P1 2019H2  S= -1.57  WR= 33.3%  t= 3  DD= -7.09%  FAIL  (smooth bull, 1 trade blocked)")
    print("    P2 2020H2  S= +1.65  WR= 75.0%  t= 4  DD= -1.66%  PASS")
    print("    P3 2022H2  S= +2.21  WR= 75.0%  t= 8  DD= -2.71%  PASS")
    for label, sh, v, ret, wr, t, dd, elapsed, err in results:
        if err:
<<<<<<< HEAD
            print(f"    {label:<12}  ERROR: {err}")
        else:
            print(f"    {label:<12}  S={sh:5.2f}  {ret:+6.2f}%  WR={wr:5.1f}%  t={t:2d}  DD={dd:+6.2f}%  [{v}]")
=======
            print("    %-12s  ERROR: %s" % (label, err))
        else:
            print("    %-12s  S=%5.2f  %+6.2f%%  WR=%5.1f%%  t=%2d  DD=%+6.2f%%  [%s]" % (
                label, sh, ret, wr, t, dd, v))
>>>>>>> origin/main

    all5 = [(-1.57, "FAIL"), (1.65, "PASS"), (2.21, "PASS")]
    for label, sh, v, *_ in results:
        if sh is not None:
            all5.append((sh, v))
    if len(all5) == 5:
<<<<<<< HEAD
        passes = sum(1 for _, v in all5 if v == "PASS")
        spasses = sum(1 for _, v in all5 if v == "S-PASS")
        avg = sum(s for s, _ in all5) / 5
        verdict = "PASS" if passes >= 4 else ("S-PASS" if passes + spasses >= 4 else "FAIL")
        print(f"\n  PASS={passes}/5  avg={avg:.2f}  -> {verdict}")

=======
        passes  = sum(1 for _, v in all5 if v == "PASS")
        spasses = sum(1 for _, v in all5 if v == "S-PASS")
        avg     = sum(s for s, _ in all5) / 5
        verdict = "PASS" if passes >= 4 else ("S-PASS" if passes + spasses >= 4 else "FAIL")
        print("\n  PASS=%d/5  avg=%.2f  -> %s" % (passes, avg, verdict))
>>>>>>> origin/main

if __name__ == "__main__":
    main()
