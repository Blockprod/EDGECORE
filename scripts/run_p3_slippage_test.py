#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""EDGECORE ÔÇö Phase 0.1 Validation: Slippage Stress-Test P3.

Objectif
--------
Valider que P3 2022H2 (seule fen├¬tre PASS dans v45b, S=2.21) tient
apr├¿s application d'un mod├¿le de slippage PLUS STRICT que le d├®faut.

Trois niveaux de friction:
  A. R├®f├®rence    : CostModel() d├®faut   (eta=0.05, delay=0.01j)
  B. R├®aliste     : equity_cost_config() (eta=0.10, delay=0.5j)    <- roadmap
  C. Spread seul  : zero_impact_slippage(eta=0.0, delay=0.0)       <- plancher

Si P3 SÔëÑ1.2 au niveau B (r├®aliste) ÔåÆ crit├¿re Phase 0.1 VALID├ë.
Si P3 S<1.2 au niveau B ÔåÆ les r├®sultats v45b sont surestim├®s, il faut
   calibrer le mod├¿le et relancer.

Usage:
    python scripts/run_p3_slippage_test.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.cost_model import CostModel, CostModelConfig, equity_cost_config
from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.slippage import (
    SlippageModel,
    conservative_equity_slippage,
    realistic_equity_slippage,
    zero_impact_slippage,
)
from execution.time_stop import TimeStopConfig, TimeStopManager

# ---------------------------------------------------------------------------
# P3 window + same universe/params as v45b
# ---------------------------------------------------------------------------

P3_WINDOW = ("P3 2022H2", "2021-01-04", "2022-07-01", "2022-07-01", "2023-01-01")

# Same 103-symbol universe as v45b
WF_SYMBOLS = [
    "SPY",
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO", "XLK",
    "INTC", "QCOM", "TXN", "CRM", "ORCL", "ACN", "CSCO",
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    "BLK", "AXP", "USB", "PNC", "COF", "BK", "TFC",
    "XOM", "CVX", "COP", "EOG",
    "SLB", "VLO", "MPC", "PSX", "OXY",
    "KO", "PEP", "PG", "CL", "WMT", "MCD",
    "COST", "MDLZ", "GIS", "PM", "MO",
    "CAT", "HON", "DE", "GE", "RTX",
    "MMM", "UPS", "BA", "ITW", "LMT", "FDX",
    "NEE", "DUK", "SO",
    "AEP", "EXC", "WEC",
    "JNJ", "PFE", "UNH", "MRK", "ABBV",
    "TMO", "ABT", "DHR", "MDT", "CVS", "CI", "BMY",
    "AMZN", "TSLA", "HD", "NKE", "LOW", "TGT", "SBUX", "F", "GM",
    "LIN", "APD", "ECL", "NEM", "FCX",
    "PLD", "AMT", "SPG", "EQIX",
    "T", "VZ", "CMCSA", "DIS", "NFLX",
]

