---
type: guide
derniere_revision: 2026-03-17
projets: EDGECORE · MULTI_ASSETS
---

# WORKFLOW — Audit → Plan → Corrections

Guide d'utilisation des prompts du dossier tasks/.
Suivre les étapes dans l'ordre strict.

---

## ÉTAPE 1 — Audit complet

**Prompt** : `tasks/audit_master_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Produit** : `AUDIT_TECHNIQUE_[PROJET].md` à la racine
```
#file:tasks/audit_master_prompt.md
Lance cet audit sur le workspace.
```

---

## ÉTAPE 2 — Génération du plan d'action

**Prompt** : `tasks/generate_action_plan_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Lit**    : `AUDIT_TECHNIQUE_[PROJET].md`
**Produit** : `PLAN_ACTION_[PROJET]_[DATE].md` à la racine
```
#file:tasks/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

---

## ÉTAPE 3 — Exécution des corrections

**Prompt** : `tasks/execute_corrections_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Lit**    : `PLAN_ACTION_[PROJET]_[DATE].md`
**Produit** : corrections appliquées · statuts ⏳ → ✅
```
#file:tasks/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## AUDITS SPÉCIALISÉS (optionnels)

À lancer après l'ÉTAPE 1 pour approfondir
une dimension spécifique :

| Prompt | Dimension | Modèle |
|--------|-----------|--------|
| `audit_technical_prompt.md` | Sécurité · Robustesse | Sonnet 4.6 |
| `audit_strategic_prompt.md` | Biais · Backtest | Sonnet 4.6 |
| `audit_structural_prompt.md` | Architecture · Modules | Sonnet 4.6 |
| `audit_ai_driven_prompt.md` | Génération contexte IA | Sonnet 4.6 |
| `audit_email_alerts_prompt.md` | Alertes email | Sonnet 4.6 |

---

## STRUCTURE COMPLÈTE DU DOSSIER TASKS
```
tasks/
├── WORKFLOW.md                      ← ce fichier
│
├── audit_master_prompt.md           ← ÉTAPE 1
├── generate_action_plan_prompt.md   ← ÉTAPE 2
├── execute_corrections_prompt.md    ← ÉTAPE 3
│
├── audit_technical_prompt.md        ← audits spécialisés
├── audit_strategic_prompt.md
├── audit_structural_prompt.md
├── audit_ai_driven_prompt.md
├── audit_email_alerts_prompt.md
│
└── audit_structural_checklist.md    ← suivi corrections
```

---

## RÈGLE D'OR
```
Ne jamais lancer ÉTAPE 3 sans avoir
validé le plan de l'ÉTAPE 2 manuellement.
```