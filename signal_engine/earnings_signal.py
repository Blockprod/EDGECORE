"""
Phase 4.1 — Earnings Surprise Signal (PEAD).

Post-Earnings Announcement Drift is one of the most documented alpha
sources.  When a company reports earnings that surprise the market
(positively or negatively), the stock tends to drift in the surprise
direction for 30-60 trading days.

For pair trading:
    - Compute a PEAD score for each symbol.
    - The pair signal favours the side with the better surprise.
    - Score in [-1, 1]: positive = sym1 has stronger drift, negative = sym2.

Data source strategy:
    - **Live**: Yahoo Finance / Alpha Vantage earnings calendar (free).
    - **Backtest**: Detect earnings-like events from daily price gaps.
      A |gap| > gap_threshold on high volume implies an earnings release.
      The sign and magnitude of the gap proxy the surprise direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class EarningsEvent:
    """Detected earnings event for a single symbol."""
    date: pd.Timestamp
    gap_pct: float        # overnight return (close-to-open gap proxy)
    surprise_score: float  # normalised surprise in [-1, 1]
    drift_days: int        # days since the event


class EarningsSurpriseSignal:
    """
    PEAD signal for pair trading.

    Detects earnings-like price gaps from daily data and tracks the
    post-event drift for ``drift_window`` trading days.

    Score decay: linear decay from full surprise_score to 0 over the
    drift window, modelling the gradual price incorporation.

    Usage::

        es = EarningsSurpriseSignal()
        es.update(prices_df)           # full universe daily prices
        score = es.compute_score("AAPL", "MSFT")
    """

    def __init__(
        self,
        gap_threshold: float = 0.03,
        drift_window: int = 45,
        volume_confirm_mult: float = 1.5,
        max_events: int = 4,
    ):
        """
        Args:
            gap_threshold: Minimum |daily return| to classify as earnings gap.
            drift_window: Days over which PEAD decays (default 45 ~= 2 months).
            volume_confirm_mult: Gap only counts if volume > mult × avg vol
                (set to 0 to disable volume confirmation in backtest).
            max_events: Maximum number of recent events to track per symbol.
        """
        if gap_threshold <= 0:
            raise ValueError(f"gap_threshold must be > 0, got {gap_threshold}")
        if drift_window < 5:
            raise ValueError(f"drift_window must be >= 5, got {drift_window}")

        self.gap_threshold = gap_threshold
        self.drift_window = drift_window
        self.volume_confirm_mult = volume_confirm_mult
        self.max_events = max_events

        # symbol -> list of EarningsEvent (most recent first)
        self._events: Dict[str, list] = {}
        self._last_bar_idx: int = -1

    def update(
        self,
        prices_df: pd.DataFrame,
        volumes_df: Optional[pd.DataFrame] = None,
    ) -> None:
        """Scan price data for earnings-like gaps.

        Detects gaps from daily returns.  Each gap above threshold is
        stored as an EarningsEvent.  Called once per bar in the backtest.

        Args:
            prices_df: Daily close prices (columns = symbols).
            volumes_df: Optional daily volumes for confirmation.
        """
        if len(prices_df) < 3:
            return

        bar_idx = len(prices_df) - 1
        if bar_idx == self._last_bar_idx:
            return  # already processed
        self._last_bar_idx = bar_idx

        for sym in prices_df.columns:
            if sym == "SPY":
                continue  # skip benchmark

            series = prices_df[sym].dropna()
            if len(series) < 3:
                continue

            # Daily return at latest bar
            p_curr = series.iloc[-1]
            p_prev = series.iloc[-2]
            if p_prev <= 0:
                continue
            daily_ret = (p_curr - p_prev) / p_prev

            if abs(daily_ret) < self.gap_threshold:
                continue

            # Volume confirmation (if available)
            if (
                volumes_df is not None
                and sym in volumes_df.columns
                and self.volume_confirm_mult > 0
            ):
                vol_series = volumes_df[sym].dropna()
                if len(vol_series) >= 21:
                    avg_vol = vol_series.iloc[-21:-1].mean()
                    curr_vol = vol_series.iloc[-1]
                    if avg_vol > 0 and curr_vol < avg_vol * self.volume_confirm_mult:
                        continue  # volume doesn't confirm

            # Create event
            surprise = float(np.clip(daily_ret / (self.gap_threshold * 3), -1.0, 1.0))
            event = EarningsEvent(
                date=prices_df.index[-1] if hasattr(prices_df.index, '__getitem__') else pd.Timestamp.now(),
                gap_pct=daily_ret,
                surprise_score=surprise,
                drift_days=0,
            )

            if sym not in self._events:
                self._events[sym] = []

            # Avoid duplicate events on the same date
            existing_dates = {e.date for e in self._events[sym]}
            if event.date not in existing_dates:
                self._events[sym].insert(0, event)
                # Keep only max_events
                self._events[sym] = self._events[sym][:self.max_events]
                logger.debug(
                    "earnings_event_detected",
                    symbol=sym,
                    gap_pct=f"{daily_ret:.2%}",
                    surprise=f"{surprise:.2f}",
                )

        # Increment drift_days for all existing events
        for sym, events in self._events.items():
            for ev in events:
                ev.drift_days += 1

    def _symbol_drift_score(self, symbol: str) -> float:
        """Compute the current PEAD drift score for a single symbol.

        Returns a score in [-1, 1] representing the active post-earnings
        drift.  Multiple events are weighted by recency.
        """
        events = self._events.get(symbol, [])
        if not events:
            return 0.0

        total_score = 0.0
        total_weight = 0.0

        for ev in events:
            if ev.drift_days > self.drift_window:
                continue  # expired
            # Linear decay
            decay = max(0.0, 1.0 - ev.drift_days / self.drift_window)
            weight = decay  # more recent events matter more
            total_score += ev.surprise_score * decay
            total_weight += weight

        if total_weight < 1e-10:
            return 0.0

        raw = total_score / total_weight
        return float(np.clip(raw, -1.0, 1.0))

    def compute_score(self, sym1: str, sym2: str) -> float:
        """Compute pair PEAD score.

        Positive = sym1 has stronger upward drift (or less downward).
        Negative = sym2 has stronger upward drift.

        For pair trading: if score > 0 → favour long spread (long sym1, short sym2).
        If score < 0 → favour short spread.

        Returns:
            Score in [-1, 1].
        """
        s1 = self._symbol_drift_score(sym1)
        s2 = self._symbol_drift_score(sym2)

        # Difference: positive means sym1 drifts up relative to sym2
        diff = s1 - s2
        return float(np.clip(diff, -1.0, 1.0))

    def get_events(self, symbol: str) -> list:
        """Return stored events for a symbol (for inspection/testing)."""
        return list(self._events.get(symbol, []))

    def has_active_event(self, symbol: str) -> bool:
        """Check whether a symbol has an active (non-expired) PEAD event."""
        for ev in self._events.get(symbol, []):
            if ev.drift_days <= self.drift_window:
                return True
        return False

    def reset(self) -> None:
        """Clear all stored events."""
        self._events.clear()
        self._last_bar_idx = -1
