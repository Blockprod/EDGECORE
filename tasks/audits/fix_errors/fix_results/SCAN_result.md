---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/SCAN_result.md
derniere_revision: 2026-04-04
creation: 2026-03-26
---

# SCAN RESULT — EDGECORE

> Revision 2026-04-04 — scan post plan-d'action #17 + G3-01

## ÉTAT GLOBAL

| Outil | Résultat |
|-------|---------|
| ruff (global) | ❌ 3 violations (UP037×1, UP017×2) |
| ruff --select ARG | ❌ 2 violations (ARG001×2) |
| pyright (44 dossiers) | ❌ 3 dossiers KO · 269 erreurs |
| get_errors (IDE) | ❌ 2 fichiers supplémentaires |

---

## FILES_TO_FIX

```
FILES_TO_FIX = [
  {
    file: "strategies/pair_trading.py",
    errors: ["typing"],
    count: 264,
    lines: [927, 935, 960, 984, 991, 996, 1017, 1030, 1038, 1055, 1062, 1063, 1286, 1287],
    detail: [
      "264 × reportAttributeAccessIssue — .year / .month sur Index générique (non-narrowé)",
      "Pattern: last_date = market_data.index.max() puis last_date.year → Index pas narrowé en Timestamp",
      "Cause: hasattr(last_date, 'year') ne suffit pas pour pyright — il faut isinstance(last_date, pd.Timestamp)",
      "Note: toutes ces lignes sont du code DEBUG [P5] avec print() — à supprimer selon règle ❌ print()"
    ]
  },
  {
    file: "backtests/strategy_simulator.py",
    errors: ["typing"],
    count: 3,
    lines: [399, 399, 401],
    detail: [
      "L399 : reportAttributeAccessIssue — .year sur Index",
      "L399 : reportAttributeAccessIssue — .month sur Index",
      "L401 : reportAttributeAccessIssue — .date sur Index"
    ]
  },
  {
    file: "data/loader.py",
    errors: ["typing"],
    count: 2,
    lines: [95, 95],
    detail: [
      "L95 : reportCallIssue — No overloads for 'rename' match the provided arguments",
      "L95 : reportArgumentType — Argument of type 'str' cannot be assigned to parameter 'mapper' of type 'Renamer | None'"
    ]
  },
  {
    file: "data/feature_store.py",
    errors: ["typing"],
    count: 1,
    lines: [123],
    detail: [
      "L123 : IDE only (Pylance) — Literal['pyarrow'] not assignable to Literal['auto', 'fastparquet']",
      "Cause: pandas stubs incomplets pour pyarrow engine (runtime correct, stub incorrect)"
    ]
  },
  {
    file: "benchmarks/spx_comparison.py",
    errors: ["ruff", "ARG", "syntax"],
    count: 5,
    lines: [14, 14, 191, 227, 227],
    detail: [
      "L14   : IDE — Unsupported escape sequence in string literal (docstring avec chemin Windows)",
      "L191  : ruff UP017 — 'timezone.utc' → 'datetime.UTC'",
      "L227  : ruff ARG001 — 'ec: dict' unused in _interpret()",
      "L227  : ruff ARG001 — 'spy: dict' unused in _interpret()"
    ]
  },
  {
    file: "backtests/walk_forward.py",
    errors: ["ruff"],
    count: 2,
    lines: [618, 669],
    detail: [
      "L618  : ruff UP037 — quoted type annotation '\"WalkForwardResult\"' → supprimer les guillemets",
      "L669  : ruff UP017 — 'timezone.utc' → 'datetime.UTC'"
    ]
  }
]
```

---

## TOTAUX

```
ruff      : 3 violation(s)  [UP037×1, UP017×2]
ARG       : 2 violation(s)  [ARG001×2 dans benchmarks/spx_comparison.py:227]
pyright   : 269 erreur(s) dans 3 dossiers (3 fichiers)
  strategies/  → 264 erreurs · 1 fichier  (pair_trading.py — code DEBUG P5)
  backtests/   →   3 erreurs · 1 fichier  (strategy_simulator.py)
  data/        →   2 erreurs · 1 fichier  (loader.py)
IDE only  : 2 erreurs supplémentaires (feature_store.py, spx_comparison.py)

dossiers_propres: [
  models, pair_selection, signal_engine, execution, live_trading,
  backtester, portfolio_engine, risk, risk_engine, execution_engine,
  common, config, universe, scheduler, persistence, monitoring,
  validation, research, scripts,
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
| `typing` | `strategies/pair_trading.py` | 927,935,960,984,991,996,1017,1030,1038,1055,1062,1063,1286,1287 | `.year`/`.month` sur `Index` non-narrowé par `hasattr` |
| `typing` | `backtests/strategy_simulator.py` | 399,401 | `.year`, `.month`, `.date` sur `Index` |
| `typing` | `data/loader.py` | 95 | `rename(str)` → overload incompatible avec `Renamer \| None` |
| `typing` | `data/feature_store.py` | 123 | `engine='pyarrow'` — stubs pandas incomplets (IDE only) |
| `ruff` | `backtests/walk_forward.py` | 618, 669 | UP037 quoted annotation · UP017 timezone |
| `ruff` | `benchmarks/spx_comparison.py` | 191 | UP017 timezone |
| `ARG` | `benchmarks/spx_comparison.py` | 227 | ARG001 `ec`, `spy` inutilisés dans `_interpret()` |
| `syntax` | `benchmarks/spx_comparison.py` | 14 | Escape sequence non-supportée dans docstring (IDE only) |

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
