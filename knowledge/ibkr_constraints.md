# IBKR Constraints — EDGECORE Knowledge Base

## Connexion & Ports

| Mode | Application | Port défaut | Variable env |
|------|-------------|-------------|--------------|
| Paper trading (ib_insync) | TWS Paper | 7497 | `IBKR_PORT=7497` |
| Live trading (ib_insync) | TWS Live | 7496 | `IBKR_PORT=7496` |
| Paper trading (ibapi sync) | IB Gateway Paper | 4002 | `IBKR_PORT=4002` |
| Live trading (ibapi sync) | IB Gateway Live | 4001 | `IBKR_PORT=4001` |

**IBKRExecutionEngine** (ib_insync) : défaut port 7497 (paper).  
**IBGatewaySync** (ibapi.client.EClient) : défaut port 4002 via `os.getenv("IBKR_PORT", "4002")`.

```python
# IBKRExecutionEngine (ib_insync)
self.port = port or int(os.getenv("IBKR_PORT", "7497"))

# IBGatewaySync (ibapi EClient)
self.port = port if port is not None else int(os.getenv("IBKR_PORT", "4002"))
```

### Client ID
- Chaque connexion doit avoir un `client_id` **unique** par processus / worker.
- EDGECORE détecte les doublons via `IBKRExecutionEngine._active_client_ids` (registre de classe).
- Duplication → `RuntimeError("[SECURITY] IBKR client_id already in use")`.
- Défaut : `client_id=1` via `os.getenv("IBKR_CLIENT_ID", "1")`.

---

## Rate Limits TWS API

| Paramètre | Valeur | Conséquence si dépassé |
|-----------|--------|----------------------|
| Hard cap messages/sec | **50 req/s** | Déconnexion automatique TWS |
| Rate limiter sustenu | **45 req/s** | Marge de sécurité |
| Burst capacity | **10 tokens** | Tolérance rafrale courte |

### Implémentation
```python
# Module-level — partagé entre toutes les instances IBKRExecutionEngine
from execution.rate_limiter import TokenBucketRateLimiter
_ibkr_rate_limiter = TokenBucketRateLimiter(rate=45, burst=10)

# OBLIGATOIRE avant tout appel API
_ibkr_rate_limiter.acquire()
self._ib.placeOrder(contract, ib_order)
```

Source : `execution/ibkr_engine.py:20` et `execution/rate_limiter.py`.

---

## Codes d'erreur IBKR

### Erreurs informatives — NE PAS interrompre le process

| Code | Signification |
|------|--------------|
| 2104 | Market data farm connected |
| 2106 | Active historical data server |
| 2158 | Sec-Def data farm connected |

```python
if errorCode not in (2104, 2106, 2158):
    logger.warning("[IBWrapper] Error %d: %s (reqId=%d)", ...)
```

### Erreurs données historiques — interrompre + `cancelHistoricalData`

| Code | Signification |
|------|--------------|
| 162 | Historical market data service error (no data) |
| 200 | No security definition found |
| 354 | Requested market data not subscribed |

```python
if err and err[0] == req_id and err[1] in (162, 200, 354):
    break
# Puis toujours :
self.client.cancelHistoricalData(req_id)
time.sleep(0.3)  # laisse IB Gateway flush les réponses retardées
```

### Autres erreurs notables

| Code | Signification | Action |
|------|--------------|--------|
| 322 | Duplicate ticker ID | Utiliser `_get_next_req_id()` strict (compteur incrémental depuis 10) |
| 430 | Fundamental data unavailable | Log warning, continuer sans données |
| 366 | reqHistoricalData response retardée | Gérer avec `cancelHistoricalData` |

---

## Types de contrats (US Equities)

```python
from ibapi.contract import Contract
# ou
from ib_insync import Stock

# ibapi
contract = Contract()
contract.symbol   = "AAPL"
contract.secType  = "STK"
contract.exchange = "SMART"   # routage intelligent IB
contract.currency = "USD"

# ib_insync (IBKRExecutionEngine)
contract = Stock("AAPL", "SMART", "USD")
```

- `secType = "STK"` uniquement — EDGECORE ne trade pas d'options/futures.
- `exchange = "SMART"` — routage automatique IBKR.

---

## Types d'ordres supportés

| Type | ib_insync | Condition |
|------|-----------|-----------|
| Limit | `LimitOrder(action, qty, price)` | Si `order.limit_price is not None` |
| Market | `MarketOrder(action, qty)` | Si `order.limit_price is None` |

