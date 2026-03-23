"""IBGatewaySync — synchronous ibapi (EClient/EWrapper) gateway.

Split from ibkr_engine.py as part of C-16: separate ibapi (sync) from
ib_insync (async) so each file has a single responsibility.

Callers that still import IBGatewaySync from execution.ibkr_engine will
continue to work via the backward-compatibility re-export in that module.
"""

import logging
import os
import threading
import time
from typing import Any

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper

from common.ibkr_rate_limiter import GLOBAL_IBKR_RATE_LIMITER as _ibkr_rate_limiter

logger = logging.getLogger(__name__)


class IBWrapper(EWrapper):
    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.RLock()  # A-03: protège l'accès concurrent msg-thread / thread principal
        self.current_time: int | None = None
        self.contract_details: list[Any] = []
        self.contract_details_done = False
        self.historical_data: list[Any] = []
        self.historical_data_done = False
        self.fundamental_data: str | None = None
        self.fundamental_data_done = False
        self.error_msg: tuple | None = None
        self.shortable_shares = -1.0  # A-08: mis à jour par tickGeneric tick 236
        self.shortable_shares_received = False  # A-08: flag de complétion
        # C-08: event-based wake-up for historical data requests (replaces sleep(0.1) polling)
        self._hist_done_event: threading.Event = threading.Event()
        self._hist_req_id: int | None = None  # set by IBGatewaySync before each request

    def currentTime(self, time_: int) -> None:
        with self._lock:
            self.current_time = time_

    def contractDetails(self, reqId: int, contractDetails: Any) -> None:
        with self._lock:
            self.contract_details.append(contractDetails)
        logger.debug("[IBWrapper] contractDetails reqId=%d count=%d", reqId, len(self.contract_details))

    def contractDetailsEnd(self, reqId: int) -> None:
        with self._lock:
            self.contract_details_done = True
        logger.debug("[IBWrapper] contractDetailsEnd reqId=%d", reqId)

    def historicalData(self, reqId: int, bar: Any) -> None:
        with self._lock:
            self.historical_data.append(bar)
        logger.debug("[IBWrapper] historicalData reqId=%d bars=%d", reqId, len(self.historical_data))

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        with self._lock:
            self.historical_data_done = True
        logger.debug("[IBWrapper] historicalDataEnd reqId=%d start=%s end=%s", reqId, start, end)
        self._hist_done_event.set()  # C-08: wake up get_historical_data immediately

    def fundamentalData(self, reqId: int, data: str) -> None:
        with self._lock:
            self.fundamental_data = data
            self.fundamental_data_done = True
        logger.debug("[IBWrapper] fundamentalData reqId=%d bytes=%d", reqId, len(data))

    def tickGeneric(self, reqId: int, tickType: int, value: float) -> None:
        """A-08: Capture tick type 236 (shortable shares) from reqMktData snapshot."""
        with self._lock:
            if tickType == 236:
                self.shortable_shares = value
                self.shortable_shares_received = True
        logger.debug("[IBWrapper] tickGeneric reqId=%d tickType=%d value=%s", reqId, tickType, value)

    def error(self, reqId: int, errorCode: int, errorString: str, *args: Any) -> None:
        with self._lock:
            self.error_msg = (reqId, errorCode, errorString)
        # Error codes 2104, 2106, 2158 are informational - not real errors
        if errorCode not in (2104, 2106, 2158):
            logger.warning("[IBWrapper] Error %d: %s (reqId=%d)", errorCode, errorString, reqId)
        if args:
            logger.debug("[IBWrapper] error extra data reqId=%d extra=%s", reqId, args)
        # C-08: unblock get_historical_data immediately on fatal data errors for the current request
        if errorCode in (162, 200, 354) and reqId == self._hist_req_id:
            self._hist_done_event.set()


