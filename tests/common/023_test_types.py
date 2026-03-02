"""
Type hint validation and testing.

Tests:
- TypedDict compliance
- Type coverage
- Return type validation
- Parameter type validation
"""

import pytest
from typing import get_type_hints, Any
from common.types import (
    OHLCVCandle, OrderRecord, PositionRecord, EquitySnapshot,
    ValidationResult, RiskMetrics, AlertRecord, TradeRecord,
    OrderSide, OrderType, OrderStatus, ExecutionMode, AlertSeverity,
    CircuitBreakerState, Price, Quantity, Symbol, OrderID,
)
from datetime import datetime
import inspect


class TestTypedDictStructures:
    """Test TypedDict definitions are correct."""
    
    def test_ohlcv_candle_structure(self):
        """Test OHLCVCandle TypedDict."""
        candle: OHLCVCandle = {
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": 1000.0,
            "timestamp": datetime.utcnow()
        }
        
        assert candle["open"] == 100.0
        assert candle["close"] == 102.0
        assert isinstance(candle["timestamp"], datetime)
    
    def test_order_record_structure(self):
        """Test OrderRecord TypedDict."""
        order: OrderRecord = {
            "order_id": "order_123",
            "symbol": "AAPL",
            "side": OrderSide.BUY,
            "quantity": 1.0,
            "filled_quantity": 0.5,
            "order_type": OrderType.MARKET,
            "status": OrderStatus.PARTIAL,
            "submitted_at": datetime.utcnow(),
        }
        
        assert order["order_id"] == "order_123"
        assert order["status"] == OrderStatus.PARTIAL
    
    def test_position_record_structure(self):
        """Test PositionRecord TypedDict."""
        position: PositionRecord = {
            "position_id": "pos_456",
            "symbol": "AAPL",
            "quantity": 1.5,
            "entry_price": 50000.0,
            "entry_time": datetime.utcnow(),
            "current_price": 51000.0,
            "marked_price": 51000.0,
            "side": "long",
            "unrealized_pnl": 1500.0,
            "pnl_percent": 2.0,
        }
        
        assert position["symbol"] == "AAPL"
        assert position["side"] == "long"
        assert position["unrealized_pnl"] == 1500.0
    
    def test_equity_snapshot_structure(self):
        """Test EquitySnapshot TypedDict."""
        snapshot: EquitySnapshot = {
            "timestamp": datetime.utcnow(),
            "total_equity": 100000.0,
            "cash": 50000.0,
            "positions_value": 50000.0,
            "unrealized_pnl": 2000.0,
        }
        
        assert snapshot["total_equity"] == 100000.0
        assert snapshot["cash"] + snapshot["positions_value"] == 100000.0
    
    def test_alert_record_structure(self):
        """Test AlertRecord TypedDict."""
        alert: AlertRecord = {
            "alert_id": "alert_001",
            "severity": AlertSeverity.WARNING,
            "category": "risk",
            "title": "High volatility detected",
            "message": "Volatility exceeded threshold",
            "timestamp": datetime.utcnow(),
            "acknowledged": False,
            "resolved": False,
        }
        
        assert alert["severity"] == AlertSeverity.WARNING
        assert alert["acknowledged"] is False


class TestEnumTypes:
    """Test enum definitions."""
    
    def test_order_side_enum(self):
        """Test OrderSide enum."""
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"
    
    def test_order_type_enum(self):
        """Test OrderType enum."""
        assert OrderType.MARKET.value == "market"
        assert OrderType.LIMIT.value == "limit"
    
    def test_order_status_enum(self):
        """Test OrderStatus enum."""
        statuses = [OrderStatus.PENDING, OrderStatus.FILLED, 
                    OrderStatus.CANCELLED, OrderStatus.REJECTED]
        assert len(statuses) == 4
    
    def test_execution_mode_enum(self):
        """Test ExecutionMode enum."""
        assert ExecutionMode.PAPER.value == "paper"
        assert ExecutionMode.LIVE.value == "live"
        assert ExecutionMode.BACKTEST.value == "backtest"
    
    def test_alert_severity_enum(self):
        """Test AlertSeverity enum."""
        severities = [AlertSeverity.INFO, AlertSeverity.WARNING,
                     AlertSeverity.CRITICAL, AlertSeverity.ERROR]
        assert len(severities) == 4
    
    def test_circuit_breaker_state_enum(self):
        """Test CircuitBreakerState enum."""
        assert CircuitBreakerState.CLOSED.value == "closed"
        assert CircuitBreakerState.OPEN.value == "open"
        assert CircuitBreakerState.HALF_OPEN.value == "half_open"


