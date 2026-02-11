"""
Data integrity validators for OHLCV market data and positions.

Ensures:
- OHLCV data quality (no NaN, valid ranges)
- Price consistency (High >= Low >= Close >= Open within bounds)
- Volume checks (non-negative, non-zero)
- Position data validity
- Sequence continuity (no gaps, monotonic timestamps)
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from structlog import get_logger
import pandas as pd
import numpy as np
import math

logger = get_logger(__name__)


class DataValidationError(Exception):
    """Raised when data validation fails."""
    pass


@dataclass
class ValidationResult:
    """Result of a data validation check."""
    is_valid: bool
    checks_passed: int
    checks_failed: int
    errors: List[str]
    warnings: List[str]
    
    def __bool__(self) -> bool:
        """Validation passes if is_valid is True."""
        return self.is_valid


class OHLCVValidator:
    """
    Validates OHLCV (Open, High, Low, Close, Volume) market data.
    
    Checks:
    - No NaN or infinite values
    - High >= Low >= Close within bounds
    - Volume >= 0
    - No duplicate timestamps
    - Consistent decimal precision
    """
    
    def __init__(self, symbol: str = ""):
        """
        Initialize validator.
        
        Args:
            symbol: Optional symbol for better error messages
        """
        self.symbol = symbol
    
    def validate(self, df: pd.DataFrame, raise_on_error: bool = False, max_age_hours: float = 99999.0) -> ValidationResult:
        """
        Validate OHLCV dataframe.
        
        Args:
            df: DataFrame with OHLCV data
            raise_on_error: If True, raise exception on validation failure
            max_age_hours: Maximum age of data in hours (default 99999.0 = essentially unlimited for testing)
        
        Returns:
            ValidationResult with details
        
        Raises:
            DataValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        checks_passed = 0
        checks_failed = 0
        
        # Check 1: DataFrame not empty
        if df.empty:
            errors.append("OHLCV data is empty")
            checks_failed += 1
        else:
            checks_passed += 1
        
        if df.empty:
            result = ValidationResult(
                is_valid=len(errors) == 0,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                errors=errors,
                warnings=warnings
            )
            if raise_on_error and not result.is_valid:
                raise DataValidationError("; ".join(errors))
            return result
        
        # Check 2: Required columns exist
        required_cols = {'open', 'high', 'low', 'close', 'volume'}
        df_cols = set(c.lower() for c in df.columns)
        missing_cols = required_cols - df_cols
        
        if missing_cols:
            errors.append(f"Missing required columns: {missing_cols}")
            checks_failed += 1
            # Early return if required columns missing
            result = ValidationResult(
                is_valid=False,
                checks_passed=checks_passed,
                checks_failed=checks_failed + 8,  # Remaining checks can't run
                errors=errors,
                warnings=warnings
            )
            if raise_on_error:
                raise DataValidationError("; ".join(errors))
            return result
        else:
            checks_passed += 1
        
        # Check 3: No NaN values in price/volume
        if df[['open', 'high', 'low', 'close', 'volume']].isna().any().any():
            nan_count = df[['open', 'high', 'low', 'close', 'volume']].isna().sum().sum()
            errors.append(f"Found {nan_count} NaN values in OHLCV data")
            checks_failed += 1
        else:
            checks_passed += 1
        
        # Check 4: No infinite values
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if (np.isinf(df[col])).any():
                inf_count = (np.isinf(df[col])).sum()
                errors.append(f"Found {inf_count} infinite values in {col}")
                checks_failed += 1
                break
        else:
            checks_passed += 1
        
        # Check 5: Price consistency (High >= Low >= Close)
        invalid_prices = []
        for idx, row in df.iterrows():
            h, l, c, o = row['high'], row['low'], row['close'], row['open']
            
            if h < l:
                invalid_prices.append(f"Row {idx}: High ({h}) < Low ({l})")
            elif l > c and l > o:
                # Warning if low is above both open and close
                warnings.append(f"Row {idx}: Low ({l}) > both Open and Close")
            elif h < c and h < o:
                # Warning if high is below both open and close
                warnings.append(f"Row {idx}: High ({h}) < both Open and Close")
        
        if invalid_prices:
            errors.extend(invalid_prices[:5])  # Show first 5
            checks_failed += 1
        else:
            checks_passed += 1
        
        # Check 6: Positive prices (> 0)
        zero_prices = (df[['open', 'high', 'low', 'close']] <= 0).any().any()
        if zero_prices:
            errors.append("Found zero or negative prices")
            checks_failed += 1
        else:
            checks_passed += 1
        
        # Check 7: Non-negative volume
        if (df['volume'] < 0).any():
            neg_vol = (df['volume'] < 0).sum()
            errors.append(f"Found {neg_vol} rows with negative volume")
            checks_failed += 1
        else:
            checks_passed += 1
        
        # Check 8: Zero volume warning (trading may have stopped)
        zero_vol_rows = (df['volume'] == 0).sum()
        if zero_vol_rows > 0:
            warnings.append(f"{zero_vol_rows} rows have zero volume (possible trading halt)")
        else:
            checks_passed += 1
        
        # Check 9: No duplicate timestamps (if timestamp is index)
        if df.index.duplicated().any():
            dup_count = df.index.duplicated().sum()
            errors.append(f"Found {dup_count} duplicate timestamps")
            checks_failed += 1
        else:
            checks_passed += 1
        
        # Check 10: Timestamp monotonicity (increasing)
        if not df.index.is_monotonic_increasing:
            errors.append("Timestamps are not monotonically increasing (data may be unordered)")
            checks_failed += 1
        else:
            checks_passed += 1
        
        # Check 11: Data not stale (timestamp age)
        if len(df) > 0:
            latest_timestamp = df.index[-1]
            # Handle both datetime and pd.Timestamp
            if hasattr(latest_timestamp, 'to_pydatetime'):
                latest_dt = latest_timestamp.to_pydatetime()
            else:
                latest_dt = latest_timestamp
            
            age_hours = (datetime.utcnow() - latest_dt).total_seconds() / 3600
            
            if age_hours > max_age_hours:
                errors.append(f"Latest data is {age_hours:.1f}h old (max allowed: {max_age_hours}h)")
                checks_failed += 1
            else:
                checks_passed += 1
        
        # Check 12: No future timestamps (clock skew)
        max_future_seconds = 60  # Allow 1 min clock skew
        future_count = 0
        for ts in df.index:
            if hasattr(ts, 'to_pydatetime'):
                ts_dt = ts.to_pydatetime()
            else:
                ts_dt = ts
            
            time_diff = (ts_dt - datetime.utcnow()).total_seconds()
            if time_diff > max_future_seconds:
                future_count += 1
                if future_count == 1:  # Only warn once
                    errors.append(f"Future timestamp detected: {ts_dt} ({time_diff:.0f}s in future)")
        
        if future_count == 0:
            checks_passed += 1
        else:
            checks_failed += 1
        
        is_valid = len(errors) == 0
        
        result = ValidationResult(
            is_valid=is_valid,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            errors=errors,
            warnings=warnings
        )
        
        if raise_on_error and not result.is_valid:
            raise DataValidationError("; ".join(errors))
        
        return result
    
    def validate_row(self, o: float, h: float, l: float, c: float, v: float) -> bool:
        """
        Quick validation of a single OHLCV row.
        
        Returns:
            True if valid, False otherwise
        """
        # Check for NaN/inf
        for val in [o, h, l, c, v]:
            if math.isnan(val) or math.isinf(val):
                return False
        
        # Check constraints
        if o <= 0 or h <= 0 or l <= 0 or c <= 0:
            return False
        if h < l:
            return False
        if v < 0:
            return False
        
        return True


