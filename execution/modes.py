"""
Unified execution engine with pluggable execution modes.

Abstracts execution differences (paper/live/backtest) through:
- ExecutionContext: Shared state for all modes
- ExecutionMode abstract base: Interface for mode-specific logic
- Mode-specific implementations: Paper, Live, Backtest

This eliminates code duplication and makes adding new modes easy.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from structlog import get_logger
import threading

logger = get_logger(__name__)


class ModeType(str, Enum):
    """Execution mode types."""
    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"


class OrderStatus(str, Enum):
    """Order lifecycle states — delegates to execution.base.OrderStatus values."""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


@dataclass
class Order:
    """Order data structure."""
    order_id: str
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    price: Optional[float]  # None for market orders
    order_type: str  # "market" or "limit"
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_price: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_complete(self) -> bool:
        """Check if order is complete (filled or cancelled)."""
        return self.status in [
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.FAILED
        ]
    
    @property
    def fill_ratio(self) -> float:
        """Return fill ratio (0.0 to 1.0)."""
        if self.quantity == 0:
            return 1.0
        return self.filled_quantity / self.quantity


@dataclass
class Position:
    """Position data structure."""
    symbol: str
    quantity: float  # Positive for long, negative for short
    entry_price: float
    entry_time: datetime
    current_price: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def side(self) -> str:
        """Return position side."""
        return "long" if self.quantity > 0 else "short"
    
    @property
    def pnl(self) -> float:
        """Return unrealized P&L."""
        if self.quantity > 0:
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * abs(self.quantity)
    
    @property
    def pnl_pct(self) -> float:
        """Return unrealized P&L %."""
        if self.entry_price == 0:
            return 0.0
        return (self.pnl / (abs(self.quantity) * self.entry_price)) * 100


@dataclass
class ExecutionContext:
    """Shared execution state across all modes.
    
    Maintains:
    - Orders placed and their status
    - Current positions
    - Account balance/equity
    - Transactions
    """
    
    mode: ModeType
    orders: Dict[str, Order] = field(default_factory=dict)
    positions: Dict[str, Position] = field(default_factory=dict)
    market_prices: Dict[str, float] = field(default_factory=dict)
    equity: float = 10000.0
    cash: float = 10000.0
    lock: threading.RLock = field(default_factory=threading.RLock)
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position by symbol."""
        with self.lock:
            return self.positions.get(symbol)
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        with self.lock:
            return self.orders.get(order_id)
    
    def add_position(self, position: Position) -> None:
        """Add or update position."""
        with self.lock:
            self.positions[position.symbol] = position
    
    def remove_position(self, symbol: str) -> Optional[Position]:
        """Remove and return position."""
        with self.lock:
            return self.positions.pop(symbol, None)
    
    def add_order(self, order: Order) -> None:
        """Add order to tracking."""
        with self.lock:
            self.orders[order.order_id] = order
    
    def update_order_status(self, order_id: str, status: OrderStatus) -> None:
        """Update order status."""
        with self.lock:
            if order_id in self.orders:
                self.orders[order_id].status = status
                self.orders[order_id].updated_at = datetime.utcnow()
    
    def update_market_price(self, symbol: str, price: float) -> None:
        """Update market price for symbol."""
        with self.lock:
            self.market_prices[symbol] = price
            # Update position current price
            if symbol in self.positions:
                self.positions[symbol].current_price = price
    
    def get_total_position_value(self) -> float:
        """Calculate total position market value."""
        with self.lock:
            total = 0.0
            for position in self.positions.values():
                total += abs(position.quantity) * position.current_price
            return total
    
    def get_total_pnl(self) -> float:
        """Calculate total unrealized P&L."""
        with self.lock:
            total = 0.0
            for position in self.positions.values():
                total += position.pnl
            return total


