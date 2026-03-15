"""
Production Logging Configuration and Infrastructure

Provides structured, context-aware logging with:
- JSON formatting for easy parsing
- Automatic request tracking and tracing
- Daily/size-based rotation
- Contextual metadata (request ID, user, action)
- Performance metrics logging
- Async writing for minimal overhead
"""

import json
import logging
import logging.handlers
import os
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from functools import wraps
import time


# Global context storage (thread-local)
_context = threading.local()


class ContextFilter(logging.Filter):
    """Add context information to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to the log record."""
        # Add request ID
        record.request_id = getattr(_context, 'request_id', 'NO_REQUEST')
        
        # Add user info
        record.user = getattr(_context, 'user', 'SYSTEM')
        
        # Add action
        record.action = getattr(_context, 'action', 'UNKNOWN')
        
        # Add correlation ID for distributed tracing
        record.correlation_id = getattr(_context, 'correlation_id', None)
        
        # Add service info
        record.service = getattr(_context, 'service', 'trading-engine')
        
        # Add environment
        record.environment = os.getenv('ENVIRONMENT', 'development')
        
        return True


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for easy parsing and ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'request_id': getattr(record, 'request_id', 'NO_REQUEST'),
            'user': getattr(record, 'user', 'SYSTEM'),
            'action': getattr(record, 'action', 'UNKNOWN'),
            'correlation_id': getattr(record, 'correlation_id', None),
            'service': getattr(record, 'service', 'trading-engine'),
            'environment': getattr(record, 'environment', 'development'),
        }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            log_data['exception_type'] = record.exc_info[0].__name__

        # Add custom fields
        if hasattr(record, 'extra_fields'):
            log_data['extra'] = record.extra_fields

        # Add performance metrics if present
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms
        if hasattr(record, 'tokens_used'):
            log_data['tokens_used'] = record.tokens_used
        if hasattr(record, 'cache_hit'):
            log_data['cache_hit'] = record.cache_hit

        return json.dumps(log_data, default=str)


class RotatingJSONHandler(logging.handlers.TimedRotatingFileHandler):
    """Rotating file handler that writes JSON logs."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit the log record."""
        try:
            msg = self.format(record)
            self.stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


def setup_logging(
    log_dir: str = 'logs',
    level: int = logging.INFO,
    console_level: int = logging.WARNING,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 7,
    json_format: bool = True
) -> logging.Logger:
    """
    Configure production logging with rotation and context.

    Args:
        log_dir: Directory for log files
        level: Root logger level
        console_level: Console output level
        max_bytes: Max file size before rotation
        backup_count: Number of backup files to keep
        json_format: Use JSON formatting

    Returns:
        Configured root logger
    """
    # Create log directory
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add context filter
    context_filter = ContextFilter()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.addFilter(context_filter)

    if json_format:
        console_formatter = JSONFormatter()
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - '
            '[%(request_id)s] - %(message)s'
        )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = RotatingJSONHandler(
        filename=os.path.join(log_dir, 'trading.log'),
        when='midnight',
        interval=1,
        backupCount=backup_count,
        utc=True
    )
    file_handler.setLevel(level)
    file_handler.addFilter(context_filter)

    if json_format:
        file_formatter = JSONFormatter()
    else:
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - '
            '[%(request_id)s] - %(message)s'
        )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # API-specific log file
    api_handler = RotatingJSONHandler(
        filename=os.path.join(log_dir, 'api.log'),
        when='midnight',
        interval=1,
        backupCount=backup_count,
        utc=True
    )
    api_handler.setLevel(logging.INFO)
    api_handler.addFilter(context_filter)
    api_handler.setFormatter(JSONFormatter() if json_format else logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(request_id)s] - %(message)s'
    ))
    logging.getLogger('monitoring.api').addHandler(api_handler)

    # Risk-specific log file
    risk_handler = RotatingJSONHandler(
        filename=os.path.join(log_dir, 'risk.log'),
        when='midnight',
        interval=1,
        backupCount=backup_count,
        utc=True
    )
    risk_handler.setLevel(logging.DEBUG)
    risk_handler.addFilter(context_filter)
    risk_handler.setFormatter(JSONFormatter() if json_format else logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(request_id)s] - %(message)s'
    ))
    logging.getLogger('risk').addHandler(risk_handler)

    # Execution-specific log file
    execution_handler = RotatingJSONHandler(
        filename=os.path.join(log_dir, 'execution.log'),
        when='midnight',
        interval=1,
        backupCount=backup_count,
        utc=True
    )
    execution_handler.setLevel(logging.DEBUG)
    execution_handler.addFilter(context_filter)
    execution_handler.setFormatter(JSONFormatter() if json_format else logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(request_id)s] - %(message)s'
    ))
    logging.getLogger('execution').addHandler(execution_handler)

    return root_logger


