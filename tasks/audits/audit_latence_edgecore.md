# AUDIT LATENCE — EDGECORE_V1
**Date** : 2026-03-22 (génération automatique post-lecture complète du code source)  
**Auditeur** : GitHub Copilot — Claude Sonnet 4.6  
**Périmètre** : chemin critique temps réel, pair discovery, I/O synchrones, thread contention  
**Référence** : `tasks/prompts/audit_latence_prompt.md` — v1.0

---

## Légende des criticités

| Symbole | Seuil | Description |
|---------|-------|-------------|
| 🔴 | > 500 ms ou bloquant | Critique — dépasse le bar_interval actif |
| 🟠 | 1 – 500 ms | Majeur — coût mesurable sur le chemin A |
| 🟡 | < 1 ms ou hors chemin A | Mineur — tech debt ou risque indirect |
| ✅ | — | Implémentation correcte |

---

## BLOC 1 — Chemins critiques

### 1.1 · Chemin A — Boucle temps réel (`_tick()`)

**Fichier** : `live_trading/runner.py`  
**Fréquence** : toutes les `bar_interval_seconds = 60 s` (après le `time.sleep()` qui suit le tick)

| # | Étape | Fonction | Coût estimé | Statut |
|---|-------|----------|-------------|--------|
| 1 | Poll confirmations ordres | `_process_fill_confirmations()` → `router.get_order_status()` | ~100-500 ms (appel IBKR) | 🟠 |
| 2 | Réconciliation broker | `_maybe_reconcile()` → `BrokerReconciler` (toutes les 5 min) | 0 ms hors fenêtre / 500-2 000 ms si déclenchée | 🟠 |
| 3 | Kill switch check | `_step_check_kill_switch()` | < 0.1 ms | ✅ |
| 4 | Re-découverte paires | `_maybe_rediscover_pairs()` → `_fetch_market_data()` interne | 0 ms hors fenêtre / **35 000–50 000 ms** si déclenchée | 🔴 |
| 5 | **Chargement données marché** | `_fetch_market_data()` → `load_price_data()` | **35 000–50 000 ms (N=50)** | 🔴 |
| 6 | Stops | `_step_process_stops()` | ~1-5 ms + appel IBKR si stop déclenché | 🟡 |
| 7 | Génération signaux | `_step_generate_signals()` (6 composants) | **15-50 ms (N_pairs=10)** | 🟠 |
| 8 | Exécution signaux | `_step_execute_signals()` → `get_account_balance()` + `submit_order()` | ~100-500 ms par signal | 🟠 |
| 9 | Tâches périodiques | `_step_periodic_tasks()` → ML save (toutes les 100 ticks) | ~1 ms / 100-500 ms si save | 🟡 |
| 10 | Métriques | `_update_metrics()` | < 1 ms | ✅ |

**Estimation totale chemin A (N=50 symboles, steady-state)**

```
load_price_data()  : 50 × (IBKR_rtt ~300ms + sleep 500ms) = ~40 000 ms
StationarityMonitor: 10 paires × 3 ms = 30 ms
StructuralBreak    : 10 paires × 4 ms = 40 ms
TOTAL DOMINANT     : ~40 100 ms
bar_interval       : 60 000 ms
```

> **Conclusion** : le tick consomme ~67 % de l'intervalle avant même d'entrer dans la logique métier. Avec N > 70 symboles, le tick déborde systématiquement.

---

### 1.2 · Chemin B — Re-découverte des paires

**Fichier** : `live_trading/runner.py:_maybe_rediscover_pairs()` → `strategies.pair_trading.PairTradingStrategy.find_cointegrated_pairs()`  
**Fréquence** : toutes les 24 h (timer `_last_discovery`)

```
Étape 1 : _fetch_market_data() dans _maybe_rediscover_pairs()  → 40 000 ms (N=50)
Étape 2 : PairTradingStrategy.find_cointegrated_pairs()
          └── PairDiscoveryEngine.discover() ou méthode interne
              └── engle_granger_test() pur Python × C(50,2) = 1 225 tests
                  ≈ 5-20 ms/test × 1 225 = 6 000–24 000 ms
Étape 3 : _fetch_market_data() dans _tick() (DOUBLE FETCH)         → 40 000 ms
TOTAL    : ~86 000 – 104 000 ms (1,4 à 1,7 minutes bloquant)
```

