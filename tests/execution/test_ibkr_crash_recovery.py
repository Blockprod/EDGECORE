"""C-06 — Tests: crash réseau mid-order + idempotence de persistance.

Scénarios couverts :
  1. L'order_id est persisté avec perm_id=0 *avant* le sleep/crash
     → même si le processus meurt après `_save_order_map()`, l'idempotence
     est garantie au redémarrage.
  2. Au redémarrage, tout order_id déjà dans `_persisted_order_ids` est
     rejeté par la garde d'idempotence — pas de double-soumission chez IBKR.
  3. `_save_order_map()` écrit via un fichier .tmp puis replace atomiquement
     → aucune corruption possible en cas de crash pendant l'écriture.
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from execution.base import Order, OrderSide
from execution.ibkr_engine import IBKRExecutionEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_order(order_id: str = "ORD-CR-001") -> Order:
    return Order(
        order_id=order_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        limit_price=None,
    )


def _build_engine(client_id: int = 77) -> IBKRExecutionEngine:
    """Build an un-connected engine instance bypassing the constructor."""
    engine = IBKRExecutionEngine.__new__(IBKRExecutionEngine)
    engine.host = "127.0.0.1"
    engine.port = 7497
    engine.client_id = client_id
    engine.readonly = False
    engine.timeout = 5
    engine._ib = None
    engine._order_map = {}
    engine._persisted_order_ids = {}
    engine._consecutive_failures = 0
    engine._max_consecutive_failures = 5
    engine._last_failure_time = 0.0
    engine._cb_reset_timeout = 300
    # Prevent real disk I/O in most tests
    engine._load_order_map = MagicMock()
    engine._save_order_map = MagicMock()
    return engine


# ---------------------------------------------------------------------------
# 1. Persistance placeholder avant crash
# ---------------------------------------------------------------------------


class TestOrderIdPersistedBeforeCrash:
    """order_id est enregistré avec perm_id=0 *avant* le sleep 500 ms.

    Même si le processus crashe pendant ce sleep, l'idempotence est active.
    """

    def test_order_id_in_persisted_map_after_placement(self):
        """Après submit_order réussi, order_id est dans _persisted_order_ids."""
        engine = _build_engine()

        mock_trade = MagicMock()
        mock_trade.order.permId = 98765
        engine._ensure_connected = MagicMock(return_value=None)
        engine._place_order_with_retry = MagicMock(return_value=mock_trade)

        order = _make_order("ORD-PERSIST-001")
        with patch("time.sleep"):  # évite le sleep 500 ms en test
            engine.submit_order(order)

        assert order.order_id in engine._persisted_order_ids, (
            "order_id doit être dans _persisted_order_ids après submit_order réussi"
        )

    def test_save_order_map_called_with_placeholder_before_perm_id(self):
        """_save_order_map() est d'abord appelé avec perm_id=0 (placeholder).

        Cela garantit la persistance même si le processus meurt avant que
        IBKR renvoie le permId réel.
        """
        engine = _build_engine()

        save_calls: list[dict[str, int]] = []

        def _record_save():
            save_calls.append(dict(engine._persisted_order_ids))

        engine._save_order_map = MagicMock(side_effect=_record_save)

        mock_trade = MagicMock()
        mock_trade.order.permId = 42
        engine._ensure_connected = MagicMock(return_value=None)
        engine._place_order_with_retry = MagicMock(return_value=mock_trade)

        order = _make_order("ORD-PERSIST-002")
        with patch("time.sleep"):
            engine.submit_order(order)

        # La *première* sauvegarde doit contenir perm_id=0 (placeholder crash-safe)
        assert len(save_calls) >= 1, "_save_order_map doit être appelé au moins une fois"
        first_save = save_calls[0]
        assert order.order_id in first_save, "order_id doit être présent dès le premier save"
        assert first_save[order.order_id] == 0, (
            "La première persistance doit être avec perm_id=0 (placeholder) "
            "pour garantir l'idempotence en cas de crash immédiat"
        )


# ---------------------------------------------------------------------------
# 2. Idempotence après redémarrage
# ---------------------------------------------------------------------------


class TestIdempotencyAfterRestart:
    """Simule un redémarrage : _persisted_order_ids pré-chargé depuis disque."""

    def test_duplicate_order_rejected_without_ibkr_call(self):
        """Un order_id déjà persisté est rejeté immédiatement, sans appel IBKR."""
        engine = _build_engine()
        preloaded_order_id = "ORD-RESTART-001"
        engine._persisted_order_ids[preloaded_order_id] = 99999  # chargé depuis disque

        engine._ensure_connected = MagicMock()
        engine._place_order_with_retry = MagicMock()

        order = _make_order(preloaded_order_id)
        result = engine.submit_order(order)

        # L'idempotence bloque l'ordre
        assert result == preloaded_order_id, "submit_order doit retourner l'order_id sans erreur"
        engine._place_order_with_retry.assert_not_called()
        engine._ensure_connected.assert_not_called()

    def test_save_order_map_not_called_for_duplicate(self):
        """_save_order_map() ne doit pas être appelé pour un dupliqué."""
        engine = _build_engine()
        engine._persisted_order_ids["ORD-RESTART-002"] = 11111

        order = _make_order("ORD-RESTART-002")
        engine.submit_order(order)

        from unittest.mock import MagicMock as _MM

        save_mock = engine._save_order_map
        assert isinstance(save_mock, _MM), "_save_order_map should be a MagicMock"
        assert save_mock.call_count == 0

    def test_new_order_after_restart_is_accepted(self):
        """Un order_id ABSENT de _persisted_order_ids est traité normalement."""
        engine = _build_engine()
        # Map pré-chargé avec un ID différent
        engine._persisted_order_ids["ORD-OLD-001"] = 55555

        mock_trade = MagicMock()
        mock_trade.order.permId = 12345
        engine._ensure_connected = MagicMock(return_value=None)
        engine._place_order_with_retry = MagicMock(return_value=mock_trade)

        new_order = _make_order("ORD-NEW-001")
        with patch("time.sleep"):
            engine.submit_order(new_order)

        engine._place_order_with_retry.assert_called_once()
        assert "ORD-NEW-001" in engine._persisted_order_ids


# ---------------------------------------------------------------------------
# 3. Écriture atomique via .tmp → replace
# ---------------------------------------------------------------------------


class TestAtomicOrderMapWrite:
    """_save_order_map() écrit via .tmp puis remplace — protège contre
    la corruption en cas de crash pendant l'écriture."""

    def test_tmp_file_replaced_by_final_file(self, tmp_path: Path):
        """Le fichier final existe et le .tmp temporaire est supprimé."""
        engine = _build_engine()
        map_file = tmp_path / "ibkr_order_map.json"
        # Restaurer la vraie méthode _save_order_map (non mockée)
        engine._save_order_map = IBKRExecutionEngine._save_order_map.__get__(engine, IBKRExecutionEngine)
        _eng: Any = engine
        _eng._ORDER_MAP_FILE = str(map_file)
        engine._persisted_order_ids = {"ORD-ATOM-001": 12345, "ORD-ATOM-002": 67890}

        engine._save_order_map()

        assert map_file.exists(), "Le fichier final doit exister après _save_order_map()"
        tmp_file = map_file.with_suffix(".tmp")
        assert not tmp_file.exists(), "Le fichier .tmp doit être supprimé après le replace"

    def test_saved_content_is_valid_json(self, tmp_path: Path):
        """Le contenu du fichier est du JSON valide représentant _persisted_order_ids."""
        engine = _build_engine()
        map_file = tmp_path / "ibkr_order_map.json"
        engine._save_order_map = IBKRExecutionEngine._save_order_map.__get__(engine, IBKRExecutionEngine)
        _eng: Any = engine
        _eng._ORDER_MAP_FILE = str(map_file)
        engine._persisted_order_ids = {"ORD-JSON-001": 111, "ORD-JSON-002": 222}

        engine._save_order_map()

        content = json.loads(map_file.read_text())
        assert content == {"ORD-JSON-001": 111, "ORD-JSON-002": 222}

    def test_load_order_map_restores_persisted_ids(self, tmp_path: Path):
        """_load_order_map() restaure correctement les IDs depuis le fichier."""
        map_file = tmp_path / "ibkr_order_map.json"
        map_file.write_text(json.dumps({"ORD-LOAD-001": 555, "ORD-LOAD-002": 666}))

        engine = _build_engine()
        engine._load_order_map = IBKRExecutionEngine._load_order_map.__get__(engine, IBKRExecutionEngine)
        _eng: Any = engine
        _eng._ORDER_MAP_FILE = str(map_file)
        engine._persisted_order_ids = {}

        engine._load_order_map()

        assert engine._persisted_order_ids == {"ORD-LOAD-001": 555, "ORD-LOAD-002": 666}


