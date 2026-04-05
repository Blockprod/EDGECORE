<<<<<<< HEAD
﻿"""
Parameter Cross-Validation ÔÇô Phase 3 (addresses audit ┬º4.2).
=======
"""
Parameter Cross-Validation – Phase 3 (addresses audit §4.2).
>>>>>>> origin/main

Problem
-------
The strategy has 12+ free parameters (entry thresholds, HL adjustments,
vol percentiles, etc.) that were manually chosen without systematic
optimisation.  Risk of **over-fitting** to historical data is high.

Solution
--------
Walk-forward **parameter cross-validation** using the existing
``split_walk_forward`` infrastructure:

1. Define a parameter grid (or random sample).
2. For each fold: fit parameters on the training set, evaluate on the
   test set using a single objective (Sharpe, or a composite metric).
3. Select the parameter set with the best **average OOS performance**
   across all folds.
4. Report stability metrics: how much does the optimal parameter set
   vary across folds?

<<<<<<< HEAD
This does NOT overwrite production parameters automatically ÔÇô it
=======
This does NOT overwrite production parameters automatically – it
>>>>>>> origin/main
generates a **recommendation report** that the human reviews.

Usage::

    cv = ParameterCrossValidator(prices_df, num_folds=5)
    report = cv.run(param_grid)
    best_params = cv.best_params()
"""

from __future__ import annotations

<<<<<<< HEAD
import itertools

# pyright: reportUnusedImport=false, reportUnusedVariable=false
from dataclasses import dataclass
from typing import Any, Callable

=======
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Callable
import itertools
>>>>>>> origin/main
import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class ParamSpec:
    """Specification for a single parameter to optimise."""

    name: str
    """Dotted path to the parameter, e.g. 'base_entry_threshold'."""

<<<<<<< HEAD
    values: list[Any]
=======
    values: List[Any]
>>>>>>> origin/main
    """Candidate values to try."""


@dataclass
class CVResult:
    """Result of cross-validating one parameter set."""

<<<<<<< HEAD
    params: dict[str, Any]
    fold_scores: list[float]
=======
    params: Dict[str, Any]
    fold_scores: List[float]
>>>>>>> origin/main
    mean_score: float
    std_score: float
    worst_fold: float
    best_fold: float


class ParameterCrossValidator:
    """
    Walk-forward cross-validation for strategy parameters.
    """

    def __init__(
        self,
        prices_df: pd.DataFrame,
        num_folds: int = 5,
        oos_ratio: float = 0.2,
<<<<<<< HEAD
        scoring_fn: Callable | None = None,
=======
        scoring_fn: Optional[Callable] = None,
>>>>>>> origin/main
        max_combinations: int = 200,
    ):
        """
        Args:
            prices_df: Full price DataFrame (symbols as columns).
            num_folds: Number of walk-forward folds.
            oos_ratio: Out-of-sample ratio per fold.
<<<<<<< HEAD
            scoring_fn: Function(BacktestMetrics) Ôåô float.
=======
            scoring_fn: Function(BacktestMetrics) ↓ float.
