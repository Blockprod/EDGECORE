<<<<<<< HEAD
﻿"""
Market Regime Filter ÔÇö SPY-based adaptive trend & volatility regime detection.

Post-v27/v28/v29 evolution:
  v27: No filter ÔåÆ -26.55% (shorts destroyed in bull market)
  v28: Binary filter ÔåÆ -8.29% (blocked ALL entries in TRENDING)
  v29: Directional filter ÔåÆ +2.08% (longs allowed in bull TRENDING)
  v30: ADAPTIVE BIDIRECTIONAL filter ÔåÆ works in both BULL and BEAR markets
=======
"""
Market Regime Filter — SPY-based adaptive trend & volatility regime detection.

Post-v27/v28/v29 evolution:
  v27: No filter → -26.55% (shorts destroyed in bull market)
  v28: Binary filter → -8.29% (blocked ALL entries in TRENDING)
  v29: Directional filter → +2.08% (longs allowed in bull TRENDING)
  v30: ADAPTIVE BIDIRECTIONAL filter → works in both BULL and BEAR markets
>>>>>>> origin/main

The key insight: mean-reversion has a directional tailwind:
  - In BULL trends: LONG-side MR (buy the relative dip) works; shorts fight the trend
  - In BEAR trends: SHORT-side MR (sell the relative outperformer) works; longs fight the trend
  - In HIGH-VOL / crossover: BOTH sides have mean-reversion opportunities (vol clusters)

Detection uses two indicators on SPY data (from IBKR, no external feeds):
  1. **Trend direction**: 50-day MA vs 200-day MA spread % (signed)
  2. **Volatility regime**: 20-day rolling realized vol (annualized)

Four states:
<<<<<<< HEAD
  - ``BULL_TRENDING``:    MA50 >> MA200 AND low vol ÔåÆ longs only
  - ``BEAR_TRENDING``:    MA50 << MA200 AND low vol ÔåÆ longs blocked, shorts at 0.80 (v43a baseline)
  - ``MEAN_REVERTING``:   High vol (any trend) ÔåÆ both sides full sizing
  - ``NEUTRAL``:          Near crossover, moderate vol ÔåÆ both sides reduced
=======
  - ``BULL_TRENDING``:    MA50 >> MA200 AND low vol → longs only
  - ``BEAR_TRENDING``:    MA50 << MA200 AND low vol → longs blocked, shorts at 0.80 (v43a baseline)
  - ``MEAN_REVERTING``:   High vol (any trend) → both sides full sizing
  - ``NEUTRAL``:          Near crossover, moderate vol → both sides reduced
>>>>>>> origin/main

Usage::

    from signal_engine.market_regime import MarketRegimeFilter, MarketRegime

    mrf = MarketRegimeFilter(ma_fast=50, ma_slow=200)
    state = mrf.classify(spy_prices)
    if state.regime == MarketRegime.BULL_TRENDING:
        # Allow longs, block shorts
        pass
    elif state.regime == MarketRegime.BEAR_TRENDING:
        # Allow shorts, block longs
        pass
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
<<<<<<< HEAD
=======
from typing import Optional
>>>>>>> origin/main

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


class MarketRegime(Enum):
    """Market-level regime classification (v30: adaptive bidirectional)."""

<<<<<<< HEAD
    MEAN_REVERTING = "mean_reverting"  # High vol ÔåÆ both sides at 100%
    TRENDING = "trending"  # Legacy alias for BULL_TRENDING (backward compat)
    BULL_TRENDING = "bull_trending"  # Bull trend ÔåÆ longs only
    BEAR_TRENDING = (
        "bear_trending"  # Bear trend ÔåÆ longs blocked, shorts favored (v43a baseline; v44 neutral tested but reverted)
    )
    NEUTRAL = "neutral"  # Crossover zone ÔåÆ both reduced
=======
    MEAN_REVERTING = "mean_reverting"    # High vol → both sides at 100%
    TRENDING = "trending"               # Legacy alias for BULL_TRENDING (backward compat)
    BULL_TRENDING = "bull_trending"      # Bull trend → longs only
    BEAR_TRENDING = "bear_trending"     # Bear trend → longs blocked, shorts favored (v43a baseline; v44 neutral tested but reverted)
    NEUTRAL = "neutral"                  # Crossover zone → both reduced
>>>>>>> origin/main


