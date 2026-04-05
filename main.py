"""
EDGECORE main entry point.

Modes:
- backtest: Historical performance analysis
- paper: Sandbox trading (no real money)
- live: Production trading (EXTREME CAUTION)
"""

import argparse
import os
import sys
import threading
import time
from datetime import datetime
from typing import Any, Callable

import pandas as pd
from structlog import get_logger

from backtests.runner import BacktestRunner
from common.context_memory import ContextMemory
from common.errors import DataError, ErrorCategory
from config.settings import get_settings
from data.delisting_guard import DelistingGuard
from data.liquidity_filter import LiquidityFilter
from data.loader import DataLoader
from data.validators import OHLCVValidator
from strategies.pair_trading import PairTradingStrategy
from risk.engine import RiskEngine
from execution.ibkr_engine import IBKRExecutionEngine
from execution.paper_execution import PaperExecutionEngine
from execution.base import Order, OrderSide
from execution.ibkr_engine import IBKRExecutionEngine
from execution.order_lifecycle_integration import OrderLifecycleIntegration
from execution.paper_execution import PaperExecutionEngine
from execution.reconciler import BrokerReconciler
from execution.shutdown_manager import ShutdownManager
from monitoring.api import initialize_dashboard_api
from monitoring.dashboard import DashboardGenerator
from monitoring.email_alerter import EmailAlerter
from monitoring.logging_config import setup_logging as setup_production_logging
from monitoring.slack_alerter import SlackAlerter
from portfolio_engine.allocator import PortfolioAllocator, SizingMethod
from risk.engine import RiskEngine
from strategies.pair_trading import PairTradingStrategy

# Load .env variables (SMTP, Slack, IBKR, etc.)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed ÔÇö rely on system env vars

# Use production-grade structured logging with rotation and JSON output
try:
    setup_production_logging(log_dir="logs", json_format=True)
except Exception:
    pass  # fallback: structlog works without explicit setup
logger = get_logger("main")

# --- HOOKS AI ORCHESTRATION (BP-01) ---
# Permet d'injecter dynamiquement des hooks d'orchestration AI (HyperAgents, fallback, etc.)
AI_HOOKS: list[Callable] = []


def register_ai_hook(hook: Callable):
    """Ajoute un hook d'orchestration AI à la pipeline principale."""
    AI_HOOKS.append(hook)
    logger.info("ai_hook_registered", hook=str(hook))


# Appel des hooks à chaque démarrage de main()
def _run_ai_hooks(context: dict):
    for hook in AI_HOOKS:
        try:
            hook(context)
            logger.info("ai_hook_executed", hook=str(hook))
        except Exception as e:
            logger.error("ai_hook_failed", hook=str(hook), error=str(e))


def _load_market_data_for_symbols(symbols: list[str], loader: DataLoader, settings: Any) -> dict[str, pd.Series]:
    """
    Load market data for all trading symbols with unified error handling.

    Wrapped with @with_error_handling to provide automatic retries
    for transient errors and exponential backoff for API throttling.

    Args:
        symbols: List of trading symbols (e.g., ['AAPL', 'MSFT'])
        loader: DataLoader instance
        settings: Settings configuration

    Returns:
        Dictionary mapping symbol to price Series

    Raises:
        DataError: If no valid price data can be loaded
    """
    prices = {}
    load_errors = []

    for symbol in symbols:
        try:
            df = loader.load_ibkr_data(symbol, timeframe="1h", limit=100)

            if df is not None and len(df) > 0:
                # Validate data quality including staleness
                validation = OHLCVValidator(symbol).validate(
                    df, max_age_hours=settings.trading.data_max_age_hours, raise_on_error=False
                )

                if not validation.is_valid:
                    logger.error("data_validation_failed", symbol=symbol, errors=validation.errors)
                    load_errors.append(symbol)
                    continue

                prices[symbol] = df["close"]
                logger.info("data_loaded", symbol=symbol, rows=len(df))
            else:
                logger.warning("empty_data_returned", symbol=symbol)
                load_errors.append(symbol)

        except Exception as e:
            logger.error("data_load_failed_for_symbol", symbol=symbol, error=str(e))
            load_errors.append(symbol)

    if not prices:
        error_msg = f"Failed to load any valid price data. Failed symbols: {load_errors}"
        raise DataError(error_msg, original_error=None)

    if load_errors:
        logger.warning(
            "partial_data_load_failure",
            loaded_symbols=list(prices.keys()),
            failed_symbols=load_errors,
            partial_load=True,
        )

    return prices


