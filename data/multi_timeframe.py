"""
<<<<<<< HEAD
Multi-Timeframe Engine ��� Daily + Weekly confirmation for pair trading.

Architecture:
    - Daily prices are loaded from IBKR / cache (existing pipeline)
    - Weekly prices are **resampled locally** from daily data ��� zero
=======
Multi-Timeframe Engine — Daily + Weekly confirmation for pair trading.

Architecture:
    - Daily prices are loaded from IBKR / cache (existing pipeline)
    - Weekly prices are **resampled locally** from daily data — zero
>>>>>>> origin/main
      additional API calls.  Uses ``data.preprocessing.resample_ohlcv``.
    - Weekly cointegration scoring provides a *confirmation* signal
      that gates daily-level entries.

Why Daily + Weekly:
    - Weekly bars give 6+ years of lookback on IBKR (vs 1yr for intraday)
    - Mean-reversion that holds on both daily AND weekly timeframes has
      ~2x better out-of-sample persistence (literature: Galenko 2012)
    - Eliminates noise-driven daily-only cointegration that breaks down

Scoring:
    ``compute_mtf_score()`` combines daily and weekly p-values into
    a weighted composite score.  Only pairs passing BOTH timeframes
    are promoted to the trading universe.

Usage::

    mtf = MultiTimeframeEngine(weekly_weight=0.40)
    weekly_prices = mtf.resample_to_weekly(daily_prices)
    score = mtf.compute_mtf_score(daily_pval=0.01, weekly_pval=0.03)
    if mtf.passes_confirmation(daily_pval, weekly_pval):
        # This pair is confirmed on both timeframes
        ...
"""

from __future__ import annotations

from dataclasses import dataclass
<<<<<<< HEAD
=======
from typing import Dict, List, Optional, Tuple
>>>>>>> origin/main

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class MTFConfig:
    """Configuration for multi-timeframe analysis."""
<<<<<<< HEAD

    # Timeframes to use
    timeframes: list[str] | None = None  # e.g. ["D", "W"]
    # Weekly lookback in weekly bars (252 daily ��� 50 weekly)
    weekly_lookback_bars: int = 104  # ~2 years of weekly bars
=======
    # Timeframes to use
    timeframes: List[str] = None              # e.g. ["D", "W"]
    # Weekly lookback in weekly bars (252 daily ≈ 50 weekly)
    weekly_lookback_bars: int = 104           # ~2 years of weekly bars
>>>>>>> origin/main
    # Weight for weekly cointegration in composite score
    weekly_coint_weight: float = 0.40
    # Daily weight (computed as 1 - weekly)
    daily_coint_weight: float = 0.60
    # Maximum p-value for weekly confirmation
    weekly_max_pvalue: float = 0.10
    # Require weekly confirmation for entry?
    weekly_confirmation_required: bool = True
    # Weekly z-score gate: entry blocked if weekly z < this threshold
    weekly_zscore_entry_gate: float = 1.0
    # Minimum weekly bars required for valid analysis
<<<<<<< HEAD
    min_weekly_bars: int = 52  # ~1 year minimum
=======
    min_weekly_bars: int = 52                 # ~1 year minimum
>>>>>>> origin/main

    def __post_init__(self):
        if self.timeframes is None:
            self.timeframes = ["D", "W"]
        self.daily_coint_weight = 1.0 - self.weekly_coint_weight


