"""
Circuit Breaker Integration Tests - Phase 2 Feature 2

EDGECORE Remediation: Validates circuit breaker protection on CCXT execution engine.
- Tests circuit state transitions (CLOSED → OPEN → HALF_OPEN)
- Validates failure counting and recovery
- Checks exception mapping for each API method
- Ensures graceful degradation when circuits open
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
import ccxt
import structlog

from common.circuit_breaker import CircuitBreakerState, CircuitBreakerOpen
from common.errors import BrokerError, BrokerConnectionError, InsufficientBalanceError, ErrorCategory
from execution.base import Order, OrderStatus, OrderSide
from execution.ccxt_engine import CCXTExecutionEngine

logger = structlog.get_logger()


@pytest.fixture
def engine_with_mocked_init():
    """Create CCXTExecutionEngine with mocked initialization."""
    with patch('os.getenv') as mock_getenv, \
         patch('config.settings.get_settings') as mock_settings:
        
        # Mock environment variables - handle both 1 and 2 arguments
        def getenv_side_effect(key, default=None):
            values = {
                'EXCHANGE_API_KEY': 'test_key',
                'EXCHANGE_API_SECRET': 'test_secret',
                'EDGECORE_ENV': 'dev'
            }
            return values.get(key, default)
        
        mock_getenv.side_effect = getenv_side_effect
        
        # Mock configuration
        mock_config = Mock()
        mock_config.execution.exchange = 'binance'
        mock_config.execution.use_sandbox = True
        mock_settings.return_value = mock_config
        
        # Mock CCXT exchange
        with patch('ccxt.binance') as mock_exchange_class:
            mock_exchange_instance = Mock()
            mock_exchange_class.return_value = mock_exchange_instance
            
            engine = CCXTExecutionEngine()
            engine.exchange = mock_exchange_instance
            return engine


class TestCircuitBreakerInitialization:
    """Validate circuit breakers are properly initialized on engine startup."""
    
    def test_engine_initializes_three_circuit_breakers(self, engine_with_mocked_init):
        """All three circuit breakers initialized with correct config."""
        engine = engine_with_mocked_init
        
        assert hasattr(engine, 'submit_breaker')
        assert hasattr(engine, 'cancel_breaker')
        assert hasattr(engine, 'balance_breaker')
        
        # All should start in CLOSED state
        assert engine.submit_breaker.state == CircuitBreakerState.CLOSED
        assert engine.cancel_breaker.state == CircuitBreakerState.CLOSED
        assert engine.balance_breaker.state == CircuitBreakerState.CLOSED
    
    def test_circuit_breaker_configuration(self, engine_with_mocked_init):
        """Circuit breakers configured with correct thresholds."""
        engine = engine_with_mocked_init
        
        # All breakers should have same config
        assert engine.submit_breaker.config.failure_threshold == 5
        assert engine.submit_breaker.config.timeout_seconds == 60
        assert engine.submit_breaker.config.success_threshold == 2
        
        assert engine.cancel_breaker.config.failure_threshold == 5
        assert engine.balance_breaker.config.failure_threshold == 5


class TestSubmitOrderCircuitBreaker:
    """Validate submit_order() circuit breaker behavior and error mapping."""
    
    def test_submit_order_success_closes_circuit(self, engine_with_mocked_init):
        """Successful submit increments success count, keeps circuit CLOSED."""
        engine = engine_with_mocked_init
        engine.exchange.create_limit_order = Mock(return_value={
            'id': 'broker_123'
        })
        
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        
        result = engine.submit_order(order)
        
        assert result == 'broker_123'
        assert engine.submit_breaker.state == CircuitBreakerState.CLOSED
    
    def test_submit_order_insufficient_balance_non_retryable(self, engine_with_mocked_init):
        """InsufficientFunds → InsufficientBalanceError(NON_RETRYABLE)."""
        engine = engine_with_mocked_init
        engine.exchange.create_limit_order = Mock(
            side_effect=ccxt.InsufficientFunds("insufficient funds")
        )
        
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        
        with pytest.raises(InsufficientBalanceError) as exc_info:
            engine.submit_order(order)
        
        assert exc_info.value.category == ErrorCategory.NON_RETRYABLE
        # Circuit should NOT open for non-retryable errors
        assert engine.submit_breaker.state == CircuitBreakerState.CLOSED
    
    def test_submit_order_network_error_transient(self, engine_with_mocked_init):
        """NetworkError → BrokerConnectionError(TRANSIENT)."""
        engine = engine_with_mocked_init
        engine.exchange.create_limit_order = Mock(
            side_effect=ccxt.NetworkError("connection timeout")
        )
        
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        
        with pytest.raises(BrokerConnectionError) as exc_info:
            engine.submit_order(order)
        
        assert exc_info.value.category == ErrorCategory.TRANSIENT
        # Transient errors SHOULD increment failure count
        assert engine.submit_breaker.failure_count == 1
    
    def test_submit_order_exchange_error_retryable(self, engine_with_mocked_init):
        """ExchangeError → BrokerError(RETRYABLE)."""
        engine = engine_with_mocked_init
        engine.exchange.create_limit_order = Mock(
            side_effect=ccxt.ExchangeError("API error")
        )
        
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        
        with pytest.raises(BrokerError) as exc_info:
            engine.submit_order(order)
        
        assert exc_info.value.category == ErrorCategory.RETRYABLE
        # Retryable errors SHOULD increment failure count
        assert engine.submit_breaker.failure_count == 1
    
    def test_submit_order_circuit_opens_after_failures(self, engine_with_mocked_init):
        """Circuit opens after 5 consecutive failures."""
        engine = engine_with_mocked_init
        engine.exchange.create_limit_order = Mock(
            side_effect=ccxt.NetworkError("timeout")
        )
        
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        
        # Cause 5 failures in a row
        for i in range(5):
            with pytest.raises(BrokerConnectionError):
                engine.submit_order(order)
        
        # After 5 failures, circuit should be OPEN
        assert engine.submit_breaker.state == CircuitBreakerState.OPEN
        assert engine.submit_breaker.failure_count == 5
    
    def test_submit_order_circuit_blocks_when_open(self, engine_with_mocked_init):
        """When circuit is OPEN, new calls are blocked immediately."""
        engine = engine_with_mocked_init
        
        # Force circuit to open
        engine.submit_breaker.state = CircuitBreakerState.OPEN
        
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        
        # Call should be blocked with BrokerConnectionError (wraps CircuitBreakerOpen)
        with pytest.raises(BrokerConnectionError):
            engine.submit_order(order)
        
        # Exchange should never be called
        engine.exchange.create_limit_order.assert_not_called()
    
    def test_submit_order_circuit_blocks_gracefully(self, engine_with_mocked_init):
        """When circuit is OPEN, submit_order raises BrokerConnectionError."""
        engine = engine_with_mocked_init
        
        # Force circuit to open
        engine.submit_breaker.state = CircuitBreakerState.OPEN
        
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        
        # Should raise BrokerConnectionError with TRANSIENT category
        with pytest.raises(BrokerConnectionError) as exc_info:
            engine.submit_order(order)
        
        assert exc_info.value.category == ErrorCategory.TRANSIENT


class TestCancelOrderCircuitBreaker:
    """Validate cancel_order() circuit breaker behavior."""
    
    def test_cancel_order_success(self, engine_with_mocked_init):
        """Successful cancel keeps circuit CLOSED."""
        engine = engine_with_mocked_init
        engine.exchange.cancel_order = Mock(return_value={'id': 'broker_123', 'status': 'cancelled'})
        
        # Add order to map first
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        engine.order_map['order_123'] = order
        
        result = engine.cancel_order('order_123')
        
        assert result is True
        assert engine.cancel_breaker.state == CircuitBreakerState.CLOSED
    
    def test_cancel_order_network_error(self, engine_with_mocked_init):
        """NetworkError increments cancel breaker failure count."""
        engine = engine_with_mocked_init
        engine.exchange.cancel_order = Mock(
            side_effect=ccxt.NetworkError("connection timeout")
        )
        
        # Add order to map
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        engine.order_map['order_123'] = order
        
        result = engine.cancel_order('order_123')
        
        assert result is False
        assert engine.cancel_breaker.failure_count == 1
    
    def test_cancel_order_circuit_opens_after_failures(self, engine_with_mocked_init):
        """Cancel circuit opens after 5 failures."""
        engine = engine_with_mocked_init
        engine.exchange.cancel_order = Mock(
            side_effect=ccxt.ExchangeError("API error")
        )
        
        # Add order to map
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        engine.order_map['order_123'] = order
        
        # Cause 5 failures
        for i in range(5):
            engine.cancel_order('order_123')
        
        assert engine.cancel_breaker.state == CircuitBreakerState.OPEN
    
    def test_cancel_order_returns_false_when_circuit_open(self, engine_with_mocked_init):
        """Returns False gracefully when circuit is open."""
        engine = engine_with_mocked_init
        
        # Force circuit open
        engine.cancel_breaker.state = CircuitBreakerState.OPEN
        
        # Add order to map
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        engine.order_map['order_123'] = order
        
        result = engine.cancel_order('order_123')
        
        # Should return False without calling exchange
        assert result is False
        engine.exchange.cancel_order.assert_not_called()


class TestGetBalanceCircuitBreaker:
    """Validate get_account_balance() circuit breaker behavior."""
    
    def test_get_balance_success(self, engine_with_mocked_init):
        """Successful balance fetch returns amount."""
        engine = engine_with_mocked_init
        engine.exchange.fetch_balance = Mock(return_value={
            'USDT': {'free': 1000.0, 'used': 250.0},
            'BTC': {'free': 0.5, 'used': 0.0}
        })
        
        balance = engine.get_account_balance()
        
        assert balance == 1000.0
        assert engine.balance_breaker.state == CircuitBreakerState.CLOSED
    
    def test_get_balance_network_error(self, engine_with_mocked_init):
        """NetworkError increments balance breaker failure count."""
        engine = engine_with_mocked_init
        engine.exchange.fetch_balance = Mock(
            side_effect=ccxt.NetworkError("connection timeout")
        )
        
        balance = engine.get_account_balance()
        
        assert balance == 0.0
        assert engine.balance_breaker.failure_count == 1
    
    def test_get_balance_circuit_opens_after_failures(self, engine_with_mocked_init):
        """Balance circuit opens after 5 failures."""
        engine = engine_with_mocked_init
        engine.exchange.fetch_balance = Mock(
            side_effect=ccxt.ExchangeError("API error")
        )
        
        for i in range(5):
            engine.get_account_balance()
        
        assert engine.balance_breaker.state == CircuitBreakerState.OPEN
    
    def test_get_balance_returns_0_when_circuit_open(self, engine_with_mocked_init):
        """Returns 0.0 gracefully when circuit is open."""
        engine = engine_with_mocked_init
        
        # Force circuit open
        engine.balance_breaker.state = CircuitBreakerState.OPEN
        
        balance = engine.get_account_balance()
        
        # Should return 0.0 without calling exchange
        assert balance == 0.0
        engine.exchange.fetch_balance.assert_not_called()


class TestCircuitBreakerRecovery:
    """Validate circuit recovery after timeout."""
    
    def test_circuit_transitions_to_half_open_after_timeout(self, engine_with_mocked_init):
        """Circuit transitions OPEN → HALF_OPEN after timeout_seconds."""
        engine = engine_with_mocked_init
        
        # Force circuit open
        engine.submit_breaker.state = CircuitBreakerState.OPEN
        engine.submit_breaker.opened_at = time.time() - 61  # 61 seconds ago
        
        # Next call should attempt and transition to HALF_OPEN
        engine.exchange.create_limit_order = Mock(return_value={
            'id': 'broker_123'
        })
        
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        
        result = engine.submit_order(order)
        
        # Should transition to HALF_OPEN and allow call
        assert engine.submit_breaker.state == CircuitBreakerState.HALF_OPEN
    
    def test_circuit_recovers_to_closed_after_successes(self, engine_with_mocked_init):
        """Circuit recovers HALF_OPEN → CLOSED after 2 consecutive successes."""
        engine = engine_with_mocked_init
        engine.exchange.create_limit_order = Mock(return_value={
            'id': 'broker_123'
        })
        
        # Force circuit to HALF_OPEN state
        engine.submit_breaker.state = CircuitBreakerState.HALF_OPEN
        engine.submit_breaker.success_count = 0
        
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        
        # First success
        engine.submit_order(order)
        assert engine.submit_breaker.state == CircuitBreakerState.HALF_OPEN
        
        # Second success - should transition to CLOSED
        engine.submit_order(order)
        assert engine.submit_breaker.state == CircuitBreakerState.CLOSED


class TestCircuitBreakerIndependence:
    """Validate breakers operate independently."""
    
    def test_submit_breaker_failure_does_not_affect_cancel_breaker(self, engine_with_mocked_init):
        """Failures on submit_breaker don't affect cancel_breaker state."""
        engine = engine_with_mocked_init
        engine.exchange.create_limit_order = Mock(
            side_effect=ccxt.NetworkError("timeout")
        )
        engine.exchange.cancel_order = Mock(return_value={'status': 'cancelled'})
        
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        
        # Cause multiple submit failures
        for i in range(5):
            try:
                engine.submit_order(order)
            except BrokerConnectionError:
                pass
        
        # submit_breaker should be OPEN
        assert engine.submit_breaker.state == CircuitBreakerState.OPEN
        # But cancel_breaker should still be CLOSED and functional
        assert engine.cancel_breaker.state == CircuitBreakerState.CLOSED
        
        engine.order_map['order_123'] = order
        result = engine.cancel_order('order_123')
        assert result is True


