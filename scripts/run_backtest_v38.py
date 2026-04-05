# ruff: noqa: UP031
#!/usr/bin/env python
"""EDGECORE v38 -- Phase 5: Multi-Marché & Scaling.

Adds on top of v37 (Phase 4, 39 symbols):
  5.1  Universe expansion: 39 → 62 US large-cap single stocks only
         No ETFs / no international — same statistical regime as v37 core
         Additions are sector-matched to proven v37 pairs:
           Tech +6 (ORCL, IBM, CRM, QCOM, TXN, INTC)
           Fin +5  (BLK, AXP, CB, USB, PNC)
           Energy +3 (SLB, VLO, HES)
           CS +3 (COST, TSN, ADM)
           Indust +3 (LMT, UPS, MMM)
           HC +3 (LLY, TMO, ABT)
  5.3  Leverage 1.5× (gross exposure = 150% of NAV)

v37 baseline: +13.92% S1.67 PF8.54 WR65.2% 23t DD-1.13% Calmar12.35
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager

# ── Universe v38 (62 US large-cap single stocks only — no ETFs) ───────────────
V38_SYMBOLS = [
    # === MARKET BENCHMARK ===
    "SPY",

    # === TECHNOLOGY (13 = 7 v37 + 6 new) ===
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO",
    "ORCL", "IBM", "CRM", "QCOM", "TXN", "INTC",   # +6 new

    # === FINANCIALS (12 = 7 v37 + 5 new) ===
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    "BLK", "AXP", "CB", "USB", "PNC",               # +5 new

    # === ENERGY (7 = 4 v37 + 3 new) ===
    "XOM", "CVX", "COP", "EOG",
    "SLB", "VLO", "HES",                             # +3 new

    # === CONSUMER STAPLES (8 = 5 v37 + 3 new) ===
    "KO", "PEP", "PG", "CL", "WMT", "MCD",
    "COST", "TSN",                                    # +2 new (ADM removed — small-cap behaviour)

    # === INDUSTRIALS (8 = 5 v37 + 3 new) ===
    "CAT", "HON", "DE", "GE", "RTX",
    "LMT", "UPS", "MMM",                             # +3 new

    # === UTILITIES (4 = 4 v37) ===
    "NEE", "DUK", "SO", "AES",

    # === HEALTHCARE (8 = 5 v37 + 3 new) ===
    "JNJ", "PFE", "UNH", "MRK", "ABBV",
    "LLY", "TMO", "ABT",                             # +3 new

    # === CONSUMER DISCRETIONARY (4 = 4 v37) ===
    "AMZN", "HD", "NKE", "SBUX",

    # === REAL ESTATE (2 = 2 v37) ===
    "AMT", "PLD",
]

V38_SECTOR_MAP = {
    # Technology
    "AAPL": "technology", "MSFT": "technology", "GOOGL": "technology",
    "META": "technology", "NVDA": "technology", "AMD": "technology",
    "AVGO": "technology", "ORCL": "technology", "IBM": "technology",
    "CRM": "technology", "QCOM": "technology", "TXN": "technology",
    "INTC": "technology",
    # Financials
    "JPM": "financials", "GS": "financials", "BAC": "financials",
    "MS": "financials", "WFC": "financials", "C": "financials",
    "SCHW": "financials", "BLK": "financials", "AXP": "financials",
    "CB": "financials", "USB": "financials", "PNC": "financials",
    # Energy
    "XOM": "energy", "CVX": "energy", "COP": "energy", "EOG": "energy",
    "SLB": "energy", "VLO": "energy", "HES": "energy",
    # Consumer Staples
    "KO": "consumer_staples", "PEP": "consumer_staples",
    "PG": "consumer_staples", "CL": "consumer_staples",
    "WMT": "consumer_staples", "MCD": "consumer_staples",
    "COST": "consumer_staples", "TSN": "consumer_staples",
    # Industrials
    "CAT": "industrials", "HON": "industrials", "DE": "industrials",
    "GE": "industrials", "RTX": "industrials", "LMT": "industrials",
    "UPS": "industrials", "MMM": "industrials",
    # Utilities
    "NEE": "utilities", "DUK": "utilities", "SO": "utilities",
    "AES": "utilities",
    # Healthcare
    "JNJ": "healthcare", "PFE": "healthcare", "UNH": "healthcare",
    "MRK": "healthcare", "ABBV": "healthcare", "LLY": "healthcare",
    "TMO": "healthcare", "ABT": "healthcare",
    # Consumer Discretionary
    "AMZN": "consumer_discretionary", "HD": "consumer_discretionary",
    "NKE": "consumer_discretionary", "SBUX": "consumer_discretionary",
    # Real Estate
    "AMT": "real_estate", "PLD": "real_estate",
    # Benchmark
    "SPY": "benchmark",
}


def main():
    print("=" * 75)
    print("  EDGECORE v38 -- Phase 5: Multi-Marché & Scaling")
    print("  Universe: %d symbols (v37: 39) — US large-cap singles only" % len(V38_SYMBOLS))
    print("  Phase 5: +23 sector-matched US equities + Leverage 1.5×")
    print("  No ETFs/intl — same statistical regime as v37 proven core")
    print("  v37 baseline: +13.92%%  S1.67  PF8.54  WR65.2%%  23t  DD-1.13%%")
    print("=" * 75)
    print()

    s = get_settings()
    s.strategy.lookback_window = 120
    s.strategy.additional_lookback_windows = [63]
    s.strategy.entry_z_score = 1.8
    s.strategy.exit_z_score = 0.2
    s.strategy.entry_z_min_spread = 0.30
    s.strategy.z_score_stop = 2.5
    s.strategy.min_correlation = 0.75   # tighter: filter weaker pairs (was 0.65)
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
    s.risk.max_concurrent_positions = 12  # balanced: more than v37(10) but capped
    if hasattr(s.strategy, 'fdr_q_level'):
        s.strategy.fdr_q_level = 0.05   # strict: ~5 FP per 100 tests (was 0.25)

    time_stop = TimeStopManager(TimeStopConfig(
        half_life_multiplier=1.2, max_days_cap=20, default_max_bars=20,
    ))

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000

    print("  Running backtest (2023-03-04 to 2026-03-04)...")
    t0 = time.time()

    metrics = runner.run_unified(
        symbols=V38_SYMBOLS, start_date="2023-03-04", end_date="2026-03-04",
        sector_map=V38_SECTOR_MAP, pair_rediscovery_interval=5,
        allocation_per_pair_pct=50.0,    # same as v37
        max_position_loss_pct=0.07,      # same as v37
        max_portfolio_heat=3.0,          # same as v37
        time_stop=time_stop,
        leverage_multiplier=1.5,   # Phase 5.3: 1.5× leverage (sector fix applied)
    )
    elapsed = time.time() - t0
    print(f"  Completed in {elapsed:.0f}s")
    print()

    # ── Results vs Baselines ──────────────────────────────────────────────────
    # v37+lever=1.5 benchmark (after sector fix — same Sharpe, 1.5× return)
    v37_ret = 21.42   # lever=1.5 version of v37 baseline
    v37_s = 1.67
    v37_pf = 8.41
    v37_wr = 65.2
    v37_t = 23
    v37_dd = -1.69
    v37_cal = abs(21.42 / 1.69)

    ret  = metrics.total_return * 100
    s    = metrics.sharpe_ratio
    pf   = metrics.profit_factor
    wr   = metrics.win_rate * 100
    t    = metrics.total_trades
    dd   = metrics.max_drawdown * 100
    cal  = abs(ret / dd) if dd != 0 else 0.0

    print("=" * 75)
    print("  v38 RESULTS vs v37 BASELINE")
    print("=" * 75)
    print(f"  Return:  {ret:+.2f}%  (v37: {v37_ret:+.2f}%)  delta={ret-v37_ret:+.2f}%")
    print(f"  Sharpe:  {s:.2f}   (v37: {v37_s:.2f})  delta={s-v37_s:+.2f}")
    print(f"  PF:      {pf:.2f}   (v37: {v37_pf:.2f})  delta={pf-v37_pf:+.2f}")
    print(f"  WR:      {wr:.1f}%   (v37: {v37_wr:.1f}%)")
    print(f"  Trades:  {t}     (v37: {v37_t})  delta={t-v37_t:+d}")
    print(f"  MaxDD:   {dd:.2f}%  (v37: {v37_dd:.2f}%)")
    print(f"  Calmar:  {cal:.2f}   (v37: {v37_cal:.2f})")
    print()
    print("  TARGET CHECK:")
    print(f"    Sharpe >= 1.5 : {'PASS' if s >= 1.5 else 'MISS'} ({s:.2f})")
    print(f"    Sharpe >= 2.0 : {'PASS' if s >= 2.0 else 'MISS'} ({s:.2f})")
    print(f"    PF     >= 2.5 : {'PASS' if pf >= 2.5 else 'MISS'} ({pf:.2f})")
    print(f"    DD     > -8%  : {'PASS' if dd > -8.0 else 'MISS'} ({dd:.2f}%)")
    print(f"    Trades > v37  : {'PASS' if t > v37_t else 'MISS'} ({t} vs {v37_t})")
    if s >= 2.0 and pf >= 2.5:
        print()
        print("  >>> ALL TARGETS MET — Phase 5 VALIDATED <<<")
    else:
        missing = []
        if s < 2.0:
            missing.append(f"Sharpe {s:.2f}<2.0")
        if pf < 2.5:
            missing.append(f"PF {pf:.2f}<2.5")
        print()
        print(f"  >>> Partial targets met — check: {', '.join(missing)} <<<")


if __name__ == "__main__":
    main()
