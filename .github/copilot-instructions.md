# GitHub Copilot — Instructions EDGECORE

## Stack technique

- **Langage** : Python 3.11 (venv) / 3.13 (system). Dockerfile cible `python:3.11.9-slim`.
- **Extensions compilées** : Cython — `models/cointegration_fast.pyx` compilé en `.cp311-win_amd64.pyd` et `.cp313-win_amd64.pyd`. Commande de recompilation : `venv\Scripts\python.exe setup.py build_ext --inplace`.
- **Broker** : Interactive Brokers via `ib_insync` (ordres live) + `ibapi.client.EClient` (données historiques / shortable shares). Jamais `ccxt`.
- **Data** : `pandas.DataFrame` OHLCV, colonnes = symboles, index = `DatetimeIndex`. Source principale : IBKR `reqHistoricalData` + Yahoo Finance fallback.
- **Logging** : `structlog.get_logger(__name__)` partout — **jamais** `print()` ni `logging.basicConfig`.
- **Tests** : `pytest tests/` — 2654 passants, 0 skipped, 0 failed. Commande : `venv\Scripts\python.exe -m pytest tests/ -q`.
- **Config** : `from config.settings import get_settings` — singleton global. Environnements : `dev` / `test` / `prod` (via `EDGECORE_ENV`).
- **Datetime** : toujours `datetime.now(timezone.utc)` — **jamais** `datetime.utcnow()`.

---

## Modules clés et responsabilités

| Module | Classe principale | Rôle |
|--------|-------------------|------|
| `universe/` | `UniverseManager` | Liste de symboles actifs + filtre liquidité |
| `pair_selection/` | `PairDiscoveryEngine` | Tests de cointégration, sélection de paires |
| `models/` | `cointegration.py`, `spread.py`, `kalman_hedge.py` | Maths stat-arb (EG, Johansen, Kalman, z-score) |
| `signal_engine/` | `SignalGenerator`, `SignalCombiner` | Alpha : z-score × 0.70 + momentum × 0.30 |
| `risk_engine/` | `PositionRiskManager`, `PortfolioRiskManager`, `KillSwitch` | Stops opérationnels |
| `risk/` | `RiskEngine`, `RiskFacade` | Logique de risque mathématique + façade unifiée |
| `portfolio_engine/` | `PortfolioAllocator` | Dimensionnement des positions |
| `execution_engine/` | `ExecutionRouter` | Routage PAPER / LIVE / BACKTEST |
| `execution/` | `IBKRExecutionEngine`, `PaperExecutionEngine` | Connexion broker réelle |
| `live_trading/` | `LiveTradingRunner` | Boucle de trading (orchestrateur) |
| `config/` | `Settings` (singleton) | Configuration centralisée via YAML |
| `backtests/` | `BacktestRunner`, `StrategyBacktestSimulator` | Simulation historique |
| `backtester/` | `BacktestEngine`, `WalkForwardEngine`, `OOSValidationEngine` | Façades haut niveau (wrappent `backtests/`) |
| `monitoring/` | `SystemMetrics`, `dashboard.py`, `alerter.py` | Observabilité, Prometheus, Grafana |
| `persistence/` | `AuditTrail` | Crash recovery, positions persistées |

---

## Conventions critiques

### Types d'ordres
- Type canonical : `execution.base.Order` (ordre interne) et `execution_engine.router.TradeOrder` (ordre routeur).
- **Ne pas** créer de nouveaux types d'ordre — adapter les existants.
- `OrderStatus` : source de vérité = `execution/base.py`. Les deux classes doivent partager ce même enum.

### Config
- Toujours lire via `get_settings().section.champ` — jamais hardcoder un seuil de risque.
- Les valeurs YAML overrident les defaults dataclass. L'environnement se passe via `EDGECORE_ENV` (valeurs valides : `dev`, `test`, `prod` — **pas** `production`).
- `CostConfig` est la source de vérité pour slippage/commission. `execution_engine/router.py` doit lire `get_settings().costs` — les valeurs `slippage = 2.0` hardcodées aux lignes 162 et 189 sont une dette connue (B5-02).

