---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_lean_edgecore.md
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

#codebase

Tu es un Senior Engineer spécialisé en systèmes de trading algorithmique.  
Ton objectif : **cartographier l’existant sur EDGECORE avant toute implémentation** pour éviter duplication ou écrasement de code/test/caches existants.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
1. Vérifie si ce fichier existe déjà :
   `tasks/audits/resultats/audit_lean_edgecore.md`

2. Si trouvé, affiche :
   "⚠️ Audit LEAN existant détecté :
    Fichier : tasks/audits/resultats/audit_lean_edgecore.md
    Date    : [date modification]

    [NOUVEAU]  → audit complet (écrase l'existant)
    [MÀJOUR]   → compléter sections manquantes
    [ANNULER]  → abandonner"

3. Si absent → démarrer directement :
   "✅ Aucun audit LEAN existant. Démarrage..."

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- **Ne modifier aucun fichier**  
- **Ne générer aucun code**  
- Cite fichier:ligne pour chaque point factuel  
- Écris "NONE" si aucune implémentation trouvée  

─────────────────────────────────────────────
BLOC 1 — FEATURE STORE (CACHE)
─────────────────────────────────────────────
Source : data/ + pair_selection/ + models/ + signal_engine/

1.1 Cache existant
    - Existe-t-il un mécanisme de cache (pickle, parquet, joblib) ? (fichier:ligne)
    - Basé sur hash/checksum de paramètres ?
    - NONE / PARTIAL / OK

1.2 Versioning
    - Les artefacts sont-ils horodatés ou versionnés ? (fichier:ligne)
    - NONE / PARTIAL / OK

1.3 Reproductibilité
    - Même entrée → même sortie avec cache ? (fichier:ligne)
    - NONE / PARTIAL / OK

─────────────────────────────────────────────
BLOC 2 — TESTS STATISTIQUES
─────────────────────────────────────────────
Source : tests/

2.1 Tests Sharpe
    - Assertions Sharpe ratio existantes ? (fichier:ligne)
    - NONE / PARTIAL / OK

2.2 Sensibilité paramètres
    - Tests entry_z, half-life variations ? (fichier:ligne)
    - NONE / PARTIAL / OK

2.3 Tests OOS
    - Tests out-of-sample identifiés ? (fichier:ligne)
    - NONE / PARTIAL / OK

─────────────────────────────────────────────
BLOC 3 — RÉGRESSION PnL
─────────────────────────────────────────────
Source : tests/ + backtests/

3.1 Snapshots PnL
    - Snapshots commités existants ? (fichier:ligne)
    - NONE / PARTIAL / OK

3.2 Assertions PnL
    - Assertions numériques sur PnL, Sharpe, drawdown ? (fichier:ligne)
    - NONE / PARTIAL / OK

3.3 Cible make qa
    - `make qa` ou équivalent enchaînant tests + régression ? (fichier:ligne)
    - NONE / PARTIAL / OK

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Créer : tasks/audits/resultats/audit_lean_edgecore.md

Tableau synthèse :

| Amélioration    | Critère             | Statut          | Référence     |
|-----------------|--------------------|----------------|---------------|
| Feature Store   | cache               | OK/PARTIAL/NONE | fichier:ligne |
| Feature Store   | versioning          | OK/PARTIAL/NONE | fichier:ligne |
| Feature Store   | reproductibilité    | OK/PARTIAL/NONE | fichier:ligne |
| Tests stat.     | sharpe_tests        | OK/PARTIAL/NONE | fichier:ligne |
| Tests stat.     | param_sensitivity   | OK/PARTIAL/NONE | fichier:ligne |
| Tests stat.     | oos_tests           | OK/PARTIAL/NONE | fichier:ligne |
| Régression PnL  | snapshots           | OK/PARTIAL/NONE | fichier:ligne |
| Régression PnL  | pnl_assertions      | OK/PARTIAL/NONE | fichier:ligne |
| Régression PnL  | make_qa             | OK/PARTIAL/NONE | fichier:ligne |

Confirmation finale dans le chat :
"✅ tasks/audits/resultats/audit_lean_edgecore.md créé"
