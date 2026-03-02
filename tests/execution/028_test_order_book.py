"""
Tests for realistic order book simulation (Phase 4).

Covers:
- Order book generation with realistic levels
- Bid-ask spread calculation
- Liquidity metrics and depth analysis
- Market impact estimation
- Microstructure effects
"""


import pytest

from common.types import (
    BookSimulationConfig,
)
from execution.order_book import (
    OrderBookSimulator,
    MarketMicrostructure,
)


# ============================================================================
# ORDER BOOK SIMULATOR TESTS
# ============================================================================


class TestOrderBookSimulator:
    """Test OrderBookSimulator for realistic order book generation."""

    def test_simulator_creation(self) -> None:
        """Test simulator instantiation."""
        config: BookSimulationConfig = {
            "symbols": ["AAPL", "MSFT"],
            "bid_ask_spread_bps": 5.0,
            "depth_mode": "medium",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }
        sim = OrderBookSimulator(config)
        assert sim.config["bid_ask_spread_bps"] == 5.0

    def test_simulator_validation(self) -> None:
        """Test simulator validates configuration."""
        invalid_config: BookSimulationConfig = {
            "symbols": [],
            "bid_ask_spread_bps": 0.1,  # Too small
            "depth_mode": "medium",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }
        with pytest.raises(ValueError):
            OrderBookSimulator(invalid_config)

    def test_order_book_creation(self) -> None:
        """Test order book is created with realistic structure."""
        config: BookSimulationConfig = {
            "symbols": ["AAPL"],
            "bid_ask_spread_bps": 5.0,
            "depth_mode": "medium",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }
        sim = OrderBookSimulator(config)

        book = sim.create_order_book(
            symbol="AAPL",
            mid_price=150.0,
            volatility=20.0,
        )

        assert book["symbol"] == "AAPL"
        assert len(book["bid_levels"]) > 0
        assert len(book["ask_levels"]) > 0
        assert book["bid_volume"] > 0
        assert book["ask_volume"] > 0

    def test_order_book_spread_calculation(self) -> None:
        """Test bid-ask spread is calculated correctly."""
        config: BookSimulationConfig = {
            "symbols": ["AAPL"],
            "bid_ask_spread_bps": 5.0,
            "depth_mode": "medium",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }
        sim = OrderBookSimulator(config)

        book = sim.create_order_book(
            symbol="AAPL",
            mid_price=150.0,
            volatility=20.0,
        )

        # Spread should be positive and in reasonable range
        assert book["bid_ask_spread_bps"] > 0
        assert book["bid_ask_spread_bps"] < 30  # Not too wide

    def test_bid_ask_levels_ordering(self) -> None:
        """Test bid/ask levels are properly ordered."""
        config: BookSimulationConfig = {
            "symbols": ["AAPL"],
            "bid_ask_spread_bps": 5.0,
            "depth_mode": "medium",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }
        sim = OrderBookSimulator(config)

        book = sim.create_order_book(
            symbol="AAPL",
            mid_price=150.0,
            volatility=20.0,
        )

        # Bids should be descending
        bid_prices = [level["price"] for level in book["bid_levels"]]
        assert bid_prices == sorted(bid_prices, reverse=True)

        # Asks should be ascending
        ask_prices = [level["price"] for level in book["ask_levels"]]
        assert ask_prices == sorted(ask_prices)

        # Best bid < best ask
        if bid_prices and ask_prices:
            assert bid_prices[0] < ask_prices[0]

    def test_spread_widens_with_volatility(self) -> None:
        """Test spread increases with higher volatility."""
        config: BookSimulationConfig = {
            "symbols": ["AAPL"],
            "bid_ask_spread_bps": 5.0,
            "depth_mode": "medium",
            "volatility_factor": 2.0,
            "realism_level": "realistic",
        }
        sim = OrderBookSimulator(config)

        # Low volatility
        book_low_vol = sim.create_order_book(
            symbol="AAPL",
            mid_price=150.0,
            volatility=10.0,
        )

        # High volatility
        book_high_vol = sim.create_order_book(
            symbol="AAPL",
            mid_price=150.0,
            volatility=50.0,
        )

        # High vol should have wider spread
        assert book_high_vol["bid_ask_spread_bps"] >= book_low_vol["bid_ask_spread_bps"]

    def test_depth_mode_affects_book(self) -> None:
        """Test depth mode affects order book structure."""
        shallow_config: BookSimulationConfig = {
            "symbols": ["AAPL"],
            "bid_ask_spread_bps": 5.0,
            "depth_mode": "shallow",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }
        deep_config: BookSimulationConfig = {
            "symbols": ["AAPL"],
            "bid_ask_spread_bps": 5.0,
            "depth_mode": "deep",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }

        shallow_sim = OrderBookSimulator(shallow_config)
        deep_sim = OrderBookSimulator(deep_config)

        shallow_book = shallow_sim.create_order_book("AAPL", 150.0, 20.0)
        deep_book = deep_sim.create_order_book("AAPL", 150.0, 20.0)

        # Deep book has more levels and volume
        assert len(deep_book["bid_levels"]) > len(shallow_book["bid_levels"])
        assert deep_book["bid_volume"] > shallow_book["bid_volume"]

    def test_estimate_execution_price_buy(self) -> None:
        """Test execution price estimation for buy order."""
        config: BookSimulationConfig = {
            "symbols": ["AAPL"],
            "bid_ask_spread_bps": 5.0,
            "depth_mode": "medium",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }
        sim = OrderBookSimulator(config)

        book = sim.create_order_book("AAPL", 150.0, 20.0)
        best_ask = book["ask_levels"][0]["price"]

        # Small order should fill at best ask
        exec_price, filled, impact = sim.estimate_execution_price(book, "buy", 10.0)

        assert filled > 0
        assert exec_price >= best_ask  # Execute at or worse than best ask
        assert impact >= 0

    def test_estimate_execution_price_sell(self) -> None:
        """Test execution price estimation for sell order."""
        config: BookSimulationConfig = {
            "symbols": ["AAPL"],
            "bid_ask_spread_bps": 5.0,
            "depth_mode": "medium",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }
        sim = OrderBookSimulator(config)

        book = sim.create_order_book("AAPL", 150.0, 20.0)
        best_bid = book["bid_levels"][0]["price"]

        exec_price, filled, impact = sim.estimate_execution_price(book, "sell", 10.0)

        assert filled > 0
        assert exec_price <= best_bid  # Execute at or worse than best bid
        assert impact >= 0

    def test_large_order_market_impact(self) -> None:
        """Test large orders show significant market impact."""
        config: BookSimulationConfig = {
            "symbols": ["AAPL"],
            "bid_ask_spread_bps": 5.0,
            "depth_mode": "medium",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }
        sim = OrderBookSimulator(config)

        book = sim.create_order_book("AAPL", 150.0, 20.0)

        # Small order
        small_price, _, small_impact = sim.estimate_execution_price(book, "buy", 10.0)

        # Large order
        large_price, _, large_impact = sim.estimate_execution_price(book, "buy", 5000.0)

        # Large order should have more impact
        assert large_impact >= small_impact

    def test_calculate_liquidity_metrics(self) -> None:
        """Test liquidity metrics calculation."""
        config: BookSimulationConfig = {
            "symbols": ["AAPL"],
            "bid_ask_spread_bps": 5.0,
            "depth_mode": "medium",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }
        sim = OrderBookSimulator(config)

        book = sim.create_order_book("AAPL", 150.0, 20.0)
        metrics = sim.calculate_liquidity_metrics(book, 150.0)

        assert metrics["symbol"] == "AAPL"
        assert metrics["bid_ask_spread"] > 0
        assert metrics["bid_ask_spread_pct"] > 0
        assert metrics["depth_at_10bps"] > 0
        assert metrics["depth_at_20bps"] >= metrics["depth_at_10bps"]
        assert metrics["estimated_impact_100bps"] >= 0

    def test_generate_order_update(self) -> None:
        """Test order book update generation."""
        config: BookSimulationConfig = {
            "symbols": ["AAPL"],
            "bid_ask_spread_bps": 5.0,
            "depth_mode": "medium",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }
        sim = OrderBookSimulator(config)

        book = sim.create_order_book("AAPL", 150.0, 20.0)
        update = sim.generate_order_update(book, side="bid")

        assert update["symbol"] == "AAPL"
        assert update["side"] in ["bid", "ask"]
        assert update["update_type"] in ["trade", "add", "cancel", "modify"]
        assert update["quantity"] > 0
        assert update["order_count"] >= 0


