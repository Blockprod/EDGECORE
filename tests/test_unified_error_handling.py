"""
Tests for unified error handling system (Phase 2 Feature 1).

Tests:
- Error taxonomy and classification
- Error handler behavior based on category
- Decorator with retries and backoff
- Integration with main.py data loading
"""

import pytest
import time
from unittest.mock import Mock, patch, call

from common.errors import (
    ErrorCategory,
    TradingError,
    DataError,
    DataValidationError,
    BrokerError,
    BrokerConnectionError,
    InsufficientBalanceError,
    StrategyError,
    ConfigError,
    classify_exception
)
from common.error_handler import handle_error, with_error_handling


class TestErrorTaxonomy:
    """Tests for error classification and hierarchy."""
    
    def test_trading_error_base_class(self):
        """✓ TradingError stores message, category, original error."""
        original = ValueError("original error")
        error = TradingError(
            "Something went wrong",
            ErrorCategory.RETRYABLE,
            original
        )
        
        assert error.message == "Something went wrong"
        assert error.category == ErrorCategory.RETRYABLE
        assert error.original_error == original
    
    def test_data_error_defaults_transient(self):
        """✓ DataError defaults to TRANSIENT category."""
        error = DataError("Data load failed")
        assert error.category == ErrorCategory.TRANSIENT
    
    def test_data_validation_error_is_transient(self):
        """✓ DataValidationError is TRANSIENT (retry network)."""
        error = DataValidationError("Invalid OHLCV")
        assert error.category == ErrorCategory.TRANSIENT
    
    def test_broker_connection_error_is_transient(self):
        """✓ BrokerConnectionError is TRANSIENT (network issue)."""
        error = BrokerConnectionError("Cannot connect")
        assert error.category == ErrorCategory.TRANSIENT
    
    def test_insufficient_balance_error_is_non_retryable(self):
        """✓ InsufficientBalanceError is NON_RETRYABLE (operator action)."""
        error = InsufficientBalanceError("Not enough balance")
        assert error.category == ErrorCategory.NON_RETRYABLE
    
    def test_strategy_error_is_fatal(self):
        """✓ StrategyError is FATAL (logic error)."""
        error = StrategyError("Bad signal logic")
        assert error.category == ErrorCategory.FATAL
    
    def test_config_error_is_fatal(self):
        """✓ ConfigError is FATAL (logic error)."""
        error = ConfigError("Missing env var")
        assert error.category == ErrorCategory.FATAL


class TestExceptionClassifier:
    """Tests for classify_exception helper."""
    
    def test_classify_timeout_as_transient(self):
        """✓ TimeoutError → TRANSIENT."""
        category = classify_exception(TimeoutError("timeout"))
        assert category == ErrorCategory.TRANSIENT
    
    def test_classify_connection_error_as_transient(self):
        """✓ ConnectionError → TRANSIENT."""
        category = classify_exception(ConnectionError("no connection"))
        assert category == ErrorCategory.TRANSIENT
    
    def test_classify_key_error_as_fatal(self):
        """✓ KeyError (missing field) → FATAL (logic error)."""
        category = classify_exception(KeyError("missing_field"))
        assert category == ErrorCategory.FATAL
    
    def test_classify_value_error_as_fatal(self):
        """✓ ValueError (invalid value) → FATAL (logic error)."""
        category = classify_exception(ValueError("invalid value"))
        assert category == ErrorCategory.FATAL
    
    def test_classify_generic_as_retryable(self):
        """✓ Unknown exception → RETRYABLE (default safe)."""
        category = classify_exception(Exception("unknown"))
        assert category == ErrorCategory.RETRYABLE


class TestErrorHandler:
    """Tests for unified error handling function."""
    
    @patch('common.error_handler.logger')
    def test_handle_transient_error_logs_warning(self, mock_logger):
        """✓ TRANSIENT errors logged as WARNING."""
        error = DataError("Network timeout")
        handle_error(error, context="load_data")
        
        mock_logger.warning.assert_called_once()
        # Verify first positional arg is the log message
        log_message = mock_logger.warning.call_args[0][0]
        assert "TRANSIENT_ERROR" in log_message
    
    @patch('common.error_handler.logger')
    def test_handle_retryable_error_logs_error(self, mock_logger):
        """✓ RETRYABLE errors logged as ERROR."""
        error = TradingError("API throttled", ErrorCategory.RETRYABLE)
        handle_error(error, context="submit_order")
        
        mock_logger.error.assert_called()
    
    @patch('common.error_handler.logger')
    def test_handle_non_retryable_error_logs_critical(self, mock_logger):
        """✓ NON_RETRYABLE errors logged as CRITICAL."""
        error = InsufficientBalanceError("Insufficient funds")
        handle_error(error, context="place_trade")
        
        mock_logger.critical.assert_called()
    
    @patch('common.error_handler.logger')
    def test_handle_fatal_error_raises(self, mock_logger):
        """✓ FATAL errors are re-raised."""
        error = StrategyError("Invalid logic")
        
        with pytest.raises(TradingError):
            handle_error(error, context="validate_signal")
    
    @patch('common.error_handler.logger')
    def test_handle_error_with_context(self, mock_logger):
        """✓ Error context is logged."""
        error = DataError("Bad data")
        handle_error(error, context="load_BTC/USDT")
        
        # Verify context was logged
        mock_logger.warning.assert_called()
        call_kwargs = mock_logger.warning.call_args[1]
        assert "load_BTC/USDT" in str(call_kwargs)


