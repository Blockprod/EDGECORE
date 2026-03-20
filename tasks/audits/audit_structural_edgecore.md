---
projet: EDGECORE
type: audit-structurel
date: 2026-03-20
modele: claude-sonnet-4.6
---

# AUDIT STRUCTUREL — EDGECORE
# Date : 2026-03-20

---

## BLOC 1 — PIPELINE RÉEL

### Chemin complet source → ordre IBKR

```
IBKR TWS / IB Gateway (port 4002)
  ↓
data/loader.py (DataLoader.load_ibkr_data / load_price_data)
  └─ execution/ibkr_engine.py (IBGatewaySync) ← appel IBKR reqHistoricalData
  └─ data/validators.py (OHLCVValidator) ← validation 12 checks OHLCV
  └─ data/cache/ (parquet) ← mise en cache locale
  ↓
universe/manager.py (UniverseManager)
  └─ data/liquidity_filter.py (LiquidityFilter)
  └─ data/delisting_guard.py (DelistingGuard)
  └─ data/event_filter.py (EventFilter) ← blackout earnings
  └─ universe/correlation_prefilter.py (pre-filtre correlation)
  ↓
[optionnel] data/multi_timeframe.py (MultiTimeframeEngine)
  └─ resample daily → weekly (W-FRI)
  └─ weekly cointegration + MTF score
  ↓
pair_selection/discovery.py (PairDiscoveryEngine)
  └─ models/cointegration.py (engle_granger_test)
      └─ models/cointegration_fast.cp311-win_amd64.pyd (Cython, fallback Python)
  └─ models/johansen.py (Johansen double-screening confirmation)
  └─ pair_selection/filters.py (filtres post-test)
  └─ pair_selection/blacklist.py (paires blacklistees)
  └─ cache/pairs/ (cache JSON des paires decouvertes)
  ↓
signal_engine/generator.py (SignalGenerator)
  └─ models/spread.py (SpreadModel ← hedge ratio OLS / Kalman)
  └─ models/kalman_hedge.py (KalmanHedgeEstimator)
  └─ signal_engine/zscore.py (ZScoreCalculator)
  └─ signal_engine/adaptive.py (AdaptiveThresholdEngine)
  └─ signal_engine/momentum.py (MomentumOverlay)
  └─ signal_engine/combiner.py (SignalCombiner — z×0.70 + mom×0.30)
  └─ models/regime_detector.py (RegimeDetector ← VolatilityRegime)
  └─ models/stationarity_monitor.py (rolling ADF guard)
  ↓
risk_engine/position_risk.py (PositionRiskManager)
  └─ execution/trailing_stop.py (TrailingStopManager)
  └─ execution/time_stop.py (TimeStopManager)
  └─ models/hedge_ratio_tracker.py
risk_engine/portfolio_risk.py (PortfolioRiskManager)
risk_engine/kill_switch.py (KillSwitch) ← persiste etat (data/kill_switch_state.bak)
risk/facade.py (RiskFacade ← compose risk.engine + kill_switch)
  └─ risk/engine.py (RiskEngine ← per-trade checks)
  └─ risk/drawdown_manager.py / beta_neutral.py / factor_model.py
  ↓
portfolio_engine/allocator.py (PortfolioAllocator)
  ↓
execution_engine/router.py (ExecutionRouter — BACKTEST / PAPER / LIVE)
  ├─ [BACKTEST] → simulation via CostConfig
  ├─ [PAPER]    → execution/paper_execution.py (PaperExecutionEngine)
  └─ [LIVE]     → execution/ibkr_engine.py (IBKRExecutionEngine)
                   └─ execution/rate_limiter.py (TokenBucketRateLimiter 45req/s)
  ↓
execution/reconciler.py (BrokerReconciler) ← toutes les 5 min
persistence/audit_trail.py (AuditTrail) ← crash recovery

ORCHESTRATEUR : live_trading/runner.py (LiveTradingRunner)
```

### Comparaison avec pipeline declare (9 modules)

