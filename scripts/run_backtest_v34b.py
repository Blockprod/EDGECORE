#!/usr/bin/env python
"""EDGECORE v34b -- Active Winners Only.

v34b = v32j (37) + 8 active winners from Phase 1.5 = 45 symbols.
Only includes symbols that individually improved Sharpe AND PF.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from execution.time_stop import TimeStopConfig, TimeStopManager
from config.settings import get_settings

# v34b Universe: 45 symbols (37 base + 8 active winners)
V34B_SYMBOLS = [
    # === BASE (37) ===
    "SPY",
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO",
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    "XOM", "CVX", "COP", "EOG",
    "KO", "PEP", "PG", "CL", "WMT",
    "CAT", "HON", "DE", "GE", "RTX",
    "NEE", "DUK", "SO",
    "JNJ", "PFE", "UNH", "MRK", "ABBV",
    # === ACTIVE WINNERS (8) ===
    "INTC", "QCOM", "TXN", "ADBE", "CRM", "CSCO",  # tech +dS +dPF
    "XLK",                                            # tech ETF (best)
    "MCD",                                            # consumer +dS +dPF
]

V34B_SECTOR_MAP = {
    "AAPL": "technology", "MSFT": "technology", "GOOGL": "technology",
    "META": "technology", "NVDA": "technology", "AMD": "technology",
    "AVGO": "technology",
    "JPM": "financials", "GS": "financials", "BAC": "financials",
    "MS": "financials", "WFC": "financials", "C": "financials",
    "SCHW": "financials",
    "XOM": "energy", "CVX": "energy", "COP": "energy", "EOG": "energy",
    "KO": "consumer_staples", "PEP": "consumer_staples",
    "PG": "consumer_staples", "CL": "consumer_staples",
    "WMT": "consumer_staples",
    "CAT": "industrials", "HON": "industrials", "DE": "industrials",
    "GE": "industrials", "RTX": "industrials",
    "NEE": "utilities", "DUK": "utilities", "SO": "utilities",
    "JNJ": "healthcare", "PFE": "healthcare", "UNH": "healthcare",
    "MRK": "healthcare", "ABBV": "healthcare",
    "INTC": "technology", "QCOM": "technology", "TXN": "technology",
    "ADBE": "technology", "CRM": "technology", "CSCO": "technology",
    "XLK": "technology",
    "MCD": "consumer_staples",
}


def main():
    print("=" * 75)
    print("  EDGECORE v34b -- Active Winners Only")
    print("  Universe: %d symbols (37 base + 8 active winners)" % len(V34B_SYMBOLS))
    print("  v32j baseline: +4.37%%  S0.80  PF2.57  18t  DD-2.70%%")
    print("=" * 75)
    print()

    s = get_settings()
    s.strategy.lookback_window = 120
    s.strategy.additional_lookback_windows = [63]
    s.strategy.entry_z_score = 1.8
    s.strategy.exit_z_score = 0.5
    s.strategy.entry_z_min_spread = 0.30
    s.strategy.z_score_stop = 3.0
    s.strategy.min_correlation = 0.65
    s.strategy.max_half_life = 60
    s.strategy.max_position_loss_pct = 0.07
    s.strategy.internal_max_drawdown_pct = 0.25
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
        half_life_multiplier=1.5, max_days_cap=30, default_max_bars=30,
    ))

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000

    print("  Running backtest (2023-03-04 to 2026-03-04)...")
    t0 = time.time()

    metrics = runner.run_unified(
        symbols=V34B_SYMBOLS, start_date="2023-03-04", end_date="2026-03-04",
        sector_map=V34B_SECTOR_MAP, pair_rediscovery_interval=2,
        allocation_per_pair_pct=50.0, max_position_loss_pct=0.07,
        max_portfolio_heat=3.0, time_stop=time_stop,
    )

    elapsed = time.time() - t0
    print("  Completed in %.0fs" % elapsed)
    print()

    r = {
        "return_pct": round(metrics.total_return * 100, 2),
        "sharpe": round(metrics.sharpe_ratio, 2),
        "pf": round(metrics.profit_factor, 2),
        "win_rate": round(metrics.win_rate * 100, 1),
        "trades": metrics.total_trades,
        "max_dd": round(metrics.max_drawdown * 100, 2),
        "calmar": round(metrics.calmar_ratio, 2),
    }

    base = {"return_pct": 4.37, "sharpe": 0.80, "pf": 2.57, "trades": 18, "max_dd": -2.70}

    print("=" * 75)
    print("  v34b RESULTS vs v32j BASELINE")
    print("=" * 75)
    print("  Return:  %+.2f%%  (v32j: +%.2f%%)  delta=%+.2f%%" % (
        r['return_pct'], base['return_pct'], r['return_pct'] - base['return_pct']))
    print("  Sharpe:  %.2f   (v32j: %.2f)  delta=%+.2f" % (
        r['sharpe'], base['sharpe'], r['sharpe'] - base['sharpe']))
    print("  PF:      %.2f   (v32j: %.2f)  delta=%+.2f" % (
        r['pf'], base['pf'], r['pf'] - base['pf']))
    print("  WR:      %.1f%%" % r['win_rate'])
    print("  Trades:  %d     (v32j: %d)  delta=%+d" % (
        r['trades'], base['trades'], r['trades'] - base['trades']))
    print("  MaxDD:   %.2f%%  (v32j: %.2f%%)" % (r['max_dd'], base['max_dd']))
    print("  Calmar:  %.2f" % r['calmar'])
    print()

    improved = (r['sharpe'] >= base['sharpe'] and r['pf'] >= base['pf']
                and r['trades'] >= base['trades'])
    if improved:
        print("  >> v34b PASSES -- adopt as new baseline")
    else:
        print("  >> v34b FAILS strict criteria")
        # Show if partially improved
        if r['trades'] > base['trades'] and r['return_pct'] > base['return_pct']:
            print("     BUT: more trades (%d vs %d) and higher return (%.2f%% vs %.2f%%)" % (
                r['trades'], base['trades'], r['return_pct'], base['return_pct']))
            print("     Consider adopting if trade count priority > risk-adjusted purity")


if __name__ == "__main__":
    main()
