---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/PLAN_result.md
derniere_revision: 2026-03-26
creation: 2026-03-26
---

# PLAN DE CORRECTION — EDGECORE

## LOGIQUE DE BATCHING

`backtests/runner.py` importe `engle_granger_test_cpp_optimized` depuis `models/`.
`models/` doit donc être entièrement propre **avant** de traiter `backtests/`.
→ 2 batches suffisent, dans l'ordre strict.

---

## PLAN

```
PLAN = [

  {
    batch      : 1,
    module     : "models/",
    files      : [
      "models/johansen.py",
      "models/ml_threshold_optimizer.py",
      "models/model_retraining.py",
      "models/performance_optimizer.py"
    ],
    error_types    : ["typing"],
    estimated_fixes: 11,
    difficulty     : "Moyen",
    patterns       : [
      "bool.any() → np.bool_(array).any() ou bool() wrapping",
      "df[col] → pd.Series() wrap pour .corr()",
      "pd.DataFrame(data, columns=...) → pd.Index(cols) ou cast",
      ".values sur ndarray|Unknown → np.asarray() direct",
      "Unknown|Index → str → cast(str, ...)"
    ],
    validation : "venv\\Scripts\\python.exe -m pytest tests\\models\\ -q --tb=no"
  },

  {
    batch      : 2,
    module     : "backtests/",
    files      : [
      "backtests/runner.py",
      "backtests/simulation_loop.py",
      "backtests/strategy_simulator.py"
    ],
    error_types    : ["Timestamp", "typing"],
    estimated_fixes: 11,
    difficulty     : "Moyen",
    patterns       : [
      "pd.Timestamp(x) → NaTType : cast(pd.Timestamp, ...) ou isinstance guard",
      "Timestamp | NaTType >= Timestamp | NaTType → cast × 2",
      "df[sym] → Series | Unknown → pd.Series(df[sym])",
      "Unknown | Index → pd.Timestamp(ts_input) → cast(pd.Timestamp, pd.Timestamp(str(...)))",
      "_clock assignment → setattr() ou cast si attribut protégé"
    ],
    validation : "venv\\Scripts\\python.exe -m pytest tests\\backtests\\ -q --tb=no"
  }

]
```

---

## RÉSUMÉ

PLAN = [
  {
    batch      : 1,
    module     : "models/",
    files      : [
      "models/model_retraining.py",
      "models/performance_optimizer.py"
    ],
    error_types    : ["typing"],
    estimated_fixes: 5,
    difficulty     : "Moyen"
  },
  {
    batch      : 2,
    module     : "backtests/",
    files      : [
      "backtests/stress_testing.py",
      "backtests/runner.py",
      "backtests/simulation_loop.py",
      "backtests/strategy_simulator.py"
    ],
    error_types    : ["ruff", "ARG", "Timestamp", "typing"],
    estimated_fixes: 57,
    difficulty     : "Moyen"
  }
]
### Batch 1 — `models/`

RÉSUMÉ:
  total_batches    : 2
  total_files      : 6
  estimated_fixes  : 62
  ordre_validation : pytest → ruff → pyright par batch
| `ml_threshold_optimizer.py` | 634 | `feature_names_in_` absent du stub sklearn → `getattr()` ou `hasattr` guard | Moyen |
| `model_retraining.py` | 245, 246, 316, 317 | `recent_data[sym].values` → `np.asarray(recent_data[sym], dtype=float)` | Facile |
| `performance_optimizer.py` | 196 | `Unknown \| Index` → `str` → `str(pair_key)` ou `cast(str, ...)` | Facile |

### Batch 2 — `backtests/`

| Fichier | Lignes | Pattern | Difficulté |
|---------|--------|---------|-----------|
| `runner.py` | 224 | `NaTType.isoformat()` → `cast(pd.Timestamp, ts).isoformat()` ou guard | Moyen |
| `runner.py` | 413 (×2) | `df[sym1]`, `df[sym2]` → `pd.Series()` wrap | Facile |
| `simulation_loop.py` | 65 | `>=` sur `Timestamp \| NaTType` → `cast(pd.Timestamp, ts1) >= cast(pd.Timestamp, ts2)` | Moyen |
| `strategy_simulator.py` | 386 | `_clock` assignment → `setattr(strategy, "_clock", ...)` | Moyen |
| `strategy_simulator.py` | 648, 1540 | `Unknown \| Index` → `pd.Timestamp` → `cast(pd.Timestamp, pd.Timestamp(str(...)))` | Moyen |

---

## PRÉREQUIS AVANT BATCH 1

```powershell
# Confirmer état initial (doit afficher 11 erreurs)
venv\Scripts\python.exe -m pyright models\ 2>&1 | Select-Object -Last 3
```

## VALIDATION FINALE APRÈS BATCH 2

```powershell
# Pyright global KO dirs uniquement
venv\Scripts\python.exe -m pyright models\ backtests\ 2>&1 | Select-Object -Last 3

# Tests concernés
venv\Scripts\python.exe -m pytest tests\models\ tests\backtests\ -q --tb=no 2>&1 | Select-Object -Last 3
```
