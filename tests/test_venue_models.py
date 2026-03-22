"""Tests for venue-specific market models."""

from common.types import VenueType
from execution.venue_models import (
    CEXVenueModel,
    CMEVenueModel,
    DEXVenueModel,
    NasdaqVenueModel,
    NYSEVenueModel,
    OrderExecutionMicrostructure,
    SpotCryptoVenueModel,
    get_venue_model,
)


class TestCEXVenueModel:
    """Test centralized exchange model."""

    def test_cex_initialization(self):
        """Test CEX model creation."""
        model = CEXVenueModel()

        assert model.venue == VenueType.CENTRALIZED_EXCHANGE
        assert model.characteristics["base_spread_bps"] == 2.0
        assert model.characteristics["is_24_7"] == True

    def test_cex_market_impact(self):
        """Test CEX market impact calculation."""
        model = CEXVenueModel()

        # Small order in liquid market
        impact = model.calculate_market_impact(
            order_size_usd=10_000,
            market_price=50_000,
            market_volume_24h=1_000_000_000,
            bid_ask_spread_bps=2.0,
        )

        assert impact > 0
        assert impact < 5.0  # Should be small

    def test_cex_large_order_impact(self):
        """Test that large orders have larger impact."""
        model = CEXVenueModel()

        small_impact = model.calculate_market_impact(
            order_size_usd=10_000,
            market_price=50_000,
            market_volume_24h=1_000_000_000,
            bid_ask_spread_bps=2.0,
        )

        large_impact = model.calculate_market_impact(
            order_size_usd=1_000_000,
            market_price=50_000,
            market_volume_24h=1_000_000_000,
            bid_ask_spread_bps=2.0,
        )

        assert large_impact > small_impact

    def test_cex_fill_time_aggressive(self):
        """Test CEX aggressive order fill time."""
        model = CEXVenueModel()

        fill_time = model.estimate_fill_time(
            order_size_usd=100_000,
            market_volume_24h=1_000_000_000,
            order_aggressiveness="aggressive",
        )

        assert fill_time < 1.0  # Should be instant

    def test_cex_fill_time_passive(self):
        """Test CEX passive order fill time."""
        model = CEXVenueModel()

        fill_time = model.estimate_fill_time(
            order_size_usd=100_000,
            market_volume_24h=1_000_000_000,
            order_aggressiveness="passive",
        )

        assert fill_time > 5.0  # Should take longer

    def test_cex_is_open(self):
        """Test CEX 24/7 availability."""
        model = CEXVenueModel()
        assert model.is_market_open() == True


class TestDEXVenueModel:
    """Test decentralized exchange model."""

    def test_dex_initialization(self):
        """Test DEX model creation."""
        model = DEXVenueModel()

        assert model.venue == VenueType.DECENTRALIZED_EXCHANGE
        assert model.characteristics["is_24_7"] == True

    def test_dex_market_impact_higher(self):
        """Test that DEX has higher impact than CEX."""
        cex_model = CEXVenueModel()
        dex_model = DEXVenueModel()

        cex_impact = cex_model.calculate_market_impact(
            order_size_usd=100_000,
            market_price=50_000,
            market_volume_24h=500_000_000,  # Lower volume
            bid_ask_spread_bps=3.0,
        )

        dex_impact = dex_model.calculate_market_impact(
            order_size_usd=100_000,
            market_price=50_000,
            market_volume_24h=500_000_000,
            bid_ask_spread_bps=3.0,
        )

        # DEX should have higher impact due to AMM model
        assert dex_impact > cex_impact

    def test_dex_execution_price(self):
        """Test DEX execution price calculation."""
        model = DEXVenueModel()

        exec_price = model.calculate_execution_price(
            market_price=100.0,
            order_side="buy",
            order_size_usd=50_000,
            market_volume_24h=500_000_000,
            bid_ask_spread=3.0,
        )

        # Buy should execute above market due to spread + impact
        assert exec_price > 100.0

    def test_dex_fill_time(self):
        """Test DEX fill times."""
        model = DEXVenueModel()

        aggressive_time = model.estimate_fill_time(
            order_size_usd=50_000,
            market_volume_24h=500_000_000,
            order_aggressiveness="aggressive",
        )

        passive_time = model.estimate_fill_time(
            order_size_usd=50_000,
            market_volume_24h=500_000_000,
            order_aggressiveness="passive",
        )

        assert aggressive_time < passive_time


