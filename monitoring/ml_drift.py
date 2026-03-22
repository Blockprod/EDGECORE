"""ML feature drift monitoring via Population Stability Index (PSI) — C-09.

Usage::

    monitor = MLFeatureDriftMonitor(feature_names=MLSignalCombiner.FEATURE_NAMES)
    # After training, set the reference distribution:
    monitor.set_reference(train_stats)  # {"zscore": {"mean": 0.1, "std": 0.8}, ...}

    # Every 252 bars, in _tick():
    drift_report = monitor.check(current_stats)
    if drift_report.has_critical_drift:
        alerter.send_alert(...)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from structlog import get_logger

logger = get_logger(__name__)

# PSI thresholds (industry standard)
PSI_STABLE = 0.10
PSI_WARNING = 0.25  # drift critique si dépassé


@dataclass
class FeatureDriftReport:
    """Result of a PSI drift check."""

    psi_by_feature: dict[str, float]
    """PSI score for each feature."""

    warning_features: list[str]
    """Features with PSI in [0.10, 0.25)."""

    critical_features: list[str]
    """Features with PSI ≥ 0.25."""

    has_critical_drift: bool = False
    """True if ≥ 3 features exceed PSI_WARNING threshold."""

    overall_psi: float = 0.0
    """Mean PSI across all features."""


class MLFeatureDriftMonitor:
    """Monitor feature distribution drift using PSI between training and live data.

    PSI (Population Stability Index) compares the distribution of a variable
    between a reference (training) set and a current (live) set.

    Interpretation:
        PSI < 0.10  : stable (no action needed)
        0.10–0.25   : minor shift (monitor closely)
        > 0.25      : significant drift (retrain / alert)
    """

    def __init__(
        self,
        feature_names: list[str],
        n_bins: int = 10,
        critical_feature_count: int = 3,
        check_interval_bars: int = 252,
    ) -> None:
        self._feature_names = feature_names
        self._n_bins = n_bins
        self._critical_feature_count = critical_feature_count
        self._check_interval_bars = check_interval_bars

        # Reference distribution: {feature: {"mean": float, "std": float, "samples": list[float]}}
        self._reference: dict[str, dict] = {}
        # Live sample buffer: {feature: list[float]}
        self._live_buffer: dict[str, list[float]] = {f: [] for f in feature_names}
        self._last_check_bar: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_reference(self, train_stats: dict[str, dict]) -> None:
        """Register training distribution as the PSI reference.

        Args:
            train_stats: Mapping from feature name to
                ``{"mean": float, "std": float, "samples": list[float]}``.
                The ``samples`` key is preferred; ``mean``/``std`` used as
                fallback to synthesize a Gaussian reference.
        """
        self._reference = {k: v for k, v in train_stats.items() if k in self._feature_names}
        logger.info(
            "ml_drift_reference_set",
            features=list(self._reference.keys()),
        )

    def record(self, features: dict[str, float]) -> None:
        """Feed one bar's feature values into the live buffer."""
        for name in self._feature_names:
            if name in features:
                self._live_buffer[name].append(features[name])

    def maybe_check(self, current_bar: int) -> FeatureDriftReport | None:
        """Run a PSI check if the interval has elapsed.

        Args:
            current_bar: Current iteration/bar counter.

        Returns:
            ``FeatureDriftReport`` if a check was performed, else ``None``.
        """
        if current_bar - self._last_check_bar < self._check_interval_bars:
            return None
        if not self._reference:
            return None

        report = self._compute_psi_report()
        self._last_check_bar = current_bar

        logger.info(
            "ml_feature_drift",
            overall_psi=round(report.overall_psi, 4),
            critical_features=report.critical_features,
            warning_features=report.warning_features,
            has_critical_drift=report.has_critical_drift,
            current_bar=current_bar,
        )

        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def compute_psi(
        expected: list[float],
        actual: list[float],
        n_bins: int = 10,
    ) -> float:
        """Compute Population Stability Index between two 1-D samples.

        Args:
            expected: Reference (training) sample values.
            actual:   Current (live) sample values.
            n_bins:   Number of histogram bins.

        Returns:
            PSI value (0.0 = identical distribution).
        """
        if len(expected) < 5 or len(actual) < 5:
            return 0.0  # not enough data for meaningful PSI

        eps = 1e-8
        # Bin edges based on reference distribution
        _, bin_edges = np.histogram(expected, bins=n_bins)
        bin_edges[0] -= 1e-10  # include left edge
        bin_edges[-1] += 1e-10

        exp_hist, _ = np.histogram(expected, bins=bin_edges)
        act_hist, _ = np.histogram(actual, bins=bin_edges)

        exp_pct = exp_hist / (len(expected) + eps)
        act_pct = act_hist / (len(actual) + eps)

        # Replace zeros to avoid log(0)
        exp_pct = np.where(exp_pct == 0, eps, exp_pct)
        act_pct = np.where(act_pct == 0, eps, act_pct)

        psi = float(np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct)))
        return max(0.0, psi)

    def _compute_psi_report(self) -> FeatureDriftReport:
        psi_scores: dict[str, float] = {}

        for feature in self._feature_names:
            ref_entry = self._reference.get(feature, {})
            ref_samples: list[float] = ref_entry.get("samples", [])
            live_samples = self._live_buffer.get(feature, [])

            if not ref_samples:
                # Synthesize from mean/std if raw samples not stored
                mean = ref_entry.get("mean", 0.0)
                std = ref_entry.get("std", 1.0)
                rng = np.random.default_rng(42)
                ref_samples = rng.normal(mean, max(std, 1e-8), 500).tolist()

            psi = self.compute_psi(ref_samples, live_samples, n_bins=self._n_bins)
            psi_scores[feature] = psi

        warning = [f for f, p in psi_scores.items() if PSI_STABLE <= p < PSI_WARNING]
        critical = [f for f, p in psi_scores.items() if p >= PSI_WARNING]
        overall = float(np.mean(list(psi_scores.values()))) if psi_scores else 0.0

        return FeatureDriftReport(
            psi_by_feature=psi_scores,
            warning_features=warning,
            critical_features=critical,
            has_critical_drift=len(critical) >= self._critical_feature_count,
            overall_psi=overall,
        )
