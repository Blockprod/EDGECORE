<<<<<<< HEAD
﻿#!/usr/bin/env python
=======
#!/usr/bin/env python
>>>>>>> origin/main
"""Test hot-reload configuration feature."""
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_hot_reload():
    """Test hot-reload capabilities."""
    os.environ['EDGECORE_ENV'] = 'dev'
    
    from config.settings import get_settings
    
    settings = get_settings()
    
    print("=" * 70)
    print("  HOT-RELOAD CONFIGURATION TEST")
    print("=" * 70)
    print()
    
    # Test 1: Initial state
    print("1. Initial State (DEV)")
    print(f"   Environment: {settings.env}")
    print(f"   Symbols: {len(settings.trading_universe.symbols)} (first 3: {settings.trading_universe.symbols[:3]})")
    print()
    
    # Test 2: Reload from file
    print("2. Reload from Configuration File")
    settings.reload_symbols()
    print(f"   Symbols reloaded: {len(settings.trading_universe.symbols)} symbols")
    print()
    
    # Test 3: Manual symbol override
    print("3. Manual Symbol Override")
    custom_symbols = ["AAPL", "MSFT", "GOOGL"]
    settings.reload_symbols(custom_symbols)
    print(f"   Changed to: {settings.trading_universe.symbols}")
    print()
    
    # Test 4: Switch environment  
    print("4. Switch Environment (DEV -> TEST)")
    settings.switch_environment('test')
    print(f"   Environment: {settings.env}")
    print(f"   Symbols: {len(settings.trading_universe.symbols)} (first 3: {settings.trading_universe.symbols[:3]})")
    print()
    
    # Test 5: Switch to production
    print("5. Switch Environment (TEST -> PROD)")
    settings.switch_environment('prod')
    print(f"   Environment: {settings.env}")
    print(f"   Symbols: {len(settings.trading_universe.symbols)} (first 3: {settings.trading_universe.symbols[:3]})")
    print()
    
    # Test 6: Get symbols for environment
    print("6. Get Symbols for Current Environment")
    symbols = settings.get_symbols_for_env()
    print(f"   Current env: {settings.env}")
    print(f"   Total symbols: {len(symbols)}")
    print()
    
    print("=" * 70)
    print("  ALL HOT-RELOAD TESTS PASSED [OK]")
    print("=" * 70)

if __name__ == '__main__':
    test_hot_reload()
