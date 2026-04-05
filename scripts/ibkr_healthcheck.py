"""
Test IBKR Gateway connection and data access using IBGatewaySync
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))
from execution.ibkr_engine import IBGatewaySync
from ibapi.contract import Contract
import time

# Configuration
HOST = "127.0.0.1"
PORT = 4002  # Port API selon settings IBKR Gateway
CLIENT_ID = 1001
TIMEOUT = 30

# Test symbol
SYMBOL = "AAPL"
EXCHANGE = "SMART"
CURRENCY = "USD"

# Create IBGatewaySync instance
ibkr = IBGatewaySync(host=HOST, port=PORT, client_id=CLIENT_ID, timeout=TIMEOUT)

# Wait for connection
print("Waiting for IBKR connection...")
for _ in range(TIMEOUT):
    if ibkr.connected:
        print("Connected to IBKR Gateway!")
        break
    time.sleep(1)
else:
    print("[ERROR] Could not connect to IBKR Gateway.")
    exit(1)

# Create contract
contract = Contract()
contract.symbol = SYMBOL
contract.secType = "STK"
contract.exchange = EXCHANGE
contract.currency = CURRENCY

# Request historical data
print(f"Requesting historical data for {SYMBOL}...")
ibkr.wrapper.historical_data = []
ibkr.client.reqHistoricalData(
    1, contract, "", "1 D", "1 min", "TRADES", 0, 1, False, []
)

# Wait for data
for _ in range(TIMEOUT):
    if ibkr.wrapper.historical_data:
        print(f"Received {len(ibkr.wrapper.historical_data)} bars for {SYMBOL}.")
        break
    time.sleep(1)
else:
    print(f"[ERROR] No data received for {SYMBOL}.")

# Disconnect
ibkr.client.disconnect()
print("Disconnected.")
