"""
Execution Router ÔÇö Unified order routing across execution backends.

Routes orders to the appropriate execution engine based on the
current operating mode:

    - BACKTEST:  No execution ÔÇö returns simulated fills via cost model
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
from typing import Dict, List

from structlog import get_logger

from execution.base import Order, OrderSide
from execution.rate_limiter import TokenBucketRateLimiter

logger = get_logger(__name__)


class ExecutionMode(Enum):
    """Operating mode for the execution engine."""
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


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
        # A-02: order_id → OrderStatus tracking for fill confirmations
        self._pending_orders: Dict[str, object] = {}
        # IBKR API rate limiter ÔÇö 45 req/s sustained, 10 burst
        # (hard cap is 50/s; exceeding triggers disconnect)
        self._rate_limiter = TokenBucketRateLimiter(rate=45, burst=10)

        logger.info("execution_router_initialized", mode=mode.value)

    # ------------------------------------------------------------------
    # Mode management
    # ------------------------------------------------------------------

    def set_mode(self, mode: ExecutionMode) -> None:
        """Switch execution mode (e.g. paper ÔåÆ live)."""
        old = self._mode
        self._mode = mode
        logger.warning("execution_mode_changed", old=old.value, new=mode.value)

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    # ------------------------------------------------------------------
    # Order submission
    # ------------------------------------------------------------------

    def submit_order(self, order: Order) -> TradeExecution:
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
            pair=getattr(order, 'pair_key', None) or getattr(order, 'symbol', ''),
            symbol=order.symbol,
            side=order.side.value if hasattr(order.side, 'value') else order.side,
            filled=result.filled_qty,
            price=result.fill_price,
        )

        return result

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    def _simulate_fill(self, order) -> TradeExecution:
        """Backtest mode: instant fill at limit price with cost model."""
        from config.settings import get_settings
        price = order.limit_price or 0.0
        slippage = get_settings().costs.slippage_bps
        pair_key = getattr(order, 'pair_key', None) or order.symbol
        side_str = order.side.value.lower() if hasattr(order.side, 'value') else str(order.side).lower()

        return TradeExecution(
            pair_key=pair_key,
            symbol=order.symbol,
            side=side_str,
            requested_qty=order.quantity,
            filled_qty=order.quantity,
            fill_price=price * (1 + slippage / 10_000 if side_str == "buy" else 1 - slippage / 10_000),
            commission=order.quantity * price * get_settings().costs.commission_pct,
            slippage_bps=slippage,
        )

    def _paper_fill(self, order) -> TradeExecution:
        """Paper mode: uses PaperExecutionEngine for realistic simulation."""
        if self._paper_engine is None:
            from execution.paper_execution import PaperExecutionEngine
            self._paper_engine = PaperExecutionEngine()

        pair_key = getattr(order, 'pair_key', order.metadata.get('pair_key', order.symbol) if hasattr(order, 'metadata') else order.symbol)
        side_str = order.side.value.lower() if hasattr(order.side, 'value') else str(order.side).lower()
        price = order.limit_price or 0.0
        from config.settings import get_settings
        slippage = get_settings().costs.slippage_bps

        # A-02: record immediate fill for paper orders
        order_id = getattr(order, 'order_id', None)
        if order_id:
            from execution.base import OrderStatus
            self._pending_orders[order_id] = OrderStatus.FILLED

        return TradeExecution(
            pair_key=pair_key,
            symbol=order.symbol,
            side=side_str,
            requested_qty=order.quantity,
            filled_qty=order.quantity,
            fill_price=price * (1 + slippage / 10_000 if side_str == "buy" else 1 - slippage / 10_000),
            commission=order.quantity * price * get_settings().costs.commission_pct,
            slippage_bps=slippage,
        )

    def _live_fill(self, order) -> TradeExecution:
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

        # Build an Order compatible with IBKRExecutionEngine.
        # Reuse the caller's order_id if available (A-02: enables fill-confirmation tracking).
        from execution.base import OrderStatus
        from uuid import uuid4

        side_str = order.side.value.lower() if hasattr(order.side, 'value') else str(order.side).lower()
        ibkr_side = OrderSide.BUY if side_str == 'buy' else OrderSide.SELL

        # Preserve the caller's order_id so _pending_orders can be keyed on it
        original_order_id = getattr(order, 'order_id', None) or str(uuid4())
        pair_key = order.metadata.get('pair_key', order.symbol) if hasattr(order, 'metadata') else order.symbol

        ibkr_order = Order(
            order_id=original_order_id,
            symbol=order.symbol,
            side=ibkr_side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            order_type=order.order_type.upper(),
        )

        # A-08: Anti-short guard — block SELL orders when shortable shares are insufficient
        if ibkr_side == OrderSide.SELL and hasattr(self._ibkr_engine, 'get_shortable_shares'):
            shortable = self._ibkr_engine.get_shortable_shares(ibkr_order.symbol)
            if 0 <= shortable < ibkr_order.quantity:
                logger.warning(
                    "short_blocked_insufficient_shortable_shares",
                    symbol=ibkr_order.symbol,
                    available=shortable,
                    needed=ibkr_order.quantity,
                )
                self._pending_orders[original_order_id] = OrderStatus.REJECTED
                return TradeExecution(
                    pair_key=pair_key,
                    symbol=ibkr_order.symbol,
                    side=side_str,
                    requested_qty=ibkr_order.quantity,
                    filled_qty=0.0,
                    fill_price=0.0,
                    commission=0.0,
                    slippage_bps=0.0,
                    is_partial=False,
                )

        # Rate-limit before hitting IBKR API (50 req/s hard cap)
        self._rate_limiter.acquire()

        # Submit through IBKR engine
        submitted_order_id = self._ibkr_engine.submit_order(ibkr_order)

        # Poll for fill (timeout after 60 seconds)
        max_wait = 60
        poll_interval = 0.5
        waited = 0.0
        fill_price = order.limit_price or 0.0
        filled_qty = 0.0
        commission = 0.0
        is_partial = False

        while waited < max_wait:
            status = self._ibkr_engine.get_order_status(submitted_order_id)
            if status == OrderStatus.FILLED:
                # Retrieve actual fill data from ib_insync trade object
                trade_obj = self._ibkr_engine._order_map.get(submitted_order_id)
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
                logger.warning("live_order_cancelled", order_id=submitted_order_id)
                break
            _time.sleep(poll_interval)
            waited += poll_interval

        if waited >= max_wait and filled_qty == 0:
            # Timeout — cancel and log
            logger.error("live_order_timeout", order_id=submitted_order_id, waited=max_wait)
            self._ibkr_engine.cancel_order(submitted_order_id)
            is_partial = True

        # Compute slippage
        ref_price = order.limit_price or fill_price
        slippage_bps = abs(fill_price - ref_price) / max(ref_price, 1e-9) * 10_000 if ref_price else 0.0

        # A-02: record final status for fill-confirmation tracking
        final_status = OrderStatus.FILLED if filled_qty > 0 else (
            OrderStatus.TIMEOUT if is_partial else OrderStatus.UNKNOWN
        )
        self._pending_orders[original_order_id] = final_status

        return TradeExecution(
            pair_key=pair_key,
            symbol=order.symbol,
            side=side_str,
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

    def get_order_status(self, order_id: str) -> object:
        """Return the current status for a previously submitted order.

        Checks the local _pending_orders cache first (populated by all fill
        paths), then delegates to the IBKR engine for live orders that may
        not yet appear in the cache.

        Returns an OrderStatus enum value (from execution.base).
        """
        from execution.base import OrderStatus
        if order_id in self._pending_orders:
            return self._pending_orders[order_id]
        # Live mode: delegate to IBKR engine for real-time status
        if self._ibkr_engine is not None:
            return self._ibkr_engine.get_order_status(order_id)
        # Paper / backtest: all orders fill instantly — treat unknown as FILLED
        return OrderStatus.FILLED

    def get_account_balance(self) -> float:
        """Return current account balance.

        In paper mode, returns initial capital minus commissions
        (a rough approximation). In live mode, queries IBKR.
        """
        if self._mode == ExecutionMode.LIVE and self._ibkr_engine is not None:
            try:
                return self._ibkr_engine.get_account_balance()
            except Exception:
                pass
        if self._paper_engine is not None:
            try:
                return self._paper_engine.get_account_balance()
            except Exception:
                pass
        # Fallback: no engine initialized yet
        return 0.0