def _close_all_positions(risk_engine: RiskEngine, execution_engine, positions_to_close: dict) -> None:
    """
    Close all open positions gracefully.

    First cancels ALL pending orders at the broker to prevent
    stale limit orders from filling after a kill-switch halt.
    Then submits market/limit close orders for each open position.

    Args:
        risk_engine: Risk engine with position tracking
        execution_engine: Execution engine for order submission
        positions_to_close: Dict of positions to close
    """
    # RISK-1: Cancel all pending orders at broker FIRST
    if hasattr(execution_engine, "cancel_all_pending"):
        try:
            cancelled = execution_engine.cancel_all_pending()
            logger.warning("pending_orders_cancelled_on_halt", count=cancelled)
        except Exception as e:
            logger.error("cancel_pending_orders_failed", error=str(e))

    if not positions_to_close:
        logger.info("no_positions_to_close")
        return

    logger.warning(
        "closing_all_positions_on_shutdown", count=len(positions_to_close), symbols=list(positions_to_close.keys())
    )

    for symbol_pair, position in list(positions_to_close.items()):
        try:
            # Create market close order (at current market, no limit)
            order = Order(
                order_id=f"shutdown_close_{datetime.now().timestamp()}_{symbol_pair}",
                symbol=symbol_pair,
                side=OrderSide.SELL if position.side == "long" else OrderSide.BUY,
                quantity=position.quantity,
                limit_price=position.marked_price or position.entry_price,  # Use marked price if available
            )

            try:
                order_id = execution_engine.submit_order(order)
                logger.info(
                    "shutdown_position_close_submitted",
                    symbol=symbol_pair,
                    order_id=order_id,
                    quantity=position.quantity,
                    side=order.side,
                )
                # Notify risk engine so P&L tracking stays consistent on shutdown
                exit_price = float(position.marked_price or position.entry_price or 0.0)
                risk_engine.register_exit(symbol_pair, exit_price=exit_price, pnl=0.0)
            except Exception as e:
                logger.error("shutdown_position_close_failed", symbol=symbol_pair, error=str(e))
        except Exception as e:
            logger.error("shutdown_position_preparation_failed", symbol=symbol_pair, error=str(e))

    logger.info("all_positions_close_orders_submitted")