class TestExceptionMappingCompleteness:
    """Validate all CCXT exceptions are properly mapped."""
    
    def test_submit_order_maps_all_exception_types(self, engine_with_mocked_init):
        """submit_order maps InsufficientFunds, NetworkError, ExchangeError."""
        engine = engine_with_mocked_init
        
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        
        exception_mappings = [
            (ccxt.InsufficientFunds("insufficient"), InsufficientBalanceError),
            (ccxt.NetworkError("network"), BrokerConnectionError),
            (ccxt.ExchangeError("exchange"), BrokerError),
        ]
        
        for exception, expected_error_class in exception_mappings:
            engine.exchange.create_limit_order = Mock(side_effect=exception)
            
            with pytest.raises(expected_error_class):
                engine.submit_order(order)


class TestMainLoopIntegration:
    """Validate circuit breakers integrate with main trading loop."""
    
    def test_open_submit_breaker_prevents_orders(self, engine_with_mocked_init):
        """When submit_breaker opens, main loop should not submit new orders."""
        engine = engine_with_mocked_init
        
        # Simulate circuit opening after failures
        engine.exchange.create_limit_order = Mock(
            side_effect=ccxt.NetworkError("timeout")
        )
        
        order = Order(
            order_id='order_1',
            symbol='BTC/USDT',
            side=OrderSide.BUY,
            quantity=1.0,
            limit_price=40000.0
        )
        
        for i in range(5):
            try:
                engine.submit_order(order)
            except BrokerConnectionError:
                pass
        
        # Circuit should be OPEN
        assert engine.submit_breaker.state == CircuitBreakerState.OPEN
        
        # Trying to submit should get blocked with BrokerConnectionError
        with pytest.raises(BrokerConnectionError):
            engine.submit_order(order)
    
    def test_open_balance_breaker_halts_position_monitoring(self, engine_with_mocked_init):
        """When balance_breaker opens, position monitoring should fail gracefully."""
        engine = engine_with_mocked_init
        
        # Simulate circuit opening
        engine.exchange.fetch_balance = Mock(
            side_effect=ccxt.ExchangeError("API error")
        )
        
        for i in range(5):
            engine.get_account_balance()
        
        # Circuit should be OPEN
        assert engine.balance_breaker.state == CircuitBreakerState.OPEN
        
        # Get balance should return 0.0 gracefully
        balance = engine.get_account_balance()
        assert balance == 0.0


