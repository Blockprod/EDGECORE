---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/resultats/audit_best_practices_ai_edgecore.md
derniere_revision: 2026-03-27
creation: 2026-03-27 à 10:00
---

─────────────────────────────────────────────
SOURCES VISUELLES — À LIRE EN PREMIER
─────────────────────────────────────────────
Lis et exploite les images suivantes :
1. tasks/audits/code/knowledge/best_practices_ai_1.png
2. tasks/audits/code/knowledge/best_practices_ai_2.png
3. tasks/audits/code/knowledge/best_practices_ai_3.png
4. tasks/audits/code/knowledge/best_practices_ai_4.png
5. tasks/audits/code/knowledge/best_practices_ai_5.png

Tu dois extraire et synthétiser toutes les bonnes pratiques, patterns, frameworks, workflows, checklists, etc. présents dans ces images, et les comparer à l’état du projet EDGECORE.

#codebase

Tu es un AI Agent Engineer senior, expert en best practices Claude, Copilot, HyperAgents et systèmes de trading institutionnels.
Tu réalises un audit EXCLUSIF des "pratiques et patterns AI/agent" sur EDGECORE.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà :
  tasks/audits/resultats/audit_best_practices_ai_edgecore.md

Si trouvé, affiche :
"⚠️ Audit best practices AI existant détecté :
 Fichier : tasks/audits/resultats/audit_best_practices_ai_edgecore.md
 Date    : [date modification]
 Lignes  : [nombre approximatif]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit best practices AI existant. Démarrage..."

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
Tu analyses UNIQUEMENT :
- Patterns d'agentification (Claude, Copilot, HyperAgents, AI agent best practices)
- Systèmes de mémoire (mémoire de travail, vectorielle, file, DB, structlog, audit trail)
- Hooks, triggers, orchestration, self-improving loop
- Prompts contextuels, patterns Claude/Copilot, fichiers context, skills, agents
- Sécurité des workflows agents (gestion secrets, permissions, auditabilité)
- Modularité, extensibilité, plugins/connecteurs, RAG/LLM integration
- Observabilité, monitoring, tests automatiques, CI/CD avancé
- Documentation agent, WORKFLOW.md, lessons.md, copilot-instructions.md

Tu NE traites PAS :
- Structure modulaire classique (déjà couvert par audit structurel)
- Pipeline stat-arb, stratégie, latence, Cython, trade journal (déjà couverts)
- Fichiers markdown, txt, rst (sauf WORKFLOW.md, lessons.md, copilot-instructions.md)
- Code métier pur (hors patterns agent/AI)

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Ne lis aucun fichier .md, .txt, .rst SAUF : WORKFLOW.md, lessons.md, copilot-instructions.md
- Cite fichier:ligne pour chaque problème/code clé
- Pour chaque best practice manquante, propose une solution concrète (pattern, fichier, ref image)
- Ignore tout commentaire de style PEP8
- Priorise : sécurité, auditabilité, modularité, self-improvement, orchestration, mémoire, prompts

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Réfléchis profondément étape par étape avant de produire ta sortie. Explore d'abord, planifie ensuite, puis exécute.

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier : tasks/audits/resultats/audit_best_practices_ai_edgecore.md

Inclure un tableau synthèse :
| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |

Confirme dans le chat :
"✅ tasks/audits/resultats/audit_best_practices_ai_edgecore.md créé · 🔴 X · 🟠 X · 🟡 X"

---

## CHECKLIST RGPD & SÉCURITÉ PROMPTS (BP-04)

- [ ] Tous les prompts d'audit (.md) contiennent une section explicite sur la sécurité, la confidentialité et la conformité RGPD si applicable.
- [ ] Les prompts traitant des données personnelles ou de la configuration doivent rappeler les bonnes pratiques de protection (pas de credentials, pas de données nominatives, anonymisation, etc.).
- [ ] Les workflows d'agent (Copilot, Claude, HyperAgents) doivent rappeler l'auditabilité et la traçabilité des actions.
- [ ] Les fichiers critiques (WORKFLOW.md, copilot-instructions.md) doivent mentionner la conformité RGPD et la sécurité des prompts.

> Pour chaque nouveau prompt, vérifier et compléter cette checklist.
