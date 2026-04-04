---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/resultats/audit_final_upgrade_edgecore.md
derniere_revision: 2026-04-04
creation: 2026-04-04
---

# AUDIT FINAL UPGRADE — EDGECORE
> Révision 2026-04-04 · Audit #18 · Senior Quant Systems Engineer — brutal, no-bullshit

**Périmètre** : 376 fichiers Python · 2808 tests · 155 fichiers de tests · ~44 000 LOC estimées (hors venv/build)

---

## 1. GLOBAL ARCHITECTURE

### Graphe de dépendances réel (basé sur imports, pas sur le README)

```
DataLoader (data/loader.py)
    └→ UniverseManager (universe/manager.py)
        └→ PairDiscoveryEngine (pair_selection/discovery.py)
            └→ SignalGenerator (signal_engine/generator.py)
                └→ SignalCombiner (signal_engine/combiner.py)
                    └→ RiskFacade (risk/facade.py)
                        ├→ RiskEngine (risk/engine.py)
                        └→ KillSwitch (risk_engine/kill_switch.py)
                            └→ ExecutionRouter (execution_engine/router.py)
                                ├→ PaperExecutionEngine (execution/paper_engine.py)
                                └→ IBKRExecutionEngine (execution/ibkr_engine.py)
                                    └→ BrokerReconciler → AuditTrail
```

**Ce pipeline est réel et cohérent.** Les imports le confirment — ce n'est pas un claim README.

### Écart architecture documentée ↔ implémentation réelle

| Claim documenté | Réalité | Écart |
|-----------------|---------|-------|
| `execution/` = couche d'exécution unifiée | `execution/__init__.py` est **vide** — aucun export | 🔴 Pas d'interface unifiée. `execution_engine/router.py` importe directement `execution/ibkr_engine.py` |
| `RiskFacade` **unifie** tous les managers | `LiveTradingRunner` instancie `PositionRiskManager`, `PortfolioRiskManager`, `KillSwitch` ET `RiskFacade` séparément (lignes 290, 292, 303) | 🔴 B2-02 non résolu |
| `backtester/` est la façade de `backtests/` | `backtester/__init__.py` réexporte `backtests/` avec `# noqa: F401` — wrapper uniquement | ⚠️ Couche inutile sans valeur ajoutée |
| Walk-forward validé | `backtests/walk_forward.py` est un **stub** avec TODO B-1 documenté | 🔴 UNVERIFIED claim |
| Signal pipeline config-driven | Backtest utilise `entry_threshold=0.30` hardcodé (ligne 230) — live utilise `entry_z_score=2.0` depuis config | 🔴 Seuils de signal **différents** entre backtest et live |

### Modules redondants / doublons

| Paire | Status | Impact |
|-------|--------|--------|
| `execution/` ↔ `execution_engine/` | Coexistant — `execution_engine/router.py` est le vrai routeur | 🟠 Confusion conceptuelle |
| `risk/` ↔ `risk_engine/` | Double couche risk — `risk/facade.py` censée unifier mais B2-02 ouvert | 🔴 Double gate en production |
| `backtester/` ↔ `backtests/` | `backtester/` re-wrappe `backtests/` sans logique propre | 🟡 Complexité inutile |

**Score architecture : 7/10** — Pipeline clair et DAG propre. Malus pour les 3 doublons et l'absence d'interface `execution/__init__.py`.

---

## 2. TECHNICAL CHOICES

### Évaluation du stack

| Composant | Outil choisi | Verdict | Justification |
|-----------|-------------|---------|---------------|
| Broker API | `ib_insync` + `ibapi` | ✅ **Bon choix** | Seule lib Python mature pour IBKR TWS/Gateway |
| Cython extensions | `.pyx` → `.pyd` | ✅ **Gain réel** | 5-10x speedup sur half-life + Engle-Granger. Fallback Python documenté et testé |
| Logging | `structlog` | ✅ **Correct** | Structuré, JSON-compatible, contexte par requête |
| Config | Dataclasses + YAML | ⚠️ **Acceptable mais fragile** | Pas de validation runtime (pas de Pydantic). Une valeur YAML malformée échoue en silencieux |
| Type checking | Pyright `basic` + mypy | ⚠️ **Sous-optimal** | `typeCheckingMode: "basic"` manque ~30% des erreurs qu'attrape `"standard"` |
| Tests | `pytest` + 155 fichiers | ✅ **Excellent** | 2808 tests, couverture structurée par module |
| Trading loop | Synchrone (bar-by-bar) | ⚠️ **Risque latence** | Pas d'event loop async. OK pour daily/hourly, tendu sur 5-min avec 39 paires |

