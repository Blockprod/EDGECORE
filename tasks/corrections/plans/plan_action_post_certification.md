---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: plan_action_post_certification.md
derniere_revision: 2026-04-05
creation: 2026-04-05 à 00:00
---

# PLAN D'ACTION — POST-CERTIFICATION EDGECORE V1
**Source** : `tasks/audits/resultats/audit_certification_edgecore.md`  
**Score initial** : 78 / 100 — CONDITIONNEL  
**Objectif** : atteindre ≥ 85 / 100 pour certification complète  
**Date cible** : 2026-04-19 (14 jours ouvrés)

---

## PHASES & PRIORITÉS

```
Phase 1 — Bloquants (J1–J3)      → CERT-01 + CERT-02
Phase 2 — Majeurs   (J4–J8)      → CERT-03 + CERT-04 + CERT-05
Phase 3 — Mineurs   (J9–J14)     → CERT-06 à CERT-10
```

---

## PHASE 1 — BLOQUANTS (J1–J3)

> ⛔ Aucun trading live avec capital réel avant la résolution complète de cette phase.

---

### CERT-01 — Cython : fonctions manquantes dans le `.pyd` compilé
**Critères impactés** : C3, C6  
**Sévérité** : 🔴 BLOQUANT  
**Fichiers** : `models/cointegration_fast.pyx`, `setup.py`

#### Problème
Les fonctions `brownian_bridge_batch_fast` et `compute_zscore_last_fast` sont absentes du `.pyd` compilé (`models/cointegration_fast.cp311-win_amd64.pyd`), ce qui provoque 11 échecs de tests dans `tests/models/`. Le module Python source les définit mais elles ne sont pas exportées correctement lors de la compilation.

#### Actions

- [ ] **1.1** Ouvrir `models/cointegration_fast.pyx` et vérifier que `brownian_bridge_batch_fast` et `compute_zscore_last_fast` sont déclarées `cpdef` ou `def` (pas `cdef` seul)
- [ ] **1.2** Si `cdef` seul → les passer en `cpdef` pour les exposer à Python
- [ ] **1.3** Supprimer les artefacts compilés obsolètes :
  ```powershell
  Remove-Item models\cointegration_fast.cp311-win_amd64.pyd -ErrorAction SilentlyContinue
  Remove-Item models\cointegration_fast.cp313-win_amd64.pyd -ErrorAction SilentlyContinue
  Remove-Item -Recurse build\ -ErrorAction SilentlyContinue
  ```
- [ ] **1.4** Recompiler :
  ```powershell
  venv\Scripts\python.exe setup.py build_ext --inplace
  ```
- [ ] **1.5** Vérifier les exports :
  ```powershell
  venv\Scripts\python.exe -c "from models.cointegration_fast import brownian_bridge_batch_fast, compute_zscore_last_fast; print('OK')"
  ```
- [ ] **1.6** Relancer les tests ciblés :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/models/ -q
  ```
- [ ] **1.7** Relancer la suite complète — valider 0 fail Cython :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/ -q
  ```

**Critère de succès** : `tests/models/` entièrement vert, 0 fail Cython dans la suite complète.

---

### CERT-02 — Backtest v48 : 0 trades générés sur OOS 2024H2
**Critères impactés** : C3  
**Sévérité** : 🔴 BLOQUANT  
**Fichiers** : `backtests/strategy_simulator.py`, `config/dev.yaml`, `pair_selection/discovery.py`

#### Problème
Le backtest v48 période P5 (2024H2) génère 0 trades et un Sharpe de 0.00, rendant la validation d'alpha OOS impossible. Cause probable : filtres Johansen + Newey-West HAC trop stricts pour l'univers actuel en 2024H2, ou problème de chargement des données.

#### Actions

- [ ] **2.1** Relancer le backtest v48 en mode debug en activant les logs de rejet de paires :
  ```powershell
  $env:EDGECORE_ENV = "dev"
  venv\Scripts\python.exe scripts\run_backtest.py --period P5 --debug-pairs 2>&1 | Select-String "rejected|no_pairs|coint|discovery"
  ```
- [ ] **2.2** Vérifier le nombre de paires découvertes en P5 :
  - Si 0 paires → le filtrage Johansen/HAC est trop strict pour 2024H2
  - Si paires mais 0 signaux → les seuils de z-score entry sont trop élevés
