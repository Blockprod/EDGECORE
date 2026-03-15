#!/usr/bin/env python
"""EDGECORE v33 ÔÇö Phase 1 Multi-Signal Backtest.

Compare v32j baseline (Almgren-Chriss only, 2 signals) vs v33
(same costs + 5-source SignalCombiner: zscore, momentum, OU, vol, cross-sec).

The new signals change signal STRENGTH (used by simulator for sizing
quality multiplier) but do NOT change the z-score entry threshold gate.
This means trade count should be identical, but strength refinement
may improve win rate and PF.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

SYMBOLS = [
    "SPY",
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO",
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    "XOM", "CVX", "COP", "EOG",
    "KO", "PEP", "PG", "CL", "WMT",
    "CAT", "HON", "DE", "GE", "RTX",
    "NEE", "DUK", "SO",
    "JNJ", "PFE", "UNH", "MRK", "ABBV",
]

SECTOR_MAP = {
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
}


def setup_settings():
    from config.settings import get_settings
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


def make_time_stop():
    from execution.time_stop import TimeStopConfig, TimeStopManager
    return TimeStopManager(TimeStopConfig(
        half_life_multiplier=1.5, max_days_cap=30, default_max_bars=30,
    ))


def run_backtest(label):
    setup_settings()
    runner = BacktestRunner()
    runner.config.initial_capital = 100_000

    metrics = runner.run_unified(
        symbols=SYMBOLS, start_date="2023-03-04", end_date="2026-03-04",
        sector_map=SECTOR_MAP, pair_rediscovery_interval=2,
        allocation_per_pair_pct=50.0, max_position_loss_pct=0.07,
        max_portfolio_heat=3.0, time_stop=make_time_stop(),
    )
    return {"label": label, "summary": metrics.summary(), "metrics": metrics}


def main():
    print("=" * 70)
    print("  EDGECORE v33 ÔÇö Phase 1 Multi-Signal Backtest")
    print("  Costs: Almgren-Chriss (eta=0.05, delay=0.01) ÔÇö v32j defaults")
    print("  Signals: zscore(0.40) + momentum(0.20) + OU(0.20)")
    print("           + vol_regime(0.10) + cross_sectional(0.10)")
    print("=" * 70)
    print()

    t0 = time.time()
    r = run_backtest("v33_phase1_multisignal")
    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.0f}s")
    print()

    s = r["summary"]
    print("  COMPARISON")
    print("  " + "-" * 60)
    print(f"  v31h (no costs): +8.17%  Sharpe 1.31  PF 3.88  WR 62.5%  24t  DD -1.79%")
    print(f"  v32j (Phase 0):  +4.37%  Sharpe 0.80  PF 2.57  WR 55.6%  18t  DD -2.70%")
    print(f"  >>> {r['label']} <<<")
    print(f"  Final Capital:     {s.get('final_capital', 0):>12,.2f} EUR")
    print(f"  Total Return:      {s.get('total_return_pct', 0):>10.2f}%")
    print(f"  Sharpe Ratio:      {s.get('sharpe_ratio', 0):>10.2f}")
    print(f"  Max Drawdown:      {s.get('max_drawdown_pct', 0):>10.2f}%")
    print(f"  Calmar Ratio:      {s.get('calmar_ratio', 0):>10.2f}")
    print(f"  Win Rate:          {s.get('win_rate_pct', 0):>10.2f}%")
    print(f"  Profit Factor:     {s.get('profit_factor', 0):>10.2f}")
    print(f"  Total Trades:      {s.get('total_trades', 0):>10d}")
    print()

    # Save results
    out = os.path.join(_ROOT, "results", "v33_phase1_results.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(f"v33 Phase 1 Multi-Signal Backtest\n")
        f.write(f"{'='*60}\n")
        for k, v in s.items():
            f.write(f"  {k}: {v}\n")
    print(f"  [Saved] {out}")


if __name__ == "__main__":
    main()
