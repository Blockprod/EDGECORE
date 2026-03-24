# EDGECORE — Leçons apprises
**Création :** 2026-03-20 à 00:32   (Self-Improvement Loop)

> Lire ce fichier au début de chaque session.
> Mettre à jour après toute correction de l'utilisateur.
> Chaque entrée = un pattern d'erreur à ne plus reproduire.

---

## L-01 · Patcher la mauvaise classe IBKR dans les tests

**Contexte** : Test de `DataLoader.load_ibkr_data` patchait `IBKRExecutionEngine`.
**Erreur** : `DataLoader` utilise `IBGatewaySync` (sync/ibapi) — le mock manquait la cible → connexion IBKR réelle tentée → `RuntimeError: No data`.
**Règle** : `IBGatewaySync` est la classe sync (ibapi, `ibkr_sync_gateway.py`). `IBKRExecutionEngine` est la classe async (ib_insync, `ibkr_engine.py`). Toujours vérifier quelle classe est importée dans le module testé avant de patcher.
**Ref** : `tests/data/006_test_data.py` — commit `e39f8d0`

---

## L-02 · Chemin relatif dans les tests pytest → cassé en CI

**Contexte** : `test_cython_pyd_file_exists` utilisait `Path("models")` (relatif au cwd).
**Erreur** : En CI, le cwd peut différer du répertoire racine du projet → fichier introuvable même si compilé.
**Règle** : Toujours utiliser `Path(__file__).parent.parent.parent / "models"` (chemin absolu depuis `__file__`) dans les tests. Ne jamais assumer le cwd dans pytest.
**Ref** : `tests/models/056_test_cython_module.py` — commit `e39f8d0`

---

## L-03 · Cython `.pyd` (Windows) vs `.so` (Linux) en CI

**Contexte** : Test glob uniquement `*.pyd` → introuvable sur `ubuntu-latest`.
**Erreur** : CI Linux compile en `.so` — le test échouait systématiquement sur GitHub Actions.
**Règle** : Toujours tester les deux extensions : `list(models_dir.glob("*.pyd")) + list(models_dir.glob("*.so"))`. Si aucune trouvée et `CYTHON_AVAILABLE=False` → `pytest.skip()` (pas `assert False`).
**Ref** : `tests/models/056_test_cython_module.py` — commit `e39f8d0`

---

## L-04 · Cython non installé en CI → build_ext échoue

**Contexte** : Step CI `python setup.py build_ext --inplace` lancé sans installer Cython.
**Erreur** : `ModuleNotFoundError: No module named 'Cython'` — step en échec immédiat.
**Règle** : Toujours exécuter `pip install cython numpy` AVANT `python setup.py build_ext --inplace` dans le CI. Cython n'est pas dans `requirements.txt` (dépendance de build seulement).
**Ref** : `.github/workflows/ci.yml` — commit `fadaa83`

---

## L-05 · f-string sans placeholder → ruff F541

**Contexte** : `f"Cython not compiled — ..."` sans variable `{}` dedans.
**Erreur** : ruff signale F541 (f-string inutile) et fait échouer le step Lint en CI.
**Règle** : Ne jamais préfixer `f` une chaîne qui ne contient pas de `{variable}`. Utiliser des guillemets simples ou doubles ordinaires.
**Ref** : `tests/models/056_test_cython_module.py` — commit `91433f5`

---

## L-06 · `EDGECORE_ENV=production` invalide → fallback silencieux sur dev

**Contexte** : Dockerfile/docker-compose utilisait `EDGECORE_ENV=production`.
**Erreur** : La valeur `production` n'existe pas — le Settings singleton tombe silencieusement sur `dev.yaml`, chargeant une config de développement en production.
**Règle** : Les valeurs valides sont `dev`, `test`, `prod` (source : `config/settings.py`). Vérifier `EDGECORE_ENV` dans Dockerfile et docker-compose avant tout déploiement.
**Ref** : `.github/copilot-instructions.md` — issue B5-01

---

## L-07 · Risk tiers : ne jamais modifier l'ordre T1 ≤ T2 ≤ T3

**Contexte** : Modification d'un seuil de drawdown dans `RiskConfig` ou `KillSwitchConfig`.
**Erreur** : Si T1 > T2 ou T2 > T3, `_assert_risk_tier_coherence()` lève une exception au démarrage → système ne démarre pas.
**Règle** : T1 (10%) ≤ T2 (15%) ≤ T3 (20%). Toujours ajuster les trois ensemble et relancer `venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"`.
**Ref** : `.github/copilot-instructions.md` — risk tiers section

