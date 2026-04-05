#!/usr/bin/env python
"""EDGECORE v38d -- Phase 5: Surgical universe (+1 symbol per sector).

Hypothesis: adding +6 large bulk was disrupting v37's sector pair dynamics.
Fix: add exactly 1 new symbol per sector — sector pools grow by only 1,
     keeping FDR selection stable, preserving proven v37 pairs.

v37 core (39 symbols) + 6 curated additions = 45 total:
  Tech     +1: QCOM  (semiconductor — confirmed AMD_QCOM pair in testing)
  Fin      +1: BLK   (asset mgmt — distinct niche within financials)
  Energy   +1: SLB   (oilfield services — different micro from E&P)
  CS       +1: COST  (warehouse retail — different model from WMT/KO/PEP)
  Indust   +1: LMT   (defense — distinct from HON/CAT/DE industrials)
  HC       +1: LLY   (pharma mega-cap — confirmed high-volume)

v37+lever=1.5 benchmark: +21.42%  S1.67  PF8.41  WR65.2%  23t  DD-1.69%
v38  (62 symbols)       : + 8.23%  S0.78  PF1.61  WR44.8%  39t  DD-5.50%  MISS
v38c (62 sym fdr=0.05)  : + 3.81%  S0.49  PF1.43  WR44.8%  29t  DD-3.87%  MISS
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager

# ── Universe v38d: v37 core + 1 curated symbol per sector ────────────────────
V38D_SYMBOLS = [
    # === MARKET BENCHMARK ===
    "SPY",

    # === TECHNOLOGY (8 v37 + 1 new = 9) ===
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO", "XLK",
    "QCOM",   # +1: semiconductor — pairs with AMD/NVDA

    # === FINANCIALS (7 v37 + 1 new = 8) ===
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    "BLK",    # +1: asset management — distinct niche

    # === ENERGY (4 v37 + 1 new = 5) ===
    "XOM", "CVX", "COP", "EOG",
    "SLB",    # +1: oilfield services — pairs with E&P names

    # === CONSUMER STAPLES (6 v37 + 1 new = 7) ===
    "KO", "PEP", "PG", "CL", "WMT", "MCD",
    "COST",   # +1: warehouse retail

    # === INDUSTRIALS (5 v37 + 1 new = 6) ===
    "CAT", "HON", "DE", "GE", "RTX",
    "LMT",    # +1: defense / aerospace

    # === UTILITIES (3 v37, no addition) ===
    "NEE", "DUK", "SO",

    # === HEALTHCARE (5 v37 + 1 new = 6) ===
    "JNJ", "PFE", "UNH", "MRK", "ABBV",
    "LLY",    # +1: mega-cap pharma

    # === CONSUMER DISCRETIONARY (4 v37, no addition) ===
    "AMZN", "HD", "NKE", "SBUX",

    # === REAL ESTATE (2 v37, no addition) ===
    "AMT", "PLD",
]

V38D_SECTOR_MAP = {
    # Technology
    "AAPL": "technology", "MSFT": "technology", "GOOGL": "technology",
    "META": "technology", "NVDA": "technology", "AMD": "technology",
    "AVGO": "technology", "XLK": "technology", "QCOM": "technology",
    # Financials
    "JPM": "financials", "GS": "financials", "BAC": "financials",
    "MS": "financials", "WFC": "financials", "C": "financials",
    "SCHW": "financials", "BLK": "financials",
    # Energy
    "XOM": "energy", "CVX": "energy", "COP": "energy", "EOG": "energy",
    "SLB": "energy",
    # Consumer Staples
    "KO": "consumer_staples", "PEP": "consumer_staples",
    "PG": "consumer_staples", "CL": "consumer_staples",
    "WMT": "consumer_staples", "MCD": "consumer_staples",
    "COST": "consumer_staples",
    # Industrials
    "CAT": "industrials", "HON": "industrials", "DE": "industrials",
    "GE": "industrials", "RTX": "industrials", "LMT": "industrials",
    # Utilities
    "NEE": "utilities", "DUK": "utilities", "SO": "utilities",
    # Healthcare
    "JNJ": "healthcare", "PFE": "healthcare", "UNH": "healthcare",
    "MRK": "healthcare", "ABBV": "healthcare", "LLY": "healthcare",
    # Consumer Discretionary
    "AMZN": "consumer_discretionary", "HD": "consumer_discretionary",
    "NKE": "consumer_discretionary", "SBUX": "consumer_discretionary",
    # Real Estate
    "AMT": "real_estate", "PLD": "real_estate",
    # Benchmark
    "SPY": "benchmark",
}


def main():
    n = len(V38D_SYMBOLS)
    print("=" * 75)
    print("  EDGECORE v38d -- Phase 5: Surgical Universe (+1 per sector)")
    print(f"  Universe: {n} symbols (v37: 39, +6 curated) — US large-cap singles")
    print("  Phase 5.3: Leverage 1.5× with sector-weight fix")
    print("  v37+L1.5 baseline: +21.42%  S1.67  PF8.41  WR65.2%  23t  DD-1.69%")
    print("=" * 75)
    print()

    s = get_settings()
    # ── Exact v37 settings ──────────────────────────────────────────────────
    s.strategy.lookback_window = 120
    s.strategy.additional_lookback_windows = [63]
    s.strategy.entry_z_score = 1.8
    s.strategy.exit_z_score = 0.2
    s.strategy.entry_z_min_spread = 0.30
    s.strategy.z_score_stop = 2.5
    s.strategy.min_correlation = 0.65       # same as v37
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
    s.risk.max_concurrent_positions = 10    # same as v37
    if hasattr(s.strategy, 'fdr_q_level'):
        s.strategy.fdr_q_level = 0.25       # same as v37

    time_stop = TimeStopManager(TimeStopConfig(
        half_life_multiplier=1.2, max_days_cap=20, default_max_bars=20,
    ))

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000

    print("  Running backtest (2023-03-04 to 2026-03-04)...")
    t0 = time.time()

    metrics = runner.run_unified(
        symbols=V38D_SYMBOLS, start_date="2023-03-04", end_date="2026-03-04",
        sector_map=V38D_SECTOR_MAP, pair_rediscovery_interval=2,
        allocation_per_pair_pct=50.0,    # same as v37
        max_position_loss_pct=0.07,      # same as v37
        max_portfolio_heat=3.0,          # same as v37
        time_stop=time_stop,
        leverage_multiplier=1.5,         # Phase 5.3
    )
    elapsed = time.time() - t0
    print(f"  Completed in {elapsed:.0f}s")
    print()

    # ── Results vs baselines ──────────────────────────────────────────────────
    v37_ret = 21.42   # v37+lever=1.5 (after sector fix)
    v37_s   = 1.67
    v37_pf  = 8.41
    v37_wr  = 65.2
    v37_t   = 23
    v37_dd  = -1.69

    ret = metrics.total_return * 100
    s   = metrics.sharpe_ratio
    pf  = metrics.profit_factor
    wr  = metrics.win_rate * 100
    t   = metrics.total_trades
    dd  = metrics.max_drawdown * 100
    cal = abs(ret / dd) if dd != 0 else 0.0

    print("=" * 75)
    print("  v38d RESULTS vs v37+L1.5 BASELINE")
    print("=" * 75)
    print(f"  Return:  {ret:+.2f}%  (v37: {v37_ret:+.2f}%)  delta={ret-v37_ret:+.2f}%")
    print(f"  Sharpe:  {s:.2f}   (v37: {v37_s})  delta={s-v37_s:+.2f}")
    print(f"  PF:      {pf:.2f}   (v37: {v37_pf})")
    print(f"  WR:      {wr:.1f}%   (v37: {v37_wr}%)")
    print(f"  Trades:  {t}     (v37: {v37_t})  delta={t-v37_t:+d}")
    print(f"  MaxDD:   {dd:.2f}%  (v37: {v37_dd}%)")
    print(f"  Calmar:  {cal:.2f}")
    print()
    print("  TARGET CHECK:")
    print(f"    Sharpe >= 1.5 : {'PASS' if s >= 1.5 else 'MISS'} ({s:.2f})")
    print(f"    Sharpe >= 2.0 : {'PASS' if s >= 2.0 else 'MISS'} ({s:.2f})")
    print(f"    PF     >= 2.5 : {'PASS' if pf >= 2.5 else 'MISS'} ({pf:.2f})")
    print(f"    DD     > -8%  : {'PASS' if dd > -8.0 else 'MISS'} ({dd:.2f}%)")
    print(f"    Trades > v37  : {'PASS' if t > v37_t else 'MISS'} ({t} vs {v37_t})")
    print()
    if s >= 1.5 and t > v37_t:
        print("  >>> Phase 5 PASS: Sharpe >= 1.5 AND trades > v37 <<<")
    elif s >= 1.5:
        print(f"  >>> Sharpe target MET — trades at {t} (need > {v37_t}) <<<")
    else:
        print(f"  >>> Partial targets met — check: Sharpe {s:.2f}<1.5, trades {t} <<<")
    print()


if __name__ == "__main__":
    main()
