#!/usr/bin/env python
"""v66 — Backtest continu 3 ans (2023-04-14 → 2026-04-14).

BASE    : v63 Sweet Spot CERT-03b (entry_z=1.8, exit_z=0.10, blacklist ON)
LEVIER  : Réestimation plus fréquente — lookback plus court pour détecter
          les cassures de régime plus vite.

PROBLÈME v63_3y : SLB_PSX, CVX_VLO, TFC_V gardés trop longtemps après
  cassure structurelle 2025. Les filtres stricts (v65) ne les rejettent pas
  car ils ÉTAIENT genuinement coïntégrés — ils ont cassé EN COURS DE ROUTE.

LEVIER 2 — Fenêtre plus courte = réestimation plus réactive :
  lookback_window              : 180 → 120  (détecte la cassure ~2 mois plus tôt)
  additional_lookback_windows  : [63] → [42] (confirmation sur 2 mois)

INCHANGÉ vs v63 :
  adf_p=0.15, min_corr=0.65, max_hl=60j  (filtres d'entrée identiques à v63)
  entry_z=1.8, exit_z=0.10, time_stop=45d, max_loss=5%
  blacklist ON(2/30), regime unfav_sz=0.30, momentum OFF

Capital initial : 100 000 $
Train  : 2021-04-14 → 2023-04-13
OOS    : 2023-04-14 → 2026-04-14

Usage:
    venv\\Scripts\\python.exe scripts/run_v66_3y.py
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

# ── Universe (85 symbols, sector-restricted) ────────────────────────────────
SYMBOLS = [
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
SYMBOLS = list(dict.fromkeys(SYMBOLS))

SECTOR_MAP = {
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
    "AVBO": "tech",
    "ACN": "tech",
    "IBM": "tech",
    "TXN": "tech",
    "QCOM": "tech",
    "MU": "tech",
    "AVGO": "tech",
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

# ── Dates ───────────────────────────────────────────────────────────────────
TRAIN_START = "2021-04-14"
TRAIN_END = "2023-04-13"
OOS_START = "2023-04-14"
OOS_END = "2026-04-14"


def _apply_settings_v66():
    """v66 — v63 base + lookback plus court pour réactivité aux cassures."""
    s = get_settings()

    # ── Signal : INCHANGÉ vs v63 ─────────────────────────────────────────
    s.strategy.entry_z_score = 1.8
    s.strategy.exit_z_score = 0.10
    s.strategy.z_score_stop = 4.0
    s.strategy.entry_z_min_spread = 0.0

    # ── Coïntégration : lookback PLUS COURT ──────────────────────────────
    s.strategy.lookback_window = 120  # v66: 120 (était 180 en v63)
    s.strategy.additional_lookback_windows = [42]  # v66: 42j (était 63j en v63)
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


def main():
    print("=" * 70)
    print("  v66 — v63 base + lookback plus court (Levier 2)")
    print("  2023-04-14 -> 2026-04-14 | Capital: 100K$")
    print("  CHANGE  : lookback=120 (était 180), additional=[42] (était [63])")
    print("  INCHANGE: entry_z=1.8, exit_z=0.10, adf_p=0.15, min_corr=0.65")
    print("  INCHANGE: max_loss=5%, time_stop=45d, blacklist ON(2/30)")
    print("=" * 70)
    print()

    gc.collect()
    _apply_settings_v66()

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

    results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)

    print(f"  train {TRAIN_START} -> {TRAIN_END} | OOS {OOS_START} -> {OOS_END}")
    print(f"  {len(SYMBOLS)} symbols, sector-restricted")
    print()

    t0 = time.time()
    try:
        metrics = runner.run_unified(
            symbols=SYMBOLS,
            start_date=TRAIN_START,
            end_date=OOS_END,
            oos_start_date=OOS_START,
            sector_map=SECTOR_MAP,
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
    except Exception as e:
        elapsed = int(time.time() - t0)
        print(f"\n  ERROR après {elapsed}s: {e}")
        traceback.print_exc()
        sys.exit(1)

    elapsed = int(time.time() - t0)

    sh = metrics.sharpe_ratio
    ret = metrics.total_return * 100
    wr = metrics.win_rate * 100
    t = metrics.total_trades
    dd = metrics.max_drawdown * 100

    print("=" * 70)
    print("  v66 — RÉSULTATS 3 ANS")
    print("=" * 70)
    print(f"  Sharpe ratio  : {sh:.4f}   (v63_3y: -0.4019  |  v65_3y: -0.4601)")
    print(f"  Total return  : {ret:+.2f}%   (v63_3y: -3.48%  |  v65_3y: -3.19%)")
    print(f"  Win rate      : {wr:.1f}%   (v63_3y: 47.1%  |  v65_3y: 40.0%)")
    print(f"  Total trades  : {t}   (v63_3y: 70  |  v65_3y: 45)")
    print(f"  Max drawdown  : {dd:.2f}%   (v63_3y: -5.52%  |  v65_3y: -3.87%)")
    print(f"  Elapsed       : {elapsed}s")
    print()

    if hasattr(metrics, "per_pair") and metrics.per_pair:
        print("  Per-pair breakdown:")
        print(f"  {'Pair':<25} {'Trades':>7} {'PnL':>10} {'WR':>7}")
        print("  " + "-" * 55)
        for pk, ps in sorted(metrics.per_pair.items(), key=lambda x: x[1].get("pnl", 0)):
            n = ps.get("n_trades", 0)
            pnl = ps.get("pnl", 0)
            pair_wr = ps.get("win_rate", 0) * 100
            print(f"  {pk:<25} {n:6d} {pnl:+10.0f}$ {pair_wr:6.1f}%")
        print()

    results_path = os.path.join(results_dir, "v66_3y_results.txt")
    with open(results_path, "w", encoding="utf-8") as f:
        f.write("v66 — v63 base + lookback plus court (Levier 2) — 3 ans\n")
        f.write("=" * 60 + "\n")
        f.write("Capital initial : 100 000 $\n")
        f.write("MODIFIE vs v63  : lookback=120 (était 180), additional=[42] (était [63])\n")
        f.write("INCHANGE vs v63 : entry_z=1.8, exit_z=0.10, adf_p=0.15, min_corr=0.65\n")
        f.write("  max_hl=60j, max_loss=5%, time_stop=45d\n")
        f.write("  blacklist ON(2/30), regime unfav_sz=0.30, momentum=OFF\n")
        f.write(f"\nTrain  : {TRAIN_START} -> {TRAIN_END}\n")
        f.write(f"OOS    : {OOS_START} -> {OOS_END}\n")
        f.write(f"Symbols: {len(SYMBOLS)}\n\n")
        f.write(f"Sharpe ratio  : {sh:.4f}   (v63_3y: -0.4019  |  v65_3y: -0.4601)\n")
        f.write(f"Total return  : {ret:+.2f}%   (v63_3y: -3.48%  |  v65_3y: -3.19%)\n")
        f.write(f"Win rate      : {wr:.1f}%   (v63_3y: 47.1%  |  v65_3y: 40.0%)\n")
        f.write(f"Total trades  : {t}   (v63_3y: 70  |  v65_3y: 45)\n")
        f.write(f"Max drawdown  : {dd:.2f}%   (v63_3y: -5.52%  |  v65_3y: -3.87%)\n")
        f.write(f"Elapsed       : {elapsed}s\n")

        if hasattr(metrics, "per_pair") and metrics.per_pair:
            f.write("\nPer-pair breakdown:\n")
            for pk, ps in sorted(metrics.per_pair.items(), key=lambda x: x[1].get("pnl", 0)):
                n = ps.get("n_trades", 0)
                pnl = ps.get("pnl", 0)
                pair_wr = ps.get("win_rate", 0) * 100
                f.write(f"  {pk:<25} n={n:3d}  pnl={pnl:+8.0f}$  wr={pair_wr:5.1f}%\n")

    print(f"  Results saved to: {results_path}")


if __name__ == "__main__":
    main()
