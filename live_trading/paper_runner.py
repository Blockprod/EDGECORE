<<<<<<< HEAD
﻿"""
Paper Trading Runner ÔÇö Simulated live trading for dry-run validation.
=======
"""
Paper Trading Runner — Simulated live trading for dry-run validation.
>>>>>>> origin/main

Extends :class:`LiveTradingRunner` with paper-specific defaults:
    - ExecutionMode.PAPER (no real money)
    - Simulated fills with realistic cost model
    - Full audit logging for walk-forward comparison

Use this to validate the live pipeline before deploying real capital.
"""

from __future__ import annotations

<<<<<<< HEAD
from typing import Any
=======
from typing import Any, Optional
>>>>>>> origin/main

from structlog import get_logger

from live_trading.runner import LiveTradingRunner, TradingLoopConfig

logger = get_logger(__name__)


class PaperTradingRunner(LiveTradingRunner):
    """
    Paper trading variant of the live trading loop.

    Inherits all behavior from :class:`LiveTradingRunner` but forces
    ``mode="paper"`` and adds paper-specific logging.

    Usage::

        from live_trading import PaperTradingRunner

        runner = PaperTradingRunner(TradingLoopConfig(
            symbols=["AAPL", "MSFT", "GOOGL", "META"],
            bar_interval_seconds=60,
            initial_capital=100_000,
        ))
        runner.start()
    """

    def __init__(
        self,
<<<<<<< HEAD
        config: TradingLoopConfig | None = None,
        email_alerter: Any | None = None,
        slack_alerter: Any | None = None,
=======
        config: Optional[TradingLoopConfig] = None,
        email_alerter: Optional[Any] = None,
        slack_alerter: Optional[Any] = None,
>>>>>>> origin/main
    ):
        cfg = config or TradingLoopConfig()
        cfg.mode = "paper"  # force paper mode
        super().__init__(config=cfg, email_alerter=email_alerter, slack_alerter=slack_alerter)
        logger.info("paper_trading_runner_initialized")

    def _initialize(self) -> None:
        """Initialize with paper execution mode."""
        super()._initialize()
        logger.info(
            "paper_trading_ready",
            capital=self.config.initial_capital,
            symbols=len(self.config.symbols),
        )

    def _tick(self) -> None:
        """
<<<<<<< HEAD
        Paper trading tick ÔÇö identical to live but with simulated fills.
=======
        Paper trading tick — identical to live but with simulated fills.
>>>>>>> origin/main

        All signals, risk checks, and portfolio logic run identically
        to live mode. Only the execution engine differs (paper fills
        instead of IBKR fills).
        """
        super()._tick()

        # Paper-specific: log P&L snapshot every 100 ticks
        if self._iteration % 100 == 0:
            logger.info(
                "paper_trading_snapshot",
                iteration=self._iteration,
                open_positions=len(self._positions),
            )
