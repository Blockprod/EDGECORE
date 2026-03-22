# Architecture Decision Records — EDGECORE

---

## ADR-001 : Séparation modules publics / internes

**Date** : 2026-02  
**Statut** : Actif

### Contexte
Le projet dispose de deux couches d'exécution : `execution/` (24 fichiers, logique broker réelle) et `execution_engine/` (1 fichier, routeur d'entrée). Idem pour `risk/` vs `risk_engine/`, et `backtests/` vs `backtester/`.

### Décision
- **`execution/`** = couche interne, implémentations concrètes (`IBKRExecutionEngine`, `PaperExecutionEngine`, stops, slippage, reconciler)
- **`execution_engine/`** = façade publique, unique point d'entrée (`ExecutionRouter`)
- **`risk/`** = moteur mathématique (`RiskEngine`, `RiskFacade`, Kelly, VaR, beta-neutral, factor)
- **`risk_engine/`** = contrôles opérationnels (`PositionRiskManager`, `PortfolioRiskManager`, `KillSwitch`)
- **`backtests/`** = moteur de backtest (stratégie simulateur, metrics, cost model)
- **`backtester/`** = façades haut niveau (`BacktestEngine`, `WalkForwardEngine`, `OOSValidationEngine`)

### Conséquences
- Les modules de production (`live_trading/`, `signal_engine/`) n'importent que les façades publiques
- Le testeur peut mocker `ExecutionRouter` sans toucher IBKR
- **Dette actuelle** : `live_trading/runner.py` contourne `RiskFacade` et instancie les 3 risk managers séparément (B2-02)

---

## ADR-002 : Triple-gate de coïntégration (EG + Johansen + Newey-West HAC)

**Date** : Sprint 4.1 / 4.3  
**Statut** : Actif

### Contexte
L'Engle-Granger (EG) seul génère trop de faux positifs sur données financières (multiple testing, hétéroscédasticité).

### Décision
Trois tests requis pour qu'une paire soit acceptée :
1. **Engle-Granger** avec correction Bonferroni : `significance_level / n_pairs`
2. **Johansen** (test de rang) : confirmation de la direction de cointégration
3. **Newey-West HAC** : consensus OLS + HAC sur les résidus

Activé via `StrategyConfig` :
```python
bonferroni_correction:  bool = True
johansen_confirmation:  bool = True
newey_west_consensus:   bool = True
significance_level:     float = 0.05
```

### Conséquences
- Moins de paires mais de meilleure qualité
- Backtests plus conservatifs, drawdowns réduits
- Plus lent (3 tests vs 1) → justifie le cache par régime de volatilité (`cache_ttl_high_vol=2h`, `normal=12h`, `low=24h`)

---

## ADR-003 : Kalman vs hedge ratio fixe (OLS)

**Date** : Sprint 2.2  
**Statut** : Actif

### Contexte
Le hedge ratio β entre deux actifs change avec le temps. OLS fixe sur lookback_window crée un "stale hedge" qui génère des faux signaux quand β dérive.

### Décision
Option par configuration (`use_kalman: bool = True`) :
- **Kalman ON** (prod default) : hedge ratio mis à jour barre par barre via `models/kalman_hedge.py`. Réduit le slippage lié au β-drift.
- **Kalman OFF** : OLS sur lookback window, plus simple, utilisé en backtests rapides.

Réévaluation forcée si spread vol > `emergency_vol_threshold_sigma=3.0σ`.  
Réévaluation périodique : `hedge_ratio_reestimation_days=7`.

### Conséquences
- Kalman nécessite stabilisation initiale (≥30 barres)
- `models/hedge_ratio_tracker.py` maintient l'état Kalman par paire
- Tests de cohérence dans `tests/models/` vérifient que Kalman et OLS convergent sur long terme

---

## ADR-004 : Z-score adaptatif (AdaptiveThresholdEngine)

**Date** : Sprint 3.4 / signal_engine/adaptive.py  
**Statut** : Actif

