#!/usr/bin/env python
"""EDGECORE Phase 1.5 ÔÇö Incremental Universe Expansion.

Tests each candidate symbol ONE AT A TIME against the v32j baseline
universe (37 symbols). Measures delta Sharpe, delta PF, delta trades.

Decision rule:
  - KEEP if delta_Sharpe >= 0 AND delta_PF >= 0 AND total_trades >= baseline
  - REJECT otherwise

Candidates are tested in order of expected quality (mega-caps first).
"""

import os
import sys
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

# ÔöÇÔöÇ Current v32j baseline universe (37 symbols) ÔöÇÔöÇ
BASE_SYMBOLS = [
    "SPY",
    "AAPL",
    "MSFT",
    "GOOGL",
    "META",
    "NVDA",
    "AMD",
    "AVGO",
    "JPM",
    "GS",
    "BAC",
    "MS",
    "WFC",
    "C",
    "SCHW",
    "XOM",
    "CVX",
    "COP",
    "EOG",
    "KO",
    "PEP",
    "PG",
    "CL",
    "WMT",
    "CAT",
    "HON",
    "DE",
    "GE",
    "RTX",
    "NEE",
    "DUK",
    "SO",
    "JNJ",
    "PFE",
    "UNH",
    "MRK",
    "ABBV",
]

BASE_SECTOR_MAP = {
    "AAPL": "technology",
    "MSFT": "technology",
    "GOOGL": "technology",
    "META": "technology",
    "NVDA": "technology",
    "AMD": "technology",
    "AVGO": "technology",
    "JPM": "financials",
    "GS": "financials",
    "BAC": "financials",
    "MS": "financials",
    "WFC": "financials",
    "C": "financials",
    "SCHW": "financials",
    "XOM": "energy",
    "CVX": "energy",
    "COP": "energy",
    "EOG": "energy",
    "KO": "consumer_staples",
    "PEP": "consumer_staples",
    "PG": "consumer_staples",
    "CL": "consumer_staples",
    "WMT": "consumer_staples",
    "CAT": "industrials",
    "HON": "industrials",
    "DE": "industrials",
    "GE": "industrials",
    "RTX": "industrials",
    "NEE": "utilities",
    "DUK": "utilities",
    "SO": "utilities",
    "JNJ": "healthcare",
    "PFE": "healthcare",
    "UNH": "healthcare",
    "MRK": "healthcare",
    "ABBV": "healthcare",
}

# ÔöÇÔöÇ Candidate symbols to test (ordered by quality) ÔöÇÔöÇ
CANDIDATES = [
    # Tech ÔÇö semis / enterprise
    ("INTC", "technology"),
    ("QCOM", "technology"),
    ("TXN", "technology"),
    ("ADBE", "technology"),
    ("CRM", "technology"),
    ("CSCO", "technology"),
    # Financials
    ("BLK", "financials"),
    ("AXP", "financials"),
    ("USB", "financials"),
    # Energy
    ("SLB", "energy"),
    ("VLO", "energy"),
    ("MPC", "energy"),
    # Industrials / Defense
    ("LMT", "industrials"),
    ("UNP", "industrials"),
    ("UPS", "industrials"),
    ("MMM", "industrials"),
    # Healthcare / Pharma
    ("LLY", "healthcare"),
    ("TMO", "healthcare"),
    ("ABT", "healthcare"),
    ("BMY", "healthcare"),
    # Consumer
    ("COST", "consumer_staples"),
    ("MCD", "consumer_staples"),
    ("NKE", "consumer_discretionary"),
    ("HD", "consumer_discretionary"),
    ("LOW", "consumer_discretionary"),
    # ETFs (sector matching)
    ("XLK", "technology"),
    ("XLF", "financials"),
    ("XLE", "energy"),
    ("XLV", "healthcare"),
    ("XLI", "industrials"),
]


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
    if hasattr(s.strategy, "fdr_q_level"):
        s.strategy.fdr_q_level = 0.25


def make_time_stop():
    from execution.time_stop import TimeStopConfig, TimeStopManager

    return TimeStopManager(
        TimeStopConfig(
            half_life_multiplier=1.5,
            max_days_cap=30,
            default_max_bars=30,
        )
    )


def run_backtest(symbols, sector_map):
    """Run a single backtest with given symbols/sectors."""
    setup_settings()
    runner = BacktestRunner()
    runner.config.initial_capital = 100_000

    metrics = runner.run_unified(
        symbols=symbols,
        start_date="2023-03-04",
        end_date="2026-03-04",
        sector_map=sector_map,
        pair_rediscovery_interval=2,
        allocation_per_pair_pct=50.0,
        max_position_loss_pct=0.07,
        max_portfolio_heat=3.0,
        time_stop=make_time_stop(),
    )
    return metrics


def extract_metrics(metrics):
    """Extract key metrics from BacktestMetrics."""
    return {
        "return_pct": round(metrics.total_return * 100, 2),
        "sharpe": round(metrics.sharpe_ratio, 2),
        "pf": round(metrics.profit_factor, 2),
        "win_rate": round(metrics.win_rate * 100, 1),
        "trades": metrics.total_trades,
        "max_dd": round(metrics.max_drawdown * 100, 2),
        "calmar": round(metrics.calmar_ratio, 2),
    }


