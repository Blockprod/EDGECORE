"""
Paper Trading Runner — Simulated live trading for dry-run validation.

Extends :class:`LiveTradingRunner` with paper-specific defaults:
    - ExecutionMode.PAPER (no real money)
    - Simulated fills with realistic cost model
    - Full audit logging for walk-forward comparison

Use this to validate the live pipeline before deploying real capital.
"""

from __future__ import annotations

from typing import Optional

from structlog import get_logger

from live_trading.runner import LiveTradingRunner, TradingLoopConfig, TradingState

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

    def __init__(self, config: Optional[TradingLoopConfig] = None):
        cfg = config or TradingLoopConfig()
        cfg.mode = "paper"  # force paper mode
        super().__init__(config=cfg)
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
        Paper trading tick — identical to live but with simulated fills.

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