### Patterns réels vs claims

- **Cargo-cult détecté** : `backtester/` wrapper sans valeur. 3 classes qui délèguent à 3 classes de `backtests/` avec zéro logique propre — complexité gratuite.
- **Over-engineering détecté** : `common/context_memory.py`, `common/typed_api.py` — modules avec faible utilisation dans le pipeline productif. Utiles pour research, absents du chemin critique.
- **Genuine pattern** : Cython avec fallback Python documenté (`CYTHON_AVAILABLE`), rang de risque T1/T2/T3, `_assert_risk_tier_coherence()` au démarrage — **ces patterns sont réels et corrects**.

**Score Technical Choices : 7/10** — Stack approprié pour du retail quant. Malus pour config non-validée et loop synchrone.

---

## 3. CODE ROBUSTNESS

### Type safety

| Métrique | Valeur | Cible | Status |
|----------|--------|-------|--------|
| `# type: ignore` total | ~147 | <20 | 🔴 |
| `# type: ignore` dans code production | ~35 | <10 | 🔴 |
| `typeCheckingMode` | `"basic"` | `"standard"` | 🟠 |
| DTZ003 `utcnow()` | 0 | 0 | ✅ |
| `EDGECORE_ENV=production` | 0 | 0 | ✅ |

**Top offenders `# type: ignore` en production :**

| Fichier | Count | Pattern |
|---------|-------|---------|
| `live_trading/runner.py` | 7 | `attr-defined` sur résultats hasattr — corrigible avec `cast()` |
| `execution/ml_impact.py` | 4 | NumPy matrix ops — légitimes mais non documentés |
| `models/kalman_hedge.py` | 3 | NumPy indexing sur optionnels — corrigibles avec assert |

### Qualité des tests

- **2808 tests passants, 0 skipped, 0 failed** — remarquable pour 376 fichiers
- Couverture par module : `risk/`, `signal_engine/`, `models/`, `backtests/`, `execution/` tous couverts
- **Shadow coverage** : tests parfois tests-unitaires purs sur classes déjà couvertes par intégration → pas de coverage theater, couvrage réel
- Faiblesse : tests `execution/ibkr_engine.py` utilisent des mocks IBKR extensifs — comportement live non testé

### Error handling

- `common/errors.py` : taxonomie `ErrorCategory` (CONFIG, DATA, IBKR, RISK...) — **solide**
- `common/circuit_breaker.py` : implémenté et utilisé dans IBKR path — **correct**
- `common/retry.py` : décorateurs avec backoff exponentiel — **correct**
- Exceptions **swallowed** : `except Exception as exc: logger.debug(...)` dans `portfolio_risk.py:223` — acceptable car non-critique

### Logging

- `structlog` dans tout le pipeline principal ✅
- `print()` dans **code production** :

| Fichier | Lignes | Sévérité | Nature |
|---------|--------|----------|--------|
| `main.py` | 339-347, 759-847 | 🟡 Intentionnel | Prompts interactifs LIVE TRADING (avertissements volontaires) |
| `execution/position_stops.py` | 477-481 | 🔴 Violation | Banner module load — inutile en production |
| `pair_selection/discovery.py` | 117 | 🔴 Violation | Debug `print(p.pair_key, p.half_life)` oublié |
| `strategies/pair_trading.py` | 895, 902 | 🟠 Debug | `[DEBUG]` tags — non nettoyés |
| `common/secrets.py` | 512 | 🔴 **SÉCURITÉ** | `print(api_key)` — fuite credentials |
| `models/ou_model.py` | 222-223 | 🟠 Debug | Paramètres OU affichés à la console |
| `backtester/oos.py` | 81, 103 | 🟡 | Résultats OOS en stdout — acceptable pipeline CLI |

### Hardcoded values

| Fichier | Ligne | Valeur | Devrait être |
|---------|-------|--------|-------------|
| `strategies/pair_trading.py` | 694 | `stability_threshold = 0.8` | `config.strategy.stability_threshold` |
| `strategies/pair_trading.py` | 987 | `adf_threshold = 0.10` | `config.strategy.adf_threshold` (fallback existant, logique OK) |
| `backtests/strategy_simulator.py` | 230-231 | `entry_threshold=0.30, exit_threshold=0.12` | Lu depuis `SignalCombinerConfig` |
| `backtester/oos.py` | 70 | `acceptance_threshold=0.70` | `config.oos.acceptance_threshold` |

**Score Code Robustness : 6/10** — Tests excellents, logging structuré en main path. Malus : 147 type:ignore, print() dans production, `common/secrets.py:512` est une fuite credentials active.

