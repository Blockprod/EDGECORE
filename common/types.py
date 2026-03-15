"""
Type definitions for EDGECORE trading system.

Provides:
- TypedDict for complex data structures
- Type aliases for clarity
- Enum types for constants
- Protocol definitions for interfaces
"""

from typing import TypedDict, Dict, List, Any, Literal
from typing_extensions import NotRequired
from datetime import datetime
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class OrderSide(Enum):
    """Order side (buy/sell)."""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order type (market/limit)."""
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(Enum):
    """Order execution status ÔÇö aligned with execution.base.OrderStatus."""
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class ExecutionMode(Enum):
    """Trading execution mode."""
    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, blocked
    HALF_OPEN = "half_open"  # Testing recovery


class StopType(Enum):
    """Position stop types."""
    STOP_LOSS = "stop_loss"          # Absolute stop loss price
    TAKE_PROFIT = "take_profit"      # Profit target price
    TRAILING_STOP = "trailing_stop"  # Trailing stop follows price


class FillType(Enum):
    """Order fill type."""
    FULL = "full"              # Order completely filled
    PARTIAL = "partial"        # Order partially filled
    NONE = "none"              # No fill


class SlippageModel(Enum):
    """Slippage model type."""
    FIXED_BPS = "fixed_bps"           # Fixed basis points
    ADAPTIVE = "adaptive"              # Adaptive to volume
    VOLUME_BASED = "volume_based"     # Based on order volume


class CommissionType(Enum):
    """Commission calculation type."""
    PERCENT = "percent"        # Percentage of trade value
    FIXED = "fixed"            # Fixed amount per trade


class DepthMode(Enum):
    """Order book depth profile."""
    SHALLOW = "shallow"      # Thin order book, wide spreads
    MEDIUM = "medium"        # Normal liquidity
    DEEP = "deep"            # Heavy liquidity, tight spreads


class VenueType(Enum):
    """Trading venue type."""
    CME_FUTURES = "cme"               # CME futures
    NASDAQ_EQUITIES = "nasdaq"        # US equities (Nasdaq)
    NYSE_EQUITIES = "nyse"            # US equities (NYSE)
    IBKR_SMART = "smart"             # IBKR Smart Routing (default)


class TraceLevel(Enum):
    """Distributed trace verbosity."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# ============================================================================
# TYPE ALIASES
# ============================================================================

Price = float  # Market price
Quantity = float  # Position size
PnL = float  # Profit/Loss
Volatility = float  # Volatility estimate (%)
Correlation = float  # Correlation coefficient (-1 to 1)
Equity = float  # Portfolio equity
Symbol = str  # Trading pair symbol
OrderID = str  # Unique order identifier
PositionID = str  # Unique position identifier


# ============================================================================
# DATA STRUCTURE TYPEDDICTS
# ============================================================================

class OHLCVCandle(TypedDict):
    """OHLCV candlestick data."""
    open: Price
    high: Price
    low: Price
    close: Price
    volume: float
    timestamp: datetime


class SignalData(TypedDict):
    """Trading signal from strategy."""
    signal_type: Literal["entry", "exit"]
    symbol: Symbol
    z_score: float
    spread: float
    timestamp: datetime
    confidence: float  # 0-1 confidence
    metadata: NotRequired[Dict[str, Any]]


class OrderRequest(TypedDict):
    """Request to submit an order."""
    symbol: Symbol
    side: OrderSide
    quantity: Quantity
    order_type: OrderType
    price: NotRequired[Price]  # Required for limit orders
    timeout_seconds: NotRequired[float]
    metadata: NotRequired[Dict[str, Any]]


class OrderRecord(TypedDict):
    """Order execution record."""
    order_id: OrderID
    symbol: Symbol
    side: OrderSide
    quantity: Quantity
    filled_quantity: float
    order_type: OrderType
    status: OrderStatus
    filled_price: NotRequired[Price]
    submitted_at: datetime
    filled_at: NotRequired[datetime]
    metadata: NotRequired[Dict[str, Any]]


