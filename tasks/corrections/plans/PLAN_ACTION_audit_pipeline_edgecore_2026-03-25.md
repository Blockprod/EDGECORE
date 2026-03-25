---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: PLAN_ACTION_audit_pipeline_edgecore_2026-03-25.md
derniere_revision: 2026-03-25
creation: 2026-03-25 à 00:00
---

# PLAN D'ACTION — EDGECORE — 2026-03-25

**Sources** : `tasks/audits/resultats/audit_pipeline_edgecore.md`  
**Total** : 🔴 4 · 🟠 5 · 🟡 4 · **Effort estimé : ~4 jours**

---

## PHASE 1 — CRITIQUES 🔴

---

### [C-01] Brancher StrategyBacktestSimulator sur get_settings().costs

**Fichier** : `backtests/strategy_simulator.py:128`  
**Problème** : `CostModel()` est instancié avec les valeurs hardcodées de `CostModelConfig`. `get_settings().costs` (source de vérité `CostConfig`) n'est jamais lue en backtest. Modifier `costs.slippage_bps` dans le YAML n'a aucun effet sur les backtests.

**Correction** :
```python
# Avant
self.cost_model = cost_model or CostModel()

# Après
from config.settings import get_settings as _gs
_costs = _gs().costs
self.cost_model = cost_model or CostModel(
    CostModelConfig(
        base_slippage_bps=_costs.slippage_bps,
        taker_fee_bps=_costs.taker_fee_bps,
        maker_fee_bps=_costs.maker_fee_bps,
        borrowing_cost_annual_pct=_costs.borrowing_cost_annual * 100,
        slippage_model=_costs.slippage_model,
    )
)
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "cost or simulator or backtest"
# Attendu : 0 erreurs, slippage/commission cohérents entre config et CostModel
```

**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-02] Lire SignalCombinerConfig dans PairTradingStrategy

**Fichier** : `strategies/pair_trading.py:163–176`  
**Problème** : Les poids du `SignalCombiner` sont hardcodés (zscore=0.35, momentum=0.08, entry_threshold=0.30), ignorant totalement `SignalCombinerConfig` (zscore=0.70, momentum=0.30, entry_threshold=0.60). Le backtest est basé sur un signal fondamentalement différent du live.

**Correction** : Lire `get_settings().signal_combiner` pour les poids zscore/momentum et les seuils entrée/sortie des deux sources primaires, tout en conservant les sources additionnelles (ou, vol_regime, etc.) avec leurs poids relatifs normalisés.  
Option minimale (alignement des 2 sources primaires) :
```python
_sc = get_settings().signal_combiner
# Remplacer les lignes 163-176 — conserver les sources avancées
# mais lire zscore_weight et momentum_weight depuis config
_zw = _sc.zscore_weight          # 0.70
_mw = _sc.momentum_weight        # 0.30 (si momentum enabled)
# Recalibrer les autres sources proportionnellement ou les figer à 0
# jusqu'à définition formelle de leur poids depuis config.
```

Option pragmatique : exposer un `additional_sources_weights` dans `SignalCombinerConfig` ou limiter pour l'instant le combiner à 2 sources (zscore + momentum) aligné sur la documentation.

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "pair_trading or signal_combiner or combiner"
# Attendu : SignalCombiner utilise zscore_weight=0.70, momentum_weight=0.30
```

**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-03] Activer momentum_overlay dans SignalGenerator live

**Fichier** : `live_trading/runner.py:267–271`  
**Problème** : `SignalGenerator` est initialisé sans `momentum_overlay=...`. `MomentumOverlay` (configuré enabled=True, weight=0.30) est absent du pipeline live. Live = z-score seul ; backtest = z-score + momentum.

**Correction** :
```python
from signal_engine.momentum import MomentumOverlay
from config.settings import get_settings
_mom = get_settings().momentum
_overlay = MomentumOverlay(
    lookback=_mom.lookback,
    weight=_mom.weight,
    min_strength=_mom.min_strength,
    max_boost=_mom.max_boost,
) if _mom.enabled else None

