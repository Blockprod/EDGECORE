<<<<<<< HEAD
﻿"""
=======
"""
>>>>>>> origin/main
Circuit Breaker Integration Tests - Phase 2 Feature 2

EDGECORE: Tests circuit breaker state machine, failure counting, and recovery
for the IBKR-based trading system.
"""

<<<<<<< HEAD
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
=======
import pytest
from unittest.mock import Mock
from datetime import datetime, timedelta, timezone
>>>>>>> origin/main

from common.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
<<<<<<< HEAD
    CircuitBreakerOpen,
    CircuitBreakerState,
=======
    CircuitBreakerState,
    CircuitBreakerOpen,
>>>>>>> origin/main
)
from common.errors import BrokerConnectionError


@pytest.fixture
def breaker():
    """Create a CircuitBreaker with low threshold for fast testing."""
    config = CircuitBreakerConfig(failure_threshold=3, timeout_seconds=60, success_threshold=2)
    return CircuitBreaker(name="test_breaker", config=config)


@pytest.fixture
def default_breaker():
    """Create a CircuitBreaker with default config."""
    return CircuitBreaker(name="default_breaker")


class TestCircuitBreakerInitialization:
    """Validate circuit breaker is properly initialized."""

    def test_breaker_starts_in_closed_state(self, breaker):
        assert breaker.state == CircuitBreakerState.CLOSED

    def test_breaker_config_stored(self, breaker):
        assert breaker.config.failure_threshold == 3
        assert breaker.config.timeout_seconds == 60
        assert breaker.config.success_threshold == 2

    def test_default_config_values(self, default_breaker):
        assert default_breaker.config.failure_threshold == 5
        assert default_breaker.config.timeout_seconds == 60
        assert default_breaker.config.success_threshold == 2

    def test_breaker_name_stored(self, breaker):
        assert breaker.name == "test_breaker"

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            CircuitBreaker(name="")

    def test_failure_count_starts_at_zero(self, breaker):
        assert breaker.failure_count == 0


class TestCircuitBreakerClosedState:
    """Validate behavior in CLOSED state (normal operation)."""

    def test_successful_calls_keep_circuit_closed(self, breaker):
        result = breaker.call(lambda: "success")
        assert result == "success"
        assert breaker.state == CircuitBreakerState.CLOSED

    def test_single_failure_does_not_open(self, breaker):
        def _fail():
            raise ValueError("one failure")
<<<<<<< HEAD

=======
>>>>>>> origin/main
        with pytest.raises(ValueError):
            breaker.call(_fail)
        assert breaker.state == CircuitBreakerState.CLOSED

    def test_failure_count_increments(self, breaker):
        def _fail():
            raise Exception("fail")
<<<<<<< HEAD

=======
>>>>>>> origin/main
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(_fail)
        assert breaker.failure_count == 2
        assert breaker.state == CircuitBreakerState.CLOSED

    def test_success_after_failures_keeps_closed(self, breaker):
        def _fail():
            raise Exception("fail")
<<<<<<< HEAD

=======
>>>>>>> origin/main
        with pytest.raises(Exception):
            breaker.call(_fail)
        result = breaker.call(lambda: "ok")
        assert result == "ok"
        assert breaker.state == CircuitBreakerState.CLOSED


class TestCircuitBreakerOpening:
    """Validate circuit transitions to OPEN after threshold failures."""

    def test_circuit_opens_after_threshold_failures(self, breaker):
        def _fail():
            raise Exception("fail")
<<<<<<< HEAD

=======
>>>>>>> origin/main
        for _ in range(3):
            with pytest.raises(Exception):
                breaker.call(_fail)
        assert breaker.state == CircuitBreakerState.OPEN

    def test_open_circuit_blocks_calls(self, breaker):
        def _fail():
            raise Exception("fail")
<<<<<<< HEAD

=======
>>>>>>> origin/main
        for _ in range(3):
            with pytest.raises(Exception):
                breaker.call(_fail)
        with pytest.raises(CircuitBreakerOpen):
            breaker.call(lambda: "should not run")

    def test_blocked_call_does_not_invoke_function(self, breaker):
        mock_func = Mock(return_value="result")
        breaker.metrics.state = CircuitBreakerState.OPEN
        with pytest.raises(CircuitBreakerOpen):
            breaker.call(mock_func)
        mock_func.assert_not_called()

    def test_failure_count_at_threshold(self, breaker):
        def _fail():
            raise Exception("fail")
<<<<<<< HEAD

=======
>>>>>>> origin/main
        for _ in range(3):
            with pytest.raises(Exception):
                breaker.call(_fail)
        assert breaker.failure_count >= 3


class TestCircuitBreakerHalfOpen:
    """Validate HALF_OPEN state transitions."""

    def test_circuit_transitions_to_half_open_after_timeout(self, breaker):
        def _fail():
            raise Exception("fail")
<<<<<<< HEAD

=======
>>>>>>> origin/main
        for _ in range(3):
            with pytest.raises(Exception):
                breaker.call(_fail)
        assert breaker.state == CircuitBreakerState.OPEN
<<<<<<< HEAD
        breaker.metrics.state_change_time = datetime.now(UTC) - timedelta(seconds=61)
=======
        breaker.metrics.state_change_time = datetime.now(timezone.utc) - timedelta(seconds=61)
>>>>>>> origin/main
        result = breaker.call(lambda: "test")
        assert result == "test"
        assert breaker.state in (CircuitBreakerState.HALF_OPEN, CircuitBreakerState.CLOSED)

    def test_half_open_failure_returns_to_open(self, breaker):
        def _fail():
            raise Exception("fail")
<<<<<<< HEAD

=======
>>>>>>> origin/main
        breaker.metrics.state = CircuitBreakerState.HALF_OPEN
        with pytest.raises(Exception):
            breaker.call(_fail)
        assert breaker.state == CircuitBreakerState.OPEN

    def test_half_open_success_threshold_closes_circuit(self, breaker):
        breaker.metrics.state = CircuitBreakerState.HALF_OPEN
        breaker.metrics.consecutive_successes = 0
        for _ in range(2):
            breaker.call(lambda: "ok")
        assert breaker.state == CircuitBreakerState.CLOSED


class TestCircuitBreakerRecovery:
    """Validate full recovery cycle."""

    def test_full_state_cycle(self, breaker):
        def _fail():
            raise Exception("fail")
<<<<<<< HEAD

=======
>>>>>>> origin/main
        for _ in range(3):
            with pytest.raises(Exception):
                breaker.call(_fail)
        assert breaker.state == CircuitBreakerState.OPEN
<<<<<<< HEAD
        breaker.metrics.state_change_time = datetime.now(UTC) - timedelta(seconds=61)
=======
        breaker.metrics.state_change_time = datetime.now(timezone.utc) - timedelta(seconds=61)
>>>>>>> origin/main
        breaker.call(lambda: "probe")
        breaker.call(lambda: "probe2")
        assert breaker.state == CircuitBreakerState.CLOSED

    def test_circuit_can_reopen_after_recovery(self, breaker):
        def _fail():
            raise Exception("fail")
<<<<<<< HEAD

        for _ in range(3):
            with pytest.raises(Exception):
                breaker.call(_fail)
        breaker.metrics.state_change_time = datetime.now(UTC) - timedelta(seconds=61)
=======
        for _ in range(3):
            with pytest.raises(Exception):
                breaker.call(_fail)
        breaker.metrics.state_change_time = datetime.now(timezone.utc) - timedelta(seconds=61)
>>>>>>> origin/main
        for _ in range(2):
            breaker.call(lambda: "ok")
        assert breaker.state == CircuitBreakerState.CLOSED


class TestCircuitBreakerIndependence:
    """Validate multiple circuit breakers operate independently."""

    def test_two_breakers_are_independent(self):
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker_a = CircuitBreaker("service_a", config)
        breaker_b = CircuitBreaker("service_b", config)

        def _fail():
            raise Exception("fail")

        for _ in range(3):
            with pytest.raises(Exception):
                breaker_a.call(_fail)

        assert breaker_a.state == CircuitBreakerState.OPEN
        assert breaker_b.state == CircuitBreakerState.CLOSED
        result = breaker_b.call(lambda: "works")
        assert result == "works"

    def test_breakers_have_independent_counts(self):
        config = CircuitBreakerConfig(failure_threshold=5)
        b1 = CircuitBreaker("api_a", config)
        b2 = CircuitBreaker("api_b", config)

        def _fail():
            raise Exception("fail")

        with pytest.raises(Exception):
            b1.call(_fail)
        with pytest.raises(Exception):
            b2.call(_fail)
        with pytest.raises(Exception):
            b2.call(_fail)

        assert b1.failure_count == 1
        assert b2.failure_count == 2


class TestCircuitBreakerIBKRIntegration:
    """Validate circuit breaker pattern with IBKR execution logic."""

    def test_circuit_protects_ibkr_submit(self):
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("ibkr_submit", config)
        call_count = 0

        def failing_submit():
            nonlocal call_count
            call_count += 1
            raise BrokerConnectionError("TWS connection lost")

        for _ in range(3):
            with pytest.raises(Exception):
                breaker.call(failing_submit)

        assert breaker.state == CircuitBreakerState.OPEN

        with pytest.raises(CircuitBreakerOpen):
            breaker.call(failing_submit)

        assert call_count == 3

    def test_circuit_recovers_when_ibkr_reconnects(self):
        config = CircuitBreakerConfig(failure_threshold=3, timeout_seconds=60, success_threshold=2)
        breaker = CircuitBreaker("ibkr_submit", config)

        def _fail():
            raise BrokerConnectionError("down")

        for _ in range(3):
            with pytest.raises(Exception):
                breaker.call(_fail)

        assert breaker.state == CircuitBreakerState.OPEN

<<<<<<< HEAD
        breaker.metrics.state_change_time = datetime.now(UTC) - timedelta(seconds=61)
=======
        breaker.metrics.state_change_time = datetime.now(timezone.utc) - timedelta(seconds=61)
>>>>>>> origin/main

        for _ in range(2):
            breaker.call(lambda: "order_submitted")

        assert breaker.state == CircuitBreakerState.CLOSED


class TestCircuitBreakerProperties:
    """Validate circuit breaker properties."""

    def test_state_property(self, breaker):
        assert breaker.state == CircuitBreakerState.CLOSED
        breaker.metrics.state = CircuitBreakerState.OPEN
        assert breaker.state == CircuitBreakerState.OPEN

    def test_failure_count_property(self, breaker):
        def _fail():
            raise Exception("fail")
<<<<<<< HEAD

=======
>>>>>>> origin/main
        assert breaker.failure_count == 0
        with pytest.raises(Exception):
            breaker.call(_fail)
        assert breaker.failure_count == 1

    def test_success_count_property(self, breaker):
        count_before = breaker.success_count
        breaker.call(lambda: "ok")
        assert breaker.success_count == count_before + 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
