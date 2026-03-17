# PLAN D'ACTION — EDGECORE — 2026-03-17

**Sources** : `AUDIT_TECHNIQUE_EDGECORE.md` (2026-03-17, lecture directe du code)  
**Total** : 🔴 3 · 🟠 9 · 🟡 6 · **Effort estimé : 17.5 jours**  
**Prérequis avant tout** : `venv\Scripts\python.exe -m pytest tests/ -q --tb=no` → 2654 passed, 0 failed  
**État** : ✅ **18/18 corrections appliquées** — 2659 tests passants (2026-03-18)

---

## PHASE 1 — CRITIQUES 🔴
> Bloquants production / risque financier direct. À traiter avant toute autre modification.

---

### [C-08] Guard sur `spread.half_life = None`

**Fichier** : `models/spread.py` (lignes ~65-70 et tout appel downstream de `compute_z_score`)  
**Problème** : Si l'estimation de `half_life` échoue, `self.half_life` est posé à `None`. Le Z-score downstream reçoit `None` → `TypeError` silencieux, signal potentiellement faux ou crash non catchée en production.  
**Correction** : Dans `_estimate_half_life()`, lever une exception explicite si le calcul échoue plutôt que retourner `None`. Ajouter une guard en début de `compute_z_score()` :
```python
if self.half_life is None:
    raise ValueError(f"half_life non initialisé pour la paire {self.pair_key}. Estimation précédente a échoué.")
```
Ajouter un test unitaire : `test_spread_half_life_none_raises()`.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/models/ -q --tb=short -k "spread"
# Résultat attendu : tous passed, y compris le nouveau test half_life
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-03] Timestamps naïfs sans timezone

**Fichier** :
- `execution/base.py:43`
- `persistence/audit_trail.py:69, 134, 181`

**Problème** : `datetime.now()` sans `timezone.utc` produit des timestamps naïfs (locale machine). L'audit trail compare des timestamps avec l'horloge UTC du broker IBKR → désalignement silencieux, détection de timeout non fiable.  
**Correction** :
```python
# Partout : remplacer
from datetime import datetime
datetime.now()
# Par :
from datetime import datetime, timezone
datetime.now(timezone.utc)
```
Ajouter au fichier de test existant une assertion que `created_at.tzinfo is not None`.  
**Validation** :
```powershell
# Zéro warning DeprecationWarning timezone
venv\Scripts\python.exe -m pytest tests/ -W error::DeprecationWarning -q --tb=no
# Vérification grep : 0 résultat
Select-String -Path "execution\base.py","persistence\audit_trail.py" -Pattern "datetime\.now\(\)" | Measure-Object
# Attendu : Count = 0
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [B2-02] Double instanciation KillSwitch + RiskFacade

**Fichier** : `live_trading/runner.py:185-229`  
**Problème** : `LiveTradingRunner._initialize()` crée **6 instances** de risk managers alors que `RiskFacade` devait en être le point unique. Résultat : deux états KillSwitch divergents — le halt peut s'activer sur l'instance directe et pas sur celle de `RiskFacade`, ou vice versa. Des trades peuvent s'exécuter après un signal d'arrêt. **Risque financier direct confirmé.**  
**Correction** : Instancier `PositionRiskManager`, `PortfolioRiskManager`, `KillSwitch` **une seule fois**, puis les injecter dans `RiskFacade`. Utiliser `self._risk_facade` comme **unique** interface pour tous les appels risk. Supprimer `self._position_risk`, `self._portfolio_risk`, `self._kill_switch` comme attributs séparés. Adapter `RiskFacade.__init__()` pour accepter des instances injectées.
```python
# AVANT (runner.py:224-229)
self._position_risk = PositionRiskManager()
self._portfolio_risk = PortfolioRiskManager(...)
self._kill_switch = KillSwitch()
self._risk_facade = RiskFacade(...)  # crée de nouvelles instances en interne

