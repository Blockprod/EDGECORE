"""
Phase 2.3 — Portfolio VaR / CVaR Monitor.

Computes rolling historical VaR and CVaR (Expected Shortfall) at the
95% confidence level over a lookback window. When VaR exceeds a threshold
(default: 2% of NAV), a circuit-breaker signal is emitted.

Implementation uses historical simulation (no parametric assumptions).
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class VaRConfig:
    """Configuration for the VaR/CVaR monitor."""

    confidence_level: float = 0.95
    """Confidence level for VaR/CVaR (0.95 = 95%)."""

    lookback_window: int = 60
    """Number of daily returns for historical VaR estimation."""

    var_limit_pct: float = 0.02
    """Trip circuit breaker if 1-day VaR > this fraction of NAV."""

    min_observations: int = 20
    """Minimum returns needed before computing VaR."""


class VaRMonitor:
    """
    Rolling historical VaR / CVaR monitor.

    Usage::

        vm = VaRMonitor()

        # Each bar:
        vm.update(daily_return)
        var_95, cvar_95 = vm.current_var(), vm.current_cvar()
        is_ok, breach_info = vm.check_limit(portfolio_value)
    """

    def __init__(self, config: Optional[VaRConfig] = None):
        self.config = config or VaRConfig()
        self._returns: List[float] = []
        self._current_var: Optional[float] = None
        self._current_cvar: Optional[float] = None
        logger.info(
            "var_monitor_initialized",
            confidence=self.config.confidence_level,
            lookback=self.config.lookback_window,
            var_limit=f"{self.config.var_limit_pct:.1%}",
        )

    def update(self, daily_return: float) -> None:
        """Add a daily return observation and recompute VaR/CVaR."""
        self._returns.append(daily_return)

        # Keep only lookback window
        if len(self._returns) > self.config.lookback_window:
            self._returns = self._returns[-self.config.lookback_window:]

        if len(self._returns) >= self.config.min_observations:
            self._recompute()

    def _recompute(self) -> None:
        """Recompute VaR and CVaR from the return buffer."""
        arr = np.array(self._returns)
        alpha = 1.0 - self.config.confidence_level  # e.g. 0.05

        # VaR: the alpha-quantile of losses (negative returns)
        var_pct = float(np.percentile(arr, alpha * 100))
        self._current_var = -var_pct  # convention: VaR is positive

        # CVaR (Expected Shortfall): mean of returns below VaR
        tail = arr[arr <= var_pct]
        if len(tail) > 0:
            self._current_cvar = float(-np.mean(tail))
        else:
            self._current_cvar = self._current_var

    def current_var(self) -> Optional[float]:
        """Return current 1-day VaR as a positive fraction (e.g. 0.015 = 1.5%)."""
        return self._current_var

    def current_cvar(self) -> Optional[float]:
        """Return current 1-day CVaR (Expected Shortfall) as positive fraction."""
        return self._current_cvar

    def check_limit(self, portfolio_value: float) -> Tuple[bool, Optional[str]]:
        """Check if current VaR breaches the limit.

        Returns:
            (is_ok: bool, breach_info: Optional[str])
            is_ok is True when VaR is within limits or insufficient data.
        """
        if self._current_var is None:
            return True, None

        if self._current_var > self.config.var_limit_pct:
            breach_msg = (
                f"VAR_BREACH: 1d VaR95={self._current_var:.3%} "
                f"> limit {self.config.var_limit_pct:.1%} "
                f"(CVaR95={self._current_cvar:.3%}, "
                f"NAV=${portfolio_value:,.0f})"
            )
            logger.warning(
                "var_limit_breached",
                var_95=round(self._current_var, 5),
                cvar_95=round(self._current_cvar, 5) if self._current_cvar else None,
                limit=self.config.var_limit_pct,
                portfolio_value=round(portfolio_value, 2),
            )
            return False, breach_msg

        return True, None

    def get_report(self, portfolio_value: float) -> dict:
        """Return a risk report dict for logging/dashboard."""
        return {
            "var_95_pct": round(self._current_var, 5) if self._current_var else None,
            "cvar_95_pct": round(self._current_cvar, 5) if self._current_cvar else None,
            "var_95_usd": round(self._current_var * portfolio_value, 2) if self._current_var else None,
            "cvar_95_usd": round(self._current_cvar * portfolio_value, 2) if self._current_cvar else None,
            "observations": len(self._returns),
            "limit_pct": self.config.var_limit_pct,
        }

    def reset(self) -> None:
        """Clear all state."""
        self._returns.clear()
        self._current_var = None
        self._current_cvar = None


__all__ = ["VaRMonitor", "VaRConfig"]
