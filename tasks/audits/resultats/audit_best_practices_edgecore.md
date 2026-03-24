# AUDIT BEST PRACTICES — EDGECORE_V1 — 2026-03-24
**Création :** 2026-03-24  
*Exécuté par : GitHub Copilot (Claude Sonnet 4.6)*  
*Prompt : `tasks/audits/methode/best_practices_prompt.md`*

Sources analysées :
- https://github.com/shanraisshan/claude-code-best-practice
- https://claude.com/fr-fr/blog/using-claude-md-files
- https://code.claude.com/docs/
- https://platform.claude.com/docs/en/home

Stack : Claude Sonnet 4.6 · Copilot Pro+ · VSCode · Python 3.11 · IBKR

---

## BEST PRACTICES DÉJÀ EN PLACE

| # | Practice | Source | Fichier | Statut |
|---|---|---|---|---|
| 1 | Context file projet pour Copilot (≤ 200 lignes) | claude.com/blog | `.github/copilot-instructions.md` (116 lignes) | ✅ |
| 2 | Règles de modification strictes | shanraisshan | `.claude/rules.md` | ✅ |
| 3 | Snapshot complet du projet (pipeline, modules, paramètres) | shanraisshan | `.claude/context.md` | ✅ |
| 4 | Agents spécialisés avec description, domaine et checklist | shanraisshan (skills) | `agents/quant_researcher.md`, `agents/risk_manager.md`, `agents/code_auditor.md`, `agents/dev_engineer.md` | ✅ |
| 5 | Base de connaissances domaine (contraintes broker, trading) | shanraisshan | `knowledge/ibkr_constraints.md`, `knowledge/trading_constraints.md` | ✅ |
| 6 | ADRs — Architecture Decision Records | shanraisshan | `architecture/decisions.md` (ADR-001 → ADR-008) | ✅ |
| 7 | Diagrammes ASCII du pipeline dans les fichiers de contexte | shanraisshan | `.claude/context.md` (section pipeline DataLoader → AuditTrail) | ✅ |
| 8 | Workflow structuré explore → plan → execute → commit | claude.com/blog | `tasks/WORKFLOW.md` (étapes A+B+C, lignes 15-25) | ✅ |
| 9 | Prompts réutilisables organisés par type et phase | shanraisshan (commands) | `tasks/audits/code/`, `tasks/audits/methode/`, `tasks/corrections/` | ✅ |
| 10 | `#file:` pour cibler le contexte dans les prompts | claude.com/blog | Tous les fichiers `tasks/audits/*_prompt.md` (frontmatter) | ✅ |
| 11 | Leçons capturées en fichier dédié | shanraisshan | `tasks/lessons.md` | ✅ |
| 12 | Secrets jamais dans les fichiers de contexte AI | claude.com/blog | `common/secrets.py`, `config/schemas.py` (env vars) | ✅ |
| 13 | Type checking + formatter imposés via VSCode | code.claude.com | `pyrightconfig.json`, `.vscode/settings.json` (ruff formatOnSave) | ✅ |

---

## BEST PRACTICES MANQUANTES — PERTINENTES COPILOT

### BP-01 — Directive de raisonnement profond dans les prompts complexes

**Source** : https://github.com/shanraisshan/claude-code-best-practice  
**Description** : L'ajout du mot-clé `ultrathink` (ou son équivalent : "Réfléchis profondément étape par étape avant de répondre") dans les prompts complexes force le modèle à activer un raisonnement étendu avant de produire une réponse. Cette pratique est particulièrement documentée pour les tâches d'audit, de correction multi-fichiers, et de planification stratégique.

**Pourquoi pertinent pour EDGECORE_V1 + Copilot VSCode** :  
Les prompts d'audit EDGECORE (audit_technical, audit_latence, audit_master) sont des missions complexes impliquant l'analyse de dizaines de fichiers, la détection de dettes croisées et la hiérarchisation de corrections. Ces tâches bénéficient directement d'un raisonnement étendu. La directive s'intègre dans les prompts existants sans modifier la structure.