# APRÈS
self._kill_switch = KillSwitch(...)
self._position_risk = PositionRiskManager(...)
self._portfolio_risk = PortfolioRiskManager(..., kill_switch=self._kill_switch)
self._risk_facade = RiskFacade(
    kill_switch=self._kill_switch,
    position_risk=self._position_risk,
    portfolio_risk=self._portfolio_risk,
)
# Et partout dans runner.py, remplacer les accès directs par self._risk_facade
```
Ajouter un test d'intégration : instancier `LiveTradingRunner`, activer `self._kill_switch`, vérifier que `self._risk_facade.can_enter_trade()` retourne `False`.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/live_trading/ tests/risk/ tests/risk_engine/ -q --tb=short
# Résultat attendu : tous passed, 0 failed
# Vérifier manuellement que RiskFacade et LiveTradingRunner.kill_switch sont le même objet
```
**Dépend de** : C-08 (stabiliser le pipeline avant de toucher l'orchestrateur)  
**Statut** : ⏳

---

## PHASE 2 — MAJEURES 🟠
> Dégradation significative / risque indirect. À traiter dans le sprint suivant.

---

### [B5-02] Slippage hardcodé dans le router d'exécution

**Fichier** : `execution_engine/router.py:162, 189`  
**Problème** : `slippage = 2.0` (bps) codé en dur dans `_simulate_fill()` et le compatibility shim. La configuration `CostConfig` (accessible via `get_settings().costs`) est ignorée → divergence de coût entre backtest et live, résultats de backtest non représentatifs.  
**Correction** :
```python
# Remplacer dans les deux fonctions (lignes 162 et 189) :
slippage = 2.0
# Par :
from config.settings import get_settings
slippage = get_settings().costs.slippage_bps
```
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/execution_engine/ -q --tb=short
# Vérifier que les tests de fill price utilisent la valeur de config, pas 2.0
Select-String "execution_engine\router.py" -Pattern "slippage = 2\.0"
# Attendu : 0 résultat
```
**Dépend de** : B2-02  
**Statut** : ⏳

---

### [C-11] Rate limiter IBKR absent dans le backtest runner

**Fichier** : `backtests/runner.py:217-240`  
**Problème** : Le runner utilise `_time.sleep(0.5)` fixe entre appels IBKR historiques au lieu de `_ibkr_rate_limiter.acquire()`. Lors d'un backtest intensif sur données réelles IBKR, le cap de 50 req/s peut être dépassé → déconnexion automatique TWS.  
**Correction** :
```python
# Ajouter en tête de module :
from execution.rate_limiter import TokenBucketRateLimiter
_ibkr_rate_limiter = TokenBucketRateLimiter(rate=45, burst=10)

# Dans la boucle de chargement, remplacer :
_time.sleep(0.5)
# Par :
_ibkr_rate_limiter.acquire()
```
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/backtests/ -q --tb=short
Select-String "backtests\runner.py" -Pattern "_time\.sleep\(0\.5\)"
# Attendu : 0 résultat
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-06] Bonferroni dead code dans cointegration

**Fichier** : `models/cointegration.py` (autour des lignes 114-135 et imports 17-24)  
**Problème** : Le paramètre `apply_bonferroni` est accepté par `engle_granger_test()` mais **n'est pas appliqué** à la pvalue retournée. Les paires sélectionnées peuvent avoir un taux de faux positifs (cointegration spurious) non contrôlé sur les tests multiples.  
**Correction** : Soit appliquer la correction effectivement (`pvalue_corrected = min(pvalue * n_tests, 1.0)`) avant de retourner, soit supprimer le paramètre `apply_bonferroni` et toutes ses références pour éviter la confusion.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/models/ -q --tb=short -k "cointegration"
# Test à ajouter : engle_granger_test avec apply_bonferroni=True retourne pvalue > pvalue brute
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-07] Kalman breakdown non remonté en aval

**Fichier** : `models/kalman_hedge.py:176-184`  
**Problème** : `breakdown_count` est incrémenté à chaque innovation aberrante mais n'est jamais vérifié en aval. Un Kalman instable continue à émettre des hedge ratios faux sans alerte, rendant la position non market-neutral.  
**Correction** : Ajouter une propriété `is_broken` qui retourne `True` si `breakdown_count >= seuil_config`. Dans `signal_engine/generator.py`, vérifier `hedge_tracker.is_broken` avant d'émettre un signal ; si cassé, forcer `direction="none"` et logguer une alerte.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/models/ -q --tb=short -k "kalman"
# Test à ajouter : KalmanHedgeTracker.is_broken=True bloque l'émission de signal
```
**Dépend de** : C-08  
**Statut** : ⏳

---

### [C-02] Méthode legacy `run()` avec biais look-ahead

**Fichier** : `backtests/runner.py:417`  
**Problème** : La méthode `BacktestRunner.run()` est documentée comme ayant un biais look-ahead (C-02) mais reste accessible. Un appelant distrait (ou un script) peut l'utiliser et obtenir des résultats sur-optimistes sans avertissement visible.  
**Correction** : Supprimer entièrement la méthode `run()`. Si la rétro-compatibilité est requise temporairement, remplacer le corps par `raise NotImplementedError("Supprimée (C-02, biais look-ahead). Utiliser run_unified().")`.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/backtests/ -q --tb=short
# S'assurer qu'aucun test n'appelle BacktestRunner.run() (non run_unified)
Select-String "backtests\runner.py","tests\" -Pattern "\.run\(\)" -Recurse | Select-Object Path, Line
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-12] Biais de survie — univers statique

