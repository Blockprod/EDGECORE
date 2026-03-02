"""
Pair Filters — Pre-screening filters for pair candidate selection.

Applied *before* the expensive cointegration test to reduce the search
space and eliminate obviously unsuitable pairs.

Filters:
    1. Correlation pre-filter (|ρ| ≥ min_correlation)
    2. Data quality filter (no NaN, min length)
    3. Variance filter (non-constant series)
    4. Sector matching (optional intra-sector only)
    5. Spread half-life pre-screen (quick AR(1) check)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


class PairFilters:
    """
    Collection of fast pre-filters for pair candidate screening.

    All methods return a boolean mask or filtered list — designed to be
    chained in a pipeline.

    Usage::

        filters = PairFilters(min_correlation=0.7, min_data_points=60)
        candidates = filters.apply_all(price_data, candidate_pairs)
    """

    def __init__(
        self,
        min_correlation: float = 0.7,
        min_data_points: int = 60,
        min_variance: float = 1e-10,
        max_half_life_hint: int = 60,
        sector_map: Optional[Dict[str, str]] = None,
        require_same_sector: bool = False,
    ):
        self.min_correlation = min_correlation
        self.min_data_points = min_data_points
        self.min_variance = min_variance
        self.max_half_life_hint = max_half_life_hint
        self.sector_map = sector_map or {}
        self.require_same_sector = require_same_sector

    def apply_all(
        self,
        price_data: pd.DataFrame,
        candidate_pairs: List[Tuple[str, str]],
    ) -> List[Tuple[str, str]]:
        """
        Apply all pre-filters and return surviving pairs.

        Args:
            price_data: DataFrame with symbol columns.
            candidate_pairs: List of (sym1, sym2) tuples.

        Returns:
            Filtered list of candidate pairs.
        """
        passed: List[Tuple[str, str]] = []
        available_cols = set(price_data.columns)

        for sym1, sym2 in candidate_pairs:
            if sym1 not in available_cols or sym2 not in available_cols:
                continue

            s1 = price_data[sym1].dropna()
            s2 = price_data[sym2].dropna()

            if not self._check_data_quality(s1, s2):
                continue
            if not self._check_variance(s1, s2):
                continue
            if not self._check_correlation(s1, s2):
                continue
            if not self._check_sector_match(sym1, sym2):
                continue

            passed.append((sym1, sym2))

        logger.info(
            "pair_prefilter_complete",
            candidates=len(candidate_pairs),
            passed=len(passed),
            filtered_out=len(candidate_pairs) - len(passed),
        )
        return passed

    # ------------------------------------------------------------------
    # Individual filters
    # ------------------------------------------------------------------

    def _check_data_quality(self, s1: pd.Series, s2: pd.Series) -> bool:
        """Minimum data points and no NaN in overlap."""
        overlap = min(len(s1), len(s2))
        return overlap >= self.min_data_points

    def _check_variance(self, s1: pd.Series, s2: pd.Series) -> bool:
        """Reject constant or near-constant series."""
        return float(s1.std()) > self.min_variance and float(s2.std()) > self.min_variance

    def _check_correlation(self, s1: pd.Series, s2: pd.Series) -> bool:
        """Reject pairs below minimum absolute correlation."""
        corr = float(s1.corr(s2))
        return abs(corr) >= self.min_correlation

    def _check_sector_match(self, sym1: str, sym2: str) -> bool:
        """Check sector/industry economic rationale.

        When ``require_same_sector`` is True, both symbols must belong to
        the same sector.  When sector data is unavailable and requirement
        is on, the pair is allowed through (fail-open for data gaps).
        """
        if not self.require_same_sector or not self.sector_map:
            return True  # no constraint
        sec1 = self.sector_map.get(sym1)
        sec2 = self.sector_map.get(sym2)
        if sec1 is None or sec2 is None:
            return True  # missing data → allow through
        return sec1 == sec2

    @staticmethod
    def check_spread_stationarity_hint(
        s1: pd.Series,
        s2: pd.Series,
        max_half_life: int = 60,
    ) -> bool:
        """
        Quick AR(1) half-life pre-screen (no full ADF).

        Returns True if the OLS spread has an estimated half-life
        ≤ max_half_life.  This is a *hint*, not definitive.
        """
        try:
            X = np.column_stack([np.ones(len(s2)), s2.values])
            beta = np.linalg.lstsq(X, s1.values, rcond=None)[0]
            spread = s1.values - X @ beta
            lag = spread[:-1].reshape(-1, 1)
            diff = spread[1:]
            if len(lag) < 20:
                return True  # not enough data, allow through
            rho = np.linalg.lstsq(lag, diff, rcond=None)[0][0]
            if rho >= 0:
                return False  # not mean-reverting
            hl = -np.log(2) / np.log(1 + rho)
            return 0 < hl <= max_half_life
        except Exception:
            return True  # degrade gracefully
