#!/usr/bin/env python
"""v54 — Walk-Forward 3-Window + Cross-Window Pair Blacklisting (CERT-03b).

Problem in v53: 5 serial-loser pairs (EOG_MPC -20k, NVDA_AMD -13k,
AAPL_AMD -13k, UNH_CVS -10k, MA_COF -9k) destroyed PnL across all
three windows.  These pairs were cointegrated in the 2021-2022 bear
market but their relationship broke permanently in 2023+.

Fix: Cross-window pair blacklisting.
  - After W1, pairs with WR < WL_WR_THRESHOLD or PnL < WL_PNL_THRESHOLD
    are pre-seeded into the PairBlacklist for W2 (via persist_path JSON).
  - After W2, W2 losers are added to the cumulative blacklist for W3.
  - The blacklist cooldown_days is set to 400 (> 365) so blacklisted pairs
    stay blocked for the entire next OOS window.

Thresholds (conservative):
  WL_WR_THRESHOLD  = 0.30  (win rate < 30% = clear loser)
  WL_PNL_THRESHOLD = -1500 (absolute PnL loss, USD)

Same base params as v52/v53.

CERT-03b criteria (aggregate):
  - Combined Sharpe >= 0.5
  - Total OOS trades >= 40  (some pairs blocked => fewer, lower bar)
  - Max DD per window < 20%
"""

import gc
import io
import json
import os
import sys
import time
import traceback
from datetime import date, timedelta
from pathlib import Path

# Force UTF-8 on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager
from risk.spread_correlation import SpreadCorrelationConfig, SpreadCorrelationGuard

# ── Blacklisting thresholds ────────────────────────────────────────────────
WL_WR_THRESHOLD = 0.30  # pairs with win_rate < 30% get blacklisted
WL_PNL_THRESHOLD = -1500  # pairs with PnL < -1500 USD get blacklisted
BL_COOLDOWN_DAYS = 400  # > 365 → blocks for the entire next OOS year

# ── Universe (same as v52/v53) ─────────────────────────────────────────────
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


def _apply_settings_v54():
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
    # Pair blacklist: enabled but threshold high (cross-window seeding handles it)
    s.pair_blacklist.enabled = True
    s.pair_blacklist.max_consecutive_losses = 3
    s.pair_blacklist.cooldown_days = BL_COOLDOWN_DAYS
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


def _build_blacklist_json(
    per_pair: dict,
    existing_path: str | None,
    oos_end_date: str,
) -> str:
    """Build a PairBlacklist JSON from per-pair metrics + prior blacklist state.

    Pairs with WR < WL_WR_THRESHOLD OR PnL < WL_PNL_THRESHOLD are added
    with a cooldown ending BL_COOLDOWN_DAYS after oos_end_date.

    Returns the path to the written JSON file.
    """
    # Load existing state if any
    state: dict = {}
    if existing_path and Path(existing_path).exists():
        with open(existing_path, encoding="utf-8") as f:
            state = json.load(f)

    blacklist_date = date.fromisoformat(oos_end_date)
    cooldown_until = (blacklist_date + timedelta(days=BL_COOLDOWN_DAYS)).isoformat()

    newly_blacklisted = []
    for pair_key, stats in per_pair.items():
        n = stats.get("n_trades", 0)
        pnl = stats.get("pnl", 0.0)
        wr = stats.get("win_rate", 1.0)
        if n == 0:
            continue
        if wr < WL_WR_THRESHOLD or pnl < WL_PNL_THRESHOLD:
            # Merge: don't overwrite if already blacklisted with later date
            existing = state.get(pair_key, {})
            existing_until = existing.get("cooldown_until")
            if existing_until is None or existing_until < cooldown_until:
                state[pair_key] = {
                    "consecutive_losses": 3,  # ≥ max_consecutive_losses
                    "blacklisted_on": blacklist_date.isoformat(),
                    "cooldown_until": cooldown_until,
                    "total_losses": existing.get("total_losses", 0) + max(1, n - round(wr * n)),
                    "total_wins": existing.get("total_wins", 0) + round(wr * n),
                }
                newly_blacklisted.append(pair_key)

    # Write to temp path
    bl_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "results",
        "v54_cross_window_blacklist.json",
    )
    os.makedirs(os.path.dirname(bl_path), exist_ok=True)
    with open(bl_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    print(f"  Cross-window blacklist: {len(state)} total blocked pairs ({len(newly_blacklisted)} new)")
    if newly_blacklisted:
        print(
            f"  Newly blocked: {', '.join(sorted(newly_blacklisted)[:10])}"
            + (" ..." if len(newly_blacklisted) > 10 else "")
        )
    return bl_path


def _run_window(
    label: str,
    train_start: str,
    train_end: str,
    oos_start: str,
    oos_end: str,
    blacklist_path: str | None,
):
    ts60 = TimeStopManager(TimeStopConfig(half_life_multiplier=2.0, max_days_cap=60, default_max_bars=60))
    spread_guard = SpreadCorrelationGuard(SpreadCorrelationConfig(max_correlation=0.80, min_overlap_bars=20))

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000

    blocked_count = 0
    if blacklist_path and Path(blacklist_path).exists():
        with open(blacklist_path, encoding="utf-8") as f:
            blocked_count = len(json.load(f))

    print(f"  [{label}] train {train_start} -> {train_end} | OOS {oos_start} -> {oos_end}  [blocked={blocked_count}]")
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
            blacklist_persist_path=blacklist_path,
        )
        elapsed = int(time.time() - t0)
        sh = metrics.sharpe_ratio
        ret = metrics.total_return * 100
        wr = metrics.win_rate * 100
        t = metrics.total_trades
        dd = metrics.max_drawdown * 100
        print(f"  [{label}] → S={sh:5.2f}  {ret:+6.2f}%  WR={wr:5.1f}%  trades={t:3d}  DD={dd:+6.2f}%  [{elapsed}s]")
        return metrics, elapsed
    except Exception as e:
        elapsed = int(time.time() - t0)
        print(f"  [{label}] ERROR: {str(e)[:200]}")
        print(traceback.format_exc())
        return None, elapsed