- [ ] **2.3** Si filtrage trop strict → relancer en désactivant temporairement `newey_west_consensus` dans `config/dev.yaml` :
  ```yaml
  strategy:
    newey_west_consensus: false
    johansen_confirmation: false
  ```
  Valider que des paires sont trouvées.
- [ ] **2.4** Si seuil z-score trop élevé → tester avec `entry_z_score: 1.5` dans `config/dev.yaml`
- [ ] **2.5** Recalibrer les filtres pour obtenir un résultat OOS 2024–2025 avec :
  - Sharpe ≥ 0.5
  - ≥ 50 trades
  - Max drawdown < 15%
- [ ] **2.6** Une fois les paramètres identifiés, documenter la configuration dans `config/prod.yaml` et créer `results/v49_p5_recalibrated.txt`

**Critère de succès** : backtest OOS 2024–2025 avec Sharpe ≥ 0.5 et ≥ 50 trades, résultat documenté dans `results/`.

---

## PHASE 2 — MAJEURS (J4–J8)

---

### CERT-03 — Double comptage du drawdown (PortfolioRiskManager + RiskEngine)
**Critères impactés** : C2  
**Sévérité** : 🟠 MAJEUR  
**Fichiers** : `live_trading/runner.py`, `risk/facade.py`, `risk_engine/portfolio_risk.py`

#### Problème
`PortfolioRiskManager` (T1 = 10%) et `RiskEngine` dans `RiskFacade` suivent le drawdown indépendamment avec des équités initialisées séparément. En cas de divergence de synchro, les seuils T1 peuvent déclencher à des moments différents.

#### Actions

- [ ] **3.1** Lire `risk/engine.py` et `risk_engine/portfolio_risk.py` pour cartographier exactement quel champ calcule le DD dans chaque module
- [ ] **3.2** Décider de la stratégie de consolidation :
  - **Option A** (recommandée) : `PortfolioRiskManager` reste l'unique source de vérité pour le DD. `RiskFacade.can_enter_trade()` délègue à `PortfolioRiskManager.can_open_position()` au lieu de `RiskEngine.can_enter_trade()`
  - **Option B** : synchroniser `RiskEngine.equity` à chaque `update_equity()` appelé sur `PortfolioRiskManager`
