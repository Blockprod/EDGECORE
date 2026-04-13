---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/resultats/audit_ibkr_connexion_edgecore.md
derniere_revision: 2026-04-13
creation: 2026-04-13 à 18:31
---

# AUDIT CONNEXION IBKR / IB GATEWAY — EDGECORE V1

**Scope** : Tous les fichiers impliqués dans la connexion, reconnexion, rate limiting et gestion du cycle de vie broker.

**Fichiers audités** :
- `execution/ibkr_engine.py` (IBKRExecutionEngine — ib_insync async)
- `execution/ibkr_sync_gateway.py` (IBGatewaySync — ibapi sync)
- `execution/gw_manager.py` (IB Gateway health & auto-launch)
- `execution/rate_limiter.py` (TokenBucketRateLimiter)
- `execution/reconciler.py` (BrokerReconciler)
- `execution/shutdown_manager.py` (ShutdownManager)
- `execution/borrow_check.py` (BorrowChecker)
- `execution_engine/router.py` (ExecutionRouter)
- `live_trading/runner.py` (LiveTradingRunner)
- `data/loader.py` (load_price_data, DataLoader)
- `data/intraday_loader.py` (IntradayLoader)
- `data/corporate_actions.py` (CorporateActionsProvider)
- `data/event_filter.py` (EventFilter)
- `common/ibkr_rate_limiter.py` (Singleton global)
- `common/retry.py` (RetryPolicy)
- `common/circuit_breaker.py` (CircuitBreaker)
- `config/settings.py` (ExecutionConfig)
- `docker-compose.yml`, `Dockerfile`
- `backtests/runner.py` (BacktestRunner — HMDS check)

---