| Module declare         | Module reel                      | Statut    |
|------------------------|----------------------------------|-----------|
| UniverseManager        | universe/manager.py              | OK aligne |
| PairDiscoveryEngine    | pair_selection/discovery.py      | OK aligne |
| SignalGenerator        | signal_engine/generator.py       | OK aligne |
| PositionRiskManager    | risk_engine/position_risk.py     | OK aligne |
| PortfolioRiskManager   | risk_engine/portfolio_risk.py    | OK aligne |
| KillSwitch             | risk_engine/kill_switch.py       | OK aligne |
| PortfolioAllocator     | portfolio_engine/allocator.py    | OK aligne |
| ExecutionRouter        | execution_engine/router.py       | OK aligne |
| IBKRExecutionEngine    | execution/ibkr_engine.py         | OK aligne |
| —                      | risk/facade.py (RiskFacade)      | NON DECLARE — s'intercale entre risk_engine et PortfolioAllocator |
| —                      | data/multi_timeframe.py          | NON DECLARE — filtre MTF entre universe et pair_selection |
| —                      | execution/reconciler.py          | NON DECLARE — boucle de reconciliation post-execution |

---

## BLOC 2 — DOUBLONS FONCTIONNELS

### 2.1 execution/ vs execution_engine/

| Aspect | execution/ | execution_engine/ |
|--------|-----------|-------------------|
| Fichiers | 24 modules | 2 fichiers (router.py + __init__.py) |
| Type Order | `execution/base.py::Order` (single source of truth) | `execution_engine/router.py::TradeOrder` (deprecated, B2-01) |
| Type OrderStatus | `execution/base.py::OrderStatus` (11 etats) | — |
| **Troisieme doublon** | `execution/modes.py::Order` + `OrderStatus` **(868 lignes!)** | — |

**Probleme cle :** `execution/modes.py` definit en ligne 44-65 une troisieme classe `Order` et un troisieme `OrderStatus` (6 etats, incomplet vs 11 dans base.py). Le commentaire sur `OrderStatus` dit "delegates to execution.base.OrderStatus values" mais les valeurs sont **redefines localement**, pas importees. Risque de desynchronisation silencieuse.

Fichiers : `execution/modes.py:27-65`, `execution/base.py:1-40`, `execution_engine/router.py:42-67`

### 2.2 risk/ vs risk_engine/

| Module | risk/ | risk_engine/ |
|--------|-------|--------------|
| Responsabilite | Math risque + facade | Controles operationnels en boucle |
| risk/engine.py | RiskEngine (per-trade checks, stop-loss, drawdown) | — |
| risk/facade.py | RiskFacade (unifie RiskEngine + KillSwitch) | — |
| risk_engine/position_risk.py | — | PositionRiskManager (trailing stop, time stop, hedge drift) |
| risk_engine/portfolio_risk.py | — | PortfolioRiskManager (drawdown, heat, consecutive losses) |
| risk_engine/kill_switch.py | — | KillSwitch (halt global) |

**Probleme cle (B2-02) :** `live_trading/runner.py._initialize()` instancie `PositionRiskManager`, `PortfolioRiskManager`, `KillSwitch` **ET** `RiskFacade` separement. La `RiskFacade` etait censee unifier tout cela. Resultat : deux instances de `KillSwitch` potentiellement actives avec des etats divergents.

Fichiers : `live_trading/runner.py:195-230`, `risk/facade.py:54-80`

**Overlap** : `risk/engine.py::RiskEngine` et `risk_engine/portfolio_risk.py::PortfolioRiskManager` gerent tous deux le drawdown portfolio — logique dupliquee sans SRP clair.

### 2.3 backtests/ vs backtester/

| Couche | backtests/ | backtester/ |
|--------|-----------|-------------|
| Role | Implementations reelles | Facades haut niveau |
| runner.py | BacktestRunner (logique reelle) | BacktestEngine (wraps BacktestRunner) |
| walk_forward.py | WalkForwardBacktester (logique reelle) | WalkForwardEngine (wraps WalkForwardBacktester) |
| oos.py | — | OOSValidationEngine |

Architecture intentionnelle mais peu documentee : `backtester/` offre une API clean pour les callers externes, `backtests/` contient la logique. **A verifier** : qui appelle directement `backtests/runner.py` vs `backtester/runner.py` ?

