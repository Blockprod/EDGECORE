# EDGECORE — Rapport d'Audit Stratégique Complet

**Date :** 25 février 2026  
**Auditeur :** Développeur Quant Senior & Architecte Système  
**Périmètre :** Audit complet du code source — évaluation de la maturité pour le trading en argent réel  
**Base de code :** `C:\Users\averr\EDGECORE` — Système d'Arbitrage Statistique de Pair Trading  

---

## Table des Matières

1. [Résumé Exécutif](#1-résumé-exécutif)
2. [Architecture](#2-architecture)
3. [Stratégie & Logique Quantitative](#3-stratégie--logique-quantitative)
4. [Qualité du Code](#4-qualité-du-code)
5. [Moteur de Risque & Portefeuille](#5-moteur-de-risque--portefeuille)
6. [Backtesting & Validation](#6-backtesting--validation)
7. [Monitoring & Logging](#7-monitoring--logging)
8. [Configuration & Sécurité](#8-configuration--sécurité)
9. [Documentation](#9-documentation)
10. [Plan d'Actions Consolidé](#10-plan-dactions-consolidé)

---

## 1. Résumé Exécutif

EDGECORE est une plateforme d'arbitrage statistique bien architecturée couvrant de manière exhaustive la découverte de paires, les tests de cointégration, la modélisation de spread, la gestion des risques, le backtesting et le monitoring. Le code démontre des fondations quantitatives solides (Engle-Granger, Johansen, Kalman, HMM de Markov, ACP) et des préoccupations de production matures (kill switches, circuit breakers, réconciliation, piste d'audit).

### Notes Globales

| Domaine | Note | Résumé |
|---------|------|--------|
| Architecture | **B** | Bonne modularité avec séparation par domaine ; problèmes de couplage et sous-systèmes dupliqués |
| Stratégie & Logique Quant | **B+** | Fondations solides ; modules avancés construits mais non branchés sur le chemin de production |
| Qualité du Code | **B-** | Modules individuels bien structurés ; duplication 3x de la config, prolifération d'enums |
| Moteur de Risque & Portefeuille | **A-** | Multi-couches, complet ; meilleur de sa catégorie pour un système pré-production |
| Backtesting & Validation | **B+** | Walk-forward, OOS, stress tests présents ; bugs critiques dans la logique pass/fail |
| Monitoring & Logging | **A-** | Logging structuré de qualité production, alertes, dashboard, tracing |
| Configuration & Sécurité | **C+** | Triple système de config, schémas Pydantic inutilisés, secrets en mémoire uniquement |
| Documentation | **C** | README obsolète, documents référencés manquants, aucun ADR |

### Bloqueurs Critiques pour la Production (P0)

| # | Problème | Impact |
|---|----------|--------|
| 1 | Bug de casse dans `submit_order()` IBKR — tous les ordres sont routés vers SELL | **Catastrophique** — chaque ordre d'achat devient une vente |
| 2 | `live_trading/runner.py` `_tick()` est un stub — aucune logique de trading | Le trading live est non fonctionnel |
| 3 | Correction de Bonferroni désactivée par défaut dans le chemin principal de la stratégie | Taux de faux positifs >50% pour 50+ symboles |
| 4 | `ModelRetrainingManager` accède à de mauvaises clés de dictionnaire — cycle de vie des paires cassé | Aucune revalidation des paires en production |
| 5 | `paper_execution.py` hérite d'IBKR et appelle une connexion live | Le paper trading nécessite une connexion broker réelle |
| 6 | `signal.SIGUSR1` sur Windows fait crasher `ShutdownManager` au démarrage | Le système ne démarre pas sous Windows |
| 7 | Le Dockerfile référence un répertoire supprimé `cpp/` + mauvaise variable d'env | Les builds Docker échouent |
| 8 | `WalkForwardEngine` référence la mauvaise clé — pass/fail échoue systématiquement | Validation walk-forward cassée |

---

## 2. Architecture

### 2.1 Cartographie des Modules

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│ pair_select  │────▶│  strategies  │────▶│  signal_engine   │
│  discovery   │     │ pair_trading │     │  generator/zscore │
└─────────────┘     └──────┬──────┘     └────────┬────────┘
                           │                      │
                    ┌──────▼──────┐        ┌──────▼──────┐
                    │   models    │        │  risk_engine │
                    │ coint/spread│        │  kill_switch │
                    │ kalman/hmm  │        │  portfolio   │
                    └─────────────┘        └──────┬──────┘
                                                  │
┌─────────────┐     ┌──────────────┐       ┌──────▼──────┐
│  backtests   │────▶│  execution   │◀──────│ portfolio_  │
│ walk_forward │     │ ibkr/paper   │       │   engine    │
│ stress_test  │     │ stops/recon  │       └─────────────┘
└─────────────┘     └──────────────┘
        │
┌───────▼─────┐     ┌──────────────┐       ┌─────────────┐
│  backtester  │     │  monitoring  │       │    data      │
│   wrapper    │     │  api/alerts  │       │ loader/valid │
└──────────────┘     └──────────────┘       └─────────────┘
```

### 2.2 Points Forts

- **Séparation nette par domaine** : 15+ modules de premier niveau avec des responsabilités ciblées
- **Pattern Strategy** dans l'exécution (`PaperTradingMode`, `LiveTradingMode`, `BacktestMode`)
- **Composition plutôt qu'héritage** dans `PortfolioHedger`, `PositionRiskManager`
- **Couche d'utilitaires communs** (`errors`, `circuit_breaker`, `retry`, `validators`) réduit la duplication
- **Points d'entrée multiples** : `main.py` (live/paper), `run_backtest.py`, wrappers `backtester/`

### 2.3 Constats

| ID | Constat | Criticité | Détails |
|----|---------|-----------|---------|
| A-1 | **Fonction « dieu » : `run_paper_trading()`** | Moyenne | ~300 lignes gérant l'initialisation, la réconciliation, la reprise sur crash, la boucle de trading, le traitement des signaux, les stop-loss et le nettoyage. Doit être décomposée en une classe `TradingSession`. |
| A-2 | **Couplage fort dans `main.py`** | Moyenne | Importe directement ~15 classes concrètes. Aucune injection de dépendances ni pattern factory. Changer d'implémentation nécessite de modifier ce fichier. |
| A-3 | **Sous-systèmes dupliqués** | Haute | Deux systèmes de risque (`risk/engine.py` + `risk_engine/portfolio_risk.py`), deux hiérarchies d'exécution (`base.py→IBKREngine` + `modes.py`), trois modules de gestion de stops, trois implémentations de découverte de paires. |
| A-4 | **Constantes magiques codées en dur** | Moyenne | `quantity=10.0`, `volatility=0.02`, `limit_price * 0.99`, `max_attempts=100`, `max_consecutive_errors=10` dispersées dans `main.py` sans référence à la config. |
| A-5 | **Fuite de thread du dashboard** | Basse | L'API Flask tourne dans un thread daemon sans arrêt propre ; le port 5000 peut ne pas être libéré. |
| A-6 | **`run_live_trading` appelle `input()`** | Moyenne | Bloque en environnement headless/Docker ; non testable. |
| A-7 | **`typed_api.py` : façade inutilisée** | Basse | Crée de nouvelles instances de moteur à chaque appel, force le mode paper, importé par rien. |

### 2.4 Actions Recommandées

- [ ] **TODO (A-1) :** Refactoriser `run_paper_trading()` en une classe `TradingSession` avec les méthodes `init()`, `reconcile()`, `recover()`, `tick()`, `shutdown()`.
- [ ] **TODO (A-2) :** Introduire un `ServiceContainer` ou factory pour l'injection de dépendances. Au minimum, créer `create_execution_engine(mode)`, `create_risk_engine(settings)`.
- [ ] **TODO (A-3) :** Consolider les sous-systèmes dupliqués : unifier `risk/engine.py` et `risk_engine/portfolio_risk.py` sous une seule façade de risque ; désigner une seule implémentation de découverte de paires (`PairDiscoveryEngine`).
- [ ] **TODO (A-7) :** Supprimer `common/typed_api.py` ou le brancher correctement.

---

## 3. Stratégie & Logique Quantitative

### 3.1 Vue d'Ensemble du Pipeline

$$\text{Prix} \xrightarrow[\text{E-G / Johansen}]{\text{Découverte de Paires}} \text{Paires} \xrightarrow[\text{OLS / Kalman}]{\text{Spread}} \xrightarrow[\text{Rolling / EWMA}]{\text{Z-score}} \xrightarrow[\text{Régime}]{\text{Seuil}} \text{Signal}$$

### 3.2 Évaluation par Composant

| Composant | Fichier(s) | Note | Remarques |
|-----------|------------|------|-----------|
| Test d'Engle-Granger | `models/cointegration.py` | **A** | Garde sur le nombre de condition, gestion d'erreurs robuste, Bonferroni disponible |
| Test de Johansen | `models/johansen.py` | **A-** | Rang conservateur = min(trace, max-eig), implémentation propre |
| HAC Newey-West | `models/cointegration.py` | **A** | Double test de consensus, robuste à l'hétéroscédasticité |
| Modèle de spread (OLS) | `models/spread.py` | **B+** | Lookback adaptatif par demi-vie, clipping du Z-score à ±6 |
| Ratio de couverture Kalman | `models/kalman_hedge.py` | **B** | Filtre scalaire correct, mais pas d'état d'intercept ; recalcule tout l'historique |
| Seuils adaptatifs | `models/adaptive_thresholds.py` | **B+** | Ajustement vol-percentile + demi-vie, plage ±0.3–0.5σ |
| Détection de régime (percentile) | `models/regime_detector.py` | **B** | Simple et rapide ; problème de seuils circulaires |
| Détection de régime (HMM) | `models/markov_regime.py` | **A-** | Transitions probabilistes, re-fit périodique, ordonnancement des labels par moyenne |
| Estimateur de demi-vie | `models/half_life_estimator.py` | **B+** | AR(1) correct mais utilise la moyenne complète (biais prospectif) |
| Moniteur de stationnarité | `models/stationarity_monitor.py` | **B** | ADF glissant avec p=0.10 conservateur, mais faible puissance sur fenêtres courtes |
| Détecteur de rupture structurelle | `models/structural_break.py` | **A-** | CUSUM + stabilité β, mais **jamais appelé depuis le chemin de trading** |
| Optimiseur ML de seuils | `models/ml_threshold_optimizer.py` | **C** | Entraîné sur données synthétiques uniquement ; bug de direction P&L sur les shorts ; splits mélangés |
| Validateur ML de seuils | `models/ml_threshold_validator.py` | **A-** | Gate OOS walk-forward, auto-désactivation si dégradation >20% |
| Découverte de paires | `pair_selection/discovery.py` | **A** | Bonferroni par défaut, consensus Johansen + NW, meilleure implémentation |

### 3.3 Constats Quantitatifs Critiques

| ID | Constat | Criticité | Détails |
|----|---------|-----------|---------|
| Q-1 | **Correction de Bonferroni désactivée dans la stratégie principale** | **Haute** | `PairTradingStrategy.find_cointegrated_pairs()` met `apply_bonferroni=False`. Avec 50 symboles (1 225 tests), faux positifs attendus ≈ 61 à α=0.05. Seul `PairDiscoveryEngine` l'applique par défaut. |
| Q-2 | **`SignalGenerator` rejette Kalman/DynamicSpreadModel** | Haute | Crée un nouveau `SpreadModel` (OLS) à chaque appel. Toute l'infrastructure Kalman du Sprint 4.2 est construite mais inutilisée dans le chemin de production. |
| Q-3 | **`StructuralBreakDetector` est du code mort dans le chemin critique** | Haute | Jamais appelé depuis `generate_signals()` ni aucune boucle de stratégie. Les ruptures structurelles passent inaperçues. |
| Q-4 | **Vérification I(1) désactivée par défaut** | Moyenne | `check_integration_order=False` dans `engle_granger_test()`. EG peut trouver une « cointégration » entre deux séries stationnaires ou I(2). |
| Q-5 | **L'entraînement ML utilise uniquement des données synthétiques** | Moyenne | `ThresholdDataGenerator` crée des processus AR(1) sans queues épaisses, sans changement de régime, sans effets de microstructure. Les modèles ne peuvent pas généraliser aux spreads réels. |
| Q-6 | **Bug P&L ML pour les shorts** | Moyenne | `simulate_trades()` calcule toujours `pnl = prix_sortie - prix_entrée` quel que soit la direction. Le P&L des trades short est inversé. |
| Q-7 | **Trois implémentations séparées de découverte de paires** | Moyenne | `PairTradingStrategy`, `PairDiscoveryEngine`, `ModelRetrainingManager` — Bonferroni, noms de clés et filtres différents. |
| Q-8 | **Seuil de sortie par défaut à 0.0** | Moyenne | La stratégie sort exactement à la moyenne — maximise le whipsaw et les coûts de transaction. Devrait être 0.3–0.5. |
| Q-9 | **Le filtre de Kalman n'a pas d'état d'intercept** | Basse | Spread = y − βx (pas de α). Introduit un biais quand l'intercept est non nul. |
| Q-10 | **L'estimateur de demi-vie utilise la moyenne complète** | Basse | L'étape de centrage utilise la moyenne sur tout l'historique — biais prospectif en contexte glissant. |

### 3.4 Actions Recommandées

- [ ] **TODO (Q-1) :** Activer Bonferroni dans `PairTradingStrategy` ou remplacer sa découverte par `PairDiscoveryEngine.discover()`.
- [ ] **TODO (Q-2) :** Router `SignalGenerator` à travers `DynamicSpreadModel` pour exploiter le β Kalman et les seuils adaptatifs.
- [ ] **TODO (Q-3) :** Ajouter un appel `StructuralBreakDetector.check_from_prices()` dans `SignalGenerator.generate()` — forcer la sortie sur rupture détectée.
- [ ] **TODO (Q-4) :** Mettre `check_integration_order=True` par défaut en découverte de paires de production.
- [ ] **TODO (Q-5) :** Entraîner les modèles ML de seuils sur des données historiques de spread de paires, pas sur des AR(1) synthétiques.
- [ ] **TODO (Q-6) :** Corriger le calcul P&L : `pnl = (sortie - entrée) si long sinon (entrée - sortie)`.
- [ ] **TODO (Q-7) :** Consolider vers un seul chemin de découverte : `PairDiscoveryEngine`.
- [ ] **TODO (Q-8) :** Changer le `exit_z_score` par défaut de 0.0 à 0.3.

---

## 4. Qualité du Code

### 4.1 Points Forts

- Utilisation cohérente de `structlog` pour le logging structuré
- Définitions de dataclass propres avec validation `__post_init__`
- Type hints sur la plupart des API publiques
- Bon usage des ABC Python (`BaseStrategy`, `BaseExecutionEngine`)
- Taxonomie d'erreurs complète avec gestion par catégorie

### 4.2 Constats

| ID | Constat | Criticité | Détails |
|----|---------|-----------|---------|
| C-1 | **Triple système de configuration** | **Haute** | Dataclasses (`settings.py`), modèles Pydantic v2 (`schemas.py`), TypedDicts (`types.py`) définissent les mêmes concepts avec des noms de champs différents. Les schémas Pydantic ne sont **jamais invoqués**. |
| C-2 | **Duplication d'enums** | Moyenne | `OrderSide`, `OrderType`, `OrderStatus`, `ExecutionMode`, `CircuitBreakerState` ont chacun 2–3 définitions à travers les modules. Importer le mauvais provoque des incompatibilités de type silencieuses. |
| C-3 | **`common/types.py` fait 812 lignes** | Moyenne | Un seul fichier couvre 14 enums + 11 alias + 40 TypedDicts. Devrait être découpé en `types/orders.py`, `types/risk.py`, `types/backtest.py`. |
| C-4 | **Ordre des arguments de `DataError` incohérent** | Moyenne | `DataError.__init__(message, original_error, category)` inverse l'ordre par rapport au parent `TradingError.__init__(message, category, original_error)`. `DataError("msg", ErrorCategory.RETRYABLE)` stocke silencieusement l'enum comme `original_error`. |
| C-5 | **Collision de noms `ConfigError`** | Moyenne | `common.errors.ConfigError(TradingError)` vs `common.validators.ConfigError(ValidationError)` — hiérarchies différentes, même nom. |
| C-6 | **Systèmes de retry redondants** | Moyenne | `error_handler.with_error_handling` et `retry.retry_with_backoff` sont des décorateurs indépendants. `with_error_handling` n'a pas de jitter ; `retry_with_backoff` a du jitter mais est moins utilisé. Aucun ne compose avec le circuit breaker. |
| C-7 | **`datetime.utcnow()` déprécié** | Basse | Utilisé dans `circuit_breaker.py`, `secrets.py`, `order_lifecycle.py`. Utiliser `datetime.now(timezone.utc)` (Python 3.12+). |
| C-8 | **`validate_symbol` trop restrictif** | Basse | La regex `^[A-Z]{1,5}$` rejette `BRK.B`, `BF.B`, les tickers avec des chiffres. |
| C-9 | **Modules de code mort** | Basse | `config/schemas.py` (jamais importé), `common/typed_api.py` (jamais importé), `RetryStats` (jamais instancié), sections de `config.yaml` (`market`, `portfolio`, `validation`, `monitoring`) silencieusement ignorées par `Settings`. |
| C-10 | **Le chargement YAML de `settings.py` accepte les fautes de frappe** | Moyenne | `setattr(self.strategy, key, value)` pour chaque clé YAML — `entry_z_scroe: 5.0` crée un nouvel attribut silencieusement au lieu de lever une erreur. |

### 4.3 Couverture de Tests

| Sous-système | Fichiers de test | Fonctions de test | Évaluation |
|--------------|-----------------|-------------------|------------|
| Models | 19 | ~380 | **Forte** — cointégration, Kalman, HMM, seuils, demi-vie |
| Backtests | 7 | ~110 | **Bonne** — modèle de coûts, walk-forward, event-driven, anti look-ahead |
| Monitoring | 0 (dans `tests/`) | 0 | **Lacune** — aucun test de monitoring trouvé dans `tests/` |
| Execution | 3 | ~45 | **Faible** — seulement concentration, trailing stop, time stop |
| Data | 2 | ~30 | **Faible** — filtre de liquidité et pipeline d'outliers uniquement |
| Risk | 1 | ~15 | **Très faible** — seul le spread correlation guard est testé |
| Strategies | 3 | ~50 | **Correcte** — cache TTL, limites internes, corrélation de jambes |
| Validation | 1 | ~10 | **Très faible** — validateur OOS uniquement |
| Config | 1 | ~10 | **Très faible** — validation univers YAML uniquement |
| Intégration | 1 | ~15 | **Très faible** — un seul fichier de test d'intégration |
| **Total** | **38** | **~774** | **Modérée** — forte sur les modèles, faible sur risque/exécution/intégration |

### 4.4 Actions Recommandées

- [ ] **TODO (C-1) :** Supprimer `config/schemas.py` OU remplacer les dataclasses de `settings.py` par les modèles Pydantic. Un seul système de config.
- [ ] **TODO (C-2) :** Créer une source canonique unique pour chaque enum dans `common/types.py` et ré-exporter. Déprécier les définitions locales aux modules.
- [ ] **TODO (C-3) :** Découper `common/types.py` en package `common/types/`.
- [ ] **TODO (C-4) :** Corriger l'ordre des arguments de `DataError.__init__` pour correspondre au parent.
- [ ] **TODO (C-6) :** Consolider la logique de retry : composer `retry_with_backoff` avec `CircuitBreaker`. Supprimer `with_error_handling`.
- [ ] **TODO :** Ajouter des tests pour : `risk/engine.py`, `execution/ibkr_engine.py`, `execution/modes.py`, `execution/order_lifecycle.py`, `execution/reconciler.py`, sous-système `monitoring/`.

---

## 5. Moteur de Risque & Portefeuille

### 5.1 Architecture des Couches de Risque

```
                    ┌──────────────────┐
                    │   KillSwitch     │  ← Arrêt d'urgence (5 vérifications auto + manuel)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ PortfolioRiskMgr  │  ← Drawdown, perte quotidienne, heat, circuit breaker
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────▼───┐  ┌──────▼──────┐  ┌───▼─────────┐
    │ RiskEngine   │  │ Concentration│  │ PortfolioHedger│
    │ (pré-trade)  │  │   Manager    │  │ (β-neutre)     │
    └──────────────┘  └─────────────┘  └───────────────┘
                                            │
                              ┌──────────────┼───────────────┐
                              │              │               │
                    ┌─────────▼──┐  ┌───────▼──────┐  ┌────▼────────┐
                    │ SpreadCorr  │  │ PCASpread    │  │ BetaNeutral │
                    │   Guard     │  │  Monitor     │  │   Hedger    │
                    └────────────┘  └──────────────┘  └─────────────┘
```

### 5.2 Points Forts

- **Défense multi-couches** : kill switch → risque portefeuille → garde pré-trade → stops par position
- **Le KillSwitch nécessite un reset manuel** — empêche la reprise automatique accidentelle
- **Détection de concentration factorielle par ACP** (au-delà de la simple corrélation pairwise)
- **Couverture à trois couches** : corrélation de spread + ACP + beta-neutre
- **Quatre méthodes de dimensionnement** : équipondéré, inverse-volatilité, demi-Kelly, pondéré par signal
- **Gestion complète des stops** : trailing (basé Z-score), time stops, stops P&L, prise de profit partielle, protection breakeven

### 5.3 Constats

| ID | Constat | Criticité | Détails |
|----|---------|-----------|---------|
| R-1 | **Le circuit breaker portefeuille reprend automatiquement** | **Haute** | `PortfolioRiskManager` reprend le trading après `circuit_breaker_cooldown_bars` (10 barres). En production, la reprise après drawdown devrait nécessiter une confirmation manuelle. |
| R-2 | **État du KillSwitch non persisté** | **Haute** | En mémoire uniquement. Crash du processus → redémarrage → trades exécutés avant que le kill switch ne se redéclenche. |
| R-3 | **Double suivi d'état de risque** | Moyenne | `RiskEngine` et `PortfolioRiskManager` suivent indépendamment le drawdown, la perte quotidienne et les pertes consécutives. Risque de désynchronisation. |
| R-4 | **`daily_loss` ne se remet jamais à zéro automatiquement** | Moyenne | `RiskEngine` requiert que l'appelant invoque `reset_daily_stats()`. Si oublié → la perte quotidienne s'accumule sur plusieurs jours → arrêt permanent du trading. |
| R-5 | **Pas de surveillance de marge** | Moyenne | Aucune vérification contre les exigences de marge du broker avant le dimensionnement. |
| R-6 | **`ConcentrationManager.check_entry()` a des effets de bord** | Moyenne | Appeler `check_entry()` enregistre aussi la position. Pas de vérification sans engagement possible. |
| R-7 | **La métrique `concentration_pct` est trompeuse** | Moyenne | Calculée comme `|net|/brut` — mesure la couverture, pas la concentration du portefeuille. Un symbole avec 10L+10S = 0% de « concentration » mais 100% d'exposition. |
| R-8 | **Pas de taille de position minimum** | Basse | `PortfolioAllocator` peut allouer des positions minuscules qui coûtent plus en commissions qu'elles ne rapportent. |
| R-9 | **Corrélation Monte Carlo non implémentée** | Basse | `create_correlated_simulations()` calcule la matrice de Cholesky mais ne l'applique jamais. Les actifs simulent indépendamment. |
| R-10 | **Les stops de position utilisent un singleton global** | Basse | `_stop_manager` dans `position_stops.py` est au niveau module — non thread-safe, problématique pour des stratégies concurrentes. |

### 5.4 Actions Recommandées

- [ ] **TODO (R-1) :** Changer le circuit breaker portefeuille pour exiger un reset manuel en mode production.
- [ ] **TODO (R-2) :** Persister l'état du kill switch sur disque (ajouter à la piste d'audit). Au démarrage, vérifier si le kill switch était actif avant le crash.
- [ ] **TODO (R-3) :** Unifier le suivi de risque dans un seul `RiskState` que les deux systèmes référencent.
- [ ] **TODO (R-4) :** Ajouter un reset quotidien automatique basé sur le calendrier de trading dans `RiskEngine`.
- [ ] **TODO (R-5) :** Ajouter une vérification pré-trade de marge via l'API IBKR `whatIfOrder()`.
- [ ] **TODO (R-6) :** Ajouter une méthode `check_only()` à `ConcentrationManager` qui valide sans engagement.

---

## 6. Backtesting & Validation

### 6.1 Matrice de Capacités

| Fonctionnalité | Statut | Implémentation |
|---------------|--------|----------------|
| Walk-forward (fenêtre expansible) | ✅ Complet | `backtests/walk_forward.py` — ré-entraînement par période, validation OOS des paires |
| Validation hors-échantillon | ✅ Complet | `validation/oos_validator.py` — persistance de cointégration, dérive de demi-vie |
| Modèle de coûts (4 composantes) | ✅ Complet | `backtests/cost_model.py` — maker/taker + slippage + emprunt + financement |
| Simulation event-driven | ✅ Complet | `backtests/event_driven.py` — remplissages partiels, impact de marché |
| Tests de stress | ⚠️ Partiel | 4/5 scénarios ; pas de sécheresse de liquidité, pas de chocs asymétriques |
| Cross-validation des paramètres | ✅ Complet | `backtests/parameter_cv.py` — CV walk-forward avec analyse de stabilité |
| Prévention du look-ahead | ✅ Complet | Chemin unifié via `run_unified()`, isolation du cache en WF |
| Comptabilité MtM | ⚠️ Partiel | `strategy_simulator.py` l'a ; `event_driven.py` non |
| Dimensionnement adapté au régime | ✅ Complet | `strategy_simulator.py` — multiplicateurs de volatilité + qualité |

### 6.2 Constats

| ID | Constat | Criticité | Détails |
|----|---------|-----------|---------|
| B-1 | **`WalkForwardEngine` : mauvais nom de clé** | **Haute** | Référence `per_period_results` mais la vraie clé est `per_period_metrics`. Le pass/fail retourne toujours « non réussi ». |
| B-2 | **Le `run()` legacy est toujours fonctionnel** | Moyenne | Le chemin legacy utilise 1% d'allocation vs 30% pour l'unifié, 15bps de coûts fixes vs 4bps. Produit des résultats radicalement différents. Devrait être bloqué. |
| B-3 | **Le walk-forward fait la moyenne du `max_drawdown`** | Moyenne | `_aggregate_metrics()` moyenne les max_drawdown entre périodes. Les drawdowns ne se moyennent pas de façon significative — rapporter la pire période ou calculer depuis la courbe d'équité concaténée. |
| B-4 | **`strategy_simulator.py` fait 908 lignes** | Moyenne | Combine ~8 mécanismes de sortie/dimensionnement dans un seul fichier. Interactions cachées entre trailing stops, time stops, P&L stops, circuit breaker, dimensionnement par régime, allocation par qualité. |
| B-5 | **Allocation par défaut de 30% par paire** | Moyenne | Une seule paire consomme 30% du capital — extrêmement concentré. Le défaut devrait être plus bas (10–15%) pour une stratégie market-neutral. |
| B-6 | **Le modèle de coûts utilise les jours calendaires pour l'emprunt** | Basse | `holding_cost()` divise par 365 mais le système opère sur 252 jours de trading — surestime les coûts d'emprunt de ~30%. |
| B-7 | **`BacktestMetrics.summary()` affiche « EUR »** | Basse | Le système cible les actions US — devrait afficher « USD ». |
| B-8 | **Le validateur OOS rejette p ∈ (0.001, 0.05)** | Basse | Des paires avec p=0.002 classifiées comme « faibles » malgré une signification statistique élevée. Règle trop agressive. |
| B-9 | **Vérification `survived` du stress testing : mauvais signe** | Basse | `max_drawdown > -1.0` utilise la mauvaise convention de signe — `max_drawdown` des métriques est déjà négatif. |

### 6.3 Actions Recommandées

- [ ] **TODO (B-1) :** Corriger la référence de clé dans `backtester/walk_forward.py` de `per_period_results` à `per_period_metrics`.
- [ ] **TODO (B-2) :** Supprimer ou bloquer le `run()` legacy dans `backtests/runner.py`. Ajouter `raise DeprecationError`.
- [ ] **TODO (B-3) :** Calculer le max_drawdown depuis la courbe d'équité concaténée dans `_aggregate_metrics()`.
- [ ] **TODO (B-5) :** Réduire `allocation_per_pair_pct` par défaut de 30.0 à 10.0–15.0.
- [ ] **TODO (B-8) :** Supprimer la bande de rejet « p-value faible » (0.001, 0.05) dans `oos_validator.py`.

---

## 7. Monitoring & Logging

### 7.1 Cartographie de l'Infrastructure

| Composant | Fichier | Statut |
|-----------|---------|--------|
| Logging structuré | `monitoring/logger.py`, `logging_config.py` | ✅ Qualité production (structlog + JSON + rotation) |
| Cycle de vie des alertes | `monitoring/alerter.py` | ✅ Complet (créer → acquitter → résoudre, routage par sévérité) |
| Intégration Slack | `monitoring/slack_alerter.py` | ✅ Throttlé, dégradation gracieuse |
| Alertes email | `monitoring/email_alerter.py` | ⚠️ Utilisation de `MIMEMultipart` incorrecte |
| Dashboard REST | `monitoring/api.py` | ✅ Flask avec rate limiting, auth par clé API |
| Données du dashboard | `monitoring/dashboard.py` | ✅ Système + risque + positions + ordres + performance |
| Spec OpenAPI | `monitoring/api_schema.py` | ✅ Spécification 3.0 complète |
| Suivi de latence | `monitoring/latency.py` | ❌ Crash à l'exécution — `numpy` non importé |
| Profileur | `monitoring/profiler.py` | ✅ Basé sur `perf_counter()`, détection de goulets |
| Tracing distribué | `monitoring/tracing.py` | ✅ Spans type OpenTelemetry |
| Couche de cache | `monitoring/cache.py` | ✅ LRU thread-safe avec TTL |
| Sécurité de l'API | `monitoring/api_security.py` | ⚠️ Rate limiter en mémoire, secret JWT codé en dur |
| Métriques Prometheus | `monitoring/metrics.py` | ❌ Ébauche — aucune intégration de la bibliothèque client |

### 7.2 Constats

| ID | Constat | Criticité | Détails |
|----|---------|-----------|---------|
| M-1 | **`latency.py` crash à l'exécution** | **Haute** | Utilise `np.percentile()` sans importer numpy. `NameError` au premier calcul de métrique de latence. |
| M-2 | **Accumulation de handlers de log** | Moyenne | `setup_logger()` appelle `root_logger.addHandler()` à chaque appel — doublons d'entrées de log sur les appels répétés. |
| M-3 | **Les métriques Prometheus sont une ébauche** | Moyenne | `SystemMetrics` exporte du texte mais pas d'intégration `prometheus_client`, pas d'histogrammes, pas de push gateway. |
| M-4 | **Le rate limiter est en mémoire uniquement** | Moyenne | Se réinitialise au redémarrage, ne fonctionne pas entre plusieurs workers. |
| M-5 | **Secret JWT codé en dur** | Moyenne | Secret par défaut dans `api_security.py` — un avertissement de production est présent mais pas d'enforcement. |
| M-6 | **Construction MIME de `email_alerter.py`** | Basse | `MIMEMultipart('text', 'plain')` est incorrect — devrait être `MIMEMultipart()` + `MIMEText()`. |
| M-7 | **`cpu_percent(interval=0.1)` du dashboard** | Basse | Bloque 100ms par appel au dashboard. Utiliser `cpu_percent(interval=None)` pour un appel non bloquant. |
| M-8 | **Aucun test de monitoring dans `tests/`** | Moyenne | Zéro fichier de test pour le sous-système de monitoring malgré que ce soit l'un des plus gros modules. |

### 7.3 Actions Recommandées

- [ ] **TODO (M-1) :** Ajouter `import numpy as np` au niveau module dans `monitoring/latency.py`.
- [ ] **TODO (M-2) :** Protéger contre l'enregistrement multiple de handlers : vérifier `if not root_logger.handlers:` avant d'ajouter.
- [ ] **TODO (M-3) :** Intégrer la bibliothèque `prometheus_client` pour une exposition de métriques appropriée.
- [ ] **TODO (M-5) :** Imposer `JWT_SECRET` depuis une variable d'environnement ; faire échouer le démarrage si non défini en production.
- [ ] **TODO (M-8) :** Ajouter une suite de tests pour `monitoring/alerter.py`, `api.py`, `api_security.py`, `latency.py`.

---

## 8. Configuration & Sécurité

### 8.1 Évaluation du Système de Configuration

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  settings.py         │    │  schemas.py          │    │  types.py           │
│  @dataclass configs  │    │  Modèles Pydantic    │    │  TypedDicts          │
│  ✅ UTILISÉ          │    │  ❌ JAMAIS INVOQUÉ   │    │  ❌ NON APPLIQUÉ     │
│  ⚠️ Pas de validat.  │    │  ✅ A la validation  │    │  ⚠️ Structurel seul  │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
              Trois représentations. Zéro intégration.
```

### 8.2 Constats

| ID | Constat | Criticité | Détails |
|----|---------|-----------|---------|
| S-1 | **Schémas Pydantic jamais invoqués** | **Haute** | `FullConfigSchema` avec une excellente validation de champs existe mais est du code mort. `Settings` utilise des dataclasses brutes qui acceptent tout. |
| S-2 | **Sections de `config.yaml` silencieusement ignorées** | Haute | Les sections `market`, `portfolio`, `validation`, `monitoring` existent dans le YAML mais `Settings._load_yaml()` ne traite que `strategy`, `trading_universe`, `risk`, `execution`, `backtest`, `secrets`. |
| S-3 | **Le chargement YAML accepte les fautes de frappe** | Haute | `setattr(self.strategy, key, value)` crée de nouveaux attributs pour les clés mal orthographiées au lieu de lever des erreurs. Une faute de frappe dans la config pourrait silencieusement désactiver une limite de risque. |
| S-4 | **Singleton Settings non thread-safe** | Moyenne | `__new__` + `__init__` avec le flag `_initialized` a une condition de course TOCTOU dans un contexte Flask multi-threadé. |
| S-5 | **Le coffre-fort de secrets est en mémoire uniquement** | Moyenne | Pas de persistance, pas de chiffrement au repos. La mort du processus perd tout l'état du coffre-fort. |
| S-6 | **`load_from_env` des secrets : faux positifs** | Basse | Correspond à toute variable d'env contenant « key », « token », « password » — capture `PYTEST_CURRENT_TEST`, `PYTHONDONTWRITEBYTECODE`. |
| S-7 | **Conflits de versions de dépendances** | **Haute** | `pyproject.toml` fixe `vectorbt==0.25.0`, `requirements.txt` fixe `>=0.26.0`. `pydantic` absent des deux. `requires-python = "==3.11.9"` rejette 3.11.10+. |
| S-8 | **Docker `ENVIRONMENT` vs `EDGECORE_ENV`** | Haute | Le Dockerfile définit `ENVIRONMENT=production` mais Settings lit `EDGECORE_ENV`. Retombe sur la config `dev` dans le conteneur de production. |
| S-9 | **Redis/Elasticsearch non authentifiés** | Moyenne | `docker-compose.yml` : Redis tourne sans `requirepass`, Elasticsearch a `xpack.security.enabled: "false"`. |
| S-10 | **Tous les ports sur 0.0.0.0** | Moyenne | Docker expose les ports sur toutes les interfaces — devrait être lié à `127.0.0.1` en production. |
| S-11 | **Mot de passe Grafana par défaut** | Basse | `${GRAFANA_PASSWORD:-admin}` par défaut à `admin`. |

### 8.3 Actions Recommandées

- [ ] **TODO (S-1) :** Remplacer les dataclasses de config par les modèles Pydantic de `schemas.py`. Un seul système de validation.
- [ ] **TODO (S-3) :** Ajouter un garde `__setattr__` sur les dataclasses de config qui rejette les noms d'attributs inconnus.
- [ ] **TODO (S-7) :** Réconcilier `pyproject.toml` et `requirements.txt`. Fixer des plages compatibles. Ajouter `pydantic>=2.0,<3.0`. Assouplir `requires-python` à `>=3.11,<3.13`.
- [ ] **TODO (S-8) :** Changer le Dockerfile en `ENV EDGECORE_ENV=production`.
- [ ] **TODO (S-9) :** Ajouter `requirepass` à Redis et activer la sécurité Elasticsearch dans `docker-compose.yml`.
- [ ] **TODO (S-10) :** Lier tous les ports à `127.0.0.1` dans docker-compose ; utiliser un reverse proxy pour l'accès externe.

---

## 9. Documentation

### 9.1 État Actuel

| Document | Statut | Problèmes |
|----------|--------|-----------|
| `README.md` | ⚠️ Obsolète | Référence des classes inexistantes (`BacktestEngine`, `BacktestConfig`). Les exemples d'API ne correspondent pas au code. |
| `ARCHITECTURE.md` | ❌ Manquant | Référencé dans le README mais n'existe pas. |
| `CONFIG_GUIDE.md` | ❌ Manquant | Référencé dans le README mais n'existe pas. |
| `OPERATIONS_RUNBOOK.md` | ❌ Manquant | Référencé dans le README mais n'existe pas. |
| `BACKTEST_USAGE.md` | ❌ Manquant | Référencé dans le README mais n'existe pas. |
| `monitoring/API_SECURITY.md` | ✅ Existe | Documentation de sécurité de l'API. |
| `monitoring/DASHBOARD_CACHING.md` | ✅ Existe | Documentation de stratégie de cache. |
| `monitoring/DEPLOYMENT_GUIDE.md` | ✅ Existe | Instructions de déploiement. |
| `monitoring/PRODUCTION_LOGGING.md` | ✅ Existe | Guide de configuration du logging. |
| Docstrings de modules | ⚠️ Partiel | La plupart des modules ont des docstrings ; certains manquent d'exemples d'utilisation. |
| ADRs (Architecture Decision Records) | ❌ Manquant | Aucun enregistrement des décisions d'architecture (pourquoi triple config, pourquoi deux moteurs de risque, etc.). |

### 9.2 Constats

| ID | Constat | Criticité | Détails |
|----|---------|-----------|---------|
| D-1 | **Exemples de code du README cassés** | Moyenne | Les exemples du quick-start référencent `BacktestEngine`, `WalkForwardEngine`, `PaperTradingRunner` — les noms de classes ne correspondent pas au code. |
| D-2 | **Quatre documents référencés manquants** | Moyenne | `ARCHITECTURE.md`, `CONFIG_GUIDE.md`, `OPERATIONS_RUNBOOK.md`, `BACKTEST_USAGE.md` — liens morts. |
| D-3 | **Pas de guide d'intégration (onboarding)** | Moyenne | Un nouveau développeur n'a aucun chemin clair de « cloner le repo » à « lancer un backtest » à « comprendre l'architecture ». |
| D-4 | **Pas d'ADR** | Basse | Les décisions de conception (triple système de config, deux moteurs de risque, tentative d'accélération C++) ne sont pas documentées. |
| D-5 | **Affirmation « 295+ tests, 100% pass rate »** | Basse | Le README affirme cela mais le nombre réel est ~774 fonctions de test dans 38 fichiers. L'affirmation est obsolète et non vérifiée. |

### 9.3 Actions Recommandées

- [ ] **TODO (D-1) :** Mettre à jour les exemples du quick-start du README pour correspondre à l'API réelle (`BacktestRunner.run_unified()`, etc.).
- [ ] **TODO (D-2) :** Créer ou supprimer les références aux documents manquants.
- [ ] **TODO (D-3) :** Rédiger `docs/ONBOARDING.md` avec un guide pas-à-pas (installation → config → premier backtest → vue d'ensemble de l'architecture).
- [ ] **TODO (D-4) :** Créer un dossier `docs/adr/` avec des ADR pour les décisions de conception clés.

---

## 10. Plan d'Actions Consolidé

### Priorité 0 — À corriger impérativement avant la production

| # | Action | Domaine | Effort |
|---|--------|---------|--------|
| 1 | Corriger la casse dans `submit_order()` IBKR : `order.side.value.lower()` ou comparer en majuscules | Exécution | 1h |
| 2 | Implémenter `live_trading/runner.py` `_tick()` avec le flux réel signal → risque → ordre | Architecture | 3j |
| 3 | Activer la correction de Bonferroni dans `PairTradingStrategy` (ou déléguer à `PairDiscoveryEngine`) | Quant | 2h |
| 4 | Corriger les clés dict de `ModelRetrainingManager` (`p_value` → `adf_pvalue`, `hedge_ratio` → `beta`) | Quant | 1h |
| 5 | Découpler `PaperExecutionEngine` de `IBKRExecutionEngine` — aucune connexion live nécessaire | Exécution | 4h |
| 6 | Protéger `signal.SIGUSR1` avec `hasattr(signal, 'SIGUSR1')` dans `ShutdownManager` | Exécution | 30m |
| 7 | Corriger le Dockerfile : supprimer `COPY cpp/`, changer `ENVIRONMENT` → `EDGECORE_ENV`, ajouter `.dockerignore` | Déploiement | 1h |
| 8 | Corriger la clé dans `WalkForwardEngine` : `per_period_results` → `per_period_metrics` | Backtest | 30m |
| 9 | Ajouter `import numpy as np` dans `monitoring/latency.py` | Monitoring | 5m |

### Priorité 1 — Requis pour la robustesse

| # | Action | Domaine | Effort |
|---|--------|---------|--------|
| 10 | Router `SignalGenerator` à travers `DynamicSpreadModel` / Kalman | Quant | 1j |
| 11 | Brancher `StructuralBreakDetector` dans le chemin de génération de signaux | Quant | 4h |
| 12 | Consolider la config en un seul système (Pydantic) — supprimer les dataclasses de config | Config | 2j |
| 13 | Unifier les enums `OrderStatus`, `OrderSide`, `ExecutionMode` en une source canonique unique | Qualité Code | 4h |
| 14 | Persister l'état du kill switch dans la piste d'audit | Risque | 4h |
| 15 | Changer le circuit breaker portefeuille en reset manuel en production | Risque | 2h |
| 16 | Réconcilier les versions de dépendances entre `pyproject.toml` et `requirements.txt` | Build | 2h |
| 17 | Ajouter un reset quotidien automatique dans `RiskEngine` | Risque | 2h |
| 18 | Supprimer le `BacktestRunner.run()` legacy ou lever `DeprecationError` | Backtest | 1h |
| 19 | Consolider les trois implémentations de découverte de paires en une seule | Quant | 1j |
| 20 | Corriger l'entraînement ML de seuils : données réelles, direction P&L correcte, splits temporels | Quant | 2j |

### Priorité 2 — Améliorations recommandées

| # | Action | Domaine | Effort |
|---|--------|---------|--------|
| 21 | Refactoriser `run_paper_trading()` en classe `TradingSession` | Architecture | 1j |
| 22 | Ajouter l'injection de dépendances / conteneur de services | Architecture | 2j |
| 23 | Découper `common/types.py` (812 lignes) en package | Qualité Code | 4h |
| 24 | Corriger l'ordre des arguments du constructeur `DataError` | Qualité Code | 30m |
| 25 | Changer le Z-score de sortie par défaut de 0.0 à 0.3 | Quant | 30m |
| 26 | Réduire `allocation_per_pair_pct` par défaut de 30% à 10–15% | Backtest | 30m |
| 27 | Ajouter une vérification pré-trade de marge via IBKR `whatIfOrder()` | Risque | 4h |
| 28 | Ajouter `check_only()` à `ConcentrationManager` | Risque | 1h |
| 29 | Intégrer proprement `prometheus_client` pour les métriques | Monitoring | 4h |
| 30 | Corriger la construction MIME de l'alerteur email | Monitoring | 30m |
| 31 | Mettre à jour le README avec les exemples d'API corrects | Docs | 2h |
| 32 | Créer la documentation manquante (ARCHITECTURE, CONFIG_GUIDE, ONBOARDING) | Docs | 2j |
| 33 | Activer `check_integration_order=True` par défaut | Quant | 30m |
| 34 | Ajouter l'état d'intercept au filtre de Kalman | Quant | 4h |
| 35 | Sécuriser Redis/Elasticsearch dans docker-compose | Sécurité | 1h |

### Priorité 3 — Souhaitable

| # | Action | Domaine | Effort |
|---|--------|---------|--------|
| 36 | Ajouter la logique de reconnexion IBKR avec backoff exponentiel | Exécution | 4h |
| 37 | Ajouter le rate limiting des ordres | Exécution | 2h |
| 38 | Implémenter la simulation Monte Carlo corrélée (terminer Cholesky) | Exécution | 2h |
| 39 | Ajouter `omega_ratio`, `information_ratio` à `BacktestMetrics` | Backtest | 2h |
| 40 | Implémenter des scénarios de chocs asymétriques dans les stress tests | Backtest | 4h |
| 41 | Créer un dossier ADR pour les décisions de conception | Docs | 1j |
| 42 | Corriger la regex `validate_symbol` pour les tickers style `BRK.B` | Qualité Code | 30m |
| 43 | Remplacer `datetime.utcnow()` par `datetime.now(timezone.utc)` partout | Qualité Code | 1h |
| 44 | Singleton `Settings` thread-safe avec `threading.Lock` | Config | 1h |
| 45 | Ajouter le pooling de connexions IBKR dans `DataLoader` | Data | 4h |

---

## Annexe A : Carte Thermique de Risque par Fichier

| Niveau de risque | Fichiers |
|------------------|----------|
| 🔴 **Critique** | `execution/ibkr_engine.py`, `live_trading/runner.py`, `execution/paper_execution.py`, `Dockerfile` |
| 🟠 **Élevé** | `strategies/pair_trading.py` (Bonferroni), `config/settings.py` (accepte fautes), `models/model_retraining.py` (mauvaises clés), `backtester/walk_forward.py` (mauvaise clé) |
| 🟡 **Moyen** | `main.py` (fonction dieu), `execution/modes.py` (confusion enums), `risk_engine/portfolio_risk.py` (reprise auto), `models/ml_threshold_optimizer.py` (synthétique uniquement) |
| 🟢 **Sain** | `models/cointegration.py`, `pair_selection/discovery.py`, `risk_engine/kill_switch.py`, `execution/time_stop.py`, `backtests/cost_model.py`, `monitoring/slack_alerter.py` |

## Annexe B : Problèmes de Graphe de Dépendances

```
models/ml_threshold_optimizer.py  →  Utilise sklearn.ensemble.RandomForestRegressor
                                     Mais sklearn N'EST PAS dans requirements.txt ni pyproject.toml
                                     ⚠️ Dépendance manquante — l'import échouera sur une installation propre

models/markov_regime.py           →  Utilise hmmlearn.hmm.GaussianHMM
                                     Mais hmmlearn N'EST PAS dans requirements.txt ni pyproject.toml
                                     ⚠️ Dépendance manquante

monitoring/api.py                 →  Utilise flask
                                     Dans requirements.txt mais PAS dans pyproject.toml
                                     ⚠️ Déclaration de dépendance partielle
```

---

*Fin du rapport d'audit. Généré le : 25 février 2026.*
