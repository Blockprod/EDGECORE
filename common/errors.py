"""
Error taxonomy and custom exceptions for EDGECORE trading system.

Provides:
- ErrorCategory enum for classification
- TradingError base exception
- Specialized error types (DataError, BrokerError, StrategyError)
- Exception classifier for external library errors
"""

from enum import Enum
from typing import Optional
import ccxt


class ErrorCategory(Enum):
    """Classification of errors for handling strategy."""
    
    TRANSIENT = "transient"              # Temporary (network, timeout) → Retry immediately
    RETRYABLE = "retryable"              # May resolve with backoff (API throttle) → Exponential backoff
    NON_RETRYABLE = "non_retryable"      # Operator action required (insufficient balance) → Alert + stop
    FATAL = "fatal"                      # System must stop (logic error) → Crash


class TradingError(Exception):
    """
    Base exception for all trading-related errors.
    
    Attributes:
        message: Human-readable error description
        category: ErrorCategory for handling strategy
        original_error: Original exception that caused this error (if any)
    """
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        original_error: Optional[Exception] = None
    ):
        self.message = message
        self.category = category
        self.original_error = original_error
        super().__init__(message)


class DataError(TradingError):
    """
    Error loading or validating market data.
    
    Category: TRANSIENT (network issue) or RETRYABLE (format issue)
    """
    
    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        category: ErrorCategory = ErrorCategory.TRANSIENT
    ):
        super().__init__(message, category, original_error)


class DataValidationError(DataError):
    """Data validation failed (e.g., missing candles, invalid OHLCV)."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, original_error, ErrorCategory.TRANSIENT)


class BrokerError(TradingError):
    """Error communicating with broker API."""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.RETRYABLE,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message, category, original_error)


class BrokerConnectionError(BrokerError):
    """Cannot connect to broker (network issue)."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.TRANSIENT, original_error)


class InsufficientBalanceError(BrokerError):
    """Account has insufficient balance for trade."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.NON_RETRYABLE, original_error)


class StrategyError(TradingError):
    """Error in strategy logic (signal generation, signal validation)."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.FATAL, original_error)


class ConfigError(TradingError):
    """Configuration error (invalid settings, missing env var)."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.FATAL, original_error)


def classify_exception(exc: Exception) -> ErrorCategory:
    """
    Classify an exception from external library for handling.
    
    Args:
        exc: Exception to classify
    
    Returns:
        ErrorCategory indicating how to handle the error
    
    Examples:
        - TimeoutError → TRANSIENT (retry immediately)
        - ccxt.InsufficientBalance → NON_RETRYABLE (alert operator)
        - KeyError (missing field in data) → FATAL (logic error)
    """
    
    # Network/temporary errors
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return ErrorCategory.TRANSIENT
    
    # CCXT-specific errors
    if isinstance(exc, ccxt.NetworkError):
        return ErrorCategory.TRANSIENT
    
    if isinstance(exc, ccxt.ExchangeNotAvailable):
        return ErrorCategory.TRANSIENT  # Exchange temporarily down
    
    if isinstance(exc, ccxt.DDoSProtection):
        return ErrorCategory.RETRYABLE  # Exchange rate-limiting, retry with backoff
    
    if isinstance(exc, (ccxt.InsufficientFunds, ccxt.InsufficientBalance if hasattr(ccxt, 'InsufficientBalance') else type(None))):
        return ErrorCategory.NON_RETRYABLE  # Account lacks funds, operator action needed
    
    if isinstance(exc, (ccxt.InvalidOrder, ccxt.OrderNotFound)):
        return ErrorCategory.NON_RETRYABLE  # Order validation or matching issue
    
    # Data errors (logic)
    if isinstance(exc, (KeyError, ValueError, TypeError)):
        return ErrorCategory.FATAL  # Programming error, must stop
    
    # Default: assume retryable but log warning
    return ErrorCategory.RETRYABLE
