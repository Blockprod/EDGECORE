"""Venue-specific market models for realistic execution simulation.

Provides market models tailored to different trading venues:
- Stock exchanges: Nasdaq, NYSE (via IBKR)
- Futures: CME
- IBKR Smart Routing (default)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
<<<<<<< HEAD
from typing import Literal

from common.types import Symbol, VenueCharacteristics, VenueType
=======
from typing import Optional, Literal
import logging

from common.types import Symbol, VenueType, VenueCharacteristics
>>>>>>> origin/main

logger = logging.getLogger(__name__)


@dataclass
class OrderExecutionMicrostructure:
    """Microstructure details of an order execution."""

    venue: VenueType
    symbol: Symbol
    order_side: Literal["buy", "sell"]
    order_size_usd: float
    market_price: float
    bid_ask_spread_bps: float
    order_book_depth: float  # Total volume at best 5 levels
    market_volume_24h: float
    execution_price: float
    market_impact_bps: float
    fee_bps: float
    total_cost_bps: float  # Impact + fees
    liquidity_score: float  # 0-1, how abundant liquidity is
    estimated_fill_time_s: float  # Seconds to fill


class VenueModelBase(ABC):
    """Abstract base for venue-specific models."""

    def __init__(self, venue: VenueType, characteristics: VenueCharacteristics):
        """
        Initialize venue model.

        Args:
            venue: Type of venue
            characteristics: Venue characteristics
        """
        self.venue = venue
        self.characteristics = characteristics

    @abstractmethod
    def calculate_market_impact(
        self,
        order_size_usd: float,
        market_price: float,
        market_volume_24h: float,
        bid_ask_spread_bps: float,
    ) -> float:
        """
        Calculate market impact in BPS.

        Args:
            order_size_usd: Order size in USD
            market_price: Current market price
            market_volume_24h: 24-hour trading volume
            bid_ask_spread_bps: Current bid-ask spread

        Returns:
            Impact in basis points
        """
        pass

    @abstractmethod
    def estimate_fill_time(
        self,
        order_size_usd: float,
        market_volume_24h: float,
        order_aggressiveness: Literal["passive", "normal", "aggressive"],
    ) -> float:
        """
        Estimate time to fill in seconds.

        Args:
            order_size_usd: Order size in USD
            market_volume_24h: 24-hour trading volume
            order_aggressiveness: How aggressive the order is

        Returns:
            Estimated fill time in seconds
        """
        pass

    @abstractmethod
    def is_market_open(self) -> bool:
        """Check if market is currently open."""
        pass

    def calculate_execution_price(
        self,
        market_price: float,
        order_side: Literal["buy", "sell"],
        order_size_usd: float,
        market_volume_24h: float,
        bid_ask_spread: float,
    ) -> float:
        """
        Calculate expected execution price.

        Args:
            market_price: Current market price
            order_side: Buy or sell
            order_size_usd: Order size
            market_volume_24h: 24h volume
            bid_ask_spread: Spread in BPS

        Returns:
            Expected execution price
        """
        impact_bps = self.calculate_market_impact(
            order_size_usd=order_size_usd,
            market_price=market_price,
            market_volume_24h=market_volume_24h,
            bid_ask_spread_bps=bid_ask_spread,
        )

        # Add half-spread + impact
        half_spread = bid_ask_spread / 2.0
        total_cost_bps = half_spread + impact_bps

        if order_side == "buy":
            return market_price * (1 + total_cost_bps / 10000.0)
        else:
            return market_price * (1 - total_cost_bps / 10000.0)


class IBKRSmartVenueModel(VenueModelBase):
    """Model for IBKR Smart Routing (default venue)."""
<<<<<<< HEAD

    def __init__(self, characteristics: VenueCharacteristics | None = None):
=======
    
    def __init__(self, characteristics: Optional[VenueCharacteristics] = None):
>>>>>>> origin/main
        """Initialize IBKR Smart Routing model."""
        if characteristics is None:
            characteristics = {
                "venue": VenueType.IBKR_SMART,
                "name": "IBKR Smart Routing",
                "base_spread_bps": 1.0,
                "min_spread_bps": 0.1,
                "max_spread_bps": 30.0,
                "typical_volume": 5e9,
                "fee_bps": 0.35,  # IBKR fixed rate ~$0.005/share
                "taker_fee_bps": 0.35,
<<<<<<< HEAD
                "maker_fee_bps": 0.0,  # IBKR rebates for adding liquidity
                "opening_hours": "09:30-16:00 EST",
                "is_24_7": False,
            }

        super().__init__(VenueType.IBKR_SMART, characteristics)

=======
                "maker_fee_bps": 0.0,   # IBKR rebates for adding liquidity
                "opening_hours": "09:30-16:00 EST",
                "is_24_7": False,
            }
        
        super().__init__(VenueType.IBKR_SMART, characteristics)
    
>>>>>>> origin/main
    def calculate_market_impact(
        self,
        order_size_usd: float,
        market_price: float,
        market_volume_24h: float,
        bid_ask_spread_bps: float,
    ) -> float:
        """IBKR smart-routed equity impact using participation rate."""
<<<<<<< HEAD
        shares_ordered = order_size_usd / max(market_price, 1.0)
        shares_volume = market_volume_24h / max(market_price, 1.0)
        participation_rate = shares_ordered / max(shares_volume, shares_ordered)

        # Equity impact: moderate, benefits from smart routing
        impact_bps = 1.0 * (participation_rate**1.3)

        # Add spread adjustment
        impact_bps += bid_ask_spread_bps * 0.3

        return float(min(impact_bps, 30.0))

=======
        participation_rate = order_size_usd / max(market_volume_24h, order_size_usd)
        
        # Equity impact: moderate, benefits from smart routing
        impact_bps = 1.0 * (participation_rate ** 1.3)
        
        # Add spread adjustment
        impact_bps += bid_ask_spread_bps * 0.3
        
        return min(impact_bps, 30.0)
    
>>>>>>> origin/main
    def estimate_fill_time(
        self,
        order_size_usd: float,
        market_volume_24h: float,
        order_aggressiveness: Literal["passive", "normal", "aggressive"],
    ) -> float:
        """IBKR Smart Routing fill times."""
        if order_aggressiveness == "aggressive":
            return 0.5
        elif order_aggressiveness == "normal":
            return 3.0
        else:
            participation = order_size_usd / max(market_volume_24h, 1e6)
            return 15.0 + 200.0 * participation
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def is_market_open(self) -> bool:
        """Check if US equity markets are open (9:30-16:00 EST)."""
        return True


class CMEVenueModel(VenueModelBase):
    """Model for CME futures."""

    def __init__(self, characteristics: VenueCharacteristics | None = None):
        """Initialize CME model."""
        if characteristics is None:
            characteristics = {
                "venue": VenueType.CME_FUTURES,
                "name": "CME Futures",
                "base_spread_bps": 0.5,  # Futures very tight
                "min_spread_bps": 0.1,
                "max_spread_bps": 5.0,
                "typical_volume": 1e11,  # Massive volume
                "fee_bps": 0.3,  # Relatively low fees
                "opening_hours": "17:00-16:00 CST",  # Nearly 24/7 with hour break
                "is_24_7": False,
            }

        super().__init__(VenueType.CME_FUTURES, characteristics)

    def calculate_market_impact(
        self,
        order_size_usd: float,
        market_price: float,
        market_volume_24h: float,
        bid_ask_spread_bps: float,
    ) -> float:
        """CME futures have minimal market impact (liquid)."""
        shares_ordered = order_size_usd / max(market_price, 1.0)
        shares_volume = market_volume_24h / max(market_price, 1.0)
        participation_rate = shares_ordered / max(shares_volume, shares_ordered)

        # Futures impact is minimal
        impact_bps = 0.5 * participation_rate  # Very low

        # Add tick sensitivity (CME often 0.25 BPS tick) plus spread component
        impact_bps += 0.25 + bid_ask_spread_bps * 0.1

        return min(impact_bps, 5.0)

    def estimate_fill_time(
        self,
        order_size_usd: float,
        market_volume_24h: float,
        order_aggressiveness: Literal["passive", "normal", "aggressive"],
    ) -> float:
        """Futures fill almost instantly in normal conditions."""
        if order_aggressiveness == "aggressive":
            return 0.05
        elif order_aggressiveness == "normal":
            return 0.5
        else:
            participation = order_size_usd / max(market_volume_24h, 1e9)
            return 5.0 + 100.0 * participation

    def is_market_open(self) -> bool:
        """Check if market open (17:00-16:00 CST)."""
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # Simplified: assume open (would check actual time in production)
        return True


class NasdaqVenueModel(VenueModelBase):
    """Model for Nasdaq stock exchange."""

    def __init__(self, characteristics: VenueCharacteristics | None = None):
        """Initialize Nasdaq model."""
        if characteristics is None:
            characteristics = {
                "venue": VenueType.NASDAQ_EQUITIES,
                "name": "Nasdaq",
                "base_spread_bps": 1.0,
                "min_spread_bps": 0.1,
                "max_spread_bps": 50.0,
                "typical_volume": 5e9,
                "fee_bps": 0.0,  # No individual fees (market maker model)
                "opening_hours": "09:30-16:00 EST",
                "is_24_7": False,
            }

        super().__init__(VenueType.NASDAQ_EQUITIES, characteristics)

    def calculate_market_impact(
        self,
        order_size_usd: float,
        market_price: float,
        market_volume_24h: float,
        bid_ask_spread_bps: float,
    ) -> float:
        """Stock market impact with uptick rule considerations."""
        shares_ordered = order_size_usd / max(market_price, 1.0)
        shares_volume = market_volume_24h / max(market_price, 1.0)
        participation_rate = shares_ordered / max(shares_volume, shares_ordered)

        # Stock market impact
        impact_bps = 1.0 * (participation_rate**1.3)

        # Add spread component
        impact_bps += bid_ask_spread_bps * 0.3

        return float(min(impact_bps, 30.0))

    def estimate_fill_time(
        self,
        order_size_usd: float,
        market_volume_24h: float,
        order_aggressiveness: Literal["passive", "normal", "aggressive"],
    ) -> float:
        """Stock fills depend on liquidity and market conditions."""
        if order_aggressiveness == "aggressive":
            return 1.0
        elif order_aggressiveness == "normal":
            return 5.0
        else:
            participation = order_size_usd / max(market_volume_24h, 1e6)
            return 20.0 + 300.0 * participation

    def is_market_open(self) -> bool:
        """Check if Nasdaq is open (9:30-16:00 EST)."""
        # Simplified for now
        return True


class NYSEVenueModel(VenueModelBase):
    """Model for NYSE stock exchange."""

    def __init__(self, characteristics: VenueCharacteristics | None = None):
        """Initialize NYSE model (similar to Nasdaq)."""
        if characteristics is None:
            characteristics = {
                "venue": VenueType.NYSE_EQUITIES,
                "name": "NYSE",
                "base_spread_bps": 1.2,  # Slightly wider than Nasdaq
                "min_spread_bps": 0.1,
                "max_spread_bps": 50.0,
                "typical_volume": 4e9,
                "fee_bps": 0.0,
                "opening_hours": "09:30-16:00 EST",
                "is_24_7": False,
            }

        super().__init__(VenueType.NYSE_EQUITIES, characteristics)

    def calculate_market_impact(
        self,
        order_size_usd: float,
        market_price: float,
        market_volume_24h: float,
        bid_ask_spread_bps: float,
    ) -> float:
        """NYSE impact similar to Nasdaq."""
        shares_ordered = order_size_usd / max(market_price, 1.0)
        shares_volume = market_volume_24h / max(market_price, 1.0)
        participation_rate = shares_ordered / max(shares_volume, shares_ordered)

        impact_bps = 1.2 * (participation_rate**1.3)
        impact_bps += bid_ask_spread_bps * 0.35

        return float(min(impact_bps, 35.0))

    def estimate_fill_time(
        self,
        order_size_usd: float,
        market_volume_24h: float,
        order_aggressiveness: Literal["passive", "normal", "aggressive"],
    ) -> float:
        """NYSE fill times slightly slower than Nasdaq."""
        if order_aggressiveness == "aggressive":
            return 1.5
        elif order_aggressiveness == "normal":
            return 6.0
        else:
            participation = order_size_usd / max(market_volume_24h, 1e6)
            return 25.0 + 350.0 * participation

    def is_market_open(self) -> bool:
        """Check if NYSE is open."""
        return True


<<<<<<< HEAD
class CEXVenueModel(VenueModelBase):
    """Model for centralized crypto exchanges (CEX)."""

    def __init__(self, characteristics: VenueCharacteristics | None = None):
        if characteristics is None:
            characteristics = {
                "venue": VenueType.CENTRALIZED_EXCHANGE,
                "name": "Centralized Exchange",
                "base_spread_bps": 2.0,
                "min_spread_bps": 0.5,
                "max_spread_bps": 200.0,
                "typical_volume": 1e10,
                "fee_bps": 0.2,
                "is_24_7": True,
            }
        super().__init__(VenueType.CENTRALIZED_EXCHANGE, characteristics)

    def calculate_market_impact(
        self,
        order_size_usd: float,
        market_price: float,
        market_volume_24h: float,
        bid_ask_spread_bps: float,
    ) -> float:
        shares_ordered = order_size_usd / max(market_price, 1.0)
        shares_volume = market_volume_24h / max(market_price, 1.0)
        participation = shares_ordered / max(shares_volume, 1.0)
        impact = 2.0 * (participation**0.9) + bid_ask_spread_bps * 0.5
        return float(max(0.0, min(impact, 200.0)))

    def estimate_fill_time(
        self,
        order_size_usd: float,
        market_volume_24h: float,
        order_aggressiveness: Literal["passive", "normal", "aggressive"],
    ) -> float:
        if order_aggressiveness == "aggressive":
            return 0.2
        elif order_aggressiveness == "normal":
            return 1.0
        else:
            participation = order_size_usd / max(market_volume_24h, 1e9)
            return 10.0 + 50.0 * participation

    def is_market_open(self) -> bool:
        return True


class DEXVenueModel(VenueModelBase):
    """Model for decentralized exchanges (AMM-style)."""

    def __init__(self, characteristics: VenueCharacteristics | None = None):
        if characteristics is None:
            characteristics = {
                "venue": VenueType.DECENTRALIZED_EXCHANGE,
                "name": "Decentralized Exchange (AMM)",
                "base_spread_bps": 5.0,
                "min_spread_bps": 1.0,
                "max_spread_bps": 500.0,
                "typical_volume": 5e9,
                "fee_bps": 0.3,
                "is_24_7": True,
            }
        super().__init__(VenueType.DECENTRALIZED_EXCHANGE, characteristics)

    def calculate_market_impact(
        self, order_size_usd: float, market_price: float, market_volume_24h: float, bid_ask_spread_bps: float
    ) -> float:
        # AMM impact scales non-linearly (simulated as power law)
        shares_ordered = order_size_usd / max(market_price, 1.0)
        shares_volume = market_volume_24h / max(market_price, 1.0)
        participation = shares_ordered / max(shares_volume, 1.0)
        impact = 10.0 * (participation**0.6) + bid_ask_spread_bps * 0.8
        return float(max(0.0, min(impact, 500.0)))

    def estimate_fill_time(
        self,
        order_size_usd: float,
        market_volume_24h: float,
        order_aggressiveness: Literal["passive", "normal", "aggressive"],
    ) -> float:
        if order_aggressiveness == "aggressive":
            return 0.5
        elif order_aggressiveness == "normal":
            return 2.0
        else:
            participation = order_size_usd / max(market_volume_24h, 1e9)
            return 20.0 + 200.0 * participation

    def is_market_open(self) -> bool:
        return True


class SpotCryptoVenueModel(CEXVenueModel):
    """Specialization for spot crypto markets (inherits CEX behavior)."""

    def __init__(self, characteristics: VenueCharacteristics | None = None):
        super().__init__(characteristics)
        self.venue = VenueType.CRYPTO_SPOT


=======
>>>>>>> origin/main
def get_venue_model(venue: VenueType) -> VenueModelBase:
    """
    Factory function to get appropriate venue model.

    Args:
        venue: Type of venue

    Returns:
        Appropriate VenueModelBase subclass instance
    """
    models = {
        VenueType.CME_FUTURES: CMEVenueModel,
        VenueType.NASDAQ_EQUITIES: NasdaqVenueModel,
        VenueType.NYSE_EQUITIES: NYSEVenueModel,
        VenueType.IBKR_SMART: IBKRSmartVenueModel,
<<<<<<< HEAD
        VenueType.CENTRALIZED_EXCHANGE: CEXVenueModel,
        VenueType.DECENTRALIZED_EXCHANGE: DEXVenueModel,
        VenueType.CRYPTO_SPOT: SpotCryptoVenueModel,
    }

=======
    }
    
>>>>>>> origin/main
    model_class = models.get(venue, IBKRSmartVenueModel)
    logger.info(f"Using {model_class.__name__} for venue {venue}")
    return model_class()  # type: ignore[abstract]
