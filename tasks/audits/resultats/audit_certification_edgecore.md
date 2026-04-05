---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_certification_edgecore.md
derniere_revision: 2026-07-14
creation: 2026-07-14 à 00:00
---

# AUDIT DE CERTIFICATION — EDGECORE V1
**Date** : 2026-07-14  
**Branche** : `main` — commit `c17264b`  
**Tests** : 2723 ✅ / 2734 collectés (11 échecs Cython)  
**Auditeur** : GitHub Copilot (Claude Sonnet 4.6)

---

## GRILLE DE CERTIFICATION — 10 CRITÈRES

---

### C1 — ROBUSTESSE DE L'EXÉCUTION IBKR

| Point de contrôle | Filed:Ligne | Statut |
|---|---|---|
| Reconnect auto avec backoff exponentiel [5, 15, 30]s + 30% jitter | `execution/ibkr_engine.py:97-143` | ✅ |
| Circuit breaker CLOSED/OPEN/HALF_OPEN, seuil 5 échecs | `common/circuit_breaker.py:26-29` | ✅ |
| Rate limiter 40 req/s (< 50 TWS hard cap) | `common/ibkr_rate_limiter.py:17` | ✅ |
| Rate limiter appelé avant tout appel IBKR live | `execution_engine/router.py:299` | ✅ |
| Retry policy sur submit_order (3 tentatives, backoff ×2, jitter 20%) | `execution_engine/router.py:307-316` | ✅ |
| Anti-short guard : bloque SELL si shortable < quantity | `execution_engine/router.py:258-275` | ✅ |
| Guard duplicate client_id (`_active_client_ids` registry) | `execution/ibkr_engine.py:48` | ✅ |
| Slippage lu depuis `get_settings().costs.slippage_bps` (pas hardcodé) | `execution_engine/router.py:156` | ✅ |
| Commission lue depuis `get_settings().costs.commission_pct` | `execution_engine/router.py:203` | ✅ |
| BrokerReconciler toutes les 5 minutes | `live_trading/runner.py:353,354` | ✅ |
| Reconciliation critique bloque le trading au démarrage | `live_trading/runner.py:~605` | ✅ |
| Récupération fill réel via `trade_obj.fills` (avg price + commission) | `execution_engine/router.py:330-345` | ✅ |
| Synchronisation atomique des deux legs (long + short) | Non vérifié — absent du `_live_fill()` | ⚠️ |

**Observations :** La logique de connexion/reconnexion est exemplaire. L'anti-short guard et le retry policy sur submit sont des bonnes pratiques institutionnelles. La seule lacune est l'absence de rollback atomique si le leg 2 échoue après remplissage du leg 1 — en cas de rejet partiel, la position devient déséquilibrée.

**Score C1 : 9 / 10**

---

### C2 — RISK MANAGEMENT & KILL-SWITCH

| Point de contrôle | Fichier:Ligne | Statut |
|---|---|---|
| Tier 1 — DD 10% halt entrées (`RiskConfig.max_drawdown_pct`) | `config/settings.py:116` | ✅ |
| Tier 2 — DD 15% halt global (`KillSwitchConfig.max_drawdown_pct`) | `risk_engine/kill_switch.py:~KillSwitchConfig` | ✅ |
| Tier 3 — DD 20% breaker stratégie (`internal_max_drawdown_pct`) | `config/settings.py:~85` | ✅ |
| Assertion cohérence T1 ≤ T2 ≤ T3 au démarrage | `config/settings.py (_assert_risk_tier_coherence)` | ✅ |
| 7 conditions KillSwitch : DRAWDOWN / DAILY_LOSS / CONSECUTIVE_LOSSES / VOLATILITY_EXTREME / DATA_STALE / MANUAL / EXCHANGE_ERROR | `risk_engine/kill_switch.py:50-57` | ✅ |
| État KillSwitch persisté sur disque (crash recovery) | `risk_engine/kill_switch.py (data/kill_switch_state.json)` | ✅ |
| `_activation_lock` thread-safety | `risk_engine/kill_switch.py:~A-16` | ✅ |
| KillSwitch partagé entre LiveTradingRunner et RiskFacade (B2-02 corrigé) | `live_trading/runner.py:315-318` | ✅ |
| `_on_kill_switch_activated()` : annule tous les ordres IBKR + alerte CRITICAL | `live_trading/runner.py:400-415` | ✅ |
| `ConcentrationManager` : limite par symbole 30% | `portfolio_engine/concentration.py:38` | ✅ |
| `RiskConfig.max_sector_weight = 0.40` (40% max par secteur) | `config/settings.py:127` | ✅ |
| `RiskConfig.spread_correlation_max = 0.40` | `config/settings.py:128` | ✅ |
| PortfolioRiskManager T1 câblé depuis `get_settings().risk.max_drawdown_pct` | `live_trading/runner.py:302` | ✅ |
| Double comptage DD entre `PortfolioRiskManager` et `RiskFacade/RiskEngine` | Résiduel B2-02 — deux compteurs indépendants | ⚠️ |

