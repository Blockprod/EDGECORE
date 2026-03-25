#!/usr/bin/env python
"""C-01 — Backtest IS de référence avec config 2 sources (zscore=0.70, momentum=0.30).

Exécute le backtest in-sample complet sur la période 2019-01-01 → 2025-01-01
avec l'univers v48 (103 symboles) et la configuration actuelle à 2 sources.
Exporte les résultats dans `results/bt_reference_2sources_output.json`.

Usage :
    venv\\Scripts\\python.exe scripts\\run_is_2sources.py

Durée estimée : 30-120 min (selon cache IBKR local — nécessite TWS/Gateway ouvert si données non encore en cache).
"""

import gc
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager
from pair_selection.filters import MomentumDivergenceFilter

# ── Univers v48 (103 symboles) ─────────────────────────────────────────────────
IS_SYMBOLS = [
    "SPY",
    "AAPL",
    "MSFT",
    "GOOGL",
    "META",
    "NVDA",
    "AMD",
    "AVGO",
    "XLK",
    "INTC",
    "QCOM",
    "TXN",
    "CRM",
    "ORCL",
    "ACN",
    "CSCO",
    "JPM",
    "GS",
    "BAC",
    "MS",
    "WFC",
    "C",
    "SCHW",
    "BLK",
    "AXP",
    "USB",
    "PNC",
    "COF",
    "BK",
    "TFC",
    "XOM",
    "CVX",
    "COP",
    "EOG",
    "SLB",
    "VLO",
    "MPC",
    "PSX",
    "OXY",
    "KO",
    "PEP",
    "PG",
    "CL",
    "WMT",
    "MCD",
    "COST",
    "MDLZ",
    "GIS",
    "PM",
    "MO",
    "CAT",
    "HON",
    "DE",
    "GE",
    "RTX",
    "MMM",
    "UPS",
    "BA",
    "ITW",
    "LMT",
    "FDX",
    "NEE",
    "DUK",
    "SO",
    "AEP",
    "EXC",
    "WEC",
    "JNJ",
    "PFE",
    "UNH",
    "MRK",
    "ABBV",
    "TMO",
    "ABT",
    "DHR",
    "MDT",
    "CVS",
    "CI",
    "BMY",
    "AMZN",
    "TSLA",
    "HD",
    "NKE",
    "LOW",
    "TGT",
    "SBUX",
    "F",
    "GM",
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
]

IS_SECTOR_MAP = {
    "AAPL": "technology",
    "MSFT": "technology",
    "GOOGL": "technology",
    "META": "technology",
    "NVDA": "technology",
    "AMD": "technology",
    "AVGO": "technology",
    "XLK": "technology",
    "INTC": "technology",
    "QCOM": "technology",
    "TXN": "technology",
    "CRM": "technology",
    "ORCL": "technology",
    "ACN": "technology",
    "CSCO": "technology",
    "JPM": "financials",
    "GS": "financials",
    "BAC": "financials",
    "MS": "financials",
    "WFC": "financials",
    "C": "financials",
    "SCHW": "financials",
    "BLK": "financials",
    "AXP": "financials",
    "USB": "financials",
    "PNC": "financials",
    "COF": "financials",
    "BK": "financials",
    "TFC": "financials",
    "XOM": "energy",
    "CVX": "energy",
    "COP": "energy",
    "EOG": "energy",
    "SLB": "energy",
    "VLO": "energy",
    "MPC": "energy",
    "PSX": "energy",
    "OXY": "energy",
    "KO": "consumer_staples",
    "PEP": "consumer_staples",
    "PG": "consumer_staples",
    "CL": "consumer_staples",
    "WMT": "consumer_staples",
    "MCD": "consumer_staples",
    "COST": "consumer_staples",
    "MDLZ": "consumer_staples",
    "GIS": "consumer_staples",
    "PM": "consumer_staples",
    "MO": "consumer_staples",
    "CAT": "industrials",
    "HON": "industrials",
    "DE": "industrials",
    "GE": "industrials",
    "RTX": "industrials",
    "MMM": "industrials",
    "UPS": "industrials",
    "BA": "industrials",
    "ITW": "industrials",
    "LMT": "industrials",
    "FDX": "industrials",
    "NEE": "utilities",
    "DUK": "utilities",
    "SO": "utilities",
    "AEP": "utilities",
    "EXC": "utilities",
    "WEC": "utilities",
    "JNJ": "healthcare",
    "PFE": "healthcare",
    "UNH": "healthcare",
    "MRK": "healthcare",
    "ABBV": "healthcare",
    "TMO": "healthcare",
    "ABT": "healthcare",
    "DHR": "healthcare",
    "MDT": "healthcare",
    "CVS": "healthcare",
    "CI": "healthcare",
    "BMY": "healthcare",
    "AMZN": "consumer_discretionary",
    "TSLA": "consumer_discretionary",
    "HD": "consumer_discretionary",
    "NKE": "consumer_discretionary",
    "LOW": "consumer_discretionary",
    "TGT": "consumer_discretionary",
    "SBUX": "consumer_discretionary",
    "F": "consumer_discretionary",
    "GM": "consumer_discretionary",
    "LIN": "materials",
    "APD": "materials",
    "ECL": "materials",
    "NEM": "materials",
    "FCX": "materials",
    "PLD": "real_estate",
    "AMT": "real_estate",
    "SPG": "real_estate",
    "EQIX": "real_estate",
    "T": "communication",
    "VZ": "communication",
    "CMCSA": "communication",
    "DIS": "communication",
    "NFLX": "communication",
    "SPY": "benchmark",
}

