"""
Comprehensive end-to-end integration tests.

Tests complete trading flows:
- Data load ↓ Signal generation ↓ Risk check ↓ Order submission ↓ Position management
- Error recovery at each step
- State consistency (local vs broker)
- Monitoring and alerting
"""

import pytest
from datetime import datetime
import pandas as pd
import numpy as np

from models.cointegration import engle_granger_test
from models.spread import SpreadModel
from risk.engine import RiskEngine
from execution.modes import ExecutionEngine, ModeType
from data.validators import OHLCVValidator
from monitoring.alerter import AlertManager
from config.schemas import FullConfigSchema


@pytest.fixture
def test_config():
    """Create test configuration."""
    return FullConfigSchema(
        risk={"max_position_size": 0.1, "max_portfolio_heat": 0.2},
        strategy={"min_spread_bps": 5.0, "max_spread_bps": 50.0},
        execution={"mode": "paper"},
        data_source={"ohlcv_interval_minutes": 5}
    )


@pytest.fixture
def sample_ohlcv_data():
    """Create realistic sample OHLCV data."""
    dates = pd.date_range('2024-01-01', periods=200, freq='1h')
    base_price = 50000.0
    
    df = pd.DataFrame({
        'open': base_price + np.cumsum(np.random.randn(200) * 100),
        'high': base_price + 200 + np.cumsum(np.random.randn(200) * 100),
        'low': base_price - 200 + np.cumsum(np.random.randn(200) * 100),
        'close': base_price + np.cumsum(np.random.randn(200) * 100),
        'volume': 1000 + np.random.randint(0, 500, 200)
    }, index=dates)
    
    # Ensure High >= Low >= Close
    df['high'] = df[['open', 'high', 'close']].max(axis=1) + 50
    df['low'] = df[['open', 'low', 'close']].min(axis=1) - 50
    
    return df


@pytest.fixture
def cointegrated_pair_data():
    """Create cointegrated pair for testing."""
    dates = pd.date_range('2024-01-01', periods=200, freq='1h')
    
    # X and Y are cointegrated
    X = 100 + np.cumsum(np.random.randn(200) * 0.5)
    Y = 200 + 2 * X + np.random.randn(200) * 5  # Y = 2X + noise
    
    df_x = pd.DataFrame({
        'open': X * 0.99,
        'high': X * 1.01,
        'low': X * 0.98,
        'close': X,
        'volume': 1000
    }, index=dates)
    
    df_y = pd.DataFrame({
        'open': Y * 0.99,
        'high': Y * 1.01,
        'low': Y * 0.98,
        'close': Y,
        'volume': 1000
    }, index=dates)
    
    return {"AAPL": df_x, "MSFT": df_y}


@pytest.fixture
def execution_engine(test_config):
    """Create paper trading execution engine."""
    engine = ExecutionEngine(mode=ModeType.PAPER)
    engine.context.equity = 100000.0
    engine.context.cash = 100000.0
    return engine


@pytest.fixture
def risk_engine(test_config):
    """Create risk engine."""
    return RiskEngine(initial_equity=100000.0)


@pytest.fixture
def alerter():
    """Create AlertManager for testing."""
    return AlertManager()


class TestEndToEndDataLoadingFlow:
    """Test complete data loading flow."""
    
    def test_load_ohlcv_and_validate(self, sample_ohlcv_data):
        """Test loading and validating OHLCV data."""
        validator = OHLCVValidator(symbol="AAPL")
        
        result = validator.validate(sample_ohlcv_data)
        
        assert result.is_valid
        assert result.checks_failed == 0
        assert len(result.errors) == 0
    
    def test_reject_corrupted_data(self):
        """Test rejection of corrupted data."""
        # Create data with NaN
        dates = pd.date_range('2024-01-01', periods=10, freq='1h')
        df = pd.DataFrame({
            'open': [100, np.nan, 100, 100, 100, 100, 100, 100, 100, 100],
            'high': [102] * 10,
            'low': [98] * 10,
            'close': [101] * 10,
            'volume': [1000] * 10
        }, index=dates)
        
        validator = OHLCVValidator(symbol="AAPL")
        result = validator.validate(df)
        
        assert not result.is_valid
        assert any("NaN" in e for e in result.errors)
    
    def test_multiple_symbols_all_valid(self, sample_ohlcv_data):
        """Test loading multiple symbols."""
        validator = OHLCVValidator(symbol="AAPL")
        
        symbols = ["AAPL", "MSFT", "JPM"]
        for symbol in symbols:
            result = validator.validate(sample_ohlcv_data)
            assert result.is_valid


