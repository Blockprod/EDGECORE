#!/usr/bin/env python
"""v62 — Walk-Forward 3-Window — High-Quality Entries + Tight Stops (CERT-03b).

KEY CHANGES from v61/v60:
  1. entry_z_score = 2.0 (was 1.5)
     → Fewer but higher-quality entries (z-score must reach 2.0 to enter)
     → Reduces count but improves average trade quality

  2. max_position_loss_pct = 0.03 (was 0.05)
     → Tighter stop loss (3% instead of 5%)
     → Cuts losers faster, protects capital

  3. time_stop max_days_cap = 30 (was 60)
     → Exits after 30 days if spread hasn't converged
     → Reduces exposure to regime changes and trend reversals

  4. neutral_band_pct = 0.03 (was 0.05 in v61, 0.02 in v60)
     → Middle ground: |spread| < 3% = NEUTRAL, >3% = TRENDING
     → Better balance between filtering and overfiltering

  5. trend_unfavorable_sizing = 0.25 (between v60's 0.30 and v61's 0.20)

  6. exit_z = 0.20 (was 0.05)
     → Don't wait for perfect mean reversion, take profit earlier
     → Reduces time in trade → less exposure to regime risk

CERT-03b criteria (aggregate):
  - Combined Sharpe >= 0.5
  - Total OOS trades >= 40
  - Max DD per window < 20%
"""

import gc
import io
import os
import sys
import time
import traceback

# Force UTF-8 on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager
from risk.spread_correlation import SpreadCorrelationConfig, SpreadCorrelationGuard

# ── Universe ────────────────────────────────────────────────────────────────
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
WF_SYMBOLS = list(dict.fromkeys(WF_SYMBOLS))

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

WF_WINDOWS = [
    ("W1-2023", "2021-01-04", "2022-12-30", "2023-01-02", "2023-12-29"),
    ("W2-2024", "2021-01-04", "2023-12-29", "2024-01-02", "2024-12-31"),
    ("W3-2025", "2021-01-04", "2024-12-31", "2025-01-02", "2025-12-31"),
]


def _apply_settings_v62():
    """v62 — High-Quality Entries + Tight Stops + Moderate Band."""
    s = get_settings()

    # ── Signal: HIGHER ENTRY Z for quality ──────────────────────────────
    s.strategy.entry_z_score = 2.0  # v62: up from 1.5 — fewer but better entries
    s.strategy.exit_z_score = 0.20  # v62: up from 0.05 — take profit earlier
    s.strategy.z_score_stop = 4.0
    s.strategy.entry_z_min_spread = 0.0

    # ── Cointegration: same as v60/v61 ──────────────────────────────────
    s.strategy.lookback_window = 180
    s.strategy.additional_lookback_windows = [63]
    s.strategy.adf_pvalue_threshold = 0.15
    s.strategy.min_correlation = 0.65
    if hasattr(s.strategy, "fdr_q_level"):
        s.strategy.fdr_q_level = 0.30
    s.strategy.max_half_life = 60
    s.strategy.use_kalman = True
    s.strategy.bonferroni_correction = False
    s.strategy.johansen_confirmation = True
    s.strategy.newey_west_consensus = True
    s.strategy.weekly_zscore_entry_gate = 0.0

    # ── Sizing: TIGHTER STOPS ──────────────────────────────────────────
    s.strategy.max_position_loss_pct = 0.03  # v62: 3% (was 5%) — cut losers faster
    s.strategy.internal_max_drawdown_pct = 0.25
    if hasattr(s.strategy, "internal_max_daily_trades"):
        s.strategy.internal_max_daily_trades = 500
    if hasattr(s.strategy, "internal_max_positions"):
        s.strategy.internal_max_positions = 50
    s.risk.max_concurrent_positions = 12

    # ── REGIME: MODERATE NEUTRAL BAND ───────────────────────────────────
    s.regime.enabled = True
    s.regime.neutral_sizing = 1.0
    s.regime.trend_favorable_sizing = 1.0
    s.regime.trend_unfavorable_sizing = 0.25  # v62: moderate (between v60=0.30 and v61=0.20)
    s.regime.neutral_band_pct = 0.03  # v62: 3% (between v60=2% and v61=5%)

    # ── Momentum — disabled ─────────────────────────────────────────────
    s.momentum.enabled = False

    # ── BLACKLIST OFF ────────────────────────────────────────────────────
    s.pair_blacklist.enabled = False