**Observations :** Architecture 3-tiers correctement câblée. L'instance KillSwitch partagée résout B2-02 pour le kill-switch, mais `PortfolioRiskManager` (T1) et `RiskEngine` dans `RiskFacade` suivent tous les deux le drawdown indépendamment — risque de divergence de seuil entre les deux.

**Score C2 : 8.5 / 10**

---

### C3 — INTÉGRITÉ DU BACKTEST (ABSENCE DE LOOK-AHEAD BIAS)

| Point de contrôle | Fichier:Ligne | Statut |
|---|---|---|
| Walk-forward : zéro fuite de données (commentaire explicite Sprint 1.3) | `backtests/walk_forward.py:8` | ✅ |
| Instance `StrategyBacktestSimulator` fraîche par période WF | `backtests/walk_forward.py:~WalkForwardBacktester` | ✅ |
| Fenêtre expanding (train depuis t=0), séquence strictement chronologique | `backtests/walk_forward.py:58-72` | ✅ |
| Modèle de coût Almgren-Chriss (market impact + gap + borrow + fees) | `backtests/cost_model.py:14-40` | ✅ |
| HTB par symbole (CSV `data/htb_rates.csv`) | `backtests/cost_model.py:63` | ✅ |
| Event-driven backtester (partial fills, bid/ask spread, price gap) | `backtests/event_driven.py:1-100` | ✅ |
| Bonferroni correction activée | `config/settings.py:StrategyConfig.bonferroni_correction=True` | ✅ |
| FDR Benjamini-Hochberg activé (`fdr_q_level = 0.20`) | `config/settings.py:StrategyConfig` | ✅ |
| Johansen double-screening (`johansen_confirmation=True`) | `config/settings.py:StrategyConfig` | ✅ |
| Newey-West HAC consensus (`newey_west_consensus=True`) | `config/settings.py:StrategyConfig` | ✅ |
| Signal.timestamp sans `timezone.utc` (`datetime.now()` nu) | `signal_engine/generator.py:55` | ⚠️ |
| v48 backtest OOS 2024H2 : Sharpe=0.00, **0 trades** — verdict FAIL | `results/v48_p5_results.txt` | 🔴 |
| Cython `brownian_bridge_batch_fast` absent du `.pyd` compilé | Tests 11 échecs Cython | 🔴 |

**Observations :** L'infrastructure anti-look-ahead est solide (walk-forward expanding, coût Almgren-Chriss, double screening). Mais le dernier résultat OOS publié (v48, 2024H2) génère **0 trades**, ce qui rend toute validation de performance impossible. Ce n'est pas un biais de look-ahead mais un défaut de configuration/data pipeline qui empêche la certification d'un alpha réel.

**Score C3 : 6.5 / 10** ← pénalisé par le 0-trade en OOS

---

### C4 — INFRASTRUCTURE & DEVOPS

