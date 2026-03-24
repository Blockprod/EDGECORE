# PLAN D'ACTION — EDGECORE — 2026-03-21
**Création :** 2026-03-21 à 22:48  

Sources : `tasks/audits/audit_technical_edgecore.md`  
Total : 🔴 1 · 🟠 3 · 🟡 10 · Effort estimé : 3 jours

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Compléter `.gitignore`
Fichier : `.gitignore`  
Problème : `.gitignore` ne contient que `README_PRIVATE.md`. Un `git add .` accidentel exposerait `.env` (credentials IBKR), `data/` (audit trail), `*.bak/.tmp` (persistence), `logs/`, `cache/`, `results/`.  
Correction : ajouter les entrées manquantes :
```
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
Validation :
```powershell
git status --short | Select-String "data/|logs/|\.env|\.bak|\.tmp"
# Attendu : aucune sortie (ces fichiers/dossiers sont ignorés)
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659 passed, 0 failed
```
Dépend de : Aucune  
Statut : ⏳

---

## PHASE 2 — MAJEURES 🟠

### [C-02] Créer `.dockerignore` pour exclure `.env` du contexte de build
Fichier : `.dockerignore` (à créer à la racine)  
Problème : `Dockerfile` contient `COPY . .` — si un fichier `.env` existe localement (usage dev/test), il est intégré dans l'image Docker, exposant les credentials IBKR à quiconque peut exécuter l'image.  
Correction : créer `.dockerignore` avec le contenu suivant :
```
.env
*.bak
*.tmp
data/
logs/
cache/
results/
backups/
.git/
tests/
__pycache__/
*.pyc
*.pyd
*.so
build/
dist/
.pytest_cache/
venv/
```
Validation :
```powershell
docker build --no-cache -t edgecore:test . 2>&1 | Select-String "\.env|COPY"
# Attendu : pas de mention de .env dans les layers
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659 passed, 0 failed
```
Dépend de : Aucune  
Statut : ⏳

---

### [C-03] Attendre `permId > 0` avant d'enregistrer dans `_persisted_order_ids`
Fichier : `execution/ibkr_engine.py`  
Problème : dans `submit_order()`, `perm_id = getattr(trade.order, "permId", 0) or 0` peut valoir `0` si le fill n'est pas encore confirmé. L'ordre est immédiatement ajouté à `_persisted_order_ids` avec `perm_id=0`. Un crash à cet instant produit un double-ordre silencieux au redémarrage (l'idempotency guard ne reconnaît pas l'ordre IBKR).  
Correction :
1. Enregistrer d'abord l'`order_id` interne dans `_persisted_order_ids` (clé = `order_id`, non `perm_id`).
2. Finaliser l'enregistrement `perm_id` uniquement après que `trade.isDone()` ou `trade.orderStatus.status` == `"Filled"` soit confirmé.
3. Si `permId` reste `0` après le timeout de fill confirmation, logger une alerte et laisser la réconciliation corriger l'état.

Alternative immédiate (sans refactor complet) : lire `perm_id` depuis `trade.orderStatus.permId` après un court wait de confirmation (500ms) avant de persister.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/execution/ -x -q
# Attendu : tous les tests execution passent
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659 passed, 0 failed
```
Dépend de : Aucune  
Statut : ⏳

---

### [C-04] Protéger `_active_client_ids` (dict de classe) par un Lock
Fichier : `execution/ibkr_engine.py`  
Problème : `_active_client_ids` est un attribut de **classe** partagé entre toutes les instances. Le pattern check-then-set n'est protégé par aucun lock. Une création concurrente de deux instances (reconnexion depuis deux threads) peut aboutir à un `client_id` dupliqué côté TWS, déclenchant une déconnexion silencieuse de la session existante.  
Correction :
```python
# Ajouter au niveau classe (juste après _active_client_ids)
_active_client_ids_lock: ClassVar[threading.Lock] = threading.Lock()

# Dans __init__, remplacer le check-then-set par :
with IBKRExecutionEngine._active_client_ids_lock:
    if client_id in IBKRExecutionEngine._active_client_ids:
        raise RuntimeError(f"client_id {client_id} déjà utilisé par PID {IBKRExecutionEngine._active_client_ids[client_id]}")
    IBKRExecutionEngine._active_client_ids[client_id] = os.getpid()
```
Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/execution/ -x -q
# Attendu : tous les tests execution passent
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659 passed, 0 failed
```
Dépend de : Aucune  
Statut : ⏳

---

## PHASE 3 — MINEURES 🟡

### [C-05] Protéger `PortfolioAllocator._allocations` par un Lock
Fichier : `portfolio_engine/allocator.py:149`  
Problème : `allocate()` effectue un check-then-write sur `_allocations` sans lock. Deux appels concurrents (e.g. via `ThreadPoolExecutor` sur plusieurs paires) lisent `current_heat` simultanément en sous-estimant la chaleur réelle, puis écrivent chacun leur fraction, dépassant `max_portfolio_heat`.  
Correction :
```python
# Dans __init__ :
self._lock = threading.Lock()

