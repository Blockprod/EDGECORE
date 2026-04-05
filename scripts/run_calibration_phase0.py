<<<<<<< HEAD
﻿#!/usr/bin/env python
=======
#!/usr/bin/env python
>>>>>>> origin/main
"""EDGECORE Calibration Study -- Kelly + Almgren-Chriss Tuning.

Ablation showed:
  - Kelly (1/4, max 10%) crushes return from +2.91% to +0.01%
  - Almgren-Chriss (eta=0.10) reduces return from +8.17% to +2.91%
  - EventFilter + BorrowCheck = zero impact on mega-caps

Calibration plan:
  v32e: Almgren eta=0.05 only (no Kelly) -- reduce market impact for mega-caps
  v32f: Kelly as safety net (fraction=0.5, max_pos=50%) + Almgren eta=0.05
  v32g: Full Phase 0 but calibrated (Kelly 0.5/50%, Almgren 0.05, event+borrow)
  v32h: Almgren eta=0.03 only -- minimal impact for liquid mega-caps
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
    """Run one calibration variant."""
    setup_settings()

    # Inject custom cost model into runner
    runner = BacktestRunner()
    runner.config.initial_capital = 100_000

    # We need to pass cost_model through to the simulator.
    # The runner creates CostModel() internally, so we monkeypatch it
    # by importing and modifying the simulator directly.
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
            symbols=SYMBOLS,
            start_date="2023-03-04",
            end_date="2026-03-04",
            sector_map=SECTOR_MAP,
            pair_rediscovery_interval=2,
            allocation_per_pair_pct=50.0,
            max_position_loss_pct=0.07,
            max_portfolio_heat=3.0,
            time_stop=make_time_stop(),
            kelly_sizer=kelly_sizer,
            event_filter=event_filter,
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

    # v32e: Almgren eta=0.05 only
    print("=" * 70)
    print("  [1/4] v32e: Almgren eta=0.05 only (no Kelly)")
    print("=" * 70)
    t0 = time.time()
    cm_05 = CostModel(CostModelConfig(market_impact_eta=0.05))
    r = run_variant("v32e_eta005", cost_model=cm_05)
    print(f"  Done in {time.time()-t0:.0f}s")
    results.append(r)

    # v32f: Kelly safety net + Almgren eta=0.05
    print()
    print("=" * 70)
    print("  [2/4] v32f: Kelly safety-net (0.5, max 50%) + Almgren eta=0.05")
    print("=" * 70)
    t0 = time.time()
    kelly_safe = KellySizer(KellySizerConfig(
        kelly_fraction=0.50,
        max_position_pct=50.0,
        min_position_pct=2.0,
        max_sector_pct=40.0,
        max_gross_leverage=3.0,
        max_loss_per_trade_nav_pct=1.5,
        default_allocation_pct=30.0,
    ))
    r = run_variant("v32f_kelly_safe_eta005", cost_model=cm_05, kelly_sizer=kelly_safe)
    print(f"  Done in {time.time()-t0:.0f}s")
    results.append(r)

    # v32g: Full Phase 0 calibrated
    print()
    print("=" * 70)
    print("  [3/4] v32g: Full Phase 0 calibrated")
    print("         Kelly(0.5, max50%) + Almgren(0.05) + Event + Borrow")
    print("=" * 70)
    t0 = time.time()
    ef = EventFilter(EventFilterConfig(
        gap_sigma_threshold=3.0, blackout_days_before=2,
        blackout_days_after=2, rolling_window=60, enabled=True,
    ))
    bc = BorrowChecker(BorrowCheckerConfig(
        max_borrow_fee_pct=3.0, min_shortable_shares=1_000,
        htb_borrow_fee_pct=5.0, default_borrow_fee_pct=0.5, enabled=True,
    ))
    r = run_variant("v32g_full_calibrated", cost_model=cm_05,
                    kelly_sizer=kelly_safe, event_filter=ef, borrow_checker=bc)
    print(f"  Done in {time.time()-t0:.0f}s")
    results.append(r)

    # v32h: Almgren eta=0.03 only (minimal for liquid mega-caps)
    print()
    print("=" * 70)
    print("  [4/4] v32h: Almgren eta=0.03 only (minimal for mega-caps)")
    print("=" * 70)
    t0 = time.time()
    cm_03 = CostModel(CostModelConfig(market_impact_eta=0.03))
    r = run_variant("v32h_eta003", cost_model=cm_03)
    print(f"  Done in {time.time()-t0:.0f}s")
    results.append(r)

    # RESULTS
    print()
    print()
    print("=" * 70)
    print("  CALIBRATION RESULTS -- Kelly + Almgren-Chriss Tuning")
    print("=" * 70)
    print()
    print("  BASELINE v31h:  +8.17%  Sharpe 1.31  PF 3.88  WR 62.5%  24t  DD -1.79%")
    print("  Ablation v32a:  +2.91%  Sharpe 0.54  PF 1.83  WR 55.6%  18t  DD -3.29%  (eta=0.10)")
    print("  Full v32:       +0.01%  Sharpe 0.06  PF 1.07  WR 55.6%  18t  DD -0.15%")
    print()
    print("-" * 70)

    for r in results:
        print()
        print(f"  >>> {r['label']} <<<")
        print(r["summary"])

    print()
    print("=" * 70)

    # Save
    os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
    out = os.path.join(_ROOT, "results", "calibration_phase0.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("EDGECORE Phase 0 Calibration Study\n")
        f.write("=" * 60 + "\n")
        f.write("Baseline v31h: +8.17%, Sharpe 1.31, PF 3.88, WR 62.5%, 24t\n")
        f.write("Ablation v32a: +2.91%, Sharpe 0.54, PF 1.83, WR 55.6%, 18t (eta=0.10)\n")
        f.write("Full v32:      +0.01%, Sharpe 0.06, PF 1.07, WR 55.6%, 18t\n\n")
        for r in results:
            f.write(f"--- {r['label']} ---\n")
            f.write(r["summary"])
            f.write("\n\n")
    print(f"\n[Saved] {out}")


if __name__ == "__main__":
    main()
