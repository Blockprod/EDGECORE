import os
from dataclasses import dataclass, field
<<<<<<< HEAD
from pathlib import Path

import yaml
=======
from typing import List
>>>>>>> origin/main
from dotenv import load_dotenv
from structlog import get_logger

load_dotenv()

logger = get_logger(__name__)


@dataclass
class StrategyConfig:
    """Pair trading strategy parameters."""

    lookback_window: int = 252  # Days for cointegration
    entry_z_score: float = 2.0  # Entry threshold (P0: raised from 1.0)
<<<<<<< HEAD
    exit_z_score: float = 0.5  # Exit threshold (was 0.0 ÔÇö unreachable in float)
=======
    exit_z_score: float = 0.5   # Exit threshold (was 0.0 — unreachable in float)
>>>>>>> origin/main
    entry_z_min_spread: float = 0.50  # Min absolute spread ($) to filter micro-deviations
    short_sizing_multiplier: float = 0.50  # Sizing multiplier for shorts in TRENDING/NEUTRAL regime (P1 fix)
    disable_shorts_in_bull_trend: bool = False  # If True, block all shorts in TRENDING regime
    regime_directional_filter: bool = False  # When True, regime only blocks shorts; longs allowed in TRENDING
    trend_long_sizing: float = 0.75  # Sizing multiplier for longs in TRENDING regime (when directional filter ON)
    min_correlation: float = 0.7  # Min correlation for pairs
    max_half_life: int = 60  # Max half-life (days) for spread mean reversion
    bonferroni_correction: bool = True  # NEW: Apply Bonferroni correction to handle multiple testing
    significance_level: float = 0.05  # NEW: Nominal significance level (before Bonferroni)
    use_kalman: bool = True  # Dynamic hedge ratio via Kalman filter
    max_position_loss_pct: float = 0.10  # P&L stop per position (10% default)
    hedge_ratio_reestimation_days: int = 7  # Sprint 2.2: Reestimate hedge ratio every 7 days (was 30)
    regime_min_duration: int = 1  # Sprint 2.2: Min bars before regime transition (was 3)
<<<<<<< HEAD
    emergency_vol_threshold_sigma: float = 3.0  # Sprint 2.2: Emergency reestimate if spread vol > N¤â
    instant_transition_percentile: float = 99.0  # Sprint 2.2: Instant regime transition for extreme vol
    # Sprint 3.5: Adaptive cache TTL by regime (hours)
    cache_ttl_high_vol: int = 2  # HIGH regime -> frequent re-discovery
=======
    emergency_vol_threshold_sigma: float = 3.0  # Sprint 2.2: Emergency reestimate if spread vol > Nσ
    instant_transition_percentile: float = 99.0  # Sprint 2.2: Instant regime transition for extreme vol
    # Sprint 3.5: Adaptive cache TTL by regime (hours)
    cache_ttl_high_vol: int = 2    # HIGH regime -> frequent re-discovery
>>>>>>> origin/main
    # Sprint 4.1: Johansen double-screening confirmation
    johansen_confirmation: bool = True  # Confirm EG pairs with Johansen test
    # Sprint 4.3: Newey-West HAC consensus
    newey_west_consensus: bool = True  # Require OLS + HAC agreement for cointegration
    cache_ttl_normal_vol: int = 12  # NORMAL regime -> moderate TTL
<<<<<<< HEAD
    cache_ttl_low_vol: int = 24  # LOW regime -> stable, long TTL
    # Sprint 4.4: Self-contained internal risk limits (defense in depth)
    internal_max_positions: int = 50  # Let simulator's portfolio-heat / risk-engine control position count
    internal_max_drawdown_pct: float = (
        0.20  # 20% strategy-internal DD breaker (Tier 3: after RiskConfig 10% and KillSwitch 15%)
    )
    internal_max_daily_trades: int = 200  # Generous limit ÔÇö backtest runs all bars in one real-world day
    # Sprint 4.6: Rolling leg correlation monitoring
    leg_correlation_window: int = 30  # Rolling window (bars) for recent correlation
    leg_correlation_decay_threshold: float = 0.3  # Sweet spot ÔÇö proven by backtest optimization
    # Multi-lookback discovery: additional lookback windows (union with primary)
    additional_lookback_windows: list[int] = field(default_factory=list)
    # Z-score based stop-loss (complements PnL stop ÔÇö more natural for stat-arb)
    z_score_stop: float = 3.5  # Close position if |z| > this threshold
    # ÔöÇÔöÇ Multi-Timeframe configuration ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    # Timeframes for cointegration analysis (default: daily + weekly)
    timeframes: list[str] = field(default_factory=lambda: ["D", "W"])