### 2.4 models/ vs strategies/

Pas de duplication fonctionnelle reelle — separation claire :
- `models/` : maths statistiques pures (cointegration, spread, Kalman, johansen)
- `strategies/` : logique de decision (quand entrer/sortir)

`strategies/pair_trading.py` importe massivement depuis `models/` et `signal_engine/` — c'est un **God Object**, pas un doublon (voir BLOC 3).

### 2.5 edgecore/ — wrappers C++ devenus passthrough

`edgecore/cointegration_engine_wrapper.py` : wrappait une extension C++ (`cointegration_cpp.cp313-win_amd64.pyd`). Appelle maintenant directement `models/cointegration.engle_granger_test_cpp_optimized` en Python pur. Le `.pyd` Python 3.13 dans ce dossier est un artefact residuel — le projet cible Python 3.11.

`edgecore/backtest_engine_wrapper.py` : implementation backtest standalone entierement redondante avec `backtests/strategy_simulator.py`. N'est probablement plus appele.

Fichiers : `edgecore/cointegration_engine_wrapper.py:1-100`, `edgecore/backtest_engine_wrapper.py:1-134`

---

## BLOC 3 — SEPARATION DES RESPONSABILITES

### 3.1 Violations SRP majeures

**`strategies/pair_trading.py` — 1 102 lignes**
- Decouverte de paires (test cointegration, stabilite sur fenetres multiples)
- Calcul spread, hedge ratio, z-score
- Gestion des trades actifs (`active_trades` dict)
- Regime de vol (regime detection inline)
- Signaux de sortie (z-score stop, P&L stop, trailing stop)
- Import de 12+ modules (signal_engine.*, models.*, strategies.base)

Fichiers : `strategies/pair_trading.py:1-1102`

**`backtests/strategy_simulator.py` — 1 609 lignes (God class)**
- Simulation bar-par-bar
- Gestion des ordres (entry, exit, sizing)
- Gestion du risque (drawdown inline, position caps)
- Modele de couts
- Pair discovery inline (au lieu de deleguer a pair_selection/)
- Metriques de performance
- Reporting

Fichiers : `backtests/strategy_simulator.py:1-1609`

**`execution/modes.py` — 868 lignes**
- Definit `ExecutionEngine` (ligne 817) — classe qui orchestre tout
- Contient plusieurs `ExecutionMode` abstracts et concretes (Paper, Live, Backtest)
- Redefiit `Order` et `OrderStatus` (doublons de execution/base.py)
- Represente une architecture parallele entiere non utilisee par le pipeline principal

Fichiers : `execution/modes.py:1-868`

**`live_trading/runner.py` — 761 lignes**
- Initialise TOUS les modules (universe, pairs, signals, risk, allocator, router)
- Boucle de tick (1 min)
- Alerting (email + slack)
- Gestion shutdown
- Reconciliation

Acceptable pour un orchestrateur, mais `_tick()` fait trop : universe refresh + pair rediscovery + signal gen + risk checks + execution + monitoring en une seule methode.

### 3.2 Fonctions > 100 lignes (estimations)

| Fichier | Methode candidate | Estimation |
|---------|-------------------|-----------|
| `backtests/strategy_simulator.py` | methode `run()` | ~400+ lignes |
| `strategies/pair_trading.py` | `find_cointegrated_pairs_parallel()` | ~200 lignes |
| `data/loader.py` | `bulk_load()` | ~130 lignes (avec bug doublon) |
| `execution/modes.py` | classe `ExecutionEngine` entiere | ~50 methodes |
| `live_trading/runner.py` | `_initialize()` + `_tick()` | ~100 lignes chacune |

### 3.3 research/ importe depuis la production ?

**Non pour les modules de production critiques.** Deux cas limites :
- `examples/examples_pair_discovery.py:7` — `from research.pair_discovery import screen_pairs`
- `scripts/phase4_validation.py:379` — `from research.pair_discovery import CointegrationAnalyzer`

Fichiers : `examples/examples_pair_discovery.py:7`, `scripts/phase4_validation.py:379`

### 3.4 config/Settings — global ou injecte ?

