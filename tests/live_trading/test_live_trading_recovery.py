"""C-06 — Tests: crash + redémarrage avec position pending_close.

Scénarios couverts :
  1. Une position avec status="pending_close" n'est PAS ré-ouverte par le
     signal generator (qui retourne uniquement des EXIT signals pour les paires
     déjà en position).
  2. _process_fill_confirmations() est appelé dès le premier tick après un
     redémarrage simulé avec un _positions pré-rempli (pending_close).
  3. Quand le broker retourne PENDING (fill partiel ou ordre encore en cours),
     la position reste en pending_close sans alerte — le runner attend le
     prochain tick.
"""

import threading
from unittest.mock import MagicMock

from execution.base import OrderStatus
from live_trading.runner import LiveTradingRunner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runner() -> LiveTradingRunner:
    """Crée un runner minimal, sans connexion IBKR."""
    runner = LiveTradingRunner()
    # Injecter un lock visible (déjà créé dans __init__)
    runner._positions_lock = threading.RLock()
    runner._slack_alerter = MagicMock()
    runner._email_alerter = MagicMock()
    return runner


# ---------------------------------------------------------------------------
# 1. Pas de ré-ouverture d'une position pending_close
# ---------------------------------------------------------------------------


class TestNoPendingCloseReopen:
    """Après redémarrage simulé, les positions pending_close ne sont pas ré-ouvertes."""

    def test_signal_generates_exit_not_entry_for_pending_close_pair(self):
        """Le signal generator ne génère pas d'entrée pour une paire déjà en position.

        Assertion : le signal ne contient PAS side='long' ou side='short'
        (entrée) pour la paire déjà dans _positions (quelle que soit le statut).
        """
        from signal_engine.generator import SignalGenerator

        pair_key = "AAPL_MSFT"
        gen = SignalGenerator()

        # La paire est marquée pending_close dans active_positions
        active_positions = {pair_key: {"quantity": 100, "status": "pending_close"}}

        # Construire un DataFrame synthétique avec spread hors seuil d'entrée
        import numpy as np
        import pandas as pd

        idx = pd.date_range("2024-01-01", periods=300, freq="D")
        np.random.seed(42)
        price_a = np.cumsum(np.random.randn(300)) + 100
        price_b = price_a * 0.95 + np.random.randn(300) * 0.5  # co-intégrés
        data = pd.DataFrame({"AAPL": price_a, "MSFT": price_b}, index=idx)

        signals = gen.generate(
            market_data=data,
            active_pairs=[("AAPL", "MSFT", 0.01, 78.0)],  # (sym1, sym2, pval, half_life)
            active_positions=active_positions,
        )

        # Aucun signal d'entrée (long/short) pour la paire déjà en position
        entry_signals = [s for s in signals if s.pair_key == pair_key and s.side in ("long", "short")]
        assert len(entry_signals) == 0, (
            f"Le signal generator ne doit PAS générer d'entrée pour une paire "
            f"déjà dans _positions (pending_close), mais a retourné: {entry_signals}"
        )

    def test_fill_confirmation_called_for_pending_close_positions(self):
        """_process_fill_confirmations() est appelé pour les pending_close.

        Simule un redémarrage : _positions contient déjà une pending_close.
        Vérifie que la première action est de vérifier le statut de l'ordre
        chez IBKR, pas de soumettre un nouvel ordre.
        """
        runner = _make_runner()
        pair_key = "SPY_QQQ"
        order_id = "close-order-001"
        runner._positions = {pair_key: {"quantity": 200, "status": "pending_close", "close_order_id": order_id}}

        mock_router = MagicMock()
        # Broker indique que l'ordre est toujours en cours (fill partiel ou en attente)
        mock_router.get_order_status.return_value = OrderStatus.PENDING
        runner._router = mock_router

        runner._process_fill_confirmations()

        # Vérification : get_order_status appelé pour l'ordre en attente
        mock_router.get_order_status.assert_called_once_with(order_id)
        # Aucun nouvel ordre soumis
        mock_router.submit_order.assert_not_called()


