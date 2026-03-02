"""
Pytest configuration and shared fixtures for all integration tests.

Provides:
- Mock execution engines
- Mock data loaders
- Mock API clients
- Realistic test data generators
- Common test utilities
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock
import pandas as pd
import numpy as np

from execution.modes import ExecutionEngine, ModeType, ExecutionContext
from data.loader import DataLoader
from data.validators import OHLCVValidator, EquityValidator
from monitoring.alerter import AlertManager
from risk.engine import RiskEngine
from config.schemas import FullConfigSchema


# ============================================================================
# DATA GENERATION FIXTURES
# ============================================================================

@pytest.fixture
def production_config():
    """Production-like configuration."""
    return FullConfigSchema(
        risk={
            "max_position_size": 0.1,
            "max_portfolio_heat": 0.2,
            "max_loss_per_trade": 0.05,
            "max_drawdown_pct": 10.0,
            "max_correlation": 0.8,
            "position_timeout_hours": 24,
            "min_equity": 10000.0
        },
        strategy={
            "min_spread_bps": 5.0,
            "max_spread_bps": 50.0,
            "fast_sma_periods": 20,
            "slow_sma_periods": 50,
            "entry_z_score": 2.0,
            "exit_z_score": 1.0,
            "profit_target_bps": 20.0,
            "stop_loss_bps": 15.0
        },
        execution={
            "mode": "paper",
            "order_type": "market",
            "timeout_seconds": 30.0,
            "max_retries": 3
        },
        data_source={
            "feed_type": "rest",
            "ohlcv_interval_minutes": 5,
            "lookback_hours": 24,
            "buffer_size": 1000
        },
        alerter={
            "alert_modes": ["log", "email"],
            "deduplication_window_minutes": 5,
            "rate_limit_per_hour": 100
        },
        backtest={
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_equity": 100000.0,
            "slippage_pct": 0.05,
            "commission_pct": 0.1
        }
    )


@pytest.fixture
def minimal_config():
    """Minimal valid configuration for quick tests."""
    return FullConfigSchema(
        risk={"max_position_size": 0.1},
        strategy={"min_spread_bps": 5.0},
        execution={"mode": "paper"},
        data_source={"feed_type": "rest"},
        alerter={"alert_modes": ["log"]},
        backtest={"initial_equity": 100000.0}
    )


@pytest.fixture
def clean_ohlcv_data():
    """Clean, realistic OHLCV data without anomalies."""
    dates = pd.date_range('2024-01-01', periods=500, freq='1h')
    base_price = 50000.0
    
    # Create realistic price movement with trends
    returns = np.random.normal(0.0001, 0.01, 500)
    prices = base_price * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame({
        'open': prices * (1 + np.random.uniform(-0.001, 0.001, 500)),
        'high': prices * (1 + np.abs(np.random.uniform(0.002, 0.005, 500))),
        'low': prices * (1 - np.abs(np.random.uniform(0.002, 0.005, 500))),
        'close': prices,
        'volume': 1000 + np.random.randint(0, 2000, 500)
    }, index=dates)
    
    # Ensure consistency: High >= Low
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    df['high'] = df['high'] + 10  # Guarantee high is highest
    df['low'] = df['low'] - 10    # Guarantee low is lowest
    
    return df


@pytest.fixture
def corrupted_ohlcv_data():
    """OHLCV data with various quality issues."""
    dates = pd.date_range('2024-01-01', periods=100, freq='1h')
    
    df = pd.DataFrame({
        'open': [100, np.nan, 100, -50, 100, 100] * 17,  # NaN, negative
        'high': [102, 102, 102, 102, 102, 102] * 17,
        'low': [98, 98, 98, 98, 98, 98] * 17,
        'close': [101, 101, 101, 101, 101, 101] * 17,
        'volume': [1000, -500, 1000, 1000, 0, 1000] * 17  # Negative and zero
    }, index=dates[:100])
    
    return df


@pytest.fixture
def trending_data():
    """Data with consistent uptrend."""
    dates = pd.date_range('2024-01-01', periods=200, freq='1h')
    prices = 50000 + np.arange(200) * 100  # 200 continuous increase
    
    df = pd.DataFrame({
        'open': prices * 0.99,
        'high': prices * 1.01,
        'low': prices * 0.98,
        'close': prices,
        'volume': 1000
    }, index=dates)
    
    df['high'] = df[['open', 'high', 'close']].max(axis=1) + 50
    df['low'] = df[['open', 'low', 'close']].min(axis=1) - 50
    
    return df


@pytest.fixture
def ranging_data():
    """Data trading in a range."""
    dates = pd.date_range('2024-01-01', periods=200, freq='1h')
    base = 50000
    noise = np.sin(np.linspace(0, 20*np.pi, 200)) * 500 + np.random.randn(200) * 50
    prices = base + noise
    
    df = pd.DataFrame({
        'open': prices * 0.99,
        'high': prices * 1.01,
        'low': prices * 0.98,
        'close': prices,
        'volume': 1000
    }, index=dates)
    
    df['high'] = df[['open', 'high', 'close']].max(axis=1) + 50
    df['low'] = df[['open', 'low', 'close']].min(axis=1) - 50
    
    return df


@pytest.fixture
def cointegrated_pair():
    """Two cointegrated price series (Y ≈ 2*X + noise)."""
    dates = pd.date_range('2024-01-01', periods=200, freq='1h')
    
    X = 100 + np.cumsum(np.random.randn(200) * 0.5)
    Y = 200 + 2 * X + np.random.randn(200) * 5
    
    df_x = pd.DataFrame({
        'open': X * 0.99, 'high': X * 1.01,
        'low': X * 0.98, 'close': X, 'volume': 1000
    }, index=dates)
    
    df_y = pd.DataFrame({
        'open': Y * 0.99, 'high': Y * 1.01,
        'low': Y * 0.98, 'close': Y, 'volume': 1000
    }, index=dates)
    
    df_x['high'] = df_x[['open', 'high', 'close']].max(axis=1) + 1
    df_x['low'] = df_x[['open', 'low', 'close']].min(axis=1) - 1
    df_y['high'] = df_y[['open', 'high', 'close']].max(axis=1) + 1
    df_y['low'] = df_y[['open', 'low', 'close']].min(axis=1) - 1
    
    return {"AAPL": df_x, "MSFT": df_y}


@pytest.fixture
def independent_pair():
    """Two independent price series."""
    dates = pd.date_range('2024-01-01', periods=200, freq='1h')
    
    X = 100 + np.cumsum(np.random.randn(200) * 0.5)
    Y = 200 + np.cumsum(np.random.randn(200) * 0.5)  # Independent brownian
    
    df_x = pd.DataFrame({
        'open': X * 0.99, 'high': X * 1.01,
        'low': X * 0.98, 'close': X, 'volume': 1000
    }, index=dates)
    
    df_y = pd.DataFrame({
        'open': Y * 0.99, 'high': Y * 1.01,
        'low': Y * 0.98, 'close': Y, 'volume': 1000
    }, index=dates)
    
    df_x['high'] = df_x[['open', 'high', 'close']].max(axis=1) + 1
    df_x['low'] = df_x[['open', 'low', 'close']].min(axis=1) - 1
    df_y['high'] = df_y[['open', 'high', 'close']].max(axis=1) + 1
    df_y['low'] = df_y[['open', 'low', 'close']].min(axis=1) - 1
    
    return {"AAPL": df_x, "MSFT": df_y}


# ============================================================================
# EXECUTION ENGINE FIXTURES
# ============================================================================

@pytest.fixture
def paper_engine():
    """Paper trading execution engine."""
    engine = ExecutionEngine(mode=ModeType.PAPER)
    engine.context.equity = 100000.0
    engine.context.cash = 100000.0
    return engine


@pytest.fixture
def backtest_engine():
    """Backtest execution engine."""
    engine = ExecutionEngine(mode=ModeType.BACKTEST)
    engine.context.equity = 100000.0
    engine.context.cash = 100000.0
    return engine


@pytest.fixture
def live_engine_mock():
    """Mock live trading engine (for testing without real broker)."""
    engine = ExecutionEngine(mode=ModeType.LIVE)
    engine.context.equity = 100000.0
    engine.context.cash = 100000.0
    
    # Mock the API client
    engine.executor.api_client = MagicMock()
    engine.executor.api_client.submit_order = MagicMock(
        return_value="mock_order_123"
    )
    
    return engine


@pytest.fixture
def execution_context():
    """Bare execution context for testing."""
    return ExecutionContext()


# ============================================================================
# VALIDATOR FIXTURES
# ============================================================================

@pytest.fixture
def ohlcv_validator():
    """OHLCV validator."""
    return OHLCVValidator(symbol="AAPL")


@pytest.fixture
def equity_validator():
    """Equity validator."""
    return EquityValidator()


# ============================================================================
# RISK & MONITORING FIXTURES
# ============================================================================

@pytest.fixture
def risk_engine_default(production_config):
    """Risk engine with production config."""
    return RiskEngine(initial_equity=100000.0)


@pytest.fixture
def risk_engine_conservative(production_config):
    """Risk engine with conservative limits."""
    return RiskEngine(initial_equity=50000.0)


@pytest.fixture
def alerter_mock():
    """Mock alerter."""
    return AlertManager()


# ============================================================================
# DATA LOADER FIXTURES
# ============================================================================

@pytest.fixture
def data_loader_mock():
    """Mock data loader."""
    loader = MagicMock(spec=DataLoader)
    loader.load_ohlcv = MagicMock()
    loader.load_latest = MagicMock()
    return loader


# ============================================================================
# UTILITIES & MARKERS
# ============================================================================

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (full flow)"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers",
        "regression: mark test as regression test"
    )


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory for tests."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    return data_dir


def create_sample_position(symbol="AAPL", quantity=1.0, entry_price=50000.0):
    """Helper to create sample position."""
    from execution.modes import Position
    
    return Position(
        symbol=symbol,
        quantity=quantity,
        entry_price=entry_price,
        entry_time=datetime.utcnow(),
        current_price=entry_price,
    )


def assert_positions_equal(pos1, pos2):
    """Assert two positions are equal."""
    assert pos1.symbol == pos2.symbol
    assert pos1.quantity == pos2.quantity
    assert abs(pos1.entry_price - pos2.entry_price) < 0.01
    assert abs(pos1.current_price - pos2.current_price) < 0.01


def assert_dataframe_valid(df, symbol="TEST"):
    """Assert dataframe passes basic OHLCV validation."""
    validator = OHLCVValidator(symbol=symbol)
    result = validator.validate(df)
    assert result.is_valid, f"Validation failed: {result.errors}"


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    from common.circuit_breaker import reset_all_circuit_breakers
    
    reset_all_circuit_breakers()
    
    yield
    
    reset_all_circuit_breakers()


if __name__ == "__main__":
    print("... Conftest configured")
    print("- 6 data generation fixtures (clean, corrupted, trending, ranging, cointegrated, independent)")
    print("- 4 execution engine fixtures (paper, backtest, live mock, bare context)")
    print("- 3 risk/monitoring fixtures (default, conservative, alerter)")
    print("- Utilities for position creation and assertions")
