# PLAN D'ACTION POUR CORRECTION DES TESTS

## 1. Corriger les erreurs `NameError: name 'timezone' is not defined`

**Fichiers concernés :**
- `tests/backtests/027_test_backtest_realism.py`

**Étapes :**
- Ajouter en haut du fichier :
  ```python
  from datetime import timezone
  ```
- Vérifier que tous les appels à `datetime.now(timezone.utc)` utilisent bien l'import.

---

## 2. Corriger les erreurs `TypeError: can't compare/subtract offset-naive and offset-aware datetimes`

**Fichiers concernés :**
- `execution/order_lifecycle.py`
- `tests/execution/014_test_order_lifecycle.py`
- `tests/execution/test_order_lifecycle.py`

**Étapes :**
- S’assurer que toutes les variables datetime utilisées dans les comparaisons ou soustractions sont soit toutes “aware” (avec timezone), soit toutes “naive”.
- Pour chaque attribut comme `self.timeout_at`, `self.last_update`, etc. :
  - Lors de leur création, utiliser `datetime.now(timezone.utc)` ou ajouter `.replace(tzinfo=timezone.utc)` si nécessaire.
- Exemple :
  ```python
  # Pour rendre une datetime naive en aware
  dt_aware = dt_naive.replace(tzinfo=timezone.utc)
  ```
- Vérifier que toutes les initialisations et mises à jour de datetime dans les objets OrderLifecycle sont bien “aware”.

---

## 3. Corriger l’erreur de logique de risk check (test d’intégration)

**Fichier concerné :**
- `tests/integration/059_test_main_loop_integration.py`
- `risk/engine.py` (ou logique associée)

**Étapes :**
- Vérifier la logique de la fonction de risk check (ex : `can_enter_trade` ou équivalent).
- S’assurer que la vérification du levier et des positions respecte strictement les paramètres de configuration.
- Modifier le test pour qu’il vérifie correctement le rejet des positions surleviées.

---

## 4. Vérification finale

- Relancer tous les tests avec `pytest`.
- S’assurer qu’il n’y a plus d’erreurs liées à timezone, datetime ou risk check.
- Documenter les changements dans le changelog ou README.

---

## 5. Commandes à exécuter

```bash
# 1. Ajouter les imports manquants
# 2. Corriger les initialisations de datetime
# 3. Vérifier la logique risk check
python -m pytest tests/ -v
```

---

## 6. Points de vigilance

- Ne jamais mélanger datetime “naive” et “aware” dans les comparaisons ou calculs.
- Toujours utiliser `datetime.now(timezone.utc)` pour les timestamps.
- Vérifier la cohérence des tests d’intégration sur la logique de risk.

---

**Ce plan peut être suivi étape par étape pour garantir la correction complète des erreurs.**

---

## Note sur la correction récente des tests

- Contexte : un test unitaire modifiait globalement la fonction `get_settings` en
  remplaçant le binding importé dans `risk.engine`, ce qui a provoqué des
  effets de bord lors de l'exécution des tests d'intégration (config plus laxiste
  utilisée par d'autres modules).
- Correctif appliqué :
  - Le moteur de risque (`risk/engine.py`) utilise désormais `config.settings.get_settings()`
    via le module (`import config.settings as settings_mod`) au lieu d'importer
    la fonction par nom. Cela permet aux tests d'intercepter `get_settings`
    proprement avec `monkeypatch` sans muter des liaisons au niveau du module.
  - Le test `tests/risk/test_engine.py` a été ajusté pour patcher
    `config.settings.get_settings` via un fixture `autouse` utilisant `monkeypatch`.

- Recommandation :
  - Lorsqu'il faut contrôler la configuration dans des tests, utilisez
    `monkeypatch.setattr(config.settings, 'get_settings', ...)` ou une fixture
    dédiée plutôt que d'écraser des symboles importés dans d'autres modules.
  - Ajouter une courte note dans CONTRIBUTING ou TESTING.md pour expliquer
    cette bonne pratique afin d'éviter les fuites d'état entre tests.

---

Si vous voulez que je crée ou mette à jour un fichier `CONTRIBUTING.md` ou que je
crée un petit commit git avec ces changements, dites-le moi et je m'en
occupe.

---

Note: CI trigger: workflow run requested (2026-03-15)
