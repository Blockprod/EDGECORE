<<<<<<< HEAD
﻿#!/usr/bin/env python
=======
#!/usr/bin/env python
>>>>>>> origin/main
"""EDGECORE Ablation Study -- Phase 0 Factor Isolation.

Runs 4 backtests, each with exactly ONE Phase 0 component active:
  v32a: Almgren-Chriss slippage ONLY
  v32b: Kelly sizing + NAV stop ONLY
  v32c: EventFilter ONLY
  v32d: BorrowChecker ONLY

Baseline: v31h = +8.17%, Sharpe 1.31, PF 3.88, WR 62.5%, 24 trades, DD -1.79%
Full v32: +0.01%, Sharpe 0.06, PF 1.07, WR 55.6%, 18 trades

Goal: identify which factor costs how much performance.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# == v30b Universe ==
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


def setup_v31h_settings():
    """Apply v31h settings (shared across all ablation runs)."""
    from config.settings import get_settings
    settings = get_settings()

    settings.strategy.lookback_window = 120
    settings.strategy.additional_lookback_windows = [63]
    settings.strategy.entry_z_score = 1.8
    settings.strategy.exit_z_score = 0.5
    settings.strategy.entry_z_min_spread = 0.30
    settings.strategy.z_score_stop = 3.0
    settings.strategy.min_correlation = 0.65
    settings.strategy.max_half_life = 60
    settings.strategy.max_position_loss_pct = 0.07
    settings.strategy.internal_max_drawdown_pct = 0.25
    settings.strategy.use_kalman = True
    settings.strategy.bonferroni_correction = True
    settings.strategy.johansen_confirmation = True
    settings.strategy.newey_west_consensus = True
    settings.strategy.weekly_zscore_entry_gate = 0.3

    settings.strategy.regime_directional_filter = False
    settings.strategy.trend_long_sizing = 0.75
    settings.strategy.disable_shorts_in_bull_trend = False
    settings.strategy.short_sizing_multiplier = 0.50

    settings.regime.enabled = True
    settings.regime.ma_fast = 50
    settings.regime.ma_slow = 200
    settings.regime.vol_threshold = 0.18
    settings.regime.vol_window = 20
    settings.regime.neutral_band_pct = 0.02
    settings.regime.trend_favorable_sizing = 1.0
    settings.regime.neutral_sizing = 0.70

    settings.momentum.enabled = True
    settings.momentum.lookback = 20
    settings.momentum.weight = 0.30
    settings.momentum.min_strength = 1.0
    settings.momentum.max_boost = 1.0

    settings.pair_blacklist.enabled = True
    settings.pair_blacklist.max_consecutive_losses = 5
    settings.pair_blacklist.cooldown_days = 10

    settings.risk.max_concurrent_positions = 10

    if hasattr(settings.strategy, 'fdr_q_level'):
        settings.strategy.fdr_q_level = 0.25

    return settings


def make_time_stop():
    from execution.time_stop import TimeStopConfig, TimeStopManager
    return TimeStopManager(TimeStopConfig(
        half_life_multiplier=1.5,
        max_days_cap=30,
        default_max_bars=30,
    ))


def run_ablation(label, kelly_sizer=None, event_filter=None, borrow_checker=None):
    """Run one ablation variant and return key metrics."""
    from backtests.runner import BacktestRunner

    setup_v31h_settings()
    runner = BacktestRunner()
    runner.config.initial_capital = 100_000

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

    summary = metrics.summary()
    return {
        "label": label,
        "summary": summary,
        "metrics": metrics,
    }


def main():
    from data.event_filter import EventFilter, EventFilterConfig
    from execution.borrow_check import BorrowChecker, BorrowCheckerConfig
    from risk.kelly_sizing import KellySizer, KellySizerConfig

    results = []

    # =========================================================
    # v32a: Almgren-Chriss ONLY (already default in CostModel)
    # No Kelly, no EventFilter, no BorrowChecker
    # The Almgren-Chriss model is baked into CostModel default
    # so running with NO extra components = Almgren-Chriss only
    # =========================================================
    print("=" * 70)
    print("  [1/4] v32a: Almgren-Chriss slippage ONLY")
    print("=" * 70)
    t0 = time.time()
    r = run_ablation("v32a_almgren_only")
    print(f"  Done in {time.time()-t0:.0f}s")
    results.append(r)

    # =========================================================
    # v32b: Kelly ONLY
    # =========================================================
    print()
    print("=" * 70)
    print("  [2/4] v32b: Kelly sizing ONLY (1/4 Kelly)")
    print("=" * 70)
    t0 = time.time()
    kelly = KellySizer(KellySizerConfig(
        kelly_fraction=0.25,
        max_position_pct=10.0,
        min_position_pct=2.0,
        max_sector_pct=25.0,
        max_gross_leverage=2.0,
        max_loss_per_trade_nav_pct=0.75,
        default_allocation_pct=8.0,
    ))
    r = run_ablation("v32b_kelly_only", kelly_sizer=kelly)
    print(f"  Done in {time.time()-t0:.0f}s")
    results.append(r)

    # =========================================================
    # v32c: EventFilter ONLY
    # =========================================================
    print()
    print("=" * 70)
    print("  [3/4] v32c: EventFilter ONLY (3-sigma, +/-3d)")
    print("=" * 70)
    t0 = time.time()
    ef = EventFilter(EventFilterConfig(
        gap_sigma_threshold=3.0,
        blackout_days_before=3,
        blackout_days_after=3,
        rolling_window=60,
        enabled=True,
    ))
    r = run_ablation("v32c_event_only", event_filter=ef)
    print(f"  Done in {time.time()-t0:.0f}s")
    results.append(r)

    # =========================================================
    # v32d: BorrowChecker ONLY
    # =========================================================
    print()
    print("=" * 70)
    print("  [4/4] v32d: BorrowChecker ONLY")
    print("=" * 70)
    t0 = time.time()
    bc = BorrowChecker(BorrowCheckerConfig(
        max_borrow_fee_pct=3.0,
        min_shortable_shares=1_000,
        htb_borrow_fee_pct=5.0,
        default_borrow_fee_pct=0.5,
        enabled=True,
    ))
    r = run_ablation("v32d_borrow_only", borrow_checker=bc)
    print(f"  Done in {time.time()-t0:.0f}s")
    results.append(r)

    # =========================================================
    # RESULTS SUMMARY
    # =========================================================
    print()
    print()
    print("=" * 70)
    print("  ABLATION STUDY RESULTS -- Phase 0 Factor Isolation")
    print("=" * 70)
    print()
    print("  BASELINE: v31h = +8.17%, Sharpe 1.31, PF 3.88, WR 62.5%,")
    print("                   24 trades, DD -1.79%, Calmar 4.56")
    print()
    print("  FULL v32: +0.01%, Sharpe 0.06, PF 1.07, WR 55.6%,")
    print("                   18 trades, DD -0.15%")
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
    out_path = os.path.join(_ROOT, "results", "ablation_phase0.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("EDGECORE Phase 0 Ablation Study\n")
        f.write("=" * 60 + "\n")
        f.write("Baseline: v31h = +8.17%, Sharpe 1.31, PF 3.88, WR 62.5%, 24 trades\n")
        f.write("Full v32: +0.01%, Sharpe 0.06, PF 1.07, WR 55.6%, 18 trades\n\n")
        for r in results:
            f.write(f"--- {r['label']} ---\n")
            f.write(r["summary"])
            f.write("\n\n")
    print(f"\n[Saved] {out_path}")


if __name__ == "__main__":
    main()
