---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/corrections/plans/PLAN_ACTION_audit_final_upgrade_edgecore_2026-04-04.md
derniere_revision: 2026-04-04
creation: 2026-04-04
---

# PLAN D'ACTION — EDGECORE — 2026-04-04
**Sources** : `tasks/audits/resultats/audit_final_upgrade_edgecore.md`
**Total** : 🔴 4 · 🟠 6 · 🟡 3 · **Effort estimé : 9.5 jours**

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Supprimer la fuite credentials — common/secrets.py:512
**Fichier** : `common/secrets.py:512`
**Problème** : `print(api_key)` expose la clé API IBKR en clair dans stdout, CI/CD logs, Docker logs et terminal recordings.
**Correction** : Remplacer par `logger.debug("api_key_loaded", masked=api_key[:4] + "****")` ou supprimer la ligne si debug non nécessaire.
**Validation** :
```powershell
Select-String -Path common/secrets.py -Pattern "print\(api_key"
# Attendu : aucun résultat

venv\Scripts\python.exe -m pytest tests/ -x -q -k "secret"
# Attendu : tous les tests secrets passent
```
**Dépend de** : Aucune
**Statut** : ⏳

---

### [C-02] Supprimer print() violation — execution/position_stops.py:477-481
**Fichier** : `execution/position_stops.py:477-481`
**Problème** : Banner de module-load imprimé à chaque import en production. Non filtrable, pollue stdout et les logs CI.
**Correction** : Supprimer les 5 lignes `print(...)` du bloc module-load (lignes 477-481). Si un signal de chargement est nécessaire, utiliser `logger.debug("position_stops_module_loaded")`.
**Validation** :
```powershell
Select-String -Path execution/position_stops.py -Pattern "print\("
# Attendu : aucun résultat

venv\Scripts\python.exe -m pytest tests/execution/ -x -q
# Attendu : tous les tests execution passent
```
**Dépend de** : Aucune
**Statut** : ⏳

---

### [C-03] Supprimer print() debug — pair_selection/discovery.py:117
**Fichier** : `pair_selection/discovery.py:117`
**Problème** : `print(p.pair_key, p.half_life)` — instruction de debug oubliée, exécutée à chaque découverte de paires en production.
**Correction** : Remplacer par `logger.debug("pair_discovery_candidate", pair_key=p.pair_key, half_life=p.half_life)`.
**Validation** :
```powershell
Select-String -Path pair_selection/discovery.py -Pattern "print\("
# Attendu : aucun résultat

venv\Scripts\python.exe -m pytest tests/ -x -q -k "discovery or pair_selection"
# Attendu : tous les tests pair_selection passent
```
**Dépend de** : Aucune
**Statut** : ⏳

---

### [C-04] Aligner les seuils de signal backtest ↔ live
**Fichier** : `backtests/strategy_simulator.py:230-231`
**Problème** : Le backtest utilise `entry_threshold=0.30, exit_threshold=0.12` — seuils sur le signal combiné normalisé (0-1). Le live utilise `entry_z_score=2.0, exit_z_score=0.5` — seuils sur le z-score brut. Ce sont deux échelles différentes : les métriques Sharpe=1.33 / PF=4.22 ne prédisent pas le comportement live.
**Correction** : Deux options mutuellement exclusives — choisir avant d'implémenter :
- **Option A (recommandée)** : Dans le simulateur, remplacer les thresholds hardcodés par `get_settings().strategy.entry_z_score` et `exit_z_score`, et s'assurer que le SimulationLoop applique le même pipeline SignalGenerator+SignalCombiner que le live path.
- **Option B (documentaire)** : Ajouter un commentaire explicite dans `strategy_simulator.py` documentant que `entry_threshold=0.30` est le seuil sur le signal combiné (≠ z-score brut du live) et que les métriques historiques ne doivent pas être comparées directement au live.

> ⚠️ Option A nécessite de re-backtester pour mettre à jour `tests/regression/fixtures/bt_v36_output.json`.

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/regression/test_equity_curve_regression.py -q
# Si Option A : mettre à jour le baseline après re-run

venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2808+ passed, 0 failed
```
**Dépend de** : Aucune (si Option B) / [C-14] si Option A
**Statut** : ⏳

---

## PHASE 2 — MAJEURES 🟠

### [C-05] Supprimer print() debug — strategies/pair_trading.py:895,902
**Fichier** : `strategies/pair_trading.py:895, 902`
**Problème** : `print(f"[DEBUG] generate_signals: ...")` et `print(f"[DEBUG] Cointegrated pairs: ...")` — tags debug non nettoyés, exécutés à chaque barre en production.
**Correction** : Supprimer ou remplacer par `logger.debug(...)` avec les mêmes informations.
**Validation** :
```powershell
Select-String -Path strategies/pair_trading.py -Pattern "print\(" | Where-Object { $_.Line -match "\[DEBUG\]" }
# Attendu : aucun résultat

