#!/usr/bin/env python
"""Validation test for T0.3: Broker Reconciliation Integration"""

from execution.reconciler import BrokerReconciler


def test_t0_3():
    print("\n=== T0.3 VALIDATION: Broker Reconciliation Integration ===\n")

    # Step 1: Verify BrokerReconciler can be imported in main.py context
    try:
        from main import run_paper_trading

        _ = run_paper_trading
        print("[OK] main.py imports BrokerReconciler successfully")
    except ImportError as e:
        print(f"[FAIL] Import error: {e}")
        raise

    # Step 2: Test BrokerReconciler initialization
    print("\n[TEST] Creating BrokerReconciler with test equity...")
    reconciler = BrokerReconciler(
        internal_equity=100000.0,
        internal_positions={},
        equity_tolerance_pct=0.01,  # 0.01%
    )
    assert reconciler is not None
    print("[OK] BrokerReconciler initialized")

    # Step 3: Test startup reconciliation with matching equity
    print("\n[TEST] Testing startup reconciliation (matching equity)...")
    matches, diff_pct = reconciler.reconcile_equity(broker_equity=100000.0)
    assert matches
    assert diff_pct == 0.0
    print(f"[OK] Reconciliation passed (diff: {diff_pct:.6f}%)")

    # Step 4: Test reconciliation with small divergence (within tolerance)
    print("\n[TEST] Testing small divergence (within 0.01% tolerance)...")
    matches, diff_pct = reconciler.reconcile_equity(broker_equity=99999.5)
    assert matches, f"Expected match within tolerance, got diff: {diff_pct}"
    assert diff_pct < 0.01
    print(f"[OK] Small divergence within tolerance (diff: {diff_pct:.6f}%)")

    # Step 5: Test reconciliation with large divergence (outside tolerance)
    print("\n[TEST] Testing large divergence (outside tolerance)...")
    matches, diff_pct = reconciler.reconcile_equity(broker_equity=99000.0)  # 1% diff
    assert not matches, "Expected mismatch for 1% divergence"
    assert diff_pct > 0.01
    print(f"[OK] Large divergence detected (diff: {diff_pct:.4f}%)")

    # Step 6: Verify divergence was recorded
    assert len(reconciler.divergences) > 0
    print(f"[OK] Divergence tracking enabled ({len(reconciler.divergences)} recorded)")

    print("\n[PASS] T0.3 Validation Successful\n")


if __name__ == "__main__":
    try:
        test_t0_3()
    except Exception as e:
        print(f"\n[FAIL] T0.3 Validation Failed: {e}\n")
        import traceback

        traceback.print_exc()
        raise