**Comment l'appliquer concrètement** :
- Dans chaque fichier `tasks/audits/*_prompt.md`, ajouter au début de la section MISSION :
  ```
  ─────────────────────────────────────────────
  RAISONNEMENT
  ─────────────────────────────────────────────
  Réfléchis profondément étape par étape avant
  de produire ta sortie. Explore d'abord, planifie
  ensuite, puis exécute.
  ```
- L'ajouter aussi dans `tasks/corrections/execute_corrections_prompt.md` (étape C, la plus risquée)
- Utiliser dans Copilot Chat avec `#file:tasks/audits/code/audit_technical_prompt.md`

**Effort** : XS  
**Impact estimé** : Réduction des erreurs d'analyse sur les audits multi-fichiers ; meilleure cohérence entre les sections d'un même audit (détection croisée entre issues B2, B3, B4, B5)

---

### BP-02 — `.vscode/tasks.json` pour les commandes de validation

**Source** : https://code.claude.com/docs/ + shanraisshan  
**Description** : Définir les commandes de validation récurrentes (pytest, build Cython, vérification risk tiers) comme VSCode Tasks permet à Copilot de les référencer précisément via `#task:`, réduit les erreurs de frappe et assure la cohérence entre agents.

**Pourquoi pertinent pour EDGECORE_V1 + Copilot VSCode** :  
Le projet utilise 5 commandes de validation récurrentes (listées dans `.github/copilot-instructions.md` section "Commandes de validation"). Aujourd'hui, chaque agent doit les retaper. Un `tasks.json` les centralise et permet à Copilot Chat de les invoquer directement via "Run Task".

**Comment l'appliquer concrètement** :
- Créer `.vscode/tasks.json` :
  ```json
  {
    "version": "2.0.0",
    "tasks": [
      {
        "label": "pytest (complet)",
        "type": "shell",
        "command": "venv\\Scripts\\python.exe -m pytest tests/ -q",
        "group": { "kind": "test", "isDefault": true },
        "presentation": { "reveal": "always" }
      },
      {
        "label": "pytest (DeprecationWarning strict)",
        "type": "shell",
        "command": "venv\\Scripts\\python.exe -m pytest tests/ -W error::DeprecationWarning -q",
        "group": "test"
      },
      {
        "label": "Cython build",
        "type": "shell",
        "command": "venv\\Scripts\\python.exe setup.py build_ext --inplace",
        "group": "build"
      },
      {
        "label": "Risk tier coherence check",
        "type": "shell",
        "command": "venv\\Scripts\\python.exe -c \"from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')\"",
        "group": "test"
      }
    ]
  }
  ```
- Dans Copilot Chat : "Exécute la task pytest (complet) et analyse les résultats"

**Effort** : S  
**Impact estimé** : Zéro typos sur les commandes de validation ; tous les agents utilisent exactement la même commande ; accès Ctrl+Shift+P → "Run Task" pour validation rapide

---

### BP-03 — Exemple d'invocation dans les fichiers agents

**Source** : https://github.com/shanraisshan/claude-code-best-practice (skills/subagents section)  
**Description** : Les fichiers agents (`agents/*.md`) décrivent le domaine et la checklist mais ne montrent pas comment l'invoquer depuis Copilot Chat. En CLI Claude Code, les agents ont une syntaxe dédiée. Pour Copilot VSCode, l'équivalent est un bloc "Invocation" avec la commande `#file:` exacte.

**Pourquoi pertinent pour EDGECORE_V1 + Copilot VSCode** :  
Les 4 agents EDGECORE (quant_researcher, risk_manager, code_auditor, dev_engineer) sont des fichiers de référence solides mais n'ont aucune section "Comment utiliser dans Copilot". Un développeur qui ouvre le projet ne sait pas comment activer l'agent code_auditor dans sa session Copilot.

**Comment l'appliquer concrètement** :
- Ajouter à chaque fichier `agents/*.md` une section finale :
  ```markdown
  ---
  ## Invocation dans Copilot Chat (VSCode)

  **Mode Ask** :
  ```
  #file:agents/code_auditor.md
  #file:.claude/rules.md
  Vérifie la conformité de [module] selon ta checklist.
  ```

  **Mode Agent** :
  ```
  #file:agents/code_auditor.md
  #codebase
  Lance un audit complet B2→B5 sur le module risk_engine/.
  ```
  ```
