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

## L-16 · fix(ci): ignore CVE-2026-4539 (pygments, no fix available) in pip-audit [DRAFT — À COMPLÉTER]

**Contexte** : Commit `7af6ea6` : fix(ci): ignore CVE-2026-4539 (pygments, no fix available) in pip-audit. Fichiers : .github/workflows/ci.yml
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `.github/workflows/ci.yml` — commit `7af6ea6` (2026-03-24)

---

## L-18 · RÈGLE D'OR — Un nouvel audit écrase l'ancien (même type)

**Contexte** : Deux fichiers plan d'action du même type coexistaient dans `tasks/corrections/plans/` après régénération.
**Erreur** : `PLAN_ACTION_audit_strategic_edgecore_2026-03-22.md` et `_2026-03-25.md` présents simultanément — l'agent lisait potentiellement l'ancien.
**Règle** : Toujours supprimer le plan précédent du même type avant (ou après) création du nouveau. Un seul plan par type d'audit doit exister dans `tasks/corrections/plans/`. Le fichier le plus récent fait foi.
**Règle (template)** : Tout fichier `tasks/` (plans, audits, prompts) doit commencer par le frontmatter YAML obligatoire des copilot-instructions. Champs requis : `modele`, `mode`, `contexte`, `produit`, `derniere_revision`, `creation` (format `YYYY-MM-DD à HH:MM`). Aucun champ supplémentaire non prévu par le template (`source_audit:`, etc.). Vérifier systématiquement à la création.
**Ref** : `tasks/corrections/plans/` — 2026-03-25

---

## L-17 · fix(pipeline): C01-C13 — align config→backtest→live costs, risk gate, momentum, combiner weights [DRAFT — À COMPLÉTER]

**Contexte** : Commit `88284bb` : fix(pipeline): C01-C13 — align config→backtest→live costs, risk gate, momentum, combiner weights. Fichiers : backtests/strategy_simulator.py, config/settings.py
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `backtests/strategy_simulator.py`, `config/settings.py`, `execution_engine/router.py` — commit `88284bb` (2026-03-25)

---

## L-19 · fix(ci): skip test_from_htb_csv_with_real_seed_file si data/htb_rates.csv absent (gitignored) [DRAFT — À COMPLÉTER]

**Contexte** : Commit `2a6d635` : fix(ci): skip test_from_htb_csv_with_real_seed_file si data/htb_rates.csv absent (gitignored). Fichiers : tests/backtests/test_cost_model_extended.py
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `tests/backtests/test_cost_model_extended.py` — commit `2a6d635` (2026-03-25)

---

## L-20 · QA finale EDGECORE : P3/P4 fixes validés, 12/12 checks passés, READY pour merge. (voir FINAL_QA_result.md) [DRAFT — À COMPLÉTER]

**Contexte** : Commit `9f182e4` : QA finale EDGECORE : P3/P4 fixes validés, 12/12 checks passés, READY pour merge. (voir FINAL_QA_result.md). Fichiers : backtests/runner.py, backtests/simulation_loop.py
**Erreur** : print() dans du code de production
**Règle** : Utiliser structlog.get_logger(__name__) partout. print() interdit hors scripts/, examples/, research/.
**Ref** : `backtests/runner.py`, `backtests/simulation_loop.py`, `backtests/strategy_simulator.py` — commit `9f182e4` (2026-03-26)

---

## 2026-03-27 — Corrections Best Practices AI
- Ce qui a fonctionné :
  - Ajout d’une infrastructure de hooks AI (main.py) et d’une mémoire contextuelle persistante (common/context_memory.py) accessible à tous les agents/hooks.
  - Mise en place d’un versioning automatique des prompts (PROMPTS_CHANGELOG.md) et d’une checklist RGPD/sécurité dans les prompts critiques.
  - Intégration d’une étape CI pour la traçabilité des modifications de prompts.
  - Validation globale : 2800 tests passés, aucune régression.
- Ce qui a bloqué :
  - Bloc context initialisé hors fonction dans main.py, provoquant des erreurs d’import lors des tests (résolu en déplaçant tout dans main()).