=======
    cache_ttl_low_vol: int = 24     # LOW regime -> stable, long TTL
    # Sprint 4.4: Self-contained internal risk limits (defense in depth)
    internal_max_positions: int = 50       # Let simulator's portfolio-heat / risk-engine control position count
    internal_max_drawdown_pct: float = 0.20  # 20% strategy-internal DD breaker (Tier 3: after RiskConfig 10% and KillSwitch 15%)
    internal_max_daily_trades: int = 200   # Generous limit — backtest runs all bars in one real-world day
    # Sprint 4.6: Rolling leg correlation monitoring
    leg_correlation_window: int = 30          # Rolling window (bars) for recent correlation
    leg_correlation_decay_threshold: float = 0.3  # Sweet spot — proven by backtest optimization
    # Multi-lookback discovery: additional lookback windows (union with primary)
    additional_lookback_windows: List[int] = field(default_factory=list)
    # Z-score based stop-loss (complements PnL stop — more natural for stat-arb)
    z_score_stop: float = 3.5  # Close position if |z| > this threshold
    # ── Multi-Timeframe configuration ────────────────────────────────
    # Timeframes for cointegration analysis (default: daily + weekly)
    timeframes: List[str] = field(default_factory=lambda: ["D", "W"])
>>>>>>> origin/main
    # Require weekly cointegration confirmation for pair entry
    weekly_confirmation: bool = True
    # Weight of weekly cointegration in composite MTF score (0.0-1.0)
    weekly_coint_weight: float = 0.40
    # Maximum p-value for weekly cointegration confirmation
    weekly_max_pvalue: float = 0.10
    # Weekly lookback in weekly bars (~2 years)
    weekly_lookback_bars: int = 104
    # Minimum absolute weekly z-score to allow entry
    weekly_zscore_entry_gate: float = 1.0
<<<<<<< HEAD
    # FDR (False Discovery Rate) q-level for multiple testing correction
    fdr_q_level: float = 0.20  # Benjamini-Hochberg q-level (relaxed default)
    # C-07: Periodic model retraining interval (bars = trading days)
    retraining_interval_bars: int = 14  # Re-estimate hedge ratios every 2 weeks by default
    # C-11: Kalman process noise — controls how fast the hedge ratio adapts (smaller = smoother)
    kalman_delta: float = 1e-4
    # C-11 (plan): Cointegration stability filter — min fraction of rolling windows that confirm coint.
    cointegration_stability_threshold: float = 0.8
    # C-13 (plan): OOS acceptance threshold — min fraction of pairs that must pass OOS validation.
    oos_acceptance_threshold: float = 0.70

=======
>>>>>>> origin/main

@dataclass
class ScannerConfig:
    """Dynamic universe scanner configuration."""
<<<<<<< HEAD

    min_market_cap_usd: float = 500_000_000  # $500M minimum
    min_avg_volume_usd: float = 5_000_000  # $5M daily volume
    min_price: float = 5.0  # exclude penny stocks
    exchanges: list[str] = field(default_factory=lambda: ["NYSE", "NASDAQ", "AMEX"])
    cache_ttl_hours: int = 24
    ibkr_validation_workers: int = 5
    ibkr_batch_size: int = 50
    scan_enabled: bool = False  # Enable dynamic scanning
    scan_schedule_cron: str = "0 5 * * 1-5"  # Mon-Fri 5am UTC

=======
    min_market_cap_usd: float = 500_000_000     # $500M minimum
    min_avg_volume_usd: float = 5_000_000       # $5M daily volume
    min_price: float = 5.0                       # exclude penny stocks
    exchanges: List[str] = field(default_factory=lambda: ["NYSE", "NASDAQ", "AMEX"])
    cache_ttl_hours: int = 24
    ibkr_validation_workers: int = 5
    ibkr_batch_size: int = 50
    scan_enabled: bool = False                   # Enable dynamic scanning
    scan_schedule_cron: str = "0 5 * * 1-5"      # Mon-Fri 5am UTC
>>>>>>> origin/main

@dataclass
class TradingUniverseConfig:
    """Trading universe configuration (which symbols to trade)."""
<<<<<<< HEAD

    symbols: list = field(
        default_factory=lambda: [
            "AAPL",
            "MSFT",  # Default: US equities if config not available
        ]
    )
    max_leverage: float = 2.0  # Max leverage for the universe

=======
    symbols: list = field(default_factory=lambda: [
        "AAPL", "MSFT",  # Default: US equities if config not available
    ])
    max_leverage: float = 2.0  # Max leverage for the universe
>>>>>>> origin/main

@dataclass
class RiskConfig:
    """Risk management parameters."""

    max_risk_per_trade: float = 0.005  # 0.5% of equity
    max_concurrent_positions: int = 10
    max_daily_loss_pct: float = 0.02  # 2% daily loss kill-switch
    max_consecutive_losses: int = 3
    volatility_percentile_threshold: float = 1.5  # Regime break detection
    position_sizing_method: str = "volatility"  # volatility or kelly
    max_leverage: float = 2.0  # Maximum portfolio leverage (equity: 2x)
    # Drawdown Tier 1 (of 3): halt new entries. Tier 2 = kill_switch 15%. Tier 3 = strategy 20%.
    max_drawdown_pct: float = 0.10  # Portfolio drawdown hard stop (10% default)
    max_sector_weight: float = 0.40  # Max 40% of positions in a single sector
<<<<<<< HEAD
    spread_correlation_max: float = 0.40  # Max |¤ü| between spreads (R-6)


@dataclass
class CostConfig:
    """Centralised transaction cost model ÔÇö single source of truth.

=======
    spread_correlation_max: float = 0.40  # Max |ρ| between spreads (R-6)

@dataclass
class CostConfig:
    """Centralised transaction cost model — single source of truth.
    