self._signal_gen = SignalGenerator(
    threshold_engine=AdaptiveThresholdEngine(
        base_entry=getattr(strat, "entry_z_score", 2.0),
        base_exit=getattr(strat, "exit_z_score", 0.5),
        max_entry=getattr(strat, "z_score_stop", 3.5),
    ),
    momentum_overlay=_overlay,   # ← ajout
)
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "signal_gen or momentum or live_trading"
# Attendu : SignalGenerator.momentum_overlay is not None quand config.momentum.enabled=True
```

**Dépend de** : C-02 (cohérence poids avant d'activer un nouveau composant)  
**Statut** : ⏳

---

### [C-04] Brancher le gate d'entrée sur PortfolioRiskManager.can_open_position()

**Fichier** : `live_trading/runner.py:~800` (`_step_execute_signals`)  
**Problème** : `_portfolio_risk.can_open_position()` n'est jamais appelé. Le gate T1 (heat, consecutive losses, position count) de `PortfolioRiskManager` est inactif en live. Seul `RiskFacade.can_enter_trade()` est dans le chemin critique.

**Correction** : Dans `_step_execute_signals`, après le check `RiskFacade`, ajouter :
```python
# 4b. PortfolioRiskManager gate (T1: heat, position count, consecutive losses)
prm_ok, prm_reason = self._portfolio_risk.can_open_position(
    position_risk_pct=get_settings().risk.max_risk_per_trade,
)
if not prm_ok:
    logger.warning("live_trade_blocked_portfolio_risk", pair=sig.pair_key, reason=prm_reason)
    continue
```

Également wirer `record_trade_result()` et `update_equity()` dans les callbacks de trade (entrée/sortie confirmée).

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "portfolio_risk or live_trading or risk_manager"
# Attendu : can_open_position() invoqué ; test de heat=95% bloque nouvelle entrée
```

**Dépend de** : C-05 (s'assurer que PortfolioRiskConfig est T1 avant d'activer le gate)  
**Statut** : ⏳

---

## PHASE 2 — MAJEURES 🟠

---

### [C-05] Configurer PortfolioRiskManager avec le seuil T1 (0.10)

**Fichier** : `live_trading/runner.py:275` · `risk_engine/portfolio_risk.py:28`  
**Problème** : `PortfolioRiskConfig.max_drawdown_pct` par défaut = 0.15 (T2). `PortfolioRiskManager` est instancié sans config explicite → déclenche à 15 % au lieu de 10 % (T1).

**Correction** :
```python
from risk_engine.portfolio_risk import PortfolioRiskConfig
self._portfolio_risk = PortfolioRiskManager(
    initial_equity=self.config.initial_capital,
    config=PortfolioRiskConfig(
        max_drawdown_pct=get_settings().risk.max_drawdown_pct,  # T1 = 0.10
        max_daily_loss_pct=get_settings().risk.max_daily_loss_pct,
        max_concurrent_positions=get_settings().risk.max_concurrent_positions,
    ),
)
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "portfolio_risk or kill_switch"
venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('Tiers OK')"
# Attendu : PortfolioRiskManager.config.max_drawdown_pct == 0.10
```

**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-06] Mettre à jour l'equity de RiskFacade à chaque tick

**Fichier** : `live_trading/runner.py:~580` (dans `_tick()`)  
**Problème** : `RiskFacade.risk_engine` utilisise l'equity initiale figée (100k). Aucun `update_equity()` n'est appelé dans la boucle tick. Les calculs de drawdown et de sizing sont basés sur une equity obsolète.

**Correction** : Dans `_tick()`, après le fetch du balance (L~580) :
```python
_tick_balance = self._router.get_account_balance() if self._router else self.config.initial_capital
# ← ajouter :
if self._risk_facade and _tick_balance > 0:
    self._risk_facade.risk_engine.update_equity(_tick_balance)
if self._portfolio_risk and _tick_balance > 0:
    self._portfolio_risk.update_equity(_tick_balance)
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "risk_facade or live_trading"
# Attendu : risk_facade.risk_engine._equity reflète le solde broker courant
```

**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-07] Normaliser la commission backtest/live (taker_fee_bps → commission_pct)

**Fichier** : `backtests/cost_model.py:24` · `config/settings.py:130`  
**Problème** : Backtest = `taker_fee_bps=2.0` → 0.020 %/leg ; live = `commission_pct=0.00035` → 0.035 %/leg. Écart ×1.75 sur la commission par leg.

**Correction** : Deux options :
- **Option A** (recommandée) : Exposer `commission_pct` dans `CostConfig` (déjà présent como `commission_pct=0.00035`) et l'utiliser dans `CostModelConfig` via C-01 :  
  `taker_fee_bps = costs.commission_pct * 10_000` (0.00035 × 10000 = **3.5 bps**)
- **Option B** : Aligner `costs.commission_pct` sur `2.0 bps` si le vrai taux IBKR est 2 bps.

