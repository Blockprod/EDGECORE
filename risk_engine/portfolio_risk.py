"""
Portfolio Risk Manager — Portfolio-level risk controls.

Monitors aggregate portfolio health:
    1. Portfolio drawdown (peak-to-trough)
    2. Daily loss accumulation
    3. Consecutive loss streak
    4. Maximum concurrent positions
    5. Portfolio heat (aggregate risk budget)

All checks are independent of the strategy — the risk manager only
sees portfolio-level metrics and enforces hard limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Tuple

from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class PortfolioRiskConfig:
    """Portfolio-level risk limits."""
    max_drawdown_pct: float = 0.15
    max_daily_loss_pct: float = 0.03
    max_consecutive_losses: int = 5
    max_concurrent_positions: int = 10
    max_portfolio_heat: float = 0.95
    circuit_breaker_cooldown_bars: int = 10


@dataclass
class PortfolioRiskState:
    """Current portfolio risk state — snapshot."""
    current_equity: float
    peak_equity: float
    drawdown_pct: float
    daily_loss_pct: float
    consecutive_losses: int
    open_positions: int
    portfolio_heat: float
    is_halted: bool
    halt_reason: str = ""


class PortfolioRiskManager:
    """
    Portfolio-level risk gate.

    Called before every trade entry to verify portfolio health.
    Also monitors running positions for circuit-breaker conditions.

    Usage::

        prm = PortfolioRiskManager(initial_equity=100_000)

        # Before entry:
        ok, reason = prm.can_open_position(position_risk_pct=0.02)

        # After trade result:
        prm.record_trade_result(pnl=-500)

        # Each bar:
        prm.update_equity(99_500)
        state = prm.get_state()
    """

    def __init__(
        self,
        initial_equity: float = 100_000.0,
        config: Optional[PortfolioRiskConfig] = None,
    ):
        self.config = config or PortfolioRiskConfig()
        self._initial_equity = initial_equity
        self._current_equity = initial_equity
        self._peak_equity = initial_equity
        self._equity_history: List[float] = [initial_equity]

        # Daily tracking
        self._daily_loss: float = 0.0
        self._daily_date: date = date.today()

        # Streak tracking
        self._consecutive_losses: int = 0

        # Position counting (caller must update)
        self._open_positions: int = 0

        # Circuit breaker
        self._is_halted: bool = False
        self._halt_reason: str = ""
        self._cooldown_remaining: int = 0

        logger.info(
            "portfolio_risk_manager_initialized",
            initial_equity=initial_equity,
            max_dd=f"{self.config.max_drawdown_pct:.0%}",
            max_daily_loss=f"{self.config.max_daily_loss_pct:.0%}",
        )

    # ------------------------------------------------------------------
    # Equity updates
    # ------------------------------------------------------------------

    def update_equity(self, equity: float) -> None:
        """Update current equity and recalculate drawdown."""
        self._current_equity = equity
        self._equity_history.append(equity)
        if equity > self._peak_equity:
            self._peak_equity = equity

        # Automatic circuit breaker check
        dd = self.drawdown_pct
        if dd >= self.config.max_drawdown_pct and not self._is_halted:
            self._halt("drawdown_breach", f"Drawdown {dd:.2%} >= {self.config.max_drawdown_pct:.0%}")

    def set_open_positions(self, count: int) -> None:
        """Update the number of currently open positions."""
        self._open_positions = count

    # ------------------------------------------------------------------
    # Trade result tracking
    # ------------------------------------------------------------------

    def record_trade_result(self, pnl: float) -> None:
        """Record a closed trade's P&L for streak and daily loss tracking."""
        self._maybe_reset_daily()

        if pnl < 0:
            self._consecutive_losses += 1
            self._daily_loss += abs(pnl)
        else:
            self._consecutive_losses = 0

        # Daily loss check
        if self._current_equity > 0:
            daily_pct = self._daily_loss / self._current_equity
            if daily_pct >= self.config.max_daily_loss_pct:
                self._halt("daily_loss", f"Daily loss {daily_pct:.2%}")

        # Consecutive loss check
        if self._consecutive_losses >= self.config.max_consecutive_losses:
            self._halt(
                "consecutive_losses",
                f"{self._consecutive_losses} consecutive losses",
            )

    # ------------------------------------------------------------------
    # Pre-trade gate
    # ------------------------------------------------------------------

    def can_open_position(
        self,
        position_risk_pct: float = 0.0,
    ) -> Tuple[bool, str]:
        """
        Check whether a new position can be opened.

        Args:
            position_risk_pct: Risk of proposed position as fraction of equity.

        Returns:
            (allowed, reason).
        """
        # Cooldown handling — log remaining time but do NOT auto-reset.
        # A halt MUST be cleared by an explicit manual_reset() call.
        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1
            logger.info(
                "portfolio_risk_cooldown_tick",
                remaining=self._cooldown_remaining,
            )

        if self._is_halted:
            return False, f"HALTED: {self._halt_reason} (requires manual_reset)"

        if self._open_positions >= self.config.max_concurrent_positions:
            return False, f"Max positions ({self.config.max_concurrent_positions}) reached"

        dd = self.drawdown_pct
        if dd >= self.config.max_drawdown_pct:
            return False, f"Drawdown {dd:.2%} >= limit"

        self._maybe_reset_daily()
        if self._current_equity > 0:
            daily_pct = self._daily_loss / self._current_equity
            if daily_pct >= self.config.max_daily_loss_pct:
                return False, f"Daily loss limit reached ({daily_pct:.2%})"

        if self._consecutive_losses >= self.config.max_consecutive_losses:
            return False, f"Consecutive losses ({self._consecutive_losses})"

        # Portfolio heat check
        current_heat = (self._open_positions * position_risk_pct) if position_risk_pct > 0 else 0
        if current_heat >= self.config.max_portfolio_heat:
            return False, f"Portfolio heat {current_heat:.2%} >= {self.config.max_portfolio_heat:.0%}"

        return True, ""

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def drawdown_pct(self) -> float:
        if self._peak_equity <= 0:
            return 0.0
        return (self._peak_equity - self._current_equity) / self._peak_equity

    def get_state(self) -> PortfolioRiskState:
        """Return current portfolio risk snapshot."""
        self._maybe_reset_daily()
        daily_pct = (
            self._daily_loss / self._current_equity
            if self._current_equity > 0
            else 0.0
        )
        return PortfolioRiskState(
            current_equity=self._current_equity,
            peak_equity=self._peak_equity,
            drawdown_pct=self.drawdown_pct,
            daily_loss_pct=daily_pct,
            consecutive_losses=self._consecutive_losses,
            open_positions=self._open_positions,
            portfolio_heat=0.0,  # placeholder
            is_halted=self._is_halted,
            halt_reason=self._halt_reason,
        )

    # ------------------------------------------------------------------
    # Halt / Reset
    # ------------------------------------------------------------------

    def _halt(self, reason_code: str, message: str) -> None:
        self._is_halted = True
        self._halt_reason = message
        self._cooldown_remaining = self.config.circuit_breaker_cooldown_bars
        logger.critical(
            "portfolio_risk_HALTED",
            reason=reason_code,
            message=message,
            equity=self._current_equity,
            drawdown=f"{self.drawdown_pct:.2%}",
        )

    def _reset_halt(self) -> None:
        self._is_halted = False
        self._halt_reason = ""
        logger.info("portfolio_risk_halt_reset")

    def manual_reset(self) -> None:
        """Manually reset the halt state (requires operator action)."""
        self._reset_halt()
        self._consecutive_losses = 0
        self._daily_loss = 0.0
        logger.warning("portfolio_risk_manual_reset")

    def _maybe_reset_daily(self) -> None:
        today = date.today()
        if self._daily_date != today:
            self._daily_loss = 0.0
            self._daily_date = today