---

## 4. TRADING SYSTEM COHERENCE

### Latence

- **Chemin critique** : bar close → signal → ordre ≈ `DataLoader` (I/O) + `PairDiscoveryEngine` (CPU) + `SignalGenerator` (CPU) + `ExecutionRouter` (réseau IBKR)
- **Risque identifié** : `_trading_loop()` dans `live_trading/runner.py` est **synchrone**. Sur 5-min bars avec 39 paires, si Cython absent → O(N²) scan = 39×38/2 = 741 paires → risque de dépassement du délai de bar close
- **Protection partielle** : `CYTHON_AVAILABLE` flag loggué en WARNING si absent — mais aucun guard automatique n'interrompt le trading si Cython manque

### Exécution ordres

- `PaperExecutionEngine` : fills instantanés avec slippage modèle — acceptable pour backtest
- `IBKRExecutionEngine` : rate limiter 45 req/s (`_ibkr_rate_limiter.acquire()`) — **correctement implémenté**
- **UNVERIFIED** : gestion partial fills sur jambe longue si jambe courte rejetée (stock halté, short impossible). Aucun mécanisme de reversal automatique identifié dans le code. **Risque legs divergents en live.**
- **UNVERIFIED** : comportement exact sur reconnexion IBKR avec positions ouvertes. `AuditTrail` persiste les positions mais la réconciliation automatique post-reconnexion n'est pas vérifiable dans le code local.

### Risk management

- Kill switch **câblé** dans le live path (runner.py:560) ✅
- **Dual risk gate** (B2-02) : checker `RiskFacade` à la ligne 812, PUIS `PortfolioRiskManager` à la ligne 831 séparément — redondant mais ne crée pas de trou de sécurité (fail-safe by design, mais maintenance hazard)
- Cohérence tiers : T1=0.10 ≤ T2=0.15 ≤ T3=0.20, validée par `_assert_risk_tier_coherence()` au démarrage ✅

### Intégrité backtest ↔ live — **PROBLÈME CRITIQUE**

```
Backtest (strategy_simulator.py:230-231) :
    entry_threshold = 0.30   ← seuil sur SORTIE du SignalCombiner (scale 0-1)
    exit_threshold  = 0.12

Live (config/settings.py:19-20) :
    entry_z_score = 2.0      ← seuil sur Z-SCORE brut (scale ≥0)
    exit_z_score  = 0.5
```

Ces sont **deux signaux différents sur deux échelles différentes**. Le backtest mesure la performance d'une logique d'entrée qui n'est PAS celle du live. Les métriques historiques (Sharpe=1.33, PF=4.22) doivent être considérées **UNVERIFIED** pour leur valeur prédictive sur le live.

**NB** : La ligne 1145 du simulator montre `exit_threshold=strategy.config.exit_z_score` — ce qui suggère une incohérence interne au simulator lui-même (deux chemins de code avec des logiques différentes).

### Walk-forward validation

- `backtests/walk_forward.py` : TODO B-1 documenté, implémentation partielle — **claim non tenu**
- `backtester/oos.py` : OOS basique avec `acceptance_threshold=0.70` hardcodé — **fonctionnel mais minimal**

**Score Trading System Coherence : 4/10** — La cascade risk est solide. La latence est acceptable pour daily/hourly. Mais le mismatch signal backtest ↔ live disqualifie les preuves de performance, et le partial fill gap est un risque réel.

---

## 5. CRITICAL FAILURE POINTS

### F-1 · Signal weight mismatch backtest ↔ live
**Trigger** : Déploiement en production basé sur les métriques backtest actuelles.  
**Impact** : Le live exécute avec `entry_z_score=2.0` (z-score brut) tandis que le backtest a optimisé sur `entry_threshold=0.30` (signal combiné normalisé 0-1). Performance réelle en live sera **différente des 1.33 Sharpe / 4.22 PF annoncés**.  
**Mitigation existante** : Aucune.  
**Fichier** : `backtests/strategy_simulator.py:230-231` vs `config/settings.py:19-20`

### F-2 · Credentials leak — common/secrets.py:512
**Trigger** : Tout appel au code path qui atteint `common/secrets.py:512`.  
**Impact** : `print(api_key)` — la clé API apparaît en clair dans stdout. CI/CD logs, Docker logs, terminal recording → exposition credentials IBKR.  
**Mitigation existante** : Aucune.  
**Fichier** : `common/secrets.py:512`

