---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/BATCH_result.md
derniere_revision: 2026-04-06
creation: 2026-03-26
---

# BATCH RESULT — EDGECORE

---

## SESSION 2026-04-06 (suite) — Batches 3–5 appliqués inline lors de P4 VERIFY

### BATCH 3 — risk/engine.py + risk_engine/portfolio_risk.py ✅

```
BATCH_RESULT:
  batch          : 3
  module         : risk/ + risk_engine/
  fixed_files    : 2  (risk/engine.py · risk_engine/portfolio_risk.py)
  remaining_errors: 0
  blockers       : []
  tests          : 100 passed / 0 failed  (tests/risk/ + tests/risk_engine/)
```

| Fichier | Ligne | Code | Fix |
|---------|-------|------|-----|
| `risk/engine.py` | multiple | UP017×2 | `timezone.utc` → `datetime.UTC`; `timezone` import supprimé (F401); imports triés (I001) |
| `risk_engine/portfolio_risk.py` | multiple | UP017×2 | idem |

---

### BATCH 4 — tests/models/test_kalman_hedge.py + tests/execution/ ✅

```
BATCH_RESULT:
  batch          : 4
  module         : tests/models/ + tests/execution/
  fixed_files    : 3  (test_kalman_hedge.py · test_ibkr_crash_recovery.py · test_ibkr_disconnect_during_order.py)
  remaining_errors: 0
  blockers       : []
  tests          : 42 passed / 0 failed
```

| Fichier | Ligne | Code | Fix |
|---------|-------|------|-----|
| `tests/models/test_kalman_hedge.py` | multiple | B905×5 | `zip(y, x)` → `zip(y, x, strict=False)` (unsafe-fix) |
| `tests/execution/test_ibkr_crash_recovery.py` | 51 | reportInvalidTypeForm | `engine._pending_confirm_orders: set[str] = set()` → `engine._pending_confirm_orders = set()` |
| `tests/execution/test_ibkr_disconnect_during_order.py` | 47 | reportInvalidTypeForm | idem |

---

### BATCH 5 — tests/live_trading/ + tests/monitoring/ + tests/universe/ ✅

```
BATCH_RESULT:
  batch          : 5
  module         : tests/live_trading/ + tests/monitoring/ + tests/universe/
  fixed_files    : 3  (test_live_trading_recovery.py · 042_test_api.py · test_universe_pit.py)
  remaining_errors: 0
  blockers       : []
  tests          : 84 passed / 0 failed
```

| Fichier | Ligne | Code | Fix |
|---------|-------|------|-----|
| `tests/live_trading/test_live_trading_recovery.py` | 29 | reportArgumentType | `threading.Lock()` → `threading.RLock()` (prod utilise RLock) |
| `tests/monitoring/042_test_api.py` | 576 | reportAttributeAccessIssue | `app._system_metrics = metrics  # pyright: ignore[reportAttributeAccessIssue]` |
| `tests/universe/test_universe_pit.py` | multiple | reportArgumentType (NaT) | `cast(pd.Timestamp, pd.Timestamp("..."))` ×3 |

---

### Régressions corrigées (suite P4 VERIFY)

| Fichier | Fix |
|---------|-----|
| `strategies/pair_trading.py` | Re-ajout `newey_west_consensus as _newey_west_consensus  # noqa: F401` (re-export pour test patching — supprimé par erreur en batch 1) |
| `tests/models/test_newey_west_hac.py` | Patch targets mis à jour : `strategies.pair_trading.*` → `strategies.pair_validator.*` pour `engle_granger_test`, `_newey_west_consensus`, `half_life_mean_reversion` (fonctions résident dans pair_validator depuis refactor PairValidator) |
| `tests/phase4/test_phase4_signals.py` | `MagicMock()` manquait les valeurs numériques `zscore_weight=0.70`, `momentum_weight=0.30`, `entry_threshold=2.0`, `exit_threshold=0.5` → ajoutés dans les 2 tests `TestMarkovRegimeConcordance` |

---

