"""
Realistic order book modeling for backtest execution.

Simulates realistic market microstructure including:
- Bid-ask spreads
- Order book depth profiles
- Liquidity constraints
- Market impact
- Partial fill probabilities
"""

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from common.types import (
    LiquidityMetrics,
    OrderBook,
    OrderBookLevel,
    OrderBookUpdate,
    Price,
    Quantity,
    Symbol,
    BookSimulationConfig,
)


@dataclass
class OrderBookSimulator:
    """Simulates realistic order book for trading simulation."""

    config: BookSimulationConfig = field(
        default_factory=lambda: {
            "symbols": [],
            "bid_ask_spread_bps": 5.0,
            "depth_mode": "medium",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }
    )

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.config["bid_ask_spread_bps"] < 0.5:
            raise ValueError("Spread must be >= 0.5 basis points")
        if self.config["volatility_factor"] < 0.5 or self.config["volatility_factor"] > 2.0:
            raise ValueError("Volatility factor must be 0.5-2.0")

    def create_order_book(
        self,
        symbol: Symbol,
        mid_price: Price,
        volatility: float,
        timestamp: Optional[datetime] = None,
    ) -> OrderBook:
        """
        Create realistic order book snapshot.

        Args:
            symbol: Trading symbol
            mid_price: Current market price
            volatility: Price volatility (annualized %)
            timestamp: Book timestamp

        Returns:
            Realistic OrderBook snapshot
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Calculate bid-ask spread
        spread_bps = self._calculate_spread(volatility)
        spread_price = mid_price * (spread_bps / 10000)

        bid_price = mid_price - spread_price / 2
        ask_price = mid_price + spread_price / 2

        # Generate depth levels
        bid_levels = self._generate_bid_levels(bid_price, mid_price, spread_bps)
        ask_levels = self._generate_ask_levels(ask_price, mid_price, spread_bps)

        # Calculate totals
        bid_volume = sum(level["quantity"] for level in bid_levels)
        ask_volume = sum(level["quantity"] for level in ask_levels)

        return OrderBook(
            symbol=symbol,
            timestamp=timestamp,
            bid_levels=bid_levels,
            ask_levels=ask_levels,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            bid_ask_spread_bps=spread_bps,
        )

    def _calculate_spread(self, volatility: float) -> float:
        """
        Calculate bid-ask spread based on volatility.

        Args:
            volatility: Annualized volatility (%)

        Returns:
            Spread in basis points
        """
        base_spread = self.config["bid_ask_spread_bps"]

        # Spread widens with volatility
        vol_multiplier = 1.0 + (volatility / 100.0) * self.config["volatility_factor"]
        spread_bps = base_spread * vol_multiplier

        # Cap spread based on realism level
        if self.config["realism_level"] == "tight":
            max_spread = base_spread * 2.0
        elif self.config["realism_level"] == "academic":
            max_spread = base_spread * 5.0
        else:  # realistic
            max_spread = base_spread * 3.0

        return min(spread_bps, max_spread)

    def _generate_bid_levels(
        self, best_bid: Price, mid_price: Price, spread_bps: float
    ) -> list[OrderBookLevel]:
        """Generate realistic bid levels."""
        levels: list[OrderBookLevel] = []

        if self.config["depth_mode"] == "shallow":
            level_count = 5
            volume_per_level = 100.0
            level_distance_bps = 3.0
        elif self.config["depth_mode"] == "deep":
            level_count = 15
            volume_per_level = 500.0
            level_distance_bps = 1.0
        else:  # medium
            level_count = 10
            volume_per_level = 250.0
            level_distance_bps = 2.0

        for i in range(level_count):
            # Price decreases as we go down (worse bids)
            distance_bps = (i + 1) * level_distance_bps
            level_price = best_bid - (mid_price * distance_bps / 10000)

            # Volume decreases for worse bids (realistic)
            volume_multiplier = 1.0 - (i / level_count) * 0.6
            quantity = volume_per_level * volume_multiplier

            # Add some randomness
            quantity *= random.uniform(0.8, 1.2)

            levels.append(
                OrderBookLevel(
                    price=level_price,
                    quantity=quantity,
                    order_count=max(1, int(quantity / 50)),
                )
            )

        return levels

    def _generate_ask_levels(
        self, best_ask: Price, mid_price: Price, spread_bps: float
    ) -> list[OrderBookLevel]:
        """Generate realistic ask levels."""
        levels: list[OrderBookLevel] = []

        if self.config["depth_mode"] == "shallow":
            level_count = 5
            volume_per_level = 100.0
            level_distance_bps = 3.0
        elif self.config["depth_mode"] == "deep":
            level_count = 15
            volume_per_level = 500.0
            level_distance_bps = 1.0
        else:  # medium
            level_count = 10
            volume_per_level = 250.0
            level_distance_bps = 2.0

        for i in range(level_count):
            # Price increases as we go up (worse asks)
            distance_bps = (i + 1) * level_distance_bps
            level_price = best_ask + (mid_price * distance_bps / 10000)

            # Volume decreases for worse asks
            volume_multiplier = 1.0 - (i / level_count) * 0.6
            quantity = volume_per_level * volume_multiplier

            # Add randomness
            quantity *= random.uniform(0.8, 1.2)

            levels.append(
                OrderBookLevel(
                    price=level_price,
                    quantity=quantity,
                    order_count=max(1, int(quantity / 50)),
                )
            )

        return levels

    def estimate_execution_price(
        self,
        order_book: OrderBook,
        side: str,
        quantity: Quantity,
    ) -> tuple[Price, Quantity, float]:
        """
        Estimate execution price and fill for an order.

        Args:
            order_book: Current order book
            side: "buy" or "sell"
            quantity: Order size

        Returns:
            Tuple of (exec_price, filled_qty, market_impact_bps)
        """
        if side.lower() == "buy":
            levels = order_book["ask_levels"]
            start_price = levels[0]["price"]
        else:
            levels = order_book["bid_levels"]
            start_price = levels[0]["price"]

        # Walk through levels until order filled
        remaining_qty = quantity
        total_cost = 0.0
        filled_qty = 0.0

        for level in levels:
            if remaining_qty <= 0:
                break

            # How much can we fill at this level?
            fill_at_level = min(remaining_qty, level["quantity"])
            total_cost += fill_at_level * level["price"]
            filled_qty += fill_at_level
            remaining_qty -= fill_at_level

        # Calculate metrics
        if filled_qty > 0:
            avg_price = total_cost / filled_qty
            impact_bps = abs(avg_price - start_price) / start_price * 10000
        else:
            avg_price = start_price
            impact_bps = 0.0

        return avg_price, filled_qty, impact_bps

    def calculate_liquidity_metrics(
        self, order_book: OrderBook, mid_price: Price
    ) -> LiquidityMetrics:
        """
        Calculate liquidity metrics from order book.

        Args:
            order_book: Current order book
            mid_price: Current mid price

        Returns:
            LiquidityMetrics with market depth analysis
        """
        best_bid = order_book["bid_levels"][0]["price"] if order_book["bid_levels"] else mid_price
        best_ask = order_book["ask_levels"][0]["price"] if order_book["ask_levels"] else mid_price

        spread = best_ask - best_bid
        spread_pct = (spread / mid_price * 100) if mid_price > 0 else 0

        # Calculate depth at different price ranges
        depth_10bps = self._calculate_depth(order_book, mid_price, 10)
        depth_20bps = self._calculate_depth(order_book, mid_price, 20)

        # Estimate market impact of 100 BPS order
        test_qty = mid_price * 100 / 10000  # 100 BPS notional
        _, filled, impact = self.estimate_execution_price(
            order_book, "buy", test_qty
        )

        return LiquidityMetrics(
            symbol=order_book["symbol"],
            timestamp=order_book["timestamp"],
            bid_ask_spread=spread,
            bid_ask_spread_pct=spread_pct,
            mid_price=mid_price,
            depth_at_10bps=depth_10bps,
            depth_at_20bps=depth_20bps,
            estimated_impact_100bps=impact,
        )

    def _calculate_depth(
        self, order_book: OrderBook, mid_price: Price, bps_width: float
    ) -> float:
        """Calculate volume within specified distance from mid price."""
        range_price = mid_price * (bps_width / 10000)
        low_price = mid_price - range_price / 2
        high_price = mid_price + range_price / 2

        volume = 0.0

        for level in order_book["bid_levels"]:
            if level["price"] >= low_price:
                volume += level["quantity"]

        for level in order_book["ask_levels"]:
            if level["price"] <= high_price:
                volume += level["quantity"]

        return volume

    def generate_order_update(
        self, order_book: OrderBook, side: str = "bid"
    ) -> OrderBookUpdate:
        """
        Generate realistic order book update.

        Args:
            order_book: Current order book
            side: "bid" or "ask"

        Returns:
            OrderBookUpdate simulating market activity
        """
        timestamp = datetime.now(timezone.utc)
        
        if side.lower() == "bid":
            levels = order_book["bid_levels"]
            price = levels[0]["price"] if levels else 0
        else:
            levels = order_book["ask_levels"]
            price = levels[0]["price"] if levels else 0

        # Random update type
        update_type = random.choice(["trade", "add", "cancel", "modify"])

        # Random quantity
        quantity = random.uniform(10, 100)

        return OrderBookUpdate(
            symbol=order_book["symbol"],
            timestamp=timestamp,
            update_type=update_type,
            side=side,
            price=price,
            quantity=quantity,
            order_count=random.randint(1, 5),
        )


@dataclass
class MarketMicrostructure:
    """Analyze market microstructure impact."""

    def estimate_market_impact(
        self,
        order_size: Quantity,
        market_volume: float,
        volatility: float,
        side: str = "buy",
    ) -> float:
        """
        Estimate market impact of order.

        Based on: impact = sqrt(order_size / market_volume) * volatility_adjustment

        Args:
            order_size: Order quantity
            market_volume: Daily market volume
            volatility: Price volatility
            side: "buy" or "sell"

        Returns:
            Impact in basis points
        """
        if market_volume <= 0:
            market_volume = 1.0

        # Basic impact formula
        size_ratio = order_size / market_volume
        size_impact = math.sqrt(max(0, size_ratio)) * 100

        # Volatility adjustment (higher vol = can absorb larger order)
        vol_multiplier = 1.0 / (1.0 + volatility / 10.0)

        # Combine
        total_impact = size_impact * vol_multiplier

        # Cap at reasonable maximum
        return min(total_impact, 200.0)  # 200 bps max

    def estimate_participation_rate_impact(
        self,
        order_size: Quantity,
        time_window_minutes: int,
        daily_volume: float,
    ) -> float:
        """
        Estimate impact based on participation rate.

        If executing at X% of volume over Y minutes, impact scales.

        Args:
            order_size: Order quantity
            time_window_minutes: Time to execute over
            daily_volume: Expected daily volume

        Returns:
            Estimated market impact in basis points
        """
        # Infer minute volume from daily volume
        minute_volume = daily_volume / 1440  # 1440 mins per day
        time_window_volume = minute_volume * time_window_minutes

        participation_rate = order_size / time_window_volume if time_window_volume > 0 else 0

        # Participation rate impact
        # 1% participation = ~5 bps, 5% = ~50 bps, 10% = 100+ bps
        if participation_rate < 0.01:
            return 5.0
        elif participation_rate < 0.05:
            return 5.0 + (participation_rate - 0.01) * 1000
        elif participation_rate < 0.10:
            return 45.0 + (participation_rate - 0.05) * 1000
        else:
            return 95.0 + (participation_rate - 0.10) * 500
