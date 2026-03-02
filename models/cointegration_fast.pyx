# cython: language_level=3, boundscheck=False, wraparound=False
"""
Fast cointegration testing with Cython.
Hybrid approach: Cython-accelerated OLS + statsmodels ADF for correctness.
Much simpler than C++/pybind11, significantly faster than pure Python.
"""

import numpy as np
cimport numpy as np
cimport cython
from libc.math cimport log, isnan, isinf, sqrt
from cython.parallel import prange
from statsmodels.tsa.stattools import adfuller as _adfuller

DTYPE = np.float64
ctypedef np.float64_t DTYPE_t

@cython.boundscheck(False)
@cython.wraparound(False)
def engle_granger_fast(
    np.ndarray[DTYPE_t, ndim=1] y,
    np.ndarray[DTYPE_t, ndim=1] x,
) -> dict:
    """
    Fast Engle-Granger cointegration test using Cython.
    5-10x faster than pure Python without complex C++ setup.
    
    Args:
        y: Dependent series (numpy array)
        x: Independent series (numpy array)
    
    Returns:
        Dictionary with test results {is_cointegrated, adf_pvalue, beta, ...}
    """
    
    cdef int n = y.shape[0]
    cdef int i, j
    cdef double sum_x = 0.0, sum_y = 0.0, sum_x2 = 0.0, sum_xy = 0.0, sum_y2 = 0.0
    cdef double mean_x, mean_y, beta, intercept, residual, residual_mean
    cdef double sum_res = 0.0, sum_res2 = 0.0
    cdef double variance_x, variance_y
    cdef double x_val, y_val
    
    # Input validation
    if n < 20:
        return {
            'beta': np.nan,
            'intercept': np.nan,
            'residuals': np.array([]),
            'adf_pvalue': 1.0,
            'is_cointegrated': False,
            'error': 'Insufficient data'
        }
    
    # Check for NaN values (fast loop)
    for i in range(n):
        if isnan(y[i]) or isnan(x[i]):
            return {
                'beta': np.nan,
                'intercept': np.nan,
                'residuals': np.array([]),
                'adf_pvalue': 1.0,
                'is_cointegrated': False,
                'error': 'NaN in data'
            }
    
    # Calculate sums (Cython is fast here)
    for i in range(n):
        x_val = x[i]
        y_val = y[i]
        sum_x += x_val
        sum_y += y_val
        sum_x2 += x_val * x_val
        sum_xy += x_val * y_val
        sum_y2 += y_val * y_val
    
    mean_x = sum_x / n
    mean_y = sum_y / n
    
    # Calculate variances
    variance_x = 0.0
    variance_y = 0.0
    for i in range(n):
        variance_x += (x[i] - mean_x) * (x[i] - mean_x)
        variance_y += (y[i] - mean_y) * (y[i] - mean_y)
    
    variance_x = variance_x / n
    variance_y = variance_y / n
    
    # Check for zero variance
    if variance_x < 1e-10 or variance_y < 1e-10:
        return {
            'beta': np.nan,
            'intercept': np.nan,
            'residuals': np.array([]),
            'adf_pvalue': 1.0,
            'is_cointegrated': False,
            'error': 'Zero variance'
        }
    
    # OLS regression: y = intercept + beta * x
    # beta = cov(x,y) / var(x)
    cdef double cov_xy = 0.0
    for i in range(n):
        cov_xy += (x[i] - mean_x) * (y[i] - mean_y)
    cov_xy = cov_xy / n
    
    beta = cov_xy / variance_x
    intercept = mean_y - beta * mean_x
    
    # Calculate residuals
    cdef np.ndarray[DTYPE_t, ndim=1] residuals = np.zeros(n, dtype=DTYPE)
    for i in range(n):
        residuals[i] = y[i] - (intercept + beta * x[i])
        sum_res += residuals[i]
        sum_res2 += residuals[i] * residuals[i]
    
    # Step 2: ADF test on residuals (via statsmodels for correctness)
    cdef double adf_pvalue = 1.0
    cdef double adf_statistic = 0.0
    cdef bint is_cointegrated = False
    cdef dict critical_values = {}
    cdef str error_msg = None
    
    try:
        adf_result = _adfuller(residuals, regression='c', autolag='AIC')
        adf_statistic = float(adf_result[0])
        adf_pvalue = float(adf_result[1])
        critical_values = adf_result[4]
        is_cointegrated = adf_pvalue < 0.05
    except Exception as exc:
        error_msg = str(exc)[:80]
    
    # Return result in same format as Python version
    return {
        'beta': float(beta),
        'intercept': float(intercept),
        'residuals': residuals,
        'adf_statistic': adf_statistic,
        'adf_pvalue': adf_pvalue,
        'is_cointegrated': is_cointegrated,
        'critical_values': critical_values,
        'error': error_msg
    }

@cython.boundscheck(False)
@cython.wraparound(False)
def half_life_fast(np.ndarray[DTYPE_t, ndim=1] spread) -> int:
    """
    Fast half-life of mean reversion calculation using Cython.
    
    Args:
        spread: Time series of spread values
    
    Returns:
        Half-life in periods, or -1 if invalid
    """
    
    cdef int n = spread.shape[0]
    cdef int i
    cdef double sum_spread_diff = 0.0, sum_spread_lag = 0.0
    cdef double sum_spread_diff_lag = 0.0, sum_spread_lag2 = 0.0
    cdef double sum_spread_diff2 = 0.0
    cdef double spread_diff, spread_lag
    cdef double beta, rho, log_rho, half_life
    cdef int valid_count = 0
    
    if n < 3:
        return -1
    
    # Calculate differences
    for i in range(1, n):
        spread_diff = spread[i] - spread[i-1]
        spread_lag = spread[i-1]
        
        if not isnan(spread_diff) and not isnan(spread_lag) and not isinf(spread_diff) and not isinf(spread_lag):
            sum_spread_diff += spread_diff
            sum_spread_lag += spread_lag
            sum_spread_diff_lag += spread_diff * spread_lag
            sum_spread_lag2 += spread_lag * spread_lag
            sum_spread_diff2 += spread_diff * spread_diff
            valid_count += 1
    
    if valid_count < 2:
        return -1
    
    # OLS: spread_diff = beta_0 + beta_1 * spread_lag
    cdef double mean_lag = sum_spread_lag / valid_count
    cdef double mean_diff = sum_spread_diff / valid_count
    
    cdef double cov = (sum_spread_diff_lag / valid_count) - (mean_diff * mean_lag)
    cdef double var = (sum_spread_lag2 / valid_count) - (mean_lag * mean_lag)
    
    if var < 1e-10:
        return -1
    
    beta = cov / var
    rho = 1.0 + beta  # AR(1) coefficient
    
    # Validate rho
    if rho <= 0.0 or rho >= 1.0 or isnan(rho) or isinf(rho):
        return -1
    
    log_rho = log(rho)
    if isnan(log_rho) or isinf(log_rho) or abs(log_rho) < 1e-10:
        return -1
    
    half_life = -log(2.0) / log_rho
    
    if half_life <= 0 or isnan(half_life) or isinf(half_life):
        return -1
    
    return <int>half_life