# Dans allocate() :
with self._lock:
    current_heat = sum(self._allocations.values())
    if current_heat + frac > self.max_portfolio_heat:
        frac = max(0, self.max_portfolio_heat - current_heat)
    self._allocations[pair_key] = frac

# Dans release() et current_heat property :
with self._lock:
    ...
```
Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/portfolio_engine/ -x -q
# Attendu : tous les tests portfolio passent
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659 passed, 0 failed
```
Dépend de : Aucune  
Statut : ⏳

---

### [C-06] Protéger `ExecutionRouter._pending_orders` par un Lock
Fichier : `execution_engine/router.py`  
Problème : `_pending_orders: dict[str, OrderStatus]` est lu dans `get_order_status()` et écrit dans `_paper_fill()` et `_live_fill()` sans synchronisation. Si le routeur est partagé entre threads, les accès concurrents peuvent corrompre l'état de suivi des ordres.  
Correction :
```python
# Dans __init__ :
self._orders_lock = threading.Lock()

# Protéger chaque accès à _pending_orders :
with self._orders_lock:
    self._pending_orders[order_id] = OrderStatus.FILLED
# et
with self._orders_lock:
    if order_id in self._pending_orders:
        return self._pending_orders[order_id]
```
Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/execution_engine/ -x -q 2>$null ; venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659 passed, 0 failed
```
Dépend de : Aucune  
Statut : ⏳

---

### [C-07] Volume docker-compose en lecture seule
Fichier : `docker-compose.yml`  
Problème : `./config:/app/config` est un bind-mount en lecture-écriture. En cas de compromission du container, un attaquant peut modifier `prod.yaml`.  
Correction : ajouter `:ro` sur le montage :
```yaml
volumes:
  - ./config:/app/config:ro
```
Validation :
```powershell
Select-String "config.*ro" docker-compose.yml
# Attendu : ligne trouvée avec :ro
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659 passed, 0 failed
```
Dépend de : Aucune  
Statut : ⏳

---

### [C-08] Probe active avant libération du circuit breaker (HALF_OPEN)
Fichier : `common/circuit_breaker.py`  
Problème : le circuit breaker passe de `OPEN` à `HALF_OPEN` uniquement sur l'écoulement du temps (`elapsed >= reset_timeout`), sans vérifier que la cause racine est résolue. Si TWS est encore déconnecté, le circuit ré-échoue immédiatement et accumule des tentatives inutiles.  
Correction : dans la transition `HALF_OPEN`, appeler une fonction de probe (optionnelle, injectée à l'instanciation) avant d'accepter des appels. Si la probe échoue, réinitialiser le compteur et repasser en `OPEN`.
```python
# Paramètre optionnel dans __init__ :
probe_fn: Callable[[], bool] | None = None

# Dans _can_attempt() (transition OPEN → HALF_OPEN) :
if self._probe_fn and not self._probe_fn():
    self._failure_count = 0  # reset pour re-tenter après prochain timeout
    return False
```
Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659 passed, 0 failed
```
Dépend de : Aucune  
Statut : ⏳

---

