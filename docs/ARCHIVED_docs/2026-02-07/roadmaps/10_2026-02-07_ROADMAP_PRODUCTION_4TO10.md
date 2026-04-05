# ROADMAP: Score 4/10 ÔåÆ 10/10

**Objectif**: Transformer EDGECORE en syst├¿me production-grade pour trading r├®el avec capital.

**Strat├®gie**: 
- **Phase 1 (CRITICAL FIX)**: ├ëliminer tous les blocages ­ƒö┤ ÔåÆ Score 5ÔåÆ6
- **Phase 2 (ROBUSTNESS)**: S├®curit├® + fiabilit├® ÔåÆ Score 6ÔåÆ7
- **Phase 3 (QUALITY)**: Tests + monitoring ÔåÆ Score 7ÔåÆ8
- **Phase 4 (EXCELLENCE)**: Perf + documentation ÔåÆ Score 8ÔåÆ10

**Dur├®e estim├®e**: 80-100 heures = 2-3 semaines (full-time)

**Budget de risque**: Aucune modification ne peut r├®duire le score (toutes les PRs test├®es en isolation)

---

## PHASE 1: CRITICAL FIX (4ÔåÆ6/10) ÔÇö 24 heures

**Objectif**: ├ëliminer les 5 blocages ­ƒö┤ qui cr├®ent 75% des risques.

### 1.1 Input Validation Framework (4h)

**Probl├¿me**: Pas de validation d'entr├®e ÔåÆ crashes, garbage values

**Solution**: Cr├®er un validateur centralis├® r├®utilisable

```
FICHIER: common/validators.py
CONTENU:
  - validate_symbol(symbol: str) ÔåÆ raises ValueError
  - validate_position_size(size: float) ÔåÆ raises ValueError
  - validate_equity(equity: float) ÔåÆ raises ValueError
  - validate_volatility(vol: float) ÔåÆ raises ValueError
  - validate_config(config: dict) ÔåÆ raises ConfigError
  - SanityCheckContext (context manager)

TESTS: common/test_validators.py (20 tests)
  - Boundary values (0, -1, inf, NaN)
  - Type mismatches
  - Out-of-bounds values
```

**Effort**: 4h  
**Impact**: ­ƒö┤ÔåÆ­ƒƒá (kills silent failures)  
**Check**: `pytest common/test_validators.py -v --cov`

---

### 1.2 Inject Equity Config (1h)

**Probl├¿me**: `RiskEngine.initial_equity = 100000` hardcod├®

**Solution**: Passer equity en param├¿tre constructeur + settings

```
FICHIER: risk/engine.py
CHANGE:
  - __init__(self) ÔåÆ __init__(self, initial_equity: float, initial_cash: float)
  - Add assertions: 100 <= initial_equity <= 1_000_000_000
  - Add assertions: 0 < initial_cash <= initial_equity

FICHIER: main.py
CHANGE:
  - risk_engine = RiskEngine()
  - TO: risk_engine = RiskEngine(
      initial_equity=settings.backtest.initial_capital,
      initial_cash=settings.backtest.initial_capital
    )

FICHIER: tests/test_risk_engine.py
ADD:
  - test_risk_engine_invalid_equity()
  - test_risk_engine_cash_limit()
```

**Effort**: 1h  
**Impact**: ­ƒö┤ÔåÆ­ƒƒá (fixes state initialization)  
**Check**: `pytest tests/test_risk_engine.py::test_risk_engine_invalid_equity -v`

---

### 1.3 Broker Reconciliation at Startup (6h)

**Probl├¿me**: Local positions Ôëá broker positions ÔåÆ state divergence

**Solution**: Implement reconciliation loop at startup

```
FICHIER: risk/reconciler.py (NEW)
CONTAINS:
  class BrokerReconciler:
    def reconcile(broker) ÔåÆ None
    - Fetch broker positions
    - Fetch broker orders
    - Compare with local state
    - Raise ERROR if mismatch
    - Log full reconciliation report
    
    def diagnose_mismatch() ÔåÆ str
    - What's on broker but not in cache
    - What's in cache but not on broker
    - Quantified risk from mismatch

FICHIER: execution/base.py
ADD:
  - get_open_orders() ÔåÆ List[Order]
  - get_account_summary() ÔåÆ Dict (equity, cash, risk level)

FICHIER: execution/IBKR API_engine.py
IMPLEMENT:
  - get_open_orders() ÔåÆ fetch all active orders from IBKR
  - get_account_summary() ÔåÆ fetch account balance + positions

FICHIER: main.py
CHANGE:
  - At startup (before any trading):
    execution_engine = IBKR APIExecutionEngine()
    reconciler = BrokerReconciler()
    reconciler.reconcile(execution_engine)  # BLOCKS if mismatch
    logger.info("reconciliation_complete")

FICHIER: tests/test_reconciliation.py (NEW)
TESTS:
  - test_reconcile_matching_state() Ô£ô
  - test_reconcile_missing_broker_position() Ô£ô (raises)
  - test_reconcile_unknown_broker_position() Ô£ô (raises)
  - test_reconcile_partial_fills() Ô£ô
```

