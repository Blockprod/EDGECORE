---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/resultats/audit_process_doc_edgecore.md
derniere_revision: 2026-03-27
creation: 2026-03-27 à 00:00
---

# PROMPT D'AUDIT — Processus & Documentation EDGECORE

## Objectif
Évaluer la maturité du projet EDGECORE_V1 sur les axes "Process" (CI/CD, automatisation, sécurité, exploitation) et "Documentation" (onboarding, usage, monitoring, bonnes pratiques).

## Instructions d'audit

1. **Process**
   - Vérifie la présence d'un pipeline CI/CD (tests, lint, build Docker, déploiement auto).
   - Contrôle l'automatisation de la recompilation Cython et des vérifications critiques (risk tier, config) dans la CI.
   - Vérifie la génération et la publication d'un rapport de couverture de tests (ex : pytest-cov).
   - Analyse l'intégration de checks de sécurité (dépendances, secrets, audit code) dans la CI.
   - Recherche la documentation/versioning des procédures d'exploitation (runbook, rollback, monitoring).

2. **Documentation**
   - Vérifie la complétude/actualité du README.md (onboarding, installation, usage, troubleshooting, FAQ).
   - Recherche la présence d'exemples d'utilisation (scripts, notebooks, cas d'usage).
   - Analyse la documentation de la configuration (structure YAML, variables d'environnement, overrides).
   - Vérifie la documentation du monitoring (Prometheus, Grafana), alertes, gestion des incidents.
   - Cherche une section "bonnes pratiques" et "limitations connues".

## SORTIE OBLIGATOIRE
- Crée le fichier résultat : `tasks/audits/resultats/audit_process_doc_edgecore.md`
- Fournis un tableau synthèse :

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|

- Ajoute une synthèse globale (forces, faiblesses, recommandations prioritaires).
- Confirme dans le chat : "✅ tasks/audits/resultats/audit_process_doc_edgecore.md créé · 🔴 X · 🟠 X · 🟡 X"
