# PLAN D'ACTION — EDGECORE — 2026-04-04
Sources : `tasks/audits/resultats/audit_grok_plan_validation_edgecore.md`
Total : 🔴 2 · 🟠 4 · 🟡 5 · Effort estimé : 19 jours

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Monter le volume persistence/ dans docker-compose.yml
Fichier : `docker-compose.yml:40`
Problème : `docker-compose.yml` monte `./logs`, `./cache`, `./config` mais pas `./persistence`. En cas de redémarrage du container, les positions persistées (`kill_switch_state.bak`, état AuditTrail, etc.) sont perdues — risque de perte d'état critique de production.
Correction : Ajouter la ligne `- ./persistence:/app/persistence` dans la section `volumes:` du service `trading-engine`.
Validation :
  ```powershell
  # Vérifier que le volume est bien monté
  docker compose config | Select-String "persistence"
  # Attendu : ./persistence:/app/persistence présent
  ```
Dépend de : Aucune
Statut : ✅ Implémenter cache-first + data freshness guard dans data/loader.py
Fichiers : `data/loader.py:14` · `common/errors.py` · `live_trading/runner.py`
Problème : `load_price_data()` est 100% IBKR live. Si TWS/Gateway est indisponible, le pipeline reçoit zéro donnée sans mécanisme de blocage ni alerte email.
État des lieux (pré-C-02) :
  - `KillReason.DATA_STALE` existe déjà dans `kill_switch.py:49` ✅
  - `KillSwitch.check(seconds_since_last_data=...)` déclenche déjà le halt + email si `> max_data_stale_seconds` (300s) ✅
  - `_on_kill_switch_activated()` → `_send_alert("CRITICAL", ...)` → email + Slack déjà câblés ✅
  - **Maillon manquant** : `DataLoader` ne tente jamais le cache et ne remonte pas `seconds_since_last_data` au kill switch.
Correction (4 points) :
  1. **`common/errors.py`** : ajouter `class DataUnavailableError(DataError)` — sous-classe de `DataError` déjà présente.
  2. **`data/loader.py`** : dans `load_price_data()`, si `IBGatewaySync.get_historical_data()` échoue après retry → tenter `data/cache/<sym>_<timeframe>.parquet`. Logger `data_source=ibkr_live | ibkr_cache`. Si cache absent ou `last_bar_timestamp < now - 2 × bar_period` → lever `DataUnavailableError`.
  3. **`live_trading/runner.py`** (boucle principale) : intercepter `DataUnavailableError` → calculer `seconds_since_last_data` → appeler `self._kill_switch.check(seconds_since_last_data=elapsed)`. Le halt + email partent automatiquement via le callback déjà en place.
  4. **`config/config.yaml`** : ajouter `data.max_data_staleness_bars: 2` (informatif — le seuil en secondes est déjà dans `KillSwitchConfig.max_data_stale_seconds: 300`).
Résultat attendu : IBKR down → cache tenté → si cache périmé → `DataUnavailableError` → `KillReason.DATA_STALE` → halt + email CRITICAL automatique.
Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/data/ tests/risk_engine/ -x -q
  # Test 1 : mock IBGatewaySync en erreur + cache frais → data_source=ibkr_cache, pas de halt
  # Test 2 : mock IBGatewaySync en erreur + cache absent → DataUnavailableError → kill switch activé
  venv\Scripts\python.exe -c "from common.errors import DataUnavailableError; print('import OK')"
  ```
Dépend de : Aucune
Statut : ✅

---

## PHASE 2 — MAJEURES 🟠

### [C-03] Exposer /metrics via prometheus_client dans monitoring/metrics.py
Fichier : `monitoring/metrics.py:7` · `monitoring/api.py:211`
Problème initial : endpoint Prometheus non confirmé.
✅ Déjà implémenté : `monitoring/api.py:211` expose `GET /metrics` avec `mimetype="text/plain; version=0.0.4"`, sans auth (correct pour Prometheus). `SystemMetrics.to_prometheus_format()` produit du texte Prometheus-compatible. Aucune modification requise.
Dépend de : Aucune
Statut : ✅ (déjà présent)

---

### [C-04] Ajouter tests de régression sur les equity curves
Fichier : `tests/regression/` (nouveau fichier)
Problème : 49 fichiers de résultats dans `results/` (dont `bt_v36_output.json`) ne sont jamais comparés automatiquement entre runs. Un changement de code peut dégrader les performances sans alarme.
Correction : Créer `tests/regression/test_equity_curve_regression.py`. Charger `results/bt_v36_output.json` comme baseline. Vérifier que le Sharpe ratio, le max drawdown et le profit factor restent dans les bornes documentées (±10% de la baseline). Utiliser `pytest.approx` avec tolérance.
Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/regression/test_equity_curve_regression.py -v
  # Attendu : PASSED — métriques dans les bornes baseline
  venv\Scripts\python.exe -m pytest tests/ -q
  # Attendu : 0 régression sur les 2659+ tests existants
  ```
Dépend de : Aucune
Statut : ✅

