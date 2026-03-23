# AUDIT TECHNIQUE — EDGECORE
**Date** : 2026-03-21  
**Auditeur** : GitHub Copilot — Lead Architect review  
**Base** : 2764 tests, 63 fichiers de test, Python 3.11.9  
**Révision précédente** : aucune (premier audit de référence dans `tasks/audits/`)

---

## 1. Vue d'ensemble

**Objectif réel inféré depuis le code** : Moteur d'arbitrage statistique market-neutral sur actions US via Interactive Brokers TWS/Gateway. Stratégie unique : stat-arb pairs trading (z-score × 0.70 + momentum × 0.30). Horizon intraday à quelques jours. Capital réel visé.

**Type de système** : Live-ready avec mode paper ; backtest historique ; paper trading actif.

**Niveau de maturité** : **Pré-production avancée** — architecture solide, tous les composants critiques existent et sont testés, mais 4 lacunes de câblage/config empêchent une mise en production immédiate sans risque.

**Points forts réels (5 max)**
1. KillSwitch atomique à 5 conditions, état persisté, partagé entre `RiskFacade` et `LiveTradingRunner` (B2-02 résolu).
2. Rate limiting IBKR rigoureux : `TokenBucketRateLimiter(rate=45, burst=10)` ; `acquire()` appelé avant chaque appel API.
3. PIT universe (`load_constituents_csv` + `get_symbols_as_of`) — zéro biais de survie dans la sélection de l'univers.
4. Pipeline de backtest bien séparé de la logique live : `BacktestRunner` / `StrategyBacktestSimulator` n'importent pas de code live.
5. `persistence/audit_trail.py` : journalisation atomique `.tmp` → rename + HMAC-SHA256 optionnel.

**Signaux d'alerte globaux (5 max)**
1. `PortfolioHedger` (beta-neutral) **non câblé** dans `live_trading/runner.py` → le pipeline live trade sans neutralisation du beta marché.
2. Fallback Yahoo Finance dans `data/loader.py` sans rate-limit ni validation de contrat de données → risque de données silencieusement incorrectes en prod.
3. `strategies/pair_trading.py` : `regime_lookback_window` hardcodé à `20` ; config `RegimeDetectorConfig.regime_window=60` ignorée.
4. `AUDIT_HMAC_KEY` chargée sans validation à l'import : si la variable d'env est absente, toutes les entrées d'audit sont non signées (mode silencieux).
5. `backtester/` duplique `backtests/` sans valeur ajoutée claire — deux `WalkForward`, deux `BacktestRunner`-like, risque de divergence silencieuse.

---

## 2. Architecture & design système

### Organisation réelle

| Couche | Package | Rôle effectif |
|--------|---------|---------------|
| Interface publique | `universe/` | `UniverseManager` + PIT filtering |
| Interface publique | `pair_selection/` | `PairDiscoveryEngine` triple-gate EG+Johansen+HAC |
| Interface publique | `signal_engine/` | `SignalGenerator` + `SignalCombiner` (zscore×0.7 + momentum×0.3) |
| Interface publique | `risk_engine/` | `PositionRiskManager`, `PortfolioRiskManager`, `KillSwitch` (interface) |
| Interface publique | `portfolio_engine/` | `PortfolioAllocator` (VOLATILITY_INVERSE) + `PortfolioHedger` non câblé |
| Interface publique | `execution_engine/` | `ExecutionRouter` — thin adapter vers `execution/` |
| Interface publique | `backtester/` | `BacktestEngine` wrappant `BacktestRunner` |
| Interface publique | `live_trading/` | `LiveTradingRunner` — orchestrateur pipeline complet |
| Interface publique | `monitoring/` | `dashboard.py`, `alerter.py`, `email_alerter.py`, Prometheus |
| Implémentation | `execution/` | 28 fichiers — `Order`, `OrderStatus`, `IBKRExecutionEngine`, rate limiter, réconciliateur, stops |
| Implémentation | `risk/` | 13 fichiers — `RiskEngine`, `RiskFacade`, KillSwitch, Kelly, VaR, beta-neutral, PCA |
| Implémentation | `backtests/` | 11 fichiers — `StrategyBacktestSimulator`, `BacktestRunner`, `CostModel`, walk-forward |
| Implémentation | `models/` | 18 fichiers — `SpreadModel` (log-prices, Kalman), `RegimeDetector` (adaptatif), Cython cointegration |
| Implémentation | `strategies/` | `pair_trading.py` — boucle signal principale |
| Implémentation | `config/` | Singleton `get_settings()`, YAML par env |