class MultiTimeframeEngine:
    """
    Multi-timeframe analysis for pair trading confirmation.

    Core workflow:
<<<<<<< HEAD
        1. Resample daily ��� weekly (``resample_to_weekly``)
=======
        1. Resample daily → weekly (``resample_to_weekly``)
>>>>>>> origin/main
        2. Run cointegration on weekly data (same engine)
        3. Compute composite MTF score
        4. Gate daily entries with weekly z-score confirmation

<<<<<<< HEAD
    This module does NOT run its own cointegration tests ��� it provides
=======
    This module does NOT run its own cointegration tests — it provides
>>>>>>> origin/main
    the data preparation and scoring logic.  The actual cointegration
    engine (``PairTradingStrategy.find_cointegrated_pairs_parallel``)
    calls this for weekly data preparation and score combination.

    Args:
        config: MTFConfig with timeframe parameters.
    """

    def __init__(self, config: MTFConfig | None = None):
        self.config = config or MTFConfig()
        logger.info(
            "mtf_engine_initialized",
            timeframes=self.config.timeframes,
            weekly_weight=self.config.weekly_coint_weight,
            weekly_max_pval=self.config.weekly_max_pvalue,
            weekly_confirmation=self.config.weekly_confirmation_required,
        )

    # ==================================================================
<<<<<<< HEAD
    # Data preparation: daily ��� weekly resampling
=======
    # Data preparation: daily → weekly resampling
>>>>>>> origin/main
    # ==================================================================

    def resample_to_weekly(
        self,
        daily_prices: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Resample daily close prices to weekly frequency.

        Uses Friday close as the weekly reference point to align with
        standard market weeks.  Handles multi-symbol DataFrames.

        Args:
            daily_prices: DataFrame with DatetimeIndex and one column
                per symbol (close prices).

        Returns:
            Weekly-resampled DataFrame with same columns.
        """
        if daily_prices.empty:
            return daily_prices

        # Ensure DatetimeIndex
        if not isinstance(daily_prices.index, pd.DatetimeIndex):
            daily_prices = daily_prices.copy()
            daily_prices.index = pd.to_datetime(daily_prices.index)

        # Resample: take last close of each week (Friday)
        weekly = daily_prices.resample("W-FRI").last()

        # Drop weeks with NaN (partial weeks at start/end)
        weekly = weekly.dropna(how="all")

        n_daily = len(daily_prices)
        n_weekly = len(weekly)
        logger.debug(
            "resampled_daily_to_weekly",
            daily_bars=n_daily,
            weekly_bars=n_weekly,
            symbols=len(weekly.columns),
        )
        return weekly

    def resample_ohlcv_to_weekly(
        self,
        daily_ohlcv: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Resample full OHLCV daily data to weekly using proper aggregation.

        Args:
            daily_ohlcv: DataFrame with open/high/low/close/volume columns.

        Returns:
            Weekly OHLCV DataFrame.
        """
        from data.preprocessing import resample_ohlcv
<<<<<<< HEAD

=======
>>>>>>> origin/main
        return resample_ohlcv(daily_ohlcv, "W-FRI")

    # ==================================================================
    # MTF scoring
    # ==================================================================

    def compute_mtf_score(
        self,
        daily_pvalue: float,
        weekly_pvalue: float,
    ) -> float:
        """
        Compute weighted multi-timeframe cointegration score.

        Lower score = stronger cointegration signal on both timeframes.

        Score = daily_weight * daily_pval + weekly_weight * weekly_pval

        Args:
            daily_pvalue: ADF p-value from daily cointegration test.
            weekly_pvalue: ADF p-value from weekly cointegration test.

        Returns:
            Composite MTF score in [0, 1].
        """
<<<<<<< HEAD
        score = self.config.daily_coint_weight * daily_pvalue + self.config.weekly_coint_weight * weekly_pvalue
=======
        score = (
            self.config.daily_coint_weight * daily_pvalue
            + self.config.weekly_coint_weight * weekly_pvalue
        )
>>>>>>> origin/main
        return float(min(1.0, max(0.0, score)))

    def passes_confirmation(
        self,
        daily_pvalue: float,
        weekly_pvalue: float,
    ) -> bool:
        """
        Check if a pair passes weekly confirmation.

        The pair must:
          1. Be cointegrated on daily (already tested)
<<<<<<< HEAD
          2. Have weekly_pvalue ��� weekly_max_pvalue
=======
          2. Have weekly_pvalue ≤ weekly_max_pvalue
>>>>>>> origin/main

        If weekly_confirmation_required is False, always returns True.

        Args:
            daily_pvalue: ADF p-value from daily test.
            weekly_pvalue: ADF p-value from weekly test.

        Returns:
            True if the pair passes multi-timeframe confirmation.
        """
        if not self.config.weekly_confirmation_required:
            return True
<<<<<<< HEAD
        passed = weekly_pvalue <= self.config.weekly_max_pvalue
        logger.debug(
            "passes_confirmation",
            daily_pvalue=daily_pvalue,
            weekly_pvalue=weekly_pvalue,
            weekly_max_pvalue=self.config.weekly_max_pvalue,
            passed=passed,
        )
        return passed
=======
        return weekly_pvalue <= self.config.weekly_max_pvalue
>>>>>>> origin/main

    def weekly_zscore_gate(
        self,
        weekly_zscore: float,
    ) -> bool:
        """
        Check if weekly z-score supports entry.

        Entry is only allowed when the weekly z-score is >= the gate
        threshold (confirming that the weekly spread is also diverged).

        Args:
            weekly_zscore: Current z-score on the weekly timeframe.

        Returns:
            True if weekly z-score supports entry.
        """
        return abs(weekly_zscore) >= self.config.weekly_zscore_entry_gate

    # ==================================================================
    # Weekly cointegration testing (batch)
    # ==================================================================

    def test_weekly_cointegration(
        self,
        weekly_prices: pd.DataFrame,
<<<<<<< HEAD
        pairs: list[tuple[str, str]],
        lookback: int | None = None,
    ) -> dict[tuple[str, str], float]:
=======
        pairs: List[Tuple[str, str]],
        lookback: Optional[int] = None,
    ) -> Dict[Tuple[str, str], float]:
