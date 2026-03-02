"""
Execution Engine Module — Order routing and execution abstraction.

Provides:
    - ExecutionRouter: Routes orders to the appropriate execution backend
    - ExecutionMode: Enum for execution targets (backtest, paper, live)
"""

from execution_engine.router import ExecutionRouter, ExecutionMode

__all__ = ["ExecutionRouter", "ExecutionMode"]
