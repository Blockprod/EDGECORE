# EDGECORE — System Design

*Dernière mise à jour : 2026-03-20*

---

## 1. Vue d'ensemble

EDGECORE est un système de **statistical arbitrage** automatisé sur actions US.  
Stratégie : **mean-reversion sur paires cointégrées** (spread z-score ± 2.0 σ).

| Dimension | Valeur |
|-----------|--------|
| Marché cible | US Equities (NYSE, NASDAQ) via IBKR |
| Mode d'opération | Intraday + overnight; pas d'options ni de futures |
| Cadence principale | Every 5 min (scan) + 1 min (tick risk) |
| Instruments | Paires d'actions ; short via IBKR shortable shares |
| Broker | Interactive Brokers TWS / Gateway |
| Environnements | `dev` / `test` / `prod` (env var `EDGECORE_ENV`) |

---

## 2. Architecture des composants

```
┌─────────────────────────────────────────────────────────────────────┐
│  DATA LAYER                                                         │
│  data/loader.py (IBKR reqHistoricalData + Yahoo Finance fallback)   │
│  data/intraday_loader.py (tick/1-min streaming)                     │
│  data/liquidity_filter.py (ADV, bid-ask spread)                     │
│  data/preprocessing.py (forward-fill, outlier clip)                 │
│  data/multi_timeframe.py (daily ↔ intraday alignment)               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ DataFrame OHLCV (cols=symbols)
┌───────────────────────────────▼─────────────────────────────────────┐
│  UNIVERSE LAYER                                                      │
│  universe/UniverseManager (liquidity screen, S&P500 subset)         │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ List[Symbol]
┌───────────────────────────────▼─────────────────────────────────────┐
│  PAIR SELECTION LAYER                                                │
│  pair_selection/PairDiscoveryEngine                                  │
│  → Triple-gate : EG (ADF) + Johansen + HAC (HAC-adjusted t-stat)    │
│  → Kalman hedge ratio (models/kalman_hedge.py)                       │
│  → Résultats mis en cache (cache/pairs/)                             │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ List[PairCandidate]
┌───────────────────────────────▼─────────────────────────────────────┐
│  SIGNAL LAYER                                                        │
│  signal_engine/SignalGenerator  → z-score (EG spread)               │
│  signal_engine/SignalCombiner   → composite = z×0.70 + momentum×0.30│
└───────────────────────────────┬─────────────────────────────────────┘
                                │ Signal (entry / exit / stop)
┌───────────────────────────────▼─────────────────────────────────────┐
│  RISK LAYER (3 tiers)                                                │
│  Tier 1 : risk_engine/PositionRiskManager  → stop si drawdown > 10% │
│  Tier 2 : risk_engine/KillSwitch           → halt global si > 15%   │
│  Tier 3 : strategies/pair_trading.py       → breaker interne > 20%  │
│  risk/RiskFacade (wrapper unifié)                                    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ Approved Order
┌───────────────────────────────▼─────────────────────────────────────┐
│  SIZING LAYER                                                        │
│  portfolio_engine/PortfolioAllocator                                 │
│  → heat ≤ 95%, risk_per_trade = 0.5%, max_concurrent = 10           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ execution.base.Order
┌───────────────────────────────▼─────────────────────────────────────┐
│  EXECUTION LAYER                                                     │
│  execution_engine/ExecutionRouter → route vers PAPER / LIVE / BT    │
│  execution/IBKRExecutionEngine   → TWS via ib_insync (prod)         │
│  execution/PaperExecutionEngine  → simulation fill (paper)          │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ filled Trade
┌───────────────────────────────▼─────────────────────────────────────┐
│  PERSISTENCE / MONITORING                                            │
│  persistence/AuditTrail  → JSON crash-recovery                      │
│  monitoring/SystemMetrics → Prometheus metrics (/metrics port 8000) │
│  monitoring/dashboard.py  → Grafana dashboards                      │
│  BrokerReconciler         → toutes les 5 min (livretradingrunner)   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Orchestrateur principal

**`live_trading/LiveTradingRunner`** — boucle principale :

```
_initialize()
  ├── instancie IBKRExecutionEngine (ou Paper)
  ├── instancie PositionRiskManager, PortfolioRiskManager, KillSwitch
  └── instancie RiskFacade (actuellement redondant — dette B2-02)