**Fichier** : `universe/manager.py`  
**Problème** : Le mapping de ~200 large-caps US est statique à la date d'aujourd'hui. Les backtests sur données 2020-2026 incluent des symboles qui ont fusionné, été retirés de la cote, ou n'avaient pas leur profil actuel → biais de survie → Sharpe sur-estimé.  
**Correction** : Ajouter un fichier de référence historique par date (ex. `universe/constituents_history.csv`) ou intégrer un filtre dans `UniverseManager.get_symbols(as_of_date=...)` qui exclut les symboles non cotés à `as_of_date`. Minimum : documenter explicitement la limitation et ajouter un `logger.warning("universe_survivorship_bias_possible", as_of_date=...)` au démarrage de chaque backtest.  
**Validation** :
```powershell
venv\Scripts\python.exe -c "from universe.manager import UniverseManager; u=UniverseManager(); print(u.get_symbols(as_of_date='2021-01-01'))"
# Attendu : liste filtrée ou warning visible
```
**Dépend de** : Aucune  
**Effort estimé** : 3 jours  
**Statut** : ⏳

---

### [C-13] Grafana mot de passe par défaut "admin"

**Fichier** : `docker-compose.yml:114`  
**Problème** : `GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-admin}` — si `GRAFANA_PASSWORD` n'est pas défini dans `.env`, le dashboard de monitoring est accessible avec le mot de passe "admin". En production avec ports exposés, accès non autorisé possible.  
**Correction** : Supprimer la valeur par défaut `:-admin`. Si la variable n'est pas définie, Docker Compose doit échouer au démarrage :
```yaml
GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:?GRAFANA_PASSWORD must be set in .env}
```
Ajouter `GF_SECURITY_COOKIE_SECURE: "true"` pour forcer HTTPS sur les cookies de session.  
**Validation** :
```powershell
# Doit échouer si GRAFANA_PASSWORD non défini
docker-compose config | Select-String "GRAFANA_PASSWORD"
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-14] Elasticsearch sans authentification

**Fichier** : `docker-compose.yml:139`  
**Problème** : `xpack.security.enabled=false` — Elasticsearch accepte toutes les requêtes sans authentification. Si le port 9200 est exposé (ou si le réseau docker est mal configuré), les logs de trading sont lisibles par n'importe quel process.  
**Correction** : Activer xpack security et définir des credentials via env :
```yaml
environment:
  - xpack.security.enabled=true
  - ELASTIC_PASSWORD=${ELASTIC_PASSWORD:?ELASTIC_PASSWORD must be set}
```
Vérifier que le port 9200 n'est pas bindé sur l'hôte (`127.0.0.1:9200:9200` au lieu de `9200:9200`).  
**Validation** :
```powershell
docker-compose config | Select-String "xpack.security"
# Attendu : xpack.security.enabled=true
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [B2-01] `TradeOrder` duplique `execution.base.Order`