**Effort**: 6h  
**Impact**: ­ƒö┤ÔåÆ­ƒƒá (prevents state divergence)  
**Check**: `pytest tests/test_reconciliation.py -v`

---

### 1.4 Order Timeout + Force Close Logic (5h)

**Probl├¿me**: Ordres peuvent rester ouvertes ind├®finiment ("stuck orders")

**Solution**: Track order age, force cancel/liquidate si > timeout

```
FICHIER: execution/order_lifecycle.py (NEW)
CONTAINS:
  class OrderLifecycleManager:
    - track_order(order_id, created_at, symbol, qty)
    - get_stale_orders(timeout_sec=300) ÔåÆ List[stale_orders]
    - force_cancel_stale() ÔåÆ None (cancel + log)
    - force_liquidate_stale() ÔåÆ None (market order to close)
    
    - Properties: MAX_ORDER_AGE = 300 seconds (5 min)

FICHIER: execution/IBKR API_engine.py
ADD:
  - self.order_lifecycle = OrderLifecycleManager()
  - submit_order() ÔåÆ registers order in lifecycle manager
  - get_stale_orders() ÔåÆ delegates to lifecycle manager

FICHIER: main.py
CHANGE:
  - Every loop iteration, check for stale orders:
    stale = execution_engine.get_stale_orders()
    if stale:
      logger.warning("force_closing_stale_orders", count=len(stale))
      execution_engine.force_cancel_stale()

FICHIER: tests/test_order_lifecycle.py (NEW)
TESTS:
  - test_order_tracking()
  - test_stale_order_detection()
  - test_force_cancel_stale()
  - test_stale_order_cleanup_after_fill()
```

**Effort**: 5h  
**Impact**: ­ƒö┤ÔåÆ­ƒƒá (prevents stuck orders)  
**Check**: `pytest tests/test_order_lifecycle.py -v`

---

### 1.5 Add Monitoring + Slack Alerts (8h)

**Probl├¿me**: Pas d'alerts ÔåÆ humans unaware of failures

**Solution**: Critical alerts to Slack (equity drop, errors, order timeout)

```
FICHIER: monitoring/alerter.py (NEW)
CONTAINS:
  class AlertManager:
    def alert(level: str, message: str, context: dict = None)
    
    Levels:
      - INFO (just log)
      - WARNING (log + maybe Slack)
      - ERROR (log + Slack)
      - CRITICAL (log + Slack + SMS if configured)
    
    Properties:
      - slack_webhook_url  (from env)
      - alert_threshold (don't spam; max 1 alert per 30sec per type)
      - retry_failed_alerts

FICHIER: monitoring/events.py
ENHANCE:
  - Event types for critical events:
    * EQUITY_DROP_THRESHOLD
    * ORDER_TIMEOUT
    * DATA_STALE
    * BROKER_ERROR
    * RECONCILIATION_FAILED
    * STRATEGY_ERROR

FICHIER: monitoring/dashboard.py (NEW)
Create simple JSON-based status file:
  {
    "timestamp": "2026-02-07T12:30:45Z",
    "equity": 98500,
    "positions_open": 3,
    "orders_pending": 1,
    "last_signal": "2026-02-07T12:29:00Z",
    "error_count_24h": 2,
    "status": "HEALTHY|WARNING|CRITICAL"
  }

FICHIER: .env.example
ADD:
  SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
  ALERTING_ENABLED=true
  ALERT_THRESHOLD_EQUITY_DROP_PCT=5.0
  ALERT_THRESHOLD_ERROR_RATE=10

FICHIER: main.py
CHANGE:
  - Track metrics each loop:
    alerter = AlertManager()
    
    # In loop:
    equity = execution_engine.get_account_balance()
    if equity < last_equity * 0.95:  # 5% drop
      alerter.alert("WARNING", f"Equity drop {equity} vs {last_equity}")
    
    if len(errors) > 10:
      alerter.alert("CRITICAL", f"High error rate: {len(errors)}")

FICHIER: tests/test_alerter.py (NEW)
TESTS:
  - test_alert_throttling() (no spam)
  - test_slack_webhook_call()
  - test_alert_level_routing()
  - test_dashboard_json_generation()
```