## SESSION 2026-04-06 — Plan rev. 2026-04-06 (5 batches)

### BATCH 1 — strategies/pair_trading.py ✅

```
BATCH_RESULT:
  batch          : 1
  module         : strategies/
  fixed_files    : 1  (strategies/pair_trading.py)
  remaining_errors: 0
  blockers       : []
  tests          : 92 passed / 0 failed  (tests/strategies/)
```

| Ligne | Code | Fix |
|-------|------|-----|
| 3 | F401 | Supprimé `timedelta` de `from datetime import date, datetime, timedelta` → `from datetime import date, datetime` |
| 20 | F401 | Supprimé la ligne `from models.cointegration import newey_west_consensus as _newey_west_consensus` (jamais appelée comme fonction) |

---

### BATCH 2 — execution/ml_impact.py + execution_engine/router.py ✅

```
BATCH_RESULT:
  batch          : 2
  module         : execution/ + execution_engine/
  fixed_files    : 2  (execution/ml_impact.py · execution_engine/router.py)
  remaining_errors: 0
  blockers       : []
  tests          : 394 passed / 0 failed  (tests/execution/ · tests/execution_engine/)
```

| Fichier | Ligne | Code | Fix |
|---------|-------|------|-----|
| `execution/ml_impact.py` | 127 | reportArgumentType ×6 | Ajout guard `if self.W1 is None or ... raise RuntimeError(...)` avant `np.savez()` — W1/b1/W2/b2/W3/b3 garantis non-None après le guard |
| `execution_engine/router.py` | 353 | F811 | Supprimé le `import time as _time` dupliqué — L243 déjà en scope dans `_live_fill()` |




### BATCH 1 — models/performance_optimizer_s41.py ✅

```
BATCH_RESULT:
  batch          : 1
  module         : models/
  fixed_files    : 1  (performance_optimizer_s41.py)
  remaining_errors: 0
  blockers       : []
  tests          : 25 passed / 0 failed  (tests/models/test_performance_optimizer.py)
```

| Ligne | Erreur | Fix |
|-------|--------|-----|
| 17 | `Dict, Optional, Tuple` from `typing` → UP006/UP045 | Remplacé par `dict`, `tuple`, `X \| None` natifs |
| 130 | `pair` (`Unknown \| int`) → `str` pour `get_thresholds_for_pair` | `str(pair)` sur les 2 appels dans la boucle |
| 215 | `setattr(...)` B010 | `# noqa: B010` (setattr sur fonction — pattern LRU cache dynamique, `cache_clear` non dans le type `_Wrapped`) |

**Pyright** : 0 errors, 0 warnings ✅  
**Ruff** : All checks passed ✅  
**Tests** : 25/25 ✅

---

## SESSION 2026-04-05 (suite) — Batches 2–7

### BATCH 2 — execution/ ✅

```
BATCH_RESULT:
  batch          : 2
  module         : execution/
  fixed_files    : 2  (modes_legacy.py, order_lifecycle_integration.py)
  remaining_errors: 0
  tests          : 11 passed (035_test_order_lifecycle_integration) / 0 failed
```

| Fichier | Fix |
|---------|-----|
| `execution/modes_legacy.py:39` | `class OrderStatus(str, Enum):  # noqa: UP042` |
| `execution/order_lifecycle_integration.py:14-17` | Suppression import dupliqué + tri isort |

---

### BATCH 3 — data/intraday_loader.py ✅

```
BATCH_RESULT:
  batch          : 3
  module         : data/
  fixed_files    : 1  (intraday_loader.py)
  remaining_errors: 0
  tests          : 176 passed (tests/data/) / 0 failed
```

| Fichier | Fix |
|---------|-----|
| `data/intraday_loader.py:175` | `req_end: pd.Timestamp = cast(pd.Timestamp, min(...))` — résout NaTType.strftime |

---

### BATCH 4 — monitoring/ + backtests/ ✅

