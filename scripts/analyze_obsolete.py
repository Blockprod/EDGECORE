#!/usr/bin/env python3
"""Detailed analysis of potentially obsolete test files."""

import re
from pathlib import Path

test_dir = Path("C:\\Users\\averr\\EDGECORE\\tests")

def count_lines(filepath):
    """Count lines in a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return len(f.readlines())
    except:
        return 0

def check_imports(filepath):
    """Check imports and find broken ones."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            imports = re.findall(r'^(?:from|import)\s+([^\s\.]+)', content, re.MULTILINE)
            return imports
    except:
        return []

# Analyze potentially redundant files
print("\n" + "="*80)
print("POTENTIALLY OBSOLETE FILES ANALYSIS")
print("="*80)

obsolete_candidates = [
    # __pycache__ file
    ("C:\\Users\\averr\\EDGECORE\\tests\\__pycache__\\__init__.py", 
     "Cache file", "DELETE"),
    
    # Non-numbered files that might be replaced by numbered versions
    ("C:\\Users\\averr\\EDGECORE\\tests\\models\\test_regime_detector.py",
     "S2.5 Regime Detection", "CHECK_CONTENT"),
    ("C:\\Users\\averr\\EDGECORE\\tests\\models\\test_z_score_lookback.py",
     "S2.2 Dynamic Z-Score", "CHECK_CONTENT"),
    ("C:\\Users\\averr\\EDGECORE\\tests\\models\\test_spread_integration.py",
     "S3.2d Spread Model", "CHECK_CONTENT"),
    ("C:\\Users\\averr\\EDGECORE\\tests\backtests\\test_trading_costs.py",
     "S3.4 Cost Implementation", "CHECK_CONTENT"),
]

for filepath, desc, action in obsolete_candidates:
    path = Path(filepath)
    
    if not path.exists():
        print(f"\nÔØî NOT FOUND: {filepath}")
        continue
    
    lines = count_lines(path)
    size = path.stat().st_size
    
    print(f"\n-'- {path.name}")
    print(f"   Path: {filepath}")
    print(f"   Size: {size} bytes, Lines: {lines}")
    print(f"   Purpose: {desc}")
    print(f"   Status: {action}")
    
    # Show first few lines
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines_content = f.readlines()[:5]
            if lines_content:
                print("   First lines:")
                for line in lines_content:
                    line_str = line.rstrip()
                    if line_str:
                        print(f"     {line_str[:75]}")
    except:
        pass

# Summary
print("\n" + "="*80)
print("SUMMARY OF FINDINGS")
print("="*80)

print("""
DEFINITE OBSOLETE FILES:
1. tests/__pycache__/__init__.py
   - Size: 0 bytes
   - Reason: Cache file, should not be in version control
   - Action: DELETE

POTENTIAL REDUNDANT FILES (need review):
1. Non-numbered test files in models/:
   - test_adaptive_thresholds.py
   - test_bonferroni_correction.py
   - test_half_life_estimator.py
   - test_hedge_ratio_tracker.py
   - test_ml_threshold_optimizer.py
   - test_model_retraining.py
   - test_performance_optimizer.py
   - test_regime_detector.py
   - test_spread_integration.py
   - test_z_score_lookback.py
   
   Status: KEEP (these test specific modules, not numbered phases)

2. Non-numbered test files in backtests/:
   - test_cache_isolation.py
   - test_trading_costs.py
   
   Status: KEEP (these test specific functionality)

3. Non-numbered test files in execution/:
   - test_concentration_limits.py
   - test_trailing_stop.py
   
   Status: KEEP (these test specific features)

4. Non-numbered test files in validation/:
   - test_oos_validator.py
   
   Status: KEEP (tests OOS validation framework)

EMPTY __init__.py files:
- Multiple empty __init__.py files across test folders
- Status: KEEP (these are standard Python package markers)

CYTHON MODULE TESTS WITH SKIP:
- 056_test_cython_module.py contains pytest.skip() calls
- Status: KEEP (conditional skips based on Cython availability)
""")

print("="*80)
print("END OF ANALYSIS")
print("="*80)
