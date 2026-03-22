"""
Ongoing Correlation Monitor ÔÇö Phase 4 (addresses audit ┬º3.5).

Continuously tracks rolling correlation between pair legs during position
lifetime.  Triggers exit signals when correlation degrades below threshold.

Usage::

    monitor = CorrelationMonitor(min_correlation=0.60, lookback=60)

    # On each bar, update with latest prices
    alert = monitor.update("AAPL_MSFT", price_aapl, price_msft)
    if alert and alert['degraded']:
        # close or reduce position
        ...
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class CorrelationMonitorConfig:
    """Configuration for the ongoing correlation monitor."""

    lookback: int = 60
    """Rolling window for correlation calculation (bars)."""

    min_correlation: float = 0.60
    """Minimum absolute correlation before flagging degradation."""

    exit_correlation: float = 0.40
    """Correlation level that triggers a hard exit signal."""

    grace_bars: int = 5
    """Number of consecutive bars below threshold before alerting."""


class PairCorrelationTracker:
    """Tracks rolling correlation for a single pair."""

    def __init__(self, pair_key: str, config: CorrelationMonitorConfig):
        self.pair_key = pair_key
        self.config = config
        self._prices_a: deque = deque(maxlen=config.lookback)
        self._prices_b: deque = deque(maxlen=config.lookback)
        self._below_count: int = 0
        self.last_correlation: float | None = None

    def update(self, price_a: float, price_b: float) -> dict[str, Any] | None:
        """Add a new bar and return alert if correlation degraded."""
        self._prices_a.append(price_a)
        self._prices_b.append(price_b)

        n = len(self._prices_a)
        if n < max(20, self.config.lookback // 2):
            return None  # not enough data

        a = np.array(self._prices_a, dtype=np.float64)
        b = np.array(self._prices_b, dtype=np.float64)

        corr = float(np.corrcoef(a, b, dtype=np.float64)[0, 1])
        self.last_correlation = corr
        abs_corr = abs(corr)

        degraded = False
        hard_exit = False

        if abs_corr < self.config.min_correlation:
            self._below_count += 1
        else:
            self._below_count = 0

        if self._below_count >= self.config.grace_bars:
            degraded = True
            if abs_corr < self.config.exit_correlation:
                hard_exit = True

        if degraded:
            return {
                "pair_key": self.pair_key,
                "correlation": corr,
                "abs_correlation": abs_corr,
                "degraded": True,
                "hard_exit": hard_exit,
                "below_count": self._below_count,
            }
        return None


class CorrelationMonitor:
    """
    Monitors rolling correlation for all active pair positions.

    Wire into the live trading loop to check on every tick::

        for pair_key in active_positions:
            alert = monitor.update(pair_key, price_a, price_b)
            if alert and alert['hard_exit']:
                # exit the pair
    """

    def __init__(self, config: CorrelationMonitorConfig | None = None):
        self.config = config or CorrelationMonitorConfig()
        self._trackers: dict[str, PairCorrelationTracker] = {}
        logger.info(
            "correlation_monitor_initialized",
            lookback=self.config.lookback,
            min_correlation=self.config.min_correlation,
            exit_correlation=self.config.exit_correlation,
        )

    def update(self, pair_key: str, price_a: float, price_b: float) -> dict[str, Any] | None:
        """Update correlation tracking for a pair.

        Args:
            pair_key: Pair identifier (e.g. "AAPL_MSFT").
            price_a: Latest price for leg A.
            price_b: Latest price for leg B.

        Returns:
            Alert dict if correlation degraded, else None.
        """
        if pair_key not in self._trackers:
            self._trackers[pair_key] = PairCorrelationTracker(pair_key=pair_key, config=self.config)
        return self._trackers[pair_key].update(price_a, price_b)

    def remove_pair(self, pair_key: str) -> None:
        """Stop tracking a pair (on position close)."""
        self._trackers.pop(pair_key, None)

    def get_all_correlations(self) -> dict[str, float | None]:
        """Get latest correlation for all tracked pairs."""
        return {k: t.last_correlation for k, t in self._trackers.items()}

    def get_degraded_pairs(self) -> list[str]:
        """Get pair keys whose correlation is below threshold."""
        degraded = []
        for key, tracker in self._trackers.items():
            if tracker.last_correlation is not None:
                if abs(tracker.last_correlation) < self.config.min_correlation:
                    degraded.append(key)
        return degraded
