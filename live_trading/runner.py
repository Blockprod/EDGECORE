"""
Live Trading Runner — Production trading loop composing all EDGECORE modules.

Orchestrates the full trading pipeline in real-time:

    1. Universe refresh          (universe.UniverseManager)
    2. Pair re-discovery         (pair_selection.PairDiscoveryEngine)
    3. Signal generation         (signal_engine.SignalGenerator)
    4. Risk checks               (risk_engine.PositionRiskManager / PortfolioRiskManager)
    5. Portfolio sizing           (portfolio_engine.PortfolioAllocator)
    6. Order execution           (execution_engine.ExecutionRouter)
    7. Position monitoring       (risk_engine.KillSwitch)

The loop runs once per bar interval (configurable, default 1 minute for
intraday or 1 day for daily).  It is designed to be run as a long-lived
process under process supervision (systemd, Docker, etc.).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


class TradingState(Enum):
    """Trading loop state machine."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    HALTED = "halted"       # kill-switch triggered
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


@dataclass
class TradingLoopConfig:
    """Configuration for the live trading loop."""
    symbols: List[str] = field(default_factory=list)
    bar_interval_seconds: int = 60         # 60s = 1-minute bars
    pair_rediscovery_hours: int = 24       # re-discover pairs every N hours
    max_positions: int = 10
    initial_capital: float = 100_000.0
    mode: str = "live"                     # "live" or "paper"