### [C-09] Ajouter un HMAC SHA-256 par ligne dans l'audit trail
Fichier : `persistence/audit_trail.py`  
Problème : le CSV est append-only sans mécanisme d'intégrité. Des lignes modifiées silencieusement (bit rot, manipulation manuelle, truncation partielle) sont chargées sans erreur par `recover_state()`.  
Correction : dans `_atomic_append()`, calculer `hmac.new(secret, row_bytes, "sha256").hexdigest()` et l'écrire dans une colonne `_hmac`. Dans `recover_state()`, vérifier chaque HMAC avant de charger la ligne ; ignorer (et logger) les lignes invalides.

La secret key peut être dérivée de `common/secrets.py` ou d'une variable d'environnement `AUDIT_HMAC_KEY`.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/persistence/ -x -q
# Attendu : tous les tests persistence passent
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659 passed, 0 failed
```
Dépend de : Aucune  
Statut : ⏳

---

### [C-10] Rotation journalière du fichier audit trail
Fichier : `persistence/audit_trail.py`  
Problème : le CSV grossit indéfiniment en production. `recover_state()` itère l'ensemble du fichier à chaque redémarrage.  
Correction : implémenter une rotation sur critère de date (ou taille max 100 Mo). Renommer `audit_trail.csv` → `audit_trail_YYYY-MM-DD.csv` en début de session. `recover_state()` ne charge que le fichier du jour courant (ou les N derniers jours configurables).  
Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/persistence/ -x -q
# Attendu : tous les tests persistence passent
```
Dépend de : C-09 (refactor cohérent du module persistence)  
Statut : ⏳

---

### [C-11] Porter le seuil de couverture CI à 70 %
Fichier : `.github/workflows/ci.yml`  
Problème : `--cov-fail-under=40` est insuffisant pour un système de trading algorithmique. Des régressions dans `live_trading/` et `execution_engine/` passent sans être détectées.  
Correction : modifier la ligne pytest dans `ci.yml` :
```yaml
# Avant :
run: pytest --cov=. --cov-fail-under=40 ...
# Après :
run: pytest --cov=. --cov-fail-under=70 ...
```
Avant d'appliquer, vérifier la couverture actuelle (`pytest --cov=. --cov-report=term-missing`) pour identifier les modules à couvrir en priorité.  
Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ --cov=. --cov-fail-under=70 -q
# Attendu : coverage >= 70%, 2659 passed
```
Dépend de : Aucune (appliquer le seuil cible progressivement si la couverture actuelle < 70 %)  
Statut : ⏳

---

### [C-12] Rendre `mypy` bloquant en CI
Fichier : `.github/workflows/ci.yml`  
Problème : `continue-on-error: true` sur l'étape mypy fait que les erreurs de type n'échouent jamais le pipeline. Des régressions de typage passent inaperçues.  
Correction :
1. Lancer `mypy risk/ risk_engine/ execution/ --ignore-missing-imports --no-error-summary` localement.
2. Corriger toutes les erreurs restantes (sans `# type: ignore` sauf cas documentés).
3. Supprimer `continue-on-error: true` du step mypy dans `ci.yml`.

