"""
Stress Testing Framework -- Phase 3 (addresses audit S6.6).

Problem
-------
The backtest only evaluates performance on *historical* data.  It does not
test what happens under **extreme scenarios** that may not have occurred in
the historical window: flash crashes, prolonged drawdowns, correlation
breakdowns, liquidity droughts, and regime shifts.

Solution
--------
Synthetic scenario injection into historical price data:

1. **Flash crash** -- Injects a sudden drop (user-defined magnitude) over
   a short window, then partial recovery.
2. **Prolonged drawdown** -- Applies a gradual negative trend over N bars.
3. **Correlation breakdown** -- Decorrelates pair legs by adding independent
   noise to one leg, breaking the cointegration relationship.
4. **Volatility spike** -- Multiplies returns by a factor for N bars to
   simulate a vol regime change.
5. **Liquidity drought** -- Widens effective slippage and reduces volume.

Each scenario returns modified price data that can be fed to the standard
``StrategyBacktestSimulator`` for evaluation.

Usage::

    stress = StressTestRunner(simulator)
    results = stress.run_all_scenarios(prices_df, pairs)
    report = stress.generate_report(results)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class StressScenario:
    """Definition of a single stress scenario."""

    name: str
    """Human-readable scenario name."""

    description: str
    """What this scenario simulates."""

    severity: str = "moderate"
    """Severity level: 'mild', 'moderate', 'severe'."""


@dataclass
class StressTestResult:
    """Result from running one stress scenario."""

    scenario: StressScenario
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    num_trades: int
    win_rate: float
    survived: bool
    """Whether the strategy survived (equity > 0 and DD < 100%)."""
    details: dict[str, Any] = field(default_factory=dict)


class StressScenarioGenerator:
    """
    Generates stressed price data by injecting synthetic shocks
    into historical price series.
    """

    @staticmethod
    def flash_crash(
        prices: pd.DataFrame,
        crash_bar: int | None = None,
        crash_pct: float = 0.30,
        recovery_pct: float = 0.50,
        crash_duration: int = 1,
        recovery_duration: int = 5,
    ) -> pd.DataFrame:
        """Inject a flash crash into all columns.

        Args:
            prices: Original price data (columns = symbols).
            crash_bar: Bar index where crash starts.  Default: middle.
            crash_pct: Drop magnitude (0.30 = 30% drop).
            recovery_pct: Fraction of drop recovered (0.50 = recovers half).
            crash_duration: Bars over which the drop occurs.
            recovery_duration: Bars over which recovery occurs.
        """
        df = prices.copy()
        n = len(df)
        if crash_bar is None:
            crash_bar = n // 2

        for col in df.columns:
            series = df[col].values.astype(float)
            pre_crash_price = series[crash_bar]

            # Apply crash
            drop = pre_crash_price * crash_pct
            for i in range(crash_duration):
                idx = crash_bar + i
                if idx < n:
                    frac = (i + 1) / crash_duration
                    series[idx] = pre_crash_price - drop * frac

            # Apply recovery
            crash_bottom = pre_crash_price - drop
            recovery_amount = drop * recovery_pct
            for i in range(recovery_duration):
                idx = crash_bar + crash_duration + i
                if idx < n:
                    frac = (i + 1) / recovery_duration
                    series[idx] = crash_bottom + recovery_amount * frac

            # Shift remaining prices by the net impact
            net_shift = -(drop * (1 - recovery_pct))
            shift_start = crash_bar + crash_duration + recovery_duration
            if shift_start < n:
                series[shift_start:] += net_shift

            df[col] = series

        return df

    @staticmethod
    def prolonged_drawdown(
        prices: pd.DataFrame,
        start_bar: int | None = None,
        duration: int = 60,
        total_drop_pct: float = 0.20,
    ) -> pd.DataFrame:
        """Apply a gradual downtrend to all series.

        Args:
            prices: Original price data.
            start_bar: Where drawdown begins.  Default: 1/3 into the series.
            duration: Bars over which the drawdown occurs.
            total_drop_pct: Total cumulative drop (0.20 = 20%).
        """
        df = prices.copy()
        n = len(df)
        if start_bar is None:
            start_bar = n // 3

        daily_factor = (1 - total_drop_pct) ** (1 / duration)

        for col in df.columns:
            series = df[col].values.astype(float)
            for i in range(duration):
                idx = start_bar + i
                if idx < n:
                    cumulative = daily_factor ** (i + 1)
                    series[idx] *= cumulative

            # Shift remaining bars
            end_idx = start_bar + duration
            if end_idx < n:
                final_factor = daily_factor**duration
                series[end_idx:] *= final_factor

            df[col] = series

        return df

    @staticmethod
    def correlation_breakdown(
        prices: pd.DataFrame,
        start_bar: int | None = None,
        duration: int = 30,
        noise_scale: float = 0.05,
        affected_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """Break cointegration by adding independent noise to selected columns.

        Args:
            prices: Original price data.
            start_bar: Where breakdown begins.
            duration: Number of bars of decorrelation.
            noise_scale: Magnitude of noise relative to price (0.05 = 5%).
            affected_columns: Which columns get noise (default: odd-indexed).
        """
        df = prices.copy()
        n = len(df)
        if start_bar is None:
            start_bar = n // 2

        if affected_columns is None:
            affected_columns = [df.columns[i] for i in range(1, len(df.columns), 2)]

        rng = np.random.RandomState(42)

        for col in affected_columns:
            if col not in df.columns:
                continue
            series = df[col].values.astype(float)
            for i in range(duration):
                idx = start_bar + i
                if idx < n:
                    noise = rng.normal(0, noise_scale * series[idx])
                    series[idx] += noise
            df[col] = series

        return df

    @staticmethod
    def volatility_spike(
        prices: pd.DataFrame,
        start_bar: int | None = None,
        duration: int = 20,
        vol_multiplier: float = 3.0,
    ) -> pd.DataFrame:
        """Multiply return volatility by a factor for N bars.

        Args:
            prices: Original price data.
            start_bar: Where vol spike begins.
            duration: Number of bars of elevated volatility.
            vol_multiplier: Factor by which daily returns are multiplied.
        """
        df = prices.copy()
        n = len(df)
        if start_bar is None:
            start_bar = n // 2

        for col in df.columns:
            series = df[col].values.astype(float)
            for i in range(duration):
                idx = start_bar + i
                if idx < n and idx > 0:
                    orig_ret = (series[idx] - series[idx - 1]) / series[idx - 1]
                    amplified_ret = orig_ret * vol_multiplier
                    series[idx] = series[idx - 1] * (1 + amplified_ret)

            # Propagate from end of spike
            for idx in range(start_bar + duration, n):
                if idx > 0:
                    orig_ret = (prices[col].values[idx] - prices[col].values[idx - 1]) / prices[col].values[idx - 1]
                    series[idx] = series[idx - 1] * (1 + orig_ret)

            df[col] = series

        return df


class StressTestRunner:
    """
    Runs the strategy through multiple stress scenarios and aggregates results.
    """

    def __init__(self, simulator_factory=None):
        """
        Args:
            simulator_factory: Callable that returns a fresh
                ``StrategyBacktestSimulator`` instance.  If None, uses a
                default factory that imports and creates one with standard config.
        """
        self._simulator_factory = simulator_factory or self._default_factory
        self.results: list[StressTestResult] = []

    @staticmethod
    def _default_factory():
        from backtests.cost_model import CostModel
        from backtests.strategy_simulator import StrategyBacktestSimulator

        return StrategyBacktestSimulator(cost_model=CostModel())

    def get_default_scenarios(self) -> list[tuple[StressScenario, Callable, dict]]:
        """Return the default suite of stress scenarios.

        Returns:
            List of (scenario_def, generator_func, kwargs).
        """
        gen = StressScenarioGenerator

        return [
            (
                StressScenario("Flash Crash -20%", "Sudden 20% drop with 50% recovery", "moderate"),
                gen.flash_crash,
                {"crash_pct": 0.20, "recovery_pct": 0.50},
            ),
            (
                StressScenario("Flash Crash -40%", "Severe 40% crash with 30% recovery", "severe"),
                gen.flash_crash,
                {"crash_pct": 0.40, "recovery_pct": 0.30},
            ),
            (
                StressScenario("Prolonged Bear -15%", "Gradual 15% drawdown over 60 bars", "moderate"),
                gen.prolonged_drawdown,
                {"duration": 60, "total_drop_pct": 0.15},
            ),
            (
                StressScenario("Prolonged Bear -30%", "Severe 30% drawdown over 90 bars", "severe"),
                gen.prolonged_drawdown,
                {"duration": 90, "total_drop_pct": 0.30},
            ),
            (
                StressScenario("Correlation Breakdown", "Pair decorrelation for 30 bars", "moderate"),
                gen.correlation_breakdown,
                {"duration": 30, "noise_scale": 0.05},
            ),
            (
                StressScenario("Severe Decorrelation", "Strong decorrelation for 60 bars", "severe"),
                gen.correlation_breakdown,
                {"duration": 60, "noise_scale": 0.10},
            ),
            (
                StressScenario("Vol Spike 3x", "Volatility triples for 20 bars", "moderate"),
                gen.volatility_spike,
                {"duration": 20, "vol_multiplier": 3.0},
            ),
            (
                StressScenario("Vol Spike 5x", "Volatility 5x for 10 bars", "severe"),
                gen.volatility_spike,
                {"duration": 10, "vol_multiplier": 5.0},
            ),
        ]

    def run_scenario(
        self,
        prices_df: pd.DataFrame,
        scenario: StressScenario,
        generator_func: Callable,
        gen_kwargs: dict,
        fixed_pairs: list | None = None,
    ) -> StressTestResult:
        """Run a single stress scenario.

        Args:
            prices_df: Original price data.
            scenario: Scenario definition.
            generator_func: Function that transforms prices_df.
            gen_kwargs: Kwargs for the generator function.
            fixed_pairs: Pre-discovered pairs to use.

        Returns:
            StressTestResult with performance metrics.
        """
        logger.info("stress_test_scenario_start", name=scenario.name, severity=scenario.severity)

        # Generate stressed data
        stressed_prices = generator_func(prices_df, **gen_kwargs)

        # Run simulator
        simulator = self._simulator_factory()
        try:
            metrics = simulator.run(stressed_prices, fixed_pairs=fixed_pairs)
            survived = metrics.max_drawdown > -1.0 and metrics.total_return > -0.99

            result = StressTestResult(
                scenario=scenario,
                total_return=metrics.total_return,
                max_drawdown=metrics.max_drawdown,
                sharpe_ratio=metrics.sharpe_ratio,
                num_trades=metrics.total_trades,
                win_rate=metrics.win_rate,
                survived=survived,
                details={
                    "profit_factor": metrics.profit_factor,
                    "sortino_ratio": metrics.sortino_ratio,
                    "calmar_ratio": metrics.calmar_ratio,
                },
            )
        except Exception as e:
            logger.error("stress_test_scenario_failed", name=scenario.name, error=str(e))
            result = StressTestResult(
                scenario=scenario,
                total_return=-1.0,
                max_drawdown=-1.0,
                sharpe_ratio=0.0,
                num_trades=0,
                win_rate=0.0,
                survived=False,
                details={"error": str(e)},
            )

        logger.info(
            "stress_test_scenario_complete",
            name=scenario.name,
            survived=result.survived,
            total_return=f"{result.total_return:.2%}",
            max_drawdown=f"{result.max_drawdown:.2%}",
        )
        return result

    def run_all_scenarios(
        self,
        prices_df: pd.DataFrame,
        fixed_pairs: list | None = None,
        scenarios: list[tuple] | None = None,
    ) -> list[StressTestResult]:
        """Run all default (or custom) scenarios.

        Returns:
            List of StressTestResult.
        """
        if scenarios is None:
            scenarios = self.get_default_scenarios()

        self.results = []
        for scenario_def, gen_func, gen_kwargs in scenarios:
            result = self.run_scenario(prices_df, scenario_def, gen_func, gen_kwargs, fixed_pairs)
            self.results.append(result)

        return self.results

    def generate_report(self, results: list[StressTestResult] | None = None) -> dict[str, Any]:
        """Generate a summary report from stress test results.

        Returns:
            Dict with survival rate, worst scenario, per-scenario details.
        """
        results = results or self.results
        if not results:
            return {"error": "No results to report"}

        survived_count = sum(1 for r in results if r.survived)
        total = len(results)

        worst = min(results, key=lambda r: r.total_return)
        best = max(results, key=lambda r: r.total_return)

        per_scenario = []
        for r in results:
            per_scenario.append(
                {
                    "name": r.scenario.name,
                    "severity": r.scenario.severity,
                    "survived": r.survived,
                    "total_return": round(r.total_return, 4),
                    "max_drawdown": round(r.max_drawdown, 4),
                    "sharpe_ratio": round(r.sharpe_ratio, 4),
                    "num_trades": r.num_trades,
                    "win_rate": round(r.win_rate, 4),
                }
            )

        report = {
            "total_scenarios": total,
            "survived": survived_count,
            "survival_rate": survived_count / total,
            "worst_scenario": worst.scenario.name,
            "worst_return": round(worst.total_return, 4),
            "best_scenario": best.scenario.name,
            "best_return": round(best.total_return, 4),
            "avg_return": round(np.mean([r.total_return for r in results]), 4),
            "avg_max_drawdown": round(np.mean([r.max_drawdown for r in results]), 4),
            "per_scenario": per_scenario,
        }

        logger.info(
            "stress_test_report",
            survival_rate=f"{report['survival_rate']:.0%}",
            worst=report["worst_scenario"],
            worst_return=f"{report['worst_return']:.2%}",
        )

        return report


__all__ = [
    "StressScenario",
    "StressTestResult",
    "StressScenarioGenerator",
    "StressTestRunner",
]
