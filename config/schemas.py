"""
Configuration validation with Pydantic v2.

Schemas for:
- Risk engine configuration
- Strategy trading parameters
- Execution mode settings
- Data source configuration

All configs validated on instantiation with clear error messages.
"""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExecutionMode(StrEnum):
    """Available execution modes."""

    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"


class OrderType(StrEnum):
    """Available order types."""

    MARKET = "market"
    LIMIT = "limit"


class RiskConfigSchema(BaseModel):
    """Risk engine configuration schema.

    Validates:
    - Max position sizes (0 < size <= portfolio)
    - Max loss limits (0 <= loss < portfolio)
    - Correlation checks (0 <= corr <= 1)
    - Drawdown limits (0 <= dd < 100)
    """

    max_position_size: float = Field(
        default=0.1, gt=0, le=1.0, description="Max % of portfolio per position (0 < size <= 1.0)"
    )

    max_portfolio_heat: float = Field(
        default=0.2, ge=0, le=1.0, description="Max % of portfolio at risk (0 <= heat <= 1.0)"
    )

    max_loss_per_trade: float = Field(default=0.02, ge=0, lt=1.0, description="Max loss % per trade (0 <= loss < 1.0)")

    max_drawdown_pct: float = Field(default=10.0, ge=0, lt=100, description="Max portfolio drawdown % (0 <= dd < 100)")

    max_correlation: float = Field(
        default=0.7, ge=0, le=1.0, description="Max correlation between pairs (0 <= corr <= 1.0)"
    )

    position_timeout_minutes: int = Field(default=120, gt=0, description="Max position duration in minutes")

    min_equity_usd: float = Field(default=1000.0, gt=0, description="Minimum equity to continue trading")

    @field_validator("max_position_size")
    @classmethod
    def validate_position_size(cls, v):
        if v <= 0 or v > 1.0:
            raise ValueError("position_size must be 0 < size <= 1.0")
        return v

    @model_validator(mode="after")
    def validate_relationships(self):
        """Validate field relationships."""
        if self.max_position_size > 1.0:
            raise ValueError("position_size cannot exceed 1.0")
        if self.max_loss_per_trade >= self.max_portfolio_heat:
            raise ValueError("loss_per_trade must be < portfolio_heat")
        return self

    model_config = ConfigDict(validate_assignment=True)