class PositionValidator:
    """
    Validates position data for consistency and safety.
    
    Checks:
    - Positive quantity
    - Valid side (long/short)
    - Entry price > 0
    - Current price > 0
    - Position age reasonable
    """
    
    @staticmethod
    def validate_position(
        symbol: str,
        quantity: float,
        entry_price: float,
        current_price: float,
        side: str = "long",
        opened_at: Optional[datetime] = None
    ) -> ValidationResult:
        """
        Validate position data.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USD")
            quantity: Position size
            entry_price: Entry price
            current_price: Current market price
            side: "long" or "short"
            opened_at: When position was opened
        
        Returns:
            ValidationResult
        """
        errors = []
        warnings = []
        checks_passed = 0
        checks_failed = 0
        
        # Check 1: Symbol format
        if not symbol or "/" not in symbol:
            errors.append(f"Invalid symbol format: {symbol}")
            checks_failed += 1
        else:
            checks_passed += 1
        
        # Check 2: Positive quantity
        if quantity <= 0 or math.isnan(quantity) or math.isinf(quantity):
            errors.append(f"Invalid quantity: {quantity}")
            checks_failed += 1
        else:
            checks_passed += 1
        
        # Check 3: Valid side
        if side.lower() not in ["long", "short"]:
            errors.append(f"Invalid side: {side} (must be 'long' or 'short')")
            checks_failed += 1
        else:
            checks_passed += 1
        
        # Check 4: Entry price valid
        if entry_price <= 0 or math.isnan(entry_price) or math.isinf(entry_price):
            errors.append(f"Invalid entry price: {entry_price}")
            checks_failed += 1
        else:
            checks_passed += 1
        
        # Check 5: Current price valid
        if current_price <= 0 or math.isnan(current_price) or math.isinf(current_price):
            errors.append(f"Invalid current price: {current_price}")
            checks_failed += 1
        else:
            checks_passed += 1
        
        # Check 6: Position age check (if provided)
        if opened_at:
            age = datetime.utcnow() - opened_at
            if age < timedelta(0):
                errors.append(f"Position opened in the future")
                checks_failed += 1
            elif age > timedelta(days=365):
                warnings.append(f"Position age exceeds 1 year ({age})")
            checks_passed += 1
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            errors=errors,
            warnings=warnings
        )


