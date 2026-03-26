---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/BATCH_result.md
derniere_revision: 2026-03-26
creation: 2026-03-26
---

# BATCH RESULT — EDGECORE

## BATCH 1 — models/ ✅

```
BATCH_RESULT:
  batch          : 1
  module         : models/
  fixed_files    : 4
  remaining_errors: 0
  blockers       : []
  tests          : 507 passed / 0 failed
```

---

## DÉTAIL DES CORRECTIONS

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