| Point de contrôle | Fichier:Ligne | Statut |
|---|---|---|
| Dockerfile 2 stages (builder + production) | `Dockerfile:1-80` | ✅ |
| Image de base `debian:bookworm-slim` (surface CVE minimale) | `Dockerfile:1` | ✅ |
| `EDGECORE_ENV=prod` (pas `production`) | `Dockerfile:34` | ✅ |
| Utilisateur non-root `appuser` (UID 1000) | `Dockerfile:56` | ✅ |
| `HEALTHCHECK` Docker configuré | `Dockerfile:68` | ✅ |
| docker-compose : healthchecks sur tous les services | `docker-compose.yml:40-44, 68-73` | ✅ |
| `restart: unless-stopped` | `docker-compose.yml:37` | ✅ |
| Volumes montés (logs, cache, config:ro, persistence) | `docker-compose.yml:31-36` | ✅ |
| Config montée read-only (`./config:/app/config:ro`) | `docker-compose.yml:34` | ✅ |
| Prometheus + Grafana services dans docker-compose | `docker-compose.yml:~80-120` | ✅ |
| CI : ruff autofix + type check (mypy + pyright) | `.github/workflows/main.yml:100-110` | ✅ |
| CI : pip-audit (CVE scan, exception CVE-2026-4539 tracée) | `.github/workflows/main.yml:113-116` | ✅ |
| CI : trufflehog secret scan (only-verified) | `.github/workflows/main.yml:118-123` | ✅ |
| CI : coverage ≥70% (`--cov-fail-under=70`) | `.github/workflows/main.yml:131` | ✅ |
| CI : test statistiques + régression séparés | `.github/workflows/main.yml:135-140` | ✅ |
| CI : build + push Docker vers ghcr.io sur `main` | `.github/workflows/main.yml:~150-180` | ✅ |
| `EDGECORE_ENV=prod` dans docker-compose corrigé (B5-01) | `docker-compose.yml:13` | ✅ |
| Fichier `ci.yml` absent — 1 seul workflow `main.yml` | `.github/workflows/` (1 fichier) | ⚠️ |

**Score C4 : 8.5 / 10**

---

### C5 — QUALITÉ DE CODE & ARCHITECTURE

| Point de contrôle | Fichier:Ligne | Statut |
|---|---|---|
| `structlog.get_logger(__name__)` dans tous les modules revus | Multiple fichiers | ✅ |
| Pas de `print()` trouvé dans les modules de production | Revue manuelle | ✅ |
| Pas de `datetime.utcnow()` dans les modules revus | Revue manuelle | ✅ |
| Pas de seuils de risque hardcodés dans les modules revus | Multiple fichiers | ✅ |
| mypy strict sur `risk.*`, `risk_engine.*`, `execution.*` | `pyproject.toml:~65` | ✅ |
| mypy `ignore_errors=True` sur `strategies.*`, `signal_engine.*`, `monitoring.*` | `pyproject.toml:~50-60` | ⚠️ |
| `Signal.timestamp = datetime.now()` sans UTC | `signal_engine/generator.py:55` | ⚠️ |
| `monitoring/logger.py` : crée `datetime.now()` sans UTC à la ligne 10 | `monitoring/logger.py:10` | ⚠️ |
| Double architecture `execution/` (24 fichiers) + `execution_engine/` (2 fichiers) | Architecture globale | ⚠️ |
| Double architecture `risk/` (12 fichiers) + `risk_engine/` (4 fichiers) | Architecture globale | ⚠️ |
| Import `IBKRExecutionEngine` dupliqué dans `main.py` (lignes 32 et 37) | `main.py:32,37` | ⚠️ |
| `ruff` enforced en CI, `pyproject.toml` configuré | `pyproject.toml + .github/workflows/main.yml` | ✅ |

**Observations :** La qualité des modules critiques (risk, execution) est institutionnelle. La dette architecturale double (execution/execution_engine, risk/risk_engine) est le principal point noir. `ignore_errors=True` dans mypy sur `signal_engine.*` masque potentiellement des bugs dans la logique de signal.

**Score C5 : 7 / 10**

---

### C6 — TESTS & COUVERTURE

