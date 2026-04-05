<<<<<<< HEAD
﻿"""
Universe Module ÔÇö Trading universe management and symbol selection.

Provides:
    - UniverseManager: Central manager for tradeable symbol universe
    - Sector: Equity sector classification (deprecated ÔÇö use plain strings)
=======
"""
Universe Module — Trading universe management and symbol selection.

Provides:
    - UniverseManager: Central manager for tradeable symbol universe
    - Sector: Equity sector classification (deprecated — use plain strings)
>>>>>>> origin/main
    - UniverseSnapshot: Point-in-time universe state
    - IBKRUniverseScanner: Dynamic full-IBKR universe scanning
    - IBKRRateLimiter: Thread-safe IBKR API rate limiter
"""

from universe.manager import UniverseManager, Sector, UniverseSnapshot
from universe.scanner import IBKRUniverseScanner, ScannedSymbol, ScannerConfig
from universe.rate_limiter import IBKRRateLimiter

__all__ = [
    "UniverseManager", "Sector", "UniverseSnapshot",
    "IBKRUniverseScanner", "ScannedSymbol", "ScannerConfig",
    "IBKRRateLimiter",
]