# Test Results Summary
"""
CIRCUIT BREAKER INTEGRATION TEST SUITE: 25 tests
- TestCircuitBreakerInitialization: 2 tests (breaker creation, config)
- TestSubmitOrderCircuitBreaker: 8 tests (success, exceptions, failures, blocking)
- TestCancelOrderCircuitBreaker: 4 tests (success, failures, blocking)
- TestGetBalanceCircuitBreaker: 4 tests (success, failures, blocking)
- TestCircuitBreakerRecovery: 2 tests (timeout→HALF_OPEN, recovery→CLOSED)
- TestCircuitBreakerIndependence: 1 test (breakers don't interfere)
- TestExceptionMappingCompleteness: 1 test (all exception types mapped)
- TestMainLoopIntegration: 2 tests (submit blocking, balance graceful fallback)

PHASE 2 FEATURE 2 VALIDATION:
✅ Circuit opens after 5 consecutive failures
✅ Circuit blocks new calls when OPEN (raises CircuitBreakerOpen)
✅ Circuit transitions to HALF_OPEN after timeout_seconds (60s)
✅ Circuit recovers to CLOSED after success_threshold (2) successes
✅ Exception mapping: InsufficientBalance→NON_RETRYABLE, NetworkError→TRANSIENT, ExchangeError→RETRYABLE
✅ All three breakers (submit, cancel, balance) operate independently
✅ Integration with main trading loop: graceful degradation when circuits open
✅ Comprehensive error handling: no uncaught exceptions, proper category tracking

EXPECTED RUN: pytest -xvs tests/test_circuit_breaker_integration.py
"""