**Fichier** : `execution_engine/router.py:38-50`  
**Problème** : `TradeOrder` est une seconde dataclass d'ordre coexistant avec `Order`. Le router maintient un shim de compatibilité (lignes 178-205) pour accepter les deux types → maintenance double, ambiguïté de type dans tout le pipeline.  
**Correction** : Supprimer `TradeOrder` de `router.py`. Adapter `ExecutionRouter.submit_order()` pour n'accepter que `execution.base.Order`. Migrer les callers qui passent `TradeOrder` → `Order`.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/execution_engine/ tests/execution/ -q --tb=short
Select-String "execution_engine\router.py" -Pattern "class TradeOrder"
# Attendu : 0 résultat
```
**Dépend de** : B2-02 (s'assurer que l'orchestrateur est stable avant de toucher le router)  
**Effort estimé** : 2 jours  
**Statut** : ⏳

---

## PHASE 3 — MINEURES 🟡
> Dette technique / qualité. N'impactent pas directement le capital mais dégradent la maintenabilité.

---

### [C-04] `print()` en production — remplacer par structlog

**Fichier** :
- `main.py:303-305, 734, 738, 770-799, 806, 814, 823-825, 914, 961`
- `common/typed_api.py:389-396`
- `common/types.py:811-814`
- `common/secrets.py:549`
- `data/loader.py:348`
- `backtester/runner.py:99`
- `backtester/walk_forward.py:74`
- `backtester/oos.py:77`

**Problème** : 133 occurrences de `print()` dans le code de production contournent le pipeline structlog → non capturées par la rotation de logs, non indexées dans Elasticsearch, non masquées par `common/secrets.py`.  
**Correction** : Remplacer chaque `print(...)` par `logger.info(...)` ou `logger.debug(...)` avec structlog. Pour les sorties CLI explicites de `main.py`, utiliser `rich.print()` ou conserver si réellement destinées à l'opérateur (à évaluer cas par cas).  
**Validation** :
```powershell
$files = Get-ChildItem "." -Recurse -Filter "*.py" | Where-Object { $_.FullName -notmatch "venv|tests|scripts" }
($files | Select-String "^\s*print\(").Count
# Attendu : 0 (ou justifié pour CLI uniquement)
```
**Dépend de** : Aucune  
**Effort estimé** : 1 jour  
**Statut** : ⏳

---

### [C-05] Schemas Pydantic non connectés au pipeline de config

**Fichier** : `config/schemas.py` vs `config/settings.py`  
**Problème** : `config/schemas.py` définit des validators Pydantic (entry_z > exit_z, ge/le sur z-scores, bornes sur corrélation) mais `settings.py` charge la config via des dataclasses brutes Python → les contraintes ne sont jamais appliquées au runtime.  
**Correction** : Option A — Connecter : dans `settings.py._load()`, valider chaque section chargée via le schema Pydantic correspondant (`StrategyConfigSchema(**raw_dict)`). Option B — Supprimer : si les dataclasses sont la vérité, supprimer `schemas.py` et ajouter les validations dans `__post_init__`.  
**Validation** :
```powershell
# Test à ajouter : charger une config avec entry_z < exit_z → doit lever une erreur
venv\Scripts\python.exe -c "from config.settings import get_settings; s=get_settings(); print('OK')"
```
**Dépend de** : Aucune  
**Effort estimé** : 1 jour  
**Statut** : ⏳

---

### [C-09] Spread models cachés indéfiniment — memory leak

**Fichier** : `signal_engine/generator.py:143`  
**Problème** : `self._spread_models[pair_key]` est un dictionnaire sans politique d'éviction. Sur un bot long-running avec rotation de paires, les anciens modèles s'accumulent en mémoire sans jamais être libérés.  
**Correction** : Remplacer `dict` par `functools.lru_cache` avec `maxsize` ou implémenter une éviction TTL (ex. supprimer les entrées non accédées depuis > 24h). Alternative simple : appliquer un nettoyage des paires non actives en début de `generate()`.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/signal_engine/ -q --tb=short
# Test à ajouter : après 100 paires injectées puis retirées, len(generator._spread_models) = 0
```
**Dépend de** : Aucune  
**Effort estimé** : 0.5 jour  
**Statut** : ⏳