**Effort**: 8h  
**Impact**: ­ƒƒáÔåÆ­ƒƒó (visibility + response)  
**Check**: 
```bash
pytest tests/test_alerter.py -v
curl -s http://localhost:8000/status.json  # Check dashboard
```

---

## PHASE 1 CHECKPOINT: Score 4ÔåÆ6/10 Ô£à

| Item | Before | After | Gained |
|------|--------|-------|--------|
| Input validation | 0% | 95% | ­ƒƒá Major |
| State management | 20% | 70% | ­ƒƒá Major |
| Error handling | 15% | 60% | ­ƒƒá Major |
| Observability | 5% | 50% | ­ƒƒá Major |

**Actions**: 1 + 2 + 3 + 4 + 5  
**Effort**: 4 + 1 + 6 + 5 + 8 = **24 hours**  
**Expected score**: 6/10

**Verification**:
```bash
pytest tests/test_validators.py tests/test_risk_engine.py tests/test_reconciliation.py tests/test_order_lifecycle.py tests/test_alerter.py -v --cov=common,risk,execution,monitoring
```

---

## PHASE 2: ROBUSTNESS (6ÔåÆ7/10) ÔÇö 20 heures

### 2.1 Input Validation in Configuration (2h)

**Probl├¿me**: YAML config peut avoir n'importe quelle valeur

**Solution**: Validate config schema on load

```
FICHIER: config/validators.py (NEW)
CONTAINS:
  from pydantic import BaseModel, Field, validator
  
  class RiskConfigValidated(BaseModel):
    max_risk_per_trade: float = Field(0.001, ge=0.0001, le=0.1)
    max_concurrent_positions: int = Field(10, ge=1, le=100)
    max_daily_loss_pct: float = Field(0.02, ge=0.001, le=0.5)
    # ... etc, with hard constraints

FICHIER: config/settings.py
CHANGE:
  - Load YAML ÔåÆ Validate with Pydantic
  - If validation fails ÔåÆ raise ConfigError with clear message
  - Log all config values on startup (for audit)

FICHIER: tests/test_config_validation.py
TESTS:
  - test_config_invalid_risk_above_max()
  - test_config_invalid_positions_below_min()
  - test_config_yaml_typo_caught()
```

**Effort**: 2h  
**Impact**: ­ƒƒáÔåÆ­ƒƒó (config errors caught immediately)

---

### 2.2 Refactor Paper/Live Code Duplication (4h)

**Probl├¿me**: `run_paper_trading()` et `run_live_trading()` = 90% duplicate code

**Solution**: Extract common loop, separate pre-flight checks

```
FICHIER: execution/execution_context.py (NEW)
CONTAINS:
  @dataclass
  class ExecutionContext:
    mode: "BacktestMode|PaperMode|LiveMode"
    symbols: List[str]
    execution_engine: BaseExecutionEngine
    risk_engine: RiskEngine
    strategy: PairTradingStrategy
    settings: Settings
    alerter: AlertManager

FICHIER: execution/modes.py (NEW)
CONTAINS:
  class ExecutionMode(ABC):
    @abstractmethod
    def validate_startup_conditions() ÔåÆ None
    @abstractmethod
    def on_startup(context: ExecutionContext) ÔåÆ None
    @abstractmethod
    def on_shutdown(context: ExecutionContext) ÔåÆ None
  
  class BacktestMode(ExecutionMode): ...
  class PaperMode(ExecutionMode): ...
  class LiveMode(ExecutionMode):
    - Requires user confirmation
    - Requires env=prod
    - Requires email confirmation
    - Logs to CRITICAL level

FICHIER: execution/trading_loop.py (NEW)
CONTAINS:
  def run_trading_loop(context: ExecutionContext):
    """Single implementation for all modes."""
    mode.on_startup(context)
    
    for iteration in range(context.settings.max_iterations):
      try:
        # Data load
        prices = load_market_data(...)
        
        # Signal generation
        signals = context.strategy.generate_signals(prices)
        
        # Risk gate
        for signal in signals:
          can_enter = context.risk_engine.can_enter_trade(...)
          if not can_enter:
            logger.warning("trade_rejected", ...)
            continue
          
          # Execution
          order = Order(...)
          context.execution_engine.submit_order(order)
        
        # Monitoring
        context.alerter.update_metrics(...)
        
        time.sleep(context.settings.loop_interval)
      
      except Exception as e:
        context.alerter.alert("ERROR", ...)
        
    mode.on_shutdown(context)

FICHIER: main.py
SIMPLIFY:
  - if args.mode == "backtest":
      mode = BacktestMode()
      context = ExecutionContext(mode="backtest", ...)
      run_trading_loop(context)
    
    elif args.mode == "paper":
      mode = PaperMode()
      context = ExecutionContext(mode="paper", ...)
      run_trading_loop(context)
    
    elif args.mode == "live":
      mode = LiveMode()
      mode.validate_startup_conditions()  # Hard checks
      context = ExecutionContext(mode="live", ...)
      run_trading_loop(context)

FICHIER: tests/test_execution_modes.py
TESTS:
  - test_backtest_mode_init()
  - test_paper_mode_requires_sandbox()
  - test_live_mode_requires_prod_env()
  - test_trading_loop_common_flow()
```

