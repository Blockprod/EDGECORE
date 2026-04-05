<<<<<<< HEAD
﻿"""
Pair Selection Module ÔÇö Cointegrated pair discovery and filtering.
=======
"""
Pair Selection Module — Cointegrated pair discovery and filtering.
>>>>>>> origin/main

Provides:
    - PairDiscoveryEngine: Orchestrates pair screening and cointegration testing
    - PairFilters: Pre-filters for candidate pair screening
    - CointegratedPair: Typed result from pair discovery
"""

from pair_selection.discovery import PairDiscoveryEngine, CointegratedPair
from pair_selection.filters import PairFilters

__all__ = ["PairDiscoveryEngine", "CointegratedPair", "PairFilters"]