| Point de contrôle | Fichier:Ligne | Statut |
|---|---|---|
| 2723 tests passants sur 2734 collectés | `pytest.ini + CI` | ✅ |
| 152 fichiers de test | `tests/` | ✅ |
| Couverture ≥70% requise par CI | `.github/workflows/main.yml:131` | ✅ |
| Tests statistiques séparés (`-m slow`) | `tests/statistical/` | ✅ |
| Tests de régression séparés | `tests/regression/` | ✅ |
| 11 échecs Cython : `brownian_bridge_batch_fast` absent du `.pyd` | `tests/models/test_cointegration_fast.py` | 🔴 |
| `compute_zscore_last_fast` absent du `.pyd` compilé | Extension Cython incomplète | 🔴 |
| Guard live mode présent : `if not CYTHON_AVAILABLE and mode == "live": raise` | `live_trading/runner.py:~470` | ✅ |
| Aucun `@pytest.mark.skip` sans commentaire traçable (règle) | Non vérifié exhaustivement | ⚠️ |

**Observations :** Le volume de tests est excellent et la structure (unit / stats / regression) est institutionnelle. Les 11 échecs Cython sont bloquants car ils signalent que le `.pyd` actuellement compilé est incompatible avec le code source (fonctions manquantes). Le guard live mode protège contre l'exécution, mais les tests qui dépendent de ces fonctions sont faux positifs permanents.

**Score C6 : 7 / 10**

---

### C7 — OBSERVABILITÉ & MONITORING

| Point de contrôle | Fichier:Ligne | Statut |
|---|---|---|
| structlog JSON renderer configuré (`JSONRenderer`) | `monitoring/logger.py:41` | ✅ |
| Fichier log horodaté par module | `monitoring/logger.py:18-20` | ✅ |
| `AlertManager` avec 4 niveaux (INFO/WARNING/ERROR/CRITICAL) | `monitoring/alerter.py:17-22` | ✅ |
| 8 catégories d'alerte (EQUITY/POSITION/ORDER/RISK/BROKER/SYSTEM/...) | `monitoring/alerter.py:26-35` | ✅ |
| Email + Slack alerters wired dans `LiveTradingRunner` | `live_trading/runner.py:358-361` | ✅ |
| Dispatch asynchrone via `ThreadPoolExecutor(max_workers=1)` | `live_trading/runner.py:364` | ✅ |
| `SystemMetrics.to_prometheus_format()` exporte le format texte Prometheus | `monitoring/metrics.py:22-44` | ✅ |
| Prometheus + Grafana dans docker-compose | `docker-compose.yml:~85-130` | ✅ |
| `CorrelationMonitor` wired dans `_initialize()` | `live_trading/runner.py:332` | ✅ |
| `KillSwitch` activé → alerte CRITICAL envoyée | `live_trading/runner.py:408-414` | ✅ |
| Endpoint Flask servant `to_prometheus_format()` non confirmé | `monitoring/api.py` non relu | ⚠️ |
| `SystemMetrics` : métriques basiques only (pas de histogramme latence, pas de gauge par paire) | `monitoring/metrics.py:1-50` | ⚠️ |
| Pas d'intégration log-shipping (Loki/ELK) confirmée au-delà du driver json-file | `docker-compose.yml` | ⚠️ |

**Score C7 : 7.5 / 10**

---

### C8 — INTÉGRITÉ DES DONNÉES

| Point de contrôle | Fichier:Ligne | Statut |
|---|---|---|
| `OHLCVValidator` avec 12 checks | `data/validators.py` | ✅ |
| Rate limiter dans `data/loader.py` avant appel IBKR | `data/loader.py:10,57` | ✅ |
| Cache disque parquet (fallback IBKR) | `data/loader.py:74-85` | ✅ |
| `DelistingGuard` : volume crash >80%, penny <$0.001, stale >3j | `data/delisting_guard.py:13-17` | ✅ |
| `LiquidityFilter` : min $5M daily volume | `data/liquidity_filter.py` | ✅ |
| `ibkr_invalid_symbols.txt` — blacklist symboles invalides | `ibkr_invalid_symbols.txt` | ✅ |
| Corporate actions flag : `adjust_for_corporate_actions=True` | `config/settings.py:BacktestConfig` | ✅ |
| Earnings gap detection wired (`earnings_gaps_detected` dans logs v45b) | `results/v45b_p5_rerun.txt` | ✅ |
| `data/event_filter.py` — blackout earnings | Architecture step 1 | ✅ |
| Yahoo Finance fallback non confirmé dans `data/loader.py` | Uniquement cache disque visible | ⚠️ |
| Handling NaN/inf dans `data/preprocessing.py` non relu | `data/preprocessing.py` | ⚠️ |

