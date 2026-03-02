"""
Realistic backtest execution with slippage, commissions, and partial fills.

This module provides realistic order fill simulation for backtesting,
including:
- Slippage calculation (fixed, adaptive, volume-based)
- Commission deduction (percent or fixed)
- Partial fill handling
- Multi-leg order execution
"""

import math
from dataclasses import dataclass, field
from datetime import datetime

from common.types import (
    CommissionConfig,
    CommissionType,
    ExecutionResult,
    FillSimulation,
    FillType,
    OrderID,
    Price,
    Quantity,
    SlippageConfig,
    SlippageModel,
    Symbol,
)


@dataclass
class SlippageCalculator:
    """Calculates order slippage based on configured model."""

    config: SlippageConfig

    def calculate(
        self,
        order_price: Price,
        market_price: Price,
        order_quantity: Quantity,
        market_volume: float,
        side: str,
    ) -> tuple[float, Price]:
        """
        Calculate slippage and execution price.

        Args:
            order_price: Price at order submission
            market_price: Current market price
            order_quantity: Order size
            market_volume: Available market volume
            side: "buy" or "sell"

        Returns:
            Tuple of (slippage_bps, execution_price)
        """
        if self.config["model"] == SlippageModel.FIXED_BPS:
            return self._fixed_slippage(order_price, side)
        elif self.config["model"] == SlippageModel.ADAPTIVE:
            return self._adaptive_slippage(
                order_price, market_price, side
            )
        elif self.config["model"] == SlippageModel.VOLUME_BASED:
            return self._volume_based_slippage(
                order_price, order_quantity, market_volume, side
            )
        else:
            # Default: no slippage
            return 0.0, order_price

    def _fixed_slippage(self, order_price: Price, side: str) -> tuple[float, Price]:
        """Calculate fixed basis points slippage."""
        slippage_bps = self.config.get("fixed_bps", 5.0)  # Default 5 bps
        slippage_amount = (slippage_bps / 10000) * order_price

        # Slippage always costs: buy prices up, sell prices down
        if side.lower() == "buy":
            execution_price = order_price + slippage_amount
        else:
            execution_price = order_price - slippage_amount

        return slippage_bps, execution_price

    def _adaptive_slippage(
        self, order_price: Price, market_price: Price, side: str
    ) -> tuple[float, Price]:
        """Calculate adaptive slippage based on market conditions."""
        # Slippage increases with distance from market price
        distance = abs(order_price - market_price) / market_price
        base_slippage = self.config.get("fixed_bps", 5.0)
        multiplier = self.config.get("adaptive_multiplier", 2.0)

        # distance is fractional (0.05 for 5%), multiply by 100 to get bps
        slippage_bps = base_slippage + (distance * multiplier * 100)

        # Apply max slippage cap
        max_slippage_bps = self.config.get("max_slippage_bps", 50.0)
        slippage_bps = min(slippage_bps, max_slippage_bps)

        slippage_amount = (slippage_bps / 10000) * order_price

        if side.lower() == "buy":
            execution_price = order_price + slippage_amount
        else:
            execution_price = order_price - slippage_amount

        return slippage_bps, execution_price

    def _volume_based_slippage(
        self,
        order_price: Price,
        order_quantity: Quantity,
        market_volume: float,
        side: str,
    ) -> tuple[float, Price]:
        """Calculate slippage based on order size vs market volume."""
        if market_volume <= 0:
            # Fallback to fixed slippage if volume unknown
            return self._fixed_slippage(order_price, side)

        # Order volume as percentage of market volume
        order_volume_pct = order_quantity / market_volume

        base_slippage = self.config.get("fixed_bps", 5.0)
        multiplier = self.config.get("adaptive_multiplier", 100.0)

        # Slippage = base + (order_volume_pct * multiplier) * 100 bps
        slippage_bps = base_slippage + (order_volume_pct * multiplier)

        # Apply max slippage cap
        max_slippage_bps = self.config.get("max_slippage_bps", 100.0)
        slippage_bps = min(slippage_bps, max_slippage_bps)

        slippage_amount = (slippage_bps / 10000) * order_price

        if side.lower() == "buy":
            execution_price = order_price + slippage_amount
        else:
            execution_price = order_price - slippage_amount

        return slippage_bps, execution_price


@dataclass
class CommissionCalculator:
    """Calculates commission on executed orders."""

    config: CommissionConfig

    def calculate(self, trade_value: float) -> float:
        """
        Calculate commission on trade value.

        Args:
            trade_value: Total trade value (price * quantity)

        Returns:
            Commission amount
        """
        if self.config["type"] == CommissionType.PERCENT:
            percent = self.config.get("percent", 0.02)  # Default 0.02%
            commission = (percent / 100) * trade_value
        elif self.config["type"] == CommissionType.FIXED:
            commission = self.config.get("fixed_amount", 1.0)  # Default $1
        else:
            commission = 0.0

        # Apply min/max bounds
        min_commission = self.config.get("min_commission")
        max_commission = self.config.get("max_commission")

        if min_commission is not None:
            commission = max(commission, min_commission)
        if max_commission is not None:
            commission = min(commission, max_commission)

        return commission