@dataclass
class MarketRegimeState:
    """Current market regime state and diagnostics."""

    regime: MarketRegime
    ma_fast: float  # Current fast MA value
    ma_slow: float  # Current slow MA value
    ma_spread_pct: float  # (MA_fast - MA_slow) / MA_slow as %
    realized_vol: float  # 20-day annualized realized vol
    vol_threshold: float  # Configured threshold
    sizing_multiplier: float  # Legacy: 1.0 (MR), 0.0 (TRENDING), 0.5 (NEUTRAL)
    # v30: per-side sizing multipliers
<<<<<<< HEAD
    long_sizing: float = 1.0  # Sizing multiplier for long entries
=======
    long_sizing: float = 1.0   # Sizing multiplier for long entries
>>>>>>> origin/main
    short_sizing: float = 1.0  # Sizing multiplier for short entries


class MarketRegimeFilter:
    """
    Market-level regime filter based on SPY trend and volatility.

<<<<<<< HEAD
    v30: Adaptive bidirectional ÔÇö detects bull vs bear trends and gates
=======
    v30: Adaptive bidirectional — detects bull vs bear trends and gates
>>>>>>> origin/main
    entries by side accordingly. Both bull AND bear markets can generate
    profitable trades when the right side is selected.

    When ``enabled=False``, always returns ``MEAN_REVERTING`` (no filtering).
    """

    def __init__(
        self,
        ma_fast: int = 50,
        ma_slow: int = 200,
        vol_threshold: float = 0.18,
        vol_window: int = 20,
        neutral_band_pct: float = 0.02,
        enabled: bool = True,
        trend_favorable_sizing: float = 0.80,
        neutral_sizing: float = 0.65,
    ):
        """
        Args:
            ma_fast: Fast moving average window (days).
            ma_slow: Slow moving average window (days).
            vol_threshold: Annualized realized vol threshold.
                Above this -> market is volatile -> mean-reversion friendly.
            vol_window: Rolling window for realized vol calculation.
            neutral_band_pct: MA spread % band for NEUTRAL zone.
                |ma_spread_pct| < neutral_band_pct -> NEUTRAL.
            enabled: If False, always returns MEAN_REVERTING.
            trend_favorable_sizing: Sizing for the favorable side in trends.
                In BULL: long_sizing = this value. In BEAR: short_sizing = this.
            neutral_sizing: Sizing for both sides in NEUTRAL regime.
        """
        self.ma_fast = ma_fast
        self.ma_slow = ma_slow
        self.vol_threshold = vol_threshold
        self.vol_window = vol_window
        self.neutral_band_pct = neutral_band_pct
        self.enabled = enabled
        self.trend_favorable_sizing = trend_favorable_sizing
        self.neutral_sizing = neutral_sizing
<<<<<<< HEAD
        self._last_state: MarketRegimeState | None = None
=======
        self._last_state: Optional[MarketRegimeState] = None
>>>>>>> origin/main

    def classify(self, spy_prices: pd.Series) -> MarketRegimeState:
        """
        Classify the current market regime from SPY price series.

        Args:
            spy_prices: Series of SPY close prices (needs >= ma_slow bars).

        Returns:
            MarketRegimeState with regime, per-side sizing multipliers.
        """
        if not self.enabled:
            state = MarketRegimeState(
                regime=MarketRegime.MEAN_REVERTING,
<<<<<<< HEAD
                ma_fast=0.0,
                ma_slow=0.0,
                ma_spread_pct=0.0,
                realized_vol=0.0,
                vol_threshold=self.vol_threshold,
                sizing_multiplier=1.0,
                long_sizing=1.0,
                short_sizing=1.0,
=======
                ma_fast=0.0, ma_slow=0.0, ma_spread_pct=0.0,
                realized_vol=0.0, vol_threshold=self.vol_threshold,
                sizing_multiplier=1.0,
                long_sizing=1.0, short_sizing=1.0,
>>>>>>> origin/main
            )
            self._last_state = state
            return state

        if len(spy_prices) < self.ma_slow:
            # Not enough data -> default to NEUTRAL (cautious)
            state = MarketRegimeState(
                regime=MarketRegime.NEUTRAL,
<<<<<<< HEAD
                ma_fast=0.0,
                ma_slow=0.0,
                ma_spread_pct=0.0,
                realized_vol=0.0,
                vol_threshold=self.vol_threshold,
=======
                ma_fast=0.0, ma_slow=0.0, ma_spread_pct=0.0,
                realized_vol=0.0, vol_threshold=self.vol_threshold,
>>>>>>> origin/main
                sizing_multiplier=0.5,
                long_sizing=self.neutral_sizing,
                short_sizing=self.neutral_sizing,
            )
            self._last_state = state
            return state

        # 1. Trend indicator: MA crossover (signed)
