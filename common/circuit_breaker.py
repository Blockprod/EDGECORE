"""
Circuit breaker pattern for preventing cascading failures.

Provides:
- Circuit breaker state machine (CLOSED → OPEN → HALF_OPEN → CLOSED)
- Automatic state transitions based on failures
- Detailed state logging and monitoring
- Per-endpoint circuit breakers
"""

from typing import Callable, TypeVar, Any, Optional, Dict, List
from enum import Enum
from datetime import datetime, timedelta, timezone
from structlog import get_logger
from dataclasses import dataclass, field
import threading

logger = get_logger(__name__)

T = TypeVar('T')


class CircuitBreakerState(Enum):
    """Circuit breaker state machine states."""
    CLOSED = "closed"           # Normal operation, requests pass through
    OPEN = "open"               # Too many failures, requests blocked
    HALF_OPEN = "half_open"     # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5      # Failures before opening
    timeout_seconds: int = 60       # How long to stay open
    success_threshold: int = 2      # Successes to close in half-open
    
    def __post_init__(self):
        """Validate configuration."""
        if self.failure_threshold < 1:
            raise ValueError(f"failure_threshold must be >= 1, got {self.failure_threshold}")
        if self.timeout_seconds < 1:
            raise ValueError(f"timeout_seconds must be >= 1, got {self.timeout_seconds}")
        if self.success_threshold < 1:
            raise ValueError(f"success_threshold must be >= 1, got {self.success_threshold}")


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open (service unavailable)."""
    pass


@dataclass
class CircuitBreakerMetrics:
    """Metrics for a circuit breaker."""
    state: CircuitBreakerState
    failure_count: int = 0
    success_count: int = 0
    total_calls: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_change_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitBreaker:
    """
    Circuit breaker implementation for resilient service calls.
    
    Prevents cascading failures by stopping calls to a failing service.
    States:
    - CLOSED: Normal operation
    - OPEN: Service is failing, block calls
    - HALF_OPEN: Test if service recovered
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker.
        
        Args:
            name: Identifier for this breaker (e.g., "ibkr_api")
            config: CircuitBreakerConfig (uses defaults if None)
        """
        if not name:
            raise ValueError("Circuit breaker name cannot be empty")
        
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        self.metrics = CircuitBreakerMetrics(state=CircuitBreakerState.CLOSED)
        self.lock = threading.RLock()
        
        logger.info(
            "circuit_breaker_initialized",
            name=name,
            failure_threshold=self.config.failure_threshold,
            timeout_seconds=self.config.timeout_seconds
        )
    
    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Function result
        
        Raises:
            CircuitBreakerOpen: If circuit is open
        """
        with self.lock:
            # Check if circuit should close due to timeout
            if self.metrics.state == CircuitBreakerState.OPEN:
                time_since_open = datetime.now(timezone.utc) - self.metrics.state_change_time
                if time_since_open.total_seconds() > self.config.timeout_seconds:
                    self._transition_to_half_open()
            
            # Block call if open
            if self.metrics.state == CircuitBreakerState.OPEN:
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Service unavailable (failed {self.metrics.consecutive_failures} times)"
                )
        
        # Execute the call
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self) -> None:
        """Record successful call."""
        with self.lock:
            self.metrics.success_count += 1
            self.metrics.total_calls += 1
            self.metrics.last_success_time = datetime.now(timezone.utc)
            self.metrics.consecutive_successes += 1
            self.metrics.consecutive_failures = 0
            
            # Close circuit if enough successes in half-open state
            if self.metrics.state == CircuitBreakerState.HALF_OPEN:
                if self.metrics.consecutive_successes >= self.config.success_threshold:
                    self._transition_to_closed()
            
            logger.debug(
                "circuit_breaker_success",
                name=self.name,
                state=self.metrics.state.value,
                consecutive_successes=self.metrics.consecutive_successes
            )
    
    def _on_failure(self) -> None:
        """Record failed call."""
        with self.lock:
            self.metrics.failure_count += 1
            self.metrics.total_calls += 1
            self.metrics.last_failure_time = datetime.now(timezone.utc)
            self.metrics.consecutive_failures += 1
            self.metrics.consecutive_successes = 0
            
            # In HALF_OPEN: any failure immediately re-opens the circuit
            if self.metrics.state == CircuitBreakerState.HALF_OPEN:
                self._transition_to_open()
            # Open circuit if threshold reached
            elif self.metrics.consecutive_failures >= self.config.failure_threshold:
                if self.metrics.state != CircuitBreakerState.OPEN:
                    self._transition_to_open()
            
            logger.warning(
                "circuit_breaker_failure",
                name=self.name,
                state=self.metrics.state.value,
                consecutive_failures=self.metrics.consecutive_failures,
                failure_threshold=self.config.failure_threshold
            )
    
    def _transition_to_open(self) -> None:
        """Transition circuit to OPEN state."""
        self.metrics.state = CircuitBreakerState.OPEN
        self.metrics.state_change_time = datetime.now(timezone.utc)
        self.metrics.consecutive_successes = 0
        
        logger.error(
            "circuit_breaker_opened",
            name=self.name,
            consecutive_failures=self.metrics.consecutive_failures
        )
    
    def _transition_to_half_open(self) -> None:
        """Transition circuit to HALF_OPEN state."""
        self.metrics.state = CircuitBreakerState.HALF_OPEN
        self.metrics.state_change_time = datetime.now(timezone.utc)
        self.metrics.consecutive_successes = 0
        self.metrics.consecutive_failures = 0
        
        logger.info(
            "circuit_breaker_half_open",
            name=self.name,
            timeout_elapsed_seconds=(
                datetime.now(timezone.utc) - self.metrics.state_change_time
            ).total_seconds()
        )
    
    def _transition_to_closed(self) -> None:
        """Transition circuit to CLOSED state."""
        self.metrics.state = CircuitBreakerState.CLOSED
        self.metrics.state_change_time = datetime.now(timezone.utc)
        self.metrics.failure_count = 0
        self.metrics.consecutive_failures = 0
        self.metrics.consecutive_successes = 0
        
        logger.info(
            "circuit_breaker_closed",
            name=self.name
        )
    
    def get_state(self) -> CircuitBreakerState:
        """Get current circuit state."""
        with self.lock:
            return self.metrics.state
    
    @property
    def state(self) -> CircuitBreakerState:
        """Property for accessing current state."""
        return self.get_state()
    
    @state.setter
    def state(self, value: CircuitBreakerState):
        """Property for setting current state directly (for testing)."""
        with self.lock:
            self.metrics.state = value
    
    @property
    def failure_count(self) -> int:
        """Property for accessing failure count."""
        with self.lock:
            return self.metrics.failure_count
    
    @property
    def success_count(self) -> int:
        """Property for accessing success count."""
        with self.lock:
            return self.metrics.success_count
    
    @success_count.setter
    def success_count(self, value: int):
        """Property for setting success count directly (for testing)."""
        with self.lock:
            self.metrics.success_count = value
    
    @property
    def opened_at(self) -> Optional[float]:
        """Property for accessing when circuit was opened (as timestamp)."""
        with self.lock:
            if self.metrics.state == CircuitBreakerState.OPEN:
                return self.metrics.state_change_time.timestamp()
            return None
    
    @opened_at.setter
    def opened_at(self, value: float):
        """Property for setting when circuit was opened (accepts timestamp)."""
        with self.lock:
            # Convert Unix timestamp to UTC datetime
            from datetime import timezone
            self.metrics.state_change_time = datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None)
    
    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get current metrics."""
        with self.lock:
            # Return a copy to avoid external modification
            import copy
            return copy.deepcopy(self.metrics)
    
    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        with self.lock:
            self.metrics = CircuitBreakerMetrics(state=CircuitBreakerState.CLOSED)
            logger.info("circuit_breaker_reset", name=self.name)


class CircuitBreakerRegistry:
    """
    Central registry for managing multiple circuit breakers.
    
    Allows per-endpoint circuit breaking (e.g., separate for each broker API endpoint)
    """
    
    def __init__(self):
        """Initialize registry."""
        self.breakers: Dict[str, CircuitBreaker] = {}
        self.lock = threading.RLock()
    
    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """
        Get or create a circuit breaker.
        
        Args:
            name: Unique identifier for the breaker
            config: Configuration (only used if creating new)
        
        Returns:
            CircuitBreaker instance
        """
        with self.lock:
            if name not in self.breakers:
                self.breakers[name] = CircuitBreaker(name, config)
            return self.breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get existing circuit breaker by name."""
        with self.lock:
            return self.breakers.get(name)
    
    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        with self.lock:
            for breaker in self.breakers.values():
                breaker.reset()
            logger.info("circuit_breaker_reset_all", count=len(self.breakers))
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get states of all breakers."""
        with self.lock:
            states = {}
            for name, breaker in self.breakers.items():
                metrics = breaker.get_metrics()
                states[name] = {
                    "state": metrics.state.value,
                    "failure_count": metrics.failure_count,
                    "success_count": metrics.success_count,
                    "total_calls": metrics.total_calls,
                    "consecutive_failures": metrics.consecutive_failures
                }
            return states


# Global registry instance
_global_registry = CircuitBreakerRegistry()


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """Get or create circuit breaker from global registry."""
    return _global_registry.get_or_create(name, config)


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers globally."""
    _global_registry.reset_all()
