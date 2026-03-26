---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/fix_errors/FINAL_QA_result.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

#codebase

Tu es un Release Manager EDGECORE. Tu valides la readiness complète
du système avant merge / déploiement.

─────────────────────────────────────────────
INPUT
─────────────────────────────────────────────
Lire `tasks/audits/fix_errors/VERIFY_result.md`.
Si VERDICT GLOBAL = FAIL → arrêter immédiatement et indiquer
"❌ FINAL QA bloqué — relancer P3 + P4 d'abord".

─────────────────────────────────────────────
CHECKLIST EDGECORE (12 points)
─────────────────────────────────────────────

### 1. Qualité statique (depuis VERIFY_result.md)
- [ ] ruff : 0 violation
- [ ] ARG : 0 violation
- [ ] pyright : 0 erreur dans les 49 dossiers

### 2. Tests
- [ ] `pytest tests/ -q` → ≥ 2800 passed, 0 failed, 0 error
- [ ] `pytest tests/ -W error::DeprecationWarning -q` → 0 DeprecationWarning
  ```powershell
  venv\Scripts\python.exe -m pytest tests/ -W error::DeprecationWarning -q --tb=no 2>&1 | Select-Object -Last 3
  ```

### 3. Cohérence de la configuration
- [ ] Risk tier coherence
  ```powershell
  venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"
  ```
- [ ] `EDGECORE_ENV` valide : `dev`, `test` ou `prod` (jamais `production`)
  ```powershell
  venv\Scripts\python.exe -c "from config.settings import get_settings; print(get_settings().env)"
  ```

### 4. Module Cython
- [ ] Extension compilée présente et importable
  ```powershell
  venv\Scripts\python.exe -c "from models.cointegration_fast import engle_granger_fast; print('Cython OK')"
  ```

### 5. Pipeline critique — smoke test
- [ ] Imports de tous les modules productifs sans erreur
  ```powershell
  venv\Scripts\python.exe -c "
  from models.cointegration import engle_granger_test
  from pair_selection.filters import PairFilter
  from signal_engine.generator import SignalGenerator
  from strategies.pair_trading import PairTradingStrategy
  from execution_engine.router import ExecutionRouter
  from risk.facade import RiskFacade
  print('Pipeline imports OK')
  "
  ```

### 6. Interdictions EDGECORE — vérification grep
  ```powershell
  # Aucun datetime.utcnow()
  venv\Scripts\python.exe -m ruff check . --select DTZ003 --exclude venv,__pycache__,build 2>&1 | Select-Object -Last 3

  # Aucun # type: ignore
  $hits = (Select-String -Path "**\*.py" -Pattern "# type: ignore" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Path -notmatch "venv|__pycache__|build" })
  if ($hits) { Write-Host "❌ type:ignore trouvés : $($hits.Count)" ; $hits | Select-Object -First 5 }
  else { Write-Host "✅ 0 type:ignore" }

  # Aucun print() dans les modules de production (hors tests/scripts/research)
  $printhits = (Select-String -Path ".\*.py",".\**\*.py" -Pattern "^\s*print\(" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Path -notmatch "venv|tests|scripts|research|__pycache__|build" })
  if ($printhits) { Write-Host "❌ print() trouvés : $($printhits.Count)" }
  else { Write-Host "✅ 0 print() en production" }
  ```

### 7. Cohérence des types d'ordre
- [ ] Vérifier que `TradeOrder` n'a pas été recréé (bug B2-01 déjà corrigé)
  ```powershell
  Select-String -Path "execution_engine\router.py" -Pattern "class TradeOrder" -ErrorAction SilentlyContinue
  ```
  Résultat attendu : aucune ligne.

### 8. Docker
- [ ] `EDGECORE_ENV` dans Dockerfile = `prod` (pas `production`)
  ```powershell
  Select-String -Path "Dockerfile","docker-compose.yml" -Pattern "EDGECORE_ENV"
  ```

### 9. CI
- [ ] `.github/workflows/ci.yml` présent et syntaxe YAML valide
  ```powershell
  Test-Path ".github\workflows\ci.yml"
  ```

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Créer `tasks/audits/fix_errors/FINAL_QA_result.md` avec :

```
FINAL_QA_EDGECORE:

  QUALITÉ STATIQUE :
    ruff          : ✅ / ❌
    ARG           : ✅ / ❌
    pyright       : ✅ / ❌

  TESTS :
    pytest        : ✅ N passed / ❌ N failed
    DeprecWarning : ✅ / ❌

  CONFIG :
    risk_tiers    : ✅ / ❌
    EDGECORE_ENV  : ✅ prod | dev | test / ❌ production
    cython        : ✅ / ❌

  PIPELINE :
    imports       : ✅ / ❌

  INTERDICTIONS :
    type:ignore   : ✅ 0 / ❌ N hits
    utcnow        : ✅ 0 / ❌ N hits
    print         : ✅ 0 / ❌ N hits
    TradeOrder    : ✅ absent / ❌ présent

  INFRA :
    docker        : ✅ / ❌
    ci.yml        : ✅ / ❌

SYSTÈME : READY ✅ / NOT READY ❌

BLOCKERS RESTANTS:
  - [description] ou "aucun"

ACTIONS REQUISES AVANT MERGE:
  - [action] ou "aucune"
```

Confirmer dans le chat :
"✅ FINAL QA EDGECORE : READY — N/12 checks passés"
ou
"❌ FINAL QA EDGECORE : NOT READY — blockers : [liste courte]"