venv\Scripts\python.exe -m pytest tests/strategies/ -x -q
# Attendu : tous les tests strategies passent
```
**Dépend de** : Aucune
**Statut** : ⏳

---

### [C-06] Supprimer print() debug — models/ou_model.py:222-223
**Fichier** : `models/ou_model.py:222-223`
**Problème** : `print(f"Estimated Half-Life: ...")` et `print(f"OU Parameters: ...")` — sortie console sur chaque fit du modèle OU.
**Correction** : Remplacer par `logger.debug("ou_model_fit", half_life=hl, params=str(params))`.
**Validation** :
```powershell
Select-String -Path models/ou_model.py -Pattern "print\("
# Attendu : aucun résultat

venv\Scripts\python.exe -m pytest tests/models/ -x -q
# Attendu : tous les tests models passent
```
**Dépend de** : Aucune
**Statut** : ⏳

---

### [C-07] Passer typeCheckingMode à "standard"
**Fichier** : `pyrightconfig.json`
**Problème** : `"typeCheckingMode": "basic"` manque ~30% des erreurs de type qu'attrape `"standard"`. Contribue directement à la dette des 147 `# type: ignore` (certains masquent des erreurs réelles non détectées en basic).
**Correction** :
1. Changer `"typeCheckingMode": "basic"` → `"typeCheckingMode": "standard"` dans `pyrightconfig.json`
2. Lancer pyright sur tout le workspace
3. Corriger les nouvelles erreurs émergentes (utiliser `cast()`, Protocol, assert, TypeGuard plutôt que `# type: ignore`)
4. Objectif : réduire `# type: ignore` production de ~35 à <10
**Validation** :
```powershell
venv\Scripts\python.exe -m pyright --outputjson 2>$null | ConvertFrom-Json | Select-Object -ExpandProperty summary
# Attendu : errorCount: 0

venv\Scripts\python.exe -m pytest tests/ -q
# Attendu : 2808+ passed
```
**Dépend de** : Aucune (peut être lancé indépendamment)
**Statut** : ⏳

---

### [C-08] Documenter ou corriger les `# type: ignore` non justifiés — live_trading/runner.py
**Fichier** : `live_trading/runner.py` (7 occurrences)
**Problème** : 7 `# type: ignore[attr-defined]` sur des résultats de `hasattr()` — pattern corrigible avec `cast()` ou `isinstance()` guard.
**Correction** : Pour chaque `# type: ignore[attr-defined]` :
- Si `hasattr(obj, 'method')` → remplacer par une vérification typée : `if isinstance(obj, SpecificType): obj.method()`
- Ou utiliser `cast(SpecificType, obj).method()` si la vérification hasattr garantit le type
**Validation** :
```powershell
Select-String -Path live_trading/runner.py -Pattern "type: ignore"
# Attendu : 0 occurrences (ou <3 avec justification traceable)

venv\Scripts\python.exe -m pytest tests/live_trading/ -x -q
# Attendu : tous les tests live_trading passent
```
**Dépend de** : [C-07] (recommandé en premier pour détecter les vrais besoins)
**Statut** : ⏳

---

### [C-09] Ajouter guard Cython dans la trading loop
**Fichier** : `live_trading/runner.py` (méthode `_trading_loop`)
**Problème** : Si `CYTHON_AVAILABLE=False`, le scan O(N²) de 741 paires en Python pur risque de dépasser le délai de bar. Le système continue sans protection. Possible look-ahead bias par accumulation de retard.
**Correction** : Dans `_initialize()` ou au démarrage de `_trading_loop()`, ajouter :
```python
from models import CYTHON_AVAILABLE
if not CYTHON_AVAILABLE:
    logger.warning(
        "cython_unavailable_trading_paused",
        message="Cython non disponible — performance insuffisante pour trading live. "
                "Recompiler avec: venv\\Scripts\\python.exe setup.py build_ext --inplace"
    )
    # Si mode live (pas paper), lever une exception ou retourner False
    if self._mode == ExecutionMode.LIVE:
        raise RuntimeError("Cython requis pour le trading live avec 39 paires")
```
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/live_trading/ -x -q
# Attendu : tous les tests live_trading passent

