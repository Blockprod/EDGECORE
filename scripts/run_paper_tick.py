#!/usr/bin/env python
"""EDGECORE Paper Trading ÔÇö Single Tick or Continuous Loop with Dashboard.

Two modes:
  1. Single tick (default):  Execute ONE tick then exit.
     Designed for Windows Task Scheduler (daily at 16:05 EST).
  2. Continuous (--continuous): Loop indefinitely with a live dashboard.
     All verbose logs go to file only; console shows a clean dashboard.

Each tick:
  1. Connects to IB Gateway (port 4002)
  2. Loads latest daily prices for 31 symbols
  3. Discovers cointegrated pairs (BH-FDR per sector)
  4. Generates z-score signals
  5. Executes paper trades (simulated fills)
  6. Logs everything to logs/edgecore_paper_YYYYMMDD.log

Usage:
    python run_paper_tick.py                 # single tick, default params
    python run_paper_tick.py --continuous     # continuous loop (Ctrl+C to stop)
    python run_paper_tick.py --continuous --interval 3600   # loop every hour
    pythonw -B run_paper_tick.py             # silent (Task Scheduler)
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Detect continuous mode early (before logging setup)
CONTINUOUS_MODE = "--continuous" in sys.argv

# Load .env variables (SMTP, Slack, IBKR, etc.)
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass  # python-dotenv not installed ÔÇö rely on system env vars

# ÔöÇÔöÇ Logging to file ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"edgecore_paper_{datetime.now():%Y%m%d}.log"

# In continuous mode: file-only logging (dashboard replaces console output)
# In single-tick mode: file + console logging
_handlers: list[logging.Handler] = [logging.FileHandler(log_file, encoding="utf-8")]
if not CONTINUOUS_MODE:
    _handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s ÔÇö %(message)s",
    handlers=_handlers,
)
log = logging.getLogger("edgecore.paper")

# Suppress structlog console output in continuous mode
if CONTINUOUS_MODE:
    import structlog

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    # Route all structlog output through the file-only root logger
    for handler in logging.root.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            logging.root.removeHandler(handler)

    # Silence ibapi loggers (they add their own StreamHandlers)
    for _name in ("ibapi", "ibapi.client", "ibapi.wrapper", "ibapi.utils"):
        _iblog = logging.getLogger(_name)
        _iblog.handlers = [h for h in _iblog.handlers if isinstance(h, logging.FileHandler)]
        _iblog.propagate = True  # let root file handler catch them
        _iblog.setLevel(logging.WARNING)  # suppress verbose REQUEST/ANSWER noise


# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ
# Rich Dashboard ÔÇö Premium Terminal UI
# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich import box

_rich_console = Console(highlight=False)

# Import dashboard builder from dedicated module
from monitoring.rich_dashboard import build_dashboard, format_duration

# Color aliases for shutdown message
_C_ACCENT = "#6366F1"
_C_DIM = "#64748B"
_C_RED = "#EF4444"


def _get_entry_z() -> float:
    """Get current entry z-score threshold."""
    try:
        from config.settings import get_settings

        return getattr(get_settings().strategy, "entry_z_score", 2.0)
    except Exception:
        return 1.5


def _render_shutdown(tick_count: int, start_time: datetime) -> None:
    """Print a clean shutdown summary using Rich."""
    total = (datetime.now() - start_time).total_seconds()
    t = Table.grid(padding=(0, 2))
    t.add_column(style=_C_DIM)
    t.add_column(style=_C_ACCENT)
    t.add_row("Ticks completed", f"[bold {_C_ACCENT}]{tick_count}[/bold {_C_ACCENT}]")
    t.add_row("Total uptime", f"[bold {_C_ACCENT}]{format_duration(total)}[/bold {_C_ACCENT}]")
    t.add_row("Log file", f"[{_C_DIM}]{log_file}[/{_C_DIM}]")
    _rich_console.print()
    _rich_console.print(
        Panel(
            t,
            title=f"[bold {_C_RED}]Ôûá  EDGECORE ÔÇö Paper Trading Stopped[/bold {_C_RED}]",
            border_style=_C_RED,
            box=box.ROUNDED,
            padding=(1, 3),
        )
    )
    _rich_console.print()


# ÔöÇÔöÇ Universe (same 31 symbols as backtest v22) ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
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


def main() -> int:
    """Execute one paper trading tick. Returns 0 on success, 1 on error."""
    start = datetime.now()
    log.info("=" * 60)
    log.info("EDGECORE Paper Trading ÔÇö Tick started at %s", start.isoformat())
    log.info("=" * 60)

    # ÔöÇÔöÇ Initialise alerters from environment variables ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    email_alerter = None
    slack_alerter = None
    try:
        from monitoring.email_alerter import EmailAlerter

        email_alerter = EmailAlerter.from_env()
        if email_alerter:
            email_alerter.trading_mode = "paper"
            log.info("Email alerter initialised (%d recipients) ÔÇö mode: paper", len(email_alerter.recipients))
        else:
            log.info("Email alerter not configured (set EMAIL_SMTP_* env vars)")
    except Exception as exc:
        log.warning("Email alerter init failed: %s", exc)

    try:
        from monitoring.slack_alerter import SlackAlerter

        slack_alerter = SlackAlerter(webhook_url=os.getenv("SLACK_WEBHOOK_URL"))
        if slack_alerter.enabled:
            log.info("Slack alerter initialised")
        else:
            log.info("Slack alerter not configured (set SLACK_WEBHOOK_URL env var)")
            slack_alerter = None  # don't pass a disabled stub
    except Exception as exc:
        log.warning("Slack alerter init failed: %s", exc)

    try:
        # ÔöÇÔöÇ 1. Set v22 strategy parameters ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        from config.settings import get_settings

        strat = get_settings().strategy
        strat.entry_z_score = 1.5
        strat.exit_z_score = 0.3
        strat.z_score_stop = 3.5
        strat.lookback_window = 252
        strat.additional_lookback_windows = [126]
        strat.min_correlation = 0.50
        strat.max_half_life = 120
        strat.internal_max_drawdown_pct = 0.25
        strat.fdr_q_level = 0.20
        get_settings().execution.use_sandbox = True

        log.info(
            "Strategy params: entry_z=%.1f exit_z=%.1f fdr_q=%.2f corr=%.2f hl=%d",
            strat.entry_z_score,
            strat.exit_z_score,
            strat.fdr_q_level,
            strat.min_correlation,
            strat.max_half_life,
        )

        # ÔöÇÔöÇ 2. Initialize paper trading runner ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        from live_trading.runner import TradingLoopConfig
        from live_trading.paper_runner import PaperTradingRunner

        config = TradingLoopConfig(
            symbols=SYMBOLS,
            sector_map=SECTOR_MAP,
            bar_interval_seconds=86400,  # not used in single-tick
            pair_rediscovery_hours=0,  # force rediscovery every tick
            max_positions=4,
            initial_capital=100_000.0,
            allocation_per_pair_pct=90.0,
            max_portfolio_heat=4.0,
            mode="paper",
        )

        runner = PaperTradingRunner(
            config,
            email_alerter=email_alerter,
            slack_alerter=slack_alerter,
        )
        log.info("Initializing modules...")
        runner._initialize()
        log.info("Modules initialized OK")

        # ÔöÇÔöÇ 3. Execute tick(s) ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        continuous = "--continuous" in sys.argv
        interval = 86400  # default 24h for daily strategy
        if "--interval" in sys.argv:
            try:
                idx = sys.argv.index("--interval")
                interval = int(sys.argv[idx + 1])
            except (IndexError, ValueError):
                log.warning("Invalid --interval value, using default %d", interval)

        if continuous:
            log.info("CONTINUOUS MODE ÔÇö interval=%ds (Ctrl+C to stop)", interval)
            import time
            import signal
            import threading

            tick_count = 0
            tick_elapsed = 0.0

            # ÔöÇÔöÇ Reliable Ctrl+C on Windows ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
            # Rich Live + screen=True modifies console mode and swallows
            # SIGINT before it reaches except KeyboardInterrupt.
            # Solution: register a signal handler that sets an event,
            # then poll that event every 0.1 s in the countdown loop.
            _stop_event = threading.Event()

            def _sigint_handler(sig, frame):
                log.debug("sigint_received sig=%s frame=%s", sig, frame)
                _stop_event.set()

            signal.signal(signal.SIGINT, _sigint_handler)

            with Live(
                build_dashboard(
                    runner,
                    tick_count=0,
                    tick_elapsed=0,
                    start_time=start,
                    interval=interval,
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
                    log.info("Tick #%d starting at %s", tick_count, tick_start.isoformat())

                    live.update(
                        build_dashboard(
                            runner,
                            tick_count=tick_count,
                            tick_elapsed=tick_elapsed,
                            start_time=start,
                            interval=interval,
                            status="COMPUTING",
                            sector_map=SECTOR_MAP,
                        )
                    )
                    live.refresh()

                    runner._tick()
                    tick_elapsed = (datetime.now() - tick_start).total_seconds()
                    log.info(
                        "Tick #%d completed in %.1fs ÔÇö pairs=%d positions=%d",
                        tick_count,
                        tick_elapsed,
                        len(runner._active_pairs),
                        len(runner._positions),
                    )

                    # ÔöÇÔöÇ Countdown ÔÇö poll stop event every 0.1 s ÔöÇÔöÇÔöÇÔöÇÔöÇ
                    remaining = interval
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
                                    interval=interval,
                                    status="RUNNING",
                                    next_tick_in=remaining,
                                    sector_map=SECTOR_MAP,
                                )
                            )
                            live.refresh()
                            last_render = now_t
                            remaining -= 1
                        time.sleep(0.1)

                # ÔöÇÔöÇ STOPPED state: shown for 2 s then terminal restored ÔöÇÔöÇ
                log.info("Stop signal received ÔÇö stopped after %d ticks.", tick_count)
                live.update(
                    build_dashboard(
                        runner,
                        tick_count=tick_count,
                        tick_elapsed=tick_elapsed,
                        start_time=start,
                        interval=interval,
                        status="STOPPED",
                        next_tick_in=0,
                        sector_map=SECTOR_MAP,
                    )
                )
                live.refresh()
                time.sleep(2)

            # Restore default SIGINT (raise KeyboardInterrupt) after exit
            signal.signal(signal.SIGINT, signal.default_int_handler)

            total_elapsed = (datetime.now() - start).total_seconds()
            log.info("=" * 60)
            log.info("EDGECORE ÔÇö Stopped after %d ticks (%.0fs)", tick_count, total_elapsed)
            log.info("=" * 60)
            _render_shutdown(tick_count, start)
            return 0
        else:
            # Single tick mode (Task Scheduler)
            log.info("Executing single tick...")
            runner._tick()

            elapsed = (datetime.now() - start).total_seconds()
            log.info(
                "Tick completed in %.1fs ÔÇö pairs=%d signals=%d positions=%d",
                elapsed,
                len(runner._active_pairs),
                0,  # signals count not easily accessible
                len(runner._positions),
            )

            log.info("=" * 60)
            log.info("EDGECORE Paper Trading ÔÇö Tick finished OK")
            log.info("=" * 60)
            return 0

    except Exception as exc:
        log.exception("FATAL ERROR during paper trading tick: %s", exc)
        # Send alert for fatal crash
        for alerter in (email_alerter, slack_alerter):
            if alerter:
                try:
                    alerter.send_alert(
                        level="CRITICAL",
                        title="Paper trading tick CRASHED",
                        message=f"Fatal exception: {exc}",
                        data={"traceback": str(exc)[:500]},
                    )
                except Exception:
                    pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