---

## L-08 · Annotations mypy : `any` (builtin) vs `Any` (typing)

**Contexte** : Annotation de type écrite `any` au lieu de `Any`.
**Erreur** : mypy refuse `any` comme type — c'est la fonction builtin Python, pas le type `typing.Any`.
**Règle** : Toujours `from typing import Any` et utiliser `Any` (majuscule). `any(iterable)` est une fonction, pas un type.
**Ref** : `execution/position_stops.py` — commit `e39f8d0`

---

## L-09 · TypedDict : assigner `dict[str, object]` sans `cast`

**Contexte** : `default_factory=lambda: {...}` pour un champ TypedDict → mypy `Incompatible types`.
**Erreur** : mypy infère `dict[str, object]` alors que le champ attend un TypedDict précis.
**Règle** : Toujours wrapper avec `cast(MonTypedDict, {...})`. Ajouter `from typing import cast` en imports.
**Ref** : `execution/order_book.py`, `execution/paper_execution.py` — commit `e39f8d0`

---

## L-10 · Appel IBKR sans rate limiter → déconnexion TWS

**Contexte** : Ajout d'un appel `reqHistoricalData` direct sans passer par le rate limiter.
**Erreur** : TWS déconnecte automatiquement au-delà de 50 req/s — perte de session.
**Règle** : Toujours appeler `_ibkr_rate_limiter.acquire()` avant tout appel API IBKR. Hard cap : 50 req/s. Limite sustained : 45 req/s (burst 10).
**Ref** : `.github/copilot-instructions.md` — IBKR rate limit section

---

## L-11 · fix(lessons): force utf-8 stdout via reconfigure() — fixes cp1252 UnicodeEncodeError on Windows [DRAFT — À COMPLÉTER]

**Contexte** : Commit `c029cb8` : fix(lessons): force utf-8 stdout via reconfigure() — fixes cp1252 UnicodeEncodeError on Windows. Fichiers : scripts/update_lessons.py
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `scripts/update_lessons.py` — commit `c029cb8` (2026-03-20)

---

## L-12 · audit IA/ML: 10 corrections C-01-C-10 (2681 tests passing) [DRAFT — À COMPLÉTER]

**Contexte** : Commit `4d5459e` : audit IA/ML: 10 corrections C-01-C-10 (2681 tests passing). Fichiers : backtester/oos.py, backtester/runner.py
**Erreur** : datetime.utcnow() utilisé au lieu de datetime.now(timezone.utc)
**Règle** : Toujours utiliser datetime.now(timezone.utc). datetime.utcnow() est deprecated depuis Python 3.12.
**Ref** : `backtester/oos.py`, `backtester/runner.py`, `backtester/walk_forward.py` — commit `4d5459e` (2026-03-22)

---

## L-13 · fix(ruff): UP017 timezone.utc -> UTC, B905 zip strict=False [DRAFT — À COMPLÉTER]

**Contexte** : Commit `52e92ab` : fix(ruff): UP017 timezone.utc -> UTC, B905 zip strict=False. Fichiers : models/model_retraining.py, pair_selection/discovery.py
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `models/model_retraining.py`, `pair_selection/discovery.py` — commit `52e92ab` (2026-03-22)

---

## L-14 · perf(latence): C-01 to C-15 — audit latence complet (2787 tests) [DRAFT — À COMPLÉTER]

**Contexte** : Commit `ee34f5c` : perf(latence): C-01 to C-15 — audit latence complet (2787 tests). Fichiers : backtester/__init__.py, backtester/runner.py
**Erreur** : datetime.utcnow() utilisé au lieu de datetime.now(timezone.utc)
**Règle** : Toujours utiliser datetime.now(timezone.utc). datetime.utcnow() est deprecated depuis Python 3.12.
**Ref** : `backtester/__init__.py`, `backtester/runner.py`, `backtester/walk_forward.py` — commit `ee34f5c` (2026-03-23)

---

## L-15 · fix(audit#12): Trade Journal — 9 corrections C-01→C-09 [DRAFT — À COMPLÉTER]

**Contexte** : Commit `f29e6af` : fix(audit#12): Trade Journal — 9 corrections C-01→C-09. Fichiers : backtests/strategy_simulator.py, execution/ibkr_sync_gateway.py
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `backtests/strategy_simulator.py`, `execution/ibkr_sync_gateway.py`, `live_trading/runner.py` — commit `f29e6af` (2026-03-24)

---
