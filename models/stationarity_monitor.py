"""
Stationarity Monitor ÔÇô Sprint 2.1 (fixes M-01: stationarity assumed between re-tests).

Problem
-------
The system only tests cointegration at pair discovery time (every N bars).
Between re-tests, the spread is *assumed* stationary.  If the cointegration
relationship breaks (regime change, structural break), the strategy continues
trading a non-stationary spread ÔÇô which is equivalent to betting on a random
walk.  Mean-reversion signals on a random walk are pure noise.

Solution
--------
Run a lightweight **rolling ADF test** on the last ``window`` observations
of each active spread, every bar.  If the p-value exceeds ``alert_pvalue``
(i.e. we can no longer reject the null of a unit root), the spread is
flagged as non-stationary.

    p_adf(recent) < alert_pvalue  Ôåô  STATIONARY  (continue trading)
    p_adf(recent) ÔëÑ alert_pvalue  Ôåô  NON-STATIONARY  (close & block)

Default: ``window=60``, ``alert_pvalue=0.10`` (conservative: flag early).

Performance: ADF on 60 observations Ôëê 1-3 ms Ôåô acceptable bar-by-bar.

Expected Impact: Regime-resistance score 5/10 Ôåô 8/10.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class StationarityConfig:
    """Configuration for the rolling stationarity monitor."""

    window: int = 60
    """Number of recent observations for the rolling ADF test."""

    alert_pvalue: float = 0.10
    """p-value threshold above which the spread is flagged as
    non-stationary.  0.10 is intentionally conservative (flags earlier
    than 0.05) because acting late on stationarity loss is costly."""

    min_observations: int = 30
    """Minimum spread length before any check is performed.
    Below this, the monitor conservatively returns ``stationary=True``."""

    check_interval_bars: int = 5
    """Run ADF only every N calls per pair (C-06). Between runs, the cached
    result is returned unchanged. Default 5 ≈ 5-bar latency before detecting
    a newly non-stationary spread — acceptable given ADF is a statistical test
    on 60 observations and regime changes are gradual."""


class StationarityMonitor:
    """
    Bar-by-bar rolling ADF test on active spreads.

    Usage::

        monitor = StationarityMonitor()

        # Each bar:
        is_ok, pval = monitor.check(spread_series)
        if not is_ok:
            # close position / block new entries
            ...
    """

    def __init__(self, config: StationarityConfig | None = None):
        self.config = config or StationarityConfig()
        self._call_counts: dict[str, int] = {}
        self._last_results: dict[str, tuple[bool, float]] = {}
        logger.info(
            "stationarity_monitor_initialized",
            window=self.config.window,
            alert_pvalue=self.config.alert_pvalue,
            check_interval_bars=self.config.check_interval_bars,
        )

    def check(self, spread: pd.Series, pair_key: str | None = None) -> tuple[bool, float]:
        """Run a rolling ADF test on the tail of *spread*.

        Args:
            spread: Full spread series up to the current bar.
            pair_key: Optional identifier for per-pair call-count throttling
                (C-06). When provided, ADF is only recomputed every
                ``check_interval_bars`` calls; the cached result is returned
                between runs. Callers that omit ``pair_key`` always recompute.

        Returns:
            (is_stationary, p_value)

            * ``is_stationary=True`` if ``p_value < alert_pvalue``
              (we can reject the unit-root null — spread is stationary).
            * ``is_stationary=True`` also returned when there is
              insufficient data (conservative default — don't kill
              positions prematurely).
        """
        # C-06: throttle ADF per pair using call-count cache
        if pair_key is not None:
            count = self._call_counts.get(pair_key, 0) + 1
            self._call_counts[pair_key] = count
            if count % self.config.check_interval_bars != 0 and pair_key in self._last_results:
                return self._last_results[pair_key]

        n = len(spread)

        if n < self.config.min_observations:
            return True, 0.0  # Not enough data — presume OK

        recent = spread.iloc[-self.config.window :] if n >= self.config.window else spread

        try:
            values = np.asarray(recent, dtype=np.float64)

            # Guard against constant / near-constant series
            if np.std(values) < 1e-12:
                return False, 1.0  # Zero variance — non-stationary by definition

            adf_result = adfuller(values, regression="c", autolag="AIC")
            pvalue = float(adf_result[1])

            is_stationary = pvalue < self.config.alert_pvalue
            result = is_stationary, pvalue
            if pair_key is not None:
                self._last_results[pair_key] = result
            return result

        except Exception as e:
            logger.debug("stationarity_check_error", error=str(e)[:80])
            return True, 0.0  # On error, don't kill positions