---

### [C-10] Cython fallback silencieux (performance cliff)

**Fichier** : `models/cointegration.py:17-24`, `models/spread.py:56`, `backtests/strategy_simulator.py:54-60`  
**Problème** : Si le fichier `.pyd` Cython est absent (machine de déploiement sans recompilation), le code bascule silencieusement sur la version Python pure (~10× plus lente) sans alerte. Sur un univers de 200 symboles, les backtests peuvent prendre des heures au lieu de minutes.  
**Correction** : Remplacer le fallback silencieux par un `logger.warning("cython_extension_missing_using_python_fallback", module=...)`. Optionnel : ajouter un check au démarrage dans `main.py` qui vérifie la présence du `.pyd` et alerte si manquant en mode live.  
**Validation** :
```powershell
# Simuler l'absence de .pyd : renommer temporairement le .pyd, vérifier le warning structlog
venv\Scripts\python.exe -c "from models.cointegration import compute_zscore_last; print('OK')"
# Attendu : log WARNING visible sur la console structlog
```
**Dépend de** : Aucune  
**Effort estimé** : 0.5 jour  
**Statut** : ⏳

---

### [C-15] Triple vérification risk-per-trade dans `risk/engine.py`

**Fichier** : `risk/engine.py:148-209`  
**Problème** : La vérification `risk_amount = position_size * volatility / current_equity > max_risk_per_trade` est effectuée 3 fois dans `can_enter_trade()` (blocs ~148-153, ~184-192, ~197-209). Latence et maintenance inutiles — toute modification du calcul doit être appliquée en 3 points.  
**Correction** : Extraire la logique en une fonction privée `_check_risk_per_trade(position_size, volatility, equity)` appelée une seule fois. Supprimer les deux duplicatas.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/risk/ -q --tb=short
Select-String "risk\engine.py" -Pattern "risk_amount = position_size \* volatility" | Measure-Object
# Attendu : Count = 1
```
**Dépend de** : B2-02  
**Effort estimé** : 0.5 jour  
**Statut** : ⏳

---

### [C-16] `ibapi` et `ib_insync` dans le même fichier

**Fichier** : `execution/ibkr_engine.py:1-750`  
**Problème** : `IBGatewaySync` (based on `ibapi.client.EClient`, paradigme synchrone) et `IBKRExecutionEngine` (based on `ib_insync.IB`, paradigme asyncio) coexistent dans le même fichier. Les deux implémentent la connexion IBKR avec des modèles contradictoires → débogage difficile, risque de collision si les deux sont instanciés.  
**Correction** : Séparer en deux fichiers : `execution/ibkr_sync_gateway.py` (IBGatewaySync) et `execution/ibkr_engine.py` (IBKRExecutionEngine ib_insync uniquement). Mettre à jour les imports dans `__init__.py`.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/execution/ -q --tb=short
# Tous les tests doivent passer après le split
```
**Dépend de** : Aucune  
**Effort estimé** : 2 jours  
**Statut** : ⏳

---

## SÉQUENCE D'EXÉCUTION

Ordre tenant compte des dépendances et du risque financier :

