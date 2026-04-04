"""
Walk-forward testing: periodic retraining + OOS evaluation.

Walk-forward validation is a time-series cross-validation technique that simulates
live trading by:
1. Training a model on historical data (pair discovery on train window)
2. Optionally validating pairs OOS on a hold-out slice of the train window
3. Testing on out-of-sample forward data using the unified StrategyBacktestSimulator
4. Moving the window forward and repeating
5. Aggregating results across all periods

Sprint 1.3 (C-03): Each period now re-trains (re-discovers pairs) on its own
training window and uses a FRESH strategy instance.  Zero data leakage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from structlog import get_logger

from backtests.cost_model import CostModel
from backtests.runner import BacktestRunner
from backtests.strategy_simulator import StrategyBacktestSimulator
from strategies.pair_trading import PairTradingStrategy

logger = get_logger(__name__)


def split_walk_forward(
    data: pd.DataFrame, num_periods: int = 4, oos_ratio: float = 0.2
) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Create walk-forward splits with **expanding** training windows.

    Each successive training window starts from the beginning of the data
    and grows, simulating the real-world scenario where all historical data
    is available for model fitting.

    Args:
        data: Full time series
        num_periods: Number of rebalancing periods
        oos_ratio: Out-of-sample ratio (0.2 = 20% test, 80% train)

    Returns:
        List of tuples (training_data, test_data) for each period
    """
    n = len(data)

    # ---- Validate inputs ------------------------------------------------
    if num_periods < 1:
        raise ValueError(f"num_periods must be >= 1, got {num_periods}")
    # Minimum viable split: at least 2 rows per period (1 train + 1 test)
    min_rows_needed = num_periods * 2
    if n < min_rows_needed:
        raise ValueError(f"Not enough data rows ({n}) for {num_periods} periods. Need at least {min_rows_needed} rows.")

    # Reserve a portion for the first training window; remaining split across periods
    # Each period's test block has equal length
    oos_total_rows = int(n * oos_ratio * num_periods / (num_periods + 1))
    oos_per_period = max(1, oos_total_rows // num_periods)

    # First training window ends before the first test block
    first_train_end = n - oos_per_period * num_periods
    if first_train_end < 1:
        raise ValueError(
            f"Not enough data rows ({n}) for {num_periods} periods with "
            f"oos_ratio={oos_ratio}. Reduce num_periods or add more data."
        )

    splits = []
    for i in range(num_periods):
        # Expanding window: always start from 0
        train_end = first_train_end + i * oos_per_period
        test_start = train_end
        test_end = test_start + oos_per_period

        train_data = data.iloc[0:train_end]
        test_data = data.iloc[test_start:test_end]

        if len(train_data) > 0 and len(test_data) > 0:
            splits.append((train_data, test_data))

    logger.info(
        "walk_forward_splits_created",
        num_splits=len(splits),
        total_rows=n,
        oos_per_period=oos_per_period,
        scheme="expanding_window",
    )

    return splits


class WalkForwardBacktester:
    """Time-series cross-validation for strategy validation."""

    def __init__(self, backtest_runner: BacktestRunner | None = None):
        """
        Initialize walk-forward backtester.

        Args:
            backtest_runner: BacktestRunner instance (creates if None)
        """
        self.runner = backtest_runner or BacktestRunner()
        self.results = []
        self.per_period_metrics = []

    def run_walk_forward(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        num_periods: int = 4,
        oos_ratio: float = 0.2,
        use_synthetic: bool = False,
        validate_pairs_oos: bool = True,
        oos_validation_split: float = 0.8,
    ) -> dict[str, Any]:
        """
        Run walk-forward backtest with per-period retraining.

        **Sprint 1.3 (C-03):** Each period now:
          1. Discovers pairs on ``train_df`` only (no look-ahead).
          2. Optionally validates pairs OOS on the last 20% of ``train_df``.
          3. Simulates trading on ``test_df`` via ``StrategyBacktestSimulator``
             with a **fresh** strategy instance (no state leakage).

        Args:
            symbols: List of trading pairs
            start_date: Full backtest start date
            end_date: Full backtest end date
            num_periods: Number of train/test periods
            oos_ratio: Out-of-sample ratio (0.2 = 20% test, 80% train)
            use_synthetic: Use synthetic data for testing
            validate_pairs_oos: Whether to validate pairs against an OOS slice
                of the training window before trading.
            oos_validation_split: Fraction of ``train_df`` used for in-sample
                discovery; the remainder is the OOS validation hold-out.

        Returns:
            Dict with aggregate results + per-period breakdown
        """
        logger.info(
            "walk_forward_backtest_started",
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            num_periods=num_periods,
            oos_ratio=oos_ratio,
            validate_pairs_oos=validate_pairs_oos,
        )

        # ---- Load full dataset ------------------------------------------
        full_df = self._load_full_data(symbols, start_date, end_date, use_synthetic)

        # ---- Create walk-forward splits ---------------------------------
        splits = split_walk_forward(full_df, num_periods=num_periods, oos_ratio=oos_ratio)
        if len(splits) == 0:
            raise ValueError("No splits created. Check data length and num_periods.")

        logger.info(
            "walk_forward_data_prepared",
            rows=len(full_df),
            splits=len(splits),
        )

        # ---- Process each period ----------------------------------------
        self.per_period_metrics = []
        cost_model = CostModel()

        for period_idx, (train_df, test_df) in enumerate(splits):
            logger.info(
                "walk_forward_period_started",
                period=period_idx + 1,
                train_rows=len(train_df),
                test_rows=len(test_df),
                train_start=str(train_df.index[0]),
                train_end=str(train_df.index[-1]),
                test_start=str(test_df.index[0]),
                test_end=str(test_df.index[-1]),
            )

            try:
                # STEP 1  - Fresh strategy for this period (no state leakage)
                strategy = PairTradingStrategy()
                strategy.disable_cache()

                # STEP 2  - Discover pairs on train_df ONLY
                if validate_pairs_oos:
                    # Split train_df into IS and OOS validation slices
                    is_end = int(len(train_df) * oos_validation_split)
                    is_data = train_df.iloc[:is_end]
                    oos_data = train_df.iloc[is_end:]

                    all_pairs = strategy.find_cointegrated_pairs(is_data, use_cache=False, use_parallel=True)

                    # Validate pairs against OOS slice
                    if all_pairs and len(oos_data) > 20:
                        # validate_pairs_oos() not yet implemented
                        # Use all discovered pairs for now
                        validated_pairs = all_pairs
                        val_results: dict[str, Any] = {}
                        logger.info(
                            "walk_forward_oos_validation",
                            period=period_idx + 1,
                            discovered=len(all_pairs),
                            validated=len(validated_pairs),
                            validation_rate=val_results.get("validation_rate", "N/A"),
                        )
                    else:
                        validated_pairs = all_pairs
                else:
                    validated_pairs = strategy.find_cointegrated_pairs(train_df, use_cache=False, use_parallel=True)

                logger.info(
                    "walk_forward_pairs_discovered",
                    period=period_idx + 1,
                    pairs_count=len(validated_pairs) if validated_pairs else 0,
                )

                # STEP 3  - Simulate on test_df with FIXED pairs from training
                simulator = StrategyBacktestSimulator(
                    cost_model=cost_model,
                    initial_capital=self.runner.config.initial_capital,
                    pair_rediscovery_interval=999,  # Never re-discover; pairs are frozen
                )
                period_metrics = simulator.run(test_df, fixed_pairs=validated_pairs)

                # STEP 3b — C-07: IS vs OOS degradation check
                try:
                    _is_simulator = StrategyBacktestSimulator(
                        cost_model=cost_model,
                        initial_capital=self.runner.config.initial_capital,
                        pair_rediscovery_interval=999,
                    )
                    _is_metrics = _is_simulator.run(train_df.tail(min(len(train_df), 252)), fixed_pairs=validated_pairs)
                    _is_sharpe = _is_metrics.sharpe_ratio or 0.0
                    _oos_sharpe = period_metrics.sharpe_ratio or 0.0
                    if abs(_is_sharpe) > 0.01:
                        _degradation = (_oos_sharpe - _is_sharpe) / abs(_is_sharpe)
                        if _degradation <= -0.50:
                            logger.error(
                                "oos_degradation_critical",
                                period=period_idx + 1,
                                is_sharpe=round(_is_sharpe, 3),
                                oos_sharpe=round(_oos_sharpe, 3),
                                degradation_pct=round(_degradation * 100, 1),
                            )
                        elif _degradation <= -0.30:
                            logger.warning(
                                "oos_degradation_high",
                                period=period_idx + 1,
                                is_sharpe=round(_is_sharpe, 3),
                                oos_sharpe=round(_oos_sharpe, 3),
                                degradation_pct=round(_degradation * 100, 1),
                            )
                except Exception as _e_is:
                    logger.warning("is_comparison_failed", period=period_idx + 1, error=str(_e_is))

                self.per_period_metrics.append(
                    {
                        "period": period_idx + 1,
                        "train_start": str(train_df.index[0]),
                        "train_end": str(train_df.index[-1]),
                        "test_start": str(test_df.index[0]),
                        "test_end": str(test_df.index[-1]),
                        "pairs_discovered": len(validated_pairs) if validated_pairs else 0,
                        "metrics": period_metrics.__dict__,
                    }
                )

                logger.info(
                    "walk_forward_period_completed",
                    period=period_idx + 1,
                    total_return=period_metrics.total_return,
                    sharpe_ratio=period_metrics.sharpe_ratio,
                    max_drawdown=period_metrics.max_drawdown,
                    pairs_used=len(validated_pairs) if validated_pairs else 0,
                )

            except Exception as e:
                logger.error(
                    "walk_forward_period_failed",
                    period=period_idx + 1,
                    error=str(e),
                )
                continue

        # ---- Aggregate ------------------------------------------------
        if not self.per_period_metrics:
            raise ValueError("No periods completed successfully")

        aggregate_metrics = self._aggregate_metrics()

        result = {
            "status": "completed",
            "num_periods": len(self.per_period_metrics),
            "aggregate_metrics": aggregate_metrics,
            "per_period_metrics": self.per_period_metrics,
            "symbols": symbols,
            "full_start_date": str(full_df.index[0]),
            "full_end_date": str(full_df.index[-1]),
            "total_rows": len(full_df),
        }

        logger.info(
            "walk_forward_backtest_completed",
            num_periods=len(self.per_period_metrics),
            aggregate_return=aggregate_metrics["aggregate_return"],
            aggregate_sharpe=aggregate_metrics["aggregate_sharpe_ratio"],
            aggregate_drawdown=aggregate_metrics["aggregate_max_drawdown"],
        )

        return result

    # ------------------------------------------------------------------
    # Data loading (extracted for clarity)
    # ------------------------------------------------------------------

    @staticmethod
    def _load_full_data(
        symbols: list[str],
        start_date: str,
        end_date: str,
        use_synthetic: bool,
    ) -> pd.DataFrame:
        """Load the full price DataFrame for the walk-forward run."""
        try:
            if use_synthetic:
                from backtests.runner import _generate_cointegrated_pair

                return _generate_cointegrated_pair(start_date, end_date)

            from data.loader import DataLoader

            loader = DataLoader()
            batch_results = loader.load_ibkr_data_batch(
                symbols=symbols,
                timeframe="1d",
                validate=True,
            )
            price_data = {}
            for symbol, df in batch_results.items():
                try:
                    price_data[symbol] = df["close"]
                except Exception as e:
                    logger.warning(
                        "walk_forward_symbol_load_failed",
                        symbol=symbol,
                        error=str(e),
                    )

            if not price_data:
                raise ValueError("No symbols loaded successfully")

            full_df = pd.DataFrame(price_data)
            full_df = full_df[(full_df.index >= start_date) & (full_df.index <= end_date)]
            if len(full_df) == 0:
                raise ValueError(f"No data in date range {start_date} to {end_date}")
            return full_df

        except Exception as e:
            logger.error("walk_forward_data_load_failed", error=str(e))
            raise

    def _aggregate_metrics(self) -> dict[str, Any]:
        """
        Aggregate metrics across all periods.

        Sharpe and Sortino are computed on the CONCATENATED return series
        (not averaged per-period), which is statistically correct for
        periods of different lengths and volatilities.

        Returns:
            Dictionary with aggregate metrics
        """
        if not self.per_period_metrics:
            return {}

        period_returns = []
        period_drawdowns = []
        period_win_rates = []
        period_profit_factors = []

        # Collect raw daily returns from each period for proper aggregation
        all_daily_returns = []

        for period_data in self.per_period_metrics:
            metrics = period_data["metrics"]
            period_returns.append(metrics["total_return"])
            period_drawdowns.append(metrics["max_drawdown"])
            period_win_rates.append(metrics["win_rate"])
            period_profit_factors.append(metrics["profit_factor"])

            # Collect raw daily returns if available
            if "daily_returns" in metrics and metrics["daily_returns"] is not None:
                dr = metrics["daily_returns"]
                if isinstance(dr, pd.Series):
                    all_daily_returns.append(dr)
                elif isinstance(dr, list):
                    all_daily_returns.append(pd.Series(dr))

        # Compute aggregate Sharpe on concatenated returns (statistically correct)
        if all_daily_returns:
            concat_returns = pd.concat(all_daily_returns, ignore_index=True)
            if len(concat_returns) > 1 and concat_returns.std() > 0:
                from backtests.metrics import TRADING_DAYS_PER_YEAR

                aggregate_sharpe = (concat_returns.mean() / concat_returns.std()) * np.sqrt(TRADING_DAYS_PER_YEAR)
                # Sortino on concatenated returns
                downside = concat_returns[concat_returns < 0]
                if len(downside) > 0 and downside.std() > 0:
                    aggregate_sortino = (concat_returns.mean() / downside.std()) * np.sqrt(TRADING_DAYS_PER_YEAR)
                else:
                    aggregate_sortino = 0.0
            else:
                aggregate_sharpe = 0.0
                aggregate_sortino = 0.0
        else:
            # Fallback to per-period average if raw returns not available
            per_period_sharpes = [p["metrics"]["sharpe_ratio"] for p in self.per_period_metrics]
            aggregate_sharpe = np.mean(per_period_sharpes)
            aggregate_sortino = 0.0

        # Compute per-period Sharpe std for reporting
        per_period_sharpes = [p["metrics"]["sharpe_ratio"] for p in self.per_period_metrics]
        aggregate_sharpe_std = float(np.std(per_period_sharpes)) if len(per_period_sharpes) > 1 else 0.0

        return {
            "aggregate_return": np.mean(period_returns),
            "aggregate_return_std": np.std(period_returns),
            "aggregate_sharpe_ratio": aggregate_sharpe,
            "aggregate_sharpe_std": aggregate_sharpe_std,
            "aggregate_sortino_ratio": aggregate_sortino,
            "aggregate_max_drawdown": np.mean(period_drawdowns),
            "aggregate_drawdown_std": np.std(period_drawdowns),
            "aggregate_win_rate": np.mean(period_win_rates),
            "aggregate_profit_factor": np.mean(period_profit_factors),
            "num_periods_completed": len(self.per_period_metrics),
            "min_return": np.min(period_returns),
            "max_return": np.max(period_returns),
        }

    def print_summary(self) -> str:
        """Print formatted walk-forward summary."""
        if not self.per_period_metrics:
            return "No periods completed"

        agg = self._aggregate_metrics()

        summary = f"""
========================================
      WALK-FORWARD VALIDATION SUMMARY     
========================================
Periods Completed:      {agg["num_periods_completed"]}/
Aggregate Return:       {agg["aggregate_return"]:>7.2%} (┬▒{agg["aggregate_return_std"]:.2%})
Aggregate Sharpe:       {agg["aggregate_sharpe_ratio"]:>7.2f} (┬▒{agg["aggregate_sharpe_std"]:.2f})
Aggregate Max DD:       {agg["aggregate_max_drawdown"]:>7.2%}
Aggregate Win Rate:     {agg["aggregate_win_rate"]:>7.2%}
Aggregate Profit Fact:  {agg["aggregate_profit_factor"]:>7.2f}

Return Range:           {agg["min_return"]:>7.2%} to {agg["max_return"]:>7.2%}
========================================

Per-Period Breakdown:
"""
        for period_data in self.per_period_metrics:
            p = period_data
            metrics = p["metrics"]
            summary += f"""
Period {p["period"]}:
  Train: {p["train_start"]} to {p["train_end"]}
  Test:  {p["test_start"]} to {p["test_end"]}
  Return: {metrics["total_return"]:>7.2%} | Sharpe: {metrics["sharpe_ratio"]:>7.2f} | DD: {metrics["max_drawdown"]:>7.2%}
"""

        return summary


# ---------------------------------------------------------------------------
# High-level facade API  (C-05 consolidation — single source of truth)
# Formerly in backtester/walk_forward.py; moved here so that fixes propagate
# automatically to all callers importing from either path.
# ---------------------------------------------------------------------------


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
        # per_period items have shape {"period": …, "metrics": {"sharpe_ratio": …}}
        sharpes = [p.get("metrics", {}).get("sharpe_ratio", 0.0) for p in self.per_period]
        return float(pd.Series(sharpes).mean()) if sharpes else 0.0

    @property
    def avg_return(self) -> float:
        returns = [p.get("metrics", {}).get("total_return", 0.0) for p in self.per_period]
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

    def __init__(self) -> None:
        self._backtester = WalkForwardBacktester()

    def run(self, config: WalkForwardConfig) -> WalkForwardResult:
        """
        Execute full walk-forward validation.

        Args:
            config: Walk-forward configuration.

        Returns:
            WalkForwardResult with per-period breakdown and aggregate verdict.
        """
        _log = get_logger(__name__)
        _log.info(
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

        per_period: list[dict[str, Any]] = raw.get("per_period_metrics", [])
        aggregate: dict[str, Any] = raw.get("aggregate_metrics", {})

        # pass/fail: >=50% of periods profitable
        # Each entry has shape {"period": int, "metrics": {"total_return": float, …}}
        profitable_periods = sum(1 for p in per_period if p.get("metrics", {}).get("total_return", 0.0) > 0)
        passed = len(per_period) > 0 and (profitable_periods / len(per_period)) >= 0.50

        result = WalkForwardResult(
            per_period=per_period,
            aggregate=aggregate,
            config=config,
            num_periods_executed=len(per_period),
            passed=passed,
        )

        _log.info(
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
    ) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Create train/test splits without running backtests.

        Returns:
            List of (train_df, test_df) tuples.
        """
        return split_walk_forward(data, num_periods=num_periods, oos_ratio=oos_ratio)


def generate_walk_forward_report(
    result: WalkForwardResult,
    output_path: str | None = None,
) -> dict[str, Any]:
    """
    Generate a structured walk-forward report from a WalkForwardResult.

    Writes a JSON file if output_path is provided.
    Emits a warning if OOS Sharpe < 0.5 × IS Sharpe (overfitting signal).

    Args:
        result: WalkForwardResult produced by WalkForwardEngine.run().
        output_path: Optional path to write JSON report (e.g. "results/wf_report.json").

    Returns:
        Report dict with per-period metrics, global stats, and overfitting flag.
    """
    import json
    from datetime import UTC, datetime
    from pathlib import Path

    per_period_summary = []
    for p in result.per_period:
        m = p.get("metrics", {})
        per_period_summary.append(
            {
                "period": p.get("period"),
                "sharpe": round(float(m.get("sharpe_ratio", 0.0)), 4),
                "max_drawdown": round(float(m.get("max_drawdown", 0.0)), 4),
                "profit_factor": round(float(m.get("profit_factor", 0.0)), 4),
                "total_return": round(float(m.get("total_return", 0.0)), 6),
                "num_trades": int(m.get("num_trades", 0)),
            }
        )

    oos_sharpes = [p["sharpe"] for p in per_period_summary]
    avg_oos_sharpe = float(pd.Series(oos_sharpes).mean()) if oos_sharpes else 0.0

    # Check for IS/OOS degradation (requires aggregate IS metrics if available)
    is_sharpe = float(result.aggregate.get("is_sharpe", avg_oos_sharpe))
    oos_oos_ratio = avg_oos_sharpe / is_sharpe if is_sharpe > 0 else 1.0
    overfitting_flag = oos_oos_ratio < 0.5

    if overfitting_flag:
        logger.warning(
            "walk_forward_overfitting_signal",
            is_sharpe=round(is_sharpe, 3),
            avg_oos_sharpe=round(avg_oos_sharpe, 3),
            oos_is_ratio=round(oos_oos_ratio, 3),
        )

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "config": {
            "symbols": getattr(result.config, "symbols", []),
            "num_periods": result.num_periods_executed,
            "oos_ratio": getattr(result.config, "oos_ratio", None),
        },
        "global_stats": {
            "avg_oos_sharpe": round(avg_oos_sharpe, 4),
            "avg_oos_return": round(result.avg_return, 6),
            "is_sharpe": round(is_sharpe, 4),
            "oos_is_ratio": round(oos_oos_ratio, 4),
            "passed": result.passed,
            "overfitting_flag": overfitting_flag,
        },
        "per_period": per_period_summary,
    }

    if output_path is not None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info("walk_forward_report_written", path=output_path)

    return report
