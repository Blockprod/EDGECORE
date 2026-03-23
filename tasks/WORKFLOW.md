---
type: guide
projet: EDGECORE
broker: Interactive Brokers (TWS/Gateway)
stack: Python 3.11.9 · Cython 3.0 · ib_insync · Windows
derniere_revision: 2026-03-23
---

# WORKFLOW — Audit → Plan → Corrections
# EDGECORE — Moteur d'arbitrage statistique market-neutral

Chaque audit suit le même pipeline en **3 étapes** :

| Étape | Prompt | Mode | Produit |
|:---:|---|:---:|---|
| **A** | `audit_<type>_prompt.md` | Ask / Agent | `tasks/audits/audit_<type>_edgecore.md` |
| **B** | `generate_action_plan_prompt.md` | Agent | `tasks/plans/PLAN_ACTION_<type>_[DATE].md` |
| **C** | `execute_corrections_prompt.md` | Agent | corrections appliquées · ⏳ → ✅ |

> Toujours exécuter **A → B → C** dans l'ordre strict.
> Ne jamais lancer B sans avoir l'audit A complet.

---

## AUDITS DISPONIBLES

| # | Audit | Dimension | Mode A |
|:---:|---|---|:---:|
| 1 | [Structurel](#1--structurel) | Pipeline stat-arb · SRP · Couplage modules · Cython ↔ Python | Ask |
| 2 | [AI-Driven](#2--ai-driven-file-engineering) | Fichiers agents · architecture/ · knowledge/ · copilot-instructions | Agent |
| 3 | [Email & Alertes](#3--email--alertes) | Couverture notifications · Kill switch · drawdown · Sécurité SMTP | Agent |
| 4 | [IA / ML](#4--ia--ml) | Modules ML orphelins · ML z-score/régime · Opportunités IBKR | Ask |
| 5 | [Technique & Sécurité](#5--technique--sécurité) | Credentials IBKR · Thread-safety · Robustesse API · CI/CD | Ask |
| 6 | [Cython](#6--cython) | .pyx ↔ consommateurs · Fallback Python · Build reproductible · Tests | Ask |
| 7 | [Stratégique](#7--stratégique) | Intégrité statistique · Walk-forward · Kalman · Risk management financier | Ask |
| 8 | [Master](#8--master) | Audit complet toutes dimensions | Agent |
| 9 | [Modernisation Python](#9--modernisation-python) | Ruff · Pylance · syntaxe 3.11.9 · ARG · Alignement Cython | Agent |
| 10 | [Latence](#10--latence) | Chemin critique bar→ordre · Cython fallback · IBKR threading · Pipeline signal · Sources tierces | Agent |

---

## `1 · STRUCTUREL`

> Pipeline stat-arb · Couplage modules · SRP · Doublons fonctionnels · execution/ vs execution_engine/ · risk/ vs risk_engine/

**Produit A** : `tasks/audits/audit_structural_edgecore.md`

**A — Audit**
```
#file:tasks/prompts/audit_structural_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/prompts/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/prompts/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `2 · AI-DRIVEN (FILE ENGINEERING)`

> État des fichiers AI-Driven · copilot-instructions · agents/ · architecture/ · knowledge/ · Plan de migration

**Produit A** : `tasks/audits/audit_ai_driven_edgecore.md`

**A — Audit & restructuration**
```
#file:tasks/prompts/audit_ai_driven_prompt.md
Lance cet audit et cette restructuration sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/prompts/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/prompts/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `3 · EMAIL & ALERTES`

> Couverture notifications trading · Kill switch · Alertes drawdown · Protection tempêtes · Sécurité SMTP

**Produit A** : `tasks/audits/audit_email_alerts_edgecore.md`

**A — Audit**
```
#file:tasks/prompts/audit_email_alerts_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/prompts/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/prompts/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `4 · IA / ML`

> Modules ML orphelins vs actifs · Opportunités z-score/régime/seuils · Réalisme déploiement IBKR

**Produit A** : `tasks/audits/audit_ia_ml_edgecore.md`

**A — Audit**
```
#file:tasks/prompts/audit_ia_ml_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/prompts/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/prompts/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `5 · TECHNIQUE & SÉCURITÉ`

> Sécurité credentials IBKR · Thread-safety · Robustesse IB Gateway · Gestion erreurs asyncio · Pipeline CI/CD

**Produit A** : `tasks/audits/audit_technical_edgecore.md`

**A — Audit**
```
#file:tasks/prompts/audit_technical_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/prompts/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/prompts/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `6 · CYTHON`

> Cohérence .pyx ↔ consommateurs · Fallback Python · Build reproductible · setup.py · Couverture tests · Imports suspects

**Produit A** : `tasks/audits/audit_cython_edgecore.md`

**A — Audit**
```
#file:tasks/prompts/audit_cython_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/prompts/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/prompts/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `7 · STRATÉGIQUE`

> Intégrité statistique des signaux · Biais backtest · Walk-forward · Cohérence backtest ↔ live · Kalman · Risk management financier

**Produit A** : `tasks/audits/audit_strategic_edgecore.md`

**A — Audit**
```
#file:tasks/prompts/audit_strategic_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/prompts/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/prompts/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `8 · MASTER`

> Audit complet couvrant toutes les dimensions du projet en une seule passe

**Produit A** : `tasks/audits/audit_master_edgecore.md`

**A — Audit**
```
#file:tasks/prompts/audit_master_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/prompts/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/prompts/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `9 · MODERNISATION PYTHON`

> Ruff auto-fix · Pylance erreurs résiduelles · syntaxe Python 3.11.9 · ARG orphelins · Alignement Cython · dossier par dossier

**Produit** : corrections appliquées directement · 2787 tests verts

**A — Audit & corrections**
```
#file:tasks/prompts/audit_modernize_python_syntax_prompt.md
Lance cet audit sur le workspace.
```

> ⚠️ Cet audit intègre les étapes B et C directement —
> il corrige et valide en une seule passe. Aucun plan intermédiaire requis.

---

## `10 · LATENCE`

> Chemin critique bar → signal → ordre · Re-découverte de paires (O(N²)) · Cython fallback silencieux · Contention GIL/locks · I/O synchrones · Sources de données tierces (violation institutionnelle)

**Produit A** : `tasks/audits/AUDIT_LATENCE_EDGECORE.md`

**A — Audit**
```
#file:tasks/prompts/audit_latence_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/prompts/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/prompts/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## AJOUT D'UNE NOUVELLE STRATÉGIE

**Procédure** : `tasks/prompts/add_strategy.md`  
**Mode**      : Agent  
**Prérequis** : tests verts · audit structurel passé · `_assert_risk_tier_coherence()` OK

Copier-coller le prompt ci-dessous dans le chat Agent, en remplaçant
`[SYM1/SYM2, ...]` par les paires cibles et `...` par les paramètres souhaités
(laisser vide = valeurs `dev.yaml` par défaut) :

```
#file:tasks/prompts/add_strategy.md

En suivant exactement la procédure définie dans tasks/prompts/add_strategy.md,
implémente une stratégie stat-arb sur les paires [SYM1/SYM2, SYM3/SYM4]
avec les paramètres suivants :

entry_z_score:    <valeur>   # laisser vide = dev.yaml par défaut (1.6)
exit_z_score:     <valeur>   # laisser vide = dev.yaml par défaut (0.5)
lookback_window:  <valeur>   # laisser vide = dev.yaml par défaut (120)
use_kalman:       true|false
adaptive_window:  true|false
start_date:       YYYY-MM-DD
end_date:         YYYY-MM-DD
```

**Exemple concret — paires énergie + banques :**
```
#file:tasks/prompts/add_strategy.md

En suivant exactement la procédure définie dans tasks/prompts/add_strategy.md,
implémente une stratégie stat-arb sur les paires [XOM/CVX, BAC/JPM]
avec les paramètres suivants :

entry_z_score:    1.6
exit_z_score:     0.5
lookback_window:  120
use_kalman:       true
adaptive_window:  true
start_date:       2020-01-01
end_date:         2024-12-31
```

---

## VALIDATIONS RAPIDES

Commandes à lancer à tout moment sans prompt :
```powershell
# Tests complets (venv Python 3.11)
venv\Scripts\python.exe -m pytest tests/ -q

# Tests avec warnings stricts
venv\Scripts\python.exe -m pytest tests/ -W error::DeprecationWarning -q

# Linting
venv\Scripts\python.exe -m ruff check .

# Type check
venv\Scripts\python.exe -m mypy risk/ risk_engine/ execution/ --ignore-missing-imports --no-error-summary

# Recompiler Cython
venv\Scripts\python.exe setup.py build_ext --inplace

# Vérifier risk tiers
venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"

# Config par environnement
venv\Scripts\python.exe -c "from config.settings import get_settings; s=get_settings(); print(s.strategy.entry_z_score)"
```

---

## STRUCTURE COMPLÈTE DU DOSSIER TASKS
```
tasks/
├── WORKFLOW.md                          ← ce fichier
├── lessons.md                           ← leçons capturées (lire en début de session)
│
├── prompts/                             ← instructions pour agents
│   ├── audit_master_prompt.md           ← audit #8 (toutes dimensions)
│   ├── generate_action_plan_prompt.md   ← étape B (plan d'action)
│   ├── execute_corrections_prompt.md    ← étape C (exécution)
│   ├── audit_structural_prompt.md       ← audit #1 (architecture & modules)
│   ├── audit_ai_driven_prompt.md        ← audit #2 (fichiers AI-Driven)
│   ├── audit_email_alerts_prompt.md     ← audit #3 (alertes email)
│   ├── audit_ia_ml_prompt.md            ← audit #4 (IA / ML)
│   ├── audit_technical_prompt.md        ← audit #5 (sécurité & technique)
│   ├── audit_cython_prompt.md           ← audit #6 (Cython + build)
│   ├── audit_strategic_prompt.md        ← audit #7 (quant / statistiques)
│   ├── audit_modernize_python_syntax_prompt.md ← audit #9 (ruff + Pylance)
│   ├── add_strategy.md                  ← procédure ajout nouvelle stratégie
│   └── correct_p0.md                    ← template correction P0 critique
│
├── audits/                              ← résultats d'audit (générés par les prompts)
│   └── audit_structural_edgecore.md     ← checklist structurelle (B2 → B5)
│
└── plans/                               ← plans d'action (générés par étape B)
    └── PLAN_ACTION_EDGECORE_2026-03-17.md
```

---

## RÈGLE D'OR

```
Ne jamais lancer l'étape C sans avoir
validé le plan de l'étape B manuellement.

Ne jamais lancer un audit spécialisé
à la place de l'audit master —
les audits spécialisés approfondissent,
ils ne remplacent pas.
```