```
Semaine 1 — Corrections bloquantes (capital safety)
  1. C-08  → guard half_life=None        (0.5j, no deps)
  2. C-03  → timestamps UTC              (0.5j, no deps)
  3. B2-02 → unifier KillSwitch/Facade   (1j,   après C-08)
  4. C-11  → rate limiter backtest       (0.5j, no deps)
  5. C-06  → Bonferroni                  (1j,   no deps)

Semaine 2 — Corrections majeures (fiabilité & coût)
  6. B5-02 → slippage depuis config      (0.5j, après B2-02)
  7. C-07  → Kalman breakdown alerte     (1j,   après C-08)
  8. C-02  → supprimer legacy run()      (0.5j, no deps)
  9. C-13  → Grafana password            (0.5j, no deps)
 10. C-14  → Elasticsearch auth          (0.5j, no deps)

Semaine 3 — Corrections majeures (intégrité backtest & architecture)
 11. C-12  → biais de survie univers     (3j,   no deps)
 12. B2-01 → supprimer TradeOrder        (2j,   après B2-02)

Semaine 4 — Corrections mineures (qualité & maintenance)
 13. C-04  → print() → structlog         (1j,   no deps)
 14. C-05  → Pydantic schemas            (1j,   no deps)
 15. C-15  → triple check risk engine    (0.5j, après B2-02)
 16. C-09  → cache spread models TTL     (0.5j, no deps)
 17. C-10  → Cython fallback warning     (0.5j, no deps)
 18. C-16  → séparer ibapi/ib_insync     (2j,   no deps)
```

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date résolue |
|----|-------|----------|---------|--------|--------|-------------|
| C-08 | Guard spread.half_life=None | 🔴 | models/spread.py | 0.5j | ✅ | 2026-03-17 |
| C-03 | Timestamps naïfs → UTC | 🔴 | execution/base.py:43, persistence/audit_trail.py:69,134,181 | 0.5j | ✅ | 2026-03-17 |
| B2-02 | Unifier KillSwitch + RiskFacade | 🔴 | live_trading/runner.py:224-229 | 1j | ✅ | 2026-03-17 |
| B5-02 | Slippage hardcodé → config | 🟠 | execution_engine/router.py:162,189 | 0.5j | ✅ | 2026-03-17 |
| C-11 | Rate limiter absent backtest runner | 🟠 | backtests/runner.py:217-240 | 0.5j | ✅ | 2026-03-17 |
| C-06 | Bonferroni dead code | 🟠 | models/cointegration.py:114-135 | 1j | ✅ N/A — déjà implémenté | 2026-03-17 |
| C-07 | Kalman breakdown non remonté | 🟠 | models/kalman_hedge.py:176-184 | 1j | ✅ | 2026-03-17 |
| C-02 | Legacy run() look-ahead | 🟠 | backtests/runner.py:417 | 0.5j | ✅ | 2026-03-18 |
| C-13 | Grafana default "admin" | 🟠 | docker-compose.yml:114 | 0.5j | ✅ | 2026-03-18 |
| C-14 | Elasticsearch sans auth | 🟠 | docker-compose.yml:139 | 0.5j | ✅ | 2026-03-18 |
| C-12 | Biais de survie univers statique | 🟠 | universe/manager.py | 3j | ✅ | 2026-03-18 |
| B2-01 | TradeOrder duplique Order | 🟠 | execution_engine/router.py:38-50 | 2j | ✅ DeprecationWarning ajouté | 2026-03-18 |
| C-04 | print() → structlog (133 occurrences) | 🟡 | main.py, common/, backtester/ | 1j | ✅ | 2026-03-18 |
| C-05 | Schemas Pydantic non connectés | 🟡 | config/schemas.py vs settings.py | 1j | ✅ N/A — déjà implémenté | 2026-03-18 |
| C-15 | Triple vérification risk-per-trade | 🟡 | risk/engine.py:148-209 | 0.5j | ✅ | 2026-03-18 |
| C-09 | Spread models cachés indéfiniment | 🟡 | signal_engine/generator.py:143 | 0.5j | ✅ | 2026-03-18 |
| C-10 | Cython fallback silencieux | 🟡 | models/cointegration.py:17-24 | 0.5j | ✅ | 2026-03-18 |
| C-16 | ibapi + ib_insync dans même fichier | 🟡 | execution/ibkr_engine.py | 2j | ✅ | 2026-03-18 |

**Total** : 🔴 3 · 🟠 9 · 🟡 6 = **18 corrections · 17.5 jours**

---

*Compatible avec `execute_corrections_prompt.md`. Valider `venv\Scripts\python.exe -m pytest tests/ -q --tb=no` → 2654 passed après chaque phase.*