>>>>>>> origin/main
    All execution modules (backtest, paper, live) MUST read from this config
    instead of maintaining their own hardcoded defaults.  Values calibrated
    for US equities via IBKR.
    """
<<<<<<< HEAD

    slippage_bps: float = 3.0  # Base slippage (adaptive on top)
    commission_pct: float = (
        0.00020  # IBKR Pro US equity commission (~2.0 bps/leg — aligned with CostModelConfig.taker_fee_bps)
    )
    maker_fee_bps: float = 1.5  # Exchange maker rebate/fee
    taker_fee_bps: float = 2.0  # Exchange taker fee
    borrowing_cost_annual: float = 0.005  # Short-borrow GC rate (0.5%)
    max_slippage_bps: float = 50.0  # Hard cap on adaptive slippage
    slippage_model: str = "adaptive"  # fixed_bps | adaptive | volume_based

=======
    slippage_bps: float = 3.0           # Base slippage (adaptive on top)
    commission_pct: float = 0.00035     # IBKR US equity commission (0.035%)
    maker_fee_bps: float = 1.5          # Exchange maker rebate/fee
    taker_fee_bps: float = 2.0          # Exchange taker fee
    borrowing_cost_annual: float = 0.005  # Short-borrow GC rate (0.5%)
    max_slippage_bps: float = 50.0      # Hard cap on adaptive slippage
    slippage_model: str = "adaptive"    # fixed_bps | adaptive | volume_based
>>>>>>> origin/main

@dataclass
class TradingConfig:
    """Operational constants for paper/live trading loops (F-7).

    All values formerly hardcoded in main.py are centralised here
    so they can be overridden per-environment via YAML.
    """
<<<<<<< HEAD

    max_loop_iterations: int = 100  # Max trading-loop iterations
    max_consecutive_errors: int = 10  # Halt after N consecutive failures
    data_max_age_hours: float = 99999.0  # Max staleness for OHLCV validation
    max_allocation_pct: float = 0.20  # Max single-pair allocation (20%)
    equity_tolerance_pct: float = 0.01  # Reconciler equity tolerance (%)
    reconciliation_divergence_pct: float = 0.10  # Alert threshold for periodic recon
    fallback_spread_vol: float = 0.02  # Fallback spread-vol if < 10 bars
    min_order_quantity: float = 1.0  # Floor on order quantity (shares)
    limit_price_offset_pct: float = 0.01  # Limit price = market * (1 - offset)
    # C-13: Paper mode fill rate (1.0 = 100% fill; reduce to model partial fills)
    paper_fill_rate: float = 1.0

=======
    max_loop_iterations: int = 100           # Max trading-loop iterations
    max_consecutive_errors: int = 10         # Halt after N consecutive failures
    data_max_age_hours: float = 99999.0      # Max staleness for OHLCV validation
    max_allocation_pct: float = 0.20         # Max single-pair allocation (20%)
    equity_tolerance_pct: float = 0.01       # Reconciler equity tolerance (%)
    reconciliation_divergence_pct: float = 0.10  # Alert threshold for periodic recon
    fallback_spread_vol: float = 0.02        # Fallback spread-vol if < 10 bars
    min_order_quantity: float = 1.0          # Floor on order quantity (shares)
    limit_price_offset_pct: float = 0.01     # Limit price = market * (1 - offset)
>>>>>>> origin/main

@dataclass
class ExecutionConfig:
    """Execution layer parameters."""
<<<<<<< HEAD

    engine: str = "ibkr"  # ibkr (Interactive Brokers)
=======
    engine: str = "ibkr"      # ibkr (Interactive Brokers)
>>>>>>> origin/main
    timeout_seconds: int = 30
    max_retries: int = 3
    slippage_bps: float = 2.0  # Basis points
    use_sandbox: bool = True
    # C-10: Explicit trading mode discriminant read by EDGECORE_MODE env var.
    # Values: "live" | "paper". "paper" forces use_sandbox=True and is merged
    # from config/paper.yaml when EDGECORE_MODE=paper.
    mode: str = "live"
    paper_trading_loop_interval_seconds: int = 10  # Loop sleep interval
    initial_capital: float = 100000.0  # Starting capital for paper/live trading
    paper_slippage_model: str = "fixed_bps"  # fixed_bps, adaptive, volume_based
    paper_commission_pct: float = 0.005  # Commission percentage (0.005% ≈ $0.005/share IBKR)
<<<<<<< HEAD

=======
>>>>>>> origin/main

@dataclass
class BacktestConfig:
    """Backtesting parameters."""
<<<<<<< HEAD

=======
>>>>>>> origin/main
    start_date: str = "2018-01-01"  # 8 years of US equity history
    end_date: str = "2026-01-01"
    initial_capital: float = 100000.0
    commission_bps: float = 2.0
    walk_forward_periods: int = 4
    out_of_sample_ratio: float = 0.2
    feature_store_dir: str = "data/feature_store/"  # P2: versioned spread cache
    # P-01: mark split/dividend ex-dates in prices and suppress new entries that bar
    adjust_for_corporate_actions: bool = True


@dataclass
class SecretsConfig:
    """Secrets management and rotation parameters."""

    rotation_interval_days: int = 90  # Rotate API keys every 90 days
    rotation_time_utc: str = "02:00"  # 2 AM UTC for rotation
    auto_load_from_env: bool = True  # Auto-load secrets from environment
    mask_ratio: float = 0.8  # Mask 80% of secret value in logs
    audit_trail_enabled: bool = True  # Enable audit logging for secret access


@dataclass
class BlacklistConfig:
<<<<<<< HEAD
    """Dynamic pair blacklist configuration (post-v27 ├ëtape 3).
