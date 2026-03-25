---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_pipeline_edgecore.md
derniere_revision: 2026-07-10
creation: 2026-07-10 à 00:00
---

# Audit #7 — Pipeline Engineering · EDGECORE

> **Scope** : cohérence paramètres config↔backtest↔live, pipeline all-or-nothing, données spread, modèle de coûts, risk engine, routage d'exécution.  
> **Branche** : `lfs-migration-preview` · **Date** : 2026-07-10

---

## Tableau synthèse

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|
| P1-01 | Cohérence params | SignalCombiner backtest ignore SignalCombinerConfig : poids hardcodés (zscore 0.35 vs config 0.70, entry_thr 0.30 vs 0.60) | `strategies/pair_trading.py:163` | 🔴 | Signaux forward-test ≠ live → Sharpe backtest invalide | M |
| P1-02 | Cohérence params | Pipeline live ignore momentum : `SignalGenerator` init sans `momentum_overlay` → momentum_weight=0.30 config non appliqué en live | `live_trading/runner.py:268` | 🔴 | Live n'utilise pas 30 % du signal configuré | S |
| P1-03 | Cohérence params | `costs.slippage_bps` (défaut 3.0) non surchargé dans dev.yaml ; backtest utilise `CostModelConfig.base_slippage_bps=2.0` → 1 bps de divergence systématique | `config/dev.yaml`, `backtests/cost_model.py:26` | 🟠 | Backtest sous-estime le coût d'exécution de ~33 % | S |
| P1-04 | Cohérence params | `ExecutionConfig.slippage_bps=2.0` (dev.yaml L197) orphelin : aucun appelant ne le lit ; router lit `costs.slippage_bps` | `config/dev.yaml:197`, `execution_engine/router.py` | 🟡 | Faux sentiment de contrôle — paramètre mort | XS |
| P2-01 | All-or-nothing | `PortfolioRiskManager.can_open_position()` jamais appelé dans le gate d'entrée live — `_portfolio_risk` créé mais mort | `live_trading/runner.py:275` | 🔴 | Gate T1 desactivé en live → drawdown non contrôlé côté PortfolioRisk | M |
| P3-01 | Spread data | `kalman_delta=1e-4` hardcodé dans `KalmanHedgeRatio` — aucun champ config pour le tuner | `models/kalman_hedge.py:57` | 🟡 | Adaptation β non ajustable sans code change | S |
| P4-01 | Modèle coûts | `StrategyBacktestSimulator` instancie `CostModel()` sans lire `get_settings().costs` → `CostConfig` (source de vérité) jamais utilisée en backtest | `backtests/strategy_simulator.py:128` | 🔴 | Coûts backtest décorrélés de la config runtime | M |
| P4-02 | Modèle coûts | Commission incohérente : backtest = `taker_fee_bps=2.0` (0.02 % par leg), live = `costs.commission_pct=0.00035` (0.035 % par leg) → ×1.75 d'écart | `backtests/cost_model.py:24`, `config/settings.py:130` | 🟠 | P&L backtest surestimé (~1.75× sur commission) | M |
| P4-03 | Modèle coûts | `AlgoConfig.impact_bps=2.0` hardcodé dans `StrategyBacktestSimulator._algo_executor` | `backtests/strategy_simulator.py:~160` | 🟡 | Market impact non configurable → backtest peu réaliste | XS |
| P5-01 | Risk engine | B2-02 résidu : `PortfolioRiskManager` initialisé avec `max_drawdown_pct=0.15` (T2) alors que T1=0.10 est voulu | `risk_engine/portfolio_risk.py:28`, `live_trading/runner.py:275` | 🟠 | Tier T1 inactif — PortfolioRiskManager ne coupe pas à 10 % | S |
| P5-02 | Risk engine | `RiskFacade` initialisé avec `initial_equity` mais aucune mise à jour mark-to-market dans le tick loop — equity stale | `live_trading/runner.py:281`, `risk/facade.py` | 🟠 | Calcul de position sizing basé sur equity obsolète | M |
| P6-01 | Routage | `_simulate_fill` et `_paper_fill` : `price = order.limit_price or 0.0` → si order.limit_price is None, fill à 0 $ | `execution_engine/router.py:147,182` | 🟠 | Market orders donnent fill à 0 → coût nul, bilan faux | S |
| P6-02 | Routage | Paper mode : 100 % fill assumé toujours (`filled_qty=order.quantity`) — aucun modèle de partial fill | `execution_engine/router.py:183` | 🟡 | Liquidité surestimée en paper trading | S |

