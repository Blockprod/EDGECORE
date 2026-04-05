---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/SCAN_result.md
derniere_revision: 2026-04-05
creation: 2026-03-26
---

# SCAN RESULT — EDGECORE

> Revision 2026-04-05 — scan post CERT-01→CERT-10 (2742/2742 ✅)

## ÉTAT GLOBAL

| Outil | Résultat |
|-------|---------|
| ruff (global) | ❌ 418 violations · ~65 fichiers |
| ruff --select ARG | ❌ 3 violations (ARG001×3) |
| pyright (production) | ❌ 3 dossiers KO · 4 erreurs |
| get_errors (IDE) | ✅ 0 erreur |
| pytest | ✅ 2742/2742 |

---

## FILES_TO_FIX

### BATCH A — Production critique (pyright)

```
FILES_TO_FIX = [
  {
    file: "data/intraday_loader.py",
    errors: ["Timestamp"],
    count: 1,
    lines: [183],
    detail: "Cannot access attribute 'strftime' for class 'NaTType' — req_end peut être NaT"
  },
  {
    file: "models/performance_optimizer_s41.py",
    errors: ["typing"],
    count: 1,
    lines: [130],
    detail: "Argument of type 'Unknown | int' cannot be assigned to parameter 'pair_key' of type 'str'"
  },
]
```

### BATCH B — Production ruff (F811 / I001 / UP042)

```
FILES_TO_FIX = [
  {
    file: "monitoring/logger.py",
    errors: ["ruff"],
    count: 1,
    lines: [23],
    codes: ["UP017"],
    detail: "Use datetime.UTC alias (auto-fix)"
  },
  {
    file: "main.py",
    errors: ["ruff"],
    count: 5,
    lines: [10, 34, 36, 45, 46],
    codes: ["I001", "F811", "F811", "F811", "F811"],
    detail: "Import non trié + redéfinitions IBKRExecutionEngine, PaperExecutionEngine, RiskEngine, PairTradingStrategy"
  },
  {
    file: "backtests/walk_forward.py",
    errors: ["ruff"],
    count: 2,
    lines: [16, 28],
    codes: ["I001", "F811"],
    detail: "Import non trié + redéfinition CostModel"
  },
  {
    file: "execution/order_lifecycle_integration.py",
    errors: ["ruff"],
    count: 3,
    lines: [11, 17, 17],
    codes: ["I001", "F811", "F811"],
    detail: "Import non trié + redéfinition OrderLifecycleManager + OrderStatus"
  },
  {
    file: "execution/modes_legacy.py",
    errors: ["ruff"],
    count: 1,
    lines: [39],
    codes: ["UP042"],
    detail: "class OrderStatus hérite de str + enum.Enum → utiliser StrEnum"
  },
  {
    file: "research/pair_discovery.py",
    errors: ["ruff"],
    count: 4,
    lines: [5, 6, 9, 9],
    codes: ["I001", "F401", "F811", "F811"],
    detail: "Import non trié + correlation_matrix inutilisé + redéfinitions engle_granger_test, half_life_mean_reversion"
  },
  {
    file: "research/param_optimization.py",
    errors: ["ruff"],
    count: 2,
    lines: [10, 13],
    codes: ["I001", "F811"],
    detail: "Import non trié + redéfinition pd"
  },
]
```

### BATCH C — Production ruff (UP006 / UP045 — type annotations modernes)

```
FILES_TO_FIX = [
  {
    file: "models/performance_optimizer_s41.py",
    errors: ["ruff"],
    count: 14,
    lines: [41, 41, 52, 69, 103, ...],
    codes: ["UP045", "UP006", ...],
    detail: "Dict/Tuple → dict/tuple + Optional[X] → X | None (14 violations)"
  },
  {
    file: "monitoring/cache_advanced_s42.py",
    errors: ["ruff"],
    count: 17,
    lines: [25, 54, 69, 83, 100, ...],
    codes: ["I001", "UP045", "UP006", ...],
    detail: "Import non trié + Dict → dict + Optional → X | None (17 violations)"
  },
  {
    file: "monitoring/portfolio_extension_s43.py",
    errors: ["ruff"],
    count: 23,
    lines: [33, 34, 43, 58, 58, ...],
    codes: ["UP006", ...],
    detail: "Set/Dict/List/Tuple → set/dict/list/tuple (23 violations)"
  },
]
```

### BATCH D — ARG (arguments inutilisés)

```
FILES_TO_FIX = [
  {
    file: "run_paper_tick.py",
    errors: ["ARG"],
    count: 2,
    lines: [331, 331],
    codes: ["ARG001", "ARG001"],
    detail: "Signal handler _sigint_handler(sig, frame) → renommer _sig, _frame"
  },
  {
    file: "scripts/run_backtest_v41fg.py",
    errors: ["ARG"],
    count: 1,
    lines: [120],
    codes: ["ARG001"],
    detail: "_apply_base_settings(entry_z, exit_z, half_life_cap, rediscovery) → renommer rediscovery → _rediscovery"
  },
]
```

