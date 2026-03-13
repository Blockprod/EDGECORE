"""
Cross-Sectional Momentum Signal — Relative ranking for pair trading.

For a pair (A, B), ranks both legs by their return over multiple windows
(1M, 3M, 6M, 12M). The signal reflects whether A is strong relative
to B (or vice versa) within the broader cross-section.

Combined with cointegration: enter when z-score AND rank divergence
both confirm the trade direction.

Phase 1, Etape 1.2.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


class CrossSectionalMomentum:
    """
    Cross-sectional momentum signal for pair trading.

    Ranks all symbols in the universe by their return over multiple
    lookback windows, then produces a [-1, 1] score for any pair
    based on their rank difference.

    Positive score = A outranks B (A is stronger) => expect spread to widen.
    Negative score = B outranks A (B is stronger) => expect spread to narrow.

    Usage::

        csm = CrossSectionalMomentum()
        csm.update_rankings(prices_df)  # full universe prices
        score = csm.compute_score("AAPL", "MSFT")
    """

    # Default lookback windows in trading days
    DEFAULT_WINDOWS = [21, 63, 126, 252]  # ~1M, 3M, 6M, 12M

    def __init__(
        self,
        windows: Optional[List[int]] = None,
        min_history: int = 63,
    ):
        """
        Args:
            windows: List of lookback windows in trading days.
            min_history: Minimum bars required to compute rankings.
        """
        self.windows = windows or self.DEFAULT_WINDOWS
        self.min_history = min_history
        # symbol -> composite percentile rank (0..1)
        self._rankings: Dict[str, float] = {}

    def update_rankings(self, prices: pd.DataFrame) -> None:
        """Recompute cross-sectional rankings from a universe price DataFrame.

        Args:
            prices: DataFrame with columns = symbols, rows = dates, values = prices.
        """
        if prices.empty or len(prices) < self.min_history:
            self._rankings = {}
            return

        n_symbols = len(prices.columns)
        if n_symbols < 2:
            self._rankings = {}
            return

        # Compute returns for each window and average the percentile ranks
        rank_sum = pd.Series(0.0, index=prices.columns)
        valid_windows = 0

        for window in self.windows:
            if len(prices) < window + 1:
                continue
            returns = prices.iloc[-1] / prices.iloc[-window - 1] - 1.0
            returns = returns.dropna()
            if len(returns) < 2:
                continue
            # Percentile rank: 0 = worst, 1 = best
            ranks = returns.rank(pct=True)
            rank_sum = rank_sum.add(ranks, fill_value=0.0)
            valid_windows += 1

        if valid_windows == 0:
            self._rankings = {}
            return

        composite = rank_sum / valid_windows
        self._rankings = composite.to_dict()

    def compute_score(self, sym_a: str, sym_b: str) -> float:
        """Compute cross-sectional momentum score for pair (A, B).

        Returns:
            Score in [-1, 1].
            Positive: A ranks higher than B (A has stronger momentum).
            Negative: B ranks higher than A.
            0.0 if either symbol has no ranking.
        """
        rank_a = self._rankings.get(sym_a)
        rank_b = self._rankings.get(sym_b)

        if rank_a is None or rank_b is None:
            return 0.0

        # Rank difference: range is [-1, 1] since ranks are percentiles 0..1
        diff = rank_a - rank_b

        # Scale to make it more discriminative (tanh compression)
        score = float(np.tanh(diff * 2.0))

        return float(np.clip(score, -1.0, 1.0))

    @property
    def rankings(self) -> Dict[str, float]:
        """Current symbol rankings (read-only copy)."""
        return dict(self._rankings)
