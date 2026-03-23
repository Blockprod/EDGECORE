# Procédure : Ajouter une nouvelle stratégie de trading

> Référence : pipeline EDGECORE stat-arb pair trading  
> Prérequis : audit structurel C-01→C-09 passé, tests **2764** verts  
> Mis à jour : 2026-03-22

---

## Vue d'ensemble du pipeline à traverser

```
UniverseManager.get_symbols_as_of(date)   ← PIT — pas de survivorship bias
  ↓
PairDiscoveryEngine.discover()            ← triple-gate EG + Johansen + HAC
  ↓
SpreadModel (log-prix + Kalman optionnel) ← C-08 / C-04
  ↓
RegimeDetector (fenêtre adaptative)       ← C-09
  ↓
SignalGenerator + SignalCombiner          ← z-score×0.70 + momentum×0.30
  ↓
PositionRiskManager → PortfolioRiskManager → KillSwitch
  ↓
PortfolioAllocator (VOLATILITY_INVERSE)   ← C-07
  ↓
ExecutionRouter → {Paper|IBKR}ExecutionEngine  ← fill T+1 (C-02)
  ↓
BrokerReconciler (toutes les 5 min) → AuditTrail
```

---

## Étape 1 — Définir la stratégie

### 1.1 Identifier le type de stratégie
- **Stat-arb paires** (existant) : cointégration EG + Johansen + HAC
- **Nouveau type** : documenter dans `architecture/decisions.md` (ADR nouveau)

### 1.2 Paramètres à configurer dans `config/dev.yaml`
```yaml
strategy:
  entry_z_score:           1.6    # z-score seuil d'entrée
  exit_z_score:            0.5    # z-score seuil de sortie
  entry_z_min_spread:      0.50   # filtre micro-déviations ($)
  lookback_window:         120    # fenêtre hedge ratio (barres)
  max_half_life:           70     # max half-life (jours)
  min_correlation:         0.60   # corrélation minimale des legs
  use_kalman:              true   # hedge ratio dynamique Kalman (C-04)
  max_position_loss_pct:   0.10   # stop P&L par position (10%)
  short_sizing_multiplier: 0.50   # sizing shorts en régime TRENDING
  disable_shorts_in_bull_trend: false
  regime_directional_filter:    false
  trend_long_sizing:       0.75

signal_combiner:
  enabled:          true
  zscore_weight:    0.70   # poids z-score dans l'alpha composite
  momentum_weight:  0.30   # poids momentum
  entry_threshold:  0.6
  exit_threshold:   0.2

regime:
  enabled:               true
  ma_fast:               50
  ma_slow:               200
  vol_threshold:         0.18
  vol_window:            20
  neutral_band_pct:      0.02
  trend_favorable_sizing: 0.80
  neutral_sizing:        0.65
```

**Ne jamais hardcoder ces valeurs dans le code — toujours lire via `get_settings()`.**

---

## Étape 2 — Sélectionner les paires candidates (PIT)

```python
from universe.manager import UniverseManager
from pair_selection.discovery import PairDiscoveryEngine
from config.settings import get_settings

# Univers Point-in-time : évite le survivorship bias (C-01)
mgr = UniverseManager(
    symbols=["AAPL", "MSFT", ...],
    sector_map={"AAPL": "technology", ...},
)
mgr.load_constituents_csv("data/universe_history.csv")
symbols_today = mgr.get_symbols_as_of("2024-01-15")  # date de backtest

# Découverte de paires
engine = PairDiscoveryEngine(config=get_settings())
pairs = engine.discover(
    price_data=historical_prices,   # DataFrame OHLCV, colonnes = symboles
    candidate_pairs=None,           # None = toutes les combinaisons
    use_cache=True,
    lookback=None,                  # None = valeur de StrategyConfig
)
# pairs : List[CointegratedPair] avec .ticker_a, .ticker_b, .half_life, .coint_pvalue
```