**Effort**: 4h  
**Impact**: ­ƒƒáÔåÆ­ƒƒó (eliminates bugs from copy-paste)

---

### 2.3 Add Graceful Error Recovery (3h)

**Probl├¿me**: Exception echoue toute la boucle silencieusement

**Solution**: Retry logic dengan exponential backoff, circuit breaker

```
FICHIER: common/retry.py (NEW)
CONTAINS:
  class RetryPolicy:
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
  
  @retry_with_backoff(policy=RetryPolicy())
  def risky_operation():
    # Auto-retries with exponential backoff

FICHIER: common/circuit_breaker.py (NEW)
CONTAINS:
  class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout_sec: int = 60)
    def call(func, *args) ÔåÆ result or raises CircuitBreakerOpen
    # Opens after 5 failures, stays open 60 sec, then half-open
    
    Properties (for monitoring):
      - state: CLOSED|OPEN|HALF_OPEN
      - failure_count: int
      - last_failure_time: datetime

FICHIER: execution/IBKR API_engine.py
ENHANCE:
  - Wrap risky IBKR API calls with @retry_with_backoff
  - API calls have circuit breaker
  - Log retry attempts and circuit breaker state

FICHIER: tests/test_retry_logic.py
TESTS:
  - test_retry_success_on_third_attempt()
  - test_exponential_backoff_timing()
  - test_circuit_breaker_opens_after_threshold()
  - test_circuit_breaker_half_open_recovery()
```

**Effort**: 3h  
**Impact**: ­ƒƒáÔåÆ­ƒƒó (resilient to transient failures)

---

### 2.4 Secure Secrets Management (4h)

**Probl├¿me**: API keys in .env, exposed in logs/memory

**Solution**: Use proper secrets management

```
FICHIER: common/secrets.py (NEW)
CONTAINS:
  class SecretsManager:
    def load_secret(key_name: str) ÔåÆ str
    # Priority:
    # 1. Environment variables (for deployed)
    # 2. AWS Secrets Manager (if AWS_REGION set)
    # 3. HashiCorp Vault (if VAULT_ADDR set)
    # 4. Local encrypted file (for dev, with warning)
    
    def mask_secret(secret: str, show_last_n: int = 4) ÔåÆ str
    # Returns: "sk_live_****...j9a5"

FICHIER: common/logging_filters.py (NEW)
CONTAINS:
  class SensitiveDataFilter(logging.Filter):
    """Remove secrets from logs."""
    sensitive_keys = ["api_key", "secret", "password", "email", "token"]
    
    def filter(record):
      for key in sensitive_keys:
        if key in record.__dict__:
          record.__dict__[key] = "***REDACTED***"
      return True

FICHIER: execution/IBKR API_engine.py
CHANGE:
  - api_key = SecretsManager.load_secret("broker_API_KEY")
  - Log masked key: logger.info(..., api_key=mask_secret(api_key))

FICHIER: monitoring/logger.py
CHANGE:
  - Add SensitiveDataFilter to logging config
  - All logs are filtered automatically

FICHIER: config/.env.example
CHANGE:
  - Add AWS_REGION=us-east-1 (optional, for Secrets Manager)
  - Add VAULT_ADDR=https://vault.example.com (optional)
  - WARNING comment: "Never paste real secrets in .env"

FICHIER: tests/test_secrets.py
TESTS:
  - test_secrets_masked_in_logs()
  - test_secrets_not_exposed_in_exceptions()
  - test_secrets_manager_priority()
```

**Effort**: 4h  
**Impact**: ­ƒö┤ÔåÆ­ƒƒá (security critical)

---

### 2.5 Add Data Integrity Checks (3h)

**Probl├¿me**: OHLCV data peut avoir NaN, gaps, volumes=0

**Solution**: Validate data quality before use

```
FICHIER: data/validators.py (NEW)
CONTAINS:
  class OHLCVValidator:
    def validate(df: pd.DataFrame) ÔåÆ ValidationResult
    Checks:
      - No NaN values
      - High >= Low
      - Close between High/Low
      - Volume >= 0
      - No duplicate timestamps
      - No time gaps (missing candles)
      - Min 100 rows (arbitrary, configurable)
    
    Returns: ValidationResult(is_valid, errors[], warnings[])
    
    If invalid: raises DataIntegrityError with clear message

FICHIER: data/loader.py
CHANGE:
  - After load_IBKR API_data(), validate result
  - If invalid, log ERROR and return None
  - Caller must handle None (skip symbol, alert)

FICHIER: tests/test_data_validators.py
TESTS:
  - test_validate_clean_data()
  - test_reject_nan_values()
  - test_reject_invalid_candles()
  - test_detect_time_gaps()
  - test_detect_stale_data()
```