- [ ] **3.3** Implémenter l'option choisie
- [ ] **3.4** Ajouter un test dans `tests/risk/` qui vérifie que le même événement de drawdown déclenche exactement un halt (ni zéro, ni deux)
- [ ] **3.5** Relancer les tests risk :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/risk/ tests/risk_engine/ -q
  ```

**Critère de succès** : un seul compteur DD canonique, test de non-régression passant.

---

### CERT-04 — Route Prometheus `/metrics` non confirmée
**Critères impactés** : C7  
**Sévérité** : 🟠 MAJEUR  
**Fichiers** : `monitoring/api.py`, `monitoring/metrics.py`

#### Problème
`SystemMetrics.to_prometheus_format()` existe mais aucune route Flask n'est confirmée pour l'exposer. Prometheus ne peut pas scraper si l'endpoint est absent ou non configuré.

#### Actions

- [ ] **4.1** Lire `monitoring/api.py` en entier — vérifier si `/metrics` ou `/health` existe déjà
- [ ] **4.2** Si la route n'existe pas, l'ajouter :
  ```python
  @app.route("/metrics")
  def metrics_endpoint():
      from monitoring.metrics import SystemMetrics
      # Récupérer l'instance singleton si elle existe
      metrics = _get_metrics_instance()  # à implémenter selon le pattern existant
      return metrics.to_prometheus_format(), 200, {"Content-Type": "text/plain; version=0.0.4"}
  ```
- [ ] **4.3** Vérifier que `prometheus.yml` cible bien `trading-engine:5000/metrics` :
  ```yaml
  scrape_configs:
    - job_name: 'edgecore'
      static_configs:
        - targets: ['trading-engine:5000']
      metrics_path: '/metrics'
  ```
- [ ] **4.4** Tester localement :
  ```powershell
  venv\Scripts\python.exe -c "from monitoring.api import initialize_dashboard_api; print('OK')"
  ```
- [ ] **4.5** Ajouter un test d'intégration simple vérifiant que la route retourne HTTP 200 avec `Content-Type: text/plain`

**Critère de succès** : `GET /metrics` retourne HTTP 200 avec le format texte Prometheus valide.

---

### CERT-05 — Absence de CLI pour `KillSwitch.reset()`
**Critères impactés** : C10  
**Sévérité** : 🟠 MAJEUR  
**Fichiers** : `scripts/` (à créer), `risk/facade.py`

#### Problème
Après activation du kill-switch, l'opérateur doit accéder au code Python pour réinitialiser l'état. Il n'existe pas de script CLI avec confirmation interactive.

#### Actions

- [ ] **5.1** Créer `scripts/reset_kill_switch.py` :
  ```python
  """Réinitialise manuellement le kill-switch après résolution d'un incident.

  Usage:
      venv\\Scripts\\python.exe scripts\\reset_kill_switch.py [--force]
  """
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).parent.parent))

  from risk_engine.kill_switch import KillSwitch
  from structlog import get_logger

  logger = get_logger(__name__)

  def main():
      ks = KillSwitch()
      if not ks.is_active:
          print("Kill-switch inactif — aucune action requise.")
          return
      print(f"Kill-switch ACTIF : raison = {ks.reason}")
      if "--force" not in sys.argv:
          confirm = input("Confirmer la réinitialisation ? (oui/non) : ").strip().lower()
          if confirm != "oui":
              print("Annulé.")
              return
      ks.reset()
      logger.info("kill_switch_reset_manual")
      print("Kill-switch réinitialisé.")

  if __name__ == "__main__":
      main()
  ```
- [ ] **5.2** Tester le script :
  ```powershell
  venv\Scripts\python.exe scripts\reset_kill_switch.py
  ```
- [ ] **5.3** Documenter dans `README.md` (section Opérations) :
  ```markdown
  ## Réinitialiser le kill-switch
  venv\Scripts\python.exe scripts\reset_kill_switch.py
  ```

**Critère de succès** : script fonctionnel avec confirmation interactive, documenté dans README.

---

## PHASE 3 — MINEURS (J9–J14)

---

### CERT-06 — `Signal.timestamp` sans timezone UTC
**Critères impactés** : C5, C3  
**Sévérité** : 🟡 MINEUR  
**Fichier** : `signal_engine/generator.py:55`

#### Action
```python
# Avant
timestamp: datetime = field(default_factory=datetime.now)

# Après
from datetime import timezone
timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **6.1** Appliquer le correctif dans `signal_engine/generator.py`
- [ ] **6.2** Vérifier qu'aucun test compare `timestamp` avec une naive datetime
- [ ] **6.3** Relancer `venv\Scripts\python.exe -m pytest tests/signal_engine/ -q`

---

### CERT-07 — `monitoring/logger.py` : `datetime.now()` sans UTC
**Critères impactés** : C5  
**Sévérité** : 🟡 MINEUR  
**Fichier** : `monitoring/logger.py:10`

#### Action
```python
# Avant
f"{log_dir}/{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Après
from datetime import timezone
f"{log_dir}/{name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.log"
```

- [ ] **7.1** Appliquer le correctif dans `monitoring/logger.py`
- [ ] **7.2** Relancer `venv\Scripts\python.exe -m pytest tests/monitoring/ -q`

---

### CERT-08 — Stratégie de fallback data documentée et renforcée dans `data/loader.py`
**Critères impactés** : C8  
**Sévérité** : 🟡 MINEUR  
**Fichier** : `data/loader.py`

> ⚠️ **Règle absolue** : Yahoo Finance (ou tout fournisseur non-professionnel) est interdit. La seule source de données autorisée est IBKR. Le cache disque parquet est le seul mécanisme de résilience.

#### Actions

- [ ] **8.1** Documenter explicitement la stratégie 2-niveaux dans le docstring de `load_price_data()` :
  - Niveau 1 : IBKR `reqHistoricalData` (source canonique)
  - Niveau 2 : cache disque parquet `data/cache/<sym>_<tf>.parquet` (fallback si IBKR injoignable)
  - Aucun niveau 3 : lever `DataUnavailableError` si les deux niveaux échouent
- [ ] **8.2** Vérifier que le TTL du cache est respecté — rejeter les fichiers parquet dont l'horodatage dépasse `max_stale` :
  ```python
  cache_mtime = datetime.fromtimestamp(_cache_file.stat().st_mtime, tz=UTC)
  if datetime.now(UTC) - cache_mtime > max_stale:
      logger.warning("load_price_data_cache_stale_rejected", symbol=sym, age_hours=...)
      s = None  # forcer DataUnavailableError
  ```