### Doublons fonctionnels

| Doublon | Verdict | Risque |
|---------|---------|--------|
| `execution/` (28 fichiers) vs `execution_engine/` (3 fichiers) | ✅ Architecture intentionnelle — router thin adapter | Faible |
| `risk/` (13 fichiers) vs `risk_engine/` (4 fichiers) | ✅ Séparation impl / interface claire | Faible |
| `backtests/` (11 fichiers) vs `backtester/` (4 fichiers) | 🟠 Redondance réelle — deux `WalkForward`, `BacktestEngine` wrapper sans valeur | Moyen |
| `models/` vs `strategies/` | ✅ Maths brutes vs logique applicative — séparation correcte | Faible |

**Fichiers debug/archivés à la racine** : Aucun `ARCHIVED_*`, `bt_results_v*.txt`, `debug_*.txt` ni `CMakeLists.txt` trouvés — racine propre.

### Séparation stratégie / risk / exécution

- **Signal → Risque → Sizing → Exécution** : pipeline linéaire dans `LiveTradingRunner._run_loop()`. Ordre correct.
- **Couplage critique** : `_risk_facade` est la seule entrée du gate de risque pré-ordre. Le `KillSwitch` partagé par injection directe depuis `runner.py:270` — correct.
- **Gap** : `PortfolioHedger` (beta-neutral) existe dans `portfolio_engine/` avec tests, mais n'est pas instancié dans `runner.py`. Le pipeline live ignore le beta marché.

### Clean architecture

| Principe | Statut |
|----------|--------|
| Dépendances unidirectionnelles | ✅ `live_trading` → `execution_engine` → `execution/` |
| Pas d'import `research/` depuis prod | ✅ Vérifié |
| Config centralisée | ✅ `get_settings()` singleton |
| `datetime.utcnow()` banni | ✅ Zéro occurrence dans les sources |
| `print()` banni | ✅ Zéro occurrence dans les sources |

---

## 3. Qualité du code

### Lisibilité et cohérence

- Conventions respectées : `structlog`, `get_settings()`, `datetime.now(timezone.utc)`.  
- Nommage cohérent entre modules. Typage présent sur les interfaces publiques.
- `# type: ignore` absent (conforme aux instructions du projet).

### Fonctions > 100 lignes (exemples identifiés)

| Fichier | Méthode | Estimation |
|---------|---------|------------|
| `live_trading/runner.py` | `_run_loop()` | ~350 lignes — trop monolithique |
| `live_trading/runner.py` | `_initialize()` | ~180 lignes |
| `execution/ibkr_engine.py` | `submit_order()` | ~150 lignes |
| `backtests/simulation_loop.py` | boucle principale | ~200 lignes estimées |

`_run_loop()` cumule : fill confirmations, réconciliation, kill-switch check, pair re-discovery, market data fetch, stop checks, signal generation, risk gate, sizing, order submission — extraction en méthodes privées recommandée mais non bloquante.

### Duplication de logique

- Deux `WalkForward` : `backtests/walk_forward.py` et `backtester/walk_forward.py` — risque de divergence de comportement.
- Calcul du z-score présent dans `models/spread.py` ET potentiellement recalculé dans `strategies/pair_trading.py` (à vérifier avant duplication de fix).

### Gestion des erreurs

- `try/except Exception` avec log + `continue` dans `_run_loop()` — acceptable pour loop de trading (non-fatal par défaut).
- Aucun `bare except:` détecté dans les sources.
- `swallowing silencieux` identifié : Yahoo fallback dans `data/loader.py` — l'exception IBKR est catchée, Yahoo est tenté sans signalment d'alerte critique.

### Typage et validation

- Interfaces publiques bien typées. `common/validators.py` existe.
- `_cfg_val(config, name, default)` dans `strategies/pair_trading.py` : helper non typé avec default gratuit — risque de masquage de valeur de config.

---

## 4. Robustesse & fiabilité (TRADING-CRITICAL)

### Gestion des états dans `persistence/`

