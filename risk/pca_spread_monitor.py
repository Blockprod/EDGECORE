"""
PCA Spread Factor Monitor ÔÇô Phase 3 (addresses audit ┬º8.2).

Problem
-------
The ``SpreadCorrelationGuard`` checks **pairwise** correlations between active
spreads.  Five spreads may each have |¤ü| < 0.60 with every other, yet all
be driven by the same **latent factor** (e.g. sector rotation in equities,
or interest-rate sensitivity across financials).  Pairwise guards cannot detect this hidden
concentration.

Solution
--------
Run PCA on the matrix of active spread returns.  If the first principal
component explains more than ``max_pc1_variance`` (default 50%), the
portfolio is factor-concentrated.  New entries that increase PC1 loading
are rejected; existing positions may be flagged for reduction.

This runs **alongside** the pairwise ``SpreadCorrelationGuard`` ÔÇô it is
an additional (not replacement) layer of risk control.

Usage::

    monitor = PCASpreadMonitor()
    monitor.update_spreads({"AAPL_MSFT": spread1, "JPM_BAC": spread2, ...})

    # Before entering a new pair:
    allowed, reason = monitor.check_entry("GOOGL_AMZN", candidate_spread)

    # Periodic check:
    report = monitor.get_concentration_report()
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class PCASpreadConfig:
    """Configuration for PCA spread factor monitoring."""

    max_pc1_variance: float = 0.50
    """Maximum fraction of total variance explained by PC1 before
    flagging the portfolio as factor-concentrated.  0.50 = 50%."""

    min_spreads: int = 3
    """Minimum number of active spreads to perform PCA.  Below this
    the monitor is dormant (always allows entries)."""

    min_observations: int = 30
    """Minimum overlapping observations across spreads for PCA."""

    max_candidate_loading: float = 0.70
    """Maximum |loading| a candidate spread may have on PC1 when the
    portfolio is already concentrated.  Entries above this are rejected."""

    warn_pc1_variance: float = 0.40
    """Variance threshold for issuing a warning (below rejection)."""


class PCASpreadMonitor:
    """
    Factor-level concentration monitor using PCA on active spreads.

    Detects hidden common-factor exposure that pairwise correlation
    guards miss.
    """

    def __init__(self, config: PCASpreadConfig | None = None):
        self.config = config or PCASpreadConfig()
        self._spreads: dict[str, pd.Series] = {}
        self._last_pca_result: dict[str, Any] | None = None
        logger.info(
            "pca_spread_monitor_initialized",
            max_pc1_variance=self.config.max_pc1_variance,
            min_spreads=self.config.min_spreads,
        )

    # ÔôÇÔôÇ Public API ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

    def update_spreads(self, spreads: dict[str, pd.Series]) -> None:
        """Replace the full set of active spreads (called each bar)."""
        self._spreads = dict(spreads)

    def register_spread(self, pair_key: str, spread: pd.Series) -> None:
        """Add or update a single spread (on entry / each bar)."""
        self._spreads[pair_key] = spread

    def remove_spread(self, pair_key: str) -> None:
        """Remove a spread on position exit."""
        self._spreads.pop(pair_key, None)

    def check_entry(
        self,
        candidate_key: str,
        candidate_spread: pd.Series,
    ) -> tuple[bool, str | None]:
        """Decide whether a new entry increases factor concentration.

        Args:
            candidate_key: Pair key for the proposed new position.
            candidate_spread: Spread series of the candidate pair.

        Returns:
            (allowed, reject_reason)
        """
        n_active = len(self._spreads)
        if n_active < self.config.min_spreads:
            return True, None  # Not enough spreads for PCA

        # Build return matrix from existing spreads
        ret_matrix, keys = self._build_return_matrix()
        if ret_matrix is None or ret_matrix.shape[0] < self.config.min_observations:
            return True, None  # Insufficient data

        # Run PCA on existing portfolio
        pc1_var, components = self._run_pca(ret_matrix)
        self._last_pca_result = {
            "pc1_variance_ratio": pc1_var,
            "n_spreads": len(keys),
            "keys": keys,
        }

        # If portfolio is not concentrated, allow entry
        if pc1_var < self.config.max_pc1_variance:
            return True, None

        # Portfolio IS concentrated ÔÇô check candidate's loading on PC1
        cand_ret = candidate_spread.pct_change().dropna()
        if len(cand_ret) < self.config.min_observations:
            return True, None

        # Project candidate onto PC1
        pc1 = components[0]  # first principal component direction
        # Align lengths
        n = min(len(cand_ret), ret_matrix.shape[0])
        cand_tail = cand_ret.values[-n:]
        pc1_scores = ret_matrix[-n:] @ pc1

        # Correlation between candidate and PC1 scores
        if np.std(np.asarray(cand_tail, dtype=float)) < 1e-12 or np.std(np.asarray(pc1_scores, dtype=float)) < 1e-12:
            return True, None
        loading = abs(float(np.corrcoef(np.asarray(cand_tail, dtype=float), np.asarray(pc1_scores, dtype=float))[0, 1]))

        if loading > self.config.max_candidate_loading:
            reason = (
                f"PCA_FACTOR_GUARD: PC1 explains {pc1_var:.1%} of portfolio variance, "
                f"candidate {candidate_key} has {loading:.2f} loading on PC1 "
                f"> threshold {self.config.max_candidate_loading}"
            )
            logger.info(
                "pca_factor_entry_rejected",
                candidate=candidate_key,
                pc1_variance=round(pc1_var, 4),
                candidate_loading=round(loading, 4),
            )
            return False, reason

        return True, None

    def get_concentration_report(self) -> dict[str, Any]:
        """Get the current factor concentration analysis.

        Returns a dict with PC1 variance ratio, per-spread loadings,
        and concentration status.
        """
        n_active = len(self._spreads)
        report: dict[str, Any] = {
            "n_active_spreads": n_active,
            "pca_computed": False,
            "pc1_variance_ratio": None,
            "is_concentrated": False,
            "is_warning": False,
            "spread_loadings": {},
        }

        if n_active < self.config.min_spreads:
            return report

        ret_matrix, keys = self._build_return_matrix()
        if ret_matrix is None or ret_matrix.shape[0] < self.config.min_observations:
            return report

        pc1_var, components = self._run_pca(ret_matrix)
        pc1 = components[0]

        report["pca_computed"] = True
        report["pc1_variance_ratio"] = float(pc1_var)
        report["is_concentrated"] = pc1_var >= self.config.max_pc1_variance
        report["is_warning"] = pc1_var >= self.config.warn_pc1_variance

        # Per-spread loadings on PC1
        for i, key in enumerate(keys):
            report["spread_loadings"][key] = float(pc1[i])

        if report["is_concentrated"]:
            logger.warning(
                "pca_portfolio_concentrated",
                pc1_variance=round(pc1_var, 4),
                n_spreads=n_active,
            )
        elif report["is_warning"]:
            logger.info(
                "pca_portfolio_concentration_warning",
                pc1_variance=round(pc1_var, 4),
            )

        self._last_pca_result = report
        return report

    def clear(self) -> None:
        """Remove all tracked spreads."""
        self._spreads.clear()
        self._last_pca_result = None

    # ÔôÇÔôÇ Internals ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

    def _build_return_matrix(self) -> tuple[np.ndarray | None, list[str]]:
        """Build a (T ├ù N) matrix of spread returns from active spreads.

        Returns:
            (return_matrix, spread_keys) or (None, []) if insufficient data.
        """
        keys = sorted(self._spreads.keys())
        if len(keys) < self.config.min_spreads:
            return None, []

        # Compute returns and align by index
        ret_frames = {}
        for k in keys:
            s = self._spreads[k]
            ret = s.pct_change().dropna()
            if len(ret) >= self.config.min_observations:
                ret_frames[k] = ret

        if len(ret_frames) < self.config.min_spreads:
            return None, []

        # Align on common index
        sorted(ret_frames.keys())
        df = pd.DataFrame(ret_frames)
        df = df.dropna()

        if len(df) < self.config.min_observations:
            return None, []

        return df.values, list(df.columns)

    @staticmethod
    def _run_pca(X: np.ndarray) -> tuple[float, np.ndarray]:
        """Run PCA on return matrix X (T ├ù N).

        Uses numpy's eigendecomposition on the covariance matrix (fast for
        small N, which is typical ÔÇô we rarely have >20 active spreads).

        Returns:
            (pc1_variance_ratio, components)  ÔÇô components is (N_components ├ù N_features).
        """
        # Center
        X_centered = X - X.mean(axis=0)

        # Covariance matrix
        cov = np.cov(X_centered, rowvar=False)
        if cov.ndim == 0:
            return 1.0, np.array([[1.0]])

        # Eigendecomposition
        eigenvalues, eigenvectors = np.linalg.eigh(cov)

        # Sort descending
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]

        total_var = eigenvalues.sum()
        if total_var < 1e-14:
            return 0.0, eigenvectors.T

        pc1_var_ratio = float(eigenvalues[0] / total_var)
        return pc1_var_ratio, eigenvectors.T


__all__ = [
    "PCASpreadConfig",
    "PCASpreadMonitor",
]
