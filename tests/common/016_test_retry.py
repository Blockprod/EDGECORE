"""Tests for retry logic and exponential backoff."""

from datetime import UTC, datetime

import pytest
<<<<<<< HEAD

from common.retry import RetryException, RetryPolicy, RetryStats, retry_with_backoff
=======
from datetime import datetime
from common.retry import (
    RetryPolicy,
    retry_with_backoff,
    RetryException,
    RetryStats
)
>>>>>>> origin/main


class TestRetryPolicy:
    """Test retry policy configuration."""

    def test_policy_defaults(self):
        """Test default policy values."""
        policy = RetryPolicy()

        assert policy.max_attempts == 3
        assert policy.initial_delay_seconds == 1.0
        assert policy.max_delay_seconds == 60.0

    def test_policy_custom_values(self):
        """Test custom policy values."""
        policy = RetryPolicy(max_attempts=5, initial_delay_seconds=2.0, max_delay_seconds=120.0)

        assert policy.max_attempts == 5
        assert policy.initial_delay_seconds == 2.0

    def test_policy_invalid_max_attempts(self):
        """Test that invalid max_attempts raises error."""
        with pytest.raises(ValueError):
            RetryPolicy(max_attempts=0)

    def test_policy_invalid_delay_order(self):
        """Test that max_delay < initial_delay raises error."""
        with pytest.raises(ValueError):
            RetryPolicy(initial_delay_seconds=10.0, max_delay_seconds=5.0)

    def test_policy_invalid_jitter_factor(self):
        """Test that invalid jitter raises error."""
        with pytest.raises(ValueError):
            RetryPolicy(jitter_factor=1.5)


class TestExponentialBackoff:
    """Test exponential backoff calculation."""

    def test_backoff_first_attempt(self):
        """Test delay for first attempt."""
        policy = RetryPolicy(initial_delay_seconds=1.0, exponential_base=2.0)

        delay = policy.calculate_delay(0)
        # Should be ~1.0 + jitter
        assert 0.9 < delay < 1.2

    def test_backoff_exponential_growth(self):
        """Test exponential growth of delay."""
        policy = RetryPolicy(
            initial_delay_seconds=1.0,
            exponential_base=2.0,
            jitter_factor=0.0,  # No jitter for predictable test
        )

        delay_0 = policy.calculate_delay(0)  # 1.0
        delay_1 = policy.calculate_delay(1)  # 2.0
        delay_2 = policy.calculate_delay(2)  # 4.0

        assert 0.95 < delay_0 < 1.05
        assert 1.95 < delay_1 < 2.05
        assert 3.95 < delay_2 < 4.05

    def test_backoff_max_delay_cap(self):
        """Test that delay is capped at max."""
        policy = RetryPolicy(initial_delay_seconds=1.0, max_delay_seconds=10.0, exponential_base=2.0, jitter_factor=0.0)

        # With exponential base 2, attempt 4 would be 16.0
        # But should be capped at 10.0
        delay = policy.calculate_delay(4)
        assert delay <= 10.0

    def test_backoff_negative_attempt_fails(self):
        """Test that negative attempt raises error."""
        policy = RetryPolicy()

        with pytest.raises(ValueError):
            policy.calculate_delay(-1)


