"""
Phase 0.3 ÔÇô Earnings & Dividend Event Filter (IBKR-only).

Backtest mode:
    Detects earnings events from price gap anomalies (>3¤â overnight moves)
    in historical IBKR ADJUSTED_LAST data.  Adjusted prices already
    neutralise dividend effects.

Live mode:
    Uses ``IBGatewaySync.get_earnings_calendar()`` which calls
    ``reqFundamentalData("CalendarReport")`` via IBKR API.

Both modes apply a configurable blackout window (default ┬▒3 trading days)
around detected events to prevent entering trades during high-IV periods.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class EventFilterConfig:
    """Configuration for the earnings/event filter."""
    gap_sigma_threshold: float = 3.0       # overnight gap threshold (std devs)
    blackout_days_before: int = 3          # days to block before event
    blackout_days_after: int = 3           # days to block after event
    rolling_window: int = 60               # window for gap ¤â estimation
    enabled: bool = True


class EarningsDetector:
    """Detect probable earnings events from overnight price gaps."""

    def __init__(self, config: Optional[EventFilterConfig] = None):
        self.config = config or EventFilterConfig()

    def detect_from_prices(
        self,
        prices: pd.Series,
        symbol: str = "",
    ) -> pd.DatetimeIndex:
        """Return dates of detected earnings-like gaps (>3¤â overnight moves).

        Args:
            prices: Daily close prices (ADJUSTED_LAST) for a single symbol.
            symbol: Symbol name for logging.

        Returns:
            DatetimeIndex of dates where an anomalous gap was detected.
        """
        if len(prices) < self.config.rolling_window + 5:
            return pd.DatetimeIndex([])

        # Daily returns
        returns = prices.pct_change().dropna()
        if len(returns) < self.config.rolling_window:
            return pd.DatetimeIndex([])

        # Rolling ¤â of returns
        rolling_std = returns.rolling(
            window=self.config.rolling_window, min_periods=20
        ).std()

        # An earnings-like event = |return| > gap_sigma_threshold * rolling ¤â
        abs_ret = returns.abs()
        threshold = self.config.gap_sigma_threshold * rolling_std
        gap_mask = abs_ret > threshold

        # Drop NaN rows
        gap_mask = gap_mask.dropna()
        event_dates = gap_mask.index[gap_mask]

        if len(event_dates) > 0:
            logger.debug(
                "earnings_gaps_detected",
                symbol=symbol,
                count=len(event_dates),
            )

        return pd.DatetimeIndex(event_dates)


class EventFilter:
    """Applies blackout windows around detected events.

    Usage in backtest:
        1. Call ``build_blackout_from_prices(prices_df)`` at simulator init
           to pre-compute all blackout dates from historical data.
        2. Call ``is_blackout(symbol, date)`` at each entry decision.

    Usage in live:
        1. Call ``add_events(symbol, dates)`` with earnings dates from IBKR.
        2. Call ``is_blackout(symbol, date)`` before entering.
    """

    def __init__(self, config: Optional[EventFilterConfig] = None):
        self.config = config or EventFilterConfig()
        self._detector = EarningsDetector(self.config)
        # symbol ÔåÆ set of blackout dates (as pd.Timestamp)
        self._blackout_dates: Dict[str, Set[pd.Timestamp]] = {}
        # Trading calendar (built from prices_df index)
        self._trading_dates: Optional[pd.DatetimeIndex] = None

    def build_blackout_from_prices(self, prices_df: pd.DataFrame) -> None:
        """Pre-compute blackout windows for all symbols from historical prices.

        Args:
            prices_df: Daily prices DataFrame (columns=symbols, index=DatetimeIndex).
        """
        if not self.config.enabled:
            return

        self._trading_dates = prices_df.index
        total_events = 0

        for symbol in prices_df.columns:
            series = prices_df[symbol].dropna()
            if len(series) < self.config.rolling_window + 5:
                continue

            event_dates = self._detector.detect_from_prices(series, symbol)
            if len(event_dates) == 0:
                continue

            total_events += len(event_dates)
            self._expand_blackout(symbol, event_dates)

        logger.info(
            "event_filter_built",
            symbols=len(prices_df.columns),
            total_events=total_events,
            total_blackout_symbols=len(self._blackout_dates),
        )

    def add_events(
        self,
        symbol: str,
        event_dates: pd.DatetimeIndex,
        trading_dates: Optional[pd.DatetimeIndex] = None,
    ) -> None:
        """Add known event dates (e.g. from IBKR CalendarReport) for a symbol."""
        if trading_dates is not None:
            self._trading_dates = trading_dates
        self._expand_blackout(symbol, event_dates)

    def is_blackout(self, symbol: str, date) -> bool:
        """Check if a symbol is in a blackout window on the given date.

        Args:
            symbol: Ticker symbol.
            date: Date to check (pd.Timestamp, datetime, or date).

        Returns:
            True if the symbol should NOT be traded on this date.
        """
        if not self.config.enabled:
            return False

        if symbol not in self._blackout_dates:
            return False

        ts = pd.Timestamp(date).normalize()
        return ts in self._blackout_dates[symbol]

    def is_pair_blackout(self, sym1: str, sym2: str, date) -> bool:
        """Check if either leg of a pair is in blackout."""
        return self.is_blackout(sym1, date) or self.is_blackout(sym2, date)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _expand_blackout(
        self, symbol: str, event_dates: pd.DatetimeIndex
    ) -> None:
        """Expand event dates into blackout windows using trading calendar."""
        if symbol not in self._blackout_dates:
            self._blackout_dates[symbol] = set()

        for event_date in event_dates:
            if self._trading_dates is not None and len(self._trading_dates) > 0:
                # Use trading calendar for accurate business-day offsets
                try:
                    idx = self._trading_dates.get_indexer(
                        [event_date], method="nearest"
                    )[0]
                except Exception:
                    idx = -1

                if idx >= 0:
                    start = max(0, idx - self.config.blackout_days_before)
                    end = min(
                        len(self._trading_dates) - 1,
                        idx + self.config.blackout_days_after,
                    )
                    for i in range(start, end + 1):
                        self._blackout_dates[symbol].add(
                            self._trading_dates[i].normalize()
                        )
                else:
                    # Fallback to calendar-day offsets
                    self._add_calendar_blackout(symbol, event_date)
            else:
                self._add_calendar_blackout(symbol, event_date)

    def _add_calendar_blackout(
        self, symbol: str, event_date: pd.Timestamp
    ) -> None:
        """Fallback: use calendar days when no trading calendar available."""
        for offset in range(
            -self.config.blackout_days_before,
            self.config.blackout_days_after + 1,
        ):
            d = pd.Timestamp(event_date).normalize() + pd.Timedelta(days=offset)
            self._blackout_dates[symbol].add(d)
