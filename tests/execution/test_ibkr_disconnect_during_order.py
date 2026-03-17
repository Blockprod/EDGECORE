"""A-13 — Tests: IBKR disconnection during order submission/fill.

Covers two scenarios:
  1. The IB gateway is disconnected *before* submit_order() → ConnectionError raised,
     no partial commit in _persisted_order_ids.
  2. After reconnection the engine can re-submit successfully.
"""
import pytest
from unittest.mock import MagicMock, patch

from execution.ibkr_engine import IBKRExecutionEngine
from execution.base import Order, OrderSide


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_order(order_id: str = "ORD-001") -> Order:
    return Order(
        order_id=order_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        limit_price=None,
    )


def _build_engine() -> IBKRExecutionEngine:
    """Build an engine instance with IB insync stubbed out."""
    with patch.dict("sys.modules", {"ib_insync": MagicMock()}):
        engine = IBKRExecutionEngine.__new__(IBKRExecutionEngine)
        engine.host = "127.0.0.1"
        engine.port = 7497
        engine.client_id = 99
        engine.readonly = False
        engine.timeout = 5
        engine._ib = None
        engine._order_map = {}
        engine._persisted_order_ids = {}
        engine._consecutive_failures = 0
        engine._max_consecutive_failures = 5
        engine._last_failure_time = 0.0
        engine._cb_reset_timeout = 300
        # Prevent real disk I/O
        engine._load_order_map = MagicMock()
        engine._save_order_map = MagicMock()
        return engine


# ---------------------------------------------------------------------------
# Test 1 — submit_order raises ConnectionError when IB is unreachable
# ---------------------------------------------------------------------------

class TestDisconnectDuringOrderSubmission:
    def test_connection_error_raised_when_disconnected(self):
        """submit_order() must propagate ConnectionError if all retries fail."""
        engine = _build_engine()

        # Simulate: _ensure_connected always fails
        engine._ensure_connected = MagicMock(
            side_effect=ConnectionError("Simulated IBKR unreachable")
        )

        order = _make_order("ORD-DISC-001")
        with pytest.raises(ConnectionError):
            engine.submit_order(order)

    def test_no_partial_commit_when_connection_fails(self):
        """When ConnectionError occurs before placement, order must NOT appear
        in _persisted_order_ids (no partial commit)."""
        engine = _build_engine()
        engine._ensure_connected = MagicMock(
            side_effect=ConnectionError("Simulated IBKR unreachable")
        )

        order = _make_order("ORD-DISC-002")
        try:
            engine.submit_order(order)
        except ConnectionError:
            pass

        assert order.order_id not in engine._persisted_order_ids, (
            "Order must not be committed if connection failed before placement"
        )

    def test_no_partial_commit_when_placement_raises(self):
        """When _place_order_with_retry raises (e.g. IBKR rejects the order),
        order must NOT appear in _persisted_order_ids."""
        engine = _build_engine()
        # Connection succeeds …
        engine._ensure_connected = MagicMock(return_value=None)
        # … but the placement itself fails
        engine._place_order_with_retry = MagicMock(
            side_effect=RuntimeError("Order rejected by IBKR")
        )

        order = _make_order("ORD-DISC-003")
        with pytest.raises(RuntimeError):
            engine.submit_order(order)

        assert order.order_id not in engine._persisted_order_ids


# ---------------------------------------------------------------------------
# Test 2 — reconnect after disconnect restores ability to submit
# ---------------------------------------------------------------------------

class TestReconnectAfterDisconnect:
    def test_reconnect_clears_ib_reference(self):
        """_on_disconnect() must set self._ib = None so next call reconnects."""
        engine = _build_engine()
        mock_ib = MagicMock()
        mock_ib.isConnected.return_value = True
        engine._ib = mock_ib

        engine._on_disconnect()

        assert engine._ib is None

    def test_resubmit_succeeds_after_reconnect(self):
        """After a disconnect, submit_order() can succeed once reconnected."""
        engine = _build_engine()
        engine._on_disconnect()  # clears engine._ib

        # Now _ensure_connected succeeds (simulates reconnect)
        engine._ensure_connected = MagicMock(return_value=None)
        mock_trade = MagicMock()
        mock_trade.order.permId = 42
        engine._place_order_with_retry = MagicMock(return_value=mock_trade)

        order = _make_order("ORD-RECON-001")
        result = engine.submit_order(order)

        assert result == order.order_id
        assert order.order_id in engine._persisted_order_ids

    def test_idempotency_prevents_double_submission(self):
        """Once an order is in _persisted_order_ids, resubmitting is a no-op."""
        engine = _build_engine()
        engine._ensure_connected = MagicMock(return_value=None)
        engine._place_order_with_retry = MagicMock()

        order = _make_order("ORD-IDEM-001")
        # Manually mark as already persisted
        engine._persisted_order_ids[order.order_id] = 99

        result = engine.submit_order(order)

        assert result == order.order_id
        # _place_order_with_retry must NOT have been called again
        engine._place_order_with_retry.assert_not_called()
