---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/plans/PLAN_ACTION_[NOM_AUDIT]_[DATE].md
derniere_revision: 2026-03-20
creation: 2026-03-17 à 22:15
---

#codebase

Je suis le chef de projet EDGECORE.

Scanne le workspace, détecte tous les fichiers d'audit
disponibles (*.md contenant : critique, P0, 🔴,
NON CONFORME, fichier:ligne) et affiche-les numérotés.

Demande : "Quel(s) audit(s) utiliser ?
[TOUS] ou [1][2]..."

Puis génère dans `tasks/plans/` le fichier plan en nommant
le fichier d'après l'audit source (sans extension) :
  PLAN_ACTION_[NOM_AUDIT]_[DATE].md

Exemple : audit source = `audit_structural_edgecore.md`
  → `tasks/plans/PLAN_ACTION_audit_structural_edgecore_2026-03-20.md`

Exemple : audit source = `audit_master_edgecore.md`
  → `tasks/plans/PLAN_ACTION_audit_master_edgecore_2026-03-20.md`

─────────────────────────────────────────────
STRUCTURE OBLIGATOIRE DU FICHIER
─────────────────────────────────────────────
# PLAN D'ACTION — EDGECORE — [DATE]
Sources : [audits utilisés]
Total : 🔴 X · 🟠 X · 🟡 X · Effort estimé : X jours

## PHASE 1 — CRITIQUES 🔴
## PHASE 2 — MAJEURES 🟠
## PHASE 3 — MINEURES 🟡

Pour chaque correction :
### [C-XX] Titre
Fichier : chemin/fichier.py:ligne
Problème : [description]
Correction : [ce qui doit être fait]
Validation :
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : [résultat attendu]
Dépend de : [C-XX ou Aucune]
Statut : ⏳

## SÉQUENCE D'EXÉCUTION
[ordre tenant compte des dépendances]

## CRITÈRES PASSAGE EN PRODUCTION
- [ ] Zéro 🔴 ouvert
- [ ] pytest tests/ : 100% pass (2659+)
- [ ] mypy risk/ risk_engine/ execution/ : exit 0
- [ ] ruff check . : 0 erreurs
- [ ] Zéro credential IBKR dans les logs
- [ ] Kill-switch persisté au redémarrage
- [ ] Risk tiers cohérents (_assert_risk_tier_coherence OK)
- [ ] EDGECORE_ENV=prod dans Dockerfile (pas "production")
- [ ] Paper trading validé avant live

## TABLEAU DE SUIVI
| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |

─────────────────────────────────────────────
RÈGLES
─────────────────────────────────────────────
- Ne modifier aucun fichier de code source
- Ne jamais modifier config/prod.yaml directement
- Un problème dans plusieurs audits = une seule entrée
- Effort inconnu → "À ESTIMER"
- Nommer le fichier plan d'après l'audit source (voir en-tête)
- Fichier compatible avec execute_corrections_prompt.md

Confirme dans le chat uniquement :
"✅ tasks/plans/PLAN_ACTION_[NOM_AUDIT]_[DATE].md créé
 🔴 X · 🟠 X · 🟡 X · Effort : X jours
 👉 Lance tasks/prompts/execute_corrections_prompt.md pour démarrer."