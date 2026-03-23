"""
Walk-Forward facade re-export shim (C-05 consolidation).

Source of truth: :mod:`backtests.walk_forward`.
Import from here for backwards compatibility; all logic lives upstream.
"""
# ruff: noqa: F401
from backtests.walk_forward import (
    WalkForwardBacktester,
    WalkForwardConfig,
    WalkForwardEngine,
    WalkForwardResult,
    split_walk_forward,
)

__all__ = [
    "WalkForwardBacktester",
    "WalkForwardConfig",
    "WalkForwardEngine",
    "WalkForwardResult",
    "split_walk_forward",
]