class PositionRecord(TypedDict):
    """Active trading position."""
    position_id: PositionID
    symbol: Symbol
    quantity: Quantity  # Can be negative for short
    entry_price: Price
    entry_time: datetime
    current_price: Price
    marked_price: Price
    side: Literal["long", "short"]
    unrealized_pnl: PnL
    pnl_percent: float
    metadata: NotRequired[Dict[str, Any]]


class AlertRecord(TypedDict):
    """Alert notification record."""
    alert_id: str
    severity: AlertSeverity
    category: str
    title: str
    message: str
    timestamp: datetime
    acknowledged: bool
    resolved: bool
    data: NotRequired[Dict[str, Any]]


class TradeRecord(TypedDict):
    """Completed trade record."""
    trade_id: str
    symbol: Symbol
    entry_price: Price
    exit_price: Price
    quantity: Quantity
    entry_time: datetime
    exit_time: datetime
    realized_pnl: PnL
    pnl_percent: float
    duration_seconds: float
    metadata: NotRequired[Dict[str, Any]]


class EquitySnapshot(TypedDict):
    """Portfolio equity at a point in time."""
    timestamp: datetime
    total_equity: Equity  # Cash + positions value
    cash: Equity  # Available cash
    positions_value: Equity  # Total marked position value
    unrealized_pnl: PnL
    realized_pnl: NotRequired[PnL]
    daily_pnl: NotRequired[PnL]


class RiskMetrics(TypedDict):
    """Risk assessment metrics."""
    current_equity: Equity
    available_cash: Equity
    positions_count: int
    largest_position_pct: float
    portfolio_heat: float  # Sum of position risks
    daily_loss: float
    drawdown_pct: float
    max_correlation: float


class ConnectionStatus(TypedDict):
    """API connection status."""
    connected: bool
    timestamp: datetime
    last_heartbeat: datetime
    latency_ms: float
    error: NotRequired[str]


class DataSourceConfig(TypedDict):
    """Data source configuration."""
    source_type: Literal["rest", "websocket"]
    interval_minutes: int
    lookback_hours: int
    update_frequency_seconds: NotRequired[int]
    retry_attempts: NotRequired[int]
    timeout_seconds: NotRequired[float]


# ============================================================================
# VALIDATION RESULT TYPEDDICTS
# ============================================================================

class ValidationResult(TypedDict):
    """Result of data validation."""
    is_valid: bool
    checks_passed: int
    checks_failed: int
    errors: List[str]
    warnings: List[str]


class RiskCheckResult(TypedDict):
    """Result of risk check."""
    allowed: bool
    reason: NotRequired[str]
    risk_metrics: NotRequired[RiskMetrics]


class CointegrationResult(TypedDict):
    """Cointegration test result."""
    is_cointegrated: bool
    p_value: float
    test_statistic: float
    critical_values: Dict[str, float]
    beta: NotRequired[float]


# ============================================================================
# CIRCUIT BREAKER TYPEDDICTS  
# ============================================================================

class CircuitBreakerConfig(TypedDict):
    """Circuit breaker configuration."""
    failure_threshold: int
    timeout_seconds: float
    success_threshold: int
    name: NotRequired[str]


class CircuitBreakerMetrics(TypedDict):
    """Circuit breaker state metrics."""
    state: CircuitBreakerState
    failure_count: int
    success_count: int
    total_calls: int
    consecutive_failures: int
    consecutive_successes: int
    last_state_change: datetime
    last_call_time: NotRequired[datetime]


# ============================================================================
# POSITION STOPS TYPEDDICTS
# ============================================================================

