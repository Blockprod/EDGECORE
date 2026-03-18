from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, cast

import numpy as np
from structlog import get_logger

import config.settings as settings_mod
from common.validators import (
    EquityError,
    validate_equity,
    validate_position_size,
    validate_volatility,
)
from monitoring.events import EventType, TradingEvent
from persistence.audit_trail import AuditTrail

logger = get_logger(__name__)

@dataclass
class Position:
    """Active position record."""
    symbol_pair: str
    entry_time: datetime
    entry_price: float
    quantity: float
    side: str  # "long" or "short"
    pnl: float = 0.0
    marked_price: float = 0.0
    current_price: float = 0.0  # Current market price for P&L calculation
    stop_loss_pct: float = 0.05  # Default 5% stop-loss
    
    @property
    def pnl_pct(self) -> float:
        """Calculate P&L percentage based on side."""
        if self.entry_price == 0:
            return 0.0
        
        price_to_use = self.current_price if self.current_price > 0 else self.marked_price
        
        if self.side == "long":
            return (price_to_use - self.entry_price) / self.entry_price
        else:  # short
            return (self.entry_price - price_to_use) / self.entry_price
    
    def should_stop_out(self) -> bool:
        """Check if position should be closed at stop-loss level."""
        return abs(self.pnl_pct) >= self.stop_loss_pct

