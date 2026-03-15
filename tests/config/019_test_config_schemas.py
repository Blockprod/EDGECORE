"""
Tests for configuration schema validation.

Covers:
- Risk configuration validation
- Strategy parameter validation
- Execution configuration validation
- Data source configuration validation
- Alerter configuration validation
- Backtest configuration validation
- Full system configuration validation
"""

import pytest
from pydantic import ValidationError

from config.schemas import (
    RiskConfigSchema,
    StrategyConfigSchema,
    ExecutionConfigSchema,
    DataSourceConfigSchema,
    AlerterConfigSchema,
    BacktestConfigSchema,
    FullConfigSchema,
    ExecutionMode,
    OrderType,
    validate_config_file
)


class TestRiskConfigSchema:
    """Test risk configuration validation."""
    
    def test_default_risk_config(self):
        """Test default risk configuration."""
        config = RiskConfigSchema()
        
        assert config.max_position_size == 0.1
        assert config.max_portfolio_heat == 0.2
        assert config.max_loss_per_trade == 0.02
        assert config.max_drawdown_pct == 10.0
        assert config.max_correlation == 0.7
        assert config.position_timeout_minutes == 120
    
    def test_custom_risk_config(self):
        """Test custom risk configuration."""
        config = RiskConfigSchema(
            max_position_size=0.15,
            max_portfolio_heat=0.25,
            max_loss_per_trade=0.03
        )
        
        assert config.max_position_size == 0.15
        assert config.max_portfolio_heat == 0.25
        assert config.max_loss_per_trade == 0.03
    
    def test_invalid_position_size_zero(self):
        """Test rejection of zero position size."""
        with pytest.raises(ValidationError):
            RiskConfigSchema(max_position_size=0.0)
    
    def test_invalid_position_size_too_large(self):
        """Test rejection of position size > 1.0."""
        with pytest.raises(ValidationError):
            RiskConfigSchema(max_position_size=1.5)
    
    def test_invalid_position_size_negative(self):
        """Test rejection of negative position size."""
        with pytest.raises(ValidationError):
            RiskConfigSchema(max_position_size=-0.1)
    
    def test_invalid_drawdown_zero(self):
        """Test rejection of negative drawdown."""
        with pytest.raises(ValidationError):
            RiskConfigSchema(max_drawdown_pct=-5.0)
    
    def test_invalid_drawdown_too_large(self):
        """Test rejection of drawdown >= 100%."""
        with pytest.raises(ValidationError):
            RiskConfigSchema(max_drawdown_pct=100.0)
    
    def test_invalid_correlation_negative(self):
        """Test rejection of negative correlation."""
        with pytest.raises(ValidationError):
            RiskConfigSchema(max_correlation=-0.1)
    
    def test_invalid_correlation_too_large(self):
        """Test rejection of correlation > 1.0."""
        with pytest.raises(ValidationError):
            RiskConfigSchema(max_correlation=1.5)
    
    def test_invalid_position_timeout(self):
        """Test rejection of zero timeout."""
        with pytest.raises(ValidationError):
            RiskConfigSchema(position_timeout_minutes=0)
    
    def test_loss_greater_than_heat(self):
        """Test rejection when loss_per_trade >= portfolio_heat."""
        with pytest.raises(ValidationError):
            RiskConfigSchema(
                max_loss_per_trade=0.5,
                max_portfolio_heat=0.3
            )