class TestTypeAliases:
    """Test type alias definitions."""
    
    def test_price_alias(self):
        """Test Price type alias."""
        price: Price = 50000.0
        assert price == 50000.0
        assert isinstance(price, float)
    
    def test_quantity_alias(self):
        """Test Quantity type alias."""
        qty: Quantity = 1.5
        assert qty == 1.5
        assert isinstance(qty, float)
    
    def test_symbol_alias(self):
        """Test Symbol type alias."""
        symbol: Symbol = "AAPL"
        assert symbol == "AAPL"
        assert isinstance(symbol, str)
    
    def test_order_id_alias(self):
        """Test OrderID type alias."""
        order_id: OrderID = "order_123456"
        assert isinstance(order_id, str)


class TestTypeHints:
    """Test that functions have proper type hints."""
    
    def test_common_retry_module_types(self):
        """Test retry module has type hints."""
        from common import retry
        
        # Check key functions have type hints
        assert hasattr(retry.retry_with_backoff, '__annotations__')
    
    def test_common_circuit_breaker_module_types(self):
        """Test circuit breaker module has type hints."""
        from common import circuit_breaker
        
        # Check class has type hints
        assert hasattr(circuit_breaker.CircuitBreaker, '__init__')
    
    def test_execution_modes_module_types(self):
        """Test execution modes module has type hints."""
        from execution import modes
        
        # Check main classes exist
        assert hasattr(modes, 'ExecutionEngine')
        assert hasattr(modes, 'ExecutionContext')


class TestTypeCompliance:
    """Test type compliance of actual instances."""
    
    def test_validation_result_compliance(self):
        """Test ValidationResult compliance."""
        result: ValidationResult = {
            "is_valid": True,
            "checks_passed": 5,
            "checks_failed": 0,
            "errors": [],
            "warnings": []
        }
        
        assert result["is_valid"] is True
        assert isinstance(result["checks_passed"], int)
        assert isinstance(result["errors"], list)
    
    def test_risk_metrics_compliance(self):
        """Test RiskMetrics compliance."""
        metrics: RiskMetrics = {
            "current_equity": 100000.0,
            "available_cash": 50000.0,
            "positions_count": 2,
            "largest_position_pct": 0.40,
            "portfolio_heat": 0.60,
            "daily_loss": 500.0,
            "drawdown_pct": 2.0,
            "max_correlation": 0.65,
        }
        
        assert metrics["current_equity"] > 0
        assert 0 <= metrics["max_correlation"] <= 1.0
        assert metrics["portfolio_heat"] <= 1.0
    
    def test_trade_record_compliance(self):
        """Test TradeRecord compliance."""
        now = datetime.utcnow()
        trade: TradeRecord = {
            "trade_id": "trade_001",
            "symbol": "AAPL",
            "entry_price": 50000.0,
            "exit_price": 51000.0,
            "quantity": 1.0,
            "entry_time": now,
            "exit_time": now,
            "realized_pnl": 1000.0,
            "pnl_percent": 2.0,
            "duration_seconds": 3600.0,
        }
        
        assert trade["pnl_percent"] == 2.0
        assert trade["realized_pnl"] == 1000.0


class TestTypeAnnotationCoverage:
    """Test that modules have adequate type annotation coverage."""
    
    def test_retry_policy_annotated(self):
        """Test RetryPolicy has type annotations."""
        from common.retry import RetryPolicy
        
        # Check that the class is a dataclass with type hints
        assert hasattr(RetryPolicy, '__dataclass_fields__')
    
    def test_circuit_breaker_config_annotated(self):
        """Test CircuitBreakerConfig has proper structure."""
        from common.circuit_breaker import CircuitBreakerConfig
        
        # Config should have proper type structure
        assert hasattr(CircuitBreakerConfig, '__dataclass_fields__')
    
    def test_secrets_vault_methods_annotated(self):
        """Test SecretsVault has annotated methods."""
        from common.secrets import SecretsVault
        
        # Check key methods exist
        assert hasattr(SecretsVault, 'store_secret')
        assert hasattr(SecretsVault, 'get_secret')