=======
    """Dynamic pair blacklist configuration (post-v27 Étape 3).
>>>>>>> origin/main

    Tracks consecutive losses per pair and blocks re-entry for a
    configurable cooldown period.
    """
<<<<<<< HEAD

    enabled: bool = True  # Enable/disable blacklist
    max_consecutive_losses: int = 2  # Losses before blacklisting
    cooldown_days: int = 30  # Calendar days of cooldown
=======
    enabled: bool = True                     # Enable/disable blacklist
    max_consecutive_losses: int = 2          # Losses before blacklisting
    cooldown_days: int = 30                  # Calendar days of cooldown
>>>>>>> origin/main


@dataclass
class SignalCombinerConfig:
    """Signal combiner / ensemble configuration (v31).

    Controls the weighted combination of multiple alpha sources
    into a single composite entry/exit score.
    """
<<<<<<< HEAD

    enabled: bool = True  # Enable/disable signal combiner
    zscore_weight: float = 0.70  # Weight for z-score signal
    momentum_weight: float = 0.30  # Weight for momentum signal
    entry_threshold: float = 0.6  # Composite score threshold for entry
    exit_threshold: float = 0.2  # Composite score threshold for exit
    ml_combiner_shadow_mode: bool = True  # True=log ML predictions only; False=gate signals
    # ML combiner entry/exit thresholds (applied to composite ML score, scale 0–1).
    # NOTE: These govern the BACKTEST gate (ML composite ≥ threshold → enter).
    # In LIVE trading, ml_combiner_shadow_mode=True means these thresholds are NOT
    # used for entry decisions — the live gate is StrategyConfig.entry_z_score (raw z-score).
    # Backtest metrics (Sharpe, PF) reflect ML-gated performance; live uses z-score alone.
    ml_entry_threshold: float = 0.30  # ML composite score threshold for entry (backtest-calibrated)
    ml_exit_threshold: float = 0.12  # ML composite score threshold for exit (backtest-calibrated)
    use_markov_regime: bool = False  # True=use MarkovRegimeDetector (HMM) instead of RegimeDetector
=======
    enabled: bool = True               # Enable/disable signal combiner
    zscore_weight: float = 0.70       # Weight for z-score signal
    momentum_weight: float = 0.30     # Weight for momentum signal
    entry_threshold: float = 0.6      # Composite score threshold for entry
    exit_threshold: float = 0.2       # Composite score threshold for exit
>>>>>>> origin/main


@dataclass
class MomentumConfig:
    """Relative momentum overlay configuration (v31).

    Computes cross-sectional relative strength between pair legs
    and adjusts signal strength accordingly.
    """
<<<<<<< HEAD

    enabled: bool = True  # Enable/disable momentum overlay
    lookback: int = 20  # Rolling return window (bars)
    weight: float = 0.30  # Momentum weight in composite score
    min_strength: float = 0.30  # Floor for contra-momentum signals
    max_boost: float = 1.0  # Cap for momentum-confirmed signals


@dataclass
class RegimeDetectorConfig:
    """Spread-level volatility regime detector configuration (C-09: adaptive window).

    Controls RegimeDetector instances used inside SignalGenerator and PairTradingStrategy.
    """

    # Default effective lookback window (bars) — raised from 20 to 60 to capture slow regimes
    regime_window: int = 60
    # Enable adaptive window: window shrinks in high vol, grows in low vol
    adaptive_window: bool = False
    # Minimum effective window when adaptive_window=True (fast-response floor)
    min_window: int = 20
    # Maximum effective window when adaptive_window=True (stability ceiling)
    max_window: int = 120
=======
    enabled: bool = True               # Enable/disable momentum overlay
    lookback: int = 20                 # Rolling return window (bars)
    weight: float = 0.30              # Momentum weight in composite score
    min_strength: float = 0.30        # Floor for contra-momentum signals
    max_boost: float = 1.0            # Cap for momentum-confirmed signals
>>>>>>> origin/main


@dataclass
class RegimeConfig:
    """Market-level regime filter configuration (v30: adaptive bidirectional).

    Controls the SPY-based trend & volatility regime detector.
    v30: detects bull vs bear trends for per-side entry gating.
    """
