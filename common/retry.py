"""
Retry logic with exponential backoff for resilient error handling.

Provides:
- Configurable retry policies
- Exponential backoff delay
- Jitter to prevent thundering herd
- Decorator-based retry for easy integration
- Detailed retry logging
"""

from typing import Callable, TypeVar, Any, Optional, Type, Tuple
from functools import wraps
import time
import math
from structlog import get_logger
from dataclasses import dataclass

logger = get_logger(__name__)

T = TypeVar('T')


class RetryException(Exception):
    """Raised when retry attempts are exhausted."""
    pass


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0
    jitter_factor: float = 0.1  # Add random jitter to avoid thundering herd
    
    # Only retry on these exception types
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        IOError,
        OSError,
    )
    
    def __post_init__(self):
        """Validate policy configuration."""
        if self.max_attempts < 1:
            raise ValueError(f"max_attempts must be >= 1, got {self.max_attempts}")
        if self.initial_delay_seconds < 0:
            raise ValueError(f"initial_delay_seconds must be >= 0, got {self.initial_delay_seconds}")
        if self.max_delay_seconds < self.initial_delay_seconds:
            raise ValueError(
                f"max_delay_seconds ({self.max_delay_seconds}) must be >= "
                f"initial_delay_seconds ({self.initial_delay_seconds})"
            )
        if not (0 <= self.jitter_factor <= 1):
            raise ValueError(f"jitter_factor must be 0-1, got {self.jitter_factor}")
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number.
        
        Args:
            attempt: Attempt number (0-indexed)
        
        Returns:
            Delay in seconds
        """
        if attempt < 0:
            raise ValueError(f"attempt must be >= 0, got {attempt}")
        
        # Exponential backoff: initial_delay * (base ^ attempt)
        delay = self.initial_delay_seconds * math.pow(self.exponential_base, attempt)
        
        # Cap at max delay
        delay = min(delay, self.max_delay_seconds)
        
        # Add jitter (random factor between 0 and jitter_factor * delay)
        import random
        jitter = random.uniform(0, self.jitter_factor * delay)
        delay = delay + jitter
        
        return delay


def retry_with_backoff(
    policy: Optional[RetryPolicy] = None,
    on_retry: Optional[Callable] = None
) -> Callable:
    """
    Decorator for automatic retry with exponential backoff.
    
    Args:
        policy: RetryPolicy configuration (uses defaults if None)
        on_retry: Optional callback(attempt, exception, delay) called on each retry
    
    Returns:
        Decorated function that retries on failure
    
    Example:
        @retry_with_backoff(RetryPolicy(max_attempts=5))
        def api_call():
            response = requests.get(...)
            return response
    """
    if policy is None:
        policy = RetryPolicy()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            
            for attempt in range(policy.max_attempts):
                try:
                    result = func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(
                            "retry_succeeded",
                            func_name=func.__name__,
                            attempt=attempt,
                            attempts_total=policy.max_attempts
                        )
                    
                    return result
                
                except Exception as e:
                    
                    # Check if exception is retryable
                    if not isinstance(e, policy.retryable_exceptions):
                        logger.error(
                            "retry_fatal_exception",
                            func_name=func.__name__,
                            exception=type(e).__name__,
                            message=str(e),
                            attempt=attempt
                        )
                        raise
                    
                    # Check if we have remaining attempts
                    if attempt >= policy.max_attempts - 1:
                        logger.error(
                            "retry_exhausted",
                            func_name=func.__name__,
                            max_attempts=policy.max_attempts,
                            last_exception=type(e).__name__
                        )
                        raise RetryException(
                            f"Retry exhausted after {policy.max_attempts} attempts: {str(e)}"
                        ) from e
                    
                    # Calculate and apply delay
                    delay = policy.calculate_delay(attempt)
                    
                    logger.warning(
                        "retry_scheduled",
                        func_name=func.__name__,
                        attempt=attempt,
                        max_attempts=policy.max_attempts,
                        delay_seconds=delay,
                        exception=type(e).__name__,
                        message=str(e)
                    )
                    
                    # Call on_retry callback if provided
                    if on_retry:
                        try:
                            on_retry(attempt, e, delay)
                        except Exception as cb_error:
                            logger.error("on_retry_callback_error", error=str(cb_error))
                    
                    # Wait before retry
                    time.sleep(delay)
            
            # Should never reach here
            raise RetryException(f"Unexpected exit from retry loop for {func.__name__}")
        
        return wrapper
    
    return decorator


class RetryStats:
    """Track retry statistics for monitoring."""
    
    def __init__(self):
        """Initialize stats tracker."""
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.total_retries = 0
        self.total_retry_time_seconds = 0.0
        self.by_function: dict = {}
    
    def record_call(self, func_name: str, success: bool, retries: int = 0, time_seconds: float = 0.0):
        """Record statistics for a function call."""
        self.total_calls += 1
        
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        
        self.total_retries += retries
        self.total_retry_time_seconds += time_seconds
        
        if func_name not in self.by_function:
            self.by_function[func_name] = {
                "calls": 0,
                "successful": 0,
                "failed": 0,
                "total_retries": 0
            }
        
        self.by_function[func_name]["calls"] += 1
        if success:
            self.by_function[func_name]["successful"] += 1
        else:
            self.by_function[func_name]["failed"] += 1
        self.by_function[func_name]["total_retries"] += retries
    
    def get_stats(self) -> dict:
        """Get statistics summary."""
        success_rate = 0.0
        if self.total_calls > 0:
            success_rate = (self.successful_calls / self.total_calls) * 100
        
        avg_retry_time = 0.0
        if self.total_retries > 0:
            avg_retry_time = self.total_retry_time_seconds / self.total_retries
        
        return {
            "total_calls": self.total_calls,
            "successful": self.successful_calls,
            "failed": self.failed_calls,
            "success_rate_pct": success_rate,
            "total_retries": self.total_retries,
            "avg_retry_time_seconds": avg_retry_time,
            "by_function": self.by_function
        }