# ── Période IS ─────────────────────────────────────────────────────────────────
IS_START = "2019-01-01"
IS_END = "2025-01-01"


def _apply_settings_2sources() -> None:
    """Config v48 + forcer zscore_weight=0.70, momentum_weight=0.30 explicitement."""
    s = get_settings()

    # Signal combiner — 2 sources (config C-01)
    s.signal_combiner.zscore_weight = 0.70
    s.signal_combiner.momentum_weight = 0.30
    s.signal_combiner.enabled = True

    # Paramètres stratégie v48
    s.strategy.lookback_window = 120
    s.strategy.additional_lookback_windows = [63]
    s.strategy.entry_z_score = 1.6
    s.strategy.exit_z_score = 0.5
    s.strategy.entry_z_min_spread = 0.30
    s.strategy.z_score_stop = 2.5
    s.strategy.min_correlation = 0.65
    s.strategy.max_half_life = 60
    s.strategy.max_position_loss_pct = 0.03
    s.strategy.internal_max_drawdown_pct = 0.12
    s.strategy.use_kalman = True
    s.strategy.bonferroni_correction = True
    s.strategy.johansen_confirmation = True
    s.strategy.newey_west_consensus = True
    s.strategy.weekly_zscore_entry_gate = 0.3
    s.strategy.trend_long_sizing = 0.75
    s.strategy.disable_shorts_in_bull_trend = False
    s.strategy.short_sizing_multiplier = 0.50
    s.strategy.regime_directional_filter = True

    s.momentum.enabled = True
    s.momentum.lookback = 20
    s.momentum.weight = 0.30
    s.momentum.min_strength = 1.0
    s.momentum.max_boost = 1.0

    s.pair_blacklist.enabled = True
    s.pair_blacklist.max_consecutive_losses = 5
    s.pair_blacklist.cooldown_days = 10

    s.risk.max_concurrent_positions = 15

    s.regime.enabled = True
    s.regime.ma_fast = 50
    s.regime.ma_slow = 200
    s.regime.vol_threshold = 0.35
    s.regime.vol_window = 20
    s.regime.neutral_band_pct = 0.02
    s.regime.trend_favorable_sizing = 0.80
    s.regime.neutral_sizing = 0.70

    if hasattr(s.strategy, "fdr_q_level"):
        s.strategy.fdr_q_level = 0.30


def _wilson_ci_95(wins: int, n: int) -> tuple[float, float]:
    """Intervalle de confiance de Wilson à 95% sur le win rate."""
    if n == 0:
        return (0.0, 0.0)
    import math

    z = 1.96
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4))


