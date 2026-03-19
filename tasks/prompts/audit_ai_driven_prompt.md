#codebase

Sur la base du diagnostic structurel qui vient d'être réalisé,
génère le plan de restructuration AI-Driven complet pour EDGECORE.

─────────────────────────────────────────────
CONTRAINTES
─────────────────────────────────────────────
- Génère le contenu RÉEL de chaque fichier
  basé sur le code source — pas de templates génériques
- Chaque fichier doit être prêt à copier-coller
- Si une information n'est pas trouvable dans le code :
  indique [À COMPLÉTER MANUELLEMENT]

─────────────────────────────────────────────
ÉTAPE 1 — NETTOYAGE PRÉALABLE
─────────────────────────────────────────────
Liste les actions de nettoyage à réaliser AVANT
de créer les fichiers AI-Driven :
- Fichiers racine à archiver ou supprimer
- Doublons fonctionnels à résoudre en priorité
- Fichiers à déplacer vers docs/
- setup.py vs pyproject.toml : lequel conserver ?
- CMakeLists.txt : à supprimer ou conserver ?

─────────────────────────────────────────────
ÉTAPE 2 — ARBORESCENCE CIBLE
─────────────────────────────────────────────
Propose l'arborescence complète du repo restructuré
en AI-Driven avec les nouveaux dossiers :
.claude/ · .github/ · architecture/ ·
knowledge/ · agents/ · tasks/
et les context.md par module critique.

─────────────────────────────────────────────
ÉTAPE 3 — CONTENU DES FICHIERS AI-DRIVEN
─────────────────────────────────────────────
Génère le contenu complet et réel de :

1. .github/copilot-instructions.md
   Stack · modules clés · conventions critiques
   issues du code · interdictions absolues ·
   commandes de validation

2. .claude/rules.md
   Règles de modification · ordre de priorité ·
   obligations post-modification · interdictions

3. .claude/context.md
   Pipeline complet depuis le code · table des modules
   avec responsabilité réelle · paramètres clés
   extraits de config/ · ce qui ne doit pas changer

4. architecture/decisions.md
   ADR pour : séparation modules publics/internes ·
   triple-gate coïntégration · Kalman vs hedge fixe ·
   z-score adaptatif · kill-switch 6 conditions ·
   migration C++ → Python · Docker

5. knowledge/ibkr_constraints.md
   Types d'ordres IBKR · rate limits · ports TWS/Gateway ·
   contraintes de sizing · gestion market impact

6. context.md pour les 4 modules critiques :
   execution/ · models/ · risk_engine/ · backtests/
   (responsabilité · ce qu'il FAIT · ce qu'il NE FAIT PAS ·
   contrats · exceptions · dépendances)

7. agents/quant_researcher.md
8. agents/risk_manager.md
9. agents/code_auditor.md
10. agents/dev_engineer.md

11. tasks/audit_structural.md (checklist cochable)
12. tasks/add_strategy.md (procédure ajout scénario)
13. tasks/correct_p0.md (template correction P0)

─────────────────────────────────────────────
ÉTAPE 4 — PLAN DE MIGRATION PRIORISÉ
─────────────────────────────────────────────
Tableau :
| Priorité | Fichier | Effort | % Auto | Impact session |

% Auto = part générée depuis le code vs manuelle.
Impact session = ce que ce fichier élimine comme
re-explication à chaque session Claude/Copilot.

─────────────────────────────────────────────
FORMAT
─────────────────────────────────────────────
Chaque fichier dans un bloc de code markdown
avec son chemin exact en titre.
Tableau de migration en fin de réponse.