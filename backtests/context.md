# backtests/ — Context Module

## Responsabilité

Simulation historique de la stratégie stat-arb. Ce dossier contient la **logique réelle de simulation** (8 fichiers). À distinguer de `backtester/` (3 fichiers, no `__init__.py`) qui n'est qu'une façade wrappant `backtests/`.

---

## Ce que ce module FAIT

| Fichier | Classe principale | Rôle |
|---------|-------------------|------|
| `runner.py` | `BacktestRunner` | Orchestrateur principal — charge data, itère stratégie, calcule métriques |
| `strategy_simulator.py` | `StrategyBacktestSimulator` | Simulation tick-by-tick des règles entry/exit d'une paire |
| `event_driven.py` | `EventDrivenBacktester` | Simulation event-driven sans lookahead bias |
| `walk_forward.py` | `WalkForwardBacktester` | Walk-forward validation IS/OOS windows |
| `parameter_cv.py` | `ParameterCVBacktester` | Cross-validation des paramètres (entry_z, exit_z, etc.) |
| `metrics.py` | `BacktestMetrics` | Calcul Sharpe, Sortino, max drawdown, Calmar, profit factor |
| `cost_model.py` | `CostModel` | Commission + slippage par trade |
| `stress_testing.py` | `StressTester` | Scénarios : crash -20%, vol × 3, spread widening |

---

## Ce que ce module NE FAIT PAS

- ❌ Connexion à l'IBKR → `execution/`
- ❌ Trading live → `live_trading/`
- ❌ Walk-forward global → voir `backtester/walk_forward.py` (façade)
- ❌ OOS validation → voir `backtester/oos.py` (façade)
- ❌ Gestion de l'univers de paires → `pair_selection/`

---

## Dette connue — `backtests/runner.py`

```python
# ⚠️ DEPRECATED — constantes hardcodées (B5-02)
COMMISSION_BPS = 10   # À lire depuis get_settings().costs.commission_bps
SLIPPAGE_BPS   = 5    # À lire depuis get_settings().costs.slippage_bps
```

Ces valeurs ignorent `CostConfig` de `config/settings.py`. Toute nouvelle utilisation de `BacktestRunner` doit passer `cost_model=CostModel.from_settings()`.

---

## Architecture `backtests/` vs `backtester/`

```
backtests/          ← LOGIQUE RÉELLE (a un __init__.py)
├── runner.py              BacktestRunner
├── strategy_simulator.py  StrategyBacktestSimulator
├── event_driven.py        EventDrivenBacktester
├── walk_forward.py        WalkForwardBacktester
├── parameter_cv.py        ParameterCVBacktester
├── metrics.py             BacktestMetrics
├── cost_model.py          CostModel
└── stress_testing.py      StressTester

backtester/         ← FAÇADES (pas de __init__.py — B4-05)
├── runner.py              wraps BacktestRunner
├── walk_forward.py        wraps WalkForwardBacktester
└── oos.py                 OOSValidationEngine  (logique partielle ici)
```

**Règle :** Importer depuis `backtests.*`, jamais depuis `backtester.*` sans avoir d'abord créé `backtester/__init__.py`.

---

## Contrats

### `BacktestRunner`

```python
class BacktestRunner:
    def run(
        self,
        price_data: pd.DataFrame,       # OHLCV, colonnes = symboles
        pair_list: List[Tuple[str,str]], # ex: [("AAPL","MSFT"), ...]
        config: Optional[StrategyConfig] = None,
        cost_model: Optional[CostModel] = None,
    ) -> BacktestResults: ...

# BacktestResults :
# .metrics    : BacktestMetrics
# .trades     : pd.DataFrame (trade log)
# .equity_curve : pd.Series
# .pair_results : Dict[str, PairBacktestResult]
```

### `CostModel`

```python
class CostModel:
    commission_bps: float   # default via settings : X bps
    slippage_bps:   float   # default via settings : X bps

    @classmethod
    def from_settings(cls) -> "CostModel":
        s = get_settings()
        return cls(
            commission_bps=s.costs.commission_bps,
            slippage_bps=s.costs.slippage_bps,
        )

    def apply(self, notional: float, side: str) -> float:
        # returns cost in dollars
```

### `BacktestMetrics`

```python
@dataclass
class BacktestMetrics:
    total_return:       float
    annualized_return:  float
    sharpe_ratio:       float
    sortino_ratio:      float
    calmar_ratio:       float
    max_drawdown:       float
    profit_factor:      float
    win_rate:           float
    avg_trade_return:   float
    total_trades:       int
    total_pairs_tested: int
```

---

## Dépendances internes

```
backtests/runner.py            ←── data/loader.py
                               ←── models/spread.py (SpreadModel)
                               ←── strategies/pair_trading.py  ← NOTE: pas signal_engine direct
                               ←── backtests/cost_model.py
                               ←── backtests/metrics.py

backtests/strategy_simulator.py ←── signal_engine/signal_generator.py
                                ←── risk_engine/position_risk.py
                                ←── backtests/cost_model.py

backtests/walk_forward.py      ←── backtests/runner.py

backtests/parameter_cv.py      ←── backtests/runner.py
                               ←── sklearn (si disponible, sinon custom CV)

backtests/stress_testing.py    ←── backtests/runner.py
                               ←── backtests/strategy_simulator.py
```

---

## Utilisation typique

```python
from backtests.runner import BacktestRunner
from backtests.cost_model import CostModel
from config.settings import get_settings

runner = BacktestRunner()
results = runner.run(
    price_data=price_df,
    pair_list=[("AAPL", "MSFT"), ("JPM", "GS")],
    config=get_settings().strategy,
    cost_model=CostModel.from_settings(),
)

print(f"Sharpe: {results.metrics.sharpe_ratio:.2f}")
print(f"Max DD: {results.metrics.max_drawdown:.1%}")
```

---

## Walk-Forward + OOS

```python
from backtests.walk_forward import WalkForwardBacktester

wf = WalkForwardBacktester(
    train_window=252,   # jours
    test_window=63,     # jours
    n_splits=5,
)
wf_results = wf.run(price_data=..., pair_list=...)

# OOS via backtester/oos.py (façade)
from backtester.oos import OOSValidationEngine
oos = OOSValidationEngine()
oos_results = oos.validate(strategy_config=..., price_data=...)
```