class StrategyConfigSchema(BaseModel):
    """Strategy trading configuration schema.

    Validates:
    - Spread parameters (min > 0, max > min)
    - SMA periods (greater than 0, reasonable ranges)
    - Position sizing (positive)
    - Timeout periods (positive)
    """

    # Spread validation
    min_spread_bps: float = Field(default=5.0, gt=0, description="Minimum spread in basis points")

    max_spread_bps: float = Field(default=50.0, gt=0, description="Maximum spread in basis points")

    # SMA periods for mean reversion detection
    fast_sma_period: int = Field(default=20, gt=0, le=500, description="Fast SMA period (candles)")

    slow_sma_period: int = Field(default=50, gt=0, le=500, description="Slow SMA period (candles)")

    # Position sizing
    position_qty_base: float = Field(default=1.0, gt=0, description="Base position quantity")

    # Entry/exit parameters
    entry_threshold_std: float = Field(default=2.0, gt=0, description="Entry threshold in standard deviations")

    exit_threshold_std: float = Field(default=1.0, gt=0, description="Exit threshold in standard deviations")

    # Stat-arb z-score entry/exit (validated in _validate_config)
    entry_z_score: float = Field(
        default=2.0, ge=1.5, le=4.0, description="Z-score threshold for stat-arb entry (1.5-4.0)"
    )

    exit_z_score: float = Field(default=0.5, ge=0.0, le=2.0, description="Z-score threshold for stat-arb exit (0-2.0)")

    entry_z_min_spread: float = Field(
        default=0.50, ge=0.0, le=5.0, description="Min absolute spread ($) for entry ÔÇö filters micro-deviations"
    )

    # Stat-arb z-score entry/exit (validated in _validate_config)
    entry_z_score: float = Field(
        default=2.0,
        ge=1.5,
        le=4.0,
        description="Z-score threshold for stat-arb entry (1.5-4.0)"
    )
    
    exit_z_score: float = Field(
        default=0.5,
        ge=0.0,
        le=2.0,
        description="Z-score threshold for stat-arb exit (0-2.0)"
    )

    entry_z_min_spread: float = Field(
        default=0.50,
        ge=0.0,
        le=5.0,
        description="Min absolute spread ($) for entry — filters micro-deviations"
    )

    short_sizing_multiplier: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Sizing multiplier for shorts in TRENDING/NEUTRAL bull regime (0=block, 1=full)",
    )

    regime_directional_filter: bool = Field(
        default=False, description="When True, regime filter only blocks shorts; longs allowed in TRENDING"
    )

    trend_long_sizing: float = Field(
        default=0.75,
        ge=0.1,
        le=1.0,
        description="Sizing multiplier for longs in TRENDING regime (when directional filter ON)",
    )

    trend_favorable_sizing: float = Field(
        default=0.80,
        ge=0.1,
        le=1.0,
        description="v30: Sizing for the favorable side in trending regimes (BULL->longs, BEAR->shorts)",
    )

    neutral_sizing: float = Field(
        default=0.65, ge=0.1, le=1.0, description="v30: Sizing for both sides in NEUTRAL regime"
    )

    take_profit_pct: float = Field(default=2.0, gt=0, le=100, description="Take profit target %")

    stop_loss_pct: float = Field(default=1.0, gt=0, le=100, description="Stop loss %")

    # Timeouts
    max_position_minutes: int = Field(default=120, gt=0, description="Max position hold time")

    @model_validator(mode="after")
    def validate_spread_range(self):
        """Validate spread relationships."""
        if self.min_spread_bps >= self.max_spread_bps:
            raise ValueError("min_spread must be < max_spread")
        return self

    @model_validator(mode="after")
    def validate_sma_periods(self):
        """Validate SMA period relationships."""
        if self.fast_sma_period >= self.slow_sma_period:
            raise ValueError("fast_sma must be < slow_sma")
        return self

    @model_validator(mode="after")
    def validate_thresholds(self):
        """Validate entry/exit thresholds."""
        if self.take_profit_pct <= self.stop_loss_pct:
            raise ValueError("take_profit must be > stop_loss")
        if self.entry_threshold_std <= self.exit_threshold_std:
            raise ValueError("entry_threshold must be > exit_threshold")
        return self

    @model_validator(mode="after")
    def validate_z_score_thresholds(self):
        """Validate stat-arb z-score entry > exit."""
        if self.entry_z_score <= self.exit_z_score:
            raise ValueError("entry_z_score must be > exit_z_score")
        return self

    model_config = ConfigDict(validate_assignment=True)


class ExecutionConfigSchema(BaseModel):
    """Execution engine configuration schema.

    Validates:
    - Mode selection (paper/live/backtest)
    - Timeouts (positive)
    - Retry counts (positive)
    - Order types
    """

    mode: ExecutionMode = Field(default=ExecutionMode.PAPER, description="Execution mode")

    order_type: OrderType = Field(default=OrderType.LIMIT, description="Default order type")

    limit_order_timeout_seconds: int = Field(default=30, gt=0, description="Timeout for limit orders")

    max_order_retries: int = Field(default=3, ge=1, description="Max retries for order submission")

    retry_delay_seconds: float = Field(default=1.0, gt=0, description="Delay between retries")

    cancel_timeout_seconds: int = Field(default=10, gt=0, description="Timeout for cancel operations")

    @model_validator(mode="after")
    def validate_timeouts(self):
        """Validate timeout ordering."""
        if self.cancel_timeout_seconds > self.limit_order_timeout_seconds:
            # Warning: may be intentional, but should be suspect
            pass
        return self

    model_config = ConfigDict(validate_assignment=True)