WF_SECTOR_MAP = {
    "AAPL": "technology", "MSFT": "technology", "GOOGL": "technology",
    "META": "technology", "NVDA": "technology", "AMD": "technology",
    "AVGO": "technology", "XLK": "technology",
    "INTC": "technology", "QCOM": "technology", "TXN": "technology",
    "CRM": "technology", "ORCL": "technology", "ACN": "technology",
    "CSCO": "technology",
    "JPM": "financials", "GS": "financials", "BAC": "financials",
    "MS": "financials", "WFC": "financials", "C": "financials",
    "SCHW": "financials",
    "BLK": "financials", "AXP": "financials", "USB": "financials",
    "PNC": "financials", "COF": "financials", "BK": "financials",
    "TFC": "financials",
    "XOM": "energy", "CVX": "energy", "COP": "energy", "EOG": "energy",
    "SLB": "energy", "VLO": "energy", "MPC": "energy",
    "PSX": "energy", "OXY": "energy",
    "KO": "consumer_staples", "PEP": "consumer_staples",
    "PG": "consumer_staples", "CL": "consumer_staples",
    "WMT": "consumer_staples", "MCD": "consumer_staples",
    "COST": "consumer_staples", "MDLZ": "consumer_staples",
    "GIS": "consumer_staples", "PM": "consumer_staples",
    "MO": "consumer_staples",
    "CAT": "industrials", "HON": "industrials", "DE": "industrials",
    "GE": "industrials", "RTX": "industrials",
    "MMM": "industrials", "UPS": "industrials", "BA": "industrials",
    "ITW": "industrials", "LMT": "industrials", "FDX": "industrials",
    "NEE": "utilities", "DUK": "utilities", "SO": "utilities",
    "AEP": "utilities", "EXC": "utilities", "WEC": "utilities",
    "JNJ": "healthcare", "PFE": "healthcare", "UNH": "healthcare",
    "MRK": "healthcare", "ABBV": "healthcare",
    "TMO": "healthcare", "ABT": "healthcare", "DHR": "healthcare",
    "MDT": "healthcare", "CVS": "healthcare", "CI": "healthcare",
    "BMY": "healthcare",
    "AMZN": "consumer_discretionary", "TSLA": "consumer_discretionary",
    "HD": "consumer_discretionary", "NKE": "consumer_discretionary",
    "LOW": "consumer_discretionary", "TGT": "consumer_discretionary",
    "SBUX": "consumer_discretionary", "F": "consumer_discretionary",
    "GM": "consumer_discretionary",
    "LIN": "materials", "APD": "materials", "ECL": "materials",
    "NEM": "materials", "FCX": "materials",
    "PLD": "real_estate", "AMT": "real_estate",
    "SPG": "real_estate", "EQIX": "real_estate",
    "T": "communication", "VZ": "communication", "CMCSA": "communication",
    "DIS": "communication", "NFLX": "communication",
    "SPY": "benchmark",
}


def _apply_v45_settings():
    """Param├¿tres v43a fig├®s (identiques ├á v45b)."""
    s = get_settings()
    s.strategy.lookback_window             = 120
    s.strategy.additional_lookback_windows = [63]
    s.strategy.entry_z_score               = 1.6
    s.strategy.exit_z_score                = 0.2
    s.strategy.entry_z_min_spread          = 0.30
    s.strategy.z_score_stop                = 2.5
    s.strategy.min_correlation             = 0.65
    s.strategy.max_half_life               = 60
    s.strategy.max_position_loss_pct       = 0.03
    s.strategy.internal_max_drawdown_pct   = 0.12
    s.strategy.use_kalman                  = True
    s.strategy.bonferroni_correction       = True
    s.strategy.johansen_confirmation       = True
    s.strategy.newey_west_consensus        = True
    s.strategy.weekly_zscore_entry_gate    = 0.3
    s.strategy.trend_long_sizing           = 0.75
    s.strategy.disable_shorts_in_bull_trend = False
    s.strategy.short_sizing_multiplier     = 0.50
    s.momentum.enabled        = True
    s.momentum.lookback       = 20
    s.momentum.weight         = 0.30
    s.momentum.min_strength   = 1.0
    s.momentum.max_boost      = 1.0
    s.pair_blacklist.enabled                = True
    s.pair_blacklist.max_consecutive_losses = 5
    s.pair_blacklist.cooldown_days          = 10
    s.risk.max_concurrent_positions         = 15
    s.strategy.regime_directional_filter    = True
    s.regime.enabled          = True
    s.regime.ma_fast          = 50
    s.regime.ma_slow          = 200
    s.regime.vol_threshold    = 0.35
    s.regime.vol_window       = 20
    s.regime.neutral_band_pct = 0.02
    s.regime.trend_favorable_sizing = 0.80
    s.regime.neutral_sizing   = 0.70
    if hasattr(s.strategy, 'fdr_q_level'):
        s.strategy.fdr_q_level = 0.30


