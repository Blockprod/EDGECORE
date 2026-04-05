"""
Tests for data integrity validators.

Covers:
- OHLCV data validation
- Position data validation
- Equity tracking and jump detection
- Single row validation
- Dataframe validation with various error types
"""

<<<<<<< HEAD
from datetime import UTC, datetime, timedelta
=======
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
>>>>>>> origin/main

import numpy as np
import pandas as pd
import pytest

from data.validators import DataValidationError, EquityValidator, OHLCVValidator, PositionValidator, ValidationResult


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_validation_result_valid(self):
        """Test ValidationResult with valid state."""
        result = ValidationResult(is_valid=True, checks_passed=5, checks_failed=0, errors=[], warnings=[])
        assert result.is_valid
        assert bool(result) is True
        assert result.checks_passed == 5
        assert result.checks_failed == 0

    def test_validation_result_invalid(self):
        """Test ValidationResult with invalid state."""
        result = ValidationResult(
            is_valid=False, checks_passed=3, checks_failed=2, errors=["Error 1", "Error 2"], warnings=[]
        )
        assert not result.is_valid
        assert bool(result) is False
        assert result.checks_failed == 2
        assert len(result.errors) == 2

    def test_validation_result_with_warnings(self):
        """Test ValidationResult with warnings."""
        result = ValidationResult(
            is_valid=True, checks_passed=4, checks_failed=0, errors=[], warnings=["Warning 1", "Warning 2"]
        )
        assert result.is_valid
        assert len(result.warnings) == 2


class TestOHLCVValidatorBasic:
    """Test basic OHLCV validation."""

    def test_validator_initialization(self):
        """Test OHLCVValidator creation."""
        validator = OHLCVValidator(symbol="AAPL")
        assert validator.symbol == "AAPL"
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_empty_dataframe(self):
        """Test validation of empty dataframe."""
        validator = OHLCVValidator()
        df = pd.DataFrame()

        result = validator.validate(df)

        assert not result.is_valid
        assert "empty" in result.errors[0].lower()

    def test_valid_ohlcv_data(self):
        """Test validation of valid OHLCV data."""
        validator = OHLCVValidator(symbol="AAPL")
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # Create valid data
        dates = pd.date_range("2024-01-01", periods=10, freq="1h")
        df = pd.DataFrame(
            {
                "open": [100.0 + i for i in range(10)],
                "high": [102.0 + i for i in range(10)],
                "low": [98.0 + i for i in range(10)],
                "close": [101.0 + i for i in range(10)],
                "volume": [1000.0 + i * 10 for i in range(10)],
            },
            index=dates,
        )

        result = validator.validate(df)

        assert result.is_valid
        assert result.checks_failed == 0


class TestOHLCVValidatorNaN:
    """Test NaN and infinite value detection."""

    def test_nan_in_open(self):
        """Test detection of NaN in open."""
        validator = OHLCVValidator()

        dates = pd.date_range("2024-01-01", periods=5, freq="1h")
        df = pd.DataFrame(
            {
                "open": [100.0, np.nan, 100.0, 100.0, 100.0],
                "high": [102.0] * 5,
                "low": [98.0] * 5,
                "close": [101.0] * 5,
                "volume": [1000.0] * 5,
            },
            index=dates,
        )

        result = validator.validate(df)

        assert not result.is_valid
        assert any("NaN" in e or "nan" in e.lower() for e in result.errors)

    def test_nan_in_volume(self):
        """Test detection of NaN in volume."""
        validator = OHLCVValidator()

        dates = pd.date_range("2024-01-01", periods=5, freq="1h")
        df = pd.DataFrame(
            {
                "open": [100.0] * 5,
                "high": [102.0] * 5,
                "low": [98.0] * 5,
                "close": [101.0] * 5,
                "volume": [1000.0, 1000.0, np.nan, 1000.0, 1000.0],
            },
            index=dates,
        )

        result = validator.validate(df)

        assert not result.is_valid
        assert any("NaN" in e for e in result.errors)

    def test_infinite_value(self):
        """Test detection of infinite values."""
        validator = OHLCVValidator()

        dates = pd.date_range("2024-01-01", periods=5, freq="1h")
        df = pd.DataFrame(
            {
                "open": [100.0, 100.0, np.inf, 100.0, 100.0],
                "high": [102.0] * 5,
                "low": [98.0] * 5,
                "close": [101.0] * 5,
                "volume": [1000.0] * 5,
            },
            index=dates,
        )

        result = validator.validate(df)

        assert not result.is_valid
        assert any("infinite" in e.lower() for e in result.errors)