<<<<<<< HEAD

    enabled: bool = True  # Enable/disable regime filter
    ma_fast: int = 50  # Fast moving average (days)
    ma_slow: int = 200  # Slow moving average (days)
    vol_threshold: float = 0.18  # Annualized realized vol threshold
    vol_window: int = 20  # Rolling window for realized vol
    neutral_band_pct: float = 0.02  # MA spread % to distinguish NEUTRAL
    trend_favorable_sizing: float = 0.80  # Sizing for favorable side in trends
    neutral_sizing: float = 0.65  # Sizing for both sides in NEUTRAL
    # C-02: Dispersion filter — block entries when market is highly correlated
    dispersion_filter_enabled: bool = False  # Off by default; ON in dev.yaml
    dispersion_filter_lookback: int = 60  # Rolling window (bars) for correlation computation
    dispersion_filter_min_index: float = 0.15  # Min std of pairwise correlations to allow entries
    # C-09: Adaptive threshold ramp above blocking floor
    dispersion_ideal_index: float = 0.30  # Above this: no threshold penalty
    dispersion_max_entry_adj: float = 0.50  # Max z-score raise at min_index boundary


@dataclass
class PortfolioConfig:
    """Portfolio engine configuration (C-07).

    Controls position sizing method used by PortfolioAllocator.
    Maps to the `portfolio:` section in YAML config files.
    """

    # Sizing method: "equal_weight" | "volatility_inverse" | "kelly" | "signal_weighted"
    # volatility_inverse is the production default: allocates more capital to
    # lower-volatility spreads, reducing tail risk from volatile-spread dominance.
    sizing_method: str = "volatility_inverse"
    # Floor on spread vol used by vol-inverse sizing (avoids division by zero)
    min_vol_floor: float = 0.001
    # Max allocation fraction per pair
    max_allocation_pct: float = 0.30
    # Max portfolio heat (total allocation fraction across all open pairs)
    max_portfolio_heat: float = 0.95
=======
    enabled: bool = True                 # Enable/disable regime filter
    ma_fast: int = 50                    # Fast moving average (days)
    ma_slow: int = 200                   # Slow moving average (days)
    vol_threshold: float = 0.18          # Annualized realized vol threshold
    vol_window: int = 20                 # Rolling window for realized vol
    neutral_band_pct: float = 0.02       # MA spread % to distinguish NEUTRAL
    trend_favorable_sizing: float = 0.80 # Sizing for favorable side in trends
    neutral_sizing: float = 0.65         # Sizing for both sides in NEUTRAL
>>>>>>> origin/main


