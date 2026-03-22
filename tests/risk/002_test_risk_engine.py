import pytest

from common.validators import EquityError
from risk.engine import RiskEngine


def test_risk_engine_position_limit():
    """Test max concurrent position limit."""
    engine = RiskEngine(initial_equity=100000.0)
    engine.config.max_concurrent_positions = 3

    can_enter, reason = engine.can_enter_trade("AAPL_MSFT", 10.0, 100000, 0.05)
    assert can_enter

    # Add positions
    for i in range(3):
        engine.register_entry(f"PAIR_{i}", 100.0, 10.0, "long")

    # Try to exceed limit
    can_enter, reason = engine.can_enter_trade("NEW_PAIR", 10.0, 100000, 0.05)
    assert not can_enter
    assert reason is not None
    assert "Max concurrent" in reason


def test_risk_engine_loss_streak():
    """Test consecutive loss tracking."""
    engine = RiskEngine(initial_equity=100000.0)
    engine.config.max_consecutive_losses = 2

    # Register 2 losing trades
    engine.register_entry("PAIR_1", 100.0, 10.0, "long")
    engine.register_exit("PAIR_1", 95.0, -50.0)

    engine.register_entry("PAIR_2", 100.0, 10.0, "long")
    engine.register_exit("PAIR_2", 98.0, -20.0)

    # Third trade should be blocked
    can_enter, reason = engine.can_enter_trade("PAIR_3", 10.0, 100000, 0.05)
    assert not can_enter
    assert reason is not None
    assert "Consecutive loss" in reason


if __name__ == "__main__":
    test_risk_engine_position_limit()
    test_risk_engine_loss_streak()
    print("Ô£ô All risk tests passed")


class TestRiskEngineEquityInjection:
    """Test Phase 1.2: Equity configuration injection and validation."""

    def test_init_with_valid_equity(self):
        """Test RiskEngine initialization with valid equity."""
        engine = RiskEngine(initial_equity=100000.0)
        assert engine.initial_equity == 100000.0
        assert engine.initial_cash == 100000.0  # Defaults to initial_equity

    def test_init_with_valid_equity_and_cash(self):
        """Test RiskEngine initialization with both equity and cash."""
        engine = RiskEngine(initial_equity=100000.0, initial_cash=50000.0)
        assert engine.initial_equity == 100000.0
        assert engine.initial_cash == 50000.0

    def test_init_with_zero_equity_fails(self):
        """Test RiskEngine initialization with zero equity raises error."""
        with pytest.raises(EquityError):
            RiskEngine(initial_equity=0.0)

    def test_init_with_negative_equity_fails(self):
        """Test RiskEngine initialization with negative equity raises error."""
        with pytest.raises(EquityError):
            RiskEngine(initial_equity=-50000.0)

    def test_init_with_nan_equity_fails(self):
        """Test RiskEngine initialization with NaN equity raises error."""
        import math

        with pytest.raises(EquityError):
            RiskEngine(initial_equity=math.nan)

    def test_init_with_inf_equity_fails(self):
        """Test RiskEngine initialization with infinite equity raises error."""
        import math

        with pytest.raises(EquityError):
            RiskEngine(initial_equity=math.inf)

    def test_init_with_equity_too_low_fails(self):
        """Test RiskEngine initialization with equity < $100 fails."""
        with pytest.raises(EquityError):
            RiskEngine(initial_equity=50.0)

    def test_init_with_equity_too_high_fails(self):
        """Test RiskEngine initialization with equity > $1B fails."""
        with pytest.raises(EquityError):
            RiskEngine(initial_equity=2e9)

    def test_init_cash_exceeds_equity_fails(self):
        """Test RiskEngine initialization with cash > equity fails."""
        with pytest.raises(EquityError):
            RiskEngine(initial_equity=100000.0, initial_cash=150000.0)

    def test_init_negative_cash_fails(self):
        """Test RiskEngine initialization with negative cash fails."""
        with pytest.raises(EquityError):
            RiskEngine(initial_equity=100000.0, initial_cash=-10000.0)

    def test_can_enter_trade_validates_position_size(self):
        """Test that can_enter_trade validates position size input."""
        engine = RiskEngine(initial_equity=100000.0)

        # Negative position size should raise validation error
        with pytest.raises(Exception):
            engine.can_enter_trade("AAPL_MSFT", -10.0, 100000, 0.05)

    def test_can_enter_trade_validates_volatility(self):
        """Test that can_enter_trade validates volatility input."""
        engine = RiskEngine(initial_equity=100000.0)

        # Negative volatility should raise validation error
        with pytest.raises(Exception):
            engine.can_enter_trade("AAPL_MSFT", 10.0, 100000, -0.05)

    def test_initialization_stores_equity_values(self):
        """Test that initialization stores equity values correctly."""
        engine = RiskEngine(initial_equity=50000.0, initial_cash=25000.0)
        assert engine.initial_equity == 50000.0
        assert engine.initial_cash == 25000.0
        assert len(engine.equity_history) == 1
        assert engine.equity_history[0] == 50000.0
