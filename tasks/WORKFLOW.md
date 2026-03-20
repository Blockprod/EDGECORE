---
type: guide
projet: EDGECORE
stack: Python 3.11 · Docker · Interactive Brokers (TWS/Gateway)
derniere_revision: 2026-03-20
---

# WORKFLOW — Audit → Plan → Corrections
# EDGECORE — Moteur d'arbitrage statistique market-neutral

Guide d'utilisation des prompts du dossier tasks/.
Suivre les étapes dans l'ordre strict.

---

## ÉTAPE 1 — Audit complet

**Prompt** : `tasks/prompts/audit_master_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Produit** : `tasks/audits/audit_master_edgecore.md`
```
#file:tasks/prompts/audit_master_prompt.md
Lance cet audit sur le workspace.
```

---

## ÉTAPE 2 — Génération du plan d'action

**Prompt** : `tasks/prompts/generate_action_plan_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Lit**    : `tasks/audits/audit_master_edgecore.md`
**Produit** : `tasks/plans/PLAN_ACTION_EDGECORE_[DATE].md`
```
#file:tasks/prompts/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

---

## ÉTAPE 3 — Exécution des corrections

**Prompt** : `tasks/prompts/execute_corrections_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Lit**    : `tasks/plans/PLAN_ACTION_EDGECORE_[DATE].md`
**Produit** : corrections appliquées · statuts ⏳ → ✅
```
#file:tasks/prompts/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

## AUDITS SPÉCIALISÉS (optionnels)

À lancer après l'ÉTAPE 1 pour approfondir
une dimension spécifique.

### Audit Technique & Sécurité

#### Étape A — Audit

**Prompt** : `tasks/prompts/audit_technical_prompt.md`
**Mode**   : Ask
**Modèle** : Sonnet 4.6
**Dimension** : Sécurité credentials IBKR ·
               Thread-safety · Robustesse API ·
               Gestion erreurs silencieuses ·
               Pipeline CI/CD
**Produit** : `tasks/audits/audit_technical_edgecore.md`
```
#file:tasks/prompts/audit_technical_prompt.md
Lance cet audit sur le workspace.
```

#### Étape B — Génération du plan d'action

**Prompt** : `tasks/prompts/generate_action_plan_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Lit**    : `tasks/audits/audit_technical_edgecore.md`
**Produit** : `tasks/plans/PLAN_ACTION_technical_[DATE].md`
```
#file:tasks/prompts/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

#### Étape C — Exécution des corrections

**Prompt** : `tasks/prompts/execute_corrections_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Lit**    : `tasks/plans/PLAN_ACTION_technical_[DATE].md`
**Produit** : corrections appliquées · statuts ⏳ → ✅
```
#file:tasks/prompts/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

### Audit Stratégique

#### Étape A — Audit

**Prompt** : `tasks/prompts/audit_strategic_prompt.md`
**Mode**   : Ask
**Modèle** : Sonnet 4.6
**Dimension** : Intégrité statistique des signaux ·
               Biais backtest · Walk-forward ·
               Kalman · Risk management financier
**Produit** : `tasks/audits/audit_strategic_edgecore.md`
```
#file:tasks/prompts/audit_strategic_prompt.md
Lance cet audit sur le workspace.
```

#### Étape B — Génération du plan d'action

**Prompt** : `tasks/prompts/generate_action_plan_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Lit**    : `tasks/audits/audit_strategic_edgecore.md`
**Produit** : `tasks/plans/PLAN_ACTION_strategic_[DATE].md`
```
#file:tasks/prompts/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

#### Étape C — Exécution des corrections

**Prompt** : `tasks/prompts/execute_corrections_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Lit**    : `tasks/plans/PLAN_ACTION_strategic_[DATE].md`
**Produit** : corrections appliquées · statuts ⏳ → ✅
```
#file:tasks/prompts/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

### Audit Structurel

#### Étape A — Audit

**Prompt** : `tasks/prompts/audit_structural_prompt.md`
**Mode**   : Ask
**Modèle** : Sonnet 4.6
**Dimension** : Doublons fonctionnels · SRP ·
               Couplage modules · Dettes de code ·
               execution/ vs execution_engine/ ·
               risk/ vs risk_engine/
**Produit** : `tasks/audits/audit_structural_edgecore.md`
```
#file:tasks/prompts/audit_structural_prompt.md
Lance cet audit sur le workspace.
```

#### Étape B — Génération du plan d'action

**Prompt** : `tasks/prompts/generate_action_plan_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Lit**    : `tasks/audits/audit_structural_edgecore.md`
**Produit** : `tasks/plans/PLAN_ACTION_structural_[DATE].md`
```
#file:tasks/prompts/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

#### Étape C — Exécution des corrections

**Prompt** : `tasks/prompts/execute_corrections_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Lit**    : `tasks/plans/PLAN_ACTION_structural_[DATE].md`
**Produit** : corrections appliquées · statuts ⏳ → ✅
```
#file:tasks/prompts/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

### Audit Alertes Email

#### Étape A — Audit

**Prompt** : `tasks/prompts/audit_email_alerts_prompt.md`
**Mode**   : Ask
**Modèle** : Sonnet 4.6
**Dimension** : Couverture notifications trading ·
               Kill switch · Alertes drawdown ·
               Sécurité emails SMTP
**Produit** : `tasks/audits/audit_email_alerts_edgecore.md`
```
#file:tasks/prompts/audit_email_alerts_prompt.md
Lance cet audit sur le workspace.
```

#### Étape B — Génération du plan d'action

**Prompt** : `tasks/prompts/generate_action_plan_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Lit**    : `tasks/audits/audit_email_alerts_edgecore.md`
**Produit** : `tasks/plans/PLAN_ACTION_email_alerts_[DATE].md`
```
#file:tasks/prompts/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

#### Étape C — Exécution des corrections

**Prompt** : `tasks/prompts/execute_corrections_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Lit**    : `tasks/plans/PLAN_ACTION_email_alerts_[DATE].md`
**Produit** : corrections appliquées · statuts ⏳ → ✅
```
#file:tasks/prompts/execute_corrections_prompt.md
Démarre l'exécution du plan d'action disponible.
```