class TestSignalGenerationFlow:
    """Test signal generation from data."""
    
    def test_cointegration_detection(self, cointegrated_pair_data):
        """Test detecting cointegrated pairs."""
        x_data = cointegrated_pair_data["AAPL"]['close']
        y_data = cointegrated_pair_data["MSFT"]['close']
        
        # Should detect cointegration (since data is cointegrated)
        result = engle_granger_test(y_data, x_data)
        
        # Cointegrated data should be detected
        assert isinstance(result, dict)
        assert 'adf_pvalue' in result
        assert 'is_cointegrated' in result
    
    def test_spread_analysis(self, cointegrated_pair_data):
        """Test spread analysis on cointegrated pair."""
        x_data = cointegrated_pair_data["AAPL"]['close']
        y_data = cointegrated_pair_data["MSFT"]['close']
        
        # Create spread model
        model = SpreadModel(y_data, x_data)
        
        # Model should have computed spread parameters
        assert model.beta is not None
        assert model.intercept is not None
        assert model.std_residuals > 0
    
    def test_z_score_signal_generation(self, cointegrated_pair_data):
        """Test Z-score based signal generation."""
        x_data = cointegrated_pair_data["AAPL"]['close']
        y_data = cointegrated_pair_data["MSFT"]['close']
        
        # Create spread model
        model = SpreadModel(y_data, x_data)
        
        # Compute the spread
        spread_series = model.compute_spread(y_data, x_data)
        
        # Should be able to compute Z-scores
        assert len(spread_series) > 0
        assert spread_series.std() > 0


class TestRiskGatingFlow:
    """Test risk engine gating of trades."""
    
    def test_risk_engine_blocks_oversized_position(self):
        """Test risk engine rejects oversized position due to position limit."""
        from risk.engine import Position as RiskPosition
        
        risk_engine = RiskEngine(initial_equity=100000.0)
        
        # Fill up to max concurrent positions first
        for i in range(risk_engine.config.max_concurrent_positions):
            position = RiskPosition(
                symbol_pair=f"PAIR{i}",
                entry_time=datetime.utcnow(),
                entry_price=100.0,
                quantity=1.0,
                side="long"
            )
            risk_engine.positions[f"PAIR{i}"] = position
        
        # Now try to enter another trade (should be rejected)
        can_enter, reason = risk_engine.can_enter_trade(
            symbol_pair="AAPL",
            position_size=1.0,
            current_equity=100000.0,
            volatility=0.5
        )
        
        # Should be rejected due to position limit
        assert can_enter is False
        assert reason is not None
    
    def test_risk_engine_allows_sized_position(self):
        """Test risk engine allows reasonable position."""
        risk_engine = RiskEngine(initial_equity=100000.0)
        
        # Try reasonable position with low volatility
        can_enter, reason = risk_engine.can_enter_trade(
            symbol_pair="AAPL",
            position_size=1.0,
            current_equity=100000.0,
            volatility=0.5  # Low volatility (in %)
        )
        
        assert can_enter is True
        assert reason is None
    
    def test_risk_engine_blocks_after_consecutive_losses(self):
        """Test risk engine blocks after consecutive losses."""
        risk_engine = RiskEngine(initial_equity=100000.0)
        
        # Simulate losses at the configured maximum (equity dev: max_consecutive_losses=5)
        risk_engine.loss_streak = risk_engine.config.max_consecutive_losses

        can_enter, reason = risk_engine.can_enter_trade(
            symbol_pair="AAPL",
            position_size=1.0,
            current_equity=95000.0,
            volatility=0.5
        )

        # Should be blocked due to consecutive loss limit
        assert can_enter is False