# Simuler Cython absent :
$env:EDGECORE_FORCE_PYTHON = "1"
venv\Scripts\python.exe -c "from live_trading.runner import LiveTradingRunner; print('OK')"
```
**Dépend de** : Aucune
**Statut** : ⏳

---

### [C-10] Implémenter reversal automatique sur jambe divergente
**Fichier** : `execution/ibkr_engine.py` (chemin d'exécution des paires)
**Problème** : Si Leg 2 d'une paire est rejeté (stock halté, HTB non disponible) après que Leg 1 a été exécuté, la position Leg 1 reste ouverte et non couverte. Aucun mécanisme de reversal automatique identifié.
**Correction** :
1. Dans la méthode d'exécution d'une paire, après le timeout d'attente de confirmation Leg 2 :
   - Détecter que l'ordre Leg 2 n'est pas filled/confirmed dans le délai imparti
   - Émettre un ordre de clôture de Leg 1 (direction inverse, taille exacte filled)
   - Logger l'incident : `logger.error("pair_leg_divergence", leg1=..., leg2_status=..., action="reversal")`
   - Notifier via le système d'alertes existant
2. Écrire un test couvrant ce scénario (mock Leg 2 timeout)
**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/execution/ -x -q -k "leg or pair_execution"
# Attendu : tests leg divergence présents et passants

venv\Scripts\python.exe -m pytest tests/ -q
# Attendu : 2808+ passed
```
**Dépend de** : Aucune
**Statut** : ⏳

---

## PHASE 3 — MINEURES 🟡

### [C-11] Extraire stability_threshold vers la config
**Fichier** : `strategies/pair_trading.py:694`
**Problème** : `stability_threshold = 0.8` — valeur hardcodée, non ajustable sans modifier le code source.
**Correction** :
1. Ajouter `stability_threshold: float = 0.8` dans `StrategyConfig` (config/settings.py)
2. Lire `get_settings().strategy.stability_threshold` à la ligne 694
3. Mettre à jour `config/config.yaml` avec la nouvelle clé
**Validation** :
```powershell
venv\Scripts\python.exe -c "from config.settings import get_settings; print(get_settings().strategy.stability_threshold)"
# Attendu : 0.8

venv\Scripts\python.exe -m pytest tests/strategies/ -x -q
# Attendu : tous les tests strategies passent
```
**Dépend de** : Aucune
**Statut** : ⏳

---

### [C-12] Exposer exports dans execution/__init__.py
**Fichier** : `execution/__init__.py`
**Problème** : Fichier vide — aucun export. `execution_engine/router.py` importe directement depuis les sous-modules. Interface instable : si la structure interne change, les importeurs cassent sans warning.
**Correction** : Ajouter les exports fondamentaux :
```python
from execution.base import Order, OrderStatus, Fill
from execution.paper_engine import PaperExecutionEngine
from execution.ibkr_engine import IBKRExecutionEngine

__all__ = ["Order", "OrderStatus", "Fill", "PaperExecutionEngine", "IBKRExecutionEngine"]
```
**Validation** :
```powershell
venv\Scripts\python.exe -c "from execution import Order, OrderStatus, PaperExecutionEngine; print('OK')"
# Attendu : OK

venv\Scripts\python.exe -m pytest tests/execution/ -x -q
# Attendu : tous les tests execution passent
```
**Dépend de** : Aucune
**Statut** : ⏳

---

### [C-13] Extraire acceptance_threshold OOS vers la config
**Fichier** : `backtester/oos.py:70`
**Problème** : `acceptance_threshold=0.70` hardcodé — non ajustable via config YAML.
**Correction** :
1. Ajouter `oos_acceptance_threshold: float = 0.70` dans `BacktestConfig` ou créer `OOSConfig` dans config/settings.py
2. Lire depuis `get_settings().backtest.oos_acceptance_threshold`
**Validation** :
```powershell
venv\Scripts\python.exe -c "from config.settings import get_settings; print(get_settings().backtest.oos_acceptance_threshold)"
# Attendu : 0.7

venv\Scripts\python.exe -m pytest tests/ -x -q -k "oos"
# Attendu : tous les tests OOS passent
```
**Dépend de** : Aucune
**Statut** : ⏳

---

## CORRECTIF HORS BATCH — Optionnel (décision architecturale)

