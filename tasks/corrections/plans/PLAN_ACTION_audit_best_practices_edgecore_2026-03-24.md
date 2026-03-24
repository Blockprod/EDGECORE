# PLAN D'ACTION — EDGECORE — 2026-03-24
Sources : `tasks/audits/resultats/audit_best_practices_edgecore.md`
Total : 🔴 1 · 🟠 3 · 🟡 2 · Effort estimé : 0.5 jour

> **Périmètre** : fichiers de contexte AI et configuration VSCode uniquement.
> Aucun fichier de code production n'est modifié par ce plan.
> Aucune régression pytest possible — validation = review manuel du contenu.

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Directive raisonnement profond dans tous les prompts d'audit et de correction

**BP source** : BP-01  
**Fichiers** :
- `tasks/audits/code/audit_structural_prompt.md`
- `tasks/audits/code/audit_email_alerts_prompt.md`
- `tasks/audits/code/audit_technical_prompt.md`
- `tasks/audits/code/audit_cython_prompt.md`
- `tasks/audits/code/audit_strategic_prompt.md`
- `tasks/audits/code/audit_master_prompt.md`
- `tasks/audits/code/audit_modernize_python_syntax_prompt.md`
- `tasks/audits/code/audit_latence_prompt.md`
- `tasks/audits/methode/audit_ai_driven_prompt.md`
- `tasks/audits/methode/audit_ia_ml_prompt.md`
- `tasks/audits/methode/best_practices_prompt.md`
- `tasks/corrections/execute_corrections_prompt.md`

**Problème** : Aucun des 12 fichiers de prompt ne contient de directive de raisonnement explicite. Les audits complexes (master, technical, latence) analysent des dizaines de fichiers croisés sans guidage de profondeur de raisonnement.

**Correction** : Dans chaque fichier, insérer un bloc `RAISONNEMENT` juste **avant** la section `MISSION` (ou en première section si MISSION est absente) :

```
─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Réfléchis profondément étape par étape avant
de produire ta sortie. Explore d'abord, planifie
ensuite, puis exécute.
```

**Validation** :
```powershell
# Vérifier la présence dans chaque fichier prompt
Select-String -Path "tasks\audits\**\*_prompt.md","tasks\corrections\execute_corrections_prompt.md" -Pattern "RAISONNEMENT" -Recurse
# Attendu : 12 correspondances (une par fichier)
```

**Dépend de** : Aucune  
**Statut** : ⏳

---

## PHASE 2 — MAJEURES 🟠

### [C-02] Protocol écrit de mise à jour de `tasks/lessons.md` dans WORKFLOW.md

**BP source** : BP-04  
**Fichier** : `tasks/WORKFLOW.md`

**Problème** : `tasks/lessons.md` est mentionné ligne 398 comme "lire en début de session" mais il n'existe aucune instruction pour l'alimenter. La boucle de capitalisation est à sens unique.

**Correction** : Dans `tasks/WORKFLOW.md`, après la description de l'étape C (section "SÉQUENCE COMPLÈTE"), ajouter :

```markdown
### Post-étape C — Mise à jour obligatoire de `tasks/lessons.md`

Après chaque exécution d'étape C, ajouter une entrée dans `tasks/lessons.md` :

```
## [DATE] — Corrections [TYPE]
- Ce qui a fonctionné : ...
- Ce qui a bloqué : ...
- À retenir pour la prochaine fois : ...
- Issues closes : [B*-* ou BP-*]
```
```

**Validation** :
```powershell
Select-String -Path "tasks\WORKFLOW.md" -Pattern "Post-étape C"
# Attendu : 1 correspondance
```

**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-03] Sortie obligatoire lessons.md dans `execute_corrections_prompt.md`

**BP source** : BP-04  
**Fichier** : `tasks/corrections/execute_corrections_prompt.md`

**Problème** : Le prompt de l'étape C n'inclut pas la mise à jour de `tasks/lessons.md` dans ses sorties obligatoires, rendant la boucle de feedback optionnelle et donc ignorée.

**Correction** : Dans `tasks/corrections/execute_corrections_prompt.md`, dans la section des sorties ou des obligations post-exécution, ajouter :

```
- Mettre à jour tasks/lessons.md : ajouter une entrée avec
  ce qui a fonctionné, ce qui a bloqué, et les issues closes
```

**Validation** :
```powershell
Select-String -Path "tasks\corrections\execute_corrections_prompt.md" -Pattern "lessons\.md"
# Attendu : 1+ correspondances
```

**Dépend de** : C-02 (cohérence avec le format défini dans WORKFLOW.md)  
**Statut** : ⏳

---

### [C-04] Section "Invocation dans Copilot Chat (VSCode)" dans les 4 fichiers agents

