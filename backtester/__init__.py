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
