# EDGECORE — Roadmap correctifs vers production IBKR

**TL;DR** : 7 P0 bloquants doivent être corrigés avant tout test paper trading. La correction la plus critique (S-2 : unification signal path backtest/live) invalide rétrospectivement toutes les métriques backtest actuelles — il faudra les recalculer. L'ordre des phases respecte les dépendances techniques : aucun correctif de Phase 1 ne peut être validé sans les fixes de Phase 0, et le paper trading ne peut démarrer sans les tests de Phase 3. Architecture estimée : **~130h de dev + 4 semaines paper** = go-live en **semaine 9-10**.

---

## Phase 0 — Corrections d'urgence, aucune dépendance (Sem. 1)

**Critère de passage** : tous les tests unitaires existants passent en CI après ces corrections. Aucune régression.

| ID | Problème | Fichier | Correction | Effort |
|----|---------|---------|------------|--------|
| E-2 | `OrderSide` enum en minuscules → 100% des ordres IBKR rejetés | `execution/ibkr_engine.py` | Ajouter `.upper()` sur `order.side.value` avant envoi à ib_insync, ou corriger les valeurs de l'enum | **1h** |
| R-1 | `KillSwitch` avale silencieusement les erreurs de persistence | `risk_engine/kill_switch.py` | Transformer le `try/except` de persistence en `fatal()` — si l'état ne peut être sauvegardé, déclencher un halt immédiat | **2h** |
| S-5 | `Bonferroni=False` dans `PairTradingStrategy` → ~61 paires fantômes sur 1225 tests | `strategies/pair_trading.py` | Passer `apply_bonferroni=True` dans `find_cointegrated_pairs()` | **0.5h** |
| S-6 | Walk-forward clé `per_period_results` vs `per_period_metrics` → crash silencieux | `backtester/walk_forward.py` | Aligner les noms de clés entre `WalkForwardEngine` et le runner de backtest | **1h** |
| E-7 | `signal.SIGUSR1` inexistant sur Windows → crash au démarrage | `live_trading/` | Ajouter `if hasattr(signal, 'SIGUSR1')` avant l'enregistrement. Utiliser `signal.SIGBREAK` comme fallback Windows | **0.5h** |
| T-5 | `PairDiscoveryEngine` fail-open sur exception NW-HAC/Johansen → paires invalides acceptées | `pair_selection/discovery.py` | Inverser : `except Exception → continue` (rejeter la paire si un test de confirmation échoue) | **2h** |
| R-8 | `exit_z_score = 0.0` par défaut → whipsaw systématique au mean-crossing | Config YAML | Changer la valeur par défaut à `0.3` dans `config/config.yaml` | **0.5h** |

**Total Phase 0 : ~7.5h**

---

## Phase 1 — Correctifs P0 structurels (Sem. 1–2)

**Dépendance** : Phase 0 complète.  
**Critère de passage** : (1) le mode paper tourne sans connexion TWS. (2) un backtest complet s'exécute via le pipeline live. (3) les trailing stops déclenchent dans les tests unitaires.

### 1-A : Découpler `PaperExecutionEngine` du code live `[E-6]` — 6h

**Problème** : `execution/paper_execution.py` hérite de `IBKRExecutionEngine`. Le `__init__` parent peut établir une connexion live.

**Correction** :
- Faire hériter `PaperExecutionEngine` de `BaseExecutionEngine` (`execution/base.py`) directement
- Implémenter un fill synthétique interne : à la soumission d'un ordre, simuler un fill au `limit_price` après 1 tick
- Supprimer tout import `ib_insync` de `execution/paper_execution.py`
- **Validation** : lancer `PaperExecutionEngine` sans TWS running → doit se démarrer. Injecter un ordre → doit produire un fill simulé dans les 5s.

### 1-B : Unifier le signal path backtest = live `[S-2]` — 16h