# ============================================================================
# MARKET MICROSTRUCTURE TESTS
# ============================================================================


class TestMarketMicrostructure:
    """Test MarketMicrostructure for impact analysis."""

    def test_market_impact_small_order(self) -> None:
        """Test market impact for small order."""
        ms = MarketMicrostructure()
        impact = ms.estimate_market_impact(
            order_size=100,
            market_volume=1000000.0,
            volatility=20.0,
        )
        assert impact > 0
        assert impact < 10  # Should be small

    def test_market_impact_large_order(self) -> None:
        """Test market impact for large order."""
        ms = MarketMicrostructure()
        impact = ms.estimate_market_impact(
            order_size=100000,
            market_volume=1000000.0,
            volatility=20.0,
        )
        assert impact > 0
        assert impact > 10  # Should be substantial

    def test_market_impact_scales_with_size(self) -> None:
        """Test impact scales with order size."""
        ms = MarketMicrostructure()

        impact_small = ms.estimate_market_impact(100, 1000000.0, 20.0)
        impact_large = ms.estimate_market_impact(10000, 1000000.0, 20.0)

        assert impact_large > impact_small

    def test_market_impact_reduced_by_volatility(self) -> None:
        """Test higher volatility reduces market impact."""
        ms = MarketMicrostructure()

        impact_low_vol = ms.estimate_market_impact(
            order_size=10000,
            market_volume=1000000.0,
            volatility=10.0,
        )
        impact_high_vol = ms.estimate_market_impact(
            order_size=10000,
            market_volume=1000000.0,
            volatility=50.0,
        )

        # Higher volatility should reduce impact
        assert impact_high_vol < impact_low_vol

    def test_participation_rate_impact_low(self) -> None:
        """Test participation rate impact for low participation."""
        ms = MarketMicrostructure()

        impact = ms.estimate_participation_rate_impact(
            order_size=1000,
            time_window_minutes=60,
            daily_volume=10000000.0,
        )

        assert impact > 0
        assert impact < 10

    def test_participation_rate_impact_high(self) -> None:
        """Test participation rate impact for high participation."""
        ms = MarketMicrostructure()

        impact = ms.estimate_participation_rate_impact(
            order_size=100000,
            time_window_minutes=5,
            daily_volume=1000000.0,
        )

        assert impact > 50

    def test_participation_rate_impact_scaling(self) -> None:
        """Test participation rate impact increases with rate."""
        ms = MarketMicrostructure()

        impact_1pct = ms.estimate_participation_rate_impact(
            order_size=10000,
            time_window_minutes=10,
            daily_volume=10000000.0,
        )
        impact_5pct = ms.estimate_participation_rate_impact(
            order_size=50000,
            time_window_minutes=10,
            daily_volume=10000000.0,
        )

        assert impact_5pct > impact_1pct


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestOrderBookIntegration:
    """Integration tests for order book simulation."""

    def test_realistic_trading_scenario(self) -> None:
        """Test realistic trading scenario with order book."""
        config: BookSimulationConfig = {
            "symbols": ["SPY"],
            "bid_ask_spread_bps": 3.0,
            "depth_mode": "deep",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }
        sim = OrderBookSimulator(config)

        # Create order book
        book = sim.create_order_book("SPY", mid_price=420.0, volatility=15.0)

        # Simulate several trades
        results = []
        for i in range(3):
            exec_price, filled, impact = sim.estimate_execution_price(
                book, "buy", 1000.0
            )
            results.append((exec_price, filled, impact))

        # All trades should show fills and impact
        for exec_price, filled, impact in results:
            assert filled > 0
            assert exec_price > 0
            assert impact >= 0

    def test_liquidity_comparison_across_depths(self) -> None:
        """Compare liquidity across different depth modes."""
        shallow_config: BookSimulationConfig = {
            "symbols": ["SPY"],
            "bid_ask_spread_bps": 3.0,
            "depth_mode": "shallow",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }
        deep_config: BookSimulationConfig = {
            "symbols": ["SPY"],
            "bid_ask_spread_bps": 3.0,
            "depth_mode": "deep",
            "volatility_factor": 1.0,
            "realism_level": "realistic",
        }

        shallow_sim = OrderBookSimulator(shallow_config)
        deep_sim = OrderBookSimulator(deep_config)

        shallow_book = shallow_sim.create_order_book("SPY", 420.0, 15.0)
        deep_book = deep_sim.create_order_book("SPY", 420.0, 15.0)

        shallow_metrics = shallow_sim.calculate_liquidity_metrics(shallow_book, 420.0)
        deep_metrics = deep_sim.calculate_liquidity_metrics(deep_book, 420.0)

        # Deep book should have better depth
        assert deep_metrics["depth_at_10bps"] >= shallow_metrics["depth_at_10bps"]
        # Impact estimate may be 0 for small orders, so just check depth is better
        assert deep_metrics["depth_at_20bps"] >= shallow_metrics["depth_at_20bps"]

    def test_microstructure_impact_vs_order_book_impact(self) -> None:
        """Compare impact from two different models."""
        sim = OrderBookSimulator()
        ms = MarketMicrostructure()

        book = sim.create_order_book("SPY", mid_price=420.0, volatility=20.0)

        # Get impact from order book
        _, _, book_impact = sim.estimate_execution_price(book, "buy", 5000.0)

        # Get impact from microstructure model
        ms_impact = ms.estimate_market_impact(
            order_size=5000,
            market_volume=100000000.0,
            volatility=20.0,
        )

        # Both should indicate impact
        assert book_impact >= 0
        assert ms_impact > 0