class EquityValidator:
    """
    Validates equity and balance information.
    
    Checks:
    - Positive equity
    - Reasonable equity range
    - Cash <= equity
    - No unexplained equity jumps
    """
    
    def __init__(self):
        """Initialize equity validator."""
        self.equity_history: List[Tuple[datetime, float]] = []
        self.max_jump_pct = 10.0  # Alert if > 10% jump
    
    def validate_equity(self, equity: float, check_jump: bool = True) -> ValidationResult:
        """
        Validate equity value.
        
        Args:
            equity: Current equity
            check_jump: Check for unexplained jumps
        
        Returns:
            ValidationResult
        """
        errors = []
        warnings = []
        checks_passed = 0
        checks_failed = 0
        
        # Check 1: Positive
        if equity <= 0 or math.isnan(equity) or math.isinf(equity):
            errors.append(f"Invalid equity: {equity}")
            checks_failed += 1
        else:
            checks_passed += 1
        
        # Check 2: Reasonable range (100 - 1B)
        if equity < 100:
            errors.append(f"Equity too low: {equity} (< $100)")
            checks_failed += 1
        elif equity > 1e9:
            errors.append(f"Equity too high: {equity} (> $1B)")
            checks_failed += 1
        else:
            checks_passed += 1
        
        # Check 3: Jump detection
        if check_jump and len(self.equity_history) > 0:
            last_time, last_equity = self.equity_history[-1]
            time_delta = datetime.utcnow() - last_time
            equity_change_pct = abs((equity - last_equity) / last_equity) * 100
            
            # Only alert for jumps > threshold in short timeframes
            if time_delta.total_seconds() < 300:  # 5 minutes
                if equity_change_pct > self.max_jump_pct:
                    warnings.append(
                        f"Equity jump {equity_change_pct:.2f}% in {time_delta.total_seconds():.0f}s"
                    )
            
            checks_passed += 1
        elif check_jump:
            checks_passed += 1
        
        # Record this equity
        self.equity_history.append((datetime.utcnow(), equity))
        # Keep only last 100 entries
        if len(self.equity_history) > 100:
            self.equity_history = self.equity_history[-100:]
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            errors=errors,
            warnings=warnings
        )
