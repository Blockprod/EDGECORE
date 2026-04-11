---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/fix_results/SCAN_result.md
derniere_revision: 2026-04-06
creation: 2026-03-26
---

# SCAN RESULT — EDGECORE

> Revision 2026-04-06 — scan post P0→P5-03 (2764/2768 ✅, 0 CVE, 0 Bandit H/M)

## ÉTAT GLOBAL

| Outil | Résultat |
|-------|---------|
| ruff (global) | ❌ 12 violations · 4 fichiers prod + 1 test |
| ruff --select ARG | ✅ 0 violation |
| pyright (22 dirs prod) | ❌ 6 erreurs · 1 fichier (`execution/ml_impact.py`) |
| pyright (23 dirs tests) | ❌ 7 erreurs · 5 fichiers |
| get_errors (IDE) | ✅ 0 erreur |
| pytest | ✅ 2764/2768 (4 pre-existing) |

---

## FILES_TO_FIX

```
FILES_TO_FIX = [

  # ── PYRIGHT PROD ─────────────────────────────────────────────────────────────

  {
    file: "execution/ml_impact.py",
    errors: ["typing"],
    count: 6,
    lines: [135, 136, 137, 138, 139, 140],
    details: "reportArgumentType — ndarray[Unknown,Unknown]|None cannot be assigned to ArrayLike in numpy.savez(). W1, b1, W2, b2, W3, b3 are Optional[ndarray] but numpy.savez expects ArrayLike. Root: weights initialized to None before training.",
    pyright_code: "reportArgumentType",
    fix: "assert self.W1 is not None (and other weights) before savez block, or cast(np.ndarray, self.W1)"
  },

  # ── PYRIGHT TESTS ─────────────────────────────────────────────────────────────

  {
    file: "tests/execution/test_ibkr_crash_recovery.py",
    errors: ["typing"],
    count: 1,
    lines: [51],
    details: "reportInvalidTypeForm — Type annotation not supported for this statement",
    pyright_code: "reportInvalidTypeForm",
    fix: "Rewrite annotation as standard variable annotation or remove if test-only mock"
  },

  {
    file: "tests/execution/test_ibkr_disconnect_during_order.py",
    errors: ["typing"],
    count: 1,
    lines: [47],
    details: "reportInvalidTypeForm — Type annotation not supported for this statement",
    pyright_code: "reportInvalidTypeForm",
    fix: "Same pattern as above"
  },

  {
    file: "tests/live_trading/test_live_trading_recovery.py",
    errors: ["typing"],
    count: 1,
    lines: [29],
    details: "reportAttributeAccessIssue — Cannot assign `_positions_lock`. LockType is not assignable to RLock.",
    pyright_code: "reportAttributeAccessIssue",
    fix: "Cast: runner._positions_lock = cast(RLock, threading.Lock())"
  },

  {
    file: "tests/monitoring/042_test_api.py",
    errors: ["typing"],
    count: 1,
    lines: [576],
    details: "reportAttributeAccessIssue — Cannot assign to `_system_metrics` for class Flask. Attribute unknown.",
    pyright_code: "reportAttributeAccessIssue",
    fix: "Use setattr(app, '_system_metrics', mock_metrics) or type: ignore with explicit comment"
  },

  {
    file: "tests/universe/test_universe_pit.py",
    errors: ["Timestamp"],
    count: 3,
    lines: [268, 276, 283],
    details: "reportArgumentType — Timestamp|NaTType not assignable to Timestamp|None parameter of get_snapshot(). NaTType is not None.",
    pyright_code: "reportArgumentType",
    fix: "Guard: ts if not pd.isna(ts) else None before passing to get_snapshot()"
  },

  # ── RUFF ─────────────────────────────────────────────────────────────────────

  {
    file: "execution_engine/router.py",
    errors: ["ruff-F811"],
    count: 1,
    lines: [353],
    details: "F811 — Redefinition of unused `_time` from line 243",
    fixable: true,
    fix: "Remove or rename duplicate `_time` at line 353"
  },

  {
    file: "risk/engine.py",
    errors: ["ruff-UP017"],
    count: 2,
    lines: [97, 459],
    details: "UP017 — Use `datetime.UTC` alias instead of `timezone.utc`",
    fixable: true,
    fix: "ruff check --fix --select UP017 risk/engine.py"
  },

  {
    file: "risk_engine/portfolio_risk.py",
    errors: ["ruff-UP017"],
    count: 2,
    lines: [94, 282],
    details: "UP017 — Use `datetime.UTC` alias instead of `timezone.utc`",
    fixable: true,
    fix: "ruff check --fix --select UP017 risk_engine/portfolio_risk.py"
  },

  {
    file: "strategies/pair_trading.py",
    errors: ["ruff-F401"],
    count: 2,
    lines: [3, 20],
    details: [
      "L3  — F401: `datetime.timedelta` imported but unused",
      "L20 — F401: `models.cointegration.newey_west_consensus` imported but unused"
    ],
    fixable: true,
    fix: "ruff check --fix --select F401 strategies/pair_trading.py"
  },

  {
    file: "tests/models/test_kalman_hedge.py",
    errors: ["ruff-B905"],
    count: 5,
    lines: [382, 392, 405, 419, 424],
    details: "B905 — zip() without explicit strict= parameter",
    fixable: false,
    fix: "Add strict=False (or strict=True if mismatched lengths should raise) to each zip() call"
  },

]
```

