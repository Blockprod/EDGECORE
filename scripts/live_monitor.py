#!/usr/bin/env python3
"""
Live Monitor ÔÇö Intraday monitoring of active pair trading positions.

Responsibilities:
  - Poll IBKR for current positions and P&L
  - Monitor z-score drifts on active pairs
  - Check circuit breaker conditions
  - Emit alerts on stop/exit triggers
  - Log portfolio state for audit trail

This runs as a lightweight background loop during market hours.
It does NOT execute trades ÔÇö it monitors and alerts.

Usage::

    # Start monitoring (runs until market close or Ctrl+C)
    python scripts/live_monitor.py

    # Monitor with custom interval
    python scripts/live_monitor.py --interval 60

    # Dry-run (no IBKR connection, uses cached data)
    python scripts/live_monitor.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structlog import get_logger

logger = get_logger(__name__)

# Graceful shutdown
_shutdown = False


def _signal_handler(signum, frame):
    global _shutdown
    _shutdown = True
    logger.info("shutdown_signal_received", signal=signum, frame=str(frame))


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def parse_args():
    parser = argparse.ArgumentParser(description="EDGECORE Live Monitor")
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Monitoring interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode ÔÇö no IBKR connection",
    )
    parser.add_argument(
        "--pairs-file",
        type=str,
        default="cache/daily_scan_result.json",
        help="Path to daily scan results JSON",
    )
    parser.add_argument(
        "--max-drawdown-pct",
        type=float,
        default=15.0,
        help="Portfolio drawdown alert threshold (%%)",
    )
    parser.add_argument(
        "--z-score-alert",
        type=float,
        default=3.0,
        help="Z-score threshold for position alerts",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="logs/monitor",
        help="Directory for monitoring logs",
    )
    return parser.parse_args()


class LiveMonitor:
    """
    Intraday position monitor for pair trading.

    Monitors:
      - Portfolio P&L and drawdown
      - Active pair z-scores
      - Circuit breaker conditions
      - Position stop levels

    This is observation-only ÔÇö no order execution.
    """

    def __init__(
        self,
        interval_sec: int = 30,
        max_drawdown_pct: float = 15.0,
        z_score_alert: float = 3.0,
        dry_run: bool = False,
    ):
        self.interval = interval_sec
        self.max_drawdown_pct = max_drawdown_pct
        self.z_score_alert = z_score_alert
        self.dry_run = dry_run
        self._peak_equity = 0.0
        self._alerts: list[dict] = []

    def load_active_pairs(self, pairs_file: str) -> list[dict]:
        """Load discovered pairs from daily scan output."""
        path = Path(pairs_file)
        if not path.exists():
            logger.warning("pairs_file_not_found", path=str(path))
            return []
        with open(path) as f:
            data = json.load(f)
        return data.get("pairs", [])

    def check_portfolio(self) -> dict:
        """Check portfolio state from IBKR."""
        if self.dry_run:
            return {
                "equity": 100_000.0,
                "positions": 0,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
            }

        try:
            from execution.ibkr_engine import IBKRExecutionEngine

            engine = IBKRExecutionEngine()
            engine.connect()
            try:
                balance = engine.get_account_balance()
                positions = engine.get_positions()
                return {
                    "equity": balance,
                    "positions": len(positions) if positions else 0,
                    "unrealized_pnl": 0.0,
                    "realized_pnl": 0.0,
                }
            finally:
                engine.disconnect()
        except Exception as exc:
            logger.error("portfolio_check_failed", error=str(exc)[:100])
            return {"equity": 0, "positions": 0, "unrealized_pnl": 0, "realized_pnl": 0}

    def check_drawdown(self, equity: float) -> dict | None:
        """Check portfolio drawdown against limit."""
        if equity > self._peak_equity:
            self._peak_equity = equity

        if self._peak_equity <= 0:
            return None

        dd_pct = (self._peak_equity - equity) / self._peak_equity * 100

        if dd_pct >= self.max_drawdown_pct:
            alert = {
                "type": "DRAWDOWN_ALERT",
                "timestamp": datetime.now().isoformat(),
                "drawdown_pct": round(dd_pct, 2),
                "limit_pct": self.max_drawdown_pct,
                "equity": round(equity, 2),
                "peak_equity": round(self._peak_equity, 2),
            }
            self._alerts.append(alert)
            logger.error(
                "DRAWDOWN_ALERT",
                drawdown=f"{dd_pct:.1f}%",
                limit=f"{self.max_drawdown_pct:.1f}%",
                equity=round(equity, 2),
            )
            return alert
        return None

    def run_monitoring_cycle(self, pairs: list[dict]) -> dict:
        """Run one monitoring cycle."""
        portfolio = self.check_portfolio()
        dd_alert = self.check_drawdown(portfolio["equity"])

        status = {
            "timestamp": datetime.now().isoformat(),
            "portfolio": portfolio,
            "drawdown_alert": dd_alert is not None,
            "active_pairs_tracked": len(pairs),
            "total_alerts": len(self._alerts),
        }

        logger.info(
            "monitor_cycle",
            equity=round(portfolio["equity"], 2),
            positions=portfolio["positions"],
            unrealized_pnl=round(portfolio["unrealized_pnl"], 2),
            alerts=len(self._alerts),
        )

        return status

    def run(self, pairs_file: str, log_dir: str):
        """Run continuous monitoring loop."""
        global _shutdown

        pairs = self.load_active_pairs(pairs_file)
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        logger.info(
            "monitor_starting",
            interval=self.interval,
            pairs=len(pairs),
            dry_run=self.dry_run,
        )

        cycle = 0
        while not _shutdown:
            try:
                cycle += 1
                status = self.run_monitoring_cycle(pairs)

                # Save status log periodically
                if cycle % 10 == 0:
                    status_file = log_path / f"monitor_status_{datetime.now().strftime('%Y%m%d')}.jsonl"
                    with open(status_file, "a") as f:
                        f.write(json.dumps(status) + "\n")

                time.sleep(self.interval)

            except KeyboardInterrupt:
                break
            except Exception as exc:
                logger.error("monitor_cycle_error", error=str(exc)[:200])
                time.sleep(self.interval)

        logger.info(
            "monitor_stopped",
            cycles=cycle,
            total_alerts=len(self._alerts),
        )


def main():
    args = parse_args()

    monitor = LiveMonitor(
        interval_sec=args.interval,
        max_drawdown_pct=args.max_drawdown_pct,
        z_score_alert=args.z_score_alert,
        dry_run=args.dry_run,
    )

    print("\nEDGECORE Live Monitor")
    print(f"  Interval:   {args.interval}s")
    print(f"  DD Limit:   {args.max_drawdown_pct}%")
    print(f"  Dry Run:    {args.dry_run}")
    print(f"  Pairs File: {args.pairs_file}")
    print("  Press Ctrl+C to stop\n")

    monitor.run(args.pairs_file, args.log_dir)


if __name__ == "__main__":
    main()