class TestStrategyConfigSchema:
    """Test strategy configuration validation."""
    
    def test_default_strategy_config(self):
        """Test default strategy configuration."""
        config = StrategyConfigSchema()
        
        assert config.min_spread_bps == 5.0
        assert config.max_spread_bps == 50.0
        assert config.fast_sma_period == 20
        assert config.slow_sma_period == 50
        assert config.entry_threshold_std == 2.0
        assert config.exit_threshold_std == 1.0
    
    def test_custom_strategy_config(self):
        """Test custom strategy configuration."""
        config = StrategyConfigSchema(
            min_spread_bps=10.0,
            max_spread_bps=100.0,
            fast_sma_period=30,
            slow_sma_period=60
        )
        
        assert config.min_spread_bps == 10.0
        assert config.max_spread_bps == 100.0
        assert config.fast_sma_period == 30
        assert config.slow_sma_period == 60
    
    def test_invalid_spread_zero(self):
        """Test rejection of zero spread."""
        with pytest.raises(ValidationError):
            StrategyConfigSchema(min_spread_bps=0.0)
    
    def test_invalid_spread_reversal(self):
        """Test rejection when min >= max spread."""
        with pytest.raises(ValidationError):
            StrategyConfigSchema(
                min_spread_bps=50.0,
                max_spread_bps=30.0
            )
    
    def test_invalid_sma_periods_equal(self):
        """Test rejection when fast_sma == slow_sma."""
        with pytest.raises(ValidationError):
            StrategyConfigSchema(
                fast_sma_period=50,
                slow_sma_period=50
            )
    
    def test_invalid_sma_periods_reversed(self):
        """Test rejection when fast_sma > slow_sma."""
        with pytest.raises(ValidationError):
            StrategyConfigSchema(
                fast_sma_period=60,
                slow_sma_period=30
            )
    
    def test_invalid_sma_zero(self):
        """Test rejection of zero SMA period."""
        with pytest.raises(ValidationError):
            StrategyConfigSchema(fast_sma_period=0)
    
    def test_invalid_sma_too_large(self):
        """Test rejection of SMA period > 500."""
        with pytest.raises(ValidationError):
            StrategyConfigSchema(fast_sma_period=600)
    
    def test_invalid_position_qty_zero(self):
        """Test rejection of zero position quantity."""
        with pytest.raises(ValidationError):
            StrategyConfigSchema(position_qty_base=0.0)
    
    def test_invalid_threshold_zero(self):
        """Test rejection of zero threshold."""
        with pytest.raises(ValidationError):
            StrategyConfigSchema(entry_threshold_std=0.0)
    
    def test_invalid_threshold_reversed(self):
        """Test rejection when entry <= exit threshold."""
        with pytest.raises(ValidationError):
            StrategyConfigSchema(
                entry_threshold_std=1.0,
                exit_threshold_std=2.0
            )
    
    def test_invalid_profit_target_zero(self):
        """Test rejection of zero profit target."""
        with pytest.raises(ValidationError):
            StrategyConfigSchema(take_profit_pct=0.0)
    
    def test_invalid_stop_loss_greater_than_profit(self):
        """Test rejection when stop_loss >= take_profit."""
        with pytest.raises(ValidationError):
            StrategyConfigSchema(
                stop_loss_pct=2.5,
                take_profit_pct=2.0
            )


class TestExecutionConfigSchema:
    """Test execution configuration validation."""
    
    def test_default_execution_config(self):
        """Test default execution configuration."""
        config = ExecutionConfigSchema()
        
        assert config.mode == ExecutionMode.PAPER
        assert config.order_type == OrderType.LIMIT
        assert config.limit_order_timeout_seconds == 30
        assert config.max_order_retries == 3
        assert config.retry_delay_seconds == 1.0
    
    def test_custom_execution_config(self):
        """Test custom execution configuration."""
        config = ExecutionConfigSchema(
            mode=ExecutionMode.LIVE,
            order_type=OrderType.MARKET,
            limit_order_timeout_seconds=60
        )
        
        assert config.mode == ExecutionMode.LIVE
        assert config.order_type == OrderType.MARKET
        assert config.limit_order_timeout_seconds == 60
    
    def test_invalid_timeout_zero(self):
        """Test rejection of zero timeout."""
        with pytest.raises(ValidationError):
            ExecutionConfigSchema(limit_order_timeout_seconds=0)
    
    def test_invalid_retries_zero(self):
        """Test rejection of zero retries."""
        with pytest.raises(ValidationError):
            ExecutionConfigSchema(max_order_retries=0)
    
    def test_invalid_retry_delay_zero(self):
        """Test rejection of zero retry delay."""
        with pytest.raises(ValidationError):
            ExecutionConfigSchema(retry_delay_seconds=0.0)
    
    def test_invalid_cancel_timeout_zero(self):
        """Test rejection of zero cancel timeout."""
        with pytest.raises(ValidationError):
            ExecutionConfigSchema(cancel_timeout_seconds=0)


