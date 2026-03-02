"""
IBKR API Rate Limiter — Token-bucket pacing for Interactive Brokers.

IBKR enforces strict API rate limits:
  - 50 messages/second (global)
  - Historical data: max 60 requests per 10 minutes for daily bars
  - Identical requests: 15-second duplicate penalty
  - Scanner: max 10 concurrent scanner subscriptions

This module provides a thread-safe rate limiter that all IBKR-facing code
should acquire before making API calls.

Usage::

    limiter = IBKRRateLimiter()
    limiter.acquire("historical")   # blocks until budget available
    data = ib.reqHistoricalData(...)
    limiter.acquire("message")      # for general API messages
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict

from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit budget configuration."""
    # Global message rate
    max_messages_per_second: int = 45       # conservative (IBKR limit: 50)
    # Historical data pacing
    max_historical_per_10min: int = 55      # conservative (IBKR limit: 60)
    historical_min_interval_sec: float = 0.5  # min gap between hist requests
    # Scanner pacing
    max_scanner_concurrent: int = 8         # conservative (IBKR limit: 10)
    # Contract details pacing
    max_contract_per_second: int = 10       # conservative estimate


class _SlidingWindowCounter:
    """Thread-safe sliding window rate counter."""

    def __init__(self, max_count: int, window_seconds: float):
        self._max_count = max_count
        self._window = window_seconds
        self._timestamps: deque = deque()
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        """Try to acquire a slot. Returns True if allowed."""
        now = time.monotonic()
        with self._lock:
            # Purge expired entries
            cutoff = now - self._window
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            if len(self._timestamps) < self._max_count:
                self._timestamps.append(now)
                return True
            return False

    def wait_and_acquire(self) -> float:
        """Block until a slot is available. Returns wait time in seconds."""
        total_wait = 0.0
        while True:
            now = time.monotonic()
            with self._lock:
                cutoff = now - self._window
                while self._timestamps and self._timestamps[0] < cutoff:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._max_count:
                    self._timestamps.append(now)
                    return total_wait
                # Calculate wait time until oldest entry expires
                wait_time = self._timestamps[0] + self._window - now + 0.01
            if wait_time > 0:
                total_wait += wait_time
                time.sleep(wait_time)

    @property
    def current_count(self) -> int:
        """Number of requests in the current window."""
        now = time.monotonic()
        with self._lock:
            cutoff = now - self._window
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            return len(self._timestamps)


class IBKRRateLimiter:
    """
    Thread-safe rate limiter for IBKR API calls.

    Maintains separate budgets for different API call categories:
      - ``message``: global 50 msg/s limit
      - ``historical``: 60 req/10 min for daily bars
      - ``contract``: contract resolution calls
      - ``scanner``: scanner data requests

    Usage::

        limiter = IBKRRateLimiter()

        # Before any IBKR API call:
        limiter.acquire("historical")
        data = ib.reqHistoricalData(...)

        # For general messages:
        limiter.acquire("message")
        ib.reqContractDetails(...)
    """

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._last_historical = 0.0

        # Category-specific sliding windows
        self._windows: Dict[str, _SlidingWindowCounter] = {
            "message": _SlidingWindowCounter(
                self.config.max_messages_per_second, 1.0
            ),
            "historical": _SlidingWindowCounter(
                self.config.max_historical_per_10min, 600.0
            ),
            "contract": _SlidingWindowCounter(
                self.config.max_contract_per_second, 1.0
            ),
            "scanner": _SlidingWindowCounter(
                self.config.max_scanner_concurrent, 1.0
            ),
        }
        self._lock = threading.Lock()
        self._total_waits = 0.0
        self._total_acquires = 0

        logger.info(
            "ibkr_rate_limiter_initialized",
            msg_per_sec=self.config.max_messages_per_second,
            hist_per_10min=self.config.max_historical_per_10min,
        )

    def acquire(self, category: str = "message") -> float:
        """
        Acquire a rate limit slot, blocking if necessary.

        Args:
            category: API call category (message, historical, contract, scanner)

        Returns:
            Total wait time in seconds (0.0 if no wait was needed).
        """
        window = self._windows.get(category)
        if window is None:
            logger.warning("rate_limiter_unknown_category", category=category)
            return 0.0

        # Always count against global message budget too
        total_wait = 0.0

        # For historical data, enforce minimum interval
        if category == "historical":
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_historical
                if elapsed < self.config.historical_min_interval_sec:
                    gap = self.config.historical_min_interval_sec - elapsed
                    time.sleep(gap)
                    total_wait += gap
                self._last_historical = time.monotonic()

        # Acquire from category window
        total_wait += window.wait_and_acquire()

        # Also acquire from global message window
        if category != "message":
            total_wait += self._windows["message"].wait_and_acquire()

        self._total_acquires += 1
        if total_wait > 0:
            self._total_waits += total_wait
            logger.debug(
                "rate_limiter_throttled",
                category=category,
                wait_sec=round(total_wait, 3),
            )

        return total_wait

    def stats(self) -> Dict[str, float | int]:
        """Return rate limiter statistics."""
        return {
            "total_acquires": self._total_acquires,
            "total_wait_seconds": round(self._total_waits, 2),
            "avg_wait_ms": round(
                (self._total_waits / max(1, self._total_acquires)) * 1000, 1
            ),
            "current_msg_rate": self._windows["message"].current_count,
            "current_hist_10min": self._windows["historical"].current_count,
        }