@dataclass
class PartialFillHandler:
    """Handles partial fill scenarios in backtest."""

    fill_simulation: FillSimulation = field(
        default_factory=lambda: {
            "base_volume_bps": 100,  # 1% base
            "market_volume": 1000000.0,
            "max_fill_pct": 10.0,
            "partial_fill_probability": 0.1,
        }
    )

    def determine_fill_quantity(
        self,
        requested_quantity: Quantity,
        market_volume: float,
        is_aggressive: bool = True,
    ) -> tuple[Quantity, FillType]:
        """
        Determine actual fill quantity and type.

        Args:
            requested_quantity: Requested order size
            market_volume: Available market liquidity
            is_aggressive: Whether order is aggressive (market order)

        Returns:
            Tuple of (filled_quantity, fill_type)
        """
        # Calculate maximum fillable quantity
        base_volume_pct = self.fill_simulation.get("base_volume_bps", 100) / 10000
        max_fillable = market_volume * base_volume_pct

        # Aggressive orders get better fills
        if is_aggressive:
            max_fill_pct = self.fill_simulation.get("max_fill_pct", 10.0) / 100
            effective_max = market_volume * max_fill_pct
        else:
            effective_max = max_fillable

        # Determine fill quantity
        if requested_quantity <= effective_max:
            # Can fill completely
            filled_quantity = requested_quantity
            fill_type = FillType.FULL
        else:
            # Partial fill
            filled_quantity = effective_max
            fill_type = FillType.PARTIAL

        # Floor to whole units
        filled_quantity = max(1.0, math.floor(filled_quantity))

        return filled_quantity, fill_type


@dataclass
class BacktestExecutor:
    """Execute orders with realistic fill simulation for backtesting."""

    slippage_calc: SlippageCalculator = field(
        default_factory=lambda: SlippageCalculator(
            {
                "model": SlippageModel.FIXED_BPS,
                "fixed_bps": 5.0,
                "max_slippage_bps": 50.0,
            }
        )
    )
    commission_calc: CommissionCalculator = field(
        default_factory=lambda: CommissionCalculator(
            {
                "type": CommissionType.PERCENT,
                "percent": 0.02,
            }
        )
    )
    fill_handler: PartialFillHandler = field(
        default_factory=PartialFillHandler
    )

    def execute_order(
        self,
        order_id: OrderID,
        symbol: Symbol,
        side: str,
        quantity: Quantity,
        order_price: Price,
        market_price: Price,
        market_volume: float,
        execution_time: datetime,
    ) -> ExecutionResult:
        """
        Execute order with realistic fill simulation.

        Args:
            order_id: Order identifier
            symbol: Trade symbol
            side: "buy" or "sell"
            quantity: Requested quantity
            order_price: Price at submission
            market_price: Current market price
            market_volume: Available market volume
            execution_time: Execution timestamp

        Returns:
            ExecutionResult with filled quantity, prices, costs
        """
        # Determine fill quantity and type
        filled_quantity, fill_type = self.fill_handler.determine_fill_quantity(
            quantity, market_volume, is_aggressive=True
        )

        # Calculate slippage
        slippage_bps, execution_price = self.slippage_calc.calculate(
            order_price, market_price, filled_quantity, market_volume, side
        )
        slippage_amount = execution_price - order_price

        # Calculate trade value and commission
        trade_value = execution_price * filled_quantity
        commission = self.commission_calc.calculate(trade_value)

        # Calculate net proceeds
        if side.lower() == "buy":
            net_proceeds = -(trade_value + commission)
        else:
            net_proceeds = trade_value - commission

        return ExecutionResult(
            order_id=order_id,
            symbol=symbol,
            side=side,
            submitted_price=order_price,
            executed_price=execution_price,
            requested_quantity=quantity,
            filled_quantity=filled_quantity,
            fill_type=fill_type,
            slippage_bps=slippage_bps,
            slippage_amount=slippage_amount,
            commission=commission,
            net_proceeds=net_proceeds,
            execution_time=execution_time,
        )

    def execute_multi_leg_order(
        self,
        order_id: OrderID,
        legs: list[dict],
        execution_time: datetime,
    ) -> list[ExecutionResult]:
        """
        Execute multi-leg order (e.g., pair trade).

        Args:
            order_id: Order identifier
            legs: List of leg dicts with symbol, side, qty, prices
            execution_time: Execution timestamp

        Returns:
            List of ExecutionResult for each leg
        """
        results: list[ExecutionResult] = []

        for i, leg in enumerate(legs):
            leg_result = self.execute_order(
                order_id=f"{order_id}_L{i+1}",
                symbol=leg["symbol"],
                side=leg["side"],
                quantity=leg["quantity"],
                order_price=leg["order_price"],
                market_price=leg["market_price"],
                market_volume=leg.get("market_volume", 1000000.0),
                execution_time=execution_time,
            )
            results.append(leg_result)

        return results