class TestDataSourceConfigSchema:
    """Test data source configuration validation."""
    
    def test_default_data_source_config(self):
        """Test default data source configuration."""
        config = DataSourceConfigSchema()
        
        assert config.feed_type == "rest"
        assert config.ohlcv_interval_minutes == 5
        assert config.max_lookback_candles == 500
        assert config.buffer_size == 1000
        assert config.price_feed_timeout_seconds == 30
    
    def test_custom_data_source_config(self):
        """Test custom data source configuration."""
        config = DataSourceConfigSchema(
            feed_type="websocket",
            ohlcv_interval_minutes=15,
            max_lookback_candles=1000
        )
        
        assert config.feed_type == "websocket"
        assert config.ohlcv_interval_minutes == 15
        assert config.max_lookback_candles == 1000
    
    def test_invalid_interval_zero(self):
        """Test rejection of zero interval."""
        with pytest.raises(ValidationError):
            DataSourceConfigSchema(ohlcv_interval_minutes=0)
    
    def test_invalid_lookback_zero(self):
        """Test rejection of zero lookback."""
        with pytest.raises(ValidationError):
            DataSourceConfigSchema(max_lookback_candles=0)
    
    def test_invalid_lookback_too_large(self):
        """Test rejection of lookback > 10000."""
        with pytest.raises(ValidationError):
            DataSourceConfigSchema(max_lookback_candles=15000)
    
    def test_invalid_buffer_too_small(self):
        """Test rejection when buffer < max_lookback."""
        with pytest.raises(ValidationError):
            DataSourceConfigSchema(
                max_lookback_candles=1000,
                buffer_size=500
            )
    
    def test_invalid_feed_type(self):
        """Test rejection of invalid feed type."""
        with pytest.raises(ValidationError):
            DataSourceConfigSchema(feed_type="invalid")  # type: ignore
    
    def test_invalid_timeout_zero(self):
        """Test rejection of zero timeout."""
        with pytest.raises(ValidationError):
            DataSourceConfigSchema(price_feed_timeout_seconds=0)


class TestAlerterConfigSchema:
    """Test alerter configuration validation."""
    
    def test_default_alerter_config(self):
        """Test default alerter configuration."""
        config = AlerterConfigSchema()
        
        assert config.alert_on_position_opened is True
        assert config.alert_on_position_closed is True
        assert config.alert_on_strategy_error is True
        assert config.alert_deduplication_seconds == 60
        assert config.max_alerts_per_minute == 60
    
    def test_custom_alerter_config(self):
        """Test custom alerter configuration."""
        config = AlerterConfigSchema(
            alert_on_position_opened=False,
            alert_deduplication_seconds=120,
            max_alerts_per_minute=30
        )
        
        assert config.alert_on_position_opened is False
        assert config.alert_deduplication_seconds == 120
        assert config.max_alerts_per_minute == 30
    
    def test_invalid_deduplication_negative(self):
        """Test rejection of negative deduplication time."""
        with pytest.raises(ValidationError):
            AlerterConfigSchema(alert_deduplication_seconds=-1)
    
    def test_invalid_rate_limit_zero(self):
        """Test rejection of zero rate limit."""
        with pytest.raises(ValidationError):
            AlerterConfigSchema(max_alerts_per_minute=0)


class TestBacktestConfigSchema:
    """Test backtest configuration validation."""
    
    def test_valid_backtest_config(self):
        """Test valid backtest configuration."""
        config = BacktestConfigSchema(
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_equity=10000.0
        )
        
        assert config.start_date == "2024-01-01"
        assert config.end_date == "2024-12-31"
        assert config.initial_equity == 10000.0
        assert config.slippage_pct == 0.05
        assert config.commission_pct == 0.1
    
    def test_invalid_equity_zero(self):
        """Test rejection of zero equity."""
        with pytest.raises(ValidationError):
            BacktestConfigSchema(
                start_date="2024-01-01",
                end_date="2024-12-31",
                initial_equity=0.0
            )
    
    def test_invalid_slippage_negative(self):
        """Test rejection of negative slippage."""
        with pytest.raises(ValidationError):
            BacktestConfigSchema(
                start_date="2024-01-01",
                end_date="2024-12-31",
                slippage_pct=-0.1
            )
    
    def test_invalid_slippage_too_large(self):
        """Test rejection of slippage > 10%."""
        with pytest.raises(ValidationError):
            BacktestConfigSchema(
                start_date="2024-01-01",
                end_date="2024-12-31",
                slippage_pct=15.0
            )
    
    def test_invalid_commission_too_large(self):
        """Test rejection of commission > 10%."""
        with pytest.raises(ValidationError):
            BacktestConfigSchema(
                start_date="2024-01-01",
                end_date="2024-12-31",
                commission_pct=15.0
            )
    
    def test_invalid_high_total_costs(self):
        """Test warning for high total costs."""
        with pytest.raises(ValidationError):
            BacktestConfigSchema(
                start_date="2024-01-01",
                end_date="2024-12-31",
                slippage_pct=3.0,
                commission_pct=3.0
            )