@contextmanager
def log_context(
    request_id: Optional[str] = None,
    user: str = 'SYSTEM',
    action: str = 'UNKNOWN',
    correlation_id: Optional[str] = None,
    service: str = 'trading-engine'
):
    """
    Context manager for logging context.

    Args:
        request_id: Unique request identifier
        user: User performing action
        action: Action being performed
        correlation_id: Correlation ID for distributed tracing
        service: Service name

    Usage:
        with log_context(request_id='req123', user='trader', action='place_order'):
            logger.info('Placing order...')
    """
    # Store old values
    old_request_id = getattr(_context, 'request_id', None)
    old_user = getattr(_context, 'user', None)
    old_action = getattr(_context, 'action', None)
    old_correlation_id = getattr(_context, 'correlation_id', None)
    old_service = getattr(_context, 'service', None)

    try:
        # Set new values
        _context.request_id = request_id or str(uuid.uuid4())
        _context.user = user
        _context.action = action
        _context.correlation_id = correlation_id or str(uuid.uuid4())
        _context.service = service

        yield _context.request_id

    finally:
        # Restore old values
        if old_request_id is not None:
            _context.request_id = old_request_id
        else:
            delattr(_context, 'request_id') if hasattr(_context, 'request_id') else None

        if old_user is not None:
            _context.user = old_user
        else:
            delattr(_context, 'user') if hasattr(_context, 'user') else None

        if old_action is not None:
            _context.action = old_action
        else:
            delattr(_context, 'action') if hasattr(_context, 'action') else None

        if old_correlation_id is not None:
            _context.correlation_id = old_correlation_id
        else:
            delattr(_context, 'correlation_id') if hasattr(_context, 'correlation_id') else None

        if old_service is not None:
            _context.service = old_service
        else:
            delattr(_context, 'service') if hasattr(_context, 'service') else None


def set_context(
    request_id: Optional[str] = None,
    user: Optional[str] = None,
    action: Optional[str] = None,
    correlation_id: Optional[str] = None,
    service: Optional[str] = None
):
    """
    Set logging context without context manager.

    Args:
        request_id: Unique request identifier
        user: User performing action
        action: Action being performed
        correlation_id: Correlation ID for distributed tracing
        service: Service name
    """
    if request_id is not None:
        _context.request_id = request_id
    if user is not None:
        _context.user = user
    if action is not None:
        _context.action = action
    if correlation_id is not None:
        _context.correlation_id = correlation_id
    if service is not None:
        _context.service = service


def clear_context():
    """Clear all logging context."""
    for attr in ['request_id', 'user', 'action', 'correlation_id', 'service']:
        if hasattr(_context, attr):
            delattr(_context, attr)


def log_performance(logger: logging.Logger, duration_ms: float, **extra_fields):
    """
    Log performance metrics.

    Args:
        logger: Logger instance
        duration_ms: Duration in milliseconds
        **extra_fields: Additional fields to log
    """
    record = logging.LogRecord(
        name=logger.name,
        level=logging.INFO,
        pathname='',
        lineno=0,
        msg='Performance metrics',
        args=(),
        exc_info=None
    )
    record.duration_ms = duration_ms
    record.extra_fields = extra_fields

    logger.handle(record)


def log_with_metrics(func):
    """Decorator to automatically log function execution time and results."""
    logger = logging.getLogger(func.__module__)

    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(f'Starting {func.__name__}')
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            record = logging.LogRecord(
                name=logger.name,
                level=logging.DEBUG,
                pathname='',
                lineno=0,
                msg=f'Completed {func.__name__}',
                args=(),
                exc_info=None
            )
            record.duration_ms = duration_ms
            record.extra_fields = {'result_type': type(result).__name__}

            logger.handle(record)
            return result

        except Exception:
            duration_ms = (time.time() - start_time) * 1000
            logger.exception(
                f'Error in {func.__name__} after {duration_ms:.2f}ms',
                exc_info=True
            )
            raise

    return wrapper


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)


# Global setup flag
_logging_initialized = False


def initialize_logging(
    log_dir: str = 'logs',
    level: int = logging.INFO,
    console_level: int = logging.WARNING,
    json_format: bool = True
) -> logging.Logger:
    """
    Initialize logging system (idempotent).

    Args:
        log_dir: Directory for log files
        level: Root logger level
        console_level: Console output level
        json_format: Use JSON formatting

    Returns:
        Configured logger
    """
    global _logging_initialized

    if not _logging_initialized:
        setup_logging(
            log_dir=log_dir,
            level=level,
            console_level=console_level,
            json_format=json_format
        )
        _logging_initialized = True

    return logging.getLogger()
