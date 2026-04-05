"""
Tests for Production Logging Configuration and Infrastructure

Tests core logging functionality:
- Context management (request ID, user, action)
- JSON formatting with structured data
- Performance metrics logging
- Decorator-based automatic logging
- Context isolation in multi-threaded scenarios
"""

# pyright: reportAttributeAccessIssue=false

import json
import logging
import threading
import time

import pytest

from monitoring.logging_config import (
    ContextFilter,
    JSONFormatter,
    clear_context,
    get_logger,
    log_context,
    log_performance,
    log_with_metrics,
    set_context,
)


class TestLoggerFunctionality:
    """Test basic logger functionality."""

    def test_get_logger(self):
        """Test getting a named logger."""
        logger = get_logger("test.module")
        assert logger is not None
        assert logger.name == "test.module"

    def test_logger_levels(self):
        """Test logger supports all standard levels."""
        logger = get_logger("test")

        # Just verify the methods exist and are callable
        assert callable(logger.debug)
        assert callable(logger.info)
        assert callable(logger.warning)
        assert callable(logger.error)
        assert callable(logger.critical)

    def test_logger_exception_method(self):
        """Test logger.exception() method."""
        logger = get_logger("test")

        try:
            raise ValueError("Test error")
        except ValueError:
            # Should not raise
            logger.exception("An error occurred")


class TestContextManagement:
    """Test logging context management."""

    def teardown_method(self):
        """Cleanup after each test."""
        clear_context()

    def test_log_context_sets_values(self):
        """Test that log_context sets context values."""
        clear_context()

        with log_context(request_id="req123", user="trader", action="place_order"):
            from monitoring.logging_config import _context

            assert _context.request_id == "req123"
            assert _context.user == "trader"
            assert _context.action == "place_order"

        clear_context()

    def test_log_context_clears_values(self):
        """Test that log_context clears values on exit."""
        clear_context()

        with log_context(request_id="req123"):
            pass

        from monitoring.logging_config import _context

        assert not hasattr(_context, "request_id")

        clear_context()

    def test_log_context_generates_request_id(self):
        """Test that log_context generates request_id if not provided."""
        clear_context()

        with log_context() as request_id:
            assert request_id is not None
            assert len(request_id) > 0

        clear_context()

    def test_log_context_nesting(self):
        """Test nested log contexts."""
        clear_context()

        with log_context(request_id="outer", user="user1"):
            from monitoring.logging_config import _context

            assert _context.request_id == "outer"
            assert _context.user == "user1"

            with log_context(request_id="inner", user="user2"):
                assert _context.request_id == "inner"
                assert _context.user == "user2"

            assert _context.request_id == "outer"
            assert _context.user == "user1"

        clear_context()

    def test_set_context(self):
        """Test setting context without context manager."""
        clear_context()

        set_context(request_id="req456", user="admin")

        from monitoring.logging_config import _context

        assert _context.request_id == "req456"
        assert _context.user == "admin"

        clear_context()

    def test_set_context_partial(self):
        """Test setting only some context values."""
        clear_context()

        set_context(request_id="req789")
        set_context(user="operator")

        from monitoring.logging_config import _context

        assert _context.request_id == "req789"
        assert _context.user == "operator"

        clear_context()

    def test_clear_context(self):
        """Test clearing all context."""
        clear_context()

        set_context(request_id="req999", user="test", action="test_action", correlation_id="corr123")

        clear_context()

        from monitoring.logging_config import _context

        assert not hasattr(_context, "request_id")
        assert not hasattr(_context, "user")
        assert not hasattr(_context, "action")
        assert not hasattr(_context, "correlation_id")

        clear_context()