**Score C8 : 8 / 10**

---

### C9 — SÉCURITÉ

| Point de contrôle | Fichier:Ligne | Statut |
|---|---|---|
| Image non-root `appuser` UID 1000 | `Dockerfile:56-58` | ✅ |
| `AUDIT_HMAC_KEY` : RuntimeError en prod si absent | `persistence/audit_trail.py:31-38` | ✅ |
| HMAC par ligne dans l'audit trail | `persistence/audit_trail.py` | ✅ |
| `common/secrets.py` — module gestion secrets | `common/secrets.py` | ✅ |
| trufflehog secret scan en CI (only-verified) | `.github/workflows/main.yml:118-123` | ✅ |
| pip-audit CVE scan en CI | `.github/workflows/main.yml:113-116` | ✅ |
| Config montée read-only | `docker-compose.yml:34` | ✅ |
| Aucun credential hardcodé trouvé dans les modules revus | Revue manuelle | ✅ |
| `common/validators.py` — validation des inputs | `common/validators.py` | ✅ |
| `SecretsConfig.mask_ratio=0.8` — masquage dans les logs | `config/settings.py:SecretsConfig` | ✅ |
| `SecretsConfig.rotation_interval_days=90` | `config/settings.py:SecretsConfig` | ✅ |
| Double import `IBKRExecutionEngine` dans `main.py` | `main.py:32,37` | ⚠️ |
| `.env.example` non vérifié (non relu) | Fichier non trouvé en workspace | ⚠️ |

**Score C9 : 8.5 / 10**

---

### C10 — MATURITÉ OPÉRATIONNELLE

| Point de contrôle | Fichier:Ligne | Statut |
|---|---|---|
| Graceful shutdown : `ShutdownManager.is_shutdown_requested()` dans la boucle | `live_trading/runner.py:461` | ✅ |
| `KeyboardInterrupt` catchée → `_shutdown()` en `finally` | `live_trading/runner.py:467-470` | ✅ |
| `_alert_executor.shutdown(wait=False)` — flush non-bloquant | `live_trading/runner.py:476` | ✅ |
| Crash recovery : `AuditTrail.recover_state()` au démarrage | `live_trading/runner.py:~550-562` | ✅ |
| `fsync` après chaque ligne d'audit (`fsync_mode="always"` par défaut) | `persistence/audit_trail.py:~60` | ✅ |
| Réconciliation de démarrage : halt si status "critical" | `live_trading/runner.py:~605` | ✅ |
| Réconciliation périodique toutes les 5 minutes | `live_trading/runner.py:353-354` | ✅ |
| Venv + Makefile + pytest task VS Code documéntés | `Makefile + .vscode/tasks.json` | ✅ |
| `KillSwitch.reset()` existe mais pas de wrapper CLI | `risk/facade.py:reset_kill_switch()` | ⚠️ |
| `_reconciler` reste `None` silencieusement si init échoue | `live_trading/runner.py:~570` | ⚠️ |
| SIGTERM non capturé directement (via `ShutdownManager` pattern seulement) | `execution/shutdown_manager.py` | ⚠️ |
| Pas de runbook documenté pour redémarrage post kill-switch | Docs / README | ⚠️ |

**Score C10 : 7.5 / 10**

---

## TABLEAU DE SYNTHÈSE DES ANOMALIES

