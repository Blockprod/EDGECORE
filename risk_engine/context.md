# risk_engine/ — Context Module

## Responsabilité

Contrôles de risque **opérationnels** : stops par position, surveillance du portfolio, halt global d'urgence (kill-switch). Ce module est le gardien entre les signaux de trading et l'exécution des ordres.

**Ce module est la couche de sécurité opérationnelle.** Il connaît le contexte du marché en temps réel et peut bloquer ou interrompre le trading à tout moment.

---

## Ce que ce module FAIT

| Fichier | Classe | Rôle |
|---------|--------|------|
| `position_risk.py` | `PositionRiskManager` | Checks par position : trailing stop, time stop, P&L stop, hedge drift |
| `portfolio_risk.py` | `PortfolioRiskManager` | Checks portfolio : drawdown, daily loss, consecutive losses, heat |
| `kill_switch.py` | `KillSwitch` | Halt global d'urgence — 6 conditions — reset manuel requis |

---

## Ce que ce module NE FAIT PAS

- ❌ Calcule le sizing des positions → `portfolio_engine/`
- ❌ Modélise le risque mathématique (VaR, Kelly, factor) → `risk/`
- ❌ Émet des ordres → `execution_engine/`
- ❌ Génère des signaux → `signal_engine/`

---

## Hiérarchie risk tiers (CRITIQUE — NE PAS MODIFIER)

```
Tier 1 : RiskConfig.max_drawdown_pct          = 0.10  (10%)
         → Déclenche halt nouvelles ENTRÉES
         → Source : config/settings.py RiskConfig

Tier 2 : KillSwitchConfig.max_drawdown_pct    = 0.15  (15%)
         → Déclenche HALT GLOBAL (kill-switch)
         → Source : risk_engine/kill_switch.py KillSwitchConfig

Tier 3 : StrategyConfig.internal_max_drawdown_pct = 0.20  (20%)
         → Breaker interne stratégie
         → Source : config/settings.py StrategyConfig

Assertion au boot : T1 ≤ T2 ≤ T3
```

### Vérification
```python
# Appelé dans Settings.__init__() via _assert_risk_tier_coherence()
# En cas de violation → ValueError levé au démarrage
venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"
```

---

## Contrats

### `PositionRiskManager`

```python
class PositionRiskManager:
    def register_position(
        self, pair_key: str, side: str, entry_z: float,
        entry_price: float, entry_bar: int, half_life: Optional[float],
        notional: float
    ) -> None: ...

    def check(
        self, pair_key: str, current_z: float,
        current_bar: int, pnl_pct: float
    ) -> Tuple[bool, Optional[str]]:
        # Returns (should_exit, reason)
        # reason: "trailing_stop", "time_stop", "pnl_stop", "hedge_drift"
```

### `PortfolioRiskManager`

```python
class PortfolioRiskManager:
    def can_open_position(self, position_risk_pct: float) -> Tuple[bool, str]: ...
    def record_trade_result(self, pnl: float) -> None: ...
    def update_equity(self, current_equity: float) -> None: ...
    def get_state(self) -> PortfolioRiskState: ...

# PortfolioRiskState fields :
# current_equity, peak_equity, drawdown_pct, daily_loss_pct,
# consecutive_losses, open_positions, portfolio_heat,
# is_halted, halt_reason
```

### `KillSwitch`

```python
class KillSwitch:
    is_active: bool           # True si le switch est déclenché

    def check(
        self, drawdown_pct: float, daily_loss_pct: float,
        consecutive_losses: int, seconds_since_last_data: float,
        current_vol: float, historical_vol_mean: float,
    ) -> Tuple[bool, KillReason, str]: ...

    def activate(self, reason: KillReason, message: str = "") -> None: ...
    def reset(self, operator_id: str) -> None: ...
    def get_state(self) -> KillSwitchState: ...
```

### `KillReason` enum
```python
DRAWDOWN | DAILY_LOSS | CONSECUTIVE_LOSSES |
VOLATILITY_EXTREME | DATA_STALE | MANUAL | EXCHANGE_ERROR | UNKNOWN
```

---

## KillSwitchConfig (valeurs par défaut codées dans kill_switch.py)

```python
@dataclass
class KillSwitchConfig:
    max_drawdown_pct:         float = 0.15   # Tier 2
    max_daily_loss_pct:       float = 0.03
    max_consecutive_losses:   int   = 5
    max_data_stale_seconds:   int   = 300    # 5 minutes
    extreme_vol_multiplier:   float = 3.0    # σ au-dessus de la moyenne historique
    alert_on_activation:      bool  = True
```

---

## Intégration dans le pipeline

### Via `RiskFacade` (chemin recommandé)
```python
# risk/facade.py compose KillSwitch + RiskEngine
from risk.facade import RiskFacade

facade = RiskFacade(initial_equity=100_000.0)
ok, reason = facade.can_enter_trade(
    symbol_pair="AAPL_MSFT",
    position_size=5000.0,
    current_equity=98_000.0,
    volatility=0.018,
    drawdown_pct=0.02,
)
```

### Via `LiveTradingRunner` (chemin actuel — B2-02 dette)
```python
# live_trading/runner.py instancie séparément (à corriger) :
self._position_risk  = PositionRiskManager()         # Tier indépendant
self._portfolio_risk = PortfolioRiskManager(...)      # Tier indépendant
self._kill_switch    = KillSwitch()                   # Tier indépendant
self._risk_facade    = RiskFacade(...)                # Devrait tout contenir
```

---

## Dépendances internes

```
risk_engine/position_risk.py   ←── execution/trailing_stop.py
                               ←── execution/time_stop.py
                               ←── models/hedge_ratio_tracker.py
                               ←── models/stationarity_monitor.py

risk_engine/portfolio_risk.py  ←── (standalone)

risk_engine/kill_switch.py     ←── (standalone — aucune dépendance externe)
                               # intentionnel : dernier rempart, zero deps
```

---

## Relation avec `risk/` (module mathématique)

| `risk_engine/` | `risk/` |
|----------------|---------|
| Contrôles opérationnels | Modélisation mathématique du risque |
| `KillSwitch`, stops, drawdown | `RiskEngine`, Kelly, VaR, factor model, beta-neutral |
| Décide de BLOQUER/HALTER | Calcule la taille optimale |
| Sans dépendance à `risk/` | Dépend de `risk_engine/` via `RiskFacade` |

**`risk/facade.py`** est le pont : compose `RiskEngine` (risk/) et `KillSwitch` (risk_engine/) dans une interface unifiée.
