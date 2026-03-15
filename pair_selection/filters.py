"""
Pair Filters ÔÇö Pre-screening filters for pair candidate selection.

Applied *before* the expensive cointegration test to reduce the search
space and eliminate obviously unsuitable pairs.

Filters:
    1. Correlation pre-filter (|¤ü| ÔëÑ min_correlation)
    2. Data quality filter (no NaN, min length)
    3. Variance filter (non-constant series)
    4. Sector matching (optional intra-sector only)
    5. Spread half-life pre-screen (quick AR(1) check)
    6. Momentum divergence (cross-sectional momentum outlier ÔÇö v46)
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

    All methods return a boolean mask or filtered list ÔÇö designed to be
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
            return True  # missing data ÔåÆ allow through
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
        Ôëñ max_half_life.  This is a *hint*, not definitive.
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



class MomentumDivergenceFilter:
    """
    Rejects pair entries where one leg is a cross-sectional momentum outlier,
    and blocks ALL entries when cross-sectional return dispersion is too low.

    Two complementary gates:

    1. Per-pair momentum divergence (v46):
       Compute trailing lookback_days cross-sectional z-scores; reject if
       |z(sym1) - z(sym2)| > threshold (one leg is a momentum leader).

    2. Market-level dispersion gate (v47):
       Compute std of trailing returns across ALL universe symbols.
       If std < min_dispersion: block ALL new entries for that bar.
       Rationale: in smooth bull markets, stocks move synchronously and pair
       spreads drift rather than mean-revert.

    Calibration (v45b/v46 analysis):
        2019H2 smooth bull: cs-dispersion ~5-8%  -> block (P1 was -1.67 with 4t)
        2020H2 COVID recov: cs-dispersion ~15-25% -> allow (P2 was +2.27 with 3t)
        2022H2 rate-hike:   cs-dispersion ~12-18% -> allow (P3 was +2.24 with 5t)
        2023H2 AI bull:     cs-dispersion ~12-18% -> allow (P4 was +0.46 with 12t)
        2024H2 smooth bull: cs-dispersion ~6-9%   -> block (P5 was -1.14 with 3t)
        Recommended min_dispersion=0.08 (8%).

    Fail-open: returns (True, "") on any data error.
    """

    def __init__(
        self,
        lookback_days: int = 60,
        threshold: float = 1.5,
        min_universe_size: int = 20,
        min_dispersion: float = 0.0,
    ):
        self.lookback_days = lookback_days
        self.threshold = threshold
        self.min_universe_size = min_universe_size
        self.min_dispersion = min_dispersion

    def _compute_returns(self, price_data: pd.DataFrame):
        """Compute cross-sectional trailing returns. Returns None on error."""
        try:
            n_bars = len(price_data)
            lb = min(self.lookback_days, n_bars - 1)
            if lb < 10:
                return None
            recent = price_data.iloc[-(lb + 1):]
            returns = (recent.iloc[-1] / recent.iloc[0]) - 1.0
            returns = returns.dropna()
            if len(returns) < self.min_universe_size:
                return None
            return returns
        except Exception:
            return None

    def check_market_dispersion(
        self,
        price_data: pd.DataFrame,
    ) -> Tuple[bool, str]:
        """
        Market-level gate: block ALL new entries when cross-sectional return
        dispersion is below min_dispersion.

        Returns:
            (allowed, reason) -- allowed=False means skip all entries this bar.
        """
        if self.min_dispersion <= 0.0:
            return True, ""
        try:
            returns = self._compute_returns(price_data)
            if returns is None:
                return True, ""  # fail open
            dispersion = float(returns.std())
            if dispersion < self.min_dispersion:
                return False, (
                    "low_cs_dispersion=%.3f<%.3f (smooth_bull_gate)"
                    % (dispersion, self.min_dispersion)
                )
            return True, ""
        except Exception:
            return True, ""

    def check_entry_allowed(
        self,
        sym1: str,
        sym2: str,
        price_data: pd.DataFrame,
    ) -> Tuple[bool, str]:
        """
        Per-pair gate: reject entry when one leg is a cross-sectional momentum
        outlier.

        Returns:
            (allowed, reason) -- allowed=False means reject the entry.
        """
        try:
            if sym1 not in price_data.columns or sym2 not in price_data.columns:
                return True, ""

            returns = self._compute_returns(price_data)
            if returns is None:
                return True, ""

            mu = float(returns.mean())
            std = float(returns.std())
            if std < 1e-8:
                return True, ""

            z_scores = (returns - mu) / std

            if sym1 not in z_scores.index or sym2 not in z_scores.index:
                return True, ""

            z1 = float(z_scores[sym1])
            z2 = float(z_scores[sym2])
            divergence = abs(z1 - z2)

            if divergence > self.threshold:
                return False, (
                    "momentum_divergence=%.2f>%.2f z(%s)=%.2f z(%s)=%.2f"
                    % (divergence, self.threshold, sym1, z1, sym2, z2)
                )
            return True, ""
        except Exception:
            return True, ""  # degrade gracefully
