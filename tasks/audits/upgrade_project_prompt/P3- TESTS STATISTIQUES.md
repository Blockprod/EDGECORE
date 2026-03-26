---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tests/statistical/test_strategy_robustness.py
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

#codebase

Tu es un Senior Engineer spécialisé en systèmes de trading algorithmique.  
Ton objectif : **implémenter des tests de robustesse statistique** pour EDGECORE, garantissant que la stratégie reste stable face aux variations de paramètres, aux périodes et à l’overfitting OOS/IS.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE
─────────────────────────────────────────────
1. Vérifie si le fichier existe déjà :  
   `tests/statistical/test_strategy_robustness.py`

2. Si trouvé, affiche :
   "⚠️ Test statistique existant détecté :
    Fichier : tests/statistical/test_strategy_robustness.py
    Date    : [date modification]

    [NOUVEAU]  → écraser et réimplémenter
    [MÀJOUR]   → compléter tests manquants
    [ANNULER]  → abandonner"

3. Si absent → démarrer directement :
   "✅ Aucun test statistique détecté. Démarrage..."

─────────────────────────────────────────────
RÈGLES ABSOLUES
─────────────────────────────────────────────
- Aucun hardcode → toujours utiliser `get_settings()`
- Tests déterministes (seed fixe si stochastique)
- Marker pytest : `@pytest.mark.slow` pour chaque test
- Ruff OK · Pyright OK après implémentation

─────────────────────────────────────────────
ÉTAPE 1 — CRÉER tests/statistical/test_strategy_robustness.py
─────────────────────────────────────────────
1.1 Stabilité Sharpe (sensibilité paramètres)
    - Variation `entry_z` ±20% autour de la valeur config
    - Variation `half-life` ±50% autour de la valeur config
    - Assertion : Sharpe > seuil minimal pour chaque variation
    - Assertion : max drawdown ≤ `get_settings().risk.max_drawdown_pct`

1.2 Robustesse temporelle
    - Tester ≥ 3 périodes distinctes : bull / bear / crash
    - Assertion : Sharpe > seuil minimal sur chaque période

1.3 Overfitting check (IS vs OOS)
    - Calculer Sharpe IS (entraînement)
    - Calculer Sharpe OOS (hors-échantillon)
    - Assertion : decay = (Sharpe_IS - Sharpe_OOS) / Sharpe_IS ≤ 40%
    - Decay > 40% → suspicion d'overfitting → 🔴

─────────────────────────────────────────────
ÉTAPE 2 — MAKEFILE
─────────────────────────────────────────────
Ajouter dans le Makefile :

      test-statistical:
          pytest tests/statistical/ -q -m slow

      qa:
          + make test-statistical

─────────────────────────────────────────────
VALIDATION OBLIGATOIRE
─────────────────────────────────────────────
- `pytest tests/statistical/ -q -m slow` → passage complet
- `ruff check .` → 0 erreur
- `pyright` → 0 erreur
- Aucun seuil hardcodé dans le fichier

Confirmation finale dans le chat :  
"✅ tests/statistical/test_strategy_robustness.py créé · 3 blocs implémentés"
