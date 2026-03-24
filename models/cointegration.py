from typing import Any, cast

import numpy as np
import pandas as pd
from scipy.linalg import LinAlgError
from statsmodels.tsa.stattools import adfuller, kpss
from structlog import get_logger

logger = get_logger(__name__)

# Try to load Cython acceleration for cointegration testing
try:
    from models.cointegration_fast import engle_granger_fast as _engle_granger_fast

    CYTHON_COINTEGRATION_AVAILABLE = True
    logger.info("Cython cointegration engine loaded - hybrid acceleration enabled")
except ImportError as e:
    CYTHON_COINTEGRATION_AVAILABLE = False
    logger.warning(
        "cython_extension_missing_using_python_fallback",
        module="models.cointegration_fast",
        error=str(e),
        impact="10x slower cointegration tests — recompile with: python setup.py build_ext --inplace",
    )


def verify_integration_order(
    series: pd.Series,
    name: str | None = None,
) -> dict[str, Any]:
    """
    Verify that a time series is integrated of order 1 (I(1)).

    Uses ADF on levels (should fail to reject => non-stationary),
    KPSS on levels (should reject => non-stationary),
    and ADF on first differences (should reject => stationary after differencing).

    Args:
        series: The time series to test.
        name: Optional label for the series.

    Returns:
        Dict with keys: series_name, is_I1, adf_level_pvalue,
        kpss_level_pvalue, adf_diff_pvalue, error.
    """
    result: dict[str, Any] = {
        "series_name": name,
        "is_I1": False,
        "adf_level_pvalue": np.nan,
        "kpss_level_pvalue": np.nan,
        "adf_diff_pvalue": np.nan,
        "error": None,
    }

    # Clean NaN ÔÇö handle both pd.Series and np.ndarray
    if hasattr(series, "dropna"):
        s = series.dropna()
    else:
        s = pd.Series(series).dropna()

    if len(s) < 20:
        result["error"] = "Insufficient data for integration order test"
        return result

    # Constant / zero-variance guard
    if s.std() < 1e-10:
        result["error"] = None  # no crash, but clearly not I(1)
        result["adf_level_pvalue"] = 0.0
        result["kpss_level_pvalue"] = 1.0
        result["adf_diff_pvalue"] = 0.0
        return result

    try:
        import warnings as _w

        arr = np.asarray(s, dtype=np.float64)

        # ADF on levels
        adf_level = adfuller(arr, regression="c", autolag="AIC")
        result["adf_level_pvalue"] = float(adf_level[1])

        # KPSS on levels (suppress FutureWarning about nlags)
        with _w.catch_warnings():
            _w.simplefilter("ignore")
            kpss_level = kpss(arr, regression="c", nlags="auto")
        result["kpss_level_pvalue"] = float(kpss_level[1])

        # ADF on first differences
        diff = np.diff(arr)
        adf_diff = adfuller(diff, regression="c", autolag="AIC")
        result["adf_diff_pvalue"] = float(adf_diff[1])

        # Decision logic:
        #   I(1) <=> level is non-stationary AND differenced is stationary
        #   ADF level p-value HIGH (fail to reject unit root)  => non-stationary
        #   ADF diff  p-value LOW  (reject unit root)          => stationary after diff
        level_nonstationary = result["adf_level_pvalue"] > 0.05
        diff_stationary = result["adf_diff_pvalue"] < 0.05

        result["is_I1"] = bool(level_nonstationary and diff_stationary)

    except Exception as exc:
        result["error"] = str(exc)[:120]

    return result


