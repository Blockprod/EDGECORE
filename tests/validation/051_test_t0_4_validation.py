#!/usr/bin/env python
"""Validation test for T0.4: Max Leverage Configuration"""

from config.settings import get_settings
from risk.engine import RiskEngine, Position
from datetime import datetime

def test_t0_4():
    print("\n=== T0.4 VALIDATION: Max Leverage Configuration ===\n")
    
    # Step 1: Load settings and check max_leverage config
    settings = get_settings()
    print("[TEST] Loading max_leverage from settings...")
    assert hasattr(settings.risk, 'max_leverage')
    assert settings.risk.max_leverage == 2.0  # Equity default (reduced from 3.0 for safety)
    print(f"[OK] max_leverage loaded: {settings.risk.max_leverage}x")

    # Step 2: Initialize RiskEngine
    print("\n[TEST] Initialize RiskEngine...")
    risk_engine = RiskEngine(initial_equity=100000.0)
    assert risk_engine.config.max_leverage == 2.0  # Equity default
    print(f"[OK] RiskEngine has max_leverage: {risk_engine.config.max_leverage}x")
    
    # Step 3: Test get_total_exposure() method exists
    print("\n[TEST] Testing get_total_exposure() method...")
    assert hasattr(risk_engine, 'get_total_exposure')
    total_exposure = risk_engine.get_total_exposure()
    assert total_exposure == 0.0  # No positions yet
    print(f"[OK] get_total_exposure() works (current: ${total_exposure})")
    
    # Step 4: Add a test position to verify exposure calculation
    print("\n[TEST] Adding test position to calculate exposure...")
    pos = Position(
        symbol_pair="AAPL",
        entry_time=datetime.utcnow(),
        entry_price=45000.0,
        quantity=1.0,
        side="long",
        marked_price=45000.0
    )
    risk_engine.positions["AAPL"] = pos
    
    total_exposure = risk_engine.get_total_exposure()
    expected_exposure = abs(1.0 * 45000.0)
    assert total_exposure == expected_exposure
    print(f"[OK] Exposure calculation correct: ${total_exposure}")
    
    # Step 5: Test leverage check in can_enter_trade()
    print("\n[TEST] Testing leverage constraint in can_enter_trade()...")
    
    # Try to enter a small trade (should pass)
    can_enter, reason = risk_engine.can_enter_trade(
        symbol_pair="MSFT",
        position_size=10.0,
        current_equity=100000.0,
        volatility=0.02
    )
    assert can_enter
    print("[OK] Small trade allowed (leverage OK)")
    
    # Try to enter a very large trade (should fail due to leverage)
    # First clear the existing position to test clean scenario
    risk_engine.positions.clear()
    
    # Pre-populate with exposure equal to 2x equity
    for i in range(2):
        risk_engine.positions[f"PRE{i}"] = Position(
            symbol_pair=f"PRE{i}",
            entry_time=datetime.utcnow(),
            entry_price=1000.0,
            quantity=100000.0,  # ~1x equity per position
            side="long",
            marked_price=1000.0
        )
    
    current_exposure = risk_engine.get_total_exposure()
    print(f"[DEBUG] Current exposure: ${current_exposure} (vs equity: $100000)")
    
    # Now try to add one more large position - should hit leverage limit
    can_enter, reason = risk_engine.can_enter_trade(
        symbol_pair="BOOM",
        position_size=40000.0,  # This would push leverage over 3x
        current_equity=100000.0,
        volatility=0.001  # Very low to bypass risk check
    )
    
    assert not can_enter
    assert "leverage" in reason.lower()
    print(f"[OK] Trade correctly rejected for leverage: {reason}")
    
    # Step 6: Verify prod config has lower leverage
    print("\n[TEST] Checking prod config for lower leverage limit...")
    from pathlib import Path
    
    prod_yaml_path = Path("config/prod.yaml")
    with open(prod_yaml_path, 'r', encoding='utf-8') as f:
        prod_content = f.read()
    
    assert "max_leverage: 1.5" in prod_content
    print("[OK] prod.yaml has max_leverage: 1.5 (conservative for production)")
    
    print("\n[PASS] T0.4 Validation Successful\n")


if __name__ == "__main__":
    try:
        test_t0_4()
    except Exception as e:
        print(f"\n[FAIL] T0.4 Validation Failed: {e}\n")
        import traceback
        traceback.print_exc()
        raise