<<<<<<< HEAD
        ma_f = float(pd.Series(spy_prices.rolling(self.ma_fast).mean()).iloc[-1])
        ma_s = float(pd.Series(spy_prices.rolling(self.ma_slow).mean()).iloc[-1])
=======
        ma_f = float(spy_prices.rolling(self.ma_fast).mean().iloc[-1])
        ma_s = float(spy_prices.rolling(self.ma_slow).mean().iloc[-1])
>>>>>>> origin/main
        ma_spread_pct = (ma_f - ma_s) / ma_s if ma_s != 0 else 0.0

        # 2. Volatility indicator: realized vol (annualized)
        returns = spy_prices.pct_change().dropna()
<<<<<<< HEAD
        recent_returns = returns.iloc[-self.vol_window :]
        realized_vol = float(recent_returns.std() * np.sqrt(252)) if len(recent_returns) >= 5 else 0.0
=======
        recent_returns = returns.iloc[-self.vol_window:]
        realized_vol = (
            float(recent_returns.std() * np.sqrt(252))
            if len(recent_returns) >= 5
            else 0.0
        )
>>>>>>> origin/main

        # 3. Adaptive bidirectional classification
        #
        # HIGH VOL (any direction) -> MEAN_REVERTING: both sides full
        #   Rationale: vol clusters create MR opportunities on both sides
        #
        # BULL TRENDING (MA50 >> MA200, low vol) -> longs favored, shorts blocked
        #   Rationale: relative underperformers tend to catch up in bull trends
        #
        # BEAR TRENDING (MA50 << MA200, low vol) -> shorts favored, longs blocked
        #   Rationale: relative outperformers tend to fall back in bear trends
        #
        # NEUTRAL (near crossover, moderate vol) -> both sides at reduced sizing
        #   Rationale: uncertain direction, reduce exposure

        if realized_vol >= self.vol_threshold:
            # High vol -> mean-reversion paradise (both sides)
            regime = MarketRegime.MEAN_REVERTING
            sizing_mult = 1.0
            long_sz = 1.0
            short_sz = 1.0
        elif ma_spread_pct > self.neutral_band_pct:
            # Bull trend + low vol -> longs only
            regime = MarketRegime.BULL_TRENDING
            sizing_mult = 0.0  # Legacy: block all (backward compat)
            long_sz = self.trend_favorable_sizing
            short_sz = 0.0  # Block shorts in bull
        elif ma_spread_pct < -self.neutral_band_pct:
            # Bear trend + low vol -> shorts favored, longs blocked (v43a baseline)
            # v44 tested: neutral sizing for both sides (BEAR->neutral), but caused
            # regime oscillation at vol_threshold=0.35 in 2022H2 -> WORSE results.
            # Reverted to v43a to use as v44b baseline comparison.
            regime = MarketRegime.BEAR_TRENDING
            sizing_mult = 0.0  # Legacy compat
<<<<<<< HEAD
            long_sz = 0.0  # Block longs in bear trend
=======
            long_sz = 0.0                           # Block longs in bear trend
>>>>>>> origin/main
            short_sz = self.trend_favorable_sizing  # Favor shorts in bear
        else:
            # Near crossover -> neutral, both sides reduced
            regime = MarketRegime.NEUTRAL
            sizing_mult = self.neutral_sizing
            long_sz = self.neutral_sizing
            short_sz = self.neutral_sizing

        state = MarketRegimeState(
            regime=regime,
            ma_fast=ma_f,
            ma_slow=ma_s,
            ma_spread_pct=ma_spread_pct,
            realized_vol=realized_vol,
            vol_threshold=self.vol_threshold,
            sizing_multiplier=sizing_mult,
            long_sizing=long_sz,
            short_sizing=short_sz,
        )

        # Log regime transitions
        if self._last_state is not None and self._last_state.regime != regime:
            logger.info(
                "market_regime_transition",
                old=self._last_state.regime.value,
                new=regime.value,
                ma_spread_pct=f"{ma_spread_pct:.4f}",
                realized_vol=f"{realized_vol:.4f}",
                long_sizing=f"{long_sz:.2f}",
                short_sizing=f"{short_sz:.2f}",
            )

        self._last_state = state
        return state

    @property
<<<<<<< HEAD
    def last_state(self) -> MarketRegimeState | None:
=======
    def last_state(self) -> Optional[MarketRegimeState]:
>>>>>>> origin/main
        """Return the most recent regime state."""
        return self._last_state