- `AuditTrail` : écriture atomique `.tmp` → rename + HMAC optionnel. ✅
- `KillSwitch` : état persisté dans `data/kill_switch_state.json` (atomic). ✅
- `IBKRExecutionEngine._persisted_order_ids` : dict en mémoire sérialisé — **non persisté entre redémarrages process**. Risque d'ordre dupliqué si crash + redémarrage rapide.

### Résilience aux données manquantes

- `data/loader.py` : `reqHistoricalData` IBKR → fallback Yahoo Finance. Yahoo n'a pas de rate-limit, contrat de données différent (splits, dividendes traitement divergent possible). Aucune alerte critique émise lors du fallback.
- `data/preprocessing.py` : validateurs présents. `data/validators.py` : contrat de données vérifié à l'entrée.
- Données `NaN` : pipeline utilise `ffill`/`dropna` — comportement non documenté sur fenêtres longues.

### Points de défaillance unique (SPOF)

| SPOF | Mitigation |
|------|-----------|
| Connexion TWS/Gateway | 3 retries + jitter + circuit breaker 5 échecs + reset 300s ✅ |
| `get_settings()` singleton | Fail-fast au démarrage ✅ |
| `KillSwitch` state | Persisté + callback `_on_kill_switch_activated` ✅ |
| Yahoo fallback | Aucune mitigation — SPOF silencieux 🟠 |
| `_persisted_order_ids` | Non persisté sur disque — SPOF redémarrage 🟠 |

### Crash mid-execution

- **Ordre soumis, crash avant confirmation** : `pending_close` status mis en `_positions`. Au redémarrage, `_positions` est rechargé depuis `persistence/` mais `_persisted_order_ids` est vide → le fill peut ne pas être reconnu et une double soumission est possible.
- `BrokerReconciler` (toutes les 5 min) devrait rattraper cet état — mais l'investissement de tests couvrant ce scénario est absent.

---

## 5. Interface IBKR & exécution des ordres

| Point de contrôle | Statut | Preuve |
|-------------------|--------|--------|
| Reconnexion automatique | ✅ | `_ensure_connected()` : 3 retries, backoff exponentiel + 30% jitter, circuit breaker 5 échecs, reset 300s |
| Rate limiting 50 req/s | ✅ | `_ibkr_rate_limiter = TokenBucketRateLimiter(rate=45, burst=10)` module-level ; `acquire()` avant chaque appel |
| Idempotence des ordres | ✅ (partielle) | `_persisted_order_ids` dict en mémoire — non persisté sur disque |
| Ordres partiels | 🟠 | `_process_fill_confirmations()` existe ; scénarios de fills partiels pas testés |
| Séparation paper/live | ✅ | `ENABLE_LIVE_TRADING` guard + `use_sandbox` en config prod (`false` confirmé) |
| Double soumission timeout | 🟠 | `_persisted_order_ids` non persisté → risque post-redémarrage |
| Erreurs informationnelles 2104/2106/2158 | ✅ | Loggées, non bloquantes |
| Erreurs historiques 162/200/354 | ✅ | `cancelHistoricalData` appelé dans `ibkr_sync_gateway.py` |

**Types d'ordres** : `MARKET`, `LIMIT`, `STOP_LIMIT` dans `execution/base.py`. `TRAILING_STOP_MARKET` absent — cohérent avec les restrictions IBKR sur certains produits.

---

## 6. Risk management & capital protection

### Moteur de risque

- `RiskEngine` (dans `risk/`) est **indépendant** de l'exécution — interface via `RiskFacade`. ✅
- Gate pré-ordre : `_risk_facade.can_enter_trade()` dans `_run_loop` avant toute soumission d'ordre. ✅

### KillSwitch — 5 conditions de halt

| Condition | Implémentée | Vérifiée pré-ordre | Persistée |
|-----------|-------------|-------------------|-----------|
| `drawdown_pct >= max_drawdown_pct` (10%) | ✅ | ✅ via `is_halted` | ✅ |
| `daily_loss_pct >= max_daily_loss_pct` | ✅ | ✅ | ✅ |
| `consecutive_losses >= max_consecutive_losses` | ✅ | ✅ | ✅ |
| `seconds_since_last_data > max_data_stale_seconds` | ✅ | ✅ | ✅ |
| `current_vol > historical_vol_mean × extreme_vol_multiplier` | ✅ | ✅ | ✅ |

