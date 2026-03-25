---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_strategic_edgecore_2026-03-25.md
derniere_revision: 2026-03-25
creation: 2026-03-25 à 00:00
---

# PLAN D'ACTION — EDGECORE STRATÉGIQUE — 2026-03-25
**Sources** : `tasks/audits/resultats/audit_strategic_edgecore.md` (2026-03-25)
**Total** : 🔴 5 · 🟠 7 · 🟡 3 · **Effort estimé : 6–8 jours**

> ⚠️ VERDICT AUDIT : **NO-GO (2/10)**
> L'audit détecte deux catégories de corrections :
> - **Corrections code** (C-03 à C-10) : isolées, réversibles, exécutables immédiatement
> - **Refonte stratégique** (C-01 et C-02) : nécessitent une décision architecturale
>   avant toute exécution de code — elles débloquent tous les 🔴 restants

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Reconstruire le backtest IS de référence avec la config à 2 sources
**Anomalies** : SB5-01, SB1-01, SB1-02, SB1-03, SB8-01
**Fichiers** : `results/bt_v36_output.json:5` · `config/dev.yaml:49` · `signal_engine/combiner.py:106`

**Problème** :
Le backtest IS de référence `bt_v36` a été exécuté avec `SignalCombiner` configuré à **6 sources** (`zscore=0.35, momentum=0.15, OU=0.20, vol=0.10, CS=0.10, intraday=0.10`) — une configuration abandonnée. La config actuelle utilise **2 sources** (`zscore=0.70, momentum=0.30`). Les métriques IS (S=1.33, PF=4.22, N=21) sont donc non reproductibles et ne mesurent pas la stratégie déployée en live. C'est aussi la source des anomalies SB1-01/02/03 : N=21 sur un IS qui n'est pas la bonne config.

**Correction** :
Lancer un backtest IS complet sur la même période et le même univers avec la configuration actuelle (`zscore_weight=0.70`, `momentum_weight=0.30`) et exporter les résultats dans `results/bt_reference_2sources_output.json` avec les métriques per-trade (avg_win, avg_loss, per-pair P&L).

```powershell
# Vérifier la config actuelle avant lancement
venv\Scripts\python.exe -c "from config.settings import get_settings; s=get_settings(); print('zscore_weight:', s.signal_combiner.zscore_weight, '| momentum_weight:', s.signal_combiner.momentum_weight)"
# Attendu : zscore_weight: 0.7 | momentum_weight: 0.3
```

**Validation** :
- Le fichier `results/bt_reference_2sources_output.json` contient `"zscore": 0.70, "momentum": 0.30`
- N_IS ≥ 30 trades (si != → le drought est confirmé même en IS → escalade C-02)
- IC 95% sur WR calculé et documenté dans le fichier résultat
- Le Sharpe IS du nouveau run est la nouvelle baseline de référence

```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2787+ passed, 0 failed
```

**Dépend de** : Aucune
**Effort** : L (~2 jours — run + analyse + documentation)
**Statut** : ⏳

---

### [C-02] Implémenter un filtre de régime macroéconomique (anti-drought)
**Anomalies** : SB3-01, SB1-03, SB2-01
**Fichiers** : `signal_engine/generator.py` · `backtests/strategy_simulator.py` · `models/adaptive_thresholds.py` · `config/dev.yaml`

**Problème** :
La stratégie ne génère d'edge que dans un régime de **haute dispersion intrasectorielle** (confirmé sur 2022H2 uniquement, PASS=1/5). En bull-market comprimé (2024H2), aucun spread n'atteint `entry_z_score = 1.6` → 3 trades en 382 jours. La cause n'est pas paramétrique mais structurelle : l'absence d'un filtre de régime provoque 4 périodes de pertes sur 5 en walk-forward multi-années.

**Correction** (choix architectural — décision humaine requise) :

**Option A — Filtre VIX/dispersion** :
- Mesurer la dispersion intrasectorielle `corr_rolling_std` sur fenêtre 60j
- N'autoriser les entrées que si `dispersion_index > seuil_min` (à calibrer sur IS)
- Implémentation dans `signal_engine/generator.py`

**Option B — Activer `models/adaptive_thresholds.py`** :
- Ajouter dans `config/dev.yaml` : `adaptive_thresholds: { enabled: true }`
- Brancher dans `signal_engine/generator.py` : remplacer `entry_z_score` fixe par `AdaptiveThresholds.get_entry_threshold(regime)`
- Brancher dans `backtests/strategy_simulator.py` : idem pour la simulation

