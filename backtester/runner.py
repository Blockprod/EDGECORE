"""
Backtest Engine ÔÇö Clean orchestrator over the proven StrategyBacktestSimulator.

Composes:
    - backtests.runner.BacktestRunner          (legacy + unified paths)
    - backtests.strategy_simulator             (bar-by-bar simulator)
    - backtests.metrics.BacktestMetrics        (result aggregation)

The BacktestEngine provides a high-level interface that:
    1. Loads or receives market data
    2. Runs the bar-by-bar simulator with configurable parameters
    3. Returns typed BacktestResult with full diagnostics
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from structlog import get_logger

from backtests.runner import BacktestRunner
from backtests.metrics import BacktestMetrics

logger = get_logger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for a single backtest run."""
    symbols: List[str] = field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    initial_capital: float = 100_000.0
    commission_bps: float = 5.0
    slippage_bps: float = 2.0
    use_synthetic: bool = False
    validate_data: bool = True
    pair_rediscovery_interval: int = 5


@dataclass
class BacktestResult:
    """Structured backtest result."""
    metrics: BacktestMetrics
    config: BacktestConfig
    run_time_seconds: float = 0.0
    run_timestamp: datetime = field(default_factory=datetime.now)

    # Convenience accessors for key metrics
    @property
    def total_return(self) -> float:
        return getattr(self.metrics, "total_return", 0.0)

    @property
    def sharpe_ratio(self) -> float:
        return getattr(self.metrics, "sharpe_ratio", 0.0)

    @property
    def max_drawdown(self) -> float:
        return getattr(self.metrics, "max_drawdown", 0.0)

    @property
    def win_rate(self) -> float:
        return getattr(self.metrics, "win_rate", 0.0)

    @property
    def total_trades(self) -> int:
        return getattr(self.metrics, "total_trades", 0)

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict for logging / display."""
        return {
            "total_return": self.total_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "total_trades": self.total_trades,
            "run_time_s": round(self.run_time_seconds, 2),
        }


class BacktestEngine:
    """
    High-level backtest orchestrator.

    Wraps :class:`backtests.runner.BacktestRunner` with a cleaner interface
    and returns typed :class:`BacktestResult` objects.

    Usage::

        engine = BacktestEngine()
        result = engine.run(BacktestConfig(
            symbols=["AAPL", "MSFT"],
            start_date="2022-01-01",
            end_date="2023-12-31",
        ))
        print(result.summary())
    """

    def __init__(self):
        self._runner = BacktestRunner()

    def run(self, config: BacktestConfig) -> BacktestResult:
        """
        Execute a full backtest.

        Args:
            config: Backtest configuration.

        Returns:
            Typed BacktestResult with metrics and diagnostics.
        """
        import time

        start = time.monotonic()

        logger.info(
            "backtest_engine_run_start",
            symbols=config.symbols[:5],
            start_date=config.start_date,
            end_date=config.end_date,
        )

        metrics = self._runner.run_unified(
            symbols=config.symbols,
            start_date=config.start_date,
            end_date=config.end_date,
            validate_data=config.validate_data,
            use_synthetic=config.use_synthetic,
            pair_rediscovery_interval=config.pair_rediscovery_interval,
        )

        elapsed = time.monotonic() - start

        result = BacktestResult(
            metrics=metrics,
            config=config,
            run_time_seconds=elapsed,
        )

        logger.info("backtest_engine_run_complete", **result.summary())

        return result

    def run_batch(
        self,
        configs: List[BacktestConfig],
    ) -> List[BacktestResult]:
        """
        Run multiple backtests sequentially.

        Useful for parameter sweeps or multi-period analysis.

        Args:
            configs: List of backtest configurations.

        Returns:
            List of BacktestResult objects.
        """
        results = []
        for i, cfg in enumerate(configs, 1):
            logger.info("batch_backtest_run", run=i, total=len(configs))
            results.append(self.run(cfg))
        return results