class Settings:
    """Global configuration manager."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
<<<<<<< HEAD

        # Support multiple environment variable names: EDGECORE_ENV, ENVIRONMENT, ENV
        self.env = (os.getenv("EDGECORE_ENV") or os.getenv("ENVIRONMENT") or os.getenv("ENV") or "dev").lower()

=======
        
        # Support multiple environment variable names: EDGECORE_ENV, ENVIRONMENT, ENV
        self.env = (
            os.getenv("EDGECORE_ENV") or 
            os.getenv("ENVIRONMENT") or 
            os.getenv("ENV") or 
            "dev"
        ).lower()
        
>>>>>>> origin/main
        # Validate environment
        valid_envs = ["dev", "test", "prod"]
        if self.env not in valid_envs:
            logger.warning("invalid_environment", env=self.env, valid=valid_envs)
            self.env = "dev"
<<<<<<< HEAD

        # Valid config files: dev.yaml | test.yaml | prod.yaml (selected by EDGECORE_ENV).
        # config/config.yaml is a reference document ONLY — never loaded at runtime.
=======
        
>>>>>>> origin/main
        config_path = Path(__file__).parent / f"{self.env}.yaml"

        self.strategy = StrategyConfig()
        self.trading_universe = TradingUniverseConfig()
        self.risk = RiskConfig()
        self.execution = ExecutionConfig()
        self.backtest = BacktestConfig()
        self.secrets = SecretsConfig()
        self.costs = CostConfig()
        self.scanner = ScannerConfig()
        self.trading = TradingConfig()
        self.regime = RegimeConfig()
<<<<<<< HEAD
        self.regime_detector_config = RegimeDetectorConfig()
        self.momentum = MomentumConfig()
        self.signal_combiner = SignalCombinerConfig()
        self.pair_blacklist = BlacklistConfig()
        self.portfolio = PortfolioConfig()
=======
        self.momentum = MomentumConfig()
        self.signal_combiner = SignalCombinerConfig()
        self.pair_blacklist = BlacklistConfig()
>>>>>>> origin/main
        self.raw_config = {}

        if config_path.exists():
            logger.info("loading_config", env=self.env, path=str(config_path))
            self._load_yaml(config_path)
        else:
            logger.warning("config_not_found", env=self.env, path=str(config_path))
<<<<<<< HEAD

        # C-10: Merge paper.yaml overrides when EDGECORE_MODE=paper.
        # paper.yaml is applied ON TOP of the active env config so paper-mode
        # risk limits (lower position sizes, use_sandbox=True, mode="paper")
        # cannot be accidentally overridden by prod.yaml.
        trading_mode = (os.getenv("EDGECORE_MODE") or "").lower()
        if trading_mode == "paper":
            paper_path = Path(__file__).parent / "paper.yaml"
            if paper_path.exists():
                logger.info("applying_paper_mode_overrides", path=str(paper_path))
                self._load_yaml(paper_path)
            else:
                logger.warning("paper_yaml_not_found", path=str(paper_path))
            # Always enforce sandbox + mode when EDGECORE_MODE=paper,
            # regardless of whether paper.yaml was found.
            self.execution.use_sandbox = True
            self.execution.mode = "paper"
            logger.info("paper_mode_active", use_sandbox=True)

        # Validate configuration using Pydantic schemas
        self._validate_config()

=======
        
        # Validate configuration using Pydantic schemas
        self._validate_config()
        
>>>>>>> origin/main
        # Safety check: prevent live trading unless explicitly enabled
        if not self.execution.use_sandbox:
            if os.getenv("ENABLE_LIVE_TRADING") != "true":
                logger.warning("LIVE_TRADING_DISABLED_BY_DEFAULT")
                self.execution.use_sandbox = True  # Force sandbox mode
                logger.info("sandbox_mode_forced", reason="ENABLE_LIVE_TRADING env var not set")
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        logger.info(
            "config_loaded",
            env=self.env,
            num_symbols=len(self.trading_universe.symbols),
<<<<<<< HEAD
            initial_capital=self.execution.initial_capital,
        )

        # R-3: Assert risk-threshold tier coherence
        # Tier 1 (RiskConfig) < Tier 2 (KillSwitch) < Tier 3 (Strategy internal)
        self._assert_risk_tier_coherence()

        self._initialized = True

    def _validate_config(self) -> None:
        """Validate loaded configuration using Pydantic schemas."""
        try:
            from config.schemas import (
                AlerterConfigSchema,
                BacktestConfigSchema,
                DataSourceConfigSchema,
                ExecutionConfigSchema,
                RiskConfigSchema,
                StrategyConfigSchema,
            )

=======
            initial_capital=self.execution.initial_capital
        )
        
        # R-3: Assert risk-threshold tier coherence
        # Tier 1 (RiskConfig) < Tier 2 (KillSwitch) < Tier 3 (Strategy internal)
        self._assert_risk_tier_coherence()
        
        self._initialized = True
    
    def _validate_config(self) -> None:
        """Validate loaded configuration using Pydantic schemas."""
        try:
            from config.schemas import RiskConfigSchema, StrategyConfigSchema
>>>>>>> origin/main
            # Validate risk config
            RiskConfigSchema(
                max_drawdown_pct=self.risk.max_drawdown_pct * 100,  # schema expects 0-100
                max_loss_per_trade=self.risk.max_risk_per_trade,
            )
            # Validate strategy config
            StrategyConfigSchema(
                entry_z_score=self.strategy.entry_z_score,
                exit_z_score=self.strategy.exit_z_score,
                entry_z_min_spread=self.strategy.entry_z_min_spread,
                short_sizing_multiplier=self.strategy.short_sizing_multiplier,
<<<<<<< HEAD
            )
            # Validate execution engine constraints
            ExecutionConfigSchema()
            # Validate data source defaults
            DataSourceConfigSchema()
            # Validate alerter defaults
            AlerterConfigSchema()
            # Validate backtest date range and costs
            BacktestConfigSchema(
                start_date=self.backtest.start_date,
                end_date=self.backtest.end_date,
                initial_equity=self.backtest.initial_capital,
                slippage_pct=self.costs.slippage_bps / 100,  # bps → percent
                commission_pct=self.costs.commission_pct * 100,  # fraction → percent
=======
                lookback_window=self.strategy.lookback_window,
>>>>>>> origin/main
            )
            logger.debug("config_validation_passed")
        except ImportError:
            logger.debug("pydantic_schemas_not_available_skipping_validation")
        except Exception as exc:
            logger.error("config_validation_failed", error=str(exc)[:200])
            raise ValueError(f"Configuration validation failed: {exc}") from exc

    def _assert_risk_tier_coherence(self) -> None:
        """R-3: Assert that risk thresholds respect the tiered hierarchy.

<<<<<<< HEAD
        Tier 1 (RiskConfig)  Ôëñ  Tier 2 (KillSwitch via raw_config)  Ôëñ  Tier 3 (Strategy internal).
        Violation means a tighter tier fires after a looser one, which is
        confusing at best and dangerous at worst.
        """
        tier1_dd = self.risk.max_drawdown_pct  # e.g. 0.10
        tier3_dd = self.strategy.internal_max_drawdown_pct  # e.g. 0.20 (fraction)

        # KillSwitch tier (Tier 2) lives in raw_config YAML, not in a dataclass
        ks = (self.raw_config.get("risk", {}) or {}).get("kill_switch", {}) or {}
        tier2_dd = ks.get("max_drawdown_pct", 0.15)  # default 0.15
=======
        Tier 1 (RiskConfig)  ≤  Tier 2 (KillSwitch via raw_config)  ≤  Tier 3 (Strategy internal).
        Violation means a tighter tier fires after a looser one, which is
        confusing at best and dangerous at worst.
        """
        tier1_dd = self.risk.max_drawdown_pct              # e.g. 0.10
        tier3_dd = self.strategy.internal_max_drawdown_pct  # e.g. 0.20 (fraction)

        # KillSwitch tier (Tier 2) lives in raw_config YAML, not in a dataclass
        ks = (self.raw_config.get('risk', {}) or {}).get('kill_switch', {}) or {}
        tier2_dd = ks.get('max_drawdown_pct', 0.15)        # default 0.15
