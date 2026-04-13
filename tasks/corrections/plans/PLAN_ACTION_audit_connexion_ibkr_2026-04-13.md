---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/corrections/plans/PLAN_ACTION_audit_connexion_ibkr_2026-04-13.md
derniere_revision: 2026-04-13
creation: 2026-04-13 à 18:35
---

# PLAN D'ACTION — Audit Connexion IBKR / IB Gateway

**Source** : `tasks/audits/resultats/audit_ibkr_connexion_edgecore.md`
**Référence audit** : 3 🔴 critiques · 6 🟠 moyens · 5 🟡 faibles

---

## SPRINT 0 — CORRECTIONS CRITIQUES (avant toute session live)

> Ces 3 corrections doivent être faites ensemble dans un seul commit avant la prochaine session de trading live.

---

### CX-09 ✦ Rate limiter manquant dans `get_historical_data()`

**Fichier** : `execution/ibkr_engine.py` — méthode `get_historical_data()` ~L530
**Risque** : Déconnexion forcée par IBKR en bulk loading (hard cap 50 req/s)
**Effort** : S — 1 ligne à ajouter

**Action** :
```python
# Avant self._ib.reqHistoricalData(...)
_ibkr_rate_limiter.acquire()
self._ib.reqHistoricalData(...)
```

**Test** : `tests/execution/` — vérifier qu'aucun nouveau test n'est rouge.

---

### CX-01 + CX-05 ✦ `IBGatewaySync.connect()` — socket réel vs flag booléen

**Fichier** : `execution/ibkr_sync_gateway.py` — méthode `connect()` ~L125
**Risque** : Après restart gateway 05:30 ou coupure réseau, le module croit être connecté et envoie des requêtes dans le vide → perte totale du data feed sans détection ni alerte
**Effort** : M

**Action** :
1. À l'entrée de `connect()`, remplacer le check `if not self.connected:` par un check double :
   - `self.connected AND self.client.isConnected()` → connexion réellement active, retourner directement
   - flag `True` mais socket mort → forcer une reconnexion (reset flag, cleanup socket)
2. À la fin du `connect()` positif, enregistrer un callback de déconnexion si l'API EClient l'expose (sinon, tolérer — la correction CX-01 suffit à détecter le problème au prochain appel)

**Changement en pseudocode** :
```python
def connect(self) -> bool:
    with self._lock:
        # Vérification RÉELLE du socket (pas juste le flag interne)
        if self.connected and self.client.isConnected():
            return True
        # Flag désynchronisé ou première connexion → reset propre
        if self.connected:
            try:
                self.client.disconnect()
            except Exception:
                pass
            self.connected = False
            self._msg_thread = None
        # Tentative de connexion (inchangée)
        try:
            self.client.connect(self.host, self.port, self.client_id)
            self._msg_thread = threading.Thread(target=self.client.run, daemon=True)
            self._msg_thread.start()
            time.sleep(0.5)
            self.connected = True
            logger.info(...)
        except Exception as e:
            logger.error(...)
            self.connected = False
        return self.connected
```

**Test** : Ajouter un test unitaire qui simule `client.isConnected()` retournant `False` alors que le flag est `True`, et vérifie que `connect()` force une reconnexion.

---

### CX-03 ✦ Retry dans `IBGatewaySync.connect()`

**Fichier** : `execution/ibkr_sync_gateway.py` — méthode `connect()` ~L125
**Risque** : Un seul échec réseau de 100ms fait échouer tout le chargement de l'univers
**Effort** : M (à faire dans le même éditeur que CX-01)

**Action** : Envelopper le bloc connect dans une boucle de retry (3 tentatives, délais 2/5/10s avec jitter) en utilisant le `RetryPolicy` existant dans `common/retry.py` :

```python
from common.ibkr_rate_limiter import GLOBAL_IBKR_RATE_LIMITER as _ibkr_rate_limiter
from common.retry import RetryPolicy

_SYNC_GW_RETRY = RetryPolicy(
    max_attempts=3,
    initial_delay_seconds=2.0,
    max_delay_seconds=10.0,
    retryable_exceptions=(ConnectionError, OSError, TimeoutError),
)
```