class PositionStopConfig(TypedDict):
    """Configuration for position stop levels."""
    stop_loss_price: NotRequired[Price]      # Absolute stop loss level
    take_profit_price: NotRequired[Price]    # Profit target level
    trailing_stop_percent: NotRequired[float]  # Trailing stop as percent
    trailing_stop_distance: NotRequired[Price]  # Trailing stop as absolute distance
    hard_exit_time_minutes: NotRequired[int]  # Maximum hold time in minutes
    breakeven_trigger_percent: NotRequired[float]  # Move to breakeven at this profit %


class PositionStopStatus(TypedDict):
    """Current stop status for a position."""
    position_id: PositionID
    symbol: Symbol
    active_stops: List[str]  # List of active stop types
    stop_loss_price: NotRequired[Price]
    take_profit_price: NotRequired[Price]
    trailing_high: NotRequired[Price]  # Highest price for trailing stop
    distance_from_stop: Price  # Current distance to nearest stop
    time_to_hard_exit: NotRequired[int]  # Seconds remaining (if hard exit set)
    last_updated: datetime


class PositionWithStops(TypedDict):
    """Position with stop information."""
    position_id: PositionID
    symbol: Symbol
    quantity: Quantity
    entry_price: Price
    entry_time: datetime
    current_price: Price
    side: Literal["long", "short"]
    unrealized_pnl: PnL
    pnl_percent: float
    stops: PositionStopConfig
    stop_status: PositionStopStatus


# ============================================================================
# BACKTEST REALISM TYPEDDICTS
# ============================================================================

class SlippageConfig(TypedDict):
    """Slippage configuration for realistic backtesting."""
    model: SlippageModel
    fixed_bps: NotRequired[float]         # Fixed slippage in basis points
    adaptive_multiplier: NotRequired[float]  # Multiplier for volume-based slippage
    max_slippage_bps: NotRequired[float]  # Maximum slippage cap


class CommissionConfig(TypedDict):
    """Commission configuration for realistic backtesting."""
    type: CommissionType
    percent: NotRequired[float]           # Commission as % of trade value
    fixed_amount: NotRequired[float]      # Fixed commission per trade
    min_commission: NotRequired[float]    # Minimum commission
    max_commission: NotRequired[float]    # Maximum commission


class ExecutionResult(TypedDict):
    """Result of order execution with realistic factors."""
    order_id: OrderID
    symbol: Symbol
    side: Literal["buy", "sell"]               # Buy or sell side
    submitted_price: Price              # Price at submission time
    executed_price: Price               # Actual price after slippage
    requested_quantity: Quantity        # Amount requested
    filled_quantity: Quantity           # Amount actually filled
    fill_type: FillType                # Full or partial
    slippage_bps: float                # Slippage in basis points
    slippage_amount: Price             # Slippage in currency
    commission: float                  # Commission paid
    net_proceeds: float                # After slippage and commission
    execution_time: datetime           # When execution occurred
    reason: NotRequired[str]           # Additional details


class FillSimulation(TypedDict):
    """Fill simulation parameters for backtest."""
    base_volume_bps: float             # Base order volume as % of market volume
    market_volume: float               # Available market volume
    max_fill_pct: float               # Maximum fill percentage (default 10%)
    partial_fill_probability: float    # Chance of partial fill (0-1)


