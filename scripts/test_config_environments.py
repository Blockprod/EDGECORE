<<<<<<< HEAD
﻿#!/usr/bin/env python
=======
#!/usr/bin/env python
>>>>>>> origin/main
"""Test environment-specific configuration loading."""
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_environment(env_name):
    """Test loading configuration for a specific environment."""
    # Set environment
    os.environ['EDGECORE_ENV'] = env_name
    
    # Force reload of settings module
    if 'config.settings' in sys.modules:
        del sys.modules['config.settings']
    
    from config.settings import Settings
    Settings._instance = None  # Reset singleton
    
    from config.settings import get_settings
    settings = get_settings()
    
    return {
        'env': env_name,
        'num_symbols': len(settings.trading_universe.symbols),
        'symbols': settings.trading_universe.symbols[:3],
        'initial_capital': settings.execution.initial_capital
    }

if __name__ == '__main__':
    print("=" * 70)
    print("  ENVIRONMENT-SPECIFIC CONFIGURATION TEST")
    print("=" * 70)
    print()
    
    for env in ['dev', 'test', 'prod']:
        result = test_environment(env)
        print(f"Environment: {result['env'].upper()}")
        print(f"  Symbols:         {result['num_symbols']}")
        print(f"  First 3:         {result['symbols']}")
        print(f"  Initial Capital: ${result['initial_capital']:,.0f}")
        print()
    
    print("=" * 70)
<<<<<<< HEAD
    print("  ALL TESTS PASSED Ô£ô")
=======
    print("  ALL TESTS PASSED ✓")
>>>>>>> origin/main
    print("=" * 70)