`get_settings()` est un singleton global. Acces **direct** via `get_settings()` dans presque tous les modules (non injecte). Acceptable pour ce type de projet, mais rend les tests plus fragiles (le singleton est partage entre tests).

### 3.5 Dependances circulaires

Aucune detectee via grep. La note dans `persistence/audit_trail.py:26` signale une definition "locale pour eviter les imports circulaires" — a surveiller.

### 3.6 Points d'extension (ABC / Protocol)

| Interface | Statut |
|-----------|--------|
| `execution/base.py::BaseExecutionEngine` | OK — ABC avec @abstractmethod |
| `strategies/base.py::BaseStrategy` | OK — ABC avec @abstractmethod |
| `execution/modes.py` ExecutionModeBase | OK — ABC (dans le module parallele) |
| SignalGenerator, RiskFacade, PortfolioAllocator | AVERTISSEMENT — Classes concretes, pas de Protocol |
| PairDiscoveryEngine | AVERTISSEMENT — Classe concrete, pas de Protocol |

---

## BLOC 4 — DETTE TECHNIQUE

### 4.1 Bug P0 — Double ThreadPoolExecutor dans bulk_load

`data/loader.py` : la methode `bulk_load()` contient **deux blocs** `with ThreadPoolExecutor(...)` identiques. Le premier s'execute et les resultats sont collectes dans `worker_results` mais pas persistes dans `results`. La variable `completed` est ensuite remise a 0. Le second bloc re-execute exactement le meme travail et persiste les resultats.

**Impact operationnel :** chaque appel a `bulk_load()` declenche **2x les appels IBKR** pour tous les symboles non caches — double consommation du rate limit (45 req/s), temps d'execution double, risque de deconnexion TWS.

Fichiers : `data/loader.py:310-385` (zone approximative des deux ThreadPoolExecutor)

### 4.2 Bug P0 — Debug file ecriture systematique en production

`data/loader.py` : a chaque appel `bulk_load()`, le code ecrit un fichier `debug_bulk_to_fetch_snapshot.txt` a la racine du projet. Ce fichier est un artefact de debug qui ne doit pas etre en production.

Fichiers : `data/loader.py:~297-310`

### 4.3 execution/modes.py — 3eme OrderStatus incomplet

`execution/modes.py:27-40` : `OrderStatus` redefini avec 6 etats (`PENDING, SUBMITTED, FILLED, PARTIALLY_FILLED, CANCELLED, FAILED`) vs 11 dans `execution/base.py` (`+ PARTIAL, TIMEOUT, ERROR, UNKNOWN, REJECTED`). Le commentaire dit "delegates to execution.base.OrderStatus values" — **ce n'est pas le cas** : les valeurs sont string literals redefinis localement.

Fichiers : `execution/modes.py:27-40`, `execution/base.py:13-23`

### 4.4 edgecore/ — artefacts C++ obsoletes

- `edgecore/backtest_engine_cpp.cp313-win_amd64.pyd` : extension compilee Python 3.13, projet cible 3.11
- `edgecore/cointegration_cpp.cp313-win_amd64.pyd` : idem
- `edgecore/backtest_engine_wrapper.py` : 134 lignes de wrapper devenu pure-Python fallback — doublon de `backtests/strategy_simulator.py`
- `edgecore/cointegration_engine_wrapper.py` : appelle desormais directement `models/cointegration.engle_granger_test_cpp_optimized`

Ces fichiers sont des residus de l'ancienne architecture C++/pybind11/CMake. Aucun module de production n'importe depuis `edgecore/` (A VERIFIER).

Fichiers : `edgecore/__init__.py`, `edgecore/backtest_engine_wrapper.py`, `edgecore/cointegration_engine_wrapper.py`

### 4.5 setup.py vs pyproject.toml — versions incoherentes

- `setup.py:30` : `version='0.1.0'`
- `pyproject.toml:7` : `version = "1.0.0"`

Deux sources de verite pour la version du package. `setup.py` est le vrai outil de build Cython (indispensable). `pyproject.toml` definit les metadonnees projet et les dependances. Les deux coexistent mais de facon non synchronisee.

Fichiers : `setup.py:30`, `pyproject.toml:7`

