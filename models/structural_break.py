"""
Structural Break Detector ÔÇô Phase 3 (addresses audit ┬º2.4).

Problem
-------
The ``StationarityMonitor`` tests whether the *spread* is stationary, but it
does NOT detect whether the **cointegration relationship itself** has changed.
A spread can appear stationary for a while even after the true ╬▓ / ╬▒ has
shifted (lag between economic breakdown and statistical detection).

Solution
--------
Two complementary tests run on the OLS residuals of the cointegration
regression (y Ôêô ╬▒ Ôêô ╬▓┬Àx):

1. **CUSUM test** (BrownÔÇôDurbinÔÇôEvans, 1975)
   Cumulative sum of recursive residuals.  If the CUSUM path exceeds
   ┬▒(critical_boundary), we flag a structural break.  Fast, O(n).

2. **Recursive ╬▓ stability** (simplified BaiÔÇôPerron flavour)
   Re-estimate ╬▓ on an expanding window and check whether the latest
   ╬▓ differs from the full-sample ╬▓ by more than ``beta_drift_threshold``.
   This catches gradual drift that CUSUM may miss.

Either test flagging Ôåô the pair's cointegration is degraded.

Usage::

    detector = StructuralBreakDetector()

    # Feed the raw cointegration residuals (y - alpha - beta*x)
    has_break, details = detector.check(residuals_series)
    if has_break:
        # close position / flag pair for re-evaluation
        ...

Performance: CUSUM on 252 obs Ôëê 2-5 ms.  Acceptable bar-by-bar.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class StructuralBreakConfig:
    """Configuration for the structural break detector."""

    cusum_significance: float = 0.05
    """Significance level for the CUSUM test (0.05 = 95% confidence).
    Lower values make the test more conservative (fewer false alarms)."""

    min_observations: int = 60
    """Minimum number of residuals before running the test."""

    beta_drift_threshold: float = 0.15
    """Maximum relative change in ╬▓ (recent window vs full sample)
    before flagging instability.  0.15 = 15% drift tolerance."""

    beta_window: int = 60
    """Rolling window for the recent ╬▓ estimate."""

    cusum_trim: float = 0.10
    """Fraction of observations trimmed from start/end of CUSUM path
    to avoid spurious boundary crossings near endpoints."""

    check_interval_bars: int = 5
    """Run CUSUM+beta tests only every N calls (C-07). Between runs, the
    cached result is returned unchanged. Default 5 bars — structural breaks
    are gradual; a 5-bar detection delay is negligible."""


class StructuralBreakDetector:
    """
    Detects structural breaks in the cointegration relationship.

    Combines CUSUM-based residual monitoring with recursive ╬▓ stability
    checks to catch both abrupt and gradual breakdowns.
    """

    def __init__(self, config: StructuralBreakConfig | None = None):
        self.config = config or StructuralBreakConfig()
        self._call_count: int = 0
        self._last_result: tuple[bool, dict[str, Any]] | None = None
        logger.info(
            "structural_break_detector_initialized",
            cusum_significance=self.config.cusum_significance,
            beta_drift_threshold=self.config.beta_drift_threshold,
            check_interval_bars=self.config.check_interval_bars,
        )

    def check(
        self,
        residuals: pd.Series,
        y: pd.Series | None = None,
        x: pd.Series | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """Run structural break tests on cointegration residuals.

        Args:
            residuals: OLS residuals from the cointegration regression
                       (y - alpha - beta*x).
            y: Dependent series (required for β stability check).
            x: Independent series (required for β stability check).

        Returns:
            (has_break, details)

            * ``has_break=True`` if **either** CUSUM or β stability
              flags a structural break.
            * ``details`` dict with sub-test results.
        """
        # C-07: throttle per-instance using call count
        self._call_count += 1
        if self._call_count % self.config.check_interval_bars != 0 and self._last_result is not None:
            return self._last_result

        n = len(residuals)
        details: dict[str, Any] = {
            "n_observations": n,
            "cusum_break": False,
            "beta_break": False,
            "cusum_max_stat": None,
            "cusum_critical": None,
            "beta_drift_pct": None,
        }

        if n < self.config.min_observations:
            return False, details

        # ÔôÇÔôÇ Test 1: CUSUM on recursive residuals ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
        cusum_break, cusum_stat, cusum_crit = self._cusum_test(residuals, y=y, x=x)
        details["cusum_break"] = cusum_break
        details["cusum_max_stat"] = float(cusum_stat)
        details["cusum_critical"] = float(cusum_crit)

        # ÔôÇÔôÇ Test 2: Recursive ╬▓ stability ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
        if y is not None and x is not None and len(y) == n and len(x) == n:
            beta_break, drift_pct = self._beta_stability(y, x)
            details["beta_break"] = beta_break
            details["beta_drift_pct"] = float(drift_pct) if drift_pct is not None else None

        has_break = details["cusum_break"] or details["beta_break"]

        if has_break:
            logger.warning(
                "structural_break_detected",
                cusum_break=details["cusum_break"],
                beta_break=details["beta_break"],
                cusum_stat=details["cusum_max_stat"],
                beta_drift=details["beta_drift_pct"],
            )

        result = has_break, details
        self._last_result = result  # C-07: cache for throttled calls
        return result

    # ÔôÇÔôÇ CUSUM test (BrownÔÇôDurbinÔÇôEvans) ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

    def _cusum_test(
        self,
        residuals: pd.Series,
        y: pd.Series | None = None,
        x: pd.Series | None = None,
    ) -> tuple[bool, float, float]:
        """Compute the CUSUM statistic using proper recursive residuals.

        When *y* and *x* are provided the test uses genuine one-step-ahead
        prediction errors (BrownÔÇôDurbinÔÇôEvans, 1975).  When they are not
        available it falls back to standardised OLS residuals.

        Returns:
            (has_break, max_|cusum_stat|, critical_value)
        """
        vals = np.asarray(residuals, dtype=np.float64)
        n = len(vals)

        # --- Compute recursive (one-step-ahead) residuals ----------------
        if y is not None and x is not None and len(y) == n and len(x) == n:
            ya = np.asarray(y, dtype=np.float64)
            xa = np.asarray(x, dtype=np.float64)
            k = 2  # intercept + slope
            start = max(k + 1, int(n * 0.10))  # need >k obs to start OLS
            rec_resids = []
            for t in range(start, n):
                X_train = np.column_stack([np.ones(t), xa[:t]])
                y_train = ya[:t]
                try:
                    beta_hat, _res, _rank, _sv = np.linalg.lstsq(X_train, y_train, rcond=None)
                except np.linalg.LinAlgError:
                    rec_resids.append(0.0)
                    continue
                y_pred = beta_hat[0] + beta_hat[1] * xa[t]
                rec_resids.append(ya[t] - y_pred)
            vals = np.array(rec_resids, dtype=np.float64)
            n = len(vals)
            if n < 10:
                return False, 0.0, 1.0

        # Standardize residuals
        sigma = np.std(vals, ddof=1)
        if sigma < 1e-14:
            return False, 0.0, 1.0

        std_resid = vals / sigma

        # Cumulative sum
        cusum = np.cumsum(std_resid)

        # Trim boundaries to avoid false alarms at endpoints
        trim = max(1, int(n * self.config.cusum_trim))
        cusum_trimmed = cusum[trim : n - trim]

        if len(cusum_trimmed) == 0:
            return False, 0.0, 1.0

        # Normalize by ÔêÜn for comparison with critical value
        cusum_normalized = cusum_trimmed / np.sqrt(n)

        max_stat = float(np.max(np.abs(cusum_normalized)))

        # Critical value from Brownian bridge approximation
        # At 5% significance: c Ôëê 1.358 (OLS-CUSUM)
        # At 1% significance: c Ôëê 1.628
        critical_values = {
            0.01: 1.628,
            0.05: 1.358,
            0.10: 1.224,
        }
        # Pick closest significance level
        sig = self.config.cusum_significance
        if sig <= 0.01:
            crit = critical_values[0.01]
        elif sig <= 0.05:
            crit = critical_values[0.05]
        else:
            crit = critical_values[0.10]

        has_break = max_stat > crit

        return has_break, max_stat, crit

    # ÔôÇÔôÇ Recursive ╬▓ stability ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

    def _beta_stability(self, y: pd.Series, x: pd.Series) -> tuple[bool, float | None]:
        """Check whether recent ╬▓ diverges from full-sample ╬▓.

        Estimates ╬▓ on the full sample and on the last ``beta_window``
        observations.  Flags instability if the relative change exceeds
        ``beta_drift_threshold``.

        Returns:
            (has_break, drift_pct)
        """
        try:
            yv = np.asarray(y, dtype=np.float64)
            xv = np.asarray(x, dtype=np.float64)
            n = len(yv)

            if n < self.config.beta_window + 10:
                return False, None

            # Full-sample OLS ╬▓
            X_full = np.column_stack([np.ones(n), xv])
            beta_full = np.linalg.lstsq(X_full, yv, rcond=None)[0]

            # Recent-window OLS ╬▓
            w = self.config.beta_window
            X_recent = np.column_stack([np.ones(w), xv[-w:]])
            beta_recent = np.linalg.lstsq(X_recent, yv[-w:], rcond=None)[0]

            # Relative drift on the slope coefficient (index 1)
            if abs(beta_full[1]) < 1e-10:
                return False, None

            drift_pct = abs(beta_recent[1] - beta_full[1]) / abs(beta_full[1])
            has_break = drift_pct > self.config.beta_drift_threshold

            return has_break, drift_pct

        except Exception as e:
            logger.warning("beta_stability_check_failed", error=str(e))
            return False, None

    # ÔôÇÔôÇ Convenience: full pipeline on price series ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

    def check_from_prices(self, y: pd.Series, x: pd.Series) -> tuple[bool, dict[str, Any]]:
        """Run structural break detection directly from price series.

        Estimates the cointegration regression internally and tests the
        residuals.

        Args:
            y: Dependent price series.
            x: Independent price series.

        Returns:
            (has_break, details) ÔÇô same as ``check()``.
        """
        yv = np.asarray(y, dtype=np.float64)
        xv = np.asarray(x, dtype=np.float64)
        n = len(yv)

        if n < self.config.min_observations:
            return False, {"n_observations": n, "cusum_break": False, "beta_break": False}

        # OLS regression
        X = np.column_stack([np.ones(n), xv])
        beta = np.linalg.lstsq(X, yv, rcond=None)[0]
        residuals = yv - X @ beta

        return self.check(pd.Series(residuals, index=y.index), y=y, x=x)
