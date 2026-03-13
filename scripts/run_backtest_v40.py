#!/usr/bin/env python
"""EDGECORE v40 -- Phase 3 Validation: Intraday 1-Hour Synthetic Bars.

Phase 3 targets:
  Trades  >= 200/year
  Sharpe  >= 1.5
  Leverage = 1.5x

Architecture:
  - Load 3-year daily prices (IBKR, 2023-03-04 to 2026-03-04, same universe as v37/v39)
  - Generate synthetic 1-hour bars via Brownian bridge (7 bars/trading day)
  - Run simulator bar-by-bar with intraday-rescaled parameters
  - Sharpe annualized at 252 x 7 = 1764 bars/year

Parameter rescaling (daily -> intraday 7-bar/day):
  lookback_window     : 120d  ->  420 bars  (60 trading days x 7)
  additional_lookback : [63d] ->  [210 bars] (30 trading days x 7)
  max_half_life       : 60d   ->  350 bars   (50 trading days x 7)
  pair_rediscovery    : 2d    ->  7 bars     (1 trading day)
  TimeStop max_days   : 20d   ->  14 bars    (2 trading days)
  entry_z_score       : 1.8   ->  1.4        (lower: intraday noise is higher)
  exit_z_score        : 0.2   ->  0.15       (faster exit at intraday scale)
  z_score_stop        : 2.5   ->  2.0        (tighter: faster MR expected)

v39 baseline (daily, 2.5x leverage):
  +42.55%  S=1.82  PF=9.06  WR=65.2%  23t  DD=-2.69%
"""

import logging
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtests.cost_model import CostModel
from backtests.strategy_simulator import StrategyBacktestSimulator
from config.settings import get_settings
from data.intraday_loader import IntradayLoader
from execution.time_stop import TimeStopConfig, TimeStopManager


def _load_daily_prices_ibkr(symbols: list, start_date: str, end_date: str,
                              client_id: int = 5100) -> pd.DataFrame:
    """Load 3-year daily prices from IBKR using a dedicated client_id.

    Uses client_id=5100 by default to avoid conflicts with live/other backtests
    that use client_id=5000.
    """
    from tqdm import tqdm

    from execution.ibkr_engine import IBGatewaySync

    logging.getLogger("execution.ibkr_engine").setLevel(logging.ERROR)
    price_data = {}
    engine = IBGatewaySync(host="127.0.0.1", port=4002, client_id=client_id)
    engine.connect()
    try:
        with tqdm(total=len(symbols), desc="[IBKR daily] Loading", ncols=80) as pbar:
            for sym in symbols:
                try:
                    bars = engine.get_historical_data(
                        symbol=sym, duration="5 Y",
                        bar_size="1 day", what_to_show="ADJUSTED_LAST"
                    )
                    if bars:
                        df = pd.DataFrame(
                            {"close": [b.close for b in bars]},
                            index=pd.DatetimeIndex([b.date for b in bars]),
                        )
                        price_data[sym] = df["close"]
                except Exception as e:
                    print(f"       WARN: {sym} failed: {e}")
                pbar.update(1)
    finally:
        try:
            engine.disconnect()
        except Exception:
            pass

    if not price_data:
        raise RuntimeError("No price data loaded from IBKR")

    prices = pd.DataFrame(price_data).sort_index()
    # Trim to requested window
    prices = prices.loc[start_date:end_date]
    prices = prices.ffill().dropna(how="all")
    return prices

# -- Universe: exact v37/v39 core (39 symbols) --------------------------------
V40_SYMBOLS = [
    # Market benchmark
    "SPY",
    # Technology (8)
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO", "XLK",
    # Financials (7)
    "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
    # Energy (4)
    "XOM", "CVX", "COP", "EOG",
    # Consumer Staples (5)
    "KO", "PEP", "PG", "CL", "WMT",
    # Industrials (5)
    "CAT", "HON", "DE", "GE", "RTX",
    # Utilities (3)
    "NEE", "DUK", "SO",
    # Healthcare (5)
    "JNJ", "PFE", "UNH", "MRK", "ABBV",
    # Consumer Staples addition (v37 surgical)
    "MCD",
]