class BacktestMetrics(TypedDict):
    """Backtest execution metrics with realistic factors."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_slippage: float             # Total slippage costs
    total_commissions: float          # Total commissions paid
    gross_pnl: float                  # PnL before costs
    net_pnl: float                    # PnL after slippage and commission
    slippage_impact_pct: float        # Slippage as % of gross PnL
    commission_impact_pct: float      # Commission as % of gross PnL
    sharpe_ratio: NotRequired[float]
    max_drawdown_pct: NotRequired[float]
    win_rate_pct: NotRequired[float]
    avg_trade_pnl: NotRequired[float]


class BacktestConfig(TypedDict):
    """Backtest configuration with realism settings."""
    start_date: str
    end_date: str
    initial_equity: Equity
    slippage_config: NotRequired[SlippageConfig]
    commission_config: NotRequired[CommissionConfig]
    fill_simulation: NotRequired[FillSimulation]


# ============================================================================
# ORDER BOOK TYPEDDICTS
# ============================================================================

class OrderBookLevel(TypedDict):
    """Single price level in order book."""
    price: Price
    quantity: Quantity
    order_count: int  # Number of orders at this level


class OrderBook(TypedDict):
    """Market order book snapshot."""
    symbol: Symbol
    timestamp: datetime
    bid_levels: List[OrderBookLevel]  # Best bid first (sorted descending)
    ask_levels: List[OrderBookLevel]  # Best ask first (sorted ascending)
    bid_volume: float  # Total bid volume
    ask_volume: float  # Total ask volume
    bid_ask_spread_bps: float  # Spread in basis points


class OrderBookUpdate(TypedDict):
    """Order book update event."""
    symbol: Symbol
    timestamp: datetime
    update_type: Literal["trade", "add", "cancel", "modify"]
    side: Literal["bid", "ask"]
    price: Price
    quantity: Quantity
    order_count: NotRequired[int]


class LiquidityMetrics(TypedDict):
    """Liquidity analysis for a symbol."""
    symbol: Symbol
    timestamp: datetime
    bid_ask_spread: Price  # Absolute spread
    bid_ask_spread_pct: float  # Spread as % of mid price
    mid_price: Price  # (bid + ask) / 2
    depth_at_10bps: float  # Volume within 10 bps of mid
    depth_at_20bps: float  # Volume within 20 bps of mid
    estimated_impact_100bps: float  # Estimated impact of 100 BPS order


class BookSimulationConfig(TypedDict):
    """Configuration for order book simulation."""
    symbols: List[Symbol]
    bid_ask_spread_bps: float  # Fixed spread or base spread
    depth_mode: Literal["shallow", "medium", "deep"]  # Book depth profile
    volatility_factor: float  # How spread adjusts with volatility (0.5-2.0)
    realism_level: Literal["academic", "realistic", "tight"]


# ============================================================================
# MONTE CARLO TYPEDDICTS
# ============================================================================

class MonteCarloConfig(TypedDict):
    """Configuration for Monte Carlo order book simulation."""
    num_simulations: int  # Number of paths to simulate
    time_steps: int  # Steps per simulation
    price_drift_bps: float  # Expected drift in BPS per step
    volatility_annual_pct: float  # Annual volatility for diffusion
    jump_probability: float  # Probability of jump per step (0-1)
    jump_size_std: float  # Standard deviation of jump size
    mean_reversion_speed: NotRequired[float]  # Mean reversion parameter
    volume_scaling: float  # How to scale simulated volumes


class MonteCarloResult(TypedDict):
    """Results from Monte Carlo simulation."""
    symbol: Symbol
    num_simulations: int
    price_paths: List[List[float]]  # [simulation][step]
    volume_paths: List[List[float]]  # [simulation][step]
    percentile_5: float  # 5th percentile price path
    percentile_25: float  # 25th percentile
    percentile_50: float  # Median
    percentile_75: float  # 75th percentile
    percentile_95: float  # 95th percentile
    std_dev: float  # Standard deviation of final prices
    mean_final_price: float  # Expected final price


# ============================================================================
# VENUE-SPECIFIC TYPEDDICTS
# ============================================================================

class VenueCharacteristics(TypedDict):
    """Market characteristics for specific venue."""
    venue: VenueType
    name: str
    base_spread_bps: float  # Typical spread
    min_spread_bps: float  # Minimum spread
    max_spread_bps: float  # Maximum spread
    typical_volume: float  # Daily volume
    fee_bps: float  # Trading fee in basis points
    taker_fee_bps: NotRequired[float]  # Separate taker fee if applicable
    maker_fee_bps: NotRequired[float]  # Separate maker fee if applicable
    opening_hours: NotRequired[str]  # Market hours (e.g., "09:30-16:00 EST")
    is_24_7: bool  # 24/7 trading available


class VenueModel(TypedDict):
    """Venue-specific market model."""
    venue: VenueType
    characteristics: VenueCharacteristics
    spread_volatility_multiplier: float  # How spread responds to vol
    micro_impact_bps_per_million: float  # Impact per $1M traded
    macro_impact_factor: float  # Impact from broader market moves
    liquidity_decay_hours: float  # Hours to liquidify full day volume


# ============================================================================
# DISTRIBUTED TRACING TYPEDDICTS
# ============================================================================

class TraceContext(TypedDict):
    """Distributed trace context."""
    trace_id: str  # Unique trace identifier
    span_id: str  # Current span identifier
    parent_span_id: NotRequired[str]  # Parent span for nesting
    timestamp: datetime
    source: str  # Component name


class TraceSpan(TypedDict):
    """Individual trace span."""
    trace_id: str
    span_id: str
    parent_span_id: NotRequired[str]
    name: str  # Operation name
    start_time: datetime
    end_time: NotRequired[datetime]
    duration_ms: NotRequired[float]
    status: Literal["UNSET", "OK", "ERROR"]
    attributes: Dict[str, Any]  # Key-value metadata
    events: NotRequired[List[Dict[str, Any]]]  # Log events
    level: TraceLevel


class TraceMetrics(TypedDict):
    """Aggregated trace metrics."""
    service_name: str
    total_spans: int
    total_errors: int
    error_rate_pct: float
    avg_span_duration_ms: float
    p95_span_duration_ms: float
    p99_span_duration_ms: float
    most_common_operations: List[tuple[str, int]]  # (op_name, count)


# ============================================================================
# ML IMPACT PREDICTION TYPEDDICTS
# ============================================================================

class ImpactFeatures(TypedDict):
    """Features for ML impact prediction."""
    order_size_pct: float  # Order size as % of volume
    volatility_annual_pct: float  # Market volatility
    bid_ask_spread_bps: float  # Current bid-ask spread
    market_volume_24h: float  # 24h trading volume
    time_of_day_factor: float  # 0-1 based on time of day
    day_of_week: int  # 0-6 (Monday-Sunday)
    recent_volatility_spike: bool  # Whether vol recently spiked
    order_urgency: Literal["passive", "normal", "aggressive"]  # Order type


class MLImpactPrediction(TypedDict):
    """ML-based market impact prediction."""
    features: ImpactFeatures
    predicted_impact_bps: float  # Mean prediction
    confidence_interval_lower: float  # 95% CI lower bound
    confidence_interval_upper: float  # 95% CI upper bound
    model_version: str  # Which model was used
    timestamp: datetime
    feature_importance: Dict[str, float]  # SHAP or similar


class MLModelMetrics(TypedDict):
    """Performance metrics for ML impact model."""
    model_version: str
    training_samples: int
    r_squared: float  # R┬▓ on test set
    mean_absolute_error_bps: float  # MAE on test set
    mean_squared_error: float  # MSE
    is_production: bool
    last_retrained: datetime


# ============================================================================
# REAL-TIME LATENCY TYPEDDICTS
# ============================================================================

class LatencyMeasurement(TypedDict):
    """Single latency measurement."""
    operation: str  # e.g., "order_submission", "data_fetch"
    component_source: str  # Which component initiated
    component_dest: str  # Which component received
    latency_ms: float
    timestamp: datetime
    success: bool


class LatencyMetrics(TypedDict):
    """Aggregated latency metrics for operation."""
    operation: str
    total_measurements: int
    min_ms: float
    max_ms: float
    mean_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    p99_9_ms: float
    stdev_ms: float
    success_rate_pct: float


class LatencyBudget(TypedDict):
    """Latency budget for SLA."""
    operation: str
    p95_target_ms: float
    p99_target_ms: float
    alert_threshold_ms: float
    description: NotRequired[str]


# ============================================================================
# RETRY TYPEDDICTS
# ============================================================================

class RetryStats(TypedDict):
    """Retry attempt statistics."""
    function_name: str
    total_calls: int
    successful_calls: int
    failed_calls: int
    total_retries: int
    average_retries: float
    success_rate: float


# ============================================================================
# SECRETS TYPEDDICTS
# ============================================================================

class SecretMetadata(TypedDict):
    """Secret metadata tracking."""
    created_at: datetime
    last_accessed_at: datetime
    access_count: int
    rotation_interval_days: NotRequired[int]
    last_rotated_at: NotRequired[datetime]
    requires_rotation: bool


# ============================================================================
# CONFIGURATION TYPEDDICTS
# ============================================================================

class RiskConfig(TypedDict):
    """Risk management configuration."""
    max_position_size: float
    max_portfolio_heat: float
    max_loss_per_trade: float
    max_drawdown_pct: float
    max_correlation: float
    position_timeout_hours: float
    min_equity: float
    max_concurrent_positions: NotRequired[int]
    max_consecutive_losses: NotRequired[int]


class StrategyConfig(TypedDict):
    """Strategy configuration."""
    min_spread_bps: float
    max_spread_bps: float
    fast_sma_periods: int
    slow_sma_periods: int
    entry_z_score: float
    exit_z_score: float
    profit_target_bps: float
    stop_loss_bps: float


class ExecutionConfig(TypedDict):
    """Execution configuration."""
    mode: ExecutionMode
    order_type: OrderType
    timeout_seconds: float
    max_retries: int


class DataSourceConfigDict(TypedDict):
    """Data source configuration."""
    feed_type: Literal["rest", "websocket"]
    ohlcv_interval_minutes: int
    lookback_hours: int
    buffer_size: NotRequired[int]


class AlerterConfig(TypedDict):
    """Alerter configuration."""
    alert_modes: List[str]
    deduplication_window_minutes: int
    rate_limit_per_hour: int


class BacktestConfigSimple(TypedDict):
    """Backtest configuration (simple, flat fields)."""
    start_date: str
    end_date: str
    initial_equity: Equity
    slippage_pct: float
    commission_pct: float


# ============================================================================
# RESPONSE TYPEDDICTS
# ============================================================================

class APIResponse(TypedDict):
    """API response structure."""
    success: bool
    data: NotRequired[Dict[str, Any]]
    error: NotRequired[str]
    timestamp: datetime
    latency_ms: NotRequired[float]


class HealthCheckResponse(TypedDict):
    """System health check response."""
    healthy: bool
    timestamp: datetime
    components: Dict[str, bool]
    metrics: NotRequired[Dict[str, Any]]


# ============================================================================
# EVENT TYPEDDICTS
# ============================================================================

class TradeEvent(TypedDict):
    """Trade event for monitoring."""
    event_type: str
    symbol: Symbol
    quantity: Quantity
    price: Price
    timestamp: datetime
    pnl: NotRequired[PnL]
    metadata: NotRequired[Dict[str, Any]]


class RiskAlertEvent(TypedDict):
    """Risk alert event."""
    event_type: str
    severity: AlertSeverity
    description: str
    metrics: RiskMetrics
    timestamp: datetime


class ConnectionEvent(TypedDict):
    """Connection status event."""
    event_type: Literal["connected", "disconnected", "reconnecting"]
    source: str
    timestamp: datetime
    details: NotRequired[Dict[str, Any]]


if __name__ == "__main__":
    print("Ô£à Common types module loaded")
    print(f"- Order types: {[t.name for t in OrderType]}")
    print(f"- Execution modes: {[m.name for m in ExecutionMode]}")
    print(f"- Circuit breaker states: {[s.name for s in CircuitBreakerState]}")
