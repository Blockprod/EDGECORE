<<<<<<< HEAD
﻿"""
=======
"""
>>>>>>> origin/main
Phase 3.2 Complete Type Hints Test Suite.

Tests:
- All TypedDict definitions work correctly
- All Enums are functional
- All type aliases operate correctly
- Key modules have proper type hints
- mypy can import all types without errors
- Runtime type validation passes
"""

<<<<<<< HEAD
from datetime import UTC, datetime

import pytest
=======
import pytest
from datetime import datetime

# Import all type definitions
from common.types import (
    # Enums
    OrderSide, OrderType, OrderStatus, ExecutionMode, AlertSeverity, CircuitBreakerState,
    # Type aliases
    Price, Quantity, Symbol, OrderID, PositionID,
    # Data structures
    OHLCVCandle, OrderRequest, OrderRecord, PositionRecord, AlertRecord, 
    RiskConfig, ValidationResult, APIResponse, HealthCheckResponse
)
>>>>>>> origin/main

# Import typed API
from common import typed_api

<<<<<<< HEAD
# Import all type definitions
from common.types import (
    AlertRecord,
    AlertSeverity,
    APIResponse,
    CircuitBreakerState,
    ExecutionMode,
    HealthCheckResponse,
    # Data structures
    OHLCVCandle,
    OrderID,
    OrderRecord,
    OrderRequest,
    # Enums
    OrderSide,
    OrderStatus,
    OrderType,
    PositionID,
    PositionRecord,
    # Type aliases
    Price,
    Quantity,
    RiskConfig,
    Symbol,
    ValidationResult,
)


class TestPhase32TypeSystem:
    """Complete Phase 3.2 type system validation."""

    def test_all_enums_defined(self):
        """Verify all required enums exist."""
        enums = [OrderSide, OrderType, OrderStatus, ExecutionMode, AlertSeverity, CircuitBreakerState]

        for enum_cls in enums:
            assert hasattr(enum_cls, "__members__"), f"{enum_cls.__name__} not an Enum"
            assert len(enum_cls.__members__) > 0, f"{enum_cls.__name__} has no members"

    def test_enum_values_correct(self):
        """Verify enum values are correct types."""
        # OrderSide should have BUY, SELL
        assert hasattr(OrderSide, "BUY")
        assert hasattr(OrderSide, "SELL")
        assert isinstance(OrderSide.BUY.value, str)

        # OrderType should have MARKET, LIMIT
        assert hasattr(OrderType, "MARKET")
        assert hasattr(OrderType, "LIMIT")

        # OrderStatus should have PENDING, FILLED, etc
        assert hasattr(OrderStatus, "PENDING")
        assert hasattr(OrderStatus, "FILLED")

        # ExecutionMode should have PAPER, LIVE, BACKTEST
        assert hasattr(ExecutionMode, "PAPER")
        assert hasattr(ExecutionMode, "LIVE")
        assert hasattr(ExecutionMode, "BACKTEST")

        # AlertSeverity should have INFO, WARNING, CRITICAL, ERROR
        assert hasattr(AlertSeverity, "INFO")
        assert hasattr(AlertSeverity, "WARNING")
        assert hasattr(AlertSeverity, "CRITICAL")
        assert hasattr(AlertSeverity, "ERROR")

        # CircuitBreakerState should have CLOSED, OPEN, HALF_OPEN
        assert hasattr(CircuitBreakerState, "CLOSED")
        assert hasattr(CircuitBreakerState, "OPEN")
        assert hasattr(CircuitBreakerState, "HALF_OPEN")

=======

class TestPhase32TypeSystem:
    """Complete Phase 3.2 type system validation."""
    
    def test_all_enums_defined(self):
        """Verify all required enums exist."""
        enums = [
            OrderSide, OrderType, OrderStatus, ExecutionMode, 
            AlertSeverity, CircuitBreakerState
        ]
        
        for enum_cls in enums:
            assert hasattr(enum_cls, '__members__'), f"{enum_cls.__name__} not an Enum"
            assert len(enum_cls.__members__) > 0, f"{enum_cls.__name__} has no members"
    
    def test_enum_values_correct(self):
        """Verify enum values are correct types."""
        # OrderSide should have BUY, SELL
        assert hasattr(OrderSide, 'BUY')
        assert hasattr(OrderSide, 'SELL')
        assert isinstance(OrderSide.BUY.value, str)
        
        # OrderType should have MARKET, LIMIT
        assert hasattr(OrderType, 'MARKET')
        assert hasattr(OrderType, 'LIMIT')
        
        # OrderStatus should have PENDING, FILLED, etc
        assert hasattr(OrderStatus, 'PENDING')
        assert hasattr(OrderStatus, 'FILLED')
        
        # ExecutionMode should have PAPER, LIVE, BACKTEST
        assert hasattr(ExecutionMode, 'PAPER')
        assert hasattr(ExecutionMode, 'LIVE')
        assert hasattr(ExecutionMode, 'BACKTEST')
        
        # AlertSeverity should have INFO, WARNING, CRITICAL, ERROR
        assert hasattr(AlertSeverity, 'INFO')
        assert hasattr(AlertSeverity, 'WARNING')
        assert hasattr(AlertSeverity, 'CRITICAL')
        assert hasattr(AlertSeverity, 'ERROR')
        
        # CircuitBreakerState should have CLOSED, OPEN, HALF_OPEN
        assert hasattr(CircuitBreakerState, 'CLOSED')
        assert hasattr(CircuitBreakerState, 'OPEN')
        assert hasattr(CircuitBreakerState, 'HALF_OPEN')
    
>>>>>>> origin/main
    def test_type_aliases_are_correct(self):
        """Verify type aliases are set correctly."""
        # Type aliases should be float or str
        test_price: Price = 100.0
        assert isinstance(test_price, float)
<<<<<<< HEAD

        test_qty: Quantity = 10.0
        assert isinstance(test_qty, float)

        test_sym: Symbol = "AAPL"
        assert isinstance(test_sym, str)

        test_oid: OrderID = "order_123"
        assert isinstance(test_oid, str)

        test_posid: PositionID = "pos_456"
        assert isinstance(test_posid, str)

    def test_ohlcv_candle_structure(self):
        """Verify OHLCVCandle TypedDict structure."""
        candle: OHLCVCandle = {
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": 102.0,
            "volume": 1000.0,
            "timestamp": datetime.now(UTC),
        }

        assert candle["open"] == 100.0
        assert candle["close"] == 102.0
        assert isinstance(candle["timestamp"], datetime)

    def test_order_record_structure(self):
        """Verify OrderRecord TypedDict structure."""
        order: OrderRecord = {
            "order_id": "ord_001",
            "symbol": "MSFT",
            "side": OrderSide.BUY,
            "quantity": 1.5,
            "filled_quantity": 1.5,
            "order_type": OrderType.MARKET,
            "status": OrderStatus.FILLED,
            "filled_price": 2000.0,
            "submitted_at": datetime.now(UTC),
        }

        assert order["order_id"] == "ord_001"
        assert order["symbol"] == "MSFT"
        assert order["status"] == OrderStatus.FILLED

    def test_position_record_structure(self):
        """Verify PositionRecord TypedDict structure."""
        position: PositionRecord = {
            "position_id": "pos_001",
            "symbol": "AAPL",
            "quantity": 0.5,
            "entry_price": 45000.0,
            "entry_time": datetime.now(UTC),
            "current_price": 45500.0,
            "marked_price": 45500.0,
            "side": "long",
            "unrealized_pnl": 2000.0,
            "pnl_percent": 4.44,
        }

        assert position["symbol"] == "AAPL"
        assert position["quantity"] == 0.5
        assert position["side"] == "long"

    def test_alert_record_structure(self):
        """Verify AlertRecord TypedDict structure."""
        alert: AlertRecord = {
            "alert_id": "alert_001",
            "severity": AlertSeverity.WARNING,
            "category": "risk",
            "title": "High volatility detected",
            "message": "Volatility exceeded 5%",
            "timestamp": datetime.now(UTC),
            "acknowledged": False,
            "resolved": False,
            "data": {"volatility": 5.2},
        }

        assert alert["severity"] == AlertSeverity.WARNING
        assert not alert["acknowledged"]
        assert "volatility" in alert["data"]

    def test_risk_config_structure(self):
        """Verify RiskConfig TypedDict structure."""
        config: RiskConfig = {
            "max_position_size": 0.05,
            "max_portfolio_heat": 0.2,
            "max_loss_per_trade": 0.01,
            "max_drawdown_pct": 0.10,
            "max_correlation": 0.85,
            "position_timeout_hours": 48.0,
            "min_equity": 10000.0,
        }

        assert config["max_position_size"] == 0.05
        assert config["max_drawdown_pct"] == 0.10

    def test_circuit_breaker_config_structure(self):
        """Verify CircuitBreakerConfig TypedDict."""
        from common.types import CircuitBreakerConfig as CBConfig

        config: CBConfig = {
            "failure_threshold": 5,
            "timeout_seconds": 60,
            "success_threshold": 2,
            "name": "test_breaker",
        }

        assert config["failure_threshold"] == 5
        assert config["name"] == "test_breaker"

    def test_validation_result_structure(self):
        """Verify ValidationResult TypedDict."""
        result: ValidationResult = {
            "is_valid": True,
            "checks_passed": 3,
            "checks_failed": 0,
            "errors": [],
            "warnings": ["Low volume observed"],
        }

        assert result["is_valid"]
        assert result["checks_passed"] == 3
        assert len(result["errors"]) == 0

    def test_risk_check_result_structure(self):
        """Verify RiskCheckResult TypedDict."""
        from common.types import RiskCheckResult as RCR

        result: RCR = {"allowed": True, "reason": "Position size within limits"}

        assert result["allowed"]
        assert "limits" in result["reason"]

    def test_typed_api_functions_exist(self):
        """Verify typed API functions are defined."""
        functions = [
            "submit_order_typed",
            "open_position_typed",
            "close_position_typed",
            "validate_ohlcv_typed",
            "check_risk_typed",
            "create_alert_typed",
            "store_secret_typed",
            "get_secret_typed",
            "retry_with_backoff_typed",
            "get_typed_circuit_breaker",
        ]

=======
        
        test_qty: Quantity = 10.0
        assert isinstance(test_qty, float)
        
        test_sym: Symbol = "AAPL"
        assert isinstance(test_sym, str)
        
        test_oid: OrderID = "order_123"
        assert isinstance(test_oid, str)
        
        test_posid: PositionID = "pos_456"
        assert isinstance(test_posid, str)
    
    def test_ohlcv_candle_structure(self):
        """Verify OHLCVCandle TypedDict structure."""
        candle: OHLCVCandle = {
            'open': 100.0,
            'high': 105.0,
            'low': 99.0,
            'close': 102.0,
            'volume': 1000.0,
            'timestamp': datetime.utcnow()
        }
        
        assert candle['open'] == 100.0
        assert candle['close'] == 102.0
        assert isinstance(candle['timestamp'], datetime)
    
    def test_order_record_structure(self):
        """Verify OrderRecord TypedDict structure."""
        order: OrderRecord = {
            'order_id': 'ord_001',
            'symbol': 'MSFT',
            'side': OrderSide.BUY,
            'quantity': 1.5,
            'filled_quantity': 1.5,
            'status': OrderStatus.FILLED,
            'filled_price': 2000.0
        }
        
        assert order['order_id'] == 'ord_001'
        assert order['symbol'] == 'MSFT'
        assert order['status'] == OrderStatus.FILLED
    
    def test_position_record_structure(self):
        """Verify PositionRecord TypedDict structure."""
        position: PositionRecord = {
            'position_id': 'pos_001',
            'symbol': 'AAPL',
            'quantity': 0.5,
            'entry_price': 45000.0,
            'side': 'long',
            'unrealized_pnl': 2000.0
        }
        
        assert position['symbol'] == 'AAPL'
        assert position['quantity'] == 0.5
        assert position['side'] == 'long'
    
    def test_alert_record_structure(self):
        """Verify AlertRecord TypedDict structure."""
        alert: AlertRecord = {
            'alert_id': 'alert_001',
            'severity': AlertSeverity.WARNING,
            'category': 'risk',
            'title': 'High volatility detected',
            'message': 'Volatility exceeded 5%',
            'timestamp': datetime.utcnow(),
            'acknowledged': False,
            'resolved': False,
            'data': {'volatility': 5.2}
        }
        
        assert alert['severity'] == AlertSeverity.WARNING
        assert not alert['acknowledged']
        assert 'volatility' in alert['data']
    
    def test_risk_config_structure(self):
        """Verify RiskConfig TypedDict structure."""
        config: RiskConfig = {
            'max_position_size_pct': 5.0,
            'max_daily_loss_pct': 2.0,
            'max_correlation': 0.85,
            'min_equity_pct': 10.0,
            'max_volatility_pct': 10.0,
            'require_cointegration': True,
            'min_cointegration_score': 0.7
        }
        
        assert config['max_position_size_pct'] == 5.0
        assert config['require_cointegration']
    
    def test_circuit_breaker_config_structure(self):
        """Verify CircuitBreakerConfig TypedDict."""
        from common.types import CircuitBreakerConfig as CBConfig
        
        config: CBConfig = {
            'failure_threshold': 5,
            'timeout_seconds': 60,
            'success_threshold': 2,
            'name': 'test_breaker'
        }
        
        assert config['failure_threshold'] == 5
        assert config['name'] == 'test_breaker'
    
    def test_validation_result_structure(self):
        """Verify ValidationResult TypedDict."""
        result: ValidationResult = {
            'is_valid': True,
            'checks_passed': ['format', 'nulls', 'ranges'],
            'checks_failed': [],
            'errors': [],
            'warnings': ['Low volume observed']
        }
        
        assert result['is_valid']
        assert 'format' in result['checks_passed']
        assert len(result['errors']) == 0
    
    def test_risk_check_result_structure(self):
        """Verify RiskCheckResult TypedDict."""
        from common.types import RiskCheckResult as RCR
        
        result: RCR = {
            'allowed': True,
            'reason': 'Position size within limits'
        }
        
        assert result['allowed']
        assert 'limits' in result['reason']
    
    def test_typed_api_functions_exist(self):
        """Verify typed API functions are defined."""
        functions = [
            'submit_order_typed',
            'open_position_typed', 
            'close_position_typed',
            'validate_ohlcv_typed',
            'check_risk_typed',
            'create_alert_typed',
            'store_secret_typed',
            'get_secret_typed',
            'retry_with_backoff_typed',
            'get_typed_circuit_breaker'
        ]
        
>>>>>>> origin/main
        for func_name in functions:
            assert hasattr(typed_api, func_name), f"{func_name} not defined in typed_api"
            func = getattr(typed_api, func_name)
            assert callable(func), f"{func_name} is not callable"
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_type_hints_preserved_runtime(self):
        """Verify type hints are preserved at runtime."""
        # Get all type definitions
        type_defs = {
<<<<<<< HEAD
            "OHLCVCandle": OHLCVCandle,
            "OrderRecord": OrderRecord,
            "PositionRecord": PositionRecord,
            "AlertRecord": AlertRecord,
            "RiskConfig": RiskConfig,
        }

        # Verify TypedDicts have annotations
        for name, typed_dict in type_defs.items():
            assert hasattr(typed_dict, "__annotations__"), f"{name} missing __annotations__"
            assert len(typed_dict.__annotations__) > 0, f"{name} has empty annotations"

=======
            'OHLCVCandle': OHLCVCandle,
            'OrderRecord': OrderRecord,
            'PositionRecord': PositionRecord,
            'AlertRecord': AlertRecord,
            'RiskConfig': RiskConfig,
        }
        
        # Verify TypedDicts have annotations
        for name, typed_dict in type_defs.items():
            assert hasattr(typed_dict, '__annotations__'), f"{name} missing __annotations__"
            assert len(typed_dict.__annotations__) > 0, f"{name} has empty annotations"
    
>>>>>>> origin/main
    def test_type_alias_operations(self):
        """Verify type alias operations work correctly."""
        # Price operations
        p1: Price = 100.0
        p2: Price = 50.0
        p3: Price = p1 + p2
        assert p3 == 150.0
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # Quantity operations
        q1: Quantity = 10.0
        q2: Quantity = 5.0
        q3: Quantity = q1 * q2
        assert q3 == 50.0
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # Symbol operations
        s1: Symbol = "AAPL"
        s2: Symbol = "MSFT"
        s3: Symbol = s1 + "-" + s2
        assert s3 == "AAPL-MSFT"
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_enum_comparison(self):
        """Verify enum comparison works correctly."""
        side1 = OrderSide.BUY
        side2 = OrderSide.BUY
        side3 = OrderSide.SELL
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        assert side1 == side2
        assert side1 != side3
        assert side1.value == "buy"
        assert side3.value == "sell"
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_status_enum_values(self):
        """Verify OrderStatus enum has all required values."""
        statuses = [
            OrderStatus.PENDING,
            OrderStatus.FILLED,
            OrderStatus.PARTIAL,
            OrderStatus.CANCELLED,
<<<<<<< HEAD
            OrderStatus.REJECTED,
        ]

=======
            OrderStatus.REJECTED
        ]
        
>>>>>>> origin/main
        for status in statuses:
            assert status is not None
            assert isinstance(status.value, str)
            assert len(status.value) > 0
<<<<<<< HEAD

    def test_api_response_structure(self):
        """Verify APIResponse TypedDict."""
        response: APIResponse = {
            "success": True,
            "data": {"order_id": "123"},
            "error": "",
            "timestamp": datetime.now(UTC),
        }

        assert response["success"]
        assert "order_id" in (response.get("data") or {})

    def test_health_check_response_structure(self):
        """Verify HealthCheckResponse TypedDict."""
        health: HealthCheckResponse = {
            "healthy": True,
            "timestamp": datetime.now(UTC),
            "components": {"data_loader": True, "execution_engine": True},
            "metrics": {},
        }

        assert health["healthy"] is True
        assert "data_loader" in health["components"]

    def test_all_typed_dicts_instantiable(self):
        """Verify all TypedDicts can be instantiated."""
        # Create minimal instances of each TypedDict

        # OHLCVCandle
        ohlcv: OHLCVCandle = {
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
            "volume": 100.0,
            "timestamp": datetime.now(UTC),
        }
        assert ohlcv is not None

        # OrderRequest
        order_req: OrderRequest = {
            "symbol": "AAPL",
            "side": OrderSide.BUY,
            "quantity": 1.0,
            "order_type": OrderType.MARKET,
        }
        assert order_req is not None

        # PositionRecord
        pos: PositionRecord = {
            "position_id": "p1",
            "symbol": "MSFT",
            "quantity": 1.0,
            "entry_price": 1000.0,
            "entry_time": datetime.now(UTC),
            "current_price": 1100.0,
            "marked_price": 1100.0,
            "side": "long",
            "unrealized_pnl": 100.0,
            "pnl_percent": 10.0,
        }
        assert pos is not None

    def test_type_import_completeness(self):
        """Verify all types import correctly from common.types."""
        from common import types as types_module

        # Verify all exported names are present
        exported = [
            "OrderSide",
            "OrderType",
            "OrderStatus",
            "ExecutionMode",
            "AlertSeverity",
            "CircuitBreakerState",
            "Price",
            "Quantity",
            "PnL",
            "Volatility",
            "Correlation",
            "Equity",
            "Symbol",
            "OrderID",
            "PositionID",
            "OHLCVCandle",
            "OrderRequest",
            "OrderRecord",
            "PositionRecord",
            "AlertRecord",
            "TradeRecord",
            "EquitySnapshot",
            "SignalData",
            "RiskConfig",
            "StrategyConfig",
            "ExecutionConfig",
            "ValidationResult",
            "RiskCheckResult",
            "CointegrationResult",
            "CircuitBreakerConfig",
            "CircuitBreakerMetrics",
            "RetryStats",
            "APIResponse",
            "HealthCheckResponse",
        ]

        for name in exported:
            assert hasattr(types_module, name), f"{name} not exported from types"

    def test_literal_types_present(self):
        """Verify Literal types are used in TypedDicts."""
        from common.types import PositionRecord

        # PositionRecord should have side: Literal["long", "short"]
        annotations = PositionRecord.__annotations__
        assert "side" in annotations

        # Validate the annotation is for literal string values
        pos: PositionRecord = {
            "position_id": "p1",
            "symbol": "AAPL",
            "quantity": 1.0,
            "entry_price": 50000.0,
            "entry_time": datetime.now(UTC),
            "current_price": 50500.0,
            "marked_price": 50500.0,
            "side": "long",
            "unrealized_pnl": 500.0,
            "pnl_percent": 1.0,
        }
        assert pos["side"] in ["long", "short"]
=======
    
    def test_api_response_structure(self):
        """Verify APIResponse TypedDict."""
        response: APIResponse = {
            'success': True,
            'data': {'order_id': '123'},
            'error': None,
            'timestamp': datetime.utcnow()
        }
        
        assert response['success']
        assert 'order_id' in response['data']
    
    def test_health_check_response_structure(self):
        """Verify HealthCheckResponse TypedDict."""
        health: HealthCheckResponse = {
            'status': 'healthy',
            'timestamp': datetime.utcnow(),
            'services': {'data_loader': 'ok', 'execution_engine': 'ok'},
            'details': {}
        }
        
        assert health['status'] == 'healthy'
        assert 'data_loader' in health['services']
    
    def test_all_typed_dicts_instantiable(self):
        """Verify all TypedDicts can be instantiated."""
        # Create minimal instances of each TypedDict
        
        # OHLCVCandle
        ohlcv: OHLCVCandle = {
            'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5,
            'volume': 100.0, 'timestamp': datetime.utcnow()
        }
        assert ohlcv is not None
        
        # OrderRequest
        order_req: OrderRequest = {
            'symbol': 'AAPL', 'side': OrderSide.BUY,
            'quantity': 1.0, 'order_type': OrderType.MARKET
        }
        assert order_req is not None
        
        # PositionRecord
        pos: PositionRecord = {
            'position_id': 'p1', 'symbol': 'MSFT',
            'quantity': 1.0, 'entry_price': 1000.0,
            'side': 'long', 'unrealized_pnl': 100.0
        }
        assert pos is not None
    
    def test_type_import_completeness(self):
        """Verify all types import correctly from common.types."""
        from common import types as types_module
        
        # Verify all exported names are present
        exported = [
            'OrderSide', 'OrderType', 'OrderStatus', 'ExecutionMode',
            'AlertSeverity', 'CircuitBreakerState',
            'Price', 'Quantity', 'PnL', 'Volatility', 'Correlation',
            'Equity', 'Symbol', 'OrderID', 'PositionID',
            'OHLCVCandle', 'OrderRequest', 'OrderRecord', 'PositionRecord',
            'AlertRecord', 'TradeRecord', 'EquitySnapshot', 'SignalData',
            'RiskConfig', 'StrategyConfig', 'ExecutionConfig',
            'ValidationResult', 'RiskCheckResult', 'CointegrationResult',
            'CircuitBreakerConfig', 'CircuitBreakerMetrics',
            'RetryStats', 'APIResponse', 'HealthCheckResponse'
        ]
        
        for name in exported:
            assert hasattr(types_module, name), f"{name} not exported from types"
    
    def test_literal_types_present(self):
        """Verify Literal types are used in TypedDicts."""
        from common.types import PositionRecord
        
        # PositionRecord should have side: Literal["long", "short"]
        annotations = PositionRecord.__annotations__
        assert 'side' in annotations
        
        # Validate the annotation is for literal string values
        pos: PositionRecord = {
            'position_id': 'p1', 'symbol': 'AAPL',
            'quantity': 1.0, 'entry_price': 50000.0,
            'side': 'long', 'unrealized_pnl': 500.0
        }
        assert pos['side'] in ['long', 'short']
>>>>>>> origin/main


class TestTypeSystemIntegration:
    """Integration tests for type system with real modules."""
<<<<<<< HEAD

    def test_retry_policy_typed(self):
        """Verify RetryPolicy works with type hints."""
        from common.retry import RetryPolicy

        policy = RetryPolicy(max_attempts=3, initial_delay_seconds=1.0, max_delay_seconds=10.0)

        assert policy.max_attempts == 3
        assert policy.initial_delay_seconds == 1.0

    def test_circuit_breaker_config_typed(self):
        """Verify CircuitBreakerConfig works with type hints."""
        from common.circuit_breaker import CircuitBreakerConfig as RealCBC

        config = RealCBC(failure_threshold=5, timeout_seconds=60, success_threshold=2)

        assert config.failure_threshold == 5
        assert config.timeout_seconds == 60

    def test_typed_api_wrapper_functions(self):
        """Verify typed API wrapper functions are callable."""
        from common.typed_api import TypedCircuitBreakerConfig, TypedRetryPolicy

        # Create typed configs
        retry_cfg = TypedRetryPolicy(
            max_attempts=3, initial_delay_seconds=1.0, max_delay_seconds=10.0, exponential_base=2.0, jitter_factor=0.1
        )

        assert retry_cfg.max_attempts == 3

        breaker_cfg = TypedCircuitBreakerConfig(
            failure_threshold=5, timeout_seconds=60, success_threshold=2, name="test"
        )

        assert breaker_cfg.name == "test"
=======
    
    def test_retry_policy_typed(self):
        """Verify RetryPolicy works with type hints."""
        from common.retry import RetryPolicy
        
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay_seconds=1.0,
            max_delay_seconds=10.0
        )
        
        assert policy.max_attempts == 3
        assert policy.initial_delay_seconds == 1.0
    
    def test_circuit_breaker_config_typed(self):
        """Verify CircuitBreakerConfig works with type hints."""
        from common.circuit_breaker import CircuitBreakerConfig as RealCBC
        
        config = RealCBC(
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2
        )
        
        assert config.failure_threshold == 5
        assert config.timeout_seconds == 60
    
    def test_typed_api_wrapper_functions(self):
        """Verify typed API wrapper functions are callable."""
        from common.typed_api import (
            TypedRetryPolicy, TypedCircuitBreakerConfig
        )
        
        # Create typed configs
        retry_cfg = TypedRetryPolicy(
            max_attempts=3,
            initial_delay_seconds=1.0,
            max_delay_seconds=10.0,
            exponential_base=2.0,
            jitter_factor=0.1
        )
        
        assert retry_cfg.max_attempts == 3
        
        breaker_cfg = TypedCircuitBreakerConfig(
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
            name='test'
        )
        
        assert breaker_cfg.name == 'test'
>>>>>>> origin/main


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