class TestErrorHandlingDecorator:
    """Tests for @with_error_handling decorator."""
    
    def test_decorator_succeeds_first_attempt(self):
        """✓ Successful function doesn't retry."""
        call_count = 0
        
        @with_error_handling(max_retries=3)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = success_func()
        assert result == "success"
        assert call_count == 1  # Only called once
    
    def test_decorator_retries_transient_errors(self):
        """✓ TRANSIENT errors trigger retries."""
        call_count = 0
        
        @with_error_handling(
            category=ErrorCategory.TRANSIENT,
            max_retries=3,
            backoff_base=0.1  # Fast backoff for testing
        )
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("timeout")
            return "success"
        
        result = flaky_func()
        assert result == "success"
        assert call_count == 3  # Called 3 times before success
    
    def test_decorator_stops_on_fatal_errors(self):
        """✓ FATAL errors are not retried."""
        call_count = 0
        
        @with_error_handling(max_retries=3)
        def fatal_func():
            nonlocal call_count
            call_count += 1
            raise StrategyError("Bad logic")  # FATAL
        
        with pytest.raises(TradingError):
            fatal_func()
        
        assert call_count == 1  # Called only once (no retry)
    
    def test_decorator_stops_on_non_retryable_errors(self):
        """✓ NON_RETRYABLE errors stop immediately."""
        call_count = 0
        
        @with_error_handling(max_retries=3)
        def non_retryable_func():
            nonlocal call_count
            call_count += 1
            raise InsufficientBalanceError("Not enough funds")
        
        with pytest.raises(InsufficientBalanceError):
            non_retryable_func()
        
        assert call_count == 1  # No retry
    
    def test_decorator_respects_max_retries(self):
        """✓ Stops after max_retries attempts."""
        call_count = 0
        
        @with_error_handling(
            category=ErrorCategory.TRANSIENT,
            max_retries=2,
            backoff_base=0.01
        )
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("timeout")
        
        with pytest.raises(TimeoutError):
            always_fails()
        
        assert call_count == 2  # Called twice (max_retries=2)
    
    @patch('common.error_handler.logger')
    def test_decorator_logs_retries(self, mock_logger):
        """✓ Retries are logged with backoff info."""
        @with_error_handling(
            max_retries=2,
            backoff_base=0.01,
            context_prefix="test_"
        )
        def retry_func():
            raise TimeoutError("timeout")
        
        with pytest.raises(TimeoutError):
            retry_func()
        
        # Should log a retry message
        assert any(
            "RETRY_AFTER_BACKOFF" in str(call)
            for call in mock_logger.info.call_args_list
        )
    
    def test_decorator_with_function_args(self):
        """✓ Decorator preserves function arguments."""
        @with_error_handling()
        def add(a, b):
            return a + b
        
        result = add(2, 3)
        assert result == 5


class TestDataLoadingErrorHandling:
    """Tests for error handling applied to data loading."""
    
    def test_data_error_raised_on_empty_data(self):
        """✓ Empty data raises DataError with appropriate category."""
        from main import _load_market_data_for_symbols
        
        mock_loader = Mock()
        mock_loader.load_ccxt_data.return_value = None  # No data
        
        mock_settings = Mock()
        mock_settings.execution.exchange = "binance"
        
        with pytest.raises(DataError) as exc_info:
            _load_market_data_for_symbols(["BTC/USDT"], mock_loader, mock_settings)
        
        # DataError should be TRANSIENT (can retry) or RETRYABLE
        assert exc_info.value.category in [ErrorCategory.TRANSIENT, ErrorCategory.RETRYABLE]
    
    def test_data_load_with_partial_failure(self):
        """✓ Partial data load logs warning but succeeds."""
        from main import _load_market_data_for_symbols
        import pandas as pd
        from datetime import datetime
        
        mock_loader = Mock()
        
        # First symbol succeeds, second fails
        # Create DataFrame with proper timestamps as index
        timestamps = pd.date_range(start='2024-01-01', periods=2, freq='h')
        btc_df = pd.DataFrame({
            'open': [45000.0, 45100.0],
            'high': [45200.0, 45300.0],
            'low': [44900.0, 44950.0],
            'close': [45000.0, 45100.0],
            'volume': [100.0, 200.0]
        }, index=timestamps)
        
        def load_side_effect(exchange, symbol, *args, **kwargs):
            if symbol == "BTC/USDT":
                return btc_df
            else:
                raise Exception("Network error")
        
        mock_loader.load_ccxt_data.side_effect = load_side_effect
        
        mock_settings = Mock()
        mock_settings.execution.exchange = "binance"
        
        # Should succeed with partial data
        prices = _load_market_data_for_symbols(
            ["BTC/USDT", "ETH/USDT"],
            mock_loader,
            mock_settings
        )
        
        assert "BTC/USDT" in prices
        assert len(prices) == 1  # Only BTC loaded


class TestRealWorldScenarios:
    """Integration tests for realistic error scenarios."""
    
    def test_transient_network_error_retries(self):
        """Scenario: Network timeout → retry → success."""
        attempt = 0
        
        @with_error_handling(
            category=ErrorCategory.TRANSIENT,
            max_retries=3,
            backoff_base=0.01
        )
        def load_with_network_retry():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise TimeoutError("network timeout")
            return {"BTC/USDT": 45000.0}
        
        result = load_with_network_retry()
        assert result == {"BTC/USDT": 45000.0}
        assert attempt == 3
    
    def test_insufficient_balance_fails_fast(self):
        """Scenario: Insufficient balance → fail fast (no retry)."""
        attempt = 0
        
        @with_error_handling(max_retries=3)
        def submit_order_insufficient_balance():
            nonlocal attempt
            attempt += 1
            raise InsufficientBalanceError("Account has $10, need $50")
        
        with pytest.raises(InsufficientBalanceError):
            submit_order_insufficient_balance()
        
        assert attempt == 1  # Failed immediately, no retry


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
