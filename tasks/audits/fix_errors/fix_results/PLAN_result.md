---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/PLAN_result.md
derniere_revision: 2026-04-04
creation: 2026-03-26
---

# PLAN DE CORRECTION — EDGECORE

> Revision 2026-04-04 — basé sur SCAN_result.md (rev. 2026-04-04)

## LOGIQUE DE BATCHING

**Observation clé** : 264 des 269 erreurs pyright sont dans `strategies/pair_trading.py`
et `backtests/strategy_simulator.py`, toutes causées par le **même pattern** :
des blocs debug `[DEBUG][P5]` utilisant `hasattr(last_date, "year")` (insuffisant
pour pyright) et des `print()` (interdit par convention). La suppression de ces
blocs résout en une seule opération 267 erreurs sur 275.

**Dépendances batch** :
- `data/` est importé par `strategies/` → corriger `data/` en premier.
- `backtests/walk_forward.py` (ruff) est indépendant des deux autres batches backtests.
- `benchmarks/` est hors pipeline production — traité en dernier.

**Ordre** : data → strategies → backtests → benchmarks

---

## PLAN

```
PLAN = [
  {
    batch      : 1,
    module     : "data/",
    files      : [
      "data/loader.py",
      "data/feature_store.py"
    ],
    error_types    : ["typing"],
    estimated_fixes: 3,
    difficulty     : "Facile",
    patterns       : [
      "L95 loader.py  : Series.rename(str) → pd.Series(s, name=sym) — surcharge incompatible avec Renamer|None",
      "L123 feature_store.py : engine='pyarrow' (stubs pandas incomplets, IDE-only) → cast(Any, 'pyarrow')"
    ],
    fix_detail : [
      {
        file  : "data/loader.py",
        line  : 95,
        old   : "s = cached_df.iloc[:, 0].rename(sym)",
        new   : "s = pd.Series(cached_df.iloc[:, 0], name=sym)",
        rule  : "reportCallIssue / reportArgumentType"
      },
      {
        file  : "data/feature_store.py",
        line  : 123,
        old   : "series = pd.read_parquet(path, engine=\"pyarrow\")[\"value\"]",
        new   : "series = pd.read_parquet(path, engine=cast(Any, \"pyarrow\"))[\"value\"]",
        note  : "Ajouter 'from typing import Any, cast' si absent"
      }
    ],
    validation : "venv\\Scripts\\python.exe -m pytest tests\\data\\ -q --tb=no"
  },

  {
    batch      : 2,
    module     : "strategies/",
    files      : [
      "strategies/pair_trading.py"
    ],
    error_types    : ["typing", "print"],
    estimated_fixes: 264,
    difficulty     : "Facile",
    patterns       : [
      "264 × reportAttributeAccessIssue — .year/.month sur Index non-narrowé",
      "Root cause unique : blocs DEBUG [P5] avec hasattr(last_date, 'year') insuffisant pour pyright",
      "Co-violation : print() dans chaque bloc — interdit par convention (→ structlog)"
    ],
    fix_strategy : "Supprimer les 14 blocs debug [P5] complets (lignes 927→1287).",
    fix_detail : "Les blocs sont délimités par 'try: ... if hasattr(last_date, \"year\") ... print(f\"[DEBUG][P5]...\")' — supprimer chaque bloc entier de la try à la dernière print(). Aucun impact fonctionnel (code de diagnostic temporaire).",
    scope : {
      lines_affected : [927, 935, 960, 984, 991, 996, 1017, 1030, 1038, 1055, 1062, 1063, 1286, 1287],
      blocks_to_delete : 14,
      errors_per_block : "~18-19 (fan-out Union type)"
    },
    validation : "venv\\Scripts\\python.exe -m pytest tests\\strategies\\ -q --tb=no"
  },

  {
    batch      : 3,
    module     : "backtests/",
    files      : [
      "backtests/strategy_simulator.py",
      "backtests/walk_forward.py"
    ],
    error_types    : ["typing", "ruff", "print"],
    estimated_fixes: 5,
    difficulty     : "Facile",
    patterns       : [
      "strategy_simulator.py L399-403 : même pattern DEBUG [P5] que batch 2 — supprimer le bloc",
      "walk_forward.py L618 : UP037 — '\"WalkForwardResult\"' → WalkForwardResult (annotation non-quotée)",
      "walk_forward.py L669 : UP017 — timezone.utc → datetime.UTC"
    ],
    fix_detail : [
      {
        file  : "backtests/strategy_simulator.py",
        lines : [396, 403],
        action: "Supprimer le bloc debug P5 (try: if hasattr(bar_date, 'year') ... print(f'[DEBUG][P5]...'))",
        errors_fixed: 3
      },
      {
        file  : "backtests/walk_forward.py",
        line  : 618,
        old   : "-> \"WalkForwardResult\":",
        new   : "-> WalkForwardResult:",
        rule  : "UP037"
      },
      {
        file  : "backtests/walk_forward.py",
        line  : 669,
        old   : "timezone.utc",
        new   : "datetime.UTC",
        rule  : "UP017"
      }
    ],
    validation : "venv\\Scripts\\python.exe -m pytest tests\\backtests\\ -q --tb=no"
  },

  {
    batch      : 4,
    module     : "benchmarks/  (hors production)",
    files      : [
      "benchmarks/spx_comparison.py"
    ],
    error_types    : ["ruff", "ARG", "syntax"],
    estimated_fixes: 5,
    difficulty     : "Facile",
    fix_detail : [
      {
        file  : "benchmarks/spx_comparison.py",
        line  : "7-14 (docstring)",
        old   : "\"\"\"writes ...\n    venv\\Scripts\\python.exe ...\"\"\"",
        new   : "r\"\"\"writes ...\n    venv\\Scripts\\python.exe ...\"\"\"",
        rule  : "syntax IDE — escape sequence"
      },
      {
        file  : "benchmarks/spx_comparison.py",
        line  : 191,
        old   : "timezone.utc",
        new   : "datetime.UTC",
        rule  : "UP017"
      },
      {
        file  : "benchmarks/spx_comparison.py",
        line  : 227,
        old   : "def _interpret(ec: dict, spy: dict, sharpe_alpha: ...",
        new   : "def _interpret(_ec: dict, _spy: dict, sharpe_alpha: ...",
        rule  : "ARG001 — params ec et spy non utilisés dans le corps"
      }
    ],
    validation : "ruff check benchmarks/spx_comparison.py"
  }

]
```

