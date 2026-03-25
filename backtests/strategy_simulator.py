"""
Unified backtest simulator ÔÇô Sprint 1.1 (fixes C-01: backtest/live divergence).

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

from typing import Any, Callable

import numpy as np
import pandas as pd
from structlog import get_logger

from backtests.cost_model import CostModel
from backtests.metrics import BacktestMetrics, set_trading_days
from backtests.order_book import SimulatedOrderBook
from backtests.simulation_loop import OOSTracker
from data.event_filter import EventFilter
from execution.algo_executor import AlgoConfig, AlgoType, TWAPExecutor
from execution.borrow_check import BorrowChecker
from execution.partial_profit import PartialProfitManager
from execution.time_stop import TimeStopManager
from pair_selection.blacklist import PairBlacklist
from risk.drawdown_manager import DrawdownManager
from risk.engine import RiskEngine
from risk.factor_model import FactorModel
from risk.kelly_sizing import KellySizer
from risk.pca_spread_monitor import PCASpreadMonitor
from risk.sector_exposure import SectorExposureMonitor
from risk.spread_correlation import SpreadCorrelationGuard
from risk.var_monitor import VaRMonitor
from signal_engine.earnings_signal import EarningsSurpriseSignal
from signal_engine.intraday_signals import IntradaySignalEngine
from signal_engine.market_regime import MarketRegimeFilter
from signal_engine.ml_combiner import MLSignalCombiner
from signal_engine.options_flow import OptionsFlowSignal
from signal_engine.sentiment import SentimentSignal
from strategies.pair_trading import PairTradingStrategy

logger = get_logger(__name__)

# Cython fast path for z-score computation in the simulator hot loop.
# Loaded once at module import; falls back to None if Cython not compiled.
try:
    from models.cointegration_fast import compute_zscore_last_fast as _compute_zscore_last_fast  # noqa: E402

    _HALF_LIFE_CYTHON_SIM = True
except ImportError as _e_cython_sim:
    _compute_zscore_last_fast = None
    _HALF_LIFE_CYTHON_SIM = False
    import structlog as _structlog

    _structlog.get_logger(__name__).warning(
        "cython_extension_missing_using_python_fallback",
        module="models.cointegration_fast",
        function="compute_zscore_last_fast",
        error=str(_e_cython_sim),
        impact="10x slower z-score backtest loop — recompile with: python setup.py build_ext --inplace",
    )


class StrategyBacktestSimulator:
    """
    Simulates the live PairTradingStrategy bar-by-bar.

    The **only** source of entry / exit decisions is
    :pymethod:`PairTradingStrategy.generate_signals`.
    This class handles portfolio accounting and realistic cost application.
    """

    def __init__(
        self,
        cost_model: CostModel | None = None,
        initial_capital: float = 100_000.0,
        allocation_per_pair_pct: float = 30.0,
        pair_rediscovery_interval: int = 5,
        pair_validation_interval: int = 1,
        time_stop: TimeStopManager | None = None,
        spread_corr_guard: SpreadCorrelationGuard | None = None,
        risk_engine: RiskEngine | None = None,
        max_position_loss_pct: float = 0.10,
        max_portfolio_heat: float = 0.95,
        kelly_sizer: KellySizer | None = None,
        sector_map: dict[str, str] | None = None,
        event_filter: EventFilter | None = None,
        borrow_checker: BorrowChecker | None = None,
        leverage_multiplier: float = 1.0,
        bars_per_day: int = 1,
        momentum_filter=None,
        universe_manager=None,
        adv_by_symbol: dict[str, float] | None = None,
    ):
        """
        Args:
            cost_model: Trading cost model (default: CostModel with standard config).
            initial_capital: Starting portfolio value in USD.
            allocation_per_pair_pct: Percentage of portfolio allocated per pair.
            pair_rediscovery_interval: Bars between full EG pair re-discoveries
                (expensive: OLS + ADF + Newey-West on all candidate pairs).
            pair_validation_interval: Bars between lightweight validity checks
                on *existing* pairs (cheap: rolling z-score via Cython only).
                Set equal to pair_rediscovery_interval to disable.
            time_stop: Time-based stop manager (Sprint 1.5).  When provided,
                positions held longer than ``min(2 ├ù half_life, cap)`` bars
                are force-closed.  Default: enabled with standard config.
            spread_corr_guard: Spread correlation guard (Sprint 1.6).
                Rejects entries whose spread correlates > threshold with
                existing positions.  Default: enabled (¤ü_max=0.60).
            risk_engine: Optional RiskEngine instance.  When provided, each
                entry is validated via ``can_enter_trade()`` ÔÇô applying the
                same limits enforced in live trading (max positions, per-trade
                risk, consecutive loss limits, daily drawdown, leverage).
            max_position_loss_pct: Maximum loss per position as fraction of
                notional (e.g. 0.03 = 3%).  Positions hitting this are
                force-closed.  Set to 0 to disable.
        """
        from execution.slippage import SlippageConfig, SlippageModel

        self.slippage_model = SlippageModel(SlippageConfig())
        if cost_model is not None:
            self.cost_model = cost_model
        else:
            # C-01: CostModel reads from get_settings().costs (single source of truth)
            # so that changing costs.slippage_bps / commission_pct in YAML propagates
            # to backtests without code changes.
            from backtests.cost_model import CostModelConfig
            from config.settings import get_settings as _gs_sim

            _c = _gs_sim().costs
            self.cost_model = CostModel(
                CostModelConfig(
                    base_slippage_bps=_c.slippage_bps,
                    taker_fee_bps=_c.taker_fee_bps,
                    maker_fee_bps=_c.maker_fee_bps,
                    borrowing_cost_annual_pct=_c.borrowing_cost_annual * 100,
                    slippage_model=_c.slippage_model,
                )
            )
        self.initial_capital = initial_capital
        self.allocation_pct = allocation_per_pair_pct
        self.pair_rediscovery_interval = pair_rediscovery_interval
        self.pair_validation_interval = max(1, pair_validation_interval)
        # Phase 5.3: Leverage multiplier (1.0 = no leverage, 1.5 = 150% gross exposure)
        self.leverage_multiplier = max(1.0, float(leverage_multiplier))
        # C-01: Point-in-time universe manager (eliminates survivorship bias in backtests)
        self.universe_manager = universe_manager
        # C-06: Real per-symbol ADV for Almgren-Chriss market impact.
        # Keys are uppercase symbols, values are USD notional/day.
        # Falls back to tier-based estimates when a symbol is absent.
        self.adv_by_symbol: dict[str, float] = adv_by_symbol or {}
        # Phase 3: Intraday support ÔÇö bars per trading day (1=daily, 7=1h, 78=5min)
        self.bars_per_day: int = max(1, int(bars_per_day))
        self.time_stop = time_stop if time_stop is not None else TimeStopManager()
        self.spread_corr_guard = spread_corr_guard if spread_corr_guard is not None else SpreadCorrelationGuard()
        self.risk_engine = risk_engine
        self.max_position_loss_pct = max_position_loss_pct
        # Phase 0.2: Kelly position sizer (institutional sizing)
        self.kelly_sizer = kelly_sizer
        self._sector_map = sector_map or {}
        # Phase 0.3: Earnings/event blackout filter
        self.event_filter = event_filter or EventFilter()
        # Phase 0.4: Short borrow availability checker
        self.borrow_checker = borrow_checker or BorrowChecker()
        # Phase 3: PCA factor monitor (complements pairwise corr guard)
        self.pca_monitor = PCASpreadMonitor()
        # Phase 3: Partial profit-taking (audit ┬º4.4 ÔÇô staged exits)
        self.partial_profit = PartialProfitManager()
        # Phase 2.1: Factor model for beta-neutral pair weights
        self.factor_model = FactorModel()
        # Phase 2.2: Sector exposure monitor
        # Scale max_sector_weight proportionally with leverage so the same
        # number of concurrent same-sector positions are allowed regardless
        # of leverage (1├ù leverage: 2 tech pairs = 100% weight; 1.5├ù leverage:
        # 2 tech pairs = 150% weight ÔåÆ limit scales to 1.5 to preserve parity).
        from risk.sector_exposure import SectorExposureConfig as _SecCfg

        self.sector_monitor = SectorExposureMonitor(
            sector_map=self._sector_map,
            config=_SecCfg(max_sector_weight=1.0 * self.leverage_multiplier),
        )
        # Phase 2.3: VaR/CVaR rolling monitor
        # Scale var_limit_pct proportionally with leverage so the same effective
        # number of entries are blocked (a 1.5├ù leveraged portfolio naturally has
        # 1.5├ù larger daily returns, so the 2% raw limit should scale to 3%).
        from risk.var_monitor import VaRConfig as _VaRConfig

        self.var_monitor = VaRMonitor(
            config=_VaRConfig(
                var_limit_pct=0.02 * self.leverage_multiplier,
            )
        )
        # Phase 2.4: Multi-tier drawdown manager (replaces simple DD breaker)
        self.drawdown_manager = DrawdownManager()
        # Phase 3.2: Intraday signal engine (fast MR + gap + volume)
        self.intraday_signal_engine = IntradaySignalEngine()
        # Phase 3.3: Algo execution (TWAP/VWAP) for realistic backtest fills
        # C-12: impact_bps from CostConfig (single source of truth)
        from config.settings import get_settings as _gs_algo

        self._algo_executor = TWAPExecutor(
            config=AlgoConfig(
                algo_type=AlgoType.TWAP,
                num_slices=10,
                impact_bps=_gs_algo().costs.taker_fee_bps,
                max_participation=0.05,
            )
        )
        # Phase 4.1: Earnings surprise (PEAD) signal
        self.earnings_signal = EarningsSurpriseSignal()
        # Phase 4.2: Options flow signal (backtest proxy)
        self.options_flow_signal = OptionsFlowSignal()
        # Phase 4.3: Sentiment signal (backtest proxy)
        self.sentiment_signal = SentimentSignal()
        # Phase 4.4: ML signal combiner (walk-forward GBM)
        self.ml_combiner = MLSignalCombiner(
            entry_threshold=0.30,
            exit_threshold=0.12,
            min_samples=15,
            retrain_interval=63,
        )
        # Legacy Phase 4 DD breaker kept for backward compat (tier 3 now replaces)
        self.portfolio_dd_limit = 0.15
        self.portfolio_dd_cooldown_bars = 10
        self._dd_cooldown_remaining = 0
        # Phase 4: Portfolio heat limit (aggregate risk budget)
        self.max_portfolio_heat = max_portfolio_heat
        # Phase 5: Trailing stop ÔÇô protect profits once in the money
        self.trailing_stop_activation_pct = 0.015  # activate at 1.5% profit
        self.trailing_stop_trail_pct = 0.01  # trail 1.0% from peak unrealized
        # Post-v27: Market-level regime filter (SPY MA + realized vol)
        from config.settings import get_settings

        _regime_cfg = get_settings().regime
        self.market_regime_filter = MarketRegimeFilter(
            ma_fast=_regime_cfg.ma_fast,
            ma_slow=_regime_cfg.ma_slow,
            vol_threshold=_regime_cfg.vol_threshold,
            vol_window=_regime_cfg.vol_window,
            neutral_band_pct=_regime_cfg.neutral_band_pct,
            enabled=_regime_cfg.enabled,
            trend_favorable_sizing=_regime_cfg.trend_favorable_sizing,
            neutral_sizing=_regime_cfg.neutral_sizing,
        )
        # Post-v27 ├ëtape 3: Dynamic pair blacklist
        _bl_cfg = get_settings().pair_blacklist
        self.pair_blacklist = PairBlacklist(
            max_consecutive_losses=_bl_cfg.max_consecutive_losses,
            cooldown_days=_bl_cfg.cooldown_days,
            enabled=_bl_cfg.enabled,
        )
        # Post-v27 ├ëtape 4: Directional bias ÔÇö reduce/block shorts in bull trend
        _strat_cfg = get_settings().strategy
        self._short_sizing_multiplier = _strat_cfg.short_sizing_multiplier
        self._disable_shorts_in_bull_trend = _strat_cfg.disable_shorts_in_bull_trend
        # Post-v28: Directional regime filter ÔÇö allow longs in TRENDING
        self._regime_directional_filter = _strat_cfg.regime_directional_filter
        self._trend_long_sizing = _strat_cfg.trend_long_sizing
        # v46: Cross-sectional momentum divergence filter (rejects trending pairs)
        self.momentum_filter = momentum_filter

    # ==================================================================
    # Public API
    # ==================================================================

    def run(
        self,
        prices_df: pd.DataFrame,
        fixed_pairs: list[tuple[str, str, float, float]] | None = None,
        sector_map: dict[str, str] | None = None,
        weekly_prices: pd.DataFrame | None = None,
        oos_start_date: str | None = None,
    ) -> BacktestMetrics:
        """
        Run a bar-by-bar backtest using the live strategy code.

        Execution timing convention (C-02):
            Signal generated at bar T close → fill at bar T+1 open price.
            Entries at the final bar are skipped (no T+1 bar available).
            Exits are filled at min(T+1, last_bar) — always closed.

        Args:
            prices_df: Price DataFrame — columns are symbol names,
                       index is DatetimeIndex (daily).
            fixed_pairs: If provided, these pairs are used for the **entire**
                         run instead of periodic re-discovery.  Intended for
                         walk-forward periods where pairs come from the
                         training window.
            sector_map: Optional dict mapping symbol ÔåÆ sector name.
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
            object.__setattr__(strategy, "sector_map", sector_map)

        # ---- Align the strategy's internal equity tracker with the actual
        #      initial capital so the drawdown guard doesn't misfire when the
        #      backtest uses a different capital than the config default.
        strategy.peak_equity = self.initial_capital
        strategy.current_equity = self.initial_capital

        # ---- Annualisation: 252 trading days ├ù bars per day ----
        _ann_bars = 252 * self.bars_per_day
        set_trading_days(_ann_bars)
        logger.info("annualisation_set", trading_days=_ann_bars, bars_per_day=self.bars_per_day)

        # Portfolio tracking
        positions = SimulatedOrderBook()
        portfolio_values: list[float] = [self.initial_capital]
        daily_returns: list[float] = []
        trades_pnl: list[float] = []  # round-trip P&L per closed trade
        _trade_durations: list[int] = []  # C-06: holding bars per closed trade
        _total_slippage: float = 0.0  # C-04: cumulative slippage across all entries

        lookback_min = max(60, strategy.config.lookback_window)

        if len(prices_df) <= lookback_min:
            logger.warning(
                "simulator_insufficient_data",
                rows=len(prices_df),
                required=lookback_min,
            )
            return self._empty_metrics(prices_df)

        # Phase 0.3: Pre-compute earnings blackout dates from price gaps
        self.event_filter.build_blackout_from_prices(prices_df)

        current_pairs: list[tuple] | None = fixed_pairs
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
        # Circuit breaker high-water mark ÔÇö resets after cooldown so the
        # breaker doesn't permanently disable trading.
        _dd_hw_mark = float(self.initial_capital)
        _dd_sizing_mult = 1.0  # Phase 2.4: updated each bar by DrawdownManager

        # ---- Walk-forward OOS tracking --------------------------------
        # When oos_start_date is provided the simulation warms up on the
        # training window (bars before oos_start_date) but only collects
        # performance metrics for the OOS period.  This gives proper
        # walk-forward statistics without look-ahead bias.
        oos_tracker = OOSTracker(oos_start_date)
        oos_tracker.initialize(prices_df, lookback_min)

        from tqdm import tqdm

        print("[BACKTEST] D├®marrage du backtest principal...")
        for bar_idx in tqdm(range(lookback_min, len(prices_df)), desc="Backtest", ncols=80):
            hist_prices = prices_df.iloc[: bar_idx + 1]

            # ---- Inject bar timestamp into strategy clock (backtest determinism)
            _bar_ts = prices_df.index[bar_idx]
            # _clock should be a callable that returns the timestamp
            _clock_fn: Callable[[], Any] = lambda _ts=_bar_ts: _ts
            strategy._clock = _clock_fn

            # ---- Phase 4: Wire strategy equity tracker (activates DD guard) --
            strategy.update_equity(portfolio_values[-1])

            # Initialize bar-level P&L accumulator
            realized_pnl = 0.0

            # ---- Phase 2.4: Multi-tier drawdown manager ----
            if portfolio_values[-1] > _dd_hw_mark:
                _dd_hw_mark = portfolio_values[-1]
            _dd_action = self.drawdown_manager.evaluate(
                current_equity=portfolio_values[-1],
                peak_equity=_dd_hw_mark,
            )
            # Bug fix: when tier-3 cooldown expires the manager resets its
            # internal peak, but the simulator's _dd_hw_mark still points to
            # the pre-DD all-time high. Without resetting here, the next
            # evaluate() call recomputes the same 8%+ DD and re-triggers
            # tier-3 immediately ÔåÆ infinite halt loop blocking all OOS trades.
            if _dd_action.reset_peak:
                _dd_hw_mark = portfolio_values[-1]
            if _dd_action.is_halted:
                # Tier 3/4: force-close all + skip bar
                fc_pnl = 0.0
                for pk in list(positions.keys_list()):
                    pc = positions.pop(pk)
                    cpnl, tpnl, _dur = self._close_position(pc, prices_df, bar_idx)
                    fc_pnl += cpnl
                    trades_pnl.append(tpnl)
                    _trade_durations.append(_dur)
                    self.spread_corr_guard.remove_spread(pk)
                    self.pca_monitor.remove_spread(pk)
                    self.partial_profit.remove(pk)
                new_val = portfolio_values[-1] + fc_pnl
                dr = fc_pnl / portfolio_values[-1] if portfolio_values[-1] > 0 else 0.0
                daily_returns.append(dr)
                portfolio_values.append(new_val)
                oos_tracker.record(bar_idx, len(trades_pnl), dr)
                prev_unrealised_total = 0.0
                # Feed VaR monitor even during halt
                self.var_monitor.update(dr)
                continue
            elif _dd_action.close_fraction > 0:
                # Tier 2: close a fraction of positions (weakest first by P&L)
                _n_to_close = max(1, int(len(positions) * _dd_action.close_fraction))
                for pk in positions.weakest_positions(prices_df, bar_idx, _n_to_close):
                    pc = positions.pop(pk)
                    cpnl, tpnl, _dur = self._close_position(pc, prices_df, bar_idx)
                    realized_pnl += cpnl
                    trades_pnl.append(tpnl)
                    _trade_durations.append(_dur)
                    self.spread_corr_guard.remove_spread(pk)
                    self.pca_monitor.remove_spread(pk)
                    self.partial_profit.remove(pk)
                    strategy.active_trades.pop(pk, None)
            # Store sizing multiplier for tier 1 dampening (used at entry below)
            _dd_sizing_mult = _dd_action.sizing_multiplier

            # ---- Pair discovery ÔÇö 2-speed architecture ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔö
            # FAST path (every pair_validation_interval bars): use Cython
            # rolling z-score to drop existing pairs whose spread has become
            # non-stationary (ADF-equivalent: rolling std drift > 2¤â baseline).
            # SLOW path (every pair_rediscovery_interval bars): full EG + NW
            # discovery to find new pairs.
            if fixed_pairs is None:
                # ÔöÇÔöÇ Slow path: full EG re-discovery ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
                if bars_since_discovery >= self.pair_rediscovery_interval:
                    strategy.reset_all_correlation_exclusions()
                    # C-01: Filter hist_prices columns to PIT universe when available
                    if self.universe_manager is not None:
                        _bar_date = prices_df.index[bar_idx]
                        _pit_syms = set(self.universe_manager.get_symbols_as_of(_bar_date))
                        _discovery_prices = hist_prices[[c for c in hist_prices.columns if c in _pit_syms]]
                    else:
                        _discovery_prices = hist_prices
                    current_pairs = strategy.find_cointegrated_pairs(
                        _discovery_prices,
                        use_cache=False,
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

                # ÔöÇÔöÇ Fast path: lightweight spread stationarity check ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
                # Runs every pair_validation_interval bars between EG cycles.
                # Drops pairs whose rolling spread std has expanded >2.5├ù the
                # baseline std (sign of cointegration breakdown) ÔÇö O(n) in C.
                if (
                    _HALF_LIFE_CYTHON_SIM
                    and current_pairs
                    and (bar_idx % self.pair_validation_interval) == 0
                    and bars_since_discovery > 0  # skip when EG just ran
                ):
                    _valid_pairs = []
                    for _p in current_pairs:
                        _s1, _s2 = _p[0], _p[1]
                        if _s1 not in hist_prices.columns or _s2 not in hist_prices.columns:
                            continue
                        _y_v = hist_prices[_s1].values.astype(np.float64)
                        _x_v = hist_prices[_s2].values.astype(np.float64)
                        _xm_v = _x_v.mean()
                        _ym_v = _y_v.mean()
                        _xc_v = _x_v - _xm_v
                        _xx_v = float(np.dot(_xc_v, _xc_v))
                        _b_v = float(np.dot(_xc_v, _y_v - _ym_v)) / (_xx_v if _xx_v > 1e-10 else 1e-10)
                        _i_v = _ym_v - _b_v * _xm_v
                        _sp_v = np.ascontiguousarray(_y_v - (_i_v + _b_v * _x_v), dtype=np.float64)
                        # Compute z-score on full window; if |z| > 4 the spread
                        # has structurally broken — drop the pair until next EG.
                        if _compute_zscore_last_fast is None:
                            _valid_pairs.append(_p)
                            continue
                        _z_v = _compute_zscore_last_fast(_sp_v, min(60, len(_sp_v)))
                        if abs(_z_v) <= 4.0:
                            _valid_pairs.append(_p)
                    if len(_valid_pairs) < len(current_pairs):
                        logger.debug(
                            "pairs_invalidated_fast_check",
                            bar=bar_idx,
                            dropped=len(current_pairs) - len(_valid_pairs),
                        )
                    current_pairs = _valid_pairs

            # ---- PRE-SIGNAL P&L stop: cut losers before signal processing ----
            # Phase 4: Update advanced signal generators each bar
            self.earnings_signal.update(hist_prices)
            self.options_flow_signal.update(hist_prices)
            self.sentiment_signal.update(hist_prices, sector_map=sector_map)
            # realized_pnl already initialised to 0.0 above (before DD section)
            if self.max_position_loss_pct > 0:
                for pair_key in list(positions.keys_list()):
                    pos = positions[pair_key]
                    sym1, sym2 = pos["sym1"], pos["sym2"]
                    cur_p1 = prices_df[sym1].iloc[bar_idx]
                    cur_p2 = prices_df[sym2].iloc[bar_idx]
                    ep1, ep2 = pos["entry_price_1"], pos["entry_price_2"]
                    _n1 = pos.get("notional_1", pos["notional"] / 2.0)
                    _n2 = pos.get("notional_2", pos["notional"] / 2.0)
                    if pos["side"] == "long":
                        r1 = (cur_p1 - ep1) / ep1 if ep1 else 0
                        r2 = (ep2 - cur_p2) / ep2 if ep2 else 0
                    else:
                        r1 = (ep1 - cur_p1) / ep1 if ep1 else 0
                        r2 = (cur_p2 - ep2) / ep2 if ep2 else 0
                    unrealised = _n1 * r1 + _n2 * r2
                    loss_pct = -unrealised / pos["notional"] if pos["notional"] > 0 else 0
                    # Phase 0.2: Use per-position NAV-based stop if available
                    _stop_limit = pos.get("nav_stop_pct", self.max_position_loss_pct)
                    if loss_pct >= _stop_limit:
                        pos_closed = positions.pop(pair_key)
                        close_pnl, trade_pnl, _dur = self._close_position(pos_closed, prices_df, bar_idx)
                        realized_pnl += close_pnl
                        trades_pnl.append(trade_pnl)
                        _trade_durations.append(_dur)
                        self.spread_corr_guard.remove_spread(pair_key)
                        self.pca_monitor.remove_spread(pair_key)
                        self.partial_profit.remove(pair_key)
                        strategy.active_trades.pop(pair_key, None)
                        logger.debug(
                            "pre_signal_pnl_stop",
                            pair=pair_key,
                            loss_pct=f"{loss_pct:.2%}",
                            limit=f"{_stop_limit:.2%}",
                            trade_pnl=round(trade_pnl, 2),
                        )

            # ---- Generate signals via LIVE strategy code ------------
            signals = strategy.generate_signals(
                hist_prices,
                discovered_pairs=current_pairs,
                weekly_prices=weekly_prices,
            )

            # ---- Post-v27: Market regime filter (SPY-based) ---------
            # Classify the current market regime using SPY data.
            # In TRENDING regime: block all new entry signals.
            # In NEUTRAL regime: sizing_multiplier = 0.5 (applied below).
            _spy_col = None
            for _c in ("SPY", "spy"):
                if _c in hist_prices.columns:
                    _spy_col = _c
                    break
            if _spy_col is not None:
                _regime_state = self.market_regime_filter.classify(hist_prices[_spy_col])
                _regime_sizing = _regime_state.sizing_multiplier
            else:
                # No SPY data available ÔÇö skip regime filter
                _regime_state = None
                _regime_sizing = 1.0

            # v47: Market-level cross-sectional dispersion gate (smooth-bull blocker).
            # Computed once per bar; blocks ALL new entries when universe return
            # dispersion < min_dispersion (stocks co-trending, no genuine relative value).
            _dispersion_ok = True
            if self.momentum_filter is not None:
                _dispersion_ok, _disp_reason = self.momentum_filter.check_market_dispersion(hist_prices)
                if not _dispersion_ok:
                    logger.debug("entries_blocked_low_dispersion", reason=_disp_reason)

            # ---- Process signals (entries & exits) ------------------
            # realized_pnl is already initialized above (before pre-signal P&L stop)

            for signal in signals:
                pair_key = signal.symbol_pair
                parts = pair_key.split("_")
                if len(parts) != 2:
                    continue
                sym1, sym2 = parts

                if sym1 not in prices_df.columns or sym2 not in prices_df.columns:
                    continue

                # --- ENTRY -------------------------------------------
                if signal.side in ("long", "short") and pair_key not in positions:
                    # v30: Adaptive bidirectional regime gate
                    # Uses per-side sizing from MarketRegimeState.
                    # BULL_TRENDING: longs allowed, shorts blocked
                    # BEAR_TRENDING: shorts allowed, longs blocked
                    # MEAN_REVERTING: both at 100%
                    # NEUTRAL: both at neutral_sizing
                    if _regime_state is not None:
                        _side_sizing = (
                            _regime_state.long_sizing if signal.side == "long" else _regime_state.short_sizing
                        )
                    else:
                        _side_sizing = 1.0

                    if _side_sizing <= 0.0:
                        logger.debug(
                            "entry_blocked_regime_adaptive",
                            pair=pair_key,
                            side=signal.side,
                            regime=_regime_state.regime.value if _regime_state else "unknown",
                            ma_spread_pct=f"{_regime_state.ma_spread_pct:.4f}" if _regime_state else "N/A",
                            realized_vol=f"{_regime_state.realized_vol:.4f}" if _regime_state else "N/A",
                        )
                        continue

                    _signal_regime_mult = _side_sizing

                    # v47: Cross-sectional dispersion gate (bar-level, computed above).
                    # Block when universe returns are too synchronized (smooth bull).
                    if not _dispersion_ok:
                        logger.debug(
                            "entry_blocked_low_dispersion",
                            pair=pair_key,
                            reason=_disp_reason,
                        )
                        continue

                    # Post-v27 ├ëtape 3: Dynamic pair blacklist gate
                    _bar_date = pd.Timestamp(prices_df.index[bar_idx]).date()
                    if self.pair_blacklist.is_blocked(pair_key, _bar_date):
                        logger.debug(
                            "entry_blocked_pair_blacklist",
                            pair=pair_key,
                            date=str(_bar_date),
                        )
                        continue

                    # Phase 0.3 ÔÇô Earnings/event blackout gate
                    if self.event_filter.is_pair_blackout(sym1, sym2, _bar_date):
                        logger.debug(
                            "entry_blocked_event_blackout",
                            pair=pair_key,
                            date=str(_bar_date),
                        )
                        continue

                    # Phase 0.4 ÔÇô Short borrow availability gate
                    _short_sym = sym2 if signal.side == "long" else sym1
                    _borrow_ok, _borrow_fee = self.borrow_checker.check_shortable(_short_sym, side="short")
                    if not _borrow_ok:
                        logger.debug(
                            "entry_rejected_borrow_check",
                            pair=pair_key,
                            short_sym=_short_sym,
                            borrow_fee=_borrow_fee,
                        )
                        continue

                    # Sprint 1.6 ÔÇô Spread correlation guard (C-06 fix)
                    candidate_spread = self._compute_spread(hist_prices, sym1, sym2)
                    if candidate_spread is not None:
                        allowed, reject_reason = self.spread_corr_guard.check_entry(pair_key, candidate_spread)
                        if not allowed:
                            logger.debug(
                                "entry_rejected_spread_correlation",
                                pair=pair_key,
                                reason=reject_reason,
                            )
                            continue
                        pca_ok, pca_reason = self.pca_monitor.check_entry(pair_key, candidate_spread)
                        if not pca_ok:
                            logger.debug(
                                "entry_rejected_pca_factor",
                                pair=pair_key,
                                reason=pca_reason,
                            )
                            continue

                    # v46 ÔÇô Cross-sectional momentum divergence guard
                    # Reject entries where one leg is a universe momentum outlier
                    # (prevents entering cointegrated pairs that currently trend).
                    if self.momentum_filter is not None:
                        _mom_ok, _mom_reason = self.momentum_filter.check_entry_allowed(sym1, sym2, hist_prices)
                        if not _mom_ok:
                            logger.debug(
                                "entry_rejected_momentum_divergence",
                                pair=pair_key,
                                reason=_mom_reason,
                            )
                            continue

                    # --- Quality-weighted allocation ---------------------
                    # Better pairs (lower p-value, favourable half-life)
                    # receive up to 1.5├ù the base allocation; weak pairs 0.5├ù.
                    pair_pvalue = self._resolve_pvalue(pair_key, current_pairs)
                    pair_hl_alloc = self._resolve_half_life(pair_key, current_pairs)
                    quality_mult = self._allocation_quality_multiplier(pair_pvalue, pair_hl_alloc)
                    adjusted_alloc = self.allocation_pct * quality_mult

                    # Phase 4 ÔÇô Volatility-based position sizing
                    # Inverse-vol: allocate less to volatile spreads
                    vol_mult = self._volatility_sizing_multiplier(hist_prices, sym1, sym2)
                    adjusted_alloc *= vol_mult

                    # Phase 1 ÔÇô Signal strength sizing (disabled until
                    # universe expansion provides enough trades for the
                    # combiner quality filter to differentiate).
                    # _sig_strength = getattr(signal, 'strength', 1.0)
                    # if 0.0 < _sig_strength < 1.0:
                    #     _str_mult = 0.85 + 0.15 * _sig_strength
                    #     adjusted_alloc *= _str_mult

                    # Phase 4 ÔÇô Regime-adaptive allocation
                    # Use regime detector output (not signal.strength which
                    # represents z-score magnitude, NOT regime state).
                    # Only scale down in confirmed HIGH-volatility regimes.

                    # Post-v27: Apply market regime sizing multiplier
                    # Uses per-signal regime mult (directional filter aware)
                    if _signal_regime_mult < 1.0 and _signal_regime_mult > 0.0:
                        adjusted_alloc *= _signal_regime_mult
                        logger.debug(
                            "regime_sizing_applied",
                            pair=pair_key,
                            regime=_regime_state.regime.value if _regime_state else "neutral",
                            multiplier=_regime_sizing,
                        )

                    # (v30: Short/long directional bias is now handled by the
                    # adaptive regime filter above via per-side sizing.
                    # The old Etape 4 block is no longer needed.)

                    # Enforce a combined multiplier floor so stacked dampeners
                    # never reduce allocation below 50% of the base.
                    effective_mult = (adjusted_alloc / self.allocation_pct) if self.allocation_pct > 0 else 1.0
                    if effective_mult < 0.5:
                        adjusted_alloc = self.allocation_pct * 0.5

                    # Phase 0.2: Kelly-based allocation override
                    if self.kelly_sizer is not None:
                        # Compute sector exposure for concentration limit
                        _sym1_sector = self._sector_map.get(sym1)
                        _sym2_sector = self._sector_map.get(sym2)
                        _pair_sector = _sym1_sector or _sym2_sector
                        _sector_exp = self._compute_sector_exposure(positions._positions, portfolio_values[-1])
                        _gross_exp = sum(p["notional"] for p in positions.values_list())

                        kelly_alloc = self.kelly_sizer.compute_allocation(
                            current_equity=portfolio_values[-1],
                            sector=_pair_sector,
                            sector_exposure=_sector_exp,
                            current_gross_exposure=_gross_exp,
                        )

                        if kelly_alloc <= 0:
                            logger.debug(
                                "entry_rejected_kelly",
                                pair=pair_key,
                                reason="kelly_alloc_zero",
                            )
                            continue

                        # Kelly caps the allocation; quality/vol/regime
                        # multipliers still apply as dampeners within kelly cap
                        adjusted_alloc = min(adjusted_alloc, kelly_alloc)

                    notional = portfolio_values[-1] * adjusted_alloc / 100.0 * self.leverage_multiplier

                    # Phase 2.4 ÔÇô Drawdown tier 1 sizing dampener
                    if _dd_sizing_mult < 1.0:
                        adjusted_alloc *= _dd_sizing_mult
                        notional = portfolio_values[-1] * adjusted_alloc / 100.0 * self.leverage_multiplier

                    # Phase 4 — Portfolio heat enforcement
                    current_heat = positions.portfolio_heat(portfolio_values[-1])
                    if (
                        current_heat + (notional / portfolio_values[-1] if portfolio_values[-1] > 0 else 0)
                        > self.max_portfolio_heat
                    ):
                        logger.debug(
                            "entry_rejected_portfolio_heat",
                            pair=pair_key,
                            current_heat=f"{current_heat:.2%}",
                            limit=f"{self.max_portfolio_heat:.2%}",
                        )
                        continue

                    # Phase 2.2 ÔÇô Sector exposure gate
                    _sec_ok, _sec_reason = self.sector_monitor.can_enter(
                        pair_key, notional, portfolio_values[-1], positions._positions
                    )
                    if not _sec_ok:
                        logger.debug(
                            "entry_rejected_sector_exposure",
                            pair=pair_key,
                            reason=_sec_reason,
                        )
                        continue

                    # Phase 2.3 ÔÇô VaR limit gate
                    _var_ok, _var_breach = self.var_monitor.check_limit(portfolio_values[-1])
                    if not _var_ok:
                        logger.debug(
                            "entry_rejected_var_limit",
                            pair=pair_key,
                            reason=_var_breach,
                        )
                        continue

                    notional_per_leg = notional / 2.0

                    # Phase 2.1 ÔÇô Beta-neutral leg weighting
                    if signal.side == "long":
                        _sym_long, _sym_short = sym1, sym2
                    else:
                        _sym_long, _sym_short = sym2, sym1
                    _beta_ratio = self.factor_model.compute_beta_neutral_ratio(
                        prices_df, _sym_long, _sym_short, bar_idx
                    )
                    # Redistribute total notional between legs for beta neutrality
                    _n_long_leg = notional / (1.0 + _beta_ratio)
                    _n_short_leg = notional * _beta_ratio / (1.0 + _beta_ratio)
                    # Map back to sym1 / sym2 ordering
                    if signal.side == "long":
                        _notional_1, _notional_2 = _n_long_leg, _n_short_leg
                    else:
                        _notional_1, _notional_2 = _n_short_leg, _n_long_leg

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

                    # Compute per-symbol daily volatility for Almgren-Chriss slippage
                    _sigma1 = self._estimate_sigma(hist_prices, sym1)
                    _sigma2 = self._estimate_sigma(hist_prices, sym2)
                    _adv1 = self._estimate_adv(sym1, hist_prices, notional_per_leg)
                    _adv2 = self._estimate_adv(sym2, hist_prices, notional_per_leg)

                    # C-02: T+1 fill — signal at bar T, execution at open of bar T+1.
                    # Skip entry at the last bar since no T+1 bar exists.
                    if bar_idx + 1 >= len(prices_df):
                        continue

                    # Phase 3.3: Use algo executor for realistic entry cost
                    _entry_px1 = prices_df[sym1].iloc[bar_idx + 1]
                    _entry_px2 = prices_df[sym2].iloc[bar_idx + 1]
                    _qty1 = _notional_1 / _entry_px1 if _entry_px1 > 0 else 0
                    _qty2 = _notional_2 / _entry_px2 if _entry_px2 > 0 else 0
                    _algo_res1 = self._algo_executor.simulate(
                        symbol=sym1,
                        side="BUY" if signal.side == "long" else "SELL",
                        total_qty=_qty1,
                        current_price=_entry_px1,
                        adv=_adv1 / _entry_px1 if _entry_px1 > 0 else 1e6,
                    )
                    _algo_res2 = self._algo_executor.simulate(
                        symbol=sym2,
                        side="SELL" if signal.side == "long" else "BUY",
                        total_qty=_qty2,
                        current_price=_entry_px2,
                        adv=_adv2 / _entry_px2 if _entry_px2 > 0 else 1e6,
                    )
                    # Entry cost = sum of algo impact (in USD)
                    _algo_impact1 = abs(_algo_res1.avg_fill_price - _entry_px1) * _qty1
                    _algo_impact2 = abs(_algo_res2.avg_fill_price - _entry_px2) * _qty2
                    e_cost = _algo_impact1 + _algo_impact2
                    # Also add base commission from cost model
                    # Ajout institutionnel : co├╗t de slippage 3 composantes
                    slippage_cost_leg1 = self.slippage_model.compute(
                        notional=_notional_1,
                        adv=_adv1,
                        sigma=_sigma1,
                    )
                    slippage_cost_leg2 = self.slippage_model.compute(
                        notional=_notional_2,
                        adv=_adv2,
                        sigma=_sigma2,
                    )
                    e_cost += slippage_cost_leg1 + slippage_cost_leg2
                    _total_slippage += slippage_cost_leg1 + slippage_cost_leg2  # C-04: track cumulative slippage
                    # Commission-only portion (impact d├®j├á inclus)
                    e_cost += (
                        self.cost_model.entry_cost(
                            notional_per_leg,
                            volume_24h_sym1=_adv1,
                            volume_24h_sym2=_adv2,
                            sigma_sym1=_sigma1,
                            sigma_sym2=_sigma2,
                        )
                        * 0.3
                    )

                    # Resolve half-life for this pair (for time stop)
                    pair_hl = pair_hl_alloc  # already resolved above

                    # Phase 0.2: Compute NAV-based stop-loss
                    _nav_stop_pct = self.max_position_loss_pct
                    if self.kelly_sizer is not None:
                        _nav_stop_pct = self.kelly_sizer.compute_nav_stop_price_distance(notional, portfolio_values[-1])

                    positions[pair_key] = {
                        "side": signal.side,
                        "sym1": sym1,
                        "sym2": sym2,
                        "entry_price_1": prices_df[sym1].iloc[bar_idx + 1],
                        "entry_price_2": prices_df[sym2].iloc[bar_idx + 1],
                        "entry_bar": bar_idx + 1,  # C-02: actual fill bar
                        "notional": notional,
                        "notional_1": _notional_1,
                        "notional_2": _notional_2,
                        "beta_ratio": _beta_ratio,
                        "entry_cost": e_cost,
                        "half_life": pair_hl,
                        "peak_unrealized": 0.0,
                        "sigma1": _sigma1,
                        "sigma2": _sigma2,
                        "nav_stop_pct": _nav_stop_pct,
                        "borrow_fee_pct": _borrow_fee,
                        # Phase 4.4: Store signal features at entry for ML training
                        "ml_features": {
                            "earnings": self.earnings_signal.compute_score(sym1, sym2),
                            "options_flow": self.options_flow_signal.compute_score(sym1, sym2),
                            "sentiment": self.sentiment_signal.compute_score(sym1, sym2),
                        },
                    }
                    realized_pnl -= e_cost

                    # Register spread for correlation monitoring
                    if candidate_spread is not None:
                        self.spread_corr_guard.register_spread(pair_key, candidate_spread)
                        self.pca_monitor.register_spread(pair_key, candidate_spread)
                    # Register for partial profit tracking
                    self.partial_profit.register(pair_key)

                # --- EXIT --------------------------------------------
                elif signal.side == "exit" and pair_key in positions:
                    pos = positions.pop(pair_key)
                    close_pnl, trade_pnl, _dur = self._close_position(pos, prices_df, bar_idx)
                    realized_pnl += close_pnl
                    trades_pnl.append(trade_pnl)
                    _trade_durations.append(_dur)
                    self.spread_corr_guard.remove_spread(pair_key)
                    self.pca_monitor.remove_spread(pair_key)
                    self.partial_profit.remove(pair_key)

            # ---- Sync strategy.active_trades with simulator positions ----
            # The strategy adds to active_trades when generating signals, but
            # the simulator may reject entries (spread corr, heat, risk, etc.).
            # Remove ghost entries so the strategy doesn't think rejected
            # signals are live positions.
            ghost_keys = [k for k in strategy.active_trades if k not in positions]
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
            # stat-arb ÔÇö aligns with the z-score entry framework).
            z_stop_threshold = getattr(strategy.config, "z_score_stop", 3.5)
            for pair_key in list(positions.keys_list()):
                pos = positions[pair_key]
                sym1, sym2 = pos["sym1"], pos["sym2"]
                try:
                    if _compute_zscore_last_fast is not None:
                        # Cython fast path: inline OLS + last rolling z-score.
                        # Avoids SpreadModel construction (lstsq + HalfLifeEstimator)
                        # and pandas rolling overhead ÔÇö ~10-20x faster per call.
                        _y = hist_prices[sym1].values
                        _x = hist_prices[sym2].values
                        _xm = _x.mean()
                        _ym = _y.mean()
                        _xc = _x - _xm
                        _xx = float(np.dot(_xc, _xc))
                        _beta = float(np.dot(_xc, _y - _ym)) / (_xx if _xx > 1e-10 else 1e-10)
                        _icpt = _ym - _beta * _xm
                        _spread = np.ascontiguousarray(_y - (_icpt + _beta * _x), dtype=np.float64)
                        current_z = _compute_zscore_last_fast(_spread, 60)
                    else:
                        from models.spread import SpreadModel

                        y = hist_prices[sym1]
                        x = hist_prices[sym2]
                        from config.settings import get_settings as _gs_k

                        model = SpreadModel(y, x, kalman_delta=_gs_k().strategy.kalman_delta)
                        spread = model.compute_spread(y, x)
                        z_score_series = model.compute_z_score(spread)
                        current_z = float(z_score_series.iloc[-1])

                    # Mean-reversion exit: z reverted to near zero
                    if abs(current_z) <= strategy.config.exit_z_score:
                        pos_closed = positions.pop(pair_key)
                        close_pnl, trade_pnl, _dur = self._close_position(pos_closed, prices_df, bar_idx)
                        realized_pnl += close_pnl
                        trades_pnl.append(trade_pnl)
                        _trade_durations.append(_dur)
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
                        close_pnl, trade_pnl, _dur = self._close_position(pos_closed, prices_df, bar_idx)
                        realized_pnl += close_pnl
                        trades_pnl.append(trade_pnl)
                        _trade_durations.append(_dur)
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

            # ---- Partial profit-taking (Phase 3 ÔÇô ┬º4.4 fix) -------
            for pair_key in list(positions.keys_list()):
                pos = positions[pair_key]
                sym1, sym2 = pos["sym1"], pos["sym2"]
                cur_p1 = prices_df[sym1].iloc[bar_idx]
                cur_p2 = prices_df[sym2].iloc[bar_idx]
                ep1, ep2 = pos["entry_price_1"], pos["entry_price_2"]
                _n1 = pos.get("notional_1", pos["notional"] / 2.0)
                _n2 = pos.get("notional_2", pos["notional"] / 2.0)
                if pos["side"] == "long":
                    r1 = (cur_p1 - ep1) / ep1 if ep1 else 0
                    r2 = (ep2 - cur_p2) / ep2 if ep2 else 0
                else:
                    r1 = (ep1 - cur_p1) / ep1 if ep1 else 0
                    r2 = (cur_p2 - ep2) / ep2 if ep2 else 0
                unrealised = _n1 * r1 + _n2 * r2
                frac, force_all = self.partial_profit.check(pair_key, unrealised, pos["notional"])
                if force_all:
                    # Remainder stop: close entire remaining position
                    pos_closed = positions.pop(pair_key)
                    close_pnl, trade_pnl, _dur = self._close_position(pos_closed, prices_df, bar_idx)
                    realized_pnl += close_pnl
                    trades_pnl.append(trade_pnl)
                    _trade_durations.append(_dur)
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
                    _pp_leg = close_notional / 2.0
                    x_cost = self.cost_model.exit_cost(
                        _pp_leg,
                        volume_24h_sym1=self._estimate_adv(pos["sym1"], prices_df, _pp_leg),
                        volume_24h_sym2=self._estimate_adv(pos["sym2"], prices_df, _pp_leg),
                        sigma_sym1=pos.get("sigma1", 0.02),
                        sigma_sym2=pos.get("sigma2", 0.02),
                    )
                    realized_pnl += partial_pnl - x_cost
                    trades_pnl.append(partial_pnl - x_cost)
                    pos["notional"] *= 1 - frac
                    logger.debug(
                        "partial_profit_take",
                        pair=pair_key,
                        fraction=frac,
                        partial_pnl=round(partial_pnl - x_cost, 2),
                        remaining_notional=round(pos["notional"], 2),
                    )

            # ---- Time stop check (Sprint 1.5 ÔÇô C-05 fix) -----------
            for pair_key in list(positions.keys_list()):
                pos = positions[pair_key]
                holding_bars = bar_idx - pos["entry_bar"]
                should_exit_ts, ts_reason = self.time_stop.should_exit(holding_bars, pos.get("half_life"))
                if should_exit_ts:
                    pos_closed = positions.pop(pair_key)
                    close_pnl, trade_pnl, _dur = self._close_position(pos_closed, prices_df, bar_idx)
                    realized_pnl += close_pnl
                    trades_pnl.append(trade_pnl)
                    _trade_durations.append(_dur)
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
                for pair_key in list(positions.keys_list()):
                    pos = positions[pair_key]
                    sym1, sym2 = pos["sym1"], pos["sym2"]
                    cur_p1 = prices_df[sym1].iloc[bar_idx]
                    cur_p2 = prices_df[sym2].iloc[bar_idx]
                    ep1, ep2 = pos["entry_price_1"], pos["entry_price_2"]
                    _n1 = pos.get("notional_1", pos["notional"] / 2.0)
                    _n2 = pos.get("notional_2", pos["notional"] / 2.0)
                    if pos["side"] == "long":
                        r1 = (cur_p1 - ep1) / ep1 if ep1 else 0
                        r2 = (ep2 - cur_p2) / ep2 if ep2 else 0
                    else:
                        r1 = (ep1 - cur_p1) / ep1 if ep1 else 0
                        r2 = (cur_p2 - ep2) / ep2 if ep2 else 0
                    unrealised = _n1 * r1 + _n2 * r2
                    loss_pct = -unrealised / pos["notional"] if pos["notional"] > 0 else 0
                    # Phase 0.2: Use per-position NAV-based stop if available
                    _stop_limit = pos.get("nav_stop_pct", self.max_position_loss_pct)
                    if loss_pct >= _stop_limit:
                        pos_closed = positions.pop(pair_key)
                        close_pnl, trade_pnl, _dur = self._close_position(pos_closed, prices_df, bar_idx)
                        realized_pnl += close_pnl
                        trades_pnl.append(trade_pnl)
                        _trade_durations.append(_dur)
                        self.spread_corr_guard.remove_spread(pair_key)
                        self.pca_monitor.remove_spread(pair_key)
                        self.partial_profit.remove(pair_key)
                        strategy.active_trades.pop(pair_key, None)  # sync strategy state
                        logger.debug(
                            "pnl_stop_exit",
                            pair=pair_key,
                            loss_pct=f"{loss_pct:.2%}",
                            limit=f"{_stop_limit:.2%}",
                            trade_pnl=round(trade_pnl, 2),
                        )

            # ---- Phase 5: Trailing stop ÔÇô protect profits ---------------
            if self.trailing_stop_activation_pct > 0:
                for pair_key in list(positions.keys_list()):
                    pos = positions[pair_key]
                    sym1, sym2 = pos["sym1"], pos["sym2"]
                    cur_p1 = prices_df[sym1].iloc[bar_idx]
                    cur_p2 = prices_df[sym2].iloc[bar_idx]
                    ep1, ep2 = pos["entry_price_1"], pos["entry_price_2"]
                    _n1 = pos.get("notional_1", pos["notional"] / 2.0)
                    _n2 = pos.get("notional_2", pos["notional"] / 2.0)
                    if pos["side"] == "long":
                        r1 = (cur_p1 - ep1) / ep1 if ep1 else 0
                        r2 = (ep2 - cur_p2) / ep2 if ep2 else 0
                    else:
                        r1 = (ep1 - cur_p1) / ep1 if ep1 else 0
                        r2 = (cur_p2 - ep2) / ep2 if ep2 else 0
                    unrealised = _n1 * r1 + _n2 * r2
                    unrealised / pos["notional"] if pos["notional"] > 0 else 0
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
                            close_pnl, trade_pnl, _dur = self._close_position(pos_closed, prices_df, bar_idx)
                            realized_pnl += close_pnl
                            trades_pnl.append(trade_pnl)
                            _trade_durations.append(_dur)
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
            for _pk, _pos in positions.items_list():
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
            daily_ret = (realized_pnl + delta_unrealised) / portfolio_values[-1] if portfolio_values[-1] > 0 else 0.0
            daily_returns.append(daily_ret)
            portfolio_values.append(new_value)

            # ---- OOS tracking for walk-forward -------------------------
            oos_tracker.record(bar_idx, len(trades_pnl), daily_ret)

            # ---- Phase 2.3: Feed VaR monitor with daily return ----
            self.var_monitor.update(daily_ret)

        # ---- Force-close remaining positions at final bar -----------
        if positions:
            final_bar = len(prices_df) - 1
            fc_realized = 0.0
            for pair_key in list(positions.keys_list()):
                pos = positions.pop(pair_key)
                close_pnl, trade_pnl, _dur = self._close_position(pos, prices_df, final_bar)
                fc_realized += close_pnl
                trades_pnl.append(trade_pnl)
                _trade_durations.append(_dur)
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
                daily_ret = fc_realized / portfolio_values[-1] if portfolio_values[-1] > 0 else 0.0
                daily_returns.append(daily_ret)
                portfolio_values.append(portfolio_values[-1] + fc_realized)
                # Force-close bar is always in OOS (it's the last bar)
                oos_tracker.record(len(prices_df) - 1, len(trades_pnl), daily_ret)

        # ---- Build metrics ------------------------------------------
        # When oos_start_date was supplied, compute metrics on OOS window only.
        if oos_tracker.start_bar_idx is not None and oos_tracker.daily_returns:
            _oos_trades = trades_pnl[oos_tracker.trade_start_idx :] if oos_tracker.trade_start_idx is not None else []
            _metrics_returns = pd.Series(oos_tracker.daily_returns)
            _metrics_trades = _oos_trades
            _period_start = str(prices_df.index[oos_tracker.start_bar_idx])[:10]
            _period_end = str(prices_df.index[-1])[:10]
        else:
            _metrics_returns = pd.Series(daily_returns) if daily_returns else pd.Series([0.0])
            _metrics_trades = trades_pnl if trades_pnl else []
            _period_start = str(prices_df.index[0])[:10]
            _period_end = str(prices_df.index[-1])[:10]

        metrics = BacktestMetrics.from_returns(
            returns=_metrics_returns if len(_metrics_returns) > 0 else pd.Series([0.0]),
            trades=_metrics_trades,
            start_date=_period_start,
            end_date=_period_end,
        )
        metrics.initial_capital = self.initial_capital
        metrics.final_capital = round(portfolio_values[-1], 2)
        metrics.realized_pnl = round(portfolio_values[-1] - self.initial_capital, 2)
        if _trade_durations:
            metrics.avg_trade_duration = round(sum(_trade_durations) / len(_trade_durations), 2)

        logger.info(
            "strategy_simulation_completed",
            total_bars=len(prices_df) - lookback_min,
            total_trades=len(trades_pnl),
            final_portfolio=round(portfolio_values[-1], 2),
            total_return=f"{metrics.total_return:.2%}",
            sharpe=round(metrics.sharpe_ratio, 2),
            max_dd=f"{metrics.max_drawdown:.2%}",
            total_slippage=round(_total_slippage, 4),  # C-04: slippage measured
        )

        return metrics

    # ==================================================================
    # Internal helpers
    # ==================================================================

    @staticmethod
    def _create_fresh_strategy() -> PairTradingStrategy:
        """Create a clean strategy instance with cache disabled and
        a bar-timestamp clock injected for backtest reproducibility."""
        # Use default clock (datetime.now) ÔÇö callers can override via
        # strategy._clock = lambda: bar_timestamp  if needed.
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
        current_pairs: list[tuple] | None,
    ) -> int | None:
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
        current_pairs: list[tuple] | None,
    ) -> float | None:
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
        pvalue: float | None,
        half_life: float | None,
    ) -> float:
        """Return a multiplier in [0.5, 1.5] based on pair quality.

        Scoring:
        - p-value score  (0-1): lower p Ôåô higher score
        - half-life score (0-1): 10-40 day HL is ideal
        Final multiplier = 0.5 + score (max 1.5).
        """
        score = 0.0

        # p-value component (0-0.5): very small p Ôåô max 0.5
        if pvalue is not None and pvalue > 0:
            if pvalue < 0.001:
                score += 0.5
            elif pvalue < 0.01:
                score += 0.35
            elif pvalue < 0.05:
                score += 0.15

        # half-life component (0-0.5): sweet spot 10-40 days Ôåô max 0.5
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
    ) -> tuple[float, float, int]:
        """
        Close *pos* at *bar_idx* and return (daily_realized_pnl, full_trade_pnl).

        ``daily_realized_pnl`` ÔÇô what hits the portfolio on the exit day
        (gross P&L minus exit cost and borrowing).

        ``full_trade_pnl`` ÔÇô the complete round-trip P&L including the
        entry cost that was already deducted on the entry day.
        """
        sym1, sym2 = pos["sym1"], pos["sym2"]
        # C-02: T+1 fill — execute exit at bar T+1 (clamped to last bar).
        _n_bars = len(prices_df)
        exec_bar = min(bar_idx + 1, _n_bars - 1)
        exit_price_1 = prices_df[sym1].iloc[exec_bar]
        exit_price_2 = prices_df[sym2].iloc[exec_bar]
        entry_price_1 = pos["entry_price_1"]
        entry_price_2 = pos["entry_price_2"]
        notional = pos["notional"]
        not_1 = pos.get("notional_1", notional / 2.0)
        not_2 = pos.get("notional_2", notional / 2.0)
        notional_per_leg = notional / 2.0  # average (for cost estimation)
        holding_days = max(exec_bar - pos["entry_bar"], 0)

        # P&L per leg (% return ├ù beta-neutral per-leg notional)
        if pos["side"] == "long":
            # Long sym1, short sym2
            ret_1 = (exit_price_1 - entry_price_1) / entry_price_1 if entry_price_1 != 0 else 0.0
            ret_2 = (entry_price_2 - exit_price_2) / entry_price_2 if entry_price_2 != 0 else 0.0
        else:
            # Short sym1, long sym2
            ret_1 = (entry_price_1 - exit_price_1) / entry_price_1 if entry_price_1 != 0 else 0.0
            ret_2 = (exit_price_2 - entry_price_2) / entry_price_2 if entry_price_2 != 0 else 0.0

        pnl_gross = not_1 * ret_1 + not_2 * ret_2

        # Exit-day costs (Almgren-Chriss: use stored vol + estimated ADV)
        _sig1 = pos.get("sigma1", 0.02)
        _sig2 = pos.get("sigma2", 0.02)
        _adv1 = self._estimate_adv(sym1, prices_df, notional_per_leg)
        _adv2 = self._estimate_adv(sym2, prices_df, notional_per_leg)
        x_cost = self.cost_model.exit_cost(
            notional_per_leg,
            volume_24h_sym1=_adv1,
            volume_24h_sym2=_adv2,
            sigma_sym1=_sig1,
            sigma_sym2=_sig2,
        )
        borrow = self.cost_model.holding_cost(notional_per_leg, holding_days)
        # Phase 0.4: Use per-position borrow fee when available
        _pos_borrow_fee = pos.get("borrow_fee_pct")
        if _pos_borrow_fee is not None and _pos_borrow_fee != self.cost_model.config.borrowing_cost_annual_pct:
            borrow = notional_per_leg * (_pos_borrow_fee / 100.0 / 365.0) * holding_days
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

        # Post-v27 ├ëtape 3: Record outcome for dynamic pair blacklist
        try:
            _exit_date = pd.Timestamp(prices_df.index[bar_idx]).date()
            self.pair_blacklist.record_outcome(
                f"{sym1}_{sym2}",
                pnl=full_trade,
                trade_date=_exit_date,
            )
        except Exception:
            pass  # Non-critical ÔÇö don't break the backtest

        # Phase 0.2: Record trade for adaptive Kelly computation
        if self.kelly_sizer is not None:
            self.kelly_sizer.record_trade(full_trade)

        # Phase 4.4: Record trade outcome for ML combiner training
        _ml_feats = pos.get("ml_features")
        if _ml_feats is not None:
            self.ml_combiner.record_trade(
                bar_idx=pos["entry_bar"],
                features=_ml_feats,
                outcome=full_trade / notional if notional > 0 else 0.0,
            )

        return daily_realized, full_trade, holding_days

    @staticmethod
    def _compute_spread(
        prices_df: pd.DataFrame,
        sym1: str,
        sym2: str,
    ) -> pd.Series | None:
        """Compute a simple OLS-residual spread for the correlation guard.

        Uses log-price ratio as a lightweight proxy (avoids a full
        SpreadModel fit on every bar).  Returns ``None`` on failure.
        """
        try:
            s1 = prices_df[sym1]
            s2 = prices_df[sym2]
            if len(s1) < 30 or len(s2) < 30:
                return None
            # Normalised spread: log(s1) Ôêô ╬▓┬Àlog(s2), ╬▓ via simple OLS
            # Explicitly compute cleaned series first
            s1_cleaned = s1.replace(0, np.nan).dropna()
            s2_cleaned = s2.replace(0, np.nan).dropna()
            ls1 = pd.Series(np.log(s1_cleaned.values), index=s1_cleaned.index, dtype=float)
            ls2 = pd.Series(np.log(s2_cleaned.values), index=s2_cleaned.index, dtype=float)
            common = ls1.index.intersection(ls2.index)
            if len(common) < 30:
                return None
            ls1 = ls1.loc[common]
            ls2 = ls2.loc[common]
            beta = np.polyfit(np.asarray(ls2.values, dtype=float), np.asarray(ls1.values, dtype=float), 1)[0]
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
            # If vol is lower Ôåô bigger position (up to 1.5├ù);
            # if higher Ôåô smaller (down to 0.4├ù).
            target_vol = 0.02
            raw = target_vol / vol
            return float(np.clip(raw, 0.4, 1.5))
        except Exception:
            return 1.0

    @staticmethod
    def _estimate_sigma(
        prices_df: pd.DataFrame,
        symbol: str,
        lookback: int = 60,
    ) -> float:
        """Estimate daily return volatility for a symbol from recent prices.

        Returns a decimal (e.g. 0.02 for 2% daily vol).
        """
        try:
            series = prices_df[symbol].iloc[-lookback:]
            if len(series) < 10:
                return 0.02
            vol = series.pct_change().dropna().std()
            return max(vol, 0.005)  # floor at 0.5%
        except Exception:
            return 0.02

    # ADV estimates by market-cap tier (USD notional/day).
    # v31h universe is all mega/large-cap US equities.
    _ADV_MEGA_CAP = 500_000_000  # $500M/day ÔÇö AAPL, MSFT, NVDA, etc.
    _ADV_LARGE_CAP = 150_000_000  # $150M/day ÔÇö CL, SO, DUK, etc.
    _ADV_MID_CAP = 30_000_000  # $30M/day ÔÇö fallback

    # Symbols known to be mega-cap (top-20 ADV in v31h universe)
    _MEGA_CAP_SYMBOLS = frozenset(
        {
            "AAPL",
            "MSFT",
            "GOOGL",
            "META",
            "NVDA",
            "AMD",
            "AVGO",
            "JPM",
            "BAC",
            "SPY",
            "XOM",
            "WMT",
            "UNH",
            "JNJ",
            "PFE",
            "GS",
            "WFC",
            "C",
            "MRK",
            "ABBV",
        }
    )

    def _estimate_adv(
        self,
        symbol: str,
        prices_df: pd.DataFrame,
        notional_per_leg: float,
    ) -> float:
        """Estimate Average Daily Volume in USD for slippage calculation.

        Lookup order:
        1. ``self.adv_by_symbol`` (injected real ADV from DataLoader / caller)
        2. Static mega-cap / large-cap tier table (conservative fallback)
        """
        injected = self.adv_by_symbol.get(symbol.upper())
        if injected is not None:
            return injected
        if symbol not in prices_df.columns:
            logger.debug(
                "adv_estimate_symbol_not_in_prices",
                symbol=symbol,
                notional_per_leg=notional_per_leg,
            )
        if symbol in self._MEGA_CAP_SYMBOLS:
            return self._ADV_MEGA_CAP
        # All v31h symbols are large-cap at minimum
        return self._ADV_LARGE_CAP

    def _compute_sector_exposure(
        self,
        positions: dict[str, dict],
        portfolio_value: float,
    ) -> dict[str, float]:
        """Compute sector exposure as % of portfolio value.

        Returns dict mapping sector ÔåÆ exposure percentage.
        """
        if portfolio_value <= 0 or not positions:
            return {}
        sector_notional: dict[str, float] = {}
        for pos in positions.values():
            s1 = self._sector_map.get(pos["sym1"], "unknown")
            s2 = self._sector_map.get(pos["sym2"], "unknown")
            sector = s1 if s1 != "unknown" else s2
            sector_notional[sector] = sector_notional.get(sector, 0.0) + pos["notional"]
        return {s: (n / portfolio_value) * 100.0 for s, n in sector_notional.items()}