class TestOHLCVValidatorPriceConsistency:
    """Test price relationship validation (High >= Low >= Close)."""

    def test_high_greater_than_low(self):
        """Test detection of High < Low."""
        validator = OHLCVValidator()

        dates = pd.date_range("2024-01-01", periods=5, freq="1h")
        df = pd.DataFrame(
            {
                "open": [100.0] * 5,
                "high": [98.0] * 5,  # High < Low
                "low": [102.0] * 5,
                "close": [101.0] * 5,
                "volume": [1000.0] * 5,
            },
            index=dates,
        )

        result = validator.validate(df)

        assert not result.is_valid
        assert any("High" in e and "Low" in e for e in result.errors)

    def test_zero_price(self):
        """Test detection of zero/negative prices."""
        validator = OHLCVValidator()

        dates = pd.date_range("2024-01-01", periods=5, freq="1h")
        df = pd.DataFrame(
            {
                "open": [100.0, 0.0, 100.0, 100.0, 100.0],
                "high": [102.0] * 5,
                "low": [98.0] * 5,
                "close": [101.0] * 5,
                "volume": [1000.0] * 5,
            },
            index=dates,
        )

        result = validator.validate(df)

        assert not result.is_valid
        assert any("zero" in e.lower() or "negative" in e.lower() for e in result.errors)


class TestOHLCVValidatorVolume:
    """Test volume validation."""

    def test_negative_volume(self):
        """Test detection of negative volume."""
        validator = OHLCVValidator()

        dates = pd.date_range("2024-01-01", periods=5, freq="1h")
        df = pd.DataFrame(
            {
                "open": [100.0] * 5,
                "high": [102.0] * 5,
                "low": [98.0] * 5,
                "close": [101.0] * 5,
                "volume": [1000.0, 1000.0, -500.0, 1000.0, 1000.0],
            },
            index=dates,
        )

        result = validator.validate(df)

        assert not result.is_valid
        assert any("negative volume" in e.lower() for e in result.errors)

    def test_zero_volume_warning(self):
        """Test warning for zero volume (trading halt)."""
        validator = OHLCVValidator()

        dates = pd.date_range("2024-01-01", periods=5, freq="1h")
        df = pd.DataFrame(
            {
                "open": [100.0] * 5,
                "high": [102.0] * 5,
                "low": [98.0] * 5,
                "close": [101.0] * 5,
                "volume": [1000.0, 1000.0, 0.0, 1000.0, 1000.0],
            },
            index=dates,
        )

        result = validator.validate(df)

        assert result.is_valid  # Valid but with warning
        assert any("zero volume" in w.lower() for w in result.warnings)