---

## RÉSUMÉ

```
RÉSUMÉ:
  total_batches    : 4
  total_files      : 6
  estimated_fixes  : 277  (264 pyright + 3 typing + 5 backtests + 5 benchmarks)
  dominant_pattern : blocs debug [P5] avec print() — 267 / 277 erreurs (~96%)
  ordre_validation : pytest → ruff → pyright par batch

  batch_1 : data/         → 2 fichiers · 3 fixes   · Facile
  batch_2 : strategies/   → 1 fichier  · 264 fixes · Facile (suppression blocs)
  batch_3 : backtests/    → 2 fichiers · 5 fixes   · Facile
  batch_4 : benchmarks/   → 1 fichier  · 5 fixes   · Facile (hors production)
```

---

## VALIDATION FINALE

```powershell
# 1. Pyright — seuls les 3 dossiers KO
pyright strategies data backtests 2>&1 | Select-Object -Last 3

# 2. Ruff
venv\Scripts\python.exe -m ruff check . --exclude venv,__pycache__,build 2>&1 | Select-Object -Last 5

# 3. Tests complets
venv\Scripts\python.exe -m pytest tests/ -q --tb=no 2>&1 | Select-Object -Last 3
```

---

## NOTE STRATÉGIQUE

Le ratio 264/277 erreurs dues à du code debug [P5] temporaire illustre qu'un **nettoyage
de code mort** (blocs print/diagnostic) génère plus de valeur que des micro-fixes typing.
La règle `❌ print()` du projet copilot-instructions.md aurait dû empêcher l'introduction
de ces blocs. La suppression restaure pyright à 0 erreur sur `strategies/` sans aucun
risque de régression fonctionnelle.