>>>>>>> origin/main
        """
        Run cointegration tests on weekly data for a list of pairs.

        This is called AFTER dailiy pairs are discovered, to compute
        weekly p-values for the confirmation gate.

        Args:
            weekly_prices: Weekly close price DataFrame.
            pairs: List of (sym1, sym2) tuples to test.
            lookback: Weekly lookback bars (default: config.weekly_lookback_bars).

        Returns:
            Dict mapping (sym1, sym2) -> weekly_pvalue.
            Pairs that fail the test return pvalue=1.0.
        """
        from models.cointegration import engle_granger_test

        lb = lookback or self.config.weekly_lookback_bars
        data = weekly_prices.tail(lb)
<<<<<<< HEAD
        results: dict[tuple[str, str], float] = {}
=======
        results: Dict[Tuple[str, str], float] = {}
>>>>>>> origin/main

        for sym1, sym2 in pairs:
            if sym1 not in data.columns or sym2 not in data.columns:
                results[(sym1, sym2)] = 1.0
                continue

            s1 = data[sym1].dropna()
            s2 = data[sym2].dropna()

            if len(s1) < self.config.min_weekly_bars or len(s2) < self.config.min_weekly_bars:
                results[(sym1, sym2)] = 1.0
                continue

            try:
<<<<<<< HEAD
                result = engle_granger_test(pd.Series(s1), pd.Series(s2))
=======
                result = engle_granger_test(s1, s2)
>>>>>>> origin/main
                results[(sym1, sym2)] = result.get("adf_pvalue", 1.0)
            except Exception:
                results[(sym1, sym2)] = 1.0

        n_passed = sum(1 for pv in results.values() if pv <= self.config.weekly_max_pvalue)
        logger.info(
            "weekly_cointegration_complete",
            pairs_tested=len(pairs),
            pairs_confirmed=n_passed,
            confirmation_rate=round(100 * n_passed / max(1, len(pairs)), 1),
            weekly_max_pval=self.config.weekly_max_pvalue,
        )
        return results

    # ==================================================================
    # Weekly z-score computation
    # ==================================================================

    def compute_weekly_zscore(
        self,
        weekly_prices: pd.DataFrame,
        sym1: str,
        sym2: str,
<<<<<<< HEAD
        lookback: int | None = None,
    ) -> float | None:
