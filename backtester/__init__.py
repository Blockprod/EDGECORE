<<<<<<< HEAD
# backtester: façades wrapping backtests/ (C-05: public API exports)
# ruff: noqa: F401
from backtester.oos import OOSConfig, OOSReport, OOSValidationEngine
from backtester.runner import BacktestConfig, BacktestEngine, BacktestResult
from backtester.walk_forward import (
    WalkForwardBacktester,
    WalkForwardConfig,
    WalkForwardEngine,
    WalkForwardResult,
    split_walk_forward,
)

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
    "OOSConfig",
    "OOSReport",
    "OOSValidationEngine",
    "WalkForwardBacktester",
    "WalkForwardConfig",
    "WalkForwardEngine",
    "WalkForwardResult",
    "split_walk_forward",
]
=======
"""
Backtester Module — Unified backtesting infrastructure.

Provides:
    - BacktestEngine:          High-level backtest orchestrator
    - WalkForwardEngine:       Walk-forward cross-validation harness
    - OOSValidationEngine:     Out-of-sample validation wrapper
"""

from backtester.runner import BacktestEngine
from backtester.walk_forward import WalkForwardEngine
from backtester.oos import OOSValidationEngine

__all__ = ["BacktestEngine", "WalkForwardEngine", "OOSValidationEngine"]
>>>>>>> origin/main
