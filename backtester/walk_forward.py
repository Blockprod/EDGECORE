"""
Walk-Forward Engine ÔÇö Time-series cross-validation harness.

Wraps :class:`backtests.walk_forward.WalkForwardBacktester` and
:func:`backtests.walk_forward.split_walk_forward` behind a clean API.

Walk-forward validation prevents overfitting by:
    1. Splitting data into expanding train + fixed OOS test windows
    2. Re-discovering pairs on each training window (no look-ahead)
    3. Running a fresh strategy instance on the OOS test window
    4. Aggregating per-period results into a final verdict
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from structlog import get_logger

from backtests.walk_forward import WalkForwardBacktester, split_walk_forward

logger = get_logger(__name__)


@dataclass
class WalkForwardConfig:
    """Configuration for walk-forward validation."""

    symbols: list[str] = field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    num_periods: int = 4
    oos_ratio: float = 0.20
    use_synthetic: bool = False
    validate_pairs_oos: bool = True
    oos_validation_split: float = 0.80


@dataclass
class WalkForwardResult:
    """Structured walk-forward validation result."""

    per_period: list[dict[str, Any]]
    aggregate: dict[str, Any]
    config: WalkForwardConfig
    num_periods_executed: int = 0
    passed: bool = False

    @property
    def avg_sharpe(self) -> float:
        sharpes = [p.get("sharpe_ratio", 0) for p in self.per_period]
        return float(pd.Series(sharpes).mean()) if sharpes else 0.0

    @property
    def avg_return(self) -> float:
        returns = [p.get("total_return", 0) for p in self.per_period]
        return float(pd.Series(returns).mean()) if returns else 0.0


class WalkForwardEngine:
    """
    Walk-forward cross-validation engine.

    Usage::

        engine = WalkForwardEngine()
        result = engine.run(WalkForwardConfig(
            symbols=["AAPL", "MSFT", "GOOGL"],
            start_date="2020-01-01",
            end_date="2023-12-31",
            num_periods=6,
        ))
        if result.passed:
            print("Strategy validates OOS!")
    """

    def __init__(self):
        self._backtester = WalkForwardBacktester()

    def run(self, config: WalkForwardConfig) -> WalkForwardResult:
        """
        Execute full walk-forward validation.

        Args:
            config: Walk-forward configuration.

        Returns:
            WalkForwardResult with per-period breakdown and aggregate verdict.
        """
        logger.info(
            "walk_forward_engine_start",
            symbols=config.symbols[:5],
            periods=config.num_periods,
            oos_ratio=config.oos_ratio,
        )

        raw = self._backtester.run_walk_forward(
            symbols=config.symbols,
            start_date=config.start_date,
            end_date=config.end_date,
            num_periods=config.num_periods,
            oos_ratio=config.oos_ratio,
            use_synthetic=config.use_synthetic,
            validate_pairs_oos=config.validate_pairs_oos,
            oos_validation_split=config.oos_validation_split,
        )

        per_period = raw.get("per_period_metrics", [])
        aggregate = raw.get("aggregate_metrics", {})

        # Determine pass/fail: at least 50% of periods must be profitable
        profitable_periods = sum(1 for p in per_period if p.get("total_return", 0) > 0)
        passed = len(per_period) > 0 and (profitable_periods / len(per_period)) >= 0.50

        result = WalkForwardResult(
            per_period=per_period,
            aggregate=aggregate,
            config=config,
            num_periods_executed=len(per_period),
            passed=passed,
        )

        logger.info(
            "walk_forward_engine_complete",
            periods_executed=result.num_periods_executed,
            avg_sharpe=round(result.avg_sharpe, 3),
            avg_return=round(result.avg_return, 4),
            passed=result.passed,
        )

        return result

    @staticmethod
    def create_splits(
        data: pd.DataFrame,
        num_periods: int = 4,
        oos_ratio: float = 0.20,
    ):
        """
        Create train/test splits without running backtests.

        Useful for inspection or custom validation logic.

        Returns:
            List of (train_df, test_df) tuples.
        """
        return split_walk_forward(data, num_periods=num_periods, oos_ratio=oos_ratio)
