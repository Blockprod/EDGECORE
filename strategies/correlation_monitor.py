"""
Leg-correlation stability monitoring — extracted from PairTradingStrategy.

Tracks rolling correlation between pair legs and excludes pairs whose
correlation decays below the configured threshold.

``PairTradingStrategy`` keeps backward-compatible @properties and delegation
wrappers so existing callers (and tests) work without modification.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import pandas as pd


class CorrelationMonitor:
    """Monitors rolling correlation stability between pair legs.

    State is owned by this class.  ``PairTradingStrategy`` exposes
    the underlying sets/dicts via @property descriptors so client code
    that directly mutates them (e.g. ``strategy._excluded_pairs_correlation.add(k)``)
    continues to work correctly.
    """

    def __init__(
        self,
        window: int,
        decay_threshold: float,
        clock: Callable[[], Any],
    ) -> None:
        self._excluded_pairs_correlation: set = set()
        self._correlation_exclusions: dict[str, datetime] = {}
        self._leg_correlation_history: dict[str, dict] = {}
        self._pair_historical_corr: dict[str, float] = {}
        self.leg_correlation_window: int = window
        self.leg_correlation_decay_threshold: float = decay_threshold
        self._clock = clock

    def check_stability(
        self,
        y: pd.Series,
        x: pd.Series,
        pair_key: str,
        window: int | None = None,
    ) -> bool:
        """Check if the rolling correlation between pair legs is stable.

        Returns True (safe) when data is insufficient or correlation is above
        the decay threshold.  Returns False on breakdown.
        """
        win = window or self.leg_correlation_window
        threshold = self.leg_correlation_decay_threshold

        if len(y) < 2 * win or len(x) < 2 * win:
            self._leg_correlation_history[pair_key] = {
                "stable": True,
                "recent_corr": None,
                "reason": "insufficient_data",
                "window": win,
            }
            return True

        if y.std() < 1e-12 or x.std() < 1e-12:
            self._leg_correlation_history[pair_key] = {
                "stable": True,
                "recent_corr": None,
                "reason": "constant_series",
                "window": win,
            }
            return True

        recent_corr = float(y.tail(win).corr(x.tail(win)))
        historical_corr = self._pair_historical_corr.get(pair_key, None)
        if historical_corr is None:
            historical_corr = float(y.corr(x))

        stable = abs(recent_corr) >= threshold
        self._leg_correlation_history[pair_key] = {
            "stable": stable,
            "recent_corr": recent_corr,
            "historical_corr": historical_corr,
            "threshold": threshold,
            "window": win,
        }

        if not stable:
            self._excluded_pairs_correlation.add(pair_key)
            self._correlation_exclusions[pair_key] = self._clock()

        return stable

    def get_excluded_pairs(self) -> set:
        """Return a copy of pairs excluded due to correlation breakdown."""
        return set(self._excluded_pairs_correlation)

    def get_exclusions(self) -> dict[str, datetime]:
        """Return currently excluded pairs with timestamps."""
        return dict(self._correlation_exclusions)

    def reset_exclusion(self, pair_key: str | None = None) -> None:
        """Remove a single pair or all pairs from the exclusion set."""
        if pair_key is None:
            self._excluded_pairs_correlation.clear()
            self._correlation_exclusions.clear()
        else:
            self._excluded_pairs_correlation.discard(pair_key)
            self._correlation_exclusions.pop(pair_key, None)

    def reset_all(self) -> None:
        """Remove all correlation exclusions."""
        self._excluded_pairs_correlation.clear()
        self._correlation_exclusions.clear()

    def get_analytics(self) -> dict[str, dict]:
        """Return correlation monitoring analytics."""
        return dict(self._leg_correlation_history)

    def get_history(self) -> dict[str, dict]:
        """Return leg correlation monitoring history."""
        return dict(self._leg_correlation_history)