class ExecutionMode(ABC):
    """Abstract base class for execution modes.
    
    Subclasses implement mode-specific behavior:
    - Paper: Simulated fills at current price
    - Live: Real API calls to broker
    - Backtest: Historical data fills
    """
    
    def __init__(self, context: ExecutionContext):
        """
        Initialize execution mode.
        
        Args:
            context: Shared execution context
        """
        self.context = context
        self.logger = logger.bind(mode=context.mode.value)
    
    @abstractmethod
    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "market",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Submit order and return order ID.
        
        Args:
            symbol: Trading symbol (e.g., "AAPL")
            side: "buy" or "sell"
            quantity: Order size
            price: Limit price (None for market)
            order_type: "market" or "limit"
            metadata: Additional order metadata
        
        Returns:
            Order ID
        
        Raises:
            ExecutionError: On submission failure
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel order.
        
        Args:
            order_id: ID of order to cancel
        
        Returns:
            True if cancelled, False if already complete
        """
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderStatus:
        """
        Get current order status.
        
        Args:
            order_id: Order ID to check
        
        Returns:
            OrderStatus enum value
        """
        pass
    
    @abstractmethod
    def open_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Open position (after order fills).
        
        Args:
            symbol: Trading pair
            quantity: Position size
            entry_price: Entry price
            metadata: Position metadata
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def close_position(
        self,
        symbol: str,
        exit_price: float
    ) -> Tuple[bool, Optional[float]]:
        """
        Close position.
        
        Args:
            symbol: Trading pair
            exit_price: Exit price
        
        Returns:
            (success, realized_pnl) tuple
        """
        pass
    
    @abstractmethod
    def get_account_equity(self) -> float:
        """Get current account equity."""
        pass


class PaperTradingMode(ExecutionMode):
    """Paper trading mode - simulated execution at current prices."""
    
    def __init__(self, context: ExecutionContext):
        """Initialize paper trading mode."""
        super().__init__(context)
        self.order_counter = 0
        self.fill_delay_ms = 100  # Simulate network delay
    
    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "market",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Submit order in paper trading mode."""
        # Generate order ID
        self.order_counter += 1
        order_id = f"PAPER-{self.order_counter}"
        
        # Get current market price
        current_price = self.context.market_prices.get(symbol)
        if current_price is None:
            raise ValueError(f"No price available for {symbol}")
        
        # Create order
        fill_price = price if order_type == "limit" else current_price
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            metadata=metadata or {}
        )
        
        self.context.add_order(order)
        self.logger.info(
            "paper_order_submitted",
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type
        )
        
        # Simulate immediate fill for market orders
        if order_type == "market":
            self.context.update_order_status(order_id, OrderStatus.FILLED)
            self.context.get_order(order_id).filled_quantity = quantity
            self.context.get_order(order_id).filled_price = fill_price
            self.logger.info(
                "paper_order_filled",
                order_id=order_id,
                filled_qty=quantity,
                fill_price=fill_price
            )
        
        return order_id
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order in paper trading mode."""
        order = self.context.get_order(order_id)
        if not order:
            return False
        
        if order.is_complete:
            return False  # Can't cancel complete orders
        
        self.context.update_order_status(order_id, OrderStatus.CANCELLED)
        self.logger.info("paper_order_cancelled", order_id=order_id)
        return True
    
    def get_order_status(self, order_id: str) -> OrderStatus:
        """Get order status."""
        order = self.context.get_order(order_id)
        return order.status if order else OrderStatus.FAILED
    
    def open_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Open position in paper trading."""
        position = Position(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            entry_time=datetime.utcnow(),
            current_price=entry_price,
            metadata=metadata or {}
        )
        
        self.context.add_position(position)
        self.context.cash -= quantity * entry_price  # Deduct cash
        self.logger.info(
            "paper_position_opened",
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price
        )
        return True
    
    def close_position(
        self,
        symbol: str,
        exit_price: float
    ) -> Tuple[bool, Optional[float]]:
        """Close position in paper trading."""
        position = self.context.remove_position(symbol)
        if not position:
            return False, None
        
        # Update position's current price to exit price before calculating PnL
        position.current_price = exit_price
        pnl = position.pnl
        
        self.context.cash += abs(position.quantity) * exit_price
        
        self.logger.info(
            "paper_position_closed",
            symbol=symbol,
            quantity=position.quantity,
            exit_price=exit_price,
            pnl=pnl
        )
        return True, pnl
    
    def get_account_equity(self) -> float:
        """Get account equity (cash + positions)."""
        position_value = self.context.get_total_position_value()
        return self.context.cash + position_value


