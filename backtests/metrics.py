import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class BacktestMetrics:
    """Backtest performance metrics."""
    start_date: str
    end_date: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_duration: Optional[float] = None
    calmar_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    
    @classmethod
    def from_returns(cls, returns: pd.Series, trades: List[float], start_date: str, end_date: str) -> 'BacktestMetrics':
        """
        Calculate metrics from returns and trades.
        
        Args:
            returns: Series of daily returns (0.01 = 1%)
            trades: List of trade P&L values
            start_date, end_date: Period
        
        Returns:
            BacktestMetrics with all fields filled
        """
        # Total return
        total_return = (1 + returns).prod() - 1 if len(returns) > 0 else 0.0
        
        # Sharpe ratio (252 trading days/year)
        if len(returns) > 1:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0.0
        else:
            sharpe_ratio = 0.0
        
        # Max drawdown
        if len(returns) > 0:
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min()
        else:
            max_drawdown = 0.0
        
        # Win rate
        winning_trades = sum(1 for pnl in trades if pnl > 0)
        win_rate = winning_trades / len(trades) if len(trades) > 0 else 0.0
        
        # Profit factor
        gross_profit = sum(pnl for pnl in trades if pnl > 0)
        gross_loss = abs(sum(pnl for pnl in trades if pnl < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        
        # Sortino ratio (only downside volatility)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0 and downside_returns.std() > 0:
            sortino_ratio = (returns.mean() / downside_returns.std()) * np.sqrt(252)
        else:
            sortino_ratio = 0.0
        
        # Calmar ratio (return / max drawdown)
        calmar_ratio = total_return / abs(max_drawdown) if max_drawdown < 0 else 0.0
        
        return cls(
            start_date=start_date,
            end_date=end_date,
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=len(trades),
            avg_trade_duration=None,
            calmar_ratio=calmar_ratio,
            sortino_ratio=sortino_ratio
        )
    
    def summary(self) -> str:
        """Return formatted metrics summary."""
        return f"""
========================================
         BACKTEST METRICS SUMMARY         
========================================
Period: {self.start_date} to {self.end_date}
Total Return:       {self.total_return:>7.2%}
Sharpe Ratio:       {self.sharpe_ratio:>7.2f}
Sortino Ratio:      {self.sortino_ratio:>7.2f}
Max Drawdown:       {self.max_drawdown:>7.2%}
Calmar Ratio:       {self.calmar_ratio:>7.2f}

Win Rate:           {self.win_rate:>7.2%}
Profit Factor:      {self.profit_factor:>7.2f}
Total Trades:       {self.total_trades:>7d}
========================================
        """
