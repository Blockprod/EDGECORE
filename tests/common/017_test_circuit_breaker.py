"""Tests for circuit breaker pattern."""

import pytest
import time
from common.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitBreakerState,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    get_circuit_breaker,
    reset_all_circuit_breakers
)


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration."""
    
    def test_config_defaults(self):
        """Test default configuration."""
        config = CircuitBreakerConfig()
        
        assert config.failure_threshold == 5
        assert config.timeout_seconds == 60
        assert config.success_threshold == 2
    
    def test_config_custom_values(self):
        """Test custom configuration."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            timeout_seconds=30,
            success_threshold=1
        )
        
        assert config.failure_threshold == 3
        assert config.timeout_seconds == 30
    
    def test_config_invalid_threshold(self):
        """Test that invalid threshold raises error."""
        with pytest.raises(ValueError):
            CircuitBreakerConfig(failure_threshold=0)
    
    def test_config_invalid_timeout(self):
        """Test that invalid timeout raises error."""
        with pytest.raises(ValueError):
            CircuitBreakerConfig(timeout_seconds=0)


class TestCircuitBreakerInitialization:
    """Test circuit breaker initialization."""
    
    def test_breaker_initial_state(self):
        """Test breaker starts in CLOSED state."""
        breaker = CircuitBreaker("test_breaker")
        
        assert breaker.get_state() == CircuitBreakerState.CLOSED
        assert breaker.metrics.failure_count == 0
        assert breaker.metrics.success_count == 0
    
    def test_breaker_invalid_name(self):
        """Test that empty name raises error."""
        with pytest.raises(ValueError):
            CircuitBreaker("")
    
    def test_breaker_with_custom_config(self):
        """Test breaker with custom configuration."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)
        
        assert breaker.config.failure_threshold == 3


class TestCircuitBreakerNormalOperation:
    """Test circuit breaker in normal (CLOSED) state."""
    
    def test_breaker_successful_call(self):
        """Test successful call passes through."""
        breaker = CircuitBreaker("test")
        
        def success():
            return "result"
        
        result = breaker.call(success)
        
        assert result == "result"
        assert breaker.metrics.success_count == 1
        assert breaker.metrics.state == CircuitBreakerState.CLOSED
    
    def test_breaker_single_failure(self):
        """Test single failure doesn't open circuit."""
        breaker = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
        
        def fails():
            raise ConnectionError("Connection failed")
        
        with pytest.raises(ConnectionError):
            breaker.call(fails)
        
        assert breaker.metrics.failure_count == 1
        assert breaker.metrics.state == CircuitBreakerState.CLOSED
    
    def test_breaker_multiple_failures_opens_circuit(self):
        """Test multiple failures open circuit."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)
        
        def fails():
            raise ConnectionError("Failed")
        
        # First failure
        with pytest.raises(ConnectionError):
            breaker.call(fails)
        assert breaker.metrics.state == CircuitBreakerState.CLOSED
        
        # Second failure - should open
        with pytest.raises(ConnectionError):
            breaker.call(fails)
        assert breaker.metrics.state == CircuitBreakerState.OPEN


class TestCircuitBreakerOpenState:
    """Test circuit breaker in OPEN state."""
    
    def test_breaker_open_blocks_calls(self):
        """Test that OPEN circuit blocks calls."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker("test", config)
        
        # Trigger open
        with pytest.raises(ConnectionError):
            breaker.call(lambda: 1/0 if False else (_ for _ in ()).throw(ConnectionError()))
        
        # Now circuit should block the call without executing
        def should_not_execute():
            raise AssertionError("Should not have executed")
        
        with pytest.raises(CircuitBreakerOpen):
            breaker.call(should_not_execute)
    
    def test_breaker_open_allows_timeout_transition(self):
        """Test that OPEN circuit transitions to HALF_OPEN after timeout."""
        config = CircuitBreakerConfig(failure_threshold=1, timeout_seconds=1)
        breaker = CircuitBreaker("test", config)
        
        # Open the circuit
        def fails():
            raise ConnectionError("Failed")
        
        with pytest.raises(ConnectionError):
            breaker.call(fails)
        
        assert breaker.metrics.state == CircuitBreakerState.OPEN
        
        # Wait for timeout
        time.sleep(1.1)
        
        # Should transition to HALF_OPEN on next call
        def succeed():
            return "success"
        
        result = breaker.call(succeed)
        assert result == "success"
        assert breaker.metrics.state == CircuitBreakerState.HALF_OPEN


class TestCircuitBreakerHalfOpenState:
    """Test circuit breaker in HALF_OPEN state (recovery)."""
    
    def test_breaker_half_open_success_closes(self):
        """Test that success in HALF_OPEN closes circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            timeout_seconds=60,  # Config requires >= 1
            success_threshold=1
        )
        breaker = CircuitBreaker("test", config)
        
        # Open circuit
        def fails():
            raise ConnectionError("Failed")
        
        with pytest.raises(ConnectionError):
            breaker.call(fails)
        
        # Force to HALF_OPEN
        breaker._transition_to_half_open()
        
        # Success should close
        def succeed():
            return "success"
        
        result = breaker.call(succeed)
        assert result == "success"
        assert breaker.metrics.state == CircuitBreakerState.CLOSED
    
    def test_breaker_half_open_failure_reopens(self):
        """Test that failure in HALF_OPEN reopens circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            timeout_seconds=60,
            success_threshold=1
        )
        breaker = CircuitBreaker("test", config)
        
        # Move to HALF_OPEN
        breaker._transition_to_half_open()
        assert breaker.metrics.state == CircuitBreakerState.HALF_OPEN
        
        # Failure should reopen
        def fails():
            raise ConnectionError("Failed")
        
        with pytest.raises(ConnectionError):
            breaker.call(fails)
        
        assert breaker.metrics.state == CircuitBreakerState.OPEN


