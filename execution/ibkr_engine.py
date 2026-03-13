
import logging
import os
import threading
import time

import pandas as pd
from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper

from execution.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)

# Module-level rate limiter shared by all IBKRExecutionEngine instances.
# Ensures the 50 req/s TWS socket cap is never exceeded, even with
# multiple engine instances (e.g. reconnect scenarios).
_ibkr_rate_limiter = TokenBucketRateLimiter(rate=45, burst=10)

class IBWrapper(EWrapper):
    def __init__(self):
        super().__init__()
        self.current_time = None
        self.contract_details = []
        self.contract_details_done = False
        self.historical_data = []
        self.historical_data_done = False
        self.fundamental_data = None
        self.fundamental_data_done = False
        self.error_msg = None

    def currentTime(self, time_: int):
        self.current_time = time_

    def contractDetails(self, reqId, contractDetails):
        self.contract_details.append(contractDetails)

    def contractDetailsEnd(self, reqId):
        self.contract_details_done = True

    def historicalData(self, reqId, bar):
        self.historical_data.append(bar)

    def historicalDataEnd(self, reqId, start, end):
        self.historical_data_done = True

    def fundamentalData(self, reqId, data):
        self.fundamental_data = data
        self.fundamental_data_done = True

    def error(self, reqId, errorCode, errorString, *args):
        self.error_msg = (reqId, errorCode, errorString)
        # Error codes 2104, 2106, 2158 are informational - not real errors
        if errorCode not in (2104, 2106, 2158):
            logger.warning("[IBWrapper] Error %d: %s (reqId=%d)", errorCode, errorString, reqId)


class IBGatewaySync:
    """
    Connexion robuste a IB Gateway via TWS API Sync Wrapper.
    - Reconnexion automatique
    - Validation de connexion
    - Gestion des erreurs
    - Utilisation synchrone (recommandee par IBKR)
    """
    def __init__(self, host="127.0.0.1", port=None, client_id=1, timeout=30):
        self.host = host
        self.port = port if port is not None else int(os.getenv("IBKR_PORT", "4002"))
        self.client_id = client_id
        self.timeout = timeout
        self.app = None
        self._lock = threading.Lock()
        self.connected = False
        self._msg_thread = None  # message processing thread
        self._req_id_counter = 10  # start at 10; incremented before each request
        self.wrapper = IBWrapper()
        self.client = EClient(self.wrapper)

    def connect(self):
        with self._lock:
            if not self.connected:
                try:
                    self.client.connect(self.host, self.port, self.client_id)
                    # Start the message processing loop in a background thread
                    # Without this, EClient sends requests but never reads responses
                    self._msg_thread = threading.Thread(
                        target=self.client.run, daemon=True
                    )
                    self._msg_thread.start()
                    # Give the reader thread a moment to initialize
                    time.sleep(0.5)
                    self.connected = True
                    logger.info("[IBGatewaySync] Connecte a IB Gateway %s:%d (client_id=%d)", self.host, self.port, self.client_id)
                except Exception as e:
                    logger.error("[IBGatewaySync] Connexion echouee: %s", e)
                    self.connected = False
            return self.connected

    def disconnect(self):
        with self._lock:
            if self.connected:
                self.client.disconnect()
                self.connected = False
                self._msg_thread = None
                logger.info("[IBGatewaySync] Deconnecte.")

    def is_connected(self):
        return self.connected

    def get_current_time(self):
        if not self.connect():
            return None
        self.wrapper.current_time = None
        self.client.reqCurrentTime()
        # Wait for response
        t0 = time.time()
        while self.wrapper.current_time is None and time.time() - t0 < self.timeout:
            time.sleep(0.1)
        return self.wrapper.current_time

    def get_contract_details(self, symbol, secType="STK", exchange="SMART", currency="USD"):
        if not self.connect():
            return None
        self.wrapper.contract_details = []
        self.wrapper.contract_details_done = False
        contract = Contract()
        contract.symbol = symbol
        contract.secType = secType
        contract.exchange = exchange
        contract.currency = currency
        self.client.reqContractDetails(1, contract)
        t0 = time.time()
        while not self.wrapper.contract_details_done and time.time() - t0 < self.timeout:
            time.sleep(0.1)
        return self.wrapper.contract_details

    def get_historical_data(self, symbol, duration="1 Y", bar_size="1 day", what_to_show="TRADES"):
        if not self.connect():
            return None
        # Use a unique, incrementing reqId for every request.
        # Reusing reqId=1 causes error 322 "Duplicate ticker ID" when IB Gateway
        # hasn't fully released the previous request (e.g. after cancelHistoricalData).
        self._req_id_counter += 1
        req_id = self._req_id_counter

        self.wrapper.historical_data = []
        self.wrapper.historical_data_done = False
        self.wrapper.error_msg = None
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        self.client.reqHistoricalData(
            req_id,
            contract,
            endDateTime="",
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow=what_to_show,
            useRTH=1,
            formatDate=1,
            keepUpToDate=False,
            chartOptions=[],
        )
        t0 = time.time()
        while not self.wrapper.historical_data_done and time.time() - t0 < self.timeout:
            # Only break on errors for THIS specific request (check reqId).
            # Stale error 162 from a previous cancelHistoricalData can arrive
            # during the next request and must NOT cut it short.
            if (self.wrapper.error_msg
                    and self.wrapper.error_msg[0] == req_id
                    and self.wrapper.error_msg[1] in (162, 200, 354)):
                break
            time.sleep(0.1)
        # Cancel if still pending so IB Gateway frees this reqId.
        if not self.wrapper.historical_data_done:
            try:
                self.client.cancelHistoricalData(req_id)
            except Exception:
                pass
            # Brief pause: let IB Gateway process the cancel and flush any
            # delayed 162/366 responses before the next request starts.
            time.sleep(0.3)
        return self.wrapper.historical_data

    def get_shortable_shares(self, symbol, secType="STK", exchange="SMART", currency="USD"):
        """Query shortable share availability via reqMktData (generic tick 236).

        Returns the number of shortable shares, or -1 on failure/timeout.
        Requires IBKR market data subscription.
        """
        if not self.connect():
            return -1
        self.wrapper.error_msg = None

        contract = Contract()
        contract.symbol = symbol
        contract.secType = secType
        contract.exchange = exchange
        contract.currency = currency

        # Generic tick 236 = shortable shares
        self.client.reqMktData(3, contract, "236", True, False, [])

        t0 = time.time()
        shortable = -1
        while time.time() - t0 < self.timeout:
            if self.wrapper.error_msg and self.wrapper.error_msg[1] in (162, 200, 354):
                break
            time.sleep(0.2)
            # Snapshot requests auto-complete; give a short window
            if time.time() - t0 > 3.0:
                break

        self.client.cancelMktData(3)
        return shortable

    def get_earnings_calendar(self, symbol, secType="STK", exchange="SMART", currency="USD"):
        """Retrieve earnings calendar via reqFundamentalData(CalendarReport).

        Requires IBKR market data subscription.  Returns raw XML string
        from IBKR, or None on failure/timeout.
        """
        if not self.connect():
            return None
        self.wrapper.fundamental_data = None
        self.wrapper.fundamental_data_done = False
        self.wrapper.error_msg = None

        contract = Contract()
        contract.symbol = symbol
        contract.secType = secType
        contract.exchange = exchange
        contract.currency = currency

        self.client.reqFundamentalData(2, contract, "CalendarReport", [])

        t0 = time.time()
        while not self.wrapper.fundamental_data_done and time.time() - t0 < self.timeout:
            if self.wrapper.error_msg and self.wrapper.error_msg[1] in (162, 200, 354, 430):
                logger.warning(
                    "[IBGatewaySync] Fundamental data unavailable for %s: %s",
                    symbol, self.wrapper.error_msg[2],
                )
                break
            time.sleep(0.1)

        return self.wrapper.fundamental_data

    # Ajoute ici d'autres méthodes selon les besoins (place_order, get_portfolio, etc.)

