---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/fix_results/PLAN_result.md
derniere_revision: 2026-04-06
creation: 2026-03-26
---

# PLAN DE CORRECTION — EDGECORE

> Revision 2026-04-06 — basé sur SCAN_result.md (rev. 2026-04-06)

## LOGIQUE DE BATCHING

**Contexte** : 13 erreurs pyright dans 6 fichiers, 12 violations ruff dans 5 fichiers, 0 ARG.
Le bilan est très propre post-P0→P5-03. Il reste un bug de typing prod (`ml_impact.py`),
4 violations ruff auto-fixables dans prod, 5 violations ruff manuelles dans les tests,
et 5 erreurs pyright dans les tests.

**Dépendances critiques** :
- `execution/ml_impact.py` → pyright typing prod — à corriger en priorité (batch prod)
- `strategies/pair_trading.py` → ruff F401 (imports inutilisés, aucun consommateur impacté)
- `risk/engine.py` + `risk_engine/portfolio_risk.py` → ruff UP017 (style uniquement, auto-fix)
- `execution_engine/router.py` → ruff F811 (_time redéfini, auto-fix)
- Tests : corrections isolées, aucune dépendance inter-test

**Ordre** : strategies/ → execution/ + execution_engine/ → risk/ + risk_engine/ → tests

---

## PLAN

