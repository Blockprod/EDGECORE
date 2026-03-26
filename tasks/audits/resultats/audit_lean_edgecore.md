---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_lean_edgecore.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

# AUDIT LEAN — CARTOGRAPHIE EDGECORE
**Date** : 2026-03-26  
**Objectif** : Cartographier l'existant avant P2/P3/P4 pour éviter duplication.

---

## BLOC 1 — FEATURE STORE (CACHE)

### 1.1 Cache existant

**PARTIAL**

Trois mécanismes de cache coexistent, tous spécialisés et non génériques :

| Mécanisme | Fichier:Ligne | Format | Scope |
|---|---|---|---|
| Paires cointégrées | `pair_selection/discovery.py:381` | JSON (`discovered_pairs.json`) | Résultats sélection paires |
| Barres intraday | `data/intraday_loader.py:105` | Parquet (`data/cache/intraday/{symbol}.parquet`) | Barres 5min par symbole |
| Seuils ML | `models/ml_threshold_optimizer.py:668` | Dict mémoire (`thresholds_cache: dict`) | Seuils ML par paire, volatil |

Aucun Feature Store générique pour les calculs stat-arb (spread, hedge ratio, z-score).

### 1.2 Versioning

**NONE**

- `pair_selection/discovery.py:388-391` : invalidation par âge TTL uniquement (`cache_ttl_hours: int = 12`) — pas de hash de paramètres, pas de version.
- `data/intraday_loader.py:104-109` : invalidation par plage de dates (`start_date`, `end_date`) — pas de versioning ni de checksum.
- `models/ml_threshold_optimizer.py:752-776` : cache mémoire in-process, aucune persistance entre sessions.

Aucun des trois mécanismes n'est basé sur un hash des paramètres d'entrée.

### 1.3 Reproductibilité

**PARTIAL**

- `pair_selection/discovery.py:179-181` : pattern check→compute→write présent — même entrée + TTL valide = même sortie. ✅
- `data/intraday_loader.py:107-109` : idem avec filtre dates — reproductible sur la fenêtre. ✅
- `models/ml_threshold_optimizer.py:140` : `np.random.seed(hash(pair_key) % 2**32)` — seed déterministe par paire. ✅
- **Mais** : si les paramètres de la stratégie changent (ex: `entry_z_score`), aucun cache n'est invalidé → risque de résultats périmés servis depuis le cache sans recompute. ⚠️

---

## BLOC 2 — TESTS STATISTIQUES

### 2.1 Tests Sharpe

**PARTIAL**

Des assertions Sharpe existent mais sans seuil minimal significatif :

| Fichier:Ligne | Assertion | Type |
|---|---|---|
| `tests/backtests/004_test_backtest.py:25` | `assert metrics.sharpe_ratio > 0` | Signe positif seulement |
| `tests/backtests/004_test_backtest.py:105` | `assert metrics.sharpe_ratio >= 0.0` | Non-négatif seulement |
| `tests/integration/test_rigorous_assertions.py:300` | `assert metrics.sharpe_ratio > 0.0` | Signe positif seulement |
| `tests/backtests/058_test_walk_forward_integration.py:137` | `assert isinstance(..., float)` | Type seulement |
| `tests/backtests/test_crypto_annualisation.py:85` | `abs(m260) > abs(m252)` | Comparaison relative (annualisation) |

Aucun test n'impose un seuil absolu (ex: Sharpe > 0.5 ou > 1.0). Les tests existants vérifient la cohérence mathématique, pas la qualité financière.

### 2.2 Sensibilité paramètres

**NONE**

- `backtests/parameter_cv.py` : module `ParameterCrossValidator` implémente un grid-search walk-forward avec optimisation Sharpe OOS. Mais **aucun test pytest** n'instancie ce module avec des variations `entry_z ±20%` ou `half_life ±50%` pour vérifier la stabilité.
- `tests/test_entry_z_min_spread.py:17-55` : tests de validation de configuration (valeurs déclarées dans config.yaml), pas de sweep de sensibilité.
- `tests/backtests/test_no_lookahead.py:234,290` : `half_life=20.0` hardcodé — valeur unique, pas de variation.

Aucun test de robustesse paramétrique au sens statistique (variance du Sharpe sous perturbation des paramètres).

### 2.3 Tests OOS

**PARTIAL**