class TestFullConfigSchema:
    """Test complete system configuration validation."""
    
    def test_default_full_config(self):
        """Test default full configuration."""
        config = FullConfigSchema()
        
        assert config.risk.max_position_size == 0.1
        assert config.strategy.min_spread_bps == 5.0
        assert config.execution.mode == ExecutionMode.PAPER
        assert config.data_source.feed_type == "rest"
        assert config.backtest is None
    
    def test_paper_trading_config(self):
        """Test paper trading configuration."""
        config_dict = {
            "execution": {
                "mode": "paper"
            }
        }
        config = FullConfigSchema(**config_dict)
        
        assert config.execution.mode == ExecutionMode.PAPER
    
    def test_live_trading_requires_strict_limits(self):
        """Test that live mode requires strict risk limits."""
        config_dict = {
            "execution": {
                "mode": "live"
            },
            "risk": {
                "max_position_size": 0.3  # Too high for live
            }
        }
        
        with pytest.raises(ValidationError):
            FullConfigSchema(**config_dict)
    
    def test_live_trading_valid_limits(self):
        """Test live mode with valid limits."""
        config_dict = {
            "execution": {
                "mode": "live"
            },
            "risk": {
                "max_position_size": 0.15,
                "max_portfolio_heat": 0.2
            }
        }
        
        config = FullConfigSchema(**config_dict)
        assert config.execution.mode == ExecutionMode.LIVE
    
    def test_backtest_mode_requires_config(self):
        """Test that backtest mode requires backtest configuration."""
        config_dict = {
            "execution": {
                "mode": "backtest"
            }
            # Missing backtest config
        }
        
        with pytest.raises(ValidationError):
            FullConfigSchema(**config_dict)
    
    def test_backtest_mode_with_config(self):
        """Test backtest mode with configuration."""
        config_dict = {
            "execution": {
                "mode": "backtest"
            },
            "backtest": {
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "initial_equity": 10000.0
            }
        }
        
        config = FullConfigSchema(**config_dict)
        assert config.execution.mode == ExecutionMode.BACKTEST
        assert config.backtest is not None
        assert config.backtest.initial_equity == 10000.0


class TestConfigValidationFunction:
    """Test the config file validation function."""
    
    def test_validate_valid_config(self):
        """Test validation of valid configuration."""
        config_dict = {
            "execution": {"mode": "paper"},
            "risk": {"max_position_size": 0.1}
        }
        
        config = validate_config_file(config_dict)
        assert config.execution.mode == ExecutionMode.PAPER
    
    def test_validate_invalid_config(self):
        """Test validation of invalid configuration."""
        config_dict = {
            "risk": {"max_position_size": 1.5}  # Invalid
        }
        
        with pytest.raises(ValidationError):
            validate_config_file(config_dict)
    
    def test_validate_live_mode_config(self):
        """Test validation of live mode configuration."""
        config_dict = {
            "execution": {"mode": "live"},
            "risk": {
                "max_position_size": 0.15,
                "max_portfolio_heat": 0.2
            }
        }
        
        config = validate_config_file(config_dict)
        assert config.execution.mode == ExecutionMode.LIVE


class TestConfigAssignmentValidation:
    """Test that validation works with field assignment."""
    
    def test_risk_assignment_validation(self):
        """Test risk config validates on assignment."""
        config = RiskConfigSchema()
        
        # Valid assignment
        config.max_position_size = 0.2
        assert config.max_position_size == 0.2
        
        # Invalid assignment
        with pytest.raises(ValidationError):
            config.max_position_size = 1.5
    
    def test_strategy_assignment_validation(self):
        """Test strategy config validates on assignment."""
        config = StrategyConfigSchema()
        
        # Valid assignment
        config.min_spread_bps = 10.0
        assert config.min_spread_bps == 10.0
        
        # Invalid assignment
        with pytest.raises(ValidationError):
            config.min_spread_bps = 0.0


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