```
BATCH_RESULT:
  batch          : 4
  module         : monitoring/ + backtests/
  fixed_files    : 4  (logger.py, cache_advanced_s42.py, portfolio_extension_s43.py, walk_forward.py)
  remaining_errors: 0
  tests          : 68 passed (tests/monitoring/047+048 + tests/backtests/004) / 0 failed
```

| Fichier | Fix |
|---------|-----|
| `monitoring/logger.py` | UP017: `timezone.utc` → `datetime.UTC` (auto-fix) |
| `monitoring/cache_advanced_s42.py` | UP006/UP045/I001 auto-fix |
| `monitoring/portfolio_extension_s43.py` | UP006 auto-fix |
| `backtests/walk_forward.py:28` | F811: suppression import `CostModel` dupliqué |

---

### BATCH 5 — research/ + ARG + scripts ✅

```
BATCH_RESULT:
  batch          : 5
  module         : research/ + run_paper_tick.py + scripts/
  fixed_files    : 5
  remaining_errors: 0 ruff ARG + 0 pyright
  tests          : non applicable (scripts historiques)
```

| Fichier | Fix |
|---------|-----|
| `research/pair_discovery.py:5-9` | F811/F401: suppression double import `models.cointegration` + `correlation_matrix` inutilisé |
| `research/param_optimization.py:10-13` | F811: suppression `import pandas as pd` dupliqué + tri |
| `run_paper_tick.py:331` | ARG001: `sig, frame` → `_sig, _frame` |
| `scripts/run_backtest_v41fg.py:120` | ARG001: `rediscovery` → `_rediscovery` |
| `scripts/run_backtest_v40b.py:142` | pyright ndarray.ffill: `pd.DataFrame(prices).ffill()` |

---

### BATCH 6 — main.py + scripts mass ✅

```
BATCH_RESULT:
  batch          : 6
  module         : main.py + scripts/
  fixed_files    : ~58  (main.py + 57 scripts run_backtest_v*)
  remaining_errors: 0
  tests          : 2742 passed (full suite) / 0 failed
```

| Scope | Fix |
|-------|-----|
| `main.py` | F811×4 (IBKRExecutionEngine, PaperExecutionEngine, RiskEngine, PairTradingStrategy) + I001 — auto-fix |
| `scripts/` | UP031/F541/E401/UP009/I001/F811 auto-fix ; UP032 auto-fix ; UP031 `# ruff: noqa: UP031` sur 21 fichiers legacy |

---

### BATCH 7 — tests/ + demo ✅

```
BATCH_RESULT:
  batch          : 7
  module         : tests/ + demo_dashboard.py
  fixed_files    : 0  (aucune violation I001 détectée à l'application)
  remaining_errors: 0
```

---

## RÉSULTAT FINAL TOUS BATCHES

```
ruff global  : ✅ All checks passed (0 violations)
ARG          : ✅ All checks passed (0 violations)
pyright      : ✅ 0 errors (data/intraday_loader.py, scripts/run_backtest_v40b.py, models/performance_optimizer_s41.py)
pytest       : ✅ 2742 passed in 217.52s
```

### models/johansen.py (2 erreurs → 0)

| Ligne | Erreur | Fix |
|-------|--------|-----|
| 96 | `data.isna().any().any()` — Cannot access attribute "any" for class "bool" | `data.isna().values.any()` |
| 99 | `(data.std() < 1e-10).any()` — Cannot access attribute "any" for class "bool" | `np.any(np.asarray(data.std()) < 1e-10)` |

**Imports ajoutés :** `import numpy as np`

---

### models/ml_threshold_optimizer.py (4 erreurs → 0)

| Ligne | Erreur | Fix |
|-------|--------|-----|
| 179 | `spread.corr(spread.shift(1))` — `Series \| DataFrame` cannot be assigned to `Series` | `spread.corr(pd.Series(spread.shift(1)))` |
| 489 | `pd.DataFrame(..., columns=feature_cols)` — `list[str]` → `Axes \| None` | `pd.DataFrame(..., columns=pd.Index(feature_cols))` |
| 505 | `pd.DataFrame(..., columns=self.feature_names)` — `list[str]` → `Axes \| None` | `pd.DataFrame(..., columns=pd.Index(self.feature_names))` |
| 634 | `self.entry_model.feature_names_in_` — attribute absent from sklearn stubs | `_fn = getattr(self.entry_model, "feature_names_in_", None); list(_fn) if _fn is not None else [...]` |

