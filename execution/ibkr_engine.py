
import os
import threading
import time
import pandas as pd
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract

class IBWrapper(EWrapper):
    def __init__(self):
        super().__init__()
        self.current_time = None
        self.contract_details = []
        self.historical_data = []
        self.error_msg = None

    def currentTime(self, time_: int):
        self.current_time = time_

    def contractDetails(self, reqId, contractDetails):
        self.contract_details.append(contractDetails)

    def historicalData(self, reqId, bar):
        self.historical_data.append(bar)

    def error(self, reqId, errorCode, errorString):
        self.error_msg = (reqId, errorCode, errorString)


class IBGatewaySync:
    """
    Connexion robuste à IB Gateway via TWS API Sync Wrapper.
    - Reconnexion automatique
    - Validation de connexion
    - Gestion des erreurs
    - Utilisation synchrone (recommandée par IBKR)
    """
    def __init__(self, host="127.0.0.1", port=None, client_id=1, timeout=30):
        import inspect
        print(f"[DEBUG] IBGatewaySync loaded from: {inspect.getfile(self.__class__)}")
        self.host = host
        self.port = port if port is not None else int(os.getenv("IBKR_PORT", "4002"))
        self.client_id = client_id
        self.timeout = timeout
        self.app = None
        self._lock = threading.Lock()
        self.connected = False
        self.wrapper = IBWrapper()
        self.client = EClient(self.wrapper)
        self._monitor_thread = threading.Thread(target=self._monitor_connection, daemon=True)
        self._monitor_thread.start()

    def _monitor_connection(self):
        while True:
            with self._lock:
                if not self.connected:
                    try:
                        self.client.connect(self.host, self.port, self.client_id)
                        self.connected = True
                        print(f"[IBGatewaySync] Reconnecté automatiquement à IB Gateway {self.host}:{self.port} (client_id={self.client_id})")
                    except Exception as e:
                        print(f"[IBGatewaySync] Reconnexion échouée: {e}")
                else:
                    # Optionally, check connection health here
                    pass
            time.sleep(5)

    def connect(self):
        with self._lock:
            if not self.connected:
                try:
                    self.client.connect(self.host, self.port, self.client_id)
                    self.connected = True
                    print(f"[IBGatewaySync] Connecté à IB Gateway {self.host}:{self.port} (client_id={self.client_id})")
                except Exception as e:
                    print(f"[IBGatewaySync] Connexion échouée: {e}")
                    self.connected = False
            return self.connected

    def disconnect(self):
        with self._lock:
            if self.connected:
                self.client.disconnect()
                print("[IBGatewaySync] Déconnecté.")
                self.connected = False

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
        contract = Contract()
        contract.symbol = symbol
        contract.secType = secType
        contract.exchange = exchange
        contract.currency = currency
        self.client.reqContractDetails(1, contract)
        t0 = time.time()
        while not self.wrapper.contract_details and time.time() - t0 < self.timeout:
            time.sleep(0.1)
        return self.wrapper.contract_details

    def get_historical_data(self, symbol, duration="1 Y", bar_size="1 day", what_to_show="TRADES"):
        if not self.connect():
            return None
        self.wrapper.historical_data = []
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        self.client.reqHistoricalData(
            1,
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
        while not self.wrapper.historical_data and time.time() - t0 < self.timeout:
            time.sleep(0.1)
        return self.wrapper.historical_data

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
from dotenv import load_dotenv
from execution.base import BaseExecutionEngine, Order, OrderSide, OrderStatus
from typing import Dict
from structlog import get_logger

load_dotenv()

logger = get_logger(__name__)


class IBKRExecutionEngine(BaseExecutionEngine):
    """
    Interactive Brokers execution via ib_insync.

    Requires TWS / IB Gateway running:
      - Paper trading: port 7497
      - Live trading:  port 7496
    """

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
        self._consecutive_failures = 0
        self._max_consecutive_failures = 5  # circuit breaker threshold

        import traceback
        logger.info(
            "ibkr_engine_init",
            host=self.host,
            port=self.port,
            client_id=self.client_id,
            readonly=self.readonly,
            stack=traceback.format_stack()
        )
        # Audit: refuse client_id=1 en bulk/async
        if self.client_id == 1:
            raise RuntimeError("[SECURITY] IBKR client_id=1 utilisé en contexte multi-worker/bulk. Veuillez passer un client_id unique à chaque worker !")

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
        self._ensure_connected()
        try:
            from ib_insync import Stock, LimitOrder, MarketOrder
            contract = Stock(order.symbol, 'SMART', 'USD')
            action = 'BUY' if order.side == OrderSide.BUY else 'SELL'

            if order.limit_price:
                ib_order = LimitOrder(action, order.quantity, order.limit_price)
            else:
                ib_order = MarketOrder(action, order.quantity)

            trade = self._ib.placeOrder(contract, ib_order)
            self._order_map[order.order_id] = trade
            logger.info("ibkr_order_submitted", order_id=order.order_id, symbol=order.symbol)
            return order.order_id
        except Exception as exc:
            logger.error("ibkr_order_failed", error=str(exc)[:100])
            raise

    def cancel_order(self, order_id: str) -> bool:
        self._ensure_connected()
        trade = self._order_map.get(order_id)
        if trade is None:
            return False
        self._ib.cancelOrder(trade.order)
        return True

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