def _run_p3_with_cost(cost_model: CostModel, label: str) -> dict:
    """Lance P3 avec un mod├¿le de co├╗ts donn├®. Retourne les m├®triques."""
    label_p3, train_start, train_end, oos_start, oos_end = P3_WINDOW
    _apply_v45_settings()

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000
    ts20 = TimeStopManager(TimeStopConfig(
        half_life_multiplier=1.2,
        max_days_cap=20,
        default_max_bars=20,
    ))

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
            cost_model=cost_model,
        )
        elapsed = int(time.time() - t0)
        return {
            "label": label,
            "sharpe": metrics.sharpe_ratio,
            "return_pct": metrics.total_return * 100,
            "wr_pct": metrics.win_rate * 100,
            "trades": metrics.total_trades,
            "dd_pct": metrics.max_drawdown * 100,
            "elapsed": elapsed,
            "error": None,
        }
    except Exception as e:
        elapsed = int(time.time() - t0)
        return {
            "label": label,
            "sharpe": None,
            "return_pct": 0,
            "wr_pct": 0,
            "trades": 0,
            "dd_pct": 0,
            "elapsed": elapsed,
            "error": str(e)[:150],
        }


def _print_slippage_breakdown(config, label: str):
    """Affiche les co├╗ts th├®oriques par composante."""
    sm = SlippageModel(config)
    notional = 5_000   # leg typique: 5k USD
    adv_mega = 500_000_000
    adv_large = 150_000_000
    sigma = 0.02

    bd_mega = sm.breakdown_bps(notional, adv_mega, sigma)
    bd_large = sm.breakdown_bps(notional, adv_large, sigma)
    rt_mega = sm.compute_pair_roundtrip_cost(notional, notional, adv_mega, adv_mega, sigma, sigma)
    rt_large = sm.compute_pair_roundtrip_cost(notional, notional, adv_large, adv_large, sigma, sigma)

    print("  Co├╗ts th├®oriques par leg (%s, notional=$5k, sigma=2%%):" % label)
    print("    Mega-cap (ADV=$500M)  : spread=%.1fbps + impact=%.2fbps + timing=%.2fbps = %.2fbps"
          % (bd_mega["spread_bps"], bd_mega["market_impact_bps"],
             bd_mega["timing_cost_bps"], bd_mega["total_bps"]))
    print("    Large-cap (ADV=$150M) : spread=%.1fbps + impact=%.2fbps + timing=%.2fbps = %.2fbps"
          % (bd_large["spread_bps"], bd_large["market_impact_bps"],
             bd_large["timing_cost_bps"], bd_large["total_bps"]))
    print("    Round-trip (mega) : $%.2f / $10k notional = %.0f bps" % (rt_mega, rt_mega / 10_000 * 10_000))
    print("    Round-trip (large): $%.2f / $10k notional = %.0f bps" % (rt_large, rt_large / 10_000 * 10_000))


