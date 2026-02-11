"""Venue-specific market models for realistic execution simulation.

Provides market models tailored to different trading venues:
- Centralized exchanges (CEX): Binance, Kraken
- Decentralized exchanges (DEX): Uniswap, SushiSwap
- Futures: CME
- Stock exchanges: Nasdaq, NYSE
- Spot crypto markets
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Literal
from datetime import datetime, time
import math
import logging

from common.types import Symbol, VenueType, VenueCharacteristics, VenueModel

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


class CEXVenueModel(VenueModelBase):
    """Model for centralized exchanges (Binance, Kraken, etc.)."""
    
    def __init__(self, characteristics: Optional[VenueCharacteristics] = None):
        """Initialize CEX model with typical characteristics."""
        if characteristics is None:
            characteristics = {
                "venue": VenueType.CENTRALIZED_EXCHANGE,
                "name": "Generic CEX",
                "base_spread_bps": 2.0,  # Typical CEX spread
                "min_spread_bps": 0.5,
                "max_spread_bps": 10.0,
                "typical_volume": 1e9,
                "fee_bps": 0.1,
                "taker_fee_bps": 0.1,
                "maker_fee_bps": 0.0,
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
        """CEX market impact using participation rate."""
        # Participation rate: order amount / 24h volume
        participation_rate = order_size_usd / max(market_volume_24h, order_size_usd)
        
        # Impact scales with participation rate squared (convex)
        # Base impact: 0.5 BPS per 0.1% participation
        impact_bps = 5.0 * (participation_rate ** 1.5)
        
        # Add spread adjustment
        spread_factor = bid_ask_spread_bps / 2.0  # Typical is 2 BPS
        impact_bps += spread_factor * participation_rate
        
        return min(impact_bps, 50.0)  # Cap at 50 BPS
    
    def estimate_fill_time(
        self,
        order_size_usd: float,
        market_volume_24h: float,
        order_aggressiveness: Literal["passive", "normal", "aggressive"],
    ) -> float:
        """CEX typical fill time is fast or can be patient."""
        # Base fill time in seconds
        if order_aggressiveness == "aggressive":
            # Market order: immediate
            return 0.1
        elif order_aggressiveness == "normal":
            # Mixed approach: couple seconds
            return 2.0
        else:  # passive
            # Limit order: depends on size
            participation = order_size_usd / max(market_volume_24h, 1e6)
            return 10.0 + 100.0 * participation
    
    def is_market_open(self) -> bool:
        """CEX is always open (24/7)."""
        return True


class DEXVenueModel(VenueModelBase):
    """Model for decentralized exchanges (Uniswap, etc.)."""
    
    def __init__(self, characteristics: Optional[VenueCharacteristics] = None):
        """Initialize DEX model with typical characteristics."""
        if characteristics is None:
            characteristics = {
                "venue": VenueType.DECENTRALIZED_EXCHANGE,
                "name": "Generic DEX",
                "base_spread_bps": 3.0,  # DEX spreads slightly wider
                "min_spread_bps": 0.5,
                "max_spread_bps": 50.0,  # DEX spreads can get very wide
                "typical_volume": 5e8,  # DEX volumes lower than CEX
                "fee_bps": 0.3,  # Standard pool fee
                "is_24_7": True,
            }
        
        super().__init__(VenueType.DECENTRALIZED_EXCHANGE, characteristics)
    
    def calculate_market_impact(
        self,
        order_size_usd: float,
        market_price: float,
        market_volume_24h: float,
        bid_ask_spread_bps: float,
    ) -> float:
        """
        DEX market impact using AMM constant product model.
        
        Impact = (sqrt(1 + participation_rate) - 1) * 10000 BPS
        """
        participation_rate = order_size_usd / max(market_volume_24h, order_size_usd)
        
        # AMM impact: square root formula
        # Larger impact than CEX for same size
        impact_bps = (math.sqrt(1.0 + participation_rate * 2.0) - 1.0) * 10000.0
        
        # DEX spreads also wider
        impact_bps += bid_ask_spread_bps * 0.5
        
        return min(impact_bps, 200.0)  # DEX impacts can be large
    
    def estimate_fill_time(
        self,
        order_size_usd: float,
        market_volume_24h: float,
        order_aggressiveness: Literal["passive", "normal", "aggressive"],
    ) -> float:
        """DEX fill time depends on pool liquidity."""
        # DEX fills are typically fast (seconds)
        if order_aggressiveness == "aggressive":
            return 1.0  # Flash swap
        elif order_aggressiveness == "normal":
            return 3.0  # Standard swap
        else:
            return 5.0  # Slippage tolerance negotiation
    
    def is_market_open(self) -> bool:
        """DEX is always open."""
        return True


class CMEVenueModel(VenueModelBase):
    """Model for CME futures."""
    
    def __init__(self, characteristics: Optional[VenueCharacteristics] = None):
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
        participation_rate = order_size_usd / max(market_volume_24h, order_size_usd)
        
        # Futures impact is minimal
        impact_bps = 0.5 * participation_rate  # Very low
        
        # Add tick sensitivity (CME often 0.25 BPS tick)
        impact_bps += 0.25
        
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
            return 5.0  # Limits may take longer
    
    def is_market_open(self) -> bool:
        """Check if market open (17:00-16:00 CST)."""
        from datetime import datetime, time, timezone
        
        # Simplified: assume open (would check actual time in production)
        return True


class NasdaqVenueModel(VenueModelBase):
    """Model for Nasdaq stock exchange."""
    
    def __init__(self, characteristics: Optional[VenueCharacteristics] = None):
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
        participation_rate = order_size_usd / max(market_volume_24h, order_size_usd)
        
        # Stock market impact
        impact_bps = 1.0 * (participation_rate ** 1.3)
        
        # Add spread component
        impact_bps += bid_ask_spread_bps * 0.3
        
        return min(impact_bps, 30.0)
    
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
    
    def __init__(self, characteristics: Optional[VenueCharacteristics] = None):
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
        participation_rate = order_size_usd / max(market_volume_24h, order_size_usd)
        
        impact_bps = 1.2 * (participation_rate ** 1.3)
        impact_bps += bid_ask_spread_bps * 0.35
        
        return min(impact_bps, 35.0)
    
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


class SpotCryptoVenueModel(VenueModelBase):
    """Model for spot crypto markets."""
    
    def __init__(self, characteristics: Optional[VenueCharacteristics] = None):
        """Initialize spot crypto model."""
        if characteristics is None:
            characteristics = {
                "venue": VenueType.CRYPTO_SPOT,
                "name": "Spot Crypto",
                "base_spread_bps": 1.5,
                "min_spread_bps": 0.5,
                "max_spread_bps": 20.0,
                "typical_volume": 1e10,
                "fee_bps": 0.1,
                "is_24_7": True,
            }
        
        super().__init__(VenueType.CRYPTO_SPOT, characteristics)
    
    def calculate_market_impact(
        self,
        order_size_usd: float,
        market_price: float,
        market_volume_24h: float,
        bid_ask_spread_bps: float,
    ) -> float:
        """Spot crypto market impact."""
        participation_rate = order_size_usd / max(market_volume_24h, order_size_usd)
        
        # Similar to CEX
        impact_bps = 3.0 * (participation_rate ** 1.4)
        impact_bps += bid_ask_spread_bps * 0.4
        
        return min(impact_bps, 40.0)
    
    def estimate_fill_time(
        self,
        order_size_usd: float,
        market_volume_24h: float,
        order_aggressiveness: Literal["passive", "normal", "aggressive"],
    ) -> float:
        """Spot crypto fills vary by exchange."""
        if order_aggressiveness == "aggressive":
            return 0.5
        elif order_aggressiveness == "normal":
            return 3.0
        else:
            return 8.0
    
    def is_market_open(self) -> bool:
        """Spot crypto always open."""
        return True


def get_venue_model(venue: VenueType) -> VenueModelBase:
    """
    Factory function to get appropriate venue model.
    
    Args:
        venue: Type of venue
    
    Returns:
        Appropriate VenueModelBase subclass instance
    """
    models = {
        VenueType.CENTRALIZED_EXCHANGE: CEXVenueModel,
        VenueType.DECENTRALIZED_EXCHANGE: DEXVenueModel,
        VenueType.CME_FUTURES: CMEVenueModel,
        VenueType.NASDAQ_EQUITIES: NasdaqVenueModel,
        VenueType.NYSE_EQUITIES: NYSEVenueModel,
        VenueType.CRYPTO_SPOT: SpotCryptoVenueModel,
    }
    
    model_class = models.get(venue, CEXVenueModel)
    logger.info(f"Using {model_class.__name__} for venue {venue}")
    return model_class()
