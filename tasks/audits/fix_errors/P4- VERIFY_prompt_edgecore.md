---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/VERIFY_result.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

#codebase

Tu es un QA Engineer indépendant. Tu valides UNIQUEMENT — tu ne corriges rien.
Vérification complète post-correction EDGECORE.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Lance chaque commande, capture le résultat COMPLET,
puis formule un verdict binaire par catégorie.

─────────────────────────────────────────────
ACTIONS (dans cet ordre exact)
─────────────────────────────────────────────

```powershell
# 1. Ruff global
venv\Scripts\python.exe -m ruff check . --exclude venv,__pycache__,build 2>&1 | Select-Object -Last 5

# 2. Ruff ARG
venv\Scripts\python.exe -m ruff check . --exclude venv,__pycache__,build --select ARG 2>&1 | Select-Object -Last 5

# 3. Pyright par dossier — mêmes 49 répertoires que P1
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
  if ($e -and $e -ne "0") { Write-Host "❌ $d : $e erreur(s)" }
  else { Write-Host "✅ $d" }
}

# 4. Suite de tests complète
venv\Scripts\python.exe -m pytest tests/ -q --tb=no 2>&1 | Select-Object -Last 5

# 5. Cohérence risk tiers
venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('Risk tiers OK')"

# 6. Config dev
venv\Scripts\python.exe -c "from config.settings import get_settings; s=get_settings(); print('entry_z_score =', s.strategy.entry_z_score)"
```

─────────────────────────────────────────────
SEUIL DE RÉUSSITE
─────────────────────────────────────────────
| Catégorie | Seuil PASS |
|-----------|-----------|
| ruff | 0 violation |
| ARG | 0 violation |
| pyright | 0 erreur dans chaque dossier |
| pytest | ≥ 2800 passed, 0 failed |
| risk_tiers | `Risk tiers OK` |
| config | entry_z_score ≠ None |

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Créer `C:\Users\averr\EDGECORE_V1\tasks\audits\fix_errors\fix_results\VERIFY_result.md` avec :

```
VERIFY_STATUS:
  ruff      : ✅ OK / ❌ FAIL (X violations)
  ARG       : ✅ OK / ❌ FAIL (X violations)
  pyright   : ✅ OK / ❌ FAIL — dossiers KO : [...]
  tests     : ✅ OK (N passed) / ❌ FAIL (N failed)
  risk_tiers: ✅ OK / ❌ FAIL
  config    : ✅ OK / ❌ FAIL

VERDICT GLOBAL : PASS ✅ / FAIL ❌
BLOCKERS RESTANTS:
  - [fichier:ligne — description] ou "aucun"
```

Confirmer dans le chat :
"✅ VERIFY terminé · ruff OK · pyright OK · N tests pass" 
ou
"❌ VERIFY : X blockers — relancer P3 batch Y"