---

## BLOC 1 — Cohérence paramètres

### P1-01 🔴 — `PairTradingStrategy` ignore `SignalCombinerConfig` : poids hardcodés

**Fichier** : `strategies/pair_trading.py` L163–176

```python
# Actual code in PairTradingStrategy.__init__()
_sources = [
    SignalSource("zscore",         weight=0.35),  # ← config says 0.70
    SignalSource("momentum",       weight=0.08, enabled=self._momentum_enabled),  # ← config says 0.30
    SignalSource("ou",             weight=0.15),
    SignalSource("vol_regime",     weight=0.07),
    SignalSource("cross_sectional",weight=0.05),
    SignalSource("intraday_mr",    weight=0.05),
    SignalSource("earnings",       weight=0.10),
    SignalSource("options_flow",   weight=0.07),
    SignalSource("sentiment",      weight=0.08),
]
self._signal_combiner = SignalCombiner(
    sources=_sources,
    entry_threshold=0.30,   # ← config says 0.60
    exit_threshold=0.12,    # ← config says 0.20
)
```

**Attendu** (`config/settings.py` `SignalCombinerConfig`) :
- `zscore_weight = 0.70`, `momentum_weight = 0.30`
- `entry_threshold = 0.60`, `exit_threshold = 0.20`

**Impact** : `SignalCombinerConfig` est entièrement mort pour les backtests. Le docstring EDGECORE décrit "z-score × 0.70 + momentum × 0.30" mais le backtest efficace est "zscore × 0.35 + 8 autres sources × 0.65". Le Sharpe backtesté ne prédit pas le comportement du signal live.

---

### P1-02 🔴 — Momentum désactivé en live

**Fichier** : `live_trading/runner.py` L267–271

```python
self._signal_gen = SignalGenerator(
    threshold_engine=AdaptiveThresholdEngine(
        base_entry=getattr(strat, "entry_z_score", 2.0),
        base_exit=getattr(strat, "exit_z_score", 0.5),
        max_entry=getattr(strat, "z_score_stop", 3.5),
    ),
    # ← momentum_overlay absent → None par défaut
)
```

Dans `signal_engine/generator.py` L281 :
```python
if self.momentum_overlay is not None:   # ← jamais True en live
    m_result = self.momentum_overlay.adjust_signal_strength(...)
```

**Impact** : En live, `MomentumConfig` (enabled=True, weight=0.30) est ignoré. Le signal live est purement z-score, sans composante momentum qui représente 30 % du poids documenté.

---

### P1-03 🟠 — `costs.slippage_bps` non surchargé dans dev.yaml → 1 bps de divergence

**Situation actuelle** :

| Source | Valeur | Chemin |
|--------|--------|--------|
| `CostConfig.slippage_bps` (défaut) | **3.0 bps** | `config/settings.py:123` |
| `CostModelConfig.base_slippage_bps` (backtest) | **2.0 bps** | `backtests/cost_model.py:26` |
| `ExecutionConfig.slippage_bps` (dev.yaml) | 2.0 bps | `config/dev.yaml:197` ← orphelin |

