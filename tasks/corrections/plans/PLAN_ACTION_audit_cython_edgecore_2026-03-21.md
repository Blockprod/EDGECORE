# PLAN D'ACTION — EDGECORE — 2026-03-21
**Création :** 2026-03-22 à 00:00  
Sources : `tasks/audits/audit_cython_edgecore.md`
Total : 🔴 0 · 🟠 3 · 🟡 6 · Effort estimé : ~1 jour

---

## PHASE 1 — CRITIQUES 🔴

_Aucune finding critique._

---

## PHASE 2 — MAJEURES 🟠

### [C-01] Épingler Cython dans requirements.txt et pyproject.toml

Fichier : `requirements.txt`, `pyproject.toml`, `setup.py:47`
Problème : Cython n'est pas déclaré dans `requirements.txt` ni dans `pyproject.toml`. `setup.py` déclare `Cython>=0.29` — trop permissif alors que la version installée est 3.2.4 et que les directives `language_level=3`, `boundscheck=False`, `cdivision=True` nécessitent Cython 3.x. Une installation fraîche (`pip install .`) pourrait résoudre Cython 0.x incompatible et faire échouer silencieusement la compilation.
Correction :
  1. Ajouter `Cython==3.0.12` (ou `Cython>=3.0,<4.0`) dans `requirements.txt`
  2. Ajouter la même contrainte dans `pyproject.toml` sous `[project] / dependencies` ou `[build-system] / requires`
  3. Dans `setup.py`, modifier `install_requires` : `"Cython>=3.0,<4.0"` au lieu de `"Cython>=0.29"`
  4. Dans `.github/workflows/ci.yml`, épingler `pip install "cython>=3.0,<4.0" numpy` (step lignes 49-52)
Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2659+ passed
  ```
Dépend de : Aucune
Statut : ⏳

---

### [C-02] Ajouter des tests directs pour `brownian_bridge_batch_fast`

Fichier : `tests/models/056_test_cython_module.py`
Problème : `brownian_bridge_batch_fast` n'a aucun test unitaire direct. C'est le hot path de la génération intraday synthétique (utilisé dans `data/intraday_loader.py`). Une régression de forme de sortie, de dtype ou de valeur serait silencieuse.
Correction : Ajouter dans `tests/models/056_test_cython_module.py` une classe `TestBrownianBridgeBatchFast` couvrant :
  - Cas nominal : shape sortie `= (n_days-1)*bars_per_day × n_sym`
  - Valeurs continues (pas de NaN, pas d'inf)
  - Cohérence avec implémentation Python pure (résultat proche, même forme)
  - Cas limite : `n_days=2` (minimum valide)
  - Cohérence du skip si `ImportError` (`pytest.skip`)
Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/models/056_test_cython_module.py -x -q
  # Attendu : tous les tests passent dont TestBrownianBridgeBatchFast
  ```
Dépend de : Aucune
Statut : ⏳

---

### [C-03] Ajouter des tests directs pour `compute_zscore_last_fast`

