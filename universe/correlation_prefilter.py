"""
Correlation Pre-Filter ÔÇö Vectorized O(N┬▓) correlation screening.

When the universe has 200+ symbols, brute-force pairwise cointegration
testing is O(N┬▓) with expensive statsmodels ADF calls per pair.

This module computes the **full correlation matrix** in one vectorized
numpy operation (< 1 second for 500 symbols), then applies a minimum
|¤ü| threshold to immediately eliminate low-correlation pairs that have
near-zero probability of economic cointegration.

Typical reduction:
    - 200 symbols ÔåÆ 19 900 pairs ÔåÆ ~3 000 surviving (85% reduction)
    - 300 symbols ÔåÆ 44 850 pairs ÔåÆ ~5 000 surviving (89% reduction)

This runs *before* the ThreadPoolExecutor cointegration engine, saving
thousands of expensive ADF test calls.

Usage::

    prefilter = CorrelationPreFilter(min_correlation=0.60)
    candidates = prefilter.filter_pairs(price_data, sector_map)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


class CorrelationPreFilter:
    """
    Vectorized correlation pre-filter for pair candidate screening.

    Computes the full NxN correlation matrix in one numpy operation,
    then applies thresholds to generate the candidate pair list.

    This replaces the pair-by-pair loop in ``PairFilters._check_correlation``
    when called before cointegration testing.

    Args:
        min_correlation: Minimum absolute Pearson correlation (default 0.60).
        min_data_points: Minimum overlapping data points per pair.
        require_same_sector: Only keep intra-sector pairs.
        max_pairs_per_sector: Cap on pairs per sector to limit compute.
    """

    def __init__(
        self,
        min_correlation: float = 0.60,
        min_data_points: int = 60,
        require_same_sector: bool = True,
        max_pairs_per_sector: int = 500,
    ):
        self.min_correlation = min_correlation
        self.min_data_points = min_data_points
        self.require_same_sector = require_same_sector
        self.max_pairs_per_sector = max_pairs_per_sector

    def compute_correlation_matrix(
        self,
        price_data: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Compute the full NxN Pearson correlation matrix.

        Uses pandas vectorized correlation ÔÇö handles NaN alignment
        automatically and is ~100x faster than pairwise loops.

        Args:
            price_data: DataFrame with one column per symbol.

        Returns:
            NxN correlation DataFrame with symbol labels.
        """
        # Drop symbols with insufficient data
        valid = price_data.dropna(axis=1, thresh=self.min_data_points)
        if len(valid.columns) < len(price_data.columns):
            dropped = set(price_data.columns) - set(valid.columns)
            logger.info(
                "correlation_dropped_sparse_symbols",
                dropped_count=len(dropped),
                examples=list(dropped)[:5],
            )

        corr = valid.corr(method="pearson")
        return corr

    def filter_pairs(
        self,
        price_data: pd.DataFrame,
        sector_map: dict[str, str] | None = None,
    ) -> list[tuple[str, str]]:
        """
        Generate candidate pairs using vectorized correlation + sector.

        Pipeline:
          1. Compute NxN correlation matrix (vectorized)
          2. Extract upper-triangle pairs where |¤ü| ÔëÑ min_correlation
          3. Apply sector restriction if sector_map provided
          4. Cap per-sector pairs to prevent compute explosion

        Args:
            price_data: DataFrame with one column per symbol.
            sector_map: Optional dict {symbol: sector_string}.
                If provided and require_same_sector=True, only
                intra-sector pairs are generated.

        Returns:
            List of (sym1, sym2) candidate pairs, sorted by sector.
        """
        corr_matrix = self.compute_correlation_matrix(price_data)
        symbols = list(corr_matrix.columns)
        n = len(symbols)

        if n < 2:
            logger.warning("correlation_prefilter_too_few_symbols", count=n)
            return []

        # Convert to numpy for fast upper-triangle extraction
        corr_vals = corr_matrix.values
        sym_array = np.array(symbols)

        # Get upper triangle indices (excluding diagonal)
        rows, cols = np.triu_indices(n, k=1)

        # Apply correlation threshold
        corr_upper = np.abs(corr_vals[rows, cols])
        mask = corr_upper >= self.min_correlation

        # Extract passing pairs
        passing_rows = rows[mask]
        passing_cols = cols[mask]
        passing_corrs = corr_upper[mask]

        # Build pairs with sector filtering
        use_sector = self.require_same_sector and sector_map is not None
        candidates: list[tuple[str, str]] = []
        sector_counts: dict[str, int] = {}

        # Sort by correlation descending ÔÇö keep strongest pairs first
        sort_idx = np.argsort(-passing_corrs)

        for idx in sort_idx:
            sym1 = str(sym_array[passing_rows[idx]])
            sym2 = str(sym_array[passing_cols[idx]])

            # Sector restriction
            if use_sector:
                if sector_map is None:
                    continue
                sec1 = sector_map.get(sym1)
                sec2 = sector_map.get(sym2)
                if sec1 != sec2 or sec1 is None:
                    continue

                # Per-sector cap
                sec_key = sec1
                count = sector_counts.get(sec_key, 0)
                if count >= self.max_pairs_per_sector:
                    continue
                sector_counts[sec_key] = count + 1

            candidates.append((sym1, sym2))

        # Stats logging
        total_possible = n * (n - 1) // 2
        logger.info(
            "correlation_prefilter_complete",
            total_symbols=n,
            total_possible_pairs=total_possible,
            above_correlation=int(mask.sum()),
            sector_filtered=len(candidates),
            reduction_pct=round(100 * (1 - len(candidates) / max(1, total_possible)), 1),
            min_corr=self.min_correlation,
            sector_restriction=use_sector,
        )

        if use_sector and sector_counts:
            logger.info(
                "correlation_prefilter_sectors",
                pairs_per_sector=sector_counts,
            )

        return candidates

    def filter_pairs_with_scores(
        self,
        price_data: pd.DataFrame,
        sector_map: dict[str, str] | None = None,
    ) -> list[tuple[str, str, float]]:
        """
        Like filter_pairs() but also returns the correlation score.

        Returns:
            List of (sym1, sym2, correlation) triples, sorted by |¤ü| desc.
        """
        corr_matrix = self.compute_correlation_matrix(price_data)
        symbols = list(corr_matrix.columns)
        n = len(symbols)

        if n < 2:
            return []

        corr_vals = corr_matrix.values
        sym_array = np.array(symbols)

        rows, cols = np.triu_indices(n, k=1)
        corr_upper = corr_vals[rows, cols]
        abs_corr = np.abs(corr_upper)
        mask = abs_corr >= self.min_correlation

        passing_rows = rows[mask]
        passing_cols = cols[mask]
        passing_corrs = corr_upper[mask]

        use_sector = self.require_same_sector and sector_map is not None
        results: list[tuple[str, str, float]] = []
        sector_counts: dict[str, int] = {}

        sort_idx = np.argsort(-np.abs(passing_corrs))

        for idx in sort_idx:
            sym1 = str(sym_array[passing_rows[idx]])
            sym2 = str(sym_array[passing_cols[idx]])
            corr_val = float(passing_corrs[idx])

            if use_sector:
                if sector_map is None:
                    continue
                sec1 = sector_map.get(sym1)
                sec2 = sector_map.get(sym2)
                if sec1 != sec2 or sec1 is None:
                    continue
                count = sector_counts.get(sec1, 0)
                if count >= self.max_pairs_per_sector:
                    continue
                sector_counts[sec1] = count + 1

            results.append((sym1, sym2, corr_val))

        return results

    @staticmethod
    def sector_pair_counts(
        sector_map: dict[str, str],
        symbols: list[str],
    ) -> dict[str, int]:
        """
        Count maximum possible intra-sector pairs per sector.

        Useful for capacity planning and logging.
        """
        groups: dict[str, int] = {}
        for sym in symbols:
            sec = sector_map.get(sym, "unknown")
            groups[sec] = groups.get(sec, 0) + 1

        return {sec: n * (n - 1) // 2 for sec, n in groups.items()}