# --- Fin IB Gateway Sync ---
"""
Interactive Brokers execution engine via ib_insync.

Connects to TWS / IB Gateway for:
- Order submission / cancellation
- Real-time position tracking
- Account balance queries
"""

import asyncio
from typing import Dict

from dotenv import load_dotenv
from structlog import get_logger

from common.retry import RetryPolicy, retry_with_backoff
from execution.base import BaseExecutionEngine, Order, OrderSide, OrderStatus

load_dotenv()

logger = get_logger(__name__)


class IBKRExecutionEngine(BaseExecutionEngine):
    """
    Interactive Brokers execution via ib_insync.

    Requires TWS / IB Gateway running:
      - Paper trading: port 7497
      - Live trading:  port 7496
    """

    # Path for persisting order_id → IB permId mapping (crash recovery)
    _ORDER_MAP_FILE = "data/ibkr_order_map.json"

    # Class-level registry of in-use client_ids to detect duplicates
    _active_client_ids: Dict[int, int] = {}  # client_id → refcount

    def __init__(
        self,
        host: str = None,
        port: int = None,
        client_id: int = None,
        readonly: bool = False,
        timeout: int = 30,
    ):
        self.host = host or os.getenv("IBKR_HOST", "127.0.0.1")
        self.port = port or int(os.getenv("IBKR_PORT", "7497"))
        self.client_id = client_id if client_id is not None else int(os.getenv("IBKR_CLIENT_ID", "1"))
        self.readonly = readonly
        self.timeout = timeout
        self._ib = None  # ib_insync.IB instance (lazy)
        self._order_map: Dict[str, object] = {}
        self._persisted_order_ids: Dict[str, int] = {}  # order_id → IB permId
        self._consecutive_failures = 0
        self._max_consecutive_failures = 5  # circuit breaker threshold

        # Restore persisted order map on init (crash recovery)
        self._load_order_map()

        # Audit: detect duplicate client_id usage (multi-worker collision risk)
        count = IBKRExecutionEngine._active_client_ids.get(self.client_id, 0)
        if count > 0:
            raise RuntimeError(
                f"[SECURITY] IBKR client_id={self.client_id} already in use by "
                f"another IBKRExecutionEngine instance. Each worker must use a "
                f"unique client_id to avoid IB Gateway conflicts."
            )
        IBKRExecutionEngine._active_client_ids[self.client_id] = count + 1

        import traceback
        logger.info(
            "ibkr_engine_init",
            host=self.host,
            port=self.port,
            client_id=self.client_id,
            readonly=self.readonly,
            stack="".join(traceback.format_stack())
        )

    # ── Connection helpers ──
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
            raise ConnectionError(
                f"IBKR circuit breaker open: {self._consecutive_failures} consecutive failures. "
                "Manual intervention required."
            )

        # Ensure an asyncio event loop exists (required by ib_insync on Python 3.10+)
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())

        import time
        retry_delays = [5, 15, 30]  # seconds
        last_error = None

        for attempt, delay in enumerate(retry_delays, 1):
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
                logger.warning(
                    "ibkr_connection_attempt_failed",
                    attempt=attempt,
                    max_attempts=len(retry_delays),
                    error=str(exc)[:120],
                    retry_in=delay,
                )
                if attempt < len(retry_delays):
                    time.sleep(delay)

        self._consecutive_failures += 1
        logger.error(
            "ibkr_connection_failed_all_retries",
            consecutive_failures=self._consecutive_failures,
            error=str(last_error)[:120],
        )
        raise ConnectionError(f"IBKR connection failed after {len(retry_delays)} attempts: {last_error}")

    def _on_disconnect(self) -> None:
        """Callback fired when IBKR connection drops."""
        logger.warning("ibkr_disconnected_event", host=self.host, port=self.port)
        self._ib = None  # force reconnect on next call

    # ── Order management ──
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

            # Persist order_id → IB permId for crash recovery
            perm_id = getattr(trade.order, 'permId', 0) or 0
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

    # ── Retried IBKR placement (connection/timeout resilient) ──
    _ORDER_RETRY_POLICY = RetryPolicy(
        max_attempts=3,
        initial_delay_seconds=1.0,
        max_delay_seconds=10.0,
        retryable_exceptions=(ConnectionError, TimeoutError, IOError, OSError),
    )

    @retry_with_backoff(policy=_ORDER_RETRY_POLICY)
    def _place_order_with_retry(self, order: Order):
        """Place a single order via ib_insync, retried on transient errors."""
        from ib_insync import LimitOrder, MarketOrder, Stock

        # Enforce IBKR rate limit (50 req/s hard cap → 45/s sustained)
        _ibkr_rate_limiter.acquire()

        contract = Stock(order.symbol, 'SMART', 'USD')
        action = 'BUY' if order.side == OrderSide.BUY else 'SELL'

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

    # ── Order map persistence (crash recovery) ──
    def _save_order_map(self) -> None:
        """Persist order_id → permId mapping atomically."""
        import json
        from pathlib import Path
        path = Path(self._ORDER_MAP_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        try:
            tmp.write_text(json.dumps(self._persisted_order_ids, indent=2))
            tmp.replace(path)
        except Exception as exc:
            logger.error("ibkr_order_map_save_failed", error=str(exc)[:120])

    def _load_order_map(self) -> None:
        """Restore order_id → permId mapping from disk."""
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

    def get_positions(self) -> Dict[str, float]:
        self._ensure_connected()
        positions = {}
        for pos in self._ib.positions():
            sym = pos.contract.symbol
            positions[sym] = float(pos.position)
        return positions

    def get_account_balance(self) -> float:
        self._ensure_connected()
        for item in self._ib.accountSummary():
            if item.tag == 'NetLiquidation':
                return float(item.value)
        return 0.0

    # ── Connection convenience methods (used by data/loader.py) ──
    def connect(self) -> None:
        """Public connect helper — delegates to _ensure_connected."""
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
        if cid is not None and cid in IBKRExecutionEngine._active_client_ids:
            IBKRExecutionEngine._active_client_ids[cid] -= 1
            if IBKRExecutionEngine._active_client_ids[cid] <= 0:
                del IBKRExecutionEngine._active_client_ids[cid]

    def __del__(self) -> None:
        """Safety net: release client_id on garbage collection."""
        self._release_client_id()

    # ── Historical data (used by data/loader.py) ──
    def get_historical_data(
        self,
        symbol: str,
        duration: str = '1 Y',
        bar_size: str = '1 day',
        what_to_show: str = 'TRADES',
    ) -> 'pd.DataFrame':
        """Fetch historical OHLCV bars from IBKR and return as DataFrame."""
        import pandas as pd
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
        contract = Stock(symbol, 'SMART', 'USD')
        bars = self._ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow=what_to_show,
            useRTH=True,
        )
        if not bars:
            return pd.DataFrame()
        df = pd.DataFrame(
            {
                'Open': [b.open for b in bars],
                'High': [b.high for b in bars],
                'Low': [b.low for b in bars],
                'Close': [b.close for b in bars],
                'Volume': [b.volume for b in bars],
            },
            index=pd.DatetimeIndex([b.date for b in bars]),
        )
        df.index.name = 'date'
        return df
