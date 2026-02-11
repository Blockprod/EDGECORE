"""Paper trading execution with realistic slippage and commissions."""

from typing import Optional, Tuple
from structlog import get_logger
from execution.ccxt_engine import CCXTExecutionEngine
from execution.backtest_execution import SlippageCalculator, CommissionCalculator
from execution.base import Order, OrderStatus
from config.settings import get_settings
from common.types import SlippageModel, CommissionType

logger = get_logger(__name__)


class PaperExecutionEngine(CCXTExecutionEngine):
    """Paper trading with realistic slippage and commission simulation."""
    
    def __init__(self, 
                 slippage_model: str = "fixed_bps",
                 fixed_bps: float = 5.0,
                 commission_pct: float = 0.1):
        """
        Initialize paper execution engine.
        
        Args:
            slippage_model: "fixed_bps", "adaptive", or "volume_based"
            fixed_bps: Basis points for fixed slippage
            commission_pct: Commission percentage (0.1 = 0.1%)
        """
        super().__init__()
        
        # Convert string slippage model to enum
        slippage_model_enum = self._parse_slippage_model(slippage_model)
        
        # Slippage configuration
        self.slippage_config = {
            'model': slippage_model_enum,
            'fixed_bps': fixed_bps,
            'adaptive_multiplier': 2.0,
            'max_slippage_bps': 50.0
        }
        self.slippage_calc = SlippageCalculator(self.slippage_config)
        
        # Commission configuration
        self.commission_config = {
            'type': CommissionType.PERCENT,
            'percent': commission_pct
        }
        self.commission_calc = CommissionCalculator(self.commission_config)
        
        logger.info(
            "paper_execution_engine_initialized",
            slippage_model=slippage_model,
            fixed_bps=fixed_bps,
            commission_pct=commission_pct
        )
    
    @staticmethod
    def _parse_slippage_model(model_str: str) -> SlippageModel:
        """Convert string to SlippageModel enum."""
        mapping = {
            "fixed_bps": SlippageModel.FIXED_BPS,
            "adaptive": SlippageModel.ADAPTIVE,
            "volume_based": SlippageModel.VOLUME_BASED,
        }
        if model_str not in mapping:
            raise ValueError(f"Invalid slippage model: {model_str}. Must be one of {list(mapping.keys())}")
        return mapping[model_str]
    
    def submit_order(self, order: Order) -> str:
        """
        Submit order with realistic slippage and commission.
        
        Overrides CCXTExecutionEngine to inject slippage/commission.
        """
        try:
            # Get current market price
            market_price = self._get_market_price(order.symbol)
            market_volume = self._get_market_volume(order.symbol)
            
            # Calculate slippage
            slippage_bps, slippage_price = self.slippage_calc.calculate(
                order_price=order.limit_price or market_price,
                market_price=market_price,
                order_quantity=order.quantity,
                market_volume=market_volume or 1000000.0,
                side='buy' if order.side.value == 'buy' else 'sell'
            )
            
            # Calculate commission
            trade_value = slippage_price * order.quantity
            commission = self.commission_calc.calculate(trade_value)
            
            # Adjust execution price for commission
            # On buy: price goes UP by commission %
            # On sell: price goes DOWN by commission %
            if order.side.value == 'buy':
                final_price = slippage_price * (1 + self.commission_config['percent'] / 100)
            else:
                final_price = slippage_price * (1 - self.commission_config['percent'] / 100)
            
            # Log the realistic execution
            logger.info(
                "paper_order_submitted_with_slippage",
                symbol=order.symbol,
                side=order.side.value,
                original_price=order.limit_price or market_price,
                slippage_price=slippage_price,
                slippage_bps=slippage_bps,
                commission=commission,
                final_price=final_price,
                quantity=order.quantity
            )
            
            # Create modified order with realistic price
            modified_order = Order(
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                limit_price=final_price
            )
            
            # Submit via parent class
            return super().submit_order(modified_order)
        
        except Exception as e:
            logger.error("paper_order_submission_failed", error=str(e))
            raise
    
    def _get_market_price(self, symbol: str) -> float:
        """Get current market price for symbol."""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            logger.warning("market_price_fetch_failed", symbol=symbol, error=str(e))
            return 0.0
    
    def _get_market_volume(self, symbol: str) -> float:
        """Get 24h market volume for symbol."""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker.get('quoteVolume', 0))
        except Exception as e:
            logger.warning("market_volume_fetch_failed", symbol=symbol, error=str(e))
            return 0.0