>>>>>>> origin/main
                Default: Sharpe ratio (higher is better).
            max_combinations: Maximum parameter combinations.  If the
                full grid exceeds this, random sampling is used.
        """
        self.prices_df = prices_df
        self.num_folds = num_folds
        self.oos_ratio = oos_ratio
        self.scoring_fn = scoring_fn or (lambda m: m.sharpe_ratio)
        self.max_combinations = max_combinations
<<<<<<< HEAD
        self.results: list[CVResult] = []
=======
        self.results: List[CVResult] = []
>>>>>>> origin/main

        # Create splits once
        from backtests.walk_forward import split_walk_forward

<<<<<<< HEAD
        self.splits = split_walk_forward(prices_df, num_periods=num_folds, oos_ratio=oos_ratio)
=======
        self.splits = split_walk_forward(
            prices_df, num_periods=num_folds, oos_ratio=oos_ratio
        )
>>>>>>> origin/main

        logger.info(
            "parameter_cv_initialized",
            num_folds=num_folds,
            total_bars=len(prices_df),
            splits_created=len(self.splits),
        )

<<<<<<< HEAD
    def build_grid(self, param_specs: list[ParamSpec]) -> list[dict[str, Any]]:
=======
    def build_grid(self, param_specs: List[ParamSpec]) -> List[Dict[str, Any]]:
>>>>>>> origin/main
        """Build parameter grid from specs, with optional random sampling.

        Args:
            param_specs: List of ParamSpec defining the search space.

        Returns:
            List of parameter dicts.
        """
        names = [p.name for p in param_specs]
        value_lists = [p.values for p in param_specs]
<<<<<<< HEAD
        full_grid = [dict(zip(names, combo, strict=False)) for combo in itertools.product(*value_lists)]
=======
        full_grid = [dict(zip(names, combo)) for combo in itertools.product(*value_lists)]
>>>>>>> origin/main

        if len(full_grid) > self.max_combinations:
            rng = np.random.RandomState(42)
            indices = rng.choice(len(full_grid), self.max_combinations, replace=False)
            grid = [full_grid[i] for i in sorted(indices)]
            logger.info(
                "parameter_grid_sampled",
                full_size=len(full_grid),
                sampled=len(grid),
            )
        else:
            grid = full_grid

        return grid

    def evaluate_params(
        self,
<<<<<<< HEAD
        params: dict[str, Any],
=======
        params: Dict[str, Any],
>>>>>>> origin/main
    ) -> CVResult:
        """Evaluate a single parameter set across all folds.

        For each fold:
        1. Create a fresh simulator with the given params.
        2. Run on the test data with pairs discovered from training data.
        3. Compute the scoring metric.

        Args:
            params: Parameter dict to evaluate.

        Returns:
            CVResult with fold-level scores.
        """
<<<<<<< HEAD
        from backtests.cost_model import CostModel
        from backtests.strategy_simulator import StrategyBacktestSimulator
=======
        from backtests.strategy_simulator import StrategyBacktestSimulator
        from backtests.cost_model import CostModel
>>>>>>> origin/main
        from strategies.pair_trading import PairTradingStrategy

        fold_scores = []

        for fold_idx, (train_df, test_df) in enumerate(self.splits):
            try:
                # Create fresh strategy with custom params
                strategy = PairTradingStrategy()
                strategy.disable_cache()

                # Apply parameters to strategy/threshold config
                self._apply_params(strategy, params)

                # Discover pairs on training data
<<<<<<< HEAD
                pairs = strategy.find_cointegrated_pairs(train_df, use_cache=False, use_parallel=True)
=======
                pairs = strategy.find_cointegrated_pairs(
                    train_df, use_cache=False, use_parallel=True
                )
>>>>>>> origin/main

                # Create simulator with params
                sim_kwargs = {}
                if "allocation_per_pair_pct" in params:
                    sim_kwargs["allocation_per_pair_pct"] = params["allocation_per_pair_pct"]

                simulator = StrategyBacktestSimulator(
                    cost_model=CostModel(),
                    pair_rediscovery_interval=999,  # Frozen pairs
                    **sim_kwargs,
                )

                metrics = simulator.run(test_df, fixed_pairs=pairs)
                score = self.scoring_fn(metrics)
                fold_scores.append(score)

            except Exception as e:
                logger.warning(
                    "parameter_cv_fold_failed",
                    fold=fold_idx,
                    params=params,
                    error=str(e),
                )
                fold_scores.append(float("-inf"))

        result = CVResult(
            params=params,
            fold_scores=fold_scores,
            mean_score=float(np.mean([s for s in fold_scores if np.isfinite(s)]) if fold_scores else 0),
            std_score=float(np.std([s for s in fold_scores if np.isfinite(s)]) if fold_scores else 0),
            worst_fold=float(min(fold_scores)) if fold_scores else float("-inf"),
            best_fold=float(max(fold_scores)) if fold_scores else float("-inf"),
        )

        logger.info(
            "parameter_cv_evaluated",
            params=params,
            mean_score=round(result.mean_score, 4),
            std_score=round(result.std_score, 4),
        )

        return result

<<<<<<< HEAD
    def run(self, param_specs: list[ParamSpec]) -> list[CVResult]:
=======
    def run(self, param_specs: List[ParamSpec]) -> List[CVResult]:
>>>>>>> origin/main
        """Run the full cross-validation grid search.

        Args:
            param_specs: Parameter search space.

        Returns:
            Sorted list of CVResult (best first).
        """
        grid = self.build_grid(param_specs)
        logger.info("parameter_cv_started", combinations=len(grid), folds=self.num_folds)

        self.results = []
        for i, params in enumerate(grid):
            logger.info("parameter_cv_combo", index=i + 1, total=len(grid))
            result = self.evaluate_params(params)
            self.results.append(result)

        # Sort by mean score descending
        self.results.sort(key=lambda r: r.mean_score, reverse=True)

        logger.info(
            "parameter_cv_completed",
            total_combos=len(self.results),
            best_mean_score=round(self.results[0].mean_score, 4) if self.results else None,
            best_params=self.results[0].params if self.results else None,
        )

        return self.results

<<<<<<< HEAD
    def best_params(self) -> dict[str, Any] | None:
=======
    def best_params(self) -> Optional[Dict[str, Any]]:
>>>>>>> origin/main
        """Return the best parameter set (highest mean OOS score)."""
        if not self.results:
            return None
        return self.results[0].params

<<<<<<< HEAD
    def generate_report(self) -> dict[str, Any]:
=======
    def generate_report(self) -> Dict[str, Any]:
>>>>>>> origin/main
        """Generate a human-readable report of the cross-validation."""
        if not self.results:
            return {"error": "No results. Run the CV first."}

        top_5 = self.results[:5]
        report = {
            "num_combinations_tested": len(self.results),
            "num_folds": self.num_folds,
            "best_params": top_5[0].params,
            "best_mean_score": round(top_5[0].mean_score, 4),
            "best_std_score": round(top_5[0].std_score, 4),
            "best_worst_fold": round(top_5[0].worst_fold, 4),
            "top_5": [
                {
                    "rank": i + 1,
                    "params": r.params,
                    "mean_score": round(r.mean_score, 4),
                    "std_score": round(r.std_score, 4),
                    "worst_fold": round(r.worst_fold, 4),
                    "fold_scores": [round(s, 4) for s in r.fold_scores],
                }
                for i, r in enumerate(top_5)
            ],
            "stability_check": self._stability_analysis(top_5),
        }
        return report

<<<<<<< HEAD
    def _stability_analysis(self, top_results: list[CVResult]) -> dict[str, Any]:
=======
    def _stability_analysis(self, top_results: List[CVResult]) -> Dict[str, Any]:
>>>>>>> origin/main
        """Check if top parameter sets are stable (similar values)."""
        if len(top_results) < 2:
            return {"stable": True, "detail": "Only one result"}

        # Check if all top-5 have similar parameters
        all_params = [r.params for r in top_results]
        param_keys = list(all_params[0].keys())

        stability = {}
        for key in param_keys:
            values = [p[key] for p in all_params if key in p]
            if all(isinstance(v, (int, float)) for v in values):
                stability[key] = {
                    "mean": round(float(np.mean(values)), 4),
                    "std": round(float(np.std(values)), 4),
                    "range": [min(values), max(values)],
                    "stable": float(np.std(values)) < 0.3 * abs(float(np.mean(values))) + 1e-6,
                }
            else:
                unique = set(str(v) for v in values)
                stability[key] = {"unique_values": list(unique), "stable": len(unique) == 1}

        all_stable = all(v.get("stable", True) for v in stability.values())
        return {"stable": all_stable, "per_param": stability}

    @staticmethod
<<<<<<< HEAD
    def _apply_params(strategy: Any, params: dict[str, Any]) -> None:
        """Apply parameter dict to a strategy instance.

        Handles common parameter paths:
        - ``base_entry_threshold`` Ôåô strategy threshold config
        - ``low_vol_adjustment`` / ``high_vol_adjustment`` Ôåô threshold config
        - ``short_hl_adjustment`` / ``long_hl_adjustment`` Ôåô threshold config
        - ``widening_threshold`` Ôåô trailing stop
        - ``max_days_cap`` Ôåô time stop config
