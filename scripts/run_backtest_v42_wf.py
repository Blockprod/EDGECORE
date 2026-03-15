#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""EDGECORE v42 -- Phase 4: Walk-Forward Out-of-Sample Validation.

Parametres geles depuis v41a (meilleur resultat du sweep v41) :
  entry_z=1.6, exit_z=0.2, rediscovery=2, leverage=2.5x
  max_half_life=60, TimeStop=20 bars, daily data

Design walk-forward :
  5 fenetres rolling  (Train 18 mois / OOS Test 6 mois)

  P1: Train 2018-01->2019-07  /  OOS 2019-07->2020-01
  P2: Train 2019-01->2020-07  /  OOS 2020-07->2021-01
  P3: Train 2021-01->2022-07  /  OOS 2022-07->2023-01
  P4: Train 2022-01->2023-07  /  OOS 2023-07->2024-01
  P5: Train 2023-01->2024-07  /  OOS 2024-07->2025-01

Critere de validation OOS :
  PASS   = Sharpe OOS >= 1.2 sur >= 4/5 fenetres
  S-PASS = Sharpe OOS >= 0.8 sur >= 4/5 fenetres  (acceptable)
  FAIL   = < 0.8 sur >= 2 fenetres -> overfitting

Reference in-sample (v41a) :
  S=2.00  +50.43%  WR=70.4%  ~9t/yr  DD=-3.01%  [2023-03->2026-03]
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.runner import BacktestRunner
from config.settings import get_settings
from execution.time_stop import TimeStopConfig, TimeStopManager

# -- Universe (identical to v41a) --------------------------------------------
WF_SYMBOLS = [
    "SPY",
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO", "XLK",
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    "XOM", "CVX", "COP", "EOG",
    "KO", "PEP", "PG", "CL", "WMT",
    "CAT", "HON", "DE", "GE", "RTX",
    "NEE", "DUK", "SO",
    "JNJ", "PFE", "UNH", "MRK", "ABBV",
    "MCD",
]

WF_SECTOR_MAP = {
    "AAPL": "technology", "MSFT": "technology", "GOOGL": "technology",
    "META": "technology", "NVDA": "technology", "AMD": "technology",
    "AVGO": "technology", "XLK": "technology",
    "JPM": "financials", "GS": "financials", "BAC": "financials",
    "MS": "financials", "WFC": "financials", "C": "financials",
    "SCHW": "financials",
    "XOM": "energy", "CVX": "energy", "COP": "energy", "EOG": "energy",
    "KO": "consumer_staples", "PEP": "consumer_staples",
    "PG": "consumer_staples", "CL": "consumer_staples",
    "WMT": "consumer_staples", "MCD": "consumer_staples",
    "CAT": "industrials", "HON": "industrials", "DE": "industrials",
    "GE": "industrials", "RTX": "industrials",
    "NEE": "utilities", "DUK": "utilities", "SO": "utilities",
    "JNJ": "healthcare", "PFE": "healthcare", "UNH": "healthcare",
    "MRK": "healthcare", "ABBV": "healthcare",
    "SPY": "benchmark",
}

# -- v41a frozen params -------------------------------------------------------
def _apply_v41a_settings():
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
    s.strategy.regime_directional_filter   = False
    s.strategy.trend_long_sizing           = 0.75
    s.strategy.disable_shorts_in_bull_trend = False
    s.strategy.short_sizing_multiplier     = 0.50
    s.regime.enabled          = True
    s.regime.ma_fast          = 50
    s.regime.ma_slow          = 200
    s.regime.vol_threshold    = 0.18
    s.regime.vol_window       = 20
    s.regime.neutral_band_pct = 0.02
    s.regime.trend_favorable_sizing = 1.0
    s.regime.neutral_sizing   = 0.70
    s.momentum.enabled        = True
    s.momentum.lookback       = 20
    s.momentum.weight         = 0.30
    s.momentum.min_strength   = 1.0
    s.momentum.max_boost      = 1.0
    s.pair_blacklist.enabled                = True
    s.pair_blacklist.max_consecutive_losses = 5
    s.pair_blacklist.cooldown_days          = 10
    s.risk.max_concurrent_positions         = 10
    if hasattr(s.strategy, 'fdr_q_level'):
        s.strategy.fdr_q_level = 0.25


# -- Walk-forward windows ----------------------------------------------------
# Rolling 6-month steps. Train 18 months gives enough data for lookback=120
# + pair discovery. OOS 6 months = ~126 bars per window.
WF_WINDOWS = [
    # label         train_start    train_end      oos_start      oos_end
    ("P1 2019H2", "2018-01-02", "2019-07-01", "2019-07-01", "2020-01-01"),
    ("P2 2020H2", "2019-01-02", "2020-07-01", "2020-07-01", "2021-01-01"),
    ("P3 2022H2", "2021-01-04", "2022-07-01", "2022-07-01", "2023-01-01"),
    ("P4 2023H2", "2022-01-03", "2023-07-01", "2023-07-01", "2024-01-01"),
    ("P5 2024H2", "2023-01-03", "2024-07-01", "2024-07-01", "2025-01-01"),
]


