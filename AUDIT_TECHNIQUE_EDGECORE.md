# AUDIT TECHNIQUE — EDGECORE

**Date** : 2026-03-17  
**Auditeur** : GitHub Copilot (Lead Architect Senior — systèmes de trading quantitatifs)  
**Version analysée** : sprint S4, Python 3.11.9, 354 fichiers .py hors venv  
**Tests collectés** : 2654 (référence au moment de l'audit)

---

## 1. Vue d'ensemble

### Objectif réel inféré depuis le code

Moteur d'arbitrage statistique market-neutral sur actions US longues (IBKR TWS/Gateway), déployé via Docker + docker-compose. Pipeline complet : univers → sélection de paires → signal z-score × 0.70 + momentum × 0.30 → risk check → sizing → exécution paper ou live. Backtest avec walk-forward. Observabilité Prometheus / Grafana / Elasticsearch.

### Type de système

Paper / live-capable (switch `ENABLE_LIVE_TRADING`). Pas crypto, pas CCXT (stub de test uniquement).

### Niveau de maturité

**Beta avancée / pré-production** — infrastructure solide, mais plusieurs défauts critiques bloquants avant toute mise en production avec capital réel.

### Points forts réels (max 5)

1. KillSwitch atomique, thread-safe, persisté avec backup `.bak` et fail-safe activation
2. Suite de tests dense (2654 tests, 144 fichiers, couverture par module réelle)
3. Structlog omniprésent dans les modules de production clés (risk, execution, signal)
4. Circuit-breaker IBKR avec auto-reset après 300 s, idempotence via ordre map persisté
5. Walk-forward causal via `StrategyBacktestSimulator` — fenêtre expanding, instance fraîche par période

### Signaux d'alerte globaux (max 5)

1. **B2-02 non résolu** — `LiveTradingRunner` instancie `KillSwitch` + `PortfolioRiskManager` séparément **ET** `RiskFacade` (qui crée ses propres instances internes) → deux états de risk indépendants
2. **133 `print()` dans le code de production** — main.py (30+), common/typed_api.py (8+), backtester/ — pipeline de log structuré contourné
3. **Timestamps naïfs** — `execution/base.py` ligne 43 et `persistence/audit_trail.py` lignes 69, 134, 181 utilisent `datetime.now()` sans timezone
4. **Slippage hardcodé** — `execution_engine/router.py` lignes 162 et 189 : `slippage = 2.0` — CostConfig ignoré
5. **Schemas Pydantic morts** — `config/schemas.py` définit des validateurs (entry > exit, bornes) mais le chemin de chargement réel passe par des dataclasses brutes → contraintes non appliquées

---

## 2. Architecture & design système

### Organisation réelle des modules

| Couche | Module public | Package interne | Rôle effectif |
|--------|--------------|-----------------|---------------|
| Univers | `universe/` | — | Mapping secteur + filtre liquidité |
| Sélection | `pair_selection/` | — | Tests EG, Johansen, HAC ; cache pairs |
| Signal | `signal_engine/` | `models/` | z-score × 0.70 + momentum × 0.30 |
| Risk | `risk_engine/` | `risk/` | Stops opérationnels vs logique mathématique |
| Sizing | `portfolio_engine/` | — | Kelly / VaR / fixed-fraction |
| Exécution | `execution_engine/` | `execution/` | Router PAPER/BACKTEST/LIVE → engines |
| Backtest | `backtester/` | `backtests/` | Façades haut niveau vs moteur bar-by-bar |
| Live | `live_trading/` | — | Boucle principale, reconciliation |
| Infra | `config/`, `common/`, `persistence/`, `monitoring/` | — | Config, erreurs, audit trail, métriques |

### Doublons fonctionnels identifiés

#### `execution/` vs `execution_engine/`

- `execution/` : 26 fichiers — implémentations réelles (`IBKRExecutionEngine`, `PaperExecutionEngine`, rate limiter, reconciler, shutdown manager, stops, slippage, monte carlo…)
- `execution_engine/` : 2 fichiers — `router.py` + `__init__.py`

**Problème structurel** : `execution_engine/router.py` définit `TradeOrder` (lignes 38–50) qui duplique `execution.base.Order`. Les deux types coexistent. Le router accepte les deux (`submit_order(order: TradeOrder)`, avec compatibility shim ligne 178–205) → ambiguïté de type, maintenance double.

**Verdict** : doublon confirmé. `TradeOrder` est une dette B2-01 non liquidée.

#### `risk/` vs `risk_engine/`

- `risk_engine/` (4 fichiers) : `KillSwitch`, `PositionRiskManager`, `PortfolioRiskManager`, `__init__`
- `risk/` (12 fichiers) : `RiskEngine`, `RiskFacade`, `DrawdownManager`, `VaRMonitor`, `BetaNeutral`, `FactorModel`, `KellySizing`, `PCASpreadMonitor`, `SectorExposure`, `SpreadCorrelation`

**Conception prévue** : `risk_engine/` = stops opérationnels (vérification pré-ordre rapide), `risk/` = logique mathématique avancée. `RiskFacade` devait unifier les deux.

**Problème** (B2-02) : `LiveTradingRunner._initialize()` crée **séparément** :
```python
self._position_risk = PositionRiskManager()      # instance A
self._portfolio_risk = PortfolioRiskManager(...)  # instance B
self._kill_switch = KillSwitch()                  # instance C
self._risk_facade = RiskFacade(...)               # crée ses propres D, E, F
```
Résultat : deux états de KillSwitch divergents. Si le KillSwitch de la facade s'active, `self._kill_switch` ne le sait pas, et vice versa. **Risque financier direct.**

#### `backtests/` vs `backtester/`

- `backtests/` : moteur bar-by-bar (`StrategyBacktestSimulator`), cost model, walk-forward, métriques, stress testing, event-driven
- `backtester/` : façades haut niveau (3 fichiers : `runner.py`, `walk_forward.py`, `oos.py`) qui délèguent à `backtests/`

**Verdict** : doublon intentionnel (façade pattern), acceptable architecturalement. Problème : les 3 fichiers de `backtester/` utilisent `print()` au lieu de structlog.

### Séparation stratégie / risk / exécution / monitoring

- ✅ Signal engine n'importe pas d'execution
- ✅ Risk engine indépendant de l'exécution en théorie
- ❌ `live_trading/runner.py` orchestre TOUT en un seul module de 851 lignes → God class

### Couplage et dépendances critiques

- `main.py` importe 20+ modules en direct → moindre changement de signature = régression
- `risk/engine.py` importe `monitoring/alerter.py` inline à l'intérieur d'un try/except (ligne 216) → alert failures silencieuses
- `execution/ibkr_engine.py` mélange deux bibliothèques : `ibapi.client.EClient` (IBGatewaySync class en haut) et `ib_insync.IB` (IBKRExecutionEngine class en bas) dans le **même fichier** → deux paradigmes de connexion contradictoires

### Tableau synthèse architecture

| Défaut | Sévérité | Fichier:ligne |
|--------|----------|---------------|
| Deux états KillSwitch indépendants (B2-02) | 🔴 | live_trading/runner.py:224-229 |
| TradeOrder duplique Order (B2-01) | 🟠 | execution_engine/router.py:38-50 |
| ibapi + ib_insync dans même fichier | 🟠 | execution/ibkr_engine.py:1-750 |
| LiveTradingRunner God class (851 lignes) | 🟡 | live_trading/runner.py |
| backtester/ utilise print() | 🟡 | backtester/*.py |

---

## 3. Qualité du code

### Lisibilité et cohérence

Qualité très variable selon le module. `risk_engine/kill_switch.py` et `common/circuit_breaker.py` sont exemplaires. `main.py` (961 lignes) et `risk/engine.py` (585 lignes) sont trop longs et difficiles à maintenir.

### Fonctions > 100 lignes

| Fichier | Fonction / classe | Lignes estimées |
|---------|-------------------|-----------------|
| `main.py` | module entier, CLI handler | 961 total, fonctions > 100 |
| `live_trading/runner.py` | `LiveTradingRunner` | 851 total |
| `risk/engine.py` | `can_enter_trade()` | ~150 avec duplications |
| `execution/ibkr_engine.py` | `IBKRExecutionEngine` | 750+ |
| `backtests/runner.py` | `BacktestRunner.run_unified()` | 500+ |
| `common/typed_api.py` | — | 400+ avec print() |
| `data/validators.py` | — | 396 |

### Duplication de logique

- `risk/engine.py` : vérification risk-per-trade effectuée **3 fois** dans `can_enter_trade()` (lignes ~148-153, ~184-192, ~197-209). Tout changement doit être appliqué en 3 points.
- `execution_engine/router.py` : `_simulate_fill()` (ligne 159) et le compatibility shim (ligne 178) dupliquent la même logique de calcul de fill price avec slippage hardcodé.

### Gestion des erreurs et états invalides

- `risk/engine.py` ligne 216 : les échecs `AlertManager` sont loggués mais **pas re-raise** → alerte critique silencieusement perdue
- `data/loader.py` ligne ~49 : `except Exception` large sans re-raise → masque les erreurs upstream
- `models/spread.py` : `reestimate_beta_if_needed()` appelle un tracker sans vérifier son existence → potentiel `AttributeError`

### Bare except / swallowing

- **0 bare `except:` (sans type)** dans le code de production — positif
- Plusieurs `except Exception as e: logger.xxx(...)` sans re-raise dans des chemins critiques

### Typage, validation

- mypy désactivé pour `execution.*`, `risk.*` dans `pyproject.toml` → `disallow_untyped_defs=false`
- `config/schemas.py` contient des validateurs Pydantic (entry > exit, ge/le sur z-scores) mais le pipeline de chargement utilise des dataclasses brutes → **schémas non connectés à la réalité**
- `execution/base.py` `Order` dataclass : `quantity: float` (pas de validation > 0), `order_type: str` (pas d'enum) 

### `print()` en production

**133 occurrences** dans le code hors tests et scripts :

| Fichier | Occurrences | Nature |
|---------|-------------|--------|
| `main.py` | ~30 | CLI output et diagnostics |
| `common/typed_api.py` | 8 | Debug output inline |
| `common/types.py` | 4 | Représentation |
| `common/secrets.py` | 1 | Masqué partiellement |
| `data/loader.py` | 1 | Debug residuel |
| `backtester/runner.py` | 1 | Progress report |
| `backtester/walk_forward.py` | 1 | Progress report |
| `backtester/oos.py` | 1 | Progress report |

---

## 4. Robustesse & fiabilité (TRADING-CRITICAL)

### Gestion des états incohérents dans `persistence/`

`persistence/audit_trail.py` :
- ✅ Écriture atomique via `.tmp` → rename + backup `.bak` (pattern A-10)
- ✅ `os.fsync()` avant rename
- ❌ Lignes 69, 134, 181 : `datetime.now()` **sans timezone** → timestamps naïfs dans tous les événements d'audit → comparaison avec broker UTC impossible

### Résilience aux données manquantes / corrompues

- `data/validators.py` : robuste, validation OHLCV complète avec `max_age_hours`
- `data/delisting_guard.py` : propre, détection des symboles delistés
- `data/loader.py` : en cas d'échec total, lève `DataError(ErrorCategory.RETRYABLE)` ✅ ; mais exception intermédiaire large peut masquer la cause racine

### Risques de crash silencieux

- `models/kalman_hedge.py` : `breakdown_count` incrémenté mais jamais vérifié en aval → Kalman instable continue à émettre des signaux
- `models/spread.py` : `self.half_life = None` si l'estimation échoue → le Z-score downstream peut recevoir `None` → `TypeError` non géré potentiel
- `signal_engine/generator.py` : les erreurs par paire sont catchées individuellement (✅), mais si elles sont toutes silencieuses, aucun signal n'est émis sans alerte

### Points de défaillance unique (SPOF)

1. **TWS/Gateway** : connexion unique gérée par `IBKRExecutionEngine` — si le process TWS crash, plus d'exécution. Reconnexion automatique présente mais borne à 5 échecs consécutifs.
2. **Redis** (docker-compose) : base de données de cache unique sans réplication — perte de cache = recalcul complet des paires
3. **`AuditTrail` fichier JSON** : fichier plat sur disque local — pas de réplication, pas de WAL transactionnel

### Comportement après crash mid-execution

- `execution/ibkr_engine.py` : `_load_order_map()` au démarrage pour récupérer `order_id → permId` → ✅ crash recovery sur ordres ouverts
- `live_trading/runner.py` : `_initialize()` appelle `_reconcile_with_broker()` au démarrage → ✅ sync des positions
- ❌ Si crash entre `submit_order()` et la persistence du mapping → ordre soumis au broker sans record local → doublon possible au redémarrage

### Tableau synthèse fiabilité

| Scénario | Couvert | Sévérité si non |
|----------|---------|-----------------|
| Crash TWS / reconnexion | ✅ circuit breaker + retry | — |
| Crash mid-order | ⚠️ partiel (order map persist) | 🔴 |
| Données corrompues | ✅ validators | — |
| Timestamps naïfs audit trail | ❌ | 🟠 |
| Kalman instable sans détection | ❌ | 🟠 |
| Spread half_life = None | ❌ | 🔴 |

---

## 5. Interface IBKR & exécution des ordres

### Robustesse connexion TWS/Gateway

- `IBKRExecutionEngine._ensure_connected()` : retry avec backoff exponentiel (5 s, 15 s, 30 s), 3 tentatives
- Circuit breaker : ouvre après 5 échecs consécutifs, auto-reset après 300 s (A-11) ✅
- `IBGatewaySync` (ibapi sync wrapper) et `IBKRExecutionEngine` (ib_insync) coexistent dans `ibkr_engine.py` → architecture ambiguë

### Rate limiting (50 req/s)

- `execution/rate_limiter.py` : `TokenBucketRateLimiter(rate=45, burst=10)` ✅ module-level singleton `_ibkr_rate_limiter`
- `execution/ibkr_engine.py` : `_ibkr_rate_limiter.acquire()` documenté et référencé ✅
- ❌ `backtests/runner.py` : utilise `_time.sleep(0.5)` figé entre appels historiques — **pas** `_ibkr_rate_limiter.acquire()` → lors de backtests intensifs sur IB réel, déconnexion possible

### Idempotence des ordres

- `IBKRExecutionEngine._persisted_order_ids` : mapping `order_id → permId` persisté en JSON ✅
- Vérification de `client_id` unique via registre de classe `_active_client_ids` ✅
- ❌ Fenêtre de race entre `submit_order()` et `_save_order_map()` (non atomique) : si crash entre les deux, ordre soumis deux fois au redémarrage

### Gestion des ordres partiellement exécutés

- `OrderStatus.PARTIAL` et `PARTIALLY_FILLED` définis dans `execution/base.py` ✅
- `live_trading/runner.py` : suivi `status="pending_close"` jusqu'à confirmation de fill ✅
- Réconciliation toutes les 5 min via `BrokerReconciler` ✅

### Séparation paper vs live

- Switch via `ENABLE_LIVE_TRADING=false` → force `use_sandbox=True` dans settings ✅
- `ExecutionRouter` route vers `PaperExecutionEngine` ou `IBKRExecutionEngine` selon mode ✅
- `ccxt_engine.py` : stub de test uniquement (pas d'appels réels) ✅ — mais son existence en production peut induire en erreur

### Risque de double-soumission

- ❌ Fenêtre non atomique entre soumission et persistence de l'order map
- ❌ Absence de verrou applicatif au niveau `submit_order()` si plusieurs threads appelants

### Tableau synthèse IBKR

| Critère | État | Notes |
|---------|------|-------|
| Reconnexion auto | ✅ | Circuit breaker + retry |
| Rate limit 50 req/s | ⚠️ | Manquant dans backtest runner |
| Idempotence ordres | ⚠️ | Race window non atomique |
| Ordres partiels | ✅ | PARTIAL status + reconciliation |
| Séparation paper/live | ✅ | Switch configurable |
| Double soumission | ⚠️ | Possible après crash mid-persist |

---

## 6. Risk management & capital protection

### Existence d'un moteur de risque indépendant

`risk_engine/` : checks opérationnels (fast path, pré-ordre)  
`risk/` : logique mathématique (VaR, DrawdownManager, KellySizing...)  
`risk/facade.py` : composition KillSwitch + RiskEngine → API unifiée `can_enter_trade()`

**Problème critique (B2-02)** : `LiveTradingRunner` n'utilise pas `RiskFacade` comme point unique — il crée ET des instances séparées ET une `RiskFacade` supplémentaire. Deux états divergent immédiatement après le premier trade.

### Les 6 conditions de halt du KillSwitch

| Condition | Implémentée | Vérifiée pré-ordre | Persistée |
|-----------|-------------|--------------------|-----------| 
| Drawdown max | ✅ | ✅ (via check()) | ✅ (JSON + .bak) |
| Daily loss max | ✅ | ✅ | ✅ |
| Pertes consécutives | ✅ | ✅ | ✅ |
| Data staleness | ✅ | ✅ | ✅ |
| Volatility spike | ✅ | ✅ | ✅ |
| Manuel | ✅ | ✅ | ✅ |
| **Cohérence B2-02** | ❌ | ❌ | N/A |

Toutes les conditions sont implémentées **sur l'instance correcte**. Le problème est que `LiveTradingRunner` vérifie `self._kill_switch` (instance C) mais `RiskFacade` en a une différente (instance F).

### Scénarios de perte non contrôlés

- Si `self._kill_switch` (ligne 228) s'active mais que les ordres passent via `self._risk_facade` → halte non interceptée
- `DrawdownManager` Tier 4 (12%) : latch permanent — mais s'il est dans `RiskFacade`, `self._portfolio_risk` continue à permettre des ouvertures

### Concentration limits

- `risk/engine.py` : vérification sector/position concentration **dans `can_enter_trade()`** → pré-ordre ✅
- `execution/concentration_limits.py` : contrôle additionnel côté exécution ✅

### Beta-neutral hedging

- `risk/beta_neutral.py` : calcul dynamique du net beta portfolio — présent en tant que moniteur
- Le sizing effectif (hedge ratio) vient du modèle Kalman → **dynamique** ✅
- Mais si Kalman breakdown non détecté (cf. section 4), le hedge ratio est faux sans alerte

### Niveau de danger pour capital réel

**ÉLEVÉ**. Le B2-02 seul suffit à invalider la mise en production. Si `RiskFacade` et les instances directes de `LiveTradingRunner` divergent, le KillSwitch peut être actif sur l'une et pas l'autre. Des trades peuvent s'exécuter après un halt.

---

## 7. Intégrité statistique du backtest

### Biais look-ahead dans `backtests/` et `backtester/`

- `backtests/strategy_simulator.py` : simulation bar-by-bar causale ✅ — fenêtre glissante sur données passées uniquement
- `backtests/walk_forward.py` : expanding window, split IS/OOS strict ✅
- ❌ `backtests/runner.py` ligne 417 : méthode legacy `run()` avec **biais look-ahead documenté (C-02)** toujours présente et accessible — `DeprecationWarning` émis mais méthode non supprimée

### Kalman filter causal

- `models/kalman_hedge.py` : filtre Kalman forward uniquement — pas de RTS smoother ✅
- Warm-up : état initial posé sur la **première barre** (`beta = y/x` ligne ~125) sans période de chauffe → instable si première barre est un outlier

### Cohérence backtest ↔ live

- `StrategyBacktestSimulator` appelle les mêmes fonctions de modèle (`SpreadModel`, `SignalCombiner`, `CostModel`) que le live ✅
- ❌ `execution_engine/router.py` en backtest mode utilise `slippage = 2.0` hardcodé (B5-02) alors que le live utilise l'IBKR fill réel → coûts divergent entre modes

### Modèle de coûts

`backtests/cost_model.py` :
- ✅ 4-leg accounting (2 entrées + 2 sorties)
- ✅ Borrow fee journalier pour la jambe courte
- ✅ 3 modèles d'impact : fixe, volume-adaptive, Almgren-Chriss
- ❌ Borrow cost fixé à 0.5% par défaut — taux réel IBKR variable par symbole (peut être 2–10%)
- ❌ Slippage déterministe (pas de distribution) → pas de stress test sur slippage adverse

### Walk-forward IS/OOS

- `backtester/walk_forward.py` : 3 critères de validation : ≥50% périodes rentables, Sharpe OOS ≥ 0, max drawdown OOS ≤ seuil ✅
- Nouvelle instance `PairTradingStrategy` par période → pas de contamination d'état ✅
- ❌ Aucune vérification que les hyperparamètres ne sont pas optimisés sur l'OOS global → risque de data snooping sur le choix du modèle global

### Biais de survie dans `universe/`

- `universe/manager.py` : mapping statique de ~200 large-caps US
- ❌ Pas de gestion des entrées/sorties d'indices — les symboles présents en 2026 qui n'existaient pas ou étaient différents en 2020 ne sont pas exclus des backtests → biais de survie possible

### Tableau synthèse backtest

| Critère | État | Notes |
|---------|------|-------|
| Simulation causale | ✅ | StrategyBacktestSimulator |
| Kalman forward-only | ✅ | Pas de RTS |
| Biais look-ahead | ⚠️ | Legacy run() encore présent |
| IS/OOS contamination | ✅ | Expanding window |
| Modèle de coûts | ⚠️ | Borrow fixe, slippage déterministe |
| Biais de survie | ❌ | Univers statique |
| Cohérence backtest/live | ❌ | Slippage divergent (B5-02) |

---

## 8. Sécurité

### Gestion des credentials IBKR

- Credentials lus depuis variables d'environnement (`os.getenv("IBKR_HOST", ...)`) ✅
- `.env.example` avec placeholders explicites `REPLACE_WITH_YOUR_*` ✅
- `common/secrets.py` : présent, gère le masquage

### Risques d'exposition dans logs / config / env

- ❌ `common/typed_api.py` (8 `print()`) et `main.py` (30+ `print()`) : des données de configuration et d'état peuvent fuir vers stdout, contournant la rotation et le masquage structlog
- ❌ `monitoring/slack_alerter.py` : `webhook_url` accepté comme paramètre de constructeur (pas uniquement lu depuis env) → risque de passage accidentel en dur dans le code
- `config/prod.yaml` : `use_sandbox: false` — correct pour prod, mais si déployé avec env wrong, trades réels déclenchés

### Dockerfile et docker-compose

- ✅ `EDGECORE_ENV=prod` dans Dockerfile (correct, le bug B5-01 n'est **pas** présent)
- ✅ Utilisateur non-root (`appuser UID 1000`)
- ✅ Multi-stage build
- ❌ `docker-compose.yml` ligne 114 : `GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-admin}` → mot de passe Grafana par défaut "admin" si variable non définie
- ❌ `docker-compose.yml` ligne 139 : `xpack.security.enabled=false` sur Elasticsearch → aucune authentification sur port 9200
- ❌ `docker-compose.yml` : `GF_SECURITY_COOKIE_SECURE: "false"` → cookies Grafana transmis en HTTP clair

### `config/.env.example`

- `ENVIRONMENT=production` (ligne 1) — incohérent avec la nomenclature interne `EDGECORE_ENV=prod`

### Tableau synthèse sécurité

| Risque | Sévérité | Statut |
|--------|----------|--------|
| Credentials IBKR exposés | — | ✅ Env vars |
| Grafana default "admin" | 🟠 | ❌ Non sécurisé |
| Elasticsearch sans auth | 🟠 | ❌ Non sécurisé |
| print() fuites stdout | 🟡 | ❌ 133 occurrences |
| Webhook Slack en param | 🟡 | ⚠️ Partiel |
| Docker env correct | — | ✅ prod (non production) |
| Conteneur non-root | — | ✅ |

---

## 9. Tests & validation

### Présence et qualité des 2654 tests

- **2654 tests collectés** (confirmé via `pytest --co`)
- 144 fichiers de tests dans 18 sous-répertoires
- Couverture fonctionnelle par module vérifiée sur les modules clés

### Couverture approximative par module

| Module | Couverture estimée | Notes |
|--------|--------------------|-------|
| `risk_engine/` | ✅ Élevée | KillSwitch crash recovery, fail-safe testé |
| `execution/` | ✅ Bonne | Order lifecycle, paper mode, rate limiter |
| `execution_engine/` | ✅ Bonne | Router, fill simulation, token bucket |
| `backtests/` | ✅ Bonne | Métriques, walk-forward, cost model |
| `models/` | ✅ Bonne | Cointegration, Kalman, spread |
| `signal_engine/` | ✅ Bonne | Combiner, generator |
| `persistence/` | ✅ Excellente | Crash recovery, `.bak`, JSON corruption |
| `live_trading/` | ⚠️ Partielle | État de la machine correcte, mais pas crash mid-order |
| `monitoring/` | ⚠️ Partielle | Dashboard, pas les alertes Slack/email en intégration |
| `data/` | ✅ Bonne | Validators, delisting, preprocessing |

### Parties non testées critiques

- Comportement KillSwitch B2-02 : deux instances divergentes — **aucun test** qui instancie `LiveTradingRunner` et vérifie la cohérence entre `self._kill_switch` et `self._risk_facade._kill_switch`
- Crash entre `submit_order()` et `_save_order_map()` — non testé
- Comportement si `spread.half_life = None` → downstream crash
- Backtest via legacy `run()` avec look-ahead — aucun test vérifiant l'absence de biais

### Tests IBKR : mocks ou appels réels ?

- ✅ Tous les tests utilisent des mocks / engines simulés — aucun appel TWS réel
- `IBKRExecutionEngine` testé via interface abstraite uniquement

### Niveau de confiance avant production

**Moyen** — La couverture est dense mais ne teste pas le scénario B2-02 ni les edge cases de crash mid-order. Les tests passent sur la logique correcte ; la défaillance est dans l'orchestration.

---

## 10. Observabilité & maintenance

### Qualité du logging

- Modules de production principaux (`risk_engine/`, `execution/ibkr_engine.py`, `signal_engine/`, `data/`) : structlog JSON ✅
- ❌ `main.py` (30+ `print()`), `backtester/` (3 `print()`), `common/typed_api.py` (8 `print()`) : stdout non structuré, non capturé par le pipeline logs

### Alerting

- `monitoring/slack_alerter.py` : webhook Slack, throttle par catégorie, retry ✅
- `monitoring/email_alerter.py` : SMTP avec auth via env ✅
- Événements déclencheurs confirmés : KillSwitch activation, drawdown tier, order fill failure
- ❌ Pas d'alerte sur la divergence des deux instances de KillSwitch (B2-02) — impossible à détecter sans instrumentation dédiée
- ❌ `reset_throttle()` dans `SlackAlerter` sans contrôle d'accès → peut masquer des alertes répétées

### Capacité de diagnostic live

- Prometheus metrics ✅
- Grafana dashboards ✅
- Elasticsearch + Kibana pour logs ✅
- `monitoring/api.py` : endpoint `/api/dashboard` avec `@require_api_key` ✅
- Mais si l'incident implique deux états de risk divergents, les métriques des deux instances ne sont **pas** séparément exposées → invisible dans le dashboard

### Maintenabilité 6–12 mois

- `scripts/` : 47 fichiers, dont `ARCHIVED_benchmark_cpp_acceleration.py`, `ARCHIVED_setup_cpp_acceleration.py` — résidus C++ à supprimer
- `docs/archived/CMakeLists.txt` — résidu inoffensif mais bruit
- `results/debug_counters.txt` — résidu debug
- 47 scripts sans structure claire → risque de régression par erreur de script

---

## 11. Dette technique

### Liste précise des dettes

| ID | Dette | Fichier:ligne | Danger |
|----|-------|---------------|--------|
| B2-01 | `TradeOrder` duplique `Order` | execution_engine/router.py:38-50 | 🟠 Maintenance |
| B2-02 | Double instanciation KillSwitch + RiskFacade | live_trading/runner.py:224-229 | 🔴 **BLOQUANT** |
| B5-01 | `EDGECORE_ENV=production` | Dockerfile | ✅ RÉSOLU (`prod` présent) |
| B5-02 | `slippage = 2.0` hardcodé | execution_engine/router.py:162,189 | 🟠 Coût divergent |
| C-02 | Legacy `run()` avec look-ahead | backtests/runner.py:417 | 🟠 Biais backtest |
| C-03 | Timestamps naïfs (sans TZ) | execution/base.py:43, persistence/audit_trail.py:69,134,181 | 🟠 Timeout errors |
| C-04 | `print()` en production | main.py, common/, backtester/ | 🟡 Log pollution |
| C-05 | Schemas Pydantic non connectés | config/schemas.py vs settings.py | 🟡 Validation morte |
| C-06 | Bonferroni dead code | models/cointegration.py | 🟠 Paires mal filtrées |
| C-07 | Kalman breakdown non remonté | models/kalman_hedge.py:176-184 | 🟠 Hedge ratio faux |
| C-08 | `spread.half_life = None` non géré | models/spread.py | 🔴 TypeError silencieux |
| C-09 | Spread models cachés indéfiniment | signal_engine/generator.py:143 | 🟡 Memory leak |
| C-10 | Cython fallback silencieux | models/cointegration.py:17-24 | 🟡 Perf cliff |
| C-11 | Rate limit absent dans backtest runner | backtests/runner.py:217-240 | 🟠 IBKR disconnect |
| C-12 | Biais de survie univers statique | universe/manager.py | 🟠 Backtest biais |
| C-13 | Grafana default "admin" | docker-compose.yml:114 | 🟠 Sécurité |
| C-14 | Elasticsearch sans auth | docker-compose.yml:139 | 🟠 Sécurité |
| C-15 | risk/engine.py triple vérification | risk/engine.py:148-209 | 🟡 Maintenance |
| C-16 | ibapi + ib_insync dans même fichier | execution/ibkr_engine.py | 🟡 Architecture |

### Dette acceptable à court terme

C-04, C-09, C-10, C-15, C-16 — qualité et performance, pas de risque financier direct.

### Dette dangereuse (risque de régression)

C-06, C-07, C-08, C-11, C-12 — silencieux, peuvent créer de mauvais trades ou de mauvais backtests sans alerte visible.

### Dette bloquante pour toute évolution sérieuse

**B2-02 (C-08 secondaire)** — impossible d'ajouter un second symbole universel ou un second worker sans résoudre la double instanciation du risk manager. Toute refactorisation de `LiveTradingRunner` doit résoudre B2-02 en priorité ou le risque s'amplifie.

---

## 12. Recommandations priorisées

### Top 5 actions immédiates (ordre strict)

1. **[BLOQUANT 🔴]** Résoudre B2-02 : injecter `position_risk`, `portfolio_risk`, `kill_switch` créés en amont dans `RiskFacade`, et utiliser `self._risk_facade` comme **unique** interface dans `LiveTradingRunner`. Supprimer les 3 `self._position_risk`, `self._portfolio_risk`, `self._kill_switch` séparés.

2. **[CRITIQUE 🔴]** Corriger les timestamps naïfs :
   - `execution/base.py:43` → `datetime.now(timezone.utc)`
   - `persistence/audit_trail.py:69,134,181` → `datetime.now(timezone.utc)`

3. **[CRITIQUE 🔴]** Corriger `models/spread.py` : ajouter un guard sur `self.half_life` avant tout appel downstream ; lever une exception explicite si `None` plutôt que passer silencieusement un `None` à `compute_z_score`.

4. **[MAJEUR 🟠]** Corriger B5-02 : `execution_engine/router.py` lignes 162 et 189 — lire `get_settings().costs.slippage_bps` au lieu de `slippage = 2.0`.

5. **[MAJEUR 🟠]** Ajouter `_ibkr_rate_limiter.acquire()` dans `backtests/runner.py` avant chaque appel `get_historical_data()` — remplacer le `_time.sleep(0.5)` figé.

### Actions à moyen terme

- Supprimer la méthode legacy `BacktestRunner.run()` (C-02) — ne garder que `run_unified()`
- Connecter `config/schemas.py` au pipeline de chargement dataclass — ou supprimer les schemas inutilisés
- Corriger le Bonferroni dans `models/cointegration.py` : appliquer la correction ou supprimer le paramètre
- Remonter le `breakdown_count` Kalman via une métrique Prometheus ou lever une alerte
- Gestion dynamique de l'univers (entrées/sorties d'indices) pour éliminer le biais de survie
- Sécuriser docker-compose : forcer `GRAFANA_PASSWORD`, activer `xpack.security`, passer `GF_SECURITY_COOKIE_SECURE=true`
- Remplacer tous les `print()` dans `main.py`, `common/typed_api.py`, `backtester/` par structlog

### Actions optionnelles / confort

- Fusionner `execution_engine/router.py` avec `execution/` et supprimer `TradeOrder` (B2-01)
- Séparer `execution/ibkr_engine.py` en deux fichiers (`ibkr_sync_gateway.py` + `ibkr_insync_engine.py`)
- Ajouter TTL ou LRU sur le cache де `signal_engine/generator.py._spread_models`
- Nettoyer `scripts/ARCHIVED_*`, `results/debug_counters.txt`, `docs/archived/CMakeLists.txt`
- Activer mypy sur `execution.*` et `risk.*` progressivement

---

## 13. Score final

### Score global : **5.2 / 10**

Justification : infrastructure correcte (structlog, KillSwitch atomique, circuit breaker IBKR, 2654 tests), mais 2 défauts critiques non résolus (B2-02 et timestamps naïfs) suffisent à invalider la production. La dette technique connue n'est pas liquidée malgré les sprints avancés.

### Score détaillé par dimension

| Dimension | Score /10 | Justification |
|-----------|-----------|---------------|
| Architecture | **4** | 6 doublons de module, B2-02 non résolu, God class LiveTradingRunner 851 lignes |
| Robustesse IBKR | **6** | Circuit breaker ✅, idempotence ⚠️, rate limit manquant en backtest |
| Risk management | **5** | KillSwitch ✅, B2-02 crée 2 états divergents → invalidant |
| Intégrité backtest | **5** | Simulateur causal ✅, biais survie ❌, slippage divergent ❌, legacy run() ❌ |
| Sécurité | **5** | Secrets env ✅, Grafana default admin ❌, ES sans auth ❌, print() leaks ❌ |
| Tests | **8** | 2654 tests denses, B2-02 non couvert |
| Observabilité | **6** | Stack complète ✅, print() contourne pipeline structlog |

### Probabilité de succès si état inchangé

< 30 % en production sustained. Un premier incident majeur (drawdown brutal, crash TWS) va révéler la divergence B2-02, et le halt ne sera pas cohérent.

### Verdict final

> 👉 **Ne peut pas trader de l'argent réel dans cet état.**
>
> La double instanciation du KillSwitch (B2-02) rend le risk management incohérent : le halt peut s'activer sur une instance et pas l'autre, permettant des trades après un signal d'arrêt. Les timestamps naïfs sur les ordres rendent la détection de timeout non fiable versus l'horloge UTC du broker. Ces deux défauts à eux seuls suffisent à disqualifier toute mise en production avec capital réel.
