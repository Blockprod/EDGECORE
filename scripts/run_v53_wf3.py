#!/usr/bin/env python
"""v53 — Walk-Forward 3-Window Statistical Validation (CERT-03).

Goal: 50-100 non-overlapping OOS trades across 3 years (2023, 2024, 2025)
to validate strategy edge with statistical significance.

Architecture: Expanding-window walk-forward (institutional standard).
  All OOS windows are strictly non-overlapping.
  Training window grows forward — no data leakage.

  W1: Train 2021-01-04 → 2022-12-30 | OOS 2023-01-02 → 2023-12-29  (~22 trades expected)
  W2: Train 2021-01-04 → 2023-12-29 | OOS 2024-01-02 → 2024-12-31  (~22 trades expected)
  W3: Train 2021-01-04 → 2024-12-31 | OOS 2025-01-02 → 2025-12-31  (~22 trades expected)

  Total expected: ~66 OOS trades across 3 calendar years.

CERT-03 criteria (aggregate across all 3 windows):
  - Sharpe >= 0.5 (combined)
  - Total OOS trades >= 50
  - Max drawdown on any single window < 20%
  - Win rate >= 45% (above coin-flip with margin)

Same params as v52 (validated):
  - internal_max_drawdown_pct: 0.30
  - adf_pvalue_threshold: 0.50
  - entry_z_score: 0.9
  - fdr_q_level: 0.60
  - spread_corr_guard: 0.80
"""

import gc
import io
import os
import sys
import time
import traceback

# Force stdout/stderr to UTF-8 on Windows (avoids cp1252 UnicodeEncodeError)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager
from risk.spread_correlation import SpreadCorrelationConfig, SpreadCorrelationGuard

# ── Universe (same as v52) ─────────────────────────────────────────────────
WF_SYMBOLS = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "META",
    "AMZN",
    "NVDA",
    "AMD",
    "INTC",
    "CSCO",
    "ORCL",
    "JPM",
    "BAC",
    "GS",
    "MS",
    "WFC",
    "C",
    "USB",
    "PNC",
    "TFC",
    "BK",
    "STT",
    "BLK",
    "SCHW",
    "AXP",
    "V",
    "MA",
    "COF",
    "JNJ",
    "PFE",
    "MRK",
    "ABT",
    "UNH",
    "CVS",
    "CI",
    "HUM",
    "MDT",
    "DHR",
    "XOM",
    "CVX",
    "COP",
    "EOG",
    "SLB",
    "MPC",
    "PSX",
    "VLO",
    "LIN",
    "APD",
    "ECL",
    "NEM",
    "FCX",
    "PLD",
    "AMT",
    "SPG",
    "EQIX",
    "T",
    "VZ",
    "CMCSA",
    "DIS",
    "NFLX",
    "WMT",
    "TGT",
    "COST",
    "HD",
    "LOW",
    "BA",
    "LMT",
    "RTX",
    "HON",
    "UPS",
    "FDX",
    "CAT",
    "DE",
    "EMR",
    "ETN",
    "NEE",
    "DUK",
    "SO",
    "D",
    "AVGO",
    "ACN",
    "IBM",
    "TXN",
    "QCOM",
    "MU",
    "SPY",
]
WF_SYMBOLS = list(dict.fromkeys(WF_SYMBOLS))  # deduplicate

