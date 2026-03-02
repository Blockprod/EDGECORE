import ccxt
import os
from typing import Dict, Optional
from dotenv import load_dotenv
from structlog import get_logger
from execution.base import BaseExecutionEngine, Order, OrderSide, OrderStatus
from config.settings import get_settings
from common.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpen
from common.errors import BrokerError, InsufficientBalanceError, BrokerConnectionError, ErrorCategory

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

class CCXTExecutionEngine(BaseExecutionEngine):
    """
    CCXT-based execution for crypto exchanges (Binance, etc.).
    
    Features:
    - Credentials loaded from environment (EXCHANGE_API_KEY, EXCHANGE_API_SECRET)
    - Order tracking via local order_map cache
    - Retry logic handled by circuit_breaker and retry modules
    """
    
    def __init__(self):
        self.config = get_settings().execution
        
        # Load API credentials from environment
        api_key = os.getenv('EXCHANGE_API_KEY')
        api_secret = os.getenv('EXCHANGE_API_SECRET')
        
        if not api_key or not api_secret:
            raise ValueError(
                "EXCHANGE_API_KEY and EXCHANGE_API_SECRET must be set in .env file. "
                "See .env.example for reference."
            )
        
        # Initialize exchange
        exchange_class = getattr(ccxt, self.config.exchange)
        self.exchange = exchange_class({
            'enableRateLimit': True,
            'sandbox': self.config.use_sandbox,
            'apiKey': api_key,
            'secret': api_secret,
        })
        
        self.order_map: Dict[str, Order] = {}  # Local order cache
        
        # PHASE 2 FEATURE 2: Circuit breakers for API calls
        self.submit_breaker = CircuitBreaker(
            name=f"{self.config.exchange}_submit_order",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout_seconds=60,
                success_threshold=2
            )
        )
        self.cancel_breaker = CircuitBreaker(
            name=f"{self.config.exchange}_cancel_order",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout_seconds=60,
                success_threshold=2
            )
        )
        self.balance_breaker = CircuitBreaker(
            name=f"{self.config.exchange}_get_balance",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout_seconds=60,
                success_threshold=2
            )
        )
        
        logger.info(
            "ccxt_engine_initialized",
            exchange=self.config.exchange,
            sandbox=self.config.use_sandbox,
            api_key_loaded=True,
            circuit_breakers_enabled=True
        )
    
    def submit_order(self, order: Order) -> str:
        """
        Submit order to exchange with circuit breaker protection.
        
        PHASE 2 FEATURE 2: Wraps API call with circuit breaker to prevent
        cascading failures when exchange is overloaded or down.
        """
        try:
            # Call wrapped by circuit breaker
            broker_order_id = self.submit_breaker.call(
                self._submit_order_raw,
                order
            )
            
            logger.info(
                "order_submitted",
                order_id=broker_order_id,
                symbol=order.symbol,
                quantity=order.quantity,
                price=order.limit_price
            )
            
            return broker_order_id
        
        except CircuitBreakerOpen as e:
            # Circuit is open - treat as transient (will retry)
            logger.warning(
                "circuit_breaker_open_cannot_submit",
                breaker=self.submit_breaker.name,
                error=str(e)
            )
            raise BrokerConnectionError(f"API temporarily unavailable: {str(e)}")
        
        except ccxt.InsufficientFunds as e:
            logger.error("insufficient_balance", symbol=order.symbol, error=str(e))
            raise InsufficientBalanceError(f"Insufficient balance for {order.symbol}: {str(e)}")
        
        except ccxt.NetworkError as e:
            logger.error("network_error_submit", symbol=order.symbol, error=str(e))
            raise BrokerConnectionError(f"Network error: {str(e)}")
        
        except ccxt.ExchangeError as e:
            logger.error("exchange_error_submit", symbol=order.symbol, error=str(e))
            raise BrokerError(f"Exchange error: {str(e)}", ErrorCategory.RETRYABLE)
        
        except Exception as e:
            logger.error("order_submission_failed", symbol=order.symbol, error=str(e))
            raise BrokerError(f"Unknown error submitting order: {str(e)}", ErrorCategory.RETRYABLE)
    
    def _submit_order_raw(self, order: Order) -> str:
        """
        Raw CCXT submit_order call (wrapped by circuit breaker).
        
        This is called by submit_breaker.call() which handles
        tracking failures and opening the circuit if needed.
        """
        side = 'buy' if order.side == OrderSide.BUY else 'sell'
        
        response = self.exchange.create_limit_order(
            symbol=order.symbol,
            side=side,
            amount=order.quantity,
            price=order.limit_price
        )
        
        broker_order_id = response['id']
        self.order_map[broker_order_id] = order
        
        return broker_order_id
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel order by ID with circuit breaker protection.
        
        PHASE 2 FEATURE 2: Wraps API call with circuit breaker.
        """
        try:
            if order_id not in self.order_map:
                logger.warning("cancel_unknown_order", order_id=order_id)
                return False
            
            # Call wrapped by circuit breaker
            result = self.cancel_breaker.call(
                self._cancel_order_raw,
                order_id
            )
            
            logger.info("order_cancelled", order_id=order_id)
            return result
        
        except CircuitBreakerOpen as e:
            logger.warning(
                "circuit_breaker_open_cannot_cancel",
                breaker=self.cancel_breaker.name,
                order_id=order_id
            )
            # Don't fail hard - just log and return False
            return False
        
        except ccxt.NetworkError as e:
            logger.error("network_error_cancel", order_id=order_id, error=str(e))
            return False
        
        except Exception as e:
            logger.error("cancel_failed", order_id=order_id, error=str(e))
            return False
    
    def _cancel_order_raw(self, order_id: str) -> bool:
        """Raw CCXT cancel call (wrapped by circuit breaker)."""
        if order_id not in self.order_map:
            return False
        
        order = self.order_map[order_id]
        self.exchange.cancel_order(order_id, symbol=order.symbol)
        return True
    
    def get_order_status(self, order_id: str) -> OrderStatus:
        """Fetch order status from exchange."""
        try:
            if order_id not in self.order_map:
                return OrderStatus.REJECTED
            
            order = self.order_map[order_id]
            status = self.exchange.fetch_order(order_id, symbol=order.symbol)
            
            if status['status'] == 'closed':
                return OrderStatus.FILLED
            elif status['status'] == 'open':
                return OrderStatus.PENDING
            else:
                return OrderStatus.CANCELLED
        
        except Exception as e:
            logger.error("status_fetch_failed", order_id=order_id, error=str(e))
            return OrderStatus.REJECTED
    
    def get_positions(self) -> Dict[str, float]:
        """Get all open positions on exchange."""
        try:
            balance = self.exchange.fetch_balance()
            positions = {}
            for symbol, amount in balance.items():
                if amount['free'] > 0 or amount['used'] > 0:
                    positions[symbol] = amount['free'] + amount['used']
            logger.info("positions_fetched", count=len(positions))
            return positions
        
        except Exception as e:
            logger.error("positions_fetch_failed", error=str(e))
            return {}
    
    def get_account_balance(self) -> float:
        """
        Get total account balance (in base currency, typically USDT).
        
        PHASE 2 FEATURE 2: Wraps API call with circuit breaker protection.
        """
        try:
            # Call wrapped by circuit breaker
            balance_usdt = self.balance_breaker.call(self._get_account_balance_raw)
            
            logger.info("balance_retrieved", balance=balance_usdt)
            return balance_usdt
        
        except CircuitBreakerOpen as e:
            logger.warning(
                "circuit_breaker_open_cannot_fetch_balance",
                breaker=self.balance_breaker.name
            )
            # Return 0 instead of failing - caller handles gracefully
            return 0.0
        
        except ccxt.NetworkError as e:
            logger.error("network_error_balance", error=str(e))
            return 0.0
        
        except Exception as e:
            logger.error("balance_fetch_failed", error=str(e))
            return 0.0
    
    def _get_account_balance_raw(self) -> float:
        """Raw CCXT balance call (wrapped by circuit breaker)."""
        balance = self.exchange.fetch_balance()
        # Assumes USDT or similar stable as base
        return float(balance.get('USDT', {}).get('free', 0.0))
