"""Dashboard generator for real-time system metrics and status."""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import psutil
import structlog

from execution.base import BaseExecutionEngine
from monitoring.cache import get_dashboard_cache
from risk.engine import RiskEngine

logger = structlog.get_logger(__name__)

# Global state tracking
_dashboard_start_time = datetime.now()

# Path to the shared state file written by the trading bot process
_LIVE_STATE_PATH = Path("data/dashboard_state.json")


class DashboardGenerator:
    """Generate JSON dashboard snapshots for real-time monitoring."""

    def __init__(
        self,
        risk_engine: RiskEngine | None = None,
        execution_engine: BaseExecutionEngine | None = None,
        mode: str = "paper",
        enable_cache: bool = True,
        enable_live_bridge: bool = False,
    ):
        """
        Initialize dashboard generator.

        Args:
            risk_engine: RiskEngine instance for position/equity metrics
            execution_engine: Execution engine for order metrics
            mode: Trading mode ('paper', 'live', 'backtest')
            enable_cache: Enable caching of dashboard data
            enable_live_bridge: Read live state from bot IPC file when engines are None
        """
        self.risk_engine = risk_engine
        self.execution_engine = execution_engine
        self.mode = mode
        self.process = psutil.Process(os.getpid())
        self.enable_cache = enable_cache
        self.cache = get_dashboard_cache() if enable_cache else None
        self.enable_live_bridge = enable_live_bridge
        # 1-second memoization: avoids re-reading the IPC file on every sub-method call
        self._live_state_cache_ts: float = 0.0
        self._live_state_cache_val: dict[str, Any] | None = None

    def _load_live_state(self) -> dict[str, Any] | None:
        """Load live trading state from shared JSON file (bot IPC).

        Returns the parsed dict if the file exists and is fresh (< 120s),
        otherwise None. Only active when enable_live_bridge=True.
        Memoized for 1 second to avoid redundant reads/logs within a single request.
        """
        if not self.enable_live_bridge:
            return None
        # Return memoized result if called within the last second
        if time.monotonic() - self._live_state_cache_ts < 1.0:
            return self._live_state_cache_val
        try:
            if not _LIVE_STATE_PATH.exists():
                self._live_state_cache_ts = time.monotonic()
                self._live_state_cache_val = None
                return None
            # Stale guard: ignore state older than 120 seconds
            age = datetime.now().timestamp() - _LIVE_STATE_PATH.stat().st_mtime
            if age > 120:
                logger.debug("live_state_stale", age_seconds=round(age, 1))
                self._live_state_cache_ts = time.monotonic()
                self._live_state_cache_val = None
                return None
            raw = _LIVE_STATE_PATH.read_text("utf-8")
            state: dict[str, Any] = json.loads(raw)
            self._live_state_cache_ts = time.monotonic()
            self._live_state_cache_val = state
            return state
        except Exception as exc:
            logger.debug("live_state_load_failed", error=str(exc)[:100])
            self._live_state_cache_ts = time.monotonic()
            self._live_state_cache_val = None
            return None

    def generate_dashboard(self, bypass_cache: bool = False) -> dict[str, Any]:
        """
        Generate complete dashboard snapshot.

        Args:
            bypass_cache: If True, bypass cache and force regeneration

        Returns:
            Dictionary with system status, risk metrics, positions, orders, alerts
        """
        # Try to get from cache
        if self.enable_cache and self.cache and not bypass_cache:
            cached = self.cache.get_cached_dashboard(bypass=False)
            if cached is not None:
                logger.debug("dashboard_cache_hit")
                return cached

        try:
            dashboard = {
                "timestamp": datetime.now().isoformat(),
                "system": self._system_status(),
                "risk": self._risk_metrics(),
                "positions": self._positions(),
                "orders": self._orders(),
                "performance": self._performance_metrics(),
            }

            # Cache the result
            if self.enable_cache and self.cache:
                self.cache.cache_dashboard(dashboard)
                logger.debug("dashboard_cached")

            logger.debug("dashboard_generated", keys=list(dashboard.keys()))
            return dashboard
        except Exception as e:
            logger.error("dashboard_generation_failed", error=str(e))
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "system": self._system_status(),  # At least return system status
            }

    def _system_status(self) -> dict[str, Any]:
        """
        Get system status (uptime, mode, resources).

        Returns:
            Dictionary with system metrics
        """
        try:
            uptime = datetime.now() - _dashboard_start_time
            memory_info = self.process.memory_info()
            cpu_percent = self.process.cpu_percent(interval=0.1)

            return {
                "status": "healthy",
                "mode": self.mode,
                "uptime_seconds": int(uptime.total_seconds()),
                "uptime_human": str(uptime).split(".")[0],
                "memory_mb": round(memory_info.rss / 1024 / 1024, 2),
                "cpu_percent": round(cpu_percent, 2),
                "pid": os.getpid(),
                "timestamp_local": datetime.now().isoformat(),
                "version": "7.8",  # System version tracking
            }
        except Exception as e:
            logger.error("system_status_failed", error=str(e))
            return {"status": "error", "error": str(e)}

    def _risk_metrics(self) -> dict[str, Any]:
        """
        Get risk metrics (equity, drawdown, position limits).

        Returns:
            Dictionary with risk metrics
        """
        if not self.risk_engine:
            # Fallback: read from shared state file (bot IPC)
            state = self._load_live_state()
            if state is None:
                return {"enabled": False, "message": "Risk engine not initialized"}
            m = state.get("metrics", {})
            equity = state.get("equity", 0)
            initial = state.get("initial_capital", 100_000)
            total_return = ((equity - initial) / initial * 100) if initial > 0 else 0
            return {
                "enabled": True,
                "source": "live_state",
                "current_equity": round(equity, 2),
                "initial_equity": round(initial, 2),
                "total_return_pct": round(total_return, 2),
                "daily_loss": 0,
                "daily_loss_pct": 0,
                "max_daily_loss_limit_pct": 0,
                "loss_streak": 0,
                "max_consecutive_losses": 0,
                "positions_count": len(state.get("positions", {})),
                "max_concurrent_positions": 0,
                "daily_trades": m.get("trades_today", 0),
                "max_drawdown_pct": round(m.get("max_drawdown", 0) * 100, 2),
                "trades_total": m.get("trades_total", 0),
                "iteration": state.get("iteration", 0),
                "bot_status": state.get("status", "unknown"),
                "last_update": state.get("timestamp", ""),
            }

        try:
            current_equity = self.risk_engine.equity_history[-1] if self.risk_engine.equity_history else 0
            initial_equity = self.risk_engine.initial_equity
            daily_loss = self.risk_engine.daily_loss
            daily_loss_pct = (daily_loss / initial_equity * 100) if initial_equity > 0 else 0
            max_loss_limit = self.risk_engine.config.max_daily_loss_pct * 100

            # Safely get config values, handling cases where config might be mocked
            max_consecutive_losses = self.risk_engine.config.max_consecutive_losses
            max_concurrent_positions = self.risk_engine.config.max_concurrent_positions

            # Convert non-serializable values (e.g., Mock objects) to defaults
            if not isinstance(max_consecutive_losses, (int, float)):
                max_consecutive_losses = 3  # Default value
            if not isinstance(max_concurrent_positions, (int, float)):
                max_concurrent_positions = 10  # Default value

            return {
                "enabled": True,
                "current_equity": round(current_equity, 2),
                "initial_equity": round(initial_equity, 2),
                "total_return_pct": round((current_equity - initial_equity) / initial_equity * 100, 2),
                "daily_loss": round(daily_loss, 2),
                "daily_loss_pct": round(daily_loss_pct, 2),
                "max_daily_loss_limit_pct": round(max_loss_limit, 2),
                "loss_streak": self.risk_engine.loss_streak,
                "max_consecutive_losses": int(max_consecutive_losses),
                "positions_count": len(self.risk_engine.positions),
                "max_concurrent_positions": int(max_concurrent_positions),
                "daily_trades": self.risk_engine.daily_trades,
            }
        except Exception as e:
            logger.error("risk_metrics_failed", error=str(e))
            return {"enabled": True, "error": str(e)}

    def _positions(self) -> list[dict[str, Any]]:
        """
        Get open positions snapshot.

        Returns:
            List of position dictionaries
        """
        if not self.risk_engine:
            # Fallback: read from shared state file (bot IPC)
            state = self._load_live_state()
            if state is None:
                return []
            positions = []
            for _key, pos in state.get("positions", {}).items():
                entry_time_str = pos.get("entry_time", "")
                try:
                    entry_dt = datetime.fromisoformat(entry_time_str) if entry_time_str else datetime.now()
                except (ValueError, TypeError):
                    entry_dt = datetime.now()
                age_hours = (datetime.now() - entry_dt).total_seconds() / 3600
                entry_price = float(pos.get("entry_price", 0))
                quantity = float(pos.get("quantity", 0))
                pnl = float(pos.get("pnl", 0))
                positions.append(
                    {
                        "symbol": pos.get("symbol_pair", _key),
                        "side": pos.get("side", "unknown"),
                        "quantity": round(quantity, 8),
                        "entry_price": round(entry_price, 2),
                        "current_price": round(float(pos.get("marked_price", 0)), 2),
                        "unrealized_pnl": round(pnl, 2),
                        "pnl_percent": round((pnl / (entry_price * quantity) * 100), 2)
                        if entry_price > 0 and quantity > 0
                        else 0,
                        "entry_time": entry_time_str,
                        "age_hours": round(age_hours, 2),
                        "current_z": pos.get("current_z", 0),
                        "holding_bars": pos.get("holding_bars", 0),
                        "status": pos.get("status", "open"),
                    }
                )
            return positions

        try:
            positions = []
            for _symbol, pos in self.risk_engine.positions.items():
                age_hours = (datetime.now() - pos.entry_time).total_seconds() / 3600

                positions.append(
                    {
                        "symbol": pos.symbol_pair,
                        "side": pos.side,
                        "quantity": round(pos.quantity, 8),
                        "entry_price": round(pos.entry_price, 2),
                        "current_price": round(pos.marked_price, 2),
                        "unrealized_pnl": round(pos.pnl, 2),
                        "pnl_percent": round((pos.pnl / (pos.entry_price * pos.quantity) * 100), 2)
                        if pos.entry_price > 0
                        else 0,
                        "entry_time": pos.entry_time.isoformat(),
                        "age_hours": round(age_hours, 2),
                    }
                )

            logger.debug("positions_snapshot", count=len(positions))
            return positions
        except Exception as e:
            logger.error("positions_snapshot_failed", error=str(e))
            return []

    def _orders(self) -> dict[str, Any]:
        """
        Get open orders snapshot.

        Returns:
            Dictionary with order info or empty/error state
        """
        if not self.execution_engine:
            # Fallback: indicate bot connection status from shared state
            state = self._load_live_state()
            if state is None:
                return {"enabled": False, "message": "Execution engine not initialized"}
            return {
                "enabled": True,
                "source": "live_state",
                "total": 0,
                "orders": [],
                "message": "Order details not available via IPC bridge",
            }

        try:
            # Try to fetch open orders
            try:
                _get_orders: Any = getattr(self.execution_engine, "get_open_orders", None)
                open_orders: list = cast(list, _get_orders()) if callable(_get_orders) else []
            except (AttributeError, NotImplementedError):
                # Method might not exist or be implemented
                logger.debug("get_open_orders_not_available")
                open_orders = []

            orders_list = []
            for order in open_orders:
                try:
                    orders_list.append(
                        {
                            "order_id": str(order.get("id", "N/A")),
                            "symbol": order.get("symbol", "N/A"),
                            "side": order.get("side", "N/A"),
                            "quantity": round(float(order.get("amount", 0)), 8),
                            "price": round(float(order.get("price", 0)), 2),
                            "status": order.get("status", "N/A"),
                            "created_at": order.get("timestamp", "N/A"),
                        }
                    )
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning("order_parse_failed", order=order, error=str(e))
                    continue

            return {
                "enabled": True,
                "total": len(orders_list),
                "orders": orders_list[:20] if len(orders_list) > 20 else orders_list,  # Cap at 20
            }
        except Exception as e:
            logger.error("orders_snapshot_failed", error=str(e))
            return {"enabled": True, "error": str(e), "total": 0, "orders": []}

    def _performance_metrics(self) -> dict[str, Any]:
        """
        Get performance metrics (returns, Sharpe, drawdown).

        Returns:
            Dictionary with performance metrics
        """
        if not self.risk_engine:
            # Fallback: read from shared state file (bot IPC)
            state = self._load_live_state()
            if state is None:
                return {"enabled": False}
            equity_history = state.get("equity_history", [])
            m = state.get("metrics", {})
            if len(equity_history) < 2:
                return {
                    "enabled": True,
                    "source": "live_state",
                    "total_return_pct": 0,
                    "trades_total": m.get("trades_total", 0),
                    "data_points": len(equity_history),
                }
            total_return = (equity_history[-1] - equity_history[0]) / equity_history[0] if equity_history[0] > 0 else 0
            return {
                "enabled": True,
                "source": "live_state",
                "total_return_pct": round(total_return * 100, 2),
                "sharpe_ratio": round(m.get("sharpe_ratio", 0), 2),
                "max_drawdown_pct": round(m.get("max_drawdown", 0) * 100, 2),
                "data_points": len(equity_history),
                "trades_total": m.get("trades_total", 0),
            }

        try:
            equity_history = self.risk_engine.equity_history

            if len(equity_history) < 2:
                return {"enabled": True, "total_return": 0, "trades_total": 0, "data_points": len(equity_history)}

            # Calculate simple returns
            returns = []
            for i in range(1, len(equity_history)):
                ret = (equity_history[i] - equity_history[i - 1]) / equity_history[i - 1]
                returns.append(ret)

            # Total return
            total_return = (equity_history[-1] - equity_history[0]) / equity_history[0]

            # Sharpe ratio (252 days/year  - US equity trading days)
            if len(returns) > 1:
                import numpy as np

                returns_arr = np.array(returns)
                mean_return = np.mean(returns_arr)
                std_return = np.std(returns_arr)
                sharpe = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0
            else:
                sharpe = 0

            # Max drawdown
            max_equity = equity_history[0]
            max_drawdown = 0
            for equity in equity_history[1:]:
                if equity > max_equity:
                    max_equity = equity
                drawdown = (max_equity - equity) / max_equity
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

            return {
                "enabled": True,
                "total_return_pct": round(total_return * 100, 2),
                "sharpe_ratio": round(sharpe, 2),
                "max_drawdown_pct": round(max_drawdown * 100, 2),
                "data_points": len(equity_history),
                "trades_total": self.risk_engine.daily_trades,
            }
        except Exception as e:
            logger.error("performance_metrics_failed", error=str(e))
            return {"enabled": True, "error": str(e)}

    def get_status(self) -> dict[str, Any]:
        """
        Get dashboard generator status for monitoring.

        Returns:
            Status dictionary
        """
        cache_stats = self.cache.get_stats() if self.cache else {}
        state = self._load_live_state()
        return {
            "mode": self.mode,
            "risk_engine_available": self.risk_engine is not None,
            "execution_engine_available": self.execution_engine is not None,
            "live_state_connected": state is not None,
            "live_state_iteration": state.get("iteration", 0) if state else 0,
            "live_state_bot_status": state.get("status", "disconnected") if state else "disconnected",
            "uptime_seconds": int((datetime.now() - _dashboard_start_time).total_seconds()),
            "cache_enabled": self.enable_cache,
            "cache_stats": cache_stats,
        }

    def invalidate_cache(self) -> int:
        """
        Invalidate dashboard cache (e.g., on position/order change).

        Returns:
            Number of cache entries invalidated
        """
        if self.cache:
            count = self.cache.invalidate_dashboard()
            logger.info("dashboard_cache_invalidated", entries_cleared=count)
            return count
        return 0

    @staticmethod
    def reset_uptime() -> None:
        """Reset the dashboard uptime counter."""
        global _dashboard_start_time
        _dashboard_start_time = datetime.now()
        logger.info("dashboard_uptime_reset")