```
PLAN = [
  {
    batch      : 1,
    module     : "strategies/",
    files      : [
      "strategies/pair_trading.py"
    ],
    error_types    : ["ruff-F401"],
    estimated_fixes: 2,
    difficulty     : "Facile (auto-fix)",
    fix_detail : [
      {
        file  : "strategies/pair_trading.py",
        line  : 3,
        type  : "ruff F401",
        issue : "datetime.timedelta imported but unused",
        fix   : "Supprimer `timedelta` du import datetime (garder uniquement datetime si utilisé)"
      },
      {
        file  : "strategies/pair_trading.py",
        line  : 20,
        type  : "ruff F401",
        issue : "models.cointegration.newey_west_consensus imported but unused",
        fix   : "Supprimer la ligne d'import `newey_west_consensus`"
      }
    ],
    command    : "venv\\Scripts\\python.exe -m ruff check --fix --select F401 strategies/pair_trading.py",
    validation : "venv\\Scripts\\python.exe -m pytest tests\\strategies\\ -q --tb=no"
  },

  {
    batch      : 2,
    module     : "execution/ + execution_engine/",
    files      : [
      "execution/ml_impact.py",
      "execution_engine/router.py"
    ],
    error_types    : ["typing", "ruff-F811"],
    estimated_fixes: 7,
    difficulty     : "Moyen",
    fix_detail : [
      {
        file  : "execution/ml_impact.py",
        lines : [135, 136, 137, 138, 139, 140],
        type  : "pyright reportArgumentType",
        issue : "ndarray[Unknown,Unknown]|None cannot be assigned to ArrayLike in numpy.savez(). W1/b1/W2/b2/W3/b3 are Optional[ndarray].",
        root  : "Weights initialized to None at class level: self.W1 = None. Pyright cannot narrow to non-None inside save() without explicit guard.",
        fix   : "Add assert guard before np.savez block:\n  if self.W1 is None or self.b1 is None or self.W2 is None or self.b2 is None or self.W3 is None or self.b3 is None:\n      raise RuntimeError('Model not trained — call fit() before save()')\n  np.savez(str(filepath.with_suffix('.npz')), W1=self.W1, ...)",
        note  : "Le guard est sémantiquement correct : save() n'a pas de sens sur un modèle non entraîné."
      },
      {
        file  : "execution_engine/router.py",
        line  : 353,
        type  : "ruff F811",
        issue : "Redefinition of unused `_time` from line 243",
        fix   : "Renommer la variable redéfinie à L353 en `_time2` ou supprimer si doublon réel",
        command: "Vérifier le contexte L240-260 et L350-360 avant fix"
      }
    ],
    validation : "venv\\Scripts\\python.exe -m pytest tests\\execution\\ tests\\execution_engine\\ -q --tb=no"
  },

  {
    batch      : 3,
    module     : "risk/ + risk_engine/",
    files      : [
      "risk/engine.py",
      "risk_engine/portfolio_risk.py"
    ],
    error_types    : ["ruff-UP017"],
    estimated_fixes: 4,
    difficulty     : "Facile (auto-fix)",
    fix_detail : [
      {
        files : ["risk/engine.py", "risk_engine/portfolio_risk.py"],
        lines : {"risk/engine.py": [97, 459], "risk_engine/portfolio_risk.py": [94, 282]},
        type  : "ruff UP017",
        issue : "Use datetime.UTC alias instead of timezone.utc",
        command: "venv\\Scripts\\python.exe -m ruff check --fix --select UP017 risk/engine.py risk_engine/portfolio_risk.py",
        note  : "Vérifier que `from datetime import timezone` est supprimé si plus utilisé après fix"
      }
    ],
    validation : "venv\\Scripts\\python.exe -m pytest tests\\risk\\ tests\\risk_engine\\ -q --tb=no"
  },

  {
    batch      : 4,
    module     : "tests/models + tests/execution",
    files      : [
      "tests/models/test_kalman_hedge.py",
      "tests/execution/test_ibkr_crash_recovery.py",
      "tests/execution/test_ibkr_disconnect_during_order.py"
    ],
    error_types    : ["ruff-B905", "typing"],
    estimated_fixes: 7,
    difficulty     : "Facile",
    fix_detail : [
      {
        file  : "tests/models/test_kalman_hedge.py",
        lines : [382, 392, 405, 419, 424],
        type  : "ruff B905",
        issue : "zip() without explicit strict= parameter",
        fix   : "Ajouter strict=False à chaque appel zip() (les séquences peuvent être de longueurs différentes en test)",
        example: "for yi, xi in zip(y, x, strict=False):"
      },
      {
        file  : "tests/execution/test_ibkr_crash_recovery.py",
        line  : 51,
        type  : "pyright reportInvalidTypeForm",
        issue : "Type annotation not supported for this statement",
        fix   : "Lire le contexte L49-53 — probablement une annotation inline sur une variable locale dans un bloc mock/patch. Réécrire en annotation séparée ou supprimer l'annotation.",
        example: "# Avant: mock_client: Mock = patch(...)\n# Après: mock_client = patch(...)  # type: Mock"
      },
      {
        file  : "tests/execution/test_ibkr_disconnect_during_order.py",
        line  : 47,
        type  : "pyright reportInvalidTypeForm",
        issue : "Même pattern que ci-dessus",
        fix   : "Même correction"
      }
    ],
    validation : "venv\\Scripts\\python.exe -m pytest tests\\models\\ tests\\execution\\ -q --tb=no"
  },

  {
    batch      : 5,
    module     : "tests/live_trading + tests/monitoring + tests/universe",
    files      : [
      "tests/live_trading/test_live_trading_recovery.py",
      "tests/monitoring/042_test_api.py",
      "tests/universe/test_universe_pit.py"
    ],
    error_types    : ["typing"],
    estimated_fixes: 5,
    difficulty     : "Moyen",
    fix_detail : [
      {
        file  : "tests/live_trading/test_live_trading_recovery.py",
        line  : 29,
        type  : "pyright reportAttributeAccessIssue",
        issue : "Cannot assign to `_positions_lock`. LockType is not assignable to RLock.",
        fix   : "cast(threading.RLock, threading.Lock()) ou utiliser RLock directement:\n  runner._positions_lock = cast(threading.RLock, threading.RLock())",
        note  : "Vérifier que `from typing import cast` et `import threading` sont importés dans le test"
      },
      {
        file  : "tests/monitoring/042_test_api.py",
        line  : 576,
        type  : "pyright reportAttributeAccessIssue",
        issue : "Cannot assign to attribute `_system_metrics` for class Flask. Attribute unknown.",
        fix   : "Remplacer l'assignation directe par setattr:\n  setattr(app, '_system_metrics', mock_metrics)",
        note  : "setattr contourne le type checker pour les attributs dynamiques de Flask"
      },
      {
        file  : "tests/universe/test_universe_pit.py",
        lines : [268, 276, 283],
        type  : "pyright reportArgumentType",
        issue : "Timestamp|NaTType not assignable to Timestamp|None parameter of get_snapshot()",
        fix   : "Ajouter guard NaT avant chaque appel:\n  ts_val = ts if not pd.isna(ts) else None\n  snapshot = history.get_snapshot(ts_val)",
        note  : "pd.isna(NaT) retourne True — le guard est correct"
      }
    ],
    validation : "venv\\Scripts\\python.exe -m pytest tests\\live_trading\\ tests\\monitoring\\ tests\\universe\\ -q --tb=no"
  }
]
```