**BP source** : BP-03  
**Fichiers** :
- `agents/code_auditor.md`
- `agents/dev_engineer.md`
- `agents/quant_researcher.md`
- `agents/risk_manager.md`

**Problème** : Les fichiers agents décrivent expertement leur domaine et checklist, mais n'indiquent pas comment les activer dans Copilot Chat VSCode. Un développeur arrivant sur le projet ne sait pas comment invoquer ces agents.

**Correction** : Ajouter à la fin de chaque fichier une section finale adaptée à chaque agent :

**code_auditor.md** :
```markdown
---

## Invocation dans Copilot Chat (VSCode)

**Mode Ask** :
```
#file:agents/code_auditor.md
#file:.claude/rules.md
Vérifie la conformité de [module] selon ta checklist B2→B5.
```

**Mode Agent** :
```
#file:agents/code_auditor.md
#codebase
Lance un audit complet B2→B5 sur le module [nom_module]/.
```
```

**dev_engineer.md** :
```markdown
---

## Invocation dans Copilot Chat (VSCode)

**Mode Ask** :
```
#file:agents/dev_engineer.md
#file:.github/copilot-instructions.md
Corrige [problème] dans [fichier] selon les conventions EDGECORE.
```

**Mode Agent** :
```
#file:agents/dev_engineer.md
#file:tasks/corrections/plans/PLAN_ACTION_[...].md
Exécute la correction [C-XX] du plan d'action.
```
```

**quant_researcher.md** :
```markdown
---

## Invocation dans Copilot Chat (VSCode)

**Mode Ask** :
```
#file:agents/quant_researcher.md
#file:knowledge/trading_constraints.md
Analyse la cohérence des paramètres de [paire/signal].
```

**Mode Agent** :
```
#file:agents/quant_researcher.md
#codebase
Revue complète du signal alpha : z-score, Kalman, momentum weights.
```
```

**risk_manager.md** :
```markdown
---

## Invocation dans Copilot Chat (VSCode)

**Mode Ask** :
```
#file:agents/risk_manager.md
#file:knowledge/trading_constraints.md
Valide la cohérence des seuils de risque dans [fichier].
```

**Mode Agent** :
```
#file:agents/risk_manager.md
#codebase
Audit complet de la politique de risque : kill-switch, tiers, sizing.
```
```

**Validation** :
```powershell
Select-String -Path "agents\*.md" -Pattern "Invocation dans Copilot"
# Attendu : 4 correspondances (une par fichier)
```

**Dépend de** : Aucune  
**Statut** : ⏳

---

## PHASE 3 — MINEURES 🟡

### [C-05] Créer `.vscode/tasks.json` avec les commandes de validation EDGECORE

**BP source** : BP-02  
**Fichier** : `.vscode/tasks.json` (à créer)

**Problème** : Les 5 commandes de validation récurrentes sont dispersées dans `.github/copilot-instructions.md`. Chaque agent les recopie manuellement, avec risque d'erreur de frappe. Aucun accès "Run Task" depuis VSCode.

**Correction** : Créer `.vscode/tasks.json` :
```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "pytest (complet)",
      "type": "shell",
      "command": "venv\\Scripts\\python.exe -m pytest tests/ -q",
      "group": { "kind": "test", "isDefault": true },
      "presentation": { "reveal": "always", "panel": "shared" }
    },
    {
      "label": "pytest (DeprecationWarning strict)",
      "type": "shell",
      "command": "venv\\Scripts\\python.exe -m pytest tests/ -W error::DeprecationWarning -q",
      "group": "test",
      "presentation": { "reveal": "always", "panel": "shared" }
    },
    {
      "label": "Cython build",
      "type": "shell",
      "command": "venv\\Scripts\\python.exe setup.py build_ext --inplace",
      "group": "build",
      "presentation": { "reveal": "always", "panel": "shared" }
    },
    {
      "label": "Risk tier coherence",
      "type": "shell",
      "command": "venv\\Scripts\\python.exe -c \"from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')\"",
      "group": "test",
      "presentation": { "reveal": "always", "panel": "shared" }
    },
    {
      "label": "Config dev check",
      "type": "shell",
      "command": "venv\\Scripts\\python.exe -c \"from config.settings import get_settings; s=get_settings(); print(s.strategy.entry_z_score)\"",
      "group": "test",
      "presentation": { "reveal": "always", "panel": "shared" }
    }
  ]
}
```

**Validation** :
```powershell
Test-Path ".vscode\tasks.json"
# Attendu : True
Get-Content ".vscode\tasks.json" | ConvertFrom-Json | Select-Object -ExpandProperty tasks | Select-Object label
# Attendu : 5 tâches listées
```

**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-06] Documenter `#sym:` dans WORKFLOW.md (section référence Copilot)

