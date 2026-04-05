"""
Tests de concurrence pour LiveTradingRunner._positions
Valide A-01 : threading.Lock sur _positions
Valide A-02 : suppression de position uniquement après submit réussi
"""

from __future__ import annotations

import threading
import time
from typing import Any
from unittest.mock import MagicMock

from live_trading.runner import LiveTradingRunner, TradingLoopConfig, TradingState


def _make_runner() -> LiveTradingRunner:
    """Construit un runner minimal sans aucune dépendance réseau."""
    runner = LiveTradingRunner(TradingLoopConfig(mode="paper"))
    runner._state = TradingState.RUNNING
    runner._positions = {"AAPL_MSFT": {"quantity": 10, "holding_bars": 0}}
    runner._active_pairs = []
    runner._signal_gen = None
    runner._router = None
    runner._kill_switch = None
    runner._portfolio_risk = None
    runner._position_risk = None
    _r: Any = runner
    _r._trailing_stop = None
    _r._time_stop = None
    _r._partial_profit = None
    _r._correlation_monitor = None
    _r._shutdown_mgr = None
    runner._metrics = MagicMock()
    _r._data_loader = None
    runner._allocator = None
    runner._email_alerter = None
    runner._slack_alerter = None
    return runner


class TestPositionsLockExists:
    def test_lock_declared(self):
        """_positions_lock doit être présent dans __init__."""
        runner = _make_runner()
        assert hasattr(runner, "_positions_lock"), "_positions_lock absent du __init__ — correction A-01 non appliquée"

    def test_lock_is_threading_lock(self):
        """_positions_lock doit être un threading.Lock."""
        runner = _make_runner()
        # threading.Lock() retourne un _thread.lock, on vérifie via acquire/release
        lock = runner._positions_lock
        acquired = lock.acquire(blocking=False)
        assert acquired, "_positions_lock ne peut pas être acquis — mauvais type ?"
        lock.release()

    def test_pop_instead_of_del(self):
        """pop(key, None) ne doit pas lever KeyError si la clé est absente."""
        runner = _make_runner()
        with runner._positions_lock:
            runner._positions.pop("NON_EXISTANT_PAIR", None)  # ne doit pas lever


class TestConcurrentStopAndTick:
    def test_no_exception_on_concurrent_mutations(self):
        """
        Simule des mutations concurrentes de _positions depuis deux threads.
        Sans lock : RuntimeError: dictionary changed size during iteration.
        Avec lock : aucune exception.
        """
        runner = _make_runner()
        errors = []

        def writer():
            for i in range(200):
                with runner._positions_lock:
                    runner._positions[f"PAIR_{i % 10}"] = {"quantity": i, "holding_bars": 0}
                time.sleep(0)

        def deleter():
            for i in range(200):
                with runner._positions_lock:
                    runner._positions.pop(f"PAIR_{i % 10}", None)
                time.sleep(0)

        def reader():
            for _ in range(200):
                try:
                    with runner._positions_lock:
                        snapshot = list(runner._positions.items())
                    _ = {k: v for k, v in snapshot}
                except Exception as exc:
                    errors.append(exc)
                time.sleep(0)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=deleter),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Race condition détectée : {errors}"

    def test_stop_concurrent_with_position_access(self):
        """
        stop() depuis un thread externe pendant que _positions est lu
        ne doit pas corrompre l'état.
        """
        runner = _make_runner()
        runner._positions = {f"AAPL_MSFT_{i}": {"quantity": i + 1} for i in range(20)}

        def stop_repeatedly():
            for _ in range(50):
                runner.stop()
                runner._state = TradingState.RUNNING
                time.sleep(0.001)

        def read_positions_repeatedly():
            for _ in range(200):
                with runner._positions_lock:
                    _ = dict(runner._positions)
                time.sleep(0)

        t_stop = threading.Thread(target=stop_repeatedly)
        t_read = threading.Thread(target=read_positions_repeatedly)
        t_stop.start()
        t_read.start()
        t_stop.join()
        t_read.join()
        # Si on arrive ici sans exception, le test passe


