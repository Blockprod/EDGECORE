# PLAN D'ACTION — EDGECORE — 2026-03-22
**Source** : `tasks/audits/audit_master_edgecore.md` (audit du 2026-03-21)  
**Base tests** : 2764 passants (63 fichiers)  
**Total** : 🔴 1 · 🟠 6 · 🟡 7 · **Effort estimé : 6.5 jours**

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Câbler PortfolioHedger dans le pipeline live

**Fichier** : `live_trading/runner.py` (méthode `_initialize()` et `_run_loop()`)  
**Problème** : `PortfolioHedger` (beta-neutral via `BetaNeutralHedger` + `PCAFactorMonitor`) est implémenté dans `portfolio_engine/hedger.py` avec tests, mais n'est jamais instancié ni appelé dans `LiveTradingRunner`. Le pipeline live trade sans neutralisation du beta marché. Un drawdown de marché corrélé sur plusieurs paires n'est pas protégé.  
**Correction** :
1. Dans `_initialize()`, instancier `self._portfolio_hedger = PortfolioHedger(benchmark_symbol=get_settings().risk.beta_benchmark)`.
2. Dans `_run_loop()`, après le sizing (`_size_positions`) et avant la soumission d'ordre, appeler `hedge_orders = self._portfolio_hedger.compute_hedge_orders(self._positions, market_data)` et soumettre les ordres de hedge via `self._router.submit_order(order)`.
3. Ajouter le benchmark SPY dans la liste de symboles à télécharger dans `_fetch_market_data()`.
4. Logger `live_trading_hedge_computed` avec `beta_portfolio` et `hedge_notional`.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/portfolio_engine/ tests/live_trading/ -x -q
# Attendu : ≥ 2764 tests passants
venv\Scripts\python.exe -c "from portfolio_engine.hedger import PortfolioHedger; h = PortfolioHedger(); print('OK')"
```
**Dépend de** : Aucune  
**Effort** : 1 jour  
**Statut** : ✅ 2026-03-22

### [C-02] Lire regime_lookback_window depuis la config (divergence backtest/live)

**Fichier** : `strategies/pair_trading.py:87`  
**Problème** : `lookback_window=self._cfg_val(_c, "regime_lookback_window", 20)` — default hardcodé à 20 alors que `RegimeDetectorConfig.regime_window=60` dans la config. En backtest, la configuration peut passer 60 via `_c` (dict depuis YAML), mais si la clé `"regime_lookback_window"` est absente du dict, la valeur 20 s'applique silencieusement. Divergence possible entre backtest et live selon le passage d'arguments.  
**Correction** :
Remplacer la ligne 87 par une lecture explicite depuis `get_settings()` :
```python
# Avant
lookback_window=self._cfg_val(_c, "regime_lookback_window", 20),
# Après
lookback_window=self._cfg_val(_c, "regime_lookback_window",
                              get_settings().regime_detector.regime_window),
```
S'assurer que `get_settings` est importé dans `strategies/pair_trading.py`. Vérifier le nom exact du champ dans `config/settings.py` (`RegimeDetectorConfig`).  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/strategies/ -x -q
# Attendu : ≥ 2764 tests passants
venv\Scripts\python.exe -c "from config.settings import get_settings; s=get_settings(); print(s.regime_detector.regime_window)"
# Attendu : 60 (ou valeur config env)
```
**Dépend de** : Aucune  
**Effort** : 0.25 jour  
**Statut** : ⏳

---

### [C-03] Persister _persisted_order_ids sur disque (risque double-ordre post-crash)

**Fichier** : `execution/ibkr_engine.py`  
**Problème** : `self._persisted_order_ids: dict[str, str]` est in-memory uniquement. Si le process crash et redémarre, le dict est vide ; un ordre `pending_close` toujours ouvert chez IBKR peut être resoumis, créant une double position.  
**Correction** :
1. À chaque `submit_order()` réussi, écrire atomiquement (`.tmp` → rename) `data/pending_order_ids.json` avec le dict `{order_id: symbol}`.
2. Dans `__init__` (ou `connect()`), charger le fichier si présent : `self._persisted_order_ids = _load_pending_order_ids()`.
3. À chaque fill confirmé (`_on_order_filled`), retirer l'entrée du fichier et réécrire atomiquement.
4. À l'initialisation, si des order_ids sont chargés, les passer au `BrokerReconciler` pour vérification immédiate.