Appliquer `@retry_with_backoff(policy=_SYNC_GW_RETRY)` sur la méthode interne de connexion, ou boucler manuellement dans `connect()`.

---

## SPRINT 1 — CORRECTIONS IMPORTANTES (dans la semaine)

---

### CX-17 ✦ Appeler `reconcile_pending_confirm()` au startup

**Fichier** : `live_trading/runner.py` — méthode `_run_startup_reconciliation()` ~L420
**Risque** : Ordres avec permId=0 (crash pendant soumission) jamais réconciliés après redémarrage → positions fantômes
**Effort** : S — 3 lignes à ajouter dans la méthode startup existante

**Action** :
```python
# Ajouter après l'initialisation de self._router dans _initialize()
# (et après que _ensure_connected() ait été appelé)
if self.config.mode == "live" and self._router and self._router._ibkr_engine:
    resolved = self._router._ibkr_engine.reconcile_pending_confirm()
    if resolved:
        logger.info("startup_pending_confirm_resolved", count=resolved)
```

---

### CX-08 ✦ Protéger le cycling de client IDs dans `data/loader.py`

**Fichier** : `data/loader.py` — `_next_client_id()` + `_IBKR_CLIENT_ID_POOL` ~L152
**Risque** : Deux threads simultanés avec le même clientId → Error 326 IBKR → déconnexion des deux
**Effort** : M

**Action** :
1. Remplacer le round-robin aveugle par un set d'IDs actifs thread-safe (pattern identique à `IBKRExecutionEngine._active_client_ids`)
2. `_next_client_id()` attend si tous les IDs du pool sont actifs (max 8 connexions simultanées)
3. Les appelants passent par un context manager `_ibkr_client_id_ctx()` qui release l'ID à la fin

---

### CX-16 ✦ Unifier les ports par défaut

**Fichier** : `execution/ibkr_engine.py` ~L60 et `execution/ibkr_sync_gateway.py` ~L112
**Risque** : `IBKRExecutionEngine` default 7497 (TWS) ≠ `IBGatewaySync` default 4002 (Gateway). En Docker, `IBKR_PORT=4002` est set mais `IBKRExecutionEngine` peut ignorer l'env si `.env` n'est pas chargé
**Effort** : S — changer 1 valeur de default

**Action** :
- `IBKRExecutionEngine.__init__` : `port = port or int(os.getenv("IBKR_PORT", "4002"))` (au lieu de `"7497"`)
- Documenter dans `.env.example` : 4002 = IB Gateway paper (port prod)

---

### CX-02 ✦ Remplacer `logging` par `structlog` dans `IBGatewaySync`

**Fichier** : `execution/ibkr_sync_gateway.py` ~L10-22
**Risque** : Logs non-structurés, invisibles dans le pipeline JSON/Prometheus
**Effort** : S

**Action** :
```python
# Remplacer :
import logging
logger = logging.getLogger(__name__)

# Par :
from structlog import get_logger
logger = get_logger(__name__)

# Adapter les appels : logger.info("msg", key=val) à la place de logger.info("fmt %s", val)
```

---

### CX-11 ✦ `_order_map` après reconnexion

**Fichier** : `execution/ibkr_engine.py` — `_on_disconnect()` ~L222
**Risque** : Les objets `Trade` ib_insync stockés dans `_order_map` sont liés à l'ancienne session IB. Après reconnexion, `get_order_status()` retourne des valeurs stale
**Effort** : M

**Action** :
```python
def _on_disconnect(self) -> None:
    logger.warning("ibkr_disconnected_event", host=self.host, port=self.port)
    self._ib = None  # force reconnect on next call
    # Invalider l'order_map — les Trade objects de la session précédente ne sont plus valides.
    # Les ordres toujours ouverts seront récupérés via reconcile_pending_confirm() au restart.
    stale_ids = [oid for oid, trade in self._order_map.items()
                 if not (trade and hasattr(trade, 'orderStatus')
                         and getattr(trade.orderStatus, 'status', '') in ('Filled', 'Cancelled'))]
    for oid in stale_ids:
        self._pending_confirm_orders.add(oid)
    self._order_map.clear()
    logger.warning("ibkr_order_map_invalidated_on_disconnect",
                   stale_orders=len(stale_ids))
```