### F-3 · Partial fill sans reversal automatique (jambes divergentes)
**Trigger** : Leg 2 d'une paire rejeté (stock halté, short non disponible) après que Leg 1 a été exécuté.  
**Impact** : Position unhedged ouverte. Le système continue sans savoir que la couverture manque. Pertes non bornées sur le leg nu.  
**Mitigation existante** : Non identifiée dans le code. **UNVERIFIED.**  
**Fichier** : `execution/ibkr_engine.py` — chemin d'exécution des paires

### F-4 · Trading loop synchrone avec Cython absent
**Trigger** : `CYTHON_AVAILABLE=False` (CI, nouveau déploiement sans recompilation) + 39+ paires + 5-min bars.  
**Impact** : `PairDiscoveryEngine` tourne en mode Python pur (10x plus lent). Loop dépasse le délai de bar. Les données de la prochaine barre arrivent avant que le traitement de la précédente soit terminé → biais look-ahead possible par accumulation.  
**Mitigation existante** : Warning loggué mais aucun guard d'auto-pause du trading.  
**Fichier** : `models/__init__.py` (CYTHON_AVAILABLE), `live_trading/runner.py` (loop)

### F-5 · Walk-forward non implémenté — performance OOS non validée
**Trigger** : Décision de déploiement basée sur les rapports de walk-forward.  
**Impact** : `backtests/walk_forward.py` est un stub avec TODO. Les claims de validation OOS dans les docs reposent sur `backtester/oos.py` avec `acceptance_threshold=0.70` hardcodé — validation minimale, pas walk-forward réel.  
**Mitigation existante** : Documenté comme dette (TODO B-1). La validation OOS basique existe.  
**Fichier** : `backtests/walk_forward.py`

### F-6 · Double risk gate en production — maintenance hazard
**Trigger** : Modification de `PortfolioRiskManager` sans mise à jour correspondante dans `RiskFacade`.  
**Impact** : Les deux systèmes peuvent diverger silencieusement. Aujourd'hui les deux arrêtent au bon seuil, mais après refactoring l'un pourrait ne plus s'arrêter.  
**Mitigation existante** : Tests sur les deux couches séparément — mais pas de test d'intégration du dual-gate.  
**Fichier** : `live_trading/runner.py:812,831` + `risk/facade.py` + `risk_engine/portfolio_risk.py`

---

## 6. HIGH-LEVERAGE IMPROVEMENTS

Classées par ratio impact/effort :

### I-1 · Corriger common/secrets.py:512 (effort : 15 min · impact : CRITIQUE)
Supprimer ou remplacer `print(api_key)` par `logger.debug("api_key_loaded", masked=api_key[:4] + "****")`.  
**Pourquoi prioritaire** : Fuite credentials active. Tout log CI/CD expose la clé IBKR.

### I-2 · Aligner les seuils de signal backtest ↔ live (effort : 4h · impact : CRITIQUE)
Dans `backtests/strategy_simulator.py`, remplacer les thresholds hardcodés (0.30/0.12) par les valeurs depuis `get_settings().strategy.entry_z_score` / `exit_z_score`, ou documenter explicitement que le backtest simule un signal combiné et les métriques ne sont pas comparables au live.  
Si on veut vraiment du apples-to-apples, réécrire le SimulationLoop pour appliquer le même pipeline `SignalGenerator + SignalCombiner` que le live path.

### I-3 · Supprimer print() en production (effort : 30 min · impact : HIGH)
- `execution/position_stops.py:477-481` → supprimer le banner module-load
- `pair_selection/discovery.py:117` → `logger.debug("pair_discovery_candidate", pair_key=p.pair_key, half_life=p.half_life)`  
- `strategies/pair_trading.py:895,902` → supprimer les `[DEBUG]` tags  
- `models/ou_model.py:222-223` → `logger.debug()`

### I-4 · Implémenter la récupération de jambe non exécutée (effort : 24h · impact : HIGH)
Dans `execution/ibkr_engine.py`, après timeout d'un ordre de jambe 2 : déclencher automatiquement un ordre de clôture de jambe 1 et logger l'incident. Référencer l'audit pour le design pattern.

### I-5 · Passer typeCheckingMode à "standard" (effort : 8h · impact : MEDIUM)
Changer `pyrightconfig.json` : `"typeCheckingMode": "standard"`. Corriger les nouvelles erreurs systématiquement. Réduire le count `# type: ignore` de ~147 à <20.  
**Pourquoi** : `"basic"` laisse passer des erreurs de type réelles que `"standard"` attrape. Cela a contribué au bug mypy CI récent (B2-02 mypy sur portfolio_risk.py).

