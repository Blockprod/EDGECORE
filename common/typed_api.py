"""
Type-annotated wrapper functions for production APIs.

Provides fully typed interfaces to all public APIs.
"""

from typing import Dict, Optional, Any, Tuple, Callable
from common.types import (
    AlertRecord, ValidationResult, RiskCheckResult,
    Price, Quantity, Symbol, OrderID,
    OrderSide, OrderType
)
from dataclasses import dataclass
import pandas as pd


# ============================================================================
# RETRY POLICY API TYPES
# ============================================================================

@dataclass
class TypedRetryPolicy:
    """Typed retry policy configuration."""
    max_attempts: int
    initial_delay_seconds: float
    max_delay_seconds: float
    exponential_base: float
    jitter_factor: float


def retry_with_backoff_typed(
    func: Callable[..., Any],
    policy: TypedRetryPolicy,
    *args: Any,
    **kwargs: Any
) -> Any:
    """
    Execute function with typed retry policy.
    
    Args:
        func: Function to retry
        policy: Retry policy configuration
        *args: Function positional arguments
        **kwargs: Function keyword arguments
    
    Returns:
        Function result
    """
    from common.retry import retry_with_backoff, RetryPolicy
    
    real_policy = RetryPolicy(
        max_attempts=policy.max_attempts,
        initial_delay_seconds=policy.initial_delay_seconds,
        max_delay_seconds=policy.max_delay_seconds,
        exponential_base=policy.exponential_base,
        jitter_factor=policy.jitter_factor
    )
    
    @retry_with_backoff(policy=real_policy)
    def wrapped(*a, **kw):
        return func(*a, **kw)
    
    return wrapped(*args, **kwargs)


# ============================================================================
# CIRCUIT BREAKER API TYPES
# ============================================================================

@dataclass
class TypedCircuitBreakerConfig:
    """Typed circuit breaker configuration."""
    failure_threshold: int
    timeout_seconds: float
    success_threshold: int
    name: str = "default"


def get_typed_circuit_breaker(
    name: str,
    config: Optional[TypedCircuitBreakerConfig] = None
) -> 'TypedCircuitBreaker':
    """
    Get or create a typed circuit breaker.
    
    Args:
        name: Breaker identifier
        config: Optional configuration
    
    Returns:
        Typed circuit breaker instance
    """
    from common.circuit_breaker import get_circuit_breaker, CircuitBreakerConfig
    
    if config:
        cb_config = CircuitBreakerConfig(
            failure_threshold=config.failure_threshold,
            timeout_seconds=config.timeout_seconds,
            success_threshold=config.success_threshold
        )
    else:
        cb_config = None
    
    breaker = get_circuit_breaker(name, cb_config)
    return TypedCircuitBreaker(breaker)


