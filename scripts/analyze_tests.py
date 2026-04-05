<<<<<<< HEAD
﻿#!/usr/bin/env python3
=======
#!/usr/bin/env python3
>>>>>>> origin/main
"""Analyze test files for obsolete/redundant files."""

import re
from pathlib import Path
from collections import defaultdict

test_dir = Path("C:\\Users\\averr\\EDGECORE\\tests")

# Find all .py files
all_files = list(test_dir.rglob("*.py"))

# Organize by folder
by_folder = defaultdict(list)
for f in all_files:
    if f.parent.name != "__pycache__":
        by_folder[f.parent].append(f.name)

# Check for potential duplicates
potential_issues = []

for folder in [
    test_dir / "models",
    test_dir / "backtests",
    test_dir / "execution",
    test_dir / "validation",
    test_dir / "data",
    test_dir / "common",
    test_dir / "monitoring",
    test_dir / "integration",
    test_dir / "strategies",
    test_dir / "risk",
    test_dir / "config"
]:
    if folder not in by_folder:
        continue
    
    files = by_folder[folder]
    print(f"\n{'='*70}")
    print(f"FOLDER: {folder.name}")
    print(f"{'='*70}")
    
    # Separate numbered vs non-numbered
    numbered = [f for f in files if re.match(r'^\d{3}_', f)]
    non_numbered = [f for f in files if f.startswith('test_') and not re.match(r'^\d{3}_', f)]
    init_files = [f for f in files if f == '__init__.py']
    
    if non_numbered:
        print(f"\nNon-numbered test files ({len(non_numbered)}):")
        for f in sorted(non_numbered):
            print(f"  - {f}")
    
    if numbered:
        print(f"\nNumbered test files ({len(numbered)}):")
        for f in sorted(numbered):
            print(f"  - {f}")

    if init_files:
        print(f"\n__init__.py files ({len(init_files)}):")
        for f in sorted(init_files):
            print(f"  - {f}")

# Special check: __pycache__/__init__.py
pycache_init = test_dir / "__pycache__" / "__init__.py"
if pycache_init.exists():
    size = pycache_init.stat().st_size
    print(f"\n{'='*70}")
    print("SPECIAL CASE: __pycache__/__init__.py")
    print(f"  Path: {pycache_init}")
    print(f"  Size: {size} bytes")
    if size == 0:
        print("  Status: EMPTY FILE - OBSOLETE")
    print(f"{'='*70}")

print("\n\nDONE!")