=======
        lookback: Optional[int] = None,
    ) -> Optional[float]:
>>>>>>> origin/main
        """
        Compute the current weekly z-score for a pair.

        Uses OLS residuals on weekly data with lookback window.

        Args:
            weekly_prices: Weekly close price DataFrame.
            sym1, sym2: Pair symbols.
            lookback: Weekly lookback bars.

        Returns:
            Current weekly z-score, or None if insufficient data.
        """
        lb = lookback or self.config.weekly_lookback_bars

        if sym1 not in weekly_prices.columns or sym2 not in weekly_prices.columns:
            return None

        data = weekly_prices[[sym1, sym2]].dropna().tail(lb)
        if len(data) < self.config.min_weekly_bars:
            return None

        try:
<<<<<<< HEAD
            y = np.asarray(data[sym1], dtype=float)
            x = np.asarray(data[sym2], dtype=float)
=======
            y = data[sym1].values
            x = data[sym2].values
>>>>>>> origin/main
            x_with_const = np.column_stack([np.ones(len(x)), x])
            beta = np.linalg.lstsq(x_with_const, y, rcond=None)[0]
            spread = y - x_with_const @ beta

            mean = spread.mean()
            std = spread.std()
            if std < 1e-10:
                return None

            zscore = (spread[-1] - mean) / std
            return float(zscore)
        except Exception:
            return None

    # ==================================================================
    # Batch: confirm daily pairs with weekly data
    # ==================================================================

    def confirm_pairs(
        self,
<<<<<<< HEAD
        daily_pairs: list[tuple[str, str, float, float]],
        weekly_prices: pd.DataFrame,
    ) -> list[tuple[str, str, float, float, float]]:
=======
        daily_pairs: List[Tuple[str, str, float, float]],
        weekly_prices: pd.DataFrame,
    ) -> List[Tuple[str, str, float, float, float]]:
>>>>>>> origin/main
        """
        Confirm daily-discovered pairs with weekly cointegration.

        Takes pairs from daily discovery and adds weekly confirmation.
        Returns extended tuples with MTF score.

        Args:
            daily_pairs: List of (sym1, sym2, daily_pvalue, half_life).
            weekly_prices: Weekly close prices DataFrame.

        Returns:
            List of (sym1, sym2, daily_pvalue, half_life, mtf_score)
            for pairs that pass weekly confirmation.
        """
        if not daily_pairs or weekly_prices.empty:
            return [(s1, s2, pv, hl, pv) for s1, s2, pv, hl in daily_pairs]

        # Get pair list for weekly testing
        pair_list = [(p[0], p[1]) for p in daily_pairs]
        weekly_pvals = self.test_weekly_cointegration(weekly_prices, pair_list)

<<<<<<< HEAD
        confirmed: list[tuple[str, str, float, float, float]] = []
=======
        confirmed: List[Tuple[str, str, float, float, float]] = []
>>>>>>> origin/main
        for s1, s2, daily_pv, hl in daily_pairs:
            weekly_pv = weekly_pvals.get((s1, s2), 1.0)

            if not self.passes_confirmation(daily_pv, weekly_pv):
                logger.debug(
                    "mtf_pair_rejected",
                    pair=f"{s1}_{s2}",
                    daily_pv=round(daily_pv, 4),
                    weekly_pv=round(weekly_pv, 4),
                )
                continue

            mtf_score = self.compute_mtf_score(daily_pv, weekly_pv)
            confirmed.append((s1, s2, daily_pv, hl, mtf_score))

        logger.info(
            "mtf_confirmation_complete",
            daily_pairs=len(daily_pairs),
            confirmed=len(confirmed),
            rejected=len(daily_pairs) - len(confirmed),
        )
        return confirmed