class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics."""
    
    def test_metrics_tracks_calls(self):
        """Test metrics track successful calls."""
        breaker = CircuitBreaker("test")
        
        breaker.call(lambda: "ok")
        breaker.call(lambda: "ok")
        
        metrics = breaker.get_metrics()
        assert metrics.total_calls == 2
        assert metrics.success_count == 2
    
    def test_metrics_tracks_failures(self):
        """Test metrics track failures."""
        breaker = CircuitBreaker("test")
        
        def fails():
            raise ConnectionError()
        
        for _ in range(3):
            try:
                breaker.call(fails)
            except ConnectionError:
                pass
        
        metrics = breaker.get_metrics()
        assert metrics.total_calls == 3
        assert metrics.failure_count == 3
    
    def test_metrics_records_timestamps(self):
        """Test metrics record timestamps."""
        breaker = CircuitBreaker("test")
        
        breaker.call(lambda: "ok")
        metrics = breaker.get_metrics()
        
        assert metrics.last_success_time is not None
        assert isinstance(metrics.last_success_time, type(metrics.state_change_time))


class TestCircuitBreakerManualControl:
    """Test manual control of circuit breaker."""
    
    def test_breaker_can_reset(self):
        """Test manual reset of circuit breaker."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker("test", config)
        
        # Open circuit
        def fails():
            raise ConnectionError()
        
        with pytest.raises(ConnectionError):
            breaker.call(fails)
        
        assert breaker.metrics.state == CircuitBreakerState.OPEN
        
        # Reset
        breaker.reset()
        
        assert breaker.metrics.state == CircuitBreakerState.CLOSED
        assert breaker.metrics.failure_count == 0


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry."""
    
    def test_registry_creates_breaker(self):
        """Test registry creates breaker on demand."""
        registry = CircuitBreakerRegistry()
        
        breaker = registry.get_or_create("api_1")
        assert breaker is not None
        assert breaker.name == "api_1"
    
    def test_registry_reuses_breaker(self):
        """Test registry reuses same breaker."""
        registry = CircuitBreakerRegistry()
        
        breaker1 = registry.get_or_create("api_1")
        breaker2 = registry.get_or_create("api_1")
        
        assert breaker1 is breaker2
    
    def test_registry_separates_breakers(self):
        """Test different breakers for different names."""
        registry = CircuitBreakerRegistry()
        
        breaker1 = registry.get_or_create("api_1")
        breaker2 = registry.get_or_create("api_2")
        
        assert breaker1 is not breaker2
    
    def test_registry_get_all_states(self):
        """Test getting states of all breakers."""
        registry = CircuitBreakerRegistry()
        
        registry.get_or_create("api_1")
        registry.get_or_create("api_2")
        
        states = registry.get_all_states()
        
        assert "api_1" in states
        assert "api_2" in states
        assert states["api_1"]["state"] == "closed"
    
    def test_registry_reset_all(self):
        """Test resetting all breakers."""
        registry = CircuitBreakerRegistry()
        
        breaker1 = registry.get_or_create("api_1")
        breaker2 = registry.get_or_create("api_2")
        
        # Open both
        breaker1._transition_to_open()
        breaker2._transition_to_open()
        
        # Reset all
        registry.reset_all()
        
        assert breaker1.get_state() == CircuitBreakerState.CLOSED
        assert breaker2.get_state() == CircuitBreakerState.CLOSED


class TestCircuitBreakerGlobalFunctions:
    """Test global circuit breaker functions."""
    
    def test_global_get_circuit_breaker(self):
        """Test getting circuit breaker from global registry."""
        reset_all_circuit_breakers()
        
        breaker1 = get_circuit_breaker("test_api")
        breaker2 = get_circuit_breaker("test_api")
        
        assert breaker1 is breaker2
    
    def test_global_reset_all(self):
        """Test global reset all."""
        breaker = get_circuit_breaker("test")
        breaker._transition_to_open()
        
        assert breaker.get_state() == CircuitBreakerState.OPEN
        
        reset_all_circuit_breakers()
        
        assert breaker.get_state() == CircuitBreakerState.CLOSED


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker."""
    
    def test_breaker_protects_failing_service(self):
        """Test circuit breaker protects against cascading failures."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout_seconds=1)
        breaker = CircuitBreaker("external_service", config)
        
        call_count = 0
        
        def flaky_service():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Service down")
            return "ok"
        
        # First two calls execute and fail
        for _ in range(2):
            with pytest.raises(ConnectionError):
                breaker.call(flaky_service)
        
        assert breaker.metrics.state == CircuitBreakerState.OPEN
        
        # Subsequent calls blocked without trying
        with pytest.raises(CircuitBreakerOpen):
            breaker.call(flaky_service)
        
        assert call_count == 2  # Service not called third time
    
    def test_breaker_recovery_sequence(self):
        """Test full recovery sequence."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            timeout_seconds=60,
            success_threshold=1
        )
        breaker = CircuitBreaker("test", config)
        
        # Fail and open
        with pytest.raises(ConnectionError):
            breaker.call(lambda: (_ for _ in ()).throw(ConnectionError()))
        assert breaker.metrics.state == CircuitBreakerState.OPEN
        
        # Wait for recovery
        breaker._transition_to_half_open()
        assert breaker.metrics.state == CircuitBreakerState.HALF_OPEN
        
        # Succeed and close
        breaker.call(lambda: "recovered")
        assert breaker.metrics.state == CircuitBreakerState.CLOSED