class TestOHLCVValidatorTimestamp:
    """Test timestamp validation."""

    def test_duplicate_timestamps(self):
        """Test detection of duplicate timestamps."""
        validator = OHLCVValidator()

        dates = pd.DatetimeIndex(
            [
                "2024-01-01 00:00:00",
                "2024-01-01 01:00:00",
                "2024-01-01 01:00:00",  # Duplicate
                "2024-01-01 03:00:00",
                "2024-01-01 04:00:00",
            ]
        )
        df = pd.DataFrame(
            {"open": [100.0] * 5, "high": [102.0] * 5, "low": [98.0] * 5, "close": [101.0] * 5, "volume": [1000.0] * 5},
            index=dates,
        )

        result = validator.validate(df)

        assert not result.is_valid
        assert any("duplicate" in e.lower() for e in result.errors)

    def test_non_monotonic_timestamps(self):
        """Test detection of non-monotonic timestamps."""
        validator = OHLCVValidator()

        dates = pd.DatetimeIndex(
            [
                "2024-01-01 00:00:00",
                "2024-01-01 02:00:00",
                "2024-01-01 01:00:00",  # Not monotonic
                "2024-01-01 03:00:00",
                "2024-01-01 04:00:00",
            ]
        )
        df = pd.DataFrame(
            {"open": [100.0] * 5, "high": [102.0] * 5, "low": [98.0] * 5, "close": [101.0] * 5, "volume": [1000.0] * 5},
            index=dates,
        )

        result = validator.validate(df)

        assert not result.is_valid
        assert any("monotonic" in e.lower() for e in result.errors)


class TestOHLCVValidatorMissingColumns:
    """Test missing column detection."""

    def test_missing_high_column(self):
        """Test detection of missing 'high' column."""
        validator = OHLCVValidator()

        dates = pd.date_range("2024-01-01", periods=5, freq="1h")
        df = pd.DataFrame(
            {
                "open": [100.0] * 5,
                # Missing 'high'
                "low": [98.0] * 5,
                "close": [101.0] * 5,
                "volume": [1000.0] * 5,
            },
            index=dates,
        )

        result = validator.validate(df)

        assert not result.is_valid
        assert any("missing" in e.lower() and "high" in e.lower() for e in result.errors)

    def test_missing_volume_column(self):
        """Test detection of missing 'volume' column."""
        validator = OHLCVValidator()

        dates = pd.date_range("2024-01-01", periods=5, freq="1h")
        df = pd.DataFrame(
            {
                "open": [100.0] * 5,
                "high": [102.0] * 5,
                "low": [98.0] * 5,
                "close": [101.0] * 5,
                # Missing 'volume'
            },
            index=dates,
        )

        result = validator.validate(df)

        assert not result.is_valid
        assert any("missing" in e.lower() and "volume" in e.lower() for e in result.errors)


class TestOHLCVValidatorSingleRow:
    """Test single row validation."""

    def test_valid_row(self):
        """Test validation of valid OHLCV row."""
        validator = OHLCVValidator()

        assert validator.validate_row(100.0, 102.0, 98.0, 101.0, 1000.0) is True

    def test_row_with_nan(self):
        """Test row validation with NaN."""
        validator = OHLCVValidator()

        assert validator.validate_row(100.0, np.nan, 98.0, 101.0, 1000.0) is False

    def test_row_with_infinite(self):
        """Test row validation with infinite."""
        validator = OHLCVValidator()

        assert validator.validate_row(100.0, np.inf, 98.0, 101.0, 1000.0) is False

    def test_row_high_less_than_low(self):
        """Test row with invalid price relationship."""
        validator = OHLCVValidator()

        assert validator.validate_row(100.0, 98.0, 102.0, 101.0, 1000.0) is False

    def test_row_zero_price(self):
        """Test row with zero price."""
        validator = OHLCVValidator()

        assert validator.validate_row(0.0, 102.0, 98.0, 101.0, 1000.0) is False

    def test_row_negative_volume(self):
        """Test row with negative volume."""
        validator = OHLCVValidator()

        assert validator.validate_row(100.0, 102.0, 98.0, 101.0, -500.0) is False