**Problème** : `backtests/strategy_simulator.py` réimplémente la génération de signal indépendamment de `strategies/pair_trading.py`.

**Correction** :
- Dans `StrategyBacktestSimulator`, remplacer le signal generation interne par un appel direct à `PairTradingStrategy.generate_signals(price_data=bar_slice)` qui prend les données en paramètre (voir 1-C ci-dessous)
- Injecter un `clock` factice retournant le timestamp de la barre courante (pour corriger E-5 simultanément)
- **Dépend de** : 1-C (injection des données)

**Validation statistique** :
1. Lancer le backtest **avant** (code actuel) → capturer : Sharpe, max DD, win rate
2. Lancer le backtest **après** unification → capturer les mêmes métriques
3. **Une dégradation des métriques est attendue et souhaitable** — elle mesure l'écart entre le backtest optimiste et la réalité
4. Si dégradation > 50% du Sharpe : approfondir l'analyse (la stratégie peut être non-profitable dans sa config actuelle)
5. Vérifier sur au moins 3 paires que les signaux d'entrée/sortie sont identiques entre le runner backtest et un run paper sur les mêmes données historiques

### 1-C : Injecter les données dans `generate_signals()` `[T-3]` — 4h

**Problème** : `strategies/pair_trading.py` charge les données en interne, rendant l'unification 1-B impossible.

**Correction** :
- Ajouter le paramètre `price_data: Optional[pd.DataFrame] = None` à `generate_signals()`
- Si `price_data is None` : utiliser le `DataLoader` interne (comportement live)
- Si `price_data` est fourni : utiliser directement (comportement backtest)

### 1-D : Câbler `TrailingStopManager` + `HedgeRatioTracker` `[F-5, R-7]` — 6h

**Problème** : Ces objets sont initialisés dans `strategies/pair_trading.py` mais leurs méthodes ne sont jamais appelées dans `generate_signals()`.

**Correction** :
- Ajouter dans la boucle de gestion des positions ouvertes : `self.trailing_stop_manager.check_stops(pair, current_spread, current_time)`
- Ajouter dans la boucle de mise à jour : `self.hedge_ratio_tracker.reestimate_beta_if_needed(pair, prices)`
- Ajouter test unitaire vérifiant qu'un trailing stop se déclenche après dégradation de `max_adverse_excursion`

### 1-E : Implémenter `LiveTradingRunner._tick()` `[E-9]` — 12h

**Problème** : `live_trading/runner.py` — `_tick()` est vide ou stub.

**Correction** :
- Implémenter `_tick()` avec le flow : fetch latest bar → `generate_signals()` → `RiskEngine.can_enter_trade()` → `ExecutionRouter.submit()` → `AuditTrail.log()`
- Réutiliser exactement la même séquence que `run_paper_trading()` dans `main.py`, mais via injection de dépendances
- **Validation** : lancer `LiveTradingRunner` en mode paper (après 1-A) et vérifier que le journal d'audit est alimenté correctement

**Total Phase 1 : ~38h**

---

## Phase 2 — Correctifs P1 Exécution & Risque (Sem. 2–3)

**Dépendance** : Phase 1-A (paper découplé) et Phase 1-B (backtest unifié).  
**Critère de passage** : les corrections sont couvertes par des tests unitaires (même minimes). Le backtest re-calibré montre un Sharpe OOS > 0.4 sur au moins 2 paires.