>>>>>>> origin/main

        # Normalise: config stores as fraction, strategy stores as fraction
        # but if tier3 was given as >1 interpret as percent
        if tier3_dd > 1:
            tier3_dd = tier3_dd / 100.0

        if not (tier1_dd <= tier2_dd <= tier3_dd):
            msg = (
                f"Risk-tier drawdown hierarchy violated: "
<<<<<<< HEAD
                f"Tier1(RiskConfig)={tier1_dd:.2%} Ôëñ "
                f"Tier2(KillSwitch)={tier2_dd:.2%} Ôëñ "
=======
                f"Tier1(RiskConfig)={tier1_dd:.2%} ≤ "
                f"Tier2(KillSwitch)={tier2_dd:.2%} ≤ "
>>>>>>> origin/main
                f"Tier3(Strategy)={tier3_dd:.2%} must hold."
            )
            logger.error("risk_tier_coherence_failed", detail=msg)
            raise ValueError(msg)

        logger.debug(
            "risk_tier_coherence_ok",
            tier1_dd=tier1_dd,
            tier2_dd=tier2_dd,
            tier3_dd=tier3_dd,
        )

    def _load_yaml(self, path: Path) -> None:
        """Load configuration from YAML file."""
<<<<<<< HEAD
        with open(path, encoding="utf-8") as f:
=======
        with open(path, 'r', encoding='utf-8') as f:
>>>>>>> origin/main
            config = yaml.safe_load(f) or {}

        self.raw_config = config