**Note :** Le `getattr(...) or [...]` initial déclenchait `ValueError: ambiguous truth value` sur numpy array → remplacé par contrôle explicite `is not None`.

---

### models/model_retraining.py (4 erreurs → 0)

| Ligne | Erreur | Fix |
|-------|--------|-----|
| 245 | `recent_data[sym1].values` — Cannot access attribute "values" for class "ndarray[Any, Unknown]" | `np.asarray(recent_data[sym1], dtype=float)` |
| 246 | `recent_data[sym2].values` — même erreur | `np.asarray(recent_data[sym2], dtype=float)` |
| 316 | `recent_data[sym1].values` — même erreur | `np.asarray(recent_data[sym1], dtype=float)` |
| 317 | `recent_data[sym2].values` — même erreur | `np.asarray(recent_data[sym2], dtype=float)` |

---

### models/performance_optimizer.py (1 erreur → 0)

| Ligne | Erreur | Fix |
|-------|--------|-----|
| 196 | `get_thresholds_for_pair(pair)` — `Unknown \| int` cannot be assigned to `str` | `pair_str = str(pair)` + utiliser `pair_str` dans les appels |

**Note :** La ligne 194 résolvait déjà l'ambiguïté via `**kwargs`, seule la ligne 196 était flaggée.

---

## VALIDATION

```
pyright models\johansen.py models\ml_threshold_optimizer.py
        models\model_retraining.py models\performance_optimizer.py
→ 0 errors, 1 warning, 0 informations ✅

pytest tests\models\ --tb=no -q
→ 507 passed in 66.84s ✅
```

---

## BATCH 2 — backtests/ ✅

```
BATCH_RESULT:
  batch          : 2
  module         : backtests/
  fixed_files    : 3
  remaining_errors: 0
  blockers       : []
  tests          : 185 passed / 0 failed
```

### Corrections batch 2

| Fichier | Ligne | Erreur | Fix |
|---------|-------|--------|-----|
| `runner.py` | 224 | `.isoformat()` sur `NaTType` | `cast(pd.Timestamp, start_buffer).isoformat()` |
| `runner.py` | 413×2 | `Series\|Unknown\|DataFrame` → `Series` | `pd.Series(series1)`, `pd.Series(series2)` |
| `simulation_loop.py` | 65 | `>=` sur `Timestamp\|NaTType` | `cast(pd.Timestamp, pd.Timestamp(ts)) >= _ts` |
| `strategy_simulator.py` | 386 | `_clock` — attribut protégé | `setattr(strategy, "_clock", _clock_fn)` |
| `strategy_simulator.py` | 648 | `Unknown\|Index` → `pd.Timestamp` | `cast(pd.Timestamp, pd.Timestamp(str(...))).date()` |
| `strategy_simulator.py` | 1540 | `Unknown\|Index` → `pd.Timestamp` | `cast(pd.Timestamp, pd.Timestamp(str(...))).date()` |

**Imports ajoutés :** `runner.py` → `from typing import cast` · `simulation_loop.py` → `from typing import cast` · `strategy_simulator.py` → `cast` ajouté au `from typing import`

```
pyright backtests\runner.py backtests\simulation_loop.py backtests\strategy_simulator.py
→ 0 errors, 2 warnings, 0 informations ✅

pytest tests\backtests\ --tb=no -q
→ 185 passed in 54.10s ✅
```

---

## ÉTAT BATCHES

```
batch 1 — models/     : ✅ DONE   (0 erreurs pyright, 507 tests verts)
batch 2 — backtests/  : ✅ DONE   (0 erreurs pyright, 185 tests verts)

remaining_errors : 0
→ Prêt pour P4 VERIFY
```
