#!/usr/bin/env python3
"""
Scheduler ÔÇö Orchestrates daily scan + live monitoring lifecycle.

This is the top-level production entry point that coordinates:
  1. Pre-market daily scan (08:00 EST)
  2. Market-hours live monitoring (09:30-16:00 EST)
  3. Post-market reporting

Scheduling modes:
  - **Standalone**: Runs in a loop with sleep-based scheduling.
    Suitable for a VPS/VM that's always running.
  - **Cron**: Designed to be called by OS scheduler (cron/Task Scheduler).
    Each invocation runs one cycle and exits.

Usage::

    # Standalone mode (runs continuously)
    python scripts/scheduler.py --mode standalone

    # Single scan cycle (for cron/Task Scheduler)
    python scripts/scheduler.py --mode cron --action scan

    # Single monitor cycle
    python scripts/scheduler.py --mode cron --action monitor

    # Full daily cycle (scan + monitor until market close)
    python scripts/scheduler.py --mode cron --action full
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structlog import get_logger

logger = get_logger(__name__)


# US market hours (Eastern Time)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0
PRE_MARKET_SCAN_HOUR = 8
PRE_MARKET_SCAN_MINUTE = 0


def parse_args():
    parser = argparse.ArgumentParser(description="EDGECORE Scheduler")
    parser.add_argument(
        "--mode",
        choices=["standalone", "cron"],
        default="cron",
        help="Scheduling mode",
    )
    parser.add_argument(
        "--action",
        choices=["scan", "monitor", "full"],
        default="full",
        help="Action to execute (cron mode only)",
    )
    parser.add_argument(
        "--sec-only",
        action="store_true",
        help="SEC-only scan (no IBKR validation)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no IBKR connection for monitoring)",
    )
    parser.add_argument(
        "--monitor-interval",
        type=int,
        default=30,
        help="Monitoring poll interval in seconds",
    )
    parser.add_argument(
        "--python",
        type=str,
        default=sys.executable,
        help="Python interpreter path",
    )
    return parser.parse_args()


def is_market_day() -> bool:
    """Check if today is a US market trading day (Mon-Fri, no holidays)."""
    now = datetime.now()
    # Weekday check (0=Mon, 4=Fri)
    if now.weekday() >= 5:
        return False
    # Note: For production, integrate with NYSE holiday calendar
    # (e.g. pandas_market_calendars or hardcoded list)
    return True


def is_market_hours() -> bool:
    """Check if current time is within US market hours."""
    now = datetime.now()
    market_open = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)
    market_close = now.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0)
    return market_open <= now <= market_close


def run_daily_scan(python: str, sec_only: bool = False) -> bool:
    """Execute daily_scan.py as a subprocess."""
    script = str(Path(__file__).parent / "daily_scan.py")
    cmd = [python, script, "--use-cache"]
    if sec_only:
        cmd.append("--sec-only")

    logger.info("running_daily_scan", cmd=" ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,
        )
        if result.returncode == 0:
            logger.info("daily_scan_completed_successfully")
            if result.stdout:
                # Print last few lines of output
                lines = result.stdout.strip().split("\n")
                for line in lines[-10:]:
                    print(f"  [scan] {line}")
            return True
        else:
            logger.error(
                "daily_scan_failed",
                returncode=result.returncode,
                stderr=result.stderr[:500] if result.stderr else "",
            )
            return False
    except subprocess.TimeoutExpired:
        logger.error("daily_scan_timeout", timeout=3600)
        return False
    except Exception as exc:
        logger.error("daily_scan_error", error=str(exc)[:200])
        return False


def run_live_monitor(
    python: str,
    interval: int,
    dry_run: bool = False,
) -> None:
    """Execute live_monitor.py as a subprocess (blocks until market close)."""
    script = str(Path(__file__).parent / "live_monitor.py")
    cmd = [python, script, "--interval", str(interval)]
    if dry_run:
        cmd.append("--dry-run")

    logger.info("starting_live_monitor", cmd=" ".join(cmd))

    try:
        process = subprocess.Popen(cmd)
        # Wait until market close or process ends
        while is_market_hours() and process.poll() is None:
            time.sleep(60)
        if process.poll() is None:
            logger.info("market_closed_stopping_monitor")
            process.terminate()
            process.wait(timeout=10)
    except Exception as exc:
        logger.error("monitor_error", error=str(exc)[:200])


def run_cron_action(args):
    """Execute a single action in cron mode."""
    if args.action == "scan":
        success = run_daily_scan(args.python, args.sec_only)
        sys.exit(0 if success else 1)

    elif args.action == "monitor":
        if not is_market_hours():
            logger.info("market_closed_skipping_monitor")
            return
        run_live_monitor(args.python, args.monitor_interval, args.dry_run)

    elif args.action == "full":
        # Full cycle: scan then monitor
        logger.info("full_cycle_starting")
        scan_ok = run_daily_scan(args.python, args.sec_only)
        if not scan_ok:
            logger.warning("scan_failed_continuing_with_cached_pairs")

        if is_market_hours():
            run_live_monitor(args.python, args.monitor_interval, args.dry_run)
        else:
            logger.info("market_not_open_skipping_monitor")


def run_standalone(args):
    """Run continuous scheduling loop."""
    logger.info("standalone_scheduler_starting")

    while True:
        try:
            if not is_market_day():
                logger.info("weekend_sleeping_until_monday")
                # Sleep until next weekday
                now = datetime.now()
                days_until_monday = (7 - now.weekday()) % 7
                if days_until_monday == 0:
                    days_until_monday = 7
                next_monday = now.replace(
                    hour=PRE_MARKET_SCAN_HOUR,
                    minute=0,
                    second=0,
                ) + timedelta(days=days_until_monday)
                sleep_sec = (next_monday - now).total_seconds()
                time.sleep(max(60, sleep_sec))
                continue

            now = datetime.now()
            pre_market = now.replace(
                hour=PRE_MARKET_SCAN_HOUR,
                minute=PRE_MARKET_SCAN_MINUTE,
            )
            market_close = now.replace(
                hour=MARKET_CLOSE_HOUR,
                minute=MARKET_CLOSE_MINUTE,
            )

            # Pre-market scan
            if now < pre_market:
                sleep_sec = (pre_market - now).total_seconds()
                logger.info("waiting_for_pre_market", sleep_minutes=round(sleep_sec / 60, 1))
                time.sleep(max(60, sleep_sec))
                continue

            _rs: Any = run_standalone
            if not hasattr(_rs, "_scanned_today"):
                _rs._scanned_today = None

            if _rs._scanned_today != now.date():
                logger.info("running_pre_market_scan")
                run_daily_scan(args.python, args.sec_only)
                _rs._scanned_today = now.date()

            # Market hours monitoring
            if is_market_hours():
                run_live_monitor(args.python, args.monitor_interval, args.dry_run)

            # Post-market: sleep until next pre-market
            if now > market_close:
                tomorrow_pre = pre_market + timedelta(days=1)
                sleep_sec = (tomorrow_pre - now).total_seconds()
                logger.info(
                    "post_market_sleeping",
                    until=tomorrow_pre.isoformat(),
                    hours=round(sleep_sec / 3600, 1),
                )
                time.sleep(max(60, sleep_sec))

        except KeyboardInterrupt:
            logger.info("scheduler_stopped_by_user")
            break
        except Exception as exc:
            logger.error("scheduler_error", error=str(exc)[:200])
            time.sleep(300)  # 5 min backoff on error


def main():
    args = parse_args()

    print("\nEDGECORE Scheduler")
    print(f"  Mode:     {args.mode}")
    print(f"  Action:   {args.action}")
    print(f"  SEC Only: {args.sec_only}")
    print(f"  Dry Run:  {args.dry_run}")
    print()

    if args.mode == "cron":
        run_cron_action(args)
    else:
        run_standalone(args)


if __name__ == "__main__":
    main()