class DataSourceConfigSchema(BaseModel):
    """Data source configuration schema.

    Validates:
    - OHLCV update frequency (positive)
    - Data retention period (positive)
    - Buffer sizes (positive)
    - Feed types
    """

    feed_type: Literal["rest", "websocket"] = Field(default="rest", description="Data feed type")

    ohlcv_interval_minutes: int = Field(default=5, gt=0, description="OHLCV candle interval")

    max_lookback_candles: int = Field(default=500, gt=0, le=10000, description="Max historical candles to maintain")

    buffer_size: int = Field(default=1000, gt=0, description="Data buffer size")

    price_feed_timeout_seconds: int = Field(default=30, gt=0, description="Timeout for price feed updates")

    heartbeat_interval_seconds: int = Field(default=5, gt=0, description="Heartbeat check interval")

    @model_validator(mode="after")
    def validate_buffers(self):
        """Validate buffer configuration."""
        if self.buffer_size < self.max_lookback_candles:
            raise ValueError("buffer_size should be >= max_lookback_candles")
        return self

    model_config = ConfigDict(validate_assignment=True)


class AlerterConfigSchema(BaseModel):
    """Alerter configuration schema.

    Validates:
    - Alert levels
    - Deduplication times (positive)
    - Rate limits (positive)
    """

    alert_on_position_opened: bool = Field(default=True, description="Alert when position opened")

    alert_on_position_closed: bool = Field(default=True, description="Alert when position closed")

    alert_on_strategy_error: bool = Field(default=True, description="Alert on strategy errors")

    alert_deduplication_seconds: int = Field(default=60, ge=0, description="Seconds to deduplicate alerts")

    max_alerts_per_minute: int = Field(default=60, gt=0, description="Rate limit for alerts")

    model_config = ConfigDict(validate_assignment=True)


class BacktestConfigSchema(BaseModel):
    """Backtest configuration schema.

    Validates:
    - Date ranges (start < end)
    - Initial equity (positive)
    - Slippage/commission percentages
    """

    start_date: str = Field(description="Backtest start date (YYYY-MM-DD)")

    end_date: str = Field(description="Backtest end date (YYYY-MM-DD)")

    initial_equity: float = Field(default=10000.0, gt=0, description="Initial backtest equity")

    slippage_pct: float = Field(default=0.05, ge=0, le=10, description="Slippage as % of price")

    commission_pct: float = Field(default=0.1, ge=0, le=10, description="Commission as % of trade value")

    @model_validator(mode="after")
    def validate_costs(self):
        """Validate cost percentages."""
        if self.slippage_pct + self.commission_pct > 5.0:
            raise ValueError("Total costs (slippage + commission) seem too high")
        return self

    model_config = ConfigDict(validate_assignment=True)


class FullConfigSchema(BaseModel):
    """Complete system configuration.

    Combines all sub-schemas with validation of cross-section constraints.
    """

    risk: RiskConfigSchema = Field(default_factory=RiskConfigSchema, description="Risk engine configuration")

    strategy: StrategyConfigSchema = Field(default_factory=StrategyConfigSchema, description="Strategy configuration")

    execution: ExecutionConfigSchema = Field(
        default_factory=ExecutionConfigSchema, description="Execution engine configuration"
    )

    data_source: DataSourceConfigSchema = Field(
        default_factory=DataSourceConfigSchema, description="Data source configuration"
    )

    alerter: AlerterConfigSchema = Field(default_factory=AlerterConfigSchema, description="Alerter configuration")

    backtest: BacktestConfigSchema | None = Field(default=None, description="Backtest configuration (optional)")

    @model_validator(mode="after")
    def validate_consistency(self):
        """Validate cross-section consistency."""
        # If backtest mode and no backtest config, warn
        if self.execution.mode == ExecutionMode.BACKTEST and not self.backtest:
            raise ValueError("Backtest mode requires backtest configuration")

        # If live mode, risk constraints must be tight
        if self.execution.mode == ExecutionMode.LIVE:
            if self.risk.max_position_size > 0.2:
                raise ValueError("Live mode: max position size should be <= 20%")
            if self.risk.max_portfolio_heat > 0.3:
                raise ValueError("Live mode: max portfolio heat should be <= 30%")

        return self

    model_config = ConfigDict(validate_assignment=True)


def validate_config_file(config_dict: dict[str, Any]) -> FullConfigSchema:
    """
    Validate configuration dictionary.

    Args:
        config_dict: Configuration dictionary from YAML/JSON

    Returns:
        Validated FullConfigSchema instance

    Raises:
        ValidationError: If configuration is invalid
    """
    return FullConfigSchema(**config_dict)