| ID | Problème | Fichier | Correction | Effort |
|----|---------|---------|------------|--------|
| S-1 | `engle_granger_test()` normalise les prix → β incorrect | `models/cointegration.py` | Supprimer la normalisation z-score avant l'OLS. L'ADF sur résidus est scale-invariant | **3h** |
| S-8 | `volume_24h=1e9` par défaut → impact de marché nul en backtest | `backtests/cost_model.py` | Supprimer la valeur par défaut ; lever `ValueError` si volume absent. Alimenter depuis `LiquidityFilter` | **4h** |
| E-1 | Exceptions génériques dans `submit_order()` → erreurs IBKR masquées | `execution/ibkr_engine.py` | Mapper les exceptions `ib_insync` vers des types internes : `MarginError`, `ContractNotFoundError`, `RateLimitError`, `NetworkError` | **6h** |
| E-3 | Pas de rate limiting → risque de rejet en masse par IBKR (50 req/s) | `execution_engine/router.py` | Implémenter un `TokenBucketRateLimiter(rate=45, burst=10)`. Injecter dans l'`ExecutionRouter` | **6h** |
| E-4 | Ordres non idempotents → double position en cas de retry réseau | `execution/ibkr_engine.py` | Générer un `client_order_id` déterministe : `sha256(symbol + side + epoch_10min_bucket)[:8]`. Vérifier l'existence avant soumission | **6h** |
| E-8 | `BrokerReconciler` jamais appelé → état diverge après crash | `execution/reconciler.py` | Appeler `BrokerReconciler.reconcile()` dans le `__init__` de `LiveTradingRunner` et `run_paper_trading()`, avant d'entrer dans la boucle | **3h** |
| R-4 | `quantity=10.0` hardcodé dans `main.py` → sizing sans rapport avec le risque | `main.py` | Remplacer par `PortfolioAllocator.compute_position_size(equity, pair_volatility, risk_per_trade=0.005)` | **5h** |
| R-5 | `RegimeDetector` reçoit un scalaire au lieu d'une série temporelle | `strategies/pair_trading.py` | Passer `spread.iloc[-60:]` (rolling window de 60 barres) au lieu de `spread.iloc[-1]` | **2h** |
| T-4 | `except Exception: pass` dans les workers per-pair → exceptions silencieuses | `strategies/pair_trading.py` | Remplacer par : `except Exception as e: logger.error(pair=pair, exc_info=e); self._error_counter.increment()`. Déclencher une alerte si `error_counter > 5` | **4h** |
| S-3 | Half-life utilise la moyenne full-sample pour centrer le spread | `models/cointegration.py` | Remplacer `spread.mean()` par `spread[:-1].mean()` dans `estimate_half_life()` | **1h** |

**Validation statistique Phase 2** :
- Après S-1 + S-8 : relancer le backtest unifié (Phase 1-B) → comparer à nouveau les métriques. Les coûts réalistes devraient réduire le Sharpe de 15-35% sur les paires illiquides.
- Critère objectif : le modèle de coûts sur une paire test doit produire un coût total entre 5-15 bps par aller-retour (fourchette IBKR réaliste).

**Total Phase 2 : ~40h**

---

## Phase 3 — Couverture de tests des modules critiques (Sem. 3–4)

**Dépendance** : Phases 1 et 2 complètes (les modules doivent être stables avant de les tester).  
**Critère de passage** : couverture ≥ 80% sur les 4 modules listés. Tous les cas limites documentés dans l'audit ont un test dédié.

| Module | Tests à créer | Cas limites prioritaires | Effort |
|--------|--------------|--------------------------|--------|
| `risk_engine/kill_switch.py` | ~15 tests | (1) halt déclenché + persistence échoue → comportement fatal. (2) redémarrage avec état "halted" → pas de trading. (3) chaque condition de halt en isolation. (4) halt sur drawdown simultané + perte journalière | **6h** |
| `signal_engine/generator.py` | ~20 tests | (1) données NaN dans la série de prix → erreur typée, pas de signal émis. (2) paire non coïntégrée → aucun signal malgré z-score extrême. (3) Bonferroni réduit correctement les paires. (4) biais look-ahead : le signal à t ne doit pas utiliser de données à t+1 | **8h** |
| `execution_engine/router.py` | ~12 tests | (1) mode paper route vers `PaperExecutionEngine` uniquement. (2) retry avec backoff sur `NetworkError`. (3) rate limiter bloque au-delà de 45 req/s. (4) client_order_id idempotent sur deux soumissions identiques | **6h** |
| `portfolio_engine/allocator.py` | ~10 tests | (1) sizing avec equity = 0 → exception, pas de division par zéro. (2) concentration limit bloque la 9e position. (3) beta-neutral rebalance ne crée pas d'exposition nette | **5h** |