---

## RÉSUMÉ

```
RÉSUMÉ:
  total_batches    : 5
  total_files      : 11
  estimated_fixes  : 25  (13 pyright + 12 ruff)
  dominant_pattern : pyright typing (Optional[ndarray], Timestamp|NaTType, AttributeAccess)
  ordre_validation : pytest par batch → ruff global → pyright global

  batch_1 : strategies/              → 1 fichier  · 2 fixes  · Facile (auto-fix F401)
  batch_2 : execution/+exec_engine/  → 2 fichiers · 7 fixes  · Moyen  (assert guard + F811)
  batch_3 : risk/+risk_engine/       → 2 fichiers · 4 fixes  · Facile (auto-fix UP017)
  batch_4 : tests/models+execution   → 3 fichiers · 7 fixes  · Facile (strict=False + TypeForm)
  batch_5 : tests/live+monitoring+universe → 3 fichiers · 5 fixes · Moyen (cast/setattr/NaT)

  cible_post_fix:
    ruff    : 0 violation
    pyright : 0 erreur prod · 0 erreur tests
    ARG     : 0 violation ✅ (déjà propre)
    pytest  : ≥ 2764/2768 (maintenir les 4 pré-existants au maximum)
```

---

*PLAN complet — 2026-04-06. Prêt pour P3 — FIX batch par batch.*


## LOGIQUE DE BATCHING

**Contexte** : 4 erreurs pyright dans 3 fichiers, 418 violations ruff (~65 fichiers), 3 ARG.
Des 418 violations ruff, ~345 sont dans des scripts historiques `run_backtest_v*.py` et sont
100 % auto-fixables. Le cœur du travail manuel porte sur ~73 violations dans 15 fichiers de production.

**Dépendances critiques** :
- `models/performance_optimizer_s41.py` → importé par `tests/models/` uniquement
- `execution/modes_legacy.py` → importé par tests, conftest, scripts — changer UP042 (StrEnum) sans toucher aux valeurs
- `execution/order_lifecycle_integration.py` → importé par `main.py` — corriger avant main.py
- `data/intraday_loader.py` → pyright NaTType, isolation totale, aucun impactant
- `monitoring/cache_advanced_s42.py` + `portfolio_extension_s43.py` → importés par tests monitoring uniquement

**Ordre** : models → execution → data → monitoring + backtests → research + ARG → main + scripts mass → tests

---

## PLAN