---

## SPRINT 2 — AMÉLIORATIONS (dans le mois)

---

### CX-07 ✦ Pool de connexions IBGatewaySync

**Fichier** : `data/loader.py`, `data/intraday_loader.py`, `data/corporate_actions.py`
**Problème** : Chaque appel à `load_price_data()` crée/détruit une connexion. ~390 connect/disconnect par session intraday.
**Action** : Créer un `IBGatewaySyncPool(size=4)` avec context manager `with pool.acquire() as engine:`. Injecter la pool dans les loaders. Singleton global, réinitialisé au startup.

---

### CX-13 ✦ Polling asynchrone des fills

**Fichier** : `execution_engine/router.py` — `_live_fill()` ~L380
**Problème** : `time.sleep(poll_interval)` dans la boucle de polling bloque le thread du tick loop pendant tout le timeout.
**Action** : Déplacer le polling de fill dans un thread dédié (ou callback ib_insync `tradeEvent`) et retourner immédiatement avec un `Future`. Le tick suivant check le résultat via `_process_fill_confirmations()` déjà en place.

---

### CX-04 ✦ Handshake `reqCurrentTime()` à la place de `sleep(0.5)`

**Fichier** : `execution/ibkr_sync_gateway.py` ~L137
**Action** : Après `self.client.connect()`, appeler `self.client.reqCurrentTime()` et attendre que `IBWrapper.current_time` soit non-None (timeout 5s). C'est un vrai signal que le reader thread est opérationnel.

---

## VALIDATION POST-CORRECTIONS

```powershell
# 1. Tests unitaires
venv\Scripts\python.exe -m pytest tests/ -q

# 2. Test strict DeprecationWarning
venv\Scripts\python.exe -m pytest tests/ -W error::DeprecationWarning -q

# 3. Risk tier coherence
venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"

# 4. Test de connexion IBGatewaySync (manuel, IB Gateway actif requis)
venv\Scripts\python.exe -c "
from execution.ibkr_sync_gateway import IBGatewaySync
gw = IBGatewaySync()
print('connect:', gw.connect())
print('isConnected:', gw.client.isConnected())
gw.disconnect()
print('OK')
"

# 5. Vérifier que le rate limiter est appelé dans get_historical_data
venv\Scripts\python.exe -c "
import ast, pathlib
src = pathlib.Path('execution/ibkr_engine.py').read_text()
assert '_ibkr_rate_limiter.acquire' in src.split('def get_historical_data')[1].split('def ')[0], 'RATE LIMITER MANQUANT'
print('OK — rate limiter présent dans get_historical_data')
"
```

---

## ORDRE D'IMPLÉMENTATION RECOMMANDÉ

```
Sprint 0 (1 session, ~2h) :
  1. CX-09  → 1 ligne dans ibkr_engine.py
  2. CX-01  → refactor connect() dans ibkr_sync_gateway.py
  3. CX-03  → retry dans connect() (même fichier, même session)
  → commit "fix(ibkr): rate limit + socket detection + retry in IBGatewaySync"
  → pytest full suite

Sprint 1 (1 semaine, ~4h) :
  4. CX-17  → startup reconciliation
  5. CX-02  → structlog dans ibkr_sync_gateway.py
  6. CX-16  → default port 4002
  7. CX-08  → client ID protection
  8. CX-11  → _order_map invalidation
  → commit "fix(ibkr): startup reconciliation + port + clientId + order_map"
  → pytest full suite

Sprint 2 (1 mois, ~8h) :
  9. CX-07  → pool de connexions
  10. CX-13 → polling asynchrone
  11. CX-04 → handshake reqCurrentTime
  → commit "feat(ibkr): connection pool + async fill polling + handshake"
```