**Validation** :
Après implémentation, relancer le walk-forward v45b `scripts/run_p5_v45b.py` et vérifier :
- ≥ 3/5 périodes PASS (seuil minimal viable)
- N_OOS ≥ 30 trades par période PASS
- Sharpe moyen OOS ≥ 0.5

```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2787+ passed, 0 failed

# Vérifier risk tiers cohérents après tout changement config
venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"
```

**Dépend de** : C-01 (les résultats IS du rebuild guident le choix Option A vs B et la valeur du seuil)
**Effort** : L (~3 jours — décision + implémentation + re-calibration + re-run walk-forward)
**Statut** : ⏳

---

## PHASE 2 — MAJEURES 🟠

### [C-03] Ajouter le logging structuré des motifs de rejet de filtres
**Anomalies** : SB2-02
**Fichiers** : `pair_selection/discovery.py`

**Problème** :
Les rejets de paires (z-score insuffisant, corrélation, demi-vie, coïntégration) ne sont pas loggés avec le motif structuré. En production, un silence prolongé est indiagnosticable — impossible de distinguer "aucune paire ne satisfait entry_z_score" de "KillSwitch actif" ou "correlation_prefilter trop restrictif".

**Correction** :
Dans `pair_selection/discovery.py`, ajouter un log structuré à chaque rejet de filtre :
```python
logger.info(
    "pair_rejected",
    pair=f"{sym1}_{sym2}",
    reason="z_score_below_threshold",   # motif explicite
    z_score=observed_z,
    threshold=self.config.entry_z_score,
)
```
Motifs à couvrir : `correlation_below_min`, `half_life_exceeds_max`, `eg_test_failed`, `z_score_below_threshold`, `i1_check_failed`.

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/test_pair_selection/ -x -q
# Attendu : passed, 0 failed
# Vérifier qu'un log "pair_rejected" apparaît dans les traces de test
```

**Dépend de** : Aucune
**Effort** : S (< 4h)
**Statut** : ⏳

---

### [C-04] Ajouter l'export per-paire dans les résultats JSON du simulateur
**Anomalies** : SB3-02
**Fichiers** : `backtests/strategy_simulator.py` · `backtests/metrics.py`

**Problème** :
`bt_v36_output.json` et `bt_v35_output.json` ne contiennent que des métriques agrégées. Impossible d'identifier les paires destructrices de valeur (PF < 1.0) ou la concentration du P&L sur quelques paires. Les avg_win/avg_loss manquants empêchent aussi le calcul de f* Kelly.

**Correction** :
Dans `backtests/strategy_simulator.py`, alimenter un dict `per_pair_stats` pendant la simulation et l'inclure dans le JSON de sortie :
```python
"per_pair": {
    "JPM_BAC": {"n_trades": 5, "pnl": 1240.0, "win_rate": 0.80, "avg_win": 310.0, "avg_loss": -155.0, "pf": 2.0},
    ...
}
```
Inclure aussi les champs globaux `avg_win`, `avg_loss` pour permettre le calcul de f*.

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/test_backtests/ -x -q
# Vérifier que le JSON de sortie contient la clé "per_pair"
```

**Dépend de** : Aucune
**Effort** : M (< 1 jour)
**Statut** : ⏳

---

### [C-05] Corriger le slippage hardcodé dans `execution_engine/router.py` (B5-02)
**Anomalies** : SB6-01
**Fichiers** : `execution_engine/router.py:162,189`

**Problème** :
Deux occurrences de slippage hardcodé `2.0` dans `execution_engine/router.py:162,189` — ignorent `get_settings().costs.slippage_bps` et le modèle `almgren_chriss` configuré dans `config/dev.yaml:217-222`. Dette technique connue B5-02.

**Correction** :
Remplacer les deux occurrences :
```python
# Avant (ligne 162 et 189)
slippage = 2.0

# Après
slippage = get_settings().costs.slippage_bps
```
Importer `get_settings` si absent en tête de fichier.

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/test_execution/ -x -q
# Attendu : passed, 0 failed

