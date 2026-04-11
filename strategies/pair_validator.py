"""
Pair cointegration validators — worker-process static methods.

Extracted from :class:`~strategies.pair_trading.PairTradingStrategy` so they
can be imported directly by multiprocessing worker pools without pickling the
full strategy instance.

``PairTradingStrategy`` keeps backward-compatible aliases::

    PairTradingStrategy._test_pair_cointegration = PairValidator.test_pair_cointegration
    PairTradingStrategy._test_pair_candidate     = PairValidator.test_pair_candidate
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from models.cointegration import (
    engle_granger_test,
    half_life_mean_reversion,
)
from models.cointegration import newey_west_consensus as _newey_west_consensus


class PairValidator:
    """Static cointegration testing helpers for multiprocessing worker pools.

    All methods are ``@staticmethod`` so they can be passed to
    :func:`multiprocessing.Pool.map` and :mod:`concurrent.futures` without
    serialising any instance state.
    """

    @staticmethod
    def test_pair_cointegration(args: tuple) -> tuple[str, str, float, float] | None:
        """Test cointegration for a single pair (runs in worker process).

        Args:
            args: Tuple of (sym1, sym2, series1, series2, min_corr, max_hl,
                            num_symbols, johansen_flag, nw_consensus_flag)
                  -- 6-element legacy tuples are also supported.

        Returns:
            (sym1, sym2, pvalue, half_life) tuple or None if not cointegrated
        """
        # Support both 6-element (legacy) and 9-element tuples
        _args: Any = args
        if len(args) == 9:
            sym1, sym2, series1, series2, min_corr, max_hl, num_symbols, _johansen_flag, nw_consensus_flag = _args
        else:
            sym1, sym2, series1, series2, min_corr, max_hl = _args[:6]
            num_symbols = None
            nw_consensus_flag = False

        # Determine Bonferroni flag: apply when num_symbols is provided
        apply_bonferroni = num_symbols is not None and num_symbols > 1

        try:
            # Check correlation threshold first (fast filter)
            corr = series1.corr(series2)
            if abs(corr) < min_corr:
                return None

            # Run Engle-Granger test with Bonferroni correction
            result = engle_granger_test(
                series1,
                series2,
                apply_bonferroni=apply_bonferroni,
                num_symbols=num_symbols,
            )

            if result["is_cointegrated"]:
                # Newey-West consensus gate
                if nw_consensus_flag:
                    cons = _newey_west_consensus(series1, series2)
                    if not cons["consensus"]:
                        return None

                # Calculate half-life of mean reversion
                hl = half_life_mean_reversion(pd.Series(result["residuals"]))

                # Filter by half-life
                if hl and hl <= max_hl:
                    return (sym1, sym2, result["adf_pvalue"], hl)

        except Exception:
            pass

        return None

    @staticmethod
    def test_pair_candidate(args: tuple) -> tuple[str, str, float, float] | None:
        """Test cointegration and return candidate with raw p-value (for BH-FDR).

        Unlike ``test_pair_cointegration``, this does NOT apply any
        multiple-testing correction.  The caller is responsible for
        applying BH-FDR on the collected p-values.

        Returns:
            (sym1, sym2, raw_pvalue, half_life) or None if fails
            correlation or half-life checks.
        """
        _args: Any = args
        if len(args) >= 9:
            sym1 = _args[0]
            sym2 = _args[1]
            series1 = _args[2]
            series2 = _args[3]
            min_corr = _args[4]
            max_hl = _args[5]
            _num_symbols = _args[6]
            _johansen_flag = _args[7]
            nw_consensus_flag = _args[8]
        else:
            sym1 = _args[0]
            sym2 = _args[1]
            series1 = _args[2]
            series2 = _args[3]
            min_corr = _args[4]
            max_hl = _args[5]
            nw_consensus_flag = False

        try:
            # Fast filter: correlation threshold
            corr = series1.corr(series2)
            if abs(corr) < min_corr:
                return None

            # Run EG test WITHOUT any multiple-testing correction
            # check_integration_order=False because the caller
            # pre-filters symbols via I(1) cache.
            result = engle_granger_test(
                series1,
                series2,
                apply_bonferroni=False,
                check_integration_order=False,
            )

            pvalue = result.get("adf_pvalue", 1.0)

            # Pre-filter: skip clearly insignificant pairs
            if pvalue >= 0.20 or np.isnan(pvalue):
                return None

            # Newey-West consensus gate (if enabled)
            if nw_consensus_flag:
                cons = _newey_west_consensus(series1, series2)
                if not cons["consensus"]:
                    return None

            # Calculate half-life of mean reversion
            hl = half_life_mean_reversion(pd.Series(result["residuals"]))
            if not hl or hl > max_hl:
                return None

            return (sym1, sym2, pvalue, hl)

        except Exception:
            return None
