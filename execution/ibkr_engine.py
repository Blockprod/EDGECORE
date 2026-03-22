"""IBKRExecutionEngine � ib_insync asyncio gateway for Interactive Brokers.

Split from the synchronous ibapi gateway as part of C-16 (single-responsibility).
The IBWrapper and IBGatewaySync classes now live in execution.ibkr_sync_gateway.

Backward-compatibility re-exports are provided below so that all existing callers
using ``from execution.ibkr_engine import IBGatewaySync`` continue to work without
any changes.
"""

import asyncio
import os
import random
import threading
import time
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from structlog import get_logger

from common.retry import RetryPolicy, retry_with_backoff
from execution.base import BaseExecutionEngine, Order, OrderSide, OrderStatus

# Backward-compat re-exports (C-16): callers that import IBGatewaySync or
# IBWrapper from this module will continue to work transparently.
from execution.ibkr_sync_gateway import IBGatewaySync, IBWrapper  # noqa: F401  # type: ignore[reportUnusedImport]
from execution.rate_limiter import TokenBucketRateLimiter

load_dotenv()

logger = get_logger(__name__)

# Module-level rate limiter shared by all IBKRExecutionEngine instances.
# Ensures the 50 req/s TWS socket cap is never exceeded, even with
# multiple engine instances (e.g. reconnect scenarios).
_ibkr_rate_limiter = TokenBucketRateLimiter(rate=45, burst=10)


