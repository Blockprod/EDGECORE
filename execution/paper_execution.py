"""Paper trading execution with realistic slippage and commissions.

Fully decoupled from IBKRExecutionEngine — no live broker connection needed.
Maintains an in-memory order book, positions, and balance for simulation.
"""

from typing import Dict
from datetime import datetime
from structlog import get_logger
from execution.backtest_execution import SlippageCalculator, CommissionCalculator
from execution.base import BaseExecutionEngine, Order, OrderSide, OrderStatus
from common.types import SlippageModel, CommissionType

logger = get_logger(__name__)


class PaperExecutionEngine(BaseExecutionEngine):
    """Paper trading with realistic slippage and commission simulation.

    Unlike the old implementation, this inherits from BaseExecutionEngine
    (not IBKRExecutionEngine) so it never attempts a broker connection.
    All fills happen instantly in-memory with configurable slippage/commission.
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        slippage_model: str = "adaptive",
        fixed_bps: float = 3.0,
        commission_pct: float = 0.035,
    ):
        """
        Args:
            initial_capital: Starting virtual balance.
            slippage_model: "fixed_bps", "adaptive", or "volume_based"
            fixed_bps: Basis points for slippage (default from CostConfig).
            commission_pct: Commission percentage (0.035 = 0.035% IBKR).
        """
        # In-memory state
        self._balance: float = initial_capital
        self._initial_capital: float = initial_capital
        self._positions: Dict[str, float] = {}          # symbol -> net qty
        self._orders: Dict[str, Order] = {}             # order_id -> Order
        self._market_prices: Dict[str, float] = {}      # symbol -> last known price

        # Convert string slippage model to enum
        slippage_model_enum = self._parse_slippage_model(slippage_model)

        # Slippage configuration
        self.slippage_config = {
            'model': slippage_model_enum,
            'fixed_bps': fixed_bps,
            'adaptive_multiplier': 2.0,
            'max_slippage_bps': 50.0,
        }
        self.slippage_calc = SlippageCalculator(self.slippage_config)

        # Commission configuration
        self.commission_config = {
            'type': CommissionType.PERCENT,
            'percent': commission_pct,
        }
        self.commission_calc = CommissionCalculator(self.commission_config)

        logger.info(
            "paper_execution_engine_initialized",
            initial_capital=initial_capital,
            slippage_model=slippage_model,
            fixed_bps=fixed_bps,
            commission_pct=commission_pct,
        )

    # ── helpers ──
    @staticmethod
    def _parse_slippage_model(model_str: str) -> SlippageModel:
        mapping = {
            "fixed_bps": SlippageModel.FIXED_BPS,
            "adaptive": SlippageModel.ADAPTIVE,
            "volume_based": SlippageModel.VOLUME_BASED,
        }
        if model_str not in mapping:
            raise ValueError(
                f"Invalid slippage model: {model_str}. "
                f"Must be one of {list(mapping.keys())}"
            )
        return mapping[model_str]

    def set_market_price(self, symbol: str, price: float) -> None:
        """Feed a market price into the paper engine (call before submit_order)."""
        self._market_prices[symbol] = price

    def set_market_prices(self, prices: Dict[str, float]) -> None:
        """Bulk-update market prices."""
        self._market_prices.update(prices)

    # ── BaseExecutionEngine interface ──

    def submit_order(self, order: Order) -> str:
        """Simulate order fill with slippage and commission."""
        market_price = self._market_prices.get(order.symbol)
        if market_price is None or market_price <= 0:
            order.status = OrderStatus.REJECTED
            self._orders[order.order_id] = order
            logger.warning("paper_order_rejected_no_price", symbol=order.symbol)
            return order.order_id

        base_price = order.limit_price or market_price

        # Slippage
        slippage_bps, slippage_price = self.slippage_calc.calculate(
            order_price=base_price,
            market_price=market_price,
            order_quantity=order.quantity,
            market_volume=1_000_000.0,
            side='buy' if order.side == OrderSide.BUY else 'sell',
        )

        # Commission
        trade_value = slippage_price * order.quantity
        commission = self.commission_calc.calculate(trade_value)

        # Final price (commission baked in)
        if order.side == OrderSide.BUY:
            final_price = slippage_price * (1 + self.commission_config['percent'] / 100)
        else:
            final_price = slippage_price * (1 - self.commission_config['percent'] / 100)

        cost = final_price * order.quantity
        if order.side == OrderSide.BUY:
            self._balance -= cost
            self._positions[order.symbol] = self._positions.get(order.symbol, 0.0) + order.quantity
        else:
            self._balance += cost
            self._positions[order.symbol] = self._positions.get(order.symbol, 0.0) - order.quantity
            # Clean up flat positions
            if abs(self._positions[order.symbol]) < 1e-9:
                del self._positions[order.symbol]

        # Mark filled
        order.status = OrderStatus.FILLED
        order.filled_price = final_price
        order.filled_quantity = order.quantity
        order.filled_at = datetime.now()
        self._orders[order.order_id] = order

        logger.info(
            "paper_order_filled",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side.value,
            quantity=order.quantity,
            final_price=round(final_price, 4),
            slippage_bps=round(slippage_bps, 2),
            commission=round(commission, 4),
            balance=round(self._balance, 2),
        )
        return order.order_id

    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order is None or order.status != OrderStatus.PENDING:
            return False
        order.status = OrderStatus.CANCELLED
        return True

    def get_order_status(self, order_id: str) -> OrderStatus:
        order = self._orders.get(order_id)
        if order is None:
            return OrderStatus.PENDING
        return order.status

    def get_positions(self) -> Dict[str, float]:
        return dict(self._positions)

    def get_account_balance(self) -> float:
        return self._balance