# ---------------------------------------------------------------------------
# 2. Fill partiel modélisé comme PENDING
# ---------------------------------------------------------------------------


class TestPartialFillHandling:
    """Un fill partiel (ex : 600/1000 actions) renvoie PENDING chez IBKR.

    Le comportement attendu :
      - La position reste en pending_close (on attend la complétion)
      - Aucune alerte n'est envoyée (ce n'est pas un rejet)
      - submit_order n'est pas ré-appelé
    """

    def test_partial_fill_position_remains_pending_close(self):
        """PENDING = fill partiel en cours → position conservée, pas d'alerte."""
        runner = _make_runner()
        pair_key = "GLD_SLV"
        order_id = "close-partial-001"
        runner._positions = {pair_key: {"quantity": 1000, "status": "pending_close", "close_order_id": order_id}}

        mock_router = MagicMock()
        mock_router.get_order_status.return_value = OrderStatus.PENDING
        runner._router = mock_router

        runner._process_fill_confirmations()

        # Position toujours pending_close
        assert pair_key in runner._positions
        assert runner._positions[pair_key]["status"] == "pending_close"

    def test_partial_fill_no_alert_sent(self):
        """Un fill partiel (PENDING) ne doit PAS déclencher d'alerte CRITICAL."""
        runner = _make_runner()
        pair_key = "TLT_IEF"
        order_id = "close-partial-002"
        runner._positions = {pair_key: {"quantity": 500, "status": "pending_close", "close_order_id": order_id}}

        mock_router = MagicMock()
        mock_router.get_order_status.return_value = OrderStatus.PENDING
        runner._router = mock_router

        runner._process_fill_confirmations()

        # Aucune alerte (slack ou email) — alerters are MagicMock instances in tests
        from unittest.mock import MagicMock as _MM

        slack = runner._slack_alerter
        email = runner._email_alerter
        assert isinstance(slack, _MM)
        assert isinstance(email, _MM)
        slack.send_alert.assert_not_called()
        email.send_alert.assert_not_called()

    def test_full_fill_removes_position_after_partial_sequence(self):
        """Après qu'un fill partiel se termine (FILLED), la position est supprimée."""
        runner = _make_runner()
        pair_key = "XOM_CVX"
        order_id = "close-full-003"
        runner._positions = {pair_key: {"quantity": 300, "status": "pending_close", "close_order_id": order_id}}

        mock_router = MagicMock()
        mock_router.get_order_status.return_value = OrderStatus.FILLED
        runner._router = mock_router

        runner._process_fill_confirmations()

        # Position supprimée dès le FILLED
        assert pair_key not in runner._positions


# ---------------------------------------------------------------------------
# 3. Garantie de non double-soumission au redémarrage
# ---------------------------------------------------------------------------


class TestNoDoubleSubmissionOnRestart:
    """Un redémarrage ne doit pas soumettre deux fois le même close order."""

    def test_no_new_close_order_while_pending_close_active(self):
        """Si l'ordre de fermeture est encore PENDING, aucun nouvel ordre n'est émis."""
        runner = _make_runner()
        pair_key = "AMZN_GOOGL"
        order_id = "close-dedup-001"
        runner._positions = {pair_key: {"quantity": 50, "status": "pending_close", "close_order_id": order_id}}

        mock_router = MagicMock()
        mock_router.get_order_status.return_value = OrderStatus.PENDING
        runner._router = mock_router

        # Appeler _process_fill_confirmations plusieurs fois (multi-tick simulation)
        runner._process_fill_confirmations()
        runner._process_fill_confirmations()
        runner._process_fill_confirmations()

        # submit_order ne doit jamais être appelé
        mock_router.submit_order.assert_not_called()
        # Position toujours présente
        assert pair_key in runner._positions