class LiveTradingMode(ExecutionMode):
    """Live trading mode - real API execution with safety guards."""
    
    def __init__(self, context: ExecutionContext, api_client=None, initial_equity: float = 100000.0):
        """Initialize live trading mode."""
        super().__init__(context)
        self.api_client = api_client
        self.initial_equity = initial_equity
        self.current_equity = initial_equity
        
        # Hard stop thresholds
        self.max_daily_loss_pct_absolute = 0.02  # 2% max daily loss
        self.max_equity_drawdown_pct_absolute = 0.15  # 15% max drawdown
        self.emergency_close_price_threshold = 0.10  # 10% move -> check sanity
        
        # Tracking
        self.max_equity_reached = initial_equity
        self.api_error_count = 0
        self.max_api_errors = 10  # Kill-switch after 10 API errors

    
    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "market",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Submit order to live broker with safety checks."""
        # Check if we can continue trading
        if not self.can_continue_trading():
            raise RuntimeError("Hard stop triggered - cannot submit new orders")
        
        if not self.api_client:
            raise RuntimeError("API client not configured for live trading")
        
        # Submit to broker
        try:
            order_id = self.api_client.submit_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type
            )
            
            self.api_error_count = 0  # Reset error count on success
            
            # Track locally
            order = Order(
                order_id=order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type,
                status=OrderStatus.SUBMITTED,
                metadata=metadata or {}
            )
            self.context.add_order(order)
            
            self.logger.info(
                "live_order_submitted",
                order_id=order_id,
                symbol=symbol,
                quantity=quantity,
                order_type=order_type
            )
            return order_id
        except Exception as e:
            self.api_error_count += 1
            self.logger.error(
                "live_order_submission_failed",
                error=str(e),
                error_count=self.api_error_count
            )
            
            if self.api_error_count > self.max_api_errors:
                self.logger.critical("MAX_API_ERRORS_EXCEEDED", stopping_trading=True)
                raise RuntimeError(f"Max API errors exceeded ({self.max_api_errors})")
            
            raise
    
    def can_continue_trading(self) -> bool:
        """Check if trading should continue or if hard stops triggered."""
        # Check 1: Daily loss limit
        current_loss_pct = (self.initial_equity - self.current_equity) / self.initial_equity
        
        if current_loss_pct > self.max_daily_loss_pct_absolute:
            self.logger.critical(
                "HARD_STOP_DAILY_LOSS",
                loss_pct=current_loss_pct,
                limit_pct=self.max_daily_loss_pct_absolute
            )
            return False
        
        # Check 2: Max drawdown
        drawdown_pct = (self.max_equity_reached - self.current_equity) / self.max_equity_reached
        
        if drawdown_pct > self.max_equity_drawdown_pct_absolute:
            self.logger.critical(
                "HARD_STOP_MAX_DRAWDOWN",
                drawdown_pct=drawdown_pct,
                limit_pct=self.max_equity_drawdown_pct_absolute
            )
            return False
        
        # Check 3: API error threshold
        if self.api_error_count > self.max_api_errors:
            self.logger.critical(
                "HARD_STOP_API_ERRORS",
                error_count=self.api_error_count,
                limit=self.max_api_errors
            )
            return False
        
        return True
    
    def set_current_equity(self, equity: float) -> None:
        """Update current equity and check for drawdown."""
        self.current_equity = equity
        
        # Track max equity for drawdown calculation
        if equity > self.max_equity_reached:
            self.max_equity_reached = equity

    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel live order."""
        if not self.api_client:
            return False
        
        order = self.context.get_order(order_id)
        if not order or order.is_complete:
            return False
        
        try:
            self.api_client.cancel_order(order_id)
            self.context.update_order_status(order_id, OrderStatus.CANCELLED)
            self.logger.info("live_order_cancelled", order_id=order_id)
            return True
        except Exception as e:
            self.logger.error("live_order_cancel_failed", order_id=order_id, error=str(e))
            return False
    
    def get_order_status(self, order_id: str) -> OrderStatus:
        """Get live order status."""
        if not self.api_client:
            return OrderStatus.FAILED
        
        try:
            status = self.api_client.get_order_status(order_id)
            self.context.update_order_status(order_id, status)
            return status
        except Exception as e:
            self.logger.error("get_order_status_failed", order_id=order_id, error=str(e))
            return OrderStatus.FAILED
    
    def open_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Open live position."""
        if not self.api_client:
            return False
        
        try:
            position = Position(
                symbol=symbol,
                quantity=quantity,
                entry_price=entry_price,
                entry_time=datetime.utcnow(),
                current_price=entry_price,
                metadata=metadata or {}
            )
            self.context.add_position(position)
            self.logger.info(
                "live_position_opened",
                symbol=symbol,
                quantity=quantity,
                entry_price=entry_price
            )
            return True
        except Exception as e:
            self.logger.error("live_position_open_failed", symbol=symbol, error=str(e))
            return False
    
    def close_position(
        self,
        symbol: str,
        exit_price: float
    ) -> Tuple[bool, Optional[float]]:
        """Close live position."""
        position = self.context.remove_position(symbol)
        if not position:
            return False, None
        
        # Update position's current price to exit price before calculating PnL
        position.current_price = exit_price
        pnl = position.pnl
        
        self.logger.info(
            "live_position_closed",
            symbol=symbol,
            quantity=position.quantity,
            exit_price=exit_price,
            pnl=pnl
        )
        return True, pnl
    
    def get_account_equity(self) -> float:
        """Get live account equity from broker."""
        if not self.api_client:
            return 0.0
        
        try:
            equity = self.api_client.get_equity()
            self.context.equity = equity
            return equity
        except Exception as e:
            self.logger.error("get_account_equity_failed", error=str(e))
            return self.context.equity


class BacktestMode(ExecutionMode):
    """Backtest mode - historical data fills."""
    
    def __init__(
        self,
        context: ExecutionContext,
        historical_data: Dict[str, List[Dict[str, float]]] = None
    ):
        """
        Initialize backtest mode.
        
        Args:
            context: Execution context
            historical_data: Historical candle data by symbol
        """
        super().__init__(context)
        self.historical_data = historical_data or {}
        self.order_counter = 0
        self.slippage_pct = 0.05  # 0.05% slippage
        self.commission_pct = 0.1  # 0.1% commission
    
    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "market",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Submit backtest order (instant fill)."""
        self.order_counter += 1
        order_id = f"BT-{self.order_counter}"
        
        # Calculate fill price with slippage
        current_price = self.context.market_prices.get(symbol)
        if current_price is None:
            raise ValueError(f"No price available for {symbol}")
        
        fill_price = current_price
        if side == "buy":
            fill_price *= (1 + self.slippage_pct / 100)
        else:
            fill_price *= (1 - self.slippage_pct / 100)
        
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            status=OrderStatus.FILLED,
            filled_quantity=quantity,
            filled_price=fill_price,
            metadata=metadata or {}
        )
        
        self.context.add_order(order)
        self.logger.info(
            "backtest_order_filled",
            order_id=order_id,
            symbol=symbol,
            quantity=quantity,
            fill_price=fill_price
        )
        
        return order_id
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel backtest order."""
        order = self.context.get_order(order_id)
        if not order or order.is_complete:
            return False
        
        self.context.update_order_status(order_id, OrderStatus.CANCELLED)
        return True
    
    def get_order_status(self, order_id: str) -> OrderStatus:
        """Get backtest order status."""
        order = self.context.get_order(order_id)
        return order.status if order else OrderStatus.FAILED
    
    def open_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Open backtest position."""
        position = Position(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            entry_time=datetime.utcnow(),
            current_price=entry_price,
            metadata=metadata or {}
        )
        
        self.context.add_position(position)
        commission = quantity * entry_price * self.commission_pct / 100
        self.context.cash -= (quantity * entry_price + commission)
        
        self.logger.info(
            "backtest_position_opened",
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            commission=commission
        )
        return True
    
    def close_position(
        self,
        symbol: str,
        exit_price: float
    ) -> Tuple[bool, Optional[float]]:
        """Close backtest position."""
        position = self.context.remove_position(symbol)
        if not position:
            return False, None
        
        # Update position's current price to exit price before calculating PnL
        position.current_price = exit_price
        
        commission = abs(position.quantity) * exit_price * self.commission_pct / 100
        realized_pnl = position.pnl
        
        self.context.cash += (abs(position.quantity) * exit_price - commission)
        
        self.logger.info(
            "backtest_position_closed",
            symbol=symbol,
            quantity=position.quantity,
            exit_price=exit_price,
            pnl_gross=realized_pnl,
            commission=commission
        )
        
        return True, realized_pnl - commission
    
    def get_account_equity(self) -> float:
        """Get backtest equity."""
        position_value = self.context.get_total_position_value()
        return self.context.cash + position_value


