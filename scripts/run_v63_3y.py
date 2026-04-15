#!/usr/bin/env python
"""v63 Sweet Spot — Backtest continu 3 ans (2023-04-14 → 2026-04-14).

Capital initial : 100 000 $
Paramètres      : v63 Sweet Spot CERT-03b certifiés (Combined Sharpe 0.5554)
Univers         : 87 symboles, secteur-restreint
Période IS      : 2021-04-14 → 2023-04-13 (lookback ~2 ans)
Période OOS     : 2023-04-14 → 2026-04-14 (3 ans complets)

Usage:
    venv\\Scripts\\python.exe scripts/run_v63_3y.py
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

# ── Universe (87 symbols, sector-restricted) ────────────────────────────────
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

# ── Dates ───────────────────────────────────────────────────────────────────
TRAIN_START = "2021-04-14"  # ~2 years lookback for cointegration estimation
TRAIN_END = "2023-04-13"
OOS_START = "2023-04-14"  # OOS starts here — 3 full years
OOS_END = "2026-04-14"  # Today


def _apply_settings_v63():
    """Apply v63 Sweet Spot parameters — CERT-03b certified."""
    s = get_settings()

    # ── Signal ──────────────────────────────────────────────────────────
    s.strategy.entry_z_score = 1.8  # v63 certified
    s.strategy.exit_z_score = 0.10  # v63 certified — faster profit capture
    s.strategy.z_score_stop = 4.0
    s.strategy.entry_z_min_spread = 0.0

    # ── Cointegration ───────────────────────────────────────────────────
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

    # ── Sizing & risk ───────────────────────────────────────────────────
    s.strategy.max_position_loss_pct = 0.05  # v63: 5% per-position stop
    s.strategy.internal_max_drawdown_pct = 0.25
    if hasattr(s.strategy, "internal_max_daily_trades"):
        s.strategy.internal_max_daily_trades = 500
    if hasattr(s.strategy, "internal_max_positions"):
        s.strategy.internal_max_positions = 50
    s.risk.max_concurrent_positions = 12

    # ── Regime ──────────────────────────────────────────────────────────
    s.regime.enabled = True
    s.regime.neutral_band_pct = 0.02  # v63 certified
    s.regime.neutral_sizing = 1.0
    s.regime.trend_favorable_sizing = 1.0
    s.regime.trend_unfavorable_sizing = 0.30  # v63 certified — key lever

    # ── Momentum — disabled ─────────────────────────────────────────────
    s.momentum.enabled = False

    # ── Pair blacklist — KEY v63 breakthrough ───────────────────────────
    s.pair_blacklist.enabled = True
    s.pair_blacklist.max_consecutive_losses = 2
    s.pair_blacklist.cooldown_days = 30


def main():
    print("=" * 70)
    print("  v63 Sweet Spot — Backtest continu 3 ans")
    print("  2023-04-14 → 2026-04-14 | Capital: 100K$")
    print("  entry_z=1.8, exit_z=0.10, max_loss=5%, time_stop=45d")
    print("  blacklist ON(2/30), REGIME ON: unfav_sz=0.30")
    print("=" * 70)
    print()

    gc.collect()
    _apply_settings_v63()

    # ── Time stop (v63: 45 days) ────────────────────────────────────────
    ts = TimeStopManager(
        TimeStopConfig(
            half_life_multiplier=3.0,
            max_days_cap=45,  # v63: 45d
            default_max_bars=45,
        )
    )

    # ── Spread correlation guard ────────────────────────────────────────
    spread_guard = SpreadCorrelationGuard(
        SpreadCorrelationConfig(
            max_correlation=0.65,
            min_overlap_bars=20,
        )
    )

    # ── Runner ──────────────────────────────────────────────────────────
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
            max_position_loss_pct=0.05,  # v63: 5%
            max_portfolio_heat=1.5,
            time_stop=ts,
            leverage_multiplier=1.0,
            momentum_filter=None,
            spread_corr_guard=spread_guard,
            blacklist_persist_path=None,
        )
    except Exception as e:
        elapsed = int(time.time() - t0)
        print(f"\n  ERROR after {elapsed}s: {e}")
        traceback.print_exc()
        sys.exit(1)

    elapsed = int(time.time() - t0)

    # ── Results ─────────────────────────────────────────────────────────
    sh = metrics.sharpe_ratio
    ret = metrics.total_return * 100
    wr = metrics.win_rate * 100
    t = metrics.total_trades
    dd = metrics.max_drawdown * 100

    print("=" * 70)
    print("  v63 SWEET SPOT — 3-YEAR BACKTEST RESULTS")
    print("=" * 70)
    print(f"  Sharpe ratio       : {sh:.4f}")
    print(f"  Total return       : {ret:+.2f}%")
    print(f"  Win rate           : {wr:.1f}%")
    print(f"  Total trades       : {t}")
    print(f"  Max drawdown       : {dd:.2f}%")
    print(f"  Elapsed            : {elapsed}s")
    print()

    # ── Per-pair breakdown ──────────────────────────────────────────────
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

    # ── Save results ────────────────────────────────────────────────────
    results_path = os.path.join(results_dir, "v63_3y_results.txt")
    with open(results_path, "w", encoding="utf-8") as f:
        f.write("v63 Sweet Spot — Backtest continu 3 ans (2023-04-14 → 2026-04-14)\n")
        f.write("=" * 60 + "\n")
        f.write("Capital initial : 100 000 $\n")
        f.write("Parametres      : v63 Sweet Spot CERT-03b\n")
        f.write("  entry_z=1.8, exit_z=0.10, z_stop=4.0\n")
        f.write("  lookback=180, additional=[63], adf_p=0.15\n")
        f.write("  min_corr=0.65, fdr_q=0.30, max_hl=60\n")
        f.write("  kalman=True, johansen=True, newey_west=True\n")
        f.write("  max_loss=5%, time_stop=45d\n")
        f.write("  regime: ON (neutral=1.0, fav=1.0, unfav=0.30)\n")
        f.write("  neutral_band_pct=0.02\n")
        f.write("  blacklist: ON (max_consecutive_losses=2, cooldown=30d)\n")
        f.write("  momentum: OFF\n")
        f.write(f"\nTrain  : {TRAIN_START} -> {TRAIN_END}\n")
        f.write(f"OOS    : {OOS_START} -> {OOS_END}\n")
        f.write(f"Symbols: {len(SYMBOLS)}\n\n")
        f.write(f"Sharpe ratio  : {sh:.4f}\n")
        f.write(f"Total return  : {ret:+.2f}%\n")
        f.write(f"Win rate      : {wr:.1f}%\n")
        f.write(f"Total trades  : {t}\n")
        f.write(f"Max drawdown  : {dd:.2f}%\n")
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
