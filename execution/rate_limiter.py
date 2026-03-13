"""
Token-Bucket Rate Limiter for IBKR API compliance.

IBKR enforces a hard cap of **50 messages/second** on the TWS API socket.
Exceeding this limit triggers automatic disconnection — catastrophic in
production.  This module implements a thread-safe token-bucket limiter
that enforces a configurable sustained rate (default 45 req/s) with burst
capacity (default 10), providing a comfortable safety margin.

Usage::

    limiter = TokenBucketRateLimiter(rate=45, burst=10)

    # Before every API call:
    limiter.acquire()          # blocks until a token is available
    ib.placeOrder(contract, order)

    # Non-blocking check:
    if limiter.try_acquire():
        ib.placeOrder(...)
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class TokenBucketRateLimiter:
    """Thread-safe token-bucket rate limiter.

    Parameters
    ----------
    rate : float
        Sustained tokens per second (default 45, below IBKR's 50/s hard cap).
    burst : int
        Maximum burst capacity — tokens available immediately before
        refill delay kicks in (default 10).
    """

    rate: float = 45.0
    burst: int = 10

    # ── internal state ──
    _tokens: float = field(init=False, repr=False)
    _last_refill: float = field(init=False, repr=False)
    _lock: threading.Lock = field(init=False, repr=False, default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self._tokens = float(self.burst)
        self._last_refill = time.monotonic()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def acquire(self, timeout: float = 5.0) -> None:
        """Block until a token is available, then consume it.

        Parameters
        ----------
        timeout : float
            Maximum seconds to wait. Raises ``RuntimeError`` if exceeded.

        Raises
        ------
        RuntimeError
            If unable to acquire a token within *timeout* seconds.
        """
        deadline = time.monotonic() + timeout

        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                # How long until the next token arrives?
                wait = (1.0 - self._tokens) / self.rate

            if time.monotonic() + wait > deadline:
                raise RuntimeError(
                    f"Rate limiter timeout: could not acquire token within {timeout}s "
                    f"(rate={self.rate}/s, burst={self.burst})"
                )

            time.sleep(min(wait, 0.05))  # sleep in small increments

    def try_acquire(self) -> bool:
        """Try to consume a token without blocking.

        Returns
        -------
        bool
            ``True`` if a token was consumed, ``False`` if none available.
        """
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _refill(self) -> None:
        """Add tokens based on elapsed time since last refill.

        Must be called while holding ``self._lock``.
        """
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now

        self._tokens = min(
            float(self.burst),
            self._tokens + elapsed * self.rate,
        )
