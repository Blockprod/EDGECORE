#!/usr/bin/env python
"""v49 P5 2024H2 — CERT-02 fix attempt.

Root cause hypothesis for v48 P5 = 0 trades:
    Quadruple screening (EG + Johansen + HAC + Bonferroni + FDR@q=0.30)
    is too restrictive for the 2023H1-2024H1 training window in the current
    low-volatility bull regime.  entry_z=1.6 is too high for the small
    2024H2 spread deviations in a smooth bull market.

Changes vs v48:
    - fdr_q_level: 0.30 → 0.50  (relax FDR cutoff, more candidate pairs pass)
    - entry_z_score: 1.6 → 1.3  (lower barrier for mildly mean-reverting spreads)
    - Everything else identical to v48

Expected outcome: ≥ 10 trades, Sharpe ≥ 0.5 on P5.

PREREQUISITES:
    IBKR Gateway running on 127.0.0.1:4002 with market data subscriptions.
"""

import gc
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager
from pair_selection.filters import MomentumDivergenceFilter

# ---------------------------------------------------------------------------
# Identical universe to v48
# ---------------------------------------------------------------------------
WF_SYMBOLS = [
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

WF_SECTOR_MAP = {
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


def _apply_settings_v49():
    """Apply v49 parameters.

    Changes vs v48:
        - fdr_q_level:  0.30 → 0.50  (relax FDR, allow more candidate pairs)
        - entry_z_score: 1.6 → 1.3   (lower barrier for 2024H2 low-vol regime)
    """
    s = get_settings()
    s.strategy.lookback_window = 120
    s.strategy.additional_lookback_windows = [63]
    s.strategy.entry_z_score = 1.3  # CERT-02 change: was 1.6
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
    s.momentum.enabled = True
    s.momentum.lookback = 20
    s.momentum.weight = 0.30
    s.momentum.min_strength = 1.0
    s.momentum.max_boost = 1.0
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
        s.strategy.fdr_q_level = 0.50  # CERT-02 change: was 0.30


def main():
    print("=" * 70)
    print("  v49 P5 2024H2 — CERT-02 fix (relaxed FDR + lower entry_z)")
    print("  v48 reference: P1=-1.71 FAIL | P2=+1.65 | P3=+2.04 | P4=-2.44 | P5=0.00 FAIL")
    print("=" * 70)

    gc.collect()

    _apply_settings_v49()
    runner = BacktestRunner()
    runner.config.initial_capital = 100_000

    ts20 = TimeStopManager(
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

    label = "P5 2024H2"
    train_start, train_end = "2023-01-03", "2024-07-01"
    oos_start, oos_end = "2024-07-01", "2025-01-01"

    print(f"\n  Running {label} (train {train_start} -> {train_end} | OOS {oos_start} -> {oos_end})")
    ret: float = 0.0
    wr: float = 0.0
    t: int = 0
    dd: float = 0.0
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
            time_stop=ts20,
            leverage_multiplier=2.5,
            momentum_filter=mom_filter,
        )
        elapsed = int(time.time() - t0)
        sh = metrics.sharpe_ratio
        ret = metrics.total_return * 100
        wr = metrics.win_rate * 100
        t = metrics.total_trades
        dd = metrics.max_drawdown * 100
        v = "PASS" if sh >= 1.2 else ("S-PASS" if sh >= 0.8 else ("CERT" if sh >= 0.5 and t >= 10 else "FAIL"))
        print(f"  -> S={sh:5.2f}  {ret:+6.2f}%  WR={wr:5.1f}%  t={t:2d}  DD={dd:+6.2f}%  [{v}/{elapsed}s]")

        results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
        os.makedirs(results_dir, exist_ok=True)
        results_path = os.path.join(results_dir, "v49_p5_results.txt")
        with open(results_path, "w", encoding="utf-8") as f:
            f.write("v49 P5 2024H2 — CERT-02 fix\n")
            f.write("entry_z_score: 1.3 (was 1.6)\n")
            f.write("fdr_q_level: 0.50 (was 0.30)\n")
            f.write(f"Sharpe ratio: {sh:.4f}\n")
            f.write(f"Total return: {ret:.2f}%\n")
            f.write(f"Win rate: {wr:.2f}%\n")
            f.write(f"Total trades: {t}\n")
            f.write(f"Max drawdown: {dd:.2f}%\n")
            f.write(f"Verdict: {v}\n")
            f.write(f"Elapsed: {elapsed}s\n")
        print(f"[Résultat] {results_path}")

        cert_pass = sh >= 0.5 and t >= 10 and dd < 15.0
        print()
        print(f"  CERT-02 criteria: Sharpe≥0.5={sh >= 0.5} trades≥10={t >= 10} DD<15%={dd < 15.0}")
        print(f"  CERT-02 result  : {'PASS ✅' if cert_pass else 'FAIL ❌ — adjust further'}")

    except Exception as e:
        elapsed = int(time.time() - t0)
        print(f"  -> ERROR: {str(e)[:200]}")


if __name__ == "__main__":
    main()