### Risk tiers (NE PAS MODIFIER l'ordre)
```
Tier 1 : RiskConfig.max_drawdown_pct  = 0.10  (10%)   ← déclenche halt entrées
Tier 2 : KillSwitchConfig             = 0.15  (15%)   ← halt global IBKR
Tier 3 : StrategyConfig.internal      = 0.20  (20%)   ← breaker stratégie
```
L'assertion `_assert_risk_tier_coherence()` vérifie T1 ≤ T2 ≤ T3 au démarrage.

### IBKR rate limit
- Hard cap TWS : **50 req/s** → déconnexion automatique si dépassé.
- Toujours passer par `_ibkr_rate_limiter.acquire()` (45/s sustained, burst 10) avant tout appel API.
- Erreurs **informatives** (ne pas interrompre) : 2104, 2106, 2158.
- Erreurs données historiques : 162, 200, 354 → interrompre et `cancelHistoricalData`.

### Codebase issues connues (ne pas réintroduire)
1. **B5-01** : `EDGECORE_ENV=production` dans Dockerfile/docker-compose → tombe silencieusement sur `dev.yaml`. La valeur correcte est `prod`.
2. **B2-01** : `TradeOrder` dans `execution_engine/router.py` duplique `Order` de `execution/base.py` — toute nouvelle fonctionnalité doit utiliser `Order`.
3. **B2-02** : `LiveTradingRunner._initialize()` instancie `PositionRiskManager`, `PortfolioRiskManager`, `KillSwitch` ET `RiskFacade` séparément — la `RiskFacade` devait unifier tout cela.
4. **B4-05** : `backtester/` n'a pas de `__init__.py` — ne pas importer `from backtester import ...` sans l'avoir d'abord créé.

---

## Interdictions absolues

- ❌ `datetime.utcnow()` → utiliser `datetime.now(timezone.utc)`
- ❌ `print()` → utiliser `structlog`
- ❌ Hardcoder des seuils de risque (entry_z, drawdown %) → lire depuis `get_settings()`
- ❌ Modifier `risk_engine/kill_switch.py` sans adapter `risk/facade.py`
- ❌ Ajouter des `@pytest.mark.skip` sans commentaire traçable
- ❌ Créer un 3ème type d'ordre (il en existe déjà 2 trop)
- ❌ `EDGECORE_ENV=production` — valeur invalide, utiliser `prod`
- ❌ Appel IBKR sans `_ibkr_rate_limiter.acquire()` au préalable
- ❌ `import` direct depuis `research/` dans un module de production
- ❌ Committer des fichiers `run_backtest_v*.py` supplémentaires dans `scripts/`

---

## Commandes de validation

```powershell
# Tests complets (venv Python 3.11)
venv\Scripts\python.exe -m pytest tests/ -q

# Tests avec warnings (doit montrer 0 DeprecationWarning utcnow)
venv\Scripts\python.exe -m pytest tests/ -W error::DeprecationWarning -q

# Recompiler Cython après modification de .pyx
venv\Scripts\python.exe setup.py build_ext --inplace

# Vérifier la config par environnement
EDGECORE_ENV=dev venv\Scripts\python.exe -c "from config.settings import get_settings; s=get_settings(); print(s.strategy.entry_z_score)"

# Vérifier risk tier coherence
venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"
```

---

## Structure du pipeline (résumé)

```
DataLoader → UniverseManager → PairDiscoveryEngine
  → SignalGenerator (z-score×0.70 + momentum×0.30)
  → PositionRiskManager → PortfolioRiskManager → KillSwitch
  → PortfolioAllocator → ExecutionRouter → {Paper|IBKR}ExecutionEngine
  → BrokerReconciler (toutes les 5 min) → AuditTrail
```