- `backtests/parameter_cv.py:1-30` : infrastructure walk-forward OOS complète (splits IS/OOS, évaluation OOS).
- `tests/backtests/058_test_walk_forward_integration.py:121-179` : tests d'intégration walk-forward — vérifient la structure des résultats (clés présentes, types), pas un seuil de performance OOS.
- `tests/backtests/test_cache_isolation.py:48-68` : teste l'isolation du cache pendant le walk-forward.

Aucun test n'impose un seuil de decay IS→OOS (ex: Sharpe OOS ≥ 60% de Sharpe IS).

---

## BLOC 3 — RÉGRESSION PnL

### 3.1 Snapshots PnL commités

**NONE**

- Aucun répertoire `tests/regression/` ni `tests/regression/snapshots/` ne existe.
- Aucun fichier JSON/CSV de snapshot de métriques commité (`total_pnl`, `sharpe`, `drawdown`, `nb_trades`).

### 3.2 Assertions PnL numériques

**PARTIAL**

Des assertions numériques existent mais sont des bounds larges, pas des snapshots de référence :

| Fichier:Ligne | Assertion | Type |
|---|---|---|
| `tests/backtests/test_trading_costs.py:93` | `net_pnl == 85.0` | Valeur exacte (test unitaire coût) |
| `tests/backtests/test_trading_costs.py:110` | `net_pnl == 10.0` | Valeur exacte (test unitaire coût) |
| `tests/backtests/test_no_lookahead.py:266` | `abs(pnl) < abs(gross) + 1000` | Borne large |
| `tests/backtests/004_test_backtest.py:26` | `metrics.max_drawdown <= 0` | Signe seulement |
| `tests/backtests/058_test_walk_forward_integration.py:181` | `metrics['max_drawdown'] <= 0.0` | Signe seulement |

Les assertions valeur-exacte (`== 85.0`) concernent des calculs de coûts unitaires isolés, pas des backtests bout-en-bout.

### 3.3 Cible make qa

**NONE**

- Aucun `Makefile` à la racine du projet.
- Aucune cible `make qa` ni équivalent (`tox`, `invoke`, `just`) enchaînant tests + régression PnL.
- La commande de validation manuelle est `venv\Scripts\python.exe -m pytest tests/ -q` (définie dans `pytest.ini` + `tasks/WORKFLOW.md`).

---

## TABLEAU SYNTHÈSE

| Amélioration    | Critère             | Statut  | Référence principale                              |
|-----------------|---------------------|---------|---------------------------------------------------|
| Feature Store   | cache               | PARTIAL | `pair_selection/discovery.py:381`, `data/intraday_loader.py:105` |
| Feature Store   | versioning          | NONE    | Aucun hash de paramètres — TTL uniquement         |
| Feature Store   | reproductibilité    | PARTIAL | Reproductible si params stables — pas d'invalidation sur changement config |
| Tests stat.     | sharpe_tests        | PARTIAL | `tests/backtests/004_test_backtest.py:25` — signe seulement |
| Tests stat.     | param_sensitivity   | NONE    | `backtests/parameter_cv.py` existe mais aucun test pytest de sweep |
| Tests stat.     | oos_tests           | PARTIAL | `tests/backtests/058_test_walk_forward_integration.py:121` — structure, pas seuil |
| Régression PnL  | snapshots           | NONE    | Aucun `tests/regression/snapshots/`               |
| Régression PnL  | pnl_assertions      | PARTIAL | `tests/backtests/test_trading_costs.py:93` — unitaire coûts uniquement |
| Régression PnL  | make_qa             | NONE    | Aucun Makefile                                    |

---

## CONCLUSIONS POUR P2/P3/P4

| Phase | Action requise | Risque de duplication |
|---|---|---|
| **P2** Feature Store | Créer `data/feature_store.py` — aucun équivalent générique | ⚠️ Ne pas dupliquer `pair_selection/discovery.py:_save_cache` — s'en distinguer par la généricité |
| **P3** Tests stat. | Créer `tests/statistical/test_strategy_robustness.py` | ✅ Aucun doublon — `parameter_cv.py` est un outil de recherche, pas des tests pytest assertions |
| **P4** Régression PnL | Créer `tests/regression/` + snapshots | ✅ Aucun doublon — les assertions existantes sont des bounds, pas des snapshots bout-en-bout |
| **P5** QA + Makefile | Créer `Makefile` à la racine | ✅ Aucun doublon |