class TestCMEVenueModel:
    """Test CME futures model."""

    def test_cme_initialization(self):
        """Test CME model creation."""
        model = CMEVenueModel()

        assert model.venue == VenueType.CME_FUTURES
        assert model.characteristics["base_spread_bps"] == 0.5

    def test_cme_minimal_impact(self):
        """Test that CME has very low market impact."""
        model = CMEVenueModel()

        impact = model.calculate_market_impact(
            order_size_usd=1_000_000,  # Large order
            market_price=50_000,
            market_volume_24h=100_000_000_000,  # Huge volume
            bid_ask_spread_bps=0.5,
        )

        assert impact < 1.0  # Minimal impact

    def test_cme_tight_spreads(self):
        """Test CME tight spreads."""
        model = CMEVenueModel()

        # Even on large orders, spreads should be tight
        assert model.characteristics["base_spread_bps"] < 1.0
        assert model.characteristics["min_spread_bps"] < 0.5


class TestNasdaqVenueModel:
    """Test Nasdaq stock exchange model."""

    def test_nasdaq_initialization(self):
        """Test Nasdaq model creation."""
        model = NasdaqVenueModel()

        assert model.venue == VenueType.NASDAQ_EQUITIES
        assert model.characteristics.get("opening_hours") == "09:30-16:00 EST"

    def test_nasdaq_market_impact(self):
        """Test Nasdaq market impact calculation."""
        model = NasdaqVenueModel()

        impact = model.calculate_market_impact(
            order_size_usd=500_000,
            market_price=100.0,
            market_volume_24h=100_000_000,
            bid_ask_spread_bps=1.0,
        )

        assert impact > 0
        assert impact < 20.0  # Reasonable range

    def test_nasdaq_execution_price(self):
        """Test Nasdaq execution price."""
        model = NasdaqVenueModel()

        buy_price = model.calculate_execution_price(
            market_price=100.0,
            order_side="buy",
            order_size_usd=100_000,
            market_volume_24h=100_000_000,
            bid_ask_spread=1.0,
        )

        sell_price = model.calculate_execution_price(
            market_price=100.0,
            order_side="sell",
            order_size_usd=100_000,
            market_volume_24h=100_000_000,
            bid_ask_spread=1.0,
        )

        # Buy should be higher, sell lower
        assert buy_price > 100.0
        assert sell_price < 100.0


class TestNYSEVenueModel:
    """Test NYSE stock exchange model."""

    def test_nyse_initialization(self):
        """Test NYSE model creation."""
        model = NYSEVenueModel()

        assert model.venue == VenueType.NYSE_EQUITIES
        assert "09:30" in (model.characteristics.get("opening_hours") or "")

    def test_nyse_impact_similar_to_nasdaq(self):
        """Test that NYSE impact is similar to but slightly higher than Nasdaq."""
        nyse_model = NYSEVenueModel()
        nasdaq_model = NasdaqVenueModel()

        nyse_impact = nyse_model.calculate_market_impact(
            order_size_usd=500_000,
            market_price=100.0,
            market_volume_24h=100_000_000,
            bid_ask_spread_bps=1.2,
        )

        nasdaq_impact = nasdaq_model.calculate_market_impact(
            order_size_usd=500_000,
            market_price=100.0,
            market_volume_24h=100_000_000,
            bid_ask_spread_bps=1.0,
        )

        # NYSE should be slightly higher
        assert nyse_impact >= nasdaq_impact


class TestSpotCryptoVenueModel:
    """Test spot crypto market model."""

    def test_spot_crypto_initialization(self):
        """Test spot crypto model creation."""
        model = SpotCryptoVenueModel()

        assert model.venue == VenueType.CRYPTO_SPOT
        assert model.characteristics["is_24_7"] == True

    def test_spot_crypto_market_impact(self):
        """Test spot crypto market impact."""
        model = SpotCryptoVenueModel()

        impact = model.calculate_market_impact(
            order_size_usd=100_000,
            market_price=50_000,
            market_volume_24h=10_000_000_000,
            bid_ask_spread_bps=1.5,
        )

        assert impact > 0
        assert impact < 50.0