<<<<<<< HEAD

        # F-8: Reject unknown top-level YAML sections
        _KNOWN_SECTIONS = {
            "market",
            "strategy",
            "trading_universe",
            "risk",
            "execution",
            "backtest",
            "secrets",
            "scanner",
            "costs",
            "trading",
            "portfolio",
            "validation",
            "monitoring",
            "regime",
            "momentum",
            "signal_combiner",
            "pair_blacklist",
=======
        
        # F-8: Reject unknown top-level YAML sections
        _KNOWN_SECTIONS = {
            'market', 'strategy', 'trading_universe', 'risk', 'execution',
            'backtest', 'secrets', 'scanner', 'costs', 'trading',
            'portfolio', 'validation', 'monitoring', 'regime',
            'momentum', 'signal_combiner', 'pair_blacklist',
>>>>>>> origin/main
        }
        unknown_sections = set(config.keys()) - _KNOWN_SECTIONS
        if unknown_sections:
            logger.error(
                "unknown_top_level_config_sections",
                unknown=sorted(unknown_sections),
                valid=sorted(_KNOWN_SECTIONS),
            )
            raise ValueError(
                f"Unknown top-level config section(s): {sorted(unknown_sections)}. "
                f"Valid sections: {sorted(_KNOWN_SECTIONS)}"
            )
<<<<<<< HEAD

        if "strategy" in config:
            self._apply_section(self.strategy, config["strategy"], "strategy")

        if "trading_universe" in config:
            # F-8: Use _apply_section for strict validation (was manual)
            self._apply_section(self.trading_universe, config["trading_universe"], "trading_universe")

        if "risk" in config:
            self._apply_section(self.risk, config["risk"], "risk")

        if "execution" in config:
            self._apply_section(self.execution, config["execution"], "execution")

        if "backtest" in config:
            self._apply_section(self.backtest, config["backtest"], "backtest")

        if "secrets" in config:
            self._apply_section(self.secrets, config["secrets"], "secrets")

        if "scanner" in config:
            self._apply_section(self.scanner, config["scanner"], "scanner")

        if "costs" in config:
            self._apply_section(self.costs, config["costs"], "costs")

        if "trading" in config:
            self._apply_section(self.trading, config["trading"], "trading")

        if "regime" in config:
            self._apply_section(self.regime, config["regime"], "regime")

        if "momentum" in config:
            self._apply_section(self.momentum, config["momentum"], "momentum")

        if "signal_combiner" in config:
            self._apply_section(self.signal_combiner, config["signal_combiner"], "signal_combiner")

        if "pair_blacklist" in config:
            self._apply_section(self.pair_blacklist, config["pair_blacklist"], "pair_blacklist")

        if "portfolio" in config:
            self._apply_section(self.portfolio, config["portfolio"], "portfolio")
=======
        
        if 'strategy' in config:
            self._apply_section(self.strategy, config['strategy'], 'strategy')
        
        if 'trading_universe' in config:
            # F-8: Use _apply_section for strict validation (was manual)
            self._apply_section(self.trading_universe, config['trading_universe'], 'trading_universe')
        
        if 'risk' in config:
            self._apply_section(self.risk, config['risk'], 'risk')
        
        if 'execution' in config:
            self._apply_section(self.execution, config['execution'], 'execution')
        
        if 'backtest' in config:
            self._apply_section(self.backtest, config['backtest'], 'backtest')
        
        if 'secrets' in config:
            self._apply_section(self.secrets, config['secrets'], 'secrets')

        if 'scanner' in config:
            self._apply_section(self.scanner, config['scanner'], 'scanner')

        if 'trading' in config:
            self._apply_section(self.trading, config['trading'], 'trading')

        if 'regime' in config:
            self._apply_section(self.regime, config['regime'], 'regime')

        if 'momentum' in config:
            self._apply_section(self.momentum, config['momentum'], 'momentum')

        if 'signal_combiner' in config:
            self._apply_section(self.signal_combiner, config['signal_combiner'], 'signal_combiner')

        if 'pair_blacklist' in config:
            self._apply_section(self.pair_blacklist, config['pair_blacklist'], 'pair_blacklist')
>>>>>>> origin/main

    @staticmethod
    def _apply_section(target, mapping: dict, section_name: str) -> None:
        """Apply YAML key-values to a dataclass, rejecting unknown keys."""
        from dataclasses import fields as dc_fields
<<<<<<< HEAD

=======
>>>>>>> origin/main
        known = {f.name for f in dc_fields(target)}
        for key, value in mapping.items():
            if key in known:
                setattr(target, key, value)
            else:
                logger.error(
                    "unknown_config_key",
                    section=section_name,
                    key=key,
                    hint=f"Valid keys: {sorted(known)}",
                )
<<<<<<< HEAD
                raise ValueError(f"Unknown config key '{key}' in section '{section_name}'. Valid keys: {sorted(known)}")

    def reload_symbols(self, symbols: list[str] | None = None) -> None:
        """
        Hot-reload trading symbols without restarting the application.

        Args:
            symbols: List of symbols to use. If None, reload from config file.

=======
                raise ValueError(
                    f"Unknown config key '{key}' in section '{section_name}'. "
                    f"Valid keys: {sorted(known)}"
                )
    
    def reload_symbols(self, symbols: List[str] = None) -> None:
        """
        Hot-reload trading symbols without restarting the application.
        
        Args:
            symbols: List of symbols to use. If None, reload from config file.
        
>>>>>>> origin/main
        Examples:
            settings = get_settings()
            # Reload from YAML file
            settings.reload_symbols()
            # Or switch to specific symbols dynamically
            settings.reload_symbols(["AAPL", "MSFT"])
        """
        if symbols is not None:
            # Use provided symbols
            old_symbols = self.trading_universe.symbols
            self.trading_universe.symbols = symbols
            logger.info(
                "symbols_reloaded_manual",
                old_count=len(old_symbols),
                new_count=len(symbols),
<<<<<<< HEAD
                symbols=symbols[:5],  # Log first 5 for clarity
=======
                symbols=symbols[:5]  # Log first 5 for clarity
>>>>>>> origin/main
            )
        else:
            # Reload from YAML file
            config_path = Path(__file__).parent / f"{self.env}.yaml"
            if config_path.exists():
                old_symbols = self.trading_universe.symbols.copy()
<<<<<<< HEAD
                with open(config_path, encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}

                if "trading_universe" in config and "symbols" in config["trading_universe"]:
                    self.trading_universe.symbols = config["trading_universe"]["symbols"]
=======
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                
                if 'trading_universe' in config and 'symbols' in config['trading_universe']:
                    self.trading_universe.symbols = config['trading_universe']['symbols']
>>>>>>> origin/main
                    logger.info(
                        "symbols_reloaded_from_config",
                        env=self.env,
                        old_count=len(old_symbols),
                        new_count=len(self.trading_universe.symbols),
<<<<<<< HEAD
                        symbols=self.trading_universe.symbols[:5],  # Log first 5
=======
                        symbols=self.trading_universe.symbols[:5]  # Log first 5
>>>>>>> origin/main
                    )
                else:
                    logger.warning("no_symbols_in_config", path=str(config_path))
            else:
                logger.error("config_file_not_found", path=str(config_path))
<<<<<<< HEAD

    def get_symbols_for_env(self) -> list[str]:
        """Get current trading symbols for active environment."""
        return self.trading_universe.symbols

    def switch_environment(self, env: str) -> None:
        """
        Switch to a different environment (dev, test, prod).

=======
    
    def get_symbols_for_env(self) -> List[str]:
        """Get current trading symbols for active environment."""
        return self.trading_universe.symbols
    
    def switch_environment(self, env: str) -> None:
        """
        Switch to a different environment (dev, test, prod).
        
>>>>>>> origin/main
        Args:
            env: Environment name (dev, test, or prod)
        """
        valid_envs = ["dev", "test", "prod"]
        if env not in valid_envs:
            logger.warning("invalid_environment_switch", env=env, valid=valid_envs)
            return
<<<<<<< HEAD

        old_env = self.env
        self.env = env
        config_path = Path(__file__).parent / f"{self.env}.yaml"

        if config_path.exists():
            self._load_yaml(config_path)
            logger.info(
                "environment_switched", old_env=old_env, new_env=env, num_symbols=len(self.trading_universe.symbols)
=======
        
        old_env = self.env
        self.env = env
        config_path = Path(__file__).parent / f"{self.env}.yaml"
        
        if config_path.exists():
            self._load_yaml(config_path)
            logger.info(
                "environment_switched",
                old_env=old_env,
                new_env=env,
                num_symbols=len(self.trading_universe.symbols)
>>>>>>> origin/main
            )
        else:
            logger.error("config_file_not_found", path=str(config_path))
            self.env = old_env  # Revert on error
<<<<<<< HEAD

=======
>>>>>>> origin/main

def get_settings() -> Settings:
    """Get global settings singleton."""
    return Settings()