**Total Phase 3 : ~25h**

**Gate de sortie Phase 3** → validation binaire avant paper trading :
- [ ] `pytest tests/` passe à 100% (zéro échec)
- [ ] Couverture kill_switch ≥ 80%, signal_engine ≥ 80%
- [ ] Test anti-leak : vérifier qu'aucun signal à la barre `t` ne dépend d'une valeur calculée sur `[t+1..T]`
- [ ] Test de non-régression backtest : Sharpe avant/après Phase 3 identique (les tests ne modifient pas le comportement)

---

## Phase 4 — Validation Paper Trading IBKR (Sem. 5–8, 4 semaines)

**Dépendance** : Phases 0, 1, 2, 3 complètes. Connexion TWS/Gateway en mode paper account IBKR.

### Configuration du run paper

- **Durée** : 4 semaines calendaires (20 jours de marché)
- **Universe** : 20-30 symboles US liquides (même univers que prévu en production)
- **Capital simulé** : utiliser la même taille qu'en production prévue
- **Environnement** : `config/prod.yaml` avec flag `paper_mode: true`

### Critères de monitoring continus (quotidiens)

| Métriques à surveiller | Seuil d'alerte | Action |
|----------------------|---------------|--------|
| Nombre d'erreurs IBKR par session | > 5/jour | Investiguer avant le lendemain |
| Fills partiels non gérés | > 0 | Investigation immédiate |
| Divergence état interne vs IBKR (après réconciliation) | > 0 position | STOP paper trading |
| Ratio signal généré / ordre soumis | < 0.9 | Bug dans le routing |
| Kill-switch déclenché | N'importe | Log complet + analyse cause |
| `datetime.now()` warnings dans logs | > 0 | Bug de clock (E-5) |

### Critères Go/No-Go capital réel (à évaluer en fin de semaine 8)

**GO si toutes les conditions sont vraies :**
- [ ] 0 crash non-récupéré sur 20 jours
- [ ] 0 ordre dupliqué ou exécution accidentelle
- [ ] Réconciliation IBKR propre à chaque redémarrage
- [ ] P&L paper positif OU conforme à la distribution attendue du backtest corrigé (± 1.5σ)
- [ ] Kill-switch s'est déclenché ET a arrêté correctement sur au moins un test manuel
- [ ] Monitoring Slack/alertes fonctionnel sur AU MOINS un incident simulé
- [ ] Trailing stops ont déclenché sur au moins 1 paire en 4 semaines

**NO-GO (retour Phase 2) si :**
- Récurrence d'ordres dupliqués
- État persisté corrompu après 1+ crash
- P&L paper > 3σ en dessous du backtest corrigé (signal path probablement encore divergent)

---

## Phase 5 — Durcissement P2 (Sem. 8–9, en parallèle fin paper trading)

**Dépendance** : Phases 1-3 stables. Peut être commencée en semaine 8 pendant que le paper trading se termine.

