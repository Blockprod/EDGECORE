"""
Signal Engine Module — Z-score computation, adaptive thresholds, signal generation.

Provides:
    - ZScoreCalculator: Spread z-score with half-life adaptive lookback
    - AdaptiveThresholdEngine: Regime-aware entry/exit thresholds
    - SignalGenerator: Unified signal generation pipeline
    - Signal: Typed trading signal
"""

from signal_engine.zscore import ZScoreCalculator
from signal_engine.adaptive import AdaptiveThresholdEngine
from signal_engine.generator import SignalGenerator, Signal

__all__ = [
    "ZScoreCalculator",
    "AdaptiveThresholdEngine",
    "SignalGenerator",
    "Signal",
]
