# Audit Technique — EDGECORE V1

**Date** : 2025-07-14     
**Création :** 2026-03-21 à 22:45  
**Périmètre** : sécurité credentials, robustesse IBKR, thread-safety, persistance, tests & CI/CD  
**Résumé** : 🔴 1 critique · 🟠 3 élevés · 🟡 7 moyens/mineurs  

---

## BLOC 1 — Sécurité credentials

### ✅ Points forts

| Élément | Détail |
|---------|--------|
| `common/secrets.py` | `SecretsVault` + `MaskedString` (80 %) — aucune fuite en log |
| `config/dev.yaml`, `config/prod.yaml` | Aucune credential — uniquement des paramètres stratégie/risque |
| `.env.example` | Toutes les valeurs sont des placeholders (`127.0.0.1`, `REPLACE_WITH_YOUR_*`), `ENABLE_LIVE_TRADING=false` par défaut |
| `execution/ibkr_engine.py` | Credentials chargées uniquement via `os.getenv("IBKR_HOST/PORT/CLIENT_ID")` |
| `docker-compose.yml` | Injection des credentials par variables d'environnement (`${IBKR_CLIENT_ID:-1}`) ✅ |

### 🔴 T1-01 — `.gitignore` quasi-vide (CRITIQUE)

**Fichier** : [`.gitignore`](.gitignore)  
**Sévérité** : P0  

`.gitignore` ne contient que `README_PRIVATE.md`. Un `git add .` accidentel commiterait :

- `.env` (credentials IBKR live)
- `config/prod.yaml` (paramètres de production)
- `data/audit/` et `data/audit_test/` (audit trail CSV)
- `*.bak`, `*.tmp` (fichiers de persistence temporaires)
- `data/kill_switch_state.json` (état opérationnel)
- `cache/`, `logs/`, `results/`, `backups/`

**Correction immédiate** : ajouter au minimum :

```gitignore
.env
*.bak
*.tmp
data/
logs/
cache/
results/
backups/
*.pyd
*.so
build/
dist/
__pycache__/
*.pyc
.pytest_cache/
```

---

### 🟠 T1-02 — `COPY . .` dans Dockerfile inclut `.env` si présent

**Fichier** : [`Dockerfile`](Dockerfile)  
**Sévérité** : P1  

L'instruction `COPY . .` dans le stage de production copie l'ensemble du contexte de build. Si un fichier `.env` existe localement (e.g. pour les tests), il sera intégré dans l'image Docker et accessible à quiconque peut `docker run`.

**Correction** : créer un `.dockerignore` :

```dockerignore
.env
*.bak
*.tmp
data/
logs/
cache/
.git/
tests/
```

---

### 🟡 T1-03 — Volume `./config:/app/config` dans `docker-compose.yml`

**Fichier** : [`docker-compose.yml`](docker-compose.yml)  
**Sévérité** : P3  

Le montage bind-mount expose tous les fichiers YAML (dont `prod.yaml`) en lecture-écriture dans le container. En cas de compromission du container, un attaquant peut lire ou modifier la configuration de production.

**Recommandation** : utiliser un volume nommé en lecture seule, ou monter uniquement le fichier `config.yaml` :  
```yaml
volumes:
  - ./config/config.yaml:/app/config/config.yaml:ro
```

---

## BLOC 2 — Robustesse IBKR

### ✅ Points forts

| Mécanisme | Implémentation |
|-----------|----------------|
| Reconnexion | `_ensure_connected()` : retries [5, 15, 30]s + jitter 30%, circuit breaker 5 failures / 300s auto-reset |
| Rate limiting | `TokenBucketRateLimiter(rate=45, burst=10)` thread-safe — en deçà du hard cap TWS 50 req/s |
| Retry | `common/retry.py` : backoff exponentiel plafonné, `jitter_factor=0.1`, exceptions retryables typées |
| Idempotence | `_persisted_order_ids` dans `IBKRExecutionEngine` : garde anti-double soumission |
| Atomic write | `_save_order_map()` : écriture `.tmp` → copie `.bak` → `rename()` atomique |
| Anti-short guard | `_live_fill()` : blocage SELL si shortable shares < quantité demandée (A-08) |
| Fill polling | `execution_engine/router.py` : poll `get_order_status()` 60s max, cancel + log si timeout |

### 🟠 T2-01 — `perm_id=0` enregistré avant confirmation du fill

**Fichier** : [`execution/ibkr_engine.py`](execution/ibkr_engine.py)  
**Sévérité** : P1  

Dans `submit_order()`, la ligne :
```python
perm_id = getattr(trade.order, "permId", 0) or 0
```
...peut retourner `0` si le fill n'est pas encore confirmé par IBKR. L'ordre est ensuite ajouté à `_persisted_order_ids` avec `perm_id=0`. Si un crash survient à cet instant, deux scénarios sont possibles :