- [ ] **8.3** S'assurer que `DataUnavailableError` est bien levée (pas avalée silencieusement) quand les deux niveaux échouent, et que le caller dans `live_trading/runner.py` la propage correctement vers le kill-switch de données stale (`KillReason.DATA_STALE`)

---

### CERT-09 — `_maybe_reconcile()` silencieux si `_reconciler` est None
**Critères impactés** : C10  
**Sévérité** : 🟡 MINEUR  
**Fichier** : `live_trading/runner.py`

#### Action
Ajouter un log WARNING dans `_maybe_reconcile()` si le reconciler n'est pas initialisé :

- [ ] **9.1** Localiser `_maybe_reconcile()` dans `live_trading/runner.py`
- [ ] **9.2** Ajouter en tête de méthode :
  ```python
  if self._reconciler is None:
      logger.warning("reconciler_not_initialized_skipping_reconciliation")
      return
  ```
- [ ] **9.3** Relancer `venv\Scripts\python.exe -m pytest tests/live_trading/ -q`

---

### CERT-10 — Plan d'activation progressive mypy sur `signal_engine.*`
**Critères impactés** : C5  
**Sévérité** : 🟡 MINEUR  
**Fichier** : `pyproject.toml`

#### Actions

- [ ] **10.1** Changer `ignore_errors=True` → `warn_return_any=false, disallow_untyped_defs=false` sur `signal_engine.*` dans `pyproject.toml` (niveau intermédiaire — ne casse pas le CI mais détecte les erreurs évidentes)
- [ ] **10.2** Lancer `mypy signal_engine/ --ignore-missing-imports --no-error-summary` et recenser les erreurs
- [ ] **10.3** Corriger les erreurs critiques (types de retour incorrects, variables non typées dans les chemins chauds)
- [ ] **10.4** Activer en CI : ajouter `signal_engine/` à la commande mypy existante dans `.github/workflows/main.yml`

---

## VÉRIFICATION FINALE

Une fois toutes les phases terminées, exécuter la séquence de validation complète :

```powershell
# 1. Tests complets
venv\Scripts\python.exe -m pytest tests/ -q

# 2. Aucun DeprecationWarning datetime.utcnow
venv\Scripts\python.exe -m pytest tests/ -W error::DeprecationWarning -q

# 3. Risk tier coherence
venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"

# 4. Cython extensions
venv\Scripts\python.exe -c "from models.cointegration_fast import brownian_bridge_batch_fast, compute_zscore_last_fast; print('Cython OK')"

# 5. Kill-switch CLI
venv\Scripts\python.exe scripts\reset_kill_switch.py

# 6. Config prod
$env:EDGECORE_ENV = "prod"; venv\Scripts\python.exe -c "from config.settings import get_settings; s=get_settings(); print(s.strategy.entry_z_score)"
```

**Score attendu post-corrections** : ≥ 87 / 100 — CERTIFIÉ

---

## SUIVI D'AVANCEMENT

| ID | Phase | Action | Responsable | Statut | Date |
|---|---|---|---|---|---|
| CERT-01 | P1 | Corriger Cython exports | — | ✅ done | 2026-04-05 |
| CERT-02 | P1 | Diagnostiquer backtest v48 0-trades | — | 🔄 partial | 2026-04-05 |
| CERT-03 | P2 | Unifier compteur drawdown | — | ✅ done | 2026-04-05 |
| CERT-04 | P2 | Confirmer/créer route `/metrics` Flask | — | ✅ done | 2026-04-05 |
| CERT-05 | P2 | Créer `scripts/reset_kill_switch.py` | — | ✅ done | 2026-04-05 |
| CERT-06 | P3 | Fix `Signal.timestamp` UTC | — | ✅ done | 2026-04-05 |
| CERT-07 | P3 | Fix `monitoring/logger.py` UTC | — | ✅ done | 2026-04-05 |
| CERT-08 | P3 | Fallback Yahoo Finance | — | ✅ done | 2026-04-05 |
| CERT-09 | P3 | Log WARNING reconciler None | — | ✅ done | 2026-04-05 |
| CERT-10 | P3 | Activer mypy sur signal_engine | — | ✅ done | 2026-04-05 |

---

*Généré à partir de `tasks/audits/resultats/audit_certification_edgecore.md` — 2026-04-05*