### Contexte
Des seuils de z-score fixes (e.g. ±2.0 d'entrée, 0.5 de sortie) sur-tradent en régimes de forte volatilité et sous-tradent en régimes calmes.

### Décision
`AdaptiveThresholdEngine` ajuste dynamiquement les seuils selon le régime de volatilité courant :
- `base_entry` : alloué depuis `get_settings().strategy.entry_z_score`
- `base_exit`  : alloué depuis `get_settings().strategy.exit_z_score`
- `max_entry`  : `z_score_stop = 3.5` (stop-loss z-score)
- En HIGH vol : seuils resserrés → moins d'entrées excessives
- En LOW vol  : seuils détendus → capture les petites réversions

Combiné avec `SignalCombiner` :
```
composite_score = zscore × 0.70 + momentum × 0.30
entrée si composite ≥ 0.6
sortie  si composite ≤ 0.2
```

### Conséquences
- `SignalCombinerConfig` centralise les poids dans `get_settings().signal_combiner`
- Tout changement de weights nécessite re-validation complète backtest

---

## ADR-005 : Kill-switch 6 conditions

**Date** : Structure initiale  
**Statut** : Actif — NE PAS MODIFIER sans audit complet

### Contexte
Besoin d'un mécanisme d'arrêt d'urgence qui ne dépend d'aucune logique de stratégie.

### Décision
`risk_engine/kill_switch.py` monitore 6 conditions indépendantes :

| Condition | Seuil | Source |
|-----------|-------|--------|
| Drawdown portfolio | > 15% | `KillSwitchConfig.max_drawdown_pct` |
| Perte journalière | > 3% | `KillSwitchConfig.max_daily_loss_pct` |
| Pertes consécutives | > 5 | `KillSwitchConfig.max_consecutive_losses` |
| Volatilité extrême | > 3σ historical mean | `KillSwitchConfig.extreme_vol_multiplier` |
| Stale data | > 300s sans données fraîches | `KillSwitchConfig.max_data_stale_seconds` |
| Activation manuelle | via `activate(reason)` | opérateur |

Une fois activé : flag global `is_active=True`, reset manuel requis.  
**Intégré dans** `RiskFacade.can_enter_trade()` → vérifié en premier.  
**Également vérifié** directement dans `LiveTradingRunner._tick()` (B2-02 : duplication à corriger).

### Conséquences
- `risk/facade.py` doit toujours déléguer `kill_switch.is_active` à `risk_engine/kill_switch.py`
- Toute nouvelle condition d'arrêt → ajouter dans `KillReason` enum de `kill_switch.py`, puis adapter `facade.py`

---

## ADR-006 : Migration C++ → Cython (abandon pybind11/CMake)

**Date** : Février 2026  
**Statut** : Actif (C++ abandonné)

### Contexte
Premier design utilisait C++17/pybind11/Eigen3/OpenMP pour accélérer les calculs de coïntégration et backtest. Complexité de build élevée (CMakeLists.txt de 150 lignes, dépendances Eigen3/OpenMP non portables sous Windows).

### Décision
Migration vers **Cython** pour `models/cointegration_fast.pyx` :
- Build simple : `python setup.py build_ext --inplace`
- Deux cibles : `.cp311-win_amd64.pyd` (venv) et `.cp313-win_amd64.pyd` (system)
- Pas de dépendance C++/Eigen3/pybind11
- `edgecore/` contient les anciens wrappers C++ (désormais vides)

### Fichiers residuels à supprimer
- `CMakeLists.txt` → déplacer vers `docs/archived/`
- `build/` → supprimer entièrement
- `cpp/` → déplacer vers `docs/archived/cpp_sources/`
- `edgecore/` → garder uniquement pour les tests legacy (1 test dépend encore des wrappers)

### Conséquences
- `setup.py` est le **seul** mécanisme de build Cython — ne pas le supprimer
- `pyproject.toml` définit les métadonnées du package, pas la compilation Cython
- `CMakeLists.txt` n'est plus exécuté mais peut rester pour historique

---

## ADR-007 : Docker single-process (sans orchestration interne)

**Date** : Février 2026  
**Statut** : Actif avec bug connu

### Contexte
Déploiement via `docker-compose.yml` avec 6 services : trading-engine, redis, prometheus, grafana, elasticsearch, kibana.

### Décision
- Image **multi-stage** : `python:3.11.9-slim AS builder` + runtime stage
- Utilisateur non-root `appuser` (UID 1000)
- Health check `curl -f http://localhost:5000/health`
- Secrets via variables d'environnement (jamais baked dans l'image)

### Bug B5-01 — ✅ CORRIGÉ (2026-03-20)
```dockerfile
# Dockerfile:37
ENV EDGECORE_ENV=prod
```
```yaml
# docker-compose.yml:11
EDGECORE_ENV: prod
```

**Vérification** : `Dockerfile:37` → `EDGECORE_ENV=prod` ✅ — `docker-compose.yml:11` → `EDGECORE_ENV: prod` ✅

---

## ADR-008 : Singleton get_settings() — injection vs global

**Date** : Design initial  
**Statut** : Actif (dette reconnue)

### Décision prise
`Settings` implémente le pattern singleton via `__new__`. Tous les modules lisent `get_settings()` directement.

### Impact
- **Pro** : simplicité, pas de propagation du contexte partout
- **Con** : impossible de faire tourner deux stratégies avec paramètres différents dans le même process ; tests doivent monkey-patcher le singleton

### Évolution envisagée
Injection de dépendance explicite dans les constructeurs des managers (passer `settings` à `PairDiscoveryEngine.__init__`, etc.). Non implémenté — complexité jugée prématurée à ce stade.