def main():
    print("=" * 75)
    print("  EDGECORE Phase 1.5 ÔÇö Incremental Universe Expansion")
    print(f"  Base: 37 symbols (v32j) | Candidates: {len(CANDIDATES)}")
    print("  Decision: KEEP if dSharpe >= 0 AND dPF >= 0")
    print("=" * 75)
    print()

    # ÔöÇÔöÇ Step 1: Baseline ÔöÇÔöÇ
    print(f"  [0/{len(CANDIDATES)}] BASELINE (37 symbols)")
    t0 = time.time()
    base_metrics = run_backtest(BASE_SYMBOLS, BASE_SECTOR_MAP)
    base = extract_metrics(base_metrics)
    print(
        f"  Baseline: +{base['return_pct']}%  Sharpe {base['sharpe']}  "
        f"PF {base['pf']}  WR {base['win_rate']}%  "
        f"{base['trades']}t  DD {base['max_dd']}%  ({time.time() - t0:.0f}s)"
    )
    print()

    # ÔöÇÔöÇ Step 2: Test each candidate ÔöÇÔöÇ
    results = []
    for idx, (sym, sector) in enumerate(CANDIDATES, 1):
        if sym in BASE_SYMBOLS:
            print(f"  [{idx}/{len(CANDIDATES)}] {sym} ÔÇö SKIP (already in base)")
            continue

        test_symbols = BASE_SYMBOLS + [sym]
        test_sectors = dict(BASE_SECTOR_MAP)
        test_sectors[sym] = sector

        print(f"  [{idx}/{len(CANDIDATES)}] Testing +{sym} ({sector})...", end=" ", flush=True)
        t0 = time.time()
        try:
            m = run_backtest(test_symbols, test_sectors)
            r = extract_metrics(m)
            elapsed = time.time() - t0

            d_sharpe = r["sharpe"] - base["sharpe"]
            d_pf = r["pf"] - base["pf"]
            d_trades = r["trades"] - base["trades"]
            d_return = r["return_pct"] - base["return_pct"]

            keep = d_sharpe >= 0 and d_pf >= 0 and r["trades"] >= base["trades"]
            verdict = "KEEP" if keep else "REJECT"

            print(
                f"+{r['return_pct']}% S{r['sharpe']} PF{r['pf']} "
                f"{r['trades']}t DD{r['max_dd']}%  "
                f"dS={d_sharpe:+.2f} dPF={d_pf:+.2f} dT={d_trades:+d}  "
                f"=> {verdict}  ({elapsed:.0f}s)"
            )

            results.append(
                {
                    "symbol": sym,
                    "sector": sector,
                    "verdict": verdict,
                    **r,
                    "d_sharpe": round(d_sharpe, 2),
                    "d_pf": round(d_pf, 2),
                    "d_trades": d_trades,
                    "d_return": round(d_return, 2),
                }
            )
        except Exception as e:
            print(f"ERROR: {e}")
            results.append(
                {
                    "symbol": sym,
                    "sector": sector,
                    "verdict": "ERROR",
                    "error": str(e),
                }
            )

    # ÔöÇÔöÇ Step 3: Summary ÔöÇÔöÇ
    print()
    print("=" * 75)
    print("  SUMMARY")
    print("=" * 75)
    kept = [r for r in results if r.get("verdict") == "KEEP"]
    rejected = [r for r in results if r.get("verdict") == "REJECT"]
    errors = [r for r in results if r.get("verdict") == "ERROR"]

    print(
        f"  Baseline: +{base['return_pct']}%  Sharpe {base['sharpe']}  "
        f"PF {base['pf']}  {base['trades']}t  DD {base['max_dd']}%"
    )
    print(f"  KEEP: {len(kept)}  |  REJECT: {len(rejected)}  |  ERROR: {len(errors)}")
    print()

    if kept:
        print("  === KEPT SYMBOLS ===")
        for r in sorted(kept, key=lambda x: x.get("d_sharpe", 0), reverse=True):
            print(
                f"    {r['symbol']:6s} ({r['sector']:20s})  "
                f"dS={r['d_sharpe']:+.2f}  dPF={r['d_pf']:+.2f}  "
                f"dT={r['d_trades']:+d}  dRet={r['d_return']:+.2f}%"
            )
        print()

    if rejected:
        print("  === REJECTED SYMBOLS ===")
        for r in sorted(rejected, key=lambda x: x.get("d_sharpe", 0)):
            print(
                f"    {r['symbol']:6s} ({r['sector']:20s})  "
                f"dS={r['d_sharpe']:+.2f}  dPF={r['d_pf']:+.2f}  "
                f"dT={r['d_trades']:+d}  dRet={r['d_return']:+.2f}%"
            )
        print()

    # Save results
    out = os.path.join(_ROOT, "results", "phase15_universe_expansion.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"baseline": base, "candidates": results}, f, indent=2)
    print(f"  [Saved] {out}")

    # Print recommended v34 universe
    if kept:
        v34_symbols = BASE_SYMBOLS + [r["symbol"] for r in kept]
        print()
        print(f"  Recommended v34 universe: {len(v34_symbols)} symbols")
        print(f"  New symbols: {', '.join(r['symbol'] for r in kept)}")


if __name__ == "__main__":
    main()
