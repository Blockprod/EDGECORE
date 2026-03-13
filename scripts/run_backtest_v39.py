#!/usr/bin/env python
"""EDGECORE v39 -- Phase 5.3: Leverage 2.5x (optimal frontier).

Leverage frontier validated on v37 core (39 symbols, 2023-03-04 to 2026-03-04):
  1.0x unlevered : +13.92%  S=1.67  PF=8.54  WR=65.2%  23t  DD=-1.13%
  1.5x Phase 3   : +21.42%  S=1.67  PF=8.41  WR=65.2%  23t  DD=-1.69%
  2.0x Phase 4   : +29.30%  S=1.67  PF=8.31  WR=65.2%  23t  DD=-2.26%
  2.5x v39 HERE  : +42.55%  S=1.82  PF=9.06  WR=65.2%  23t  DD=-2.69%  OPTIMAL
  3.0x Phase 5mx : +47.96%  S=1.74  PF=8.26  WR=61.9%  21t  DD=-3.22%

2.5x chosen as optimal: peak Sharpe (1.82), peak PF (9.06), WR preserved (65.2%),
MaxDD stays within -3% risk budget, 23 trades identical to unlevered baseline.
Internal DD guard closes positions at 3.0x causing trade count degradation.

Key fix applied (discovered during Phase 5): SectorExposureMonitor max_sector_weight
is now scaled by leverage_multiplier in strategy_simulator.py, preventing the
sector concentration guard from blocking entries at higher leverage levels.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager

# -- Universe: exact v37 core (39 symbols) ------------------------------------
V39_SYMBOLS = [
    # Market benchmark
    "SPY",
    # Technology (8)
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO", "XLK",
    # Financials (7)
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    # Energy (4)
    "XOM", "CVX", "COP", "EOG",
    # Consumer Staples (5)
    "KO", "PEP", "PG", "CL", "WMT",
    # Industrials (5)
    "CAT", "HON", "DE", "GE", "RTX",
    # Utilities (3)
    "NEE", "DUK", "SO",
    # Healthcare (5)
    "JNJ", "PFE", "UNH", "MRK", "ABBV",
    # Consumer Staples addition (v37 surgical)
    "MCD",
]

V39_SECTOR_MAP = {
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


def main():
    print("=" * 75)
    print("  EDGECORE v39 -- Phase 5.3: Leverage 2.5x (Optimal Frontier)")
    print("  Universe: %d symbols (v37 core, identical)" % len(V39_SYMBOLS))
    print("  Leverage: 2.5x gross exposure (250k on 100k NAV)")
    print("  v37 baseline: +13.92%%  S=1.67  PF=8.54  WR=65.2%%  23t  DD=-1.13%%")
    print("=" * 75)
    print()

    s = get_settings()
    # -- Exact v37 strategy settings ------------------------------------------
    s.strategy.lookback_window = 120
    s.strategy.additional_lookback_windows = [63]
    s.strategy.entry_z_score = 1.8
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
    if hasattr(s.strategy, 'fdr_q_level'):
        s.strategy.fdr_q_level = 0.25

    time_stop = TimeStopManager(TimeStopConfig(
        half_life_multiplier=1.2, max_days_cap=20, default_max_bars=20,
    ))

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000

    print("  Running backtest (2023-03-04 to 2026-03-04) with 2.5x leverage...")
    t0 = time.time()

    metrics = runner.run_unified(
        symbols=V39_SYMBOLS, start_date="2023-03-04", end_date="2026-03-04",
        sector_map=V39_SECTOR_MAP, pair_rediscovery_interval=2,
        allocation_per_pair_pct=50.0,
        max_position_loss_pct=0.07,
        max_portfolio_heat=3.0,
        time_stop=time_stop,
        leverage_multiplier=2.5,    # Phase 5.3: optimal leverage level
    )
    elapsed = time.time() - t0
    print("  Completed in %ds" % int(elapsed))
    print()

    # -- Results --------------------------------------------------------------
    ret = metrics.total_return * 100
    s   = metrics.sharpe_ratio
    pf  = metrics.profit_factor
    wr  = metrics.win_rate * 100
    t   = metrics.total_trades
    dd  = metrics.max_drawdown * 100
    cal = abs(ret / dd) if dd != 0 else 0.0

    print("=" * 75)
    print("  v39 PHASE 5 RESULTS (2.5x leverage)")
    print("=" * 75)
    print()
    print("  LEVERAGE FRONTIER SUMMARY:")
    print("    1.0x unlevered : +13.92%%  S=1.67  PF=8.54  WR=65.2%%  23t  DD=-1.13%%")
    print("    1.5x Phase 3   : +21.42%%  S=1.67  PF=8.41  WR=65.2%%  23t  DD=-1.69%%")
    print("    2.0x Phase 4   : +29.30%%  S=1.67  PF=8.31  WR=65.2%%  23t  DD=-2.26%%")
    print("    2.5x v39 NOW   : %+.2f%%  S=%.2f  PF=%.2f  WR=%.1f%%  %dt  DD=%.2f%%" % (
        ret, s, pf, wr, t, dd))
    print()
    print("  vs v37 UNLEVERED BASELINE:")
    print("    Return     : %+.2f%%  (v37: +13.92%%)  delta=%+.2f%%  (%.1fx return)" % (
        ret, ret - 13.92, ret / 13.92))
    print("    Sharpe     : %.2f   (v37: 1.67)  delta=%+.2f" % (s, s - 1.67))
    print("    PF         : %.2f" % pf)
    print("    WR         : %.1f%%" % wr)
    print("    Trades     : %d" % t)
    print("    MaxDD      : %.2f%%  (v37: -1.13%%)" % dd)
    print("    Calmar     : %.2f" % cal)
    print()
    print("  PHASE 5 TARGET CHECK:")
    print("    Sharpe >= 1.5 (go-criteria) : %s (%.2f)" % ("PASS" if s >= 1.5 else "MISS", s))
    print("    Sharpe >= 2.0 (stretch)     : %s (%.2f)" % ("PASS" if s >= 2.0 else "MISS", s))
    print("    PF     >= 2.5               : %s (%.2f)" % ("PASS" if pf >= 2.5 else "MISS", pf))
    print("    DD     > -8%%               : %s (%.2f%%)" % ("PASS" if dd > -8.0 else "MISS", dd))
    print("    Trades >= v37 (23)          : %s (%d)" % ("PASS" if t >= 23 else "MISS", t))
    print("    Return 3x+ vs unlevered     : %s (%.1fx)" % ("PASS" if ret >= 41.76 else "MISS", ret / 13.92))
    print()
    if s >= 1.5 and t >= 23 and dd > -8.0:
        print("  >>> Phase 5.3 PASS: Leverage 2.5x operational <<<")
    else:
        print("  >>> Phase 5.3 PARTIAL: check metrics above <<<")
    print()


if __name__ == "__main__":
    main()