1. L'ordre a été exécuté côté broker mais `perm_id=0` est enregistré → à la reconnexion, l'idempotency guard ne reconnaîtra pas l'ordre (id différent) → **double-ordre silencieux**.
2. Si mehrere ordres crashent avec `perm_id=0`, le guard ne distingue pas les entrées.

**Recommandation** : attendre la confirmation `permId > 0` avant d'écrire dans `_persisted_order_ids`, ou enregistrer d'abord `order_id` interne et corriger `perm_id` après confirmation de fill (via callback `orderStatus`).

---

### 🟡 T2-02 — Circuit breaker reset sur durée seule

**Fichier** : [`execution/ibkr_engine.py`](execution/ibkr_engine.py) (circuit breaker via `common/circuit_breaker.py`)  
**Sévérité** : P3  

Le circuit breaker passe de `OPEN` à `HALF_OPEN` uniquement grâce à l'écoulement du temps (`elapsed >= reset_timeout`), sans vérification que la cause racine est résolue. Si la déconnexion IBKR est structurelle (TWS coupé, ban IP), le circuit réessaiera automatiquement après 300s et accumulera à nouveau les failures.

**Recommandation** : dans `_ensure_connected()`, valider que `isConnected()` retourne `True` avant de libérer le circuit breaker (probe active en HALF_OPEN).

---

## BLOC 3 — Thread-safety

### ✅ Points forts

| Composant | Protection |
|-----------|------------|
| `KillSwitch._activation_lock` | `threading.Lock()` — activate/reset atomique (A-16) |
| `TokenBucketRateLimiter` | `threading.Lock()` interne — acquire thread-safe |
| `LiveTradingRunner._positions_lock` | `threading.Lock()` sur le dict positions |
| `CircuitBreaker` | `threading.RLock()` — re-entrant, safe pour callbacks imbriqués |

### 🟠 T3-01 — `IBKRExecutionEngine._active_client_ids` non protégé par Lock

**Fichier** : [`execution/ibkr_engine.py`](execution/ibkr_engine.py)  
**Sévérité** : P1  

`_active_client_ids` est un attribut de **classe** (partagé entre toutes les instances) utilisé pour détecter les `client_id` dupliqués. Le pattern est un check-then-set :

```python
if client_id in IBKRExecutionEngine._active_client_ids:
    raise RuntimeError(...)
IBKRExecutionEngine._active_client_ids[client_id] = ...
```

Ce bloc n'est protégé par aucun lock. Si deux instances sont créées concurremment (e.g. reconnexion depuis deux threads), les deux peuvent passer le check avant que l'une n'écrive, résultant en un `client_id` dupliqué côté TWS, ce qui provoque une déconnexion silencieuse de la session la plus ancienne.

**Correction** :

```python
_active_client_ids_lock = threading.Lock()  # class-level

def __init__(self, ...):
    with IBKRExecutionEngine._active_client_ids_lock:
        if client_id in self._active_client_ids:
            raise RuntimeError(f"client_id {client_id} already in use")
        self._active_client_ids[client_id] = os.getpid()
```

---

### 🟡 T3-02 — `PortfolioAllocator._allocations` non protégé par Lock