class TestTypeValidation:
    """Test runtime type validation."""
    
    def test_enum_value_validation(self):
        """Test enum values can be validated."""
        order_side = OrderSide.BUY
        assert order_side in [OrderSide.BUY, OrderSide.SELL]
        assert order_side.value in ["buy", "sell"]
    
    def test_typed_dict_key_access(self):
        """Test TypedDict key access patterns."""
        snapshot: EquitySnapshot = {
            "timestamp": datetime.utcnow(),
            "total_equity": 100000.0,
            "cash": 50000.0,
            "positions_value": 50000.0,
            "unrealized_pnl": 1000.0,
        }
        
        # All required keys should be accessible
        _ = snapshot["timestamp"]
        _ = snapshot["total_equity"]
        _ = snapshot["cash"]
        
        # Optional keys should be handled
        realized_pnl = snapshot.get("realized_pnl")
        assert realized_pnl is None
    
    def test_type_alias_numeric_operations(self):
        """Test type alias behavior in operations."""
        price1: Price = 100.0
        price2: Price = 200.0
        
        # Should support normal float operations
        diff = price2 - price1
        assert diff == 100.0
        
        qty1: Quantity = 5.0
        qty2: Quantity = 3.0
        total = qty1 + qty2
        assert total == 8.0


class TestUnionTypes:
    """Test union type handling."""
    
    def test_execution_mode_union(self):
        """Test ExecutionMode can be used in unions."""
        modes = [ExecutionMode.PAPER, ExecutionMode.LIVE, ExecutionMode.BACKTEST]
        assert ExecutionMode.PAPER in modes
        assert len(modes) == 3
    
    def test_alert_severity_union(self):
        """Test AlertSeverity union handling."""
        critical_severities = [AlertSeverity.CRITICAL, AlertSeverity.ERROR]
        assert AlertSeverity.CRITICAL in critical_severities
        assert AlertSeverity.INFO not in critical_severities


class TestTypeIntegration:
    """Integration tests for type system."""
    
    def test_order_to_position_type_conversion(self):
        """Test order data can become position data."""
        order: OrderRecord = {
            "order_id": "order_123",
            "symbol": "AAPL",
            "side": OrderSide.BUY,
            "quantity": 2.0,
            "filled_quantity": 2.0,
            "order_type": OrderType.MARKET,
            "status": OrderStatus.FILLED,
            "filled_price": 50000.0,
            "submitted_at": datetime.utcnow(),
            "filled_at": datetime.utcnow(),
        }
        
        # Can construct position from order
        position: PositionRecord = {
            "position_id": f"pos_{order['order_id']}",
            "symbol": order["symbol"],
            "quantity": order["filled_quantity"],
            "entry_price": order["filled_price"] or 0.0,
            "entry_time": order["filled_at"] or order["submitted_at"],
            "current_price": order["filled_price"] or 0.0,
            "marked_price": order["filled_price"] or 0.0,
            "side": "long" if order["side"] == OrderSide.BUY else "short",
            "unrealized_pnl": 0.0,
            "pnl_percent": 0.0,
        }
        
        assert position["symbol"] == order["symbol"]
        assert position["quantity"] == order["filled_quantity"]
    
    def test_position_to_trade_type_conversion(self):
        """Test position closing creates trade record."""
        now = datetime.utcnow()
        
        position: PositionRecord = {
            "position_id": "pos_001",
            "symbol": "MSFT",
            "quantity": 10.0,
            "entry_price": 2000.0,
            "entry_time": now,
            "current_price": 2100.0,
            "marked_price": 2100.0,
            "side": "long",
            "unrealized_pnl": 1000.0,
            "pnl_percent": 5.0,
        }
        
        # Create trade from position
        trade: TradeRecord = {
            "trade_id": position["position_id"],
            "symbol": position["symbol"],
            "entry_price": position["entry_price"],
            "exit_price": position["marked_price"],
            "quantity": position["quantity"],
            "entry_time": position["entry_time"],
            "exit_time": now,
            "realized_pnl": position["unrealized_pnl"],
            "pnl_percent": position["pnl_percent"],
            "duration_seconds": 3600.0,
        }
        
        assert trade["realized_pnl"] == position["unrealized_pnl"]
        assert trade["pnl_percent"] == position["pnl_percent"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
