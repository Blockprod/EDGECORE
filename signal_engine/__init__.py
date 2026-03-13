"""
Signal Engine Module -- Z-score computation, adaptive thresholds, signal generation.

Provides:
    - ZScoreCalculator: Spread z-score with half-life adaptive lookback
    - AdaptiveThresholdEngine: Regime-aware entry/exit thresholds
    - SignalGenerator: Unified signal generation pipeline
    - Signal: Typed trading signal
    - MomentumOverlay: Relative strength overlay (v31)
    - SignalCombiner: Weighted signal ensemble (v31)
    - OUSignalGenerator: Ornstein-Uhlenbeck reversion velocity (v32)
    - CrossSectionalMomentum: Cross-sectional ranking (v32)
    - VolatilityRegimeSignal: Vol compression/expansion (v32)
"""

from signal_engine.zscore import ZScoreCalculator
from signal_engine.adaptive import AdaptiveThresholdEngine
from signal_engine.generator import SignalGenerator, Signal
from signal_engine.momentum import MomentumOverlay
from signal_engine.combiner import SignalCombiner, SignalSource, CompositeSignal
from signal_engine.ou_signal import OUSignalGenerator, OUParams
from signal_engine.cross_sectional import CrossSectionalMomentum
from signal_engine.vol_signal import VolatilityRegimeSignal

__all__ = [
    "ZScoreCalculator",
    "AdaptiveThresholdEngine",
    "SignalGenerator",
    "Signal",
    "MomentumOverlay",
    "SignalCombiner",
    "SignalSource",
    "CompositeSignal",
    "OUSignalGenerator",
    "OUParams",
    "CrossSectionalMomentum",
    "VolatilityRegimeSignal",
]