class IBGatewaySync:
    """
    Connexion robuste a IB Gateway via TWS API Sync Wrapper.
    - Reconnexion automatique
    - Validation de connexion
    - Gestion des erreurs
    - Utilisation synchrone (recommandee par IBKR)
    """

    def __init__(self, host: str = "127.0.0.1", port: int | None = None, client_id: int = 1, timeout: int = 30) -> None:
        self.host = host
        self.port = port if port is not None else int(os.getenv("IBKR_PORT", "4002"))
        self.client_id = client_id
        self.timeout = timeout
        self.app = None
        self._lock = threading.Lock()
        self._req_id_lock = threading.Lock()  # A-06: protège _req_id_counter contre les accès concurrents
        self.connected = False
        self._msg_thread: threading.Thread | None = None  # message processing thread
        self._req_id_counter = 10  # start at 10; incremented before each request
        self.wrapper = IBWrapper()
        self.client = EClient(self.wrapper)

    def _get_next_req_id(self) -> int:
        """Thread-safe increment and return of the next request ID."""
        with self._req_id_lock:
            self._req_id_counter += 1
            return self._req_id_counter

    def connect(self) -> bool:
        with self._lock:
            if not self.connected:
                try:
                    self.client.connect(self.host, self.port, self.client_id)
                    # Start the message processing loop in a background thread
                    # Without this, EClient sends requests but never reads responses
                    self._msg_thread = threading.Thread(target=self.client.run, daemon=True)
                    self._msg_thread.start()
                    # Give the reader thread a moment to initialize
                    time.sleep(0.5)
                    self.connected = True
                    logger.info(
                        "[IBGatewaySync] Connecte a IB Gateway %s:%d (client_id=%d)",
                        self.host,
                        self.port,
                        self.client_id,
                    )
                except Exception as e:
                    logger.error("[IBGatewaySync] Connexion echouee: %s", e)
                    self.connected = False
            return self.connected

    def disconnect(self) -> None:
        with self._lock:
            if self.connected:
                self.client.disconnect()
                self.connected = False
                self._msg_thread = None
                logger.info("[IBGatewaySync] Deconnecte.")

    def is_connected(self) -> bool:
        return self.connected

    def get_current_time(self) -> int | None:
        if not self.connect():
            return None
        self.wrapper.current_time = None
        self.client.reqCurrentTime()
        # Wait for response (lecture atomique sous lock)
        t0 = time.time()
        while time.time() - t0 < self.timeout:
            with self.wrapper._lock:
                if self.wrapper.current_time is not None:
                    break
            time.sleep(0.1)
        with self.wrapper._lock:
            return self.wrapper.current_time

    def get_contract_details(
        self, symbol: str, secType: str = "STK", exchange: str = "SMART", currency: str = "USD"
    ) -> list[Any] | None:
        if not self.connect():
            return None
        self.wrapper.contract_details = []
        self.wrapper.contract_details_done = False
        contract = Contract()
        contract.symbol = symbol
        contract.secType = secType
        contract.exchange = exchange
        contract.currency = currency
        self.client.reqContractDetails(self._get_next_req_id(), contract)
        t0 = time.time()
        while time.time() - t0 < self.timeout:
            with self.wrapper._lock:
                if self.wrapper.contract_details_done:
                    break
            time.sleep(0.1)
        with self.wrapper._lock:
            return list(self.wrapper.contract_details)

    def get_historical_data(
        self, symbol: str, duration: str = "1 Y", bar_size: str = "1 day", what_to_show: str = "TRADES"
    ) -> list[Any] | None:
        if not self.connect():
            return None
        # Use a unique, incrementing reqId for every request.
        # Reusing reqId=1 causes error 322 "Duplicate ticker ID" when IB Gateway
        # hasn't fully released the previous request (e.g. after cancelHistoricalData).
        req_id = self._get_next_req_id()

        self.wrapper.historical_data = []
        self.wrapper.historical_data_done = False
        self.wrapper.error_msg = None
        # C-08: register this request's req_id and clear the event before sending
        self.wrapper._hist_req_id = req_id
        self.wrapper._hist_done_event.clear()
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
        # C-08: block until historicalDataEnd fires the event (or error unblocks it),
        # replacing the while/sleep(0.1) polling loop.
        completed = self.wrapper._hist_done_event.wait(timeout=self.timeout)
        # Cancel if still pending so IB Gateway frees this reqId.
        with self.wrapper._lock:
            done = self.wrapper.historical_data_done
        if not done or not completed:
            try:
                self.client.cancelHistoricalData(req_id)
            except Exception:
                pass
            # Brief pause: let IB Gateway process the cancel and flush any
            # delayed 162/366 responses before the next request starts.
            time.sleep(0.3)
        with self.wrapper._lock:
            return list(self.wrapper.historical_data)

    def get_shortable_shares(
        self, symbol: str, secType: str = "STK", exchange: str = "SMART", currency: str = "USD"
    ) -> float:
        """Query shortable share availability via reqMktData (generic tick 236).

        Returns the number of shortable shares, or -1 on failure/timeout.
        Requires IBKR market data subscription.
        """
        if not self.connect():
            return -1
        self.wrapper.error_msg = None
        self.wrapper.shortable_shares = -1.0  # A-08: reset avant chaque requête
        self.wrapper.shortable_shares_received = False  # A-08: reset flag

        contract = Contract()
        contract.symbol = symbol
        contract.secType = secType
        contract.exchange = exchange
        contract.currency = currency

        # Generic tick 236 = shortable shares; save req_id for cancelMktData
        req_id = self._get_next_req_id()
        self.client.reqMktData(req_id, contract, "236", True, False, [])

        t0 = time.time()
        while time.time() - t0 < self.timeout:
            with self.wrapper._lock:
                received = self.wrapper.shortable_shares_received
                err = self.wrapper.error_msg
            if received:
                break
            if err and err[0] == req_id and err[1] in (162, 200, 354):
                break
            time.sleep(0.2)
            # Snapshot requests auto-complete; give a short window
            if time.time() - t0 > 3.0:
                break

        self.client.cancelMktData(req_id)  # A-08: utilise req_id correct
        with self.wrapper._lock:
            return self.wrapper.shortable_shares

    def get_earnings_calendar(
        self, symbol: str, secType: str = "STK", exchange: str = "SMART", currency: str = "USD"
    ) -> str | None:
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

        self.client.reqFundamentalData(self._get_next_req_id(), contract, "CalendarReport", [])

        t0 = time.time()
        while time.time() - t0 < self.timeout:
            with self.wrapper._lock:
                done = self.wrapper.fundamental_data_done
                err = self.wrapper.error_msg
            if done:
                break
            if err and err[1] in (162, 200, 354, 430):
                logger.warning(
                    "[IBGatewaySync] Fundamental data unavailable for %s: %s",
                    symbol,
                    err[2],
                )
                break
            time.sleep(0.1)

        with self.wrapper._lock:
            return self.wrapper.fundamental_data

    # Ajoute ici d'autres méthodes selon les besoins (place_order, get_portfolio, etc.)