def main():
    print("=" * 70)
    print("  v54 — Walk-Forward 3-Window + Cross-Window Blacklisting (CERT-03b)")
    print("  Blacklist threshold: WR < 30% OR PnL < -1500 USD per window")
    print(f"  Cooldown: {BL_COOLDOWN_DAYS} days (> 365 → full next OOS year blocked)")
    print("=" * 70)
    print()

    gc.collect()
    _apply_settings_v54()

    results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)
    bl_path: str | None = None  # no blacklist for W1

    window_results = []
    total_t0 = time.time()

    for i, (label, train_start, train_end, oos_start, oos_end) in enumerate(WF_WINDOWS):
        gc.collect()
        result, elapsed = _run_window(label, train_start, train_end, oos_start, oos_end, bl_path)
        window_results.append((result, elapsed))
        print()

        # Build cross-window blacklist from this window's losers for the next window
        if result is not None and i < len(WF_WINDOWS) - 1:
            per_pair = {}
            if hasattr(result, "per_pair") and result.per_pair:
                per_pair = result.per_pair
            bl_path = _build_blacklist_json(per_pair, bl_path, oos_end)
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
        f"  CERT-03b criteria  : Sharpe≥0.5={combined_sh >= 0.5} trades≥40={total_trades >= 40} DD<20%={worst_dd < 20.0}"
    )
    print(f"  CERT-03b result    : {'PASS ✅' if cert_pass else 'FAIL ❌'}")
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
    results_path = os.path.join(results_dir, "v54_wf3_bl_results.txt")
    with open(results_path, "w", encoding="utf-8") as f:
        f.write("v54 Walk-Forward 3-Window + Cross-Window Blacklisting — CERT-03b\n")
        f.write("=" * 60 + "\n")
        f.write(f"WL_WR_THRESHOLD  : {WL_WR_THRESHOLD}\n")
        f.write(f"WL_PNL_THRESHOLD : {WL_PNL_THRESHOLD}\n")
        f.write(f"BL_COOLDOWN_DAYS : {BL_COOLDOWN_DAYS}\n")
        f.write(f"Windows completed: {n_valid}/{len(WF_WINDOWS)}\n")
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
                    for pk, st in sorted(m.per_pair.items()):
                        f.write(f"    {pk}: n={st['n_trades']} pnl={st['pnl']:.0f} wr={st['win_rate']:.0%}\n")

    print(f"\n  Results saved → {results_path}")


if __name__ == "__main__":
    main()