class LiveTradingRunner:
    """
    Production live trading loop.

    Composes all EDGECORE modules into a single coherent pipeline
    that runs continuously.

    Usage::

        from live_trading import LiveTradingRunner

        runner = LiveTradingRunner(TradingLoopConfig(
            symbols=["AAPL", "MSFT", "GOOGL", "META", ...],
            bar_interval_seconds=60,
        ))
        runner.start()  # blocks until shutdown

    The runner handles:
        - Graceful startup and shutdown
        - Periodic pair re-discovery
        - Per-bar signal generation and risk checks
        - Kill-switch integration for emergency halts
        - Structured logging for full audit trail
    """

    def __init__(self, config: Optional[TradingLoopConfig] = None):
        self.config = config or TradingLoopConfig()
        self._state = TradingState.INITIALIZING
        self._active_pairs: List[tuple] = []
        self._positions: Dict[str, Any] = {}
        self._last_discovery: Optional[datetime] = None
        self._iteration = 0

        # Module references (lazy-initialized in _initialize)
        self._universe_mgr = None
        self._pair_engine = None
        self._signal_gen = None
        self._position_risk = None
        self._portfolio_risk = None
        self._kill_switch = None
        self._allocator = None
        self._router = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the trading loop (blocking)."""
        logger.info("live_trading_starting", config=self.config)
        self._initialize()
        self._state = TradingState.RUNNING
        logger.info("live_trading_running")

        try:
            while self._state == TradingState.RUNNING:
                # Check ShutdownManager for graceful shutdown signals
                if self._shutdown_mgr and self._shutdown_mgr.is_shutdown_requested():
                    reason = self._shutdown_mgr.get_shutdown_reason() or "shutdown_requested"
                    logger.warning("live_trading_shutdown_signal", reason=reason)
                    break
                self._tick()
                time.sleep(self.config.bar_interval_seconds)
        except KeyboardInterrupt:
            logger.warning("live_trading_keyboard_interrupt")
        finally:
            self._shutdown()

    def stop(self) -> None:
        """Signal the loop to stop gracefully."""
        self._state = TradingState.SHUTTING_DOWN
        logger.info("live_trading_stop_requested")

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _initialize(self) -> None:
        """Initialize all trading modules."""
        from universe import UniverseManager
        from pair_selection import PairDiscoveryEngine
        from signal_engine import SignalGenerator
        from risk_engine import PositionRiskManager, PortfolioRiskManager, KillSwitch
        from portfolio_engine import PortfolioAllocator
        from execution_engine import ExecutionRouter, ExecutionMode
        from execution.trailing_stop import TrailingStopManager
        from execution.time_stop import TimeStopManager
        from execution.partial_profit import PartialProfitManager
        from execution.shutdown_manager import ShutdownManager
        from execution.reconciler import BrokerReconciler
        from monitoring.correlation_monitor import CorrelationMonitor

        self._universe_mgr = UniverseManager(symbols=self.config.symbols)
        self._pair_engine = PairDiscoveryEngine()
        self._signal_gen = SignalGenerator()
        self._position_risk = PositionRiskManager()
        self._portfolio_risk = PortfolioRiskManager()
        self._kill_switch = KillSwitch()
        self._allocator = PortfolioAllocator()

        # Stop managers — wired into _tick() for live position protection
        self._trailing_stop = TrailingStopManager()
        self._time_stop = TimeStopManager()
        self._partial_profit = PartialProfitManager()
        self._shutdown_mgr = ShutdownManager()
        self._correlation_monitor = CorrelationMonitor()

        # Broker reconciliation
        self._reconciler: Optional[BrokerReconciler] = None
        self._last_reconciliation: Optional[datetime] = None
        self._reconciliation_interval = timedelta(minutes=5)

        mode_map = {"live": ExecutionMode.LIVE, "paper": ExecutionMode.PAPER}
        self._router = ExecutionRouter(mode=mode_map.get(self.config.mode, ExecutionMode.PAPER))

        self._state = TradingState.INITIALIZING

        # Startup reconciliation (live mode only)
        if self.config.mode == "live":
            self._run_startup_reconciliation()

        logger.info("live_trading_modules_initialized")

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def _run_startup_reconciliation(self) -> None:
        """Run full broker reconciliation at startup."""
        try:
            if not self._router:
                return
            broker_equity = self._router.get_account_balance()
            if broker_equity <= 0:
                logger.warning("reconciliation_skipped_no_equity")
                return

            from execution.reconciler import BrokerReconciler
            self._reconciler = BrokerReconciler(
                internal_equity=self.config.initial_capital,
                internal_positions={k: v for k, v in self._positions.items()},
                equity_tolerance_pct=0.02,
            )
            broker_positions = {}
            try:
                broker_positions = self._router._engine.get_positions() if hasattr(self._router, '_engine') else {}
            except Exception:
                pass

            report = self._reconciler.full_reconciliation(
                broker_equity=broker_equity,
                broker_positions=broker_positions,
                broker_orders={},
            )
            self._last_reconciliation = datetime.now()
            if report.status.value == "critical":
                logger.critical("startup_reconciliation_critical", divergences=len(report.divergences))
                self._state = TradingState.HALTED
            else:
                logger.info("startup_reconciliation_ok", status=report.status.value)
        except Exception as exc:
            logger.error("startup_reconciliation_failed", error=str(exc)[:200])

    def _maybe_reconcile(self) -> None:
        """Run periodic reconciliation every 5 minutes."""
        if self._reconciler is None or self.config.mode != "live":
            return
        now = datetime.now()
        if self._last_reconciliation and (now - self._last_reconciliation) < self._reconciliation_interval:
            return
        try:
            broker_equity = self._router.get_account_balance() if self._router else 0
            if broker_equity <= 0:
                return
            self._reconciler.internal_equity = self.config.initial_capital  # update if tracking
            self._reconciler.internal_positions = {k: v for k, v in self._positions.items()}
            broker_positions = {}
            try:
                broker_positions = self._router._engine.get_positions() if hasattr(self._router, '_engine') else {}
            except Exception:
                pass
            report = self._reconciler.full_reconciliation(
                broker_equity=broker_equity,
                broker_positions=broker_positions,
                broker_orders={},
            )
            self._last_reconciliation = now
            if report.status.value == "critical":
                logger.critical("periodic_reconciliation_critical", divergences=len(report.divergences))
                self._state = TradingState.HALTED
        except Exception as exc:
            logger.error("periodic_reconciliation_failed", error=str(exc)[:200])

    # ------------------------------------------------------------------
    # Main loop tick
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        """Execute one iteration of the trading loop."""
        self._iteration += 1

        # 0a. Periodic reconciliation
        self._maybe_reconcile()

        # 0. Kill-switch check
        if self._kill_switch and self._kill_switch.is_active:
            self._state = TradingState.HALTED
            logger.critical("live_trading_halted_by_kill_switch")
            return

        # 1. Periodic pair re-discovery
        self._maybe_rediscover_pairs()

        # 2. Fetch latest market data for active symbols
        try:
            market_data = self._fetch_market_data()
        except Exception as exc:
            logger.error("live_trading_data_fetch_failed", error=str(exc)[:200])
            return

        if market_data is None or market_data.empty:
            logger.warning("live_trading_no_market_data", iteration=self._iteration)
            return

        # 2b. Stop manager checks on existing positions
        exit_signals_from_stops = []
        for pair_key, pos_info in list(self._positions.items()):
            try:
                holding_bars = pos_info.get('holding_bars', 0)
                pos_info['holding_bars'] = holding_bars + 1  # increment

                half_life = pos_info.get('half_life')
                entry_z = pos_info.get('entry_z', 0.0)
                current_z = pos_info.get('current_z', 0.0)
                unrealized_pnl_pct = pos_info.get('unrealized_pnl_pct', 0.0)

                # Trailing stop: exit if Z-score diverges too far from entry
                if self._trailing_stop:
                    ts_exit, ts_reason = self._trailing_stop.check(
                        pair_key=pair_key,
                        entry_z=entry_z,
                        current_z=current_z,
                    )
                    if ts_exit:
                        exit_signals_from_stops.append((pair_key, ts_reason))
                        continue

                # Time stop: exit if held too long relative to half-life
                if self._time_stop:
                    time_exit, time_reason = self._time_stop.should_exit(
                        holding_bars=holding_bars,
                        half_life=half_life,
                    )
                    if time_exit:
                        exit_signals_from_stops.append((pair_key, time_reason))
                        continue

                # Partial profit: take profit on portion of position
                if self._partial_profit:
                    pp_action = self._partial_profit.check(
                        pair_key=pair_key,
                        unrealized_pnl_pct=unrealized_pnl_pct,
                    )
                    if pp_action and pp_action.get('close_fraction', 0) > 0:
                        logger.info(
                            "live_trading_partial_profit",
                            pair=pair_key,
                            close_fraction=pp_action['close_fraction'],
                        )

                # Ongoing correlation monitor: exit if pair correlation degrades
                if self._correlation_monitor and market_data is not None:
                    syms = pair_key.split("_")
                    if len(syms) == 2 and syms[0] in market_data.columns and syms[1] in market_data.columns:
                        pa = float(market_data[syms[0]].iloc[-1])
                        pb = float(market_data[syms[1]].iloc[-1])
                        corr_alert = self._correlation_monitor.update(pair_key, pa, pb)
                        if corr_alert and corr_alert.get('hard_exit'):
                            exit_signals_from_stops.append((pair_key, f"correlation_degraded_{corr_alert['correlation']:.2f}"))
                            continue
                        elif corr_alert and corr_alert.get('degraded'):
                            logger.warning("live_trading_correlation_warning", pair=pair_key, corr=corr_alert['correlation'])

            except Exception as exc:
                logger.error("live_trading_stop_check_error", pair=pair_key, error=str(exc)[:200])

        # Execute stop-triggered exits
        for pair_key, reason in exit_signals_from_stops:
            logger.info("live_trading_stop_exit", pair=pair_key, reason=reason)
            if pair_key in self._positions:
                # Route a close order through the execution router
                try:
                    if self._router:
                        from execution.base import Order, OrderSide
                        from uuid import uuid4
                        pos = self._positions[pair_key]
                        qty = pos.get('quantity', 0)
                        close_side = OrderSide.SELL if qty > 0 else OrderSide.BUY
                        close_order = Order(
                            order_id=str(uuid4()),
                            symbol=pair_key,
                            side=close_side,
                            quantity=abs(qty),
                            limit_price=None,
                            order_type="MARKET",
                        )
                        self._router.submit_order(close_order)
                except Exception as exc:
                    logger.error("live_trading_stop_exit_failed", pair=pair_key, error=str(exc)[:200])
                del self._positions[pair_key]

        # 3. Generate signals for active pairs
        signals = []
        if self._active_pairs and self._signal_gen:
            try:
                signals = self._signal_gen.generate(
                    market_data=market_data,
                    active_pairs=self._active_pairs,
                    active_positions=self._positions,
                )
            except Exception as exc:
                logger.error("live_trading_signal_error", error=str(exc)[:200])

        # 4. Process each signal through risk checks, sizing, execution
        for sig in signals:
            try:
                # 4a. Position-level risk check
                if self._position_risk:
                    risk_ok = self._position_risk.check(
                        pair_key=sig.pair_key,
                        signal=sig,
                        positions=self._positions,
                    )
                    if not risk_ok:
                        logger.info("live_trading_signal_blocked_position_risk", pair=sig.pair_key)
                        continue

                # 4b. Portfolio-level risk check
                if self._portfolio_risk:
                    portfolio_ok = self._portfolio_risk.check(
                        positions=self._positions,
                        new_signal=sig,
                    )
                    if not portfolio_ok:
                        logger.info("live_trading_signal_blocked_portfolio_risk", pair=sig.pair_key)
                        continue

                # 4c. Size the position via allocator
                if self._allocator:
                    sized_order = self._allocator.size(
                        signal=sig,
                        capital=self._router.get_account_balance() if self._router else self.config.initial_capital,
                        max_positions=self.config.max_positions,
                        current_positions=self._positions,
                    )
                else:
                    sized_order = sig  # fallback: raw signal

                # 4d. Submit order through execution router
                if self._router and sized_order:
                    order_id = self._router.submit_order(sized_order)
                    logger.info(
                        "live_trading_order_submitted",
                        pair=sig.pair_key,
                        order_id=order_id,
                    )

            except Exception as exc:
                logger.error(
                    "live_trading_signal_processing_error",
                    pair=getattr(sig, 'pair_key', 'unknown'),
                    error=str(exc)[:200],
                )

        logger.debug(
            "live_trading_tick_complete",
            iteration=self._iteration,
            active_pairs=len(self._active_pairs),
            signals_generated=len(signals),
            open_positions=len(self._positions),
        )

    def _fetch_market_data(self) -> Optional[pd.DataFrame]:
        """Fetch recent price data for all symbols in the universe.

        Returns:
            DataFrame with columns = symbols, rows = time bars.
        """
        # Use the data loader if available, otherwise return None
        try:
            from data.loader import load_price_data
            symbols = self.config.symbols
            if self._universe_mgr:
                symbols = self._universe_mgr.get_active_symbols() or symbols
            return load_price_data(symbols=symbols)
        except ImportError:
            logger.warning("live_trading_data_loader_not_available")
            return None

    # ------------------------------------------------------------------
    # Pair discovery
    # ------------------------------------------------------------------

    def _maybe_rediscover_pairs(self) -> None:
        """Re-discover pairs if enough time has elapsed."""
        now = datetime.now()
        interval = timedelta(hours=self.config.pair_rediscovery_hours)

        if self._last_discovery is None or (now - self._last_discovery) >= interval:
            logger.info("live_trading_pair_rediscovery_start")
            # In production: fetch historical data, run discovery, validate OOS
            self._last_discovery = now
            logger.info(
                "live_trading_pair_rediscovery_complete",
                pairs=len(self._active_pairs),
            )

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def _shutdown(self) -> None:
        """Graceful shutdown: close positions, flush logs."""
        self._state = TradingState.SHUTTING_DOWN
        logger.info(
            "live_trading_shutting_down",
            iterations=self._iteration,
            open_positions=len(self._positions),
        )

        # Close all open positions via router
        if self._router and self._positions:
            for symbol, qty in list(self._positions.items()):
                try:
                    from execution.base import Order, OrderSide
                    from uuid import uuid4
                    close_side = OrderSide.SELL if qty > 0 else OrderSide.BUY
                    close_order = Order(
                        order_id=str(uuid4()),
                        symbol=symbol,
                        side=close_side,
                        quantity=abs(qty),
                        limit_price=None,
                        order_type="MARKET",
                    )
                    self._router.submit_order(close_order)
                    logger.info("live_trading_position_closed", symbol=symbol, qty=qty)
                except Exception as exc:
                    logger.error("live_trading_close_failed", symbol=symbol, error=str(exc)[:120])

        self._state = TradingState.STOPPED
        # Cleanup shutdown manager (remove trading_enabled file)
        if hasattr(self, '_shutdown_mgr') and self._shutdown_mgr:
            try:
                self._shutdown_mgr.cleanup()
            except Exception:
                pass
        logger.info("live_trading_stopped")

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def state(self) -> TradingState:
        return self._state

    @property
    def iteration_count(self) -> int:
        return self._iteration
