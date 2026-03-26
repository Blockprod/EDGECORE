---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: qa_global_ci_edgecore.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

#codebase

Tu es un Senior Engineer spécialisé en systèmes de trading algorithmique.  
Ton objectif : **valider la cohérence globale et le pipeline CI** d’EDGECORE après implémentation du Feature Store, des tests statistiques et de la régression PnL.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE
─────────────────────────────────────────────
1. Vérifie si le fichier existe déjà :  
   `tasks/audits/resultats/qa_global_ci_edgecore.md`

2. Si trouvé, affiche :
   "⚠️ QA global existant détecté :
    Fichier : tasks/audits/resultats/qa_global_ci_edgecore.md
    Date    : [date modification]

    [NOUVEAU]  → écraser et réimplémenter
    [MÀJOUR]   → compléter sections manquantes
    [ANNULER]  → abandonner"

3. Si absent → démarrer directement :
   "✅ Aucun QA global existant. Démarrage..."

─────────────────────────────────────────────
ÉTAPE 1 — VÉRIFICATIONS INDIVIDUELLES
─────────────────────────────────────────────
Source : fichiers produits par Feature Store, Tests Statistiques, Regression PnL

1.1 Lint
    - `ruff check .` → 0 erreur
    - Statut : CONFORME / NON CONFORME

1.2 Typage
    - `pyright` → 0 erreur
    - Statut : CONFORME / NON CONFORME

1.3 Tests unitaires
    - `pytest tests/ -q` → passage intégral
    - Statut : CONFORME / NON CONFORME

1.4 Tests statistiques
    - `pytest tests/statistical/ -q` → passage intégral
    - Statut : CONFORME / NON CONFORME

1.5 Tests de régression PnL
    - `pytest tests/regression/ -q` → aucun drift PnL
    - Statut : CONFORME / NON CONFORME

─────────────────────────────────────────────
ÉTAPE 2 — MAKEFILE FINAL
─────────────────────────────────────────────
Créer ou compléter le Makefile à la racine :

      test-statistical:
          pytest tests/statistical/ -q

      test-regression:
          pytest tests/regression/ -q

      qa:
          ruff check .
          pyright
          pytest tests/ -q
          make test-statistical
          make test-regression

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Rapporter dans le chat :

      QA_STATUS:
        ruff        : OK / ERREUR (N erreurs)
        typing      : OK / ERREUR (N erreurs)
        tests       : OK / ERREUR (N failures)
        statistical : OK / ERREUR (N failures)
        regression  : OK / ERREUR (N failures)

Si toutes les lignes = OK :
"✅ QA global EDGECORE — 0 erreur · pipeline qualité opérationnel"

Sinon :
- Lister chaque erreur avec fichier:ligne avant de s’arrêter
