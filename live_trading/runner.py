"""
Live Trading Runner ÔÇö Production trading loop composing all EDGECORE modules.

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

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

import pandas as pd
from structlog import get_logger

if TYPE_CHECKING:
    from monitoring.metrics import SystemMetrics

from risk_engine.kill_switch import KillReason

logger = get_logger(__name__)


class TradingState(Enum):
    """Trading loop state machine."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    HALTED = "halted"  # kill-switch triggered
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


@dataclass
class TradingLoopConfig:
    """Configuration for the live trading loop."""

    symbols: list[str] = field(default_factory=list)
    sector_map: dict[str, str] | None = None
    bar_interval_seconds: int = 60  # 60s = 1-minute bars
    pair_rediscovery_hours: int = 24  # re-discover pairs every N hours
    max_positions: int = 10
    initial_capital: float = 100_000.0
    allocation_per_pair_pct: float = 90.0  # % of capital per pair
    max_portfolio_heat: float = 4.0  # max concurrent notional / capital
    mode: str = "live"  # "live" or "paper"


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
        - Email/Slack alerting on errors, kill-switch, reconciliation
    """

    def __init__(
        self,
        config: TradingLoopConfig | None = None,
        email_alerter: Any | None = None,
        slack_alerter: Any | None = None,
    ):
        self.config = config or TradingLoopConfig()
        self._state = TradingState.INITIALIZING
        self._active_pairs: list[tuple] = []
        self._positions: dict[str, Any] = {}
        self._positions_lock = threading.Lock()
        self._last_discovery: datetime | None = None
        self._iteration = 0
        # Data load tracking (for dashboard)
        self._data_symbols_loaded: int = 0
        self._data_symbols_total: int = 0
        self._data_load_at: datetime | None = None
        self._data_load_rows: int = 0
        self._equity_history: list = []  # per-tick equity for sparkline (last 60)

        # Alerters (Email + Slack) ÔÇö initialised from env or passed in
        self._email_alerter = email_alerter
        self._slack_alerter = slack_alerter
        # C-11: dedicated single-worker executor for alert dispatch
        # (avoids blocking the tick thread on SMTP/HTTP timeouts)
        self._alert_executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="alerts")

        # Module references (lazy-initialized in _initialize)
        self._universe_mgr = None
        self._pair_engine = None
        self._signal_gen = None
        self._position_risk = None
        self._portfolio_risk = None
        self._kill_switch = None
        self._risk_facade = None
        self._allocator = None
        self._router = None
        self._audit_trail = None  # A-17: crash-recovery audit trail (lazy-init at startup)
        self._ml_combiner = None  # C-04: ML signal shadow mode (MLSignalCombiner)
        self._retraining_task = None  # C-07: periodic hedge-ratio re-estimation

    # ------------------------------------------------------------------
    # Alerting helpers
    # ------------------------------------------------------------------

    def _on_kill_switch_activated(self, reason: KillReason, message: str) -> None:
        """Callback wired into KillSwitch — called on activation.

        Cancels all pending IBKR orders to prevent runaway fills, then
        sends a CRITICAL alert to all configured channels.
        """
        logger.critical("live_trading_kill_switch_activated", reason=str(reason), message=message)
        # Cancel pending orders at the broker level
        if self._router is not None:
            ibkr_engine = getattr(self._router, "_ibkr_engine", None)
            if ibkr_engine is not None:
                try:
                    cancelled = ibkr_engine.cancel_all_pending()
                    logger.info("live_trading_kill_switch_orders_cancelled", count=cancelled)
                except Exception as exc:
                    logger.error("live_trading_kill_switch_cancel_failed", error=str(exc)[:200])
        self._send_alert(
            "CRITICAL",
            "Kill-switch activated",
            f"Trading halted — {message}",
            {"reason": str(reason)},
        )

    def _send_alert(
        self,
        level: str,
        title: str,
        message: str,
        data: dict | None = None,
    ) -> None:
        """Submit an alert to the dedicated alert thread (C-11 — non-blocking)."""
        self._alert_executor.submit(self._do_send_alert, level, title, message, data)

    def _do_send_alert(
        self,
        level: str,
        title: str,
        message: str,
        data: dict | None = None,
    ) -> None:
        """Dispatch alert to Email + Slack.  Never raises — fire-and-forget."""
        for alerter in (self._email_alerter, self._slack_alerter):
            if alerter is None:
                continue
            try:
                alerter.send_alert(level=level, title=title, message=message, data=data)
            except Exception as exc:
                logger.debug("alert_dispatch_failed", alerter=type(alerter).__name__, error=str(exc)[:120])

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
        self._alert_executor.shutdown(wait=False)  # C-11: don't block on pending alerts
        logger.info("live_trading_stop_requested")

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _initialize(self) -> None:
        """Initialize all trading modules.

        Reads strategy/risk settings from ``get_settings()`` singleton so
        that parameters set before ``start()`` (e.g. entry_z_score=1.5)
        propagate to all sub-modules.
        """
        from config.settings import get_settings
        from execution.partial_profit import PartialProfitManager
        from execution.reconciler import BrokerReconciler
        from execution.shutdown_manager import ShutdownManager
        from execution.time_stop import TimeStopManager
        from execution.trailing_stop import TrailingStopManager
        from execution_engine import ExecutionMode, ExecutionRouter
        from monitoring.correlation_monitor import CorrelationMonitor
        from monitoring.metrics import SystemMetrics
        from pair_selection import PairDiscoveryEngine
        from pair_selection.discovery import DiscoveryConfig
        from portfolio_engine import PortfolioAllocator
        from risk.facade import RiskFacade
        from risk_engine import KillSwitch, PortfolioRiskManager, PositionRiskManager
        from signal_engine import SignalGenerator
        from signal_engine.adaptive import AdaptiveThresholdEngine
        from universe import UniverseManager

        strat = get_settings().strategy
        self._lookback = getattr(strat, "lookback_window", 252)

        # Sector map from config or TradingLoopConfig
        sector_map = getattr(self.config, "sector_map", None)
        self._universe_mgr = UniverseManager(
            symbols=self.config.symbols,
            sector_map=sector_map,
        )

        # Wire strategy params into PairDiscoveryEngine
        self._pair_engine = PairDiscoveryEngine(
            config=DiscoveryConfig(
                min_correlation=getattr(strat, "min_correlation", 0.7),
                max_half_life=getattr(strat, "max_half_life", 60),
                lookback_window=self._lookback,
            )
        )

        # Wire z-score thresholds into SignalGenerator
        self._signal_gen = SignalGenerator(
            threshold_engine=AdaptiveThresholdEngine(
                base_entry=getattr(strat, "entry_z_score", 2.0),
                base_exit=getattr(strat, "exit_z_score", 0.5),
                max_entry=getattr(strat, "z_score_stop", 3.5),
            ),
        )

        self._position_risk = PositionRiskManager()
        self._portfolio_risk = PortfolioRiskManager(
            initial_equity=self.config.initial_capital,
        )
        self._kill_switch = KillSwitch(on_activate=self._on_kill_switch_activated)
        # Inject the shared KillSwitch into RiskFacade so both references
        # point to the same object — prevents divergent halt states (B2-02).
        self._risk_facade = RiskFacade(
            initial_equity=self.config.initial_capital,
            kill_switch=self._kill_switch,
        )

        # Wire portfolio heat and allocation from config
        alloc_pct = getattr(self.config, "allocation_per_pair_pct", 90.0) / 100.0
        heat = getattr(self.config, "max_portfolio_heat", 4.0)
        self._allocator = PortfolioAllocator(
            equity=self.config.initial_capital,
            max_pairs=self.config.max_positions,
            max_allocation_pct=alloc_pct,
            max_portfolio_heat=heat,
        )

        # Stop managers ÔÇö wired into _tick() for live position protection
        self._trailing_stop = TrailingStopManager()
        self._time_stop = TimeStopManager()
        self._partial_profit = PartialProfitManager()
        self._shutdown_mgr = ShutdownManager()
        self._correlation_monitor = CorrelationMonitor()

        # Monitoring metrics (published each tick for Prometheus scrape)
        self._metrics = SystemMetrics(equity=self.config.initial_capital)

        # Broker reconciliation
        self._reconciler: BrokerReconciler | None = None
        self._last_reconciliation: datetime | None = None
        self._reconciliation_interval = timedelta(minutes=5)

        mode_map = {"live": ExecutionMode.LIVE, "paper": ExecutionMode.PAPER}
        self._router = ExecutionRouter(mode=mode_map.get(self.config.mode, ExecutionMode.PAPER))

        self._state = TradingState.INITIALIZING

        # C-04: Instantiate ML combiner in shadow mode and restore persisted model
        from pathlib import Path

        from config.settings import get_settings as _gs
        from signal_engine.ml_combiner import MLSignalCombiner

        _sc = _gs().signal_combiner
        self._ml_combiner = MLSignalCombiner(enabled=True)
        _model_dir = Path("data/models")
        _model_dir.mkdir(parents=True, exist_ok=True)
        self._ml_combiner.load(_model_dir / "ml_combiner_live.joblib")

        # C-07: Periodic hedge-ratio retraining task
        from scheduler.retraining_task import RetrainingTask as _RetrainingTask

        _interval = _gs().strategy.retraining_interval_bars
        self._retraining_task = _RetrainingTask(interval_bars=_interval)

        # Startup reconciliation (live mode only)
        if self.config.mode == "live":
            self._run_startup_reconciliation()

        logger.info("live_trading_modules_initialized")

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def _run_startup_reconciliation(self) -> None:
        """Run full broker reconciliation at startup."""
        # A-17: restore in-memory positions from audit trail (crash recovery)
        try:
            from persistence.audit_trail import AuditTrail

            self._audit_trail = AuditTrail()
            recovered_positions, _ = self._audit_trail.recover_state()
            if recovered_positions:
                with self._positions_lock:
                    self._positions = {k: vars(v) for k, v in recovered_positions.items()}
                logger.info(
                    "positions_restored_from_audit_trail",
                    count=len(recovered_positions),
                )
        except Exception as exc:
            logger.warning("audit_trail_recovery_failed", error=str(exc)[:200])
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
                broker_positions = self._router._engine.get_positions() if hasattr(self._router, "_engine") else {}  # type: ignore[attr-defined]
            except Exception as exc:
                if self.config.mode == "live":
                    raise RuntimeError(f"Cannot start live trading: broker position fetch failed: {exc}") from exc
                logger.warning("startup_reconciliation_positions_unavailable", error=str(exc)[:200])

            report = self._reconciler.full_reconciliation(
                broker_equity=broker_equity,
                broker_positions=broker_positions,
                broker_orders={},
            )
            self._last_reconciliation = datetime.now()
            if report.status.value == "critical":
                logger.critical("startup_reconciliation_critical", divergences=len(report.divergences))
                self._state = TradingState.HALTED
                self._send_alert(
                    "CRITICAL",
                    "Startup reconciliation CRITICAL",
                    f"Broker/internal positions diverge critically ({len(report.divergences)} divergences). "
                    f"Trading halted.",
                    {"divergences": len(report.divergences)},
                )
            else:
                logger.info("startup_reconciliation_ok", status=report.status.value)
        except Exception as exc:
            logger.error("startup_reconciliation_failed", error=str(exc)[:200])
            self._send_alert(
                "ERROR",
                "Startup reconciliation failed",
                f"Exception during startup reconciliation: {exc}",
            )

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
            self._reconciler.internal_equity = (
                self._metrics.equity
                if hasattr(self, "_metrics") and self._metrics.equity > 0
                else self.config.initial_capital
            )
            self._reconciler.internal_positions = {k: v for k, v in self._positions.items()}
            broker_positions = {}
            try:
                broker_positions = self._router._engine.get_positions() if hasattr(self._router, "_engine") else {}  # type: ignore[attr-defined]
            except Exception as exc:
                logger.warning("periodic_reconciliation_positions_unavailable", error=str(exc)[:200])
                return  # skip ce tick, réessayer au prochain intervalle
            report = self._reconciler.full_reconciliation(
                broker_equity=broker_equity,
                broker_positions=broker_positions,
                broker_orders={},
            )
            self._last_reconciliation = now
            if report.status.value == "critical":
                logger.critical("periodic_reconciliation_critical", divergences=len(report.divergences))
                self._state = TradingState.HALTED
                self._send_alert(
                    "CRITICAL",
                    "Periodic reconciliation CRITICAL",
                    f"Broker/internal positions diverge critically ({len(report.divergences)} divergences). "
                    f"Trading halted at iteration {self._iteration}.",
                    {"divergences": len(report.divergences), "iteration": self._iteration},
                )
        except Exception as exc:
            logger.error("periodic_reconciliation_failed", error=str(exc)[:200])
            self._send_alert(
                "ERROR",
                "Periodic reconciliation failed",
                f"Exception during periodic reconciliation: {exc}",
                {"iteration": self._iteration},
            )

    # ------------------------------------------------------------------
    # Main loop tick
    # ------------------------------------------------------------------
    # Fill confirmation (A-02)
    # ------------------------------------------------------------------

    def _process_fill_confirmations(self) -> None:
        """Check fill status of pending close orders and confirm or escalate.

        Called at the start of every tick.  Positions marked ``pending_close``
        are only removed from ``_positions`` once the broker confirms FILLED.
        If the close order is rejected / cancelled, a CRITICAL alert is sent
        and the position is intentionally retained so the operator can act.
        """
        from execution.base import OrderStatus

        with self._positions_lock:
            pending = {k: v for k, v in self._positions.items() if v.get("status") == "pending_close"}

        for pair_key, pos_info in pending.items():
            order_id = pos_info.get("close_order_id")
            if not order_id or not self._router:
                continue
            try:
                status = self._router.get_order_status(order_id)
                if status == OrderStatus.FILLED:
                    with self._positions_lock:
                        self._positions.pop(pair_key, None)
                    logger.info(
                        "position_closed_confirmed",
                        pair=pair_key,
                        order_id=order_id,
                    )
                elif status in (
                    OrderStatus.CANCELLED,
                    OrderStatus.REJECTED,
                    OrderStatus.FAILED,
                ):
                    logger.error(
                        "close_order_rejected_position_retained",
                        pair=pair_key,
                        order_id=order_id,
                        status=str(status),
                    )
                    self._send_alert(
                        "CRITICAL",
                        f"Close order rejected — position retained: {pair_key}",
                        f"Order {order_id} for {pair_key} ended with status {status}. "
                        "Position NOT closed. Immediate operator intervention required.",
                        {
                            "pair": pair_key,
                            "order_id": order_id,
                            "status": str(status),
                        },
                    )
                    # Reset status so we don't re-alert every tick
                    with self._positions_lock:
                        if pair_key in self._positions:
                            self._positions[pair_key]["status"] = "close_failed"
            except Exception as exc:
                logger.error(
                    "fill_confirmation_check_failed",
                    pair=pair_key,
                    error=str(exc)[:200],
                )

    # ------------------------------------------------------------------
    # Main loop tick
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        """Execute one iteration of the trading loop."""
        self._iteration += 1

        # 0a. Process fill confirmations from pending close orders (A-02)
        self._process_fill_confirmations()

        # 0b. Periodic reconciliation
        self._maybe_reconcile()

        # 0. Kill-switch check (via RiskFacade — shared KillSwitch instance)
        if self._step_check_kill_switch():
            return

        # 1. Periodic pair re-discovery (C-02: may return cached market data)
        prefetched_data = self._maybe_rediscover_pairs()

        # 2. Fetch latest market data — reuse discovery data if already loaded (C-02)
        try:
            market_data = (
                prefetched_data
                if isinstance(prefetched_data, pd.DataFrame) and not prefetched_data.empty
                else self._fetch_market_data()
            )
        except Exception as exc:
            logger.error("live_trading_data_fetch_failed", error=str(exc)[:200])
            self._send_alert(
                "ERROR",
                "Market data fetch failed",
                f"Unable to fetch market data at iteration {self._iteration}: {exc}",
                {"iteration": self._iteration, "error": str(exc)[:200]},
            )
            return

        if market_data is None or market_data.empty:
            logger.warning("live_trading_no_market_data", iteration=self._iteration)
            return

        self._step_process_stops(market_data)

        # 3. Generate signals for active pairs
        signals = self._step_generate_signals(market_data)

        # 4. Process each signal through risk checks, sizing, execution
        # C-10: fetch account balance once per tick instead of once per signal
        _tick_balance = self._router.get_account_balance() if self._router else self.config.initial_capital
        self._step_execute_signals(signals, market_data, account_balance=_tick_balance)

        self._step_periodic_tasks(market_data, signals)

        # MON-1: Update metrics snapshot for Prometheus / dashboard
        self._update_metrics(signals, equity=_tick_balance)

    def _step_check_kill_switch(self) -> bool:
        """Check if the kill-switch has been activated.

        Returns:
            True if halted (caller should return immediately), False if clear.
        """
        if self._risk_facade and self._risk_facade.is_halted:
            self._state = TradingState.HALTED
            logger.critical("live_trading_halted_by_kill_switch")
            self._send_alert(
                "CRITICAL",
                "Kill-switch activated",
                "Trading halted ÔÇö kill-switch has been triggered. Immediate operator intervention required.",
                {"iteration": self._iteration, "open_positions": len(self._positions)},
            )
            return True
        return False

    def _step_process_stops(self, market_data: pd.DataFrame) -> None:
        """Check trailing/time/partial-profit/correlation stops and execute exits.

        Evaluates every active stop condition for open positions and submits
        close orders for positions that trigger an exit.
        """
        # 2b. Stop manager checks on existing positions
        exit_signals_from_stops = []
        with self._positions_lock:
            positions_snapshot = list(self._positions.items())
        for pair_key, pos_info in positions_snapshot:
            try:
                holding_bars = pos_info.get("holding_bars", 0)
                pos_info["holding_bars"] = holding_bars + 1  # increment

                half_life = pos_info.get("half_life")
                entry_z = pos_info.get("entry_z", 0.0)
                current_z = pos_info.get("current_z", 0.0)
                unrealized_pnl_pct = pos_info.get("unrealized_pnl_pct", 0.0)

                # Trailing stop: exit if Z-score diverges too far from entry
                if self._trailing_stop:
                    ts_exit, ts_reason = self._trailing_stop.check(  # type: ignore[attr-defined]
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
                    pp_action = self._partial_profit.check(  # type: ignore[call-arg]
                        pair_key=pair_key,
                        unrealized_pnl_pct=unrealized_pnl_pct,  # type: ignore[call-arg]
                    )
                    if pp_action and pp_action.get("close_fraction", 0) > 0:
                        logger.info(
                            "live_trading_partial_profit",
                            pair=pair_key,
                            close_fraction=pp_action["close_fraction"],
                        )

                # Ongoing correlation monitor: exit if pair correlation degrades
                if self._correlation_monitor and market_data is not None:
                    syms = pair_key.split("_")
                    if len(syms) == 2 and syms[0] in market_data.columns and syms[1] in market_data.columns:
                        pa = float(market_data[syms[0]].iloc[-1])
                        pb = float(market_data[syms[1]].iloc[-1])
                        corr_alert = self._correlation_monitor.update(pair_key, pa, pb)
                        if corr_alert and corr_alert.get("hard_exit"):
                            exit_signals_from_stops.append(
                                (pair_key, f"correlation_degraded_{corr_alert['correlation']:.2f}")
                            )
                            continue
                        elif corr_alert and corr_alert.get("degraded"):
                            logger.warning(
                                "live_trading_correlation_warning", pair=pair_key, corr=corr_alert["correlation"]
                            )

            except Exception as exc:
                logger.error("live_trading_stop_check_error", pair=pair_key, error=str(exc)[:200])
                self._send_alert(
                    "ERROR",
                    f"Stop-check error: {pair_key}",
                    f"Exception during stop/correlation check: {exc}",
                    {"pair": pair_key, "iteration": self._iteration},
                )

        # Execute stop-triggered exits
        for pair_key, reason in exit_signals_from_stops:
            logger.info("live_trading_stop_exit", pair=pair_key, reason=reason)
            if pair_key in self._positions:
                # Route a close order through the execution router
                try:
                    if self._router:
                        from uuid import uuid4

                        from execution.base import Order, OrderSide

                        pos = self._positions[pair_key]
                        qty = pos.get("quantity", 0)
                        close_side = OrderSide.SELL if qty > 0 else OrderSide.BUY
                        close_order_id = str(uuid4())
                        close_order = Order(
                            order_id=close_order_id,
                            symbol=pair_key,
                            side=close_side,
                            quantity=abs(qty),
                            limit_price=None,
                            order_type="MARKET",
                        )
                        self._router.submit_order(close_order)
                        if self._audit_trail is not None:
                            from datetime import datetime as _dt_stop
                            from datetime import timezone as _tz_stop

                            from monitoring.events import EventType as _ET_stop
                            from monitoring.events import TradingEvent as _TE_stop

                            _exit_equity = (
                                self._metrics.equity if self._metrics.equity > 0 else self.config.initial_capital
                            )
                            _exit_event = _TE_stop(
                                event_type=_ET_stop.TRADE_EXIT,
                                timestamp=_dt_stop.now(_tz_stop.utc),
                                symbol_pair=pair_key,
                                position_size=abs(qty),
                                reason=reason,
                                risk_tier="stop",
                            )
                            try:
                                self._audit_trail.log_trade_event(
                                    _exit_event,
                                    current_equity=_exit_equity,
                                    event_id=close_order_id,
                                )
                            except Exception as _ae_stop:
                                logger.error(
                                    "audit_trail_exit_log_failed",
                                    pair=pair_key,
                                    error=str(_ae_stop)[:200],
                                )
                        # A-02: Mark pending_close instead of immediately removing.
                        # _process_fill_confirmations() will confirm and remove on the
                        # next tick once IBKR confirms the fill.
                        with self._positions_lock:
                            if pair_key in self._positions:
                                self._positions[pair_key]["status"] = "pending_close"
                                self._positions[pair_key]["close_order_id"] = close_order_id
                except Exception as exc:
                    logger.error("live_trading_stop_exit_failed", pair=pair_key, error=str(exc)[:200])
                    self._send_alert(
                        "ERROR",
                        f"Stop-exit order failed: {pair_key}",
                        f"Could not submit exit order for {pair_key}: {exc}",
                        {"pair": pair_key, "reason": reason},
                    )
                    # Position intentionnellement conservée : l'ordre de fermeture a échoué

    def _step_generate_signals(self, market_data: pd.DataFrame) -> list:
        """Generate alpha signals for all active pairs.

        Returns:
            List of signal objects produced by the SignalGenerator.
        """
        signals: list = []
        if self._active_pairs and self._signal_gen:
            try:
                signals = self._signal_gen.generate(
                    market_data=market_data,
                    active_pairs=self._active_pairs,
                    active_positions=self._positions,
                )
            except Exception as exc:
                logger.error("live_trading_signal_error", error=str(exc)[:200])
        return signals

    def _step_execute_signals(
        self, signals: list, market_data: pd.DataFrame, account_balance: float | None = None
    ) -> None:
        """Process each alpha signal through risk, sizing, and execution.

        Applies RiskFacade gate, PortfolioHedger diversification check, ML
        shadow gate, position sizing, and order routing for each signal.
        """
        # C-10: use caller-provided balance cache to avoid 1 broker call per signal
        _balance = (
            account_balance
            if account_balance is not None
            else (self._router.get_account_balance() if self._router else self.config.initial_capital)
        )
        for sig in signals:
            try:
                # 4a. Portfolio-level risk check via RiskFacade (unified kill-switch + drawdown gate)
                if self._risk_facade:
                    current_eq = _balance
                    # Estimate spread volatility from recent market_data for the pair legs
                    _vol = 0.0
                    _s1, _s2 = (sig.pair_key.split(":") + [""])[:2]
                    if _s1 in market_data.columns and _s2 in market_data.columns:
                        _spread = market_data[_s1] - market_data[_s2]
                        _vol = float(_spread.std()) if len(_spread) > 1 else 0.0
                    facade_ok, facade_reason = self._risk_facade.can_enter_trade(
                        symbol_pair=sig.pair_key,
                        position_size=0.0,
                        current_equity=current_eq,
                        volatility=_vol,
                    )
                    if not facade_ok:
                        logger.info("live_trading_signal_blocked_risk_facade", pair=sig.pair_key, reason=facade_reason)
                        continue

                # 4b. ML signal shadow mode (C-04)
                if self._ml_combiner is not None:
                    from config.settings import get_settings as _gs_tick

                    _sc = _gs_tick().signal_combiner
                    # Normalize z-score to [-1, 1] for the feature vector
                    _z_norm = float(max(-1.0, min(1.0, sig.z_score / 3.0)))
                    _features = {"zscore": _z_norm}
                    _ml_pred = self._ml_combiner.combine(_features, current_bar=self._iteration)
                    logger.info(
                        "ml_signal_shadow",
                        pair=sig.pair_key,
                        signal_direction=sig.side,
                        ml_direction=_ml_pred.direction,
                        ml_score=round(_ml_pred.composite_score, 3),
                        ml_confidence=round(_ml_pred.confidence, 3),
                        model_trained=_ml_pred.model_trained,
                        iteration=self._iteration,
                    )
                    # Gate mode (shadow_mode=False): block entry if ML disagrees
                    if (
                        not _sc.ml_combiner_shadow_mode
                        and _ml_pred.model_trained
                        and sig.side in ("long", "short")
                        and _ml_pred.direction != sig.side
                    ):
                        logger.info("ml_signal_gated", pair=sig.pair_key, signal=sig.side, ml=_ml_pred.direction)
                        continue

                # 4c. Size the position via allocator
                if self._allocator:
                    sized_order = self._allocator.size(  # type: ignore[attr-defined]
                        signal=sig,
                        capital=_balance,
                        max_positions=self.config.max_positions,
                        current_positions=self._positions,
                    )
                else:
                    sized_order = sig  # fallback: raw signal

                # 4d. Submit order through execution router
                if self._router and sized_order:
                    _exec_result = self._router.submit_order(sized_order)  # type: ignore[arg-type]
                    logger.info(
                        "live_trading_order_submitted",
                        pair=sig.pair_key,
                        fill_price=_exec_result.fill_price,
                        slippage_bps=_exec_result.slippage_bps,
                    )
                    if self._audit_trail is not None:
                        from datetime import timezone as _tz

                        from monitoring.events import EventType, TradingEvent

                        _entry_equity = (
                            self._metrics.equity if self._metrics.equity > 0 else self.config.initial_capital
                        )
                        _entry_event = TradingEvent(
                            event_type=EventType.TRADE_ENTRY,
                            timestamp=sig.timestamp.replace(tzinfo=_tz.utc)
                            if sig.timestamp.tzinfo is None
                            else sig.timestamp,
                            symbol_pair=sig.pair_key,
                            position_size=_exec_result.filled_qty or getattr(sized_order, "quantity", 0.0),
                            entry_price=_exec_result.fill_price or None,
                            z_score=sig.z_score,
                            hedge_ratio=getattr(sig, "hedge_ratio", None),
                            half_life=getattr(sig, "half_life", None),
                            momentum_score=getattr(sig, "momentum_score", None),
                            slippage_actual=_exec_result.slippage_bps,
                            reason=sig.side,
                            risk_tier=getattr(sig, "risk_tier", None),
                        )
                        try:
                            self._audit_trail.log_trade_event(
                                _entry_event,
                                current_equity=_entry_equity,
                                event_id=f"{sig.pair_key}_{sig.timestamp.isoformat()}",
                            )
                        except Exception as _ae:
                            logger.error(
                                "audit_trail_entry_log_failed",
                                pair=sig.pair_key,
                                error=str(_ae)[:200],
                            )

            except Exception as exc:
                logger.error(
                    "live_trading_signal_processing_error",
                    pair=getattr(sig, "pair_key", "unknown"),
                    error=str(exc)[:200],
                )
                self._send_alert(
                    "ERROR",
                    f"Order processing error: {getattr(sig, 'pair_key', '?')}",
                    f"Failed to process signal/submit order: {exc}",
                    {"pair": getattr(sig, "pair_key", "unknown"), "iteration": self._iteration},
                )

    def _step_periodic_tasks(self, market_data: pd.DataFrame, signals: list) -> None:
        """Execute periodic housekeeping tasks at end of each tick.

        Includes: tick completion logging, portfolio beta check, ML state
        persist, PSI drift detection, and hedge-ratio re-estimation.
        """
        logger.debug(
            "live_trading_tick_complete",
            iteration=self._iteration,
            active_pairs=len(self._active_pairs),
            signals_generated=len(signals),
            open_positions=len(self._positions),
        )

        # C-04: Persist ML combiner state after each tick (every 100 ticks to limit I/O)
        # C-13: submit save() to the alert executor (background thread) to avoid blocking the tick
        if self._ml_combiner is not None and self._iteration % 100 == 0:
            from pathlib import Path as _Path

            _save_dest = _Path("data/models") / "ml_combiner_live.joblib"
            self._alert_executor.submit(self._ml_combiner.save, _save_dest)

        # C-09: PSI drift check every 252 bars
        if self._ml_combiner is not None and self._iteration % 252 == 0:
            drift_report = self._ml_combiner.check_drift(self._iteration)
            if drift_report is not None and drift_report.has_critical_drift:
                self._send_alert(
                    "WARNING",
                    "ML feature drift detected",
                    f"PSI critical: {drift_report.critical_features}",
                    {"overall_psi": round(drift_report.overall_psi, 4), "critical": drift_report.critical_features},
                )

        # C-07: Periodic hedge-ratio re-estimation (every retraining_interval_bars bars)
        if self._retraining_task is not None and self._active_pairs and market_data is not None:
            _sym_pairs = [(t[0], t[1]) for t in self._active_pairs if len(t) >= 2]
            _regime_det = getattr(self._signal_gen, "regime_detector", None) if self._signal_gen else None
            self._retraining_task.maybe_run(
                current_bar=self._iteration,
                price_data=market_data,
                active_pairs=_sym_pairs,
                kill_switch=self._kill_switch,
                regime_detector=_regime_det,  # C-10: adaptive frequency by regime
            )

    def _update_metrics(self, signals: list, equity: float | None = None) -> None:
        """Refresh SystemMetrics snapshot at end of each tick."""
        try:
            # C-10: reuse tick-level balance cache when provided to avoid extra broker call
            equity = (
                equity
                if equity is not None
                else (self._router.get_account_balance() if self._router else self.config.initial_capital)
            )
            # Fallback: if router returns 0 (paper engine has no balance tracker),
            # keep initial_capital as equity to avoid false -100% PnL display.
            if equity <= 0:
                equity = self.config.initial_capital
            self._metrics.equity = equity
            # Build equity history for sparkline (keep last 60 ticks)
            self._equity_history.append(equity)
            if len(self._equity_history) > 60:
                self._equity_history = self._equity_history[-60:]
            self._metrics.trades_today += len(signals)
            self._metrics.trades_total += len(signals)
            # Max drawdown (simple high-water mark tracking)
            if not hasattr(self, "_hw_equity"):
                self._hw_equity = equity
            self._hw_equity = max(self._hw_equity, equity)
            if self._hw_equity > 0:
                dd = (self._hw_equity - equity) / self._hw_equity
                self._metrics.max_drawdown = max(self._metrics.max_drawdown, dd)
        except Exception as exc:
            logger.debug("metrics_update_failed", error=str(exc)[:100])

    @property
    def metrics(self) -> SystemMetrics:
        """Current metrics snapshot (for API / dashboard consumption)."""
        return self._metrics

    def _fetch_market_data(self) -> pd.DataFrame | None:
        """Fetch recent price data for all symbols in the universe.

        Returns:
            DataFrame with columns = symbols, rows = time bars.
        """
        try:
            from data.loader import load_price_data

            symbols = self.config.symbols
            if self._universe_mgr:
                active = self._universe_mgr.get_active_symbols()
                if active:
                    symbols = active
            lookback = getattr(self, "_lookback", 252)
            df = load_price_data(symbols=symbols, limit=lookback)
            # C-09: freshness guard — warn if any symbol's latest bar is stale (> 10 min)
            _MAX_DATA_LAG = timedelta(minutes=10)
            if df is not None and not df.empty:
                now = datetime.now(timezone.utc)
                for sym in df.columns:
                    col = df[sym].dropna()
                    if col.empty:
                        continue
                    last_ts = col.index[-1]
                    if hasattr(last_ts, "tzinfo") and last_ts.tzinfo is None:
                        last_ts = last_ts.tz_localize("UTC")
                    lag = now - last_ts
                    if lag > _MAX_DATA_LAG:
                        logger.warning(
                            "market_data_stale",
                            symbol=sym,
                            lag_minutes=round(lag.total_seconds() / 60, 1),
                        )
            # Track data load stats for dashboard
            self._data_symbols_total = len(symbols)
            if df is not None and not df.empty:
                self._data_symbols_loaded = len(df.columns)
                self._data_load_rows = len(df)
            else:
                self._data_symbols_loaded = 0
                self._data_load_rows = 0
            self._data_load_at = datetime.now()
            return df
        except Exception as exc:
            logger.error("live_trading_data_fetch_error", error=str(exc)[:200])
            self._data_symbols_loaded = 0
            self._data_load_at = datetime.now()
            return None

    # ------------------------------------------------------------------
    # Pair discovery
    # ------------------------------------------------------------------

    def _maybe_rediscover_pairs(self) -> pd.DataFrame | None:
        """Re-discover cointegrated pairs if enough time has elapsed.

        Uses ``PairTradingStrategy.find_cointegrated_pairs()`` as the
        canonical pair discovery path (same as backtests and main.py)
        to keep all pipelines consistent.

        Returns:
            The fetched market data DataFrame if discovery was triggered and
            data was loaded successfully (so ``_tick()`` can reuse it without
            a second IBKR round-trip), or ``None`` otherwise.
        """
        now = datetime.now()
        interval = timedelta(hours=self.config.pair_rediscovery_hours)

        if self._last_discovery is not None and (now - self._last_discovery) < interval:
            return None

        logger.info("live_trading_pair_rediscovery_start")

        try:
            market_data = self._fetch_market_data()
            if market_data is None or market_data.empty:
                logger.warning("live_trading_pair_rediscovery_no_data")
                return None

            from config.settings import get_settings
            from strategies.pair_trading import PairTradingStrategy

            strategy = PairTradingStrategy()
            settings = get_settings()
            lookback = getattr(settings.strategy, "lookback_window", 120)
            pairs = strategy.find_cointegrated_pairs(market_data, lookback)
            self._active_pairs = pairs
            self._last_discovery = now
            logger.info(
                "live_trading_pair_rediscovery_complete",
                pairs=len(self._active_pairs),
            )
            return market_data  # C-02: reused by _tick() — avoids second fetch
        except Exception as exc:
            logger.error(
                "live_trading_pair_rediscovery_failed",
                error=str(exc)[:200],
            )
            # Keep existing pairs on failure
            self._last_discovery = now  # avoid tight retry loop
            return None

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
            with self._positions_lock:
                positions_to_close = list(self._positions.items())
            for symbol, qty in positions_to_close:
                try:
                    from uuid import uuid4

                    from execution.base import Order, OrderSide

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
        if hasattr(self, "_shutdown_mgr") and self._shutdown_mgr:
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
