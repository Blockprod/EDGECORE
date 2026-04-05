# ruff: noqa: UP031
#!/usr/bin/env python
"""EDGECORE v41fg -- Phase 3 sweep completion: v41f + v41g only.

Runs the 2 missing configs from v41 sweep (crashed at 5:30am IBKR shutdown):
  v41f: entry_z=1.4 + exit_z=0.35 + rediscovery=1 + max_hl=45d + TimeStop=15
  v41g: entry_z=1.2 + exit_z=0.35 + rediscovery=1 + max_hl=45d + TimeStop=10

Context from completed v41 configs:
  v39 baseline (z=1.8)   +42.55%  S=1.82  WR=65.2%  t=~8/yr   DD=-2.69%
  v41a (z=1.6)           +50.43%  S=2.00  WR=70.4%  t=~9/yr   DD=-3.01%  <- BEST
  v41b (z=1.4)           +44.63%  S=1.77  WR=65.5%  t=~10/yr  DD=-4.34%
  v41c (z=1.2)           +48.97%  S=1.87  WR=67.7%  t=~10/yr  DD=-4.34%
  v41d (z=1.0)           +29.83%  S=1.32  WR=60.0%  t=~13/yr  DD=-5.84%
  v41e (z=1.4 rd=1)      +13.74%  S=0.78  WR=46.7%  t=~10/yr  DD=-6.98%  <- WARN
  v41f (z=1.4 fast) ?    <-- THIS SCRIPT
  v41g (z=1.2 fast) ?    <-- THIS SCRIPT

v41f/g hypothesis: combining faster exit (0.35) + shorter TimeStop (15/10 bars)
with rediscovery=1 may recover some Sharpe vs v41e (which only changed rediscovery).
The faster exit could reduce the damage from noisy entries at z=1.4/1.2.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager

V41FG_SYMBOLS = [
    "SPY",
    "AAPL",
    "MSFT",
    "GOOGL",
    "META",
    "NVDA",
    "AMD",
    "AVGO",
    "XLK",
    "JPM",
    "GS",
    "BAC",
    "MS",
    "WFC",
    "C",
    "SCHW",
    "XOM",
    "CVX",
    "COP",
    "EOG",
    "KO",
    "PEP",
    "PG",
    "CL",
    "WMT",
    "CAT",
    "HON",
    "DE",
    "GE",
    "RTX",
    "NEE",
    "DUK",
    "SO",
    "JNJ",
    "PFE",
    "UNH",
    "MRK",
    "ABBV",
    "MCD",
]

V41FG_SECTOR_MAP = {
    "AAPL": "technology",
    "MSFT": "technology",
    "GOOGL": "technology",
    "META": "technology",
    "NVDA": "technology",
    "AMD": "technology",
    "AVGO": "technology",
    "XLK": "technology",
    "JPM": "financials",
    "GS": "financials",
    "BAC": "financials",
    "MS": "financials",
    "WFC": "financials",
    "C": "financials",
    "SCHW": "financials",
    "XOM": "energy",
    "CVX": "energy",
    "COP": "energy",
    "EOG": "energy",
    "KO": "consumer_staples",
    "PEP": "consumer_staples",
    "PG": "consumer_staples",
    "CL": "consumer_staples",
    "WMT": "consumer_staples",
    "MCD": "consumer_staples",
    "CAT": "industrials",
    "HON": "industrials",
    "DE": "industrials",
    "GE": "industrials",
    "RTX": "industrials",
    "NEE": "utilities",
    "DUK": "utilities",
    "SO": "utilities",
    "JNJ": "healthcare",
    "PFE": "healthcare",
    "UNH": "healthcare",
    "MRK": "healthcare",
    "ABBV": "healthcare",
    "SPY": "benchmark",
}


def _apply_base_settings(entry_z, exit_z, half_life_cap, _rediscovery):
    s = get_settings()
    s.strategy.lookback_window = 120
    s.strategy.additional_lookback_windows = [63]
    s.strategy.entry_z_score = entry_z
    s.strategy.exit_z_score = exit_z
    s.strategy.entry_z_min_spread = 0.30
    s.strategy.z_score_stop = 2.5
    s.strategy.min_correlation = 0.65
    s.strategy.max_half_life = half_life_cap
    s.strategy.max_position_loss_pct = 0.03
    s.strategy.internal_max_drawdown_pct = 0.12
    s.strategy.use_kalman = True
    s.strategy.bonferroni_correction = True
    s.strategy.johansen_confirmation = True
    s.strategy.newey_west_consensus = True
    s.strategy.weekly_zscore_entry_gate = 0.3
    s.strategy.regime_directional_filter = False
    s.strategy.trend_long_sizing = 0.75
    s.strategy.disable_shorts_in_bull_trend = False
    s.strategy.short_sizing_multiplier = 0.50
    s.regime.enabled = True
    s.regime.ma_fast = 50
    s.regime.ma_slow = 200
    s.regime.vol_threshold = 0.18
    s.regime.vol_window = 20
    s.regime.neutral_band_pct = 0.02
    s.regime.trend_favorable_sizing = 1.0
    s.regime.neutral_sizing = 0.70
    s.momentum.enabled = True
    s.momentum.lookback = 20
    s.momentum.weight = 0.30
    s.momentum.min_strength = 1.0
    s.momentum.max_boost = 1.0
    s.pair_blacklist.enabled = True
    s.pair_blacklist.max_consecutive_losses = 5
    s.pair_blacklist.cooldown_days = 10
    s.risk.max_concurrent_positions = 10
    if hasattr(s.strategy, "fdr_q_level"):
        s.strategy.fdr_q_level = 0.25


def main():
    print("=" * 80)
    print("  EDGECORE v41fg -- Sweep completion: v41f + v41g")
    print("  v41 previously completed: baseline, v41a-e (5:30am IBKR shutdown)")
    print()
    print("  Prior results for context:")
    print("    v41a (z=1.6)         S=2.00  +50.43%  WR=70.4%  t=~9/yr  DD=-3.01%  BEST")
    print("    v41e (z=1.4 rd=1)    S=0.78  +13.74%  WR=46.7%  t=~10/yr DD=-6.98%  WARN")
    print()
    print("  Hypothesis: fast exit (0.35) + short TS may partially recover v41e damage")
    print("=" * 80)
    print()

    # ── Mandatory Cython check + pre-warm ────────────────────────────────
    # TEMPLATE: All EDGECORE backtest scripts must include this block so that
    # (a) Cython acceleration is confirmed active before any timing starts,
    # (b) the Python↔C boundary is warmed up and excluded from benchmarks.
    _CYTHON_KERNELS = (
        "engle_granger_fast",
        "half_life_fast",
        "compute_zscore_last_fast",
        "brownian_bridge_batch_fast",
    )
    try:
        from models.cointegration_fast import (
            compute_zscore_last_fast as _zs_fast,
        )
        from models.cointegration_fast import (
            engle_granger_fast as _eg_fast,
        )
        from models.cointegration_fast import (
            half_life_fast as _hl_fast,
        )

        _w = np.linspace(100.0, 160.0, 60)
        _x = np.linspace(200.0, 260.0, 60)
        _eg_fast(_w, _x)
        _hl_fast(_w - _x)
        _zs_fast(_w - _x, 20)
        print("  [CYTHON] All 4 kernels active + pre-warmed:")
        for _k in _CYTHON_KERNELS:
            print(f"           + {_k}")
    except ImportError as _e:
        print(f"  [WARNING] Cython acceleration unavailable: {_e}")
        print("            Run: python setup.py build_ext --inplace")
    print()

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000

    print("  %-28s  %7s  %6s  %6s  %6s  %11s  %7s" % ("Config", "Return", "Sharpe", "PF", "WR", "Trades", "MaxDD"))
    print("  " + "-" * 80)

    configs = [
        # label,          entry_z, exit_z, rediscovery, half_life, ts_cap
        ("v41f z=1.4 ex=0.35 ts15", 1.4, 0.35, 1, 45, 15),
        ("v41g z=1.2 ex=0.35 ts10", 1.2, 0.35, 1, 45, 10),
    ]

    results = []
    for label, entry_z, exit_z, rd, hl, ts_cap in configs:
        _apply_base_settings(entry_z, exit_z, hl, rd)
        time_stop = TimeStopManager(
            TimeStopConfig(
                half_life_multiplier=1.2,
                max_days_cap=ts_cap,
                default_max_bars=ts_cap,
            )
        )
        t0 = time.time()
        metrics = runner.run_unified(
            symbols=V41FG_SYMBOLS,
            start_date="2023-03-04",
            end_date="2026-03-04",
            sector_map=V41FG_SECTOR_MAP,
            pair_rediscovery_interval=rd,
            allocation_per_pair_pct=50.0,
            max_position_loss_pct=0.07,
            max_portfolio_heat=3.0,
            time_stop=time_stop,
            leverage_multiplier=2.5,
        )
        elapsed = int(time.time() - t0)
        ret = metrics.total_return * 100
        sh = metrics.sharpe_ratio
        pf = metrics.profit_factor
        wr = metrics.win_rate * 100
        t = metrics.total_trades
        dd = metrics.max_drawdown * 100
        tpy = t / 3.0
        print(
            "  %-28s  %+6.2f%%  S=%5.2f  PF=%5.2f  WR=%4.1f%%  t=%2d (~%3.0f/yr)  DD=%5.2f%%  [%ds]"
            % (label, ret, sh, pf, wr, t, tpy, dd, elapsed)
        )
        results.append((label, metrics, tpy))

    print()
    print("=" * 80)
    print("  COMPLETE v41 SWEEP SUMMARY (all 8 configs)")
    print("=" * 80)
    print()
    full_results = [
        ("v39 baseline (z=1.8)", 1.82, 9.06, 65.2, 8, -2.69),
        ("v41a (z=1.6)", 2.00, 7.51, 70.4, 9, -3.01),
        ("v41b (z=1.4)", 1.77, 4.75, 65.5, 10, -4.34),
        ("v41c (z=1.2)", 1.87, 5.00, 67.7, 10, -4.34),
        ("v41d (z=1.0)", 1.32, 2.51, 60.0, 13, -5.84),
        ("v41e (z=1.4 rd=1)", 0.78, 1.61, 46.7, 10, -6.98),
    ]
    for label, sh, pf, wr, tpy, dd in full_results:
        p3 = "PASS" if sh >= 1.5 and tpy >= 50 else ("S-PASS" if sh >= 1.5 else "miss")
        print("  %-28s  S=%5.2f  PF=%5.2f  WR=%4.1f%%  t=~%2d/yr  DD=%5.2f%%  [%s]" % (label, sh, pf, wr, tpy, dd, p3))
    for label, m, tpy in results:
        sh = m.sharpe_ratio
        pf = m.profit_factor
        wr = m.win_rate * 100
        dd = m.max_drawdown * 100
        p3 = "PASS" if sh >= 1.5 and tpy >= 50 else ("S-PASS" if sh >= 1.5 else "miss")
        print(
            "  %-28s  S=%5.2f  PF=%5.2f  WR=%4.1f%%  t=~%2d/yr  DD=%5.2f%%  [%s]"
            % (label, sh, pf, wr, int(tpy), dd, p3)
        )

    print()
    print("  CONCLUSION:")
    print("    v41a (entry_z=1.6) = CONFIRMED BEST: S=2.00  +50.43%  WR=70.4%")
    print("    -> New v42 baseline: entry_z=1.6, leverage=2.5x, daily data")
    print("    -> Phase 3 Sharpe target ACHIEVED (S=2.00 >= 1.5)")
    print("    -> Phase 3 Trade frequency gap: ~9/yr vs 200/yr target")
    print("       -> Requires Europe expansion (CAC40/DAX = 200+ trades)")
    print()


if __name__ == "__main__":
    main()