```python
from ib_insync import LimitOrder, MarketOrder, Stock

action = 'BUY' if order.side == OrderSide.BUY else 'SELL'

if order.limit_price:
    ib_order = LimitOrder(action, order.quantity, order.limit_price)
else:
    ib_order = MarketOrder(action, order.quantity)
```

**Important** : stop orders, bracket orders, OCA groups — NON IMPLÉMENTÉS dans EDGECORE.  
Les stops sont gérés côté application (`execution/trailing_stop.py`, `execution/time_stop.py`).

---

## Données historiques

### `reqHistoricalData` via IBGatewaySync

```python
self.client.reqHistoricalData(
    req_id,
    contract,
    endDateTime="",         # chaîne vide = maintenant
    durationStr="1 Y",      # "1 D", "1 W", "1 M", "1 Y", "5 Y"
    barSizeSetting="1 day", # "1 min", "5 mins", "1 hour", "1 day"
    whatToShow="TRADES",    # "TRADES", "BID_ASK", "MIDPOINT"
    useRTH=1,               # Regular Trading Hours uniquement
    formatDate=1,           # 1 = YYYYMMDD HH:MM:SS string
    keepUpToDate=False,
    chartOptions=[],
)
```

### Récupération shortable shares (generic tick 236)

```python
req_id = self._get_next_req_id()
self.client.reqMktData(req_id, contract, "236", True, False, [])
# Attendre tickGeneric(tickType=236, value=shares)
self.client.cancelMktData(req_id)  # toujours cancel après
```

### Earnings calendar (CalendarReport)

```python
self.client.reqFundamentalData(self._get_next_req_id(), contract, "CalendarReport", [])
# Retourne XML raw, à parser avec ElementTree
```

---

## Gestion des Request IDs

- Compteur `_req_id_counter` commence à **10** (évite les IDs réservés système IB).
- Incrémenté **avant** chaque requête via `_get_next_req_id()` (thread-safe via `_req_id_lock`).
- Un reqId = une seule requête active simultanée.
- Réutiliser un reqId avant `cancelHistoricalData` → erreur 322.

```python
def _get_next_req_id(self) -> int:
    with self._req_id_lock:
        self._req_id_counter += 1
        return self._req_id_counter
```

---

## Circuit Breaker & Reconnexion (IBKRExecutionEngine)

| Paramètre | Valeur |
|-----------|--------|
| Max failures consécutives | 5 |
| Auto-reset timeout | 300s (5 min) |
| Retry attempts | 3 (5s, 15s, 30s + ±30% jitter) |

```python
retry_base_delays = [5, 15, 30]
jitter = random.uniform(0, base_delay * 0.3)
actual_delay = round(base_delay + jitter, 1)
```

---

## Contraintes de sizing

- **Minimum order quantity** : `TradingConfig.min_order_quantity = 1.0` share
- **Limit price offset** : `TradingConfig.limit_price_offset_pct = 0.01` (1% sous market)
- **Max allocation par paire** : `TradingConfig.max_allocation_pct = 0.20` (20% du capital)
- **Max leverage** : `TradingUniverseConfig.max_leverage = 2.0` (equity: 2x)
- **Max sector weight** : `RiskConfig.max_sector_weight = 0.40` (40% dans un secteur)

---

## Variables d'environnement IBKR

| Variable | Défaut | Description |
|----------|--------|-------------|
| `IBKR_HOST` | `127.0.0.1` | Adresse TWS/Gateway |
| `IBKR_PORT` | `7497` (ib_insync) / `4002` (ibapi) | Port de connexion |
| `IBKR_CLIENT_ID` | `1` | Client ID unique par worker |
| `ENABLE_LIVE_TRADING` | non défini | Doit être `"true"` pour activer live |

### Garde live trading
```python
if not self.execution.use_sandbox:
    if os.getenv("ENABLE_LIVE_TRADING") != "true":
        self.execution.use_sandbox = True  # force sandbox
```

---

## Symbols IBKR invalides connus

Voir `ibkr_invalid_symbols.txt` à la racine pour la liste des symboles rejetés lors des scans.  
La `ExecutionEngine` les ignore silencieusement (log warning).

---

## Comportement docker-compose

```yaml
# docker-compose.yml
IBKR_HOST: host.docker.internal  # accès au TWS sur l'hôte depuis le container
IBKR_PORT: "4002"                 # IB Gateway paper (dans le container)
IBKR_CLIENT_ID: ${IBKR_CLIENT_ID:-1}
```

Pour le container, TWS/IB Gateway tourne sur l'hôte Windows et le container y accède via `host.docker.internal`.
