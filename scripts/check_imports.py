#!/usr/bin/env python3
"""Check for broken imports in test files."""

import re
from pathlib import Path
from importlib.util import find_spec

test_dir = Path("C:\\Users\\averr\\EDGECORE\\tests")
root_dir = Path("C:\\Users\\averr\\EDGECORE")

# List of known module roots that should exist
known_modules = {
    'backtests', 'common', 'config', 'data', 'edgecore', 'execution',
    'models', 'monitoring', 'persistence', 'research', 'risk', 'scripts',
    'strategies', 'validation'
}

def extract_imports(filepath):
    """Extract import statements from a file."""
    imports = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Match: import X, from X import Y
            patterns = [
                r'^from\s+([\w.]+)\s+import\s+',
                r'^import\s+([\w.]+)',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                imports.extend(matches)
    except:
        pass
    return imports

def is_broken_import(module_name):
    """Check if a module import is broken."""
    # Skip standard library and third-party imports
    stdlib_modules = {
        'sys', 'os', 're', 'json', 'csv', 'datetime', 'pathlib', 
        'unittest', 'pytest', 'typing', 'collections', 'functools',
        'itertools', 'logging', 'pickle', 'numpy', 'pandas', 'scipy',
        'sklearn', 'warnings', 'copy', 'hashlib', 'uuid', 'random',
        'dataclasses', 'abc', 'enum', 'tempfile', 'shutil'
    }
    
    base_module = module_name.split('.')[0]
    
    if base_module in stdlib_modules:
        return False
    
    if base_module in known_modules:
        # Check if it exists
        try:
            find_spec(base_module)
            return False
        except (ImportError, ModuleNotFoundError, ValueError):
            return True
    
    # Try to import it
    try:
        find_spec(module_name)
        return False
    except (ImportError, ModuleNotFoundError, ValueError):
        return True

print("\n" + "="*80)
print("CHECKING FOR BROKEN IMPORTS IN TEST FILES")
print("="*80)

broken_files = []
all_imports = {}

for test_file in sorted(test_dir.rglob("test_*.py")) + sorted(test_dir.rglob("[0-9]*_test_*.py")):
    if "__pycache__" in str(test_file):
        continue
    
    imports = extract_imports(test_file)
    if not imports:
        continue
    
    # Filter to project-specific imports
    project_imports = [imp for imp in imports if imp.split('.')[0] in known_modules]
    
    if project_imports:
        broken_for_file = [imp for imp in project_imports if is_broken_import(imp)]
        
        if broken_for_file:
            rel_path = test_file.relative_to(test_dir)
            print(f"\nÔÜá´©Å  {rel_path}")
            for imp in broken_for_file:
                print(f"   BROKEN: from {imp} import ...")
            broken_files.append((test_file, broken_for_file))
        else:
            # Mark as good
            all_imports[str(test_file)] = project_imports

if not broken_files:
    print("\nÔ£à No broken imports found!")
    print(f"   Analyzed {len(all_imports)} files with valid imports")
else:
    print(f"\nÔÜá´©Å  Found {len(broken_files)} files with potential broken imports")

print("\n" + "="*80)
