# ruff: noqa: UP031
#!/usr/bin/env python
"""EDGECORE v40b -- Phase 3 Validation: Real IBKR 1-Hour Data.

POST-MORTEM v40 (synthetic Brownian bridge) -- WR=16.7%, S=-1.38, FAIL:
  Root cause: Brownian bridge guarantees path ends at daily close but has
  ZERO mean-reversion within-day.  ADF/EG detects spurious cointegration
  (artifact of the BB construction, not a real economic relationship).
  Entries fired on pure noise -> positions moved further away -> WR=16.7%.
  Lesson: synthetic intraday data is structurally incompatible with
  cointegration-based pair trading.

v40b FIX: Real IBKR 1-hour bars (confirmed: 1748 bars/year per symbol).
  - duration="1 Y", bar_size="1 hour" -> single request per symbol
  - 1 shared connection (client_id=5100) to avoid pacing conflicts
  - 1 year window: 2025-03-10 -> 2026-03-09 (250 trading days x 7 = 1750 bars)
  - lookback=420 bars (60 days) -> 1330 bars active trading (~190 trading days)

Phase 3 targets: Trades >= 200/year, Sharpe >= 1.5, MaxDD > -8%
v39 baseline (daily 2.5x): +42.55%  S=1.82  PF=9.06  WR=65.2%  23t

Parameter rescaling (daily->1h, same calendar scale):
  lookback_window     : 120d  ->  420 bars  (60 days x 7)
  max_half_life       : 60d   ->  350 bars  (50 days x 7)
  pair_rediscovery    : 2d    ->  7 bars    (1 day)
  TimeStop max_days   : 20d   ->  14 bars   (2 days)
  entry_z_score       : 1.8   ->  1.4       (lower: real hourly noise is higher)
  exit_z_score        : 0.2   ->  0.15      (faster exit)
  z_score_stop        : 2.5   ->  2.0       (tighter)
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
from execution.time_stop import TimeStopConfig, TimeStopManager

# -- Universe: exact v37/v39 core (39 symbols) --------------------------------
V40B_SYMBOLS = [
    "SPY",
    "AAPL",
    "MSFT",
    "GOOGL",
    "META",
    "NVDA",
    "AMD",
    "AVGO",
    "XLK",
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
    "MCD",
]

V40B_SECTOR_MAP = {
    "AAPL": "technology",
    "MSFT": "technology",
    "GOOGL": "technology",
    "META": "technology",
    "NVDA": "technology",
    "AMD": "technology",
    "AVGO": "technology",
    "XLK": "technology",
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
    "MCD": "consumer_staples",
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
    "SPY": "benchmark",
}

BARS_PER_DAY = 7  # 1-hour: 9:30-16:30 ET = 7 bars
START_DATE = "2025-03-10"
END_DATE = "2026-03-09"
CLIENT_ID = 5100  # dedicated, avoids conflicts with v39 (5000)


def load_1h_ibkr(symbols: list, client_id: int = CLIENT_ID) -> pd.DataFrame:
    """Load 1-hour IBKR bars for all symbols using a single persistent connection.

    Uses duration='1 Y' (single request per symbol) -- confirmed to return
    ~1748 bars per symbol for the trailing year.
    Paces requests at ~1 sec/symbol to respect IBKR 50 req/10min limit.
    """
    from tqdm import tqdm

    from execution.ibkr_engine import IBGatewaySync

    logging.getLogger("execution.ibkr_engine").setLevel(logging.ERROR)

    price_data = {}
    failed = []

    engine = IBGatewaySync(host="127.0.0.1", port=4002, client_id=client_id)
    engine.connect()
    print("  Connected to IB Gateway (client_id=%d)" % client_id)

    try:
        with tqdm(total=len(symbols), desc="  [IBKR 1h] Loading", ncols=72) as pbar:
            for sym in symbols:
                try:
                    bars = engine.get_historical_data(
                        symbol=sym,
                        duration="1 Y",
                        bar_size="1 hour",
                        what_to_show="ADJUSTED_LAST",
                    )
                    if bars and len(bars) > 50:
                        series = pd.Series(
                            [b.close for b in bars],
                            index=pd.DatetimeIndex([b.date for b in bars]),
                            name=sym,
                        )
                        price_data[sym] = series
                    else:
                        failed.append(sym)
                except Exception as exc:
                    failed.append(sym)
                    tqdm.write(f"    WARN {sym}: {str(exc)[:80]}")
                pbar.update(1)
                time.sleep(0.8)  # pace: ~1.25 symbols/sec, well under 50 req/10min
    finally:
        try:
            engine.disconnect()
        except Exception:
            pass

    if failed:
        print("  Skipped %d symbols: %s" % (len(failed), failed))

    if not price_data:
        raise RuntimeError("No 1-hour data loaded from IBKR")

    prices = pd.DataFrame(price_data).sort_index()
    prices = prices[prices.index >= pd.Timestamp(START_DATE)]
    prices = prices[prices.index <= pd.Timestamp(END_DATE) + pd.Timedelta(days=1)]
    prices = pd.DataFrame(prices).ffill().dropna(how="all")
    return prices


def main():
    print("=" * 75)
    print("  EDGECORE v40b -- Phase 3: Real IBKR 1-Hour Bars")
    print("  v40 post-mortem: BB synthetic data = spurious cointegration")
    print("  Fix: real IBKR 1h data (1748 bars confirmed per symbol)")
    print("  Universe: %d symbols | Window: %s -> %s" % (len(V40B_SYMBOLS), START_DATE, END_DATE))
    print("  Leverage: 1.5x  Bars/day: %d  Ann: 252x%d=%d bars/year" % (BARS_PER_DAY, BARS_PER_DAY, 252 * BARS_PER_DAY))
    print()
    print("  Phase 3 targets: Trades>=200/yr  Sharpe>=1.5  MaxDD>-8%")
    print("  v39 baseline:    23t  S=1.82  +42.55%  DD=-2.69%  (2.5x daily)")
    print("=" * 75)
    print()

    # ---- Strategy settings (intraday-rescaled) ----------------------------
    s = get_settings()
    s.strategy.lookback_window = 420  # 60 trading days x 7
    s.strategy.additional_lookback_windows = [210]  # 30 trading days x 7
    s.strategy.entry_z_score = 1.4
    s.strategy.exit_z_score = 0.15
    s.strategy.entry_z_min_spread = 0.30
    s.strategy.z_score_stop = 2.0
    s.strategy.min_correlation = 0.65
    s.strategy.max_half_life = 350  # 50 trading days x 7
    s.strategy.max_position_loss_pct = 0.03
    s.strategy.internal_max_drawdown_pct = 0.12
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

    # TimeStop: 28 bars = 4 trading days (slightly wider than v40's 14 to
    # allow real intraday spreads time to revert at hourly scale)
    time_stop = TimeStopManager(
        TimeStopConfig(
            half_life_multiplier=1.5,
            max_days_cap=28,
            default_max_bars=28,
        )
    )

    # ---- Load real 1-hour IBKR data ----------------------------------------
    print("  [1/2] Loading real 1-hour bars from IBKR...")
    t0 = time.time()
    prices_1h = load_1h_ibkr(V40B_SYMBOLS, client_id=CLIENT_ID)
    n_bars = len(prices_1h)
    n_syms = len(prices_1h.columns)
    n_days = n_bars / BARS_PER_DAY
    elapsed_load = time.time() - t0
    print("  Loaded: %d bars x %d symbols  (~%.0f trading days)  [%.0fs]" % (n_bars, n_syms, n_days, elapsed_load))
    print(f"  Period: {str(prices_1h.index[0])[:16]} -> {str(prices_1h.index[-1])[:16]}")
    print()

    if n_bars < 500:
        print("  ERROR: Too few bars (%d).  Check IBKR connection." % n_bars)
        return

    # ---- Run intraday simulator --------------------------------------------
    print("  [2/2] Running simulator (bars_per_day=%d, leverage=1.5x)..." % BARS_PER_DAY)
    t1 = time.time()
    sim = StrategyBacktestSimulator(
        cost_model=CostModel(),
        initial_capital=100_000,
        allocation_per_pair_pct=50.0,
        pair_rediscovery_interval=BARS_PER_DAY,  # once per trading day
        time_stop=time_stop,
        sector_map=V40B_SECTOR_MAP,
        leverage_multiplier=1.5,
        max_position_loss_pct=0.07,
        max_portfolio_heat=3.0,
        bars_per_day=BARS_PER_DAY,
    )
    metrics = sim.run(prices_1h, sector_map=V40B_SECTOR_MAP)
    elapsed_sim = time.time() - t1
    print(f"  Simulation completed in {elapsed_sim:.0f}s")
    print()

    # ---- Results ------------------------------------------------------------
    ret = metrics.total_return * 100
    sh = metrics.sharpe_ratio
    pf = metrics.profit_factor
    wr = metrics.win_rate * 100
    t = metrics.total_trades
    dd = metrics.max_drawdown * 100
    cal = abs(ret / dd) if dd != 0 else 0.0

    # Annualize: active window = total_bars / bars_per_day / 252 years
    active_trading_days = max(1, n_bars - 420) / BARS_PER_DAY
    years = active_trading_days / 252.0
    trades_per_year = t / years if years > 0 else t

    print("=" * 75)
    print("  v40b PHASE 3 RESULTS (real 1-hour IBKR, 1.5x leverage)")
    print("=" * 75)
    print()
    print(f"  Return     : {ret:+.2f}%")
    print("  Sharpe     : %.2f   (ann. at 252 x %d = %d bars/year)" % (sh, BARS_PER_DAY, 252 * BARS_PER_DAY))
    print(f"  PF         : {pf:.2f}")
    print(f"  WR         : {wr:.1f}%")
    print("  Trades     : %d total  (~%.0f/year)" % (t, trades_per_year))
    print(f"  MaxDD      : {dd:.2f}%")
    print(f"  Calmar     : {cal:.2f}")
    print("  Data       : %d bars, %.0f trading days, %.2f years active" % (n_bars, active_trading_days, years))
    print()
    print("  PHASE 3 TARGET CHECK:")
    print("    Trades >= 200/year   : {} (~{:.0f}/yr)".format("PASS" if trades_per_year >= 200 else "MISS", trades_per_year))
    print("    Sharpe >= 1.5        : {} ({:.2f})".format("PASS" if sh >= 1.5 else "MISS", sh))
    print("    Sharpe >= 2.0 (str.) : {} ({:.2f})".format("PASS" if sh >= 2.0 else "MISS", sh))
    print("    PF     >= 2.5        : {} ({:.2f})".format("PASS" if pf >= 2.5 else "MISS", pf))
    print("    WR     >= 50%       : {} ({:.1f}%)".format("PASS" if wr >= 50.0 else "MISS", wr))
    print("    MaxDD  > -8%        : {} ({:.2f}%)".format("PASS" if dd > -8.0 else "MISS", dd))
    print()
    print("  vs v39 BASELINE (2.5x daily, 3yr):")
    print(f"    Return : {ret:+.2f}%  (v39: +42.55%)")
    print(f"    Sharpe : {sh:.2f}   (v39: 1.82)")
    print(f"    WR     : {wr:.1f}%  (v39: 65.2%)")
    print(f"    Trades : {trades_per_year:.0f}/yr  (v39: ~8/yr)")
    print(f"    MaxDD  : {dd:.2f}%  (v39: -2.69%)")
    print()

    phase3_pass = trades_per_year >= 200 and sh >= 1.5 and dd > -8.0
    if phase3_pass:
        print("  >>> Phase 3 PASS: Real 1-hour intraday validated <<<")
        print("       -> Proceed to Phase 4: ML signal combiner walk-forward")
    else:
        print("  >>> Phase 3 PARTIAL: check misses above <<<")
        if sh > 0 and trades_per_year < 200:
            print("       -> Trade freq: try entry_z=1.2, pair_rediscovery=3 bars")
        if sh < 0:
            print("       -> Sharpe negative: z-score thresholds need recalibration")
            print("          Try: entry_z=2.0, exit_z=0.4, z_stop=2.8 (wider = fewer false signals)")
        print("       -> If still failing: daily+high-frequency signals hybrid approach")
    print()


if __name__ == "__main__":
    main()
