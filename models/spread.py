import numpy as np
import pandas as pd
from structlog import get_logger

from models.half_life_estimator import SpreadHalfLifeEstimator
from models.kalman_hedge import KalmanHedgeRatio

# Module-level Cython import ÔÇö avoids per-call dict lookup in hot path
try:
    from models.cointegration_fast import half_life_fast as _half_life_fast_cython

    _HALF_LIFE_CYTHON = True
except ImportError as _e_cython:
    _HALF_LIFE_CYTHON = False
    import structlog as _structlog

    _structlog.get_logger(__name__).warning(
        "cython_extension_missing_using_python_fallback",
        module="models.cointegration_fast",
        function="half_life_fast",
        error=str(_e_cython),
        impact="10x slower half-life estimation — recompile with: python setup.py build_ext --inplace",
    )

logger = get_logger(__name__)


class SpreadModel:
    """Linear spread model for pair trading with hedge ratio tracking."""

    def __init__(
        self,
        y: pd.Series,
        x: pd.Series,
        pair_key: str | None = None,
        hedge_ratio_tracker=None,
        eg_beta_raw: float | None = None,
        use_log_prices: bool = False,
        use_kalman: bool = False,
        kalman_delta: float = 1e-4,
    ):
        """
        Initialize spread model via OLS regression: y = alpha + beta * x + residuals

        Args:
            y: Dependent series (typically first asset price)
            x: Independent series (typically second asset price)
            pair_key: Identifier for tracking (e.g., "AAPL_MSFT")
            hedge_ratio_tracker: Optional HedgeRatioTracker instance for ╬▓ monitoring
            eg_beta_raw: Optional ╬▓ from the Engle-Granger test (de-normalised).
                If provided, a consistency check is performed against the
                OLS-on-raw-prices ╬▓.  Large divergences are logged as warnings.
            use_log_prices: If True, fit OLS on log-prices instead of levels.
                Preferred for equities (multiplicative process). Default False
                for backward compatibility.
            use_kalman: If True, use KalmanHedgeRatio instead of static OLS for
                hedge ratio estimation. β and intercept adapt bar-by-bar.
            kalman_delta: Process noise for KalmanHedgeRatio (default 1e-4).
        """
        self.use_log_prices = use_log_prices
        self.use_kalman = use_kalman
        self._kalman: KalmanHedgeRatio | None = None
        if use_log_prices:
            y_fit = pd.Series(np.log(np.asarray(y, dtype=float).clip(min=1e-10)), index=y.index)
            x_fit = pd.Series(np.log(np.asarray(x, dtype=float).clip(min=1e-10)), index=x.index)
        else:
            y_fit, x_fit = y, x
        X = np.column_stack([np.ones(len(x_fit)), np.asarray(x_fit, dtype=float)])
        beta = np.linalg.lstsq(X, np.asarray(y_fit, dtype=float), rcond=None)[0]

        self.intercept = beta[0]
        self.beta = beta[1]

        # C-03: verify EG ╬▓ vs SpreadModel ╬▓ consistency when available
        if eg_beta_raw is not None and abs(self.beta) > 1e-12:
            rel_diff = abs(self.beta - eg_beta_raw) / abs(self.beta)
            if rel_diff > 0.05:  # >5% divergence
                logger.warning(
                    "beta_divergence_eg_vs_spread",
                    pair=pair_key,
                    eg_beta_raw=round(eg_beta_raw, 6),
                    spread_beta=round(self.beta, 6),
                    relative_diff_pct=round(rel_diff * 100, 2),
                )
        self.y = y
        self.x = x
        self.pair_key = pair_key
        self.tracker = hedge_ratio_tracker
        self.is_deprecated = False
        self.residuals = np.asarray(y_fit, dtype=float) - X @ beta
        self.std_residuals = float(np.std(self.residuals))

        # C-04: Kalman warm-up — replace OLS residuals with Kalman spreads
        if use_kalman:
            self._kalman = KalmanHedgeRatio(delta=kalman_delta)
            _y_arr = np.asarray(y_fit, dtype=float)
            _x_arr = np.asarray(x_fit, dtype=float)
            _spread_vals: list[float] = []
            for _y_val, _x_val in zip(_y_arr, _x_arr, strict=False):
                _beta_k, _spread_k, _ = self._kalman.update(float(_y_val), float(_x_val))
                _spread_vals.append(_spread_k)
            self.intercept = self._kalman.intercept
            self.beta = self._kalman.beta if self._kalman.beta is not None else self.beta
            self.residuals = np.array(_spread_vals, dtype=float)
            self.std_residuals = float(np.std(self.residuals))

        # Estimate half-life of spread mean reversion
        self.half_life = self._estimate_half_life(y_fit, x_fit)

        # Record initial β if tracker is provided
        if self.tracker is not None and self.pair_key is not None:
            self.tracker.record_initial_beta(self.pair_key, self.beta)

    def _estimate_half_life(self, y: pd.Series, x: pd.Series) -> float | None:
        """
        Estimate half-life of the spread using AR(1) model.

        Uses the Cython ``half_life_fast`` kernel when available (pure C AR(1),
        ~10├ù faster), falling back to ``SpreadHalfLifeEstimator`` when not.

        Args:
            y: Dependent series
            x: Independent series

        Returns:
            Half-life in days, or None if not mean-reverting
        """
        try:
            # self.residuals IS the spread (y - intercept - beta*x), already
            # computed in __init__ ÔÇö no need to call compute_spread() again.
            res = self.residuals.astype(np.float64)

            # ÔöÇÔöÇ Cython fast path ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
            if _HALF_LIFE_CYTHON:
                hl_int = _half_life_fast_cython(res)
                if 5 <= hl_int <= 200:
                    logger.debug("half_life_estimated", pair=self.pair_key, half_life=hl_int)
                    return float(hl_int)

            # ÔöÇÔöÇ Pure-Python fallback ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
            # Prefer y.index; fall back to x.index when y is a bare numpy array.
            _index = y.index if hasattr(y, "index") else (x.index if hasattr(x, "index") else range(len(res)))
            spread = pd.Series(res, index=_index)
            estimator = SpreadHalfLifeEstimator(lookback=min(252, len(spread)))
            hl = estimator.estimate_half_life_from_spread(spread, validate=True)
            if hl is not None:
                logger.debug("half_life_estimated", pair=self.pair_key, half_life=hl)
            return hl
        except Exception as e:
            logger.debug("half_life_estimation_failed", pair=self.pair_key, error=str(e))
            return None

    def compute_spread(self, y: pd.Series, x: pd.Series) -> pd.Series:
        """
        Compute spread as: spread = y - (intercept + beta * x)

        When use_kalman=True, the Kalman filter updates bar-by-bar so the
        hedge ratio \u03b2 (and intercept) track structural shifts in real time:
            spread_t = y_t - (\u03b2_t * x_t + \u03b1_t)
        This eliminates bias from stale OLS estimates between re-estimation windows.

        When use_log_prices=True, spread is computed on log-prices:
            spread = log(y) - (intercept + beta * log(x))

        Args:
            y: Dependent series
            x: Independent series

        Returns:
            Spread series (in log space when use_log_prices=True)
        """
        if self.use_log_prices:
            y_vals = pd.Series(np.log(np.asarray(y, dtype=float).clip(min=1e-10)), index=y.index)
            x_vals = pd.Series(np.log(np.asarray(x, dtype=float).clip(min=1e-10)), index=x.index)
        else:
            y_vals, x_vals = y, x

        if self.use_kalman and self._kalman is not None:
            # Run Kalman update bar-by-bar; the filter retains its state across calls.
            y_arr = np.asarray(y_vals, dtype=float)
            x_arr = np.asarray(x_vals, dtype=float)
            spread_vals = np.empty(len(y_arr), dtype=float)
            for i, (_y, _x) in enumerate(zip(y_arr, x_arr, strict=False)):
                _beta_k, _spread_k, _ = self._kalman.update(float(_y), float(_x))
                spread_vals[i] = _spread_k
            # Expose latest Kalman \u03b2 on the model for external inspection
            if self._kalman.beta is not None:
                self.beta = self._kalman.beta
                self.intercept = self._kalman.intercept
            return pd.Series(spread_vals, index=y_vals.index)

        # OLS path — deterministic: cache via FeatureStore when pair_key is set.
        # Kalman path (stateful) is excluded from caching: the filter mutates
        # self._kalman state bar-by-bar and cannot be replayed from a snapshot.
        if self.pair_key is not None:
            from data.feature_store import get_feature_store as _get_fs

            _store = _get_fs()
            _key = _store.build_key(self.pair_key, "spread_ols", y_vals, x_vals)
            _cached = _store.get(_key)
            if _cached is not None:
                return _cached
            spread = y_vals - (self.intercept + self.beta * x_vals)
            _store.set(_key, spread)
            return spread

        return y_vals - (self.intercept + self.beta * x_vals)

    def reestimate_beta_if_needed(self, y: pd.Series, x: pd.Series, bar_time=None) -> bool:
        """
        Reestimate ╬▓ if enough time has passed, using recent data.

        Checks with tracker if reestimation is needed, and updates the model
        if so. Returns whether the pair is still stable.

        Args:
            y: Recent dependent series
            x: Recent independent series
            bar_time: Timestamp of the current bar (optional, passed to tracker)

        Returns:
            is_stable: Whether the relationship remains stable
        """
        if self.tracker is None or self.pair_key is None:
            # No tracking, model stays as-is
            return True
        # C-04: Kalman filter continuously updates \u03b2 \u2014 skip OLS re-estimation.
        if self.use_kalman:
            return True
        # Reestimate ╬▓ from recent data
        if self.use_log_prices:
            y_fit = np.log(np.asarray(y, dtype=float).clip(min=1e-10))
            x_fit = np.log(np.asarray(x, dtype=float).clip(min=1e-10))
        else:
            y_fit = np.asarray(y, dtype=float)
            x_fit = np.asarray(x, dtype=float)
        X = np.column_stack([np.ones(len(x_fit)), x_fit])
        try:
            beta_coef = np.linalg.lstsq(X, y_fit, rcond=None)[0]
            new_beta = beta_coef[1]
        except Exception as e:
            logger.warning("beta_reestimation_failed", pair=self.pair_key, error=str(e))
            return True  # Assume stable if reestimation fails

        # Check with tracker if this represents a drift
        current_beta, is_stable = self.tracker.reestimate_if_needed(
            self.pair_key,
            new_beta,
            drift_tolerance_pct=10.0,
            bar_time=bar_time,
        )

        # Update model if reestimation occurred
        if current_beta is not None and not self.is_deprecated:
            self.beta = current_beta
            self.intercept = beta_coef[0]
            self.residuals = y_fit - X @ beta_coef
            self.std_residuals = np.std(self.residuals)

        # Mark as deprecated if unstable
        if not is_stable:
            self.is_deprecated = True
            logger.warning("spread_model_deprecated", pair=self.pair_key, reason="Hedge ratio instability")

        return is_stable

    def compute_z_score(
        self, spread: pd.Series, lookback: int | None = None, half_life: float | None = None
    ) -> pd.Series:
        """
        Compute rolling Z-score of spread with optional adaptive lookback.

        If half_life is provided (or estimated from model), lookback window adapts:
        - Fast mean reversion (HL < 30d): lookback = 3 * HL (smooth short-term noise)
        - Normal (30-60d): lookback = HL (capture full cycle)
        - Slow reversion (HL > 60d): lookback = 60 (use max historical window)

        This ensures Z-score captures the right frequency of mean reversion.

        Args:
            spread: Spread series
            lookback: Explicit rolling window size (overrides half_life logic if provided)
            half_life: Half-life in days (used to infer optimal lookback). If None, uses self.half_life

        Returns:
            Z-score series
        """
        # Determine lookback window
        if lookback is None:
            # Use provided half_life, or fall back to estimated half_life
            hl = half_life if half_life is not None else self.half_life

            if hl is not None:
                # Smooth adaptive lookback (no discontinuity):
                # Multiplier linearly interpolates from 3.0 at HLÔëñ10
                # down to 1.0 at HLÔëÑ60, capped at 60 for HL>60.
                if hl <= 10:
                    multiplier = 3.0
                elif hl >= 60:
                    multiplier = 1.0
                else:
                    # Linear interpolation: 3.0 at HL=10 -> 1.0 at HL=60
                    multiplier = 3.0 - 2.0 * (hl - 10) / (60 - 10)
                lookback = int(np.ceil(multiplier * hl))
                # Cap at 60 for very slow reversion
                lookback = min(lookback, 60)
            else:
                # No half-life estimate available — warn so the issue is
                # visible in logs rather than a silent wrong-window fallback.
                logger.warning(
                    "half_life_unavailable_using_default_lookback",
                    pair=self.pair_key,
                    default_lookback=20,
                )
                lookback = 20

        # Enforce bounds: [10, 120]
        lookback = max(10, min(lookback, 120))

        rolling_mean = spread.rolling(window=lookback).mean()
        rolling_std = spread.rolling(window=lookback).std()
        z_score = (spread - rolling_mean) / (rolling_std + 1e-8)
        # Sprint 2.8 (M-08): Clamp Z-score to [-6, +6]
        z_score = z_score.clip(-6.0, 6.0)
        return z_score

    def get_model_info(self) -> dict:
        """Return model parameters for inspection."""
        info: dict = {
            "intercept": self.intercept,
            "beta": self.beta,
            "residual_std": self.std_residuals,
            "residual_mean": float(np.mean(self.residuals)),
            "half_life": self.half_life,
            "is_deprecated": self.is_deprecated,
            "use_kalman": self.use_kalman,
        }
        if self.use_kalman and self._kalman is not None:
            info["kalman_bars_processed"] = self._kalman.bars_processed
            info["kalman_breakdown_count"] = self._kalman.breakdown_count
            ci = self._kalman.get_confidence_interval()
            info["kalman_beta_ci_lower"] = ci[0]
            info["kalman_beta_ci_upper"] = ci[1]
        return info

    def update(self, y: pd.Series, x: pd.Series) -> None:
        """Re-fit the model with new price data *in place*.

        This preserves the object identity (and any attached
        HedgeRatioTracker state) while refreshing the OLS estimate,
        residuals, and half-life.
        """
        if self.use_log_prices:
            y_fit = np.log(np.asarray(y, dtype=float).clip(min=1e-10))
            x_fit = np.log(np.asarray(x, dtype=float).clip(min=1e-10))
        else:
            y_fit = np.asarray(y, dtype=float)
            x_fit = np.asarray(x, dtype=float)
        X = np.column_stack([np.ones(len(x_fit)), x_fit])
        try:
            beta_coef = np.linalg.lstsq(X, y_fit, rcond=None)[0]
        except Exception as exc:
            logger.warning(
                "spread_model_update_failed",
                pair=self.pair_key,
                error=str(exc),
            )
            return

        self.intercept = beta_coef[0]
        self.beta = beta_coef[1]
        self.y = y
        self.x = x
        self.residuals = y_fit - X @ beta_coef
        self.std_residuals = float(np.std(self.residuals))

        # C-04: When Kalman is active, also re-warm it on the new price window
        # so the filter state is consistent with the new data origin.
        if self.use_kalman and self._kalman is not None:
            self._kalman = KalmanHedgeRatio(delta=self._kalman.delta)
            _spread_vals_warm: list[float] = []
            for _y_val, _x_val in zip(y_fit, x_fit, strict=False):
                _beta_k, _spread_k, _ = self._kalman.update(float(_y_val), float(_x_val))
                _spread_vals_warm.append(_spread_k)
            if self._kalman.beta is not None:
                self.beta = self._kalman.beta
                self.intercept = self._kalman.intercept
            self.residuals = np.array(_spread_vals_warm, dtype=float)
            self.std_residuals = float(np.std(self.residuals))