- À retenir pour la prochaine fois :
  - Ne jamais initialiser de variables dépendant d’arguments CLI ou d’objets runtime (args, settings, alerters) au niveau module.
  - Toujours garantir que le code d’initialisation contextuelle et hooks AI est strictement dans main() ou protégé par if __name__ == "__main__".
  - Versionner systématiquement tout prompt d’audit et vérifier la checklist RGPD/sécurité à chaque ajout.
- Issues closes : [BP-01], [BP-02], [BP-03], [BP-04], [BP-05]

## L-21 · Nettoyage imports inutiles + correction style stress_testing.py ; doc activation venv PowerShell [DRAFT — À COMPLÉTER]

**Contexte** : Commit `ee899c0` : Nettoyage imports inutiles + correction style stress_testing.py ; doc activation venv PowerShell. Fichiers : backtests/stress_testing.py, common/context_memory.py
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `backtests/stress_testing.py`, `common/context_memory.py`, `main.py` — commit `ee899c0` (2026-03-27)

---

## 2026-03-27 — Corrections Process & Documentation
- Ce qui a fonctionné : Centralisation de la documentation technique, création d’un index, checklist RGPD/sécurité, versioning des runbooks/prompts, début de centralisation monitoring.
- Ce qui a bloqué : Documentation technique initialement dispersée, nécessité de créer plusieurs nouveaux fichiers pour la centralisation.
- À retenir pour la prochaine fois : Prévoir un dossier OPERATIONS dès la conception, versionner explicitement tous les runbooks/prompts critiques, maintenir une checklist RGPD/sécurité à jour.
- Issues closes : [audit_process_doc_edgecore.md — 🔴 1 · 🟠 3]

## L-22 · fix(mypy): add type annotation + get_average_correlation() — CI check passes [DRAFT — À COMPLÉTER]

**Contexte** : Commit `0f58ad4` : fix(mypy): add type annotation + get_average_correlation() — CI check passes. Fichiers : monitoring/correlation_monitor.py, risk_engine/portfolio_risk.py
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `monitoring/correlation_monitor.py`, `risk_engine/portfolio_risk.py` — commit `0f58ad4` (2026-04-04)

---

## L-23 · fix(ci): move bt_v36 baseline out of LFS — tests/regression/fixtures/ [DRAFT — À COMPLÉTER]

**Contexte** : Commit `3194dec` : fix(ci): move bt_v36 baseline out of LFS — tests/regression/fixtures/. Fichiers : tests/regression/test_equity_curve_regression.py
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `tests/regression/test_equity_curve_regression.py` — commit `3194dec` (2026-04-04)

---

## L-24 · C-04/C-07/C-08/C-09/C-11/C-12/C-13 + PROBLEMS 0: audit #18 sprint 2 complete [DRAFT — À COMPLÉTER]

**Contexte** : Commit `caccc81` : C-04/C-07/C-08/C-09/C-11/C-12/C-13 + PROBLEMS 0: audit #18 sprint 2 complete. Fichiers : backtester/oos.py, backtests/strategy_simulator.py
**Erreur** : print() dans du code de production
**Règle** : Utiliser structlog.get_logger(__name__) partout. print() interdit hors scripts/, examples/, research/.
**Ref** : `backtester/oos.py`, `backtests/strategy_simulator.py`, `common/secrets.py` — commit `caccc81` (2026-04-05)

---

## L-25 · fix(ruff): B009/B010 setattr/getattr -> cast Any + direct access [DRAFT — À COMPLÉTER]

**Contexte** : Commit `8eae0c3` : fix(ruff): B009/B010 setattr/getattr -> cast Any + direct access. Fichiers : monitoring/cache.py, scripts/scheduler.py
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `monitoring/cache.py`, `scripts/scheduler.py` — commit `8eae0c3` (2026-04-05)

---

## L-26 · feat: P-01/P-02/P-04 + README redesign [DRAFT — À COMPLÉTER]

**Contexte** : Commit `a4f5bca` : feat: P-01/P-02/P-04 + README redesign. Fichiers : backtests/event_driven.py, backtests/runner.py
**Erreur** : print() dans du code de production
**Règle** : Utiliser structlog.get_logger(__name__) partout. print() interdit hors scripts/, examples/, research/.
**Ref** : `backtests/event_driven.py`, `backtests/runner.py`, `backtests/strategy_simulator.py` — commit `a4f5bca` (2026-04-05)

