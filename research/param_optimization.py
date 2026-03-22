"""
Parameter optimization module for strategy tuning.

TODO:
- Grid search over parameter space
- Walk-forward validation
- Correlation analysis of parameters
"""

from itertools import product

import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


def grid_search_parameters(param_grid: dict, backtest_fn) -> pd.DataFrame:
    """
    Perform grid search over parameter space.

    Args:
        param_grid: Dict of {param_name: [values]}
        backtest_fn: Function that returns metric given params

    Returns:
        DataFrame with results
    """
    param_names = list(param_grid.keys())
    param_values = [param_grid[name] for name in param_names]

    results = []
    for combo in product(*param_values):
        params = dict(zip(param_names, combo, strict=False))
        try:
            metric = backtest_fn(**params)
            result_row = {**params, "metric": metric}
            results.append(result_row)
            logger.info("grid_search_iteration", params=params, metric=metric)
        except Exception as e:
            logger.error("grid_search_failed", params=params, error=str(e))
            continue

    return pd.DataFrame(results)
