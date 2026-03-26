---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: data/feature_store.py
derniere_revision: 2026-03-26
creation: 2026-03-26 à 00:00
---

#codebase

Tu es un Senior Engineer spécialisé en systèmes de trading algorithmique.  
Ton objectif : **implémenter un Feature Store versionné minimal et non intrusif** pour EDGECORE, **sans modifier le comportement des calculs existants**.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE
─────────────────────────────────────────────
1. Vérifie si le fichier existe déjà :  
   `data/feature_store.py`

2. Si trouvé, affiche :
   "⚠️ Feature Store existant détecté :
    Fichier : data/feature_store.py
    Date    : [date modification]

    [NOUVEAU]  → écraser et réimplémenter
    [MÀJOUR]   → compléter méthodes manquantes
    [ANNULER]  → abandonner"

3. Si absent → démarrer directement :
   "✅ Aucun Feature Store détecté. Démarrage..."

─────────────────────────────────────────────
RÈGLES ABSOLUES
─────────────────────────────────────────────
- Ne pas modifier la logique de calcul existante
- Ajouter uniquement un cache transparent
- Lire la config via `get_settings()`
- Ruff OK · Pyright OK après implémentation

─────────────────────────────────────────────
ÉTAPE 1 — CRÉER data/feature_store.py
─────────────────────────────────────────────
1.1 Implémenter la classe `FeatureStore` :
    - Clé de cache basée sur `(pair, période, version)`
    - Checksum de validation (hash des paramètres d'entrée)
    - Méthodes : `get(key)` → données ou None · `set(key, data)`
    - Stockage : `settings.paths.feature_store_dir`

1.2 Pattern obligatoire dans chaque injection :

      cached = store.get(key)
      if cached is not None:
          return cached
      result = compute(...)
      store.set(key, result)
      return result

─────────────────────────────────────────────
ÉTAPE 2 — INJECTION DANS LE PIPELINE
─────────────────────────────────────────────
Source : `models/spread.py` + `models/kalman_hedge.py`

2.1 Identifier les points de calcul coûteux :  
    - `models/spread.py` : calcul du spread (fichier:ligne)  
    - `models/kalman_hedge.py` : hedge ratio Kalman (fichier:ligne)

2.2 Injecter le pattern check → compute → write :  
    - Check cache AVANT le calcul  
    - Write cache APRÈS le return  
    - Ne pas modifier les signatures de fonction existantes

─────────────────────────────────────────────
ÉTAPE 3 — CONFIG ET GITIGNORE
─────────────────────────────────────────────
3.1 Ajouter dans `config/config.yaml` (section paths) :  

      feature_store_dir: data/feature_store/

3.2 Ajouter dans `.gitignore` :  

      data/feature_store/

─────────────────────────────────────────────
VALIDATION OBLIGATOIRE
─────────────────────────────────────────────
- Comportement identique avec ou sans cache  
- `ruff check .` → 0 erreur  
- `pyright` → 0 erreur  
- `pytest tests/ -q` → passage intégral des tests existants

Confirmation finale dans le chat :  
"✅ data/feature_store.py créé · cache injecté · .gitignore mis à jour"
