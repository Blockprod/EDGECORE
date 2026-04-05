<<<<<<< HEAD
﻿from datetime import datetime
=======
from datetime import datetime
>>>>>>> origin/main

import pytest

from common.validators import EquityError, ValidationError, VolatilityError
from risk.engine import Position, RiskEngine


# Mock config/settings if needed
class DummyConfig:
    max_concurrent_positions = 2
    max_risk_per_trade = 0.05
    max_consecutive_losses = 2
    max_daily_loss_pct = 0.10  # Ajout pour tests
    max_leverage = 2.0  # Ajout pour tests

<<<<<<< HEAD

=======
>>>>>>> origin/main
# Patch get_settings to return dummy config only for these tests


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch):
    import config.settings as settings_mod

    monkeypatch.setattr(
        settings_mod,
        "get_settings",
<<<<<<< HEAD
        lambda: type("S", (), {"risk": DummyConfig()})(),
=======
        lambda: type('S', (), {'risk': DummyConfig()})(),
>>>>>>> origin/main
    )
    yield


def test_init_valid_equity():
    engine = RiskEngine(initial_equity=100000)
    assert engine.initial_equity == 100000
    assert engine.current_equity == 100000
    assert engine.initial_cash == 100000
    assert isinstance(engine.audit_trail, object)


def test_init_invalid_equity():
    with pytest.raises(EquityError):
        RiskEngine(initial_equity=-100)


def test_can_enter_trade_valid():
    engine = RiskEngine(initial_equity=100000)
    allowed, reason = engine.can_enter_trade(
<<<<<<< HEAD
        symbol_pair="AAPL_MSFT", position_size=1000, current_equity=100000, volatility=0.01
=======
        symbol_pair="AAPL_MSFT",
        position_size=1000,
        current_equity=100000,
        volatility=0.01
>>>>>>> origin/main
    )
    assert allowed is True
    assert reason is None


def test_can_enter_trade_max_positions():
    engine = RiskEngine(initial_equity=100000)
    engine.positions = {"AAPL_MSFT": Position("AAPL_MSFT", datetime.now(), 100, 10, "long")}
    engine.positions["GOOGL_META"] = Position("GOOGL_META", datetime.now(), 100, 10, "short")
    allowed, reason = engine.can_enter_trade(
<<<<<<< HEAD
        symbol_pair="TSLA_NVDA", position_size=1000, current_equity=100000, volatility=0.01
    )
    assert allowed is False
    assert reason is not None
=======
        symbol_pair="TSLA_NVDA",
        position_size=1000,
        current_equity=100000,
        volatility=0.01
    )
    assert allowed is False
>>>>>>> origin/main
    assert "Max concurrent positions" in reason


def test_can_enter_trade_invalid_inputs():
    engine = RiskEngine(initial_equity=100000)
    with pytest.raises(EquityError):
        engine.can_enter_trade("AAPL_MSFT", 1000, -100, 0.01)
    with pytest.raises(ValidationError):
        engine.can_enter_trade("AAPL_MSFT", -1000, 100000, 0.01)
    with pytest.raises(VolatilityError):
        engine.can_enter_trade("AAPL_MSFT", 1000, 100000, -0.01)


def test_can_enter_trade_risk_pct():
    engine = RiskEngine(initial_equity=100000)
    # position_size * volatility = 1000 * 0.1 = 100, risk_pct = 100/100000 = 0.001
    allowed, reason = engine.can_enter_trade("AAPL_MSFT", 1000, 100000, 0.1)
    assert allowed is True
    # Exceeds max_risk_per_trade
    allowed, reason = engine.can_enter_trade("AAPL_MSFT", 100000, 100000, 0.1)
    assert allowed is False
<<<<<<< HEAD
    assert reason is not None
=======
>>>>>>> origin/main
    assert "Risk per trade" in reason


def test_can_enter_trade_loss_streak():
    engine = RiskEngine(initial_equity=100000)
    engine.loss_streak = 2
    allowed, reason = engine.can_enter_trade("AAPL_MSFT", 1000, 100000, 0.01)
    assert allowed is False
<<<<<<< HEAD
    assert reason is not None
=======
>>>>>>> origin/main
    assert "Consecutive loss limit" in reason
