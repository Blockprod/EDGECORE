# EDGECORE — Context global pour Claude

## Ce que fait ce projet

Système de **statistiques-arbitrage (stat-arb) sur US equities** via Interactive Brokers.
Stratégie : paires cointégrées, signal z-score + momentum, exécution IBKR en paper/live.
Production-ready : Docker, Prometheus, Grafana, audit trail, kill-switch 3 tiers.

---

## Pipeline complet (source → ordre IBKR)

```
[Yahoo Finance / IBKR reqHistoricalData]
        │ pd.DataFrame OHLCV (colonnes=symbols, index=DatetimeIndex)
        ▼
data/loader.py (DataLoader)
data/validators.py → data/preprocessing.py
        │
        ▼
universe/manager.py (UniverseManager)          # filtre liquidité, sector_map
  └─ universe/scanner.py                        # dynamic scanner (scan_enabled=False par défaut)
  └─ universe/correlation_prefilter.py
        │ List[str] symbols actifs
        ▼
pair_selection/discovery.py (PairDiscoveryEngine)
  ├─ models/cointegration.py (engle_granger_test → Johansen confirmation → Newey-West HAC)
  ├─ models/spread.py (SpreadModel — résidus OLS ou Kalman)
  ├─ pair_selection/filters.py
  └─ pair_selection/blacklist.py (cooldown après max_consecutive_losses=2, 30 jours)
        │ List[(sym1, sym2, beta, half_life)]
        ▼
signal_engine/generator.py (SignalGenerator)
  ├─ models/spread.py + models/kalman_hedge.py  # hedge ratio dynamique si use_kalman=True
  ├─ signal_engine/zscore.py                    # z-score normalisé sur spread
  ├─ signal_engine/adaptive.py (AdaptiveThresholdEngine)
  │     base_entry=entry_z_score, base_exit=exit_z_score, max_entry=z_score_stop=3.5
  └─ signal_engine/combiner.py (SignalCombiner)
        # composite = zscore_weight×0.70 + momentum_weight×0.30
        # entry si composite ≥ entry_threshold=0.6
        # exit  si composite ≤ exit_threshold=0.2
        │ List[TradingSignal]
        ▼
risk_engine/position_risk.py (PositionRiskManager.check())
  ├─ execution/trailing_stop.py (TrailingStopManager — widening_threshold=1.0σ)
  ├─ execution/time_stop.py (TimeStopManager — 3×half_life, max 60 bars)
  └─ models/hedge_ratio_tracker.py (reestimation toutes les 7 jours)
        ▼
risk_engine/portfolio_risk.py (PortfolioRiskManager.check())
  # drawdown ≤ 15%, daily_loss ≤ 3%, consecutive_losses ≤ 5, heat ≤ 95%
        ▼
risk_engine/kill_switch.py (KillSwitch.is_active)   ← HALT TOTAL
  # 6 conditions : drawdown, daily_loss, consecutive_losses,
  #                extreme_vol, data_stale, manual
        ▼
portfolio_engine/allocator.py (PortfolioAllocator.size())
  └─ portfolio_engine/concentration.py
        │ TradeOrder ou Signal dimensionné
        ▼
execution_engine/router.py (ExecutionRouter.submit_order())
  ├─ BACKTEST → _simulate_fill()  (fills instantanés)
  ├─ PAPER    → execution/paper_execution.py (PaperExecutionEngine)
  └─ LIVE     → execution/ibkr_engine.py (IBKRExecutionEngine via ib_insync)
        │ TradeExecution (fill confirmé)
        ▼
execution/reconciler.py (BrokerReconciler)   ← toutes les 5 min
persistence/audit_trail.py                  ← crash recovery
monitoring/metrics.py + monitoring/dashboard.py  ← Prometheus / Grafana
```

---

## Table des modules avec responsabilité réelle

| Module | Entrée | Sortie | Ne FAIT PAS |
|--------|--------|--------|-------------|
| `data/` | symboles + dates | `pd.DataFrame` OHLCV | calcul de spread |
| `universe/` | config + DataFrame | `List[str]` symbols | signaux |
| `pair_selection/` | symbols + prices | `List[Pair]` cointégrées | sizing |
| `models/` | prix, spreads | metrics (HL, beta, z) | décisions de trading |
| `signal_engine/` | pairs + prices | `List[TradingSignal]` | risk checks |
| `risk_engine/` | signal + positions | `bool can_enter` | sizing |
| `risk/` | equity + positions | risk metrics | ordre IBKR |
| `portfolio_engine/` | signal + capital | quantités dimensionnées | risk checks |
| `execution_engine/` | `TradeOrder` | `TradeExecution` | stratégie |
| `execution/` | `Order` (base) | fill IBKR / paper | signal |
| `backtests/` | historical data | `BacktestMetrics` | live trading |
| `backtester/` | config wrapper | `BacktestResult` | algo pur |
| `monitoring/` | métriques système | dashboard / alertes | trading |
| `persistence/` | états positions | recovery JSON | métriques |