class TestRetryDecorator:
    """Test retry decorator functionality."""

    def test_retry_success_on_first_attempt(self):
        """Test successful call on first attempt."""
        call_count = 0

        @retry_with_backoff()
        def successful_call():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_call()

        assert result == "success"
        assert call_count == 1

    def test_retry_success_on_second_attempt(self):
        """Test successful call after one failure."""
        call_count = 0

        @retry_with_backoff(RetryPolicy(initial_delay_seconds=0.01))
        def eventually_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("temp failure")
            return "success"

        result = eventually_succeeds()

        assert result == "success"
        assert call_count == 2

    def test_retry_exhausted(self):
        """Test that retries are exhausted."""
        call_count = 0

        @retry_with_backoff(RetryPolicy(max_attempts=2, initial_delay_seconds=0.01))
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("failed")

        with pytest.raises(RetryException):
            always_fails()

        assert call_count == 2

    def test_retry_non_retryable_exception(self):
        """Test that non-retryable exceptions are not retried."""
        call_count = 0

        @retry_with_backoff(RetryPolicy(max_attempts=3))
        def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError):
            raises_value_error()

        assert call_count == 1  # Only tried once

    def test_retry_with_custom_retryable_exceptions(self):
        """Test retry with custom exception types."""
        call_count = 0

        policy = RetryPolicy(max_attempts=2, initial_delay_seconds=0.01)
        policy.retryable_exceptions = (ValueError, RuntimeError)

        @retry_with_backoff(policy)
        def raises_custom_exception():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("custom error")
            return "success"

        result = raises_custom_exception()

        assert result == "success"
        assert call_count == 2

    def test_retry_with_callback(self):
        """Test retry with on_retry callback."""
        callback_calls = []

        def on_retry_callback(attempt, exception, delay):
            callback_calls.append((attempt, type(exception).__name__, delay))

        @retry_with_backoff(RetryPolicy(max_attempts=3, initial_delay_seconds=0.01), on_retry=on_retry_callback)
        def fails_twice():
            if len(callback_calls) < 2:
                raise ConnectionError("temp")
            return "success"

        result = fails_twice()

        assert result == "success"
        assert len(callback_calls) == 2
        assert callback_calls[0][1] == "ConnectionError"

    def test_retry_preserves_function_metadata(self):
        """Test that retry decorator preserves function metadata."""

        @retry_with_backoff()
        def my_function():
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
        assert (my_function.__doc__ or "") and "My docstring" in (my_function.__doc__ or "")


class TestRetryStats:
    """Test retry statistics tracking."""

    def test_stats_initial_state(self):
        """Test initial stats state."""
        stats = RetryStats()

        summary = stats.get_stats()
        assert summary["total_calls"] == 0
        assert summary["successful"] == 0
        assert summary["failed"] == 0

    def test_stats_record_success(self):
        """Test recording successful call."""
        stats = RetryStats()

        stats.record_call("api_call", success=True, retries=0)
        summary = stats.get_stats()

        assert summary["total_calls"] == 1
        assert summary["successful"] == 1
        assert summary["failed"] == 0
        assert summary["success_rate_pct"] == 100.0

    def test_stats_record_failure(self):
        """Test recording failed call."""
        stats = RetryStats()

        stats.record_call("api_call", success=False, retries=2)
        summary = stats.get_stats()

        assert summary["total_calls"] == 1
        assert summary["successful"] == 0
        assert summary["failed"] == 1
        assert summary["success_rate_pct"] == 0.0

    def test_stats_success_rate_calculation(self):
        """Test success rate calculation."""
        stats = RetryStats()

        stats.record_call("api_call", success=True, retries=0)
        stats.record_call("api_call", success=True, retries=0)
        stats.record_call("api_call", success=False, retries=1)

        summary = stats.get_stats()
        assert summary["successful"] == 2
        assert summary["failed"] == 1
        assert abs(summary["success_rate_pct"] - 66.67) < 1.0

    def test_stats_by_function(self):
        """Test stats tracking by function name."""
        stats = RetryStats()

        stats.record_call("func1", success=True, retries=0)
        stats.record_call("func2", success=False, retries=1)
        summary = stats.get_stats()

        assert summary["by_function"]["func1"]["successful"] == 1
        assert summary["by_function"]["func2"]["failed"] == 1


class TestRetryIntegration:
    """Integration tests for retry mechanism."""

    def test_retry_with_timeout_simulation(self):
        """Test retry can recover from temporary timeouts."""
        call_times = []

        @retry_with_backoff(RetryPolicy(max_attempts=3, initial_delay_seconds=0.01))
        def flaky_api():
            call_times.append(datetime.now(UTC))
            if len(call_times) < 2:
                raise TimeoutError("Temp timeout")
            return "success"

        result = flaky_api()

        assert result == "success"
        assert len(call_times) == 2
        # Verify delay between calls
        if len(call_times) >= 2:
            delay = (call_times[1] - call_times[0]).total_seconds()
            assert delay > 0.005  # At least some delay
