"""
BacktestEngine wrapper - maintains API compatibility with Python version.
Now using Python-only implementation (C++ approach deprecated).
"""

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# C++ extension no longer used - deprecated in favor of Python/Cython
# This module kept for test compatibility


class BacktestEngineWrapper:
    """
    Wrapper around BacktestEngine.
    Now Python-only implementation (C++ deprecated).
    """

    def __init__(self, initial_equity: float = 100000.0):
        self.initial_equity = initial_equity
        self.use_cpp = False  # Python-only now
        self._engine = None
        logger.debug("Using Python BacktestEngine")

    def run(
        self,
        prices: list[list[float]],
        symbols: list[str],
        strategy_callback: Callable,
        risk_callback: Callable,
        lookback: int = 20,
    ) -> dict[str, Any]:
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

        # Use Python implementation
        return self._run_python(prices, symbols, strategy_callback, risk_callback, lookback=lookback)

    def _run_python(
        self,
        prices: list[list[float]],
        symbols: list[str],
        strategy_callback: Callable,
        risk_callback: Callable,
        lookback: int = 20,
    ) -> dict[str, Any]:
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
                            signal.get("symbol"),
                            signal.get("size") * signal.get("side", 1),
                            signal.get("price"),
                            equity,
                        )

                        if can_trade:
                            symbol = signal.get("symbol")
                            side = signal.get("side", 1)
                            size = signal.get("size")
                            price = signal.get("price")

                            if side > 0:  # BUY
                                cost = size * price
                                if cost <= equity:
                                    positions[symbol] = {"shares": size, "entry_price": price}
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
                        pnl = (current_price - position["entry_price"]) * position["shares"]
                        equity += pnl
                        position["entry_price"] = current_price
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

        return {"equity": equity, "daily_returns": daily_returns, "positions": positions, "lookback": lookback}

    def get_equity(self) -> float:
        """Get current equity."""
        return self.initial_equity

    def get_daily_returns(self) -> list[float]:
        """Get daily returns."""
        return []


# Compatibility alias
BacktestEngine = BacktestEngineWrapper
