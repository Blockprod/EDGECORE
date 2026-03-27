---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/SCAN_result.md
derniere_revision: 2026-03-26
creation: 2026-03-26
---

# SCAN RESULT — EDGECORE

## ÉTAT GLOBAL

| Outil | Résultat |
|-------|---------|
| ruff (global) | ✅ 0 violation |
| ruff --select ARG | ✅ 0 violation |
| pyright (49 dossiers) | ❌ 2 dossiers KO · 22 erreurs |

---

## FILES_TO_FIX
  {
    file: "backtests/stress_testing.py",
    errors: ["ruff", "ARG"],
    count: 49,
    lines: [36, 37, 39, 40, 41, 100, 101, 103, 105, 106, 107, 110, 111, 112, 114, 118, 119, 120, 121, 123, 127, 128, 151, 152, 154, 156, 158, 159, 160, 161, 163, 167, 169, 193, 194, 196, 198, 200, 202, 204, 206, 209, 210, 211, 213, 234, 237],
  },
]

TOTAUX:
  ruff      : 0 violation(s)
  ARG       : 0 violation(s)
  pyright   : 49 erreur(s) dans 1 fichiers
  dossiers_propres: ["tests/backtests/058_test_walk_forward_integration.py"]
      "L634 : feature_names_in_ absent de RandomForestRegressor (sklearn stubs)"
    ]
  },

  {
    file: "models/model_retraining.py",
    errors: ["typing"],
    count: 4,
    lines: [245, 246, 316, 317],
    detail: ".values sur ndarray — recent_data[sym].values où recent_data[sym] retourne ndarray|Unknown"
  },

  {
    file: "models/performance_optimizer.py",
    errors: ["typing"],
    count: 1,
    lines: [196],
    detail: "Unknown | Index → str passé à get_thresholds_for_pair(pair_key: str)"
  },

  {
    file: "backtests/runner.py",
    errors: ["Timestamp", "typing"],
    count: 3,
    lines: [224, 413, 413],
    detail: [
      "L224 : .isoformat() sur NaTType — pd.Timestamp(x) retourne Timestamp | NaTType",
      "L413×2 : Series | Unknown | DataFrame → Series dans engle_granger_test_cpp_optimized"
    ]
  },

  {
    file: "backtests/simulation_loop.py",
    errors: ["Timestamp"],
    count: 1,
    lines: [65],
    detail: "Operator >= entre Timestamp | NaTType et Timestamp | NaTType — comparaison non-narrowée"
  },

  {
    file: "backtests/strategy_simulator.py",
    errors: ["typing", "Timestamp"],
    count: 3,
    lines: [386, 648, 1540],
    detail: [
      "L386 : Cannot assign to _clock sur PairTradingStrategy (attribut protégé ou absent du stub)",
      "L648 : Unknown | Index → pd.Timestamp.__new__ ts_input",
      "L1540 : Unknown | Index → pd.Timestamp.__new__ ts_input"
    ]
  }

]
```

---

## TOTAUX

```
ruff      : 0 violation
ARG       : 0 violation
pyright   : 22 erreurs dans 7 fichiers (2 dossiers KO)

  models/     → 11 erreurs · 4 fichiers
  backtests/  → 11 erreurs · 3 fichiers

dossiers_propres: [
  pair_selection, signal_engine, strategies, execution, data,
  live_trading, backtester, portfolio_engine, risk, risk_engine,
  execution_engine, common, config, universe, scheduler, persistence,
  monitoring, validation, research, scripts,
  tests\backtests, tests\common, tests\config, tests\data,
  tests\edgecore, tests\execution, tests\execution_engine,
  tests\integration, tests\live_trading, tests\models,
  tests\monitoring, tests\persistence, tests\phase3, tests\phase4,
  tests\portfolio_engine, tests\regression, tests\risk, tests\risk_engine,
  tests\signal_engine, tests\statistical, tests\strategies,
  tests\universe, tests\validation
]
```

---

## CLASSIFICATION PAR TYPE

| Type | Fichier | Lignes | Pattern |
|------|---------|--------|---------|
| `typing` | `models/johansen.py` | 96, 99 | `.any()` sur `bool` |
| `typing` | `models/ml_threshold_optimizer.py` | 179 | `df[col]` → `Series \| DataFrame` dans `.corr()` |
| `typing` | `models/ml_threshold_optimizer.py` | 489, 505 | `list[str]` → `columns: Axes \| None` |
| `typing` | `models/ml_threshold_optimizer.py` | 634 | `feature_names_in_` absent du stub sklearn |
| `typing` | `models/model_retraining.py` | 245, 246, 316, 317 | `.values` sur `ndarray \| Unknown` |
| `typing` | `models/performance_optimizer.py` | 196 | `Unknown \| Index` → `str` |
| `Timestamp` | `backtests/runner.py` | 224 | `.isoformat()` sur `NaTType` |
| `typing` | `backtests/runner.py` | 413 (×2) | `Series \| Unknown \| DataFrame` → `Series` |
| `Timestamp` | `backtests/simulation_loop.py` | 65 | `>=` entre `Timestamp \| NaTType` |
| `typing` | `backtests/strategy_simulator.py` | 386 | Assignation à `_clock` (attribut protégé) |
| `Timestamp` | `backtests/strategy_simulator.py` | 648, 1540 | `Unknown \| Index` → `pd.Timestamp(ts_input)` |

---

## NOTE IDE (Pylance)

`models/model_retraining.py` présente ~45 avertissements Pylance "variable not accessed"
dans une méthode incomplète (code partiellement commenté / dead code).
Ces warnings **ne sont pas des erreurs pyright** — ils ne bloquent pas le build.
À traiter en P3 uniquement si la méthode est active en production.