> 🔴 **BLOQUANT** : Pendant la barre de redécouverte, le tick dure ~100 secondes. Cette latence est invisible dans les logs sauf si on mesure explicitement `_maybe_rediscover_pairs()`.

---

### 1.3 · Point d'entrée boucle principale

```python
# live_trading/runner.py:~185
while running:
    self._tick()
    time.sleep(bar_interval_seconds)   # sleep APRÈS le tick
```

Le `time.sleep()` se place **après** le tick, donc tout débordement repousse la prochaine barre. Il n'y a pas de mécanisme de rattrapage (pas de `deadline - elapsed`).

---

## BLOC 2 — Usage Cython vs. stubs Python

### 2.1 · Inventaire des fonctions Cython disponibles

**Module compilé** : `models/cointegration_fast.cp311-win_amd64.pyd`  
**Fonctions exportées** : `engle_granger_fast()`, `half_life_fast()`

| Fonction Cython | Fichier Python appelant | Statut |
|-----------------|------------------------|--------|
| `half_life_fast` | `models/spread.py:8-20` | ✅ Correct — try/except avec flag et warning |
| `engle_granger_fast` | `pair_selection/discovery.py:27-33` | 🔴 **JAMAIS APPELÉE** |

### 2.2 · Défaut critique — PairDiscoveryEngine bypass Cython

**Fichier** `pair_selection/discovery.py:27-33` :

```python
from models.cointegration import engle_granger_test   # ← pur Python
# engle_granger_fast() de cointegration_fast n'est jamais importée
```

L'opération la plus coûteuse du pipeline — les C(N, 2) = 1 225 tests (N=50) d'Engle-Granger — s'exécute **entièrement en Python pur**, alors que l'extension Cython compilée `engle_granger_fast` existe et est disponible.

**Gain attendu** : 5-10× sur la durée de re-découverte.

```
AVANT  : 1 225 tests ×  15 ms/test  = 18 375 ms
APRÈS  : 1 225 tests × 2-3 ms/test  =  2 450 –  3 675 ms
```

### 2.3 · Bon exemple (modèle à suivre) — `models/spread.py`

```python
try:
    from models.cointegration_fast import half_life_fast as _half_life_fast_cython
    _HALF_LIFE_CYTHON = True
except ImportError:
    _HALF_LIFE_CYTHON = False
    log.warning("Cython half_life_fast indisponible — 10× plus lent")
```

Le même pattern doit être appliqué à `engle_granger_test` dans `pair_selection/discovery.py`.

### 2.4 · Absence de garde au démarrage

**Fichier** : `models/__init__.py` — **vide**  
Aucune vérification de disponibilité Cython au lancement → l'opérateur n'est pas averti en cas de `.pyd` manquant.

---

## BLOC 3 — Latence IBKR

### 3.1 · `load_price_data()` — bottleneck principal

**Fichier** `data/loader.py:14-62`

```python
# data/loader.py:~55
for symbol in symbols:
    data = engine.get_historical_data(symbol, ...)
    _time.sleep(0.5)   # 🔴 rate limiting hardcodé
```

| Facteur | Coût pour N=50 |
|---------|---------------|
| `time.sleep(0.5)` × 50 | **25 000 ms garantis** |
| IBKR round-trip × 50 (~300 ms chacun) | **15 000 ms** (optimal) |
| **Total** | **≥ 40 000 ms** |

Problèmes cumulés :
- La boucle est **séquentielle** — un symbole à la fois
- Le sleep est un rate-limiter naïf qui **ignore** le `TokenBucketRateLimiter` déjà implémenté dans `common/`
- La connexion `IBGatewaySync` est créée **une fois par appel** à `load_price_data()` mais les données sont récupérées séquentiellement sans tirer parti d'un pool

### 3.2 · `DataLoader.load_ibkr_data()` — connexion par symbole

**Fichier** `data/loader.py:~130-160`

```python
# Une NOUVELLE connexion IBKR par symbole
engine = IBGatewaySync(host=..., port=..., client_id=...)
engine.connect()
data = engine.get_historical_data(symbol, ...)
engine.disconnect()
```

Overhead de connexion TWS : ~200-500 ms par symbo. Multiplié par N, ce pattern est prohibitif.

