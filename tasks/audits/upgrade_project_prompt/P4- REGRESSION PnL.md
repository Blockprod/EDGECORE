---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tests/regression/test_pnl_regression.py
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

#codebase

Tu es un Senior Engineer spécialisé en systèmes de trading algorithmique.  
Ton objectif : **implémenter les tests de non-régression PnL** pour EDGECORE, garantissant qu’aucune modification du code ne change silencieusement les résultats financiers.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE
─────────────────────────────────────────────
1. Vérifie si le fichier existe déjà :  
   `tests/regression/test_pnl_regression.py`

2. Si trouvé, affiche :
   "⚠️ Test regression PnL existant détecté :
    Fichier : tests/regression/test_pnl_regression.py
    Date    : [date modification]

    [NOUVEAU]  → écraser et réimplémenter
    [MÀJOUR]   → compléter sections manquantes
    [ANNULER]  → abandonner"

3. Si absent → démarrer directement :
   "✅ Aucun test regression PnL détecté. Démarrage..."

─────────────────────────────────────────────
RÈGLES ABSOLUES
─────────────────────────────────────────────
- Snapshots commités → source de vérité
- Pas de suppression automatique de snapshot
- Seuils et tolérances toujours via `get_settings()`, jamais hardcodé
- Ruff OK · Pyright OK après implémentation

─────────────────────────────────────────────
ÉTAPE 1 — CRÉER tests/regression/test_pnl_regression.py
─────────────────────────────────────────────
1.1 Snapshots à capturer (métriques de référence) :
    - total_pnl
    - sharpe
    - max_drawdown
    - nb_trades

1.2 Tolérance numérique :
    - PNL_TOLERANCE = 1e-4
    - Utiliser `pytest.approx(snapshot, abs=PNL_TOLERANCE)` pour les assertions

1.3 Flag de mise à jour :
    - `pytest --update-snapshots`
    - Présent : écrire les snapshots actuels
    - Absent  : asserter contre snapshots commités

─────────────────────────────────────────────
ÉTAPE 2 — STOCKAGE DES SNAPSHOTS
─────────────────────────────────────────────
2.1 Répertoire : `tests/regression/snapshots/`
2.2 Format     : JSON (1 fichier par scénario)
2.3 Commiter snapshots initiaux immédiatement après création

─────────────────────────────────────────────
ÉTAPE 3 — MAKEFILE
─────────────────────────────────────────────
Ajouter dans le Makefile :

      test-regression:
          pytest tests/regression/ -q

      qa:
          + make test-regression

─────────────────────────────────────────────
VALIDATION OBLIGATOIRE
─────────────────────────────────────────────
- `pytest tests/regression/ -q` → passage intégral
- `ruff check .` → 0 erreur
- `pyright` → 0 erreur
- Snapshots présents dans `tests/regression/snapshots/`

Confirmation finale dans le chat :  
"✅ tests/regression/test_pnl_regression.py créé · snapshots commités"