---

## TOTAUX

```
TOTAUX:
  ruff      : 12 violation(s)
    F811    : 1  (execution_engine/router.py:353)
    UP017   : 4  (risk/engine.py:97,459 · risk_engine/portfolio_risk.py:94,282)
    F401    : 2  (strategies/pair_trading.py:3,20)
    B905    : 5  (tests/models/test_kalman_hedge.py:382,392,405,419,424)

  ARG       : 0 violation(s)  ✅

  pyright   : 13 erreur(s) dans 6 fichiers
    prod (1 fichier) :
      execution/ml_impact.py:135-140   → 6× reportArgumentType (ndarray|None → ArrayLike)
    tests (5 fichiers) :
      tests/execution/test_ibkr_crash_recovery.py:51        → 1× reportInvalidTypeForm
      tests/execution/test_ibkr_disconnect_during_order.py:47 → 1× reportInvalidTypeForm
      tests/live_trading/test_live_trading_recovery.py:29   → 1× reportAttributeAccessIssue
      tests/monitoring/042_test_api.py:576                  → 1× reportAttributeAccessIssue
      tests/universe/test_universe_pit.py:268,276,283       → 3× reportArgumentType (Timestamp|NaTType)

  get_errors IDE : 0  ✅
  pytest         : 2764/2768 (4 pre-existing failures unrelated to fixes)

  dossiers_propres_prod: [
    "models", "pair_selection", "signal_engine",
    "data", "live_trading", "backtests", "backtester", "portfolio_engine",
    "common", "config", "universe", "scheduler", "persistence", "monitoring",
    "validation", "research"
    // pyright-only also clean: execution_engine, risk, risk_engine
    // (only ruff UP017/F811 violations in those 3)
  ]

  dossiers_propres_tests: [
    "tests/backtests", "tests/common", "tests/config", "tests/data",
    "tests/edgecore", "tests/execution_engine", "tests/integration",
    "tests/models", "tests/persistence", "tests/phase3", "tests/phase4",
    "tests/portfolio_engine", "tests/regression", "tests/risk",
    "tests/risk_engine", "tests/signal_engine", "tests/statistical",
    "tests/strategies", "tests/validation"
  ]
```

---

## DÉTAIL PAR PRIORITÉ

### 🔴 CRITIQUE — Pyright prod (blocage compilation strict)

| # | Fichier | Lignes | Code pyright | Description |
|---|---|---|---|---|
| P1 | `execution/ml_impact.py` | 135–140 | reportArgumentType | 6× `ndarray\|None` → `ArrayLike` dans numpy.savez() |

**Fix** : ajouter `assert self.W1 is not None` (+ W2/W3/b1/b2/b3) avant le bloc `np.savez`, ou utiliser `cast(np.ndarray, self.W1)`.

---

### 🟠 IMPORTANT — Pyright tests

| # | Fichier | Ligne | Code pyright | Description |
|---|---|---|---|---|
| T1 | `tests/execution/test_ibkr_crash_recovery.py` | 51 | reportInvalidTypeForm | Annotation type non supportée |
| T2 | `tests/execution/test_ibkr_disconnect_during_order.py` | 47 | reportInvalidTypeForm | Annotation type non supportée |
| T3 | `tests/live_trading/test_live_trading_recovery.py` | 29 | reportAttributeAccessIssue | `LockType` ≠ `RLock` pour `_positions_lock` |
| T4 | `tests/monitoring/042_test_api.py` | 576 | reportAttributeAccessIssue | `_system_metrics` inconnu sur Flask |
| T5 | `tests/universe/test_universe_pit.py` | 268, 276, 283 | reportArgumentType | `Timestamp\|NaTType` → `Timestamp\|None` |

---

### 🟡 MINEUR — Ruff (style, auto-fixable majoritairement)

| # | Fichier | Lignes | Code | Description |
|---|---|---|---|---|
| R1 | `execution_engine/router.py` | 353 | F811 | Redéfinition `_time` (auto-fix) |
| R2 | `risk/engine.py` | 97, 459 | UP017 | `timezone.utc` → `datetime.UTC` (auto-fix) |
| R3 | `risk_engine/portfolio_risk.py` | 94, 282 | UP017 | `timezone.utc` → `datetime.UTC` (auto-fix) |
| R4 | `strategies/pair_trading.py` | 3, 20 | F401 | Imports inutilisés (auto-fix) |
| R5 | `tests/models/test_kalman_hedge.py` | 382, 392, 405, 419, 424 | B905 | `zip()` sans `strict=` (manuel) |

---

*SCAN complet — 2026-04-06. Prêt pour P2 — PLAN.*


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