### Critères de sélection (triple-gate)
1. `coint_pvalue_eg < 0.05` (Engle-Granger)
2. `johansen_rank >= 1` (confirmation Johansen)
3. `hac_tstat > 2.0` (Newey-West HAC)
4. `half_life <= max_half_life` (défini dans `StrategyConfig`)

---

## Étape 3 — Modéliser le spread (SpreadModel)

```python
from models.spread import SpreadModel

# C-08 : spread en log-prix (évite biais sur prix absolus)
# C-04 : hedge ratio dynamique via filtre de Kalman
model = SpreadModel(
    use_log_prices=True,   # recommandé pour séries non-stationnaires
    use_kalman=True,       # hedge ratio adaptatif (get_settings().strategy.use_kalman)
    kalman_delta=1e-4,
)
spread = model.compute_spread(prices_df[sym1], prices_df[sym2])
```

**Contrainte** : s'assurer que les séries ne contiennent pas de valeurs ≤ 0
(le `DelistingGuard` de `data/delisting_guard.py` est en place).

---

## Étape 4 — Valider avec backtest

```python
from backtests.runner import BacktestRunner
from backtests.cost_model import CostModelConfig
from config.settings import get_settings

runner = BacktestRunner()

# CostModelConfig est la source de vérité pour slippage/commission (C-05/C-06)
cost_cfg = CostModelConfig(
    slippage_model="almgren_chriss",   # impact de marché réel (C-06)
    borrowing_cost_annual_pct=0.5,     # taux HTB générique
    # htb_symbols={"GME": 0.25, ...}  # taux HTB par symbole (C-05)
)

metrics = runner.run_unified(
    symbols=[p.ticker_a for p in pairs] + [p.ticker_b for p in pairs],
    start_date="2020-01-01",
    end_date="2024-12-31",
    cost_model=cost_cfg,
    allocation_per_pair_pct=30.0,
    max_position_loss_pct=get_settings().strategy.max_position_loss_pct,
)

# Critères go/no-go
assert metrics.sharpe_ratio >= 0.8, f"Sharpe IS trop faible: {metrics.sharpe_ratio}"
assert metrics.max_drawdown <= 0.15, f"DD trop élevé: {metrics.max_drawdown}"
```

### Walk-forward obligatoire avant prod

```python
from backtester.walk_forward import WalkForwardEngine
from backtester.walk_forward import WalkForwardConfig

wf = WalkForwardEngine()
result = wf.run(WalkForwardConfig(
    symbols=[...],
    train_months=12,
    test_months=3,
))

# Critère : Sharpe OOS >= 0.4 (dégradation max 50% vs IS)
assert result.oos_sharpe >= 0.4
```

---

## Étape 5 — Configurer le signal

### SignalCombiner (existant — ne pas remplacer)
```python
# signal_engine/signal_combiner.py
# alpha = zscore_signal × 0.70 + momentum_signal × 0.30
# Modifier uniquement via config/dev.yaml (signal_combiner: section)
```

### Ajouter un composant signal alternatif (si nécessaire)
1. Créer dans `signal_engine/` avec tests dans `tests/test_signal_engine/test_{nom}.py`
2. L'intégrer dans `SignalCombiner` via config (pas hardcodé)
3. **Ne pas modifier `signal_combiner.py` sans tester l'impact sur le Sharpe existant**

### RegimeDetector — fenêtre adaptative (C-09)
```python
from models.regime_detector import RegimeDetector

detector = RegimeDetector(
    lookback_window=60,        # fenêtre par défaut relevée de 20 → 60
    adaptive_window=True,      # window varie avec la vol réalisée
    min_window=20,             # plancher en haute vol (réponse rapide)
    max_window=120,            # plafond en basse vol (estimations stables)
)
# Ou lire depuis get_settings().regime_detector_config
```

---

## Étape 6 — Configurer les stops (`risk_engine/`)

