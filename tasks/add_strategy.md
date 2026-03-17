# Procédure : Ajouter une nouvelle stratégie de trading

> Référence : pipeline EDGECORE stat-arb pair trading
> Prérequis : audit structurel passé, tests 2654 verts

---

## Vue d'ensemble du pipeline à traverser

```
PairDiscoveryEngine (sélection)
  ↓
StrategyConfig (paramètres)
  ↓
SignalGenerator + SignalCombiner (alpha)
  ↓
PositionRiskManager (stops)
  ↓
PortfolioRiskManager + KillSwitch (portfolio)
  ↓
PortfolioAllocator (sizing)
  ↓
ExecutionRouter → {Paper|IBKR}ExecutionEngine
```

---

## Étape 1 — Définir la stratégie

### 1.1 Identifier le type de stratégie
- **Stat-arb paires** (existant) : cointégration EG + Johansen + HAC
- **Nouveau type** : documenter dans `architecture/decisions.md` (ADR nouveau)

### 1.2 Paramètres à configurer dans `config/dev.yaml`
```yaml
strategy:
  entry_z_score:        2.0   # z-score seuil d'entrée
  exit_z_score:         0.5   # z-score seuil de sortie
  lookback_days:        252   # fenêtre hedge ratio
  min_half_life:        2
  max_half_life:        60
  min_correlation:      0.60
  coint_significance:   0.05
  adf_significance:     0.05
  # Kalman
  kalman_process_noise: 1e-5
  kalman_obs_noise:     1e-3
  # Signal combiner
  zscore_weight:        0.70
  momentum_weight:      0.30
  signal_entry_threshold: 0.6
  signal_exit_threshold:  0.2
```

**Ne jamais hardcoder ces valeurs dans le code.**

---

## Étape 2 — Sélectionner les paires candidates

```python
from pair_selection.discovery import PairDiscoveryEngine
from config.settings import get_settings

engine = PairDiscoveryEngine(config=get_settings())
pairs = engine.discover(
    universe=universe_df,     # DataFrame OHLCV, colonnes = symboles
    lookback_days=252,
)
# pairs : List[PairResult] avec .ticker_a, .ticker_b, .half_life, .coint_pvalue
```

### Critères de sélection (triple-gate)
1. `coint_pvalue_eg < 0.05` (Engle-Granger)
2. `johansen_rank >= 1`
3. `hac_tstat > 2.0`
4. `min_half_life <= half_life <= max_half_life`

---

## Étape 3 — Valider avec backtest

```python
from backtests.runner import BacktestRunner
from backtests.cost_model import CostModel
from config.settings import get_settings

runner = BacktestRunner()
results = runner.run(
    price_data=historical_prices,
    pair_list=[(p.ticker_a, p.ticker_b) for p in pairs],
    config=get_settings().strategy,
    cost_model=CostModel.from_settings(),  # jamais de valeurs hardcodées
)

# Critères go/no-go
assert results.metrics.sharpe_ratio >= 0.8, f"Sharpe IS trop faible: {results.metrics.sharpe_ratio}"
assert results.metrics.max_drawdown <= 0.15, f"DD trop élevé: {results.metrics.max_drawdown}"
```

### Walk-forward obligatoire avant prod
```python
from backtests.walk_forward import WalkForwardBacktester

wf = WalkForwardBacktester(train_window=252, test_window=63, n_splits=5)
wf_results = wf.run(price_data=historical_prices, pair_list=...)

# Critère : Sharpe OOS >= 0.4 (dégradation max 50% vs IS)
```

---

## Étape 4 — Configurer le signal

### ModèleSignalCombiner (existant — ne pas remplacer)
```python
# signal_engine/signal_combiner.py
# Signal = zscore_signal × 0.70 + momentum_signal × 0.30
# Modifier les weights uniquement via config/dev.yaml
```

### Ajouter un composant signal alternatif (si nécessaire)
1. Créer dans `signal_engine/` avec tests `tests/test_signal_engine/test_{nom}.py`
2. Implémenter l'interface `BaseSignalComponent` (si existante)
3. L'intégrer dans `SignalCombiner` via config (pas hardcodé)
4. **Ne pas modifier `signal_combiner.py` sans tester l'impact sur le Sharpe existant**

---

## Étape 5 — Configurer les stops (PositionRiskManager)

Les stops existants couvrent la majorité des cas. Modifier uniquement via config :

```yaml
# config/dev.yaml
position_risk:
  trailing_stop_sigma:       1.0
  time_stop_hl_multiplier:   3.0
  time_stop_max_bars:        60
  max_position_loss_pct:     0.10
  hedge_drift_tolerance_pct: 10.0
  hedge_reestimation_days:   7
```

---

## Étape 6 — Intégrer dans l'univers

```python
from universe.manager import UniverseManager

mgr = UniverseManager(config=get_settings())
# Vérifier que les symboles passent les filtres de liquidité
# avant de les intégrer aux pairs candidates
```

---

## Étape 7 — Tests

### Tests requis pour toute nouvelle stratégie
```
tests/test_signal_engine/     → test du signal alpha
tests/test_backtests/         → test du backtest (mock data)
tests/test_pair_selection/    → test des critères de sélection
```

### Pattern de test (conforme aux conventions)
```python
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

def test_new_strategy_signal():
    # Utiliser datetime.now(timezone.utc) pour les fixtures
    # Ne pas utiliser print() — pytest capture les logs structlog
    ...
```

---

## Étape 8 — Déploiement

### Paper trading (minimum 2 semaines)
```powershell
# EDGECORE_ENV=dev → paper trading automatique
$env:EDGECORE_ENV = "dev"
venv\Scripts\python.exe main.py --mode paper
```

### Passage en prod
1. Vérifier `config/prod.yaml` avec les paramètres validés
2. Exécuter checklist `tasks/audit_structural.md` complète
3. Tests verts : `venv\Scripts\python.exe -m pytest tests/ -q`
4. `docker build -t edgecore:latest .` + smoke test Docker

---

## Checklist Go/No-Go

- [ ] Paires validées par triple-gate cointégration
- [ ] Half-life dans `[min_half_life, max_half_life]`
- [ ] Sharpe IS ≥ 0.8 sur walk-forward
- [ ] Sharpe OOS ≥ 0.4
- [ ] Max drawdown ≤ 15%
- [ ] Coûts calculés via `CostModel.from_settings()` (pas hardcodé)
- [ ] Stops configurés dans YAML (pas hardcodé)
- [ ] Tests unitaires écrits et passants
- [ ] Paper trading ≥ 2 semaines avec résultats documentés
- [ ] Risk tier coherence validée : `_assert_risk_tier_coherence()`