Le routeur lit `get_settings().costs.slippage_bps` (= 3.0, défaut CostConfig aucun override dans dev.yaml). Le backtest utilise `CostModelConfig()` sans jamais lire `get_settings().costs`. Résultat : le live hypothétique paye 3.0 bps, le backtest pose 2.0 bps, soit 50 % de divergence sur le composant spread fixe.

---

### P1-04 🟡 — `ExecutionConfig.slippage_bps` orphelin

`config/dev.yaml:197` : `slippage_bps: 2.0` (section `execution:`)  
Aucun appelant de `get_settings().execution.slippage_bps` nulle part dans la codebase.  
Le routeur lit `get_settings().costs.slippage_bps` — clé différente, section différente. Paramètre trompeur qui donne l'illusion d'un contrôle inexistant.

---

### Bilan BLOC 1 — Tableau paramètres

| Paramètre | Config default | dev.yaml | Backtest (PairTradingStrategy) | Live (runner.py) | Statut |
|-----------|---------------|----------|-------------------------------|-----------------|--------|
| `entry_z_score` | 2.0 | 1.6 | Via strat._cfg_val → settings ✅ | `getattr(strat, ..., 2.0)` ✅ | OK |
| `exit_z_score` | 0.5 | 0.5 | Via settings ✅ | `getattr(strat, ..., 0.5)` ✅ | OK |
| `min_correlation` | 0.7 | 0.60 | Via settings ✅ | Via settings ✅ | OK |
| `max_half_life` | 60 | 70 | Via settings ✅ | `getattr(strat, ..., 60)` ✅ | OK |
| `zscore_weight` | 0.70 | 0.70 | Hardcodé 0.35 ❌ | Non appliqué ❌ | 🔴 P1-01 |
| `momentum_weight` | 0.30 | 0.30 | Hardcodé 0.08 ❌ | Non appliqué ❌ | 🔴 P1-01/02 |
| `entry_threshold` | 0.60 | 0.60 | Hardcodé 0.30 ❌ | Non appliqué ❌ | 🔴 P1-01 |
| `slippage_bps` | 3.0 (CostConfig) | 2.0 (ExecutionConfig — orphelin) | 2.0 (CostModelConfig) | 3.0 (CostConfig) | 🟠 P1-03 |
| `commission_pct` | 0.035 % | — | 0.020 % (taker_fee_bps=2) | 0.035 % | 🟠 P4-02 |
| `max_drawdown_pct` | 0.10 (T1) | 0.10 | Via RiskEngine ✅ | RiskFacade ✅ | OK |

---

## BLOC 2 — Pipeline all-or-nothing

### P2-01 🔴 — `PortfolioRiskManager.can_open_position()` jamais appelé

**Fichier** : `live_trading/runner.py`

```python
# _initialize() — L275 : créé
self._portfolio_risk = PortfolioRiskManager(initial_equity=self.config.initial_capital)

# _step_execute_signals() — L783 : seul RiskFacade appelé
# 4a. Portfolio-level risk check via RiskFacade (unified kill-switch + drawdown gate)
ok, reason = self._risk_facade.can_enter_trade(...)
```

`self._portfolio_risk` n'apparaît que 2 fois dans le fichier (L124 et L275). Aucun appel à `can_open_position()`. `PortfolioRiskManager.update_equity()` et `record_trade_result()` ne sont jamais appelés non plus. Le manager est une coquille vide en live.

**Gate d'entrée réelle** :
```
0. KillSwitch (via RiskFacade.is_halted) ✅
4a. RiskFacade.can_enter_trade() ✅ (RiskEngine interne)
— PortfolioRiskManager : ABSENT du gate ❌
```

**Impact** : Si `RiskFacade` ne réimplémente pas toutes les vérifications de `PortfolioRiskManager` (heat, consecutive losses, position count), certaines protections manquent en live. Notamment `max_portfolio_heat` (95 %) et `max_concurrent_positions`.

---

### Autres gates (OK)