| ID | Problème | Fichier | Correction | Effort |
|----|---------|---------|------------|--------|
| F-7 | Constantes hardcodées dans `run_paper_trading()` | `main.py` | Déplacer `max_consecutive_errors`, `max_attempts`, `limit_price * 0.99` vers section `trading:` dans `config/config.yaml` | **4h** |
| F-8 | Typos dans YAML acceptées silencieusement (fallback sans erreur) | `config/settings.py` | À la fin du `__init__` du Settings singleton, valider que toutes les clés YAML sont des champs connus du dataclass. `raise ConfigError` sinon | **4h** |
| R-2 | Auto-resume après circuit-breaker drawdown sans vérification | `risk_engine/portfolio_risk.py` | Remplacer la reprise automatique par une condition : volatilité réalisée doit avoir baissé de 20% par rapport au niveau lors du déclenchement | **3h** |
| R-3 | Seuils de risque dupliqués dans strategy (10 pos, 10% DD) et risk engine (10 pos, 2% DD) | `strategies/pair_trading.py` + `risk/engine.py` | Supprimer les vérifications dans `PairTradingStrategy`. `RiskEngine` devient l'unique autorité. Ajouter assertion au démarrage que les seuils config sont cohérents | **8h** |
| E-5 | `datetime.now()` dans la stratégie → timestamps incorrects en backtest | `strategies/pair_trading.py` | Injecter un `Clock` protocol : `BacktestClock(bar_time)` vs `LiveClock()`. Remplacer tous les appels `datetime.now()` par `self.clock.now()` | **6h** |
| R-6 | `SpreadCorrelationGuard` seuil ρ=0.60 trop permissif | `risk/spread_correlation.py` | Abaisser à `rho_max=0.40` dans `config/config.yaml` | **0.5h** |

**Total Phase 5 : ~26h**

---

## Phase 6 — Mise en production capital réel (Sem. 9–10)

**Dépendance** : Phase 4 go/no-go VALIDÉ + Phase 5 complète.

### Séquence de déploiement

**Semaine 9 — Préparation :**
- Basculer `config/prod.yaml` : `paper_mode: false`, `live_mode: true`
- Audit final des seuils de risque dans le YAML prod
- Test manuel : soumettre 1 ordre de test (1 action) → vérifier fill + réconciliation → annuler
- Vérifier que `LiveTradingRunner._tick()` (Phase 1-E) est testé en conditions réelles minimales

**Semaine 10 — Go-live progressif :**

| Étape | Action | Condition de continuation |
|-------|--------|--------------------------|
| J1–J5 | 10% du capital cible, 2 paires max | 0 incident P0. P&L dans ±2σ du paper |
| J6–J10 | 25% du capital, 5 paires max | Même critères |
| J11–J20 | 50% du capital, nombre de paires selon config | Sharpe hebdomadaire > 0 sur 2 semaines consécutives |
| J21+ | 100% du capital | Validation mensuelle par walk-forward OOS glissant |

---

## Backlog P3 — Refactorings post-go-live (Sans date cible fixe)

Ces corrections n'impactent pas la sécurité financière mais sont nécessaires pour la maintenabilité à long terme.

| ID | Problème | Effort | Trigger recommandé |
|----|---------|--------|-------------------|
| F-1 | `PairTradingStrategy` god class | **3j** | Avant d'ajouter une nouvelle stratégie |
| F-2 | `run_paper_trading()` god function | **2j** | Lors de la prochaine refonte de `main.py` |
| F-3 | Dual risk subsystem (`risk/` vs `risk_engine/`) | **2j** | Lors de l'ajout d'un nouveau type de risque |
| F-4 | Dual execution subsystem + 3 enums `OrderStatus` | **3j** | Lors de l'ajout d'un nouveau broker |
| S-4 | Câbler le Kalman filter en mode causal | **2j** | Après validation que EG+OLS β est insuffisant |

---

## Synthèse du plan

```
Semaine 1      [Phase 0 + Phase 1]   ~45.5h   Blocants éliminés, backtest unifié
Semaine 2      [Phase 1 suite]       ~20h     Paper mode sécurisé, live runner opérationnel
Semaine 2-3    [Phase 2]             ~40h     Exécution robuste, sizing correct, coûts réalistes
Semaine 3-4    [Phase 3]             ~25h     Tests sur modules critiques
─────────────────────────────────────────────────────────────────────────────────
Semaine 5-8    [Phase 4]             4 semaines   Paper trading IBKR + go/no-go
─────────────────────────────────────────────────────────────────────────────────
Semaine 8-9    [Phase 5]             ~26h     Durcissement P2
Semaine 9-10   [Phase 6]             go-live  Capital réel progressif
─────────────────────────────────────────────────────────────────────────────────
Post live      [Backlog P3]          ~10j     Refactorings sans urgence
```

