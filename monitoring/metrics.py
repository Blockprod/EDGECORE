"""
Metrics and monitoring hooks for Prometheus compatibility.

P4-01: Uses prometheus_client SDK (Gauge, Counter, Histogram) instead of
manually building Prometheus text format.  Each metric is registered once
as a module-level singleton so concurrent scrapers share the same registry.
"""

from dataclasses import dataclass

import prometheus_client as prom
from structlog import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level Prometheus metric singletons (P4-01)
# ---------------------------------------------------------------------------

_EQUITY = prom.Gauge("edgecore_equity", "Current account equity")
_DAILY_RETURN = prom.Gauge("edgecore_daily_return", "Daily return percentage")
_MAX_DRAWDOWN = prom.Gauge("edgecore_max_drawdown", "Maximum drawdown percentage")
_SHARPE_RATIO = prom.Gauge("edgecore_sharpe_ratio", "Sharpe ratio")
_TRADES_TOTAL = prom.Counter("edgecore_trades_total", "Total trades executed")
_RISK_VIOLATIONS = prom.Counter("edgecore_risk_violations", "Risk constraint violations")

# P4-02: Order fill latency histogram (buckets: <0.1s, <0.5s, <1s, <2s, <5s, <10s, <30s, <60s)
_ORDER_FILL_LATENCY = prom.Histogram(
    "edgecore_order_fill_latency_seconds",
    "Order-to-fill latency in seconds",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# IBKR API round-trip latency histogram
_IBKR_API_RTT = prom.Histogram(
    "edgecore_ibkr_api_rtt_seconds",
    "IBKR API request round-trip time in seconds",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

# Execution slippage gauge
_EXECUTION_SLIPPAGE_BPS = prom.Gauge(
    "edgecore_execution_slippage_bps",
    "Most recent order execution slippage in basis points",
)


@dataclass
class SystemMetrics:
    """System-level trading metrics.

    Updating a field automatically pushes the new value to the corresponding
    Prometheus SDK metric so scrapers always see live data.
    """

    equity: float = 100000.0
    daily_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    trades_total: int = 0
    trades_today: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    risk_violations: int = 0

    # ------------------------------------------------------------------
    # Prometheus push helpers
    # ------------------------------------------------------------------

    def push(self) -> None:
        """Push all current field values to their Prometheus SDK gauges/counters."""
        _EQUITY.set(self.equity)
        _DAILY_RETURN.set(self.daily_return)
        _MAX_DRAWDOWN.set(self.max_drawdown)
        _SHARPE_RATIO.set(self.sharpe_ratio)

    def to_prometheus_format(self) -> str:
        """Return Prometheus text format via the SDK registry.

        Pushes current field values first so the scrape reflects the latest
        state of this instance, then generates the full registry output.
        """
        self.push()
        return prom.generate_latest(prom.REGISTRY).decode("utf-8")