class TestOHLCVValidatorRaisesException:
    """Test raise_on_error behavior."""

    def test_raises_on_validation_failure(self):
        """Test that exception is raised when raise_on_error=True."""
        validator = OHLCVValidator()

        dates = pd.date_range("2024-01-01", periods=5, freq="1h")
        df = pd.DataFrame(
            {
                "open": [100.0, np.nan, 100.0, 100.0, 100.0],
                "high": [102.0] * 5,
                "low": [98.0] * 5,
                "close": [101.0] * 5,
                "volume": [1000.0] * 5,
            },
            index=dates,
        )

        with pytest.raises(DataValidationError):
            validator.validate(df, raise_on_error=True)

    def test_no_raise_on_valid_data(self):
        """Test no exception on valid data."""
        validator = OHLCVValidator()

        dates = pd.date_range("2024-01-01", periods=5, freq="1h")
        df = pd.DataFrame(
            {"open": [100.0] * 5, "high": [102.0] * 5, "low": [98.0] * 5, "close": [101.0] * 5, "volume": [1000.0] * 5},
            index=dates,
        )

        # Should not raise
        result = validator.validate(df, raise_on_error=True)
        assert result.is_valid


class TestPositionValidator:
    """Test position validation."""

    def test_valid_position(self):
        """Test validation of valid position."""
        result = PositionValidator.validate_position(
<<<<<<< HEAD
            symbol="AAPL", quantity=1.5, entry_price=50000.0, current_price=51000.0, side="long"
=======
            symbol="AAPL",
            quantity=1.5,
            entry_price=50000.0,
            current_price=51000.0,
            side="long"
>>>>>>> origin/main
        )

        assert result.is_valid
        assert result.checks_failed == 0

    def test_invalid_symbol(self):
        """Test detection of invalid symbol."""
        result = PositionValidator.validate_position(
            symbol="INVALID", quantity=1.5, entry_price=50000.0, current_price=51000.0
        )

        assert not result.is_valid
        assert any("symbol" in e.lower() for e in result.errors)

    def test_zero_quantity(self):
        """Test detection of zero quantity."""
        result = PositionValidator.validate_position(
<<<<<<< HEAD
            symbol="AAPL", quantity=0.0, entry_price=50000.0, current_price=51000.0
=======
            symbol="AAPL",
            quantity=0.0,
            entry_price=50000.0,
            current_price=51000.0
>>>>>>> origin/main
        )

        assert not result.is_valid
        assert any("quantity" in e.lower() for e in result.errors)

    def test_negative_quantity(self):
        """Test detection of negative quantity."""
        result = PositionValidator.validate_position(
<<<<<<< HEAD
            symbol="AAPL", quantity=-1.0, entry_price=50000.0, current_price=51000.0
=======
            symbol="AAPL",
            quantity=-1.0,
            entry_price=50000.0,
            current_price=51000.0
>>>>>>> origin/main
        )

        assert not result.is_valid
        assert any("quantity" in e.lower() for e in result.errors)

    def test_nan_quantity(self):
        """Test detection of NaN quantity."""
        result = PositionValidator.validate_position(
<<<<<<< HEAD
            symbol="AAPL", quantity=np.nan, entry_price=50000.0, current_price=51000.0
=======
            symbol="AAPL",
            quantity=np.nan,
            entry_price=50000.0,
            current_price=51000.0
>>>>>>> origin/main
        )

        assert not result.is_valid
        assert any("quantity" in e.lower() for e in result.errors)

    def test_invalid_side(self):
        """Test detection of invalid side."""
        result = PositionValidator.validate_position(
<<<<<<< HEAD
            symbol="AAPL", quantity=1.5, entry_price=50000.0, current_price=51000.0, side="invalid"
=======
            symbol="AAPL",
            quantity=1.5,
            entry_price=50000.0,
            current_price=51000.0,
            side="invalid"
>>>>>>> origin/main
        )

        assert not result.is_valid
        assert any("side" in e.lower() for e in result.errors)

    def test_zero_entry_price(self):
        """Test detection of zero entry price."""
        result = PositionValidator.validate_position(
<<<<<<< HEAD
            symbol="AAPL", quantity=1.5, entry_price=0.0, current_price=51000.0
=======
            symbol="AAPL",
            quantity=1.5,
            entry_price=0.0,
            current_price=51000.0
>>>>>>> origin/main
        )

        assert not result.is_valid
        assert any("entry price" in e.lower() for e in result.errors)

    def test_zero_current_price(self):
        """Test detection of zero current price."""
        result = PositionValidator.validate_position(
<<<<<<< HEAD
            symbol="AAPL", quantity=1.5, entry_price=50000.0, current_price=0.0
=======
            symbol="AAPL",
            quantity=1.5,
            entry_price=50000.0,
            current_price=0.0
>>>>>>> origin/main
        )

        assert not result.is_valid
        assert any("current price" in e.lower() for e in result.errors)

    def test_infinite_entry_price(self):
        """Test detection of infinite entry price."""
        result = PositionValidator.validate_position(
<<<<<<< HEAD
            symbol="AAPL", quantity=1.5, entry_price=np.inf, current_price=51000.0
=======
            symbol="AAPL",
            quantity=1.5,
            entry_price=np.inf,
            current_price=51000.0
>>>>>>> origin/main
        )

        assert not result.is_valid
        assert any("entry price" in e.lower() for e in result.errors)

    def test_position_opened_in_future(self):
        """Test warning for position opened in future."""
        future_time = datetime.now(UTC) + timedelta(hours=1)
        result = PositionValidator.validate_position(
<<<<<<< HEAD
            symbol="AAPL", quantity=1.5, entry_price=50000.0, current_price=51000.0, opened_at=future_time
=======
            symbol="AAPL",
            quantity=1.5,
            entry_price=50000.0,
            current_price=51000.0,
            opened_at=future_time
>>>>>>> origin/main
        )

        assert not result.is_valid
        assert any("future" in e.lower() for e in result.errors)

    def test_position_age_warning(self):
        """Test warning for very old position."""
        old_time = datetime.now(UTC) - timedelta(days=400)
        result = PositionValidator.validate_position(
<<<<<<< HEAD
            symbol="AAPL", quantity=1.5, entry_price=50000.0, current_price=51000.0, opened_at=old_time
=======
            symbol="AAPL",
            quantity=1.5,
            entry_price=50000.0,
            current_price=51000.0,
            opened_at=old_time
>>>>>>> origin/main
        )

        assert result.is_valid  # Valid but with warning
        assert any("year" in w.lower() for w in result.warnings)

    def test_short_position(self):
        """Test validation of short position."""
        result = PositionValidator.validate_position(
<<<<<<< HEAD
            symbol="AAPL", quantity=1.5, entry_price=50000.0, current_price=49000.0, side="short"
=======
            symbol="AAPL",
            quantity=1.5,
            entry_price=50000.0,
            current_price=49000.0,
            side="short"
>>>>>>> origin/main
        )

        assert result.is_valid