**BP source** : BP-05  
**Fichier** : `tasks/WORKFLOW.md`

**Problème** : Les prompts EDGECORE utilisent `#file:` et `#codebase` mais jamais `#sym:NomDeClasse`. Cette commande Copilot permet de charger uniquement la définition d'un symbole (classe/fonction) sans surcharger le contexte avec tout le fichier — particulièrement utile pour les corrections chirurgicales sur `KillSwitch`, `RiskFacade`, `ExecutionRouter`.

**Correction** : Ajouter dans `tasks/WORKFLOW.md` une section "Référence des commandes Copilot" (par exemple en bas, avant la section STRUCTURE) :

```markdown
## RÉFÉRENCE — COMMANDES COPILOT CHAT (VSCODE)

| Commande | Scope | Usage type |
|---|---|---|
| `#file:path/to/file.md` | Fichier entier | Charger un prompt, un fichier de contexte |
| `#file:path/to/module.py` | Fichier entier | Référencer un module de production |
| `#sym:ClassName` | Symbole uniquement | Correction ciblée sur une classe ou fonction |
| `#codebase` | Tout le projet | Recherche sémantique globale, audits master |

**Quand utiliser `#sym:` plutôt que `#file:`** :
- `#sym:KillSwitch` → correction d'un bug dans la classe uniquement
- `#sym:_ibkr_rate_limiter` → ajout d'un acquire() manquant
- `#sym:RiskFacade` → vérification de l'injection des managers

**Ne pas utiliser `#sym:` pour** : tests, configs YAML, fichiers markdown.
```

**Validation** :
```powershell
Select-String -Path "tasks\WORKFLOW.md" -Pattern "#sym:"
# Attendu : 1+ correspondances
```

**Dépend de** : C-02 (s'insère au même endroit dans WORKFLOW.md — écrire après C-02 pour éviter conflits de localisation)  
**Statut** : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
C-01  →  C-04  (parallélisables — fichiers disjoints)
C-02  →  C-03  (BP-04 : WORKFLOW.md d'abord, puis execute_corrections_prompt.md)
C-02  →  C-06  (même fichier WORKFLOW.md — exécuter séquentiellement)
C-05           (indépendant — créer .vscode/tasks.json à tout moment)
```

**Ordre recommandé** :
1. **C-01** — Directive raisonnement (12 fichiers, impact immédiat sur prochains audits)
2. **C-02** — Protocol lessons.md dans WORKFLOW.md
3. **C-06** — `#sym:` dans WORKFLOW.md (même fichier → enchaîner sans rechargement)
4. **C-03** — lessons.md dans execute_corrections_prompt.md
5. **C-04** — Invocation dans agents/*.md
6. **C-05** — `.vscode/tasks.json` (création de fichier neuf, aucune dépendance)

---

## CRITÈRES PASSAGE EN PRODUCTION

> Pas de code production modifié — critères adaptés au périmètre (fichiers de contexte AI).

- [ ] `tasks/audits/**/*_prompt.md` : bloc RAISONNEMENT présent dans les 11 fichiers
- [ ] `tasks/corrections/execute_corrections_prompt.md` : bloc RAISONNEMENT + mention lessons.md présents
- [ ] `tasks/WORKFLOW.md` : section "Post-étape C" et section "Référence Copilot" présentes
- [ ] `agents/*.md` : section "Invocation dans Copilot Chat" dans les 4 fichiers
- [ ] `.vscode/tasks.json` : créé et valide JSON (5 tâches)
- [ ] Aucun fichier de code production (`*.py`, `*.pyx`, `*.yml`) modifié
- [ ] `venv\Scripts\python.exe -m pytest tests/ -q` → résultat inchangé (aucune régression)

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier(s) | Effort | Statut | Date |
|---|---|---|---|---|---|---|
| C-01 | Directive raisonnement profond | 🔴 | 12 fichiers prompt | XS | ✅ | 2026-03-24 |
| C-02 | Protocol lessons.md dans WORKFLOW.md | 🟠 | `tasks/WORKFLOW.md` | XS | ✅ | 2026-03-24 |
| C-03 | lessons.md dans execute_corrections_prompt.md | 🟠 | `tasks/corrections/execute_corrections_prompt.md` | XS | ✅ | 2026-03-24 |
| C-04 | Invocation Copilot dans agents/*.md | 🟠 | `agents/*.md` (×4) | XS | ✅ | 2026-03-24 |
| C-05 | Créer .vscode/tasks.json | 🟡 | `.vscode/tasks.json` | S | ✅ | 2026-03-24 |
| C-06 | Documenter #sym: dans WORKFLOW.md | 🟡 | `tasks/WORKFLOW.md` | XS | ✅ | 2026-03-24 |
