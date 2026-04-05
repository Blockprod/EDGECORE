#!/usr/bin/env python3
"""Fix encoding issues in test files."""

from pathlib import Path

# Fix test_deployment.py
test_file = Path('tests/test_deployment.py')
content = test_file.read_text(encoding='utf-8')
fixed = content.replace('.read_text()', ".read_text(encoding='utf-8')")
test_file.write_text(fixed, encoding='utf-8')
print(f"Fixed {test_file}")

print("Done!")