Les stops existants couvrent la majorité des cas.  
Hiérarchie risk tiers — **ne pas modifier l'ordre** :

```
Tier 1 (RiskConfig)   : max_drawdown_pct = 0.10  ← halt entrées
Tier 2 (KillSwitch)   :                  = 0.15  ← halt global IBKR
Tier 3 (StrategyConfig): internal        = 0.20  ← breaker stratégie
```

Modifier uniquement via config YAML :
```yaml
# config/dev.yaml
strategy:
  max_position_loss_pct:    0.10   # stop P&L par position
  z_score_stop:             3.5    # ferme si |z| > seuil
  hedge_ratio_reestimation_days: 7
  emergency_vol_threshold_sigma: 3.0
```

---

## Étape 7 — Intégrer dans l'univers PIT

```python
from universe.manager import UniverseManager

mgr = UniverseManager(
    symbols=["SYM1", "SYM2", ...],
    sector_map={"SYM1": "technology", ...},
    min_volume_24h_usd=5_000_000.0,
)
# Charger l'historique point-in-time pour éviter le survivorship bias (C-01)
mgr.load_constituents_csv("data/universe_history.csv")
active_symbols = mgr.get_symbols_as_of(as_of_date="2024-01-15")
```

---

## Étape 8 — Tests

### Tests requis pour toute nouvelle stratégie
```
tests/test_signal_engine/      → signal alpha (existe)
tests/backtests/               → backtest (mock data, existe)
tests/pair_selection/          → critères de sélection (créer si absent)
tests/models/                  → spread, Kalman, RegimeDetector
```

### Pattern de test (conforme aux conventions)
```python
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

def test_new_strategy_signal():
    # ✅ datetime.now(timezone.utc) — jamais datetime.utcnow()
    # ✅ structlog — jamais print()
    # ✅ lire les seuils via get_settings() — jamais hardcoder
    ...
```

---

## Étape 9 — Déploiement

### Paper trading (minimum 2 semaines)
```powershell
# EDGECORE_ENV=dev → paper trading automatique
$env:EDGECORE_ENV = "dev"
venv\Scripts\python.exe main.py --mode paper
```

### Passage en prod
1. Vérifier `config/prod.yaml` avec les paramètres validés
2. S'assurer que `EDGECORE_ENV=prod` (pas `production` — valeur invalide)
3. Tests verts : `venv\Scripts\python.exe -m pytest tests/ -q`
4. Risk tiers cohérents : `venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"`
5. `docker build -t edgecore:latest .` + smoke test Docker

---

## Checklist Go/No-Go

- [ ] Univers chargé en mode PIT via `load_constituents_csv()` + `get_symbols_as_of()`
- [ ] Paires validées par triple-gate : EG + Johansen + HAC
- [ ] Half-life dans `[2, max_half_life]`
- [ ] Spread calculé en log-prix (`SpreadModel(use_log_prices=True)`)
- [ ] Hedge ratio Kalman activé si `use_kalman=True` dans config
- [ ] Sharpe IS ≥ 0.8 sur walk-forward in-sample
- [ ] Sharpe OOS ≥ 0.4 (WalkForwardEngine)
- [ ] Max drawdown ≤ 15%
- [ ] Coûts calculés via `CostModelConfig` (slippage Almgren-Chriss, HTB si applicable)
- [ ] Execution en T+1 (fill au prix de clôture J+1, pas J)
- [ ] Stops configurés dans YAML (pas hardcodé)
- [ ] RegimeDetector configuré (`adaptive_window` si régimes lents/rapides attendus)
- [ ] Sizing via `VOLATILITY_INVERSE` (PortfolioAllocator — C-07)
- [ ] Tests unitaires écrits et passants (`pytest tests/ -q`)
- [ ] Paper trading ≥ 2 semaines avec résultats documentés
- [ ] Risk tier coherence validée : `_assert_risk_tier_coherence()`
- [ ] `EDGECORE_ENV=prod` (jamais `production`)
