---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/resultats/audit_best_practices_edgecore.md
derniere_revision: 2026-03-24
creation: 2026-03-24 à 15:28
---

#codebase

Voici 3 sources de "best practices" pour les projets
utilisant Claude et GitHub Copilot dans VSCode :

  https://github.com/shanraisshan/claude-code-best-practice
  https://claude.com/fr-fr/blog/using-claude-md-files
  https://code.claude.com/docs/
  https://platform.claude.com/docs/en/home

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Réfléchis profondément étape par étape avant
de produire ta sortie. Explore d'abord, planifie
ensuite, puis exécute.

─────────────────────────────────────────────
MISSION
─────────────────────────────────────────────
1. Lis le contenu de chacun de ces 4 liens
2. Analyse l'ensemble du projet EDGECORE_V1 pour
   cartographier ce qui est déjà en place
3. Identifie les best practices présentes dans
   ces sources qui NE SONT PAS encore utilisées
   dans le projet
4. Pour chaque best practice identifiée, évalue
   sa pertinence dans le contexte exact du projet :
   Claude Sonnet 4.6 via Copilot Pro+ dans VSCode
   (pas Claude Code CLI, pas d'API directe)

─────────────────────────────────────────────
CONTEXTE PROJET
─────────────────────────────────────────────
EDGECORE_V1 est un système de trading algorithmique
stat-arb (paires cointégrées) sur Interactive Brokers.
Stack : Python 3.11 · ib_insync · Cython · pandas · structlog.
L'IA (Copilot Pro+) intervient sur :
  - Développement et correction de code production
  - Audit de qualité / latence / risque
  - Génération et exécution de plans d'action
Fichiers de contexte existants :
  .github/copilot-instructions.md
  .claude/rules.md
  .claude/context.md
  tasks/ (audits, corrections, lessons, workflow)

─────────────────────────────────────────────
FILTRE OBLIGATOIRE
─────────────────────────────────────────────
⚠️ Certaines best practices des sources sont
spécifiques à Claude Code CLI (outil terminal)
ou à l'API Anthropic directe.

Ces pratiques sont NON PERTINENTES pour ce projet
et doivent être classées séparément :

Exclure automatiquement :
- Tout ce qui nécessite la commande `claude` en CLI
- Tout ce qui nécessite un token API Anthropic
- Les hooks Claude Code (PreToolUse, PostToolUse)
- Les commandes slash Claude Code (/compact, /init…)
- Les fichiers CLAUDE.md auto-exécutés par Claude Code
  (ils restent utiles comme contexte Copilot mais
   leur comportement est différent — à signaler)

Conserver et évaluer :
- Les pratiques applicables via #codebase ou #file
  dans Copilot Chat VSCode
- Les fichiers de contexte (.github/copilot-instructions.md,
  .claude/rules.md, .claude/context.md)
- Les structures de prompts réutilisables dans tasks/
- Les patterns d'organisation de repo pour l'IA
- Les pratiques de documentation orientées IA

─────────────────────────────────────────────
CONTRAINTES
─────────────────────────────────────────────
- Base chaque recommandation sur le code réel
  du projet — pas de généralités
- Tiens compte de la spécificité du domaine :
  trading algo, risque financier, IBKR, Cython
- Pour chaque best practice déjà en place :
  cite le fichier:ligne qui le prouve
- Pour chaque best practice manquante et pertinente :
  explique concrètement comment l'appliquer
  à EDGECORE_V1 avec Copilot Pro+ dans VSCode
- Verdict pour chaque best practice :
  ✅ DÉJÀ EN PLACE
  ❌ MANQUANT — PERTINENT (Copilot VSCode)
  ⚠️ PARTIEL
  🚫 NON APPLICABLE (Claude Code CLI uniquement)

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/resultats/audit_best_practices_edgecore.md

Structure du fichier :

# AUDIT BEST PRACTICES — EDGECORE_V1 — [DATE]
Sources analysées : [liste des 4 URLs]
Stack : Claude Sonnet 4.6 · Copilot Pro+ · VSCode · Python 3.11 · IBKR

## BEST PRACTICES DÉJÀ EN PLACE
| Practice | Source | Fichier:Ligne | Statut |

## BEST PRACTICES MANQUANTES — PERTINENTES COPILOT
Pour chaque item :
### [Titre de la best practice]
**Source** : [URL]
**Description** : [ce que c'est]
**Pourquoi pertinent pour EDGECORE_V1 + Copilot VSCode** :
**Comment l'appliquer concrètement** :
  - Fichier à créer ou modifier
  - Contenu exact à ajouter
  - Commande Copilot pour l'utiliser (#file, #codebase…)
**Effort** : XS / S / M / L
**Impact estimé** : [bénéfice concret]

## BEST PRACTICES NON APPLICABLES (Claude Code CLI)
| Practice | Source | Raison |

## BEST PRACTICES MANQUANTES — NON PERTINENTES
| Practice | Source | Raison de non-pertinence |

## SYNTHÈSE ET PRIORITÉS
| Priorité | Practice | Effort | Impact |

Confirme dans le chat :
"✅ audit_best_practices_edgecore.md créé
 ✅ Déjà en place        : X
 ❌ Pertinentes Copilot  : X
 🚫 Claude Code CLI only : X
 ➡️ Priorité 1 : [titre]"
