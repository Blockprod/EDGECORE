<<<<<<< HEAD
﻿#!/usr/bin/env python
=======
#!/usr/bin/env python
>>>>>>> origin/main
"""Quick test to verify backtest execution."""
import subprocess
import sys
import os

os.chdir(r"C:\Users\averr\EDGECORE")

print("="*80)
print("  RUNNING BACKTEST WITH PYTHON FALLBACK")
print("="*80)
print()

result = subprocess.run(
    [sys.executable, "main.py", "--mode", "backtest"],
    capture_output=False,
    text=True
)

sys.exit(result.returncode)
