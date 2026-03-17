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

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper

from execution.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)

# Module-level rate limiter — shared with IBKRExecutionEngine via the same
# TokenBucketRateLimiter instance imported in ibkr_engine.py.
# Each file instantiates its own bucket; they do NOT share state, which is
# intentional: IBGatewaySync (sync) and IBKRExecutionEngine (async) each
# control their own request pacing at 45 req/s / burst 10.
_ibkr_rate_limiter = TokenBucketRateLimiter(rate=45, burst=10)


class IBWrapper(EWrapper):
    def __init__(self):
        super().__init__()
        self._lock = threading.RLock()  # A-03: protège l'accès concurrent msg-thread / thread principal
        self.current_time = None
        self.contract_details = []
        self.contract_details_done = False
        self.historical_data = []
        self.historical_data_done = False
        self.fundamental_data = None
        self.fundamental_data_done = False
        self.error_msg = None
        self.shortable_shares = -1.0          # A-08: mis à jour par tickGeneric tick 236
        self.shortable_shares_received = False  # A-08: flag de complétion

    def currentTime(self, time_: int):
        with self._lock:
            self.current_time = time_

    def contractDetails(self, reqId, contractDetails):
        with self._lock:
            self.contract_details.append(contractDetails)

    def contractDetailsEnd(self, reqId):
        with self._lock:
            self.contract_details_done = True

    def historicalData(self, reqId, bar):
        with self._lock:
            self.historical_data.append(bar)

    def historicalDataEnd(self, reqId, start, end):
        with self._lock:
            self.historical_data_done = True

    def fundamentalData(self, reqId, data):
        with self._lock:
            self.fundamental_data = data
            self.fundamental_data_done = True

    def tickGeneric(self, reqId: int, tickType: int, value: float):
        """A-08: Capture tick type 236 (shortable shares) from reqMktData snapshot."""
        with self._lock:
            if tickType == 236:
                self.shortable_shares = value
                self.shortable_shares_received = True

    def error(self, reqId, errorCode, errorString, *args):
        with self._lock:
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
        self._req_id_lock = threading.Lock()  # A-06: protège _req_id_counter contre les accès concurrents
        self.connected = False
        self._msg_thread = None  # message processing thread
        self._req_id_counter = 10  # start at 10; incremented before each request
        self.wrapper = IBWrapper()
        self.client = EClient(self.wrapper)

    def _get_next_req_id(self) -> int:
        """Thread-safe increment and return of the next request ID."""
        with self._req_id_lock:
            self._req_id_counter += 1
            return self._req_id_counter

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
        # Wait for response (lecture atomique sous lock)
        t0 = time.time()
        while time.time() - t0 < self.timeout:
            with self.wrapper._lock:
                if self.wrapper.current_time is not None:
                    break
            time.sleep(0.1)
        with self.wrapper._lock:
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
        self.client.reqContractDetails(self._get_next_req_id(), contract)
        t0 = time.time()
        while time.time() - t0 < self.timeout:
            with self.wrapper._lock:
                if self.wrapper.contract_details_done:
                    break
            time.sleep(0.1)
        with self.wrapper._lock:
            return list(self.wrapper.contract_details)

    def get_historical_data(self, symbol, duration="1 Y", bar_size="1 day", what_to_show="TRADES"):
        if not self.connect():
            return None
        # Use a unique, incrementing reqId for every request.
        # Reusing reqId=1 causes error 322 "Duplicate ticker ID" when IB Gateway
        # hasn't fully released the previous request (e.g. after cancelHistoricalData).
        req_id = self._get_next_req_id()

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
        while time.time() - t0 < self.timeout:
            with self.wrapper._lock:
                done = self.wrapper.historical_data_done
                err = self.wrapper.error_msg
            if done:
                break
            # Only break on errors for THIS specific request (check reqId).
            # Stale error 162 from a previous cancelHistoricalData can arrive
            # during the next request and must NOT cut it short.
            if err and err[0] == req_id and err[1] in (162, 200, 354):
                break
            time.sleep(0.1)
        # Cancel if still pending so IB Gateway frees this reqId.
        with self.wrapper._lock:
            done = self.wrapper.historical_data_done
        if not done:
            try:
                self.client.cancelHistoricalData(req_id)
            except Exception:
                pass
            # Brief pause: let IB Gateway process the cancel and flush any
            # delayed 162/366 responses before the next request starts.
            time.sleep(0.3)
        with self.wrapper._lock:
            return list(self.wrapper.historical_data)

    def get_shortable_shares(self, symbol, secType="STK", exchange="SMART", currency="USD"):
        """Query shortable share availability via reqMktData (generic tick 236).

        Returns the number of shortable shares, or -1 on failure/timeout.
        Requires IBKR market data subscription.
        """
        if not self.connect():
            return -1
        self.wrapper.error_msg = None
        self.wrapper.shortable_shares = -1.0          # A-08: reset avant chaque requête
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
                    symbol, err[2],
                )
                break
            time.sleep(0.1)

        with self.wrapper._lock:
            return self.wrapper.fundamental_data

    # Ajoute ici d'autres méthodes selon les besoins (place_order, get_portfolio, etc.)