**Effort**: 3h  
**Impact**: ­ƒƒáÔåÆ­ƒƒó (prevents bad signals from garbage data)

---

## PHASE 2 CHECKPOINT: Score 6ÔåÆ7/10 Ô£à

| Item | Before | After | Gained |
|------|--------|-------|--------|
| Config safety | 20% | 95% | ­ƒƒó Good |
| Code DRY | 40% | 90% | ­ƒƒó Good |
| Error resilience | 30% | 85% | ­ƒƒó Good |
| Secrets safety | 10% | 90% | ­ƒƒó Good |
| Data quality | 20% | 85% | ­ƒƒó Good |

**Actions**: 2.1 + 2.2 + 2.3 + 2.4 + 2.5  
**Effort**: 2 + 4 + 3 + 4 + 3 = **16 hours**  
**Expected score**: 7/10

---

## PHASE 3: QUALITY (7ÔåÆ8/10) ÔÇö 20 heures

### 3.1 Comprehensive Integration Tests (10h)

**Probl├¿me**: ~25% code coverage, no end-to-end tests

**Solution**: Test entire trading flow

```
FICHIER: tests/test_integration_e2e.py (NEW)
CONTAINS:
  - test_complete_backtest_flow()
    Load data ÔåÆ Generate signals ÔåÆ Risk gate ÔåÆ Calc returns
  
  - test_complete_paper_trading_mock()
    Mock IBKR API + Data ÔåÆ Full trading loop ÔåÆ Verify positions
  
  - test_strategy_with_real_cointegration()
    Use actual cointegration test ÔåÆ Generate real signals
  
  - test_risk_engine_stops_trades_on_drawdown()
    Simulate daily loss accumulation ÔåÆ Risk engine blocks new trades
  
  - test_order_lifecycle_complete()
    Submit ÔåÆ Fill (partial) ÔåÆ Timeout ÔåÆ Force cancel
  
  - test_broker_reconciliation_catches_mismatch()
    Local state Ôëá broker ÔåÆ raises error Ô£ô
  
  - test_monitoring_alerts_on_critical()
    Equity drop/error ÔåÆ alert generated Ô£ô
  
  - test_data_validation_rejects_bad_candles()
    NaN data ÔåÆ skipped Ô£ô

FICHIER: tests/fixtures/ (NEW)
CONTAINS:
  - sample_ohlcv_data.csv (500 rows clean)
  - sample_ohlcv_data_with_nan.csv (has gaps)
  - cointegrated_pair_data.csv (X, Y actually cointegrated)
  - non_cointegrated_pair_data.csv (random data)

FICHIER: tests/conftest.py (NEW)
CONTAINS:
  - Fixtures for MockExecutionEngine, MockDataLoader, etc.
  - Settings override for tests
  - Database/cache cleanup between tests

COVERAGE TARGET: 70%+ of code
```

**Effort**: 10h  
**Impact**: ­ƒƒáÔåÆ­ƒƒó (confidence in production readiness)

---

### 3.2 Add Type Hints Throughout (6h)

**Probl├¿me**: No type hints ÔåÆ refactor risky, IDE can't help

**Solution**: Add type hints to all public APIs

```
FICHIER: common/types.py (NEW)
CONTAINS:
  from typing import TypedDict, Literal
  
  class Signal(TypedDict):
    symbol_pair: str
    side: Literal["long", "short"]
    z_score: float
    entry_price: float
  
  class Position(TypedDict):
    symbol_pair: str
    entry_price: float
    quantity: float
    side: Literal["long", "short"]
    pnl: float

FICHIER: **/*.py
CHANGE:
  - Add type hints to all function signatures
  - Use Optional[], List[], Dict[] properly
  - Run mypy/pyright to validate

Example:
  # BEFORE:
  def can_enter_trade(self, symbol_pair, position_size, current_equity, volatility):
  
  # AFTER:
  def can_enter_trade(
    self,
    symbol_pair: str,
    position_size: float,
    current_equity: float,
    volatility: float
  ) -> tuple[bool, Optional[str]]:

FICHIER: pyproject.toml
ADD:
  [tool.mypy]
  python_version = "3.11"
  strict = true
  warn_unused_configs = true
  
  [tool.pyright]
  pyright = "latest"

FICHIER: tests/test_type_hints.py (NEW)
CONTAINS:
  - Run mypy in test mode
  - Ensure all type hints valid
```