# Vérifier la lecture de la config
venv\Scripts\python.exe -c "from config.settings import get_settings; print(get_settings().costs.slippage_bps)"
# Attendu : 2.0
```

**Dépend de** : Aucune
**Effort** : S (< 4h)
**Statut** : ⏳

---

### [C-06] Vérifier et corriger l'application du coût de borrow dans `backtests/cost_model.py`
**Anomalies** : SB6-02
**Fichiers** : `backtests/cost_model.py` · `config/dev.yaml:221`

**Problème** :
`borrowing_cost_annual: 0.005` est configuré dans `config/dev.yaml:221` mais son application effective dans `backtests/cost_model.py` n'est pas confirmée. Si absent, les positions short sont surévaluées en IS.

**Correction** :
Lire `backtests/cost_model.py` et vérifier que `borrowing_cost_annual` est appliqué proportionnellement à la durée de détention pour chaque position short. Si absent, l'ajouter :
```python
borrow_cost = position_size * get_settings().costs.borrowing_cost_annual * hold_days / 252
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/test_backtests/test_cost_model.py -x -q
# Attendu : passed, 0 failed
```

**Dépend de** : Aucune
**Effort** : XS (< 1h — lecture + correction ou confirmation)
**Statut** : ⏳

---

### [C-07] Documenter la dégradation IS→OOS dans le fichier de run walk-forward
**Anomalies** : SB4-01
**Fichiers** : `backtests/walk_forward.py` · `scripts/run_p5_v45b.py`

**Problème** :
Le walk-forward séquentiel ne calcule pas automatiquement la dégradation IS→OOS (Sharpe, WR, PF). Le résumé final (`COMPLETE RESULTS`) liste les métriques par période mais pas la dégradation relative. Impossible de détecter automatiquement un overfitting.

**Correction** :
Ajouter dans le script de run ou `backtests/walk_forward.py` le calcul automatique des ratios de dégradation :
```python
degradation_sharpe = (oos_sharpe - is_sharpe) / abs(is_sharpe) * 100
if degradation_sharpe < -30:
    logger.warning("oos_degradation_high", degradation_pct=degradation_sharpe, threshold=-30)
if degradation_sharpe < -50:
    logger.error("oos_degradation_critical", degradation_pct=degradation_sharpe, threshold=-50)
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/test_backtests/test_walk_forward.py -x -q
```

**Dépend de** : C-01 (les vrais IS metrics sont nécessaires pour calibrer le calcul)
**Effort** : S (< 4h)
**Statut** : ⏳

---

### [C-08] Recompiler le moteur Cython cointegration
**Anomalies** : SB8-02
**Fichiers** : `models/cointegration_fast.pyx` · `setup.py`

**Problème** :
Le moteur Cython `cointegration_fast.pyx` n'est pas compilé → fallback Python actif → pair discovery ~10x plus lent (~2085s/période confirmé en v45b). En live avec 101 symboles et IBKR rate limit (50 req/s), la latence de découverte de paires dépasse la fenêtre de signal.

**Correction** :
Recompiler le module Cython pour Python 3.11 :
```powershell
venv\Scripts\python.exe setup.py build_ext --inplace
# Vérifier le fichier généré
Get-ChildItem models/cointegration_fast*.pyd
# Attendu : models/cointegration_fast.cp311-win_amd64.pyd
```

Vérifier l'activation au démarrage :
```powershell
venv\Scripts\python.exe -c "from models.cointegration import CYTHON_COINTEGRATION_AVAILABLE; print(CYTHON_COINTEGRATION_AVAILABLE)"
# Attendu : True
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2787+ passed, 0 failed
```

**Dépend de** : Aucune
**Effort** : S (< 4h — compilation + validation)
**Statut** : ⏳

---

## PHASE 3 — MINEURES 🟡

### [C-09] Activer les seuils adaptatifs dans la configuration
**Anomalies** : SB5-02
**Fichiers** : `models/adaptive_thresholds.py` · `config/dev.yaml` · `signal_engine/generator.py`

**Problème** :
`models/adaptive_thresholds.py` est présent mais n'est référencé ni dans `config/dev.yaml` ni dans le pipeline signal ou backtest. En régime comprimé, des seuils adaptatifs au régime pourraient réduire le drought de signal.

**Correction** :
_(Cette correction est **conditionnelle** à la décision architecturale dans C-02)_

Si C-02 Option B est retenu, brancher `AdaptiveThresholds` dans `config/dev.yaml` et `signal_engine/generator.py` :
```yaml
# config/dev.yaml
adaptive_thresholds:
  enabled: true
  lookback_days: 60
  min_entry_z: 1.2
  max_entry_z: 2.5
```

Si C-02 Option A (filtre VIX) est retenu, cette correction devient redondante → fermer.

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"
```

**Dépend de** : C-02
**Effort** : M (< 1 jour — conditionnel à C-02)
**Statut** : ⏳