V40_SECTOR_MAP = {
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

BARS_PER_DAY = 7        # 1-hour bars: 9:30-16:00 = 7 bars
START_DATE   = "2023-03-04"
END_DATE     = "2026-03-04"


def main():
    print("=" * 75)
    print("  EDGECORE v40 -- Phase 3: Intraday 1-Hour Synthetic Bars")
    print("  Universe: %d symbols (v37/v39 core, identical)" % len(V40_SYMBOLS))
    print("  Bars:     %d/day (1-hour, synthetic via Brownian bridge)" % BARS_PER_DAY)
    print("  Leverage: 1.5x gross exposure (Phase 3 roadmap)")
    print("  Window:   %s to %s (3 years = 756 trading days x 7 = 5292 bars)" % (
        START_DATE, END_DATE))
    print()
    print("  Phase 3 targets: Trades >= 200/yr  Sharpe >= 1.5  MaxDD > -8%")
    print("  v39 baseline:    23t  S=1.82  +42.55%  DD=-2.69%  (2.5x daily)")
    print("=" * 75)
    print()

    # ---- Apply intraday-rescaled strategy settings --------------------------
    s = get_settings()
    # Cointegration / signal parameters (rescaled from daily -> 7-bar/day)
    s.strategy.lookback_window             = 420    # 60 trading days x 7
    s.strategy.additional_lookback_windows = [210]  # 30 trading days x 7
    s.strategy.entry_z_score               = 1.4    # lower (hourly noise)
    s.strategy.exit_z_score                = 0.15   # faster exit
    s.strategy.entry_z_min_spread          = 0.30   # same
    s.strategy.z_score_stop                = 2.0    # tighter (fast MR)
    s.strategy.min_correlation             = 0.65   # same as v37
    s.strategy.max_half_life               = 350    # 50 trading days x 7
    s.strategy.max_position_loss_pct       = 0.03   # same as v37
    s.strategy.internal_max_drawdown_pct   = 0.12   # same
    s.strategy.use_kalman                  = True
    s.strategy.bonferroni_correction       = True
    s.strategy.johansen_confirmation       = True
    s.strategy.newey_west_consensus        = True
    s.strategy.weekly_zscore_entry_gate    = 0.3    # kept (weekly confirm bypassed at intraday)
    s.strategy.regime_directional_filter   = False
    s.strategy.trend_long_sizing           = 0.75
    s.strategy.disable_shorts_in_bull_trend = False
    s.strategy.short_sizing_multiplier     = 0.50
    # Regime filter (same as v37)
    s.regime.enabled           = True
    s.regime.ma_fast           = 50
    s.regime.ma_slow           = 200
    s.regime.vol_threshold     = 0.18
    s.regime.vol_window        = 20
    s.regime.neutral_band_pct  = 0.02
    s.regime.trend_favorable_sizing = 1.0
    s.regime.neutral_sizing    = 0.70
    # Momentum (same as v37)
    s.momentum.enabled         = True
    s.momentum.lookback        = 20
    s.momentum.weight          = 0.30
    s.momentum.min_strength    = 1.0
    s.momentum.max_boost       = 1.0
    # Pair blacklist (same as v37)
    s.pair_blacklist.enabled                 = True
    s.pair_blacklist.max_consecutive_losses  = 5
    s.pair_blacklist.cooldown_days           = 10
    # Risk
    s.risk.max_concurrent_positions = 10
    if hasattr(s.strategy, 'fdr_q_level'):
        s.strategy.fdr_q_level = 0.25

    # ---- Time stop: 14 bars = 2 trading days at 7 bars/day ------------------
    time_stop = TimeStopManager(TimeStopConfig(
        half_life_multiplier=1.5, max_days_cap=14, default_max_bars=14,
    ))

    # ---- Step 1: Load daily prices from IBKR (client_id=5100, avoids conflicts) ----
    print("  [1/3] Loading 3-year daily prices from IBKR (client_id=5100)...")
    t0 = time.time()
    daily_prices = _load_daily_prices_ibkr(
        V40_SYMBOLS, START_DATE, END_DATE, client_id=5100
    )
    print("       Daily prices: %d rows x %d symbols (%.1fs)" % (
        len(daily_prices), len(daily_prices.columns), time.time() - t0))

    # ---- Step 2: Generate synthetic 1-hour bars via Brownian bridge ----------
    print("  [2/3] Generating synthetic 1-hour bars (%dx expansion)..." % BARS_PER_DAY)
    t1 = time.time()
    loader = IntradayLoader()
    intraday_prices = loader.generate_synthetic_intraday(
        daily_prices, bars_per_day=BARS_PER_DAY
    )
    print("       Intraday bars: %d rows x %d symbols (%.1fs)" % (
        len(intraday_prices), len(intraday_prices.columns), time.time() - t1))
    print("       Period: %s -> %s" % (
        str(intraday_prices.index[0])[:16], str(intraday_prices.index[-1])[:16]))

    # ---- Step 3: Run intraday simulator -------------------------------------
    print("  [3/3] Running intraday backtest (bars_per_day=%d, leverage=1.5x)..." % BARS_PER_DAY)
    t2 = time.time()
    sim = StrategyBacktestSimulator(
        cost_model=CostModel(),
        initial_capital=100_000,
        allocation_per_pair_pct=50.0,
        pair_rediscovery_interval=BARS_PER_DAY,  # rediscover once per trading day
        time_stop=time_stop,
        sector_map=V40_SECTOR_MAP,
        leverage_multiplier=1.5,
        max_position_loss_pct=0.07,
        max_portfolio_heat=3.0,
        bars_per_day=BARS_PER_DAY,
    )
    metrics = sim.run(intraday_prices, sector_map=V40_SECTOR_MAP)
    elapsed = time.time() - t2
    print("       Completed in %.1fs" % elapsed)
    print()

    # ---- Results ------------------------------------------------------------
    ret = metrics.total_return * 100
    sh  = metrics.sharpe_ratio
    pf  = metrics.profit_factor
    wr  = metrics.win_rate * 100
    t   = metrics.total_trades
    dd  = metrics.max_drawdown * 100
    cal = abs(ret / dd) if dd != 0 else 0.0

    # Annualize trades (3-year window -> per-year)
    try:
        years = 3.0
        trades_per_year = t / years
    except Exception:
        trades_per_year = t

    print("=" * 75)
    print("  v40 PHASE 3 RESULTS (1-hour synthetic, 1.5x leverage)")
    print("=" * 75)
    print()
    print("  Return     : %+.2f%%" % ret)
    print("  Sharpe     : %.2f   (annualized at 252 x %d = %d bars/year)" % (
        sh, BARS_PER_DAY, 252 * BARS_PER_DAY))
    print("  PF         : %.2f" % pf)
    print("  WR         : %.1f%%" % wr)
    print("  Trades     : %d total  (~%.0f/year)" % (t, trades_per_year))
    print("  MaxDD      : %.2f%%" % dd)
    print("  Calmar     : %.2f" % cal)
    print()
    print("  PHASE 3 TARGET CHECK:")
    print("    Trades >= 200/year (go-criteria) : %s (~%.0f/yr)" % (
        "PASS" if trades_per_year >= 200 else "MISS", trades_per_year))
    print("    Sharpe >= 1.5 (go-criteria)      : %s (%.2f)" % (
        "PASS" if sh >= 1.5 else "MISS", sh))
    print("    Sharpe >= 2.0 (stretch goal)     : %s (%.2f)" % (
        "PASS" if sh >= 2.0 else "MISS", sh))
    print("    PF     >= 2.5                    : %s (%.2f)" % (
        "PASS" if pf >= 2.5 else "MISS", pf))
    print("    WR     >= 50%%                   : %s (%.1f%%)" % (
        "PASS" if wr >= 50.0 else "MISS", wr))
    print("    MaxDD  > -8%%                    : %s (%.2f%%)" % (
        "PASS" if dd > -8.0 else "MISS", dd))
    print()
    print("  vs v39 BASELINE (2.5x daily):")
    print("    Return  : %+.2f%%  (v39: +42.55%%)  delta=%+.2f%%" % (ret, ret - 42.55))
    print("    Sharpe  : %.2f   (v39: 1.82)  delta=%+.2f" % (sh, sh - 1.82))
    print("    Trades  : %d/yr  (v39: ~8/yr)" % int(trades_per_year))
    print("    MaxDD   : %.2f%%  (v39: -2.69%%)" % dd)
    print()

    phase3_pass = (trades_per_year >= 200 and sh >= 1.5 and dd > -8.0)
    if phase3_pass:
        print("  >>> Phase 3 PASS: Intraday 1-hour validated <<<")
        print("       -> Proceed to Phase 4: ML signal combiner walk-forward")
    else:
        print("  >>> Phase 3 PARTIAL: see misses above <<<")
        if trades_per_year < 200:
            print("       -> Trade freq low: try lower entry_z (1.2?) or")
            print("          pair_rediscovery_interval=3 or multi-bar exits")
        if sh < 1.5:
            print("       -> Sharpe low: check noise level in synthetic bars")
        print("       -> Consider: real 1-hour IBKR data (1748 bars/year window)")
    print()


if __name__ == "__main__":
    main()
