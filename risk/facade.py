"""
Risk Facade ÔÇö Unified entry point composing RiskEngine + KillSwitch.

Provides a single API surface that both ``LiveTradingRunner`` and the
``StrategyBacktestSimulator`` can consume, eliminating the current
split where ``main.py`` uses ``risk.engine.RiskEngine`` while
``live_trading.runner`` uses ``risk_engine.KillSwitch`` separately.

Usage::

    facade = RiskFacade(initial_equity=100_000.0)

    # Pre-trade gate (combines position-level + kill-switch check)
    ok, reason = facade.can_enter_trade(
        symbol_pair="AAPL_MSFT",
        position_size=5000.0,
        current_equity=98_000.0,
        volatility=0.018,
        drawdown_pct=0.02,
    )

    # Kill-switch manual activation / query
    facade.activate_kill_switch("manual_halt")
    facade.is_halted  # True
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from structlog import get_logger

from risk.engine import RiskEngine, Position
from risk_engine.kill_switch import KillSwitch, KillSwitchConfig, KillReason

logger = get_logger(__name__)


class RiskFacade:
    """
    Unified risk management facade.

    Composes:
        * **RiskEngine**  ÔÇö per-trade sizing checks, position tracking,
          stop-loss monitoring, daily-loss / consecutive-loss counters.
        * **KillSwitch**  ÔÇö global halt on drawdown, data staleness,
          extreme volatility, or manual operator action.

    All risk queries go through :pymethod:`can_enter_trade` which checks
    the kill-switch first, then delegates to ``RiskEngine``.
    """

    def __init__(
        self,
        initial_equity: float,
        initial_cash: Optional[float] = None,
        kill_switch_config: Optional[KillSwitchConfig] = None,
        sector_map: Optional[Dict[str, str]] = None,
        kill_switch: Optional[KillSwitch] = None,
    ):
        self.risk_engine = RiskEngine(
            initial_equity=initial_equity,
            initial_cash=initial_cash,
        )
        if sector_map:
            self.risk_engine.sector_map = sector_map

        # Accept an externally-created KillSwitch so that the runner and the
        # facade always share a single instance (fixes B2-02 divergent state).
        if kill_switch is not None:
            self.kill_switch = kill_switch
        else:
            self.kill_switch = KillSwitch(
                config=kill_switch_config or KillSwitchConfig(),
            )

        logger.info(
            "risk_facade_initialized",
            initial_equity=initial_equity,
            kill_switch_active=self.kill_switch.is_active,
        )

    # ------------------------------------------------------------------
    # Trade gate (main entry point)
    # ------------------------------------------------------------------

    def can_enter_trade(
        self,
        symbol_pair: str,
        position_size: float,
        current_equity: float,
        volatility: float,
        *,
        drawdown_pct: float = 0.0,
        daily_loss_pct: float = 0.0,
        consecutive_losses: int = 0,
        seconds_since_last_data: float = 0.0,
        current_vol: float = 0.0,
        historical_vol_mean: float = 0.0,
    ) -> Tuple[bool, Optional[str]]:
        """
        Unified pre-trade gate.

        1. Run kill-switch checks (global halt).
        2. If not halted, delegate to ``RiskEngine.can_enter_trade()``.
        """
        # Kill-switch check
        halted = self.kill_switch.check(
            drawdown_pct=drawdown_pct,
            daily_loss_pct=daily_loss_pct,
            consecutive_losses=consecutive_losses,
            seconds_since_last_data=seconds_since_last_data,
            current_vol=current_vol,
            historical_vol_mean=historical_vol_mean,
        )
        if halted or self.kill_switch.is_active:
            reason = f"Kill-switch active: {self.kill_switch.reason.value}"
            return False, reason

        # Delegate to RiskEngine for position-level checks
        return self.risk_engine.can_enter_trade(
            symbol_pair=symbol_pair,
            position_size=position_size,
            current_equity=current_equity,
            volatility=volatility,
        )

    # ------------------------------------------------------------------
    # Kill-switch delegation
    # ------------------------------------------------------------------

    @property
    def is_halted(self) -> bool:
        """True if the kill-switch is active (trading halted)."""
        return self.kill_switch.is_active

    def activate_kill_switch(self, reason: str = "manual") -> None:
        """Manually activate the kill-switch."""
        self.kill_switch.activate(KillReason.MANUAL, message=reason)

    def reset_kill_switch(self) -> None:
        """Reset the kill-switch (operator action)."""
        self.kill_switch.reset()

    # ------------------------------------------------------------------
    # RiskEngine delegation
    # ------------------------------------------------------------------

    def register_entry(self, symbol_pair: str, entry_price: float,
                       quantity: float, side: str) -> None:
        self.risk_engine.register_entry(symbol_pair, entry_price, quantity, side)

    def register_exit(self, symbol_pair: str, exit_price: float, pnl: float) -> Optional[object]:
        return self.risk_engine.register_exit(symbol_pair, exit_price, pnl)

    def mark_to_market(self, prices: Dict[str, float]) -> None:
        self.risk_engine.mark_to_market(prices)

    def check_position_stops(self) -> List[dict]:
        return self.risk_engine.check_position_stops()

    def save_equity_snapshot(self) -> None:
        self.risk_engine.save_equity_snapshot()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def positions(self) -> Dict[str, Position]:
        return self.risk_engine.positions

    @property
    def current_equity(self) -> float:
        return self.risk_engine.current_equity

    @property
    def sector_map(self) -> Dict[str, str]:
        return self.risk_engine.sector_map

    @sector_map.setter
    def sector_map(self, value: Dict[str, str]) -> None:
        self.risk_engine.sector_map = value