Ne pas modifier `config/prod.yaml`.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/execution/ -x -q -k "idempotenc or persist or order"
# Attendu : ≥ 2764 tests passants
```
**Dépend de** : Aucune  
**Effort** : 0.5 jour  
**Statut** : ✅ N/A — fallback Yahoo absent du code source (vérifié 2026-03-22)

**Fichier** : `data/loader.py`  
**Constat** : L'audit décrivait un fallback Yahoo Finance dans `data/loader.py`, mais l'inspection du code source montre que `load_price_data()` est 100% IBKR — aucun appel `yfinance`, `yf.download` ou équivalent. Le fallback Yahoo mentionné dans les docs d'architecture n'a jamais été implémenté. Correction sans objet.

---

### [C-05] Consolider les deux implémentations WalkForward

**Fichier** : `backtester/walk_forward.py` + `backtests/walk_forward.py`  
**Problème** : Deux implémentations WalkForward coexistent sans différentiation fonctionnelle documentée. `BacktestEngine` dans `backtester/` importe `backtests/runner.py`, mais `backtester/walk_forward.py` est potentiellement une copie divergente. Un bug corrigé dans `backtests/` ne se propage pas dans `backtester/`, et inversement.  
**Correction** :
1. Lire les deux fichiers et identifier les différences concrètes.
2. Si `backtester/walk_forward.py` est un sous-ensemble : le supprimer et faire pointer `backtester/__init__.py` vers `backtests.walk_forward.WalkForwardEngine`.
3. Si `backtester/walk_forward.py` a des features propres : les fusionner dans `backtests/walk_forward.py` et supprimer `backtester/walk_forward.py`.
4. Mettre à jour `backtester/__init__.py` en conséquence.
5. Ajouter un test de non-régression dans `tests/backtests/` validant le même résultat sur un jeu de données fixe.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/backtests/ tests/backtester/ -x -q
# Attendu : ≥ 2764 tests passants
```
**Dépend de** : Aucune  
**Effort** : 1 jour  
**Statut** : ✅ 2026-03-22

---

### [C-06] Tests des scénarios critiques non couverts (crash réseau, fill partiel, pending_close)