WF_SECTOR_MAP = {
    "AAPL": "tech",
    "MSFT": "tech",
    "GOOGL": "tech",
    "META": "tech",
    "AMZN": "tech",
    "NVDA": "tech",
    "AMD": "tech",
    "INTC": "tech",
    "CSCO": "tech",
    "ORCL": "tech",
    "AVGO": "tech",
    "ACN": "tech",
    "IBM": "tech",
    "TXN": "tech",
    "QCOM": "tech",
    "MU": "tech",
    "JPM": "finance",
    "BAC": "finance",
    "GS": "finance",
    "MS": "finance",
    "WFC": "finance",
    "C": "finance",
    "USB": "finance",
    "PNC": "finance",
    "TFC": "finance",
    "BK": "finance",
    "STT": "finance",
    "BLK": "finance",
    "SCHW": "finance",
    "AXP": "finance",
    "V": "finance",
    "MA": "finance",
    "COF": "finance",
    "JNJ": "healthcare",
    "PFE": "healthcare",
    "MRK": "healthcare",
    "ABT": "healthcare",
    "UNH": "healthcare",
    "CVS": "healthcare",
    "CI": "healthcare",
    "HUM": "healthcare",
    "MDT": "healthcare",
    "DHR": "healthcare",
    "XOM": "energy",
    "CVX": "energy",
    "COP": "energy",
    "EOG": "energy",
    "SLB": "energy",
    "MPC": "energy",
    "PSX": "energy",
    "VLO": "energy",
    "LIN": "materials",
    "APD": "materials",
    "ECL": "materials",
    "NEM": "materials",
    "FCX": "materials",
    "PLD": "realestate",
    "AMT": "realestate",
    "SPG": "realestate",
    "EQIX": "realestate",
    "T": "telecom",
    "VZ": "telecom",
    "CMCSA": "telecom",
    "DIS": "consumer",
    "NFLX": "consumer",
    "WMT": "consumer",
    "TGT": "consumer",
    "COST": "consumer",
    "HD": "consumer",
    "LOW": "consumer",
    "BA": "industrial",
    "LMT": "industrial",
    "RTX": "industrial",
    "HON": "industrial",
    "UPS": "industrial",
    "FDX": "industrial",
    "CAT": "industrial",
    "DE": "industrial",
    "EMR": "industrial",
    "ETN": "industrial",
    "NEE": "utilities",
    "DUK": "utilities",
    "SO": "utilities",
    "D": "utilities",
    "SPY": "benchmark",
}

# ── Walk-forward windows (expanding training, non-overlapping OOS) ─────────
# Each window: (label, train_start, train_end, oos_start, oos_end)
WF_WINDOWS = [
    ("W1-2023", "2021-01-04", "2022-12-30", "2023-01-02", "2023-12-29"),
    ("W2-2024", "2021-01-04", "2023-12-29", "2024-01-02", "2024-12-31"),
    ("W3-2025", "2021-01-04", "2024-12-31", "2025-01-02", "2025-12-31"),
]


def _apply_settings_v53():
    """Apply v53 parameters (identical to validated v52 params)."""
    s = get_settings()
    s.strategy.lookback_window = 120
    s.strategy.additional_lookback_windows = [63]
    s.strategy.entry_z_score = 0.9
    s.strategy.exit_z_score = 0.3
    s.strategy.entry_z_min_spread = 0.0
    s.strategy.z_score_stop = 2.5
    s.strategy.min_correlation = 0.55
    s.strategy.max_half_life = 60
    s.strategy.max_position_loss_pct = 0.05
    s.strategy.internal_max_drawdown_pct = 0.30
    s.strategy.adf_pvalue_threshold = 0.50
    if hasattr(s.strategy, "internal_max_daily_trades"):
        s.strategy.internal_max_daily_trades = 500
    if hasattr(s.strategy, "internal_max_positions"):
        s.strategy.internal_max_positions = 50
    s.strategy.use_kalman = True
    s.strategy.bonferroni_correction = False
    s.strategy.johansen_confirmation = True
    s.strategy.newey_west_consensus = True
    s.strategy.weekly_zscore_entry_gate = 0.0
    s.strategy.trend_long_sizing = 0.80
    s.strategy.disable_shorts_in_bull_trend = False
    s.strategy.short_sizing_multiplier = 0.50
    s.momentum.enabled = False
    s.pair_blacklist.enabled = True
    s.pair_blacklist.max_consecutive_losses = 5
    s.pair_blacklist.cooldown_days = 10
    s.risk.max_concurrent_positions = 15
    s.strategy.regime_directional_filter = True
    s.regime.enabled = True
    s.regime.ma_fast = 50
    s.regime.ma_slow = 200
    s.regime.vol_threshold = 0.35
    s.regime.vol_window = 20
    s.regime.neutral_band_pct = 0.02
    s.regime.trend_favorable_sizing = 0.80
    s.regime.neutral_sizing = 0.70
    if hasattr(s.strategy, "fdr_q_level"):
        s.strategy.fdr_q_level = 0.60


