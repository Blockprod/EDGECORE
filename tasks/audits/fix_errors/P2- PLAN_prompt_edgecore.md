---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/PLAN_result.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

#codebase

Tu es un Software Architect spécialisé systèmes financiers Python.
Tu crées un plan de correction OPTIMAL à partir du SCAN.

─────────────────────────────────────────────
INPUT
─────────────────────────────────────────────
Lire `tasks/audits/fix_errors/SCAN_result.md` (FILES_TO_FIX).

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Ne modifie rien. Raisonne sur les dépendances et groupe
les fichiers de façon à minimiser le nombre d'itérations
de vérification inter-batch.

─────────────────────────────────────────────
RÈGLES DE PRIORITÉ EDGECORE
─────────────────────────────────────────────
Batch 1 (fondations — dépendances des autres) :
  models/, common/, config/

Batch 2 (pipeline cœur) :
  pair_selection/, signal_engine/, strategies/

Batch 3 (exécution) :
  execution/, execution_engine/, live_trading/, portfolio_engine/

Batch 4 (données) :
  data/, universe/, scheduler/

Batch 5 (infrastructure) :
  risk/, risk_engine/, persistence/, monitoring/, backtests/, backtester/

Batch 6 (scripts / research) :
  scripts/, research/, validation/

Batch 7+ (tests) :
  Grouper par miroir de module :
  tests\models → tests\pair_selection → tests\signal_engine →
  tests\strategies → tests\execution → tests\data →
  tests\integration → tests\backtests → tests\regression →
  autres tests\*

─────────────────────────────────────────────
RÈGLES DE GROUPEMENT
─────────────────────────────────────────────
1. Max 20 fichiers par batch
2. Fichiers du même module = même batch
3. Si A importe B → B dans un batch antérieur
4. Erreurs Cython (cointegration_fast.pyx) → toujours Batch 1
5. Erreurs `cast` manquant → grouper avec les autres erreurs `typing` du même fichier

─────────────────────────────────────────────
CATALOGUE DE PATTERNS CONNUS EDGECORE
─────────────────────────────────────────────
(pour qualifier la difficulté de chaque batch)

| Pattern | Fix | Difficulté |
|---------|-----|-----------|
| `df[col]` → `Series \| Unknown` | `pd.Series(df[col])` | Facile |
| `df[cols]` → `DataFrame \| Unknown` | `pd.DataFrame(df[cols])` | Facile |
| `rolling().mean().iloc[-1]` | `pd.Series(...).iloc[-1]` | Facile |
| `Timestamp \| NaTType` | `cast(pd.Timestamp, ...)` | Moyen |
| `index.min() < index.min()` | `cast(pd.Timestamp, ...)` × 2 | Moyen |
| `ARG004` unused static param | connecter au calcul | Moyen |
| Cython signature mismatch | aligner `.pyx` ↔ `.py` | Complexe |

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Créer `C:\Users\averr\EDGECORE_V1\tasks\audits\fix_errors\fix_results\PLAN_result.md` avec :

```
PLAN = [
  {
    batch: 1,
    module: "models/, common/",
    files: ["models/cointegration.py", ...],
    error_types: ["Cython", "typing"],
    estimated_fixes: N,
    difficulty: Facile | Moyen | Complexe
  },
  ...
]

RÉSUMÉ:
  total_batches    : X
  total_files      : Y
  estimated_fixes  : Z
  ordre_validation : pytest → ruff → pyright par batch
```
SORTIE OBLIGATOIRE :
Tous les résultats doivent être enregistrés dans :
C:\Users\averr\EDGECORE_V1\tasks\audits\fix_errors\fix_results
─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Aucune modification de code
- Si FILES_TO_FIX est vide → écrire "PLAN : rien à corriger ✅"
- Confirmer dans le chat : "✅ PLAN_result.md créé · X batches · Y fichiers"