=======
    def _apply_params(strategy: Any, params: Dict[str, Any]) -> None:
        """Apply parameter dict to a strategy instance.

        Handles common parameter paths:
        - ``base_entry_threshold`` ↓ strategy threshold config
        - ``low_vol_adjustment`` / ``high_vol_adjustment`` ↓ threshold config
        - ``short_hl_adjustment`` / ``long_hl_adjustment`` ↓ threshold config
        - ``widening_threshold`` ↓ trailing stop
        - ``max_days_cap`` ↓ time stop config
>>>>>>> origin/main
        """
        for key, value in params.items():
            # Threshold config
            if key == "base_entry_threshold":
                if hasattr(strategy, "spread_models"):
                    # Will be picked up by AdaptiveThresholdCalculator
                    strategy._cv_base_entry = value
            elif key == "allocation_per_pair_pct":
                pass  # Handled at simulator level
            elif key in ("widening_threshold",):
                if hasattr(strategy, "trailing_stop_manager"):
                    strategy.trailing_stop_manager.widening_threshold = value
            elif key == "leg_correlation_decay_threshold":
                strategy.leg_correlation_decay_threshold = value
            # Fallback: set as attribute if it exists
            elif hasattr(strategy, key):
                setattr(strategy, key, value)


<<<<<<< HEAD
# ÔôÇÔôÇ Default parameter grid (conservative) ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
=======
# ⓀⓀ Default parameter grid (conservative) ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
>>>>>>> origin/main

DEFAULT_PARAM_SPECS = [
    ParamSpec("base_entry_threshold", [1.5, 1.8, 2.0, 2.2, 2.5]),
    ParamSpec("allocation_per_pair_pct", [1.5, 2.0, 2.5, 3.0]),
    ParamSpec("leg_correlation_decay_threshold", [0.4, 0.5, 0.6]),
]


__all__ = [
    "ParamSpec",
    "CVResult",
    "ParameterCrossValidator",
    "DEFAULT_PARAM_SPECS",
]
