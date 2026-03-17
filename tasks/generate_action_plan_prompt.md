#codebase

Je suis le chef de projet.

Scanne le workspace, détecte tous les fichiers d'audit
disponibles (*.md contenant : critique, P0, 🔴, NON CONFORME,
fichier:ligne) et affiche-les numérotés.

Demande : "Quel(s) audit(s) utiliser ? [TOUS] ou [1][2]..."

Puis génère à la racine du projet :
PLAN_ACTION_[NOM_PROJET]_[DATE].md

─────────────────────────────────────────────
STRUCTURE OBLIGATOIRE DU FICHIER
─────────────────────────────────────────────
# PLAN D'ACTION — [PROJET] — [DATE]
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
Validation : commande + résultat attendu
Dépend de : [C-XX ou Aucune]
Statut : ⏳

## SÉQUENCE D'EXÉCUTION
[ordre tenant compte des dépendances]

## TABLEAU DE SUIVI
| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |

─────────────────────────────────────────────
RÈGLES
─────────────────────────────────────────────
- Ne modifier aucun fichier de code source
- Un problème présent dans plusieurs audits
  = une seule entrée avec toutes les sources
- Effort inconnu → "À ESTIMER"
- Fichier compatible avec execute_corrections_prompt.md

Confirme dans le chat uniquement :
"✅ PLAN_ACTION_[PROJET]_[DATE].md créé
 🔴 X · 🟠 X · 🟡 X · Effort : X jours
 👉 Lance execute_corrections_prompt.md pour démarrer."