"""
BacktestEngine wrapper - maintains API compatibility with Python version.
Falls back to pure Python if C++ extension is not available.
"""

import logging
from typing import Dict, List, Callable, Tuple, Any, Optional

logger = logging.getLogger(__name__)

# Try to import C++ extension
try:
    from edgecore.backtest_engine_cpp import BacktestEngine as _BacktestEngineCpp
    CPP_AVAILABLE = True
    logger.info("C++ BacktestEngine extension loaded successfully")
except ImportError as e:
    CPP_AVAILABLE = False
    logger.debug(f"C++ BacktestEngine not available: {e}")
    _BacktestEngineCpp = None


class BacktestEngineWrapper:
    """
    Wrapper around C++ BacktestEngine that maintains backward compatibility.
    Automatically selects C++ or Python implementation.
    """
    
    def __init__(self, initial_equity: float = 100000.0):
        self.initial_equity = initial_equity
        
        if CPP_AVAILABLE:
            self._engine = _BacktestEngineCpp(initial_equity)
            self.use_cpp = True
            logger.debug("Using C++ BacktestEngine")
        else:
            self._engine = None
            self.use_cpp = False
            logger.debug("C++ BacktestEngine not available, will use fallback")
    
    def run(
        self,
        prices: List[List[float]],
        symbols: List[str],
        strategy_callback: Callable,
        risk_callback: Callable,
        lookback: int = 20
    ) -> Dict[str, Any]:
        """
        Run backtest with given data and callbacks.
        
        Args:
            prices: List of price vectors (one per day)
            symbols: List of symbol names
            strategy_callback: Python function to generate signals
            risk_callback: Python function to validate trades
            lookback: Historical data window
            
        Returns:
            Dictionary with equity, daily_returns, positions
        """
        
        if self.use_cpp and CPP_AVAILABLE:
            try:
                return self._engine.run(
                    prices,
                    symbols,
                    strategy_callback,
                    risk_callback,
                    lookback
                )
            except Exception as e:
                logger.error(f"C++ BacktestEngine failed: {e}, falling back to Python")
                self.use_cpp = False
        
        # Fallback or initial Python implementation
        return self._run_python(prices, symbols, strategy_callback, risk_callback)
    
    def _run_python(
        self,
        prices: List[List[float]],
        symbols: List[str],
        strategy_callback: Callable,
        risk_callback: Callable
    ) -> Dict[str, Any]:
        """Pure Python fallback implementation."""
        
        equity = self.initial_equity
        positions = {}
        daily_returns = []
        
        old_equity = equity
        
        for day, price_vector in enumerate(prices):
            try:
                # Generate signals
                signals = strategy_callback(price_vector, day)
                
                # Process signals
                for signal in signals:
                    try:
                        can_trade = risk_callback(
                            signal.get('symbol'),
                            signal.get('size') * signal.get('side', 1),
                            signal.get('price'),
                            equity
                        )
                        
                        if can_trade:
                            symbol = signal.get('symbol')
                            side = signal.get('side', 1)
                            size = signal.get('size')
                            price = signal.get('price')
                            
                            if side > 0:  # BUY
                                cost = size * price
                                if cost <= equity:
                                    positions[symbol] = {
                                        'shares': size,
                                        'entry_price': price
                                    }
                                    equity -= cost
                            elif side < 0:  # SELL
                                if symbol in positions:
                                    equity += size * price
                                    del positions[symbol]
                    except Exception as e:
                        logger.debug(f"Risk check failed: {e}")
                
                # Update equity based on current prices
                for symbol, position in positions.items():
                    try:
                        symbol_idx = symbols.index(symbol)
                        current_price = price_vector[symbol_idx]
                        pnl = (current_price - position['entry_price']) * position['shares']
                        equity += pnl
                        position['entry_price'] = current_price
                    except (ValueError, IndexError):
                        pass
                
                # Calculate daily return
                daily_pnl = equity - old_equity
                daily_return = daily_pnl / old_equity if old_equity > 0 else 0.0
                daily_returns.append(daily_return)
                
                old_equity = equity
                
            except Exception as e:
                logger.debug(f"Error on day {day}: {e}")
                daily_returns.append(0.0)
        
        return {
            'equity': equity,
            'daily_returns': daily_returns,
            'positions': positions
        }
    
    def get_equity(self) -> float:
        """Get current equity."""
        if self.use_cpp and CPP_AVAILABLE:
            return self._engine.get_equity()
        return self.initial_equity
    
    def get_daily_returns(self) -> List[float]:
        """Get daily returns."""
        if self.use_cpp and CPP_AVAILABLE:
            return self._engine.get_daily_returns()
        return []


# Compatibility alias
BacktestEngine = BacktestEngineWrapper