_scan_loop()  → toutes les 5 min
  ├── load_data() → DataLoader
  ├── filter_universe() → UniverseManager
  ├── discover_pairs() → PairDiscoveryEngine
  ├── generate_signals() → SignalGenerator + Combiner
  ├── approve_risk() → RiskFacade
  ├── size_positions() → PortfolioAllocator
  └── route_orders() → ExecutionRouter

_reconcile()  → toutes les 5 min (décalé)
  └── BrokerReconciler.reconcile()

_risk_tick()  → toutes les 1 min
  └── KillSwitch.check()
```

---

## 4. Architecture de déploiement

Docker Compose — 6 services :

| Service | Image | Port | Rôle |
|---------|-------|------|------|
| `trading-engine` | `python:3.11.9-slim` | 8000 (metrics) | Application principale |
| `redis` | `redis:7-alpine` | 6379 | Session state / cache |
| `prometheus` | `prom/prometheus` | 9090 | Scrape metrics |
| `grafana` | `grafana/grafana` | 3000 | Dashboards |
| `elasticsearch` | `elasticsearch:8` | 9200 | Log storage |
| `kibana` | `kibana:8` | 5601 | Log visualization |

**Variable d'environnement critique :** `EDGECORE_ENV=prod`  
(❌ jamais `production` — B5-01 : tombe silencieusement sur `dev.yaml`)

---

## 5. Stack technologique

| Couche | Technologie | Notes |
|--------|-------------|-------|
| Runtime | Python 3.11.9 (venv) | Cible Dockerfile |
| Build | Cython (`.pyx` → `.pyd`) | `setup.py build_ext --inplace` |
| Broker | ib_insync + ibapi.client | ordres live + données hist. |
| Stats | statsmodels, numpy, scipy | ADF, Johansen, OLS |
| Signal | kalman-filter (models/kalman_hedge.py) | hedge ratio adaptatif |
| Logging | structlog | jamais `print()` ni `logging.basicConfig` |
| Config | YAML + dataclass Settings | singleton `get_settings()` |
| Tests | pytest (2659 passed) | `venv\Scripts\python.exe -m pytest tests/ -q` |
| Lint | ruff | `ruff check .` |
| Types | mypy | `mypy risk/ risk_engine/ execution/` |
| Monitoring | Prometheus + Grafana | port 8000, /metrics |
| Persistence | JSON AuditTrail | crash-recovery |

---

## 6. Flux de données IBKR

```
reqHistoricalData()  → OHLCV historique (data/loader.py)
reqMktData()         → tick temps réel (data/intraday_loader.py)
reqShortableShares() → disponibilité short (universe/UniverseManager)
placeOrder()         → exécution (execution/IBKRExecutionEngine)
reqOpenOrders()      → réconciliation (BrokerReconciler)
cancelHistoricalData() → timeout/erreur 162/200/354
```

Rate limit TWS : **50 req/s hard cap** → `_ibkr_rate_limiter.acquire()` (45/s sustained, burst 10).

---

## 7. Limites et scalabilité

| Contrainte | Valeur | Raison |
|------------|--------|--------|
| Paires actives max | 10 | `max_concurrent` PortfolioAllocator |
| Symboles universe max | ~200 | Rate limit IBKR reqHistoricalData |
| Fréquence scan | 5 min | Coût latence + rate limit |
| Lookback cointégration | 252 jours | Robustesse statistique |
| Short selling | IBKR shortable shares uniquement | Pas d'emprunt manuel |
| Levier | 1× (pas de marge explicite) | `risk_per_trade=0.5%` max |
| Multi-comptes | Non supporté | 1 client_id par instance |
| Crypto / Options / Futures | Hors scope | Jamais `ccxt` |

---

## 8. Modules non-production (hors pipeline live)

| Module | Usage | Interdiction |
|--------|-------|-------------|
| `research/` | Exploration, notebooks | `import` direct depuis prod interdit |
| `backtests/` | Simulation historique | Géré via `backtester/runner.py` |
| `scripts/` | Scripts one-off | Jamais `run_backtest_v*.py` supplémentaires |