**Fichier** : `tests/execution/test_ibkr_crash_recovery.py` (à créer),  
`tests/live_trading/test_live_trading_recovery.py` (à créer)  
**Problème** : Trois scénarios dangereux pour le capital réel n'ont aucun test :
- Crash réseau mid-order (ordre soumis chez IBKR, pas de réponse ACK)
- Fill partiel IBKR (1000 actions demandées, 600 remplies)
- Crash + redémarrage avec `pending_close` existant (état survit-il ? double-soumission ?)  
**Correction** :
1. `test_ibkr_crash_recovery.py` : mocker `IBKRExecutionEngine.submit_order()` pour simuler timeout post-soumission. Vérifier que `_persisted_order_ids` est écrit avant le crash. Vérifier qu'au redémarrage, le `BrokerReconciler` détecte l'ordre existant et ne le resoumet pas.
2. `test_ibkr_crash_recovery.py` : mocker une réponse IBKR de fill partiel (`filled=600 / requested=1000`). Vérifier que `_process_fill_confirmations()` gère le fill partiel (position mise à jour à 600, l'ordre résiduel est annulé ou suivi).
3. `test_live_trading_recovery.py` : simuler un redémarrage de `LiveTradingRunner` avec un `_positions` contenant un entry `status="pending_close"`. Vérifier que le runner ne reouvre pas la position.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/execution/test_ibkr_crash_recovery.py tests/live_trading/test_live_trading_recovery.py -x -v
# Attendu : tous les nouveaux tests passants + ≥ 2764 total
```
**Dépend de** : C-03 (persistance order IDs)  
**Effort** : 1.5 jours  
**Statut** : ⏳

---

## PHASE 3 — MINEURES 🟡

### [C-07] Valider AUDIT_HMAC_KEY au démarrage avec warning/error

**Fichier** : `persistence/audit_trail.py:30`  
**Problème** : `_AUDIT_HMAC_KEY = os.getenv("AUDIT_HMAC_KEY", "").encode()` — si la variable d'env est absente, toutes les entrées sont écrites sans signature HMAC-SHA256, silencieusement. En prod, l'audit trail n'est pas vérifiable.  
**Correction** :
Après la ligne 30, ajouter :
```python
if not _AUDIT_HMAC_KEY:
    import structlog as _sl
    _sl.get_logger(__name__).warning(
        "audit_trail_hmac_disabled",
        message="AUDIT_HMAC_KEY not set — audit entries are unsigned",
    )
```
En mode prod (`EDGECORE_ENV=prod`), élever en `error` (pas exception — ne pas bloquer le démarrage, mais rendre visible).  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/persistence/ -x -q
# Attendu : ≥ 2764 tests passants
```
**Dépend de** : Aucune  
**Effort** : 0.25 jour  
**Statut** : ⏳

---

### [C-08] Ajouter tests pour monitoring/ (alerter, dashboard, Prometheus)

**Fichier** : `tests/monitoring/test_monitoring.py` (à créer)  
**Problème** : Zéro fichier de test dans `tests/monitoring/`. Si `email_alerter.py` ou `alerter.py` buggent silencieusement (SMTP error swallowed, mauvais `AlertCategory`), aucun test ne le détecte.  
**Correction** :
Créer `tests/monitoring/test_monitoring.py` avec au minimum :
1. `TestAlerter` : vérifier que `send_alert(AlertCategory.RISK, ...)` appelle bien le handler email avec les bons paramètres (mock SMTP).
2. `TestEmailAlerter` : vérifier le fallback gracieux si SMTP échoue (pas d'exception levée, log d'erreur structlog).
3. `TestPrometheus` : vérifier que les métriques Prometheus sont exposées sur l'endpoint attendu (mock httpserver ou test unitaire de l'exposition).  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/monitoring/ -x -q
# Attendu : ≥ 2764 + nouveaux tests passants
```
**Dépend de** : Aucune  
**Effort** : 0.5 jour  
**Statut** : ⏳

---

### [C-09] Clarifier ou supprimer MarkovRegimeDetector

**Fichier** : `models/markov_regime.py`  
**Problème** : `MarkovRegimeDetector` existe mais `use_markov_regime=False` dans la config par défaut. Le module est dead code dans toutes les configurations standard. Risque de maintenir du code non testé en prod.  
**Correction** :
- **Option A (recommandée)** : Ajouter un bloc `if not get_settings().models.use_markov_regime: return` dans les points d'appel ET ajouter au moins 3 tests unitaires dans `tests/models/test_markov_regime.py` pour valider les transitions d'état.
- **Option B** : Supprimer le fichier et retirer la référence dans `models/__init__.py` si la décision est de ne jamais l'activer.
Documenter la décision dans un commentaire `# DECISION 2026-03-22: ...` en tête du fichier ou dans `architecture/decisions.md`.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/models/ -x -q
# Attendu : ≥ 2764 tests passants
```
**Dépend de** : Aucune  
**Effort** : 0.25 jour  
**Statut** : ⏳

---

### [C-10] Clarifier ou supprimer les fichiers ml_threshold_*.py

**Fichier** : `models/ml_threshold_*.py`  
**Problème** : Un ou plusieurs fichiers `ml_threshold*.py` dans `models/` dont le statut actif/orphelin est non évident. Aucun test direct visible. Code mort potentiel augmentant la surface de maintenance.  
**Correction** :
1. Identifier tous les fichiers `ml_threshold*.py` dans `models/`.
2. Grep les importeurs : si aucun fichier de prod ne les importe → ajouter commentaire `# ORPHAN 2026-03-22` et ouvrir une issue.
3. Si actifs : ajouter tests dans `tests/models/` et documenter leur rôle dans `models/__init__.py`.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/models/ -x -q
# Attendu : ≥ 2764 tests passants
```
**Dépend de** : Aucune  
**Effort** : 0.25 jour  
**Statut** : ⏳

---

### [C-11] Documenter ou intégrer backtester/oos.py dans le pipeline backtest

**Fichier** : `backtester/oos.py`  
**Problème** : `OOSValidationEngine` dans `backtester/oos.py` existe mais son intégration dans le pipeline standard n'est pas documentée ni testée de bout en bout. La valeur réelle de la validation OOS n'est pas accessible via l'API `BacktestEngine`.  
**Correction** :
1. Lire `backtester/oos.py` et vérifier si `BacktestEngine` l'expose ou l'appelle.
2. Si non : ajouter `BacktestEngine.run_oos_validation(train_end_date, oos_end_date)` appelant `OOSValidationEngine`.
3. Ajouter un test dans `tests/backtests/test_oos.py` vérifiant qu'un run OOS sur données synthétiques produit des métriques différentes du run IS.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/backtests/test_oos.py -x -q
# Attendu : nouveau test passant + ≥ 2764 total
```
**Dépend de** : C-05 (consolidation WalkForward préalable recommandée)  
**Effort** : 0.5 jour  
**Statut** : ⏳