def run_paper_trading(symbols, settings, slack_alerter=None, email_alerter=None, mode="paper"):
    """
    Paper trading in sandbox mode (simulated trading with real market data).

    Args:
        symbols: List of trading pairs to trade
        settings: Global settings object
        slack_alerter: Optional SlackAlerter for sending Slack alerts
        email_alerter: Optional EmailAlerter for sending email alerts
        mode: Trading mode ("paper" or "live")
    """
    logger.info("paper_trading_mode_starting", symbols=symbols)

    # Filter symbols through DelistingGuard and LiquidityFilter
    delist_guard = DelistingGuard()
    liq_filter = LiquidityFilter()
    safe_symbols = []
    for sym in symbols:
        if not delist_guard.is_safe(sym):
            logger.warning("symbol_delisting_risk", symbol=sym)
            continue
        safe_symbols.append(sym)
    # Apply liquidity filter (non-strict: accept if no volume data available)
    if safe_symbols:
        safe_symbols = liq_filter.filter_symbols(safe_symbols)
    if safe_symbols:
        logger.info("symbols_after_filtering", original=len(symbols), filtered=len(safe_symbols))
        symbols = safe_symbols

    # Validate sandbox mode
    if not settings.execution.use_sandbox:
        logger.error("sandbox_not_enabled")
        raise ValueError("Paper trading requires sandbox mode. Set use_sandbox=True in config")

    if settings.execution.engine != "ibkr":
        logger.error("invalid_engine_for_paper_trading", engine=settings.execution.engine)
        raise ValueError("Paper trading requires ibkr engine")

    # Initialize trading components
    try:
        loader = DataLoader()
        strategy = PairTradingStrategy()
        risk_engine = RiskEngine(initial_equity=settings.execution.initial_capital)

        # Wire sector map for concentration enforcement
        # Sector classification for US universe (mirrors config.yaml groupings)
        _SECTOR_MAP = {
            # Technology
            "AAPL": "Tech",
            "MSFT": "Tech",
            "GOOGL": "Tech",
            "META": "Tech",
            "NVDA": "Tech",
            "AMD": "Tech",
            "INTC": "Tech",
            "AVGO": "Tech",
            "CRM": "Tech",
            "ADBE": "Tech",
            # Financials
            "JPM": "Financials",
            "BAC": "Financials",
            "GS": "Financials",
            "MS": "Financials",
            "WFC": "Financials",
            "C": "Financials",
            "BLK": "Financials",
            "SCHW": "Financials",
            # Healthcare
            "JNJ": "Healthcare",
            "PFE": "Healthcare",
            "UNH": "Healthcare",
            "MRK": "Healthcare",
            "ABBV": "Healthcare",
            "LLY": "Healthcare",
            "TMO": "Healthcare",
            "ABT": "Healthcare",
            # Consumer Staples
            "KO": "Consumer",
            "PEP": "Consumer",
            "PG": "Consumer",
            "CL": "Consumer",
            "WMT": "Consumer",
            "COST": "Consumer",
            # Energy
            "XOM": "Energy",
            "CVX": "Energy",
            "COP": "Energy",
            "SLB": "Energy",
            "EOG": "Energy",
            # Industrials
            "CAT": "Industrials",
            "DE": "Industrials",
            "HON": "Industrials",
            "GE": "Industrials",
            "RTX": "Industrials",
            "LMT": "Industrials",
            # Utilities
            "NEE": "Utilities",
            "DUK": "Utilities",
            "SO": "Utilities",
        }
        risk_engine.sector_map = _SECTOR_MAP

        # Use PaperExecutionEngine for realistic paper trading, IBKRExecutionEngine for live
        if mode == "paper":
            execution_engine = PaperExecutionEngine(
                slippage_model=settings.costs.slippage_model,
                fixed_bps=settings.costs.slippage_bps,
                commission_pct=settings.costs.commission_pct
                * 100,  # CostConfig stores as fraction, PaperEngine expects %
            )
        else:
            execution_engine = IBKRExecutionEngine()

        logger.info(
            "paper_trading_initialized", sandbox=settings.execution.use_sandbox, engine=settings.execution.engine
        )

        # Initialize portfolio allocator for dynamic position sizing
        allocator = PortfolioAllocator(
            equity=settings.execution.initial_capital,
            max_pairs=getattr(settings.risk, "max_concurrent_positions", 10),
            max_allocation_pct=settings.trading.max_allocation_pct,
            sizing_method=SizingMethod.VOLATILITY_INVERSE,
        )

        # HOTFIX 1.1: Crash recovery - restore persisted state
        logger.info("attempting_state_recovery_from_audit_trail")
        try:
            recovered_positions = risk_engine.load_from_audit_trail()
            if recovered_positions:
                logger.warning(
                    "positions_recovered_from_previous_session",
                    count=len(recovered_positions),
                    symbols=list(recovered_positions.keys()),
                )
                # Require manual verification or SKIP_CRASH_RECOVERY=true to continue
                if os.getenv("SKIP_CRASH_RECOVERY") != "true":
                    print(f"\n[!] CRASH RECOVERY: {len(recovered_positions)} positions recovered")
                    print("   Symbols:", ", ".join(recovered_positions.keys()))
                    print("   Verify positions match your exchange account before continuing")
                    response = input("   Continue with recovered positions? (yes/no): ")
                    if response.lower() != "yes":
                        logger.warning("crash_recovery_aborted_by_user")
                        raise ValueError("Crash recovery aborted. Manual intervention required.")
        except Exception as e:
            if "Crash recovery aborted" in str(e):
                raise
            logger.warning("recovered_state_loading_skipped", error=str(e))

    except Exception as e:
        logger.error("paper_trading_initialization_failed", error=str(e))
        raise

    # Initialize dashboard and Flask API for real-time monitoring
    try:
        dashboard = DashboardGenerator(risk_engine=risk_engine, execution_engine=execution_engine, mode=mode)
        dashboard_app = initialize_dashboard_api(dashboard)

        # Start Flask API server in background thread
        api_host = os.getenv("DASHBOARD_API_HOST", "127.0.0.1")
        api_port = int(os.getenv("DASHBOARD_API_PORT", "5000"))
        api_thread = threading.Thread(
            target=lambda: dashboard_app.run(host=api_host, port=api_port, debug=False, use_reloader=False), daemon=True
        )
        api_thread.start()
        logger.info("dashboard_api_started", host=api_host, port=api_port)
    except Exception as e:
        logger.warning("dashboard_api_initialization_failed", error=str(e))
        # Continue anyway - API is optional

    # Initialize broker reconciler (FEATURE 4: Reconciliation)
    reconciler = None
    try:
        reconciler = BrokerReconciler(
            internal_equity=settings.execution.initial_capital,
            internal_positions={},  # Will be populated as trades enter
            equity_tolerance_pct=settings.trading.equity_tolerance_pct,
        )

        # First reconciliation at startup
        broker_equity = execution_engine.get_account_balance()

        # Skip reconciliation if broker returns 0 or invalid equity (paper trading)
        if broker_equity > 0:
            equity_ok, equity_diff_pct = reconciler.reconcile_equity(broker_equity)

            if not equity_ok:
                logger.critical(
                    "STARTUP_EQUITY_MISMATCH",
                    expected=settings.execution.initial_capital,
                    actual=broker_equity,
                    diff_pct=equity_diff_pct,
                )
                if os.getenv("SKIP_RECONCILIATION_CHECK") != "true":
                    raise ValueError(
                        f"Equity mismatch at startup: {equity_diff_pct:.4f}% "
                        f"(expected ${settings.execution.initial_capital}, got ${broker_equity}). "
                        f"Manual review required or set SKIP_RECONCILIATION_CHECK=true to override."
                    )
            else:
                logger.info("startup_reconciliation_passed", equity_match=True)
        else:
            logger.warning(
                "broker_returned_zero_equity",
                broker_equity=broker_equity,
                note="Skipping reconciliation - likely test/paper trading mode",
            )

    except Exception as e:
        logger.error("startup_reconciliation_failed", error=str(e))
        if os.getenv("SKIP_RECONCILIATION_CHECK") != "true":
            raise

    # Initialize global shutdown manager (FEATURE 2: Kill-Switch)
    shutdown_mgr = ShutdownManager()

    # Initialize order lifecycle manager (FEATURE 3: Order Timeout Protection)
    order_mgr = OrderLifecycleIntegration(
        execution_engine=execution_engine, timeout_seconds=settings.execution.timeout_seconds
    )

    # Main trading loop
    attempt = 0
    max_attempts = settings.trading.max_loop_iterations
    consecutive_errors = 0
    max_consecutive_errors = settings.trading.max_consecutive_errors

    try:
        while attempt < max_attempts:
            attempt += 1

            # FEATURE 2: Check for shutdown request (signal or file-based)
            if shutdown_mgr.is_shutdown_requested():
                shutdown_reason = shutdown_mgr.get_shutdown_reason() or "unknown reason"
                logger.warning("shutdown_signal_detected", reason=shutdown_reason, iteration=attempt)
                # Alert: kill-switch / shutdown
                for _alerter in (email_alerter, slack_alerter):
                    if _alerter:
                        try:
                            _alerter.send_alert(
                                level="CRITICAL",
                                title="Trading shutdown triggered",
                                message=f"Shutdown reason: {shutdown_reason} at iteration {attempt}",
                                data={"iteration": attempt, "reason": shutdown_reason},
                            )
                        except Exception:
                            pass
                # Close all open positions before exiting
                _close_all_positions(risk_engine, execution_engine, risk_engine.positions)
                break

            logger.info("paper_trading_loop_iteration", iteration=attempt, max=max_attempts)

            # FEATURE 4: Periodic reconciliation (every 10 iterations)
            if reconciler and attempt % 10 == 0:
                try:
                    broker_equity = execution_engine.get_account_balance()
                    equity_ok, equity_diff_pct = reconciler.reconcile_equity(broker_equity)
                    if not equity_ok and equity_diff_pct > settings.trading.reconciliation_divergence_pct:
                        logger.warning(
                            "periodic_reconciliation_divergence",
                            iteration=attempt,
                            diff_pct=equity_diff_pct,
                            expected=reconciler.internal_equity,
                            actual=broker_equity,
                        )
                        # Alert: reconciliation divergence
                        for _alerter in (email_alerter, slack_alerter):
                            if _alerter:
                                try:
                                    _alerter.send_alert(
                                        level="ERROR",
                                        title="Reconciliation divergence",
                                        message=(
                                            f"Equity divergence {equity_diff_pct:.4f}% at iteration {attempt}. "
                                            f"Expected ${reconciler.internal_equity:.2f}, got ${broker_equity:.2f}."
                                        ),
                                        data={"iteration": attempt, "diff_pct": equity_diff_pct},
                                    )
                                except Exception:
                                    pass
                except Exception as e:
                    logger.warning("periodic_reconciliation_failed", error=str(e))

            # Load latest market data with PHASE 2 error handling
            try:
                prices = _load_market_data_for_symbols(symbols, loader, settings)
                logger.info("market_data_load_successful", symbols=list(prices.keys()))

                # Create price dataframe
                prices_df = pd.DataFrame(prices)
                logger.info("price_data_ready", symbols=list(prices.keys()), rows=len(prices_df))

                # FEATURE 5: Update position prices and check for stop-losses
                for symbol, position in list(risk_engine.positions.items()):
                    try:
                        if symbol in prices_df.columns:
                            current_market_price = prices_df[symbol].iloc[-1]
                            position.current_price = current_market_price
                            position.marked_price = current_market_price
                    except (KeyError, IndexError):
                        logger.warning("position_price_update_failed", symbol=symbol)

                # Check for positions hitting stop-loss
                stopped_positions = risk_engine.check_position_stops()
                if stopped_positions:
                    for stopped_pos in stopped_positions:
                        logger.warning(
                            "position_stopped_out",
                            symbol=stopped_pos["symbol"],
                            reason=stopped_pos["reason"],
                            pnl_pct=stopped_pos["pnl_pct"],
                        )
                        try:
                            # Create close order
                            close_order = Order(
                                order_id=f"stop_loss_{datetime.now().timestamp()}_{stopped_pos['symbol']}",
                                symbol=stopped_pos["symbol"],
                                side=OrderSide.SELL if stopped_pos["position_object"].side == "long" else OrderSide.BUY,
                                quantity=stopped_pos["quantity"],
                                limit_price=stopped_pos["current_price"],
                            )

                            order_id = execution_engine.submit_order(close_order)
                            logger.info(
                                "stop_loss_order_submitted",
                                order_id=order_id,
                                symbol=stopped_pos["symbol"],
                                reason=stopped_pos["reason"],
                            )

                            # Remove from risk engine positions
                            del risk_engine.positions[stopped_pos["symbol"]]

                        except Exception as e:
                            logger.error(
                                "stop_loss_order_submission_failed", symbol=stopped_pos["symbol"], error=str(e)
                            )

                # Generate trading signals
                signals = strategy.generate_signals(prices_df)
                logger.info("signals_generated", count=len(signals))

                # Process each signal
                for i, signal in enumerate(signals):
                    logger.info(
                        "processing_signal",
                        signal_num=i + 1,
                        total=len(signals),
                        pair=signal.symbol_pair,
                        side=signal.side,
                    )

                    try:
                        # Get current account balance
                        equity = execution_engine.get_account_balance()
                        logger.info("account_balance_check", equity=equity)

                        # Compute realized spread volatility for this pair
                        pair_syms = signal.symbol_pair.split("_")
                        pair_vol = settings.trading.fallback_spread_vol  # fallback
                        if len(pair_syms) == 2:
                            s1, s2 = pair_syms
                            if s1 in prices_df.columns and s2 in prices_df.columns:
                                spread_ret = (prices_df[s1] - prices_df[s2]).pct_change().dropna()
                                if len(spread_ret) >= 10:
                                    pair_vol = float(spread_ret.std())
                                    pair_vol = max(pair_vol, 1e-6)  # floor

                        # Dynamic position sizing via PortfolioAllocator
                        allocator.update_equity(equity if equity > 0 else settings.execution.initial_capital)
                        alloc = allocator.allocate(
                            pair_key=signal.symbol_pair,
                            signal_strength=signal.strength,
                            spread_vol=pair_vol,
                        )

                        # Check if we can enter this trade
                        can_enter, reason = risk_engine.can_enter_trade(
                            symbol_pair=signal.symbol_pair,
                            position_size=alloc.notional,
                            current_equity=equity,
                            volatility=pair_vol,
                        )

                        if not can_enter:
                            allocator.release(signal.symbol_pair)
                            logger.warning("trade_rejected_by_risk", pair=signal.symbol_pair, reason=reason)
                            continue

                        # Get current price
                        try:
                            current_price = prices_df[signal.symbol_pair].iloc[-1]
                        except (KeyError, IndexError):
                            allocator.release(signal.symbol_pair)
                            logger.warning("price_not_available", pair=signal.symbol_pair)
                            continue

                        # Compute quantity from allocated notional
                        order_quantity = (
                            max(settings.trading.min_order_quantity, round(alloc.notional / current_price, 0))
                            if current_price > 0
                            else settings.trading.min_order_quantity
                        )

                        # Create order
                        order = Order(
                            order_id=f"paper_{datetime.now().timestamp()}_{signal.symbol_pair}",
                            symbol=signal.symbol_pair,
                            side=OrderSide.BUY if signal.side == "long" else OrderSide.SELL,
                            quantity=order_quantity,
                            limit_price=current_price
                            * (1.0 - settings.trading.limit_price_offset_pct),  # configurable offset
                        )

                        # Submit order
                        try:
                            order_id = execution_engine.submit_order(order)
                            logger.info(
                                "paper_order_submitted",
                                order_id=order_id,
                                pair=signal.symbol_pair,
                                side=signal.side,
                                quantity=order.quantity,
                                price=order.limit_price,
                            )

                            # FEATURE 3: Track order for timeout protection
                            order_mgr.track_order(
                                order_id=order_id,
                                symbol=signal.symbol_pair,
                                quantity=order.quantity,
                                price=float(order.limit_price) if order.limit_price is not None else 0.0,
                            )

                        except Exception as e:
                            logger.error("order_submission_failed", pair=signal.symbol_pair, error=str(e))
                            # Alert: order submission failure
                            for _alerter in (email_alerter, slack_alerter):
                                if _alerter:
                                    try:
                                        _alerter.send_alert(
                                            level="ERROR",
                                            title=f"Order failed: {signal.symbol_pair}",
                                            message=f"Order submission failed: {e}",
                                            data={"pair": signal.symbol_pair, "iteration": attempt},
                                        )
                                    except Exception:
                                        pass

                    except Exception as e:
                        logger.error("signal_processing_error", pair=signal.symbol_pair, error=str(e))
                        continue

                # Log summary and wait before next iteration
                logger.info(
                    "paper_trading_iteration_complete",
                    attempt=attempt,
                    signals_processed=len(signals),
                    next_iteration_in_seconds=settings.execution.paper_trading_loop_interval_seconds,
                )

                # Reset consecutive error counter on successful iteration
                consecutive_errors = 0

                # FEATURE 3: Check for timed-out orders and cancel them
                try:
                    timed_out_count = order_mgr.process_timeouts()
                    if timed_out_count > 0:
                        logger.warning("order_timeouts_detected_and_cancelled", timed_out_count=timed_out_count)
                except Exception as e:
                    logger.error("order_timeout_processing_error", error=str(e))

                # Sleep before next iteration (configurable: dev=10s, prod=3600s)
                time.sleep(settings.execution.paper_trading_loop_interval_seconds)

            except KeyboardInterrupt:
                logger.info("paper_trading_interrupted_by_user")
                break
            except DataError as e:
                # PHASE 2: Handle data errors with category-specific logic
                consecutive_errors += 1

                if e.category == ErrorCategory.TRANSIENT:
                    # Transient errors (network): retry immediately next iteration
                    logger.warning(
                        "data_error_transient", message=e.message, attempt=attempt, will_retry="next iteration"
                    )
                    time.sleep(1)  # Brief delay before retry

                elif e.category == ErrorCategory.RETRYABLE:
                    # Retryable errors (API throttle): exponential backoff
                    backoff_seconds = min(2**consecutive_errors, 60)
                    logger.warning(
                        "data_error_retryable", message=e.message, attempt=attempt, backoff_seconds=backoff_seconds
                    )
                    time.sleep(backoff_seconds)

                else:
                    # Non-retryable or fatal: stop immediately
                    logger.critical("data_error_fatal_or_non_retryable", message=e.message)
                    # Alert: fatal data error
                    for _alerter in (email_alerter, slack_alerter):
                        if _alerter:
                            try:
                                _alerter.send_alert(
                                    level="CRITICAL",
                                    title="Fatal data error",
                                    message=f"Non-retryable data error: {e.message}",
                                    data={"iteration": attempt},
                                )
                            except Exception:
                                pass
                    break

                # Break if too many errors
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("data_errors_max_consecutive_exceeded", max_allowed=max_consecutive_errors)
                    break

            except Exception as e:
                consecutive_errors += 1
                # Exponential backoff: 2^n seconds, capped at 60s
                backoff_seconds = min(2**consecutive_errors, 60)
                logger.error(
                    "paper_trading_loop_error",
                    attempt=attempt,
                    consecutive_errors=consecutive_errors,
                    backoff_seconds=backoff_seconds,
                    error=str(e),
                )

                # Break loop if too many consecutive errors
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("paper_trading_max_consecutive_errors_exceeded", max_allowed=max_consecutive_errors)
                    # Alert: max consecutive errors
                    for _alerter in (email_alerter, slack_alerter):
                        if _alerter:
                            try:
                                _alerter.send_alert(
                                    level="CRITICAL",
                                    title="Max consecutive errors exceeded",
                                    message=(
                                        f"Trading loop hit {consecutive_errors} consecutive errors. "
                                        f"Loop terminated at iteration {attempt}."
                                    ),
                                    data={"consecutive_errors": consecutive_errors, "iteration": attempt},
                                )
                            except Exception:
                                pass
                    break

                # Apply exponential backoff before retry
                logger.info("paper_trading_backoff", seconds=backoff_seconds)
                time.sleep(backoff_seconds)

        logger.info("paper_trading_completed", total_iterations=attempt)
        print("\n[OK] Paper trading session completed\n")

    except KeyboardInterrupt:
        logger.info("paper_trading_stopped_by_user")
        print("\n[OK] Paper trading stopped\n")
    finally:
        # Cleanup on exit (FEATURE 2: Remove trading_enabled marker)
        try:
            shutdown_mgr.cleanup()
        except Exception as e:
            logger.error("shutdown_cleanup_failed", error=str(e))

        # Save final equity snapshot for crash recovery
        try:
            risk_engine.save_equity_snapshot()
            logger.info("final_equity_snapshot_saved", equity=risk_engine.current_equity)
        except Exception as e:
            logger.warning("final_snapshot_save_skipped", error=str(e))