class IBKRExecutionEngine(BaseExecutionEngine):
    """
    Interactive Brokers execution via ib_insync.

    Requires TWS / IB Gateway running:
      - Paper trading: port 7497
      - Live trading:  port 7496
    """

    # Path for persisting order_id ��� IB permId mapping (crash recovery)
    _ORDER_MAP_FILE = "data/ibkr_order_map.json"

    # Class-level registry of in-use client_ids to detect duplicates
    _active_client_ids: dict[int, int] = {}  # client_id → refcount
    _active_client_ids_lock: threading.Lock = threading.Lock()  # T3-01: guard check-then-set

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        client_id: int | None = None,
        readonly: bool = False,
        timeout: int = 30,
    ):
        self.host = host or os.getenv("IBKR_HOST", "127.0.0.1")
        self.port = port or int(os.getenv("IBKR_PORT", "7497"))
        self.client_id = client_id if client_id is not None else int(os.getenv("IBKR_CLIENT_ID", "1"))
        self.readonly = readonly
        self.timeout = timeout
        self._ib: Any = None  # ib_insync.IB instance (lazy)
        self._order_map: dict[str, Any] = {}
        self._persisted_order_ids: dict[str, int] = {}  # order_id ��� IB permId
        self._consecutive_failures = 0
        self._max_consecutive_failures = 5  # circuit breaker threshold
        self._last_failure_time: float = 0.0  # A-11: timestamp of last failure for auto-reset
        _CB_RESET_TIMEOUT = 300  # 5 minutes � auto-reset after sustained inactivity
        self._cb_reset_timeout = _CB_RESET_TIMEOUT

        # Restore persisted order map on init (crash recovery)
        self._load_order_map()

        # Audit: detect duplicate client_id usage (multi-worker collision risk)
        # T3-01: check-then-set is atomic under the class-level lock.
        with IBKRExecutionEngine._active_client_ids_lock:
            count = IBKRExecutionEngine._active_client_ids.get(self.client_id, 0)
            if count > 0:
                raise RuntimeError(
                    f"[SECURITY] IBKR client_id={self.client_id} already in use by "
                    f"another IBKRExecutionEngine instance. Each worker must use a "
                    f"unique client_id to avoid IB Gateway conflicts."
                )
            IBKRExecutionEngine._active_client_ids[self.client_id] = count + 1

        logger.info(
            "ibkr_engine_init",
            host=self.host,
            port=self.port,
            client_id=self.client_id,
            readonly=self.readonly,
        )

    # ������ Connection helpers ������
    def _ensure_connected(self) -> None:
        """Connect to TWS/Gateway if not already connected.

        Implements retry with exponential backoff (3 attempts: 5s, 15s, 30s).
        Circuit breaker opens after 5 consecutive failures.
        """
        if self._ib is not None and self._ib.isConnected():
            self._consecutive_failures = 0
            return

        # Circuit breaker: refuse to connect after too many failures
        if self._consecutive_failures >= self._max_consecutive_failures:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self._cb_reset_timeout:
                # A-11: auto-reset after 5 minutes of no activity
                logger.warning(
                    "ibkr_circuit_breaker_auto_reset",
                    elapsed_s=round(elapsed, 0),
                    previous_failures=self._consecutive_failures,
                )
                self._consecutive_failures = 0
            else:
                raise ConnectionError(
                    f"IBKR circuit breaker open: {self._consecutive_failures} consecutive failures. "
                    f"Auto-reset in {self._cb_reset_timeout - elapsed:.0f}s"
                )

        # Ensure an asyncio event loop exists (required by ib_insync on Python 3.10+)
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())

        retry_base_delays = [5, 15, 30]  # seconds base
        last_error = None

        for attempt, base_delay in enumerate(retry_base_delays, 1):
            try:
                from ib_insync import IB

                self._ib = IB()
                self._ib.connect(
                    self.host,
                    self.port,
                    clientId=self.client_id,
                    readonly=self.readonly,
                    timeout=self.timeout,
                )
                self._consecutive_failures = 0

                # Register disconnect handler for auto-reconnect awareness
                self._ib.disconnectedEvent += self._on_disconnect

                logger.info("ibkr_connected", host=self.host, port=self.port, attempt=attempt)
                return
            except Exception as exc:
                last_error = exc
                # A-09: add �30% jitter to avoid thundering herd on reconnect
                jitter = random.uniform(0, base_delay * 0.3)
                actual_delay = round(base_delay + jitter, 1)
                logger.warning(
                    "ibkr_connection_attempt_failed",
                    attempt=attempt,
                    max_attempts=len(retry_base_delays),
                    error=str(exc)[:120],
                    retry_in=actual_delay,
                )
                if attempt < len(retry_base_delays):
                    time.sleep(actual_delay)

        self._consecutive_failures += 1
        self._last_failure_time = time.time()  # A-11: record failure timestamp for auto-reset
        logger.error(
            "ibkr_connection_failed_all_retries",
            consecutive_failures=self._consecutive_failures,
            error=str(last_error)[:120],
        )
        raise ConnectionError(f"IBKR connection failed after {len(retry_base_delays)} attempts: {last_error}")

    def _on_disconnect(self) -> None:
        """Callback fired when IBKR connection drops."""
        logger.warning("ibkr_disconnected_event", host=self.host, port=self.port)
        self._ib = None  # force reconnect on next call

    # ������ Order management ������
    def submit_order(self, order: Order) -> str:
        """Submit order to IBKR with idempotency via persisted order mapping.

        If *order.order_id* was already submitted successfully (persisted
        in _persisted_order_ids), the duplicate is rejected immediately to
        prevent double-execution after crash/retry.
        """
        # Idempotency guard: reject if this order_id was already filled
        if order.order_id in self._persisted_order_ids:
            logger.warning(
                "ibkr_order_duplicate_rejected",
                order_id=order.order_id,
                perm_id=self._persisted_order_ids[order.order_id],
            )
            return order.order_id

        self._ensure_connected()
        try:
            trade = self._place_order_with_retry(order)
            self._order_map[order.order_id] = trade

            # Persist order_id → IB permId for crash recovery.
            # Write order_id immediately with perm_id=0 as a placeholder so
            # that the idempotency guard is active even if the process crashes
            # before IBKR asynchronously assigns a real permId (T2-01).
            self._persisted_order_ids[order.order_id] = 0
            self._save_order_map()

            # Give IBKR 500 ms to assign the real permId, then update.
            import time as _time

            _time.sleep(0.5)
            perm_id = getattr(trade.order, "permId", 0) or 0
            if perm_id:
                self._persisted_order_ids[order.order_id] = perm_id
                self._save_order_map()

            logger.info(
                "ibkr_order_submitted",
                order_id=order.order_id,
                symbol=order.symbol,
                perm_id=perm_id,
            )
            return order.order_id
        except Exception as exc:
            logger.error("ibkr_order_failed", error=str(exc)[:100])
            raise

    # ������ Retried IBKR placement (connection/timeout resilient) ������
    _ORDER_RETRY_POLICY = RetryPolicy(
        max_attempts=3,
        initial_delay_seconds=1.0,
        max_delay_seconds=10.0,
        retryable_exceptions=(ConnectionError, TimeoutError, IOError, OSError),
    )

    @retry_with_backoff(policy=_ORDER_RETRY_POLICY)
    def _place_order_with_retry(self, order: Order) -> Any:
        """Place a single order via ib_insync, retried on transient errors."""
        from ib_insync import LimitOrder, MarketOrder, Stock

        # Enforce IBKR rate limit (50 req/s hard cap ? 45/s sustained)
        _ibkr_rate_limiter.acquire()

        contract = Stock(order.symbol, "SMART", "USD")
        action = "BUY" if order.side == OrderSide.BUY else "SELL"

        ib_order: Any
        if order.limit_price:
            ib_order = LimitOrder(action, order.quantity, order.limit_price)
        else:
            ib_order = MarketOrder(action, order.quantity)

        return self._ib.placeOrder(contract, ib_order)

    def cancel_order(self, order_id: str) -> bool:
        self._ensure_connected()
        trade = self._order_map.get(order_id)
        if trade is None:
            return False
        self._ib.cancelOrder(trade.order)
        return True

    def cancel_all_pending(self) -> int:
        """Cancel ALL pending orders at the broker via reqGlobalCancel.

        Returns the number of orders that were pending at the time of
        cancellation.
        """
        self._ensure_connected()
        try:
            open_trades = self._ib.openTrades()
            count = len(open_trades)
            self._ib.reqGlobalCancel()
            logger.warning("ibkr_global_cancel_issued", pending_orders=count)
            return count
        except Exception as exc:
            logger.error("ibkr_global_cancel_failed", error=str(exc)[:120])
            return 0

    # ������ Order map persistence (crash recovery) ������
    def _save_order_map(self) -> None:
        """Persist order_id ��� permId mapping atomically."""
        import json
        import shutil
        from pathlib import Path

        path = Path(self._ORDER_MAP_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(self._persisted_order_ids, indent=2))
            # A-10: backup existing file before overwrite
            if path.exists():
                shutil.copy2(path, path.with_suffix(".bak"))
            tmp.replace(path)
        except Exception as exc:
            logger.error("ibkr_order_map_save_failed", error=str(exc)[:120])

    def _load_order_map(self) -> None:
        """Restore order_id ��� permId mapping from disk."""
        import json
        from pathlib import Path

        path = Path(self._ORDER_MAP_FILE)
        if path.exists():
            try:
                self._persisted_order_ids = json.loads(path.read_text())
                logger.info(
                    "ibkr_order_map_restored",
                    count=len(self._persisted_order_ids),
                )
            except Exception as exc:
                logger.error("ibkr_order_map_load_failed", error=str(exc)[:120])
                self._persisted_order_ids = {}

    def get_order_status(self, order_id: str) -> OrderStatus:
        trade = self._order_map.get(order_id)
        if trade is None:
            return OrderStatus.UNKNOWN
        return OrderStatus.FILLED if trade.isDone() else OrderStatus.PENDING

    def get_shortable_shares(self, symbol: str) -> float:
        """Query shortable share availability from IBKR (tick type 236).

        Uses ib_insync reqMktData snapshot mode.  Returns -1 on failure
        or when market data is unavailable / not subscribed.
        Requires IBKR market data subscription.
        """
        self._ensure_connected()
        try:
            from ib_insync import Stock

            contract = Stock(symbol, "SMART", "USD")
            ticker = self._ib.reqMktData(contract, genericTickList="236", snapshot=True)
            deadline = time.time() + 5.0
            while time.time() < deadline:
                self._ib.sleep(0.1)
                shortable = getattr(ticker, "shortableShares", None)
                if shortable is not None and shortable >= 0:
                    self._ib.cancelMktData(contract)
                    return float(shortable)
            self._ib.cancelMktData(contract)
            logger.warning("ibkr_shortable_shares_timeout", symbol=symbol)
            return -1.0
        except Exception as exc:
            logger.warning("ibkr_shortable_shares_failed", symbol=symbol, error=str(exc)[:100])
            return -1.0

    def get_positions(self) -> dict[str, float]:
        self._ensure_connected()
        positions = {}
        for pos in self._ib.positions():
            sym = pos.contract.symbol
            positions[sym] = float(pos.position)
        return positions

    def get_account_balance(self) -> float:
        self._ensure_connected()
        for item in self._ib.accountSummary():
            if item.tag == "NetLiquidation":
                return float(item.value)
        return 0.0

    # ������ Connection convenience methods (used by data/loader.py) ������
    def connect(self) -> None:
        """Public connect helper ��� delegates to _ensure_connected."""
        self._ensure_connected()

    def disconnect(self) -> None:
        """Disconnect from TWS/Gateway if connected."""
        if self._ib is not None and self._ib.isConnected():
            self._ib.disconnect()
            logger.info("ibkr_disconnected")
        self._release_client_id()

    def _release_client_id(self) -> None:
        """Release this instance's client_id from the class-level registry."""
        cid = getattr(self, "client_id", None)
        if cid is not None:
            with IBKRExecutionEngine._active_client_ids_lock:
                if cid in IBKRExecutionEngine._active_client_ids:
                    IBKRExecutionEngine._active_client_ids[cid] -= 1
                    if IBKRExecutionEngine._active_client_ids[cid] <= 0:
                        del IBKRExecutionEngine._active_client_ids[cid]

    def __del__(self) -> None:
        """Safety net: release client_id on garbage collection."""
        self._release_client_id()

    # ������ Historical data (used by data/loader.py) ������
    def get_historical_data(
        self,
        symbol: str,
        duration: str = "1 Y",
        bar_size: str = "1 day",
        what_to_show: str = "TRADES",
    ) -> pd.DataFrame:
        """Fetch historical OHLCV bars from IBKR and return as DataFrame."""
        # Defensive: coerce symbol to a plain string (flatten lists/tuples)
        if isinstance(symbol, (list, tuple)):
            flat = []
            for el in symbol:
                if isinstance(el, (list, tuple)):
                    flat.extend([str(x) for x in el])
                else:
                    flat.append(str(el))
            symbol = ",".join(flat) if len(flat) > 1 else flat[0]
        elif not isinstance(symbol, str):
            symbol = str(symbol)

        self._ensure_connected()
        from ib_insync import Stock

        contract = Stock(symbol, "SMART", "USD")
        bars = self._ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow=what_to_show,
            useRTH=True,
        )
        if not bars:
            return pd.DataFrame()
        df = pd.DataFrame(
            {
                "Open": [b.open for b in bars],
                "High": [b.high for b in bars],
                "Low": [b.low for b in bars],
                "Close": [b.close for b in bars],
                "Volume": [b.volume for b in bars],
            },
            index=pd.DatetimeIndex([b.date for b in bars]),
        )
        df.index.name = "date"
        return df