---

### [C-10] Ajouter un guard dans `KellySizer` pour le régime drought
**Anomalies** : SB7-01
**Fichiers** : `risk/kelly_sizing.py:63,44`

**Problème** :
Quand `len(self._trade_history) < 10`, le sizer retourne `default_allocation_pct = 8.0` — un fallback aveugle non justifié par l'edge réel. En régime drought (P5 = 3 trades), 100% des allocations sont au fallback, ce qui rend le sizing indépendant de la performance observée.

**Correction** :
Ajouter un log d'avertissement et réduire le fallback proportionnellement à la confiance :
```python
if len(self._trade_history) < 10:
    logger.warning(
        "kelly_sizer_insufficient_history",
        n_trades=len(self._trade_history),
        min_required=10,
        using_fallback_pct=self.config.default_allocation_pct,
    )
    return self.config.default_allocation_pct / 100.0
```
(Le fallback en lui-même est acceptable — le problème est l'absence d'observabilité.)

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/test_risk/ -x -q
```

**Dépend de** : Aucune
**Effort** : XS (< 1h)
**Statut** : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
[Indépendantes — parallélisables immédiatement]
C-05  → Corriger slippage router.py (B5-02)
C-08  → Recompiler Cython
C-03  → Logging motifs de rejet
C-06  → Vérifier coût de borrow cost_model.py
C-10  → Guard KellySizer drought
C-04  → Export per-paire JSON

[Dépendent du rebuild IS]
C-01  → Rebuild backtest IS avec config 2 sources   [DÉBLOQUE : C-02, C-07, C-09]
C-07  → Documenter dégradation IS→OOS              [Dépend de C-01]

[Décision stratégique — après C-01]
C-02  → Filtre régime / seuils adaptatifs           [Dépend de C-01]
C-09  → Activer adaptive_thresholds                 [Dépend de C-02]
```

**Ordre recommandé** :
```
C-05 → C-08 → C-03 → C-06 → C-10 → C-04
    → C-01 (rebuild IS)
        → C-07 → C-02 (décision régime)
                    → C-09
```

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] pytest tests/ : 100% pass (2787+)
- [ ] mypy risk/ risk_engine/ execution/ : exit 0
- [ ] ruff check . : 0 erreurs
- [ ] Zéro credential IBKR dans les logs
- [ ] Kill-switch persisté au redémarrage
- [ ] Risk tiers cohérents (`_assert_risk_tier_coherence OK`)
- [ ] `EDGECORE_ENV=prod` dans Dockerfile (pas `production`)
- [ ] **Backtest IS reconstruit avec config 2 sources (Sharpe IS et N_IS documentés)**
- [ ] **Walk-forward ≥ 3/5 PASS avec N_OOS ≥ 30 trades par période PASS**
- [ ] **Sharpe OOS moyen ≥ 0.5 (actuellement : -0.63)**
- [ ] Paper trading validé avant live

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Rebuild IS backtest (config 2 sources) | 🔴 | `results/bt_reference_2sources_output.json` | L | ⏳ | — |
| C-02 | Filtre dispersion macroéconomique | 🔴 | `signal_engine/generator.py`, `config/dev.yaml` | L | ✅ | 2026-03-25 |
| C-03 | Logging motifs de rejet filtres | 🟠 | `pair_selection/discovery.py` | S | ✅ | 2026-03-25 |
| C-04 | Export per-paire JSON + total_slippage | 🟠 | `backtests/strategy_simulator.py`, `metrics.py` | M | ✅ | 2026-03-25 |
| C-05 | Slippage hardcodé router.py (B5-02) | 🟠 | `execution_engine/router.py:162,189` | S | ✅ | 2026-03-25 |
| C-06 | Coût de borrow cost_model.py | 🟠 | `backtests/cost_model.py` | XS | ✅ | 2026-03-25 |
| C-07 | Dégradation IS→OOS walk-forward | 🟠 | `backtests/walk_forward.py` | S | ✅ | 2026-03-25 |
| C-08 | Recompiler Cython cointegration | 🟠 | `models/cointegration_fast.pyx` | S | ✅ | 2026-03-25 |
| C-09 | Adaptive thresholds dispersion ramp | 🟡 | `signal_engine/adaptive.py`, `config/dev.yaml` | M | ✅ | 2026-03-25 |
| C-10 | Guard KellySizer drought | 🟡 | `risk/kelly_sizing.py:63,44` | XS | ✅ | 2026-03-25 |