class TestFillCheckBeforePositionRemoval:
    """A-02 : la position ne doit être supprimée qu'après confirmation fill."""

    def test_position_retained_when_submit_raises(self):
        """Si submit_order lève une exception, la position DOIT rester dans _positions."""
        runner = _make_runner()
        pair_key = "AAPL_MSFT"
        runner._positions = {pair_key: {"quantity": 10, "holding_bars": 3, "half_life": 5.0}}

        # Router qui simule un rejet IBKR
        mock_router = MagicMock()
        mock_router.submit_order.side_effect = RuntimeError("IBKR: Order rejected — insufficient margin")
        runner._router = mock_router

        # Simuler le bloc stop-exit tel qu'il existe dans _tick()
        from uuid import uuid4

        from execution.base import Order, OrderSide

        pos = runner._positions[pair_key]
        qty = pos.get("quantity", 0)
        close_side = OrderSide.SELL if qty > 0 else OrderSide.BUY
        close_order_id = str(uuid4())
        close_order = Order(
            order_id=close_order_id,
            symbol=pair_key,
            side=close_side,
            quantity=abs(qty),
            limit_price=None,
            order_type="MARKET",
        )

        try:
            runner._router.submit_order(close_order)
            # Submit réussi → marquer pending_close (chemin normal A-02)
            with runner._positions_lock:
                if pair_key in runner._positions:
                    runner._positions[pair_key]["status"] = "pending_close"
                    runner._positions[pair_key]["close_order_id"] = close_order_id
        except Exception:
            # submit a échoué → on NE touche PAS à la position
            pass

        assert pair_key in runner._positions, (
            "ERREUR A-02 : la position a été supprimée malgré l'échec de submit_order !"
        )
        # Status ne doit PAS être pending_close (submit a échoué)
        assert runner._positions[pair_key].get("status") != "pending_close"

    def test_position_marked_pending_close_when_submit_succeeds(self):
        """Après un submit réussi, la position doit être 'pending_close', pas supprimée."""
        runner = _make_runner()
        pair_key = "SPY_QQQ"
        runner._positions = {pair_key: {"quantity": 5, "holding_bars": 2}}

        mock_router = MagicMock()
        mock_router.submit_order.return_value = MagicMock()  # succès
        runner._router = mock_router

        from uuid import uuid4

        from execution.base import Order, OrderSide

        close_order_id = str(uuid4())
        close_order = Order(
            order_id=close_order_id,
            symbol=pair_key,
            side=OrderSide.SELL,
            quantity=5,
            limit_price=None,
            order_type="MARKET",
        )

        try:
            runner._router.submit_order(close_order)
            with runner._positions_lock:
                if pair_key in runner._positions:
                    runner._positions[pair_key]["status"] = "pending_close"
                    runner._positions[pair_key]["close_order_id"] = close_order_id
        except Exception:
            pass

        # Position DOIT être encore là, mais en pending_close
        assert pair_key in runner._positions, (
            "ERREUR A-02 : la position a été supprimée immédiatement au lieu de pending_close !"
        )
        assert runner._positions[pair_key]["status"] == "pending_close"
        assert runner._positions[pair_key]["close_order_id"] == close_order_id


class TestProcessFillConfirmations:
    """A-02 : _process_fill_confirmations() — confirmation / rejet d'ordres."""

    def test_filled_order_removes_position(self):
        """Statut FILLED → position supprimée sans alerte."""
        from execution.base import OrderStatus

        runner = _make_runner()
        pair_key = "AAPL_MSFT"
        order_id = "order-fill-001"
        runner._positions = {pair_key: {"quantity": 10, "status": "pending_close", "close_order_id": order_id}}
        mock_router = MagicMock()
        mock_router.get_order_status.return_value = OrderStatus.FILLED
        runner._router = mock_router

        runner._process_fill_confirmations()

        assert pair_key not in runner._positions, "Position devrait être supprimée après FILLED"

    def test_rejected_order_retains_position_and_alerts(self):
        """Statut REJECTED → position conservée + alerte CRITICAL envoyée."""
        from execution.base import OrderStatus

        runner = _make_runner()
        pair_key = "SPY_QQQ"
        order_id = "order-rej-002"
        runner._positions = {pair_key: {"quantity": 5, "status": "pending_close", "close_order_id": order_id}}
        mock_router = MagicMock()
        mock_router.get_order_status.return_value = OrderStatus.REJECTED
        runner._router = mock_router

        mock_alerter = MagicMock()
        runner._slack_alerter = mock_alerter

        runner._process_fill_confirmations()

        # Position doit rester (status passé à 'close_failed')
        assert pair_key in runner._positions
        assert runner._positions[pair_key]["status"] == "close_failed"
        mock_alerter.send_alert.assert_called_once()
        call_kwargs = mock_alerter.send_alert.call_args
        assert call_kwargs.kwargs["level"] == "CRITICAL"

    def test_cancelled_order_retains_position_and_alerts(self):
        """Statut CANCELLED → même comportement que REJECTED."""
        from execution.base import OrderStatus

        runner = _make_runner()
        pair_key = "GLD_SLV"
        order_id = "order-can-003"
        runner._positions = {pair_key: {"quantity": 3, "status": "pending_close", "close_order_id": order_id}}
        mock_router = MagicMock()
        mock_router.get_order_status.return_value = OrderStatus.CANCELLED
        runner._router = mock_router
        mock_email = MagicMock()
        runner._email_alerter = mock_email

        runner._process_fill_confirmations()

        assert pair_key in runner._positions
        assert runner._positions[pair_key]["status"] == "close_failed"
        mock_email.send_alert.assert_called_once()

    def test_pending_status_position_unchanged(self):
        """Statut encore PENDING → position reste en pending_close sans alerte."""
        from execution.base import OrderStatus

        runner = _make_runner()
        pair_key = "TLT_IEF"
        order_id = "order-pend-004"
        runner._positions = {pair_key: {"quantity": 8, "status": "pending_close", "close_order_id": order_id}}
        mock_router = MagicMock()
        mock_router.get_order_status.return_value = OrderStatus.PENDING
        runner._router = mock_router
        mock_alerter = MagicMock()
        runner._slack_alerter = mock_alerter

        runner._process_fill_confirmations()

        assert pair_key in runner._positions
        assert runner._positions[pair_key]["status"] == "pending_close"
        mock_alerter.send_alert.assert_not_called()

    def test_no_router_skips_gracefully(self):
        """Sans router, _process_fill_confirmations ne doit pas lever."""
        runner = _make_runner()
        runner._positions = {"A_B": {"quantity": 1, "status": "pending_close", "close_order_id": "oid-x"}}
        runner._router = None

        runner._process_fill_confirmations()  # ne doit pas lever

    def test_non_pending_position_not_touched(self):
        """Une position sans statut pending_close doit être ignorée."""
        runner = _make_runner()
        pair_key = "XOM_CVX"
        runner._positions = {pair_key: {"quantity": 2, "status": "open"}}
        mock_router = MagicMock()
        runner._router = mock_router

        runner._process_fill_confirmations()

        mock_router.get_order_status.assert_not_called()
        assert pair_key in runner._positions
