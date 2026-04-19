---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/fix_results/SCAN_result.md
derniere_revision: 2026-04-19
creation: 2026-03-26
---

# SCAN RESULT — EDGECORE

> Revision 2026-04-19 — scan complet post-corrections
> Revision précédente: 2026-04-06 — 12 ruff + 13 pyright

## ÉTAT GLOBAL

| Outil | Résultat |
|-------|---------|
| ruff (global) | ✅ 0 violation |
| ruff --select ARG | ✅ 0 violation |
| pyright (22 dirs prod) | ✅ 0 erreur |
| pyright (23 dirs tests) | ✅ 0 erreur |
| get_errors (IDE) | ✅ 0 erreur |

---

## FILES_TO_FIX

```
FILES_TO_FIX = []
```

---

## TOTAUX

```
TOTAUX:
  ruff      : 0 violation(s)  ✅
  ARG       : 0 violation(s)  ✅
  pyright   : 0 erreur(s) dans 0 fichier  ✅
  get_errors IDE : 0  ✅

  dossiers_propres_prod: [
    "models", "pair_selection", "signal_engine", "strategies",
    "execution", "data", "live_trading", "backtests", "backtester",
    "portfolio_engine", "risk", "risk_engine", "execution_engine",
    "common", "config", "universe", "scheduler", "persistence",
    "monitoring", "validation", "research", "scripts"
  ]

  dossiers_propres_tests: [
    "tests/backtests", "tests/common", "tests/config", "tests/data",
    "tests/edgecore", "tests/execution", "tests/execution_engine",
    "tests/integration", "tests/live_trading", "tests/models",
    "tests/monitoring", "tests/persistence", "tests/phase3",
    "tests/phase4", "tests/portfolio_engine", "tests/regression",
    "tests/risk", "tests/risk_engine", "tests/signal_engine",
    "tests/statistical", "tests/strategies", "tests/universe",
    "tests/validation"
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
