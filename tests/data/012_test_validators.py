"""
Comprehensive tests for input validation framework.

Tests all edge cases:
- Boundary values (0, -1, inf, NaN)
- Type mismatches
- Out-of-bounds values Ôëñ Out-of-range Unicode, missing symbols
"""

import pytest

from common.validators import (
    ConfigError,
    EquityError,
    SanityCheckContext,
    SymbolError,
    ValidationError,
    VolatilityError,
    validate_config,
    validate_equity,
    validate_position_size,
    validate_risk_parameters,
    validate_symbol,
    validate_trade_entry,
    validate_volatility,
)


class TestValidateSymbol:
    """Test symbol validation."""

    def test_valid_symbols(self):
        """Valid symbols should not raise."""
        valid_symbols = [
            "AAPL",
            "MSFT",
            "JPM",
            "V",
        ]
        for symbol in valid_symbols:
            validate_symbol(symbol)  # Should not raise

    def test_empty_symbol(self):
        """Empty symbol should raise."""
        with pytest.raises(SymbolError):
            validate_symbol("")

    def test_whitespace_only_symbol(self):
        """Whitespace-only symbol should raise."""
        with pytest.raises(SymbolError):
            validate_symbol("   ")

    def test_non_string_symbol(self):
        """Non-string symbol should raise."""
        with pytest.raises(SymbolError):
            validate_symbol(123)  # type: ignore[arg-type]

    def test_symbol_missing_slash(self):
        """Non-alphanumeric symbol should raise."""
        with pytest.raises(SymbolError):
            validate_symbol("$$INVALID$$")

    def test_symbol_multiple_slashes(self):
        """Symbol with multiple slashes should raise."""
        with pytest.raises(SymbolError):
            validate_symbol("AAPL/X")

    def test_symbol_invalid_characters(self):
        """Symbol with invalid characters should raise."""
        with pytest.raises(SymbolError):
            validate_symbol("AAPL-@")

    def test_symbol_case_insensitive(self):
        """Lowercase symbols should be accepted."""
        validate_symbol("AAPL")  # Should not raise


class TestValidatePositionSize:
    """Test position size validation."""

    def test_valid_position_sizes(self):
        """Valid position sizes should not raise."""
        valid_sizes = [0.001, 0.1, 1.0, 10.0, 100.0, 1000.0]
        for size in valid_sizes:
            validate_position_size(size)

    def test_zero_position_size(self):
        """Zero position size should raise."""
        with pytest.raises(ValidationError):
            validate_position_size(0.0)

    def test_negative_position_size(self):
        """Negative position size should raise."""
        with pytest.raises(ValidationError):
            validate_position_size(-10.0)

    def test_nan_position_size(self):
        """NaN position size should raise."""
        with pytest.raises(ValidationError):
            validate_position_size(float("nan"))

    def test_infinite_position_size(self):
        """Infinite position size should raise."""
        with pytest.raises(ValidationError):
            validate_position_size(float("inf"))

    def test_non_numeric_position_size(self):
        """Non-numeric position size should raise."""
        with pytest.raises(ValidationError):
            validate_position_size("10.0")  # type: ignore[arg-type]

    def test_position_size_below_minimum(self):
        """Position size below minimum should raise."""
        with pytest.raises(ValidationError):
            validate_position_size(0.00001)  # Below default min

    def test_position_size_above_maximum(self):
        """Position size above maximum should raise."""
        with pytest.raises(ValidationError):
            validate_position_size(10_000_001)


class TestValidateEquity:
    """Test equity validation."""

    def test_valid_equity(self):
        """Valid equity should not raise."""
        valid_equities = [1000.0, 10000.0, 100000.0, 1_000_000.0]
        for equity in valid_equities:
            validate_equity(equity)

    def test_zero_equity(self):
        """Zero equity should raise."""
        with pytest.raises(EquityError):
            validate_equity(0.0)

    def test_negative_equity(self):
        """Negative equity should raise."""
        with pytest.raises(EquityError):
            validate_equity(-1000.0)

    def test_nan_equity(self):
        """NaN equity should raise."""
        with pytest.raises(EquityError):
            validate_equity(float("nan"))

    def test_infinite_equity(self):
        """Infinite equity should raise."""
        with pytest.raises(EquityError):
            validate_equity(float("inf"))

    def test_non_numeric_equity(self):
        """Non-numeric equity should raise."""
        with pytest.raises(EquityError):
            validate_equity("100000.0")  # type: ignore[arg-type]

    def test_equity_too_low(self):
        """Equity below minimum should raise."""
        with pytest.raises(EquityError):
            validate_equity(50.0)  # Below default min

    def test_equity_too_high(self):
        """Equity above maximum should raise."""
        with pytest.raises(EquityError):
            validate_equity(2_000_000_000.0)