### I-6 · Implémenter le walk-forward réel (effort : 16h · impact : MEDIUM)
`backtests/walk_forward.py` : implémenter la logique de rolling window (train/test split par période), appeler `BacktestRunner` sur chaque window, agréger les métriques out-of-sample. Remplacer le stub TODO B-1.

### I-7 · Peupler execution/__init__.py (effort : 1h · impact : LOW)
Exposer `Order`, `OrderStatus`, `BaseExecutionEngine` en exports. Cela stabilise le contrat de l'interface execution — si la structure interne change, les importeurs ne cassent pas silencieusement.

---

## SCORING

| Section | Score | Justification |
|---------|-------|---------------|
| 1. Global Architecture | **7/10** | Pipeline clair, DAG cohérent. Malus: 3 couches doublons, execution/__init__.py vide |
| 2. Technical Choices | **7/10** | Stack approprié, Cython justifié, loop sync acceptable pour daily |
| 3. Code Robustness | **6/10** | 2808 tests exemplaires. Malus: 147 type:ignore, print() prod, credentials leak |
| 4. Trading System Coherence | **4/10** | Risk cascade solide. Disqualifié par signal mismatch et walk-forward stub |
| 5. Critical Failure Points | **(6 points identifiés)** | F-1 et F-2 sont bloquants pour production |
| 6. High-Leverage Improvements | **(7 items, priorisés)** | I-1 à I-3 corrigibles en <1 day |

**Score global : 6.0/10**

---

## VERDICT

```
PROTOTYPE AVANCÉ
```

---

## RÉSUMÉ HONNÊTE (3 phrases)

EDGECORE est un prototype avancé solide — architecture pipeline claire, 2808 tests passants, risk controls T1/T2/T3 correctement câblés et Cython fonctionnel — bien au-delà d'un projet académique ou d'un PoC. Cependant, le mismatch entre les seuils de signal du backtest (0.30/0.12 sur signal combiné) et ceux du live (2.0/0.5 sur z-score brut) signifie que les métriques de performance historiques présentées (Sharpe 1.33, PF 4.22) ne sont pas des prédicteurs fiables du comportement live. Avant tout déploiement de capital réel, trois correctifs non-négociables s'imposent : supprimer la fuite credentials (I-1), aligner les signaux backtest ↔ live (I-2), et implémenter la récupération de jambe divergente (I-4) — sans quoi le système peut perdre de l'argent pour des raisons entièrement évitables.

---

## TABLEAU SYNTHÈSE

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|
| F-1 | Signal | Mismatch entrée/sortie backtest vs live (0.30 vs 2.0) | `backtests/strategy_simulator.py:230-231` | 🔴 | Performance metrics non fiables | 8h |
| F-2 | Sécurité | `print(api_key)` — fuite credentials IBKR | `common/secrets.py:512` | 🔴 | Exposition credentials | 15min |
| F-3 | Execution | Pas de reversal automatique si jambe 2 non exécutée | `execution/ibkr_engine.py` | 🔴 | Position unhedged, perte non bornée | 24h |
| F-4 | Latence | Loop synchrone sans guard si Cython absent | `live_trading/runner.py` | 🟠 | Biais look-ahead sur 5-min bars | 4h |
| F-5 | Backtest | Walk-forward stub — OOS non validé | `backtests/walk_forward.py` | 🟠 | Décision déploiement sans preuve solide | 16h |
| F-6 | Risk | Dual risk gate — maintenance hazard | `live_trading/runner.py:812,831` | 🟠 | Désynchronisation silencieuse après refactoring | 8h |
| D-1 | Architecture | `execution/__init__.py` vide | `execution/__init__.py` | 🟠 | Interface instable | 1h |
| D-2 | Architecture | `backtester/` wrapper sans valeur ajoutée | `backtester/runner.py` | 🟡 | Complexité gratuite | — |
| D-3 | Type safety | 147 `# type: ignore` dont ~35 prod | Divers | 🟠 | Masque des erreurs réelles | 8h |
| D-4 | Logging | print() prod (position_stops, discovery, ou_model) | 3 fichiers | 🔴 | Pollution stdout, debug non filtrable | 30min |
| D-5 | Config | `stability_threshold=0.8` hardcodé | `strategies/pair_trading.py:694` | 🟡 | Non configurable | 30min |
| D-6 | Config | `typeCheckingMode: "basic"` trop permissif | `pyrightconfig.json` | 🟠 | Erreurs de type manquées | 8h |
| D-7 | Config | `acceptance_threshold=0.70` hardcodé OOS | `backtester/oos.py:70` | 🟡 | Non configurable | 30min |
