---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/SCAN_result.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

#codebase

Tu es un code quality analyst spécialisé Python / pandas / pyright.
Tu réalises un SCAN COMPLET du projet EDGECORE sans rien modifier.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Explore d'abord, ne corrige jamais. Chaque commande
doit être lancée et son résultat capturé avant de passer
à la suivante.

─────────────────────────────────────────────
ÉTAPE 1 — OUTILS STATIQUES
─────────────────────────────────────────────
Lancer dans l'ordre (terminal PowerShell, venv Python 3.11) :

```powershell
# 1. Ruff général
venv\Scripts\python.exe -m ruff check . --exclude venv,__pycache__,build 2>&1 | Select-Object -Last 10

# 2. Ruff ARG (arguments inutilisés)
venv\Scripts\python.exe -m ruff check . --exclude venv,__pycache__,build --select ARG 2>&1 | Select-Object -Last 5

# 3. Pyright — dossier par dossier (ordre priorité EDGECORE)
$dirs = @(
  "models","pair_selection","signal_engine","strategies",
  "execution","data","live_trading","backtests","backtester",
  "portfolio_engine","risk","risk_engine","execution_engine",
  "common","config","universe","scheduler","persistence",
  "monitoring","validation","research","scripts",
  "tests\backtests","tests\common","tests\config","tests\data",
  "tests\edgecore","tests\execution","tests\execution_engine",
  "tests\integration","tests\live_trading","tests\models",
  "tests\monitoring","tests\persistence","tests\phase3",
  "tests\phase4","tests\portfolio_engine","tests\regression",
  "tests\risk","tests\risk_engine","tests\signal_engine",
  "tests\statistical","tests\strategies","tests\universe",
  "tests\validation"
)
foreach ($d in $dirs) {
  $e = (venv\Scripts\python.exe -m pyright $d 2>&1 | Select-String "(\d+) error").Matches[0].Groups[1].Value
  if ($e -and $e -ne "0") { Write-Host "$d : $e erreur(s)" }
}
Write-Host "--- scan terminé ---"
```

─────────────────────────────────────────────
ÉTAPE 2 — GET_ERRORS
─────────────────────────────────────────────
Utiliser l'outil `get_errors` (sans argument = tous les fichiers)
pour croiser avec les PROBLEMS de l'IDE.

─────────────────────────────────────────────
ÉTAPE 3 — CLASSIFICATION
─────────────────────────────────────────────
Pour chaque fichier en erreur, identifier le TYPE :

| Code | Type | Exemple EDGECORE |
|------|------|-----------------|
| `ruff` | style/import | F401, E501, ARG001 |
| `ARG` | unused param | ARG002, ARG004 |
| `typing` | pyright Series/DataFrame | `df[col]` → `Series \| Unknown` |
| `Timestamp` | pyright NaTType | `pd.Timestamp(x)` → `Timestamp \| NaTType` |
| `ndarray.iloc` | pyright .iloc sur ndarray | rolling().mean().iloc[-1] |
| `import` | import manquant / circulaire | cast non importé |
| `cython` | signature pyx ≠ .py | cointegration_fast.pyx |

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Créer `C:\Users\averr\EDGECORE_V1\tasks\audits\fix_errors\fix_results\SCAN_result.md` avec :

```
FILES_TO_FIX = [
  {
    file: "chemin/relatif.py",
    errors: ["typing", "ARG"],
    count: N,
    lines: [L1, L2, ...]   ← lignes pyright exactes
  },
  ...
]

TOTAUX:
  ruff      : X violation(s)
  ARG       : X violation(s)
  pyright   : X erreur(s) dans Y fichiers
  dossiers_propres: [liste...]
```

─────────────────────────────────────────────