---

### [C-12] Supprimer ou isoler execution/ccxt_engine.py

**Fichier** : `execution/ccxt_engine.py`  
**Problème** : Module d'exécution ccxt (crypto) présent dans `execution/`, package utilisé exclusivement pour IBKR. `self.secret` stocké en attribut plaintext. Impossible à atteindre via le router IBKR. Crée une confusion architecturale et une surface de sécurité inutile.  
**Correction** :
1. Vérifier qu'aucun fichier de prod n'importe `ccxt_engine`.
2. Déplacer le fichier dans `research/` ou le supprimer.
3. Si des tests l'utilisent, les supprimer également.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : ≥ 2764 tests passants (ou légèrement moins si tests ccxt supprimés)
```
**Dépend de** : Aucune  
**Effort** : 0.25 jour  
**Statut** : ⏳

---

### [C-13] Supprimer BacktestEngine wrapper sans valeur (backtester/runner.py)

**Fichier** : `backtester/runner.py`  
**Problème** : `BacktestEngine` n'est qu'un wrapper fin sur `BacktestRunner` de `backtests/`. Sans logique propre, il double la surface de maintenance et oblige à choisir entre deux points d'entrée sans guide clair.  
**Correction** :
Après C-05 (consolidation WalkForward) et C-11 (OOS integration) :
1. Vérifier si `BacktestEngine` ajoute une logique qui n'est pas dans `BacktestRunner`.
2. Si non : faire de `BacktestEngine` un alias pur (`BacktestEngine = BacktestRunner`) avec deprecation warning, ou le supprimer.
3. Mettre à jour `backtester/__init__.py` et tous les consommateurs.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/backtests/ tests/backtester/ -x -q
# Attendu : ≥ 2764 tests passants
```
**Dépend de** : C-05, C-11  
**Effort** : 0.25 jour  
**Statut** : ⏳

---

### [C-14] Découper _run_loop() en méthodes privées nommées

**Fichier** : `live_trading/runner.py` (méthode `_run_loop()`, ~350 lignes)  
**Problème** : `_run_loop()` cumule 9 responsabilités distinctes (fill confirmations, réconciliation, kill-switch, pair re-discovery, market data, stops, signals, risk gate, execution). Méthode non testable unitairement, difficile à maintenir.  
**Correction** :
Extraire en méthodes privées nommées (sans changer leur comportement) :
- `_run_loop()` devient un séquenceur appelant :
  - `_step_process_fills()`
  - `_step_reconcile()`
  - `_step_check_kill_switch() → bool`
  - `_step_rediscover_pairs()`
  - `_step_fetch_market_data() → DataFrame | None`
  - `_step_process_stops(market_data)`
  - `_step_generate_signals(market_data) → list`
  - `_step_execute_signals(signals, market_data)`

Chaque méthode ≤ 50 lignes. Zéro changement de comportement.  
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/live_trading/ -x -q
# Attendu : ≥ 2764 tests passants (comportement inchangé)
```
**Dépend de** : C-01 (câblage hedger dans _run_loop)  
**Effort** : 0.5 jour  
**Statut** : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
C-01  → C-06 (les tests crash nécessitent la persistance order IDs de C-03)
C-02  (indépendante, peut être faite en parallèle)
C-03  → C-06
C-04  (indépendante)
C-05  → C-11 → C-13
C-07  (indépendante)
C-08  (indépendante)
C-09  (indépendante)
C-10  (indépendante)
C-12  (indépendante)
C-14  (après C-01)
```

