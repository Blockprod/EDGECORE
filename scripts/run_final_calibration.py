#!/usr/bin/env python
"""EDGECORE Final Calibration -- execution_delay + eta tuning.

Previous findings:
  - eta has negligible impact (0.03 vs 0.10 -> ~0.03% difference)
  - The REAL cost driver is timing_cost = sigma * sqrt(T_exec/252)
  - execution_delay_days=0.5 adds ~9 bps/leg for sigma=2%
  - For $100K DMA on mega-caps, execution is near-instant

Tests:
  v32i: delay=0.05, eta=0.05 (no Kelly)     -- realistic DMA mega-cap
  v32j: delay=0.01, eta=0.05 (no Kelly)     -- algo execution on mega-cap
  v32k: delay=0.05, eta=0.05 + Kelly monitor -- full Phase 0 realistic
  v32l: delay=0.05, eta=0.05 + all Phase 0  -- final candidate
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner
from backtests.cost_model import CostModel, CostModelConfig

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


def run_variant(label, cost_model=None, kelly_sizer=None,
                event_filter=None, borrow_checker=None):
    setup_settings()
    runner = BacktestRunner()
    runner.config.initial_capital = 100_000

    from backtests.strategy_simulator import StrategyBacktestSimulator
    _orig_init = StrategyBacktestSimulator.__init__
    _custom_cm = cost_model

    def _patched_init(self, *args, **kwargs):
        _orig_init(self, *args, **kwargs)
        if _custom_cm is not None:
            self.cost_model = _custom_cm

    StrategyBacktestSimulator.__init__ = _patched_init
    try:
        metrics = runner.run_unified(
            symbols=SYMBOLS, start_date="2023-03-04", end_date="2026-03-04",
            sector_map=SECTOR_MAP, pair_rediscovery_interval=2,
            allocation_per_pair_pct=50.0, max_position_loss_pct=0.07,
            max_portfolio_heat=3.0, time_stop=make_time_stop(),
            kelly_sizer=kelly_sizer, event_filter=event_filter,
            borrow_checker=borrow_checker,
        )
    finally:
        StrategyBacktestSimulator.__init__ = _orig_init

    return {"label": label, "summary": metrics.summary(), "metrics": metrics}


def main():
    from risk.kelly_sizing import KellySizer, KellySizerConfig
    from data.event_filter import EventFilter, EventFilterConfig
    from execution.borrow_check import BorrowChecker, BorrowCheckerConfig

    results = []

    # v32i: delay=0.05, eta=0.05, no Kelly
    print("=" * 70)
    print("  [1/4] v32i: Almgren delay=0.05, eta=0.05 (DMA mega-cap)")
    print("=" * 70)
    t0 = time.time()
    cm = CostModel(CostModelConfig(market_impact_eta=0.05, execution_delay_days=0.05))
    r = run_variant("v32i_delay005_eta005", cost_model=cm)
    print(f"  Done in {time.time()-t0:.0f}s")
    results.append(r)

    # v32j: delay=0.01, eta=0.05, no Kelly
    print()
    print("=" * 70)
    print("  [2/4] v32j: Almgren delay=0.01, eta=0.05 (algo execution)")
    print("=" * 70)
    t0 = time.time()
    cm2 = CostModel(CostModelConfig(market_impact_eta=0.05, execution_delay_days=0.01))
    r = run_variant("v32j_delay001_eta005", cost_model=cm2)
    print(f"  Done in {time.time()-t0:.0f}s")
    results.append(r)

    # v32k: delay=0.05, eta=0.05 + Kelly as safety net (high limits)
    print()
    print("=" * 70)
    print("  [3/4] v32k: delay=0.05 + Kelly safety (frac=1.0, max=50%)")
    print("=" * 70)
    t0 = time.time()
    cm3 = CostModel(CostModelConfig(market_impact_eta=0.05, execution_delay_days=0.05))
    kelly = KellySizer(KellySizerConfig(
        kelly_fraction=1.0,           # Full Kelly (as ceiling only)
        max_position_pct=50.0,        # Don't constrain base alloc
        min_position_pct=2.0,
        max_sector_pct=60.0,          # Very permissive
        max_gross_leverage=4.0,       # Won't trigger on $100K
        max_loss_per_trade_nav_pct=3.5, # ~= 7% of 50% alloc
        default_allocation_pct=50.0,  # Match base allocation
    ))
    r = run_variant("v32k_delay005_kelly_safe", cost_model=cm3, kelly_sizer=kelly)
    print(f"  Done in {time.time()-t0:.0f}s")
    results.append(r)

    # v32l: Full Phase 0 with optimal params
    print()
    print("=" * 70)
    print("  [4/4] v32l: Full Phase 0 optimal")
    print("         Almgren(0.05/0.05) + Kelly(1.0/50%) + Event + Borrow")
    print("=" * 70)
    t0 = time.time()
    cm4 = CostModel(CostModelConfig(market_impact_eta=0.05, execution_delay_days=0.05))
    kelly2 = KellySizer(KellySizerConfig(
        kelly_fraction=1.0, max_position_pct=50.0, min_position_pct=2.0,
        max_sector_pct=60.0, max_gross_leverage=4.0,
        max_loss_per_trade_nav_pct=3.5, default_allocation_pct=50.0,
    ))
    ef = EventFilter(EventFilterConfig(
        gap_sigma_threshold=3.0, blackout_days_before=2,
        blackout_days_after=2, rolling_window=60, enabled=True,
    ))
    bc = BorrowChecker(BorrowCheckerConfig(
        max_borrow_fee_pct=3.0, min_shortable_shares=1_000,
        htb_borrow_fee_pct=5.0, default_borrow_fee_pct=0.5, enabled=True,
    ))
    r = run_variant("v32l_full_optimal", cost_model=cm4,
                    kelly_sizer=kelly2, event_filter=ef, borrow_checker=bc)
    print(f"  Done in {time.time()-t0:.0f}s")
    results.append(r)

    # RESULTS
    print()
    print()
    print("=" * 70)
    print("  FINAL CALIBRATION -- Execution Delay + Full Phase 0")
    print("=" * 70)
    print()
    print("  BASELINE v31h:   +8.17%  Sharpe 1.31  PF 3.88  WR 62.5%  24t  DD -1.79%")
    print("  Old v32a eta010: +2.91%  Sharpe 0.54  PF 1.83  WR 55.6%  18t  DD -3.29%")
    print()
    print("-" * 70)

    for r in results:
        print()
        print(f"  >>> {r['label']} <<<")
        print(r["summary"])

    print()
    print("=" * 70)

    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    out = os.path.join(_ROOT, "results", "final_calibration_phase0.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("EDGECORE Phase 0 Final Calibration\n")
        f.write("=" * 60 + "\n")
        f.write("Baseline v31h: +8.17%, Sharpe 1.31, PF 3.88, WR 62.5%, 24t\n\n")
        for r in results:
            f.write(f"--- {r['label']} ---\n")
            f.write(r["summary"])
            f.write("\n\n")
    print(f"\n[Saved] {out}")


if __name__ == "__main__":
    main()