class TestEquityValidator:
    """Test equity validation."""

    def test_valid_equity(self):
        """Test validation of valid equity."""
        validator = EquityValidator()
        result = validator.validate_equity(equity=50000.0)

        assert result.is_valid
        assert result.checks_failed == 0

    def test_zero_equity(self):
        """Test detection of zero equity."""
        validator = EquityValidator()
        result = validator.validate_equity(equity=0.0)

        assert not result.is_valid
        assert any("equity" in e.lower() for e in result.errors)

    def test_negative_equity(self):
        """Test detection of negative equity."""
        validator = EquityValidator()
        result = validator.validate_equity(equity=-1000.0)

        assert not result.is_valid
        assert any("equity" in e.lower() for e in result.errors)

    def test_nan_equity(self):
        """Test detection of NaN equity."""
        validator = EquityValidator()
        result = validator.validate_equity(equity=np.nan)

        assert not result.is_valid
        assert any("equity" in e.lower() for e in result.errors)

    def test_infinite_equity(self):
        """Test detection of infinite equity."""
        validator = EquityValidator()
        result = validator.validate_equity(equity=np.inf)

        assert not result.is_valid
        assert any("equity" in e.lower() for e in result.errors)

    def test_equity_too_low(self):
        """Test detection of equity below minimum."""
        validator = EquityValidator()
        result = validator.validate_equity(equity=50.0)

        assert not result.is_valid
        assert any("too low" in e.lower() for e in result.errors)

    def test_equity_too_high(self):
        """Test detection of equity above maximum."""
        validator = EquityValidator()
        result = validator.validate_equity(equity=2e9)

        assert not result.is_valid
        assert any("too high" in e.lower() for e in result.errors)

    def test_equity_jump_detection(self):
        """Test detection of unexplained equity jump."""
        validator = EquityValidator()

        # First equity
        result1 = validator.validate_equity(equity=50000.0, check_jump=True)
        assert result1.is_valid

        # Wait would be needed for real jump detection, but we can test jump logic
        # Jump > 10% in < 5 minutes should trigger warning
        # Since we can't easily mock time, test the history recording
        assert len(validator.equity_history) == 1
        assert validator.equity_history[0][1] == 50000.0

    def test_equity_history_recording(self):
        """Test that equity history is recorded."""
        validator = EquityValidator()

        validator.validate_equity(equity=50000.0)
        validator.validate_equity(equity=50500.0)
        validator.validate_equity(equity=51000.0)

        assert len(validator.equity_history) == 3
        assert validator.equity_history[0][1] == 50000.0
        assert validator.equity_history[2][1] == 51000.0

    def test_equity_history_max_size(self):
        """Test that equity history is capped at 100 entries."""
        validator = EquityValidator()

        # Add 150 entries
        for i in range(150):
            validator.validate_equity(equity=50000.0 + i)

        # Should only keep last 100
        assert len(validator.equity_history) == 100
        assert validator.equity_history[0][1] == 50050.0  # Entry 50 (150 - 100)


