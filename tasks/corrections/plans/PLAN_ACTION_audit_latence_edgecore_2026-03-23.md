# PLAN D'ACTION — EDGECORE — 2026-03-23
**Création :** 2026-03-23 à 22:21  
**Source** : `tasks/audits/AUDIT_LATENCE_EDGECORE.md` (audit du 2026-03-22)  
**Base tests** : 2787 passants (pytest tests/ -q)  
**Total** : 🔴 4 · 🟠 7 · 🟡 4 · **Effort estimé : 6 jours**

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Paralléliser `load_price_data()` — supprimer `time.sleep(0.5)` hardcodé

**Fichier** : `data/loader.py:14-62` (boucle séquentielle + sleep ligne ~55)  
**Problème** : `load_price_data()` charge les données IBKR symbole par symbole en séquence, avec `time.sleep(0.5)` entre chaque. Pour N=50 symboles : ≥ 25 000 ms de sleep + ~15 000 ms de round-trip IBKR = **~40 000 ms sur 60 000 ms de bar_interval**. Le tick consomme 67 % de l'intervalle avant d'entrer dans la logique métier.  
**Correction** :
1. Remplacer la boucle séquentielle par un `ThreadPoolExecutor(max_workers=10)`.
2. Supprimer `time.sleep(0.5)` — utiliser `_ibkr_rate_limiter.acquire()` (TokenBucketRateLimiter existant dans `common/`) avant chaque appel `get_historical_data()`.
3. Maintenir **une seule instance** `IBGatewaySync` partagée (pas de connexion par thread — l'API IBKR est thread-safe pour les requêtes concurrentes via des `reqId` distincts).

```python
# data/loader.py — pattern cible
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.ibkr_rate_limiter import GLOBAL_IBKR_RATE_LIMITER  # voir C-04

def load_price_data(symbols: list[str], ...) -> dict[str, pd.DataFrame]:
    engine = IBGatewaySync(...)
    engine.connect()
    results: dict[str, pd.DataFrame] = {}

    def fetch_one(sym: str) -> tuple[str, pd.DataFrame | None]:
        GLOBAL_IBKR_RATE_LIMITER.acquire()
        return sym, engine.get_historical_data(sym, ...)

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch_one, s): s for s in symbols}
        for fut in as_completed(futures):
            sym, df = fut.result()
            if df is not None:
                results[sym] = df

    engine.disconnect()
    return results
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/data/ -x -q
# Attendu : ≥ 2787 tests passants, pas de timeout IBKR
# Mesure manuelle : timer sur _fetch_market_data() doit passer < 5 000 ms (N=50)
```
**Dépend de** : C-04 (rate-limiter global)  
**Effort** : 1 jour  
**Statut** : ✅ 2026-03-23

---

### [C-02] Éliminer le double fetch données sur les barres de re-découverte

**Fichier** : `live_trading/runner.py` — méthodes `_tick()` et `_maybe_rediscover_pairs()`  
**Problème** : `_maybe_rediscover_pairs()` appelle `_fetch_market_data()` en interne pour alimenter la découverte. Puis `_tick()` appelle `_fetch_market_data()` une deuxième fois immédiatement après. Les données du premier fetch sont ignorées. Coût supplémentaire : **~40 000 ms par cycle de 24 h** (une barre entière perdue).  
**Correction** :
1. Modifier `_maybe_rediscover_pairs()` pour qu'elle **retourne** les données chargées (ou `None` si hors fenêtre).
2. Dans `_tick()`, récupérer ce retour et le passer directement à `_step_generate_signals()`, en sautant le second `_fetch_market_data()` si des données fraîches sont déjà disponibles.

```python
# Pattern cible dans _tick()
fresh_data = self._maybe_rediscover_pairs()   # retourne DataFrame | None
if fresh_data is None:
    fresh_data = self._fetch_market_data()
# utiliser fresh_data pour la suite du tick
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/live_trading/ -x -q
# Attendu : ≥ 2787 tests passants
# Vérifier dans les logs : "_fetch_market_data called" apparaît UNE fois par tick
```
**Dépend de** : C-01  
**Effort** : 0.5 jour  
**Statut** : ✅ 2026-03-23

---

### [C-03] Pointer `engle_granger_fast` Cython dans `pair_selection/discovery.py`

**Fichier** : `pair_selection/discovery.py:27-33`  
**Problème** : `from models.cointegration import engle_granger_test` — la version **Python pur** est utilisée pour les C(N,2) = 1 225 tests (N=50). La fonction Cython `engle_granger_fast()` existe dans `models/cointegration_fast.cp311-win_amd64.pyd` et est compilée, mais **n'est jamais appelée** dans le chemin de découverte. La re-découverte dure 18 000–24 000 ms inutilement.  
**Correction** :
Appliquer le même pattern try/except que `models/spread.py` :

```python
# pair_selection/discovery.py — remplacer l'import actuel
try:
    from models.cointegration_fast import engle_granger_fast as _engle_granger_test
    _CYTHON_EG_AVAILABLE = True
except ImportError:
    from models.cointegration import engle_granger_test as _engle_granger_test
    _CYTHON_EG_AVAILABLE = False
    log.warning(
        "Cython engle_granger_fast indisponible — découverte paires 5-10× plus lente",
        module="pair_selection.discovery",
    )
```

Remplacer tous les appels `engle_granger_test(...)` par `_engle_granger_test(...)` dans le fichier.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/pair_selection/ -x -q
# Attendu : ≥ 2787 tests passants
venv\Scripts\python.exe -c "
from pair_selection.discovery import _CYTHON_EG_AVAILABLE
assert _CYTHON_EG_AVAILABLE, 'Cython non chargé'
print('Cython EG: OK')
"
```
**Dépend de** : Aucune  
**Effort** : 0.25 jour  
**Statut** : ✅ 2026-03-23

---

### [C-04] Créer un rate-limiter IBKR global partagé entre les 3 modules

**Fichiers** :
- `execution/ibkr_sync_gateway.py:27` — `_ibkr_rate_limiter = TokenBucketRateLimiter(rate=45, burst=10)`
- `execution/ibkr_engine.py:38` — `_ibkr_rate_limiter = TokenBucketRateLimiter(rate=45, burst=10)`
- `execution_engine/router.py:97` — `self._rate_limiter = TokenBucketRateLimiter(rate=45, burst=10)`

**Problème** : Trois instances indépendantes, chacune autorisant 45 req/s. En cas d'utilisation simultanée, le débit effectif peut atteindre 135 req/s → **TWS déconnecte automatiquement au-delà de 50 req/s** (hard cap).  
**Correction** :
1. Créer `common/ibkr_rate_limiter.py` :

```python
# common/ibkr_rate_limiter.py
from common.retry import TokenBucketRateLimiter

# Singleton partagé — hard cap TWS = 50 req/s, on opère à 40/s pour marge
GLOBAL_IBKR_RATE_LIMITER = TokenBucketRateLimiter(rate=40, burst=8)
```

2. Dans chacun des 3 fichiers, remplacer la création locale par :

```python
from common.ibkr_rate_limiter import GLOBAL_IBKR_RATE_LIMITER as _ibkr_rate_limiter
```

3. Dans `execution_engine/router.py`, remplacer `self._rate_limiter = ...` par une référence au singleton (adapter l'usage).

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/execution/ tests/execution_engine/ -x -q
# Attendu : ≥ 2787 tests passants
venv\Scripts\python.exe -c "
from common.ibkr_rate_limiter import GLOBAL_IBKR_RATE_LIMITER
from execution.ibkr_sync_gateway import _ibkr_rate_limiter as rl1
from execution.ibkr_engine import _ibkr_rate_limiter as rl2
assert rl1 is GLOBAL_IBKR_RATE_LIMITER
assert rl2 is GLOBAL_IBKR_RATE_LIMITER
print('Rate limiter singleton: OK')
"
```
**Dépend de** : Aucune  
**Effort** : 0.5 jour  
**Statut** : ✅ 2026-03-23

---

## PHASE 2 — MAJEURES 🟠

### [C-05] Supprimer la connexion `IBGatewaySync` par symbole dans `DataLoader.load_ibkr_data()`

**Fichier** : `data/loader.py:~130-160`  
**Problème** : `DataLoader.load_ibkr_data()` crée une nouvelle connexion `IBGatewaySync` (connect + authenticate + disconnect) pour chaque symbole. Overhead de connexion TWS : ~200-500 ms × N symboles, soit jusqu'à 25 000 ms supplémentaires.  
**Correction** :
Extraire la création/connexion hors de la boucle — partager une connexion unique entre tous les appels dans la même session.

```python
# Avant (schéma actuel)
for symbol in symbols:
    engine = IBGatewaySync(...)
    engine.connect()
    df = engine.get_historical_data(symbol, ...)
    engine.disconnect()

# Après
engine = IBGatewaySync(...)
engine.connect()
try:
    for symbol in symbols:
        GLOBAL_IBKR_RATE_LIMITER.acquire()
        df = engine.get_historical_data(symbol, ...)
        results[symbol] = df
finally:
    engine.disconnect()
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/data/ -x -q
# Attendu : ≥ 2787 tests passants
```
**Dépend de** : C-04  
**Effort** : 0.5 jour  
**Statut** : ✅ 2026-03-23

---

### [C-06] `StationarityMonitor` — ADF conditionnel (pas à chaque barre)

**Fichier** : `models/stationarity_monitor.py`  
**Problème** : `statsmodels.adfuller` est appelé **à chaque barre** sur chaque paire active (60 obs). Coût : 1-3 ms/paire. Pour 10 paires : **10-30 ms/barre** en plus de la charge principale.  
**Correction** :
Ajouter un paramètre `check_interval_bars: int = 5` (configurable via `get_settings()`) — n'exécuter ADF que toutes les N barres ou si le z-score franchit un seuil d'alerte :

```python
# models/stationarity_monitor.py
def check(self, spread: pd.Series, bar_count: int) -> StationarityResult:
    if bar_count % self._check_interval != 0:
        return self._last_result   # retourner le résultat mis en cache
    result = adfuller(spread.iloc[-self._window:], ...)
    self._last_result = result
    return result
```

Exposer `stationarity_check_interval_bars` dans `config/schemas.py` (`SignalConfig`) avec default 5.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/models/ tests/signal_engine/ -x -q
# Attendu : ≥ 2787 tests passants
```
**Dépend de** : Aucune  
**Effort** : 0.25 jour  
**Statut** : ✅ 2026-03-23

---

### [C-07] `StructuralBreakDetector` — CUSUM conditionnel (pas à chaque barre)

**Fichier** : `models/structural_break.py`  
**Problème** : CUSUM sur 252 observations appelé **à chaque barre** par paire. Coût : 2-5 ms/paire. Pour 10 paires : **20-50 ms/barre**.  
**Correction** :
Même pattern que C-06 — paramètre `check_interval_bars: int = 10` :

```python
def detect(self, spread: pd.Series, bar_count: int) -> BreakResult:
    if bar_count % self._check_interval != 0:
        return self._last_result
    # ... CUSUM calculation
```

Exposer `structural_break_check_interval_bars` dans `config/schemas.py` (`SignalConfig`) avec default 10.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/models/ -x -q
# Attendu : ≥ 2787 tests passants
```
**Dépend de** : Aucune  
**Effort** : 0.25 jour  
**Statut** : ✅ 2026-03-23

---

### [C-08] Remplacer le polling `time.sleep(0.1)` par `threading.Event` dans `IBGatewaySync`

**Fichier** : `execution/ibkr_sync_gateway.py:~200-260`  
**Problème** : La boucle d'attente des données IBKR poll toutes les 100 ms (`time.sleep(0.1)`). Si TWS répond en 10 ms, le thread attend inutilement 90 ms. De plus, sur timeout, `cancelHistoricalData()` est suivi d'un `time.sleep(0.3)` fixe.  
**Correction** :

```python
# Remplacer la boucle while/sleep par threading.Event
event = threading.Event()
self._wrapper.register_done_event(req_id, event)
completed = event.wait(timeout=30.0)   # déblocage immédiat à la réception

if not completed:
    self.cancel_historical_data(req_id)
    # Pas de sleep fixe — l'annulation est non bloquante
```

Adapter `IBWrapper` pour signaler l'event dès réception du dernier message (`historicalDataEnd`).  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/execution/ -x -q
# Attendu : ≥ 2787 tests passants
```
**Dépend de** : Aucune  
**Effort** : 0.5 jour  
**Statut** : ✅ 2026-03-23

---

### [C-09] Ajouter un garde de fraîcheur temporelle dans `_fetch_market_data()`

**Fichier** : `live_trading/runner.py` — méthode `_fetch_market_data()`  
**Problème** : Après `load_price_data()`, aucune vérification que le dernier timestamp est récent. Si IBKR renvoie des données périmées (cache TWS, symbole suspendu, connexion dégradée), le signal est calculé sur des prix obsolètes sans avertissement.  
**Correction** :

```python
# live_trading/runner.py — dans _fetch_market_data()
from datetime import datetime, timedelta, timezone
MAX_DATA_LAG = timedelta(minutes=10)

for sym, df in prices.items():
    if df is None or df.empty:
        continue
    last_ts = df.index[-1]
    if last_ts.tzinfo is None:
        last_ts = last_ts.tz_localize("UTC")
    lag = datetime.now(timezone.utc) - last_ts
    if lag > MAX_DATA_LAG:
        log.warning(
            "données_périmées",
            symbol=sym,
            lag_minutes=round(lag.total_seconds() / 60, 1),
        )
```

Exposer `max_data_lag_minutes: int = 10` dans `config/schemas.py` (`DataConfig`).  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/live_trading/ tests/data/ -x -q
# Attendu : ≥ 2787 tests passants
```
**Dépend de** : Aucune  
**Effort** : 0.25 jour  
**Statut** : ✅ 2026-03-23

---

### [C-10] Mettre en cache `get_account_balance()` — ne pas appeler par signal

**Fichier** : `live_trading/runner.py` — méthode `_step_execute_signals()`  
**Problème** : `get_account_balance()` déclenche un appel IBKR (~200-500 ms) pour chaque signal à exécuter dans la même barre. Sur 3 signaux simultanés : 600-1 500 ms supplémentaires potentiels.  
**Correction** :
Appeler `get_account_balance()` **une fois au début de `_tick()`** et passer la valeur mise en cache à `_step_execute_signals()` :

```python
# Dans _tick() :
account_balance = self._router.get_account_balance()   # un seul appel
# ...
self._step_execute_signals(signals, prices, account_balance=account_balance)
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/live_trading/ -x -q
# Attendu : ≥ 2787 tests passants
```
**Dépend de** : Aucune  
**Effort** : 0.5 jour  
**Statut** : ✅ 2026-03-23

---

### [C-11] Déporter `_send_alert()` hors du thread principal

**Fichier** : `live_trading/runner.py:~582`  
**Problème** : Les alertes email/Slack sont envoyées sur le thread principal. Un timeout SMTP (30-60 s par défaut) bloquerait le tick entier. Actuellement wrappé dans `try/except` mais le blocage se produit avant l'exception.  
**Correction** :
Utiliser un `ThreadPoolExecutor` dédié (1 worker) pour l'envoi asynchrone :

```python
# live_trading/runner.py — dans __init__
self._alert_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="alerts")

# Dans _send_alert()
self._alert_executor.submit(self._do_send_alert, subject, body, level)

# Dans stop()
self._alert_executor.shutdown(wait=False)
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/live_trading/ -x -q
# Attendu : ≥ 2787 tests passants
```
**Dépend de** : Aucune  
**Effort** : 0.25 jour  
**Statut** : ✅ 2026-03-23

---

## PHASE 3 — MINEURES 🟡

### [C-12] `AuditTrail` — buffer writes, fsync périodique hors chemin trade

**Fichier** : `persistence/audit_trail.py`  
**Problème** : `os.fsync()` est appelé après chaque append. Coût : 1-10 ms sur HDD. Sur SSD NVMe, négligeable, mais bloquant sur les environnements de staging avec disques rotatifs ou VM.  
**Correction** :
Ajouter un flag `fsync_mode: Literal["always", "periodic", "atexit"] = "periodic"` (lu depuis `get_settings().persistence.audit_fsync_mode`). En mode `"periodic"`, fsync toutes les 30 s via un thread background, mais toujours fsync sur `KillSwitch.activate()` et `stop()`.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/persistence/ -x -q
# Attendu : ≥ 2787 tests passants
```
**Dépend de** : Aucune  
**Effort** : 0.25 jour  
**Statut** : ✅ 2026-03-23

---

### [C-13] ML combiner save — déporter vers thread background

**Fichier** : `live_trading/runner.py` — méthode `_step_periodic_tasks()`  
**Problème** : `self._ml_combiner.save()` (joblib dump ~100-500 ms) s'exécute sur le thread principal toutes les 100 barres.  
**Correction** :
Réutiliser l'executor dédié créé pour C-11 :

```python
if self._tick_count % 100 == 0:
    self._alert_executor.submit(self._ml_combiner.save)
```

S'assurer que `save()` est thread-safe (lock interne si nécessaire).  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/live_trading/ -x -q
# Attendu : ≥ 2787 tests passants
```
**Dépend de** : C-11  
**Effort** : 0.25 jour  
**Statut** : ✅ 2026-03-23

---

### [C-14] Ajouter un garde Cython dans `models/__init__.py`

**Fichier** : `models/__init__.py` (actuellement vide)  
**Problème** : Aucune vérification de disponibilité Cython au démarrage. Si le `.pyd` est absent (environnement de production sans recompilation), le système bascule silencieusement sur Python pur sans log d'avertissement visible.  
**Correction** :

```python
# models/__init__.py
import structlog

_log = structlog.get_logger(__name__)

try:
    import models.cointegration_fast  # noqa: F401
    CYTHON_AVAILABLE = True
    _log.info("cython_extensions_loaded", module="models.cointegration_fast")
except ImportError:
    CYTHON_AVAILABLE = False
    _log.warning(
        "cython_extensions_unavailable",
        impact="pair_discovery 5-10x slower, half_life 10x slower",
        fix="venv\\Scripts\\python.exe setup.py build_ext --inplace",
    )
```

**Validation** :
```powershell
venv\Scripts\python.exe -c "from models import CYTHON_AVAILABLE; print('Cython:', CYTHON_AVAILABLE)"
# Attendu : Cython: True (si .pyd présent)
```
**Dépend de** : Aucune  
**Effort** : 0.25 jour  
**Statut** : ✅ 2026-03-23

---

### [C-15] Imposer un cooldown minimum après activation KillSwitch

**Fichier** : `risk_engine/kill_switch.py`  
**Problème** : Aucun délai minimum entre l'activation du kill switch et un éventuel re-démarrage manuel. Un opérateur sous stress pourrait relancer le trading immédiatement après un événement de marché extrême avant d'avoir diagnostiqué la cause.  
**Correction** :
Ajouter `cooldown_seconds: int = 300` dans `KillSwitchConfig` (lu depuis `get_settings().kill_switch.cooldown_seconds`). Dans `reset()`, vérifier que `time.time() - activation_time >= cooldown_seconds` avant d'autoriser le reset.

```python
# risk_engine/kill_switch.py — dans reset()
elapsed = time.time() - self._activation_time
if elapsed < self._config.cooldown_seconds:
    remaining = self._config.cooldown_seconds - elapsed
    raise KillSwitchCooldownError(f"Cooldown actif — {remaining:.0f}s restantes")
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/risk_engine/ -x -q
# Attendu : ≥ 2787 tests passants
```
**Dépend de** : Aucune  
**Effort** : 0.25 jour  
**Statut** : ✅ 2026-03-23

---

## SÉQUENCE D'EXÉCUTION

```
Étape 1 (fondation) : C-04             ← rate-limiter global (prérequis C-01, C-05)
Étape 2 (données)   : C-01, C-03       ← parallèle possible (indépendants)
Étape 3 (données)   : C-05, C-02       ← dépendent de C-01 et C-04
Étape 4 (signal)    : C-06, C-07       ← indépendants, parallèle possible
Étape 5 (infra)     : C-08, C-09, C-10 ← indépendants, parallèle possible
Étape 6 (alertes)   : C-11             ← prérequis C-13
Étape 7 (tech debt) : C-12, C-13, C-14, C-15 ← C-13 dépend de C-11
```

**Diagramme de dépendances** :
```
C-04 ──→ C-01 ──→ C-02
     └──→ C-05

C-03          (autonome)
C-06, C-07    (autonomes)
C-08, C-09    (autonomes)
C-10          (autonome)

C-11 ──→ C-13
C-12, C-14, C-15 (autonomes)
```

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert (C-01, C-02, C-03, C-04 tous ✅)
- [ ] `pytest tests/ -q` : ≥ 2787 tests passants, 0 failed
- [ ] `pytest tests/ -W error::DeprecationWarning -q` : 0 DeprecationWarning
- [ ] `mypy risk/ risk_engine/ execution/ --ignore-missing-imports --no-error-summary` : exit 0
- [ ] `ruff check .` : 0 erreurs
- [ ] Rate-limiter global : `python -c "from common.ibkr_rate_limiter import GLOBAL_IBKR_RATE_LIMITER; print('OK')"` → OK
- [ ] Cython guard : `python -c "from models import CYTHON_AVAILABLE; assert CYTHON_AVAILABLE"` → succès
- [ ] Mesure latence chemin A : `_fetch_market_data()` < 5 000 ms pour N=50 (log structlog à ajouter)
- [ ] Risk tiers cohérents : `get_settings()._assert_risk_tier_coherence()` → OK
- [ ] `EDGECORE_ENV=prod` dans Dockerfile (pas `production`)
- [ ] Kill switch cooldown : test manuel — reset refusé dans les 300 premières secondes
- [ ] Paper trading validé 5 barres consécutives avant live

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|-----|-------|----------|---------|--------|--------|------|
| C-01 | Paralléliser `load_price_data()` | 🔴 | `data/loader.py:55` | 1 j | ⏳ | — |
| C-02 | Éliminer double fetch re-découverte | 🔴 | `runner.py:_tick()` | 0.5 j | ⏳ | — |
| C-03 | `engle_granger_fast` Cython dans discovery | 🔴 | `pair_selection/discovery.py:30` | 0.25 j | ⏳ | — |
| C-04 | Rate-limiter IBKR global partagé | 🔴 | `common/ibkr_rate_limiter.py` (nouveau) | 0.5 j | ⏳ | — |
| C-05 | Connexion IBKR unique dans `load_ibkr_data` | 🟠 | `data/loader.py:130` | 0.5 j | ⏳ | — |
| C-06 | ADF conditionnel toutes N barres | 🟠 | `models/stationarity_monitor.py` | 0.25 j | ⏳ | — |
| C-07 | CUSUM conditionnel toutes N barres | 🟠 | `models/structural_break.py` | 0.25 j | ⏳ | — |
| C-08 | `threading.Event` remplace polling sleep | 🟠 | `execution/ibkr_sync_gateway.py:237` | 0.5 j | ⏳ | — |
| C-09 | Garde fraîcheur données (lag > 10 min) | 🟠 | `runner.py:_fetch_market_data()` | 0.25 j | ⏳ | — |
| C-10 | Cache `get_account_balance()` par tick | 🟠 | `runner.py:_step_execute_signals()` | 0.5 j | ⏳ | — |
| C-11 | `_send_alert()` sur thread dédié | 🟠 | `runner.py:582` | 0.25 j | ⏳ | — |
| C-12 | `AuditTrail` fsync périodique | 🟡 | `persistence/audit_trail.py` | 0.25 j | ⏳ | — |
| C-13 | ML combiner save en background | 🟡 | `runner.py:_step_periodic_tasks()` | 0.25 j | ⏳ | — |
| C-14 | Garde Cython dans `models/__init__.py` | 🟡 | `models/__init__.py` | 0.25 j | ⏳ | — |
| C-15 | Cooldown KillSwitch (300 s) | 🟡 | `risk_engine/kill_switch.py` | 0.25 j | ⏳ | — |
| **TOTAL** | | | | **6 j** | | |