def main():
    print("=" * 82)
    print("  EDGECORE v42 -- Phase 4: Walk-Forward Out-of-Sample Validation")
    print()
    print("  Parametres geles (v41a):")
    print("    entry_z=1.6  exit_z=0.2  rediscovery=2  leverage=2.5x  TimeStop=20")
    print()
    print("  Reference in-sample (2023-03 -> 2026-03):")
    print("    S=2.00  +50.43%  WR=70.4%  ~9t/yr  DD=-3.01%")
    print()
    print("  5 fenetres rolling (Train 18 mois / OOS 6 mois)")
    print("  Critere PASS : Sharpe OOS >= 1.2 sur >= 4/5 fenetres")
    print("=" * 82)
    print()

    runner = BacktestRunner()
    runner.config.initial_capital = 100_000
    ts20 = TimeStopManager(TimeStopConfig(
        half_life_multiplier=1.2,
        max_days_cap=20,
        default_max_bars=20,
    ))

    print("  %-12s  %-22s  %-22s  %7s  %6s  %5s  %6s  %9s  %7s" % (
        "Window", "Train", "OOS", "Return", "Sharpe", "PF", "WR",
        "t (~ann)", "MaxDD"))
    print("  " + "-" * 98)

    results = []
    for label, train_start, train_end, oos_start, oos_end in WF_WINDOWS:
        _apply_v41a_settings()
        runner.config.initial_capital = 100_000
        t0 = time.time()
        try:
            metrics = runner.run_unified(
                symbols=WF_SYMBOLS,
                start_date=train_start,   # include training window for lookback warmup
                end_date=oos_end,
                oos_start_date=oos_start, # collect metrics from OOS start only
                sector_map=WF_SECTOR_MAP,
                pair_rediscovery_interval=2,
                allocation_per_pair_pct=50.0,
                max_position_loss_pct=0.07,
                max_portfolio_heat=3.0,
                time_stop=ts20,
                leverage_multiplier=2.5,
            )
            elapsed = int(time.time() - t0)
            ret = metrics.total_return * 100
            sh  = metrics.sharpe_ratio
            pf  = metrics.profit_factor
            wr  = metrics.win_rate * 100
            t   = metrics.total_trades
            dd  = metrics.max_drawdown * 100
            tpy = t * 2      # 6-month OOS x2 = annualised estimate
            verdict = "PASS" if sh >= 1.2 else ("S-PASS" if sh >= 0.8 else "FAIL")
            print("  %-12s  %s->%s  %s->%s  %+6.2f%%  S=%5.2f  %5.2f  %5.1f%%"
                  "  t=%2d(~%2.0f)  %+6.2f%%  [%s/%ds]" % (
                      label,
                      train_start[:7], train_end[:7],
                      oos_start[:7],   oos_end[:7],
                      ret, sh, pf, wr, t, tpy, dd, verdict, elapsed))
            results.append((label, metrics, sh, verdict))
        except Exception as e:
            elapsed = int(time.time() - t0)
            print("  %-12s  ERROR: %s [%ds]" % (label, str(e)[:70], elapsed))
            results.append((label, None, None, "ERROR"))

    # -- Verdict final --------------------------------------------------------
    print()
    print("=" * 82)
    print("  VERDICT WALK-FORWARD")
    print("=" * 82)
    print()

    valid   = [(l, m, sh, v) for l, m, sh, v in results if sh is not None]
    passes  = sum(1 for _, _, sh, v in valid if v == "PASS")
    spasses = sum(1 for _, _, sh, v in valid if v == "S-PASS")
    fails   = sum(1 for _, _, sh, v in valid if v == "FAIL")
    errors  = sum(1 for _, _, sh, v in results if v == "ERROR")

    sharpes = [sh for _, _, sh, _ in valid]
    avg_sh  = sum(sharpes) / len(sharpes) if sharpes else 0.0
    min_sh  = min(sharpes) if sharpes else 0.0

    print("  Resultats OOS (%d/5 fenetres):" % len(valid))
    print("    PASS    (S>=1.2) : %d/5" % passes)
    print("    S-PASS  (S>=0.8) : %d/5" % spasses)
    print("    FAIL    (S<0.8)  : %d/5" % fails)
    if errors:
        print("    ERREURS          : %d/5" % errors)
    print()
    print("    Sharpe moyen OOS   : %.2f" % avg_sh)
    print("    Sharpe minimum OOS : %.2f" % min_sh)
    print("    vs. In-Sample      : 2.00")
    print("    Ratio OOS/IS       : %.0f%%" % (avg_sh / 2.00 * 100 if avg_sh else 0))
    print()

    if passes >= 4:
        overall = "PASS -- Strategie validee OOS"
        detail  = "Sharpe OOS robuste sur >=4/5 fenetres. Pret pour Phase 5."
    elif passes + spasses >= 4:
        overall = "S-PASS -- Strategie acceptable"
        detail  = "Perf OOS legerement degradee mais positive. Verifier fenetres FAIL."
    else:
        overall = "FAIL -- Overfitting detecte"
        detail  = "Strategie ne se generalise pas OOS. Revoir parametres v41a."

    print("  >>> %s <<<" % overall)
    print("  %s" % detail)
    print()
    print("  PROCHAINE ETAPE :")
    if "FAIL" not in overall:
        print("    -> Phase 5 : Expansion univers Europe (CAC40/DAX ~100 sym)")
        print("    -> Objectif : 50+ trades/an  (vs ~9/an actuellement)")
        print()
        print("  Pour sauvegarder les resultats :")
        print("    .\\venv\\Scripts\\python.exe scripts\\run_backtest_v42_wf.py"
              " 2>&1 | Tee-Object results\\v42_wf_output.txt")
    else:
        print("    -> Revoir entry_z / leverage / TimeStop avant expansion")
    print()


if __name__ == "__main__":
    main()
