# execution/ — Context Module

## Responsabilité

Implémentations concrètes de l'exécution des ordres : connexion broker IBKR (via `ib_insync` et `ibapi`), simulation paper, gestion des positions, stops, slippage, réconciliation.

**Ce module est la couche interne.** Il est appelé par `execution_engine/router.py`, jamais directement par `live_trading/` ou `signal_engine/`.

---

## Ce que ce module FAIT

| Fichier | Classe | Rôle |
|---------|--------|------|
| `base.py` | `Order`, `OrderSide`, `OrderStatus`, `BaseExecutionEngine` | Types canoniques d'ordres — **source de vérité** |
| `ibkr_engine.py` | `IBKRExecutionEngine`, `IBGatewaySync` | Connexion IBKR réelle (ib_insync + ibapi EClient) |
| `paper_execution.py` | `PaperExecutionEngine` | Simulation paper avec modèle de coût |
| `reconciler.py` | `BrokerReconciler`, `ReconciliationReport` | Détecte les divergences broker/interne |
| `trailing_stop.py` | `TrailingStopManager` | Stop sur élargissement du spread (1σ défaut) |
| `time_stop.py` | `TimeStopManager` | Stop sur durée de détention (3×half_life, max 60 bars) |
| `position_stops.py` | `PositionStopManager` | P&L stop par position (10% défaut) |
| `partial_profit.py` | `PartialProfitManager` | Prise de profit partielle |
| `rate_limiter.py` | `TokenBucketRateLimiter` | 45/s sustained, burst 10 (hard cap IBKR = 50/s) |
| `order_lifecycle.py` | `OrderLifecycleManager` | Transition d'états d'un ordre (PENDING→FILLED etc.) |
| `slippage.py` | `SlippageModel` | Calcul slippage adaptatif / fixe / volume-based |
| `modes.py` | `ExecutionContext`, `ExecutionMode` | Contexte d'exécution papier/live/backtest |
| `borrow_check.py` | `BorrowAvailabilityChecker` | Vérification shortable shares via tick 236 |
| `concentration_limits.py` | `ConcentrationLimitsChecker` | Max exposition sector/symbol |
| `shutdown_manager.py` | `ShutdownManager` | Arrêt gracieux sur signal OS |
| `venue_models.py` | `VenueModel` | Modélisation des venues d'exécution |

---

## Ce que ce module NE FAIT PAS

- ❌ Génère des signaux de trading → `signal_engine/`
- ❌ Calcule des z-scores ou spreads → `models/`
- ❌ Prend des décisions de risque → `risk_engine/` + `risk/`
- ❌ Size les positions → `portfolio_engine/`
- ❌ Route les ordres entre modes → `execution_engine/router.py`

---

## Contrats

### `Order` (execution/base.py) — type canonique interne
```python
@dataclass
class Order:
    order_id: str
    symbol: str
    side: OrderSide       # BUY | SELL
    quantity: float
    limit_price: Optional[float]
    order_type: str = "LIMIT"
    created_at: datetime = None    # aware s'il est initialisé via datetime.now(timezone.utc)
    filled_at: Optional[datetime] = None
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
```

### `OrderStatus` (execution/base.py) — enum source de vérité
```python
PENDING | SUBMITTED | FILLED | PARTIAL | PARTIALLY_FILLED |
CANCELLED | REJECTED | FAILED | TIMEOUT | ERROR | UNKNOWN
```

### `ReconciliationDivergence.detected_at`
Champ `datetime` **aware** (timezone.utc) via `field(default_factory=lambda: datetime.now(timezone.utc))`.  
Attention : les tests qui comparent avec `datetime.now()` naïf génèrent `TypeError`. Toujours utiliser `datetime.now(timezone.utc)` dans les tests de réconciliation.

---

## Dépendances internes

```
execution/ibkr_engine.py  ←── execution/rate_limiter.py
                          ←── execution/base.py (Order, OrderStatus)
                          ←── common/retry.py (RetryPolicy)
execution/reconciler.py   ←── execution/base.py
execution/paper_execution.py ←── execution/slippage.py
                              ←── config.settings (CostConfig)
execution/position_stops.py  ←── (standalone — lit config)
execution/trailing_stop.py   ←── (standalone)
execution/time_stop.py       ←── (standalone)
```

---

## Exceptions définies

| Exception | Déclencheur |
|-----------|-------------|
| `ConnectionError` | Circuit breaker ouvert ou 3 retries épuisés |
| `RuntimeError("[SECURITY] IBKR client_id already in use")` | `client_id` dupliqué |
| `RuntimeError("Rate limiter timeout")` | `acquire()` timeout > 5s |

---

## Points d'attention critiques

1. **`_ibkr_rate_limiter`** est **module-level** dans `ibkr_engine.py` → partagé entre toutes les instances. Ne pas créer un second limiter local.

2. **Idempotency guard** dans `IBKRExecutionEngine.submit_order()` : si `order.order_id` est déjà dans `_persisted_order_ids`, rejette silencieusement. Critique pour le crash recovery.

3. **`cancelHistoricalData` + sleep 0.3s** obligatoire après une erreur 162/200/354 pour éviter que IB Gateway accumule des réponses retardées.

4. **`reqMktData(genericTickList="236", snapshot=True)`** pour les shortable shares → toujours `cancelMktData(req_id)` après réception même en cas d'erreur.

5. **`ReconciliationDivergence.detected_at`** → champ aware (`timezone.utc`). Bug historique corrigé : un `detected_at` naïf causerait `TypeError: can't compare offset-naive and offset-aware datetimes`.
