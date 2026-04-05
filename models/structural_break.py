<<<<<<< HEAD
﻿"""
Structural Break Detector ÔÇô Phase 3 (addresses audit ┬º2.4).
=======
"""
Structural Break Detector – Phase 3 (addresses audit §2.4).
>>>>>>> origin/main

Problem
-------
The ``StationarityMonitor`` tests whether the *spread* is stationary, but it
does NOT detect whether the **cointegration relationship itself** has changed.
<<<<<<< HEAD
A spread can appear stationary for a while even after the true ╬▓ / ╬▒ has
=======
A spread can appear stationary for a while even after the true β / α has
>>>>>>> origin/main
shifted (lag between economic breakdown and statistical detection).

Solution
--------
Two complementary tests run on the OLS residuals of the cointegration
<<<<<<< HEAD
regression (y Ôêô ╬▒ Ôêô ╬▓┬Àx):

1. **CUSUM test** (BrownÔÇôDurbinÔÇôEvans, 1975)
   Cumulative sum of recursive residuals.  If the CUSUM path exceeds
   ┬▒(critical_boundary), we flag a structural break.  Fast, O(n).

2. **Recursive ╬▓ stability** (simplified BaiÔÇôPerron flavour)
   Re-estimate ╬▓ on an expanding window and check whether the latest
   ╬▓ differs from the full-sample ╬▓ by more than ``beta_drift_threshold``.
   This catches gradual drift that CUSUM may miss.

Either test flagging Ôåô the pair's cointegration is degraded.
=======
regression (y ∓ α ∓ β·x):

1. **CUSUM test** (Brown–Durbin–Evans, 1975)
   Cumulative sum of recursive residuals.  If the CUSUM path exceeds
   ±(critical_boundary), we flag a structural break.  Fast, O(n).

2. **Recursive β stability** (simplified Bai–Perron flavour)
   Re-estimate β on an expanding window and check whether the latest
   β differs from the full-sample β by more than ``beta_drift_threshold``.
   This catches gradual drift that CUSUM may miss.

Either test flagging ↓ the pair's cointegration is degraded.
>>>>>>> origin/main

Usage::

    detector = StructuralBreakDetector()

    # Feed the raw cointegration residuals (y - alpha - beta*x)
    has_break, details = detector.check(residuals_series)
    if has_break:
        # close position / flag pair for re-evaluation
        ...

<<<<<<< HEAD
Performance: CUSUM on 252 obs Ôëê 2-5 ms.  Acceptable bar-by-bar.
"""

from dataclasses import dataclass
from typing import Any
=======
Performance: CUSUM on 252 obs ≈ 2-5 ms.  Acceptable bar-by-bar.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
>>>>>>> origin/main

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
<<<<<<< HEAD
    """Maximum relative change in ╬▓ (recent window vs full sample)
    before flagging instability.  0.15 = 15% drift tolerance."""

    beta_window: int = 60
    """Rolling window for the recent ╬▓ estimate."""
=======
    """Maximum relative change in β (recent window vs full sample)
    before flagging instability.  0.15 = 15% drift tolerance."""

    beta_window: int = 60
    """Rolling window for the recent β estimate."""
>>>>>>> origin/main

    cusum_trim: float = 0.10
    """Fraction of observations trimmed from start/end of CUSUM path
    to avoid spurious boundary crossings near endpoints."""

<<<<<<< HEAD
    check_interval_bars: int = 5
    """Run CUSUM+beta tests only every N calls (C-07). Between runs, the
    cached result is returned unchanged. Default 5 bars — structural breaks
    are gradual; a 5-bar detection delay is negligible."""

=======
>>>>>>> origin/main

class StructuralBreakDetector:
    """
    Detects structural breaks in the cointegration relationship.

<<<<<<< HEAD
    Combines CUSUM-based residual monitoring with recursive ╬▓ stability
    checks to catch both abrupt and gradual breakdowns.
    """

    def __init__(self, config: StructuralBreakConfig | None = None):
        self.config = config or StructuralBreakConfig()
        self._call_count: int = 0
        self._last_result: tuple[bool, dict[str, Any]] | None = None
=======
    Combines CUSUM-based residual monitoring with recursive β stability
    checks to catch both abrupt and gradual breakdowns.
    """

    def __init__(self, config: Optional[StructuralBreakConfig] = None):
        self.config = config or StructuralBreakConfig()
>>>>>>> origin/main
        logger.info(
            "structural_break_detector_initialized",
            cusum_significance=self.config.cusum_significance,
            beta_drift_threshold=self.config.beta_drift_threshold,
<<<<<<< HEAD
            check_interval_bars=self.config.check_interval_bars,
=======
>>>>>>> origin/main
        )

    def check(
        self,
        residuals: pd.Series,
<<<<<<< HEAD
        y: pd.Series | None = None,
        x: pd.Series | None = None,
    ) -> tuple[bool, dict[str, Any]]:
=======
        y: Optional[pd.Series] = None,
        x: Optional[pd.Series] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
>>>>>>> origin/main
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
<<<<<<< HEAD
        # C-07: throttle per-instance using call count
        self._call_count += 1
        if self._call_count % self.config.check_interval_bars != 0 and self._last_result is not None:
            return self._last_result

        n = len(residuals)
        details: dict[str, Any] = {
=======
        n = len(residuals)
        details: Dict[str, Any] = {
>>>>>>> origin/main
            "n_observations": n,
            "cusum_break": False,
            "beta_break": False,
            "cusum_max_stat": None,
            "cusum_critical": None,
            "beta_drift_pct": None,
        }

        if n < self.config.min_observations:
            return False, details

<<<<<<< HEAD
        # ÔôÇÔôÇ Test 1: CUSUM on recursive residuals ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
=======
        # ⓀⓀ Test 1: CUSUM on recursive residuals ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
>>>>>>> origin/main
        cusum_break, cusum_stat, cusum_crit = self._cusum_test(residuals, y=y, x=x)
        details["cusum_break"] = cusum_break
        details["cusum_max_stat"] = float(cusum_stat)
        details["cusum_critical"] = float(cusum_crit)

<<<<<<< HEAD
        # ÔôÇÔôÇ Test 2: Recursive ╬▓ stability ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
=======
        # ⓀⓀ Test 2: Recursive β stability ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ
>>>>>>> origin/main
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

<<<<<<< HEAD
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
=======
        return has_break, details

    # ⓀⓀ CUSUM test (Brown–Durbin–Evans) ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ

    def _cusum_test(
        self, residuals: pd.Series,
        y: Optional[pd.Series] = None,
        x: Optional[pd.Series] = None,
    ) -> Tuple[bool, float, float]:
        """Compute the CUSUM statistic using proper recursive residuals.

        When *y* and *x* are provided the test uses genuine one-step-ahead
        prediction errors (Brown–Durbin–Evans, 1975).  When they are not
>>>>>>> origin/main
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
<<<<<<< HEAD
        cusum_trimmed = cusum[trim : n - trim]
=======
        cusum_trimmed = cusum[trim: n - trim]
>>>>>>> origin/main

        if len(cusum_trimmed) == 0:
            return False, 0.0, 1.0

<<<<<<< HEAD
        # Normalize by ÔêÜn for comparison with critical value
=======
        # Normalize by √n for comparison with critical value
>>>>>>> origin/main
        cusum_normalized = cusum_trimmed / np.sqrt(n)

        max_stat = float(np.max(np.abs(cusum_normalized)))

        # Critical value from Brownian bridge approximation
<<<<<<< HEAD
        # At 5% significance: c Ôëê 1.358 (OLS-CUSUM)
        # At 1% significance: c Ôëê 1.628
=======
        # At 5% significance: c ≈ 1.358 (OLS-CUSUM)
        # At 1% significance: c ≈ 1.628
>>>>>>> origin/main
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

<<<<<<< HEAD
    # ÔôÇÔôÇ Recursive ╬▓ stability ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

    def _beta_stability(self, y: pd.Series, x: pd.Series) -> tuple[bool, float | None]:
        """Check whether recent ╬▓ diverges from full-sample ╬▓.

        Estimates ╬▓ on the full sample and on the last ``beta_window``
=======
    # ⓀⓀ Recursive β stability ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ

    def _beta_stability(
        self, y: pd.Series, x: pd.Series
    ) -> Tuple[bool, Optional[float]]:
        """Check whether recent β diverges from full-sample β.

        Estimates β on the full sample and on the last ``beta_window``
>>>>>>> origin/main
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

<<<<<<< HEAD
            # Full-sample OLS ╬▓
            X_full = np.column_stack([np.ones(n), xv])
            beta_full = np.linalg.lstsq(X_full, yv, rcond=None)[0]

            # Recent-window OLS ╬▓
=======
            # Full-sample OLS β
            X_full = np.column_stack([np.ones(n), xv])
            beta_full = np.linalg.lstsq(X_full, yv, rcond=None)[0]

            # Recent-window OLS β
>>>>>>> origin/main
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

<<<<<<< HEAD
    # ÔôÇÔôÇ Convenience: full pipeline on price series ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

    def check_from_prices(self, y: pd.Series, x: pd.Series) -> tuple[bool, dict[str, Any]]:
=======
    # ⓀⓀ Convenience: full pipeline on price series ⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀⓀ

    def check_from_prices(
        self, y: pd.Series, x: pd.Series
    ) -> Tuple[bool, Dict[str, Any]]:
>>>>>>> origin/main
        """Run structural break detection directly from price series.

        Estimates the cointegration regression internally and tests the
        residuals.

        Args:
            y: Dependent price series.
            x: Independent price series.

        Returns:
<<<<<<< HEAD
            (has_break, details) ÔÇô same as ``check()``.
=======
            (has_break, details) – same as ``check()``.
>>>>>>> origin/main
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