---

## L-27 · test: remove 50 duplicate tests + narrow CI coverage scope [DRAFT — À COMPLÉTER]

**Contexte** : Commit `4374abe` : test: remove 50 duplicate tests + narrow CI coverage scope. Fichiers : tests/test_order_lifecycle.py, tests/test_walk_forward_integration.py
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `tests/test_order_lifecycle.py`, `tests/test_walk_forward_integration.py` — commit `4374abe` (2026-04-05)

---

## L-28 · fix(ci): remove lfs-migration-preview trigger + resolve merge conflict markers [DRAFT — À COMPLÉTER]

**Contexte** : Commit `57f0083` : fix(ci): remove lfs-migration-preview trigger + resolve merge conflict markers. Fichiers : .github/workflows/ci.yml
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `.github/workflows/ci.yml` — commit `57f0083` (2026-04-05)

---

## L-29 · cert: CERT-01 to CERT-10 — 9/10 corrections appliquees, 2742 tests verts [DRAFT — À COMPLÉTER]

**Contexte** : Commit `cd3f7c7` : cert: CERT-01 to CERT-10 — 9/10 corrections appliquees, 2742 tests verts. Fichiers : backtests/strategy_simulator.py, data/loader.py
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `backtests/strategy_simulator.py`, `data/loader.py`, `live_trading/runner.py` — commit `cd3f7c7` (2026-04-05)

---

## L-30 · ci: fix trufflehog base/head — use event.before/after instead of branch name [DRAFT — À COMPLÉTER]

**Contexte** : Commit `8428507` : ci: fix trufflehog base/head — use event.before/after instead of branch name. Fichiers : .github/workflows/main.yml
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `.github/workflows/main.yml` — commit `8428507` (2026-04-06)

---

## L-31 · fix(pyright): 0 errors 0 warnings — cast pandas bool-index returns + fix DatetimeIndex.normalize stubs gap [DRAFT — À COMPLÉTER]

**Contexte** : Commit `01319cc` : fix(pyright): 0 errors 0 warnings — cast pandas bool-index returns + fix DatetimeIndex.normalize stubs gap. Fichiers : backtests/runner.py, backtests/walk_forward.py
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `backtests/runner.py`, `backtests/walk_forward.py`, `data/corporate_actions.py` — commit `01319cc` (2026-04-06)

---

## L-32 · feat(gw): IB Gateway auto-launch + auto-login (win32gui coordinate approach) [DRAFT — À COMPLÉTER]

**Contexte** : Commit `9783dea` : feat(gw): IB Gateway auto-launch + auto-login (win32gui coordinate approach). Fichiers : config/settings.py, execution/gw_manager.py
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `config/settings.py`, `execution/gw_manager.py`, `live_trading/runner.py` — commit `9783dea` (2026-04-11)

---

## L-33 · feat: v63 Sweet Set CERT-03b PASS + launch infra (manage_task.bat) [DRAFT — À COMPLÉTER]

**Contexte** : Commit `064d76c` : feat: v63 Sweet Set CERT-03b PASS + launch infra (manage_task.bat). Fichiers : backtests/position_tracker.py, backtests/runner.py
**Erreur** : EDGECORE_ENV=production (valeur invalide) au lieu de prod
**Règle** : Les valeurs valides sont uniquement : dev, test, prod. La valeur 'production' tombe silencieusement sur dev.yaml.
**Ref** : `backtests/position_tracker.py`, `backtests/runner.py`, `backtests/sector_exposure_manager.py` — commit `064d76c` (2026-04-11)

---

## L-34 · fix: ruff I001 — add blank line between pytest and first-party import block [DRAFT — À COMPLÉTER]

**Contexte** : Commit `64dd28b` : fix: ruff I001 — add blank line between pytest and first-party import block. Fichiers : tests/execution/test_gw_manager_health.py
**Erreur** : [À COMPLÉTER — décrire le problème exact]
**Règle** : [À COMPLÉTER — décrire la règle à appliquer]
**Ref** : `tests/execution/test_gw_manager_health.py` — commit `64dd28b` (2026-04-11)

---
