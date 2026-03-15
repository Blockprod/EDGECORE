from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

# Annualisation factor  - configurable per market:
#   Equities: 252 (NYSE/NASDAQ trading days)
#   Forex:    252 (weekday sessions)
# Default is 252 for equities (target market).
TRADING_DAYS_PER_YEAR: int = 252


def set_trading_days(days: int) -> None:
    """Change the annualisation factor at runtime.
    
    Args:
        days: Trading days per year (252 for equities).
    """
    global TRADING_DAYS_PER_YEAR
    TRADING_DAYS_PER_YEAR = days


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
    var_95: Optional[float] = None            # Phase 4: Historical 95% Value-at-Risk
    cvar_95: Optional[float] = None           # Phase 4: Conditional VaR (Expected Shortfall)
    initial_capital: Optional[float] = None    # Starting capital
    final_capital: Optional[float] = None      # Ending capital
    realized_pnl: Optional[float] = None       # Total realised P&L
    note: Optional[str] = None
    daily_returns: Optional[pd.Series] = None  # Raw daily returns for aggregation
    num_symbols: Optional[int] = None  # Number of symbols in universe
    
    @classmethod
    def from_returns(
        cls,
        returns: pd.Series,
        trades: List[float],
        start_date: str,
        end_date: str,
        note: str = None,
        risk_free_annual: float = 0.0,
        num_symbols: Optional[int] = None,
    ) -> 'BacktestMetrics':
        """
        Calculate metrics from returns and trades.
        
        Args:
            returns: Series of daily returns (0.01 = 1%)
            trades: List of trade P&L values
            start_date, end_date: Period
            risk_free_annual: Annualised risk-free rate (e.g. 0.045 for 4.5%).
                              Deducted from the mean daily return before computing
                              Sharpe & Sortino so that ratios are true excess-return.
            num_symbols: Number of symbols in the universe (e.g. 100 for 100 stocks).
        
        Returns:
            BacktestMetrics with all fields filled
        """
        # Daily risk-free rate for excess-return calculation
        rf_daily = (1 + risk_free_annual) ** (1 / TRADING_DAYS_PER_YEAR) - 1

        # Total return
        total_return = (1 + returns).prod() - 1 if len(returns) > 0 else 0.0

        # Initial capital: assume 100000 if not provided elsewhere
        initial_capital = 100000.0
        # Final capital: initial * (1 + total_return)
        final_capital = initial_capital * (1 + total_return)
        # Realized PnL: sum of trades
        realized_pnl = sum(trades) if trades else 0.0

        # Sharpe ratio (annualised using configured trading days, excess return)
        # Guard: if no trades were made, Sharpe is meaningless (FP noise can inflate it)
        if not trades:
            sharpe_ratio = 0.0
        elif len(returns) > 1:
            excess = returns - rf_daily
            sharpe_ratio = (excess.mean() / excess.std()) * np.sqrt(TRADING_DAYS_PER_YEAR) if excess.std() > 0 else 0.0
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
        
        # Sortino ratio (only downside volatility, excess return)
        excess_returns = returns - rf_daily
        downside_returns = excess_returns[excess_returns < 0]
        if len(downside_returns) > 0 and downside_returns.std() > 0:
            sortino_ratio = (excess_returns.mean() / downside_returns.std()) * np.sqrt(TRADING_DAYS_PER_YEAR)
        else:
            sortino_ratio = 0.0
        
        # Calmar ratio (return / max drawdown)
        calmar_ratio = total_return / abs(max_drawdown) if max_drawdown < 0 else 0.0
        
        # Phase 4: Portfolio-level VaR and CVaR (Expected Shortfall)
        var_95 = None
        cvar_95 = None
        if len(returns) >= 20:
            var_95 = float(np.percentile(returns, 5))        # 5th percentile = 95% VaR
            tail = returns[returns <= var_95]
            cvar_95 = float(tail.mean()) if len(tail) > 0 else var_95
        
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
            sortino_ratio=sortino_ratio,
            var_95=var_95,
            cvar_95=cvar_95,
            initial_capital=initial_capital,
            final_capital=final_capital,
            realized_pnl=realized_pnl,
            note=note,
            daily_returns=returns,
            num_symbols=num_symbols,
        )
    
    def summary(self) -> str:
        """Return formatted metrics summary."""
        var_str = f"{self.var_95:.4f}" if self.var_95 is not None else "N/A"
        cvar_str = f"{self.cvar_95:.4f}" if self.cvar_95 is not None else "N/A"
        cap_init = f"{self.initial_capital:>10,.2f} EUR" if self.initial_capital is not None else "N/A"
        cap_final = f"{self.final_capital:>10,.2f} EUR" if self.final_capital is not None else "N/A"
        pnl_str = f"{self.realized_pnl:>+10,.2f} EUR" if self.realized_pnl is not None else "N/A"
        return f"""
========================================
         BACKTEST METRICS SUMMARY         
========================================
Period: {self.start_date} to {self.end_date}
Initial Capital:    {cap_init}
Final Capital:      {cap_final}
Realised PnL:       {pnl_str}
Total Return:       {self.total_return:>7.2%}
Sharpe Ratio:       {self.sharpe_ratio:>7.2f}
Sortino Ratio:      {self.sortino_ratio:>7.2f}
Max Drawdown:       {self.max_drawdown:>7.2%}
Calmar Ratio:       {self.calmar_ratio:>7.2f}
VaR (95%):          {var_str:>7s}
CVaR (95%):         {cvar_str:>7s}

Win Rate:           {self.win_rate:>7.2%}
Profit Factor:      {self.profit_factor:>7.2f}
Total Trades:       {self.total_trades:>7d}
========================================
        """""
