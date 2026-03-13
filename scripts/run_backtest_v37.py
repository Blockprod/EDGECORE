#!/usr/bin/env python
"""EDGECORE v37 -- Phase 4: Signaux Avancés & ML.

Adds on top of v36 baseline (39 symbols):
  4.1  EarningsSurpriseSignal: PEAD from price gaps (backtest proxy)
  4.2  OptionsFlowSignal: P/C ratio + IV skew + unusual activity proxy
  4.3  SentimentSignal: momentum divergence + conviction + surprise proxy
  4.4  MLSignalCombiner: walk-forward GBM (sklearn GradientBoosting)

Signal combiner updated: 9 sources (zscore 0.25, momentum 0.10,
  OU 0.15, vol_regime 0.08, cross_sectional 0.08, intraday_mr 0.08,
  earnings 0.10, options_flow 0.08, sentiment 0.08).

v36 baseline: +10.46% S1.33 PF4.22 WR66.7% 21t DD-1.91% Calmar5.48
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager

V37_SYMBOLS = [
    # === BASE (37) ===
    "SPY",
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO",
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    "XOM", "CVX", "COP", "EOG",
    "KO", "PEP", "PG", "CL", "WMT",
    "CAT", "HON", "DE", "GE", "RTX",
    "NEE", "DUK", "SO",
    "JNJ", "PFE", "UNH", "MRK", "ABBV",
    # === SURGICAL ADDITIONS (2) ===
    "XLK",   # tech ETF
    "MCD",   # consumer
]

V37_SECTOR_MAP = {
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
    "XLK": "technology",
    "MCD": "consumer_staples",
}


def main():
    print("=" * 75)
    print("  EDGECORE v37 -- Phase 4: Signaux Avancés & ML")
    print("  Universe: %d symbols" % len(V37_SYMBOLS))
    print("  Phase 4: Earnings + OptionsFlow + Sentiment + ML Combiner")
    print("  9-source SignalCombiner + walk-forward GBM training")
    print("  v36 baseline: +10.46%%  S1.33  PF4.22  WR66.7%%  21t  DD-1.91%%")
    print("=" * 75)
    print()

    s = get_settings()
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

    print("  Running backtest (2023-03-04 to 2026-03-04)...")
    t0 = time.time()

    metrics = runner.run_unified(
        symbols=V37_SYMBOLS, start_date="2023-03-04", end_date="2026-03-04",
        sector_map=V37_SECTOR_MAP, pair_rediscovery_interval=2,
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

    base = {
        "return_pct": 10.46, "sharpe": 1.33, "pf": 4.22,
        "win_rate": 66.7, "trades": 21, "max_dd": -1.91, "calmar": 5.48,
    }

    print("=" * 75)
    print("  v37 RESULTS vs v36 BASELINE")
    print("=" * 75)
    print("  Return:  %+.2f%%  (v36: +%.2f%%)  delta=%+.2f%%" % (
        r['return_pct'], base['return_pct'], r['return_pct'] - base['return_pct']))
    print("  Sharpe:  %.2f   (v36: %.2f)  delta=%+.2f" % (
        r['sharpe'], base['sharpe'], r['sharpe'] - base['sharpe']))
    print("  PF:      %.2f   (v36: %.2f)  delta=%+.2f" % (
        r['pf'], base['pf'], r['pf'] - base['pf']))
    print("  WR:      %.1f%%   (v36: %.1f%%)" % (r['win_rate'], base['win_rate']))
    print("  Trades:  %d     (v36: %d)  delta=%+d" % (
        r['trades'], base['trades'], r['trades'] - base['trades']))
    print("  MaxDD:   %.2f%%  (v36: %.2f%%)" % (r['max_dd'], base['max_dd']))
    print("  Calmar:  %.2f   (v36: %.2f)" % (r['calmar'], base['calmar']))
    print()

    # Phase 4 target check
    target_sharpe = 2.0
    target_pf = 2.5
    sharpe_ok = r['sharpe'] >= target_sharpe
    pf_ok = r['pf'] >= target_pf
    print("  TARGET CHECK:")
    print("    Sharpe >= %.1f : %s (%.2f)" % (target_sharpe, "PASS" if sharpe_ok else "MISS", r['sharpe']))
    print("    PF     >= %.1f : %s (%.2f)" % (target_pf, "PASS" if pf_ok else "MISS", r['pf']))
    if sharpe_ok and pf_ok:
        print("    >>> ALL TARGETS MET — Phase 4 VALIDATED <<<")
    else:
        print("    >>> Some targets not yet met — check signal weights <<<")
    print()


if __name__ == "__main__":
    main()
