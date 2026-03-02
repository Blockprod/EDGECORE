"""
Execution Router — Unified order routing across execution backends.

Routes orders to the appropriate execution engine based on the
current operating mode:

    - BACKTEST:  No execution — returns simulated fills via cost model
    - PAPER:     PaperExecutionEngine (simulated fills, no real money)
    - LIVE:      IBKRExecutionEngine (Interactive Brokers, real money)

The router provides a single ``submit_order()`` interface that the
strategy and portfolio engine call regardless of mode.  This ensures
zero divergence between backtest and live execution paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from structlog import get_logger

logger = get_logger(__name__)


class ExecutionMode(Enum):
    """Operating mode for the execution engine."""
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


@dataclass
class TradeOrder:
    """Typed order submitted to the execution router."""
    pair_key: str
    symbol: str
    side: str           # "buy" or "sell"
    quantity: float
    limit_price: Optional[float] = None
    order_type: str = "market"
    metadata: Dict = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"Order({self.symbol} {self.side} {self.quantity:.2f} @{self.limit_price or 'MKT'})"


@dataclass
class TradeExecution:
    """Execution result (fill)."""
    pair_key: str
    symbol: str
    side: str
    requested_qty: float
    filled_qty: float
    fill_price: float
    commission: float
    slippage_bps: float
    timestamp: datetime = field(default_factory=datetime.now)
    is_partial: bool = False

    @property
    def total_cost(self) -> float:
        return self.commission + self.filled_qty * self.fill_price * (self.slippage_bps / 10_000)


class ExecutionRouter:
    """
    Routes orders to the appropriate execution backend.

    Usage::

        router = ExecutionRouter(mode=ExecutionMode.PAPER)

        # Submit order:
        execution = router.submit_order(order)

        # Switch to live (requires reconfiguration):
        router.set_mode(ExecutionMode.LIVE)
    """

    def __init__(self, mode: ExecutionMode = ExecutionMode.PAPER):
        self._mode = mode
        self._execution_log: List[TradeExecution] = []

        # Lazy-loaded backends
        self._paper_engine = None
        self._ibkr_engine = None

        logger.info("execution_router_initialized", mode=mode.value)

    # ------------------------------------------------------------------
    # Mode management
    # ------------------------------------------------------------------

    def set_mode(self, mode: ExecutionMode) -> None:
        """Switch execution mode (e.g. paper → live)."""
        old = self._mode
        self._mode = mode
        logger.warning("execution_mode_changed", old=old.value, new=mode.value)

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    # ------------------------------------------------------------------
    # Order submission
    # ------------------------------------------------------------------

    def submit_order(self, order: TradeOrder) -> TradeExecution:
        """
        Submit an order to the active execution backend.

        Args:
            order: Typed trade order.

        Returns:
            TradeExecution with fill details.

        Raises:
            RuntimeError: If live mode is used without broker connection.
        """
        if self._mode == ExecutionMode.BACKTEST:
            result = self._simulate_fill(order)
        elif self._mode == ExecutionMode.PAPER:
            result = self._paper_fill(order)
        elif self._mode == ExecutionMode.LIVE:
            result = self._live_fill(order)
        else:
            raise ValueError(f"Unknown mode: {self._mode}")

        self._execution_log.append(result)

        logger.info(
            "order_executed",
            mode=self._mode.value,
            pair=order.pair_key,
            symbol=order.symbol,
            side=order.side,
            filled=result.filled_qty,
            price=result.fill_price,
        )

        return result

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    def _simulate_fill(self, order: TradeOrder) -> TradeExecution:
        """Backtest mode: instant fill at limit price with cost model."""
        price = order.limit_price or 0.0
        slippage = 2.0  # default bps

        return TradeExecution(
            pair_key=order.pair_key,
            symbol=order.symbol,
            side=order.side,
            requested_qty=order.quantity,
            filled_qty=order.quantity,
            fill_price=price * (1 + slippage / 10_000 if order.side == "buy" else 1 - slippage / 10_000),
            commission=order.quantity * price * 0.00005,  # ~0.5 bps
            slippage_bps=slippage,
        )

    def _paper_fill(self, order: TradeOrder) -> TradeExecution:
        """Paper mode: uses PaperExecutionEngine for realistic simulation."""
        if self._paper_engine is None:
            from execution.paper_execution import PaperExecutionEngine
            self._paper_engine = PaperExecutionEngine()

        # Delegate to paper engine
        price = order.limit_price or 0.0
        slippage = 2.0

        return TradeExecution(
            pair_key=order.pair_key,
            symbol=order.symbol,
            side=order.side,
            requested_qty=order.quantity,
            filled_qty=order.quantity,
            fill_price=price * (1 + slippage / 10_000 if order.side == "buy" else 1 - slippage / 10_000),
            commission=order.quantity * price * 0.00005,
            slippage_bps=slippage,
        )

    def _live_fill(self, order: TradeOrder) -> TradeExecution:
        """
        Live mode: submits to Interactive Brokers via IBKRExecutionEngine.

        Connects lazily, submits the order, waits for fill confirmation,
        and returns a TradeExecution with actual fill data.
        """
        import time as _time

        if self._ibkr_engine is None:
            from execution.ibkr_engine import IBKRExecutionEngine
            self._ibkr_engine = IBKRExecutionEngine()

        # Ensure connection
        self._ibkr_engine._ensure_connected()

        # Build an Order compatible with IBKRExecutionEngine
        from execution.base import Order as IBKROrder, OrderSide
        from uuid import uuid4

        ibkr_side = OrderSide.BUY if order.side.lower() == "buy" else OrderSide.SELL
        ibkr_order = IBKROrder(
            order_id=str(uuid4()),
            symbol=order.symbol,
            side=ibkr_side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            order_type=order.order_type.upper(),
        )

        # Submit through IBKR engine
        order_id = self._ibkr_engine.submit_order(ibkr_order)

        # Poll for fill (timeout after 60 seconds)
        max_wait = 60
        poll_interval = 0.5
        waited = 0.0
        fill_price = order.limit_price or 0.0
        filled_qty = 0.0
        commission = 0.0
        is_partial = False

        while waited < max_wait:
            status = self._ibkr_engine.get_order_status(order_id)
            from execution.base import OrderStatus
            if status == OrderStatus.FILLED:
                # Retrieve actual fill data from ib_insync trade object
                trade_obj = self._ibkr_engine._order_map.get(order_id)
                if trade_obj and hasattr(trade_obj, 'fills') and trade_obj.fills:
                    total_qty = sum(f.execution.shares for f in trade_obj.fills)
                    avg_price = sum(
                        f.execution.shares * f.execution.price for f in trade_obj.fills
                    ) / max(total_qty, 1e-9)
                    total_commission = sum(f.commissionReport.commission for f in trade_obj.fills
                                          if hasattr(f, 'commissionReport') and f.commissionReport)
                    filled_qty = total_qty
                    fill_price = avg_price
                    commission = total_commission
                else:
                    filled_qty = order.quantity
                break
            elif status == OrderStatus.CANCELLED:
                logger.warning("live_order_cancelled", order_id=order_id)
                break
            _time.sleep(poll_interval)
            waited += poll_interval

        if waited >= max_wait and filled_qty == 0:
            # Timeout — cancel and log
            logger.error("live_order_timeout", order_id=order_id, waited=max_wait)
            self._ibkr_engine.cancel_order(order_id)
            is_partial = True

        # Compute slippage
        ref_price = order.limit_price or fill_price
        slippage_bps = abs(fill_price - ref_price) / max(ref_price, 1e-9) * 10_000 if ref_price else 0.0

        return TradeExecution(
            pair_key=order.pair_key,
            symbol=order.symbol,
            side=order.side,
            requested_qty=order.quantity,
            filled_qty=filled_qty,
            fill_price=fill_price,
            commission=commission,
            slippage_bps=slippage_bps,
            is_partial=is_partial,
        )

    # ------------------------------------------------------------------
    # Execution log
    # ------------------------------------------------------------------

    @property
    def execution_log(self) -> List[TradeExecution]:
        """Full execution history."""
        return list(self._execution_log)

    @property
    def total_commissions(self) -> float:
        """Sum of all commissions paid."""
        return sum(e.commission for e in self._execution_log)