class TestGetVenueModel:
    """Test venue model factory function."""

    def test_get_cex_model(self):
        """Test getting CEX model."""
        model = get_venue_model(VenueType.CENTRALIZED_EXCHANGE)
        assert isinstance(model, CEXVenueModel)

    def test_get_dex_model(self):
        """Test getting DEX model."""
        model = get_venue_model(VenueType.DECENTRALIZED_EXCHANGE)
        assert isinstance(model, DEXVenueModel)

    def test_get_cme_model(self):
        """Test getting CME model."""
        model = get_venue_model(VenueType.CME_FUTURES)
        assert isinstance(model, CMEVenueModel)

    def test_get_nasdaq_model(self):
        """Test getting Nasdaq model."""
        model = get_venue_model(VenueType.NASDAQ_EQUITIES)
        assert isinstance(model, NasdaqVenueModel)

    def test_get_nyse_model(self):
        """Test getting NYSE model."""
        model = get_venue_model(VenueType.NYSE_EQUITIES)
        assert isinstance(model, NYSEVenueModel)

    def test_get_spot_model(self):
        """Test getting spot crypto model."""
        model = get_venue_model(VenueType.CRYPTO_SPOT)
        assert isinstance(model, SpotCryptoVenueModel)


class TestOrderExecutionMicrostructure:
    """Test order execution microstructure dataclass."""

    def test_microstructure_creation(self):
        """Test creating execution microstructure."""
        exec_micro = OrderExecutionMicrostructure(
            venue=VenueType.CENTRALIZED_EXCHANGE,
            symbol="BTC/USD",
            order_side="buy",
            order_size_usd=100_000,
            market_price=50_000,
            bid_ask_spread_bps=2.0,
            order_book_depth=5_000_000,
            market_volume_24h=1_000_000_000,
            execution_price=50_050,
            market_impact_bps=1.0,
            fee_bps=0.1,
            total_cost_bps=1.1,
            liquidity_score=0.95,
            estimated_fill_time_s=0.1,
        )

        assert exec_micro.symbol == "BTC/USD"
        assert exec_micro.execution_price > exec_micro.market_price
        assert exec_micro.total_cost_bps == 1.1


class TestComparisonAcrossVenues:
    """
    Integration tests comparing different venues.

    Tests realistic scenarios with the same order across venues.
    """

    def test_same_order_different_venues_impact(self):
        """Test same order has different impact across venues."""
        order_size_usd = 500_000
        market_price = 100.0
        market_volume_24h = 100_000_000
        spread_bps = 2.0

        models = {
            "CEX": CEXVenueModel(),
            "DEX": DEXVenueModel(),
            "CME": CMEVenueModel(),
            "Nasdaq": NasdaqVenueModel(),
            "NYSE": NYSEVenueModel(),
            "Spot": SpotCryptoVenueModel(),
        }

        impacts = {}
        for venue_name, model in models.items():
            impact = model.calculate_market_impact(
                order_size_usd=order_size_usd,
                market_price=market_price,
                market_volume_24h=market_volume_24h,
                bid_ask_spread_bps=spread_bps,
            )
            impacts[venue_name] = impact

        # CME should have lowest impact
        assert impacts["CME"] < impacts["Nasdaq"]
        assert impacts["Nasdaq"] < impacts["DEX"]

        # Verify all impacts are positive and reasonable
        for impact in impacts.values():
            assert 0 < impact < 200

    def test_liquidity_affects_execution_price(self):
        """Test how order size affects execution price across venues."""
        market_price = 50_000
        market_volume_24h = 100_000_000

        models = [
            ("CEX", CEXVenueModel()),
            ("DEX", DEXVenueModel()),
        ]

        for _venue_name, model in models:
            small_order = model.calculate_execution_price(
                market_price=market_price,
                order_side="buy",
                order_size_usd=10_000,
                market_volume_24h=market_volume_24h,
                bid_ask_spread=2.0,
            )

            large_order = model.calculate_execution_price(
                market_price=market_price,
                order_side="buy",
                order_size_usd=1_000_000,
                market_volume_24h=market_volume_24h,
                bid_ask_spread=2.0,
            )

            # Large order should execute at worse price
            assert large_order > small_order