| Gate | Mécanisme | Statut |
|------|-----------|--------|
| KillSwitch | `_step_check_kill_switch()` → `RiskFacade.is_halted` → KillSwitch partagé | ✅ |
| Position risk | `_position_risk` (PositionRiskManager) — utilisé dans `_step_process_stops()` | ✅ |
| Allocator | `_allocator.allocate()` → notional sizing | ✅ |
| BrokerReconciler | `_maybe_reconcile()` toutes les 5 min en live | ✅ |
| Fill confirmation | `_process_fill_confirmations()` — A-02 | ✅ |

---

## BLOC 3 — Données d'entrée spread

### P3-01 🟡 — `kalman_delta` non configurable depuis Settings

**Fichier** : `models/kalman_hedge.py:57`

```python
def __init__(
    self,
    delta: float = 1e-4,     # ← pas de champ config correspondant
    ve: float = 1e-3,
    ...
):
```

`StrategyConfig` et `SignalCombinerConfig` n'exposent pas de `kalman_delta`. La vitesse d'adaptation du filtre de Kalman (paramètre critique pour le ratio hedge dynamique) ne peut être ajustée sans modifier le code. Pour un système en production, ce paramètre devrait être tuneable.

---

### Points vérifiés (OK)

| Point | Vérification | Statut |
|-------|--------------|--------|
| Kalman warm-up | `SpreadModel.__init__` : boucle complète sur series historique avant démarrage | ✅ |
| Spread direction | `y - (alpha + beta*x)` — convention parée pour long/short | ✅ |
| use_kalman depuis config | `StrategyConfig.use_kalman=True`, dev.yaml `use_kalman: true` → transmis à SpreadModel | ✅ |
| β recalcul | `hedge_ratio_reestimation_days=7` (StrategyConfig) → `PositionRiskConfig.hedge_reestimation_days=7` | ✅ |
| Z-score window | `ZScoreCalculator` — window par défaut, cohérent avec `lookback_window` | ✅ |
| Stationarité monitor | `StationarityMonitor` wired dans `SignalGenerator` | ✅ |

---

## BLOC 4 — Modèle de coûts

### P4-01 🔴 — `StrategyBacktestSimulator` n'utilise jamais `get_settings().costs`

**Fichier** : `backtests/strategy_simulator.py:128`

```python
self.cost_model = cost_model or CostModel()
```

`CostModel()` s'initialise avec `CostModelConfig()` (valeurs hardcodées). La `CostConfig` (singleton settings) n'est jamais injectée. 

**Impact** : Si l'on configure `costs.slippage_bps=5.0` dans dev.yaml (pour contrainte de stress), le backtest tourne quand même à 2.0 bps. La source de vérité (`CostConfig`) est contournée en backtest.

**Correction attendue** :
```python
from config.settings import get_settings as _gs
_costs = _gs().costs
self.cost_model = cost_model or CostModel(CostModelConfig(
    base_slippage_bps=_costs.slippage_bps,
    taker_fee_bps=_costs.taker_fee_bps,
    borrowing_cost_annual_pct=_costs.borrowing_cost_annual * 100,
    slippage_model=_costs.slippage_model,
))
```

---

### P4-02 🟠 — Commission incohérente backtest vs live (~×1.75)

| Contexte | Paramètre | Valeur | Calcul par leg $10k |
|----------|-----------|--------|---------------------|
| Backtest (`CostModelConfig`) | `taker_fee_bps` | 2.0 | **$2.00** |
| Live router (`CostConfig`) | `commission_pct` | 0.00035 | **$3.50** |

Le backtest sous-estime la commission per-leg de $1.50 (75 % de plus en live). Sur 4 legs par round-trip, l'écart est $6.00 per trade sur $10k notional.

---

### P4-03 🟡 — `AlgoConfig.impact_bps=2.0` hardcodé

**Fichier** : `backtests/strategy_simulator.py` (~L160)