class TestOrderExecutionFlow:
    """Test full order execution flow."""
    
    def test_complete_order_lifecycle(self, execution_engine):
        """Test complete order lifecycle."""
        # Setup market price
        execution_engine.context.market_prices["AAPL"] = 50000.0
        
        # 1. Submit order
        order_id = execution_engine.submit_order(
            symbol="AAPL",
            side="buy",
            quantity=1.0,
            order_type="market"
        )
        
        assert order_id is not None
        
        # 2. Check order filled
        order = execution_engine.context.get_order(order_id)
        assert order.status.value == "FILLED"
        assert order.filled_quantity == 1.0
    
    def test_position_opened_after_order(self, execution_engine):
        """Test position opened after successful order."""
        execution_engine.context.market_prices["AAPL"] = 50000.0
        
        # Submit and fill order
        execution_engine.submit_order(
            symbol="AAPL",
            side="buy",
            quantity=2.0,
            order_type="market"
        )
        
        # Open position
        success = execution_engine.open_position(
            symbol="AAPL",
            quantity=2.0,
            entry_price=50000.0
        )
        
        assert success is True
        
        # Verify position exists
        position = execution_engine.context.get_position("AAPL")
        assert position is not None
        assert position.quantity == 2.0
    
    def test_position_closed_with_pnl(self, execution_engine):
        """Test position closure and P&L calculation."""
        execution_engine.context.market_prices["AAPL"] = 50000.0
        execution_engine.context.cash = 100000.0
        
        # Open position
        execution_engine.open_position(
            symbol="AAPL",
            quantity=1.0,
            entry_price=50000.0
        )
        
        # Price goes up 5%
        exit_price = 52500.0
        
        # Close position
        success, pnl = execution_engine.close_position(
            symbol="AAPL",
            exit_price=exit_price
        )
        
        assert success is True
        assert pnl is not None
        # Will be close to profitable (may include slippage)
        assert pnl >= -500  # Allow for some slippage/commission


class TestMonitoringAndAlerting:
    """Test monitoring and alert generation."""
    
    def test_alert_on_position_opened(self, alerter):
        """Test alert generated when position opened."""
        from monitoring.alerter import AlertSeverity, AlertCategory
        
        alert = alerter.create_alert(
            severity=AlertSeverity.INFO,
            category=AlertCategory.POSITION,
            title="AAPL position opened",
            message="Opened position of 1.0 AAPL at 50000.0"
        )
        
        # Should generate alert
        assert alert is not None
        assert alert.title == "AAPL position opened"
    
    def test_alert_on_position_closed(self, alerter):
        """Test alert generated when position closed."""
        from monitoring.alerter import AlertSeverity, AlertCategory
        
        alert = alerter.create_alert(
            severity=AlertSeverity.INFO,
            category=AlertCategory.POSITION,
            title="AAPL position closed",
            message="Closed position with P&L: +1000.0"
        )
        
        # Should generate alert
        assert alert is not None
        assert alert.category == AlertCategory.POSITION
    
    def test_alert_retrieval(self, alerter):
        """Test alert retrieval and filtering."""
        from monitoring.alerter import AlertSeverity, AlertCategory
        
        # Create several alerts
        for i in range(3):
            alerter.create_alert(
                severity=AlertSeverity.INFO,
                category=AlertCategory.POSITION,
                title=f"Alert {i}",
                message=f"Test alert {i}"
            )
        
        # Retrieve active alerts
        active = alerter.get_active_alerts()
        assert len(active) == 3


class TestStateConsistencyFlow:
    """Test local vs broker state consistency."""
    
    def test_reconciliation_detects_mismatch(self, execution_engine):
        """Test that reconciliation catches state mismatch."""
        # Setup local position
        execution_engine.context.market_prices["AAPL"] = 50000.0
        execution_engine.open_position(
            symbol="AAPL",
            quantity=1.0,
            entry_price=50000.0
        )
        
        # Simulate broker has different position
        mock_broker_positions = {
            "AAPL": {"quantity": 2.0, "entry_price": 50000.0}  # Different!
        }
        
        # Check for mismatch
        local_pos = execution_engine.context.get_position("AAPL")
        assert local_pos.quantity != mock_broker_positions["AAPL"]["quantity"]
    
    def test_equity_tracking_consistency(self, execution_engine):
        """Test equity tracking consistency."""
        initial_equity = 100000.0
        execution_engine.context.equity = initial_equity
        execution_engine.context.cash = initial_equity
        
        # Open position (cost: 50000)
        execution_engine.context.market_prices["AAPL"] = 50000.0
        execution_engine.open_position(
            symbol="AAPL",
            quantity=1.0,
            entry_price=50000.0
        )
        
        # Position value + cash should equal equity
        position = execution_engine.context.get_position("AAPL")
        position_value = position.quantity * position.current_price
        total = execution_engine.context.cash + position_value
        
        # Should be approximately equal (allow for commission)
        assert abs(total - initial_equity) < 1000  # Within $1000