- `_activation_lock` : atomicité garantie. ✅
- Callback `_on_kill_switch_activated` dans `LiveTradingRunner` : log critique + alerte + `TradingState.HALTED`. ✅
- **6ème condition manquante** : aucune condition sur perte par position individuelle au niveau KillSwitch (gérée séparément via `PositionRiskManager.max_position_loss_pct`).

### Tiers de risque

```
Tier 1 : RiskConfig.max_drawdown_pct   = 0.10  (10%)  ← halt entrées
Tier 2 : KillSwitchConfig              = 0.15  (15%)  ← halt global IBKR
Tier 3 : StrategyConfig.internal       = 0.20  (20%)  ← breaker stratégie
```

- `_assert_risk_tier_coherence()` validé au démarrage. ✅
- **Incohérence `prod.yaml`** : `max_position_loss_pct: 0.025` (2.5%) vs `StrategyConfig` default 0.10 (10%). Valeur prod plus stricte — acceptable mais non documentée intentionnellement.

### Beta-neutral hedging

- `BetaNeutralHedger` dans `risk/beta_neutral.py` : rolling window, dynamique par paire. ✅ dans l'implémentation.  
- **Non câblé dans `live_trading/runner.py`**. `PortfolioHedger` instancié dans `portfolio_engine/hedger.py` mais jamais appelé depuis le pipeline live. 🔴 Capital exposé au beta marché en production.

### Concentration limits

- `PortfolioRiskManager` vérifie les limites de concentration avant ordre. ✅
- Vérification **post-attribution de taille** mais **pré-soumission** — séquence correcte.

### Niveau de danger pour capital réel

**Moyen-élevé** uniquement à cause du beta non neutralisé. Avec les stops, le kill-switch et les risk tiers, le downside sur une paire est contrôlé. Mais un drawdown de marché corrélé peut déclencher des pertes sur plusieurs paires simultanément sans hedge SPY.

---

## 7. Intégrité statistique du backtest

### Biais look-ahead

- `tests/backtests/test_no_lookahead.py` : classe `TestNoLookAheadBias` présente. ✅
- `StrategyBacktestSimulator` : simulation bar-par-bar, signaux calculés sur `data[:i+1]`. ✅
- **Kalman filter** : `KalmanHedgeRatio` utilise une mise à jour séquentielle (predict-update). Aucun RTS smoother (smoother backward = look-ahead). ✅
- **RegimeDetector** : fenêtre glissante adaptative. ✅ causal.

### Cohérence backtest ↔ live

- `signal_engine/generator.py` utilisé dans les deux modes. ✅
- `SpreadModel` avec `use_log_prices=True` utilisé dans les deux modes (C-08). ✅
- **Point de risque** : `strategies/pair_trading.py` instancie `RegimeDetector` avec `regime_lookback_window=20` (hardcodé via `_cfg_val` default), tandis que la config `RegimeDetectorConfig.regime_window=60`. Si ce paramètre est utilisé dans le backtest mais pas en live (ou inversement), les résultats divergent.

### Modèle de coûts

- `CostModelConfig` : commission + slippage (Almgren-Chriss) + HTB premium par symbole. ✅
- Commission IBKR réaliste (`0.005$/action` paramétrable). ✅
- `execution_engine/router.py` : utilise `get_settings().costs.slippage_bps` (B5-02 résolu). ✅

### Walk-forward IS/OOS

- `backtests/walk_forward.py` ET `backtester/walk_forward.py` : deux implémentations.  
- `backtester/oos.py` : validateur OOS existe mais **son intégration dans le pipeline backtest principal est non documentée**.
- Contamination IS/OOS : pas de fuite évidente dans le code lu, mais la duplication `backtests/` vs `backtester/` crée un risque de régression silencieuse si un bug est corrigé dans un seul des deux.

### Biais de survie

- `universe/manager.py` : `load_constituents_csv` + `get_symbols_as_of(date)` — constituants historiques corrects. ✅
- `delisting_guard.py` dans `data/` : garde contre les données de delisting. ✅