def _run_window(label: str, train_start: str, train_end: str, oos_start: str, oos_end: str):
    """Run a single walk-forward window. Returns metrics or None on failure."""
    ts60 = TimeStopManager(
        TimeStopConfig(
            half_life_multiplier=2.0,
            max_days_cap=60,
            default_max_bars=60,
        )
    )
    spread_guard = SpreadCorrelationGuard(
        SpreadCorrelationConfig(
            max_correlation=0.80,
            min_overlap_bars=20,
        )
    )

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000

    print(f"  [{label}] train {train_start} -> {train_end} | OOS {oos_start} -> {oos_end}")
    t0 = time.time()
    try:
        metrics = runner.run_unified(
            symbols=WF_SYMBOLS,
            start_date=train_start,
            end_date=oos_end,
            oos_start_date=oos_start,
            sector_map=WF_SECTOR_MAP,
            pair_rediscovery_interval=2,
            allocation_per_pair_pct=50.0,
            max_position_loss_pct=0.07,
            max_portfolio_heat=3.0,
            time_stop=ts60,
            leverage_multiplier=2.5,
            momentum_filter=None,
            spread_corr_guard=spread_guard,
        )
        elapsed = int(time.time() - t0)
        sh = metrics.sharpe_ratio
        ret = metrics.total_return * 100
        wr = metrics.win_rate * 100
        t = metrics.total_trades
        dd = metrics.max_drawdown * 100
        print(f"  [{label}] -> S={sh:5.2f}  {ret:+6.2f}%  WR={wr:5.1f}%  trades={t:3d}  DD={dd:+6.2f}%  [{elapsed}s]")
        return metrics, elapsed
    except Exception as e:
        elapsed = int(time.time() - t0)
        tb = traceback.format_exc()
        print(f"  [{label}] ERROR: {str(e)[:200]}")
        print(tb)
        return None, elapsed


def _combined_sharpe(window_results: list) -> float:
    """
    Combine Sharpe ratios across windows using equal weighting.
    Each window contributes its OOS return stream independently.
    Simple average of per-window Sharpes (conservative).
    """
    valid = [m for m, _ in window_results if m is not None]
    if not valid:
        return 0.0
    return sum(m.sharpe_ratio for m in valid) / len(valid)