Vérifier le taux IBKR réel et trancher, puis unifier.

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "cost_model or commission"
# Attendu : commission identique en backtest et live (même source CostConfig)
```

**Dépend de** : C-01  
**Statut** : ⏳

---

### [C-08] Corriger fill à $0 pour les market orders (limit_price=None)

**Fichier** : `execution_engine/router.py:147` (`_simulate_fill`) · `router.py:182` (`_paper_fill`)  
**Problème** : `price = order.limit_price or 0.0` → si `limit_price is None` (market orders, stops), fill à $0. Commission = $0, bilan faux.

**Correction** : Exiger un prix de marché en fallback. Dans les méthodes `_simulate_fill` et `_paper_fill` :
```python
# Récupérer le dernier prix connu depuis l'order metadata ou un param additionnel
market_price = getattr(order, "market_price", None) or order.limit_price
if market_price is None or market_price <= 0:
    logger.error("order_price_unavailable_skipping_fill", symbol=order.symbol)
    raise ValueError(f"Cannot fill order for {order.symbol}: no price available (limit_price=None, no market_price)")
price = market_price
```

Alternativement : transmettre le dernier close price dans `Order.market_price` lors de la construction des ordres de stop dans `_step_process_stops`.

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "router or simulate_fill or paper_fill"
# Attendu : ValueError si aucun prix disponible ; stops passent le prix de marché
```

**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-09] Ajouter section `costs:` dans dev.yaml

**Fichier** : `config/dev.yaml`  
**Problème** : `CostConfig.slippage_bps` vaut 3.0 par défaut (settings.py) faute de surcharge dans dev.yaml. Le backtest utilise 2.0 bps. Divergence systématique de 1 bps sur le slippage fixe.

**Correction** :
```yaml
# À ajouter dans config/dev.yaml
costs:
  slippage_bps: 2.0               # Aligné sur CostModelConfig large-cap
  commission_pct: 0.00020         # ~2.0 bps — à trancher avec C-07
  taker_fee_bps: 2.0
  maker_fee_bps: 1.5
  borrowing_cost_annual: 0.005    # 0.5% GC rate
  slippage_model: "almgren_chriss"
```

**Validation** :
```powershell
venv\Scripts\python.exe -c "from config.settings import get_settings; s=get_settings(); print('slippage_bps:', s.costs.slippage_bps)"
# Attendu : 2.0 (non 3.0)
venv\Scripts\python.exe -m pytest tests/ -x -q
```

**Dépend de** : C-07 (trancher la valeur commission_pct avant de figer)  
**Statut** : ⏳

---

## PHASE 3 — MINEURES 🟡

---

### [C-10] Supprimer la clé orpheline ExecutionConfig.slippage_bps

**Fichier** : `config/dev.yaml:197`  
**Problème** : `execution.slippage_bps: 2.0` dans dev.yaml ne correspond à aucun appelant — le router lit `costs.slippage_bps`. Clé trompeuse qui donne l'illusion d'un contrôle inexistant.

**Correction** : Retirer la ligne `slippage_bps: 2.0` de la section `execution:` dans dev.yaml (et vérifier test.yaml / prod.yaml).

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : aucune régression (clé morte, pas de lecteur)
```

**Dépend de** : C-09 (s'assurer que la vraie clé costs.slippage_bps remplace bien l'orpheline)  
**Statut** : ⏳

---

### [C-11] Exposer kalman_delta dans StrategyConfig

**Fichier** : `config/settings.py` (`StrategyConfig`) · `models/kalman_hedge.py:57`  
**Problème** : `KalmanHedgeRatio(delta=1e-4)` hardcodé — vitesse d'adaptation du ratio hedge non ajustable sans code change.

**Correction** :
```python
# Dans StrategyConfig (settings.py)
kalman_delta: float = 1e-4   # Process noise — contrôle vitesse d'adaptation du ratio hedge (Kalman)

# Dans SpreadModel.__init__() et KalmanHedgeRatio instanciations :
kalman_delta = get_settings().strategy.kalman_delta
self._kalman = KalmanHedgeRatio(delta=kalman_delta)
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "kalman or spread or hedge"
```

**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-12] Lire AlgoConfig.impact_bps depuis CostConfig

**Fichier** : `backtests/strategy_simulator.py:~160`  
**Problème** : `impact_bps=2.0` hardcodé dans `AlgoConfig` — non relié à `CostConfig.taker_fee_bps`.

**Correction** :
```python
from config.settings import get_settings as _gs
self._algo_executor = TWAPExecutor(
    config=AlgoConfig(
        algo_type=AlgoType.TWAP,
        num_slices=10,
        impact_bps=_gs().costs.taker_fee_bps,   # ← depuis CostConfig
        max_participation=0.05,
    )
)
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "simulator or algo or twap"
```

**Dépend de** : C-01  
**Statut** : ⏳

---

### [C-13] Modèle de partial fill en paper mode

**Fichier** : `execution_engine/router.py:183` (`_paper_fill`)  
**Problème** : `filled_qty=order.quantity` toujours. 100 % fill systématique surestime la liquidité disponible en paper trading.

**Correction** : Ajouter un taux de fill configurable (depuis `TradingConfig` ou `ExecutionConfig`) :
```python
fill_rate = getattr(get_settings().trading, "paper_fill_rate", 1.0)  # défaut 100%
filled_qty = order.quantity * fill_rate
```

Ou implémenter un modèle de participation basé sur la liquidité (ADV) si disponible.

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "paper_fill or paper_execution or execution_router"
```

