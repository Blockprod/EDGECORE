"""
Sprint 4.1 – Johansen multi-variate cointegration test.

Complements Engle-Granger (bivariate) with:
- Cointegration rank detection (how many linear relationships)
- Multi-variable systems (>2 variables)
- More powerful for small samples

Usage:
    jt = JohansenCointegrationTest()
    result = jt.test(pd.DataFrame({'A': seriesA, 'B': seriesB}))
    if result['is_cointegrated']:
        print(f"Rank: {result['rank']}")
"""

import pandas as pd
from typing import Optional
from structlog import get_logger

logger = get_logger(__name__)


class JohansenCointegrationTest:
    """
    Johansen cointegration test for detecting multi-variate
    cointegration relationships.

    Complements Engle-Granger (bivariate):
    - Detects cointegration rank (number of linear relationships)
    - Supports systems of more than 2 variables
    - More powerful than EG for small samples

    Parameters:
        det_order: Deterministic term order.
            -1 = no deterministic terms
             0 = constant (restricted to cointegration space)
             1 = linear trend
        k_ar_diff: Number of lagged differences in the VECM.
    """

    def __init__(
        self,
        det_order: int = 0,
        k_ar_diff: int = 1,
        significance_level: float = 0.05,
    ):
        self.det_order = det_order
        self.k_ar_diff = k_ar_diff
        self.significance_level = significance_level

    def test(
        self,
        data: pd.DataFrame,
        det_order: Optional[int] = None,
        k_ar_diff: Optional[int] = None,
    ) -> dict:
        """
        Run the Johansen cointegration test on a multivariate dataset.

        Args:
            data: DataFrame where each column is a price series.
                  Minimum 2 columns, minimum 20 rows.
            det_order: Override instance det_order (optional).
            k_ar_diff: Override instance k_ar_diff (optional).

        Returns:
            dict with keys:
                rank: int – estimated cointegration rank (0 = none)
                trace_statistics: list[float] – trace test statistics
                trace_critical_values: dict – {90, 95, 99} critical values
                max_eig_statistics: list[float] – max-eigenvalue statistics
                max_eig_critical_values: dict – {90, 95, 99} critical values
                eigenvectors: list[list[float]] – cointegrating vectors
                eigenvalues: list[float] – eigenvalues
                is_cointegrated: bool – True if rank >= 1
                error: str or None – error message if test failed
        """
        det_order = det_order if det_order is not None else self.det_order
        k_ar_diff = k_ar_diff if k_ar_diff is not None else self.k_ar_diff

        # --- Input validation ---
        if not isinstance(data, pd.DataFrame):
            return self._error_result("Input must be a pandas DataFrame")

        if data.shape[1] < 2:
            return self._error_result(
                f"Need at least 2 columns, got {data.shape[1]}"
            )

        min_rows = max(20, 2 * k_ar_diff + data.shape[1] + 5)
        if len(data) < min_rows:
            return self._error_result(
                f"Need at least {min_rows} rows, got {len(data)}"
            )

        if data.isna().any().any():
            return self._error_result("Data contains NaN values")

        if (data.std() < 1e-10).any():
            return self._error_result(
                "One or more series have near-zero variance"
            )

        # --- Run Johansen test ---
        try:
            from statsmodels.tsa.vector_ar.vecm import coint_johansen

            result = coint_johansen(
                data.values, det_order=det_order, k_ar_diff=k_ar_diff
            )
        except Exception as e:
            logger.error("johansen_test_failed", error=str(e)[:200])
            return self._error_result(f"Johansen test failed: {str(e)[:100]}")

        # --- Extract results ---
        trace_stat = result.lr1          # Trace statistics
        trace_crit = result.cvt          # Trace critical values (90%, 95%, 99%)
        max_eig_stat = result.lr2        # Max eigenvalue statistics
        max_eig_crit = result.cvm        # Max-eig critical values (90%, 95%, 99%)

        # Map significance level to critical value column index
        # cvt columns: 90%, 95%, 99%
        sig_map = {0.10: 0, 0.05: 1, 0.01: 2}
        cv_idx = sig_map.get(self.significance_level, 1)  # default 95%

        # --- Determine cointegration rank (trace test) ---
        trace_rank = 0
        for i in range(len(trace_stat)):
            if trace_stat[i] > trace_crit[i, cv_idx]:
                trace_rank += 1
            else:
                break

        # --- Determine cointegration rank (max-eigenvalue test) ---
        max_eig_rank = 0
        for i in range(len(max_eig_stat)):
            if max_eig_stat[i] > max_eig_crit[i, cv_idx]:
                max_eig_rank += 1
            else:
                break

        # Use the more conservative rank (min of trace and max-eig)
        rank = min(trace_rank, max_eig_rank)

        output = {
            "rank": rank,
            "trace_rank": trace_rank,
            "max_eig_rank": max_eig_rank,
            "trace_statistics": trace_stat.tolist(),
            "trace_critical_values": {
                "90": trace_crit[:, 0].tolist(),
                "95": trace_crit[:, 1].tolist(),
                "99": trace_crit[:, 2].tolist(),
            },
            "max_eig_statistics": max_eig_stat.tolist(),
            "max_eig_critical_values": {
                "90": max_eig_crit[:, 0].tolist(),
                "95": max_eig_crit[:, 1].tolist(),
                "99": max_eig_crit[:, 2].tolist(),
            },
            "eigenvectors": result.evec.tolist(),
            "eigenvalues": result.eig.tolist(),
            "is_cointegrated": rank >= 1,
            "significance_level": self.significance_level,
            "error": None,
        }

        logger.info(
            "johansen_test_complete",
            n_series=data.shape[1],
            n_obs=len(data),
            rank=rank,
            trace_rank=trace_rank,
            max_eig_rank=max_eig_rank,
            is_cointegrated=rank >= 1,
        )

        return output

    @staticmethod
    def _error_result(error_msg: str) -> dict:
        """Return a standardized error result."""
        logger.warning("johansen_test_error", error=error_msg)
        return {
            "rank": 0,
            "trace_rank": 0,
            "max_eig_rank": 0,
            "trace_statistics": [],
            "trace_critical_values": {},
            "max_eig_statistics": [],
            "max_eig_critical_values": {},
            "eigenvectors": [],
            "eigenvalues": [],
            "is_cointegrated": False,
            "significance_level": 0.05,
            "error": error_msg,
        }


def johansen_confirm_pair(
    y: pd.Series,
    x: pd.Series,
    det_order: int = 0,
    k_ar_diff: int = 1,
    significance_level: float = 0.05,
) -> dict:
    """
    Convenience function: confirm a bivariate pair with Johansen.

    Use after Engle-Granger passes to double-validate.

    Args:
        y: First price series
        x: Second price series
        det_order: Deterministic term order
        k_ar_diff: Number of lagged differences
        significance_level: Significance level (default 0.05)

    Returns:
        dict with Johansen test results (same as JohansenCointegrationTest.test)
    """
    data = pd.DataFrame({"y": y.values, "x": x.values})
    jt = JohansenCointegrationTest(
        det_order=det_order,
        k_ar_diff=k_ar_diff,
        significance_level=significance_level,
    )
    return jt.test(data)