### 3.3 · `get_historical_data()` — polling busy-wait

**Fichier** `execution/ibkr_sync_gateway.py:~200-260`

```python
while time.time() - t0 < timeout:
    time.sleep(0.1)   # 🟠 100 ms de granularité
    if self._wrapper.is_done(req_id):
        break
# Sur timeout :
self.cancel_historical_data(req_id)
time.sleep(0.3)       # 🟠 sleep fixe après cancel
```

- Latence minimum de réponse bridée à **100 ms** (même si TWS répond en 10 ms)
- Sur chaque timeout (symbole invalide, TWS débordé) : **300 ms supplémentaires** au lieu d'un event `threading.Event.wait()`

### 3.4 · Trois rate-limiters indépendants (risque de déconnexion TWS)

| Module | Variable | Taux déclaré |
|--------|----------|-------------|
| `execution/ibkr_sync_gateway.py:27` | `_ibkr_rate_limiter` | 45 req/s, burst 10 |
| `execution/ibkr_engine.py:38` | `_ibkr_rate_limiter` | 45 req/s, burst 10 |
| `execution_engine/router.py:97` | `self._rate_limiter` | 45 req/s, burst 10 |

Ces trois instances ne **partagent pas leur état**. En cas d'utilisation simultanée (live trading pendant la re-découverte), le débit effectif vers TWS peut atteindre **135 req/s**, soit 2,7× le hard cap de 50 req/s. TWS déconnecte automatiquement au-delà de 50 req/s.

> **Note** : `load_price_data()` n'utilise PAS ce rate-limiter — il a son propre `time.sleep(0.5)` hardcodé. Cela rend la situation encore plus imprévisible.

---

## BLOC 4 — Threading et contention

### 4.1 · Architecture des threads

```
Thread principal : _tick() complet — toute la logique métier est synchrone
Thread IB msg   : IBWrapper._msg_thread — boucle de messages ib_insync
Thread pool     : ThreadPoolExecutor pour pair discovery (cpu_count-1 workers)
Thread ML       : aucune — ML combiner exécuté sur thread principal
```

### 4.2 · `_positions_lock` — section critique sur chemin A

**Fichier** `live_trading/runner.py`

```python
_positions_lock = threading.Lock()
```

Le verrou est acquis dans :
- `_process_fill_confirmations()` — mise à jour positions
- `_step_process_stops()` — lecture snapshot + soumission ordres stop
- `_step_execute_signals()` — lecture capital disponible + soumission ordres

**Risque** : si `submit_order()` est lent (await IBKR), le verrou est tenu pendant toute la durée de l'appel, bloquant les autres sections critiques.

### 4.3 · `IBWrapper._lock = threading.RLock()` — polling partagé

**Fichier** `execution/ibkr_sync_gateway.py`

Le thread principal acquiert `_lock` dans la boucle `while time.time()-t0 < timeout: time.sleep(0.1)`. Le `_msg_thread` acquiert le même `RLock` pour écrire les données reçues. Risque de contention visible à haute fréquence de réponse TWS.

### 4.4 · ThreadPoolExecutor dans discovery.py

```python
# pair_selection/discovery.py
with ThreadPoolExecutor(max_workers=os.cpu_count() - 1) as pool:
    futures = {pool.submit(engle_granger_test, ...): pair for pair in candidates}
```

Bon pattern. Cependant, `engle_granger_test` est la version **Python pur** (cf. BLOC 2). Le parallélisme compense partiellement mais le GIL limite l'accélération réelle des opérations CPU-bound Python.

---

## BLOC 5 — Pipeline de signaux

### 5.1 · Inventaire des 6 composants `SignalGenerator.generate()`

| Composant | Fréquence | Coût estimé | Statut |
|-----------|-----------|-------------|--------|
| `SpreadModel` — OLS hedge ratio | chaque barre | ~0.1-0.5 ms | ✅ |
| `KalmanHedgeRatio` — mise à jour état | chaque barre | ~0.05 ms (O(1)) | ✅ |
| `ZScoreCalculator` — rolling mean/std pandas | chaque barre | ~0.2-0.5 ms | ✅ |
| `StationarityMonitor` — ADF statsmodels | **chaque barre** | **1-3 ms × N_pairs** | 🟠 |
| `StructuralBreakDetector` — CUSUM | **chaque barre** | **2-5 ms × N_pairs** | 🟠 |
| `MomentumOverlay` — rolling returns | chaque barre | ~0.2 ms | ✅ |
| `MarkovRegimeDetector` — HMM refit | toutes les 50 barres | 50-200 ms si activé | 🟡 désactivé |