def main():
    print("=" * 95)
    print("  EDGECORE Phase 0.1 ÔÇö Slippage Stress-Test: P3 2022H2 (OOS)")
    print()
    print("  Base result (v45b, default slippage): S=2.21  t=33  +10.62%  DD=-2.71%")
    print("  Question: est-ce que SÔëÑ1.2 tient avec un slippage plus strict?")
    print()
    print("  3 niveaux de friction test├®s sur la M├èME fen├¬tre P3:")
    print("    A. D├®faut      CostModel() - eta=0.05, delay=0.01j  <- v45b actuel")
    print("    B. R├®aliste    equity_cost_config() - eta=0.10, delay=0.5j  <- roadmap")
    print("    C. Spread only zero_impact  - eta=0.0,  delay=0.0j  <- plancher")
    print()
    print("  NOTE: Cache P3 present (v45b run complet) -> pas de re-fetch IBKR")
    print("=" * 95)

    # --- D├®tail theorique avant simulation ---
    print()
    print("  D├®tail slippage par composante (avant simulation):")
    print()
    _print_slippage_breakdown(realistic_equity_slippage(), "R├®aliste B")
    print()
    _print_slippage_breakdown(conservative_equity_slippage(), "Conservateur")
    print()
    _print_slippage_breakdown(zero_impact_slippage(), "Spread only C")
    print()
    print("  ATTENTION: Le simulateur COMBINE algo_executor (impact TWAP) + cost_model")
    print("             La diff├®rence entre A et B refl├¿te uniquement le delta cost_model")
    print()

    # --- Define cost configs ---
    # A: Default (what v45b uses)
    cost_a = CostModel()  # eta=0.05, delay=0.01

    # B: equity_cost_config (roadmap's "realistic" institutional standard)
    cost_b = CostModel(equity_cost_config())  # eta=0.10, delay=0.5

    # C: spread + commission only (zero market impact + timing)
    cost_c = CostModel(CostModelConfig(
        maker_fee_bps=1.5,
        taker_fee_bps=2.0,
        base_slippage_bps=2.0,
        borrowing_cost_annual_pct=0.5,
        include_borrowing=True,
        slippage_model="fixed",   # spread only
        market_impact_eta=0.0,
        execution_delay_days=0.0,
    ))

    configs = [
        (cost_a, "A ÔÇö D├®faut (v45b)      [eta=0.05 delay=0.01]"),
        (cost_b, "B ÔÇö R├®aliste (roadmap) [eta=0.10 delay=0.50]"),
        (cost_c, "C ÔÇö Spread seul        [eta=0.00 delay=0.00]"),
    ]

    results = []
    for cost_model, label in configs:
        print("  Running %s ..." % label)
        r = _run_p3_with_cost(cost_model, label)
        results.append(r)
        if r["error"]:
            print("  -> ERROR: %s" % r["error"])
        else:
            v = "PASS" if r["sharpe"] >= 1.2 else ("S-PASS" if r["sharpe"] >= 0.8 else "FAIL")
            print("  -> S=%5.2f  %+6.2f%%  WR=%5.1f%%  t=%2d  DD=%+6.2f%%  [%s/%ds]"
                  % (r["sharpe"], r["return_pct"], r["wr_pct"],
                     r["trades"], r["dd_pct"], v, r["elapsed"]))
        print()

    # --- Summary ---
    print()
    print("=" * 95)
    print("  R├ëSULTATS ÔÇö P3 2022H2 par niveau de slippage")
    print("=" * 95)
    print()
    print("  %-42s  Sharpe  Return  Trades  DD     Verdict" % "Config slippage")
    print("  " + "-" * 80)
    for r in results:
        if r["error"]:
            print("  %-42s  ERROR: %s" % (r["label"], r["error"]))
        else:
            v = "PASS" if r["sharpe"] >= 1.2 else ("S-PASS" if r["sharpe"] >= 0.8 else "FAIL")
            print("  %-42s  %5.2f   %+6.2f%%   %3d    %+6.2f%%   %s"
                  % (r["label"], r["sharpe"], r["return_pct"], r["trades"], r["dd_pct"], v))

    print()
    print("  R├®f├®rence v45b (A d├®faut): S=2.21  t=33  +10.62%  DD=-2.71%")
    print()

    # Verdict
    r_b = next((r for r in results if "R├®aliste" in r["label"]), None)
    if r_b and r_b["error"] is None:
        if r_b["sharpe"] >= 1.2:
            print("  Ô£ô  PHASE 0.1 VALID├ëE: P3 tient ├á S=%.2f apr├¿s slippage r├®aliste (B)." % r_b["sharpe"])
            print("     Le mod├¿le de slippage actuel est ad├®quat pour la validation WF.")
            print("     P3 S=2.21 est r├®aliste et non-artefact de co├╗ts sous-estim├®s.")
            print()
            print("  NEXT: Analyser P1/P4 failures -> s├®lection paires cross-industrie")
        elif r_b["sharpe"] >= 0.8:
            print("  ~ BORDERLINE: P3 S=%.2f apr├¿s slippage r├®aliste (S-PASS)" % r_b["sharpe"])
            print("    Le WF tient mais marginalement. Calibrer eta vers 0.07 comme compromis.")
        else:
            print("  Ô£ù  ATTENTION: P3 tombe ├á S=%.2f avec slippage r├®aliste (B)." % r_b["sharpe"])
            print("     Les r├®sultats v45b sont surestim├®s. Plusieurs options:")
            print("     1. R├®duire les co├╗ts simul├®s: utiliser delay=0.10 (6min) au lieu de 0.5j")
            print("     2. Re-calibrer entry_z ├á la hausse (ex 1.8) pour n'entrer que sur")
            print("        les divergences les plus profondes (meilleur rapport qualit├®/co├╗t)")
            print("     3. Filtrer les trades < 0.5% expected PnL (before-cost)")
    print()


if __name__ == "__main__":
    main()