**Effort**: 6h  
**Impact**: ­ƒƒíÔåÆ­ƒƒó (safer refactors, better IDE)

---

### 3.3 Position-Level Stop Losses (2h)

**Probl├¿me**: Positions peuvent perdre illimit├®; seulement limite portfolio

**Solution**: Add stop loss at entry

```
FICHIER: risk/position_risk.py (NEW)
CONTAINS:
  @dataclass
  class PositionStop:
    position_id: str
    stop_loss_pct: float = 0.05  # 5% max loss per position
    take_profit_pct: float = 0.10  # 10% profit target
    
    def should_exit(current_price: float, entry_price: float) -> bool:
      pnl_pct = (current_price - entry_price) / entry_price
      if pnl_pct < -self.stop_loss_pct:
        return True
      if pnl_pct > self.take_profit_pct:
        return True
      return False
    
    def exit_reason(pnl_pct: float) -> str:
      if pnl_pct < -self.stop_loss_pct:
        return "STOP_LOSS"
      return "TAKE_PROFIT"

FICHIER: risk/engine.py
ADD:
  - position_stops: Dict[symbol, PositionStop]
  - check_position_exits() ÔåÆ List[positions_to_close]

FICHIER: main.py
CHANGE:
  - Each loop, check position stops
  - Auto-close positions that hit stop loss
  - Log: "position_closed_by_stop_loss"

FICHIER: config/settings.py
ADD:
  position_stop_loss_pct: float = 0.05
  position_take_profit_pct: float = 0.10
```

**Effort**: 2h  
**Impact**: ­ƒƒáÔåÆ­ƒƒó (limits downside per trade)

---

### 3.4 Backtest Realism Improvement (2h)

**Probl├¿me**: Backtest simulator trop simplifi├®, pas r├®aliste

**Solution**: Add slippage, commissions, partial fills

```
FICHIER: backtests/simulator.py (NEW)
CONTAINS:
  class RealisticSimulator:
    def __init__(self, slippage_bps=5, commission_bps=2):
      self.slippage = slippage_bps / 10000
      self.commission = commission_bps / 10000
    
    def simulate_order_fill(order: Order, market_price: float) -> tuple[float, float]:
      # Apply slippage
      filled_price = market_price * (1 + self.slippage)
      
      # Apply commission
      commission_charge = filled_price * order.quantity * self.commission
      
      return filled_price, commission_charge

FICHIER: backtests/runner.py
CHANGE:
  - Use RealisticSimulator instead of naive calculation
  - Match config slippage_bps and commission_bps

FICHIER: tests/test_backtest_realism.py
TESTS:
  - test_backtest_accounts_for_slippage()
  - test_backtest_accounts_for_commissions()
  - test_backtest_vs_paper_drift() (backtest vs paper results within 5%)
```

**Effort**: 2h  
**Impact**: ­ƒƒíÔåÆ­ƒƒó (backtest more predictive)

---

## PHASE 3 CHECKPOINT: Score 7ÔåÆ8/10 Ô£à

| Item | Before | After | Gained |
|------|--------|-------|--------|
| Test coverage | 25% | 70% | ­ƒƒó Very Good |
| Type safety | 0% | 95% | ­ƒƒó Very Good |
| Position safety | 60% | 100% | ­ƒƒó Perfect |
| Backtest quality | 40% | 85% | ­ƒƒó Good |

**Actions**: 3.1 + 3.2 + 3.3 + 3.4  
**Effort**: 10 + 6 + 2 + 2 = **20 hours**  
**Expected score**: 8/10

---

## PHASE 4: EXCELLENCE (8ÔåÆ10/10) ÔÇö 15 heures

### 4.1 Performance Profiling + Optimization (4h)

**Probl├¿me**: Pas de benchmarking; scalabilit├® inconnue

**Solution**: Profile + optimize hot paths

```
FICHIER: performance/profiler.py (NEW)
CONTAINS:
  @profile_function(threshold_ms=100)
  def my_function():
    # Auto-logs if execution > 100ms
  
  @memory_profile()
  def data_load():
    # Auto-logs memory usage
  
  class PerformanceMonitor:
    - tracks function execution times
    - tracks memory usage
    - generates report

FICHIER: tests/test_performance.py
CONTAINS:
  @pytest.mark.performance
  def test_cointegration_50_pairs_performance():
    # Should complete in < 2 seconds for 50 pairs
    assert time_to_run < 2.0
  
  @pytest.mark.performance
  def test_data_load_100_symbols():
    # Should complete in < 10 seconds
    assert time_to_run < 10.0
  
  @pytest.mark.memory
  def test_memory_usage_1000_symbols():
    # Should use < 500MB
    assert memory_used < 500_000_000

BENCHMARKS to optimize:
  - Cointegration test (multiprocessing vs async)
  - OHLCV loading (batch vs serial IBKR API calls)
  - Z-score calculation (vectorized vs loop)

RUN:
  pytest tests/test_performance.py -v -m performance
  python -m cProfile -s cumulative main.py --mode backtest --symbols AAPL
```

