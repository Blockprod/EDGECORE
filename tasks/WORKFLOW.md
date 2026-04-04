---
type: guide
projet: EDGECORE
broker: Interactive Brokers (TWS/Gateway)
stack: Python 3.11.9 · Cython 3.0 · ib_insync · Windows
derniere_revision: 2026-04-04
creation: 2026-03-18 à 00:53
---

# WORKFLOW — Audit → Plan → Corrections
# EDGECORE — Moteur d'arbitrage statistique market-neutral

Chaque audit suit le même pipeline en **3 étapes** :

| Étape | Prompt | Mode | Produit |
|:---:|---|:---:|---|
| **A** | `audit_<type>_prompt.md` | Ask / Agent | `tasks/audits/resultats/audit_<type>_edgecore.md` |
| **B** | `generate_action_plan_prompt.md` | Agent | `tasks/corrections/plans/PLAN_ACTION_<type>_[DATE].md` |
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
| 6 | [Cython & Build](#6--cython--build) | .pyx ↔ consommateurs · Fallback Python · Build reproductible · Tests | Ask |
| 7 | [Pipeline](#7--pipeline) | Cohérence config→live→backtest · All-or-nothing guards · Modèle coûts · RiskFacade · Routage IBKR | Agent |
| 8 | [Stratégique](#8--stratégique) | Intégrité statistique · Walk-forward · Kalman · Risk management financier | Ask |
| 9 | [Master](#9--master) | Audit complet toutes dimensions | Agent |
| 10 | [Modernisation Python](#10--modernisation-python-syntax) | Ruff · Pylance · syntaxe 3.11.9 · ARG · Alignement Cython | Agent |
| 11 | [Latence Institutionnel](#11--latence-institutionnel) | Chemin critique bar→ordre · Cython fallback · IBKR threading · Pipeline signal · Sources tierces | Agent |
| 12 | [Best Practices AI](#12--best-practices-ai) | Claude · Copilot Pro+ · VSCode · fichiers contexte · patterns prompts | Agent |
| 13 | [Trade Journal](#13--trade-journal) | AuditTrail · BrokerReconciler · persistance · réconciliation live↔backtest · crash recovery | Agent |
| 14 | [Fix Errors](#14--fix-errors) | Correction itérative ruff · pyright · ARG · Cython · pipeline 5 phases P1→P5 | Agent |
| 15 | [Best Practices AI](#15--best-practices-ai) | Claude · Copilot · HyperAgents · mémoire · hooks · orchestration · prompts · CI/CD · sécurité | Agent |
| 16 | [Process & Documentation](#16--process--documentation) | CI/CD · Automatisation build/tests · Sécurité · Exploitation · Documentation onboarding/usage/monitoring | Agent |
| 17 | [Validation Plan Grok](#17--validation-plan-grok) | Vérification point par point du plan Grok · Docker prod · Backtester événementiel · Observabilité · Scalabilité · Preuves de performance | Agent |
| 18 | [Final Upgrade](#18--final-upgrade) | Architecture réelle vs documentée · Choix techniques · Robustesse code · Cohérence système de trading · Points de rupture · Améliorations à fort levier | Agent |


## `1 · STRUCTUREL`

> Pipeline stat-arb · Couplage modules · SRP · Doublons fonctionnels · execution/ vs execution_engine/ · risk/ vs risk_engine/

**Produit A** : `tasks/audits/resultats/audit_structural_edgecore.md`

**A — Audit**
```
#file:tasks/audits/code/audit_structural_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `2 · AI-DRIVEN (FILE ENGINEERING)`

> État des fichiers AI-Driven · copilot-instructions · agents/ · architecture/ · knowledge/ · Plan de migration

**Produit A** : `tasks/audits/resultats/audit_ai_driven_edgecore.md`

**A — Audit & restructuration**
```
#file:tasks/audits/methode/audit_ai_driven_prompt.md
Lance cet audit et cette restructuration sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `3 · EMAIL & ALERTES`

> Couverture notifications trading · Kill switch · Alertes drawdown · Protection tempêtes · Sécurité SMTP

**Produit A** : `tasks/audits/resultats/audit_email_alerts_edgecore.md`

**A — Audit**
```
#file:tasks/audits/code/audit_email_alerts_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `4 · IA / ML`

> Modules ML orphelins vs actifs · Opportunités z-score/régime/seuils · Réalisme déploiement IBKR

**Produit A** : `tasks/audits/resultats/audit_ia_ml_edgecore.md`

**A — Audit**
```
#file:tasks/audits/methode/audit_ia_ml_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `5 · TECHNIQUE & SÉCURITÉ`

> Sécurité credentials IBKR · Thread-safety · Robustesse IB Gateway · Gestion erreurs asyncio · Pipeline CI/CD

**Produit A** : `tasks/audits/resultats/audit_technical_edgecore.md`

**A — Audit**
```
#file:tasks/audits/code/audit_technical_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `6 · CYTHON & BUILD`

> Cohérence .pyx ↔ consommateurs · Fallback Python · Build reproductible · setup.py · Couverture tests · Imports suspects

**Produit A** : `tasks/audits/resultats/audit_cython_edgecore.md`

**A — Audit**
```
#file:tasks/audits/code/audit_cython_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `7 · PIPELINE`

> Cohérence des paramètres config→live→backtest · Pipeline all-or-nothing (guards KillSwitch/Risk/Allocator) · Modèle de coûts · Alignement RiskFacade · Routage d'exécution IBKR/Paper

**Produit A** : `tasks/audits/resultats/audit_pipeline_edgecore.md`

**A — Audit**
```
#file:tasks/audits/code/audit_pipeline_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `8 · STRATÉGIQUE`

> Intégrité statistique des signaux · Biais backtest · Walk-forward · Cohérence backtest ↔ live · Kalman · Risk management financier

**Produit A** : `tasks/audits/resultats/audit_strategic_edgecore.md`

**A — Audit**
```
#file:tasks/audits/code/audit_strategic_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `9 · MASTER`

> Audit complet couvrant toutes les dimensions du projet en une seule passe

**Produit A** : `tasks/audits/resultats/audit_master_edgecore.md`

**A — Audit**
```
#file:tasks/audits/code/audit_master_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `10 · MODERNISATION PYTHON SYNTAX`

> Ruff auto-fix · Pylance erreurs résiduelles · syntaxe Python 3.11.9 · ARG orphelins · Alignement Cython · dossier par dossier

**Produit** : corrections appliquées directement · 2787 tests verts

**A — Audit & corrections**
```
#file:tasks/audits/code/audit_modernize_python_syntax_prompt.md
Lance cet audit sur le workspace.
```

> ⚠️ Cet audit intègre les étapes B et C directement —
> il corrige et valide en une seule passe. Aucun plan intermédiaire requis.

---

## `11 · LATENCE INSTITUTIONNEL`

> Chemin critique bar → signal → ordre · Re-découverte de paires (O(N²)) · Cython fallback silencieux · Contention GIL/locks · I/O synchrones · Sources de données tierces (violation institutionnelle)

**Produit A** : `tasks/audits/resultats/audit_latence_edgecore.md`

**A — Audit**
```
#file:tasks/audits/code/audit_latence_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `12 · BEST PRACTICES AI`

> Best practices Claude · Copilot Pro+ · VSCode · fichiers contexte AI-Driven · patterns prompts réutilisables

**Produit A** : `tasks/audits/resultats/audit_best_practices_edgecore.md`

**A — Audit**
```
#file:tasks/audits/methode/best_practices_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `13 · TRADE JOURNAL`

> AuditTrail · BrokerReconciler · persistance live · réconciliation live↔backtest · atomicité · crash recovery · contexte signal

**Produit A** : `tasks/audits/resultats/audit_trade_journal_edgecore.md`

**A — Audit**
```
#file:tasks/audits/code/audit_trade_journal_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `14 · FIX ERRORS`

> Correction itérative des erreurs statiques · ruff · pyright · ARG · Cython · 0 régression
> Pipeline séquentiel **P1 → P2 → P3 → P4 → P5** — ne jamais sauter une phase.

| Phase | Prompt | Mode | Produit |
|:---:|---|:---:|---|
| **P1** | `P1- SCAN_prompt_edgecore.md` | Agent | `tasks/audits/fix_errors/SCAN_result.md` |
| **P2** | `P2- PLAN_prompt_edgecore.md` | Agent | `tasks/audits/fix_errors/PLAN_result.md` |
| **P3** | `P3- FIX_core_prompt_edgecore.md` | Agent | corrections appliquées · `BATCH_result.md` |
| **P4** | `P4- VERIFY_prompt_edgecore.md` | Agent | `tasks/audits/fix_errors/VERIFY_result.md` |
| **P5** | `P5- FINAL QA_prompt_edgecore.md` | Agent | `tasks/audits/fix_errors/FINAL_QA_result.md` |

---

## `P1 · SCAN (FIX ERRORS)`

> Scanner tout le projet sans modifier — ruff · pyright · ARG · classification par type d'erreur

**Produit** : `tasks/audits/fix_errors/SCAN_result.md`

**P1 — Scan**
```
#file:tasks/audits/fix_errors/P1- SCAN_prompt_edgecore.md
Lance ce scan sur le workspace.
```

---

## `P2 · PLAN (FIX ERRORS)`

> Créer un plan de correction optimal groupé par batch · priorité models → pair_selection → … → tests

**Produit** : `tasks/audits/fix_errors/PLAN_result.md`

**P2 — Plan**
```
#file:tasks/audits/fix_errors/P2- PLAN_prompt_edgecore.md
Génère le plan de correction depuis SCAN_result.md.
```

> ⚠️ Prérequis : `SCAN_result.md` produit par P1.

---

## `P3 · FIX CORE (FIX ERRORS)`

> Corriger un batch du plan · patterns EDGECORE stricts · max 3 itérations/fichier · vérification par fichier puis par batch

**Produit** : corrections appliquées · `tasks/audits/fix_errors/BATCH_result.md`

**P3 — Correction (indiquer le numéro de batch)**
```
#file:tasks/audits/fix_errors/P3- FIX_core_prompt_edgecore.md
Corrige le batch 1 depuis PLAN_result.md.
```

> ⚠️ Relancer P3 pour chaque batch jusqu'à `remaining_errors: 0`.
> P3 peut être relancé plusieurs fois — P4 et P5 seulement une fois tous les batches terminés.

---

## `P4 · VERIFY (FIX ERRORS)`

> Validation indépendante complète · ruff · ARG · pyright 49 dossiers · pytest ≥ 2800 · risk tiers · config

**Produit** : `tasks/audits/fix_errors/VERIFY_result.md`

**P4 — Vérification**
```
#file:tasks/audits/fix_errors/P4- VERIFY_prompt_edgecore.md
Lance la vérification complète.
```

> ⚠️ Si VERDICT = FAIL → relancer P3 sur les batches concernés avant P5.

---

## `P5 · FINAL QA (FIX ERRORS)`

> Checklist release 12 points · DeprecationWarning · Cython import · smoke imports pipeline · interdictions grep · Docker · CI

**Produit** : `tasks/audits/fix_errors/FINAL_QA_result.md`

**P5 — QA finale**
```
#file:tasks/audits/fix_errors/P5- FINAL QA_prompt_edgecore.md
Lance la QA finale.
```

> ⚠️ Prérequis : `VERIFY_result.md` avec VERDICT GLOBAL = PASS.


## `15 · BEST PRACTICES AI`

> Claude · Copilot · HyperAgents · mémoire · hooks · orchestration · prompts · CI/CD · sécurité

**Produit A** : `tasks/audits/resultats/audit_best_practices_ai_edgecore.md`

**A — Audit (Best Practices AI)**
```
#file:tasks/audits/code/audit_best_practices_ai_prompt.md
Lance cet audit sur le workspace en t'appuyant sur les images référencées dans la section SOURCES VISUELLES du prompt.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `16 · PROCESS & DOCUMENTATION`

> CI/CD · Automatisation build/tests · Sécurité · Exploitation · Documentation onboarding/usage/monitoring

**Produit A** : `tasks/audits/resultats/audit_process_doc_edgecore.md`

**A — Audit**
```
#file:tasks/audits/code/audit_process_doc_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `17 · VALIDATION PLAN GROK`

> Vérification point par point du plan Grok (04 avril 2026) · Docker prod · Backtester événementiel · Observabilité · Scalabilité · Preuves de performance · Omissions critiques non mentionnées par Grok

**Produit A** : `tasks/audits/resultats/audit_grok_plan_validation_edgecore.md`

**A — Audit**
```
#file:tasks/audits/code/audit_grok_plan_validation_prompt.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## `18 · FINAL UPGRADE`

> Architecture réelle vs documentée · Graphe de dépendances · Choix techniques · Robustesse code · Cohérence système de trading · Points de rupture critiques · Améliorations à fort levier · Score /10 · Verdict PROTOTYPE → PRODUCTION-READY

**Produit A** : `tasks/audits/resultats/audit_final_upgrade_edgecore.md`

**A — Audit**
```
#file:tasks/audits/code/audit_final_upgrade.md
Lance cet audit sur le workspace.
```

**B — Plan d'action**
```
#file:tasks/corrections/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

**C — Exécution**
```
#file:tasks/corrections/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
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

## RÉFÉRENCE — COMMANDES COPILOT CHAT (VSCODE)

| Commande | Scope | Usage type |
|---|---|---|
| `#file:path/to/file.md` | Fichier entier | Charger un prompt, un fichier de contexte |
| `#file:path/to/module.py` | Fichier entier | Référencer un module de production |
| `#sym:ClassName` | Symbole uniquement | Correction ciblée sur une classe ou fonction |
| `#codebase` | Tout le projet | Recherche sémantique globale, audits master |

**Quand utiliser `#sym:` plutôt que `#file:`** :
- `#sym:KillSwitch` → correction d'un bug dans la classe uniquement
- `#sym:_ibkr_rate_limiter` → ajout d'un `acquire()` manquant
- `#sym:RiskFacade` → vérification de l'injection des managers

**Ne pas utiliser `#sym:` pour** : tests, configs YAML, fichiers markdown.

---

## STRUCTURE COMPLÈTE DU DOSSIER TASKS
```
tasks/
├── WORKFLOW.md                                   ← ce fichier
├── lessons.md                                    ← leçons capturées (lire en début de session)
│
├── audits/
│   ├── code/                                     ← prompts audit qualité code
│   │   ├── audit_master_prompt.md                ← audit #8 (toutes dimensions)
│   │   ├── audit_structural_prompt.md            ← audit #1 (architecture & modules)
│   │   ├── audit_email_alerts_prompt.md          ← audit #3 (alertes email)
│   │   ├── audit_technical_prompt.md             ← audit #5 (sécurité & technique)
│   │   ├── audit_cython_prompt.md                ← audit #6 (Cython + build)
│   │   ├── audit_pipeline_prompt.md               ← audit #7 (pipeline stat-arb)
│   │   ├── audit_strategic_prompt.md             ← audit #8 (quant / statistiques)
│   │   ├── audit_modernize_python_syntax_prompt.md ← audit #10 (ruff + Pylance)
│   │   ├── audit_latence_prompt.md               ← audit #11 (latence)
│   │   └── audit_trade_journal_prompt.md          ← audit #13 (trade journal)
│   ├── methode/                                  ← prompts audit méthode / IA
│   │   ├── audit_ai_driven_prompt.md             ← audit #2 (fichiers AI-Driven)
│   │   ├── audit_ia_ml_prompt.md                 ← audit #4 (IA / ML)
│   │   └── best_practices_prompt.md              ← audit #11 (best practices Copilot)
│   └── resultats/                                ← résultats d'audit (générés)
│       └── audit_*_edgecore.md
│
└── corrections/
    ├── generate_action_plan_prompt.md            ← étape B (plan d'action)
    ├── execute_corrections_prompt.md             ← étape C (exécution)
    ├── add_strategy.md                           ← procédure ajout nouvelle stratégie
    └── plans/                                    ← plans d'action (générés par étape B)
        └── PLAN_ACTION_*_[DATE].md
```

---

## POST-ÉTAPE C — Mise à jour obligatoire de `tasks/lessons.md`

Après chaque exécution d'étape C, ajouter une entrée dans `tasks/lessons.md` :

```
## [DATE] — Corrections [TYPE]
- Ce qui a fonctionné : ...
- Ce qui a bloqué : ...
- À retenir pour la prochaine fois : ...
- Issues closes : [B*-* ou BP-*]
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