- Fichiers à modifier : `agents/code_auditor.md`, `agents/dev_engineer.md`, `agents/quant_researcher.md`, `agents/risk_manager.md`

**Effort** : XS  
**Impact estimé** : Réduction du temps d'initialisation de session avec un agent spécialisé ; onboarding facilité si un second développeur rejoint le projet

---

### BP-04 — Protocol explicite de mise à jour de `tasks/lessons.md`

**Source** : https://github.com/shanraisshan/claude-code-best-practice (memory / lessons learned)  
**Description** : `tasks/lessons.md` existe et est listé dans WORKFLOW.md comme "lire en début de session" (ligne 398). Mais il n'y a aucune instruction pour l'écrire en fin de session — ni dans WORKFLOW.md, ni dans les prompts d'étape C. La boucle feedback est incomplète.

**Pourquoi pertinent pour EDGECORE_V1 + Copilot VSCode** :  
EDGECORE a produit 10 audits et de nombreuses corrections. Les leçons tirées (ex. : B2-01 → ne jamais dupliquer les types d'ordre, B5-01 → EDGECORE_ENV doit être `prod`) ont de la valeur pour les sessions futures. Sans protocole d'écriture, `tasks/lessons.md` devient stale.

**Comment l'appliquer concrètement** :
- Dans `tasks/WORKFLOW.md`, ajouter après l'étape C :
  ```markdown
  ### Post-étape C — Mise à jour obligatoire de lessons.md

  Après chaque exécution d'étape C, ajouter une entrée dans `tasks/lessons.md` :
  ```
  ## [DATE] — Correction [TYPE]
  - Ce qui a fonctionné : ...
  - Ce qui a bloqué : ...  
  - À retenir pour la prochaine fois : ...
  - Issues closes : [liste des B*-*]
  ```
  ```
- Dans `tasks/corrections/execute_corrections_prompt.md`, ajouter en sortie obligatoire :
  ```
  - Mettre à jour tasks/lessons.md avec les leçons de cette session
  ```

**Effort** : XS  
**Impact estimé** : Capitalisation progressive sur les corrections passées ; réduction des régressions sur des issues déjà résolues

---

### BP-05 — `#sym:` pour cibler les symboles dans les prompts techniques

**Source** : https://claude.com/fr-fr/blog/using-claude-md-files (contexte #file / #sym dans Copilot)  
**Description** : Dans Copilot Chat VSCode, `#sym:NomDeClasse` ou `#sym:nom_de_fonction` charge uniquement la définition du symbole et ses références directes, sans charger tout le fichier. C'est plus précis que `#file:` pour les prompts axés sur un seul module.

**Pourquoi pertinent pour EDGECORE_V1 + Copilot VSCode** :  
Les audits EDGECORE adressent souvent des classes spécifiques : `RiskFacade`, `KillSwitch`, `ExecutionRouter`, `PairDiscoveryEngine`. Utiliser `#sym:KillSwitch` dans le prompt charge le contexte exact sans surcharger la fenêtre de contexte avec des modules non liés.

**Comment l'appliquer concrètement** :
- Dans les prompts ciblés (ex. audit d'un module précis), remplacer `#file:risk_engine/kill_switch.py` par `#sym:KillSwitch` quand seule la classe est concernée
- Documenter l'usage dans `tasks/WORKFLOW.md` section "Commandes Copilot utiles" :
  ```markdown
  | Commande Copilot | Usage |
  |---|---|
  | `#file:path/to/file.py` | Charger un fichier entier |
  | `#sym:ClassName` | Charger uniquement la définition d'une classe |
  | `#codebase` | Recherche sémantique dans tout le projet |
  ```

**Effort** : XS  
**Impact estimé** : Réduction du context window utilisé sur les prompts ciblés ; moins de bruit pour les corrections chirurgicales sur une seule classe

---

## BEST PRACTICES NON APPLICABLES (Claude Code CLI)

| # | Practice | Source | Raison |
|---|---|---|---|
| 1 | Hooks `PreToolUse` / `PostToolUse` | shanraisshan | Nécessite la commande `claude` CLI — non disponible dans Copilot VSCode |
| 2 | Slash commands (`/clear`, `/init`, `/compact`, `/review`) | claude.com/blog | Commandes internes au CLI Claude Code — Copilot a ses propres raccourcis |
| 3 | Settings.json Claude Code (`model`, `permissions`, `apiKeyHelper`) | shanraisshan | Fichier de config propre au CLI Claude Code, distinct de `.vscode/settings.json` |
| 4 | MCP servers (configuration et invocation) | code.claude.com | Nécessite le CLI ou l'API Anthropic directe |
| 5 | Agent SDK Anthropic (`claude --agent`) | code.claude.com / platform.claude.com | API Anthropic directe — hors périmètre Copilot Pro+ |
| 6 | Scheduling (`claude --schedule`, Desktop scheduled tasks) | code.claude.com | CLI uniquement |
| 7 | CI/CD Claude Code (GitHub Actions, GitLab CI) | code.claude.com | Nécessite token API Anthropic dans les secrets CI |
| 8 | CLAUDE.md auto-exécuté au démarrage de session | claude.com/blog | Comportement spécifique CLI — dans Copilot, `.github/copilot-instructions.md` est chargé passivement comme contexte, pas exécuté |
| 9 | `/init` pour générer CLAUDE.md automatiquement | claude.com/blog | CLI uniquement — EDGECORE a déjà ses fichiers de contexte manuels |
| 10 | Canaux (Telegram, Discord, Slack webhooks) | code.claude.com | API uniquement |

---

## BEST PRACTICES MANQUANTES — NON PERTINENTES

| # | Practice | Source | Raison de non-pertinence |
|---|---|---|---|
| 1 | Contrôle à distance web/mobile (Remote Control) | code.claude.com | Pas de cas d'usage de développement mobile pour un système de trading serveur |
| 2 | GitHub Code Review automatique sur chaque PR | code.claude.com | Pas de pipeline CD actif sur EDGECORE — revues manuelles suffisantes |
| 3 | `bash:command` dans CLAUDE.md pour exécution auto | claude.com/blog | EDGECORE n'utilise pas Claude Code CLI — les commandes VSCode Tasks (BP-02) couvrent besoin |
| 4 | User-level vs project-level CLAUDE.md distinction | claude.com/blog | Un seul développeur sur le projet — le project-level suffit |

---

## SYNTHÈSE ET PRIORITÉS

| Priorité | Practice | Effort | Impact | Fichier(s) à modifier |
|---|---|---|---|---|
| **P1** | BP-01 — Directive raisonnement profond (ultrathink) | XS | 🔴 High | Tous les `tasks/audits/*_prompt.md` + `execute_corrections_prompt.md` |
| **P2** | BP-04 — Protocol mise à jour `lessons.md` | XS | 🟠 Medium | `tasks/WORKFLOW.md` + `tasks/corrections/execute_corrections_prompt.md` |
| **P3** | BP-03 — Exemple d'invocation dans agents/ | XS | 🟠 Medium | `agents/*.md` (4 fichiers) |
| **P4** | BP-02 — `.vscode/tasks.json` validation commands | S | 🟡 Medium | `.vscode/tasks.json` (à créer) |
| **P5** | BP-05 — `#sym:` dans prompts ciblés | XS | 🟡 Low-Medium | `tasks/WORKFLOW.md` (section référence) |

### Note sur les priorités

**BP-01 est la priorité 1** car elle s'applique à l'outil le plus utilisé (les prompts d'audit) avec un effort minimal (3 lignes par fichier de prompt). L'impact est immédiat sur la qualité des audits complexes comme l'audit technique ou l'audit master.

**BP-04 est la priorité 2** car `tasks/lessons.md` existe mais n'est jamais alimenté de manière systématique — la boucle de capitalisation est incomplète depuis la création du fichier.

**BP-02 est classé P4** plutôt que P2 car les commandes de validation sont déjà dans `.github/copilot-instructions.md` et accessibles. Le gain est réel mais moins urgent que les améliorations de prompt.
