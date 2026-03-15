# PLAN DE REM├ëDIATION ÔÇö EDGECORE 5/10 ÔåÆ 10/10
## Roadmap compl├¿te vers Production Ready (100% Capital-Safe)

**Date:** 8 f├®vrier 2026  
**Horizon total:** 12-16 semaines (3-4 mois)  
**├ëquipe requise:** 1-2 ing├®nieurs senior Python  
**Objectif final:** Score 10/10 + Capital Protection Guarantee Ô£à

---

## TABLE DES MATI├êRES

1. [Vue d'ensemble strat├®gique](#1-vue-densemble-strat├®gique)
2. [Phase 0: Stabilisation imm├®diate (48h)](#2-phase-0-stabilisation-imm├®diate-48h)
3. [Phase 1: Capital Protection Critical (2 semaines)](#3-phase-1-capital-protection-critical-2-semaines)
4. [Phase 2: Robustesse & R├®silience (3 semaines)](#4-phase-2-robustesse--r├®silience-3-semaines)
5. [Phase 3: Observabilit├® & Monitoring (2 semaines)](#5-phase-3-observabilit├®--monitoring-2-semaines)
6. [Phase 4: Testing & Validation Compl├¿te (3 semaines)](#6-phase-4-testing--validation-compl├¿te-3-semaines)
7. [Phase 5: Excellence & Optimisation (2 semaines)](#7-phase-5-excellence--optimisation-2-semaines)
8. [H├®bergement & d├®ploiement (1 semaine)](#8-h├®bergement--d├®ploiement-1-semaine)
9. [Checklist de Production](#9-checklist-de-production)

---

## 1. Vue d'ensemble strat├®gique

### 1.1 Principes directeurs

**Pilier 1: Capital Preservation (Priorit├® absolue)**
- Position persistence (crash = z├®ro perte)
- Global kill-switch (emergency control)
- Order timeout enforcement (capital locked prevention)
- Drawdown circuit breaker (hard stop on losses)

**Pilier 2: Observabilit├® & Operabilit├®**
- Real-time alerting (Slack/Email/Dashboard)
- Centralized audit trail (tous les trades trac├®s)
- Performance monitoring (latency, throughput)
- Incident diagnostics (tracer root cause rapidement)

**Pilier 3: Robustesse & R├®silience**
- Graceful error recovery (exponential backoff, circuit breaker)
- Idempotent operations (safe to retry)
- State reconciliation (broker Ôåö local)
- No silent failures (loud errors)

**Pilier 4: Test Complet & Validation**
- Unit tests (70%+ coverage)
- Integration tests (components interacting)
- E2E tests (full trading flow)
- Chaos engineering (failure scenarios)

### 1.2 Roadmap par score

```
PHASE 0 (48h)   ÔåÆ Score 5 ÔåÆ 5.5  [Critical hotfixes]
PHASE 1 (14j)   ÔåÆ Score 5.5 ÔåÆ 7  [Capital protection]
PHASE 2 (21j)   ÔåÆ Score 7 ÔåÆ 7.5  [Error handling]
PHASE 3 (14j)   ÔåÆ Score 7.5 ÔåÆ 8.5  [Monitoring/Alerts]
PHASE 4 (21j)   ÔåÆ Score 8.5 ÔåÆ 9.5  [Testing]
PHASE 5 (14j)   ÔåÆ Score 9.5 ÔåÆ 10  [Polish/Excellence]
```

**Total: 12-16 weeks (1 engineer FTE)**

### 1.3 D├®pendances critiques

```
Phase 0 (Hotfixes)
  Ôåô
Phase 1 (Position Persist) ÔåÉ BLOCKS Phase 2+3+4
  Ôåô
Phase 2 (Error Handling) ÔåÉ BLOCKS Phase 4
  Ôåô
Phase 3 (Monitoring) // Phase 4 (Testing) ÔåÉ Can run in parallel
  Ôåô
Phase 5 (Polish)
  Ôåô
Production Readiness Checklist
```

---

## 2. PHASE 0: Stabilisation imm├®diate (48h)

**Objectif:** Patch les bugs critiques qui feraient crash un test simple  
**Score cible:** 5.5/10  
**Effort:** 2-3 jours (1 ing├®nieur)

### 2.1 Hotfix 1: D├®sactiver le mode live par default

**Probl├¿me:** `prod.yaml` a `use_sandbox: false` ÔåÆ IBKR r├®el activ├® par accident  
**Solution:** Force sandbox=true dans tous les configs, requiert un env var pour d├®sactiver

**T├óches:**
```
1. Fichier: config/settings.py
   - Ajouter safety check:
     if settings.execution.use_sandbox == False and os.getenv("ENABLE_LIVE_TRADING") != "true":
         raise ValueError("Live trading disabled. Set ENABLE_LIVE_TRADING=true to enable.")
   
2. Fichier: config/prod.yaml
   - CHANGE: use_sandbox: false ÔåÆ use_sandbox: true
   - COMMENT: "# Override with ENABLE_LIVE_TRADING env var only"
   
3. Fichier: main.py
   - CHANGE: if settings.env != "prod": ÔåÆ if os.getenv("ENABLE_LIVE_TRADING") != "true":
   - Log at CRITICAL: "LIVE TRADING MODE ENABLED - TRADING WITH REAL MONEY"
```

**Acceptance criteria:**
- Ô£à config/prod.yaml defaults to sandbox=true
- Ô£à Starting without ENABLE_LIVE_TRADING=true logs error or forces paper mode
- Ô£à Test: python main.py --mode live ÔåÆ raises ValueError

**Effort:** 2h

### 2.2 Hotfix 2: Supprimer les TODO laiss├®s en code prod

**Probl├¿me:** `execution/IBKR API_engine.py` line 59 has `# TODO: Remove sandbox restriction in production`

**T├óches:**
```
1. File: execution/IBKR API_engine.py:50-65
   - Remove TODO comment
   - Replace with explicit check:
     if not self.config.use_sandbox:
         logger.critical("LIVE_TRADING_ENABLED", broker=self.config.broker)
```

**Acceptance criteria:**
- Ô£à grep -r "TODO" codebase ÔåÆ only research/param_optimization, walk_forward (non-critical)
- Ô£à execute `python -m pylint --disable=all --enable=fixme main.py` ÔåÆ no fixme warnings

**Effort:** 1h

### 2.3 Hotfix 3: Exponential backoff dans main loop

**Probl├¿me:** `time.sleep(5)` constant ÔåÆ CPU tight loop si API down

**T├óches:**
```
1. File: main.py (run_paper_trading):100-180
   BEFORE:
     except Exception as e:
         logger.error("paper_trading_loop_error", ...)
         time.sleep(5)  # ÔåÉ Constant
   
   AFTER:
     except Exception as e:
         error_count += 1
         backoff_sec = min(60, 2 ** error_count)  # Exponential, max 60s
         logger.error("paper_trading_loop_error", 
                     error_count=error_count, 
                     backoff_sec=backoff_sec)
         time.sleep(backoff_sec)
         if error_count > 10:
             logger.critical("MAX_RETRIES_EXCEEDED")
             break
```

**Acceptance criteria:**
- Ô£à First error: 2s, second: 4s, third: 8s, ... max 60s
- Ô£à After 10 consecutive errors, loop breaks (doesn't retry forever)
- Ô£à Test: force error 3x, measure delays, verify 2ÔåÆ4ÔåÆ8s pattern

**Effort:** 1h

### 2.4 Hotfix 4: Hardcoded sleep(10) ÔåÆ configurable

**Probl├¿me:** `time.sleep(10)` dans paper trading loop (commentaire: "would be 3600 in prod") ÔåÆ Dev code

**T├óches:**
```
1. File: config/settings.py - Add to ExecutionConfig:
   paper_trading_loop_interval_seconds: int = 3600  # 1 hour
   
2. File: main.py - Replace:
   BEFORE: time.sleep(10)
   AFTER: time.sleep(settings.execution.paper_trading_loop_interval_seconds)
```

**Acceptance criteria:**
- Ô£à config/dev.yaml: paper_trading_loop_interval_seconds: 10
- Ô£à config/prod.yaml: paper_trading_loop_interval_seconds: 3600
- Ô£à Configurable via env var

**Effort:** 1h

### 2.5 Hotfix 5: Fix division by zero risk

**Probl├¿me:** `risk/engine.py` line ~120: `self.daily_loss / current_equity` crashes if equity=0

**T├óches:**
```
1. File: risk/engine.py:100-140
   BEFORE:
     if self.daily_loss / current_equity > self.config.max_daily_loss_pct:
   
   AFTER:
     if current_equity <= 0:
         raise EquityError(f"Equity must be positive, got {current_equity}")
     if self.daily_loss / current_equity > self.config.max_daily_loss_pct:
```

**Acceptance criteria:**
- Ô£à Any function that divides by equity checks equity > 0 first
- Ô£à Test: can_enter_trade(current_equity=0) ÔåÆ raises EquityError

**Effort:** 1h

### 2.6 Validation Phase 0

```bash
# Run after Phase 0:
1. pytest tests/test_risk_engine.py::test_init_with_zero_equity_fails -v
2. python main.py --mode paper --symbols AAPL 2>&1 | head -20
   # Should log: "paper_trading_mode_starting"
3. grep -r "# TODO" . --include="*.py" | grep -v "research\|param_optim\|walk_forward"
   # Should return empty
4. python -c "from config.settings import get_settings; s=get_settings(); print(s.execution.paper_trading_loop_interval_seconds)"
   # Should print 10 (dev config)
```

**Acceptance criteria:**
- Ô£à All 4 hotfixes tested
- Ô£à System starts without errors
- Ô£à No critical TODOs left

---

## 3. PHASE 1: Capital Protection Critical (2 semaines)

**Objectif:** Impl├®menter persistence, kill-switch, order timeouts  
**Score cible:** 7/10  
**Effort:** 80-100 heures (2 semaines enti├¿res)  
**Blockers:** None (PHASE 0 done)

### 3.1 Feature: Position Persistence & Reconciliation (40h)

**Probl├¿me:** Crash ÔåÆ perte de toutes les positions locales ÔåÆ position leaks

**Solution:** Append-only audit trail + startup reconciliation

#### 3.1.1 Audit Trail Database

**Fichier:** `execution/audit_trail.py` (NEW, 200 LOC)

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
from typing import List, Optional

@dataclass
class AuditEvent:
    """Immutable trade event record."""
    event_id: str  # UUID
    timestamp: datetime
    event_type: str  # POSITION_OPENED, POSITION_CLOSED, ORDER_PLACED, ORDER_FILLED, etc.
    symbol_pair: str
    quantity: float
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    order_id: Optional[str] = None
    reason: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type,
            'symbol_pair': self.symbol_pair,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'pnl': self.pnl,
            'order_id': self.order_id,
            'reason': self.reason
        }

class AuditTrail:
    """Append-only audit trail for all trades."""
    
    def __init__(self, audit_dir: str = "audit"):
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.events: List[AuditEvent] = []
    
    def log_event(self, event: AuditEvent) -> None:
        """Log an audit event (thread-safe)."""
        self.events.append(event)
        
        # Write to daily file (append-only)
        audit_file = self.audit_dir / f"audit_{datetime.now().date()}.jsonl"
        with open(audit_file, 'a') as f:
            f.write(json.dumps(event.to_dict()) + '\n')
        
        logger.info("audit_event_logged", event_type=event.event_type, 
                   symbol_pair=event.symbol_pair)
    
    def load_recent_events(self, days: int = 7) -> List[AuditEvent]:
        """Load audit events from last N days."""
        events = []
        for i in range(days):
            date = datetime.now().date() - timedelta(days=i)
            audit_file = self.audit_dir / f"audit_{date}.jsonl"
            if audit_file.exists():
                with open(audit_file, 'r') as f:
                    for line in f:
                        data = json.loads(line)
                        # Reconstruct AuditEvent from dict
                        events.append(AuditEvent(
                            event_id=data['event_id'],
                            timestamp=datetime.fromisoformat(data['timestamp']),
                            # ... etc
                        ))
        return sorted(events, key=lambda e: e.timestamp)
    
    def reconstruct_positions(self, days: int = 7) -> Dict[str, Position]:
        """Reconstruct open positions from audit trail."""
        events = self.load_recent_events(days)
        positions = {}
        
        for event in events:
            if event.event_type == "POSITION_OPENED":
                positions[event.symbol_pair] = Position(
                    symbol_pair=event.symbol_pair,
                    entry_time=event.timestamp,
                    entry_price=event.entry_price,
                    quantity=event.quantity,
                    side="long" if event.quantity > 0 else "short"
                )
            elif event.event_type == "POSITION_CLOSED":
                if event.symbol_pair in positions:
                    del positions[event.symbol_pair]
        
        return positions
```

**T├óches:**
```
1. Create execution/audit_trail.py (200 LOC, 6h)
   - AuditEvent dataclass
   - AuditTrail manager
   - log_event() ÔåÆ append to daily JSONL file
   - load_recent_events(days) ÔåÆ read from disk
   - reconstruct_positions() ÔåÆ rebuild state

2. Modify risk/engine.py (10h)
   - Add audit_trail: AuditTrail = field(default_factory=AuditTrail)
   - In register_entry(): audit_trail.log_event(AuditEvent(...))
   - In register_exit(): audit_trail.log_event(AuditEvent(...))

3. Modify main.py (8h)
   - On startup: risk_engine.load_positions_from_audit(audit_dir='audit')
   - Query IBKR open orders
   - Compare local state vs IBKR state
   - Alert if mismatch

4. Create tests/test_audit_trail.py (20h)
   - test_audit_trail_logging
   - test_reconstruct_positions_after_crash
   - test_mismatch_detection
   - test_concurrent_writes
```

**Acceptance criteria:**
- Ô£à Every trade (entry/exit) logged to disk immediately
- Ô£à Restart system ÔåÆ positions reconstructed from audit trail
- Ô£à Mismatch between local state and IBKR detected + alerted
- Ô£à No data loss even if process crashes

**Effort:** 40h

#### 3.1.2 Startup Reconciliation

**Fichier:** `execution/reconciler.py` (enhance existing, 150 LOC)

```python
class BrokerReconciler:
    """Reconcile local state with broker account."""
    
    def __init__(self, execution_engine: BaseExecutionEngine, 
                 risk_engine: RiskEngine, audit_trail: AuditTrail):
        self.execution_engine = execution_engine
        self.risk_engine = risk_engine
        self.audit_trail = audit_trail
    
    def reconcile_at_startup(self) -> Dict[str, any]:
        """Compare local state vs broker state, fix mismatches."""
        
        # Load local state from audit trail
        local_positions = self.audit_trail.reconstruct_positions()
        
        # Get broker state
        broker_positions = self.execution_engine.get_positions()
        broker_orders = self.execution_engine.get_open_orders()
        
        # Compare
        mismatches = {
            'positions_in_local_not_broker': set(local_positions.keys()) - set(broker_positions.keys()),
            'positions_in_broker_not_local': set(broker_positions.keys()) - set(local_positions.keys()),
            'quantity_mismatch': {}
        }
        
        for symbol in set(local_positions.keys()) & set(broker_positions.keys()):
            if local_positions[symbol].quantity != broker_positions[symbol]:
                mismatches['quantity_mismatch'][symbol] = {
                    'local': local_positions[symbol].quantity,
                    'broker': broker_positions[symbol]
                }
        
        if mismatches['positions_in_local_not_broker']:
            logger.critical("POSITION_MISMATCH_FOUND", 
                           missing_from_broker=mismatches['positions_in_local_not_broker'])
            # Action: Log incident, alert operator
        
        if mismatches['positions_in_broker_not_local']:
            logger.critical("PHANTOM_POSITION_FOUND",
                           extra_on_broker=mismatches['positions_in_broker_not_local'])
            # Action: Close these positions immediately with MARKET order
            for symbol in mismatches['positions_in_broker_not_local']:
                self.force_close_position(symbol, reason="RECONCILIATION_MISMATCH")
        
        return mismatches
    
    def force_close_position(self, symbol: str, reason: str) -> None:
        """Force-close a position immediately."""
        position = self.risk_engine.positions.get(symbol)
        if not position:
            logger.warning("force_close_unknown_position", symbol=symbol)
            return
        
        order = Order(
            order_id=f"force_close_{symbol}_{int(time.time())}",
            symbol=symbol,
            side=OrderSide.SELL if position.side == "long" else OrderSide.BUY,
            quantity=abs(position.quantity),
            limit_price=None,  # MARKET order
            order_type="MARKET"
        )
        
        try:
            self.execution_engine.submit_order(order)
            logger.critical("POSITION_FORCE_CLOSED", symbol=symbol, reason=reason)
            self.audit_trail.log_event(AuditEvent(
                event_type="FORCE_CLOSED",
                symbol_pair=symbol,
                quantity=position.quantity,
                reason=reason
            ))
        except Exception as e:
            logger.error("force_close_failed", symbol=symbol, error=str(e))
```

**T├óches:**
```
1. Enhance execution/reconciler.py (8h) - Implement BrokerReconciler

2. Modify main.py - run_paper_trading() (6h):
   - On startup, before trading loop:
     reconciler = BrokerReconciler(execution_engine, risk_engine, audit_trail)
     mismatches = reconciler.reconcile_at_startup()
     if critical_mismatches:
         logger.critical("MANUAL_INTERVENTION_REQUIRED")
         raise RuntimeError("Fix broker mismatches before trading")
   
3. Create tests/test_reconciliation.py (12h)
   - test_reconcile_identical_state()
   - test_close_phantom_positions()
   - test_orphaned_orders_detection()
```

**Acceptance criteria:**
- Ô£à Startup compares local vs IBKR state
- Ô£à Mismatches logged at CRITICAL level
- Ô£à Phantom positions auto-closed with MARKET order
- Ô£à Audit trail updated with reconciliation actions

**Effort:** 40h (total for 3.1)

### 3.2 Feature: Global Kill-Switch (15h)

**Probl├¿me:** Pas de way to emergency stop trading

**Solution:** Implement graceful shutdown + signal handler

#### 3.2.1 Graceful Shutdown Handler

**Fichier:** `execution/shutdown_manager.py` (NEW, 100 LOC)

```python
import signal
import atexit
from typing import Callable, List

class ShutdownManager:
    """Manage graceful shutdown of trading system."""
    
    def __init__(self):
        self.is_shutting_down = False
        self.shutdown_callbacks: List[Callable] = []
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        atexit.register(self.trigger_shutdown)
    
    def register_callback(self, callback: Callable) -> None:
        """Register callback to run on shutdown."""
        self.shutdown_callbacks.append(callback)
    
    def _signal_handler(self, signum, frame):
        """Handle SIGTERM / SIGINT."""
        logger.critical("SHUTDOWN_SIGNAL_RECEIVED", signal=signum)
        self.trigger_shutdown()
    
    def trigger_shutdown(self) -> None:
        """Trigger graceful shutdown."""
        if self.is_shutting_down:
            return  # Already shutting down
        
        self.is_shutting_down = True
        logger.critical("SHUTDOWN_INITIATED")
        
        # Run all callbacks (in reverse order)
        for callback in reversed(self.shutdown_callbacks):
            try:
                callback()
            except Exception as e:
                logger.error("shutdown_callback_failed", error=str(e))
    
    def should_continue(self) -> bool:
        """Check if system should continue running."""
        return not self.is_shutting_down

# Global instance
_shutdown_manager = ShutdownManager()

def get_shutdown_manager() -> ShutdownManager:
    return _shutdown_manager
```

#### 3.2.2 Force-Close All Positions

**Fichier:** `risk/engine.py` (enhance, 20 LOC)

```python
def force_close_all_positions(self) -> List[str]:
    """Force-close ALL open positions immediately (MARKET orders)."""
    
    if not self.positions:
        logger.info("no_positions_to_close")
        return []
    
    closed_symbols = []
    for symbol_pair, position in list(self.positions.items()):
        logger.critical("FORCE_CLOSING_POSITION", 
                       symbol=symbol_pair, 
                       quantity=position.quantity)
        
        # External callback will submit MARKET close order
        # (execution_engine passed via dependency injection)
        self.positions.pop(symbol_pair)
        closed_symbols.append(symbol_pair)
    
    self.loss_streak = 0
    self.daily_loss = 0.0
    
    return closed_symbols
```

#### 3.2.3 Hook into Main Loop

**Fichier:** `main.py` (modify run_paper_trading, 15 LOC)

```python
def run_paper_trading(symbols, settings):
    """Paper trading with graceful shutdown."""
    
    shutdown_mgr = get_shutdown_manager()
    
    # Register shutdown callback: close all positions
    def on_shutdown():
        logger.critical("EMERGENCY_SHUTDOWN", mode="paper_trading")
        risk_engine.force_close_all_positions()
        # execution_engine.submit_market_close_orders(...)
    
    shutdown_mgr.register_callback(on_shutdown)
    
    # Main loop
    while shutdown_mgr.should_continue() and attempt < max_attempts:
        try:
            # ... trading logic ...
            pass
        except Exception as e:
            logger.error("...", ...)
            time.sleep(backoff_sec)
    
    logger.info("paper_trading_completed")
```

**T├óches:**
```
1. Create execution/shutdown_manager.py (6h)
   - Signal handler (SIGTERM, SIGINT)
   - Callbacks registration
   - is_shutting_down flag
   
2. Enhance risk/engine.py (4h)
   - force_close_all_positions() method
   
3. Modify main.py (3h)
   - Register shutdown callback
   - Check should_continue() in loop
   
4. Create tests/test_shutdown.py (6h)
   - test_sigint_closes_positions()
   - test_sigterm_closes_positions()
   - test_graceful_shutdown_timeout()
```

**Acceptance criteria:**
- Ô£à Ctrl+C closes all positions within 5 seconds
- Ô£à All positions logged before close
- Ô£à MARKET close orders placed immediately
- Ô£à No pending orders left open

**Effort:** 15h (total for 3.2)

### 3.3 Feature: Order Lifecycle Integration (25h)

**Probl├¿me:** Orders peuvent pendre ind├®finiment ÔåÆ capital locked

**Solution:** Enforcer 30s timeout par d├®faut, force-cancel

#### 3.3.1 Enhance OrderLifecycle class

**Fichier:** `execution/order_lifecycle.py` (enhance existing, 80 LOC)

```python
def check_and_timeout_orders(self, max_age_seconds: int = 30) -> List[str]:
    """Check all orders for timeout, return timed-out order IDs."""
    
    timed_out = []
    now = datetime.now()
    
    for order_id, lifecycle in list(self.orders.items()):
        age = (now - lifecycle.created_at).total_seconds()
        
        if age > max_age_seconds and lifecycle.status == OrderStatus.PENDING:
            logger.warning("ORDER_TIMEOUT_DETECTED", order_id=order_id, 
                          age_seconds=age)
            lifecycle.status = OrderStatus.TIMEOUT
            timed_out.append(order_id)
    
    return timed_out

def force_cancel_order(self, broker_order_id: str) -> bool:
    """Force-cancel a broker order."""
    try:
        execution_engine.cancel_order(broker_order_id)
        
        if broker_order_id in self.orders:
            self.orders[broker_order_id].status = OrderStatus.CANCELLED
        
        logger.info("ORDER_FORCE_CANCELLED", order_id=broker_order_id)
        return True
    except Exception as e:
        logger.error("FORCE_CANCEL_FAILED", order_id=broker_order_id, error=str(e))
        return False
```

#### 3.3.2 Hook into Main Loop

**Fichier:** `main.py` (modify, 15 LOC)

```python
def run_paper_trading(symbols, settings):
    """Paper trading with order timeout protection."""
    
    order_lifecycle_mgr = OrderLifecycleManager()
    
    while attempt < max_attempts and shutdown_mgr.should_continue():
        try:
            # ... signal generation, risk gate ...
            
            # Submit order
            broker_order_id = execution_engine.submit_order(order)
            order_lifecycle_mgr.track_order(broker_order_id, order)
            
            # Check for timeouts (every loop iteration)
            timed_out_order_ids = order_lifecycle_mgr.check_and_timeout_orders(
                max_age_seconds=settings.execution.order_timeout_seconds
            )
            
            for order_id in timed_out_order_ids:
                logger.critical("ORDER_TIMEOUT_CANCELLING", order_id=order_id)
                order_lifecycle_mgr.force_cancel_order(order_id)
                
                # Update risk engine: remove position
                symbol = order_lifecycle_mgr.orders[order_id].symbol
                if symbol in risk_engine.positions:
                    risk_engine.register_exit(symbol, 0, 0)  # Cancel position
```

**T├óches:**
```
1. Enhance execution/order_lifecycle.py (12h)
   - check_and_timeout_orders()
   - force_cancel_order()
   - Status tracking (PENDING ÔåÆ TIMEOUT ÔåÆ CANCELLED)
   
2. Create execution/order_lifecycle_manager.py (8h)
   - Central manager for tracking all orders
   - Query broker for order status
   - Reconcile with broker state
   
3. Modify main.py (3h)
   - Call check_and_timeout_orders() in loop
   - Force-cancel on timeout
   
4. Create tests/test_order_lifecycle_integration.py (10h)
   - test_order_timeout_30_seconds()
   - test_force_cancel_frees_capital()
   - test_orphaned_order_recovery()
```

**Acceptance criteria:**
- Ô£à Orders timeout after 30s (configurable)
- Ô£à Timed-out orders auto-cancelled
- Ô£à Position removed from RiskEngine
- Ô£à Capital becomes available for new trades

**Effort:** 25h (total for 3.3)

### 3.4 Validation Phase 1

```bash
# Run after Phase 1:
cd c:\Users\averr\EDGECORE

# 1. Test position persistence
pytest tests/test_audit_trail.py -v -s

# 2. Test reconciliation
pytest tests/test_reconciliation.py -v -s

# 3. Test graceful shutdown
pytest tests/test_shutdown.py -v -s
# Or manual: python main.py --mode paper --symbols AAPL, then Ctrl+C

# 4. Test order timeouts
pytest tests/test_order_lifecycle_integration.py -v -s

# 5. Check audit trail files created
ls -lh audit/
# Should have audit_2026-02-*.jsonl files

# 6. Manual end-to-end:
# - Start paper trading
# - Verify positions logged to audit trail
# - Kill process
# - Restart ÔåÆ positions should be recovered
```

**Acceptance criteria:**
- Ô£à All critical features (persistence, kill-switch, order timeout) working
- Ô£à Audit trail files created daily
- Ô£à Reconciliation runs on startup
- Ô£à Graceful shutdown closes positions

---

## 4. PHASE 2: Robustesse & R├®silience (3 semaines)

**Objectif:** Error recovery, circuit breaker, exponential backoff  
**Score cible:** 7.5/10  
**Effort:** 120 heures (3 semaines)  
**Blockers:** Phase 1 complete

### 4.1 Feature: Unified Error Handling Pattern (25h)

**Probl├¿me:** `except Exception: log(); continue` silencieuse everywhere

**Solution:** Error classification, categorized retries

#### 4.1.1 Error Taxonomy

**Fichier:** `common/errors.py` (NEW, 150 LOC)

```python
from enum import Enum

class ErrorCategory(Enum):
    """Error classification."""
    TRANSIENT = "transient"        # Retry (network, timeout)
    RETRYABLE = "retryable"        # Retry with circuit breaker
    NON_RETRYABLE = "non_retryable" # Fail immediately
    FATAL = "fatal"                # Crash system

class TradingError(Exception):
    """Base trading error."""
    
    def __init__(self, message: str, category: ErrorCategory, 
                 original_error: Optional[Exception] = None):
        self.message = message
        self.category = category
        self.original_error = original_error
        super().__init__(message)

class DataError(TradingError):
    """Data loading / validation error."""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.TRANSIENT, original_error)

class BrokerError(TradingError):
    """Broker API error."""
    # Subclass for each broker API: ConnectionError ÔåÆ TRANSIENT, InsufficientBalance ÔåÆ NON_RETRYABLE

class StrategyError(TradingError):
    """Error in strategy logic."""
    def __init__(self, message: str):
        super().__init__(message, ErrorCategory.NON_RETRYABLE)

# Helper function for error classification
def classify_exception(exc: Exception) -> ErrorCategory:
    """Classify exception from external library."""
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return ErrorCategory.TRANSIENT
    elif isinstance(exc, IBKR API.InsufficientBalance):
        return ErrorCategory.NON_RETRYABLE
    elif isinstance(exc, (KeyError, ValueError)):
        return ErrorCategory.FATAL  # Logic error
    else:
        return ErrorCategory.RETRYABLE  # Default: possibly retry
```

#### 4.1.2 Unified Error Handler

**Fichier:** `common/error_handler.py` (NEW, 200 LOC)

```python
from typing import Callable, TypeVar, Any
from functools import wraps

T = TypeVar('T')

def handle_error(error: TradingError, context: str = "") -> None:
    """
    Unified error handling.
    
    Args:
        error: TradingError with category
        context: Human-readable context (e.g., "loading data for AAPL")
    """
    
    if error.category == ErrorCategory.TRANSIENT:
        logger.warning("TRANSIENT_ERROR", context=context, 
                      message=error.message, error=str(error.original_error))
        # Will be retried upstream
    
    elif error.category == ErrorCategory.RETRYABLE:
        logger.error("RETRYABLE_ERROR", context=context, 
                    message=error.message, error=str(error.original_error))
        # Will be retried upstream with exponential backoff
    
    elif error.category == ErrorCategory.NON_RETRYABLE:
        logger.critical("NON_RETRYABLE_ERROR", context=context, 
                       message=error.message)
        # Must be handled by operator, don't retry
        alerter.create_alert(
            severity=AlertSeverity.CRITICAL,
            category=AlertCategory.SYSTEM,
            title=f"Non-retryable error: {context}",
            message=error.message
        )
    
    elif error.category == ErrorCategory.FATAL:
        logger.critical("FATAL_ERROR", context=context, 
                       message=error.message)
        # System must stop
        raise error

def with_error_handling(category: ErrorCategory = ErrorCategory.RETRYABLE,
                       max_retries: int = 3,
                       backoff_base: float = 2.0) -> Callable:
    """
    Decorator for automatic error handling + retries.
    
    Args:
        category: Error category if classification fails
        max_retries: Max retry attempts
        backoff_base: Exponential backoff base
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except TradingError as e:
                    handle_error(e, context=f"{func.__name__}")
                    
                    if e.category in [ErrorCategory.TRANSIENT, ErrorCategory.RETRYABLE]:
                        if attempt < max_retries - 1:
                            backoff_s = backoff_base ** attempt
                            logger.info("RETRY_AFTER_BACKOFF", 
                                       attempt=attempt, backoff_sec=backoff_s)
                            time.sleep(backoff_s)
                            continue
                    
                    raise  # Don't retry
            
            raise TradingError(f"{func.__name__} failed after {max_retries} attempts", 
                             ErrorCategory.NON_RETRYABLE)
        
        return wrapper
    return decorator
```

#### 4.1.3 Apply to Main Data Load

**Fichier:** `main.py` (refactor run_paper_trading, 30 LOC)

```python
@with_error_handling(category=ErrorCategory.TRANSIENT, max_retries=5)
def load_market_data_for_symbols(symbols: List[str], loader: DataLoader) -> Dict[str, pd.DataFrame]:
    """Load OHLCV data for all symbols."""
    
    prices = {}
    errors = []
    
    for symbol in symbols:
        try:
            df = loader.load_IBKR API_data(broker_name='IBKR', symbol=symbol)
            
            # Validate data quality
            validator = OHLCVValidator(symbol)
            result = validator.validate(df, raise_on_error=True)
            
            prices[symbol] = df['close']
            logger.info("DATA_LOADED", symbol=symbol, rows=len(df))
        
        except DataValidationError as e:
            raise DataError(f"Data validation failed for {symbol}: {e}", original_error=e)
        except Exception as e:
            raise DataError(f"Failed to load {symbol}: {e}", original_error=e)
    
    if not prices:
        raise DataError("All symbols failed to load", original_error=None)
    
    return prices
```

**T├óches:**
```
1. Create common/errors.py (8h)
   - TradingError base class
   - Error categories (TRANSIENT, RETRYABLE, NON_RETRYABLE, FATAL)
   - classify_exception() helper

2. Create common/error_handler.py (12h)
   - handle_error() unified function
   - @with_error_handling() decorator
   - Logging + alerting per category

3. Refactor main.py (15h)
   - Remove all bare except: continue
   - Replace with @with_error_handling()
   - Classify each error appropriately

4. Create tests/test_error_handling.py (12h)
   - test_transient_error_retries()
   - test_non_retryable_error_fails()
   - test_exponential_backoff_timing()
```

**Acceptance criteria:**
- Ô£à No bare `except Exception: pass` left in code
- Ô£à All errors classified (TRANSIENT vs NON_RETRYABLE)
- Ô£à Transient errors auto-retry with exponential backoff
- Ô£à Non-retryable errors alert operator

**Effort:** 25h

### 4.2 Feature: Data Integrity Validation Enforcement (20h)

**Probl├¿me:** OHLCVValidator existe mais n'est pas appel├®

**Solution:** Integrate validator into data pipeline

#### 4.2.1 Enhance Data Loader

**Fichier:** `data/loader.py` (modify, 20 LOC)

```python
class DataLoader:
    def __init__(self, cache_dir: str = "data/cache", 
                 validator: Optional[OHLCVValidator] = None):
        self.validator = validator or OHLCVValidator()
    
    def load_IBKR API_data(self, broker_name: str, symbol: str, 
                      timeframe: str = "1d", validate: bool = True) -> pd.DataFrame:
        """Load OHLCV data with validation."""
        
        try:
            # Load from IBKR API
            df = self._fetch_from_IBKR API(broker_name, symbol, timeframe)
            
            # Validate if requested
            if validate:
                result = self.validator.validate(df, raise_on_error=True)
                if not result.is_valid:
                    raise DataValidationError(
                        f"Data validation failed: {'; '.join(result.errors)}"
                    )
            
            logger.info("DATA_LOADED_AND_VALIDATED", 
                       symbol=symbol, rows=len(df), timeframe=timeframe)
            return df
        
        except DataValidationError as e:
            logger.error("DATA_VALIDATION_ERROR", symbol=symbol, error=str(e))
            raise
        except Exception as e:
            logger.error("DATA_LOAD_ERROR", symbol=symbol, error=str(e))
            raise
```

**T├óches:**
```
1. Enhance data/loader.py (6h)
   - Add validator parameter
   - Call validator.validate() after load
   - Raise on validation failure

2. Modify backtests/runner.py (6h)
   - Run validator on loaded data
   - Alert if invalid data used in backtest

3. Create tests/test_data_validation_integration.py (12h)
   - test_nan_data_rejected()
   - test_gap_data_rejected()
   - test_valid_data_accepted()
   - test_backtest_uses_validated_data()
```

**Acceptance criteria:**
- Ô£à Every load_IBKR API_data() call validates OHLCV
- Ô£à Invalid data raises DataValidationError (not silently NaN)
- Ô£à Test: load data with NaN ÔåÆ raises error

**Effort:** 20h

### 4.3 Feature: Circuit Breaker Integration (25h)

**Probl├¿me:** CircuitBreaker existe mais n'est pas utilis├® pour IBKR API calls

**Solution:** Wrap all broker API calls

#### 4.3.1 Apply Circuit Breaker to IBKR API Engine

**Fichier:** `execution/IBKR API_engine.py` (refactor, 40 LOC)

```python
from common.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

class IBKR APIExecutionEngine(BaseExecutionEngine):
    def __init__(self):
        # ... existing init ...
        self.api_breaker = CircuitBreaker(
            name="IBKR API_api",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout_seconds=60,
                success_threshold=2
            )
        )
    
    def submit_order(self, order: Order) -> str:
        """Submit order with circuit breaker protection."""
        
        try:
            # Check if circuit breaker is OPEN
            if self.api_breaker.metrics.state == CircuitBreakerState.OPEN:
                raise CircuitBreakerOpen(
                    f"Circuit breaker open. Will retry at {self.api_breaker.metrics.state_change_time + timedelta(seconds=60)}"
                )
            
            # Call wrapped API
            broker_order_id = self.api_breaker.call(
                self._submit_order_to_broker,
                order
            )
            
            logger.info("ORDER_SUBMITTED", order_id=broker_order_id, symbol=order.symbol)
            return broker_order_id
        
        except CircuitBreakerOpen as e:
            logger.error("CIRCUIT_BREAKER_OPEN", error=str(e))
            raise TradingError(str(e), ErrorCategory.TRANSIENT)
        except IBKR API.BaseError as e:
            logger.error("BROKER_ERROR", error=str(e))
            raise TradingError(str(e), ErrorCategory.RETRYABLE)
    
    def _submit_order_to_broker(self, order: Order) -> str:
        """Raw API call (wrapped by circuit breaker)."""
        response = self.broker.create_limit_order(
            symbol=order.symbol,
            side='buy' if order.side == OrderSide.BUY else 'sell',
            amount=order.quantity,
            price=order.limit_price
        )
        return response['id']
```

#### 4.3.2 Data Loader Circuit Breaker

**Fichier:** `data/loader.py` (add, 15 LOC)

```python
def load_IBKR API_data(self, broker_name: str, symbol: str, ...) -> pd.DataFrame:
    """Load data with circuit breaker protection."""
    
    try:
        breaker = getattr(self, f"api_breaker_{broker_name}", None)
        if not breaker:
            breaker = CircuitBreaker(f"data_load_{broker_name}")
            setattr(self, f"api_breaker_{broker_name}", breaker)
        
        df = breaker.call(
            self._fetch_from_IBKR API_raw,
            broker_name, symbol
        )
        return df
    
    except CircuitBreakerOpen as e:
        raise DataError(f"broker API down: {e}")
```

**T├óches:**
```
1. Refactor execution/IBKR API_engine.py (10h)
   - Wrap submit_order with circuit breaker
   - Wrap cancel_order with circuit breaker
   - Wrap get_account_balance with circuit breaker
   - Map IBKR API exceptions to ErrorCategories

2. Refactor data/loader.py (8h)
   - Wrap IBKR API fetch calls with circuit breaker
   
3. Update main.py (3h)
   - Catch CircuitBreakerOpen exceptions
   - Treat as TRANSIENT errors
   
4. Create tests/test_circuit_breaker_integration.py (12h)
   - test_circuit_opens_after_5_api_failures()
   - test_circuit_half_open_recovery()
   - test_circuit_blocks_api_calls_when_open()
```

**Acceptance criteria:**
- Ô£à 5 API failures ÔåÆ circuit opens
- Ô£à Circuit stays open for 60s
- Ô£à New API calls blocked while open
- Ô£à After 60s, circuit half-open (allows 1 test call)
- Ô£à If test succeeds, circuit closes

**Effort:** 25h

### 4.4 Validation Phase 2

```bash
# Run after Phase 2:
cd c:\Users\averr\EDGECORE

# 1. Test error handling
pytest tests/test_error_handling.py -v -s

# 2. Test data validation
pytest tests/test_data_validation_integration.py -v -s

# 3. Test circuit breaker
pytest tests/test_circuit_breaker_integration.py -v -s

# 4. Manual test: simulate API failures
# - Edit test to mock IBKR API failures
# - Verify circuit breaker opens after 5 failures
# - Verify recovery after 60s

# 5. Check no bare except: patterns
grep -r "except Exception:" . --include="*.py" | grep -v "test_\|\.venv" | wc -l
# Should return 0 or very small number
```

**Acceptance criteria:**
- Ô£à All errors classified and handled
- Ô£à Exponential backoff working
- Ô£à Circuit breaker active for IBKR API + Data loader
- Ô£à No silent failures / swallowed exceptions

---

## 5. PHASE 3: Observabilit├® & Monitoring (2 semaines)

**Objectif:** Real-time alerts, centralized logging, dashboard  
**Score cible:** 8.5/10  
**Effort:** 100 heures (2 semaines)  
**Blockers:** Phase 1 + 2 complete

### 5.1 Feature: Slack Integration (15h)

**Fichier:** `monitoring/slack_alerter.py` (NEW, 100 LOC)

```python
import requests
from typing import Dict, Optional

class SlackAlerter:
    """Send critical alerts to Slack."""
    
    def __init__(self, webhook_url: str):
        """
        Initialize Slack alerter.
        
        Args:
            webhook_url: Slack Incoming Webhook URL
        """
        self.webhook_url = webhook_url
        self.last_alert_time: Dict[str, float] = {}  # Throttle by alert type
        self.throttle_seconds = 30  # Don't spam same alert < 30s
    
    def send_alert(self, level: str, title: str, message: str, 
                   data: Optional[Dict] = None) -> bool:
        """
        Send alert to Slack.
        
        Args:
            level: CRITICAL, ERROR, WARNING, INFO
            title: Short title
            message: Detailed message
            data: Optional metadata dict
        
        Returns:
            True if sent successfully
        """
        
        # Throttle duplicates
        alert_key = f"{level}:{title}"
        now = time.time()
        if alert_key in self.last_alert_time:
            if now - self.last_alert_time[alert_key] < self.throttle_seconds:
                logger.debug("SLACK_ALERT_THROTTLED", alert_key=alert_key)
                return False
        
        # Color code by level
        color_map = {
            'CRITICAL': '#ff0000',  # Red
            'ERROR': '#ff6600',     # Orange
            'WARNING': '#ffff00',   # Yellow
            'INFO': '#00ff00'       # Green
        }
        
        # Build message
        payload = {
            'attachments': [{
                'color': color_map.get(level, '#cccccc'),
                'title': title,
                'text': message,
                'ts': int(now),
                'fields': [
                    {'title': 'Level', 'value': level, 'short': True},
                    {'title': 'Time', 'value': datetime.now().isoformat(), 'short': True}
                ]
            }]
        }
        
        if data:
            for key, value in data.items():
                payload['attachments'][0]['fields'].append({
                    'title': key,
                    'value': str(value),
                    'short': True
                })
        
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=5)
            if response.status_code == 200:
                self.last_alert_time[alert_key] = now
                logger.info("SLACK_ALERT_SENT", level=level, title=title)
                return True
            else:
                logger.error("SLACK_ALERT_FAILED", 
                           status=response.status_code, 
                           response=response.text)
                return False
        
        except Exception as e:
            logger.error("SLACK_ALERT_EXCEPTION", error=str(e))
            return False
```

**T├óches:**
```
1. Create monitoring/slack_alerter.py (8h)
   - Send to Slack with formatting
   - Throttle duplicates (30s)
   - Color code by severity

2. Integrate into AlertManager (4h)
   - Add SlackAlerter handler
   - Route CRITICAL alerts to Slack
   
3. Configure in settings (2h)
   - Add SLACK_WEBHOOK_URL env var
   - config/dev.yaml, prod.yaml

4. Test Slack integration (3h)
   - test_slack_alert_sends()
   - test_slack_alert_throttled()
```

**Acceptance criteria:**
- Ô£à CRITICAL alerts sent to Slack immediately
- Ô£à Throttling prevents spam (< 1 alert per 30s per type)
- Ô£à Formatted with color, timestamp, metadata

**Effort:** 15h

### 5.2 Feature: Email Alerts (10h)

**Fichier:** `monitoring/email_alerter.py` (NEW, 80 LOC)

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailAlerter:
    """Send alerts via email."""
    
    def __init__(self, smtp_server: str, smtp_port: int, 
                 sender_email: str, sender_password: str,
                 recipient_emails: List[str]):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.recipients = recipient_emails
    
    def send_alert(self, level: str, title: str, message: str,
                   data: Optional[Dict] = None) -> bool:
        """Send alert via email."""
        
        # Only send ERROR and CRITICAL via email (not INFO/WARNING spam)
        if level not in ['ERROR', 'CRITICAL']:
            return True
        
        try:
            msg = MIMEMultipart('text', 'plain')
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.recipients)
            msg['Subject'] = f"[{level}] {title}"
            
            body = f"""
EDGECORE Trading System Alert

Severity: {level}
Title: {title}
Time: {datetime.now().isoformat()}

Message:
{message}

Data:
"""
            if data:
                for key, value in data.items():
                    body += f"  {key}: {value}\n"
            
            msg.attach(MIMEText(body))
            
            # Send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, self.recipients, msg.as_string())
            
            logger.info("EMAIL_ALERT_SENT", level=level, title=title)
            return True
        
        except Exception as e:
            logger.error("EMAIL_ALERT_FAILED", error=str(e))
            return False
```

**T├óches:**
```
1. Create monitoring/email_alerter.py (6h)
   - SMTP integration
   - Formatted email body

2. Integrate into AlertManager (2h)
   
3. Configure SMTP settings (2h)
   - config/.env variables
   - SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASS
```

**Acceptance criteria:**
- Ô£à ERROR/CRITICAL alerts sent via email
- Ô£à Formatted with timestamp, level, metadata

**Effort:** 10h

### 5.3 Feature: Dashboard JSON Endpoint (20h)

**Fichier:** `monitoring/dashboard.py` (NEW, 250 LOC)

```python
from typing import Dict, Any
import json

class DashboardGenerator:
    """Generate JSON dashboard snapshot."""
    
    def __init__(self, risk_engine: RiskEngine, 
                 execution_engine: BaseExecutionEngine,
                 alert_manager: AlertManager):
        self.risk_engine = risk_engine
        self.execution_engine = execution_engine
        self.alert_manager = alert_manager
    
    def generate_dashboard(self) -> Dict[str, Any]:
        """Generate dashboard snapshot."""
        
        return {
            'timestamp': datetime.now().isoformat(),
            'system_status': self._system_status(),
            'risk_metrics': self._risk_metrics(),
            'positions': self._positions(),
            'orders': self._orders(),
            'alerts': self._alerts_summary(),
            'performance': self._performance_metrics()
        }
    
    def _system_status(self) -> Dict[str, Any]:
        """System status (up/down, mode, version)."""
        return {
            'status': 'healthy',
            'mode': 'paper',  # or 'live'
            'uptime_seconds': self._uptime(),
            'memory_mb': self._memory_usage()
        }
    
    def _risk_metrics(self) -> Dict[str, Any]:
        """Risk metrics."""
        return {
            'current_equity': self.risk_engine.equity_history[-1] if self.risk_engine.equity_history else 0,
            'daily_loss': self.risk_engine.daily_loss,
            'daily_loss_pct': (self.risk_engine.daily_loss / self.risk_engine.initial_equity) * 100,
            'max_daily_loss_limit_pct': self.risk_engine.config.max_daily_loss_pct * 100,
            'positions_count': len(self.risk_engine.positions),
            'max_concurrent_positions': self.risk_engine.config.max_concurrent_positions,
            'loss_streak': self.risk_engine.loss_streak,
            'max_consecutive_losses': self.risk_engine.config.max_consecutive_losses
        }
    
    def _positions(self) -> list:
        """Open positions."""
        return [
            {
                'symbol': pos.symbol_pair,
                'side': pos.side,
                'quantity': pos.quantity,
                'entry_price': pos.entry_price,
                'current_price': pos.marked_price,
                'unrealized_pnl': pos.pnl,
                'age_hours': (datetime.now() - pos.entry_time).total_seconds() / 3600
            }
            for pos in self.risk_engine.positions.values()
        ]
    
    def _orders(self) -> list:
        """Open orders."""
        # Fetch from execution engine
        open_orders = self.execution_engine.get_open_orders() or []
        return [
            {
                'order_id': order.get('id'),
                'symbol': order.get('symbol'),
                'side': order.get('side'),
                'quantity': order.get('amount'),
                'price': order.get('price'),
                'status': order.get('status')
            }
            for order in open_orders
        ]
    
    def _alerts_summary(self) -> Dict[str, Any]:
        """Alert summary."""
        all_alerts = list(self.alert_manager.alerts.values())
        critical_count = sum(1 for a in all_alerts if a.severity == AlertSeverity.CRITICAL)
        error_count = sum(1 for a in all_alerts if a.severity == AlertSeverity.ERROR)
        
        return {
            'total': len(all_alerts),
            'critical': critical_count,
            'error': error_count,
            'recent': [a.to_dict() for a in all_alerts[-5:]]  # Last 5
        }
    
    def _performance_metrics(self) -> Dict[str, Any]:
        """Performance metrics."""
        returns = self._calculate_returns()
        return {
            'total_return': returns[-1] if returns else 0,
            'sharpe_ratio': self._calculate_sharpe(returns),
            'max_drawdown': self._calculate_max_drawdown(returns),
            'trades_today': 0  # Count from audit trail
        }
```

**T├óches:**
```
1. Create monitoring/dashboard.py (12h)
   - Capture system status, risk, positions, orders, alerts
   - Generate JSON snapshot
   
2. Create API endpoint (8h)
   - Add Flask route: /api/dashboard
   - Return JSON response
   - Refresh every 30s on client
   
3. Create simple HTML dashboard (20h, optional for Phase 3)
   - plots.ly or chart.js
   - Real-time updates via WebSocket or polling
```

**Acceptance criteria:**
- Ô£à /api/dashboard returns JSON snapshot
- Ô£à Includes: equity, positions, orders, alerts, performance
- Ô£à Accessible from browser/curl

**Effort:** 20h (core), +20h (HTML UI optional)

### 5.4 Feature: Centralized Logging (15h)

**Fichier:** Enhance `monitoring/logger.py` (add persistence, 50 LOC)

```python
class CentralizedLogger:
    """Log aggregation to file + remote."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Structured logging to JSONL (one JSON per line)
        self.jsonl_handler = logging.FileHandler(
            self.log_dir / f"edgecore_{datetime.now().date()}.jsonl"
        )
        self.jsonl_handler.setFormatter(
            structlog.processors.JSONRenderer()
        )
    
    def setup(self, name: str = "edgecore"):
        """Configure structured logging."""
        
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        
        # Add JSONL file handler
        structlog_logger = structlog.get_logger(name)
        return structlog_logger
```

**T├óches:**
```
1. Enhance monitoring/logger.py (6h)
   - JSONL output (machine-parseable)
   - Daily rotation of log files
   - Max size limits (prevent disk fill)

2. Add log aggregation endpoint (6h)
   - /api/logs - search, filter, tail
   - Query by symbol, level, time range

3. Create tests/test_logging_integration.py (5h)
   - Test JSONL format
   - Test file rotation
```

**Acceptance criteria:**
- Ô£à Logs written to JSONL daily files
- Ô£à Can query logs via API
- Ô£à Fields: timestamp, level, symbol, message, context

**Effort:** 15h

### 5.5 Validation Phase 3

```bash
# Run after Phase 3:
cd c:\Users\averr\EDGECORE

# 1. Test Slack integration (manual)
# - Trigger critical alert
# - Verify message in Slack

# 2. Test Email alerts (manual)
# - Trigger error alert
# - Check email received

# 3. Test Dashboard
curl http://localhost:8000/api/dashboard | jq '.'
# Should return JSON with system status, positions, alerts

# 4. Check logs
ls -lh logs/
# Should have edgecore_2026-02-*.jsonl files

# 5. Query logs
curl http://localhost:8000/api/logs?level=CRITICAL

# 6. Manual test: start trading, trigger alerts
python main.py --mode paper --symbols AAPL
# - Should see logs written to JSONL
# - Alerts sent to Slack + Email
# - Dashboard updated
```

**Acceptance criteria:**
- Ô£à Real-time alerts via Slack/Email
- Ô£à Dashboard accessible
- Ô£à All logs in JSONL format
- Ô£à Can query/search logs

---

## 6. PHASE 4: Testing & Validation Compl├¿te (3 semaines)

**Objectif:** 70%+ coverage, E2E tests, chaos engineering  
**Score cible:** 9.5/10  
**Effort:** 140 heures (3 semaines)  
**Blockers:** Phase 1-3 complete

### 6.1 Feature: Comprehensive Unit Test Coverage (40h)

**Current state:** Estimated 40% coverage  
**Target:** 70%+ coverage

**Process:**
```bash
# 1. Measure current coverage
pytest tests/ --cov=. --cov-report=html
# Open htmlcov/index.html

# 2. Identify gaps (< 70% modules)
# Prioritize:
#   - main.py (0% ÔåÆ needs E2E, harder)
#   - backtests/runner.py (30% ÔåÆ add tests)
#   - strategies/pair_trading.py (20% ÔåÆ add tests)
#   - execution/IBKR API_engine.py (40% ÔåÆ add mocks)

# 3. Add missing tests for each gap
# Target: each module >= 70% coverage
```

**New test files needed:**
```
tests/test_main_integration.py (20h)
  - test_paper_trading_full_flow()
  - test_live_trading_safety_checks()
  - test_backtest_deterministic()

tests/test_strategy_comprehensive.py (12h)
  - test_pair_discovery_multiprocess()
  - test_cointegration_detection()
  - test_signal_generation_edge_cases()

tests/test_execution_comprehensive.py (10h)
  - test_order_submission_retry()
  - test_order_cancellation()
  - test_balance_query_circuit_breaker()

tests/test_backtests_realistic.py (15h)
  - test_backtest_with_slippage()
  - test_backtest_with_partial_fills()
  - test_backtest_with_commissions()
  - test_backtest_max_drawdown()
```

**T├óches:**
```
1. Measure current coverage (2h)
   - Run pytest --cov
   - Identify < 70% modules
   
2. Write unit tests for gaps (35h)
   - Target: 70%+ coverage overall
   
3. Validate coverage (3h)
   - Re-run coverage
   - Confirm 70%+
```

**Acceptance criteria:**
- Ô£à pytest coverage >= 70%
- Ô£à All critical paths tested
- Ô£à test_main_integration.py passes (validates full flow)

**Effort:** 40h

### 6.2 Feature: End-to-End Integration Tests (30h)

**Objective:** Test full trading flow with real IBKR testnet

**Architecture:**
```python
class E2ETestSuite:
    
    def setup_testnet_account(self):
        """Create IBKR testnet account with initial balance."""
        # API key from testnet.IBKR.vision
        # Initial balance: 10 AAPL, 10 MSFT
    
    def test_full_trading_flow(self):
        """Complete flow: discover pairs ÔåÆ generate signals ÔåÆ trade ÔåÆ close."""
        
        # 1. Load market data
        # 2. Discover cointegrated pairs
        # 3. Generate signals
        # 4. Risk gate (check constraints)
        # 5. Submit order
        # 6. Wait for fill
        # 7. Mark to market
        # 8. Generate exit signal
        # 9. Close position
        # 10. Validate P&L
        # 11. Verify audit trail logged
        # 12. Verify alerts generated
    
    def test_error_recovery_flow(self):
        """Test recovery from errors."""
        
        # Simulate: API timeout ÔåÆ retry ÔåÆ success
        # Verify: exponential backoff, circuit breaker, no silent failures
    
    def test_risk_constraints_enforced(self):
        """Verify all risk limits enforced."""
        
        # Simulate: try to exceed max_risk_per_trade
        # Verify: rejected by risk engine
        
        # Simulate: try to exceed max_concurrent_positions
        # Verify: rejected
        
        # Simulate: exceed daily loss limit
        # Verify: no new trades allowed
    
    def test_graceful_shutdown(self):
        """Verify graceful shutdown."""
        
        # Open 5 positions
        # Send SIGINT (Ctrl+C)
        # Verify: all positions closed with MARKET orders
        # Verify: audit trail updated
        # Verify: process exits cleanly
    
    def test_position_persistence(self):
        """Verify position persistence."""
        
        # Open 3 positions
        # Kill process
        # Restart ÔåÆ positions should be recovered
        # Verify: position quantities match broker
```

**T├óches:**
```
1. Create tests/test_e2e_trading_flow.py (25h)
   - Full trading flow
   - Error recovery
   - Risk constraints
   - Graceful shutdown
   - Position persistence

2. Setup IBKR testnet account (2h)
   - Generate API keys
   - Config testnet in dev.yaml

3. Infrastructure test harness (3h)
   - Fixture: testnet account setup/cleanup
   - Timeout protection (tests max 10 min each)
```

**Acceptance criteria:**
- Ô£à Full E2E test executes without errors
- Ô£à 50+ real trades executed on testnet
- Ô£à All risk constraints enforced
- Ô£à Position persistence verified
- Ô£à Graceful shutdown verified

**Effort:** 30h

### 6.3 Feature: Chaos Engineering Tests (25h)

**Objective:** Test failure scenarios

**Scenarios:**
```
1. API Failures
   - Timeouts (mock: delay 60s)
   - Rate limiting (429 response)
   - 500 errors (retry should handle)
   - Connection reset (TRANSIENT error)

2. Data Quality Issues
   - NaN prices (should be rejected)
   - Missing candles (gaps)
   - Duplicate timestamps
   - Zero volumes

3. Market Conditions
   - Large price gaps (circuit breaker volatility check)
   - No liquidity (order timeouts)
   - Extreme spreads (slippage)

4. System Failures
   - Process OOM
   - Disk full (audit trail can't write)
   - Clock skew (timestamps inconsistent)
   - Loss of database connection
```

**T├óches:**
```
1. Create tests/test_chaos_engineering.py (20h)
   - Simulate each failure scenario
   - Verify graceful handling
   - No data corruption

2. Create chaos harness (5h)
   - Helper: mock_api_timeout()
   - Helper: inject_nan_data()
   - Helper: simulate_price_gap()
   - etc.
```

**Acceptance criteria:**
- Ô£à System recovers from all transient failures
- Ô£à No crashes on data quality issues
- Ô£à No silent failures
- Ô£à All recovery attempts logged

**Effort:** 25h

### 6.4 Feature: Performance & Load Testing (20h)

**Objective:** Validate performance under load

**Tests:**
```
1. Throughput
   - 100 signals per loop iteration
   - Target: process in < 1 second
   
2. Latency
   - Trade entry ÔåÆ execution: < 5s (target < 2s)
   - Data load ÔåÆ signal ÔåÆ order: < 3s
   
3. Memory
   - Max memory: 500 MB
   - No memory leaks after 1000 trades
   
4. Scalability
   - 50 concurrent pairs
   - 1000 trades per day
   - 30 days backtest
```

**T├óches:**
```
1. Create benchmarks/ directory (8h)
   - bench_signal_generation.py
   - bench_order_submission.py
   - bench_memory_usage.py

2. Create tests/test_performance.py (12h)
   - test_throughput_100_signals()
   - test_latency_under_load()
   - test_memory_no_leaks_1000_trades()
```

**Acceptance criteria:**
- Ô£à 100 signals processed in < 1s
- Ô£à Trade latency < 5s
- Ô£à No memory leaks
- Ô£à Handles 50+ pairs without slowdown

**Effort:** 20h

### 6.5 Validation Phase 4

```bash
# Run after Phase 4:
cd c:\Users\averr\EDGECORE

# 1. Measure coverage
pytest tests/ --cov=. --cov-report=term-missing
# Should show >= 70% coverage

# 2. Run E2E tests (requires testnet)
pytest tests/test_e2e_trading_flow.py -v -s
# Should pass all tests

# 3. Run chaos tests
pytest tests/test_chaos_engineering.py -v -s

# 4. Run performance tests
pytest benchmarks/ -v

# 5. Check test results
pytest tests/ -v --tb=short | tail -20
# Should show all tests passing
```

**Acceptance criteria:**
- Ô£à 70%+ test coverage
- Ô£à E2E tests passing
- Ô£à Chaos tests handling failures
- Ô£à Performance targets met

---

## 7. PHASE 5: Excellence & Optimisation (2 semaines)

**Objectif:** Code polish, documentation, refactoring  
**Score cible:** 10/10  
**Effort:** 80 heures (2 semaines)

### 7.1 Refactor: Paper/Live Code Duplication (20h)

**Current:** run_paper_trading() and run_live_trading() duplicate ~ 80% code

**Solution:** ExecutionMode abstraction

**Fichier:** `execution/modes.py` (refactor, 250 LOC)

```python
from abc import ABC, abstractmethod

class ExecutionMode(ABC):
    """Abstract execution mode."""
    
    @abstractmethod
    def on_startup(self, context: ExecutionContext) -> None:
        """Run on mode startup."""
        pass
    
    @abstractmethod
    def on_shutdown(self, context: ExecutionContext) -> None:
        """Run on mode shutdown."""
        pass
    
    @abstractmethod
    def validate_safety(self, context: ExecutionContext) -> None:
        """Validate mode-specific safety checks."""
        pass

class BacktestMode(ExecutionMode):
    """Backtest mode (historical data, no real orders)."""
    
    def on_startup(self, context):
        logger.info("BACKTEST_MODE_STARTING")
        # Load historical data
        # Initialize metrics
    
    def on_shutdown(self, context):
        logger.info("BACKTEST_MODE_COMPLETE")
        # Print final metrics
    
    def validate_safety(self, context):
        # No safety checks needed (no real money)
        pass

class PaperMode(ExecutionMode):
    """Paper trading mode (sandbox, real data)."""
    
    def on_startup(self, context):
        logger.info("PAPER_MODE_STARTING", broker=context.settings.execution.broker)
        
        if not context.settings.execution.use_sandbox:
            raise ValueError("Paper mode requires sandbox=true")
        
        # Verify sandbox enabled
        # Print warning: "Paper trading enabled, no real money"
    
    def on_shutdown(self, context):
        logger.info("PAPER_MODE_STOPPED")
        # Close all positions
        context.risk_engine.force_close_all_positions()
    
    def validate_safety(self, context):
        if not context.settings.execution.use_sandbox:
            raise ValueError("Paper mode requires use_sandbox=true")

class LiveMode(ExecutionMode):
    """Live trading mode (real money!)."""
    
    def on_startup(self, context):
        # EXTREME caution
        logger.critical("LIVE_TRADING_STARTING", capital=context.settings.backtest.initial_capital)
        
        # Safety checks
        if context.settings.execution.use_sandbox:
            raise ValueError("Live mode requires sandbox=false in config")
        
        if os.getenv("ENABLE_LIVE_TRADING") != "true":
            raise ValueError("Live trading disabled. Set ENABLE_LIVE_TRADING=true")
        
        # Require confirmation
        print("WARNING: LIVE TRADING WITH REAL MONEY")
        confirmation = input("Type 'I UNDERSTAND THE RISKS': ")
        if confirmation != "I UNDERSTAND THE RISKS":
            raise ValueError("Live trading cancelled by user")
        
        # Email verification (optional)
        # Send email with link, require click within 5 min
    
    def on_shutdown(self, context):
        logger.critical("LIVE_TRADING_STOPPED")
        context.risk_engine.force_close_all_positions()
    
    def validate_safety(self, context):
        if context.settings.execution.use_sandbox:
            raise ValueError("Live mode requires sandbox=false")
        if os.getenv("ENABLE_LIVE_TRADING") != "true":
            raise ValueError("Live trading not enabled")
```

**Refactored main loop:** `execution/trading_loop.py` (NEW, 150 LOC)

```python
def run_trading_loop(context: ExecutionContext, mode: ExecutionMode):
    """Single unified trading loop for all modes."""
    
    mode.validate_safety(context)
    mode.on_startup(context)
    
    try:
        attempt = 0
        while attempt < context.settings.backtest.max_iterations:
            attempt += 1
            
            try:
                # 1. Load data
                prices = context.data_loader.load_market_data(context.symbols)
                
                # 2. Generate signals
                signals = context.strategy.generate_signals(prices)
                
                # 3. Risk gate + execution
                for signal in signals:
                    can_enter, reason = context.risk_engine.can_enter_trade(
                        symbol_pair=signal.symbol_pair,
                        position_size=10.0,
                        current_equity=context.execution_engine.get_account_balance(),
                        volatility=0.02
                    )
                    
                    if not can_enter:
                        logger.warning("TRADE_REJECTED", reason=reason)
                        continue
                    
                    # Submit order
                    order = Order(...)
                    broker_order_id = context.execution_engine.submit_order(order)
                
                # 4. Check for order timeouts
                timed_out = context.order_lifecycle_mgr.check_and_timeout_orders()
                for order_id in timed_out:
                    context.order_lifecycle_mgr.force_cancel_order(order_id)
                
                # 5. Update monitoring
                context.alerter.update_metrics(...)
                
                # 6. Sleep
                time.sleep(context.settings.execution.paper_trading_loop_interval_seconds)
            
            except Exception as e:
                logger.error("TRADING_LOOP_ERROR", error=str(e))
                # Backoff, retry
    
    finally:
        mode.on_shutdown(context)
```

**Refactored main():**
```python
def main():
    args = parse_args()
    settings = get_settings()
    
    # Create execution context
    context = ExecutionContext(
        symbols=args.symbols,
        settings=settings,
        data_loader=DataLoader(),
        strategy=PairTradingStrategy(),
        risk_engine=RiskEngine(...),
        execution_engine=get_execution_engine(settings),
        alerter=AlertManager(),
        audit_trail=AuditTrail(),
        # ... etc
    )
    
    # Select mode
    if args.mode == "backtest":
        mode = BacktestMode()
    elif args.mode == "paper":
        mode = PaperMode()
    elif args.mode == "live":
        mode = LiveMode()
    else:
        raise ValueError(f"Unknown mode: {args.mode}")
    
    # Run unified loop
    run_trading_loop(context, mode)
```

**T├óches:**
```
1. Create execution/modes.py (10h)
   - ExecutionMode base class
   - BacktestMode, PaperMode, LiveMode subclasses

2. Create execution/trading_loop.py (8h)
   - Unified loop logic
   - Works for all modes

3. Refactor main.py (10h)
   - Simplify main() to mode selection
   - Replace run_paper_trading() + run_live_trading()

4. Create tests/test_execution_modes.py (6h)
   - test_paper_mode_requires_sandbox()
   - test_live_mode_requires_confirmation()
   - test_backtest_mode_deterministic()
```

**Acceptance criteria:**
- Ô£à run_paper_trading() + run_live_trading() removed (consolidated)
- Ô£à main.py < 50 LOC (just mode selection)
- Ô£à trading_loop() < 100 LOC (no code duplication)
- Ô£à All mode tests passing

**Effort:** 20h

### 7.2 Documentation: Architecture Handbook (15h)

**File:** `docs/ARCHITECTURE.md` (NEW, 5000+ words)

```markdown
# EDGECORE Architecture Handbook

## 1. System Overview
- Component diagram (modules + interactions)
- Data flow (data ÔåÆ strategy ÔåÆ execution)
- Risk boundaries

## 2. Component Reference
- DataLoading (loader.py, validators.py)
- Strategy (pair_trading.py, cointegration.py)
- RiskEngine (risk/engine.py, constraints.py)
- Execution (execution/base.py, IBKR API_engine.py, ibkr_engine.py)
- Monitoring (alerter.py, logger.py, events.py)
- etc.

## 3. Key Design Decisions
- Why pair trading (cointegration)?
- Why separate risk engine?
- Why audit trail persistence?
- Why ExecutionMode abstraction?

## 4. Error Handling Philosophy
- Error categories (TRANSIENT vs FATAL)
- Retry strategies (exponential backoff)
- Circuit breaker pattern
- Silent failures ÔåÆ impossible

## 5. Safety Guarantees
- Capital preservation guarantees
- Position persistence guarantee
- Kill-switch availability
- Audit trail immutability

## 6. Testing Strategy
- Unit tests (70%+ coverage)
- Integration tests (E2E flows)
- Chaos engineering (failure scenarios)
- Performance benchmarks

## 7. Deployment Checklist
- Pre-production validation
- Testnet trading validation
- Monitoring setup
- Incident response playbook
```

**T├óches:**
```
1. Write architecture handbook (12h)
   - Diagrams (ASCII or images)
   - Deep dives into each module
   - Design decisions
   - Examples

2. Create API reference (3h)
   - Auto-generate from docstrings
   - Export as Markdown
```

**Acceptance criteria:**
- Ô£à 5000+ word handbook
- Ô£à All modules documented
- Ô£à Design decisions explained
- Ô£à Examples provided

**Effort:** 15h

### 7.3 Documentation: Operations Manual (10h)

**File:** `docs/OPERATIONS.md` (NEW, 2000+ words)

```markdown
# EDGECORE Operations Manual

## 1. Pre-Production Checklist
- [ ] All tests passing
- [ ] 70%+ coverage
- [ ] E2E tests on testnet
- [ ] Monitoring configured
- [ ] Alerts configured
- [ ] Backups setup

## 2. Starting the System
```bash
cd /path/to/edgecore
export EDGECORE_ENV=prod
export broker_API_KEY=...
export broker_API_SECRET=...
python main.py --mode paper --symbols AAPL MSFT
```

## 3. Monitoring Dashboard
- Access: http://localhost:8000/api/dashboard
- Metrics: equity, positions, alerts
- Update frequency: 30s

## 4. Alert Types & Actions
| Alert | Severity | Action |
|-------|----------|--------|
| Position exceeds max loss | CRITICAL | Close position immediately |
| API timeout | WARNING | Check internet, broker status |
| Circuit breaker open | ERROR | Wait 60s, monitor recovery |
| etc. | | |

## 5. Incident Response
### Loss of market data
- Check IBKR API status
- Verify API credentials
- Circuit breaker should prevent trading
- Manual decision: continue or halt?

### Broker API down
- Circuit breaker opens after 5 failures
- Trades rejected until recovery
- Monitor broker status page

### Position mismatch (restart)
- Reconciliation runs automatically
- Phantom positions force-closed
- Check audit trail for discrepancy

## 6. Operational Metrics
- Trades per day
- Win rate
- Sharpe ratio
- Max drawdown
- Alert rate

## 7. Maintenance Tasks
- Daily: review logs, check performance
- Weekly: backtest new parameters
- Monthly: rotate API keys
- Quarterly: disaster recovery drill
```

**T├óches:**
```
1. Write operations manual (8h)
2. Create incident playbooks (2h)
```

**Acceptance criteria:**
- Ô£à 2000+ word manual
- Ô£à Startup/shutdown procedures
- Ô£à Incident response plans
- Ô£à Monitoring guide

**Effort:** 10h

### 7.4 Code Quality Improvements (20h)

**Tasks:**
```
1. mypy strict type checking (6h)
   - Run: mypy . --strict
   - Fix all errors
   - Zero mypy warnings

2. pylint code quality (6h)
   - Run: pylint main.py execution/ risk/ strategies/
   - Fix violations
   - Target: 9.0+ score

3. Code formatting (4h)
   - black formatter
   - isort imports
   - autopep8 style

4. Remove duplication (4h)
   - Identify duplicated code
   - Extract to utils
   - DRY principle
```

**Acceptance criteria:**
- Ô£à mypy: zero warnings with --strict
- Ô£à pylint: 9.0+ on critical modules
- Ô£à black: consistent formatting
- Ô£à No code duplication

**Effort:** 20h

### 7.5 Validation Phase 5

```bash
# Run after Phase 5:
cd c:\Users\averr\EDGECORE

# 1. Type checking
mypy . --strict
# Should show: Success: no issues found in 50 source files

# 2. Code quality
pylint main.py execution/ risk/ strategies/ --disable=all --enable=E,F
# Should show: 0 errors / 0 warnings

# 3. Code formatting
black . --check
isort . --check
# Should show: no changes needed

# 4. Documentation exists
ls docs/ARCHITECTURE.md docs/OPERATIONS.md
# Should exist

# 5. Final coverage
pytest tests/ --cov=. --cov-report=term | tail -3
# Should show >= 70% coverage
```

**Acceptance criteria:**
- Ô£à 10/10 score achieved
- Ô£à All documentation complete
- Ô£à Code quality maximal
- Ô£à 70%+ test coverage

---

## 8. H├®bergement & D├®ploiement (1 semaine)

**Objectif:** Production-ready deployment

### 8.1 Docker Containerization (10h)

**Fichier:** `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy source code
COPY . .

# Create logs/audit directories
RUN mkdir -p logs audit

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/dashboard', timeout=5)"

# Run
CMD ["python", "main.py", "--mode", "paper", "--symbols", "AAPL", "MSFT"]
```

**Fichier:** `docker-compose.yml`

```yaml
version: '3.9'

services:
  edgecore:
    build: .
    container_name: edgecore-trading
    environment:
      EDGECORE_ENV: prod
      broker_API_KEY: ${broker_API_KEY}
      broker_API_SECRET: ${broker_API_SECRET}
      SLACK_WEBHOOK_URL: ${SLACK_WEBHOOK_URL}
      LOG_LEVEL: INFO
    volumes:
      - ./logs:/app/logs
      - ./audit:/app/audit
    ports:
      - "8000:8000"  # Dashboard API
    restart: unless-stopped
```

### 8.2 Kubernetes Deployment (10h) [Optional]

**File:** `k8s/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: edgecore
spec:
  replicas: 1  # Only 1 trading system (avoid double-trading)
  selector:
    matchLabels:
      app: edgecore
  template:
    metadata:
      labels:
        app: edgecore
    spec:
      containers:
      - name: edgecore
        image: edgecore:latest
        env:
        - name: EDGECORE_ENV
          value: "prod"
        - name: broker_API_KEY
          valueFrom:
            secretKeyRef:
              name: edgecore-secrets
              key: api-key
        # ... etc
```

### 8.3 Monitoring Stack (15h) [Optional]

**Setup Prometheus + Grafana**

**Fichier:** `monitoring/prometheus.yml`

```yaml
global:
  scrape_interval: 15s

scrape_configs:
- job_name: 'edgecore'
  static_configs:
  - targets: ['localhost:8000']
```

### 8.4 Validation Deployement

```bash
# Build Docker image
docker build -t edgecore:latest .

# Run container
docker run -e EDGECORE_ENV=prod \
  -e broker_API_KEY=... \
  -e broker_API_SECRET=... \
  edgecore:latest

# Check logs
docker logs edgecore-trading

# Access dashboard
curl http://localhost:8000/api/dashboard
```

**Acceptance criteria:**
- Ô£à Docker image builds successfully
- Ô£à Container starts and runs trading loop
- Ô£à Logs visible via docker logs
- Ô£à Dashboard accessible on port 8000
- Ô£à Health check passing

**Effort:** 15h (Docker + monitoring basics)

---

## 9. Checklist de Production

### Final Pre-Production Validation

```
SECTION A: CODE QUALITY
[ ] mypy --strict: 0 errors, 0 warnings
[ ] pylint: 9.0+ on critical modules
[ ] black formatted
[ ] 70%+ test coverage
[ ] All tests passing
[ ] E2E tests passing
[ ] Chaos tests passing

SECTION B: RISK MANAGEMENT
[ ] Risk engine tests: 100% passing
[ ] Max risk per trade enforced
[ ] Max concurrent positions enforced
[ ] Daily loss kill-switch enforced
[ ] Consecutive loss limit enforced
[ ] Volatility regime check enforced
[ ] Order timeout (30s) enforced
[ ] Graceful shutdown tested (Ctrl+C)
[ ] Position persistence verified (crash recovery)

SECTION C: OPERATIONAL READINESS
[ ] All 4 error categories classified
[ ] Exponential backoff implemented
[ ] Circuit breaker active (5 failures ÔåÆ OPEN)
[ ] Data validation on all OHLCV loads
[ ] Audit trail writing to disk daily
[ ] Reconciliation running on startup
[ ] Slack alerts configured and tested
[ ] Email alerts configured and tested
[ ] Dashboard accessible and updating
[ ] Logs in JSONL format and queryable

SECTION D: SECURITY
[ ] API keys in .env (not in code)
[ ] .env not committed to git
[ ] SecretsVault integrated
[ ] Secrets masked in logs
[ ] API key rotation requirement enforced (30 days)
[ ] No hardcoded credentials anywhere
[ ] HTTPS for dashboard (if remote)

SECTION E: DOCUMENTATION
[ ] Architecture handbook (5000+ words) Ô£à
[ ] Operations manual (2000+ words) Ô£à
[ ] API reference generated Ô£à
[ ] Incident response playbook Ô£à
[ ] Deployment README Ô£à

SECTION F: DEPLOYMENT
[ ] Docker image built and tested
[ ] docker-compose.yml working
[ ] Kubernetes manifests ready (optional)
[ ] Backups configured (audit trail, config)
[ ] Logs rotated daily
[ ] Disk space monitoring

SECTION G: FINAL VALIDATION
[ ] Ran on IBKR testnet for >= 1 hour
[ ] >= 50 trades executed successfully
[ ] All risk constraints honored
[ ] No crashes or exceptions
[ ] Performance met targets (< 5s latency)
[ ] All alerts working (Slack, Email, Dashboard)

Sign-off:
Date: ___________
Engineer: ___________
Lead Review: ___________
```

---

## 10. Timeline & Effort Summary

| Phase | Duration | Effort | Score | Cumulative |
|-------|----------|--------|-------|-----------|
| **Phase 0: Hotfixes** | 2 days | 15h | 5 ÔåÆ 5.5 | 5.5 |
| **Phase 1: Capital Protection** | 2 weeks | 80h | 5.5 ÔåÆ 7 | 7 |
| **Phase 2: Robustness** | 3 weeks | 120h | 7 ÔåÆ 7.5 | 7.5 |
| **Phase 3: Observability** | 2 weeks | 100h | 7.5 ÔåÆ 8.5 | 8.5 |
| **Phase 4: Testing** | 3 weeks | 140h | 8.5 ÔåÆ 9.5 | 9.5 |
| **Phase 5: Excellence** | 2 weeks | 80h | 9.5 ÔåÆ 10 | **10** |
| **Phase 6: Deployment** | 1 week | 50h | 10 | 10 |
| **TOTAL** | **15 weeks** | **585h** | **5 ÔåÆ 10** | **Ô£à PRODUCTION READY** |

**Resources:**
- 1 Senior Python engineer (FTE, 15 weeks)
- OR 2 engineers (~7-8 weeks each)

**Milestones:**
- Week 2: Phase 0+1 complete (capital protection done)
- Week 5: Phase 2 complete (error handling robust)
- Week 7: Phase 3 complete (monitoring live)
- Week 10: Phase 4 complete (70%+ coverage)
- Week 12: Phase 5 complete (documentation, polish)
- Week 13-15: Deployment, testnet validation, final QA

---

## 11. Success Metrics

**System Score: 10/10 Ô£à**

**Key Achievements:**
- Ô£à Zero silent failures (all errors handled)
- Ô£à Position persistence (crash ÔåÆ recovery)
- Ô£à Global kill-switch (emergency control)
- Ô£à Order timeout enforcement (capital freed)
- Ô£à Real-time monitoring (Slack/Email/Dashboard)
- Ô£à 70%+ test coverage (confidence)
- Ô£à E2E validated (full flow proven)
- Ô£à Production deployment (Docker ready)

**Capital Safety Guarantee:**
> "In the event of any system failure, position state can be recovered from the audit trail, and all open orders are timeout-protected and will be force-closed. The system cannot lose capital due to bugs without explicit user action."

---

## Conclusion

This roadmap transforms EDGECORE from a proof-of-concept (5/10) to a **production-grade quantitative trading system (10/10)** capable of safely trading real capital.

**Key Principles:**
1. **Capital Preservation First** ÔÇö Every feature prioritizes money safety
2. **No Silent Failures** ÔÇö All errors surfaced immediately
3. **Operational Excellence** ÔÇö Monitoring, alerting, diagnostics built-in
4. **Tested Thoroughly** ÔÇö 70%+ coverage, E2E, chaos testing
5. **Maintainable Long-Term** ÔÇö Documentation, architecture, clean code

**Ready to execute? Let's build a system we can trust with real money.** ­ƒÆ¬