### BATCH E — Scripts backtest pyright

```
FILES_TO_FIX = [
  {
    file: "scripts/run_backtest_v40b.py",
    errors: ["ndarray.iloc"],
    count: 2,
    lines: [142, 142],
    detail: "Cannot access attribute 'ffill' — NDArray inféré, cast explicite pd.DataFrame(...) requis"
  },
]
```

### BATCH F — Scripts backtest ruff (UP031/F541 — masse, auto-fixable)

> **52 fichiers** `scripts/run_backtest_v*.py` — ~345 violations UP031/F541  
> Auto-fixable intégralement avec `ruff check --fix --select UP031,F541,E401,UP009`

```
Top 5 fichiers:
  scripts/run_backtest_v40b.py   : 29 (UP031)
  scripts/run_backtest_v40.py    : 26 (UP031)
  scripts/run_backtest_v39.py    : 16 (UP031)
  scripts/run_backtest_v42_wf.py : 13 (UP031)
  scripts/run_backtest_v44b_sweep.py : 13 (UP031)
```

### BATCH G — Tests + divers

```
FILES_TO_FIX = [
  {
    file: "tests/test_momentum_signal.py",
    errors: ["ruff"],
    count: 1,
    lines: [12],
    codes: ["I001"],
    detail: "Import non trié (auto-fixable)"
  },
  {
    file: "demo_dashboard.py",
    errors: ["ruff"],
    count: 1,
    lines: [4],
    codes: ["I001"],
    detail: "Import non trié (auto-fixable)"
  },
]
```

---

## TOTAUX

```
ruff      : 418 violation(s)
  UP031   : 228  (scripts — auto-fix)
  F541    :  88  (scripts — auto-fix)
  UP006   :  42  (models/, monitoring/ — auto-fix)
  F811    :  16  (main.py, execution/, research/)
  I001    :  15  (divers — auto-fix)
  UP045   :   9  (models/, monitoring/ — auto-fix)
  UP009   :   9  (scripts — auto-fix)
  E401    :   5  (scripts anciens — auto-fix)
  UP017   :   2  (monitoring/logger.py — auto-fix)
  autres  :   4

ARG       : 3 violation(s)
  ARG001 × 2  run_paper_tick.py:331 (sig, frame)
  ARG001 × 1  scripts/run_backtest_v41fg.py:120 (rediscovery)

pyright   : 4 erreur(s) dans 3 fichiers
  data/             → 1 erreur · intraday_loader.py:183  (NaTType.strftime)
  models/           → 1 erreur · performance_optimizer_s41.py:130  (Unknown|int → str)
  scripts/          → 2 erreurs · run_backtest_v40b.py:142  (ndarray.ffill)

IDE PROBLEMS : 0
Tests        : 2742/2742 ✅

dossiers_propres (pyright 0 erreur):
  pair_selection, signal_engine, strategies, execution, live_trading,
  backtests, backtester, portfolio_engine, risk, risk_engine,
  execution_engine, common, config, universe, scheduler, persistence,
  monitoring, validation, research, tests/
```

---

## RÉSUMÉ PRIORISÉ

| Priorité | Batch | Fichiers | Violations | Type | Effort |
|---|---|---|---|---|---|
| 🔴 P1 | A | 2 | 4 pyright | typing / NaTType | Moyen |
| 🟠 P2 | B | 7 | ~18 ruff | I001 / F811 / UP042 | Faible |
| 🟠 P3 | C | 3 | 54 ruff | UP006 / UP045 (auto) | Trivial |
| 🟡 P4 | D | 2 | 3 ARG | ARG001 | Trivial |
| 🟡 P5 | E | 1 | 2 pyright | ndarray.ffill | Moyen |
| 🟢 P6 | F | 52 | ~345 ruff | UP031/F541 (auto) | Auto-fix |
| 🟢 P7 | G | 2 | 2 ruff | I001 (auto) | Trivial |

---

## NOTES P2

1. **`strategies/pair_trading.py` — PRIORITÉ HAUTE** : 264 erreurs sur seulement 14 lignes = code debug [P5]
   avec `print()` (interdit) + `hasattr` insuffisant. Fix recommandé : supprimer les blocs debug ou
   remplacer `hasattr(last_date, "year")` par `isinstance(last_date, pd.Timestamp)`.

2. **`data/loader.py:95`** : `df.rename(str)` → utiliser `df.rename(columns={...})` ou `df.rename(index=str)`.

3. **`data/feature_store.py:123`** : IDE-only (stubs). Cast `engine=cast(Any, "pyarrow")` ou ignorer.

4. **`benchmarks/spx_comparison.py`** : fichier hors production — priorité basse.
   - L14 escape seq : utiliser raw string `r"venv\Scripts\..."` dans docstring.
   - L227 ARG001 : renommer `ec` → `_ec`, `spy` → `_spy` (convention unused param).