**Ordre recommandé (séquentiel)** :
```
C-02  (0.25j — fix immédiat 1 ligne, risque zéro)
C-01  (1j    — câblage PortfolioHedger, le plus critique)
C-03  (0.5j  — persistance order IDs)
C-04  (0.5j  — Yahoo fallback flag)
C-06  (1.5j  — tests crash/fill/recovery, dépend C-03)
C-05  (1j    — consolidation WalkForward)
C-07  (0.25j — HMAC validation)
C-08  (0.5j  — tests monitoring)
C-09  (0.25j — Markov clarification)
C-10  (0.25j — ml_threshold clarification)
C-11  (0.5j  — OOS integration, après C-05)
C-12  (0.25j — supprimer ccxt_engine)
C-13  (0.25j — BacktestEngine alias, après C-05/C-11)
C-14  (0.5j  — refactor _run_loop, après C-01)
```

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert (C-01 terminé et validé)
- [ ] `pytest tests/ -x -q` : 100% pass (2764+)
- [ ] `pytest tests/ -W error::DeprecationWarning -q` : 0 warning DeprecationWarning
- [ ] `mypy risk/ risk_engine/ execution/ --ignore-missing-imports --no-error-summary` : exit 0
- [ ] `ruff check .` : 0 erreurs
- [ ] Zéro credential IBKR dans les logs (grep confirmé)
- [ ] Kill-switch persisté au redémarrage (test C-06 passant)
- [ ] `_persisted_order_ids` persisté sur disque (C-03 terminé)
- [ ] `PortfolioHedger` câblé et beta_portfolio loggé (C-01 terminé)
- [ ] Risk tiers cohérents : `venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"`
- [ ] `EDGECORE_ENV=prod` dans Dockerfile (pas "production") — déjà OK
- [ ] Yahoo fallback désactivé en prod (`data.allow_yahoo_fallback: false` dans prod.yaml) — C-04 terminé
- [ ] Paper trading validé avant live (min 5 jours de paper sans incident)

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier principal | Effort | Statut | Date |
|----|-------|----------|-------------------|--------|--------|------|
| C-01 | Câbler PortfolioHedger dans live | 🔴 | `live_trading/runner.py` | 1j | ✅ | 2026-03-22 |
| C-02 | Fix regime_lookback_window → config | 🟠 | `strategies/pair_trading.py:87` | 0.25j | ✅ | 2026-03-22 |
| C-03 | Persister _persisted_order_ids | 🟠 | `execution/ibkr_engine.py` | 0.5j | ✅ | Déjà impl. |
| C-04 | Yahoo fallback flag + alerte prod | 🟠 | `data/loader.py` | 0.5j | ✅ | N/A (vérifié 2026-03-22) |
| C-05 | Consolider deux WalkForward | 🟠 | `backtester/walk_forward.py` | 1j | ✅ | 2026-03-22 |
| C-06 | Tests crash réseau / fill partiel / recovery | 🟠 | `tests/execution/` + `tests/live_trading/` | 1.5j | ✅ | 2026-03-22 |
| C-07 | AUDIT_HMAC_KEY validation démarrage | 🟡 | `persistence/audit_trail.py:30` | 0.25j | ✅ | 2026-03-22 |
| C-08 | Tests monitoring/ (alerter + Prometheus) | 🟡 | `tests/monitoring/` | 0.5j | ✅ | N/A (vérifié 2026-03-22 — 370 tests existants) |
| C-09 | Clarifier/supprimer MarkovRegimeDetector | 🟡 | `models/markov_regime.py` | 0.25j | ✅ | 2026-03-22 |
| C-10 | Clarifier/supprimer ml_threshold_*.py | 🟡 | `models/ml_threshold_*.py` | 0.25j | ✅ | 2026-03-22 |
| C-11 | Intégrer backtester/oos.py dans pipeline | 🟡 | `backtester/oos.py` | 0.5j | ✅ | 2026-03-22 |
| C-12 | Supprimer execution/ccxt_engine.py | 🟡 | `execution/ccxt_engine.py` | 0.25j | ✅ | 2026-03-22 |
| C-13 | Supprimer BacktestEngine wrapper | 🟡 | `backtester/runner.py` | 0.25j | ✅ | N/A 2026-03-22 (run_oos_validation ajoute de la valeur) |
| C-14 | Découper _run_loop() en méthodes privées | 🟡 | `live_trading/runner.py` | 0.5j | ✅ | 2026-03-22 |

**Total estimé : 6.5 jours**
