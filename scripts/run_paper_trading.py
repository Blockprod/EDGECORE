#!/usr/bin/env python
"""EDGECORE Paper Trading ÔÇö v22 Optimized Parameters.

Launches a paper trading session using the validated v22 configuration:
    - entry_z_score = 1.5 (more entries vs default 2.0)
    - exit_z_score  = 0.3 (let winners run)
    - fdr_q_level   = 0.20 (relaxed FDR filter)
    - allocation    = 90% per pair (high conviction)
    - max_portfolio_heat = 4.0 (up to 4 concurrent positions)

Connects to IB Gateway on port 4002 (paper account).
Runs daily bars ÔÇö pair rediscovery every 24h.
Displays premium Rich dashboard with real-time metrics.

Usage:
    python run_paper_trading.py                      # defaults
    python run_paper_trading.py --capital 50000       # custom capital
    python run_paper_trading.py --interval 86400      # daily ticks (24h)

Press Ctrl+C to stop gracefully (closes all positions).
"""

import argparse
import logging
import sys
import os
import time
import signal
import threading
from datetime import datetime

_script_log = logging.getLogger(__name__)

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ÔöÇÔöÇ Universe (same 31 symbols as backtest v22) ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

SYMBOLS = [
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
]

SECTOR_MAP = {
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
}


def main():
    parser = argparse.ArgumentParser(description="EDGECORE Paper Trading (v22)")
    parser.add_argument("--capital", type=float, default=100_000, help="Starting virtual capital (EUR)")
    parser.add_argument("--interval", type=int, default=86400, help="Bar interval in seconds (86400 = daily)")
    parser.add_argument("--rediscovery", type=int, default=24, help="Pair rediscovery interval in hours")
    parser.add_argument("--alloc", type=float, default=90.0, help="Allocation per pair (%% of capital)")
    parser.add_argument("--heat", type=float, default=4.0, help="Max portfolio heat (concurrent notional / capital)")
    parser.add_argument("--max-positions", type=int, default=4, help="Max concurrent pair positions")
    args = parser.parse_args()

    # ÔöÇÔöÇ 1. Set v22 strategy parameters in settings singleton ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    from config.settings import get_settings

    settings = get_settings()
    strat = settings.strategy

    # Core v22 parameters (validated in backtest: 62.44% return, 0.85 Sharpe)
    strat.entry_z_score = 1.5
    strat.exit_z_score = 0.3
    strat.z_score_stop = 3.5
    strat.lookback_window = 252
    strat.additional_lookback_windows = [126]
    strat.min_correlation = 0.50
    strat.max_half_life = 120
    strat.internal_max_drawdown_pct = 0.25

    # FDR configuration
    strat.fdr_q_level = 0.20

    # Ensure paper mode
    settings.execution.use_sandbox = True

    # ÔöÇÔöÇ 2. Configure and launch paper trading runner ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    from live_trading.runner import TradingLoopConfig
    from live_trading.paper_runner import PaperTradingRunner

    config = TradingLoopConfig(
        symbols=SYMBOLS,
        sector_map=SECTOR_MAP,
        bar_interval_seconds=args.interval,
        pair_rediscovery_hours=args.rediscovery,
        max_positions=args.max_positions,
        initial_capital=args.capital,
        allocation_per_pair_pct=args.alloc,
        max_portfolio_heat=args.heat,
        mode="paper",
    )

    # ÔöÇÔöÇ 3. Print configuration banner ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    n_intra = sum(
        1 for i, s1 in enumerate(SYMBOLS) for s2 in SYMBOLS[i + 1 :] if SECTOR_MAP.get(s1) == SECTOR_MAP.get(s2)
    )

    print("=" * 60)
    print("  EDGECORE PAPER TRADING ÔÇö v22 Configuration")
    print("=" * 60)
    print(f"  Capital:      {args.capital:,.0f} EUR (paper)")
    print(f"  Symbols:      {len(SYMBOLS)} across 6 sectors")
    print(f"  Pairs pool:   {n_intra} intra-sector candidates")
    print(f"  Bar interval: {args.interval}s ({args.interval // 3600}h)")
    print(f"  Rediscovery:  every {args.rediscovery}h")
    print(f"  Allocation:   {args.alloc}% per pair")
    print(f"  Heat limit:   {args.heat:.0f}x ({args.heat * 100:.0f}%)")
    print(f"  Max pos:      {args.max_positions}")
    print(f"  Z-score:      entry={strat.entry_z_score}, exit={strat.exit_z_score}, stop={strat.z_score_stop}")
    print(f"  Correlation:  min={strat.min_correlation}")
    print(f"  Half-life:    max={strat.max_half_life}")
    print(f"  FDR q-level:  {strat.fdr_q_level}")
    print("  IB Gateway:   127.0.0.1:4002 (paper)")
    print("=" * 60)
    print()
    print("[EDGECORE] Starting paper trading... Press Ctrl+C to stop.")
    print()

    # ÔöÇÔöÇ 4. Launch with premium Rich dashboard ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    from rich.console import Console
    from rich.live import Live
    from monitoring.rich_dashboard import build_dashboard

    runner = PaperTradingRunner(config)
    _rich_console = Console(highlight=False)

    # Ctrl+C handler for Windows compatibility
    _stop_event = threading.Event()

    def _sigint_handler(sig, frame):
        _script_log.debug("sigint_received sig=%s frame=%s", sig, frame)
        _stop_event.set()

    signal.signal(signal.SIGINT, _sigint_handler)

    tick_count = 0
    start = datetime.now()
    tick_elapsed = 0.0

    with Live(
        build_dashboard(
            runner,
            tick_count=0,
            tick_elapsed=0,
            start_time=start,
            interval=args.interval,
            status="INITIALIZING",
            sector_map=SECTOR_MAP,
        ),
        console=_rich_console,
        screen=True,
        auto_refresh=False,
        transient=False,
    ) as live:
        while not _stop_event.is_set():
            tick_count += 1
            tick_start = datetime.now()

            # Update dashboard: COMPUTING state
            live.update(
                build_dashboard(
                    runner,
                    tick_count=tick_count,
                    tick_elapsed=tick_elapsed,
                    start_time=start,
                    interval=args.interval,
                    status="COMPUTING",
                    sector_map=SECTOR_MAP,
                )
            )
            live.refresh()

            # Execute one tick
            runner._tick()
            tick_elapsed = (datetime.now() - tick_start).total_seconds()

            # Countdown with real-time dashboard updates
            remaining = args.interval
            last_render = 0.0
            while remaining >= 0 and not _stop_event.is_set():
                now_t = time.monotonic()
                if now_t - last_render >= 1.0:
                    live.update(
                        build_dashboard(
                            runner,
                            tick_count=tick_count,
                            tick_elapsed=tick_elapsed,
                            start_time=start,
                            interval=args.interval,
                            status="RUNNING",
                            next_tick_in=remaining,
                            sector_map=SECTOR_MAP,
                        )
                    )
                    live.refresh()
                    last_render = now_t
                    remaining -= 1
                time.sleep(0.1)

        # Show STOPPED state briefly
        live.update(
            build_dashboard(
                runner,
                tick_count=tick_count,
                tick_elapsed=tick_elapsed,
                start_time=start,
                interval=args.interval,
                status="STOPPED",
                next_tick_in=0,
                sector_map=SECTOR_MAP,
            )
        )
        live.refresh()
        time.sleep(2)  # Show stopped message for 2 seconds

    print()


if __name__ == "__main__":
    main()