class ExecutionEngine:
    """Unified execution engine using pluggable mode."""
    
    def __init__(self, mode: ModeType, api_client=None):
        """
        Initialize execution engine.
        
        Args:
            mode: Execution mode (paper, live, backtest)
            api_client: Optional API client for live trading
        """
        self.context = ExecutionContext(mode=mode)
        
        # Create mode-specific executor
        if mode == ModeType.PAPER:
            self.executor = PaperTradingMode(self.context)
        elif mode == ModeType.LIVE:
            self.executor = LiveTradingMode(self.context, api_client)
        elif mode == ModeType.BACKTEST:
            self.executor = BacktestMode(self.context)
        else:
            raise ValueError(f"Unknown mode: {mode}")
        
        self.logger = logger.bind(mode=mode.value)
    
    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "market"
    ) -> str:
        """Submit order through current mode."""
        return self.executor.submit_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type
        )
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order through current mode."""
        return self.executor.cancel_order(order_id)
    
    def open_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float
    ) -> bool:
        """Open position through current mode."""
        return self.executor.open_position(symbol, quantity, entry_price)
    
    def close_position(
        self,
        symbol: str,
        exit_price: float
    ) -> Tuple[bool, Optional[float]]:
        """Close position through current mode."""
        return self.executor.close_position(symbol, exit_price)
    
    def get_equity(self) -> float:
        """Get account equity."""
        return self.executor.get_account_equity()
    
    def get_positions(self) -> Dict[str, Position]:
        """Get all open positions."""
        with self.context.lock:
            return dict(self.context.positions)
    
    def update_prices(self, prices: Dict[str, float]) -> None:
        """Update market prices."""
        for symbol, price in prices.items():
            self.context.update_market_price(symbol, price)