**Effort**: 4h  
**Impact**: ­ƒƒíÔåÆ­ƒƒó (identify bottlenecks)

---

### 4.2 Documentation + Architecture Handbook (5h)

**Probl├¿me**: Pas de doc syst├¿me; onboarding difficile

**Solution**: Write comprehensive guides

```
FICHIER: docs/ARCHITECTURE.md
CONTAINS:
  1. System Design (boxes + arrows)
  2. Data Flow (strategy ÔåÆ risk ÔåÆ execution)
  3. State Machine (order lifecycle, position lifecycle)
  4. Risk Model (detailed)
  5. Configuration Guide
  6. Deployment Checklist

FICHIER: docs/DEVELOPER_GUIDE.md
CONTAINS:
  1. Quick Start (5 min setup)
  2. Adding a new strategy (step-by-step)
  3. Adding a new broker (+ template)
  4. Testing patterns
  5. Performance tips
  6. Debugging guide

FICHIER: docs/OPERATIONS.md
CONTAINS:
  1. Production Checklist (pre-flight)
  2. Monitoring dashboard setup
  3. Alert configuration
  4. Incident response (what to do if...)
  5. Rollback procedures
  6. Log analysis tips

FICHIER: docs/RISK_MODEL.md
CONTAINS:
  1. Risk engine design
  2. Position sizing logic
  3. Drawdown limits
  4. Concentration limits
  5. Stress test scenarios
  6. Parameter tuning guide

FICHIER: docs/API_REFERENCE.md
  - Auto-generated from type hints
  - Examples for each component
```

**Effort**: 5h  
**Impact**: ­ƒƒíÔåÆ­ƒƒó (onboarding, maintenance)

---

### 4.3 CI/CD Pipeline + Automated Testing (4h)

**Probl├¿me**: No automated tests on commits; manual approval risky

**Solution**: GitHub Actions pipeline

```
FICHIER: .github/workflows/test.yml (NEW)
CONTAINS:
  on: [push, pull_request]
  
  jobs:
    test:
      runs-on: ubuntu-latest
      steps:
        - Checkout
        - Setup Python 3.11
        - Install dependencies
        - Run linting (flake8, black)
        - Run type checking (mypy)
        - Run tests (pytest --cov)
        - Upload coverage to codecov
        - Fail if coverage < 70%
    
    performance:
      runs-on: ubuntu-latest
      steps:
        - Checkout
        - Run performance tests
        - Fail if regression > 10%
    
    security:
      runs-on: ubuntu-latest
      steps:
        - Run bandit (security scanner)
        - Check for hardcoded secrets
        - Fail if vulnerabilities found

R├êGLES:
  - No PR merge without: Ô£ô Tests pass, Ô£ô Coverage >= 70%, Ô£ô Type hints valid
  - Release requires: Ô£ô All above + Ô£ô Manual approval + Ô£ô Release notes

FICHIER: pyproject.toml
ADD:
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  addopts = "--cov=. --cov-report=html --cov-report=term-missing"
  
  [tool.coverage.run]
  omit = ["tests/*", "venv/*"]
```

**Effort**: 4h  
**Impact**: ­ƒƒáÔåÆ­ƒƒó (catch bugs early)

---

### 4.4 Operational Readiness Review (2h)

**Probl├¿me**: No formal checklist; production readiness unclear

**Solution**: Structured pre-flight check

