"""Lightweight CCXT execution engine shim used for tests.

Provides a minimal `CCXTExecutionEngine` implementation with `submit_order`
to satisfy unit tests and avoid importing the full production engine.
"""

from __future__ import annotations

import uuid
from typing import Any


class CCXTExecutionEngine:
    """Minimal execution engine used in tests.

    This shim does not perform real API calls. It provides the methods
    tests expect (`submit_order`) and returns simple mock responses.
    """

    def __init__(self, api_key: str | None = None, secret: str | None = None):
        self.api_key = api_key
        self.secret = secret

    def submit_order(
        self, symbol: str, side: str, amount: float, price: float | None = None, order_type: str = "market"
    ) -> dict[str, Any]:
        """Submit a mock order and return a synthetic order record.

        Tests only check that an order can be submitted and a dict-like
        response is returned, so this minimal implementation is sufficient.
        """
        order_id = str(uuid.uuid4())
        resp = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": price,
            "type": order_type,
            "status": "open",
        }
        return resp

    def cancel_order(self, order_id: str) -> bool:
        return True

    def get_order(self, order_id: str) -> dict[str, Any]:
        return {"id": order_id, "status": "open"}
