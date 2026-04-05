"""
Phase 4.2 ÔÇö Options Flow Signal.

Extracts directional bias from options market data:
  1. Put/Call ratio: high P/C ÔåÆ bearish pressure, low ÔåÆ bullish.
  2. Implied Volatility skew: put IV > call IV ÔåÆ fear premium.
  3. Unusual options activity: volume spike ÔåÆ smart money positioning.

For pair trading, the score reflects relative options sentiment
between the two legs.  Positive = sym1 more bullish options flow.

Data source strategy:
  - **Live**: IBKR Options chain + market data subscriptions.
  - **Backtest**: Estimate from daily price dynamics.
    * IV proxy: recent realised vol scaled by vol-of-vol.
    * P/C proxy: based on price momentum vs historical patterns.
    * Unusual activity proxy: absolute daily return percentile.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class OptionsFlowSnapshot:
    """Options flow metrics for a single symbol at a point in time."""
    pc_ratio_score: float     # Put/Call ratio signal [-1, 1]
    iv_skew_score: float      # IV skew signal [-1, 1]
    unusual_activity: float   # Unusual activity indicator [0, 1]
    composite: float          # Weighted composite [-1, 1]


class OptionsFlowSignal:
    """
    Options flow signal for pair trading.

    In backtest mode (no live options data), estimates options-like
    signals from daily price and volume dynamics.

    Usage::

        ofs = OptionsFlowSignal()
        ofs.update(prices_df)
        score = ofs.compute_score("AAPL", "MSFT")
    """

    # Component weights for composite
    PC_WEIGHT = 0.40
    IV_WEIGHT = 0.35
    UNUSUAL_WEIGHT = 0.25

    def __init__(
        self,
        pc_lookback: int = 21,
        iv_lookback: int = 30,
        unusual_threshold: float = 0.90,
        vol_lookback: int = 60,
    ):
        """
        Args:
            pc_lookback: Window for put/call ratio estimation.
            iv_lookback: Window for IV skew estimation.
            unusual_threshold: Percentile threshold for unusual activity
                (e.g. 0.90 = top 10% of daily moves).
            vol_lookback: Long-term vol window for IV proxy.
        """
        if pc_lookback < 5:
            raise ValueError(f"pc_lookback must be >= 5, got {pc_lookback}")

        self.pc_lookback = pc_lookback
        self.iv_lookback = iv_lookback
        self.unusual_threshold = unusual_threshold
        self.vol_lookback = vol_lookback

        # symbol -> OptionsFlowSnapshot
        self._snapshots: dict[str, OptionsFlowSnapshot] = {}

    def update(self, prices_df: pd.DataFrame) -> None:
        """Update options flow estimates from daily prices.

        In backtest mode, derives option-like signals from:
          - Put/Call proxy: price momentum relative to vol (fear/greed).
          - IV proxy: ratio of short-term to long-term realised vol.
          - Unusual activity: absolute return percentile.

        Args:
            prices_df: Daily close prices (columns = symbols).
        """
        for sym in prices_df.columns:
            if sym == "SPY":
                continue

            series = prices_df[sym].dropna()
            if len(series) < max(self.vol_lookback, self.iv_lookback) + 5:
                continue

            returns = series.pct_change().dropna()
            if len(returns) < self.vol_lookback:
                continue

            # --- Put/Call ratio proxy ---
            # Bearish momentum ÔåÆ high P/C ÔåÆ negative score
            # Bullish momentum ÔåÆ low P/C ÔåÆ positive score
            recent_ret = returns.iloc[-self.pc_lookback:].mean()
            recent_vol = returns.iloc[-self.pc_lookback:].std()
            if recent_vol > 1e-10:
                # Sharpe-like momentum measure
                mom_signal = recent_ret / recent_vol
                pc_score = float(np.clip(mom_signal * 2.0, -1.0, 1.0))
            else:
                pc_score = 0.0

            # --- IV skew proxy ---
            # When short-term vol >> long-term vol ÔåÆ fear premium (bearish)
            # When short-term vol << long-term vol ÔåÆ calm (bullish)
            short_vol = returns.iloc[-self.iv_lookback:].std()
            long_vol = returns.iloc[-self.vol_lookback:].std()
            if long_vol > 1e-10:
                vol_ratio = short_vol / long_vol
                # vol_ratio > 1 ÔåÆ elevated fear ÔåÆ negative score
                # vol_ratio < 1 ÔåÆ compressed ÔåÆ positive score
                iv_score = float(np.clip(-(vol_ratio - 1.0) * 3.0, -1.0, 1.0))
            else:
                iv_score = 0.0

            # --- Unusual activity proxy ---
            # Based on percentile of today's absolute return
            abs_ret = abs(returns.iloc[-1])
            historical_abs = returns.iloc[-self.vol_lookback:].abs()
            if len(historical_abs) > 5:
                percentile = (historical_abs < abs_ret).mean()
                unusual = float(
                    max(0.0, (percentile - self.unusual_threshold) / (1.0 - self.unusual_threshold))
                ) if percentile > self.unusual_threshold else 0.0
            else:
                unusual = 0.0

            # Directional unusual activity: same sign as recent return
            unusual_dir = unusual * (1.0 if returns.iloc[-1] > 0 else -1.0)

            composite = (
                self.PC_WEIGHT * pc_score
                + self.IV_WEIGHT * iv_score
                + self.UNUSUAL_WEIGHT * unusual_dir
            )
            composite = float(np.clip(composite, -1.0, 1.0))

            self._snapshots[sym] = OptionsFlowSnapshot(
                pc_ratio_score=pc_score,
                iv_skew_score=iv_score,
                unusual_activity=unusual,
                composite=composite,
            )

    def compute_score(self, sym1: str, sym2: str) -> float:
        """Compute relative options flow score for a pair.

        Positive = sym1 has more bullish options flow than sym2.
        Negative = sym2 has more bullish flow.

        Returns:
            Score in [-1, 1].
        """
        s1 = self._snapshots.get(sym1)
        s2 = self._snapshots.get(sym2)

        c1 = s1.composite if s1 else 0.0
        c2 = s2.composite if s2 else 0.0

        diff = c1 - c2
        return float(np.clip(diff, -1.0, 1.0))

    def get_snapshot(self, symbol: str) -> OptionsFlowSnapshot | None:
        """Return the latest options flow snapshot for a symbol."""
        return self._snapshots.get(symbol)

    def reset(self) -> None:
        """Clear all stored snapshots."""
        self._snapshots.clear()