**Effort dev total** : ~130h (~16 jours à 8h/j) + 4 semaines paper (monitoring, pas dev).  
**Risque résiduel au go-live** : P0 tous résolus. P1 tous résolus. P2 durcis. Le seul risque résiduel connu est l'absence de refactoring P3 (maintenabilité, pas sécurité financière).

---

## Tableau de suivi des corrections

| ID | Phase | Statut | Date début | Date fin | Validé par |
|----|-------|--------|------------|----------|------------|
| E-2 | 0 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| R-1 | 0 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| S-5 | 0 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| S-6 | 0 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| E-7 | 0 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| T-5 | 0 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| R-8 | 0 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| E-6 | 1-A | ✅ Terminé | — | 2026-02-25 | Audit auto |
| S-2 | 1-B | ✅ Terminé | — | 2026-02-25 | Audit auto |
| T-3 | 1-C | ✅ Terminé | — | 2026-02-25 | Audit auto |
| F-5 | 1-D | ✅ Terminé | — | 2026-02-25 | Audit auto |
| R-7 | 1-D | ✅ Terminé | — | 2026-02-25 | Audit auto |
| E-9 | 1-E | ✅ Terminé | — | 2026-02-25 | Audit auto |
| S-1 | 2 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| S-8 | 2 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| E-1 | 2 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| E-3 | 2 | ✅ Terminé | 2026-02-26 | 2026-02-26 | rate_limiter.py créé + tests |
| E-4 | 2 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| E-8 | 2 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| R-4 | 2 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| R-5 | 2 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| T-4 | 2 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| S-3 | 2 | ✅ Terminé | — | 2026-02-25 | Audit auto |
| Tests kill_switch | 3 | ✅ Terminé | 2026-02-26 | 2026-02-26 | 6 tests, 104/104 pass |
| Tests signal_engine | 3 | ✅ Terminé | 2026-02-26 | 2026-02-26 | 4 tests, 104/104 pass |
| Tests router | 3 | ✅ Terminé | 2026-02-26 | 2026-02-26 | 6 tests, 104/104 pass |
| Tests allocator | 3 | ✅ Terminé | 2026-02-26 | 2026-02-26 | 5 tests + equity guard |
| Paper trading | 4 | ⬜ Opérationnel | — | — | Infra prête, 4 sem. requis |
| F-7 | 5 | ✅ Terminé | 2026-03-03 | 2026-03-03 | TradingConfig + 8 refs main.py |
| F-8 | 5 | ✅ Terminé | 2026-03-03 | 2026-03-03 | Top-level + TU validation |
| R-2 | 5 | ✅ BY DESIGN | — | 2026-03-03 | manual_reset() only |
| R-3 | 5 | ✅ Terminé | 2026-03-03 | 2026-03-03 | Tier coherence assertion |
| E-5 | 5 | ✅ DÉJÀ FIXÉ | — | 2026-03-03 | ClockFn injectable |
| R-6 | 5 | ✅ Terminé | 2026-03-03 | 2026-03-03 | ρ 0.70→0.40 + YAML |
| Go-live | 6 | ✅ Prêt | 2026-03-03 | 2026-03-03 | prod.yaml audité + preflight |
| F-1 | P3 | ⬜ Backlog | — | — | — |
| F-2 | P3 | ⬜ Backlog | — | — | — |
| F-3 | P3 | ⬜ Backlog | — | — | — |
| F-4 | P3 | ⬜ Backlog | — | — | — |
| S-4 | P3 | ⬜ Backlog | — | — | — |

> **Légende** : ⬜ À faire · 🔄 En cours · ✅ Terminé · ❌ Bloqué