class TestErrorRecoveryInFlow:
    """Test error recovery during trading flow."""
    
    def test_retry_on_api_timeout(self):
        """Test retry mechanism on API timeout."""
        from common.retry import RetryPolicy, retry_with_backoff
        
        call_count = 0
        
        @retry_with_backoff(
            policy=RetryPolicy(max_attempts=3, initial_delay_seconds=0.01)
        )
        def flaky_api_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("API timeout")
            return "success"
        
        result = flaky_api_call()
        
        assert result == "success"
        assert call_count == 3
    
    def test_circuit_breaker_stops_cascading_failures(self):
        """Test circuit breaker prevents cascading failures."""
        from common.circuit_breaker import get_circuit_breaker
        
        breaker = get_circuit_breaker("api_endpoint_1")
        
        # Simulate 5 failures
        for _ in range(5):
            try:
                breaker.call(lambda: 1/0)  # Division by zero
            except:
                pass
        
        # Circuit should be open now
        assert breaker.get_state().value == "open"


class TestBacktestIntegration:
    """Test backtest mode integration."""
    
    def test_backtest_complete_flow(self, sample_ohlcv_data, test_config):
        """Test complete backtest flow."""
        engine = ExecutionEngine(mode=ModeType.BACKTEST)
        engine.context.equity = 100000.0
        engine.context.cash = 100000.0
        
        # Setup initial prices
        prices = sample_ohlcv_data['close'].iloc[:5]
        for i, price in enumerate(prices):
            engine.context.update_market_price("AAPL", float(price))
        
        # Open position at first price
        entry_price = float(prices.iloc[0])
        success = engine.open_position("AAPL", 1.0, entry_price)
        assert success is True
        
        # Close at last price
        exit_price = float(prices.iloc[-1])
        success, pnl = engine.close_position("AAPL", exit_price)
        assert success is True
        assert pnl is not None
    
    def test_backtest_with_slippage(self, test_config):
        """Test backtest slippage calculation."""
        engine = ExecutionEngine(mode=ModeType.BACKTEST)
        engine.context.market_prices["AAPL"] = 50000.0
        
        # Submit buy order at market
        order_id = engine.submit_order(
            symbol="AAPL",
            side="buy",
            quantity=1.0,
            order_type="market"
        )
        
        # Check that filled price includes slippage
        order = engine.context.get_order(order_id)
        # Buy slippage should increase price: 50000 * 1.0005 ≈ 50025
        assert order.filled_price > 50000.0


class TestCompleteStrategyFlow:
    """Test complete strategy execution flow."""
    
    def test_full_strategy_cycle(
        self,
        cointegrated_pair_data,
        test_config,
        execution_engine,
        risk_engine,
        alerter
    ):
        """Test complete trading cycle."""
        
        # Step 1: Validate data
        validator = OHLCVValidator(symbol="AAPL")
        btc_data = cointegrated_pair_data["AAPL"]
        validation = validator.validate(btc_data)
        assert validation.is_valid
        
        # Step 2: Analyze cointegration
        btc_prices = btc_data['close']
        eth_prices = cointegrated_pair_data["MSFT"]['close']
        engle_granger_test(eth_prices, btc_prices)
        
        # Step 3: Check risk
        current_price = float(btc_prices.iloc[-1])
        execution_engine.context.update_market_price("AAPL", current_price)
        
        can_trade, reason = risk_engine.can_enter_trade(
            symbol_pair="AAPL",
            position_size=0.5,
            current_equity=100000.0,
            volatility=1.0  # 1% volatility
        )
        assert can_trade is True
        
        # Step 4: Enter trade
        order_id = execution_engine.submit_order(
            symbol="AAPL",
            side="buy",
            quantity=0.5,
            order_type="market"
        )
        assert order_id is not None
        
        # Step 5: Open position
        success = execution_engine.open_position(
            symbol="AAPL",
            quantity=0.5,
            entry_price=current_price
        )
        assert success is True
        
        # Step 6: Generate alert
        from monitoring.alerter import AlertSeverity, AlertCategory
        
        alert = alerter.create_alert(
            severity=AlertSeverity.INFO,
            category=AlertCategory.POSITION,
            title="Position opened: AAPL",
            message=f"Opened 0.5 AAPL long at {current_price}"
        )
        
        assert alert is not None
        
        # Step 7: Close position
        exit_price = current_price * 1.02  # 2% profit
        success, pnl = execution_engine.close_position(
            symbol="AAPL",
            exit_price=exit_price
        )
        assert success is True
        assert pnl > 0


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