**Coût signal pour N_pairs=10, par barre :**
```
StationarityMonitor : 10 × 2 ms  = 20 ms
StructuralBreak     : 10 × 3.5 ms = 35 ms
Autres composants   :               5 ms
TOTAL               :              60 ms/barre
```

### 5.2 · `StationarityMonitor` — ADF chaque barre

**Fichier** : `models/stationarity_monitor.py`

`statsmodels.adfuller` est appelé sur les 60 dernières observations à chaque barre, pour chaque paire active. Le test ADF implique une régression OLS, un calcul de statistique et une comparaison aux valeurs critiques — il ne peut pas être amortis sur plusieurs barres sans perte d'information.

**Optimisation possible** : appel conditionnel (toutes les K barres, ou si le z-score franchit un seuil). Risque : retard de détection de non-stationnarité.

### 5.3 · `StructuralBreakDetector` — CUSUM chaque barre

**Fichier** : `models/structural_break.py`

CUSUM sur 252 observations, 2-5 ms. Même profil que `StationarityMonitor`. Le pattern de sampling conditionnel s'applique.

### 5.4 · `MarkovRegimeDetector` — désactivé par défaut

`use_markov_regime: False` dans la config. Si activé, refit HMM tous les 50 barres : **50-200 ms bloquants** sur le thread principal. Ne pas activer en production sans déport vers un thread dédié.

---

## BLOC 6 — I/O synchrones

### 6.1 · `AuditTrail` — `os.fsync()` sur chaque événement trade

**Fichier** : `persistence/audit_trail.py`

```python
f.write(line)
os.fsync(f.fileno())   # 🟡 flush disque garanti — 1-10 ms
```

Sur un disque HDD : 5-10 ms par trade. Sur SSD NVMe : 0.1-1 ms. Acceptable en low-frequency mais bloquant si le volume de trades/heure est > 100.

**Optimisation** : buffer en mémoire + flush toutes les X secondes (avec flush explicite sur kill switch).

### 6.2 · ML combiner — save toutes les 100 ticks

**Fichier** : `live_trading/runner.py:_step_periodic_tasks()`

```python
if self._tick_count % 100 == 0:
    self._ml_combiner.save()   # joblib dump → disque
```

`joblib.dump()` à chaque 100e tick : ~100-500 ms selon la taille du modèle. S'exécute sur le thread principal.

### 6.3 · `KillSwitch._save_state()` — JSON synchrone sur activation

**Fichier** : `risk_engine/kill_switch.py`

Écriture JSON + flush à chaque activation. Acceptable (rare en production), mais le fichier cible (`data/kill_switch_state.json`) est dans le répertoire de travail — pas de gestion d'erreur visible si le disque est plein.

### 6.4 · `_send_alert()` — alerte email/Slack sur thread principal

**Fichier** : `live_trading/runner.py:~582`

Wrappé dans `try/except` mais bloquant si le serveur SMTP est lent (timeout socket par défaut : 30-60 s). Devrait être déporté dans un thread dédié ou une queue.

---

## BLOC 7 — Qualité des données

### 7.1 · Absence de garde de fraîcheur temporelle

**Fichier** : `live_trading/runner.py:_fetch_market_data()`

Après `load_price_data()`, aucune vérification que le dernier timestamp est "récent" (< 5 min). Si IBKR renvoie des données périmées (cache, symbole suspendu), le signal est calculé sur des prix obsolètes sans log d'avertissement.

**Pattern manquant** :
```python
last_ts = prices.index[-1]
if (datetime.now(timezone.utc) - last_ts) > timedelta(minutes=10):
    log.warning("données périmées", symbol=sym, lag_min=...)
```

### 7.2 · Double fetch sur les barres de re-découverte

**Fichier** : `live_trading/runner.py:_tick()` + `_maybe_rediscover_pairs()`