class TypedCircuitBreaker:
    """Typed wrapper for circuit breaker."""
    
    def __init__(self, breaker):
        self._breaker = breaker
    
    def call(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Function result or raises exception if open
        """
        return self._breaker.call(func, *args, **kwargs)
    
    def get_state(self) -> str:
        """Get current breaker state."""
        return self._breaker.get_state().value


# ============================================================================
# EXECUTION TYPES
# ============================================================================

def submit_order_typed(
    symbol: Symbol,
    side: OrderSide,
    quantity: Quantity,
    order_type: OrderType,
    price: Optional[Price] = None,
    timeout_seconds: float = 30.0,
    metadata: Optional[Dict[str, Any]] = None
) -> OrderID:
    """
    Submit a typed order.
    
    Args:
        symbol: Trading pair
        side: Order side (buy/sell)
        quantity: Order quantity
        order_type: Market or limit
        price: Limit price (if limit order)
        timeout_seconds: Order timeout
        metadata: Additional order data
    
    Returns:
        Order ID
    """
    from execution.modes import ExecutionEngine, ModeType
    
    engine = ExecutionEngine(mode=ModeType.PAPER)
    return engine.submit_order(
        symbol=symbol,
        side=side.value,
        quantity=quantity,
        order_type=order_type.value,
        price=price,
        timeout_seconds=timeout_seconds
    )


def open_position_typed(
    symbol: Symbol,
    quantity: Quantity,
    entry_price: Price,
    side: str = "long"
) -> bool:
    """
    Open a typed position.
    
    Args:
        symbol: Trading pair
        quantity: Position quantity
        entry_price: Entry price
        side: Long or short
    
    Returns:
        Success indicator
    """
    from execution.modes import ExecutionEngine, ModeType
    
    engine = ExecutionEngine(mode=ModeType.PAPER)
    return engine.open_position(
        symbol=symbol,
        quantity=quantity,
        entry_price=entry_price
    )


def close_position_typed(
    symbol: Symbol,
    exit_price: Price
) -> Tuple[bool, Optional[float]]:
    """
    Close a typed position.
    
    Args:
        symbol: Trading pair
        exit_price: Exit price
    
    Returns:
        (success, realized_pnl)
    """
    from execution.modes import ExecutionEngine, ModeType
    
    engine = ExecutionEngine(mode=ModeType.PAPER)
    return engine.close_position(symbol=symbol, exit_price=exit_price)


# ============================================================================
# VALIDATION API TYPES
# ============================================================================

def validate_ohlcv_typed(
    data: pd.DataFrame,
    symbol: Symbol = "UNKNOWN"
) -> ValidationResult:
    """
    Validate OHLCV data with types.
    
    Args:
        data: OHLCV DataFrame
        symbol: Trading pair
    
    Returns:
        Validation result
    """
    from data.validators import OHLCVValidator
    
    validator = OHLCVValidator(symbol=symbol)
    result = validator.validate(data)
    
    return ValidationResult(
        is_valid=result.is_valid,
        checks_passed=result.checks_passed,
        checks_failed=result.checks_failed,
        errors=result.errors,
        warnings=result.warnings
    )


# ============================================================================
# RISK ENGINE API TYPES
# ============================================================================

def check_risk_typed(
    symbol_pair: Symbol,
    position_size: Quantity,
    current_equity: float,
    volatility: float
) -> RiskCheckResult:
    """
    Check risk with types.
    
    Args:
        symbol_pair: Trading pair
        position_size: Quantity to trade
        current_equity ÔÇï: Portfolio equity
        volatility: Current volatility
    
    Returns:
        Risk check result
    """
    from risk.engine import RiskEngine
    
    engine = RiskEngine(initial_equity=current_equity)
    allowed, reason = engine.can_enter_trade(
        symbol_pair=symbol_pair,
        position_size=position_size,
        current_equity=current_equity,
        volatility=volatility
    )
    
    return RiskCheckResult(
        allowed=allowed,
        reason=reason
    )


# ============================================================================
# MONITORING API TYPES
# ============================================================================

def create_alert_typed(
    severity: str,
    category: str,
    title: str,
    message: str,
    data: Optional[Dict[str, Any]] = None
) -> AlertRecord:
    """
    Create a typed alert.
    
    Args:
        severity: Alert severity level
        category: Alert category
        title: Alert title
        message: Alert message
        data: Metadata
    
    Returns:
        Alert record
    """
    from monitoring.alerter import AlertManager, AlertSeverity
    
    manager = AlertManager()
    alert = manager.create_alert(
        severity=AlertSeverity(severity),
        category=category,
        title=title,
        message=message,
        data=data or {}
    )
    
    return AlertRecord(
        alert_id=alert.alert_id,
        severity=alert.severity,
        category=alert.category.value,
        title=alert.title,
        message=alert.message,
        timestamp=alert.timestamp,
        acknowledged=alert.is_acknowledged(),
        resolved=alert.is_resolved(),
        data=alert.data
    )


# ============================================================================
# SECRETS API TYPES
# ============================================================================

def store_secret_typed(
    name: str,
    value: str,
    rotation_interval_days: int = 30
) -> None:
    """
    Store a typed secret.
    
    Args:
        name: Secret name
        value: Secret value
        rotation_interval_days: Rotation interval
    """
    from common.secrets import get_vault
    
    vault = get_vault()
    vault.store_secret(
        name=name,
        value=value,
        rotation_interval_days=rotation_interval_days
    )


def get_secret_typed(name: str) -> Optional[str]:
    """
    Retrieve a typed secret.
    
    Args:
        name: Secret name
    
    Returns:
        Secret value or None
    """
    from common.secrets import get_vault
    
    vault = get_vault()
    return vault.get_secret(name)


if __name__ == "__main__":
    print("Ô£à Type-annotated API wrappers loaded")
    print("- Retry policy types")
    print("- Circuit breaker types")
    print("- Execution types")
    print("- Validation types")
    print("- Risk engine types")
    print("- Monitoring types")
    print("- Secrets types")