def main() -> None:
    print("=" * 70)
    print("  C-01 — Backtest IS de référence — config 2 sources")
    print(f"  Période : {IS_START} → {IS_END}")
    print(f"  Univers : {len(IS_SYMBOLS)} symboles")
    print("=" * 70)

    # Vérification config avant lancement
    _apply_settings_2sources()
    s = get_settings()
    assert s.signal_combiner.zscore_weight == 0.70, "zscore_weight incorrecte"
    assert s.signal_combiner.momentum_weight == 0.30, "momentum_weight incorrecte"
    print(
        f"\n  Config vérifiée : zscore_weight={s.signal_combiner.zscore_weight} | "
        f"momentum_weight={s.signal_combiner.momentum_weight}"
    )
    print(f"  entry_z_score={s.strategy.entry_z_score} | exit_z_score={s.strategy.exit_z_score}")
    print("  Risk tiers cohérents : ", end="")
    s._assert_risk_tier_coherence()
    print("OK")

    gc.collect()

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000

    ts = TimeStopManager(
        TimeStopConfig(
            half_life_multiplier=1.2,
            max_days_cap=20,
            default_max_bars=20,
        )
    )
    mom_filter = MomentumDivergenceFilter(
        lookback_days=60,
        threshold=1.5,
        min_universe_size=20,
        min_dispersion=0.0,
    )

    print(f"\n  Lancement backtest IS ({IS_START} → {IS_END})...")
    print("  Source données : IBKR reqHistoricalData (cache local si déjà téléchargé)")
    print("  (pas d'OOS split — run IS complet)\n")

    t0 = time.time()
    metrics = runner.run_unified(
        symbols=IS_SYMBOLS,
        start_date=IS_START,
        end_date=IS_END,
        sector_map=IS_SECTOR_MAP,
        pair_rediscovery_interval=2,
        allocation_per_pair_pct=50.0,
        max_position_loss_pct=0.07,
        max_portfolio_heat=3.0,
        time_stop=ts,
        leverage_multiplier=2.5,
        momentum_filter=mom_filter,
    )
    elapsed = int(time.time() - t0)

    # ── Calcul IC 95% (Wilson) sur le win rate ──────────────────────────────
    n_trades = metrics.total_trades
    n_wins = round(metrics.win_rate * n_trades) if n_trades > 0 else 0
    ci_lo, ci_hi = _wilson_ci_95(n_wins, n_trades)

    # ── Alerte drought ───────────────────────────────────────────────────────
    drought_flag = n_trades < 30

    # ── Construction du JSON résultat ───────────────────────────────────────
    result: dict[str, Any] = {
        "version": "bt_reference_2sources",
        "created_at": datetime.now(UTC).isoformat(),
        "config": {
            "zscore_weight": s.signal_combiner.zscore_weight,
            "momentum_weight": s.signal_combiner.momentum_weight,
            "entry_z_score": s.strategy.entry_z_score,
            "exit_z_score": s.strategy.exit_z_score,
            "z_score_stop": s.strategy.z_score_stop,
            "lookback_window": s.strategy.lookback_window,
            "min_correlation": s.strategy.min_correlation,
            "max_half_life": s.strategy.max_half_life,
        },
        "period": {
            "is_start": IS_START,
            "is_end": IS_END,
            "universe_size": n_trades,
        },
        "metrics": {
            "sharpe_ratio": round(metrics.sharpe_ratio, 4),
            "total_return_pct": round(metrics.total_return * 100, 2),
            "max_drawdown_pct": round(metrics.max_drawdown * 100, 2),
            "win_rate": round(metrics.win_rate, 4),
            "win_rate_ci95": {"lo": ci_lo, "hi": ci_hi},
            "profit_factor": round(metrics.profit_factor, 4),
            "total_trades": n_trades,
            "n_wins": n_wins,
            "calmar_ratio": round(metrics.calmar_ratio, 4) if metrics.calmar_ratio is not None else None,
            "sortino_ratio": round(metrics.sortino_ratio, 4) if metrics.sortino_ratio is not None else None,
            "avg_trade_duration_bars": round(metrics.avg_trade_duration, 2)
            if metrics.avg_trade_duration is not None
            else None,
            "initial_capital": metrics.initial_capital,
            "final_capital": metrics.final_capital,
            "realized_pnl": metrics.realized_pnl,
            "total_slippage": metrics.total_slippage,
        },
        "per_pair": metrics.per_pair or {},
        "flags": {
            "drought_warning": drought_flag,
            "drought_threshold": 30,
            "note": "drought confirmé — C-02 filtre dispersion requis" if drought_flag else "OK",
        },
        "elapsed_s": elapsed,
    }

    # ── Écriture JSON ────────────────────────────────────────────────────────
    out_dir = Path(__file__).parent.parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "bt_reference_2sources_output.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # ── Résumé console ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  RÉSULTATS IS — config 2 sources")
    print("=" * 70)
    print(f"  Trades       : {n_trades}  {'⚠️  DROUGHT (<30)' if drought_flag else '✅'}")
    print(f"  Sharpe       : {metrics.sharpe_ratio:.3f}")
    print(f"  Return       : {metrics.total_return * 100:+.2f}%")
    print(f"  Win rate     : {metrics.win_rate * 100:.1f}%  (IC 95% [{ci_lo:.2%}, {ci_hi:.2%}])")
    print(f"  Profit Factor: {metrics.profit_factor:.3f}")
    print(f"  Max DD       : {metrics.max_drawdown * 100:+.2f}%")
    print(f"  Total slip.  : {metrics.total_slippage}")
    print(f"\n  → Résultats écrits dans : {out_path}")
    print(f"  → Durée run : {elapsed}s ({elapsed // 60}m{elapsed % 60:02d}s)")

    if drought_flag:
        print("\n  ⚠️  DROUGHT CONFIRMÉ EN IS : N_IS < 30 trades sur 6 ans")
        print("      Le problème est structurel — confirme le choix Option A (filtre")
        print("      dispersion) de C-02. Vérifier dispersion_filter_min_index.")
    else:
        print("\n  ✅ N_IS ≥ 30 — baseline IS valide. Cette Sharpe IS est la nouvelle")
        print("      référence pour mesurer la dégradation IS→OOS (C-07).")


if __name__ == "__main__":
    main()