**Fichier** : [`portfolio_engine/allocator.py`](portfolio_engine/allocator.py#L149)  
**Sévérité** : P2  

La méthode `allocate()` effectue un check-then-write :

```python
current_heat = sum(self._allocations.values())   # ligne 149
if current_heat + frac > self.max_portfolio_heat: # ligne 150
    frac = max(0, self.max_portfolio_heat - current_heat)
self._allocations[pair_key] = frac               # ligne 154
```

Sans lock, deux appels concurrents à `allocate()` peuvent tous deux lire `current_heat` en sous-estimant la chaleur réelle, et assigner chacun leur fraction, dépassant `max_portfolio_heat` en pratique. Actuellement le `LiveTradingRunner` est mono-thread par paire, mais ce point devient un risque dès qu'un ThreadPoolExecutor est introduit.

**Recommandation** : ajouter `self._lock = threading.Lock()` dans `__init__` et protéger `allocate()` / `release()` / `current_heat`.

---

### 🟡 T3-03 — `ExecutionRouter._pending_orders` non protégé par Lock

**Fichier** : [`execution_engine/router.py`](execution_engine/router.py)  
**Sévérité** : P2  

`_pending_orders: dict[str, OrderStatus]` est lu dans `get_order_status()` et écrit dans `_paper_fill()`, `_live_fill()` — potentiellement depuis plusieurs goroutines si le routeur est partagé. Le dict Python n'est pas thread-safe pour les lectures-écritures concurrentes entre méthodes.

**Recommandation** : ajouter `self._orders_lock = threading.Lock()` et protéger les accès à `_pending_orders`.

---

## BLOC 4 — Persistance

### ✅ Points forts

| Mécanisme | Détail |
|-----------|--------|
| `AuditTrail._atomic_append()` | `os.open(O_WRONLY\|O_APPEND\|O_CREAT)` + `os.fsync()` — durable sur crash kernel |
| `_save_order_map()` | `.tmp` → `.bak` → `rename()` atomique — jamais de fichier tronqué au redémarrage |
| `KillSwitch._save_state()` | Même pattern `.tmp → rename` + fail-safe : active l'arrêt si la persistence échoue |
| `KillSwitch._load_state()` | Chargé à l'`__init__` — survit aux redémarrages process |
| `AuditTrail.recover_state()` | Reconstruction depuis le CSV — `event_id` idempotent |
| Tests crash | `tests/persistence/test_crash_recovery.py` couvre `.tmp` tronqué, `.bak`, kill_switch crash |

### 🟡 T4-01 — Audit trail CSV sans checksum/intégrité

**Fichier** : [`persistence/audit_trail.py`](persistence/audit_trail.py)  
**Sévérité** : P2  

L'audit trail est un fichier CSV append-only. Aucun mécanisme n'empêche la modification silencieuse d'une ligne déjà écrite (bit rot, manipulation manuelle, truncation partielle). `recover_state()` charge les lignes sans valider leur authenticité.

**Recommandation** : ajouter un HMAC SHA-256 par ligne (ou par batch de N lignes) et le vérifier à chaque `recover_state()`. Alternative légère : enregistrer un hash SHA-256 de l'ensemble du fichier dans un fichier `.checksum` séparé, vérifié au démarrage.

---

### 🟡 T4-02 — Pas de rotation du fichier audit trail

**Fichier** : [`persistence/audit_trail.py`](persistence/audit_trail.py)  
**Sévérité** : P3  

Le CSV est append-only sans rotation. En production continue, il grossit indéfiniment. Un fichier de plusieurs Go peut ralentir `recover_state()` significativement au redémarrage.

**Recommandation** : implémenter une rotation journalière ou par taille (ex. 100 Mo) avec archivage compressé, et limiter `recover_state()` à la session en cours.

---

## BLOC 5 — Tests & CI/CD

### ✅ Points forts

| Élément | Détail |
|---------|--------|
| Périmètre CI | push `main`, `fix/**`, `feat/**`, `chore/**` + PRs → couverture complète des branches |
| `pip-audit` | Scan des dépendances à chaque push — vulnérabilités connues bloquantes |
| `ruff` | Linting rapide, bloquant sur erreurs |
| Build Cython | Recompilation `.pyx` vérifiée en CI |
| Tests crash | `test_crash_recovery.py` couvre les scénarios de truncation et de kill switch |
| Tests déconnexion | `test_ibkr_disconnect_during_order.py` couvre `ConnectionError` + pas de commit partiel |
| Baseline | 2659 tests passants, 0 échec, 0 skip |

### 🟡 T5-01 — Seuil de couverture à 40 %

**Fichier** : [`.github/workflows/ci.yml`](.github/workflows/ci.yml)  
**Sévérité** : P2  

`--cov-fail-under=40` est le seuil de blocage CI. Pour un système de trading algorithmique avec gestion du risque, **80 %** est le standard minimal recommandé. Les modules non couverts (e.g. portions de `live_trading/`, `execution_engine/`) peuvent contenir des régressions silencieuses.

**Recommandation** : porter le seuil à 70 % à court terme, 80 % en cible trimestrielle. Identifier les modules les moins couverts avec `pytest --cov-report=term-missing`.

---

### 🟡 T5-02 — `mypy` non-bloquant en CI

**Fichier** : [`.github/workflows/ci.yml`](.github/workflows/ci.yml)  
**Sévérité** : P2  

```yaml
- name: Type check (mypy)
  run: mypy ...
  continue-on-error: true
```

Les erreurs de type ne bloquent jamais la CI. Des erreurs mypy non résolues peuvent masquer des bugs réels de typage (ex. `None` passé là où un objet est attendu).

**Recommandation** : supprimer `continue-on-error: true` après avoir résolu les erreurs existantes (ou les avoir marquées `# type: ignore` de façon traçable avec un ticket). Alternative immédiate : passer en mode `--ignore-missing-imports` strict et bloquer sur les erreurs restantes.

> Note : la règle de codage du projet interdit les `# type: ignore` sans justification — préférer des corrections typées explicites.

---

### 🟡 T5-03 — Aucun scan de secrets dans le pipeline

**Fichier** : [`.github/workflows/ci.yml`](.github/workflows/ci.yml)  
**Sévérité** : P2  

Le pipeline ne contient ni `trufflehog`, ni `gitleaks`, ni `github/codeql-action`. Un credential IBKR commité par erreur (cf. T1-01) passerait inaperçu jusqu'au premier audit manuel.

**Recommandation** : ajouter une étape de scan de secrets avant le build :

```yaml
- name: Secret scan
  uses: trufflesecurity/trufflehog@main
  with:
    path: ./
    base: ${{ github.event.repository.default_branch }}
    head: HEAD
```

---

### 🟡 T5-04 — Pas de build Docker en CI

**Fichier** : [`.github/workflows/ci.yml`](.github/workflows/ci.yml)  
**Sévérité** : P2  

Le `Dockerfile` n'est jamais testé dans la CI. Une modification cassant le build Docker passerait en code review sans être détectée.

**Recommandation** : ajouter un step `docker build --no-cache -t edgecore:ci .` (sans push) pour valider la construisabilité de l'image à chaque PR.

---

## SYNTHÈSE

### Tableau de bord des findings

| ID | Bloc | Sévérité | Titre | Fichier |
|----|------|----------|-------|---------|
| T1-01 | Credentials | 🔴 P0 | `.gitignore` quasi-vide — credentials exposables | [`.gitignore`](.gitignore) |
| T1-02 | Credentials | 🟠 P1 | `COPY . .` Dockerfile inclut `.env` | [`Dockerfile`](Dockerfile) |
| T2-01 | IBKR | 🟠 P1 | `perm_id=0` enregistré avant fill → double-ordre possible | [`execution/ibkr_engine.py`](execution/ibkr_engine.py) |
| T3-01 | Thread-safety | 🟠 P1 | `_active_client_ids` class dict sans Lock | [`execution/ibkr_engine.py`](execution/ibkr_engine.py) |
| T1-03 | Credentials | 🟡 P3 | Volume `./config:/app/config` expose prod.yaml | [`docker-compose.yml`](docker-compose.yml) |
| T2-02 | IBKR | 🟡 P3 | Circuit breaker reset sur durée seule | [`common/circuit_breaker.py`](common/circuit_breaker.py) |
| T3-02 | Thread-safety | 🟡 P2 | `PortfolioAllocator._allocations` sans Lock | [`portfolio_engine/allocator.py`](portfolio_engine/allocator.py) |
| T3-03 | Thread-safety | 🟡 P2 | `ExecutionRouter._pending_orders` sans Lock | [`execution_engine/router.py`](execution_engine/router.py) |
| T4-01 | Persistance | 🟡 P2 | Audit trail CSV sans checksum/HMAC | [`persistence/audit_trail.py`](persistence/audit_trail.py) |
| T4-02 | Persistance | 🟡 P3 | Pas de rotation du fichier audit trail | [`persistence/audit_trail.py`](persistence/audit_trail.py) |
| T5-01 | CI/CD | 🟡 P2 | Seuil couverture CI à 40 % | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| T5-02 | CI/CD | 🟡 P2 | `mypy` non-bloquant (`continue-on-error: true`) | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| T5-03 | CI/CD | 🟡 P2 | Aucun scan de secrets dans le pipeline | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| T5-04 | CI/CD | 🟡 P2 | Pas de build Docker en CI | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |

### Plan de correction recommandé

**Immédiat (avant prochain commit)**

1. **T1-01** : Compléter `.gitignore` — risque zéro, impact maximal.
2. **T1-02** : Créer `.dockerignore` exclusant `.env`, `data/`, `logs/`.

**Court terme (sprint en cours)**

3. **T2-01** : Attendre `permId > 0` avant d'écrire dans `_persisted_order_ids`.
4. **T3-01** : Protéger `_active_client_ids` avec un `threading.Lock()` class-level.

**Moyen terme (prochain sprint)**

5. **T3-02** : Ajouter un Lock dans `PortfolioAllocator`.
6. **T3-03** : Ajouter un Lock dans `ExecutionRouter` pour `_pending_orders`.
7. **T5-01** : Porter le seuil de couverture CI à 70 %.
8. **T5-02** : Résoudre les erreurs mypy et retirer `continue-on-error`.
9. **T5-03** : Intégrer `trufflehog` ou `gitleaks` dans le pipeline.
10. **T5-04** : Ajouter `docker build` de validation en CI.

**Backlog (technique, basse urgence)**

11. **T4-01** : HMAC SHA-256 par ligne dans l'audit trail.
12. **T4-02** : Rotation journalière du CSV d'audit.
13. **T2-02** : Probe active avant libération du circuit breaker.
14. **T1-03** : Volume docker-compose en lecture seule.
