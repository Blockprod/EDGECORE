"""
Example: Test EDGECORE configuration and system health
"""

import sys
from pathlib import Path

def check_environment():
    """Verify Python version and environment"""
    import platform
    
    print("\n[*] Environment Check:")
    print(f"    Python Version: {platform.python_version()}")
    print(f"    Platform: {platform.platform()}")
    
    # Check Python 3.11.x
    py_major, py_minor, py_patch = sys.version_info[:3]
    if py_major != 3 or py_minor != 11:
        print(f"    [!] WARNING: EDGECORE requires Python 3.11.x, you have {py_major}.{py_minor}.{py_patch}")
        print("        Consider installing Python 3.11.9")

def check_dependencies():
    """Check installed packages"""
    print("\n[*] Dependency Check:")
    
    required = [
        'numpy', 'pandas', 'scipy', 'statsmodels',
        'structlog', 'yaml', 'dotenv'
    ]
    
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
            print(f"    Ô£ô {pkg}")
        except ImportError:
            print(f"    Ô£ù {pkg} (missing)")
            missing.append(pkg)
    
    if missing:
        print(f"\n    [!] Missing packages: {', '.join(missing)}")
        print("    Run: pip install -r requirements.txt")
        return False
    return True

def check_configuration():
    """Check configuration files"""
    print("\n[*] Configuration Check:")
    
    config_dir = Path("config")
    if not config_dir.exists():
        print("    Ô£ù config/ directory not found")
        return False
    
    required_configs = [
        'settings.py',
        'dev.yaml',
        'prod.yaml'
    ]
    
    for config_file in required_configs:
        config_path = config_dir / config_file
        if config_path.exists():
            print(f"    Ô£ô {config_file}")
        else:
            print(f"    Ô£ù {config_file} (missing)")
            return False
    
    return True

def check_settings():
    """Test loading settings"""
    print("\n[*] Settings Load Check:")
    
    try:
        from config.settings import get_settings
        settings = get_settings()
        
        print(f"    Ô£ô Settings loaded (environment: {settings.env})")
        print(f"      - Strategy: lookback={settings.strategy.lookback_window} days")
        print(f"      - Risk: max_risk={settings.risk.max_risk_per_trade*100:.1f}%")
        print(f"      - Execution: engine={settings.execution.engine}, sandbox={settings.execution.use_sandbox}")
        return True
    except Exception as e:
        print(f"    Ô£ù Failed to load settings: {e}")
        return False

def check_modules():
    """Test module imports"""
    print("\n[*] Module Import Check:")
    
    modules = [
        ('data.loader', 'DataLoader'),
        ('models.cointegration', 'engle_granger_test'),
        ('strategies.pair_trading', 'PairTradingStrategy'),
        ('risk.engine', 'RiskEngine'),
        ('execution.ibkr_engine', 'IBKRExecutionEngine'),
        ('backtests.runner', 'BacktestRunner'),
    ]
    
    for module_name, class_name in modules:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            print(f"    Ô£ô {module_name}.{class_name}")
        except ImportError as e:
            print(f"    Ô£ù {module_name} (import error: {e})")
            return False
        except AttributeError:
            print(f"    Ô£ù {module_name}.{class_name} (not found)")
            return False
    
    return True

def main():
    print("\n" + "="*70)
    print("EDGECORE SYSTEM HEALTH CHECK")
    print("="*70)
    
    all_ok = True
    
    # Run all checks
    check_environment()
    all_ok = check_dependencies() and all_ok
    all_ok = check_configuration() and all_ok
    all_ok = check_settings() and all_ok
    all_ok = check_modules() and all_ok
    
    # Summary
    print("\n" + "="*70)
    if all_ok:
        print("Ô£ô SYSTEM READY - All checks passed!")
        print("\nNext steps:")
        print("  1. cp .env.example .env")
        print("  2. Edit .env with your credentials")
        print("  3. python examples_backtest.py    (run a backtest)")
        print("  4. python examples_pair_discovery.py (find pairs)")
        print("  5. python main.py --mode paper     (paper trading)")
    else:
        print("Ô£ù SYSTEM NOT READY - Fix issues above")
        sys.exit(1)
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