def engle_granger_test(
    y: pd.Series,
    x: pd.Series,
    max_lags: int = 12,
    regression: str = "c",
    check_integration_order: bool = True,
    apply_bonferroni: bool = False,
    num_symbols: int | None = None,
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
    # ÔöÇÔöÇ I(1) pre-check gate ÔöÇÔöÇ
    if check_integration_order:
        io_y = verify_integration_order(y, name="y")
        io_x = verify_integration_order(x, name="x")
        if not io_y["is_I1"] or not io_x["is_I1"]:
            failed = []
            if not io_y["is_I1"]:
                failed.append("y")
            if not io_x["is_I1"]:
                failed.append("x")
            return {
                "beta": np.nan,
                "intercept": np.nan,
                "residuals": np.array([]),
                "adf_statistic": np.nan,
                "adf_pvalue": 1.0,
                "is_cointegrated": False,
                "critical_values": {},
                "error": f"Series not I(1): {', '.join(failed)}",
                "integration_order": {"y": io_y, "x": io_x},
            }

    # Ensure pandas Series for consistent API
    if not isinstance(y, pd.Series):
        y = pd.Series(y)
    if not isinstance(x, pd.Series):
        x = pd.Series(x)

    # Input validation
    if len(y) < 20 or len(x) < 20:
        return {
            "beta": np.nan,
            "intercept": np.nan,
            "residuals": np.array([]),
            "adf_statistic": np.nan,
            "adf_pvalue": 1.0,  # Not significant
            "is_cointegrated": False,
            "critical_values": {},
            "error": "Insufficient data",
        }

    # Check for NaN values
    if y.isna().any() or x.isna().any():
        return {
            "beta": np.nan,
            "intercept": np.nan,
            "residuals": np.array([]),
            "adf_statistic": np.nan,
            "adf_pvalue": 1.0,
            "is_cointegrated": False,
            "critical_values": {},
            "error": "NaN values in data",
        }

    # Check for zero or near-zero variance
    if x.std() < 1e-10 or y.std() < 1e-10:
        return {
            "beta": np.nan,
            "intercept": np.nan,
            "residuals": np.array([]),
            "adf_statistic": np.nan,
            "adf_pvalue": 1.0,
            "is_cointegrated": False,
            "critical_values": {},
            "error": "Zero variance in data",
        }

    try:
        # ÔöÇÔöÇ Cython-accelerated path ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        if CYTHON_COINTEGRATION_AVAILABLE:
            y_arr = y.values.astype(np.float64)
            x_arr = x.values.astype(np.float64)
            cy_result = _engle_granger_fast(y_arr, x_arr)

            if cy_result.get("error"):
                # Cython hit an edge case ÔÇö fall through to pure Python
                pass
            else:
                coint_pvalue = cy_result["adf_pvalue"]

                # Bonferroni correction
                alpha = 0.05
                n_pairs = 1
                if apply_bonferroni and num_symbols and num_symbols > 1:
                    n_pairs = num_symbols * (num_symbols - 1) // 2
                    alpha = 0.05 / max(n_pairs, 1)
                is_cointegrated = coint_pvalue < alpha

                result = {
                    "beta": cy_result["beta"],
                    "intercept": cy_result["intercept"],
                    "residuals": cy_result["residuals"],
                    "adf_statistic": cy_result.get("adf_statistic", np.nan),
                    "adf_pvalue": coint_pvalue,
                    "is_cointegrated": is_cointegrated,
                    "critical_values": cy_result.get("critical_values", {}),
                    "alpha_threshold": alpha,
                    "num_pairs": n_pairs,
                }

                logger.info(
                    "eg_test_complete",
                    coint_pvalue=coint_pvalue,
                    is_cointegrated=is_cointegrated,
                )
                return result

        # ÔöÇÔöÇ Pure-Python fallback ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        # Normalize data to improve numerical stability
        x_normalized = (x - x.mean()) / x.std()
        y_normalized = (y - y.mean()) / y.std()
        x_norm_arr = np.asarray(x_normalized, dtype=float)
        y_norm_arr = np.asarray(y_normalized, dtype=float)

        # Step 1: OLS regression with proper error handling
        X = np.column_stack([np.ones(len(x_norm_arr)), x_norm_arr])

        # Check condition number to detect ill-conditioned matrices
        cond_number = np.linalg.cond(X)
        if cond_number > 1e10:  # Matrix is ill-conditioned
            return {
                "beta": np.nan,
                "intercept": np.nan,
                "residuals": np.array([]),
                "adf_statistic": np.nan,
                "adf_pvalue": 1.0,
                "is_cointegrated": False,
                "critical_values": {},
                "error": f"Ill-conditioned matrix (condition number: {cond_number:.2e})",
            }

        beta = np.linalg.lstsq(X, y_norm_arr, rcond=None)[0]

        # De-normalize to raw price scale
        y_std, x_std = float(y.std()), float(x.std())
        y_mean, x_mean = float(y.mean()), float(x.mean())
        beta_raw = beta[1] * (y_std / x_std) if x_std > 1e-15 else beta[1]
        alpha_raw = y_mean - beta_raw * x_mean

        # STAT-3: Recalculate residuals on RAW data using de-normalized
        # coefficients so that the ADF test operates in the same space
        # as the Cython path and downstream SpreadModel consumers.
        residuals = y.values - (alpha_raw + beta_raw * x.values)

        # Check for NaN in residuals
        if np.isnan(residuals).any() or np.isinf(residuals).any():
            return {
                "beta": np.nan,
                "intercept": np.nan,
                "residuals": np.array([]),
                "adf_statistic": np.nan,
                "adf_pvalue": 1.0,
                "is_cointegrated": False,
                "critical_values": {},
                "error": "Invalid residuals (NaN or Inf)",
            }

        # Step 2: ADF test on residuals with error handling
        try:
            adf_result = cast(
                tuple[float, float, int, int, dict[str, float]],
                adfuller(residuals, regression=regression, maxlag=max_lags, autolag="AIC"),
            )
        except (LinAlgError, ValueError) as e:
            return {
                "beta": beta_raw,
                "intercept": alpha_raw,
                "residuals": residuals,
                "adf_statistic": np.nan,
                "adf_pvalue": 1.0,
                "is_cointegrated": False,
                "critical_values": {},
                "error": f"ADF test failed: {str(e)[:50]}",
            }

        coint_score = adf_result[0]
        coint_pvalue = adf_result[1]

        # Bonferroni correction
        alpha = 0.05
        n_pairs = 1
        if apply_bonferroni and num_symbols and num_symbols > 1:
            n_pairs = num_symbols * (num_symbols - 1) // 2
            alpha = 0.05 / max(n_pairs, 1)
        is_cointegrated = coint_pvalue < alpha

        result = {
            "beta": beta_raw,
            "intercept": alpha_raw,
            "residuals": residuals,
            "adf_statistic": coint_score,
            "adf_pvalue": coint_pvalue,
            "is_cointegrated": is_cointegrated,
            "critical_values": dict(adf_result[4]),
            "alpha_threshold": alpha,
            "num_pairs": n_pairs,
        }

    except Exception as e:
        logger.error("engle_granger_test_exception", error=str(e)[:100])
        return {
            "beta": np.nan,
            "intercept": np.nan,
            "residuals": np.array([]),
            "adf_statistic": np.nan,
            "adf_pvalue": 1.0,
            "is_cointegrated": False,
            "critical_values": {},
            "error": str(e)[:50],
        }

    logger.info("eg_test_complete", coint_pvalue=coint_pvalue, is_cointegrated=is_cointegrated)

    return result


def engle_granger_test_cpp_optimized(
    y: pd.Series,
    x: pd.Series,
    max_lags: int = 12,
    regression: str = "c",
    check_integration_order: bool = True,
    apply_bonferroni: bool = False,
    num_symbols: int | None = None,
) -> dict:
    """
    Optimized Engle-Granger test using Cython acceleration if available.
    Falls back to pure Python implementation otherwise.

    The Cython path accelerates OLS regression in C and delegates
    the ADF test to statsmodels for correctness ÔÇö a true hybrid approach.

    Args:
        y: Dependent series
        x: Independent series
        max_lags: Max lags for error correction term
        regression: Regression type ("c", "ct", "ctt")
        check_integration_order: If True, verify both series are I(1) first

    Returns:
        Dictionary with test results (same format as engle_granger_test)
    """
    # engle_granger_test already uses Cython internally when available
    return engle_granger_test(
        y,
        x,
        max_lags,
        regression,
        check_integration_order,
        apply_bonferroni,
        num_symbols,
    )


def engle_granger_test_robust(
    y: pd.Series,
    x: pd.Series,
    max_lags: int = 12,
    regression: str = "c",
    apply_bonferroni: bool = False,
    num_symbols: int | None = None,
    hac_maxlags: int | None = None,
) -> dict:
    """
    Engle-Granger cointegration test with Newey-West HAC robust standard errors.

    Same two-step procedure as :func:`engle_granger_test` but uses
    Newey-West HAC covariance estimator so that inference on the
    cointegrating regression coefficients is robust to serial-correlation
    and heteroskedasticity.

    Args:
        y: Dependent series.
        x: Independent series.
        max_lags: Max lags for ADF on residuals.
        regression: ADF regression type ("c", "ct", "ctt").
        apply_bonferroni: Adjust alpha for multiple comparisons.
        num_symbols: Number of symbols (used for Bonferroni).
        hac_maxlags: Override Newey-West bandwidth (default: auto).

    Returns:
        Dictionary with test results including HAC standard errors.
    """
    import statsmodels.api as sm

    def _err(msg):
        return {
            "beta": np.nan,
            "intercept": np.nan,
            "residuals": np.array([]),
            "adf_statistic": np.nan,
            "adf_pvalue": 1.0,
            "is_cointegrated": False,
            "critical_values": {},
            "hac_bse": np.array([np.nan, np.nan]),
            "hac_tvalues": np.array([np.nan, np.nan]),
            "hac_pvalues": np.array([np.nan, np.nan]),
            "beta_hac_pvalue": np.nan,
            "alpha_threshold": 0.05,
            "error": msg,
        }

    # ÔöÇÔöÇ input validation ÔöÇÔöÇ
    if len(y) < 30 or len(x) < 30:
        return _err("Insufficient data (need >= 30 obs)")
    if y.isna().any() or x.isna().any():
        return _err("NaN values in data")
    if x.std() < 1e-10 or y.std() < 1e-10:
        return _err("Zero variance in data")

    try:
        y_arr = y.values.astype(np.float64)
        x_arr = x.values.astype(np.float64)
        X = sm.add_constant(x_arr)

        # HAC (Newey-West) OLS
        ols = sm.OLS(y_arr, X).fit(
            cov_type="HAC",
            cov_kwds={"maxlags": hac_maxlags} if hac_maxlags else {"maxlags": None},
        )

        residuals = ols.resid
        beta_val = float(ols.params[1])
        intercept_val = float(ols.params[0])

        # ADF on residuals
        try:
            adf_res = cast(
                tuple[float, float, int, int, dict[str, float]],
                adfuller(residuals, regression=regression, maxlag=max_lags, autolag="AIC"),
            )
        except (LinAlgError, ValueError) as e:
            return _err(f"ADF test failed: {str(e)[:50]}")

        coint_pvalue = float(adf_res[1])
        coint_stat = float(adf_res[0])

        # Bonferroni
        alpha = 0.05
        if apply_bonferroni and num_symbols and num_symbols > 1:
            n_pairs = num_symbols * (num_symbols - 1) // 2
            alpha = 0.05 / max(n_pairs, 1)

        return {
            "beta": beta_val,
            "intercept": intercept_val,
            "residuals": residuals,
            "adf_statistic": coint_stat,
            "adf_pvalue": coint_pvalue,
            "is_cointegrated": coint_pvalue < alpha,
            "critical_values": dict(adf_res[4]),
            "hac_bse": ols.bse,
            "hac_tvalues": ols.tvalues,
            "hac_pvalues": ols.pvalues,
            "beta_hac_pvalue": float(ols.pvalues[1]),
            "alpha_threshold": alpha,
            "error": None,
        }

    except Exception as exc:
        logger.error("eg_robust_exception", error=str(exc)[:100])
        return _err(str(exc)[:80])


def newey_west_consensus(
    y: pd.Series,
    x: pd.Series,
    apply_bonferroni: bool = False,
    num_symbols: int | None = None,
    hac_maxlags: int | None = None,
) -> dict:
    """
    Run both standard and HAC-robust Engle-Granger tests and report consensus.

    Returns:
        Dict with consensus, standard_cointegrated, robust_cointegrated,
        divergent flags, plus both sub-results.
    """
    r_std = engle_granger_test(
        y,
        x,
        apply_bonferroni=apply_bonferroni,
        num_symbols=num_symbols,
        check_integration_order=False,
    )
    r_rob = engle_granger_test_robust(
        y,
        x,
        apply_bonferroni=apply_bonferroni,
        num_symbols=num_symbols,
        hac_maxlags=hac_maxlags,
    )

    std_coint = bool(r_std.get("is_cointegrated", False))
    rob_coint = bool(r_rob.get("is_cointegrated", False))

    return {
        "consensus": std_coint and rob_coint,
        "standard_cointegrated": std_coint,
        "robust_cointegrated": rob_coint,
        "divergent": std_coint != rob_coint,
        "standard_result": r_std,
        "robust_result": r_rob,
    }


def half_life_mean_reversion(spread: pd.Series, _max_lag: int = 60) -> int | None:
    """
    Estimate half-life of mean reversion.

    Uses the Cython ``half_life_fast`` kernel when available, falling back to
    :class:`SpreadHalfLifeEstimator` otherwise.

    Args:
        spread: Spread time series.
        _max_lag: Reserved for backwards compatibility — not forwarded to estimator.

    Returns:
        Half-life in periods (int), or None if not mean-reverting.
    """
    from models.half_life_estimator import SpreadHalfLifeEstimator

    estimator = SpreadHalfLifeEstimator(lookback=min(252, len(spread)))
    hl = estimator.estimate_half_life_from_spread(spread, validate=True)
    if hl is None:
        return None
    return int(np.round(hl))


def is_cointegration_stable(
    sym1: str,
    sym2: str,
    price_data,
    windows: list[int] | None = None,
    threshold: float = 0.8,
) -> bool:
    """
    Check cointegration stability for a pair over multiple rolling windows.

    Returns ``True`` if the pair is cointegrated in at least *threshold*
    fraction of the rolling windows tested.

    Args:
        sym1: First symbol name (column in *price_data*).
        sym2: Second symbol name (column in *price_data*).
        price_data: Mapping / DataFrame of price series keyed by symbol.
        windows: Rolling window sizes in bars. Defaults to ``[60, 120, 180]``.
        threshold: Minimum fraction of windows that must show cointegration.

    Returns:
        ``True`` if sufficiently stable, ``False`` otherwise.
    """
    if windows is None:
        windows = [60, 120, 180]
    stable_count = 0
    total = 0
    for win in windows:
        if len(price_data[sym1]) < win or len(price_data[sym2]) < win:
            continue
        y = price_data[sym1].tail(win)
        x = price_data[sym2].tail(win)
        result = engle_granger_test(y, x, apply_bonferroni=False, check_integration_order=False)
        if result.get("is_cointegrated", False):
            stable_count += 1
        total += 1
    if total == 0:
        return False
    return stable_count / total >= threshold