```
FICHIER: docs/PRODUCTION_READINESS_CHECKLIST.md
CONTAINS:
  Ô£ô Code
    - Ô£ô All tests passing
    - Ô£ô Coverage >= 70%
    - Ô£ô Type hints 100%
    - Ô£ô No security vulnerabilities
    - Ô£ô No hardcoded secrets
  
  Ô£ô Configuration
    - Ô£ô All required env vars set
    - Ô£ô API keys rotated < 30 days
    - Ô£ô Config validated at startup
    - Ô£ô Secrets encrypted
  
  Ô£ô Infrastructure
    - Ô£ô Broker API responsive
    - Ô£ô Data sources responsive
    - Ô£ô Monitoring active
    - Ô£ô Alerts configured
  
  Ô£ô Risk
    - Ô£ô Capital at risk quantified
    - Ô£ô Max loss acceptable
    - Ô£ô Broker position limits OK
    - Ô£ô Kill-switch tested (manual)
  
  Ô£ô Operations
    - Ô£ô Runbooks written
    - Ô£ô On-call schedule set
    - Ô£ô Incident log initialized
    - Ô£ô Backup procedures tested
  
  Ô£ô Legal
    - Ô£ô Terms of service reviewed
    - Ô£ô Tax implications known
    - Ô£ô Compliance rules met

FICHIER: scripts/pre_flight_check.py (NEW)
CONTAINS:
  def run_pre_flight_checks():
    - Validate config
    - Test broker connection
    - Test data source
    - Verify capital limits
    - Verify kill-switch
    - Generate report
    
    Returns: READY or BLOCKED with reason

USAGE:
  python scripts/pre_flight_check.py --mode live
  # Outputs: Ô£ô PRODUCTION READY or Ô£ù BLOCKED because...
```

**Effort**: 2h  
**Impact**: ­ƒƒóÔåÆ­ƒƒó (confidence check)

---

## PHASE 4 CHECKPOINT: Score 8ÔåÆ10/10 Ô£à

| Item | Before | After | Gained |
|------|--------|-------|--------|
| Performance understood | 20% | 95% | ­ƒƒó Excellent |
| Documentation | 20% | 95% | ­ƒƒó Excellent |
| CI/CD | 0% | 100% | ­ƒƒó Perfect |
| Operational readiness | 30% | 100% | ­ƒƒó Perfect |

**Actions**: 4.1 + 4.2 + 4.3 + 4.4  
**Effort**: 4 + 5 + 4 + 2 = **15 hours**  
**Expected score**: 10/10

---

## FINAL RECAP

| Phase | Score Gain | Hours | Cumulative |
|-------|-----------|-------|-----------|
| 1: Critical Fix | 4ÔåÆ6 | 24 | 24h |
| 2: Robustness | 6ÔåÆ7 | 16 | 40h |
| 3: Quality | 7ÔåÆ8 | 20 | 60h |
| 4: Excellence | 8ÔåÆ10 | 15 | **75h** |

**Total effort**: **~75 hours** = **2-3 weeks full-time**

**Risk level**:
- Phase 1: ­ƒö┤ Blocks deployment (fix now)
- Phase 2: ­ƒƒá Major improvements (fix before launch)
- Phase 3: ­ƒƒí Quality (fix in first month)
- Phase 4: ­ƒƒó Polish (fix in first quarter)

---

## SUCCESS CRITERIA: SCORE 10/10

Ô£à All critical validation in place (input, config, data)  
Ô£à Broker state synced at startup + periodically  
Ô£à Orders timeout-protected + force-close logic  
Ô£à Monitoring + alerts active (Slack, dashboard)  
Ô£à No code duplication (DRY enforced)  
Ô£à Configuration safe + validated  
Ô£à Error recovery with exponential backoff  
Ô£à Secrets properly managed + masked  
Ô£à Data quality validated before use  
Ô£à Position-level stop losses enforced  
Ô£à 70%+ test coverage + integration tests  
Ô£à 100% type hints (mypy strict)  
Ô£à Realistic backtest simulator  
Ô£à Performance profiled + optimized  
Ô£à Architecture documented (5000+ words)  
Ô£à CI/CD pipeline + mandatory checks  
Ô£à Operational readiness checklist  

**Verdict**: Ô£à **PRODUCTION READY** for real trading with capital

---

## IMPLEMENTATION ORDER (Non-negotiable)

**Week 1 (Phase 1: Critical):**
```
Day 1-2: 1.1 Input Validation + 1.2 Equity Config
Day 3: 1.3 Reconciliation
Day 4: 1.4 Order Timeout + 1.5 Monitoring
Day 5: Testing all Phase 1, score check 6/10
```

**Week 2 (Phase 2: Robustness):**
```
Day 6-7: 2.1 Config Validation + 2.2 Refactor
Day 8: 2.3 Error Recovery + 2.4 Secrets
Day 9: 2.5 Data Validators
Day 10: Testing all Phase 2, score check 7/10
```

**Week 3 (Phase 3: Quality):**
```
Day 11-13: 3.1 Integration Tests
Day 14-15: 3.2 Type Hints
Day 16: 3.3 Position Stops + 3.4 Backtest Realism
End: Testing all Phase 3, score check 8/10
```

**Week 4 (Phase 4: Excellence):**
```
Day 17-18: 4.1 Performance + 4.2 Docs
Day 19-20: 4.3 CI/CD + 4.4 Pre-flight Checklist
End: Testing all Phase 4, score check 10/10
```

---

**Ready to start?** ­ƒÜÇ Pick Phase 1, Action 1.1 and let's go!