| ID | Critère | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|---|---|---|---|---|---|---|
| CERT-01 | C3, C6 | 11 tests Cython échouent — `brownian_bridge_batch_fast` et `compute_zscore_last_fast` absents du `.pyd` compilé | `tests/models/` | 🔴 BLOQUANT | Live mode garde en place mais tests faux-positifs permanents | Faible — recompiler `setup.py build_ext --inplace` et vérifier `.pyx` |
| CERT-02 | C3 | v48 OOS 2024H2 : 0 trades générés, Sharpe=0, verdict FAIL — pas de validation d'alpha récente | `results/v48_p5_results.txt` | 🔴 BLOQUANT | Impossible de certifier un alpha live sans résultat OOS valide | Moyen — diagnostiquer pipeline (filtres trop stricts ?) |
| CERT-03 | C2 | Double comptage drawdown : `PortfolioRiskManager` (T1=10%) + `RiskEngine` dans `RiskFacade` suivent le DD indépendamment | `live_trading/runner.py:302-318` | 🟠 MAJEUR | Seuils T1 pourraient diverger si equity synced différemment | Moyen — unifier via `RiskFacade` uniquement |
| CERT-04 | C7 | Endpoint Flask exposant `to_prometheus_format()` non confirmé — scraping Prometheus peut être silencieusement brisé | `monitoring/api.py` | 🟠 MAJEUR | Prometheus ne scrape rien si route absente — observabilité aveugle | Faible — vérifier `monitoring/api.py` + ajouter route |
| CERT-05 | C10 | Pas de CLI pour `KillSwitch.reset()` — l'opérateur doit modifier le code ou appeler l'API interne | `risk/facade.py:reset_kill_switch()` | 🟠 MAJEUR | En incident, délai de reprise inutile | Faible — ajouter `scripts/reset_kill_switch.py` |
| CERT-06 | C5, C3 | `Signal.timestamp = datetime.now()` sans `timezone.utc` — viole la règle absolue du projet | `signal_engine/generator.py:55` | 🟡 MINEUR | DeprecationWarning en Python 3.12+, timestamps naive en prod | Trivial — `datetime.now(timezone.utc)` |
| CERT-07 | C5 | `monitoring/logger.py:10` — `datetime.now()` sans UTC dans le formatter de log | `monitoring/logger.py:10` | 🟡 MINEUR | Timestamps log naive | Trivial |
| CERT-08 | C8 | Yahoo Finance fallback non documenté dans `data/loader.py` — si IBKR KO + cache vide, `DataUnavailableError` | `data/loader.py:~90` | 🟡 MINEUR | Résilience données en cas de panne IBKR prolongée | Faible — documenter ou ajouter yfinance fallback |
| CERT-09 | C10 | `self._reconciler` reste `None` silencieusement si init échoue — `_maybe_reconcile()` saute sans alerte | `live_trading/runner.py:~570` | 🟡 MINEUR | Réconciliation nulle non détectée | Trivial — ajouter log WARNING si reconciler None au tick |
| CERT-10 | C5 | `mypy ignore_errors=True` sur `signal_engine.*`, `strategies.*`, `monitoring.*` — bugs silencieux potentiels dans la logique de signal | `pyproject.toml:~50-60` | 🟡 MINEUR | Régression de type non détectée dans le signal engine | Moyen — activer mypy progressivement |

---

## TABLEAU DE NOTATION

| Critère | Description | Score | Statut |
|---|---|---|---|
| **C1** | Robustesse exécution IBKR | **9.0 / 10** | ✅ CERTIFIÉ |
| **C2** | Risk management & kill-switch | **8.5 / 10** | ✅ CERTIFIÉ |
| **C3** | Intégrité backtest (no look-ahead) | **6.5 / 10** | 🔴 BLOQUÉ |
| **C4** | Infrastructure & DevOps | **8.5 / 10** | ✅ CERTIFIÉ |
| **C5** | Qualité de code & architecture | **7.0 / 10** | 🟠 CONDITIONNEL |
| **C6** | Tests & couverture | **7.0 / 10** | 🔴 BLOQUÉ |
| **C7** | Observabilité & monitoring | **7.5 / 10** | 🟠 CONDITIONNEL |
| **C8** | Intégrité des données | **8.0 / 10** | ✅ CERTIFIÉ |
| **C9** | Sécurité | **8.5 / 10** | ✅ CERTIFIÉ |
| **C10** | Maturité opérationnelle | **7.5 / 10** | 🟠 CONDITIONNEL |
| **TOTAL** | | **78.0 / 100** | |