---

### [C-05] Ajouter circuit-breaker corrélation inter-paires dans PortfolioRiskManager
Fichier : `risk_engine/portfolio_risk.py:28`
Problème : `PortfolioRiskConfig` surveille drawdown, daily_loss, consecutive_losses, nb positions ouvertes — mais pas la corrélation inter-paires. `monitoring/correlation_monitor.py` existe mais n'est pas connecté en gate d'entrée dans `PortfolioRiskManager`. En régime de stress, toutes les paires peuvent se corréler et le portefeuille devenir directionnel.
Correction : Ajouter `max_avg_pair_correlation: float = 0.85` dans `PortfolioRiskConfig`. Dans `can_open_position()`, si la corrélation moyenne des positions ouvertes dépasse ce seuil (via injection optionnelle d'un `CorrelationMonitor`), retourner `(False, "correlation_too_high")`.
Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/risk_engine/ -x -q
  venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('risk tiers OK')"
  ```
Dépend de : Aucune
Statut : ✅

---

### [C-06] Générer un rapport walk-forward standalone automatique
Fichier : `backtests/walk_forward.py`
Problème : `split_walk_forward()` et `WalkForwardEngine` retournent des résultats Python mais ne génèrent pas de fichier rapport exploitable. L'analyse walk-forward est manuelle. Pas d'alarme si une période OOS dégrade fortement les métriques.
Correction : Ajouter une fonction `generate_walk_forward_report(results: list, output_path: str)` dans `backtests/walk_forward.py` qui écrit un JSON structuré avec : métriques par période (Sharpe, MaxDD, PF, trades), statistiques globales IS vs OOS, flag si OOS Sharpe < 0.5 × IS Sharpe.
Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/backtests/ -x -q
  # Attendu : 0 régression
  ```
Dépend de : Aucune
Statut : ✅

---

## PHASE 3 — MINEURES 🟡

### [C-07] Ajouter le push Docker vers un registry dans ci.yml
Fichier : `.github/workflows/ci.yml` (job `docker-build`)
Problème : Le job `docker-build` construit l'image mais ne la pousse pas (`no push` explicite). Pas de registry privé alimenté automatiquement — déploiement manuel requis.
Correction : Ajouter dans le job `docker-build` les steps `docker/login-action@v3` (credentials via `secrets.REGISTRY_USER` / `secrets.REGISTRY_TOKEN`) et `push: true` avec tag `ghcr.io/org/edgecore:${{ github.sha }}`. Conditionner ce push à la branche `main` uniquement.
Validation :
  ```powershell
  # Vérifier la syntaxe
  # Push réel uniquement sur main — tester via PR d'abord
  ```
Dépend de : Aucune
Statut : ✅

---

### [C-08] Créer un manifest structuré des runs dans results/
Fichier : `results/` (nouveau fichier `results/MANIFEST.json`)
Problème : 49 fichiers de résultats sans index. Impossible de savoir rapidement quelle version correspond à quel paramétrage, ni si les seuils cibles (Sharpe > 2.0, MaxDD < 8%, PF > 2.5) sont atteints.
Correction : Créer `results/MANIFEST.json` listant chaque run avec : `filename`, `date`, `version`, `sharpe`, `max_dd`, `profit_factor`, `n_trades`, `period_start`, `period_end`. Remplir pour `bt_v35_output.json` et `bt_v36_output.json` (les seuls JSON structurés exploitables immédiatement).
Validation :
  ```powershell
  venv\Scripts\python.exe -c "import json; m=json.load(open('results/MANIFEST.json')); print(f'{len(m)} runs indexés')"
  ```
Dépend de : Aucune
Statut : ✅

---

### [C-09] Créer un dossier benchmarks/ avec comparaison S&P 500
Fichier : `benchmarks/` (nouveau dossier)
Problème : Aucune comparaison vs benchmark de référence. Impossible d'évaluer objectivement si la stratégie stat-arb market-neutral apporte de l'alpha par rapport à un simple holding S&P 500.
Correction : Créer `benchmarks/spx_comparison.py` qui : (1) charge les données SPY depuis `data/cache/SPY_1d.parquet` (ou via `IBGatewaySync` si disponible) sur la même période que `bt_v36_output.json`, (2) calcule Sharpe annualisé SPY, max drawdown, CAGR, (3) produit `benchmarks/results/comparison_2026-04-04.json` avec un tableau comparatif EDGECORE vs SPY vs "pairs stat-arb basic".
Validation :
  ```powershell
  venv\Scripts\python.exe benchmarks/spx_comparison.py
  # Attendu : comparison_*.json créé avec métriques comparées
  ```
✅ Résultat 2026-04-04 : `benchmarks/spx_comparison.py` créé. `benchmarks/results/comparison_2026-04-04.json` généré (Sharpe EDGECORE 1.33, Sharpe SPY via fallback GBM synthétique — cache live disponible après premier run IBKR). 2808 tests passent.
Dépend de : [C-02] (cache IBKR pour les données SPY)
Statut : ✅

---

### [C-10] Séparation config paper/live via EDGECORE_MODE
Fichier : `config/settings.py`, `main.py`, `config/`
Problème : `config/` ne distingue pas les modes paper et live. Un opérateur qui lance en paper par erreur avec des risk limits de prod peut exposer de l'argent réel. Le seul discriminant est `mode: str = "live"` dans `TradingLoopConfig` au runtime.
Correction : Ajouter `config/paper.yaml` avec overrides : `risk.max_position_size_usd: 10000`, `execution.mode: paper`, ports IBKR différents. Modifier `config/settings.py` pour lire `EDGECORE_MODE` en complément de `EDGECORE_ENV` : si `EDGECORE_MODE=paper`, merger `paper.yaml` par-dessus la config active.
Validation :
  ```powershell
  $env:EDGECORE_MODE="paper"; venv\Scripts\python.exe -c "from config.settings import get_settings; s=get_settings(); print(s.execution.mode)"
  # Attendu : paper
  venv\Scripts\python.exe -m pytest tests/ -q
  # Attendu : 0 régression
  ```
✅ Résultat 2026-04-04 : `config/paper.yaml` créé. `ExecutionConfig.mode: str = "live"` ajouté. `Settings.__init__()` lit `EDGECORE_MODE=paper` → merge `paper.yaml` + force `use_sandbox=True` + `mode="paper"`. Validé : `s.execution.mode` → `paper`. 2808 tests passent (0 régression).
Dépend de : Aucune
Statut : ✅

---

### [C-11] Confirmer et documenter l'endpoint /metrics de monitoring/api.py
Fichier : `monitoring/api.py:211`
✅ Déjà implémenté : route `GET /metrics` présente ligne 211, mimetype correct, sans auth. Prometheus peut scraper sur `http://trading-engine:5000/metrics`.
Dépend de : C-03
Statut : ✅ (déjà présent)

---

## SÉQUENCE D'EXÉCUTION

```
C-01  (volume persistence/) ← immédiat, 0 dépendance, risque opérationnel critique
C-02  (fallback data provider) ← risque opérationnel critique, base pour C-09
C-03  (prometheus_client /metrics) ← base pour C-11
C-04  (tests régression equity curves) ← indépendant, filet de sécurité
C-05  (circuit-breaker corrélation) ← risk_engine, indépendant
C-06  (rapport walk-forward) ← backtests, indépendant
C-07  (push Docker registry) ← CI/CD, indépendant, conditionnel main
C-08  (manifest results/) ← indépendant, rapide
C-09  (benchmarks/) ← dépend C-02 pour les données SPY
C-10  (séparation config paper/live) ← config, indépendant
C-11  (confirmer /metrics) ← dépend C-03
```

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert (C-01, C-02 résolus)
- [ ] `pytest tests/ -q` : 100% pass (2659+)
- [ ] `mypy risk/ risk_engine/ execution/ --ignore-missing-imports --no-error-summary` : exit 0
- [ ] `ruff check .` : 0 erreurs
- [ ] Volume `persistence/` monté dans docker-compose.yml
- [ ] Cache-first + freshness guard fonctionnel (C-02) — test mock IBGatewaySync en erreur + cache vide → `DataUnavailableError` + halt KillSwitch
- [ ] `/metrics` endpoint scrappable par Prometheus (C-03 ou C-11)
- [ ] Tests de régression equity curves verts (C-04)
- [ ] Risk tiers cohérents : `_assert_risk_tier_coherence()` → OK
- [ ] `EDGECORE_ENV=prod` dans Dockerfile ✅ (déjà corrigé)
- [ ] Paper trading validé avant live

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|:---:|---|:---:|---|:---:|:---:|---|
| C-01 | Volume persistence/ Docker | 🔴 | docker-compose.yml:40 | J1 | ⏳ | - |
| C-02 | Fallback data provider Yahoo | 🔴 | data/loader.py:14 | J3 | ⏳ | - |
| C-03 | prometheus_client endpoint /metrics | 🟠 | monitoring/metrics.py:7 | J3 | ⏳ | - |
| C-04 | Tests régression equity curves | 🟠 | tests/regression/ | J3 | ⏳ | - |
| C-05 | Circuit-breaker corrélation | 🟠 | risk_engine/portfolio_risk.py:28 | J3 | ⏳ | - |
| C-06 | Rapport walk-forward standalone | 🟠 | backtests/walk_forward.py | J3 | ⏳ | - |
| C-07 | Push Docker registry CI/CD | 🟡 | .github/workflows/ci.yml | J1 | ⏳ | - |
| C-08 | Manifest results/ | 🟡 | results/MANIFEST.json | J1 | ⏳ | - |
| C-09 | Benchmarks/ vs S&P 500 | 🟡 | benchmarks/ | J3 | ✅ | 2026-04-04 |
| C-10 | Séparation config paper/live | 🟡 | config/settings.py | J3 | ✅ | 2026-04-04 |
| C-11 | Confirmer /metrics api.py | 🟡 | monitoring/api.py | J1 | ⏳ | - |
