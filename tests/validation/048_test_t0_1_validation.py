#!/usr/bin/env python
"""Validation test for T0.1: RiskEngine Initialization"""

from config.settings import get_settings
from risk.engine import RiskEngine


def test_t0_1():
    print("\n=== T0.1 VALIDATION: RiskEngine Initialization ===\n")
    
    # Step 1: Load settings
    settings = get_settings()
    print(f"[OK] initial_capital loaded from config: ${settings.execution.initial_capital}")
    
    # Step 2: Initialize RiskEngine with capital
    risk_engine = RiskEngine(initial_equity=settings.execution.initial_capital)
    print(f"[OK] RiskEngine initialized with equity: ${risk_engine.initial_equity}")
    
    # Step 3: Verify audit trail
    assert risk_engine.audit_trail is not None
    print(f"[OK] Audit trail initialized: {type(risk_engine.audit_trail).__name__}")
    
    # Step 4: Verify config matches
    assert risk_engine.initial_equity == settings.execution.initial_capital
    print("[OK] Config consistency check passed")
    
    # Step 5: Verify positions tracking
    assert risk_engine.positions == {}
    print("[OK] Positions tracking initialized (empty)")
    
    print("\n[PASS] T0.1 Validation Successful\n")

if __name__ == "__main__":
    try:
        test_t0_1()
    except Exception as e:
        print(f"\n[FAIL] T0.1 Validation Failed: {e}\n")
        raise