---

## CERTIFICATION FINALE

```
╔══════════════════════════════════════════════════════════════╗
║          EDGECORE V1 — GRILLE DE CERTIFICATION               ║
║                                                              ║
║  Score global : 78.0 / 100                                   ║
║                                                              ║
║  VERDICT : ❌ CONDITIONNEL — NON CERTIFIÉ                    ║
║                                                              ║
║  Seuil CERTIFIÉ : ≥ 85 / 100                                 ║
║  Seuil CONDITIONNEL : 70–84 / 100                            ║
║  Seuil BLOQUÉ : < 70 / 100                                   ║
╚══════════════════════════════════════════════════════════════╝
```

### CONDITIONS DE CERTIFICATION (délai recommandé : 14 jours ouvrés)

#### 🔴 BLOQUANTS — À corriger AVANT tout trading live avec capital réel

1. **CERT-01** — Recompiler l'extension Cython et corriger les exports manquants (`brownian_bridge_batch_fast`, `compute_zscore_last_fast`) dans `models/cointegration_fast.pyx`. Relancer `venv\Scripts\python.exe setup.py build_ext --inplace` et vérifier que les 11 tests repassent.
2. **CERT-02** — Diagnostiquer et corriger le backtest v48 (0 trades sur 2024H2). Cause probable : filtre Johansen + Newey-West HAC trop strict sur l'univers actuel, ou problème de chargement des données de référence. Objectif : obtenir un résultat OOS 2024–2025 avec Sharpe > 0.5 et ≥ 50 trades.

#### 🟠 MAJEURS — À corriger avant augmentation du capital

3. **CERT-03** — Unifier le suivi du drawdown via `RiskFacade` uniquement ; supprimer le double comptage avec `PortfolioRiskManager` ou les synchroniser explicitement.
4. **CERT-04** — Confirmer (ou ajouter) la route Flask `/metrics` dans `monitoring/api.py` qui retourne `SystemMetrics.to_prometheus_format()` — valider le scraping Prometheus en docker-compose.
5. **CERT-05** — Créer `scripts/reset_kill_switch.py` avec confirmation interactive pour permettre la reprise opérationnelle sans accès au code source.

#### 🟡 MINEURS — À corriger dans les 30 jours calendaires

6. **CERT-06** — `signal_engine/generator.py:55` : `datetime.now()` → `datetime.now(timezone.utc)`
7. **CERT-07** — `monitoring/logger.py:10` : idem
8. **CERT-08** — Documenter ou implémenter le fallback Yahoo Finance dans `data/loader.py`
9. **CERT-09** — Ajouter `logger.warning("reconciler_not_initialized")` si `self._reconciler is None` dans `_maybe_reconcile()`
10. **CERT-10** — Plan d'activation progressive mypy sur `signal_engine.*` (au minimum `warn_return_any=true`)

---

### POINTS FORTS À PRÉSERVER

- **Reconnect IBKR** : implémentation [5,15,30]s + jitter institutionnelle — ne pas toucher
- **Audit trail HMAC** : intégrité cryptographique en prod avec fsync — pattern de référence
- **Walk-forward expanding window** : zéro fuite de données, fresh instance par période — correct
- **3-tier risk architecture** : T1/T2/T3 cohérents et assertés au démarrage — à maintenir
- **CI/CD** : ruff + mypy scoped + pyright + pip-audit + trufflehog + coverage gate — pipeline complet
- **Kill-switch shared instance** (correctif B2-02) : un seul état de halt — crucial

---

*Audit généré automatiquement par GitHub Copilot (Claude Sonnet 4.6) — 2026-07-14*  
*Basé sur l'analyse de 320+ fichiers Python, 152 fichiers de test, 2734 tests collectés*