```python
self._algo_executor = TWAPExecutor(
    config=AlgoConfig(
        algo_type=AlgoType.TWAP,
        num_slices=10,
        impact_bps=2.0,        # ← hardcodé, non relié à CostConfig
        max_participation=0.05,
    )
)
```

`CostConfig.taker_fee_bps=2.0` et `AlgoConfig.impact_bps=2.0` coïncident par hasard — pas d'alignement intentionnel.

---

## BLOC 5 — Alignement risk engine

### P5-01 🟠 — B2-02 résidu : `PortfolioRiskManager` initialisé à T2 (0.15) au lieu de T1 (0.10)

**Fichier** : `risk_engine/portfolio_risk.py:28`
```python
@dataclass
class PortfolioRiskConfig:
    max_drawdown_pct: float = 0.15   # ← défaut = T2 (KillSwitch)
    ...
```

**Fichier** : `live_trading/runner.py:275`
```python
self._portfolio_risk = PortfolioRiskManager(
    initial_equity=self.config.initial_capital,
    # ← aucun config passé → utilise défaut 0.15
)
```

T1 est censé déclencher à 10 % (avant le KillSwitch à 15 %). Avec `max_drawdown_pct=0.15`, même si `_portfolio_risk.can_open_position()` était appelé, il ne couperait pas à T1.

**Correction** :
```python
from risk_engine.portfolio_risk import PortfolioRiskConfig
self._portfolio_risk = PortfolioRiskManager(
    initial_equity=self.config.initial_capital,
    config=PortfolioRiskConfig(
        max_drawdown_pct=get_settings().risk.max_drawdown_pct,  # T1 = 0.10
    ),
)
```

---

### P5-02 🟠 — `RiskFacade` equity stale : jamais mise à jour dans le tick loop

**Fichier** : `live_trading/runner.py`

`RiskFacade` est initialisé avec `initial_equity=100_000`. Dans `_tick()`, `_tick_balance = self._router.get_account_balance()` est appelé une fois par tick pour sizing, mais **aucun** `self._risk_facade.risk_engine.update_equity(_tick_balance)` n'est présent.

**Impact** : Le `RiskEngine` interne à `RiskFacade` calcule le drawdown vs equity initiale (100k), pas vs equity courante. Après une période de forte croissance (equity = 150k), un drawdown de 15k (10 % de la vraie equity) passerait comme 10 % vs 100k initial, ce qui est correct par coïncidence — mais en cas de perte initiale (equity = 85k), les calculs deviennent erronés.

---

### Tiers risk (OK)

| Tier | Paramètre | Valeur | Vérification |
|------|-----------|--------|--------------|
| T1 | `RiskConfig.max_drawdown_pct` | 0.10 | `settings.py` + dev.yaml ✅ |
| T2 | `KillSwitchConfig.max_drawdown_pct` | 0.15 | `kill_switch.py:68` ✅ |
| T3 | `StrategyConfig.internal_max_drawdown_pct` | 0.20 | `settings.py:52` ✅ |
| Assert | `_assert_risk_tier_coherence()` | T1≤T2≤T3 | Appelé à chaque init Settings ✅ |

---

## BLOC 6 — Routage d'exécution

### P6-01 🟠 — Fill à 0 $ si `limit_price=None` (market orders)

**Fichier** : `execution_engine/router.py:147` (`_simulate_fill`) et `L182` (`_paper_fill`)

```python
price = order.limit_price or 0.0   # ← si limit_price is None → 0.0
...
fill_price=price * (1 + slippage / 10_000 if side_str == "buy" else 1 - slippage / 10_000),
commission=order.quantity * price * get_settings().costs.commission_pct,
```

Avec `price=0.0` : fill à $0, commission $0, slippage $0. Un market order passe gratuitement et enregistre un bénéfice irréaliste.