### 4.6 ibkr_invalid_symbols.txt a la racine

Fichier non reference dans le code Python (verifie par grep). Artefact manuel genere lors de passes de validation symboles IBKR. Devrait etre archive a `data/audit/` ou ignore via `.gitignore`.

Fichiers : `ibkr_invalid_symbols.txt` (racine)

### 4.7 kill_switch_state.bak dans data/

`data/kill_switch_state.bak` : fichier d'etat persiste du KillSwitch. Se trouve dans `data/` au lieu de `persistence/` ou `data/audit/`. Incoherence avec `persistence/audit_trail.py`.

Fichiers : `data/kill_switch_state.bak`

### 4.8 Scripts de debug dans scripts/

Scripts dont le role est flou par rapport aux tests formels :
- `scripts/diag.py`, `scripts/diagnose_backtest.py`, `scripts/diagnose_backtest_v2.py`
- `scripts/quick_test.py`, `scripts/test_bt.py`
- `scripts/ARCHIVED_benchmark_cpp_acceleration.py`, `scripts/ARCHIVED_setup_cpp_acceleration.py`
- `scripts/test_config_environments.py`, `scripts/test_hot_reload.py` — tests dans scripts/ au lieu de tests/

---

## BLOC 5 — CONFIGURATION ET ENVIRONNEMENTS

### 5.1 Incoherence slippage backtest vs paper

- Backtest path (`_simulate_fill`) : `get_settings().costs.slippage_bps` → **3.0 bps** (CostConfig)
- Paper path (`_paper_fill`) : `get_settings().execution.slippage_bps` → **2.0 bps** (ExecutionConfig)

Ces deux valeurs ne sont pas synchronisees. Un backtest calibre sur 3.0 bps trade en paper a 2.0 bps → resultats de paper optimistes vs backtest.

Fichiers : `execution_engine/router.py:181` (costs.slippage_bps), `execution_engine/router.py:211` (execution.slippage_bps), `config/settings.py:~155` (CostConfig), `config/settings.py:~220` (ExecutionConfig)

### 5.2 test.yaml — exit_z_score: 0.0

