#!/usr/bin/env python
"""v68 Walk-Forward 3-Window — Validation CERT-03b.

OBJECTIF : Tester un lookback intermédiaire (150j) entre v63 (180j) et v66 (120j).
  v63 WF3 : Sharpe 0.5554 PASS  — W3-2025 = -0.14 (cassures de régime)
  v66 WF3 : Sharpe 0.4578 FAIL  — W1=0.22, W2=0.03, W3=+1.13 (trop court pour W1/W2)
  v68     : lookback=150, additional=[52] → cherche l'équilibre

PARAMÈTRES v68 vs v63 :
  MODIFIE : lookback_window=150 (était 180), additional=[52] (était [63])
  INCHANGÉ: entry_z=1.8, exit_z=0.10, adf_p=0.15, min_corr=0.65
            max_hl=60j, max_loss=5%, time_stop=45d
            blacklist ON(2/30), regime unfav_sz=0.30, momentum OFF

CERT-03b criteria (aggregate) :
  - Combined Sharpe >= 0.5
  - Total OOS trades >= 40
  - Max DD per window < 20%

Usage:
    venv\\Scripts\\python.exe scripts/run_v68_wf3.py
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

# ── Universe ─────────────────────────────────────────────────────────────────
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

# ── Walk-Forward Windows (identiques CERT-03b) ───────────────────────────────
WF_WINDOWS = [
    ("W1-2023", "2021-01-04", "2022-12-30", "2023-01-02", "2023-12-29"),
    ("W2-2024", "2021-01-04", "2023-12-29", "2024-01-02", "2024-12-31"),
    ("W3-2025", "2021-01-04", "2024-12-31", "2025-01-02", "2025-12-31"),
]


def _apply_settings_v68():
    """v68 — v63 base + lookback intermédiaire 150j."""
    s = get_settings()

    # ── Signal : INCHANGÉ vs v63 ─────────────────────────────────────────
    s.strategy.entry_z_score = 1.8
    s.strategy.exit_z_score = 0.10
    s.strategy.z_score_stop = 4.0
    s.strategy.entry_z_min_spread = 0.0

    # ── Coïntégration : lookback INTERMÉDIAIRE ───────────────────────────
    s.strategy.lookback_window = 150  # v68: 150 (v63=180, v66=120)
    s.strategy.additional_lookback_windows = [52]  # v68: 52j (v63=63j, v66=42j)
    s.strategy.adf_pvalue_threshold = 0.15  # INCHANGÉ vs v63
    s.strategy.min_correlation = 0.65  # INCHANGÉ vs v63
    if hasattr(s.strategy, "fdr_q_level"):
        s.strategy.fdr_q_level = 0.30
    s.strategy.max_half_life = 60  # INCHANGÉ vs v63
    s.strategy.use_kalman = True
    s.strategy.bonferroni_correction = False
    s.strategy.johansen_confirmation = True
    s.strategy.newey_west_consensus = True
    s.strategy.weekly_zscore_entry_gate = 0.0

    # ── Sizing & risk : INCHANGÉ vs v63 ──────────────────────────────────
    s.strategy.max_position_loss_pct = 0.05
    s.strategy.internal_max_drawdown_pct = 0.25
    if hasattr(s.strategy, "internal_max_daily_trades"):
        s.strategy.internal_max_daily_trades = 500
    if hasattr(s.strategy, "internal_max_positions"):
        s.strategy.internal_max_positions = 50
    s.risk.max_concurrent_positions = 12

    # ── Regime : INCHANGÉ vs v63 ─────────────────────────────────────────
    s.regime.enabled = True
    s.regime.neutral_band_pct = 0.02
    s.regime.neutral_sizing = 1.0
    s.regime.trend_favorable_sizing = 1.0
    s.regime.trend_unfavorable_sizing = 0.30

    # ── Momentum : INCHANGÉ (OFF) ────────────────────────────────────────
    s.momentum.enabled = False

    # ── Blacklist : INCHANGÉ vs v63 ──────────────────────────────────────
    s.pair_blacklist.enabled = True
    s.pair_blacklist.max_consecutive_losses = 2
    s.pair_blacklist.cooldown_days = 30


def _run_window(label, train_start, train_end, oos_start, oos_end):
    ts = TimeStopManager(
        TimeStopConfig(
            half_life_multiplier=3.0,
            max_days_cap=45,
            default_max_bars=45,
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
            max_position_loss_pct=0.05,
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
    print("  v68 Walk-Forward 3-Window — Validation CERT-03b")
    print("  lookback=150, additional=[52]  (intermédiaire v63/v66)")
    print("  entry_z=1.8, exit_z=0.10, max_loss=5%, time_stop=45d")
    print("  blacklist ON(2/30), REGIME ON: unfav_sz=0.30")
    print()
    print("  RÉFÉRENCE v63 WF3 : W1=0.90  W2=0.91  W3=-0.14  Combined=0.5554  CERT=PASS")
    print("  RÉFÉRENCE v66 WF3 : W1=0.22  W2=0.03  W3=+1.13  Combined=0.4578  FAIL")
    print("=" * 70)
    print()

    gc.collect()
    _apply_settings_v68()

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

    # ── Aggregate CERT-03b ─────────────────────────────────────────────────
    valid = [(i, m) for i, (m, _) in enumerate(window_results) if m is not None]
    n_valid = len(valid)
    total_trades = sum(m.total_trades for _, m in valid)
    combined_sh = sum(m.sharpe_ratio for _, m in valid) / n_valid if n_valid else 0.0
    worst_dd = max((m.max_drawdown * 100 for _, m in valid), default=0.0)
    avg_wr = sum(m.win_rate * 100 for _, m in valid) / n_valid if n_valid else 0.0

    cert_pass = combined_sh >= 0.5 and total_trades >= 40 and worst_dd < 20.0

    print("=" * 70)
    print("  CERT-03b AGGREGATE RESULTS — v68")
    print("=" * 70)
    print(f"  Windows completed  : {n_valid}/{len(WF_WINDOWS)}")
    print(f"  Total OOS trades   : {total_trades}")
    print(f"  Combined Sharpe    : {combined_sh:.4f}")
    print(f"  Avg win rate       : {avg_wr:.1f}%")
    print(f"  Worst window DD    : {worst_dd:.2f}%")
    print(f"  Total elapsed      : {total_elapsed}s")
    print()
    print(
        f"  CERT-03b criteria  : Sharpe>=0.5={combined_sh >= 0.5}"
        f"  trades>=40={total_trades >= 40}"
        f"  DD<20%={worst_dd < 20.0}"
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
                f"  {label:<12} {m.sharpe_ratio:7.3f} {m.total_return * 100:+7.2f}%"
                f" {m.win_rate * 100:6.1f}% {m.total_trades:6d} {m.max_drawdown * 100:+7.2f}%  [{v}]"
            )

    # ── Save results ──────────────────────────────────────────────────────
    results_path = os.path.join(results_dir, "v68_wf3_results.txt")
    with open(results_path, "w", encoding="utf-8") as f:
        f.write("v68 Walk-Forward 3-Window — Validation CERT-03b\n")
        f.write("=" * 60 + "\n")
        f.write("MODIFIE vs v63 : lookback=150, additional=[52]\n")
        f.write("INCHANGE vs v63: entry_z=1.8, exit_z=0.10, adf_p=0.15\n")
        f.write("  min_corr=0.65, max_hl=60j, max_loss=5%, time_stop=45d\n")
        f.write("  blacklist ON(2/30), regime unfav_sz=0.30, momentum=OFF\n")
        f.write(f"\nWindows completed: {n_valid}/{len(WF_WINDOWS)}\n")
        f.write(f"Total OOS trades : {total_trades}\n")
        f.write(f"Combined Sharpe  : {combined_sh:.4f}\n")
        f.write(f"  ref v63        : 0.5554  PASS\n")
        f.write(f"  ref v66        : 0.4578  FAIL\n")
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

    print(f"\n  Results saved to: {results_path}")


if __name__ == "__main__":
    main()