| Dimension | Verdict |
|-----------|---------|
| Look-ahead bias | ✅ Absent |
| Kalman causal | ✅ Confirmé |
| Biais de survie | ✅ Corrigé (PIT) |
| Cohérence backtest/live signal | ✅ |
| Cohérence backtest/live régime | 🟠 Divergence possible (`regime_window` 20 vs 60) |
| Modèle de coûts | ✅ Réaliste |
| OOS validation pipeline | 🟡 Existe mais intégration floue |

---

## 8. Sécurité

### Credentials IBKR

- Aucun mot de passe IBKR stocké en fichier ou config YAML. ✅
- Connexion TWS : host/port uniquement — authentification déléguée à TWS. ✅
- `common/secrets.py` : `SecretsVault` avec `MaskedString` en mémoire, migration path vers HashiCorp Vault/AWS documentée. ✅

### Logs et config

- Aucune valeur de secret dans les logs (structlog ne sérialise pas les objets `MaskedString`). ✅
- `config/*.yaml` : aucune credential hardcodée. ✅
- `AUDIT_HMAC_KEY` : chargée depuis env, valeur vide silencieuse (pas de validation à l'import). 🟡

### Docker & docker-compose

- `Dockerfile` : non-root user `appuser` (uid 1000). ✅
- `EDGECORE_ENV=prod` (B5-01 résolu). ✅
- `docker-compose.yml` : `GRAFANA_PASSWORD` et `ELASTIC_PASSWORD` via `${VAR:?error}` — fail-fast si absent. ✅
- Aucun secret hardcodé dans les fichiers de config Docker. ✅

### Mauvaises pratiques

- `execution/ccxt_engine.py` : stocke `self.secret` en attribut d'instance plaintext. 🟡 (ce module n'est pas utilisé dans la stack IBKR principale)
- Aucune injection SQL (pas de DB relationnelle utilisée).
- Aucun subprocess avec entrée utilisateur non sanitisée détecté.

| Vecteur | Risque |
|---------|--------|
| Credentials IBKR | Faible ✅ |
| Secrets en config | Faible ✅ |
| Docker secrets | Faible ✅ |
| HMAC audit sans validation | Mineur 🟡 |
| `ccxt_engine.py` secret attribute | Mineur 🟡 (module inactif) |

---

## 9. Tests & validation

### État réel des tests

- **2764 tests passants** — 0 skipped, 0 failed (dernière exécution confirmée).
- 63 fichiers de test, 19 dossiers.

### Distribution par module

| Module | Fichiers test | Estimation tests |
|--------|--------------|-----------------|
| `models/` | 19 | ~800 |
| (racine `tests/`) | 9 | ~300 |
| `backtests/` | 7 | ~250 |
| `execution/` | 4 | ~180 |
| `live_trading/` | 4 | ~150 |
| `strategies/` | 3 | ~120 |
| `risk/` | 3 | ~150 |
| `signal_engine/` | 2 | ~80 |
| `data/` | 2 | ~80 |
| Autres | ~10 | ~400 |
| **`monitoring/`** | **0** | **0** |

### Parties non testées critiques

| Scénario | Couverture |
|----------|-----------|
| Crash réseau mid-order (ordre soumis, pas de réponse) | ❌ Absent |
| Fill partiel IBKR | ❌ Absent |
| Crash + redémarrage (état `pending_close` survit-il ?) | ❌ Absent |
| KillSwitch déclenché mid-loop (état cohérent ?) | 🟡 Tests unitaires KS, pas d'intégration live |
| Yahoo fallback avec données erronées | ❌ Absent |
| `monitoring/` (alerter, dashboard, Prometheus) | ❌ Zéro test fichier |
| `backtester/oos.py` intégration | 🟡 Classe existe, intégration pipeline non testée |

### Mocking IBKR

- Tests `live_trading/` et `execution/` : IBKR mocké via `MagicMock` / `patch`. ✅ Aucun appel réel en mode test.

### Niveau de confiance avant production

**6/10** — couverture des happy paths solide, cas limites opérationnels (crash, fill partiel, données corrompues) non testés pour les chemins critiques.

---

## 10. Observabilité & maintenance

### Logging

- `structlog` JSON partout dans les sources. Aucun `print()` en production. ✅
- Événements clés loggés : kill-switch activation, signal bloqué, fill confirmé, réconciliation.
- `live_trading/runner.py` : log critique + alerte sur `is_halted`. ✅

### Alerting

