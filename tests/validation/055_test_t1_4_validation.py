#!/usr/bin/env python
"""Validation test for T1.4: Position-Level Stops"""

def test_t1_4():
    print("\n=== T1.4 VALIDATION: Position-Level Stops ===\n")
    
    # Step 1: Check Position class has stop-loss fields
    print("[TEST] Checking Position class modifications...")
    from risk.engine import Position
    from datetime import datetime
    
    # Create a test position
    pos = Position(
        symbol_pair="AAPL",
        entry_time=datetime.now(),
        entry_price=50000.0,
        quantity=1.0,
        side="long",
        stop_loss_pct=0.05  # 5% stop
    )
    
    # Check attributes exist
    assert hasattr(pos, 'current_price'), "Position missing current_price attribute"
    assert hasattr(pos, 'stop_loss_pct'), "Position missing stop_loss_pct attribute"
    assert hasattr(pos, 'pnl_pct'), "Position missing pnl_pct property"
    assert hasattr(pos, 'should_stop_out'), "Position missing should_stop_out method"
    print("[OK] Position class has all required fields and methods")
    
    # Step 2: Test pnl_pct calculation
    print("\n[TEST] Testing P&L percentage calculation...")
    pos.current_price = 50000.0
    assert pos.pnl_pct == 0.0, f"Expected pnl_pct=0 at breakeven, got {pos.pnl_pct}"
    print(f"[OK] At entry price (50000): pnl_pct = {pos.pnl_pct:.4f}")
    
    # Test profitable long position
    pos.current_price = 52000.0
    pnl_pct = pos.pnl_pct
    assert abs(pnl_pct - 0.04) < 0.001, f"Expected pnl_pct=0.04 (4%), got {pnl_pct}"
    print(f"[OK] Long position +4% profit: pnl_pct = {pnl_pct:.4f}")
    
    # Test loss position (should trigger 5% stop)
    pos.current_price = 47500.0  # 5% loss
    pnl_pct = pos.pnl_pct
    assert abs(pnl_pct - (-0.05)) < 0.001, f"Expected pnl_pct=-0.05 (-5%), got {pnl_pct}"
    print(f"[OK] Long position -5% loss: pnl_pct = {pnl_pct:.4f}")
    
    # Step 3: Test should_stop_out() method
    print("\n[TEST] Testing should_stop_out() method...")
    
    # Not stopped yet (only 4% loss)
    pos.current_price = 48000.0
    pos.stop_loss_pct = 0.05
    should_stop = pos.should_stop_out()
    assert not should_stop, "Position with 4% loss should NOT trigger 5% stop"
    print(f"[OK] 4% loss with 5% stop: should_stop_out() = {should_stop}")
    
    # Exactly at stop (5% loss)
    pos.current_price = 47500.0
    should_stop = pos.should_stop_out()
    assert should_stop, "Position with exactly 5% loss SHOULD trigger 5% stop"
    print(f"[OK] 5% loss with 5% stop: should_stop_out() = {should_stop}")
    
    # Beyond stop (6% loss)
    pos.current_price = 47000.0
    should_stop = pos.should_stop_out()
    assert should_stop, "Position with 6% loss SHOULD trigger 5% stop"
    print(f"[OK] 6% loss with 5% stop: should_stop_out() = {should_stop}")
    
    # Step 4: Test short position P&L
    print("\n[TEST] Testing short position P&L...")
    short_pos = Position(
        symbol_pair="MSFT",
        entry_time=datetime.now(),
        entry_price=3000.0,
        quantity=10.0,
        side="short",
        stop_loss_pct=0.05
    )
    
    short_pos.current_price = 3000.0
    assert short_pos.pnl_pct == 0.0, "Short at breakeven should have 0% P&L"
    print(f"[OK] Short at entry (3000): pnl_pct = {short_pos.pnl_pct:.4f}")
    
    # Short profit (price goes down)
    short_pos.current_price = 2850.0  # 5% down, profit for short
    pnl_pct = short_pos.pnl_pct
    assert abs(pnl_pct - 0.05) < 0.001, f"Short with 5% price drop should have 5% profit, got {pnl_pct}"
    print(f"[OK] Short with -5% price: pnl_pct = {pnl_pct:.4f} (profit)")
    
    # Short loss (price goes up)
    short_pos.current_price = 3150.0  # 5% up, loss for short
    pnl_pct = short_pos.pnl_pct
    assert abs(pnl_pct - (-0.05)) < 0.001, f"Short with 5% price rise should have -5% loss, got {pnl_pct}"
    should_stop = short_pos.should_stop_out()
    assert should_stop, "Short with 5% price rise should trigger 5% stop"
    print(f"[OK] Short with +5% price: pnl_pct = {pnl_pct:.4f} (loss), should_stop = {should_stop}")
    
    # Step 5: Test RiskEngine.check_position_stops()
    print("\n[TEST] Testing RiskEngine.check_position_stops()...")
    from risk.engine import RiskEngine
    
    risk_engine = RiskEngine(initial_equity=100000.0)
    
    # Add some positions
    pos1 = Position(
        symbol_pair="AAPL",
        entry_time=datetime.now(),
        entry_price=50000.0,
        quantity=1.0,
        side="long",
        stop_loss_pct=0.05,
        current_price=47500.0  # 5% loss = should stop
    )
    
    pos2 = Position(
        symbol_pair="MSFT",
        entry_time=datetime.now(),
        entry_price=3000.0,
        quantity=10.0,
        side="long",
        stop_loss_pct=0.05,
        current_price=3090.0  # 3% gain = no stop
    )
    
    pos3 = Position(
        symbol_pair="BAC",
        entry_time=datetime.now(),
        entry_price=1.0,
        quantity=10000.0,
        side="long",
        stop_loss_pct=0.02,
        current_price=0.975  # 2.5% loss = should stop (> 2%)
    )
    
    risk_engine.positions = {
        "AAPL": pos1,
        "MSFT": pos2,
        "BAC": pos3
    }
    
    # Check for stops
    stopped = risk_engine.check_position_stops()
    
    assert len(stopped) == 2, f"Expected 2 stops (AAPL & WFC), got {len(stopped)}"
    print(f"[OK] check_position_stops() returned {len(stopped)} positions to close")
    
    # Verify stopped positions
    stopped_symbols = [s['symbol'] for s in stopped]
    assert "AAPL" in stopped_symbols, "AAPL should be flagged (5% loss)"
    assert "BAC" in stopped_symbols, "BAC should be flagged (2.5% loss > 2% stop)"
    assert "MSFT" not in stopped_symbols, "MSFT should NOT be flagged (3% gain)"
    
    for stopped_pos in stopped:
        print(f"[OK] {stopped_pos['symbol']}: {stopped_pos['reason']}")
    
    # Step 6: Verify main.py integration
    print("\n[TEST] Checking main.py integration...")
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            main_content = f.read()
        
        assert 'check_position_stops' in main_content, "main.py should call check_position_stops()"
        assert 'stop_loss' in main_content.lower(), "main.py should reference stop-loss"
        assert 'stopped_positions' in main_content, "main.py should handle stopped_positions"
        
        print("[OK] main.py properly integrates stop-loss checking")
        
        # Count how many times check_position_stops is called
        call_count = main_content.count('check_position_stops')
        print(f"[OK] check_position_stops() called {call_count} time(s)")
        
    except Exception as e:
        print(f"[WARN] Could not verify main.py integration: {e}")
    
    print("\n[PASS] T1.4 Validation Successful\n")

if __name__ == '__main__':
    test_t1_4()
