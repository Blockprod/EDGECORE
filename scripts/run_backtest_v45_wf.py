#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""EDGECORE v45 -- Walk-Forward: Expanded Universe (~103 symbols).

v44b post-mortem ÔÇö levier de params ├®puis├®:
  ALL entry_z variants (1.6, 1.4, 1.2) FAIL on same 4 windows.
  P1 (2019H2): 0 OOS trades at ALL thresholds -> universe too small.
    ~40 symbols -> 2-3 active pairs -> NOT ENOUGH divergence in smooth bull.
  P2 (2020H2): more entries with lower z just adds MORE losers (z=1.2 -> S=-2.74)
  P3 (2022H2): BEAR regime blocks all longs (0 trades, all configs)
  P4 (2023H2): persistently S=-1.08 regardless (NVDA/AI bubble 2023H2)
  P5 (2024H2): stable PASS S=1.54-2.58 (works well)

v45 fix ÔÇö structural: expand universe to 103 symbols (was 40):
  Target: 10-20 active cointegrated pairs per window (was 2-3)
  More pairs -> more diverse OOS signals in ANY market regime
  Even in smooth 2019 bull: tech sector alone has 15 stocks -> many more
  potential pairs; some will diverge and mean-revert within sector.

Universe expansion sectors:
  Technology:           +7  (INTC QCOM TXN CRM ORCL ACN CSCO) -> 15 total
  Financials:           +7  (BLK AXP USB PNC COF BK TFC)       -> 14 total
  Energy:               +5  (SLB VLO MPC PSX OXY)              ->  9 total
  Consumer Staples:     +5  (COST MDLZ GIS PM MO)              -> 11 total
  Industrials:          +6  (MMM UPS BA ITW LMT FDX)           -> 11 total
  Utilities:            +3  (AEP EXC WEC)                      ->  6 total
  Healthcare:           +7  (TMO ABT DHR MDT CVS CI BMY)       -> 12 total
  Consumer Discret.*:   +9  (AMZN TSLA HD NKE LOW TGT SBUX F GM) -> 9 NEW
  Materials*:           +5  (LIN APD ECL NEM FCX)              ->  5 NEW
  Real Estate*:         +4  (PLD AMT SPG EQIX)                 ->  4 NEW
  Communication*:       +5  (T VZ CMCSA DIS NFLX)              ->  5 NEW
  (* = new sectors)

Params: v43a frozen (entry_z=1.6, vol_th=0.35, fdr_q=0.30, regime ON)
  BEAR_TRENDING still blocks longs (v43a baseline, best known config)

CACHE NOTE: New symbol set -> cache MISS on first run (IBKR re-fetch required).
  Ensure IB Gateway is connected before running.
  After first run, 5 new parquet files will be cached for future re-runs.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager

# ---------------------------------------------------------------------------
# Universe: 103 symbols across 12 sectors
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
    # Consumer Discretionary (9) -- NEW SECTOR
    "AMZN", "TSLA", "HD", "NKE", "LOW", "TGT", "SBUX", "F", "GM",
    # Materials (5) -- NEW SECTOR
    "LIN", "APD", "ECL", "NEM", "FCX",
    # Real Estate (4) -- NEW SECTOR
    "PLD", "AMT", "SPG", "EQIX",
    # Communication Services (5) -- NEW SECTOR
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


def _apply_v45_settings():
    """v43a best params, unchanged. Only the universe is expanding."""
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
    s.risk.max_concurrent_positions         = 15   # raised: more pairs available
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
    print("  EDGECORE v45 -- Walk-Forward: Expanded Universe (103 symbols)")
    print()
    print("  RATIONALE: entry_z sweep (v44b) exhausted param tuning ÔÇö ALL FAIL")
    print("    P1 gets 0 OOS trades at z=1.6, 1.4, 1.2 -> universe too small (~40 syms)")
    print("    40 symbols -> 2-3 active pairs -> insufficient divergence in smooth 2019 bull")
    print()
    print("  v45 fix: 40 -> 103 symbols (+63), 12 sectors (+4 new)")
    print("    Expected: 10-20 active pairs per window vs 2-3")
    print("    P1 target: at least 5+ OOS trades from new sector pairs")
    print()
    print("  Params: FROZEN at v43a best (entry_z=1.6, vol_th=0.35, fdr_q=0.30)")
    print("    max_concurrent_positions raised 10->15 (more pairs available)")
    print()
    print("  CACHE: New symbol set -> IBKR re-fetch required (first run only)")
    print("    Ensure IB Gateway is connected!")
    print()
    n = len(WF_SYMBOLS)
    n_pairs = n * (n - 1) // 2
    print("  Universe: %d symbols, %d potential pairs" % (n, n_pairs))
    sectors = {}
    for sym, sec in WF_SECTOR_MAP.items():
        if sec != "benchmark":
            sectors.setdefault(sec, []).append(sym)
    for sec, syms in sorted(sectors.items()):
        print("    %-25s %2d symbols" % (sec + ":", len(syms)))
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
        _apply_v45_settings()
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
    print("  v45 RESULTS -- Expanded Universe")
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

    # Comparison
    print("  Reference (v40-v44 best configs, 40-symbol universe):")
    print("    v43a (best): PASS=1/5  avg=+0.22  P1=0t  P3=0t  P5=1.54  -> FAIL")
    print("    v44b_14:     PASS=1/5  avg=-0.05  P1=0t  P3=0t  P5=2.58  -> FAIL")
    print("  v45 (this):    PASS=%d/5  avg=%+.2f -> %s" % (passes, avg_sh, verdict))
    print()

    if verdict == "PASS":
        print("  PASS! Phase 5: freeze v45 params -> live paper trading deployment")
        print("  Next: run paper trading with IBKR live data + monitoring dashboard")
    elif verdict == "S-PASS":
        print("  S-PASS. Close. Options:")
        print("    v45b: increase train window 18m->24m (more robust cointegration)")
        print("    v45c: fdr_q=0.20 (stricter pairs, higher quality)")
        print("    v45d: universe further expand to 150 symbols (add NASDAQ midcap)")
    else:
        print("  Still FAIL. Diagnosis by window:")
        for label, sh, v, ret, wr, t, dd, elapsed, err in results:
            if err:
                continue
            note = ""
            if t == 0:
                note = "  <- 0 trades: universe still too small for this regime?"
            elif sh < -1.0:
                note = "  <- persistent loser (regime/structural issue)"
            elif sh >= 0.8:
                note = "  <- near-pass: promising"
            print("    %-12s  S=%5.2f  t=%2d%s" % (label, sh, t, note))
        print()
        print("  If P1 still t=0: consider adding sector ETFs (XLF, XLV, XLE, XLI)")
        print("  as pair anchors to guarantee cross-sector signals.")
    print()


if __name__ == "__main__":
    main()