```
PLAN = [
  {
    batch      : 1,
    module     : "models/",
    files      : [
      "models/performance_optimizer_s41.py"
    ],
    error_types    : ["typing", "ruff"],
    estimated_fixes: 15,
    difficulty     : "Facile",
    fix_detail : [
      {
        file  : "models/performance_optimizer_s41.py",
        line  : 130,
        type  : "pyright",
        issue : "Argument of type 'Unknown | int' for parameter 'pair_key' of type 'str'",
        old   : "entry_t, exit_t = self.get_thresholds_for_pair(pair, **...)",
        new   : "entry_t, exit_t = self.get_thresholds_for_pair(str(pair), **...)",
        rule  : "reportArgumentType"
      },
      {
        file  : "models/performance_optimizer_s41.py",
        lines : [41, 52, 69, 103, ...],
        type  : "ruff",
        count : 14,
        codes : ["UP006", "UP045"],
        fix   : "ruff check --fix --select UP006,UP045 models/performance_optimizer_s41.py"
      }
    ],
    validation : "venv\\Scripts\\python.exe -m pytest tests\\models\\ -q --tb=no"
  },

  {
    batch      : 2,
    module     : "execution/",
    files      : [
      "execution/modes_legacy.py",
      "execution/order_lifecycle_integration.py"
    ],
    error_types    : ["ruff"],
    estimated_fixes: 4,
    difficulty     : "Facile",
    fix_detail : [
      {
        file  : "execution/modes_legacy.py",
        line  : 39,
        type  : "ruff UP042",
        old   : "class OrderStatus(str, Enum):",
        new   : "class OrderStatus(str, Enum):  # noqa: UP042",
        note  : "⚠️ StrEnum changerait le comportement de comparaison — conserver str+Enum et ignorer UP042 (fichier legacy archivé)"
      },
      {
        file  : "execution/order_lifecycle_integration.py",
        lines : [14, 17],
        type  : "ruff F811 + I001",
        issue : "Duplicate import OrderLifecycleManager + OrderStatus (L14 et L17) + import non trié",
        fix   : "Supprimer les lignes 16-17 (duplicates) ; trier les imports selon isort"
      }
    ],
    validation : "venv\\Scripts\\python.exe -m pytest tests\\execution\\ tests\\integration\\ -q --tb=no"
  },

  {
    batch      : 3,
    module     : "data/",
    files      : [
      "data/intraday_loader.py"
    ],
    error_types    : ["Timestamp"],
    estimated_fixes: 1,
    difficulty     : "Moyen",
    fix_detail : [
      {
        file  : "data/intraday_loader.py",
        line  : 183,
        type  : "pyright",
        issue : "Cannot access attribute 'strftime' for class 'NaTType' — req_end inféré comme Timestamp|NaTType",
        root  : "req_end = min(chunk_start + Timedelta(...), chunk_end) → pas de type annotation",
        old   : "req_end = min(chunk_start + pd.Timedelta(days=_CHUNK_DAYS), chunk_end)",
        new   : "req_end: pd.Timestamp = cast(pd.Timestamp, min(chunk_start + pd.Timedelta(days=_CHUNK_DAYS), chunk_end))",
        note  : "cast already imported (L194 uses it). Vérifie que 'cast' est dans les imports."
      }
    ],
    validation : "venv\\Scripts\\python.exe -m pytest tests\\data\\ -q --tb=no"
  },

  {
    batch      : 4,
    module     : "monitoring/ + backtests/",
    files      : [
      "monitoring/logger.py",
      "monitoring/cache_advanced_s42.py",
      "monitoring/portfolio_extension_s43.py",
      "backtests/walk_forward.py"
    ],
    error_types    : ["ruff"],
    estimated_fixes: 43,
    difficulty     : "Facile (auto-fix dominant)",
    fix_detail : [
      {
        file  : "monitoring/logger.py",
        line  : 23,
        type  : "ruff UP017",
        old   : "timezone.utc",
        new   : "datetime.UTC",
        note  : "Seule occurrence — modifier ou --fix"
      },
      {
        files : ["monitoring/cache_advanced_s42.py", "monitoring/portfolio_extension_s43.py"],
        type  : "ruff UP006/UP045",
        count : 40,
        fix   : "ruff check --fix --select UP006,UP045,I001 monitoring/cache_advanced_s42.py monitoring/portfolio_extension_s43.py"
      },
      {
        file  : "backtests/walk_forward.py",
        lines : [16, 28],
        type  : "ruff I001 + F811",
        issue : "Import non trié + CostModel importé deux fois (L25 et L28)",
        fix   : "Supprimer la ligne dupliquée (from backtests.cost_model import CostModel L28) ; laisser L25 ; trier imports"
      }
    ],
    validation : "venv\\Scripts\\python.exe -m pytest tests\\monitoring\\ tests\\backtests\\ -q --tb=no"
  },

  {
    batch      : 5,
    module     : "research/ + ARG + pyright scripts",
    files      : [
      "research/pair_discovery.py",
      "research/param_optimization.py",
      "run_paper_tick.py",
      "scripts/run_backtest_v41fg.py",
      "scripts/run_backtest_v40b.py"
    ],
    error_types    : ["ruff", "ARG", "ndarray"],
    estimated_fixes: 12,
    difficulty     : "Facile",
    fix_detail : [
      {
        file  : "research/pair_discovery.py",
        lines : [5, 6, 9],
        type  : "ruff I001 + F401 + F811",
        issue : "Double import models.cointegration (L6 + L9), correlation_matrix inutilisé",
        fix   : "Supprimer L6 ; garder L9 (engle_granger_test, half_life_mean_reversion) ; trier imports"
      },
      {
        file  : "research/param_optimization.py",
        lines : [10, 13],
        type  : "ruff I001 + F811",
        issue : "import pandas as pd deux fois (L10 et L13)",
        fix   : "Supprimer import pandas L10 ; trier le bloc restant (from itertools import product ↑)"
      },
      {
        file  : "run_paper_tick.py",
        line  : 331,
        type  : "ARG001",
        old   : "def _sigint_handler(sig, frame):",
        new   : "def _sigint_handler(_sig, _frame):",
        rule  : "Convention Python : préfixer _ les arguments requis mais non utilisés"
      },
      {
        file  : "scripts/run_backtest_v41fg.py",
        line  : 120,
        type  : "ARG001",
        old   : "def _apply_base_settings(entry_z, exit_z, half_life_cap, rediscovery):",
        new   : "def _apply_base_settings(entry_z, exit_z, half_life_cap, _rediscovery):",
        rule  : "ARG001"
      },
      {
        file  : "scripts/run_backtest_v40b.py",
        line  : 142,
        type  : "pyright ndarray",
        issue : "prices.ffill() retourne ndarray selon pyright — ajouter cast explicite",
        old   : "prices = prices.ffill().dropna(how=\"all\")",
        new   : "prices = pd.DataFrame(prices).ffill().dropna(how=\"all\")",
        rule  : "reportAttributeAccessIssue"
      }
    ],
    validation : "venv\\Scripts\\python.exe -m pytest tests\\regression\\ tests\\strategies\\ -q --tb=no"
  },

  {
    batch      : 6,
    module     : "main.py + scripts batch auto-fix",
    files      : [
      "main.py",
      "scripts/run_backtest_v*.py  (52 fichiers)"
    ],
    error_types    : ["ruff F811", "ruff UP031/F541 auto-fix"],
    estimated_fixes: 355,
    difficulty     : "Facile (auto-fix mass)",
    fix_detail : [
      {
        file  : "main.py",
        type  : "ruff I001 + F811 ×4",
        issue : [
          "L34 IBKRExecutionEngine déclaré deux fois (L31+L34)",
          "L36 PaperExecutionEngine déclaré deux fois (L32+L36)",
          "L45 RiskEngine déclaré deux fois (L30+L45)",
          "L46 PairTradingStrategy déclaré deux fois (L29+L46)"
        ],
        fix   : "Supprimer les secondes occurrences (L34, L36, L45, L46) ; trier imports L10"
      },
      {
        files : "scripts/run_backtest_v*.py (52 fichiers)",
        type  : "ruff UP031/F541/E401/UP009 auto-fix",
        fix   : "ruff check --fix --select UP031,F541,E401,UP009 scripts/",
        count : "~345 violations auto-fixées en une commande",
        note  : "Créer un sous-commit dédié pour isoler le mass auto-fix"
      }
    ],
    validation : "venv\\Scripts\\python.exe -m pytest tests\\ -q --tb=no -x"
  },

  {
    batch      : 7,
    module     : "tests/ + demo_dashboard.py",
    files      : [
      "tests/test_momentum_signal.py",
      "demo_dashboard.py"
    ],
    error_types    : ["ruff I001"],
    estimated_fixes: 2,
    difficulty     : "Trivial (auto-fix)",
    fix_detail : [
      {
        fix : "ruff check --fix --select I001 tests/test_momentum_signal.py demo_dashboard.py"
      }
    ],
    validation : "venv\\Scripts\\python.exe -m pytest tests\\ -q --tb=no"
  }
]
```

---

## RÉSUMÉ

```
RÉSUMÉ:
  total_batches    : 7
  total_files      : 15 production + 52 scripts + 2 tests = ~69
  estimated_fixes  : 432  (4 pyright + 3 ARG + 425 ruff)
  dominant_pattern : ruff UP031/F541 dans scripts historiques (82 % du total — auto-fix)
  ordre_validation : pytest par batch → ruff global → pyright global

  batch_1 : models/              → 1 fichier  · 15 fixes · Facile
  batch_2 : execution/           → 2 fichiers · 4 fixes  · Facile
  batch_3 : data/                → 1 fichier  · 1 fix    · Moyen
  batch_4 : monitoring/+backtests→ 4 fichiers · 43 fixes · Facile (auto)
  batch_5 : research/+ARG+script → 5 fichiers · 12 fixes · Facile
  batch_6 : main.py+scripts mass → 53 fichiers· 355 fixes· Facile (auto)
  batch_7 : tests/+demo          → 2 fichiers · 2 fixes  · Trivial

  cible_post_fix:
    pyright     : 0 erreur
    ruff        : 0 violation (hors noqa: UP042)
    ARG         : 0 violation
    pytest      : ≥ 2742/2742
    IDE PROBLEMS: 0
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
