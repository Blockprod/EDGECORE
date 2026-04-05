"""
Metrics and monitoring hooks for Prometheus compatibility.
"""

from dataclasses import dataclass


@dataclass
class SystemMetrics:
    """System-level trading metrics."""
    equity: float = 100000.0
    daily_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    trades_total: int = 0
    trades_today: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    risk_violations: int = 0
    
    def to_prometheus_format(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = [
            "# HELP edgecore_equity Current account equity",
            "# TYPE edgecore_equity gauge",
            f"edgecore_equity {self.equity}",
            "",
            "# HELP edgecore_daily_return Daily return percentage",
            "# TYPE edgecore_daily_return gauge",
            f"edgecore_daily_return {self.daily_return}",
            "",
            "# HELP edgecore_max_drawdown Maximum drawdown percentage",
            "# TYPE edgecore_max_drawdown gauge",
            f"edgecore_max_drawdown {self.max_drawdown}",
            "",
            "# HELP edgecore_sharpe_ratio Sharpe ratio",
            "# TYPE edgecore_sharpe_ratio gauge",
            f"edgecore_sharpe_ratio {self.sharpe_ratio}",
            "",
            "# HELP edgecore_trades_total Total trades executed",
            "# TYPE edgecore_trades_total counter",
            f"edgecore_trades_total {self.trades_total}",
            "",
            "# HELP edgecore_risk_violations Risk constraint violations",
            "# TYPE edgecore_risk_violations counter",
            f"edgecore_risk_violations {self.risk_violations}",
        ]
        return "\n".join(lines)