def run_live_trading(symbols, settings, slack_alerter=None, email_alerter=None):
    """
    Live trading on real exchange with real money.

    EXTREME CAUTION: This trades with real money!

    Args:
        symbols: List of trading pairs to trade
        settings: Global settings object
        slack_alerter: Optional SlackAlerter for sending Slack alerts
        email_alerter: Optional EmailAlerter for sending email alerts
    """

    # Safety check: live trading must be explicitly enabled
    if os.getenv("ENABLE_LIVE_TRADING") != "true":
        logger.error("LIVE_TRADING_NOT_ENABLED")
        print("\n[ERROR] Live trading is disabled by default.")
        print("To enable, set: export ENABLE_LIVE_TRADING=true")
        print("Then restart the system.\n")
        raise ValueError("Live trading requires ENABLE_LIVE_TRADING=true env var")

    # Safety validation
    if settings.env != "prod":
        logger.warning("not_production_environment", env=settings.env)

    if settings.execution.use_sandbox:
        logger.error("live_mode_with_sandbox_enabled")
        raise ValueError("Live trading cannot run with sandbox mode enabled")

    if settings.execution.engine != "ibkr":
        logger.error("invalid_engine_for_live_trading", engine=settings.execution.engine)
        raise ValueError("Live trading requires ibkr engine")

    # Display warning and require explicit confirmation
    print("\n" + "=" * 70)
    print("[!] LIVE TRADING ALERT - REAL MONEY AT RISK [!]")
    print("=" * 70)
    print("You are about to start LIVE TRADING with REAL MONEY")
    print(f"Trading Pairs: {', '.join(symbols)}")
    print(f"Engine: {settings.execution.engine}")
    print(f"Risk per trade: {settings.risk.max_risk_per_trade * 100:.2f}% of equity")
    print(f"Daily loss limit: {settings.risk.max_daily_loss_pct * 100:.2f}%")
    print(f"Max concurrent positions: {settings.risk.max_concurrent_positions}")
    print("=" * 70)
    print("\nThis action is IRREVERSIBLE. Losses may occur.")
    print("=" * 70 + "\n")

    # Require explicit confirmation
    confirm = input("Type 'I UNDERSTAND THE RISKS' to proceed with live trading: ").strip()

    if confirm != "I UNDERSTAND THE RISKS":
        logger.info("live_trading_cancelled_by_user")
        print("\nÔ£ô Live trading cancelled - no positions opened\n")
        return

    # Final affirmation
    confirm2 = input("Enter your email address to confirm (or 'cancel'): ").strip()

    if confirm2.lower() == "cancel" or not confirm2:
        logger.info("live_trading_cancelled_by_user")
        print("\nÔ£ô Live trading cancelled - no positions opened\n")
        return

    # Log critical event
    logger.critical("live_trading_starting", symbols=symbols, engine=settings.execution.engine, user_email=confirm2)

    print("\n" + "!" * 70)
    print("LIVE TRADING NOW ACTIVE - REAL MONEY IS AT RISK")
    print("!" * 70 + "\n")

    # Run identical trading logic as paper trading
    run_paper_trading(symbols, settings, slack_alerter, email_alerter, mode="live")


