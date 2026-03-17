# PLAN D'ACTION CORRECTIF — EDGECORE V1
### Basé sur l'audit technique & sécurité du 2026-03-16

> **Statut global :** 18 anomalies identifiées — 2 P0 bloquantes, 6 P1 hautes, 7 P2 moyennes, 3 P3 faibles  
> **Règle d'or :** Aucun déploiement avec capitaux réels tant que P0 et P1 ne sont pas fermés.

---

## TABLE DES MATIÈRES

1. [Sprint P0 — BLOQUANT (avant tout run live)](#sprint-p0)
2. [Sprint P1 — HAUTE PRIORITÉ (avant capitaux réels)](#sprint-p1)
3. [Sprint P2 — MOYEN TERME (sprint suivant)](#sprint-p2)
4. [Sprint P4 — BACKLOG (optimisations futures)](#sprint-p3)
5. [Checklist de validation finale](#checklist-finale)

---

## SPRINT P0 — BLOQUANT {#sprint-p0}
> Déploiement avec capitaux réels interdit tant que ces items ne sont pas résolus et testés.

---

### [A-01] Race condition sur `_positions` dans `LiveTradingRunner`

- **Fichier :** `live_trading/runner.py`
- **Problème :** `self._positions` est muté (lecture + écriture + suppression) dans `_tick()` sans aucun `threading.Lock`. `stop()` peut être appelé depuis un thread externe (signal OS via `ShutdownManager`) pendant qu'un tick est en cours.
- **Risque :** `KeyError`, double-position sur la même paire, ou perte silencieuse de position.

#### Correction

**Étape 1 — Ajouter le lock dans `__init__` :**

Localiser dans `live_trading/runner.py` la déclaration de `self._positions` et ajouter immédiatement après :

```python
self._positions: Dict[str, Any] = {}
self._positions_lock = threading.Lock()   # ← AJOUTER
```

S'assurer que `import threading` est présent en tête de fichier.

**Étape 2 — Protéger toutes les lectures du dictionnaire dans `_tick()` :**

Chaque bloc qui lit ou modifie `self._positions` doit être encapsulé :

```python
# Lecture (snapshot copie au début du tick)
with self._positions_lock:
    current_positions = dict(self._positions)

# Pour les suppressions de position (exit exécuté)
with self._positions_lock:
    self._positions.pop(pair_key, None)   # pop évite le KeyError

# Pour les ajouts de position
with self._positions_lock:
    self._positions[pair_key] = position_data
```

**Étape 3 — Test à écrire :**

```python
# tests/live_trading/test_runner_concurrency.py
def test_positions_thread_safety():
    """Simule un stop() concurrent pendant un tick actif."""
    import threading
    runner = build_mock_runner()
    errors = []

    def tick_loop():
        for _ in range(200):
            try:
                runner._tick()
            except Exception as e:
                errors.append(e)

    def stop_loop():
        for _ in range(50):
            time.sleep(0.001)
            runner.stop()

    t1 = threading.Thread(target=tick_loop)
    t2 = threading.Thread(target=stop_loop)
    t1.start(); t2.start()
    t1.join(); t2.join()
    assert errors == [], f"Race condition détectée : {errors}"
```

- [x] Lock déclaré dans `__init__`
- [x] Toutes les mutations de `_positions` encapsulées dans `with self._positions_lock:`
- [x] Test de concurrence écrit et passant

---

### [A-02] Suppression de position sans vérification du fill IBKR

- **Fichier :** `live_trading/runner.py` (autour de la ligne 502)
- **Problème :** Lors d'un exit (stop-loss, time-stop, signal inverse), `del self._positions[pair_key]` est appelé **immédiatement après** la soumission de l'ordre de fermeture, sans attendre la confirmation d'exécution côté IBKR.
- **Risque :** Si l'ordre est rejeté (insuffisance de liquidité, margin call, symbole non tradable), la position disparaît localement mais reste ouverte chez le broker → perte financière non trackée.

#### Correction

**Approche recommandée — Callback asynchrone sur fill :**

```python
# live_trading/runner.py — dans la méthode qui gère les exits

order_id = self._router.submit_order(close_order)

# NE PAS supprimer ici.
# Marquer comme "pending_close" et attendre le callback fill.
with self._positions_lock:
    self._positions[pair_key]["status"] = "pending_close"
    self._positions[pair_key]["close_order_id"] = order_id
```

Puis dans le callback de fill (ou dans le prochain tick via `get_order_status`) :

```python
def _process_fill_confirmations(self):
    """Appelé dans chaque tick pour vérifier les ordres pending_close."""
    with self._positions_lock:
        pending = {k: v for k, v in self._positions.items()
                   if v.get("status") == "pending_close"}

    for pair_key, pos_info in pending.items():
        order_id = pos_info["close_order_id"]
        status = self._router.get_order_status(order_id)
        if status == OrderStatus.FILLED:
            with self._positions_lock:
                self._positions.pop(pair_key, None)
            logger.info("position_closed_confirmed", pair=pair_key, order_id=order_id)
        elif status in (OrderStatus.CANCELLED, OrderStatus.REJECTED):
            logger.error("close_order_rejected_position_retained",
                         pair=pair_key, order_id=order_id, status=status)
            # Alerte critique — ne pas supprimer la position
            self._alert_manager.send_critical(
                f"Close order {order_id} for {pair_key} was {status}. Position retained."
            )
```

**Appeler `_process_fill_confirmations()` en début de chaque `_tick()`.**

- [x] `del self._positions[pair_key]` remplacé par statut `pending_close`
- [x] `_process_fill_confirmations()` implémentée et appelée dans le tick
- [x] Alerte critique envoyée si l'ordre de fermeture est rejeté
- [x] Test : vérifier que la position est retenue après rejet d'ordre

> ✅ **Complet** : `_process_fill_confirmations()` appelée en début de chaque tick. Positions marquées `pending_close` après soumission, supprimées uniquement sur confirmation FILLED. Alerte CRITICAL envoyée (Email + Slack) sur REJECTED/CANCELLED avec marquage `close_failed` anti-spam.

---

## SPRINT P1 — HAUTE PRIORITÉ {#sprint-p1}
> À corriger avant le premier run avec capitaux réels, même en paper trading supervisé.

---

### [A-03] `IBWrapper` partagé entre threads sans protection

- **Fichier :** `execution/ibkr_engine.py` — classe `IBWrapper`
- **Problème :** Les attributs `historical_data`, `error_msg`, `shortable_shares`, etc. sont écrits par le thread `client.run()` (thread messagerie IBKR) et lus par le thread principal simultanément, sans aucun `Lock`.
- **Risque :** Données historiques tronquées envoyées aux signaux → trades sur données corrompues.

#### Correction

```python
class IBWrapper(EWrapper):
    def __init__(self):
        super().__init__()
        self._lock = threading.RLock()        # ← AJOUTER
        self.historical_data: List = []
        self.historical_data_done: bool = False
        self.error_msg: Optional[Tuple] = None
        self.shortable_shares: float = -1.0
        # ... autres attributs

    # Protéger chaque callback IBKR :
    def historicalData(self, reqId, bar):
        with self._lock:
            self.historical_data.append(bar)

    def historicalDataEnd(self, reqId, start, end):
        with self._lock:
            self.historical_data_done = True

    def error(self, reqId, errorCode, errorString, *args):
        with self._lock:
            self.error_msg = (reqId, errorCode, errorString)

    def tickGeneric(self, reqId, tickType, value):
        if tickType == 236:   # shortable shares
            with self._lock:
                self.shortable_shares = value
```

Dans `get_historical_data()`, lire les attributs sous lock :

```python
# Attente de fin de données
while True:
    with self.wrapper._lock:
        done = self.wrapper.historical_data_done
    if done:
        break
    time.sleep(0.05)

# Lecture atomique du résultat
with self.wrapper._lock:
    data = list(self.wrapper.historical_data)
```

- [x] `self._lock = threading.RLock()` ajouté dans `IBWrapper.__init__`
- [x] `historicalData`, `historicalDataEnd`, `error`, `tickGeneric` protégés par lock
- [x] Toutes les lectures dans le thread principal effectuées sous lock
- [x] Tests existants toujours passants

---

### [A-04] Exception silencieuse sur `get_positions()` pendant la réconciliation

- **Fichier :** `live_trading/runner.py` — `_run_startup_reconciliation()` (~ligne 274)
- **Problème :** Un `except Exception: pass` avale silencieusement l'échec de `get_positions()`. La réconciliation démarre alors avec `broker_positions={}` → divergences non détectées.

#### Correction

```python
# Remplacer le bloc try/except silencieux par :
try:
    broker_positions = self._router._engine.get_positions()
except Exception as exc:
    logger.error(
        "startup_reconciliation_failed",
        error=str(exc),
        action="aborting_startup"
    )
    # En mode live : interrompre le démarrage, ne pas trader avec un état inconnu
    raise RuntimeError(
        "Cannot start live trading: broker position fetch failed during reconciliation. "
        f"Reason: {exc}"
    ) from exc
```

> **Note :** En mode paper, un warning suffit. Conditionner le comportement sur `self._mode`.

- [x] `except Exception: pass` remplacé par log + RuntimeError en mode live
- [x] Test : démarrage avec `get_positions()` qui lève → RuntimeError propagée

---

### [A-05] Bare `except:` silencieux dans `half_life_estimator.py`

- **Fichier :** `models/half_life_estimator.py` — lignes 173 et 215
- **Problème :** Les deux blocs `except:` (sans type) avalent toutes les exceptions, y compris `MemoryError`, `KeyboardInterrupt`, et les erreurs numpy. Ils retournent `None` silencieusement.
- **Risque :** Signal incorrecte → trade exécuté avec `half_life=None` → comportement imprévisible en aval.

#### Correction

```python
# Ligne 173 — Remplacer :
except:
    return None

# Par :
except (np.linalg.LinAlgError, ValueError, RuntimeError) as exc:
    logger.warning("half_life_estimation_failed", method="ols", error=str(exc))
    return None

# Ligne 215 — Remplacer :
except:
    return None

# Par :
except (np.linalg.LinAlgError, ValueError, RuntimeError) as exc:
    logger.warning("half_life_estimation_failed", method="kalman", error=str(exc))
    return None
```

Vérifier que les appelants traitent `None` correctement (chercher `half_life=` dans tout le codebase et ajouter des gardes).

- [x] Ligne 173 : `except:` → `except (np.linalg.LinAlgError, ValueError, RuntimeError)`
- [x] Ligne 215 : idem
- [x] Tous les appelants gèrent le cas `half_life is None`
- [x] Test : passer des données dégénérées et vérifier le log Warning (pas de silence)

---

### [A-06] `_req_id_counter` non protégé dans `IBGatewaySync`

- **Fichier :** `execution/ibkr_engine.py` — `IBGatewaySync.get_historical_data()` (~ligne 157)
- **Problème :** L'incrément `self._req_id_counter += 1` n'est pas protégé par un lock. En cas d'usage concurrent de la même instance, deux requêtes obtiennent le même `req_id` → erreur IBKR 322 "Duplicate ticker ID".

#### Correction

```python
# Dans IBGatewaySync.__init__, ajouter :
self._req_id_counter: int = 0
self._req_id_lock = threading.Lock()     # ← AJOUTER

# Dans get_historical_data() et toutes les méthodes qui incrémentent :
with self._req_id_lock:
    self._req_id_counter += 1
    req_id = self._req_id_counter
```

Remplacer les reqIds hardcodés dans les autres méthodes :

```python
# get_contract_details() : reqContractDetails(1, ...) → utiliser _get_next_req_id()
# get_shortable_shares() : reqMktData(3, ...)          → idem
# get_earnings_calendar() : reqFundamentalData(2, ...) → idem

def _get_next_req_id(self) -> int:
    with self._req_id_lock:
        self._req_id_counter += 1
        return self._req_id_counter
```

- [x] `_req_id_lock = threading.Lock()` ajouté
- [x] Méthode `_get_next_req_id()` créée
- [x] Les 3 reqIds hardcodés (1, 2, 3) remplacés par `_get_next_req_id()`
- [x] Test : deux appels concurrents à `get_historical_data()` → req_ids distincts

---

### [A-07] Stack trace complète loggée au niveau INFO

- **Fichier :** `execution/ibkr_engine.py` — lignes 330–333
- **Problème :** `traceback.format_stack()` inclut les chemins de fichiers locaux et la structure interne du processus dans les logs de production, niveau INFO.
- **Risque :** Fuite d'information structurelle exploitable si les logs sont exfiltrés.

#### Correction

```python
# Supprimer ou descendre au niveau DEBUG conditionnel :

# Remplacer :
import traceback
logger.info(
    "ibkr_engine_init",
    ...
    stack="".join(traceback.format_stack())
)

# Par :
logger.info(
    "ibkr_engine_init",
    host=self._host,
    port=self._port,
    client_id=self._client_id,
    mode=str(self._mode)
)
# Supprimer l'import traceback si plus utilisé ailleurs
```

- [x] Champ `stack=` supprimé du log `ibkr_engine_init`
- [x] `import traceback` retiré si devenu orphelin
- [x] Vérifier qu'aucun autre `format_stack()` n'est loggé au niveau INFO

---

### [A-08] `get_shortable_shares()` retourne toujours -1

- **Fichier :** `execution/ibkr_engine.py` — méthode `get_shortable_shares()` (~ligne 200–222)
- **Problème :** `shortable = -1` est initialisé mais jamais mis à jour. `IBWrapper` ne capture pas `tickGeneric` (tick 236 = Shortable Shares). La méthode retourne donc toujours `-1`.
- **Risque :** Short exécuté sur une action impossible à emprunter → rejet IBKR avec état incohérent.

#### Correction

**Étape 1 — Implémenter `tickGeneric` dans `IBWrapper` (voir aussi A-03) :**

```python
def tickGeneric(self, reqId, tickType, value):
    """Tick type 236 = shortable shares."""
    with self._lock:
        if tickType == 236:
            self.shortable_shares = value
```

**Étape 2 — Corriger `get_shortable_shares()` :**

```python
def get_shortable_shares(self, contract: Contract) -> float:
    req_id = self._get_next_req_id()
    self.wrapper.shortable_shares = -1.0   # reset avant chaque requête
    self.wrapper.shortable_shares_done = False

    self.client.reqMktData(req_id, contract, "236", False, False, [])
    timeout = time.time() + 5.0

    while time.time() < timeout:
        with self.wrapper._lock:
            if self.wrapper.shortable_shares != -1.0:
                result = self.wrapper.shortable_shares
                break
        time.sleep(0.05)
    else:
        result = -1.0
        logger.warning("shortable_shares_timeout", symbol=contract.symbol)

    try:
        self.client.cancelMktData(req_id)
    except Exception:
        pass

    return result
```

**Étape 3 — Ajouter une garde dans le router/signal avant tout short :**

```python
# execution/order_router.py ou signal_engine ou runner :
if order.direction == "SHORT":
    shortable = self._ibkr.get_shortable_shares(contract)
    if shortable < order.quantity:
        logger.warning("insufficient_shortable_shares",
                       symbol=contract.symbol, available=shortable, needed=order.quantity)
        return None   # bloquer l'ordre short
```

- [x] `tickGeneric(reqId, tickType, value)` implémenté dans `IBWrapper`
- [x] `get_shortable_shares()` corrigée (utilise `_get_next_req_id()`, attend la réponse)
- [x] Garde anti-short ajoutée dans le router avant soumission d'ordre SHORT
- [x] Test : mock `tickGeneric` avec tickType=236, valeur=5000 → méthode retourne 5000

> ✅ **Complet** : `tickGeneric` + `get_shortable_shares()` sur `IBGatewaySync` et `IBKRExecutionEngine`. Garde dans `ExecutionRouter._live_fill()` : SELL bloqué si `shortable < quantity` (REJECTED, filled_qty=0). SELL avec shortable=-1 (indisponible) laissé passer. 4 tests couvrant les cas blocked/allowed/buy-skip/neg.

---

## SPRINT P2 — MOYEN TERME {#sprint-p2}
> À planifier dans le sprint suivant post-déploiement initial.

---

### [A-09] Retry IBKR sans jitter (thundering herd)

- **Fichier :** `execution/ibkr_engine.py` — `_ensure_connected()` (~ligne 559)
- **Correction :** Ajouter un jitter aléatoire sur chaque délai de retry.

```python
import random

retry_delays = [5, 15, 30]
for attempt, base_delay in enumerate(retry_delays):
    jitter = random.uniform(0, base_delay * 0.3)   # ±30% de jitter
    actual_delay = base_delay + jitter
    logger.info("ibkr_reconnect_wait", attempt=attempt+1, delay=round(actual_delay, 1))
    time.sleep(actual_delay)
    ...
```

- [x] Jitter ajouté sur les 3 délais de retry dans `_ensure_connected()`

---

### [A-10] Absence de backup avant rename atomique

- **Fichiers :** `execution/ibkr_engine.py:502`, `risk_engine/kill_switch.py:304`
- **Correction :** Copier le fichier de production en `.bak` avant le rename.

```python
import shutil

def _save_order_map(self) -> None:
    tmp = self._order_map_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(self._order_map, indent=2, default=str))

    # Backup de l'ancien fichier avant remplacement
    if self._order_map_path.exists():
        shutil.copy2(self._order_map_path, self._order_map_path.with_suffix(".bak"))

    tmp.replace(self._order_map_path)
```

Appliquer le même pattern dans `kill_switch.py` et `pair_selection/discovery.py`.

- [x] Backup `.bak` ajouté dans `_save_order_map()`
- [x] Backup `.bak` ajouté dans `kill_switch._save_state()`
- [x] Backup `.bak` ajouté dans `pair_selection/discovery.py`

---

### [A-11] Circuit breaker IBKR local sans auto-reset timeout

- **Fichier :** `execution/ibkr_engine.py` (~ligne 437)
- **Problème :** `_consecutive_failures >= 5` lève une erreur mais ne se réinitialise jamais automatiquement → blocage permanent.
- **Correction :**

```python
# Ajouter un timestamp de dernier échec
self._last_failure_time: Optional[float] = None
CB_RESET_TIMEOUT = 300   # 5 minutes

# Dans _ensure_connected() :
if self._consecutive_failures >= 5:
    elapsed = time.time() - (self._last_failure_time or 0)
    if elapsed < CB_RESET_TIMEOUT:
        raise ConnectionError(
            f"Circuit breaker open: {self._consecutive_failures} consecutive failures. "
            f"Auto-reset in {CB_RESET_TIMEOUT - elapsed:.0f}s"
        )
    else:
        logger.warning("ibkr_circuit_breaker_auto_reset")
        self._consecutive_failures = 0
```

- [x] Timestamp de dernier échec enregistré
- [x] Auto-reset après 300s dans le circuit breaker local
- [x] Test : 5 échecs → circuit ouvert → attente simulée → circuit fermé automatiquement

---

### [A-12] Tests e2e avec `except: pass` (faux positifs)

- **Fichier :** `tests/test_integration_e2e.py` (~ligne 465)
- **Correction :** Remplacer tous les `except: pass` dans les tests par des assertions explicites.

```python
# Remplacer :
try:
    result = some_function()
except:
    pass

# Par :
result = some_function()   # laisser les exceptions se propager naturellement
# OU si une exception est réellement attendue :
with pytest.raises(SpecificException):
    some_function()
```

- [x] Tous les `except: pass` dans les fichiers de test remplacés

---

### [A-13] Tests manquants : perte de connexion IBKR en cours d'ordre

- **Nouveau fichier :** `tests/execution/test_ibkr_disconnect_during_order.py`
- **Scénario à couvrir :**

```python
def test_disconnect_during_order_submission(mock_ibkr_engine):
    """IBKR se déconnecte entre submit et fill confirmation."""
    engine = mock_ibkr_engine
    engine._ib_gateway.disconnect()   # simuler déconnexion
    
    order = build_test_order()
    with pytest.raises(ConnectionError):
        engine.submit_order(order)
    
    # Vérifier : l'ordre n'est pas dans _persisted_order_ids (pas de commit partiel)
    assert order.order_id not in engine._persisted_order_ids

def test_reconnect_after_disconnect_restores_pending_orders(mock_ibkr_engine):
    """Après reconnexion, les ordres pending sont réconciliés."""
    ...
```

- [x] Fichier test créé avec les deux scénarios (`test_connection_error_raised_when_disconnected`, `test_no_partial_commit_when_connection_fails`, `test_reconnect_clears_ib_reference`, +3)
- [x] Tests passants

---

### [A-14] Tests manquants : crash/recovery mid-write

- **Nouveau fichier :** `tests/persistence/test_crash_recovery.py`
- **Scénario :**

```python
def test_order_map_recovery_after_truncated_write(tmp_path):
    """Simule un fichier .tmp tronqué (crash en milieu d'écriture)."""
    path = tmp_path / "order_map.json"
    tmp = path.with_suffix(".tmp")
    
    # Simuler une écriture incomplète
    tmp.write_text('{"incomplete":')  # JSON invalide
    # Ne pas replace() → simuler crash avant rename
    
    # Au redémarrage, le fichier de prod est intact
    engine = build_engine_with_path(path)
    assert engine._order_map == {}   # repart propre sans crash

def test_audit_trail_recovery_after_crash(tmp_path):
    """Vérifie que recover_state() reconstruit correctement les positions."""
    ...
```

- [x] Tests de recovery créés (`test_truncated_tmp_does_not_corrupt_production_file`, `test_bak_file_created_before_rename`, +5)
- [x] Cas : `.tmp` tronqué → le fichier de prod n'est pas altéré

---

### [A-15] `.env.example` : placeholders trop réalistes

- **Fichier :** `.env.example` (~ligne 43)
- **Correction :** Remplacer les valeurs par des placeholders manifestement invalides.

```bash
# Remplacer :
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR_WORKSPACE_ID/YOUR_CHANNEL_ID/YOUR_TOKEN

# Par :
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/REPLACE_WITH_YOUR_WORKSPACE_ID/REPLACE_WITH_YOUR_CHANNEL_ID/REPLACE_WITH_YOUR_TOKEN

# Remplacer :
EMAIL_SMTP_USER=your_email@gmail.com
EMAIL_SMTP_PASS=your_app_password

# Par :
EMAIL_SMTP_USER=REPLACE_WITH_YOUR_GMAIL_ADDRESS@gmail.com
EMAIL_SMTP_PASS=REPLACE_WITH_YOUR_APP_PASSWORD
```

- [x] Placeholders `.env.example` mis à jour
- [x] Ajouter un commentaire au-dessus de chaque section sensible : `# ⚠️ Replace ALL values below before use`

---

## SPRINT P3 — BACKLOG {#sprint-p3}
> Optimisations non bloquantes à traiter après stabilisation du système.

---

### [A-16] `KillSwitch.activate()` : check-then-set non atomique

- **Fichier :** `risk_engine/kill_switch.py` (~lignes 228–231)
- **Correction :** Protéger `check()` et `activate()` par un même `threading.Lock`.

```python
def __init__(self, ...):
    self._lock = threading.Lock()
    self._is_active = False
    ...

def activate(self, reason: str) -> None:
    with self._lock:
        if self._is_active:
            return
        self._is_active = True
    # Suite du traitement hors lock...
    self._save_state()
    self._trigger_callbacks(reason)

def is_active(self) -> bool:
    with self._lock:
        return self._is_active
```

- [x] `threading.Lock` ajouté dans `KillSwitch.__init__`
- [x] `activate()` et `is_active` protégés par lock

---

### [A-17] `audit_trail.recover_state()` jamais appelée au restart

- **Fichier :** `live_trading/runner.py` — `_run_startup_reconciliation()`
- **Problème :** `AuditTrail.recover_state()` est implémentée mais jamais invoquée au démarrage. En cas de crash intra-journalier, `self._positions` repart vide.
- **Correction :** Appeler `recover_state()` comme fallback si la réconciliation broker réussit mais retourne des positions non connues localement.

```python
def _run_startup_reconciliation(self) -> None:
    # 1. Tenter de restaurer l'état local depuis l'audit trail
    if self._audit_trail:
        local_state = self._audit_trail.recover_state()
        if local_state and local_state.get("positions"):
            with self._positions_lock:
                self._positions = local_state["positions"]
            logger.info("positions_restored_from_audit_trail",
                        count=len(self._positions))

    # 2. Réconcilier avec l'état réel du broker (comme avant)
    broker_positions = self._router._engine.get_positions()
    ...
```

- [x] `recover_state()` appelée au démarrage en mode live
- [x] Test : restart après crash → positions correctement restaurées depuis audit trail

---

### [A-18] Secrets en mémoire claire dans `SecretsVault._secrets`

- **Fichier :** `common/secrets.py`
- **Note :** Impact faible — le processus détient déjà les secrets en mémoire pour fonctionner. Cette optimisation est pour les environnements multi-tenant ou haute sécurité.
- **Correction optionnelle :** Utiliser `memoryview` ou la librairie `python-secrets` avec zérotisation de la mémoire. Ou utiliser un vault externe (HashiCorp Vault, AWS Secrets Manager) comme source de vérité.

```bash
# Pour production haute sécurité, documenter dans config/settings.py :
# SECRETS_BACKEND=hashicorp_vault | aws_secrets_manager | env
```

- [x] Documenter la décision (env vars pour v1, vault externe à planifier v2)

---

## CHECKLIST DE VALIDATION FINALE {#checklist-finale}

Avant toute activation du mode live avec capitaux réels, vérifier point par point :

### P0 — OBLIGATOIRES
- [x] **A-01** : `threading.Lock` sur `_positions` implémenté, test de concurrence passant
- [x] **A-02** : Positions supprimées uniquement après confirmation fill, alertes sur rejet ✅

### P1 — OBLIGATOIRES AVANT CAPITAUX RÉELS
- [x] **A-03** : `IBWrapper` thread-safe (RLock sur tous les callbacks), tests passants
- [x] **A-04** : Réconciliation startup lève RuntimeError si `get_positions()` échoue en live
- [x] **A-05** : Bare `except:` remplacés dans `half_life_estimator.py`, appelants gèrent `None`
- [x] **A-06** : `_req_id_counter` protégé, reqIds hardcodés (1, 2, 3) éliminés
- [x] **A-07** : Stack trace supprimée du log INFO IBKR init
- [x] **A-08** : `get_shortable_shares()` retourne la vraie valeur, garde anti-short active ✅

### P2 — DU SPRINT SUIVANT
- [x] **A-09** : Jitter ajouté sur les retry delays
- [x] **A-10** : Backup `.bak` avant chaque rename atomique
- [x] **A-11** : Circuit breaker local avec auto-reset timeout (5 min)
- [x] **A-12** : `except: pass` éliminés des tests e2e
- [x] **A-13** : Tests de déconnexion IBKR en cours d'ordre créés
- [x] **A-14** : Tests de crash/recovery audit trail créés
- [x] **A-15** : `.env.example` placeholders mis à jour

### P3 — BACKLOG
- [x] **A-16** : Lock sur `KillSwitch._is_active`
- [x] **A-17** : `recover_state()` appelée au restart
- [x] **A-18** : Décision documentée sur stratégie secrets v2

### Validation finale système
- [x] Tous les tests unitaires passants (`pytest tests/ -v`) — **3740 passés, 0 échec** ✅
- [ ] Paper trading 5 jours complets sans erreur ni divergence de position
- [ ] Log de réconciliation vérifié manuellement chaque matin (delta broker/local = 0)
- [ ] Kill-switch testé en condition réelle (déclenchement manuel, vérification arrêt complet)
- [ ] Rotation des credentials IBKR avant premier run live
- [ ] Review du `.env` de production par un deuxième développeur

---

## RÉSUMÉ EXÉCUTIF

| Sprint | Items | Effort total estimé | Pré-requis pour production |
|--------|-------|---------------------|---------------------------|
| **P0** | 2 (A-01, A-02) | 1–2 jours | **BLOQUANT** |
| **P1** | 6 (A-03 à A-08) | 3–5 jours | **BLOQUANT** |
| **P2** | 7 (A-09 à A-15) | 5–7 jours | Recommandé |
| **P3** | 3 (A-16 à A-18) | 2–3 jours | Optionnel |

**Durée totale estimée pour P0+P1 :** 4–7 jours de développement pur.  
**Durée totale pour tout le plan :** 2–3 semaines.

> Points forts à ne JAMAIS toucher : idempotence des ordres, rate limiter token-bucket, écriture atomique `.tmp→rename`, réconciliation périodique, kill-switch persistant. Ces mécanismes sont correctement implémentés et constituent la colonne vertébrale de la sécurité financière du système.