### [C-14] Implémenter walk-forward réel — backtests/walk_forward.py
**Fichier** : `backtests/walk_forward.py`
**Problème** : Stub avec TODO B-1. L'OOS basique dans `backtester/oos.py` ne remplace pas un walk-forward rolling. Les claims de validation walk-forward dans les docs sont non vérifiables.
**Correction** : Implémenter rolling window train/test split : paramètres `train_periods`, `test_periods`, `step_size`. Appeler `BacktestRunner` sur chaque window. Agréger métriques OOS. Produire rapport comparatif.
**Effort** : 16h — décision architecturale requise avant démarrage
**Dépend de** : [C-04] (aligner d'abord les seuils backtest ↔ live)
**Statut** : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
Sprint 1 — Sécurité + Quick wins (< 1 journée)
  C-01 → C-02 → C-03 → C-05 → C-06
  (Suppression fuite credentials + tous print() prod)

Sprint 2 — Intégrité backtest (1 journée — décision requise sur Option A/B)
  C-04 (choisir Option A ou B avant de commencer)

Sprint 3 — Type safety (2 jours)
  C-07 → C-08
  (typeCheckingMode standard → corriger erreurs émergentes → réduire type:ignore)

Sprint 4 — Robustesse execution (2 jours)
  C-09 → C-10
  (Guard Cython + reversal automatique jambe divergente)

Sprint 5 — Config + Interface (0.5 jour)
  C-11 → C-12 → C-13
  (Hardcoded values → config, execution/__init__.py)

Sprint 6 — Walk-forward (2 jours — optionnel)
  C-14 (après décision architecturale)
```

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert (C-01 à C-04 tous ✅)
- [ ] `pytest tests/` : 2808+ passed, 0 failed
- [ ] `mypy risk/ risk_engine/ execution/ --ignore-missing-imports` : exit 0
- [ ] `ruff check .` : 0 erreurs
- [ ] Zéro credential IBKR dans les logs (`Select-String -Path common/secrets.py -Pattern "print\(api"` → vide)
- [ ] Zéro `print()` dans `execution/`, `pair_selection/`, `strategies/` (hors `main.py`)
- [ ] Kill-switch persisté au redémarrage
- [ ] Risk tiers cohérents (`_assert_risk_tier_coherence()` : OK)
- [ ] `EDGECORE_ENV=prod` dans Dockerfile (pas `production`)
- [ ] Paper trading ≥ 5 jours avant live
- [ ] Seuils backtest ↔ live documentés ou alignés (C-04)
- [ ] Guard Cython dans trading loop (C-09)

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Suppression fuite credentials api_key | 🔴 | `common/secrets.py:512` | 15 min | ✅ | 2026-04-04 |
| C-02 | Supprimer banner module-load position_stops | 🔴 | `execution/position_stops.py:477-481` | 10 min | ✅ | 2026-04-04 |
| C-03 | Supprimer print() debug discovery | 🔴 | `pair_selection/discovery.py:117` | 10 min | ✅ | 2026-04-04 |
| C-04 | Aligner seuils signal backtest ↔ live | 🔴 | `backtests/strategy_simulator.py:230-231` | 30 min | ✅ | 2026-04-04 |
| C-05 | Supprimer print() [DEBUG] pair_trading | 🟠 | `strategies/pair_trading.py:895,902` | 10 min | ✅ | 2026-04-04 |
| C-06 | Supprimer print() debug ou_model | 🟠 | `models/ou_model.py:222-223` | 10 min | ✅ | 2026-04-04 |
| C-07 | typeCheckingMode basic → standard | 🟠 | `pyrightconfig.json` | 8h | ✅ | 2026-04-04 |
| C-08 | Corriger type:ignore attr-defined runner.py | 🟠 | `live_trading/runner.py` | 4h | ✅ | 2026-04-04 |
| C-09 | Guard Cython absent dans trading loop | 🟠 | `live_trading/runner.py` | 2h | ✅ | 2026-04-04 |
| C-10 | Reversal automatique jambe divergente | 🟠 | `execution/ibkr_engine.py` | 24h | ⏳ | — |
| C-11 | stability_threshold → config | 🟡 | `strategies/pair_trading.py:694` | 30 min | ✅ | 2026-04-04 |
| C-12 | Peupler execution/__init__.py | 🟡 | `execution/__init__.py` | 1h | ✅ | 2026-04-04 |
| C-13 | acceptance_threshold OOS → config | 🟡 | `backtester/oos.py:70` | 30 min | ✅ | 2026-04-04 |
| C-14 | Implémenter walk-forward réel (optionnel) | 🟡 | `backtests/walk_forward.py` | 16h | ⏳ | — |