def main():
    parser = argparse.ArgumentParser(description="EDGECORE Trading System")
    parser.add_argument(
        "--mode",
        choices=["backtest", "paper", "live", "live-runner"],
        default="backtest",
        help="Operating mode. 'live-runner' uses the production LiveTradingRunner.",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=None,  # Will load from config if not provided
        help="Trading pairs (if not provided, uses config/dev.yaml trading_universe.symbols)",
    )
    parser.add_argument("--start-date", default=None, help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="Backtest end date (YYYY-MM-DD)")

    args = parser.parse_args()
    settings = get_settings()

    # If symbols not provided via CLI, use config
    if args.symbols is None:
        args.symbols = settings.trading_universe.symbols
        logger.info("using_symbols_from_config", num_symbols=len(args.symbols))

    # Initialize alerters (optional - based on environment variables)
    # Slack: requires SLACK_WEBHOOK_URL
    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
    slack_alerter = SlackAlerter(webhook_url=slack_webhook) if slack_webhook else None

    # Email: requires EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT, EMAIL_SMTP_USER,
    #        EMAIL_SMTP_PASS, EMAIL_RECIPIENTS
    email_alerter = EmailAlerter.from_env()

    # --- Initialisation mémoire contextuelle AI (BP-02) ---
    context = {
        "args": args,
        "settings": settings,
        "logger": logger,
        "slack_alerter": slack_alerter,
        "email_alerter": email_alerter,
        "context_memory": ContextMemory(),
    }
    # --- Appel hooks AI (BP-01) ---
    _run_ai_hooks(context)

    logger.info(
        "edgecore_startup",
        mode=args.mode,
        env=settings.env,
        slack_enabled=slack_alerter is not None and slack_alerter.enabled,
        email_enabled=email_alerter is not None and email_alerter.enabled,
    )

    # Start a minimal health-check HTTP server so Docker HEALTHCHECK
    # passes regardless of operating mode (backtest / paper / live).
    # In paper/live mode this is later superseded by the full dashboard API.
    if os.getenv("ENABLE_MONITORING", "").lower() in ("true", "1", "yes"):
        try:
            from flask import Flask as _Flask

            _health_app = _Flask("healthcheck")

            @_health_app.route("/health")
            def _hc():
                return {"status": "healthy", "mode": args.mode}, 200

            _hc_host = os.getenv("DASHBOARD_API_HOST", "0.0.0.0")
            _hc_port = int(os.getenv("DASHBOARD_API_PORT", "5000"))
            _hc_thread = threading.Thread(
                target=lambda: _health_app.run(host=_hc_host, port=_hc_port, debug=False, use_reloader=False),
                daemon=True,
            )
            _hc_thread.start()
            logger.info("health_endpoint_started", host=_hc_host, port=_hc_port)
        except Exception as e:
            logger.warning("health_endpoint_failed", error=str(e))

    try:
        if args.mode == "backtest":
            logger.info("backtest_mode_starting")
            runner = BacktestRunner()
            # Use run_unified() to avoid look-ahead bias present in legacy run()
            metrics = runner.run_unified(args.symbols, start_date=args.start_date, end_date=args.end_date)
            print(metrics.summary())

        elif args.mode == "paper":
            logger.info("paper_trading_mode_selected")
            run_paper_trading(args.symbols, settings, slack_alerter, email_alerter)

        elif args.mode == "live":
            logger.critical("live_trading_mode_selected", symbols=args.symbols)
            run_live_trading(args.symbols, settings, slack_alerter, email_alerter)

        elif args.mode == "live-runner":
            logger.info("live_runner_mode_selected", symbols=args.symbols)
            from live_trading.runner import LiveTradingRunner, TradingLoopConfig

            runner_cfg = TradingLoopConfig(
                symbols=args.symbols,
                bar_interval_seconds=getattr(settings.execution, "paper_trading_loop_interval_seconds", 60),
                pair_rediscovery_hours=24,
                max_positions=getattr(settings.risk, "max_concurrent_positions", 10),
                initial_capital=settings.execution.initial_capital,
                mode="paper",
            )
            lt_runner = LiveTradingRunner(runner_cfg, email_alerter=email_alerter, slack_alerter=slack_alerter)
            lt_runner.start()

    except Exception as e:
        logger.error("main_error", mode=args.mode, error=str(e))
        # Send critical alert to Slack and/or Email
        if slack_alerter:
            try:
                slack_alerter.send_critical_alert(
                    title="EDGECORE System Error",
                    message=str(e),
                    context={"mode": args.mode, "symbols": ", ".join(args.symbols)},
                )
            except Exception as alert_err:
                logger.error("failed_to_send_slack_alert", error=str(alert_err))
        if email_alerter:
            try:
                email_alerter.send_critical_alert(
                    title="EDGECORE System Error",
                    message=str(e),
                    context={"mode": args.mode, "symbols": ", ".join(args.symbols)},
                )
            except Exception as alert_err:
                logger.error("failed_to_send_email_alert", error=str(alert_err))
        print(f"\nÔØî Error: {str(e)}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