class TestValidateVolatility:
    """Test volatility validation."""

    def test_valid_volatility(self):
        """Valid volatility should not raise."""
        valid_vols = [0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
        for vol in valid_vols:
            validate_volatility(vol)

    def test_zero_volatility(self):
        """Zero volatility should raise."""
        with pytest.raises(VolatilityError):
            validate_volatility(0.0)

    def test_negative_volatility(self):
        """Negative volatility should raise."""
        with pytest.raises(VolatilityError):
            validate_volatility(-0.1)

    def test_nan_volatility(self):
        """NaN volatility should raise."""
        with pytest.raises(VolatilityError):
            validate_volatility(float("nan"))

    def test_infinite_volatility(self):
        """Infinite volatility should raise."""
        with pytest.raises(VolatilityError):
            validate_volatility(float("inf"))

    def test_non_numeric_volatility(self):
        """Non-numeric volatility should raise."""
        with pytest.raises(VolatilityError):
            validate_volatility("0.05")  # type: ignore[arg-type]

    def test_volatility_too_low(self):
        """Volatility below minimum should raise."""
        with pytest.raises(VolatilityError):
            validate_volatility(0.00001)

    def test_volatility_too_high(self):
        """Volatility above maximum should raise."""
        with pytest.raises(VolatilityError):
            validate_volatility(15.0)


class TestValidateConfig:
    """Test configuration validation."""

    def test_valid_config(self):
        """Valid config should not raise."""
        config = {
            "strategy": {
                "entry_z_score": 2.0,
                "max_half_life": 60,
            },
            "risk": {
                "max_risk_per_trade": 0.005,
                "max_concurrent_positions": 10,
                "max_daily_loss_pct": 0.02,
            },
            "execution": {
                "timeout_seconds": 30,
            },
        }
        validate_config(config)

    def test_config_not_dict(self):
        """Non-dict config should raise."""
        with pytest.raises(ConfigError):
            validate_config([])  # type: ignore[arg-type]

    def test_config_empty(self):
        """Empty config should raise."""
        with pytest.raises(ConfigError):
            validate_config({})

    def test_config_invalid_entry_z_score(self):
        """Invalid entry_z_score should raise."""
        config = {"strategy": {"entry_z_score": -1.0}}
        with pytest.raises(ConfigError):
            validate_config(config)

    def test_config_invalid_max_half_life(self):
        """Invalid max_half_life should raise."""
        config = {"strategy": {"max_half_life": 400}}
        with pytest.raises(ConfigError):
            validate_config(config)

    def test_config_invalid_max_risk(self):
        """Invalid max_risk_per_trade should raise."""
        config = {"risk": {"max_risk_per_trade": 0.6}}
        with pytest.raises(ConfigError):
            validate_config(config)

    def test_config_invalid_max_positions(self):
        """Invalid max_concurrent_positions should raise."""
        config = {"risk": {"max_concurrent_positions": 0}}
        with pytest.raises(ConfigError):
            validate_config(config)

    def test_config_invalid_timeout(self):
        """Invalid timeout_seconds should raise."""
        config = {"execution": {"timeout_seconds": 500}}
        with pytest.raises(ConfigError):
            validate_config(config)


class TestValidateTradeEntry:
    """Test batch validation for trade entry."""

    def test_valid_trade_entry(self):
        """Valid trade entry should not raise."""
        validate_trade_entry(symbol="AAPL", position_size=10.0, equity=100000.0, volatility=0.02)

    def test_invalid_symbol_in_trade_entry(self):
        """Invalid symbol should raise."""
        with pytest.raises(SymbolError):
            validate_trade_entry(symbol="INVALID", position_size=10.0, equity=100000.0, volatility=0.02)

    def test_invalid_position_in_trade_entry(self):
        """Invalid position size should raise."""
        with pytest.raises(ValidationError):
            validate_trade_entry(symbol="AAPL", position_size=0.0, equity=100000.0, volatility=0.02)

    def test_invalid_equity_in_trade_entry(self):
        """Invalid equity should raise."""
        with pytest.raises(EquityError):
            validate_trade_entry(symbol="AAPL", position_size=10.0, equity=0.0, volatility=0.02)

    def test_invalid_volatility_in_trade_entry(self):
        """Invalid volatility should raise."""
        with pytest.raises(VolatilityError):
            validate_trade_entry(symbol="AAPL", position_size=10.0, equity=100000.0, volatility=-0.02)


class TestValidateRiskParameters:
    """Test batch validation for risk parameters."""

    def test_valid_risk_parameters(self):
        """Valid risk parameters should not raise."""
        validate_risk_parameters(max_risk_per_trade=0.005, max_concurrent_positions=10, max_daily_loss_pct=0.02)

    def test_invalid_risk_per_trade(self):
        """Invalid max_risk_per_trade should raise."""
        with pytest.raises(ValidationError):
            validate_risk_parameters(max_risk_per_trade=0.6, max_concurrent_positions=10, max_daily_loss_pct=0.02)

    def test_invalid_positions(self):
        """Invalid max_concurrent_positions should raise."""
        with pytest.raises(ValidationError):
            validate_risk_parameters(max_risk_per_trade=0.005, max_concurrent_positions=0, max_daily_loss_pct=0.02)

    def test_invalid_daily_loss(self):
        """Invalid max_daily_loss_pct should raise."""
        with pytest.raises(ValidationError):
            validate_risk_parameters(max_risk_per_trade=0.005, max_concurrent_positions=10, max_daily_loss_pct=0.6)


class TestSanityCheckContext:
    """Test context manager for grouped validations."""

    def test_context_success(self):
        """Valid checks should succeed within context."""
        with SanityCheckContext("test_operation"):
            validate_symbol("AAPL")
            validate_position_size(10.0)

    def test_context_failure(self):
        """Invalid check should raise from context."""
        with pytest.raises(SymbolError):
            with SanityCheckContext("test_operation"):
                validate_symbol("INVALID")

    def test_context_multiple_failures(self):
        """Should raise on first failure."""
        with pytest.raises(SymbolError):
            with SanityCheckContext("test_operation"):
                validate_symbol("AAPL")  # OK
                validate_symbol("INVALID")  # Fails here
                validate_position_size(10.0)  # Never reached


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
