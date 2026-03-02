#!/usr/bin/env python
"""Validation test for T1.1: Data Staleness Checks"""

import pandas as pd
from datetime import datetime, timedelta
from data.validators import OHLCVValidator

def test_t1_1():
    print("\n=== T1.1 VALIDATION: Data Staleness Checks ===\n")
    
    # Step 1: Test fresh data (should pass)
    print("[TEST] Testing fresh data (within 2 hours)...")
    current_time = datetime.utcnow()
    dates = pd.date_range(end=current_time - timedelta(minutes=30), periods=100, freq='1h')
    df_fresh = pd.DataFrame({
        'open': 100.0,
        'high': 101.0,
        'low': 99.0,
        'close': 100.5,
        'volume': 1000.0
    }, index=dates)
    
    validator = OHLCVValidator("AAPL")
    result = validator.validate(df_fresh, raise_on_error=False, max_age_hours=2.0)
    assert result.is_valid, f"Fresh data should be valid, got: {result.errors}"
    print(f"[OK] Fresh data validation passed ({len(result.errors)} errors, {result.checks_passed} checks passed)")
    
    # Step 2: Test stale data (should fail)
    print("\n[TEST] Testing stale data (6 hours old)...")
    dates_stale = pd.date_range(end=current_time - timedelta(hours=6), periods=100, freq='1h')
    df_stale = pd.DataFrame({
        'open': 100.0,
        'high': 101.0,
        'low': 99.0,
        'close': 100.5,
        'volume': 1000.0
    }, index=dates_stale)
    
    result_stale = validator.validate(df_stale, raise_on_error=False, max_age_hours=2.0)
    assert not result_stale.is_valid, "Stale data should be invalid"
    assert any("old" in err.lower() for err in result_stale.errors), f"Should mention staleness, got: {result_stale.errors}"
    print("[OK] Stale data correctly rejected:")
    for err in result_stale.errors:
        if "old" in err.lower():
            print(f"     {err}")
    
    # Step 3: Test future timestamps (should fail)
    print("\n[TEST] Testing future timestamps (should be rejected)...")
    future_time = datetime.utcnow() + timedelta(minutes=5)
    dates_future = pd.date_range(end=future_time, periods=10, freq='1h')
    df_future = pd.DataFrame({
        'open': 100.0,
        'high': 101.0,
        'low': 99.0,
        'close': 100.5,
        'volume': 1000.0
    }, index=dates_future)
    
    result_future = validator.validate(df_future, raise_on_error=False, max_age_hours=2.0)
    assert not result_future.is_valid, "Future data should be invalid"
    assert any("future" in err.lower() for err in result_future.errors), f"Should mention future, got: {result_future.errors}"
    print("[OK] Future timestamps correctly rejected:")
    for err in result_future.errors:
        if "future" in err.lower():
            print(f"     {err}")
    
    # Step 4: Test that max_age_hours parameter works
    print("\n[TEST] Testing configurable max_age_hours parameter...")
    dates_3h_old = pd.date_range(end=current_time - timedelta(hours=3), periods=100, freq='1h')
    df_3h = pd.DataFrame({
        'open': 100.0,
        'high': 101.0,
        'low': 99.0,
        'close': 100.5,
        'volume': 1000.0
    }, index=dates_3h_old)
    
    # Should fail with 2h limit
    result_2h = validator.validate(df_3h, raise_on_error=False, max_age_hours=2.0)
    assert not result_2h.is_valid, "3h old data should fail with 2h limit"
    print("[OK] 3h old data rejected with 2h limit")
    
    # Should pass with 4h limit
    result_4h = validator.validate(df_3h, raise_on_error=False, max_age_hours=4.0)
    assert result_4h.is_valid, "3h old data should pass with 4h limit"
    print("[OK] 3h old data accepted with 4h limit")
    
    print("\n[PASS] T1.1 Validation Successful\n")


if __name__ == "__main__":
    try:
        test_t1_1()
    except Exception as e:
        print(f"\n[FAIL] T1.1 Validation Failed: {e}\n")
        import traceback
        traceback.print_exc()
        raise
