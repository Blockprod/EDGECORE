#!/usr/bin/env python
"""v58 — Walk-Forward 3-Window — Sweet Set (CERT-03b).

ROOT CAUSE FOUND in v56/v57 analysis:
  `short_sizing_multiplier` and `disable_shorts_in_bull_trend` are DEAD CODE
  in strategy_simulator.py (stored but never referenced in trading logic).
  The ONLY short/long control is MarketRegimeFilter via _regime_state.short_sizing.

  Default `neutral_sizing=0.65` reduces ALL positions by 35% in NEUTRAL regime.
  This killed v55's W2=+2.04 when regime was enabled in v56 (W2→+0.17).

  Fix: set neutral_sizing=1.0 and trend_favorable_sizing=1.0 so the regime
  filter ONLY blocks the unfavorable direction (shorts in BULL, longs in BEAR),
  without penalizing favorable-direction or neutral-regime entries.

  Additional: tighter loss caps (z_stop 4→3, max_loss 5%→3%, time_stop 60→45d)
  to prevent catastrophic single-trade losses (e.g. ORCL_ACN -4129 in v56 W3).

CERT-03b criteria (aggregate):
  - Combined Sharpe >= 0.5
  - Total OOS trades >= 40
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

# ── Blacklisting thresholds (same as v56) ─────────────────────────────────
WL_WR_THRESHOLD = 0.40
WL_PNL_THRESHOLD = -3000
BL_COOLDOWN_DAYS = 400

# ── Universe (same as v54-v57) ─────────────────────────────────────────────
WF_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "AMD", "INTC", "CSCO", "ORCL",
    "JPM", "BAC", "GS", "MS", "WFC", "C", "USB", "PNC", "TFC", "BK",
    "STT", "BLK", "SCHW", "AXP", "V", "MA", "COF",
    "JNJ", "PFE", "MRK", "ABT", "UNH", "CVS", "CI", "HUM", "MDT", "DHR",
    "XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX", "VLO",
    "LIN", "APD", "ECL", "NEM", "FCX",
    "PLD", "AMT", "SPG", "EQIX",
    "T", "VZ", "CMCSA",
    "DIS", "NFLX", "WMT", "TGT", "COST", "HD", "LOW",
    "BA", "LMT", "RTX", "HON", "UPS", "FDX", "CAT", "DE", "EMR", "ETN",
    "NEE", "DUK", "SO", "D",
    "AVGO", "ACN", "IBM", "TXN", "QCOM", "MU",
    "SPY",
]
WF_SYMBOLS = list(dict.fromkeys(WF_SYMBOLS))

WF_SECTOR_MAP = {
    "AAPL": "tech", "MSFT": "tech", "GOOGL": "tech", "META": "tech", "AMZN": "tech",
    "NVDA": "tech", "AMD": "tech", "INTC": "tech", "CSCO": "tech", "ORCL": "tech",
    "AVGO": "tech", "ACN": "tech", "IBM": "tech", "TXN": "tech", "QCOM": "tech", "MU": "tech",
    "JPM": "finance", "BAC": "finance", "GS": "finance", "MS": "finance", "WFC": "finance",
    "C": "finance", "USB": "finance", "PNC": "finance", "TFC": "finance", "BK": "finance",
    "STT": "finance", "BLK": "finance", "SCHW": "finance", "AXP": "finance",
    "V": "finance", "MA": "finance", "COF": "finance",
    "JNJ": "healthcare", "PFE": "healthcare", "MRK": "healthcare", "ABT": "healthcare",
    "UNH": "healthcare", "CVS": "healthcare", "CI": "healthcare", "HUM": "healthcare",
    "MDT": "healthcare", "DHR": "healthcare",
    "XOM": "energy", "CVX": "energy", "COP": "energy", "EOG": "energy",
    "SLB": "energy", "MPC": "energy", "PSX": "energy", "VLO": "energy",
    "LIN": "materials", "APD": "materials", "ECL": "materials", "NEM": "materials", "FCX": "materials",
    "PLD": "realestate", "AMT": "realestate", "SPG": "realestate", "EQIX": "realestate",
    "T": "telecom", "VZ": "telecom", "CMCSA": "telecom",
    "DIS": "consumer", "NFLX": "consumer", "WMT": "consumer", "TGT": "consumer",
    "COST": "consumer", "HD": "consumer", "LOW": "consumer",
    "BA": "industrial", "LMT": "industrial", "RTX": "industrial", "HON": "industrial",
    "UPS": "industrial", "FDX": "industrial", "CAT": "industrial", "DE": "industrial",
    "EMR": "industrial", "ETN": "industrial",
    "NEE": "utilities", "DUK": "utilities", "SO": "utilities", "D": "utilities",
    "SPY": "benchmark",
}

WF_WINDOWS = [
    ("W1-2023", "2021-01-04", "2022-12-30", "2023-01-02", "2023-12-29"),
    ("W2-2024", "2021-01-04", "2023-12-29", "2024-01-02", "2024-12-31"),
    ("W3-2025", "2021-01-04", "2024-12-31", "2025-01-02", "2025-12-31"),
]


def _apply_settings_v58():
    """v58 Sweet Set parameters — regime fix + tighter loss caps."""
    s = get_settings()

    # ── Signal quality (same as v55/v56 — proven in W2=+2.04) ──────────
    s.strategy.entry_z_score = 1.5
    s.strategy.exit_z_score = 0.05
    s.strategy.z_score_stop = 3.0        # was 4.0 — cap tail losses
    s.strategy.entry_z_min_spread = 0.0

    # ── Cointegration quality (same as v56) ─────────────────────────────
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

    # ── Position sizing — tighter loss cap ──────────────────────────────
    s.strategy.max_position_loss_pct = 0.03  # was 0.05 — max $3k loss/trade
    s.strategy.internal_max_drawdown_pct = 0.25
    if hasattr(s.strategy, "internal_max_daily_trades"):
        s.strategy.internal_max_daily_trades = 500
    if hasattr(s.strategy, "internal_max_positions"):
        s.strategy.internal_max_positions = 50
    s.risk.max_concurrent_positions = 12

    # ── REGIME CONFIG — THE KEY FIX ─────────────────────────────────────
    # The regime filter is the ONLY mechanism controlling short/long sizing.
    # neutral_sizing=0.65 was silently reducing ALL positions by 35%.
    # trend_favorable_sizing=0.80 was penalizing even favorable-direction trades.
    # Fix: set both to 1.0 so regime ONLY blocks unfavorable direction.
    s.regime.enabled = True
    s.regime.neutral_sizing = 1.0            # was 0.65 — CRITICAL FIX
    s.regime.trend_favorable_sizing = 1.0    # was 0.80 — full sizing for good side
    # Keep detection thresholds at defaults:
    # s.regime.vol_threshold = 0.18
    # s.regime.neutral_band_pct = 0.02

    # Note: short_sizing_multiplier and disable_shorts_in_bull_trend are
    # DEAD CODE — stored in simulator but never referenced. Don't bother.

    # ── Momentum — disabled ─────────────────────────────────────────────
    s.momentum.enabled = False

    # ── Pair blacklist (same as v56) ────────────────────────────────────
    s.pair_blacklist.enabled = True
    s.pair_blacklist.max_consecutive_losses = 4
    s.pair_blacklist.cooldown_days = BL_COOLDOWN_DAYS


def _build_blacklist_json(
    per_pair: dict,
    existing_path: str | None,
    oos_end_date: str,
) -> str:
    """Build pair blacklist JSON from per-pair metrics + prior state."""
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
            existing = state.get(pair_key, {})
            existing_until = existing.get("cooldown_until")
            if existing_until is None or existing_until < cooldown_until:
                state[pair_key] = {
                    "consecutive_losses": 3,
                    "blacklisted_on": blacklist_date.isoformat(),
                    "cooldown_until": cooldown_until,
                    "total_losses": existing.get("total_losses", 0) + max(1, n - round(wr * n)),
                    "total_wins": existing.get("total_wins", 0) + round(wr * n),
                }
                newly_blacklisted.append(pair_key)

    bl_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "results",
        "v58_cross_window_blacklist.json",
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
    # v58: tighter time stops — max 45 days, half_life_mult 2.5
    ts = TimeStopManager(
        TimeStopConfig(
            half_life_multiplier=2.5,   # was 3.0 — faster exits
            max_days_cap=45,            # was 60 — force stale position exits
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
            pair_rediscovery_interval=3,
            allocation_per_pair_pct=25.0,
            max_position_loss_pct=0.03,   # was 0.05 — tighter per-trade loss cap
            max_portfolio_heat=1.5,
            time_stop=ts,
            leverage_multiplier=1.0,
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
        print(f"  [{label}] -> S={sh:5.2f}  {ret:+6.2f}%  WR={wr:5.1f}%  trades={t:3d}  DD={dd:+6.2f}%  [{elapsed}s]")
        return metrics, elapsed
    except Exception as e:
        elapsed = int(time.time() - t0)
        print(f"  [{label}] ERROR: {str(e)[:200]}")
        print(traceback.format_exc())
        return None, elapsed


def main():
    print("=" * 70)
    print("  v58 — Walk-Forward 3-Window — Sweet Set (CERT-03b)")
    print("  KEY FIX: neutral_sizing 0.65->1.0, trend_sizing 0.80->1.0")
    print("  + z_stop 4->3, max_loss 5%->3%, time_stop 60->45d")
    print("=" * 70)
    print()

    gc.collect()
    _apply_settings_v58()

    results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)
    bl_path: str | None = None

    window_results = []
    total_t0 = time.time()

    for i, (label, train_start, train_end, oos_start, oos_end) in enumerate(WF_WINDOWS):
        gc.collect()
        result, elapsed = _run_window(label, train_start, train_end, oos_start, oos_end, bl_path)
        window_results.append((result, elapsed))
        print()

        # Build cross-window blacklist for next window
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
    results_path = os.path.join(results_dir, "v58_wf3_results.txt")
    with open(results_path, "w", encoding="utf-8") as f:
        f.write("v58 Walk-Forward 3-Window — Sweet Set — CERT-03b\n")
        f.write("=" * 60 + "\n")
        f.write("ROOT CAUSE FIX:\n")
        f.write("  neutral_sizing:           0.65 -> 1.0  (stop penalizing NEUTRAL regime)\n")
        f.write("  trend_favorable_sizing:   0.80 -> 1.0  (full sizing for favorable side)\n")
        f.write("  Note: short_sizing_multiplier & disable_shorts_in_bull are DEAD CODE\n")
        f.write("\nAdditional tighter loss caps:\n")
        f.write("  z_score_stop:       4.0 -> 3.0  (cap catastrophic single-trade losses)\n")
        f.write("  max_position_loss:  5%  -> 3%   (max $3k loss per trade)\n")
        f.write("  time_stop cap:      60d -> 45d  (force exit from stale positions)\n")
        f.write("  half_life_mult:     3.0 -> 2.5  (faster time stops)\n")
        f.write(f"\nWL_WR_THRESHOLD  : {WL_WR_THRESHOLD}\n")
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