Validation :
```powershell
venv\Scripts\python.exe -m mypy risk/ risk_engine/ execution/ --ignore-missing-imports --no-error-summary
# Attendu : exit 0, 0 erreurs
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659 passed, 0 failed
```
Dépend de : Aucune (mais effort variable selon volume d'erreurs mypy existantes — À ESTIMER)  
Statut : ⏳

---

### [C-13] Intégrer un scan de secrets dans le pipeline CI
Fichier : `.github/workflows/ci.yml`  
Problème : aucun outil de détection de credentials commitées (pas de trufflehog, gitleaks, CodeQL). Un `.env` commité (risque identifié en C-01) passerait inaperçu.  
Correction : ajouter une étape en tête du pipeline (avant le build) :
```yaml
- name: Secret scan (trufflehog)
  uses: trufflesecurity/trufflehog@main
  with:
    path: ./
    base: ${{ github.event.repository.default_branch }}
    head: HEAD
    extra_args: --only-verified
```
Validation :
```
# Push un fichier test contenant un pattern API key fictif sur une branche
# Attendu : le scan détecte et bloque le pipeline
```
Dépend de : C-01 (`.gitignore` doit être corrigé en premier pour éviter les faux positifs historiques)  
Statut : ⏳

---

### [C-14] Ajouter le build Docker comme étape de validation en CI
Fichier : `.github/workflows/ci.yml`  
Problème : le `Dockerfile` n'est jamais testé. Une modification cassant le build passe en code review sans être détectée.  
Correction : ajouter un step après les tests :
```yaml
- name: Validate Docker build
  run: docker build --no-cache -t edgecore:ci-${{ github.sha }} .
```
Validation :
```
# Attendu : `docker build` termine avec exit 0 sur la CI
```
Dépend de : C-02 (`.dockerignore` doit exister avant de tester le build)  
Statut : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
Bloc 1 — Sécurité immédiate (sans dépendances, aucun impact test)
  C-01 → C-02 → C-07

Bloc 2 — Thread-safety (corrections isolées, indépendantes)
  C-04 → C-05 → C-06

Bloc 3 — Robustesse IBKR
  C-03 (nécessite lecture ibkr_engine.py complète)
  C-08 (refactor circuit_breaker)

Bloc 4 — Persistance (cohérent de traiter ensemble)
  C-09 → C-10

Bloc 5 — CI/CD (appliquer dans l'ordre pour éviter les faux positifs)
  C-11 (vérifier couverture courante avant de modifier) → C-12 → C-13 → C-14
```

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert (C-01 fermé)
- [ ] pytest tests/ : 100 % pass (2659+)
- [ ] mypy risk/ risk_engine/ execution/ : exit 0
- [ ] ruff check . : 0 erreurs
- [ ] Zéro credential IBKR dans les logs
- [ ] Kill-switch persisté au redémarrage
- [ ] Risk tiers cohérents (`_assert_risk_tier_coherence OK`)
- [ ] `EDGECORE_ENV=prod` dans Dockerfile (pas "production")
- [ ] Paper trading validé avant live
- [ ] `.gitignore` protège `.env`, `data/`, `*.bak`, `*.tmp`
- [ ] `.dockerignore` exclut `.env` du contexte de build
- [ ] `_active_client_ids` protégé par Lock (C-04)

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Compléter `.gitignore` | 🔴 P0 | `.gitignore` | 15 min | ✅ | 2026-03-21 |
| C-02 | Créer `.dockerignore` | 🟠 P1 | `.dockerignore` | 15 min | ✅ | 2026-03-21 |
| C-03 | `perm_id=0` avant fill confirmation | 🟠 P1 | `execution/ibkr_engine.py` | 2-4 h | ✅ | 2026-03-21 |
| C-04 | `_active_client_ids` Lock class-level | 🟠 P1 | `execution/ibkr_engine.py` | 30 min | ✅ | 2026-03-21 |
| C-05 | `PortfolioAllocator._allocations` Lock | 🟡 P2 | `portfolio_engine/allocator.py:149` | 30 min | ✅ | 2026-03-21 |
| C-06 | `ExecutionRouter._pending_orders` Lock | 🟡 P2 | `execution_engine/router.py` | 30 min | ✅ | 2026-03-21 |
| C-07 | Volume docker-compose `:ro` | 🟡 P3 | `docker-compose.yml` | 10 min | ✅ | 2026-03-21 |
| C-08 | Circuit breaker probe active | 🟡 P3 | `common/circuit_breaker.py` | 1-2 h | ✅ | 2026-03-21 |
| C-09 | HMAC SHA-256 audit trail | 🟡 P2 | `persistence/audit_trail.py` | 2-3 h | ✅ | 2026-03-21 |
| C-10 | Rotation fichier audit trail | 🟡 P3 | `persistence/audit_trail.py` | 2-3 h | ✅ | 2026-03-21 |
| C-11 | Seuil couverture CI → 70 % | 🟡 P2 | `.github/workflows/ci.yml` | 15 min + tests | ✅ | 2026-03-21 |
| C-12 | mypy bloquant (retirer continue-on-error) | 🟡 P2 | `.github/workflows/ci.yml` | À ESTIMER | ✅ | 2026-03-21 |
| C-13 | Scan secrets CI (trufflehog) | 🟡 P2 | `.github/workflows/ci.yml` | 30 min | ✅ | 2026-03-21 |
| C-14 | Build Docker en CI | 🟡 P2 | `.github/workflows/ci.yml` | 15 min | ✅ | 2026-03-21 |