`config/test.yaml:18` : `exit_z_score: 0.0`. Valeur problematique (la moyenne flottante d'un spread ne touche jamais exactement 0.0 → sorties impossibles). Issue connue documentee, non corrigee.

Fichiers : `config/test.yaml:18`

### 5.3 Debordement de config entre schemas.py et settings.py

`config/schemas.py` (508 lignes) contient des classes Pydantic (`RiskConfigSchema`, `StrategyConfigSchema`, etc.) qui dupliquent partiellement les dataclasses de `config/settings.py`. La validation Pydantic n'est appliquee que partiellement dans `Settings._validate_config()` (deux schemas sur les 6 definis). Les autres schemas (`ExecutionConfigSchema`, `DataSourceConfigSchema`, etc.) ne sont jamais utilises dans le runtime.

Fichiers : `config/settings.py:265-290`, `config/schemas.py:1-508`

### 5.4 config.yaml — section racine non utilisee

Un fichier `config/config.yaml` existe. Il n'est pas charge par `Settings._load_yaml()` — seuls `dev.yaml`, `test.yaml`, `prod.yaml` sont charges. Risque de confusion.

Fichiers : `config/config.yaml`

### 5.5 Dockerfile et docker-compose — EDGECORE_ENV correctement configure

- `Dockerfile:38` : `EDGECORE_ENV=prod` (bug B5-01 corrige)
- `docker-compose.yml:11` : `EDGECORE_ENV: prod`

### 5.6 Dockerfile — multi-stage build

Dockerfile utilise un multi-stage build (`debian:bookworm-slim AS builder` + stage production). Multi-stage build securise.

### 5.7 docker-compose.yml — absence de service test isole

`docker-compose.yml` definit : `trading-engine`, `redis`, `prometheus`, `grafana`, `elasticsearch`, `kibana`. Aucun service `test` ou `sandbox` isole. Les tests CI s'executent sans Docker (via pytest direct).

---

## SYNTHESE

### Tableau des problemes

| ID | Bloc | Probleme | Fichier:Ligne | Severite | Impact | Effort |
|----|------|----------|---------------|----------|--------|--------|
| S-01 | 4 | `bulk_load` double ThreadPoolExecutor — 2x appels IBKR | `data/loader.py:~310-385` | **P0** | Rate limit, cout, perf | Faible |
| S-02 | 4 | Debug file (`debug_bulk_to_fetch_snapshot.txt`) ecrit en prod | `data/loader.py:~297` | **P0** | Ecriture disque inutile | Tres faible |
| S-03 | 2 | `execution/modes.py` 3eme `Order` + `OrderStatus` incomplet (868 lignes) | `execution/modes.py:27-65` | **P1** | Desynchronisation silencieuse OrderStatus | Moyen |
| S-04 | 2 | `TradeOrder` toujours present (B2-01), callers non migres | `execution_engine/router.py:42-67` | **P1** | Maintenance duale, confusion API | Moyen |
| S-05 | 2 | `LiveTradingRunner` instancie risk_engine/ ET RiskFacade separement (B2-02) | `live_trading/runner.py:195-230` | **P1** | Etat KillSwitch potentiellement divergent en live | Moyen |
| S-06 | 3 | `strategies/pair_trading.py` 1 102 lignes — God Object | `strategies/pair_trading.py:1-1102` | **P1** | Non testable unitairement, couplage fort | Eleve |
| S-07 | 3 | `backtests/strategy_simulator.py` 1 609 lignes — God Class | `backtests/strategy_simulator.py:1-1609` | **P1** | Impossible a paralleliser/etendre | Eleve |
| S-08 | 4 | `edgecore/` — wrappers C++ devenus passthrough, .pyd Python 3.13 | `edgecore/*.pyd` | **P1** | Confusion, poids inutile, mauvaise version | Faible |
| S-09 | 5 | Slippage backtest (3.0 bps) != paper (2.0 bps) | `execution_engine/router.py:181,211` | **P1** | Resultats paper optimistes vs backtest | Tres faible |
| S-10 | 5 | `config/schemas.py` — 4 schemas Pydantic jamais utilises en runtime | `config/schemas.py:170-508` | **P2** | Code mort, fausse securite de validation | Faible |
| S-11 | 5 | `test.yaml` exit_z_score=0.0 (sorties impossibles) | `config/test.yaml:18` | **P2** | Tests sur parametre defectueux | Tres faible |
| S-12 | 4 | `setup.py` version 0.1.0 vs `pyproject.toml` version 1.0.0 | `setup.py:30`, `pyproject.toml:7` | **P2** | Incoherence package metadata | Tres faible |
| S-13 | 3 | `research/` importe depuis `scripts/phase4_validation.py` | `scripts/phase4_validation.py:379` | **P2** | Dependance prod→research | Tres faible |
| S-14 | 3 | `execution/modes.py` — architecture parallele entiere non alignee | `execution/modes.py:817` | **P2** | Dead code 868 lignes | Moyen |
| S-15 | 4 | `ibkr_invalid_symbols.txt` non reference a la racine | `ibkr_invalid_symbols.txt` | **P3** | Pollution repo | Tres faible |
| S-16 | 4 | `data/kill_switch_state.bak` dans data/ au lieu de persistence/ | `data/kill_switch_state.bak` | **P3** | Incoherence architecturale | Tres faible |
| S-17 | 4 | Scripts debug/test dans scripts/ au lieu de tests/ | `scripts/diag.py`, `scripts/test_bt.py`... | **P3** | Confusion organisation | Tres faible |
| S-18 | 5 | `config/config.yaml` non charge mais present | `config/config.yaml` | **P3** | Confusion configuration | Tres faible |

**Legende :** P0 = critique prod P1 = bloquant scalabilite P2 = dette qualite P3 = cosmetique
**Effort :** Tres faible=< 1h Faible=1-4h Moyen=4-16h Eleve=16h+

### Schema textuel du pipeline reel (vue simplifiee)

```
[IBKR TWS:4002]
      | reqHistoricalData (IBGatewaySync)
[data/loader.py] → cache parquet
      | DataLoader.bulk_load (AVERTISSEMENT: double TP bug)
[universe/manager.py] ← liquidity_filter · delisting_guard · event_filter
      | symboles actifs
[pair_selection/discovery.py] ← cointegration_fast.pyd (Cython) · johansen · MTF
      | paires (sym1, sym2, pvalue, half_life, mtf_score)
[signal_engine/generator.py] ← spread · zscore · adaptive · momentum · combiner
      | Signal(pair_key, side, strength, z_score, regime)
[risk_engine/] ← position_risk · portfolio_risk · kill_switch
[risk/facade.py]
      | can_enter=True
[portfolio_engine/allocator.py]
      | TradeOrder / Order
[execution_engine/router.py] -PAPER→ [execution/paper_execution.py]
                              -LIVE→  [execution/ibkr_engine.py]
                              -BACK→  [cost_model simulation]
      |
[execution/reconciler.py] (t+5min)
[persistence/audit_trail.py]

ORCHESTRATEUR : live_trading/runner.py
```

### Graphe des dependances entre modules publics

```
config  ←──────────────────────── TOUS LES MODULES
data    ──→ execution (ibkr_engine)
universe ──→ data
pair_selection ──→ data · universe · models
models  ←────────── pair_selection · signal_engine · backtests · strategies
signal_engine ──→ models · config
risk_engine ──→ execution (trailing_stop, time_stop) · models
risk     ──→ risk_engine (kill_switch) · persistence · monitoring · common
portfolio_engine ──→ config · risk
execution_engine ──→ execution · config
live_trading ──→ ALL (orchestrateur)
backtests ──→ models · data · strategies · execution_engine · config
backtester ──→ backtests (thin facade)
edgecore  ──→ models (passthrough)   [a supprimer]
```

### Top 3 problemes structurels bloquant la scalabilite

**1. God classes non decomposables (S-06, S-07)**
`backtests/strategy_simulator.py` (1 609 lignes) et `strategies/pair_trading.py` (1 102 lignes) sont des God classes qui melangent discovery, signaling, risk et execution. Impossible d'ajouter une strategie sans toucher a ces fichiers. Impossible de paralleliser le deploiement de strategies multiples.

**2. Trois definitions de `Order` / `OrderStatus` incompatibles (S-03, S-04)**
`execution/base.py` (canonique), `execution_engine/router.py::TradeOrder` (deprecated), `execution/modes.py::Order` (parallele, OrderStatus incomplet). Toute nouvelle fonctionnalite d'execution oblige a choisir — et le mauvais choix cree des bugs silencieux.

**3. Risk engine splitte sans unification reelle (S-05)**
`RiskFacade` existe pour unifier `risk/` et `risk_engine/` mais `LiveTradingRunner` instancie les deux familles separement. En live trading, deux instances independantes de `KillSwitch` peuvent avoir des etats contradictoires (`is_active` divergent) — l'une bloque, l'autre non.

### Points solides a conserver

- **`risk_engine/kill_switch.py`** : SRP exemplaire, thread-safe avec `threading.Lock`, persistance d'etat, callbacks configurables, `KillReason` enum clair.
- **`config/settings.py`** : Singleton bien concu avec `_assert_risk_tier_coherence()` au demarrage, rejection des sections YAML inconnues, multi-env via `EDGECORE_ENV`.
- **`execution_engine/router.py`** : Routage mode-agnostique propre, `TokenBucketRateLimiter` IBKR integre, compatibilite `TradeOrder` + `Order` geree gracieusement.
- **`models/cointegration.py`** : Fallback Cython→Python transparent, utilitaires statistiques complets (EG, Johansen, Newey-West, Bonferroni).
- **`signal_engine/generator.py`** : Pipeline unifie backtest=live, composants clairement separes (zscore, adaptive, momentum, combiner).
- **`execution/base.py`** : ABC propre avec interface contractuelle claire pour tous les moteurs d'execution.
- **Dockerfile** : Multi-stage build securise, non-root user, `EDGECORE_ENV=prod` corrige (B5-01 resolu).

---

*Audit genere le 2026-03-20 — modele claude-sonnet-4.6*
*Perimetre : structure uniquement (pas securite, pas strategie quantitative)*