class TestJSONFormatter:
    """Test JSON log formatting."""

    def test_json_formatter_basic(self):
        """Test basic JSON formatting."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["logger"] == "test.module"
        assert "timestamp" in data

    def test_json_formatter_with_context(self):
        """Test JSON formatting with context attributes set on record."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1, msg="Test", args=(), exc_info=None
        )
        # Manually set context attributes (as would be done by ContextFilter)
        record.request_id = "req123"
        record.user = "trader"
        record.action = "buy"
        record.correlation_id = "corr456"

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["request_id"] == "req123"
        assert data["user"] == "trader"
        assert data["action"] == "buy"
        assert data["correlation_id"] == "corr456"

    def test_json_formatter_with_exception(self):
        """Test JSON formatting with exception info."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )

            formatted = formatter.format(record)
            data = json.loads(formatted)

            assert "exception" in data
            assert data["exception_type"] == "ValueError"

    def test_json_formatter_with_extra_fields(self):
        """Test JSON formatting with extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1, msg="Test", args=(), exc_info=None
        )
        record.extra_fields = {"symbol": "AAPL", "price": 45000}
        record.duration_ms = 123.45
        record.cache_hit = True

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["extra"] == {"symbol": "AAPL", "price": 45000}
        assert data["duration_ms"] == 123.45
        assert data["cache_hit"] is True

    def test_json_formatter_preserves_types(self):
        """Test that JSON formatter preserves data types."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1, msg="Test", args=(), exc_info=None
        )
        record.extra_fields = {"count": 42, "price": 100.50, "active": True, "items": ["a", "b", "c"]}

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert isinstance(data["extra"]["count"], int)
        assert isinstance(data["extra"]["price"], float)
        assert isinstance(data["extra"]["active"], bool)
        assert isinstance(data["extra"]["items"], list)


class TestContextFilter:
    """Test context filter for logs."""

    def teardown_method(self):
        """Cleanup after each test."""
        clear_context()

    def test_context_filter_adds_fields(self):
        """Test that context filter adds all fields to records."""
        clear_context()
        set_context(request_id="req123", user="trader", action="sell", correlation_id="corr456")

        filter_obj = ContextFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1, msg="Test", args=(), exc_info=None
        )

        result = filter_obj.filter(record)

        assert result is True
        assert record.request_id == "req123"
        assert record.user == "trader"
        assert record.action == "sell"
        assert record.correlation_id == "corr456"

        clear_context()

    def test_context_filter_defaults(self):
        """Test that context filter provides defaults when context is empty."""
        clear_context()

        filter_obj = ContextFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py", lineno=1, msg="Test", args=(), exc_info=None
        )

        result = filter_obj.filter(record)

        assert result is True
        assert record.request_id == "NO_REQUEST"
        assert record.user == "SYSTEM"
        assert record.action == "UNKNOWN"
        assert record.correlation_id is None

        clear_context()


class TestLogPerformance:
    """Test performance metrics logging."""

    def test_log_performance(self):
        """Test logging performance metrics."""
        logger = get_logger("test")
        log_performance(logger, duration_ms=123.45, symbol="AAPL", qty=1.5)

    def test_log_performance_with_metrics(self):
        """Test log_with_metrics decorator."""

        @log_with_metrics
        def sample_function(x, y):
            time.sleep(0.01)  # 10ms
            return x + y

        result = sample_function(1, 2)
        assert result == 3


class TestThreadSafety:
    """Test thread-safe context management."""

    def teardown_method(self):
        """Cleanup after each test."""
        clear_context()

    def test_context_isolation_between_threads(self):
        """Test that context is isolated between threads."""
        clear_context()

        results = {}

        def thread_func(thread_id, request_id):
            with log_context(request_id=request_id, user=f"user{thread_id}"):
                from monitoring.logging_config import _context

                # Sleep to ensure threads overlap
                time.sleep(0.01)

                results[thread_id] = {"request_id": _context.request_id, "user": _context.user}

        threads = []
        for i in range(3):
            t = threading.Thread(target=thread_func, args=(i, f"req{i}"))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Verify each thread had correct values
        assert results[0] == {"request_id": "req0", "user": "user0"}
        assert results[1] == {"request_id": "req1", "user": "user1"}
        assert results[2] == {"request_id": "req2", "user": "user2"}

        clear_context()


class TestIntegrationScenarios:
    """Test realistic logging scenarios."""

    def teardown_method(self):
        """Cleanup after each test."""
        clear_context()

    def test_api_request_context(self):
        """Test API request context scenario."""
        with log_context(request_id="api-req-123", user="trader-001", action="place_order"):
            from monitoring.logging_config import _context

            assert _context.request_id == "api-req-123"
            assert _context.user == "trader-001"
            assert _context.action == "place_order"

    def test_nested_context_operations(self):
        """Test nested context operations for complex flows."""
        with log_context(request_id="outer-req", user="user1"):
            from monitoring.logging_config import _context

            assert _context.request_id == "outer-req"

            def nested_operation():
                with log_context(request_id="inner-req"):
                    return _context.request_id

            inner_id = nested_operation()
            assert inner_id == "inner-req"

            # After context exits, outer context restored
            assert _context.request_id == "outer-req"

    def test_error_logging_scenario(self):
        """Test error logging with context information."""
        from monitoring.logging_config import _context

        with log_context(request_id="error-001", user="trader"):
            assert _context.request_id == "error-001"
            assert _context.user == "trader"

            try:
                raise ValueError("Invalid order price")
            except ValueError:
                # In real usage, logger.exception() would be called
                # Here we just verify context is available
                assert _context.request_id == "error-001"


class TestDecorators:
    """Test logging decorators."""

    def test_log_with_metrics_decorator(self):
        """Test the log_with_metrics decorator."""
        call_count = {"count": 0}

        @log_with_metrics
        def tracked_function(x):
            call_count["count"] += 1
            return x * 2

        result = tracked_function(5)
        assert result == 10
        assert call_count["count"] == 1

    def test_log_with_metrics_exception_handling(self):
        """Test that log_with_metrics decorator handles exceptions."""

        @log_with_metrics
        def failing_function():
            raise RuntimeError("Expected error")

        with pytest.raises(RuntimeError, match="Expected error"):
            failing_function()