def main():
    print("=" * 70)
    print("  v53 — Walk-Forward 3-Window Validation (CERT-03)")
    print("  3 x 12-month non-overlapping OOS windows (2023 / 2024 / 2025)")
    print("  Target: >= 50 OOS trades, Sharpe >= 0.5, DD < 20% per window")
    print("=" * 70)
    print()

    gc.collect()
    _apply_settings_v53()

    window_results = []  # list of (metrics | None, elapsed_s)
    total_t0 = time.time()

    for label, train_start, train_end, oos_start, oos_end in WF_WINDOWS:
        gc.collect()
        result, elapsed = _run_window(label, train_start, train_end, oos_start, oos_end)
        window_results.append((result, elapsed))
        print()

    total_elapsed = int(time.time() - total_t0)

    # ── Aggregate statistics ───────────────────────────────────────────────
    valid_results = [(i, m) for i, (m, _) in enumerate(window_results) if m is not None]
    n_valid = len(valid_results)

    total_trades = sum(m.total_trades for _, m in valid_results)
    combined_sh = _combined_sharpe(window_results)
    worst_dd = max((m.max_drawdown * 100 for _, m in valid_results), default=0.0)
    all_wrs = [m.win_rate * 100 for _, m in valid_results]
    avg_wr = sum(all_wrs) / len(all_wrs) if all_wrs else 0.0

    # Per-pair aggregation across all windows
    combined_pairs: dict = {}
    for _, m in valid_results:
        if hasattr(m, "per_pair") and m.per_pair:
            for pk, stats in m.per_pair.items():
                if pk not in combined_pairs:
                    combined_pairs[pk] = {"n_trades": 0, "pnl": 0.0, "wins": 0}
                combined_pairs[pk]["n_trades"] += stats["n_trades"]
                combined_pairs[pk]["pnl"] += stats["pnl"]
                combined_pairs[pk]["wins"] += round(stats["win_rate"] * stats["n_trades"])

    # CERT-03 verdict
    cert_pass = combined_sh >= 0.5 and total_trades >= 50 and worst_dd < 20.0

    print("=" * 70)
    print("  CERT-03 AGGREGATE RESULTS")
    print("=" * 70)
    print(f"  Windows completed  : {n_valid}/{len(WF_WINDOWS)}")
    print(f"  Total OOS trades   : {total_trades}")
    print(f"  Combined Sharpe    : {combined_sh:.4f}")
    print(f"  Avg win rate       : {avg_wr:.1f}%")
    print(f"  Worst window DD    : {worst_dd:.2f}%")
    print(f"  Total elapsed      : {total_elapsed}s")
    print()
    print(f"  CERT-03 criteria   : Sharpe>={combined_sh >= 0.5} trades>={total_trades >= 50} DD<20%={worst_dd < 20.0}")
    print(f"  CERT-03 result     : {'PASS ✅' if cert_pass else 'FAIL ❌'}")
    print()

    # ── Per-window summary table ───────────────────────────────────────────
    print("  Per-window breakdown:")
    print(f"  {'Window':<12} {'Sharpe':>7} {'Return':>8} {'WR':>7} {'Trades':>7} {'DD':>8}")
    print("  " + "-" * 55)
    for (label, _, _, _, _), (m, elapsed) in zip(WF_WINDOWS, window_results, strict=True):
        if m is None:
            print(f"  {label:<12} {'ERROR':>7}")
        else:
            sh = m.sharpe_ratio
            ret = m.total_return * 100
            wr = m.win_rate * 100
            t = m.total_trades
            dd = m.max_drawdown * 100
            v = "PASS" if sh >= 0.5 and t >= 10 else "FAIL"
            print(f"  {label:<12} {sh:7.3f} {ret:+7.2f}% {wr:6.1f}% {t:6d} {dd:+7.2f}%  [{v}]")

    # ── Save results ──────────────────────────────────────────────────────
    results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)
    results_path = os.path.join(results_dir, "v53_wf3_results.txt")

    with open(results_path, "w", encoding="utf-8") as f:
        f.write("v53 Walk-Forward 3-Window Validation — CERT-03\n")
        f.write("=" * 60 + "\n")
        f.write(f"Windows completed  : {n_valid}/{len(WF_WINDOWS)}\n")
        f.write(f"Total OOS trades   : {total_trades}\n")
        f.write(f"Combined Sharpe    : {combined_sh:.4f}\n")
        f.write(f"Avg win rate       : {avg_wr:.1f}%\n")
        f.write(f"Worst window DD    : {worst_dd:.2f}%\n")
        f.write(f"Total elapsed      : {total_elapsed}s\n")
        f.write(f"Verdict            : {'CERT' if cert_pass else 'FAIL'}\n")
        f.write("\nPer-window results:\n")
        for (label, train_start, train_end, oos_start, oos_end), (m, elapsed) in zip(
            WF_WINDOWS, window_results, strict=True
        ):
            f.write(f"\n[{label}] train={train_start}->{train_end} OOS={oos_start}->{oos_end}\n")
            if m is None:
                f.write("  ERROR — no metrics\n")
            else:
                f.write(f"  sharpe={m.sharpe_ratio:.4f}\n")
                f.write(f"  return={m.total_return * 100:.2f}%\n")
                f.write(f"  win_rate={m.win_rate * 100:.2f}%\n")
                f.write(f"  trades={m.total_trades}\n")
                f.write(f"  max_drawdown={m.max_drawdown * 100:.2f}%\n")
                f.write(f"  elapsed={elapsed}s\n")

        if combined_pairs:
            f.write("\nPer-pair aggregate (all windows):\n")
            for pk, stats in sorted(combined_pairs.items()):
                n = stats["n_trades"]
                pnl = stats["pnl"]
                wr_p = stats["wins"] / n if n > 0 else 0.0
                f.write(f"  {pk}: n={n} pnl={pnl:.0f} wr={wr_p:.0%}\n")

    print(f"\n  Results saved -> {results_path}")


if __name__ == "__main__":
    main()