## SYNTHÈSE

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|
| CX-01 | IBGatewaySync | **Pas de reconnexion automatique** — `connected` est un flag booléen interne, jamais corrélé au socket réel. Si le socket TCP tombe, `self.connected` reste `True` et toutes les requêtes échouent silencieusement | `execution/ibkr_sync_gateway.py:116-160` | 🔴 CRITIQUE | Perte totale de data feed en live sans détection | M |
| CX-02 | IBGatewaySync | **`logging.getLogger` au lieu de `structlog`** — seul fichier IBKR utilisant `import logging` au lieu de `structlog.get_logger`. Viole la convention codebase, logs invisibles dans le pipeline structlog/JSON | `execution/ibkr_sync_gateway.py:10,22` | 🟡 FAIBLE | Logs non-structurés, filtrage impossible | S |
| CX-03 | IBGatewaySync | **Pas de circuit breaker ni retry** — chaque méthode (`get_historical_data`, `get_shortable_shares`, etc.) tente un seul `connect()` sans retry. Aucune protection contre les pannes transitoires du gateway | `execution/ibkr_sync_gateway.py:125-298` | 🔴 CRITIQUE | Échec immédiat au moindre hiccup réseau | M |
| CX-04 | IBGatewaySync | **`time.sleep(0.5)` hardcodé au connect** — après `self.client.connect()`, un sleep fixe de 0.5s est censé laisser le reader thread démarrer. Insuffisant sous charge ou sur machine lente, pas de vérification réelle de la connexion | `execution/ibkr_sync_gateway.py:137` | 🟠 MOYEN | Requêtes envoyées avant que le socket soit prêt → erreurs 504 | S |
| CX-05 | IBGatewaySync | **Pas de disconnect handler** — contrairement à `IBKRExecutionEngine` qui écoute `disconnectedEvent`, `IBGatewaySync` n'a aucun mécanisme de détection de déconnexion. Le flag `connected` devient stale | `execution/ibkr_sync_gateway.py:110-160` | 🔴 CRITIQUE | Zombie connection — croit être connecté alors que le gateway a coupé | M |
| CX-06 | IBGatewaySync | **Thread message non-daemon possible leak** — `self._msg_thread` est créé comme daemon thread, mais aucun `join()` + timeout dans `disconnect()`. Le thread peut rester bloqué dans `self.client.run()` après disconnect | `execution/ibkr_sync_gateway.py:135,153` | 🟡 FAIBLE | Resource leak en cas de disconnect forcé | S |
| CX-07 | data/loader.py | **`load_price_data()` crée une connexion IBGatewaySync par appel** — pas de pooling. Si appellé fréquemment (≤1min ticks), chaque tick crée/détruit une connexion TCP au gateway. Risque d'exhaustion de clientId et rate-limit | `data/loader.py:63-65` | 🟠 MOYEN | Connexions éphémères stressent le gateway, surtout en intraday | M |
| CX-08 | data/loader.py | **Client ID cycling sans vérification de conflit** — le pool `2001-2008` tourne en round-robin mais rien ne vérifie qu'un ID n'est pas déjà actif (contrairement à `IBKRExecutionEngine` qui lève `RuntimeError`). En threading, deux loaders simultanés peuvent utiliser le même clientId | `data/loader.py:152-160` | 🟠 MOYEN | Error 326 "clientId already in use" → déconnexion des deux | M |
| CX-09 | IBKRExecutionEngine | **`get_historical_data()` n'appelle pas `_ibkr_rate_limiter.acquire()`** — la méthode appelle directement `self._ib.reqHistoricalData()` sans passer par le rate limiter global. Seule `_place_order_with_retry()` passe par le limiter | `execution/ibkr_engine.py:530-536` | 🔴 CRITIQUE | Bypass du rate limit → déconnexion auto IBKR à 50 req/s | S |
| CX-10 | data/loader (bulk) | **`IBKRExecutionEngine` utilisé pour data batch** — `_worker()` instancie `IBKRExecutionEngine` (ib_insync async) avec client_id 1000+idx, mais la classe est conçue pour le trading, pas le data loading. Pas de `_ibkr_rate_limiter.acquire()` dans la boucle worker | `data/loader.py:480-510` | 🟠 MOYEN | Rate limit non respecté en bulk loading → déconnexion | S |
| CX-11 | IBKRExecutionEngine | **`_on_disconnect` ne préserve pas `_order_map`** — quand IBKR déconnecte, `_ib` est mis à `None` mais `_order_map` (references aux `Trade` objects ib_insync) devient invalide (les objets Trade sont liés à l'ancienne session IB). Après reconnexion, `get_order_status()` retourne des résultats stale | `execution/ibkr_engine.py:222-225` | 🟠 MOYEN | Status d'ordres incorrects après reconnexion mid-session | M |
| CX-12 | gw_manager | **`ensure_gateway_ready()` utilise `asyncio.get_event_loop().run_until_complete()`** dans `_initialize()` qui est sync — si un event loop tourne déjà (Jupyter, tests), ça lève `RuntimeError: This event loop is already running` | `live_trading/runner.py:293-295` | 🟡 FAIBLE | Crash au démarrage en contexte async existant | S |
| CX-13 | ExecutionRouter | **`_live_fill()` time.sleep() dans le poll loop** — le polling d'ordres utilise `time.sleep(poll_interval)` qui bloque le thread principal. En combinaison avec `bar_interval_seconds=60`, un ordre qui timeout bloque 60s+ de plus | `execution_engine/router.py:380-397` | 🟠 MOYEN | Tick entier bloqué pendant l'attente d'un fill | M |
| CX-14 | IBGatewaySync | **`get_shortable_shares()` break prématuré après 3.0s** — le timeout standard est `self.timeout` (30s), mais un `break` hardcodé à 3.0s coupe l'attente. Pour les symboles moins liquides, IBKR peut mettre >3s à répondre | `execution/ibkr_sync_gateway.py:291-292` | 🟡 FAIBLE | Faux négatifs de shortable shares → shorts bloqués inutilement | S |
| CX-15 | IBGatewaySync | **`error()` callback pas thread-safe pour `error_msg`** — `self.error_msg` est un tuple réaffecté atomiquement MAIS lu sans lock dans `get_shortable_shares()` et `get_earnings_calendar()`. Sur CPython c'est safe (GIL), mais c'est un data race logique | `execution/ibkr_sync_gateway.py:84-92,286-289` | 🟡 FAIBLE | Race condition théorique (non critique sous CPython/GIL) | S |
| CX-16 | multiport | **Incohérence port par défaut entre modules** — `IBKRExecutionEngine` default 7497 (TWS), `IBGatewaySync` default 4002 (Gateway), `gw_manager` lit `IBKR_PORT` (env). Si `.env` n'est pas chargé, le même process utilise des ports différents pour trading vs data | `execution/ibkr_engine.py:60` vs `execution/ibkr_sync_gateway.py:112` | 🟠 MOYEN | Connexion au mauvais endpoint — trading sur TWS, data sur Gateway | S |
| CX-17 | LiveTradingRunner | **Pas de pending_confirm reconciliation au startup** — `IBKRExecutionEngine.reconcile_pending_confirm()` existe mais n'est jamais appelé dans `_run_startup_reconciliation()` ou `_initialize()` | `live_trading/runner.py:420-460` | 🟠 MOYEN | Ordres zombie (permId=0) jamais résolus après crash/restart | S |
| CX-18 | IBKRExecutionEngine | **`_active_client_ids` est class-level mutable dict** — partagé entre instances ET potentiellement entre forks/workers. En multiprocessing, le lock est local au process et ne protège rien | `execution/ibkr_engine.py:53-54` | 🟡 FAIBLE | Faux sentiment de sécurité en multi-process (Docker workers) | S |

---

## DÉTAILS PAR SÉVÉRITÉ

### 🔴 CRITIQUES (3)

#### CX-01 — IBGatewaySync : Aucune détection de déconnexion

**Problème** : `IBGatewaySync.connected` est un simple booléen positionné lors du `connect()` initial. Il n'est JAMAIS invalidé quand le socket TCP sous-jacent (`EClient`) est coupé par le gateway (restart quotidien 05:30, perte réseau, timeout idle).

Toutes les méthodes (`get_historical_data`, `get_shortable_shares`, etc.) commencent par `if not self.connect(): return None` — mais `connect()` vérifie uniquement `self.connected` (toujours `True` si le connect initial a réussi).

**Conséquence** : Après un restart gateway ou une coupure réseau, `IBGatewaySync` croit être connecté, envoie des requêtes dans le vide, et retourne des résultats vides/None sans relever l'erreur. Le data loader passe en fallback cache sans que personne ne soit alerté.

**Solution** :
```python
def connect(self) -> bool:
    with self._lock:
        # Vérifie l'état RÉEL du socket, pas juste le flag
        if self.connected and self.client.isConnected():
            return True
        # Force reconnection si le flag est désynchronisé
        self.connected = False
        try:
            self.client.disconnect()  # clean up stale socket
        except Exception:
            pass
        try:
            self.client.connect(self.host, self.port, self.client_id)
            self._msg_thread = threading.Thread(target=self.client.run, daemon=True)
            self._msg_thread.start()
            time.sleep(0.5)
            self.connected = True
        except Exception as e:
            logger.error(...)
            self.connected = False
        return self.connected
```

---

#### CX-03 — IBGatewaySync : Pas de retry ni circuit breaker

**Problème** : Contrairement à `IBKRExecutionEngine` qui implémente un circuit breaker complet (5 failures → open, exponential backoff, dead-gateway detection), `IBGatewaySync` n'a **aucun** mécanisme de retry. Un seul échec de connexion → retour `None` → pas de data.

**Conséquence** : Le data loader (`load_price_data`) dépend de `IBGatewaySync`. Un blip réseau de 100ms fait échouer le chargement entier de l'univers de symboles.

**Solution** : Wrapper le `connect()` avec un retry simple (3 essais, backoff) à minima. Optionnellement intégrer le `CircuitBreaker` de `common/circuit_breaker.py` qui existe déjà.

---

#### CX-09 — `IBKRExecutionEngine.get_historical_data()` contourne le rate limiter

**Problème** : La méthode `get_historical_data()` (lignes 530-536) appelle directement `self._ib.reqHistoricalData()` sans `_ibkr_rate_limiter.acquire()`. Quand `data/loader.py:_worker()` l'appelle en boucle serrée pour 100+ symboles, le rate limit IBKR (50 req/s) est facilement dépassé → déconnexion automatique.

**Conséquence** : En bulk loading (backfill), IBKR déconnecte l'application pour violation du rate limit. Les workers perdent tous leur connexion simultanément.

**Fix immédiat** : Ajouter `_ibkr_rate_limiter.acquire()` avant `self._ib.reqHistoricalData()`.

---

### 🟠 MOYENS (6)

#### CX-04 — `time.sleep(0.5)` hardcodé au connect

Le sleep de 0.5s entre `EClient.connect()` et la première requête est une heuristique fragile. Sous charge ou sur machine lente, le reader thread peut ne pas être prêt. Solution : attendre un signal de l'EWrapper (par ex. `currentTime()` response) plutôt qu'un sleep fixe.

#### CX-07 — Connexion éphémère dans `load_price_data()`

Chaque appel à `load_price_data()` crée/détruit une connexion IBGatewaySync. En trading intraday (1-min ticks), ça représente ~390 connect/disconnect par session. Le gateway a un coût de handshake non-négligeable. Solution : injecter un engine partagé ou utiliser un pool de connexions.

#### CX-08 — Client ID cycling sans protection anti-conflit

Le pool `2001-2008` tourne en round-robin via `_next_client_id()` mais si deux threads appellent simultanément et que la connexion précédente n'est pas encore fermée, le même clientId est réutilisé. IBKR retourne "Error 326: clientId already in use" et déconnecte les deux. Solution : tracker les IDs actifs comme le fait `IBKRExecutionEngine._active_client_ids`.

#### CX-11 — `_order_map` invalide après reconnexion

Les objets `Trade` ib_insync stockés dans `_order_map` sont liés à l'instance `IB()` qui les a créés. Quand `_on_disconnect()` met `_ib = None` et que `_ensure_connected()` crée une nouvelle instance `IB()`, les anciens objets Trade sont orphelins. `trade.isDone()` peut retourner des valeurs incorrectes.

#### CX-13 — Blocking poll dans `_live_fill()`

Le polling `while waited < max_wait: time.sleep(poll_interval)` bloque le thread principal pendant toute la durée du fill. Un ordre lent (ex: limit close to market) peut bloquer le tick loop pendant 60s.

#### CX-16 — Ports par défaut incohérents

`IBKRExecutionEngine` (trading) default → 7497 (TWS paper). `IBGatewaySync` (data) default → 4002 (Gateway paper). Si IBKR_PORT est configuré pour un seul endpoint, l'autre utilise son default. En Docker, `docker-compose.yml` set `IBKR_PORT=4002` mais `IBKRExecutionEngine` peut quand même essayer 7497 si `.env` n'est pas lu par le container.

#### CX-17 — `reconcile_pending_confirm()` jamais appelé

`IBKRExecutionEngine.reconcile_pending_confirm()` est implémenté (lignes 248-280) mais n'apparaît jamais dans `LiveTradingRunner._initialize()` ni `_run_startup_reconciliation()`. Les ordres avec permId=0 (crash pendant soumission) ne sont jamais réconciliés.

---

### 🟡 FAIBLES (5)

| ID | Description |
|----|-------------|
| CX-02 | `IBGatewaySync` utilise `logging.getLogger` au lieu de `structlog.get_logger` |
| CX-06 | Thread message daemon sans join() propre dans disconnect() |
| CX-12 | `asyncio.get_event_loop().run_until_complete()` en contexte sync |
| CX-14 | Shortable shares break prématuré à 3.0s |
| CX-15 | `error_msg` tuple lu sans lock (safe CPython/GIL mais anti-pattern) |
| CX-18 | `_active_client_ids` class-level inutile en multi-process |

---

## POINTS POSITIFS (à ne pas toucher)

| Composant | Implémentation |
|-----------|---------------|
| Circuit breaker IBKRExecutionEngine | Exponential backoff + dead-gateway detection + operator reset — exemplaire |
| Rate limiter global | TokenBucket 40 req/s + 8 burst — marge de sécurité correcte |
| Idempotency guard | `_persisted_order_ids` + crash recovery JSON — protection double-fill |
| PermId polling | Active poll 5s remplace sleep(0.5) — bonne latence |
| IB Gateway auto-launch | Détection process + auto-login pywinauto — robuste |
| Disconnect handler (ib_insync) | `disconnectedEvent` → `_ib = None` → force reconnect |
| Anti-short guard | Tick 236 vérifié avant chaque SELL en live |
| Client ID dedup (IBKRExecutionEngine) | RuntimeError si client_id déjà actif — bonne protection |
| HMDS check backtest | Probe SPY avant de charger l'univers — fail-fast correct |
| Error code filtering | 2104/2106/2158 = info, 162/200/354 = fatal — conforme IBKR docs |

---

## PLAN DE CORRECTION PRIORITAIRE

### Immédiat (avant mise en prod)

1. **CX-09** — Ajouter `_ibkr_rate_limiter.acquire()` dans `IBKRExecutionEngine.get_historical_data()` (1 ligne)
2. **CX-01 + CX-05** — Refactorer `IBGatewaySync.connect()` pour vérifier `EClient.isConnected()` au lieu du flag booléen
3. **CX-03** — Ajouter retry (3 attempts, backoff 2/5/10s) dans `IBGatewaySync.connect()`
4. **CX-17** — Appeler `reconcile_pending_confirm()` dans `LiveTradingRunner._run_startup_reconciliation()`

### Court terme (Sprint 1)

5. **CX-08** — Tracker les clientIds actifs dans `data/loader.py` comme `IBKRExecutionEngine._active_client_ids`
6. **CX-16** — Unifier le port par défaut (4002 pour tous, IB Gateway est le target prod)
7. **CX-02** — Remplacer `logging.getLogger` par `structlog.get_logger` dans `ibkr_sync_gateway.py`
8. **CX-11** — Invalider `_order_map` dans `_on_disconnect()` ou stocker les ordres sous forme sérialisable

### Moyen terme (Sprint 2)

9. **CX-07** — Pool de connexions IBGatewaySync partagé (ou injection d'engine)
10. **CX-13** — Polling asynchrone des fills (asyncio ou callback) au lieu de `time.sleep()`
11. **CX-04** — Remplacer `sleep(0.5)` par un handshake `reqCurrentTime()` avec timeout

---

**Total** : 🔴 3 · 🟠 6 · 🟡 5
