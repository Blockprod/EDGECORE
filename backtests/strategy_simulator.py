"""
Unified backtest simulator – Sprint 1.1 (fixes C-01: backtest/live divergence).

Uses ``PairTradingStrategy.generate_signals()`` as the **sole** source of
trading logic.  Zero duplication between backtest and live execution paths.

Key properties
--------------
* Bar-by-bar simulation with expanding window (no look-ahead).
* Pair discovery at configurable intervals via the live strategy code.
* Realistic cost model (4-leg entry/exit + borrowing).
* All live features active: trailing stops, concentration limits,
  regime detection, adaptive thresholds, hedge-ratio tracking.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from structlog import get_logger

from strategies.pair_trading import PairTradingStrategy
from backtests.cost_model import CostModel, CostModelConfig
from backtests.metrics import BacktestMetrics, set_trading_days, TRADING_DAYS_PER_YEAR
from execution.time_stop import TimeStopManager
from risk.spread_correlation import SpreadCorrelationGuard
from risk.pca_spread_monitor import PCASpreadMonitor
from risk.engine import RiskEngine
from execution.partial_profit import PartialProfitManager
from models.cointegration import half_life_mean_reversion

logger = get_logger(__name__)


class StrategyBacktestSimulator:
    """
    Simulates the live PairTradingStrategy bar-by-bar.

    The **only** source of entry / exit decisions is
    :pymethod:`PairTradingStrategy.generate_signals`.
    This class handles portfolio accounting and realistic cost application.
    """

    def __init__(
        self,
        cost_model: Optional[CostModel] = None,
        initial_capital: float = 100_000.0,
        allocation_per_pair_pct: float = 30.0,
        pair_rediscovery_interval: int = 5,
        time_stop: Optional[TimeStopManager] = None,
        spread_corr_guard: Optional[SpreadCorrelationGuard] = None,
        risk_engine: Optional[RiskEngine] = None,
        max_position_loss_pct: float = 0.10,
        max_portfolio_heat: float = 0.95,
    ):
        """
        Args:
            cost_model: Trading cost model (default: CostModel with standard config).
            initial_capital: Starting portfolio value in USD.
            allocation_per_pair_pct: Percentage of portfolio allocated per pair.
            pair_rediscovery_interval: Bars between pair re-discoveries
                (set to 0 to discover every bar – slow but most accurate).
            time_stop: Time-based stop manager (Sprint 1.5).  When provided,
                positions held longer than ``min(2 × half_life, cap)`` bars
                are force-closed.  Default: enabled with standard config.
            spread_corr_guard: Spread correlation guard (Sprint 1.6).
                Rejects entries whose spread correlates > threshold with
                existing positions.  Default: enabled (ρ_max=0.60).
            risk_engine: Optional RiskEngine instance.  When provided, each
                entry is validated via ``can_enter_trade()`` – applying the
                same limits enforced in live trading (max positions, per-trade
                risk, consecutive loss limits, daily drawdown, leverage).
            max_position_loss_pct: Maximum loss per position as fraction of
                notional (e.g. 0.03 = 3%).  Positions hitting this are
                force-closed.  Set to 0 to disable.
        """
        self.cost_model = cost_model or CostModel()
        self.initial_capital = initial_capital
        self.allocation_pct = allocation_per_pair_pct
        self.pair_rediscovery_interval = pair_rediscovery_interval
        self.time_stop = time_stop if time_stop is not None else TimeStopManager()
        self.spread_corr_guard = (
            spread_corr_guard if spread_corr_guard is not None
            else SpreadCorrelationGuard()
        )
        self.risk_engine = risk_engine
        self.max_position_loss_pct = max_position_loss_pct
        # Phase 3: PCA factor monitor (complements pairwise corr guard)
        self.pca_monitor = PCASpreadMonitor()
        # Phase 3: Partial profit-taking (audit §4.4 – staged exits)
        self.partial_profit = PartialProfitManager()
        # Phase 4: Portfolio-level drawdown circuit breaker
        self.portfolio_dd_limit = 0.15          # halt all trading if DD > 15%
        self.portfolio_dd_cooldown_bars = 10    # bars to wait after breaker trips
        self._dd_cooldown_remaining = 0
        # Phase 4: Portfolio heat limit (aggregate risk budget)
        self.max_portfolio_heat = max_portfolio_heat
        # Phase 5: Trailing stop – protect profits once in the money
        self.trailing_stop_activation_pct = 0.015  # activate at 1.5% profit
        self.trailing_stop_trail_pct = 0.01       # trail 1.0% from peak unrealized

    # ==================================================================
    # Public API
    # ==================================================================

    def run(
        self,
        prices_df: pd.DataFrame,
        fixed_pairs: Optional[List[Tuple[str, str, float, float]]] = None,
        sector_map: Optional[Dict[str, str]] = None,
        weekly_prices: Optional[pd.DataFrame] = None,
    ) -> BacktestMetrics:
        """
        Run a bar-by-bar backtest using the live strategy code.

        Args:
            prices_df: Price DataFrame – columns are symbol names,
                       index is DatetimeIndex (daily).
            fixed_pairs: If provided, these pairs are used for the **entire**
                         run instead of periodic re-discovery.  Intended for
                         walk-forward periods where pairs come from the
                         training window.
            sector_map: Optional dict mapping symbol → sector name.
                        When provided, pair discovery is restricted to
                        intra-sector pairs only (standard institutional
                        approach).  Passed through to
                        ``PairTradingStrategy.find_cointegrated_pairs()``.
            weekly_prices: Optional weekly close prices for multi-timeframe
                        confirmation.  When provided, pair discovery uses
                        weekly cointegration confirmation and signal
                        generation uses weekly z-score gate.

        Returns:
            BacktestMetrics with performance statistics.
        """
        strategy = self._create_fresh_strategy()

        # ---- Set sector map on strategy for intra-sector pair discovery ----
        if sector_map is not None:
            strategy.sector_map = sector_map

        # ---- Align the strategy's internal equity tracker with the actual
        #      initial capital so the drawdown guard doesn't misfire when the
        #      backtest uses a different capital than the config default.
        strategy.peak_equity = self.initial_capital
        strategy.current_equity = self.initial_capital

        # ---- US Equity annualisation: always 252 trading days ----
        set_trading_days(252)
        logger.info("annualisation_set", trading_days=252, market="us_equity")

        # Portfolio tracking
        positions: Dict[str, dict] = {}
        portfolio_values: List[float] = [self.initial_capital]
        daily_returns: List[float] = []
        trades_pnl: List[float] = []          # round-trip P&L per closed trade

        lookback_min = max(60, strategy.config.lookback_window)

        if len(prices_df) <= lookback_min:
            logger.warning(
                "simulator_insufficient_data",
                rows=len(prices_df),
                required=lookback_min,
            )
            return self._empty_metrics(prices_df)

        current_pairs: Optional[List[Tuple]] = fixed_pairs
        # Force discovery on the very first bar when not using fixed_pairs
        bars_since_discovery = self.pair_rediscovery_interval

        logger.info(
            "strategy_simulation_starting",
            total_bars=len(prices_df),
            tradeable_bars=len(prices_df) - lookback_min,
            pair_discovery_interval=self.pair_rediscovery_interval,
            using_fixed_pairs=fixed_pairs is not None,
            initial_capital=self.initial_capital,
        )

        # Phase 4: track previous bar's total unrealised P&L for MtM delta
        prev_unrealised_total = 0.0
        # Circuit breaker high-water mark — resets after cooldown so the
        # breaker doesn't permanently disable trading.
        _dd_hw_mark = float(self.initial_capital)

        from tqdm import tqdm
        print("[BACKTEST] Démarrage du backtest principal...")
        for bar_idx in tqdm(range(lookback_min, len(prices_df)), desc="Backtest", ncols=80):
            hist_prices = prices_df.iloc[: bar_idx + 1]

            # ---- Phase 4: Wire strategy equity tracker (activates DD guard) --
            strategy.update_equity(portfolio_values[-1])

            # ---- Phase 4: Portfolio-level drawdown circuit breaker ----
            if portfolio_values[-1] > _dd_hw_mark:
                _dd_hw_mark = portfolio_values[-1]
            current_dd = (_dd_hw_mark - portfolio_values[-1]) / _dd_hw_mark if _dd_hw_mark > 0 else 0.0
            if self._dd_cooldown_remaining > 0:
                self._dd_cooldown_remaining -= 1
                # Force-close everything during cooldown
                for pk in list(positions.keys()):
                    pc = positions.pop(pk)
                    cpnl, tpnl = self._close_position(pc, prices_df, bar_idx)
                    realized_pnl_pre = cpnl  # will be accumulated below
                    trades_pnl.append(tpnl)
                    self.spread_corr_guard.remove_spread(pk)
                    self.pca_monitor.remove_spread(pk)
                    self.partial_profit.remove(pk)
                # Skip straight to portfolio update
                new_val = portfolio_values[-1] + sum([])
                daily_returns.append(0.0)
                portfolio_values.append(portfolio_values[-1])
                prev_unrealised_total = 0.0
                # Reset high-water mark on last cooldown bar so that
                # the DD check restarts fresh from post-drawdown equity.
                if self._dd_cooldown_remaining == 0:
                    _dd_hw_mark = portfolio_values[-1]
                    logger.info(
                        "circuit_breaker_cooldown_expired",
                        hwm_reset_to=round(_dd_hw_mark, 2),
                    )
                continue
            if current_dd >= self.portfolio_dd_limit:
                self._dd_cooldown_remaining = self.portfolio_dd_cooldown_bars
                logger.warning(
                    "portfolio_circuit_breaker_tripped",
                    drawdown=f"{current_dd:.2%}",
                    limit=f"{self.portfolio_dd_limit:.2%}",
                    cooldown_bars=self.portfolio_dd_cooldown_bars,
                )
                # Force-close all positions
                fc_pnl = 0.0
                for pk in list(positions.keys()):
                    pc = positions.pop(pk)
                    cpnl, tpnl = self._close_position(pc, prices_df, bar_idx)
                    fc_pnl += cpnl
                    trades_pnl.append(tpnl)
                    self.spread_corr_guard.remove_spread(pk)
                    self.pca_monitor.remove_spread(pk)
                    self.partial_profit.remove(pk)
                new_val = portfolio_values[-1] + fc_pnl
                dr = fc_pnl / portfolio_values[-1] if portfolio_values[-1] > 0 else 0.0
                daily_returns.append(dr)
                portfolio_values.append(new_val)
                prev_unrealised_total = 0.0
                continue

            # ---- Pair discovery (strictly in-sample) ----------------
            if fixed_pairs is None:
                if bars_since_discovery >= self.pair_rediscovery_interval:
                    # Clear stale correlation exclusions so pairs get a
                    # fresh chance each discovery window.
                    strategy.reset_all_correlation_exclusions()

                    current_pairs = strategy.find_cointegrated_pairs(
                        hist_prices, use_cache=False,
                        weekly_prices=weekly_prices,
                    )
                    bars_since_discovery = 0
                    logger.debug(
                        "pairs_discovered",
                        bar=bar_idx,
                        date=str(prices_df.index[bar_idx])[:10],
                        pairs_found=len(current_pairs) if current_pairs else 0,
                    )
                else:
                    bars_since_discovery += 1

            # ---- PRE-SIGNAL P&L stop: cut losers before signal processing ----
            # This ensures large losses are stopped out regardless of
            # z-score reversion through shifted rolling stats.
            realized_pnl = 0.0
            if self.max_position_loss_pct > 0:
                for pair_key in list(positions.keys()):
                    pos = positions[pair_key]
                    sym1, sym2 = pos["sym1"], pos["sym2"]
                    cur_p1 = prices_df[sym1].iloc[bar_idx]
                    cur_p2 = prices_df[sym2].iloc[bar_idx]
                    ep1, ep2 = pos["entry_price_1"], pos["entry_price_2"]
                    not_per_leg = pos["notional"] / 2.0
                    if pos["side"] == "long":
                        r1 = (cur_p1 - ep1) / ep1 if ep1 else 0
                        r2 = (ep2 - cur_p2) / ep2 if ep2 else 0
                    else:
                        r1 = (ep1 - cur_p1) / ep1 if ep1 else 0
                        r2 = (cur_p2 - ep2) / ep2 if ep2 else 0
                    unrealised = not_per_leg * r1 + not_per_leg * r2
                    loss_pct = -unrealised / pos["notional"] if pos["notional"] > 0 else 0
                    if loss_pct >= self.max_position_loss_pct:
                        pos_closed = positions.pop(pair_key)
                        close_pnl, trade_pnl = self._close_position(
                            pos_closed, prices_df, bar_idx
                        )
                        realized_pnl += close_pnl
                        trades_pnl.append(trade_pnl)
                        self.spread_corr_guard.remove_spread(pair_key)
                        self.pca_monitor.remove_spread(pair_key)
                        self.partial_profit.remove(pair_key)
                        strategy.active_trades.pop(pair_key, None)
                        logger.debug(
                            "pre_signal_pnl_stop",
                            pair=pair_key,
                            loss_pct=f"{loss_pct:.2%}",
                            limit=f"{self.max_position_loss_pct:.2%}",
                            trade_pnl=round(trade_pnl, 2),
                        )

            # ---- Generate signals via LIVE strategy code ------------
            signals = strategy.generate_signals(
                hist_prices, discovered_pairs=current_pairs,
                weekly_prices=weekly_prices,
            )

            # ---- Process signals (entries & exits) ------------------
            # realized_pnl is already initialized above (before pre-signal P&L stop)

            for signal in signals:
                pair_key = signal.symbol_pair
                parts = pair_key.split("_")
                if len(parts) != 2:
                    continue
                sym1, sym2 = parts

                if (
                    sym1 not in prices_df.columns
                    or sym2 not in prices_df.columns
                ):
                    continue

                # --- ENTRY -------------------------------------------
                if signal.side in ("long", "short") and pair_key not in positions:
                    # Sprint 1.6 – Spread correlation guard (C-06 fix)
                    candidate_spread = self._compute_spread(
                        hist_prices, sym1, sym2
                    )
                    if candidate_spread is not None:
                        allowed, reject_reason = self.spread_corr_guard.check_entry(
                            pair_key, candidate_spread
                        )
                        if not allowed:
                            logger.debug(
                                "entry_rejected_spread_correlation",
                                pair=pair_key,
                                reason=reject_reason,
                            )
                            continue

                        # Phase 3 – PCA factor concentration guard
                        pca_ok, pca_reason = self.pca_monitor.check_entry(
                            pair_key, candidate_spread
                        )
                        if not pca_ok:
                            logger.debug(
                                "entry_rejected_pca_factor",
                                pair=pair_key,
                                reason=pca_reason,
                            )
                            continue

                    # --- Quality-weighted allocation ---------------------
                    # Better pairs (lower p-value, favourable half-life)
                    # receive up to 1.5× the base allocation; weak pairs 0.5×.
                    pair_pvalue = self._resolve_pvalue(pair_key, current_pairs)
                    pair_hl_alloc = self._resolve_half_life(pair_key, current_pairs)
                    quality_mult = self._allocation_quality_multiplier(
                        pair_pvalue, pair_hl_alloc
                    )
                    adjusted_alloc = self.allocation_pct * quality_mult

                    # Phase 4 – Volatility-based position sizing
                    # Inverse-vol: allocate less to volatile spreads
                    vol_mult = self._volatility_sizing_multiplier(
                        hist_prices, sym1, sym2
                    )
                    adjusted_alloc *= vol_mult

                    # Phase 4 – Regime-adaptive allocation
                    # Use regime detector output (not signal.strength which
                    # represents z-score magnitude, NOT regime state).
                    # Only scale down in confirmed HIGH-volatility regimes.
                    regime_mult = 1.0  # default: full allocation

                    # Enforce a combined multiplier floor so stacked dampeners
                    # never reduce allocation below 50% of the base.
                    effective_mult = (adjusted_alloc / self.allocation_pct) if self.allocation_pct > 0 else 1.0
                    if effective_mult < 0.5:
                        adjusted_alloc = self.allocation_pct * 0.5

                    notional = (
                        portfolio_values[-1] * adjusted_alloc / 100.0
                    )

                    # Phase 4 – Portfolio heat enforcement
                    current_heat = self._compute_portfolio_heat(
                        positions, portfolio_values[-1]
                    )
                    if current_heat + (notional / portfolio_values[-1] if portfolio_values[-1] > 0 else 0) > self.max_portfolio_heat:
                        logger.debug(
                            "entry_rejected_portfolio_heat",
                            pair=pair_key,
                            current_heat=f"{current_heat:.2%}",
                            limit=f"{self.max_portfolio_heat:.2%}",
                        )
                        continue

                    notional_per_leg = notional / 2.0

                    # --- RiskEngine gate (same limits as live) -------
                    if self.risk_engine is not None:
                        # Estimate volatility from recent spread std
                        recent_prices = hist_prices[sym1].iloc[-60:]
                        vol_estimate = recent_prices.pct_change().std() if len(recent_prices) > 2 else 0.02
                        vol_estimate = max(vol_estimate, 1e-6)
                        try:
                            re_allowed, re_reason = self.risk_engine.can_enter_trade(
                                symbol_pair=pair_key,
                                position_size=notional,
                                current_equity=portfolio_values[-1],
                                volatility=vol_estimate,
                            )
                        except Exception as re_exc:
                            logger.debug(
                                "risk_engine_check_error",
                                pair=pair_key,
                                error=str(re_exc),
                            )
                            re_allowed, re_reason = False, str(re_exc)
                        if not re_allowed:
                            logger.debug(
                                "entry_rejected_risk_engine",
                                pair=pair_key,
                                reason=re_reason,
                            )
                            continue

                    e_cost = self.cost_model.entry_cost(notional_per_leg)

                    # Resolve half-life for this pair (for time stop)
                    pair_hl = pair_hl_alloc  # already resolved above

                    positions[pair_key] = {
                        "side": signal.side,
                        "sym1": sym1,
                        "sym2": sym2,
                        "entry_price_1": prices_df[sym1].iloc[bar_idx],
                        "entry_price_2": prices_df[sym2].iloc[bar_idx],
                        "entry_bar": bar_idx,
                        "notional": notional,
                        "entry_cost": e_cost,
                        "half_life": pair_hl,
                        "peak_unrealized": 0.0,
                    }
                    realized_pnl -= e_cost

                    # Register spread for correlation monitoring
                    if candidate_spread is not None:
                        self.spread_corr_guard.register_spread(
                            pair_key, candidate_spread
                        )
                        self.pca_monitor.register_spread(
                            pair_key, candidate_spread
                        )
                    # Register for partial profit tracking
                    self.partial_profit.register(pair_key)

                # --- EXIT --------------------------------------------
                elif signal.side == "exit" and pair_key in positions:
                    pos = positions.pop(pair_key)
                    close_pnl, trade_pnl = self._close_position(
                        pos, prices_df, bar_idx
                    )
                    realized_pnl += close_pnl
                    trades_pnl.append(trade_pnl)
                    self.spread_corr_guard.remove_spread(pair_key)
                    self.pca_monitor.remove_spread(pair_key)
                    self.partial_profit.remove(pair_key)

            # ---- Sync strategy.active_trades with simulator positions ----
            # The strategy adds to active_trades when generating signals, but
            # the simulator may reject entries (spread corr, heat, risk, etc.).
            # Remove ghost entries so the strategy doesn't think rejected
            # signals are live positions.
            ghost_keys = [
                k for k in strategy.active_trades
                if k not in positions
            ]
            for gk in ghost_keys:
                strategy.active_trades.pop(gk, None)

            # ---- Simulator-level Z-score exit (mean reversion) ----------
            # CRITICAL: generate_signals() only iterates pairs in the
            # current discovery list.  When a pair drops from discoveries
            # (e.g., BH-FDR rejects it next window), the strategy code
            # never checks the z-score for that position.  This block
            # independently monitors ALL open positions and closes them
            # when the spread reverts to the exit threshold OR diverges
            # beyond the z-score stop-loss (more natural than % stop for
            # stat-arb — aligns with the z-score entry framework).
            z_stop_threshold = getattr(strategy.config, 'z_score_stop', 3.5)
            for pair_key in list(positions.keys()):
                pos = positions[pair_key]
                sym1, sym2 = pos["sym1"], pos["sym2"]
                try:
                    from models.spread import SpreadModel
                    y = hist_prices[sym1]
                    x = hist_prices[sym2]
                    model = SpreadModel(y, x)
                    spread = model.compute_spread(y, x)
                    z_score_series = model.compute_z_score(spread)
                    current_z = z_score_series.iloc[-1]

                    # Mean-reversion exit: z reverted to near zero
                    if abs(current_z) <= strategy.config.exit_z_score:
                        pos_closed = positions.pop(pair_key)
                        close_pnl, trade_pnl = self._close_position(
                            pos_closed, prices_df, bar_idx
                        )
                        realized_pnl += close_pnl
                        trades_pnl.append(trade_pnl)
                        strategy.active_trades.pop(pair_key, None)
                        self.spread_corr_guard.remove_spread(pair_key)
                        self.pca_monitor.remove_spread(pair_key)
                        self.partial_profit.remove(pair_key)
                        logger.debug(
                            "z_score_exit",
                            pair=pair_key,
                            z_score=round(float(current_z), 3),
                            exit_threshold=strategy.config.exit_z_score,
                            trade_pnl=round(trade_pnl, 2),
                        )
                    # Z-score stop: spread diverged far beyond entry
                    elif abs(current_z) > z_stop_threshold:
                        pos_closed = positions.pop(pair_key)
                        close_pnl, trade_pnl = self._close_position(
                            pos_closed, prices_df, bar_idx
                        )
                        realized_pnl += close_pnl
                        trades_pnl.append(trade_pnl)
                        strategy.active_trades.pop(pair_key, None)
                        self.spread_corr_guard.remove_spread(pair_key)
                        self.pca_monitor.remove_spread(pair_key)
                        self.partial_profit.remove(pair_key)
                        logger.debug(
                            "z_score_stop_exit",
                            pair=pair_key,
                            z_score=round(float(current_z), 3),
                            z_stop=z_stop_threshold,
                            trade_pnl=round(trade_pnl, 2),
                        )
                except Exception as e:
                    logger.debug(
                        "z_score_exit_check_failed",
                        pair=pair_key,
                        error=str(e),
                    )

            # ---- Partial profit-taking (Phase 3 – §4.4 fix) -------
            for pair_key in list(positions.keys()):
                pos = positions[pair_key]
                sym1, sym2 = pos["sym1"], pos["sym2"]
                cur_p1 = prices_df[sym1].iloc[bar_idx]
                cur_p2 = prices_df[sym2].iloc[bar_idx]
                ep1, ep2 = pos["entry_price_1"], pos["entry_price_2"]
                not_per_leg = pos["notional"] / 2.0
                if pos["side"] == "long":
                    r1 = (cur_p1 - ep1) / ep1 if ep1 else 0
                    r2 = (ep2 - cur_p2) / ep2 if ep2 else 0
                else:
                    r1 = (ep1 - cur_p1) / ep1 if ep1 else 0
                    r2 = (cur_p2 - ep2) / ep2 if ep2 else 0
                unrealised = not_per_leg * r1 + not_per_leg * r2
                frac, force_all = self.partial_profit.check(
                    pair_key, unrealised, pos["notional"]
                )
                if force_all:
                    # Remainder stop: close entire remaining position
                    pos_closed = positions.pop(pair_key)
                    close_pnl, trade_pnl = self._close_position(
                        pos_closed, prices_df, bar_idx
                    )
                    realized_pnl += close_pnl
                    trades_pnl.append(trade_pnl)
                    self.spread_corr_guard.remove_spread(pair_key)
                    self.pca_monitor.remove_spread(pair_key)
                    self.partial_profit.remove(pair_key)
                    strategy.active_trades.pop(pair_key, None)  # sync strategy state
                    logger.debug(
                        "partial_profit_remainder_exit",
                        pair=pair_key,
                        trade_pnl=round(trade_pnl, 2),
                    )
                elif frac > 0:
                    # Partial close: reduce position notional
                    close_notional = pos["notional"] * frac
                    partial_pnl = unrealised * frac
                    x_cost = self.cost_model.exit_cost(close_notional / 2.0)
                    realized_pnl += partial_pnl - x_cost
                    trades_pnl.append(partial_pnl - x_cost)
                    pos["notional"] *= (1 - frac)
                    logger.debug(
                        "partial_profit_take",
                        pair=pair_key,
                        fraction=frac,
                        partial_pnl=round(partial_pnl - x_cost, 2),
                        remaining_notional=round(pos["notional"], 2),
                    )

            # ---- Time stop check (Sprint 1.5 – C-05 fix) -----------
            for pair_key in list(positions.keys()):
                pos = positions[pair_key]
                holding_bars = bar_idx - pos["entry_bar"]
                should_exit_ts, ts_reason = self.time_stop.should_exit(
                    holding_bars, pos.get("half_life")
                )
                if should_exit_ts:
                    pos_closed = positions.pop(pair_key)
                    close_pnl, trade_pnl = self._close_position(
                        pos_closed, prices_df, bar_idx
                    )
                    realized_pnl += close_pnl
                    trades_pnl.append(trade_pnl)
                    self.spread_corr_guard.remove_spread(pair_key)
                    self.pca_monitor.remove_spread(pair_key)
                    self.partial_profit.remove(pair_key)
                    strategy.active_trades.pop(pair_key, None)  # sync strategy state
                    logger.debug(
                        "time_stop_exit",
                        pair=pair_key,
                        holding_bars=holding_bars,
                        half_life=pos_closed.get("half_life"),
                        reason=ts_reason,
                        trade_pnl=round(trade_pnl, 2),
                    )

            # ---- P&L stop: force-close positions exceeding loss limit
            if self.max_position_loss_pct > 0:
                for pair_key in list(positions.keys()):
                    pos = positions[pair_key]
                    sym1, sym2 = pos["sym1"], pos["sym2"]
                    cur_p1 = prices_df[sym1].iloc[bar_idx]
                    cur_p2 = prices_df[sym2].iloc[bar_idx]
                    ep1, ep2 = pos["entry_price_1"], pos["entry_price_2"]
                    not_per_leg = pos["notional"] / 2.0
                    if pos["side"] == "long":
                        r1 = (cur_p1 - ep1) / ep1 if ep1 else 0
                        r2 = (ep2 - cur_p2) / ep2 if ep2 else 0
                    else:
                        r1 = (ep1 - cur_p1) / ep1 if ep1 else 0
                        r2 = (cur_p2 - ep2) / ep2 if ep2 else 0
                    unrealised = not_per_leg * r1 + not_per_leg * r2
                    loss_pct = -unrealised / pos["notional"] if pos["notional"] > 0 else 0
                    if loss_pct >= self.max_position_loss_pct:
                        pos_closed = positions.pop(pair_key)
                        close_pnl, trade_pnl = self._close_position(
                            pos_closed, prices_df, bar_idx
                        )
                        realized_pnl += close_pnl
                        trades_pnl.append(trade_pnl)
                        self.spread_corr_guard.remove_spread(pair_key)
                        self.pca_monitor.remove_spread(pair_key)
                        self.partial_profit.remove(pair_key)
                        strategy.active_trades.pop(pair_key, None)  # sync strategy state
                        logger.debug(
                            "pnl_stop_exit",
                            pair=pair_key,
                            loss_pct=f"{loss_pct:.2%}",
                            limit=f"{self.max_position_loss_pct:.2%}",
                            trade_pnl=round(trade_pnl, 2),
                        )

            # ---- Phase 5: Trailing stop – protect profits ---------------
            if self.trailing_stop_activation_pct > 0:
                for pair_key in list(positions.keys()):
                    pos = positions[pair_key]
                    sym1, sym2 = pos["sym1"], pos["sym2"]
                    cur_p1 = prices_df[sym1].iloc[bar_idx]
                    cur_p2 = prices_df[sym2].iloc[bar_idx]
                    ep1, ep2 = pos["entry_price_1"], pos["entry_price_2"]
                    not_per_leg = pos["notional"] / 2.0
                    if pos["side"] == "long":
                        r1 = (cur_p1 - ep1) / ep1 if ep1 else 0
                        r2 = (ep2 - cur_p2) / ep2 if ep2 else 0
                    else:
                        r1 = (ep1 - cur_p1) / ep1 if ep1 else 0
                        r2 = (cur_p2 - ep2) / ep2 if ep2 else 0
                    unrealised = not_per_leg * r1 + not_per_leg * r2
                    profit_pct = unrealised / pos["notional"] if pos["notional"] > 0 else 0
                    # Update peak unrealized
                    if unrealised > pos.get("peak_unrealized", 0.0):
                        pos["peak_unrealized"] = unrealised
                    # Check trailing stop: activate only after reaching profit threshold
                    peak = pos.get("peak_unrealized", 0.0)
                    peak_pct = peak / pos["notional"] if pos["notional"] > 0 else 0
                    if peak_pct >= self.trailing_stop_activation_pct:
                        drawback = peak - unrealised
                        drawback_pct = drawback / pos["notional"] if pos["notional"] > 0 else 0
                        if drawback_pct >= self.trailing_stop_trail_pct:
                            pos_closed = positions.pop(pair_key)
                            close_pnl, trade_pnl = self._close_position(
                                pos_closed, prices_df, bar_idx
                            )
                            realized_pnl += close_pnl
                            trades_pnl.append(trade_pnl)
                            self.spread_corr_guard.remove_spread(pair_key)
                            self.pca_monitor.remove_spread(pair_key)
                            self.partial_profit.remove(pair_key)
                            strategy.active_trades.pop(pair_key, None)
                            logger.debug(
                                "trailing_stop_exit",
                                pair=pair_key,
                                peak_pct=f"{peak_pct:.2%}",
                                drawback_pct=f"{drawback_pct:.2%}",
                                trade_pnl=round(trade_pnl, 2),
                            )

            # ---- Phase 4: Mark-to-market portfolio (unrealised P&L) ----
            current_unrealised_total = 0.0
            for _pk, _pos in positions.items():
                _s1, _s2 = _pos["sym1"], _pos["sym2"]
                _cp1 = prices_df[_s1].iloc[bar_idx]
                _cp2 = prices_df[_s2].iloc[bar_idx]
                _ep1, _ep2 = _pos["entry_price_1"], _pos["entry_price_2"]
                _npl = _pos["notional"] / 2.0
                if _pos["side"] == "long":
                    _r1 = (_cp1 - _ep1) / _ep1 if _ep1 else 0
                    _r2 = (_ep2 - _cp2) / _ep2 if _ep2 else 0
                else:
                    _r1 = (_ep1 - _cp1) / _ep1 if _ep1 else 0
                    _r2 = (_cp2 - _ep2) / _ep2 if _ep2 else 0
                current_unrealised_total += _npl * _r1 + _npl * _r2
            delta_unrealised = current_unrealised_total - prev_unrealised_total
            prev_unrealised_total = current_unrealised_total

            # ---- Update portfolio (realized + MtM delta) ----------------
            new_value = portfolio_values[-1] + realized_pnl + delta_unrealised
            daily_ret = (
                (realized_pnl + delta_unrealised) / portfolio_values[-1]
                if portfolio_values[-1] > 0
                else 0.0
            )
            daily_returns.append(daily_ret)
            portfolio_values.append(new_value)

        # ---- Force-close remaining positions at final bar -----------
        if positions:
            final_bar = len(prices_df) - 1
            fc_realized = 0.0
            for pair_key in list(positions.keys()):
                pos = positions.pop(pair_key)
                close_pnl, trade_pnl = self._close_position(
                    pos, prices_df, final_bar
                )
                fc_realized += close_pnl
                trades_pnl.append(trade_pnl)
                self.spread_corr_guard.remove_spread(pair_key)
                self.pca_monitor.remove_spread(pair_key)
                self.partial_profit.remove(pair_key)
                logger.debug(
                    "simulated_trade_force_closed",
                    pair=pair_key,
                    holding_days=final_bar - pos["entry_bar"],
                    trade_pnl=round(trade_pnl, 2),
                )
            if fc_realized != 0.0:
                daily_ret = (
                    fc_realized / portfolio_values[-1]
                    if portfolio_values[-1] > 0
                    else 0.0
                )
                daily_returns.append(daily_ret)
                portfolio_values.append(portfolio_values[-1] + fc_realized)

        # ---- Build metrics ------------------------------------------
        returns_series = (
            pd.Series(daily_returns) if daily_returns else pd.Series([0.0])
        )

        metrics = BacktestMetrics.from_returns(
            returns=returns_series,
            trades=trades_pnl if trades_pnl else [],
            start_date=str(prices_df.index[0])[:10],
            end_date=str(prices_df.index[-1])[:10],
        )
        metrics.initial_capital = self.initial_capital
        metrics.final_capital = round(portfolio_values[-1], 2)
        metrics.realized_pnl = round(portfolio_values[-1] - self.initial_capital, 2)

        logger.info(
            "strategy_simulation_completed",
            total_bars=len(prices_df) - lookback_min,
            total_trades=len(trades_pnl),
            final_portfolio=round(portfolio_values[-1], 2),
            total_return=f"{metrics.total_return:.2%}",
            sharpe=round(metrics.sharpe_ratio, 2),
            max_dd=f"{metrics.max_drawdown:.2%}",
        )

        return metrics

    # ==================================================================
    # Internal helpers
    # ==================================================================

    @staticmethod
    def _create_fresh_strategy() -> PairTradingStrategy:
        """Create a clean strategy instance with cache disabled."""
        strategy = PairTradingStrategy()
        strategy.disable_cache()
        return strategy

    def _empty_metrics(self, prices_df: pd.DataFrame) -> BacktestMetrics:
        """Return zeroed-out metrics when data is insufficient."""
        return BacktestMetrics.from_returns(
            returns=pd.Series([0.0]),
            trades=[],
            start_date=str(prices_df.index[0])[:10],
            end_date=str(prices_df.index[-1])[:10],
            note="INSUFFICIENT_DATA",
        )

    @staticmethod
    def _resolve_half_life(
        pair_key: str,
        current_pairs: Optional[List[Tuple]],
    ) -> Optional[int]:
        """Extract the half-life for *pair_key* from the discovered pairs list.

        Pairs are stored as ``(sym1, sym2, pvalue, half_life)`` tuples.
        Returns ``None`` when unavailable (time stop will use its default cap).
        """
        if current_pairs is None:
            return None
        for tup in current_pairs:
            if len(tup) >= 4:
                s1, s2, _pv, hl = tup[:4]
                key = f"{s1}_{s2}"
                if key == pair_key:
                    return hl
        return None

    @staticmethod
    def _resolve_pvalue(
        pair_key: str,
        current_pairs: Optional[List[Tuple]],
    ) -> Optional[float]:
        """Extract the cointegration p-value for *pair_key*.

        Pairs are stored as ``(sym1, sym2, pvalue, half_life)`` tuples.
        """
        if current_pairs is None:
            return None
        for tup in current_pairs:
            if len(tup) >= 3:
                s1, s2, pv = tup[:3]
                key = f"{s1}_{s2}"
                if key == pair_key:
                    return pv
        return None

    @staticmethod
    def _allocation_quality_multiplier(
        pvalue: Optional[float],
        half_life: Optional[float],
    ) -> float:
        """Return a multiplier in [0.5, 1.5] based on pair quality.

        Scoring:
        - p-value score  (0-1): lower p ↓ higher score
        - half-life score (0-1): 10-40 day HL is ideal
        Final multiplier = 0.5 + score (max 1.5).
        """
        score = 0.0

        # p-value component (0-0.5): very small p ↓ max 0.5
        if pvalue is not None and pvalue > 0:
            if pvalue < 0.001:
                score += 0.5
            elif pvalue < 0.01:
                score += 0.35
            elif pvalue < 0.05:
                score += 0.15

        # half-life component (0-0.5): sweet spot 10-40 days ↓ max 0.5
        if half_life is not None and half_life > 0:
            if 10 <= half_life <= 40:
                score += 0.5
            elif 5 <= half_life < 10 or 40 < half_life <= 60:
                score += 0.25

        return 0.5 + score  # Range [0.5, 1.5]

    def _close_position(
        self,
        pos: dict,
        prices_df: pd.DataFrame,
        bar_idx: int,
    ) -> Tuple[float, float]:
        """
        Close *pos* at *bar_idx* and return (daily_realized_pnl, full_trade_pnl).

        ``daily_realized_pnl`` – what hits the portfolio on the exit day
        (gross P&L minus exit cost and borrowing).

        ``full_trade_pnl`` – the complete round-trip P&L including the
        entry cost that was already deducted on the entry day.
        """
        sym1, sym2 = pos["sym1"], pos["sym2"]
        exit_price_1 = prices_df[sym1].iloc[bar_idx]
        exit_price_2 = prices_df[sym2].iloc[bar_idx]
        entry_price_1 = pos["entry_price_1"]
        entry_price_2 = pos["entry_price_2"]
        notional = pos["notional"]
        notional_per_leg = notional / 2.0
        holding_days = max(bar_idx - pos["entry_bar"], 0)

        # P&L per leg (% return × notional per leg)
        if pos["side"] == "long":
            # Long sym1, short sym2
            ret_1 = (
                (exit_price_1 - entry_price_1) / entry_price_1
                if entry_price_1 != 0
                else 0.0
            )
            ret_2 = (
                (entry_price_2 - exit_price_2) / entry_price_2
                if entry_price_2 != 0
                else 0.0
            )
        else:
            # Short sym1, long sym2
            ret_1 = (
                (entry_price_1 - exit_price_1) / entry_price_1
                if entry_price_1 != 0
                else 0.0
            )
            ret_2 = (
                (exit_price_2 - entry_price_2) / entry_price_2
                if entry_price_2 != 0
                else 0.0
            )

        pnl_gross = notional_per_leg * ret_1 + notional_per_leg * ret_2

        # Exit-day costs
        x_cost = self.cost_model.exit_cost(notional_per_leg)
        borrow = self.cost_model.holding_cost(notional_per_leg, holding_days)
        funding = self.cost_model.funding_cost(notional_per_leg, holding_days)

        daily_realized = pnl_gross - x_cost - borrow - funding
        full_trade = daily_realized - pos["entry_cost"]  # include entry cost

        logger.debug(
            "simulated_trade_closed",
            pair=f"{sym1}_{sym2}",
            side=pos["side"],
            holding_days=holding_days,
            pnl_gross=round(pnl_gross, 2),
            exit_cost=round(x_cost, 2),
            borrow_cost=round(borrow, 2),
            trade_pnl=round(full_trade, 2),
        )

        return daily_realized, full_trade

    @staticmethod
    def _compute_spread(
        prices_df: pd.DataFrame,
        sym1: str,
        sym2: str,
    ) -> Optional[pd.Series]:
        """Compute a simple OLS-residual spread for the correlation guard.

        Uses log-price ratio as a lightweight proxy (avoids a full
        SpreadModel fit on every bar).  Returns ``None`` on failure.
        """
        try:
            s1 = prices_df[sym1]
            s2 = prices_df[sym2]
            if len(s1) < 30 or len(s2) < 30:
                return None
            # Normalised spread: log(s1) ∓ β·log(s2), β via simple OLS
            ls1 = np.log(s1.replace(0, np.nan).dropna())
            ls2 = np.log(s2.replace(0, np.nan).dropna())
            common = ls1.index.intersection(ls2.index)
            if len(common) < 30:
                return None
            ls1 = ls1.loc[common]
            ls2 = ls2.loc[common]
            beta = np.polyfit(ls2.values, ls1.values, 1)[0]
            spread = ls1 - beta * ls2
            return spread
        except Exception:
            return None

    # ==================================================================
    # Phase 4 helpers
    # ==================================================================

    @staticmethod
    def _volatility_sizing_multiplier(
        prices_df: pd.DataFrame,
        sym1: str,
        sym2: str,
        lookback: int = 60,
    ) -> float:
        """Return an inverse-volatility multiplier in [0.4, 1.5].

        High-vol spreads get reduced allocation; tight mean-reverting
        spreads get a boost.  Uses log-return volatility of the simple
        spread as a proxy.
        """
        try:
            s1 = prices_df[sym1].iloc[-lookback:]
            s2 = prices_df[sym2].iloc[-lookback:]
            if len(s1) < 20 or len(s2) < 20:
                return 1.0
            # Simple spread vol (% of combined price)
            spread_ret = (s1.pct_change() - s2.pct_change()).dropna()
            if len(spread_ret) < 10:
                return 1.0
            vol = spread_ret.std()
            if vol <= 0:
                return 1.0
            # Inverse-vol: target 2% daily spread vol.
            # If vol is lower ↓ bigger position (up to 1.5×);
            # if higher ↓ smaller (down to 0.4×).
            target_vol = 0.02
            raw = target_vol / vol
            return float(np.clip(raw, 0.4, 1.5))
        except Exception:
            return 1.0

    @staticmethod
    def _compute_portfolio_heat(
        positions: Dict[str, dict],
        portfolio_value: float,
    ) -> float:
        """Compute current portfolio heat (sum of position notionals / equity).

        A value of 0.20 means 20% of the portfolio is exposed.
        """
        if portfolio_value <= 0 or not positions:
            return 0.0
        total_notional = sum(p["notional"] for p in positions.values())
        return total_notional / portfolio_value