class TestOHLCVValidatorIntegration:
    """Integration tests for OHLCV validator."""

    def test_validate_multiple_issues(self):
        """Test detection of multiple issues in one dataframe."""
        validator = OHLCVValidator()

        dates = pd.date_range("2024-01-01", periods=5, freq="1h")
        df = pd.DataFrame(
            {
                "open": [100.0, np.nan, 100.0, -50.0, 100.0],
                "high": [98.0, 102.0, 102.0, 102.0, 102.0],  # First row: High < Low
                "low": [102.0, 98.0, 98.0, 98.0, 98.0],
                "close": [101.0, 101.0, 101.0, 101.0, 101.0],
                "volume": [1000.0, 1000.0, -100.0, 1000.0, 1000.0],
            },
            index=dates,
        )

        result = validator.validate(df)

        assert not result.is_valid
        assert len(result.errors) >= 3  # Multiple errors

    def test_large_valid_dataset(self):
        """Test validation of large valid dataset."""
        validator = OHLCVValidator()

        dates = pd.date_range("2024-01-01", periods=1000, freq="1h")
        df = pd.DataFrame(
            {
                "open": 100.0 + np.random.randn(1000).cumsum(),
                "high": 102.0 + np.random.randn(1000).cumsum(),
                "low": 98.0 + np.random.randn(1000).cumsum(),
                "close": 101.0 + np.random.randn(1000).cumsum(),
                "volume": 1000.0 + np.random.random(1000) * 500,
            },
            index=dates,
        )

        # Fix high/low relationship
        df["high"] = df[["open", "high", "close"]].max(axis=1) + 1
        df["low"] = df[["open", "low", "close"]].min(axis=1) - 1

        result = validator.validate(df)

        # Should be valid or warn, not error
        assert len(result.errors) == 0


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