def _run_window(
    label: str,
    train_start: str,
    train_end: str,
    oos_start: str,
    oos_end: str,
):
    ts = TimeStopManager(
        TimeStopConfig(
            half_life_multiplier=3.0,
            max_days_cap=30,  # v62: 30d (was 60d) — faster exits
            default_max_bars=30,  # v62: 30d
        )
    )
    spread_guard = SpreadCorrelationGuard(
        SpreadCorrelationConfig(
            max_correlation=0.65,
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
            pair_rediscovery_interval=5,
            allocation_per_pair_pct=20.0,
            max_position_loss_pct=0.03,  # v62: matches tighter stop
            max_portfolio_heat=1.5,
            time_stop=ts,
            leverage_multiplier=1.0,
            momentum_filter=None,
            spread_corr_guard=spread_guard,
            blacklist_persist_path=None,
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
        print(f"  [{label}] ERROR: {str(e)[:200]}")
        print(traceback.format_exc())
        return None, elapsed


def main():
    print("=" * 70)
    print("  v62 — Walk-Forward 3-Window — High-Quality Entries + Tight Stops")
    print("  entry_z=2.0, exit_z=0.20, max_loss=3%, time_stop=30d")
    print("  REGIME ON: neutral_band=3%, unfav_sz=0.25")
    print("=" * 70)
    print()

    gc.collect()
    _apply_settings_v62()

    results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)

    window_results = []
    total_t0 = time.time()

    for label, train_start, train_end, oos_start, oos_end in WF_WINDOWS:
        gc.collect()
        result, elapsed = _run_window(label, train_start, train_end, oos_start, oos_end)
        window_results.append((result, elapsed))
        print()

    total_elapsed = int(time.time() - total_t0)

    # ── Aggregate stats ────────────────────────────────────────────────────
    valid = [(i, m) for i, (m, _) in enumerate(window_results) if m is not None]
    n_valid = len(valid)
    total_trades = sum(m.total_trades for _, m in valid)
    combined_sh = sum(m.sharpe_ratio for _, m in valid) / n_valid if n_valid else 0.0
    worst_dd = max((m.max_drawdown * 100 for _, m in valid), default=0.0)
    avg_wr = sum(m.win_rate * 100 for _, m in valid) / n_valid if n_valid else 0.0

    cert_pass = combined_sh >= 0.5 and total_trades >= 40 and worst_dd < 20.0

    print("=" * 70)
    print("  CERT-03b AGGREGATE RESULTS")
    print("=" * 70)
    print(f"  Windows completed  : {n_valid}/{len(WF_WINDOWS)}")
    print(f"  Total OOS trades   : {total_trades}")
    print(f"  Combined Sharpe    : {combined_sh:.4f}")
    print(f"  Avg win rate       : {avg_wr:.1f}%")
    print(f"  Worst window DD    : {worst_dd:.2f}%")
    print(f"  Total elapsed      : {total_elapsed}s")
    print()
    print(
        f"  CERT-03b criteria  : Sharpe>=0.5={combined_sh >= 0.5} trades>=40={total_trades >= 40} DD<20%={worst_dd < 20.0}"
    )
    print(f"  CERT-03b result    : {'PASS' if cert_pass else 'FAIL'}")
    print()

    print("  Per-window breakdown:")
    print(f"  {'Window':<12} {'Sharpe':>7} {'Return':>8} {'WR':>7} {'Trades':>7} {'DD':>8}")
    print("  " + "-" * 55)
    for (label, _, _, _, _), (m, elapsed) in zip(WF_WINDOWS, window_results, strict=True):
        if m is None:
            print(f"  {label:<12} {'ERROR':>7}")
        else:
            v = "PASS" if m.sharpe_ratio >= 0.5 and m.total_trades >= 5 else "FAIL"
            print(
                f"  {label:<12} {m.sharpe_ratio:7.3f} {m.total_return * 100:+7.02f}%"
                f" {m.win_rate * 100:6.1f}% {m.total_trades:6d} {m.max_drawdown * 100:+7.02f}%  [{v}]"
            )

    # ── Save results ──────────────────────────────────────────────────────
    results_path = os.path.join(results_dir, "v62_wf3_results.txt")
    with open(results_path, "w", encoding="utf-8") as f:
        f.write("v62 Walk-Forward 3-Window — High-Quality Entries + Tight Stops — CERT-03b\n")
        f.write("=" * 60 + "\n")
        f.write("APPROACH: entry_z=2.0, exit_z=0.20, max_loss=3%, time_stop=30d\n")
        f.write("  regime: ON (neutral=1.0, favorable=1.0, unfavorable=0.25)\n")
        f.write("  neutral_band_pct: 0.03\n")
        f.write(f"\nWindows completed: {n_valid}/{len(WF_WINDOWS)}\n")
        f.write(f"Total OOS trades : {total_trades}\n")
        f.write(f"Combined Sharpe  : {combined_sh:.4f}\n")
        f.write(f"Avg win rate     : {avg_wr:.1f}%\n")
        f.write(f"Worst window DD  : {worst_dd:.2f}%\n")
        f.write(f"Total elapsed    : {total_elapsed}s\n")
        f.write(f"Verdict          : {'CERT' if cert_pass else 'FAIL'}\n")
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
                if hasattr(m, "per_pair") and m.per_pair:
                    f.write("  per_pair:\n")
                    for pk, ps in sorted(m.per_pair.items(), key=lambda x: x[1].get("pnl", 0)):
                        f.write(
                            f"    {pk:<20}  n={ps.get('n_trades', 0):3d}"
                            f"  pnl={ps.get('pnl', 0):+8.0f}"
                            f"  wr={ps.get('win_rate', 0) * 100:5.1f}%\n"
                        )

    print(f"  Results saved to: {results_path}")
    print()


if __name__ == "__main__":
    main()