class RiskEngine:
    """
    Independent risk management system.
    
    Enforces:
    - Per-trade risk limits
    - Portfolio concentration
    - Consecutive loss limits
    - Daily drawdown limits
    - Volatility regime checks
    """
    
    def __init__(self, initial_equity: float, initial_cash: Optional[float] = None):
        """
        Initialize risk engine with capital constraints.
        
        Args:
            initial_equity: Starting equity (required, validated)
            initial_cash: Starting cash available (defaults to initial_equity)
        
        Raises:
            EquityError: If initial_equity is invalid
        """
        # Validate initial equity
        validate_equity(initial_equity)
        
        self.config = settings_mod.get_settings().risk
        self.initial_equity = initial_equity
        self.initial_cash = initial_cash if initial_cash is not None else initial_equity
        
        # Validate cash constraint
        if self.initial_cash < 0 or self.initial_cash > self.initial_equity:
            raise EquityError(
                f"Initial cash ({self.initial_cash}) must be between 0 and "
                f"initial_equity ({self.initial_equity})"
            )
        
        self.positions: Dict[str, Position] = {}
        self.equity_history: List[float] = [self.initial_equity]
        self.loss_streak = 0
        self.daily_trades = 0
        self.daily_loss = 0.0
        # Sector map: symbol -> sector string (e.g. {"AAPL": "Technology"})
        self.sector_map: Dict[str, str] = {}
        self._daily_date = datetime.now().date()  # track date for auto-reset
        
        # Initialize persistent audit trail for crash recovery
        self.audit_trail = AuditTrail()
        self.current_equity = initial_equity  # Track current for logging
        
        logger.info(
            "risk_engine_initialized",
            initial_equity=initial_equity,
            initial_cash=self.initial_cash,
            max_concurrent_positions=self.config.max_concurrent_positions,
            audit_trail_enabled=True
        )
    
    def can_enter_trade(
        self,
        symbol_pair: str,
        position_size: float,
        current_equity: float,
        volatility: float
    ) -> tuple[bool, Optional[str]]:
        """
        Check if trade can be entered given risk constraints.
        
        Args:
            symbol_pair: Trading pair
            position_size: Position size (units)
            current_equity: Current portfolio equity
            volatility: Current volatility estimate
        
        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
        
        Raises:
            EquityError, ValidationError: If any input is invalid
        """
        # VALIDATION: All inputs must be valid before checking logic
        try:
            validate_equity(current_equity)
            validate_position_size(position_size)
            validate_volatility(volatility)
        except Exception as e:
            logger.error("trade_entry_validation_failed", error=str(e))
            raise

        # --- Single risk-per-trade calculation (C-15: was duplicated 3×) ---
        risk_pct, current_leverage = self._compute_risk_metrics(
            position_size, volatility, current_equity
        )

        # Check 1: Risk per trade
        if risk_pct > self.config.max_risk_per_trade:
            reason = f"Risk per trade ({risk_pct:.4f}) exceeds limit ({self.config.max_risk_per_trade}) [risk]"
            logger.warning("trade_rejected_risk", reason=reason, pair=symbol_pair)
            return False, reason

        # Check 2: Leverage constraint
        if current_leverage > self.config.max_leverage:
            reason = f"Leverage {current_leverage:.2f}x exceeds limit {self.config.max_leverage}x [leverage]"
            logger.warning("trade_rejected_leverage", reason=reason, pair=symbol_pair, current_leverage=current_leverage)
            return False, reason

        # Check 3: Max concurrent positions
        if len(self.positions) >= self.config.max_concurrent_positions:
            reason = f"Max concurrent positions ({self.config.max_concurrent_positions}) reached"
            logger.warning("trade_rejected", reason=reason, pair=symbol_pair)
            try:
                from monitoring.alerter import AlertCategory, AlertManager, AlertSeverity
                AlertManager().create_alert(
                    severity=AlertSeverity.CRITICAL,
                    category=AlertCategory.RISK,
                    title="Max concurrent positions limit breached",
                    message=reason,
                    data={"pair": symbol_pair}
                )
            except Exception as alert_exc:
                logger.error("alert_trigger_failed", error=str(alert_exc), reason=reason)
            return False, reason

        # Check 4: Consecutive losses
        if self.loss_streak >= self.config.max_consecutive_losses:
            return False, f"Consecutive loss limit ({self.config.max_consecutive_losses}) exceeded"

        # Check 5: Daily loss (auto-reset if new calendar day)
        self._maybe_reset_daily()
        try:
            daily_loss_pct = self.daily_loss / current_equity
        except ZeroDivisionError as e:
            logger.error(
                "daily_loss_division_error",
                error=str(e),
                daily_loss=self.daily_loss,
                current_equity=current_equity
            )
            raise EquityError(f"Division by zero in daily loss check: equity={current_equity}")

        if daily_loss_pct > self.config.max_daily_loss_pct:
            reason = f"Daily loss ({daily_loss_pct:.4f}) exceeds limit ({self.config.max_daily_loss_pct})"
            logger.warning("trade_rejected", reason=reason)
            try:
                from monitoring.alerter import AlertCategory, AlertManager, AlertSeverity
                AlertManager().create_alert(
                    severity=AlertSeverity.CRITICAL,
                    category=AlertCategory.RISK,
                    title="Daily loss limit breached",
                    message=reason,
                    data={"daily_loss_pct": daily_loss_pct, "current_equity": current_equity}
                )
            except Exception as alert_exc:
                logger.error("alert_trigger_failed", error=str(alert_exc), reason=reason)
            return False, reason

        # Check 6: Sector concentration
        if self.sector_map:
            sector = self._get_sector_for_pair(symbol_pair)
            if sector is not None:
                sector_count = sum(
                    1 for sp in self.positions
                    if self._get_sector_for_pair(sp) == sector
                )
                total_positions = len(self.positions) + 1  # including the new one
                sector_weight = (sector_count + 1) / max(total_positions, 1)
                if sector_weight > self.config.max_sector_weight:
                    reason = (
                        f"Sector concentration ({sector}: {sector_weight:.0%}) "
                        f"exceeds limit ({self.config.max_sector_weight:.0%})"
                    )
                    logger.warning("trade_rejected_sector", reason=reason, pair=symbol_pair, sector=sector)
                    return False, reason

        logger.info(
            "trade_approved",
            symbol_pair=symbol_pair,
            position_size=position_size,
            risk_pct=risk_pct
        )
        return True, None

    def _compute_risk_metrics(
        self,
        position_size: float,
        volatility: float,
        current_equity: float,
    ) -> tuple[float, float]:
        """Compute risk_pct and current_leverage for a prospective trade.

        Extracted from ``can_enter_trade`` (C-15) to eliminate triple duplication.

        Returns:
            (risk_pct, current_leverage) — both as fractions (not percentages).

        Raises:
            EquityError: If current_equity is zero (division by zero).
        """
        if current_equity <= 0:
            raise EquityError(
                f"Cannot compute risk metrics: current_equity must be positive, got {current_equity}"
            )
        risk_amount = position_size * volatility
        risk_pct = risk_amount / current_equity

        current_exposure = self.get_total_exposure()
        new_position_exposure = position_size * (1.0 + volatility)
        total_with_new = current_exposure + new_position_exposure
        current_leverage = total_with_new / current_equity

        return risk_pct, current_leverage

    def _get_sector_for_pair(self, symbol_pair: str) -> Optional[str]:
        """Return the sector for a symbol pair, or None if unknown.

        Pair keys use ``SYM1_SYM2`` convention.  If both symbols are in
        ``self.sector_map`` and share a sector, that sector is returned.
        If only one matches, its sector is used. Otherwise ``None``.
        """
        parts = symbol_pair.split("_")
        sectors = [self.sector_map.get(p) for p in parts if self.sector_map.get(p)]
        if not sectors:
            return None
        return sectors[0]

    def get_total_exposure(self) -> float:
        """
        Calculate total notional exposure across all positions.
        
        Returns:
            Total exposure as absolute value (always >= 0)
        """
        total_exposure = 0.0
        for position in self.positions.values():
            if position.marked_price > 0:
                position_exposure = abs(position.quantity * position.marked_price)
                total_exposure += position_exposure
        return total_exposure
    
    def check_position_stops(self) -> List[dict]:
        """
        Check all positions for stop-loss violations.
        
        Returns:
            List of dicts with positions that should be closed:
            [
                {
                    'symbol': 'AAPL',
                    'entry_price': 175.0,
                    'current_price': 166.25,
                    'pnl_pct': -0.05,
                    'reason': 'Stop-loss: -5.00%',
                    'quantity': 1.0
                }
            ]
        """
        positions_to_close = []
        
        for symbol, position in self.positions.items():
            if position.should_stop_out():
                positions_to_close.append({
                    'symbol': symbol,
                    'entry_price': position.entry_price,
                    'current_price': position.current_price or position.marked_price,
                    'pnl_pct': position.pnl_pct,
                    'reason': f"Stop-loss: {position.pnl_pct:.2%}",
                    'quantity': position.quantity,
                    'position_object': position  # Include position for action
                })
                
                logger.warning(
                    "position_stop_loss_triggered",
                    symbol=symbol,
                    entry_price=position.entry_price,
                    current_price=position.current_price or position.marked_price,
                    pnl_pct=f"{position.pnl_pct:.2%}",
                    stop_loss_pct=f"{position.stop_loss_pct:.2%}"
                )
        
        return positions_to_close
    
    def load_from_audit_trail(self) -> Dict[str, Position]:
        """
        Recover positions and equity history from persistent audit trail.
        
        Called on startup to restore state after crash.
        
        Returns:
            Dictionary of recovered open positions (empty if no trail)
        
        Raises:
            EquityError: If trail is corrupted
        """
        try:
            recovered_positions, recovered_equity_history = self.audit_trail.recover_state()
            
            if recovered_positions:
                self.positions = cast(Dict[str, Position], recovered_positions)
                logger.warning(
                    "positions_recovered_from_trail",
                    count=len(recovered_positions),
                    symbols=list(recovered_positions.keys())
                )
            
            if recovered_equity_history:
                self.equity_history = recovered_equity_history
                self.current_equity = recovered_equity_history[-1]
                logger.warning(
                    "equity_history_recovered",
                    entries=len(recovered_equity_history),
                    last_equity=self.current_equity
                )
            
            return cast(Dict[str, Position], recovered_positions)
        
        except Exception as e:
            logger.error("audit_trail_recovery_failed", error=str(e))
            raise
    
    def register_entry(
        self,
        symbol_pair: str,
        entry_price: float,
        quantity: float,
        side: str
    ) -> None:
        """Register a new position entry and persist to audit trail."""
        self.positions[symbol_pair] = Position(
            symbol_pair=symbol_pair,
            entry_time=datetime.now(),
            entry_price=entry_price,
            quantity=quantity,
            side=side
        )
        
        # Log to persistent audit trail
        try:
            event = TradingEvent(
                event_type=EventType.TRADE_ENTRY,
                timestamp=datetime.now(),
                symbol_pair=symbol_pair,
                position_size=quantity,
                entry_price=entry_price,
                reason=side
            )
            self.audit_trail.log_trade_event(event, self.current_equity)
        except Exception as e:
            logger.error("entry_audit_log_failed", error=str(e), symbol_pair=symbol_pair)
            raise
        
        logger.info(
            "position_entered",
            symbol_pair=symbol_pair,
            side=side,
            quantity=quantity,
            price=entry_price,
            persisted=True
        )
    
    def register_exit(
        self,
        symbol_pair: str,
        exit_price: float,
        pnl: float
    ) -> Optional[TradingEvent]:
        """
        Register position exit, track loss streak, and persist to audit trail.
        
        Returns:
            TradingEvent if position exists, else None
        """
        if symbol_pair not in self.positions:
            logger.warning("exit_no_position", symbol_pair=symbol_pair)
            return None
        
        position = self.positions.pop(symbol_pair)
        
        if pnl < 0:
            self.loss_streak += 1
            self.daily_loss += abs(pnl)
        else:
            self.loss_streak = 0
        
        event = TradingEvent(
            event_type=EventType.TRADE_EXIT,
            timestamp=datetime.now(),
            symbol_pair=symbol_pair,
            position_size=position.quantity,
            exit_price=exit_price,
            pnl=pnl
        )
        
        # Log to persistent audit trail
        try:
            self.audit_trail.log_trade_event(event, self.current_equity)
        except Exception as e:
            logger.error("exit_audit_log_failed", error=str(e), symbol_pair=symbol_pair)
            raise
        
        logger.info(
            "position_exited",
            symbol_pair=symbol_pair,
            pnl=pnl,
            loss_streak=self.loss_streak,
            persisted=True
        )
        
        return event
    
    def mark_to_market(self, prices: Dict[str, float]) -> None:
        """Update unrealized P&L for all positions."""
        for pair, position in self.positions.items():
            if pair in prices:
                position.marked_price = prices[pair]
                if position.side == "long":
                    position.pnl = position.quantity * (prices[pair] - position.entry_price)
                else:
                    position.pnl = position.quantity * (position.entry_price - prices[pair])
    
    def check_volatility_regime(
        self,
        volatility: float,
        historical_vol: np.ndarray,
        percentile: float = 95
    ) -> bool:
        """
        Check if current volatility breaks historical bounds (regime break).
        
        Args:
            volatility: Current realized volatility
            historical_vol: Historical volatility distribution
            percentile: Percentile threshold
        
        Returns:
            True if regime is normal, False if broken
        """
        vol_threshold = np.percentile(historical_vol, percentile)
        is_normal = volatility < vol_threshold * self.config.volatility_percentile_threshold
        
        if not is_normal:
            logger.warning(
                "volatility_regime_break",
                current_vol=volatility,
                threshold=vol_threshold
            )
        
        return bool(is_normal)
    
    def reset_daily_stats(self) -> None:
        """Reset daily counters (call at market open)."""
        self.daily_trades = 0
        self.daily_loss = 0.0
        self._daily_date = datetime.now().date()

    def _maybe_reset_daily(self) -> None:
        """Auto-reset daily counters when the calendar date rolls over."""
        today = datetime.now().date()
        if self._daily_date != today:
            self.daily_trades = 0
            self.daily_loss = 0.0
            self._daily_date = today
    
    def save_equity_snapshot(self) -> None:
        """
        Save current equity and position snapshot to persistent trail.
        
        Call periodically (e.g., at market close) for reconciliation.
        
        Raises:
            EquityError: If snapshot cannot be persisted
        """
        try:
            positions_list = ",".join(self.positions.keys())
            self.audit_trail.log_equity_snapshot(
                current_equity=self.current_equity,
                positions_count=len(self.positions),
                positions_list=positions_list
            )
            logger.info(
                "equity_snapshot_saved",
                equity=self.current_equity,
                positions_count=len(self.positions)
            )
        except Exception as e:
            logger.error("snapshot_save_failed", error=str(e))
            raise