```
_tick()
├── _maybe_rediscover_pairs()       ← appelle _fetch_market_data()  [1er fetch]
│   └── _fetch_market_data()        ← load_price_data() : ~40 000 ms
└── _fetch_market_data()            ← load_price_data() : ~40 000 ms  [2ème fetch]
```

Les données du 1er fetch sont jetées — elles ne sont pas passées au signal generator. Le 2ème fetch charge a nouveau les mêmes données. Coût supplémentaire : **~40 000 ms par cycle de 24 h**.

**Correction** : récupérer les données une seule fois et les partager.

### 7.3 · Source de données : IBKR exclusif

**Statut** : ✅  
Aucun fallback Yahoo Finance ni autre source externe dans le code production (vérifié `grep -r "yfinance|yahoo" --include="*.py"` → 0 résultat hors `tests/` et `docs/`). La politique institutionnelle est respectée. Audit master 2026-03-22 confirme.

### 7.4 · `what_to_show="ADJUSTED_LAST"` — correct

Les données sont ajustées des dividendes et splits. Cohérent avec un horizon période de détention multi-jours.

---

## BLOC 8 — Résilience et cold start

### 8.1 · Résilience connexion IBKR

**Fichier** : `execution/ibkr_engine.py:_ensure_connected()`

```
3 tentatives avec backoff exponentiel : 5 s / 15 s / 30 s
Circuit breaker après 5 échecs consécutifs
Auto-reset du circuit breaker après 300 s
```

✅ Pattern correct. Cependant `IBGatewaySync` (voie synchrone utilisée par `load_price_data()`) n'a pas de circuit breaker équivalent visible. Une déconnexion TWS pendant la boucle de chargement lèverait une exception non gérée.

### 8.2 · Cold start — blocage au premier tick

Au premier tick, `_last_discovery is None` → `_maybe_rediscover_pairs()` se déclenche immédiatement :

```
Premier tick :
  1. _fetch_market_data()        dans _maybe_rediscover_pairs()   ~40 000 ms
  2. find_cointegrated_pairs()                                     ~18 000 ms
  3. _fetch_market_data()        dans _tick()                      ~40 000 ms
  TOTAL cold start : ~98 000 ms (~1 min 38 s)
```

Ce délai est attendu mais non documenté dans les logs d'initialisation. L'opérateur pourrait croire que le système est suspendu.

### 8.3 · KillSwitch — reset manuel uniquement

**Fichier** : `risk_engine/kill_switch.py`

Une fois le kill switch activé, seul un reset manuel (appel API ou redémarrage) peut relancer le trading. Correct pour la sécurité, mais aucun délai minimum (`cooldown`) n'est imposé avant un re-démarrage — risque de re-trading immédiat après un événement de marché extrême.

### 8.4 · Cache pair discovery — TTL 12 h

`PairDiscoveryEngine` mémoïse les résultats avec un TTL configurable (12 h par défaut via `use_cache=True`). Correct — évite de refaire O(N²) tests à chaque démarrage après un crash.

---

## SYNTHÈSE

### Tableau de bord criticité

| # | Problème | Fichier | Criticité | Gain estimé |
|---|----------|---------|-----------|-------------|
| P-01 | `load_price_data()` séquentielle + `sleep(0.5)` | `data/loader.py:55` | 🔴 | −95% latence chemin A |
| P-02 | Double fetch barre re-découverte | `runner.py:_tick()` + `_maybe_rediscover_pairs()` | 🔴 | −50% sur barre 24 h |
| P-03 | `engle_granger_fast` Cython jamais appelée | `pair_selection/discovery.py:30` | 🔴 | 5-10× re-découverte |
| P-04 | 3 rate-limiters indépendants → 135 req/s | `ibkr_engine.py`, `ibkr_sync_gateway.py`, `router.py` | 🔴 | Prévient déconnexion TWS |
| P-05 | `DataLoader.load_ibkr_data()` — connexion/symbole | `data/loader.py:130` | 🟠 | −300 ms × N |
| P-06 | `AuditTrail os.fsync()` par trade | `persistence/audit_trail.py` | 🟡 | −5 ms/trade |
| P-07 | `StationarityMonitor` ADF chaque barre | `models/stationarity_monitor.py` | 🟠 | −20 ms/barre (N=10) |
| P-08 | `StructuralBreakDetector` CUSUM chaque barre | `models/structural_break.py` | 🟠 | −35 ms/barre (N=10) |
| P-09 | Polling `time.sleep(0.1)` + cancel `sleep(0.3)` | `ibkr_sync_gateway.py:237` | 🟠 | −100 ms/symbole |
| P-10 | Aucune vérification fraîcheur données | `runner.py:_fetch_market_data()` | 🟠 | Qualité signal |
| P-11 | `get_account_balance()` par signal | `runner.py:_step_execute_signals()` | 🟠 | −200-500 ms/signal |
| P-12 | `_send_alert()` sur thread principal | `runner.py:582` | 🟡 | Robustesse |
| P-13 | ML combiner save toutes les 100 ticks | `runner.py:_step_periodic_tasks()` | 🟡 | −200 ms/100 ticks |
| P-14 | `models/__init__.py` vide | `models/__init__.py` | 🟡 | Observabilité |
| P-15 | Aucun cooldown après KillSwitch | `risk_engine/kill_switch.py` | 🟡 | Sécurité opérationnelle |

