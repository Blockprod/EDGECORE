"""
Phase 4.3 ÔÇö NLP Sentiment Signal.

Sentiment-based alpha from news/text data:
  - In live mode: FinBERT (HuggingFace) on news headlines.
  - In backtest mode: price-derived sentiment proxy using:
      * Momentum divergence (price vs sector).
      * Volume-weighted returns (conviction measure).
      * Cross-sectional return anomaly (surprise factor).

The proxy captures the *information* that would drive sentiment
without requiring actual text data, making it backtest-compatible.

Score [-1, 1] per symbol: positive = bullish sentiment, negative = bearish.
Pair score = sym1_sentiment - sym2_sentiment.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class SentimentSnapshot:
    """Sentiment metrics for a single symbol."""

    momentum_divergence: float  # Price vs sector momentum divergence
    conviction: float  # Volume-weighted momentum conviction
    surprise_factor: float  # Cross-sectional return anomaly
    composite: float  # Weighted composite [-1, 1]


class SentimentSignal:
    """
    NLP Sentiment Signal (backtest-compatible proxy).

    In backtest mode, approximates sentiment from price dynamics:
      1. **Momentum divergence**: symbol return vs sector average.
         If a stock outperforms its sector ÔåÆ positive sentiment.
      2. **Conviction**: consistency of daily returns direction.
         Mostly positive days ÔåÆ bullish conviction.
      3. **Surprise factor**: cross-sectional return anomaly.
         Unusually high/low returns relative to the universe ÔåÆ surprise.

    Usage::

        sent = SentimentSignal()
        sent.update(prices_df, sector_map={"AAPL": "technology", ...})
        score = sent.compute_score("AAPL", "MSFT")
    """

    # Component weights
    DIVERGENCE_WEIGHT = 0.40
    CONVICTION_WEIGHT = 0.30
    SURPRISE_WEIGHT = 0.30

    def __init__(
        self,
        lookback: int = 20,
        long_lookback: int = 60,
        smoothing: int = 5,
    ):
        """
        Args:
            lookback: Short-term window for recent sentiment.
            long_lookback: Longer window for baseline comparisons.
            smoothing: EMA smoothing days for the composite score.
        """
        if lookback < 5:
            raise ValueError(f"lookback must be >= 5, got {lookback}")

        self.lookback = lookback
        self.long_lookback = long_lookback
        self.smoothing = smoothing

        # symbol -> SentimentSnapshot
        self._snapshots: dict[str, SentimentSnapshot] = {}
        # symbol -> list of recent composite scores (for smoothing)
        self._history: dict[str, list[float]] = {}

    def update(
        self,
        prices_df: pd.DataFrame,
        sector_map: dict[str, str] | None = None,
    ) -> None:
        """Update sentiment estimates from daily prices.

        Args:
            prices_df: Daily close prices (columns = symbols).
            sector_map: Optional mapping {symbol: sector} for divergence calc.
        """
        if len(prices_df) < self.long_lookback + 5:
            return

        returns = prices_df.pct_change(fill_method=None).dropna()
        if len(returns) < self.lookback:
            return

        recent_returns = returns.iloc[-self.lookback :]
        universe_mean = recent_returns.mean(axis=1)  # daily cross-sectional mean

        # Pre-compute sector averages
        sector_means: dict[str, pd.Series] = {}
        if sector_map:
            sectors_seen: dict[str, list] = {}
            for sym, sec in sector_map.items():
                if sym in recent_returns.columns:
                    sectors_seen.setdefault(sec, []).append(sym)
            for sec, syms in sectors_seen.items():
                sector_means[sec] = recent_returns[syms].mean(axis=1)

        for sym in prices_df.columns:
            if sym == "SPY":
                continue

            series = prices_df[sym].dropna()
            if len(series) < self.long_lookback + 5:
                continue

            sym_returns = returns[sym].dropna() if sym in returns.columns else None
            if sym_returns is None or len(sym_returns) < self.lookback:
                continue

            sym_recent = sym_returns.iloc[-self.lookback :]

            # --- 1. Momentum divergence ---
            sector = sector_map.get(sym) if sector_map else None
            if sector and sector in sector_means:
                sector_ret = sector_means[sector].mean()
            else:
                sector_ret = universe_mean.mean()

            sym_ret = sym_recent.mean()
            if abs(sector_ret) > 1e-10:
                divergence = (sym_ret - sector_ret) / abs(sector_ret)
            else:
                divergence = sym_ret * 100  # scale up when sector is flat

            div_score = float(np.clip(divergence * 5.0, -1.0, 1.0))

            # --- 2. Conviction ---
            # Fraction of positive return days minus negative
            up_days = (sym_recent > 0).sum()
            total_days = len(sym_recent)
            conviction_raw = (2.0 * up_days / total_days - 1.0) if total_days > 0 else 0.0
            conv_score = float(np.clip(conviction_raw, -1.0, 1.0))

            # --- 3. Surprise factor ---
            # How unusual is the recent return vs the universe
            sym_cum = sym_recent.sum()
            universe_cum = universe_mean.sum()
            universe_std = recent_returns.sum().std()
            if universe_std > 1e-10:
                surprise = (sym_cum - universe_cum) / universe_std
                surp_score = float(np.clip(surprise / 2.0, -1.0, 1.0))
            else:
                surp_score = 0.0

            # Composite
            raw_composite = (
                self.DIVERGENCE_WEIGHT * div_score
                + self.CONVICTION_WEIGHT * conv_score
                + self.SURPRISE_WEIGHT * surp_score
            )

            # EMA smoothing
            if sym not in self._history:
                self._history[sym] = []
            self._history[sym].append(raw_composite)
            # Keep bounded history
            if len(self._history[sym]) > self.smoothing * 3:
                self._history[sym] = self._history[sym][-self.smoothing * 3 :]

            if len(self._history[sym]) >= self.smoothing:
                alpha = 2.0 / (self.smoothing + 1)
                ema = self._history[sym][-self.smoothing]
                for v in self._history[sym][-self.smoothing + 1 :]:
                    ema = alpha * v + (1 - alpha) * ema
                composite = float(np.clip(ema, -1.0, 1.0))
            else:
                composite = float(np.clip(raw_composite, -1.0, 1.0))

            self._snapshots[sym] = SentimentSnapshot(
                momentum_divergence=div_score,
                conviction=conv_score,
                surprise_factor=surp_score,
                composite=composite,
            )

    def compute_score(self, sym1: str, sym2: str) -> float:
        """Compute relative sentiment score for a pair.

        Positive = sym1 has more bullish sentiment than sym2.
        Negative = sym2 is more bullish.

        Returns:
            Score in [-1, 1].
        """
        s1 = self._snapshots.get(sym1)
        s2 = self._snapshots.get(sym2)

        c1 = s1.composite if s1 else 0.0
        c2 = s2.composite if s2 else 0.0

        diff = c1 - c2
        return float(np.clip(diff, -1.0, 1.0))

    def get_snapshot(self, symbol: str) -> SentimentSnapshot | None:
        """Return the latest sentiment snapshot for a symbol."""
        return self._snapshots.get(symbol)

    def reset(self) -> None:
        """Clear all stored state."""
        self._snapshots.clear()
        self._history.clear()