---

### Génération AI-Driven & File Engineering

#### Étape A — Audit

**Prompt** : `tasks/prompts/audit_ai_driven_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Dimension** : Génération fichiers contexte IA ·
               Restructuration AI-native du repo
**Produit** : `tasks/audits/audit_ai_driven_edgecore.md` · `.claude/` · `.github/` ·
              `agents/` · `knowledge/` · `architecture/`
```
#file:tasks/prompts/audit_ai_driven_prompt.md
Génère les fichiers AI-Driven et le plan
de restructuration File Engineering complet.
```

#### Étape B — Génération du plan d'action

**Prompt** : `tasks/prompts/generate_action_plan_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Lit**    : `tasks/audits/audit_ai_driven_edgecore.md`
**Produit** : `tasks/plans/PLAN_ACTION_ai_driven_[DATE].md`
```
#file:tasks/prompts/generate_action_plan_prompt.md
Génère le plan d'action depuis l'audit disponible.
```

#### Étape C — Exécution des corrections

**Prompt** : `tasks/prompts/execute_corrections_prompt.md`
**Mode**   : Agent
**Modèle** : Sonnet 4.6
**Lit**    : `tasks/plans/PLAN_ACTION_ai_driven_[DATE].md`
**Produit** : corrections appliquées · statuts ⏳ → ✅
```
#file:tasks/prompts/execute_corrections_prompt.md
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

## STRUCTURE COMPLÈTE DU DOSSIER TASKS
```
tasks/
├── WORKFLOW.md                          ← ce fichier
├── lessons.md                           ← leçons capturées (lire en début de session)
│
├── prompts/                             ← instructions pour agents
│   ├── audit_master_prompt.md           ← ÉTAPE 1 (audit complet)
│   ├── generate_action_plan_prompt.md   ← ÉTAPE 2 (plan d'action)
│   ├── execute_corrections_prompt.md    ← ÉTAPE 3 (exécution)
│   ├── audit_technical_prompt.md        ← audit sécurité & technique
│   ├── audit_strategic_prompt.md        ← audit quant / statistiques
│   ├── audit_structural_prompt.md       ← audit architecture & modules
│   ├── audit_email_alerts_prompt.md     ← audit alertes email
│   ├── audit_ai_driven_prompt.md        ← génération fichiers AI-Driven
│   ├── add_strategy.md                  ← procédure ajout nouvelle stratégie
│   └── correct_p0.md                    ← template correction P0 critique
│
├── audits/                              ← résultats d'audit (générés par les prompts)
│   └── audit_structural_edgecore.md     ← checklist structurelle (B2 → B5)
│
└── plans/                               ← plans d'action (générés par ÉTAPE 2)
    └── PLAN_ACTION_EDGECORE_2026-03-17.md
```

---

## RÈGLE D'OR

```
Ne jamais lancer ÉTAPE 3 sans avoir
validé le plan de l'ÉTAPE 2 manuellement.

Ne jamais lancer un audit spécialisé
à la place de l'audit master —
les audits spécialisés approfondissent,
ils ne remplacent pas.
```