---

### Bilan latence

| Indicateur | Valeur actuelle | Cible institutionnelle |
|-----------|----------------|----------------------|
| Chemin A — steady state (N=50) | **~40 100 ms** | < 500 ms |
| Chemin A — barre 24 h redécouverte | **~98 000 ms** | < 5 000 ms |
| Latence data seule (N=50) | **~40 000 ms** | < 200 ms (parallèle) |
| Latence signal (N_pairs=10) | ~60 ms | < 20 ms |
| Capacité max symboles avant débordement | **~70** | > 200 |

---

### Top 3 priorités

#### 🔴 P-01 — Paralléliser `load_price_data()` avec `TokenBucketRateLimiter`

```python
# data/loader.py — remplacement du pattern séquentiel
from common.retry import TokenBucketRateLimiter
from concurrent.futures import ThreadPoolExecutor, as_completed

_rate = TokenBucketRateLimiter(rate=40, burst=8)   # ← shared unique

def load_price_data(symbols, ...):
    results = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        def fetch_one(sym):
            _rate.acquire()
            return sym, engine.get_historical_data(sym, ...)
        for sym, df in pool.map(fetch_one, symbols):
            results[sym] = df
    return results
```

Gain : **~95% de réduction** — de ~40 000 ms à ~2 000 ms (N=50, parallèle 10 workers à 40 req/s).

#### 🔴 P-03 — Pointer `engle_granger_fast` Cython dans `discovery.py`

```python
# pair_selection/discovery.py
try:
    from models.cointegration_fast import engle_granger_fast as _eg_test
    _CYTHON_AVAILABLE = True
except ImportError:
    from models.cointegration import engle_granger_test as _eg_test
    _CYTHON_AVAILABLE = False
    log.warning("Cython engle_granger_fast indisponible — 5-10× plus lent")
```

Gain : **5-10× sur la re-découverte** — de ~18 000 ms à ~2 000-3 000 ms (N=50 symboles).

#### 🔴 P-04 — Rate-limiter global partagé

```python
# common/ibkr_rate_limiter.py  (nouveau module singleton)
from common.retry import TokenBucketRateLimiter
_GLOBAL_IBKR_RATE_LIMITER = TokenBucketRateLimiter(rate=45, burst=10)

# Remplacer les 3 instances locales par import de ce singleton
from common.ibkr_rate_limiter import _GLOBAL_IBKR_RATE_LIMITER as _ibkr_rate_limiter
```

Impact : élimine le risque de déconnexion TWS par dépassement des 50 req/s.

---

### Plan de correction recommandé

| Sprint | Items | Effort | Impact |
|--------|-------|--------|--------|
| S1 (immédiat) | P-01, P-03, P-04 | 4-6h | −97% latence dominante |
| S2 (sprint 2) | P-02, P-05, P-09, P-11 | 6-8h | −50% latence secondaire |
| S3 (tech debt) | P-07, P-08, P-06, P-12, P-13 | 4-6h | Robustesse + observabilité |
| S4 (longue traîne) | P-10, P-14, P-15 | 2-4h | Qualité signal + sécurité |

---

*Document généré par audit automatisé — vérifier la cohérence avec les tests de régression avant tout changement.*