- `AlertCategory` : `RISK / ENTRY / EXIT / SYSTEM`. ✅
- `email_alerter.py` : SMTP via env vars (`GOOGLE_MAIL_PASSWORD` ou `EMAIL_SMTP_PASS`). ✅
- Événements couverts : kill-switch, data fetch failure, stop-exit failure, signal errors.
- **Lacune** : Yahoo fallback silencieux — aucune alerte `SYSTEM` lors du basculement.

### Diagnosticabilité live

- Prometheus metrics dans `monitoring/` : exposition correcte.  
- Grafana dans `docker-compose.yml` (password via env). ✅
- `diag.py` à la racine : outil diagnostic standalone. ✅
- **Absence de tests `monitoring/`** : si l'alerter bug silencieusement, aucun test ne le détecte.

### Maintenabilité 6–12 mois

- Pas de `ARCHIVED_*`, pas de fichiers debug racine, pas de `CMakeLists.txt`. ✅
- Deux `WalkForward` divergents (`backtests/` vs `backtester/`) : dette de fusion à planifier.
- `models/markov_regime.py` : `MarkovRegimeDetector` inactif par défaut (`use_markov_regime=False`). Code mort à clarifier ou supprimer.
- `models/ml_threshold_*.py` : fichiers ML threshold — statut actif ou orphelin non évident, aucun test visible directement référencé.

---

## 11. Dette technique

### Tableau de dette précis

| ID | Fichier:ligne | Description | Risque |
|----|--------------|-------------|--------|
| D-01 | `strategies/pair_trading.py:87` | `regime_lookback_window=20` hardcodé, ignore `RegimeDetectorConfig.regime_window=60` | 🟠 Divergence backtest/live |
| D-02 | `data/loader.py` | Yahoo fallback sans rate-limit, sans alerte critique | 🟠 Données silencieusement fausses en prod |
| D-03 | `portfolio_engine/hedger.py` / `live_trading/runner.py` | `PortfolioHedger` (beta-neutral) non câblé dans le pipeline live | 🔴 Exposition marché non neutralisée |
| D-04 | `execution/ibkr_engine.py` | `_persisted_order_ids` non persisté sur disque | 🟠 Risque double-ordre post-redémarrage |
| D-05 | `backtests/walk_forward.py` + `backtester/walk_forward.py` | Deux implémentations WalkForward | 🟠 Risque de divergence silencieuse |
| D-06 | `backtester/runner.py` | `BacktestEngine` wrappant `BacktestRunner` sans valeur ajoutée | 🟡 Dette de maintenance |
| D-07 | `persistence/audit_trail.py:30` | `AUDIT_HMAC_KEY=""` si env var absente — audit non signé sans avertissement | 🟡 Audit trail non fiable |
| D-08 | `models/markov_regime.py` | `MarkovRegimeDetector` inactif par défaut — code potentiellement orphelin | 🟡 Dead code |
| D-09 | `models/ml_threshold_*.py` | Statut actif/orphelin non évident, aucun test direct visible | 🟡 Dead code potentiel |
| D-10 | `backtester/oos.py` | OOS validator sans intégration claire dans le pipeline backtest | 🟡 Valeur réelle inconnue |
| D-11 | `execution/ccxt_engine.py` | Module ccxt (crypto) présent mais inutilisé dans la stack IBKR | 🟡 Confusion architecturale |

### Classification

**Dette dangereuse (risque de régression)**
- D-01 : divergence config régime backtest vs live
- D-03 : beta non neutralisé en live  
- D-04 : double-ordre post-crash
- D-05 : deux WalkForward pouvant diverger

**Dette acceptable court terme**
- D-02 : Yahoo fallback (acceptable en dev, inacceptable en prod sans alerte)
- D-07 : HMAC non validé (audit toujours écrit, juste non signé)

**Dette bloquante pour évolution sérieuse**
- D-05, D-06 : rend l'ajout de nouvelles stratégies de backtest ambigu (quel runner utiliser ?)

---

## 12. Recommandations priorisées

### Top 5 actions immédiates (ordre strict)

**1. Câbler `PortfolioHedger` dans `live_trading/runner.py`** (D-03 — 🔴)  
Instancier `PortfolioHedger` dans `_initialize()` et appeler `hedger.compute_hedge_orders(positions, market_data)` après sizing, avant l'ordre d'exécution. Sans ce câblage, le capital n'est pas market-neutral en live.