**Contexte** : Dans `_step_process_stops()`, les ordres de clôture d'urgence sont créés avec `limit_price=None` :
```python
close_order = Order(
    order_id=close_order_id,
    symbol=pair_key,
    side=close_side,
    quantity=abs(qty),
    limit_price=None,       # ← market order → fill à 0 $ en backtest/paper
    order_type="MARKET",
)
```

---

### P6-02 🟡 — Paper mode : 100 % fill systématique

**Fichier** : `execution_engine/router.py:183`

```python
return TradeExecution(
    ...
    filled_qty=order.quantity,   # ← toujours 100 %, aucun partial
    ...
)
```

En paper mode, tous les ordres sont réputés exécutés en totalité immédiatement. Pour des positions importantes sur des actions moins liquides, cela surestime l'efficacité d'exécution.

---

### Points vérifiés (OK)

| Point | Vérification | Statut |
|-------|--------------|--------|
| Rate limiter IBKR | `self._rate_limiter.acquire()` à `router.py:268` avant `ibkr_engine.submit_order()` | ✅ |
| Mode selection | `{"live": ExecutionMode.LIVE, "paper": ExecutionMode.PAPER}[config.mode]` | ✅ |
| Erreurs informatives IBKR | 2104/2106/2158 — gestion dans `ibkr_engine.py` (hors scope direct) | ✅ |
| Commission live | `get_settings().costs.commission_pct` | ✅ |
| B5-02 statut | `slippage` lit `get_settings().costs.slippage_bps` (was hardcoded 2.0) | ✅ (fixé) |

---

## Synthèse exécutive

### Criticité par bloc

| Bloc | 🔴 | 🟠 | 🟡 | Verdict |
|------|----|----|----|----|
| B1 Cohérence params | 2 | 1 | 1 | ⚠️ Déficit majeur config→code |
| B2 All-or-nothing | 1 | 0 | 0 | ⚠️ Gate PortfolioRisk mort |
| B3 Spread data | 0 | 0 | 1 | ✅ Stable |
| B4 Modèle coûts | 1 | 1 | 1 | ⚠️ Divergence backtest/live |
| B5 Risk engine | 0 | 2 | 0 | ⚠️ T1 inactif, equity stale |
| B6 Routage | 0 | 1 | 1 | ⚠️ Market orders au prix zéro |
| **TOTAL** | **4** | **5** | **4** | |

---

### Top 3 — Priorité absolue

1. **P1-01 + P1-02** — Backtest et live ont des pipelines signal fondamentalement différents. Le Sharpe backtesté (9 sources, zscore=0.35) ne correspond pas au live (z-score seul, momentum absent). **Invalide toute décision de déploiement basée sur le backtest.**

2. **P4-01 + P4-02** — `StrategyBacktestSimulator` bypasse `get_settings().costs`, rendant la configuration des coûts ineffective en backtest. La commission est 75 % plus élevée en live qu'en backtest — le net Sharpe réel sera inférieur aux projections.

3. **P2-01** — `PortfolioRiskManager` est instancié mais jamais interrogé. La protection contre la chaleur portefeuille (95 %) et le comptage de positions perdantes consécutives ne sont pas actifs dans le gate d'entrée live.

---

### Dette connue confirmée / infirmée

| Issue | Statut avant audit | Statut après audit |
|-------|-------------------|-------------------|
| B5-02 (router.py slippage hardcodé) | 🔴 Ouvert | ✅ **Fixé** — lit `get_settings().costs.slippage_bps` |
| B2-02 (RiskFacade vs composants dual) | 🟠 Partiellement corrigé | 🟠 **Résidu** — KillSwitch partagé ✅, mais PortfolioRiskManager mort (P2-01) et equity stale (P5-02) |
| B4-05 (backtester sans `__init__.py`) | 🟡 Signalé | ✅ **Résolu** — `backtester/__init__.py` présent |

---

*Généré par GitHub Copilot (Claude Sonnet 4.6) · Audit Pipeline Engineering EDGECORE · `lfs-migration-preview`*
