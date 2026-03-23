"""
Unified error handling for EDGECORE trading system.

Provides:
- handle_error() function for consistent error logging/alerting
- @with_error_handling decorator for automatic retries with exponential backoff
- Strategy-specific error handling based on ErrorCategory
"""

import time
from functools import wraps
from typing import Any, Callable, TypeVar

from structlog import get_logger

from common.errors import ErrorCategory, TradingError, classify_exception

logger = get_logger(__name__)

# Type variable for decorated function return type
T = TypeVar("T")


def handle_error(error: Exception, context: str = "", alerter: Any | None = None) -> None:
    """
    Unified error handling with category-specific logging and alerting.

    Args:
        error: Exception to handle
        context: Human-readable context (e.g., "loading data for AAPL")
        alerter: Optional AlertManager or SlackAlerter for critical errors

    Behavior:
        - TRANSIENT: Log warning, will retry upstream
        - RETRYABLE: Log error, will retry with backoff upstream
        - NON_RETRYABLE: Log critical, create alert (operator action needed)
        - FATAL: Log critical, raise error (system must stop)
    """

    # Normalize to TradingError
    if isinstance(error, TradingError):
        category = error.category
        message = error.message
        original_error = error.original_error
    else:
        category = classify_exception(error)
        message = str(error)
        original_error = error

    # Log and alert based on category
    if category == ErrorCategory.TRANSIENT:
        logger.warning(
            "TRANSIENT_ERROR",
            context=context,
            message=message,
            original_error=str(original_error) if original_error else None,
        )
        # Will be retried upstream (loop continues or decorator retries)

    elif category == ErrorCategory.RETRYABLE:
        logger.error(
            "RETRYABLE_ERROR",
            context=context,
            message=message,
            original_error=str(original_error) if original_error else None,
        )
        # Will be retried upstream with exponential backoff

    elif category == ErrorCategory.NON_RETRYABLE:
        logger.critical(
            "NON_RETRYABLE_ERROR",
            context=context,
            message=message,
            original_error=str(original_error) if original_error else None,
        )
        # Operator action required - try both AlertManager and SlackAlerter
        if alerter:
            try:
                # Check if it's a SlackAlerter (has send_alert method)
                if hasattr(alerter, "send_alert"):
                    alerter.send_alert(
                        level="ERROR",
                        title=f"Non-retryable error: {context}",
                        message=message,
                        data={"code": error.__class__.__name__},
                    )
                # Otherwise assume AlertManager interface
                elif hasattr(alerter, "create_alert"):
                    alerter.create_alert(
                        severity="critical", category="system", title=f"Non-retryable error: {context}", message=message
                    )
            except Exception as alert_error:
                logger.error("alert_creation_failed", error=str(alert_error))

    elif category == ErrorCategory.FATAL:
        logger.critical(
            "FATAL_ERROR",
            context=context,
            message=message,
            original_error=str(original_error) if original_error else None,
        )
        # System must stop - re-raise
        if isinstance(error, TradingError):
            raise error
        else:
            raise TradingError(message, ErrorCategory.FATAL, error)


def with_error_handling(
    category: ErrorCategory = ErrorCategory.RETRYABLE,
    max_retries: int = 3,
    backoff_base: float = 2.0,
    context_prefix: str = "",
    alerter: Any | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for automatic error handling and retries.

    Catches exceptions, logs them with category, and automatically retries
    transient/retryable errors with exponential backoff.

    Args:
        category: Default ErrorCategory if exception doesn't specify one
        max_retries: Maximum number of retry attempts
        backoff_base: Base for exponential backoff (2^attempt * backoff_base seconds)
        context_prefix: Prefix for error context messages
        alerter: Optional alerter (EmailAlerter/SlackAlerter) for sending
                 alerts on non-retryable/fatal errors or max retries exceeded

    Returns:
        Decorated function that handles errors automatically

    Example:
        @with_error_handling(category=ErrorCategory.TRANSIENT, max_retries=5)
        def load_data(symbol: str) -> pd.DataFrame:
            return loader.load(symbol)

    Behavior:
        - TRANSIENT/RETRYABLE errors: Retry with exponential backoff
        - NON_RETRYABLE errors: Raise immediately (no retry)
        - FATAL errors: Raise immediately (system will crash)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    # Build context string
                    context = f"{context_prefix}{func.__name__}"
                    if args:
                        context += f"(args={args[:2]})"  # Log first 2 args

                    # Determine error category
                    if isinstance(e, TradingError):
                        error_category = e.category
                    else:
                        classified = classify_exception(e)
                        # `category` is the decorator-level default; prefer it when
                        # classify_exception falls back to its own generic RETRYABLE default.
                        error_category = classified if classified != ErrorCategory.RETRYABLE else category

                    # Log the error (and alert if non-retryable/fatal)
                    handle_error(e, context=context, alerter=alerter)

                    # Decision: retry or raise?
                    if error_category in [ErrorCategory.TRANSIENT, ErrorCategory.RETRYABLE]:
                        if attempt < max_retries - 1:
                            # Calculate backoff
                            backoff_seconds = backoff_base**attempt
                            logger.info(
                                "RETRY_AFTER_BACKOFF",
                                function=func.__name__,
                                attempt=attempt + 1,
                                max_retries=max_retries,
                                backoff_seconds=backoff_seconds,
                            )
                            time.sleep(backoff_seconds)
                            continue
                        else:
                            logger.critical("MAX_RETRIES_EXCEEDED", function=func.__name__, max_retries=max_retries)
                            # Alert on max retries exhausted
                            if alerter and hasattr(alerter, "send_alert"):
                                try:
                                    alerter.send_alert(
                                        level="ERROR",
                                        title=f"Max retries exceeded: {func.__name__}",
                                        message=f"{context}: {e}",
                                        data={"max_retries": max_retries, "error": str(e)[:200]},
                                    )
                                except Exception:
                                    pass

                    # Don't retry: re-raise the error
                    raise

            # Should never reach here (last iteration always raises)
            raise TradingError(f"{func.__name__} failed after {max_retries} attempts", ErrorCategory.NON_RETRYABLE)

        return wrapper

    return decorator