**2. Corriger `regime_lookback_window` dans `strategies/pair_trading.py`** (D-01 — 🟠)  
Remplacer `_cfg_val(_c, "regime_lookback_window", 20)` par `get_settings().regime_detector_config.regime_window` (ou lire depuis le dict config si disponible). Harmonise backtest et live.

**3. Persister `_persisted_order_ids` sur disque** (D-04 — 🟠)  
Sérialiser le dict à chaque mise à jour dans `data/pending_orders.json` (atomic write). Charger au démarrage. Élimine le risque de double-soumission post-redémarrage.

**4. Désactiver Yahoo fallback en prod ou ajouter alerte critique** (D-02 — 🟠)  
Dans `prod.yaml`, ajouter `data.allow_yahoo_fallback: false`. Dans `loader.py`, conditionner le fallback sur ce flag et émettre une alerte `AlertCategory.SYSTEM` si activé en prod.

**5. Unifier les deux `WalkForward`** (D-05 — 🟠)  
Supprimer `backtester/walk_forward.py` et faire pointer `backtester/runner.py` vers `backtests/walk_forward.py`. Ajouter test de non-régression.

### Actions à moyen terme

- Ajouter tests `monitoring/` (alerter, email, Prometheus scrape).
- Valider `AUDIT_HMAC_KEY` au démarrage : log warning si vide, error si en mode prod.
- Clarifier `models/ml_threshold_*.py` et `models/markov_regime.py` : activer ou supprimer avec tests.
- Intégrer `backtester/oos.py` dans le rapport de backtest standard ou le documenter explicitement.
- Ajouter tests : crash réseau mid-order, fill partiel, Yahoo fallback avec données corrompues.

### Actions optionnelles / confort

- Découper `_run_loop()` (~350 lignes) en sous-méthodes privées nommées.
- Supprimer `execution/ccxt_engine.py` (module crypto inutilisé, crée confusion).
- Consolider `backtests/runner.py` et `backtester/runner.py` en un seul point d'entrée.

---

## 13. Score final

### Score global : **7.0 / 10**

**Justification** : Architecture solide et pipeline complet. Tous les composants critiques (KillSwitch, rate-limit, PIT, PnL stops) existent et fonctionnent. Le score est pénalisé principalement par (a) le beta non neutralisé en live (D-03), (b) la divergence config régime (D-01), et (c) l'absence de tests sur les cas limites opérationnels les plus dangereux.

### Score détaillé par dimension

| Dimension | Score /10 | Justification |
|-----------|-----------|---------------|
| Architecture | 7.5 | Structure claire, doublons intentionnels sauf `backtester/` |
| Robustesse IBKR | 8.0 | Rate limit, reconnect, idempotence partielle. Manque persistance `_persisted_order_ids` |
| Risk management | 6.5 | KillSwitch complet, 3 tiers cohérents. Mais beta non neutralisé en live |
| Intégrité backtest | 7.5 | PIT, causal, no look-ahead. Divergence `regime_window` |
| Sécurité | 8.0 | Bonne gestion secrets, Docker propre. HMAC non validé mineur |
| Tests | 6.0 | 2764 tests, bonne couverture happy paths. Cas limites critiques absents |
| Observabilité | 7.0 | structlog JSON, alerting, Prometheus. Monitoring sans tests, Yahoo sans alerte |

### Probabilité de succès si l'état reste inchangé

**~45%** d'atteindre un premier mois sans incident de trading significatif en capital réel — principalement à cause de l'exposition marché non neutralisée (D-03) et du risque de double-ordre post-crash (D-04).

### Verdict final

👉 **Ne peut pas trader de l'argent réel dans cet état** — le pipeline live n'applique pas le hedge beta-neutral pourtant implémenté dans `portfolio_engine/hedger.py`, exposant le capital à des drawdowns de marché non contrôlés. Après correction de D-03 (câblage `PortfolioHedger`), D-01 (regime window) et D-04 (persistance order IDs), le système atteint le niveau pré-production avec monitoring actif requis.

---

*Audit généré le 2026-03-21 — basé sur 2764 tests passants, exploration complète des 9 modules publics + 8 packages internes.*