Fichier : `tests/models/056_test_cython_module.py`
Problème : `compute_zscore_last_fast` n'a aucun test unitaire direct. C'est un hot path appelé dans la boucle de simulation (`backtests/strategy_simulator.py:460,968`). Une régression du clamping ou de la formule de z-score passerait inaperçue.
Correction : Ajouter dans `tests/models/056_test_cython_module.py` une classe `TestComputeZscoreLastFast` couvrant :
  - Cas nominal : z-score proche de la valeur attendue (spread synthétique connu)
  - Clamping inférieur : `z < -6.0` → retourne `-6.0`
  - Clamping supérieur : `z > 6.0` → retourne `6.0`
  - Cas limite `lookback > len(spread)` → retourne `0.0`
  - Cohérence avec implémentation Python pure (`np.std` + `np.mean`)
  - Skip si `ImportError`
Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/models/056_test_cython_module.py -x -q
  # Attendu : tous les tests passent dont TestComputeZscoreLastFast
  ```
Dépend de : Aucune
Statut : ⏳

---

## PHASE 3 — MINEURES 🟡

### [C-04] Exclure `cointegration_fast.c` du dépôt git

Fichier : `.gitignore`, `models/cointegration_fast.c`
Problème : `cointegration_fast.c` (fichier transpilé Cython, ~170 Ko) est commité dans le repo et absent du `.gitignore`. Il peut diverger du `.pyx` et pollue l'historique.
Correction :
  1. Ajouter `*.c` (ou `models/*.c`) dans `.gitignore`
  2. Retirer le fichier du suivi git : `git rm --cached models/cointegration_fast.c`
  3. Committer la suppression du tracking
Validation :
  ```powershell
  git status
  # Attendu : models/cointegration_fast.c apparaît dans .gitignore (untracked)
  ```
Dépend de : Aucune
Statut : ⏳

---

### [C-05] Tester les cas limites des fonctions Cython

Fichier : `tests/models/056_test_cython_module.py`
Problème : Plusieurs cas dégénérés définis dans le `.pyx` ne sont pas testés : `n < 20` pour `engle_granger_fast`, présence de NaN dans les séries d'entrée, `n < 3` → `-1` pour `half_life_fast`, `lookback > n` → `0.0` pour `compute_zscore_last_fast`, clamping `[-6, 6]`.
Correction : Ajouter une classe `TestCythonEdgeCases` dans `tests/models/056_test_cython_module.py` couvrant :
  - `engle_granger_fast(y, x)` avec `len(y) == 15` → clé `"error"` dans le résultat
  - `engle_granger_fast(y_nan, x)` avec NaN → clé `"error"` dans le résultat
  - `half_life_fast(spread_2)` avec `len(spread) == 2` → `-1`
Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/models/056_test_cython_module.py -x -q
  # Attendu : tous les tests passent dont TestCythonEdgeCases
  ```
Dépend de : C-02, C-03 (grouper dans le même fichier)
Statut : ⏳

---

### [C-06] Corriger la documentation `agents/dev_engineer.md`

Fichier : `agents/dev_engineer.md:49`
Problème : La documentation référence `from models.cointegration_fast import engle_granger_test_fast` — cette fonction n'existe pas dans le `.pyx`. Le nom réel est `engle_granger_fast`. Provoquerait un `ImportError` pour tout développeur suivant cet exemple.
Correction : Remplacer `engle_granger_test_fast` par `engle_granger_fast` à la ligne 49.
Validation :
  ```powershell
  Select-String -Path "agents/dev_engineer.md" -Pattern "engle_granger"
  # Attendu : engle_granger_fast uniquement (pas engle_granger_test_fast)
  ```
Dépend de : Aucune
Statut : ⏳

---

### [C-07] Supprimer l'alias `CPP_COINTEGRATION_AVAILABLE` (dead code)

Fichier : `models/cointegration.py:36`
Problème : `CPP_COINTEGRATION_AVAILABLE = CYTHON_COINTEGRATION_AVAILABLE` est un alias legacy sans consommateur Python de production. Il est trompeur (suggère l'existence d'une version C++ qui n'existe plus).
Correction : Supprimer la ligne 36 de `models/cointegration.py`. Vérifier qu'aucun import Python de production ne le référence (grep confirmé : aucun consommateur actif).
Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2659+ passed
  Select-String -Path "models/cointegration.py" -Pattern "CPP_COINTEGRATION"
  # Attendu : 0 résultat
  ```
Dépend de : Aucune
Statut : ⏳

---

### [C-08] Nettoyer les imports `# noqa: F401` inutilisés dans la façade

Fichier : `models/cointegration.py:13–22`
Problème : Trois symboles importés dans la façade avec `# noqa: F401` et `# pyright: ignore` ne sont jamais utilisés dans ce fichier : `_brownian_bridge_batch_fast`, `_compute_zscore_last_fast`, `_half_life_fast`. Les consommateurs importent directement depuis le `.pyx`. Ces imports trompeurs rompent la sémantique de la façade.
Correction : Deux options — choisir l'une :
  - **Option A (propre)** : supprimer ces 3 lignes d'import de `models/cointegration.py`. Les consommateurs (`spread.py`, `intraday_loader.py`, `strategy_simulator.py`) ayant leurs propres imports directs, aucune régression attendue.
  - **Option B (façade complète)** : conserver les imports ET créer des fonctions wrapper publiques dans `cointegration.py` pour centraliser l'accès (plus lourd, à réserver à une refactorisation ultérieure).
  
  Recommandé : **Option A** — supprimer les 3 imports inutilisés.
Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2659+ passed
  venv\Scripts\python.exe -m ruff check models/cointegration.py
  # Attendu : 0 erreur F401
  ```
Dépend de : Aucune
Statut : ⏳

---

### [C-09] Documenter le bypass de façade dans `data/intraday_loader.py`

Fichier : `data/intraday_loader.py:250`
Problème : `data/intraday_loader.py` importe `brownian_bridge_batch_fast` directement depuis `models.cointegration_fast` au lieu de passer par la façade `models.cointegration`. Le fallback local est correct mais la convention architecturale est rompue (deux chemins d'import différents pour la même fonction selon le consommateur).
Correction : Ajouter un commentaire documentant l'import direct intentionnel, OU rediriger l'import via la façade si `brownian_bridge_batch_fast` y est exposé (cf. C-08 Option B). Vu la décision prise en C-08 (Option A), maintenir l'import direct et ajouter un commentaire `# Import direct intentionnel — façade ne réexpose pas brownian_bridge_batch_fast`.
Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2659+ passed
  ```
Dépend de : C-08
Statut : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
C-01 → C-04   # Indépendants — lancer en premier (build + git)
C-06, C-07    # Documentation et dead code — sans risque
C-02, C-03    # Tests brownian + zscore — base pour C-05
C-05          # Tests edge cases — dépend de C-02/C-03 (même fichier)
C-08          # Nettoyage façade
C-09          # Dépend de la décision C-08

Ordre recommandé : C-01 → C-04 → C-06 → C-07 → C-02 → C-03 → C-05 → C-08 → C-09
```

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `pytest tests/` : 100% pass (2659+)
- [ ] `mypy risk/ risk_engine/ execution/` : exit 0
- [ ] `ruff check .` : 0 erreurs
- [ ] Zéro credential IBKR dans les logs
- [ ] Kill-switch persisté au redémarrage
- [ ] Risk tiers cohérents (`_assert_risk_tier_coherence` OK)
- [ ] `EDGECORE_ENV=prod` dans Dockerfile (pas `"production"`)
- [ ] Paper trading validé avant live
- [ ] Cython épinglé `>=3.0,<4.0` dans `requirements.txt` ET `pyproject.toml`
- [ ] `brownian_bridge_batch_fast` et `compute_zscore_last_fast` couverts en tests

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Épingler Cython dans requirements.txt et pyproject.toml | 🟠 | `requirements.txt`, `pyproject.toml`, `setup.py` | 15 min | ⏳ | |
| C-02 | Tests directs `brownian_bridge_batch_fast` | 🟠 | `tests/models/056_test_cython_module.py` | 1-2 h | ⏳ | |
| C-03 | Tests directs `compute_zscore_last_fast` | 🟠 | `tests/models/056_test_cython_module.py` | 1-2 h | ⏳ | |
| C-04 | Exclure `cointegration_fast.c` du dépôt | 🟡 | `.gitignore`, `models/cointegration_fast.c` | 5 min | ⏳ | |
| C-05 | Tests cas limites (n<20, NaN, n<3, lookback>n) | 🟡 | `tests/models/056_test_cython_module.py` | 1 h | ⏳ | |
| C-06 | Corriger `engle_granger_test_fast` → `engle_granger_fast` dans doc | 🟡 | `agents/dev_engineer.md:49` | 5 min | ⏳ | |
| C-07 | Supprimer `CPP_COINTEGRATION_AVAILABLE` (dead code) | 🟡 | `models/cointegration.py:36` | 5 min | ⏳ | |
| C-08 | Nettoyer imports `# noqa: F401` inutilisés dans la façade | 🟡 | `models/cointegration.py:13–22` | 15 min | ⏳ | |
| C-09 | Documenter bypass de façade dans `intraday_loader.py` | 🟡 | `data/intraday_loader.py:250` | 15 min | ⏳ | |