---

## Paramètres clés extraits de config/

### StrategyConfig (config/settings.py)
```python
entry_z_score:        float = 2.0    # prod; dev=1.6
exit_z_score:         float = 0.5    # test=0.0 (bug historique corrigé en prod=0.5)
entry_z_min_spread:   float = 0.50   # filtre micro-déviation ($)
z_score_stop:         float = 3.5    # stop-loss z-score
min_correlation:      float = 0.7    # dev lowered to 0.60
max_half_life:        int   = 60     # jours; dev=70
lookback_window:      int   = 252    # dev=120
use_kalman:           bool  = True   # hedge ratio dynamique
johansen_confirmation:bool  = True   # double-screening EG + Johansen
newey_west_consensus: bool  = True   # EG + HAC agreement requis
short_sizing_multiplier: float = 0.50
internal_max_drawdown_pct: float = 0.20  # Tier 3
```

### RiskConfig
```python
max_drawdown_pct:     float = 0.10   # Tier 1 — halt nouvelles entrées
max_risk_per_trade:   float = 0.005  # 0.5% equity
max_concurrent_positions: int = 10
max_daily_loss_pct:   float = 0.02
```

### KillSwitchConfig (risk_engine/kill_switch.py)
```python
max_drawdown_pct:     float = 0.15   # Tier 2 — halt global
max_daily_loss_pct:   float = 0.03
max_consecutive_losses: int = 5
max_data_stale_seconds: int = 300
extreme_vol_multiplier: float = 3.0
```

### CostConfig (source de vérité pour les coûts)
```python
slippage_bps:         float = 3.0
commission_pct:       float = 0.00035  # IBKR US equity
borrowing_cost_annual:float = 0.005    # 0.5% GC rate
max_slippage_bps:     float = 50.0
slippage_model:       str   = "adaptive"
```

### SignalCombinerConfig
```python
zscore_weight:   float = 0.70
momentum_weight: float = 0.30
entry_threshold: float = 0.6
exit_threshold:  float = 0.2
```

---

## Ce qui ne doit PAS changer

1. **Risk tier hierarchy** : T1(10%) ≤ T2(15%) ≤ T3(20%) — assertion au boot
2. **OrderStatus enum** dans `execution/base.py` — source de vérité unique
3. **`_ibkr_rate_limiter`** module-level dans `execution/ibkr_engine.py` — partagé entre instances
4. **`get_settings()` singleton** — une seule instance par processus, thread-safe par `__new__`
5. **Environments** : `["dev", "test", "prod"]` uniquement — `production` est invalide
6. **`_KNOWN_SECTIONS`** dans `settings._load_yaml()` — rejette les sections YAML inconnues
7. **`_assert_risk_tier_coherence()`** appelé au boot dans `Settings.__init__()`
8. **Cython .pyd** : deux fichiers nécessaires (cp311 + cp313) pour venv et system Python

---

## Dettes techniques connues (ne pas aggraver)

| ID | Localisation | Description | Fix requis |
|----|-------------|-------------|-----------|
| B5-01 | `Dockerfile:34`, `docker-compose.yml:11` | `EDGECORE_ENV=production` → fallback `dev.yaml` silencieux | Changer en `prod` |
| B5-02 | `execution_engine/router.py:162,189` | `slippage = 2.0` hardcodé, ignore `CostConfig` | Lire `get_settings().costs` |
| B2-01 | `execution_engine/router.py:37` | `TradeOrder` duplique `Order` de `execution/base.py` | Unifier |
| B2-02 | `live_trading/runner.py:224-231` | `PositionRiskManager` + `PortfolioRiskManager` + `KillSwitch` + `RiskFacade` instanciés séparément | `RiskFacade` devrait tout contenir |
| B4-05 | `backtester/` | Pas de `__init__.py` — pas importable | Créer `__init__.py` |
