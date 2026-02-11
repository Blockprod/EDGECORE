import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import adfuller, grangercausalitytests
from structlog import get_logger
from typing import Tuple, Optional

logger = get_logger(__name__)

def engle_granger_test(
    y: pd.Series,
    x: pd.Series,
    max_lags: int = 12,
    regression: str = "c"
) -> dict:
    """
    Perform Engle-Granger two-step cointegration test.
    
    Args:
        y: Dependent series
        x: Independent series
        max_lags: Max lags for error correction term
        regression: Regression type ("c", "ct", "ctt")
    
    Returns:
        Dictionary with test results
    """
    # Step 1: OLS regression
    X = np.column_stack([np.ones(len(x)), x.values])
    beta = np.linalg.lstsq(X, y.values, rcond=None)[0]
    residuals = y.values - X @ beta
    
    # Step 2: ADF test on residuals
    adf_result = adfuller(residuals, regression=regression, autolag='AIC')
    
    coint_score = adf_result[0]
    coint_pvalue = adf_result[1]
    is_cointegrated = coint_pvalue < 0.05
    
    result = {
        'beta': beta[1],
        'intercept': beta[0],
        'residuals': residuals,
        'adf_statistic': coint_score,
        'adf_pvalue': coint_pvalue,
        'is_cointegrated': is_cointegrated,
        'critical_values': adf_result[4]
    }
    
    logger.info(
        "eg_test_complete",
        coint_pvalue=coint_pvalue,
        is_cointegrated=is_cointegrated
    )
    
    return result

def correlation_matrix(prices: pd.DataFrame) -> Tuple[np.ndarray, list]:
    """
    Compute rolling correlation matrix and identify pairs.
    
    Args:
        prices: DataFrame with multiple price series (columns = symbols)
    
    Returns:
        Tuple of (correlation_matrix, list of symbol pairs)
    """
    corr = prices.corr()
    
    # Extract upper triangle (avoid duplicates)
    pairs = []
    symbols = prices.columns.tolist()
    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            pairs.append((symbols[i], symbols[j], corr.iloc[i, j]))
    
    return corr.values, pairs

def half_life_mean_reversion(spread: pd.Series, max_lag: int = 60) -> Optional[int]:
    """
    Estimate half-life of mean reversion via AR(1) model.
    
    Uses OLS regression: spread_diff = beta_0 + beta_1 * spread_lag
    Which gives: spread_t = beta_0 + (1 + beta_1) * spread_{t-1}
    So AR(1) coefficient: rho = 1 + beta_1
    
    Args:
        spread: Spread time series
        max_lag: Maximum lag to test
    
    Returns:
        Half-life in periods, or None if AR coefficient >= 1 or invalid
    """
    spread_diff = spread.diff().dropna()
    spread_lag = spread.shift(1).dropna()
    
    # Align series
    common_idx = spread_diff.index.intersection(spread_lag.index)
    y = spread_diff.loc[common_idx]
    X = np.column_stack([np.ones(len(spread_lag)), spread_lag.loc[common_idx]])
    
    try:
        beta = np.linalg.lstsq(X, y.values, rcond=None)[0]
        beta_1 = beta[1]  # Regression coefficient
        
        # The actual AR(1) coefficient is rho = 1 + beta_1
        # This comes from: spread_t - spread_{t-1} = beta_0 + beta_1 * spread_{t-1}
        # Rearranged: spread_t = beta_0 + (1 + beta_1) * spread_{t-1}
        rho = 1.0 + beta_1
        
        # Validate rho: must be in (0, 1) for mean reversion
        # Check for: >= 1.0 (non-stationary), <= 0 (invalid), NaN, or Inf
        if rho >= 1.0 or rho <= 0.0 or np.isnan(rho) or np.isinf(rho):
            return None
        
        # Compute half-life: -log(2) / log(rho)
        # This is safe now because rho is in (0, 1)
        log_rho = np.log(rho)
        
        # Extra safety check on the log result
        if np.isnan(log_rho) or np.isinf(log_rho):
            return None
        
        # Avoid division by zero (rho = 1.0 case, though already checked)
        if abs(log_rho) < 1e-10:
            return None
        
        half_life = -np.log(2) / log_rho
        
        # Verify the result is valid
        if np.isnan(half_life) or np.isinf(half_life) or half_life <= 0:
            return None
        
        return int(np.round(half_life))
    except:
        return None