**Dépend de** : Aucune  
**Statut** : ⏳

---

## SÉQUENCE D'EXÉCUTION

Ordre tenant compte des dépendances et de l'impact systémique :

```
C-05  →  C-04          (T1 config avant d'activer le gate PortfolioRisk)
C-01  →  C-07  →  C-09  →  C-10   (coûts : source de vérité → normalisation → YAML → nettoyage)
C-08                   (market orders : indépendant, haute priorité)
C-02  →  C-03          (combiner poids config → activer momentum live)
C-06                   (equity update : indépendant)
C-11                   (kalman delta : indépendant)
C-12                   (après C-01, algo_executor)
C-13                   (partial fill : indépendant)
```

Séquence linéaire recommandée :
**C-05 → C-08 → C-01 → C-07 → C-09 → C-04 → C-06 → C-02 → C-03 → C-10 → C-11 → C-12 → C-13**

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert (C-01, C-02, C-03, C-04 tous en statut ✅)
- [ ] `pytest tests/` : 100 % pass (2787+ tests)
- [ ] `mypy risk/ risk_engine/ execution/ execution_engine/ signal_engine/ strategies/` : exit 0
- [ ] `ruff check . --select ALL` : 0 erreurs
- [ ] Zéro credential IBKR dans les logs
- [ ] Kill-switch persisté au redémarrage (state file présent)
- [ ] Risk tiers cohérents : `_assert_risk_tier_coherence()` OK
- [ ] `EDGECORE_ENV=prod` dans Dockerfile (pas "production")
- [ ] `PortfolioRiskManager.can_open_position()` dans le chemin critique live (C-04)
- [ ] `SignalGenerator` avec `momentum_overlay` en live (C-03)
- [ ] Costs backtest == costs live via `get_settings().costs` (C-01 + C-09)
- [ ] Market orders transmettent un prix valide (C-08)
- [ ] Paper trading validé 1 semaine avant live

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | CostModel ← get_settings().costs | 🔴 | `backtests/strategy_simulator.py:128` | S (1h) | ⏳ | — |
| C-02 | SignalCombiner poids ← config | 🔴 | `strategies/pair_trading.py:163` | M (2h) | ⏳ | — |
| C-03 | momentum_overlay en live | 🔴 | `live_trading/runner.py:268` | S (1h) | ⏳ | — |
| C-04 | Gate PortfolioRiskManager actif | 🔴 | `live_trading/runner.py:~800` | M (2h) | ⏳ | — |
| C-05 | PortfolioRiskConfig ← T1 (0.10) | 🟠 | `live_trading/runner.py:275` | XS (15min) | ⏳ | — |
| C-06 | Equity update RiskFacade/tick | 🟠 | `live_trading/runner.py:~580` | S (1h) | ⏳ | — |
| C-07 | Commission backtest == live | 🟠 | `backtests/cost_model.py:24` | M (2h) | ⏳ | — |
| C-08 | Market orders prix non nul | 🟠 | `execution_engine/router.py:147,182` | M (2h) | ⏳ | — |
| C-09 | Section costs: dans dev.yaml | 🟠 | `config/dev.yaml` | XS (15min) | ⏳ | — |
| C-10 | Supprimer clé orpheline slippage_bps | 🟡 | `config/dev.yaml:197` | XS (5min) | ⏳ | — |
| C-11 | kalman_delta dans StrategyConfig | 🟡 | `config/settings.py` | S (1h) | ⏳ | — |
| C-12 | AlgoConfig.impact_bps ← CostConfig | 🟡 | `backtests/strategy_simulator.py:~160` | XS (15min) | ⏳ | — |
| C-13 | Partial fill model paper mode | 🟡 | `execution_engine/router.py:183` | M (2h) | ⏳ | — |

**Effort total estimé** : ~4 jours  
*(XS=15min, S=1h, M=2h — inclut tests et revue)*
