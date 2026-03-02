import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, List
from dotenv import load_dotenv
from structlog import get_logger

load_dotenv()

logger = get_logger(__name__)

@dataclass
class StrategyConfig:
    """Pair trading strategy parameters."""
    lookback_window: int = 252  # Days for cointegration
    entry_z_score: float = 2.0  # Entry threshold
    exit_z_score: float = 0.5   # Exit threshold (was 0.0 — unreachable in float)
    min_correlation: float = 0.7  # Min correlation for pairs
    max_half_life: int = 60  # Max half-life (days) for spread mean reversion
    bonferroni_correction: bool = True  # NEW: Apply Bonferroni correction to handle multiple testing
    significance_level: float = 0.05  # NEW: Nominal significance level (before Bonferroni)
    use_kalman: bool = True  # Dynamic hedge ratio via Kalman filter
    max_position_loss_pct: float = 0.10  # P&L stop per position (10% default)
    hedge_ratio_reestimation_days: int = 7  # Sprint 2.2: Reestimate hedge ratio every 7 days (was 30)
    regime_min_duration: int = 1  # Sprint 2.2: Min bars before regime transition (was 3)
    emergency_vol_threshold_sigma: float = 3.0  # Sprint 2.2: Emergency reestimate if spread vol > Nσ
    instant_transition_percentile: float = 99.0  # Sprint 2.2: Instant regime transition for extreme vol
    # Sprint 3.5: Adaptive cache TTL by regime (hours)
    cache_ttl_high_vol: int = 2    # HIGH regime -> frequent re-discovery
    # Sprint 4.1: Johansen double-screening confirmation
    johansen_confirmation: bool = True  # Confirm EG pairs with Johansen test
    # Sprint 4.3: Newey-West HAC consensus
    newey_west_consensus: bool = True  # Require OLS + HAC agreement for cointegration
    cache_ttl_normal_vol: int = 12  # NORMAL regime -> moderate TTL
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

@dataclass
class ScannerConfig:
    """Dynamic universe scanner configuration."""
    min_market_cap_usd: float = 500_000_000     # $500M minimum
    min_avg_volume_usd: float = 5_000_000       # $5M daily volume
    min_price: float = 5.0                       # exclude penny stocks
    exchanges: List[str] = field(default_factory=lambda: ["NYSE", "NASDAQ", "AMEX"])
    cache_ttl_hours: int = 24
    ibkr_validation_workers: int = 5
    ibkr_batch_size: int = 50
    scan_enabled: bool = False                   # Enable dynamic scanning
    scan_schedule_cron: str = "0 5 * * 1-5"      # Mon-Fri 5am UTC

@dataclass
class TradingUniverseConfig:
    """Trading universe configuration (which symbols to trade)."""
    symbols: list = field(default_factory=lambda: [
        "AAPL", "MSFT",  # Default: US equities if config not available
    ])
    max_leverage: float = 2.0  # Max leverage for the universe

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

@dataclass
class CostConfig:
    """Centralised transaction cost model — single source of truth.
    
    All execution modules (backtest, paper, live) MUST read from this config
    instead of maintaining their own hardcoded defaults.  Values calibrated
    for US equities via IBKR.
    """
    slippage_bps: float = 3.0           # Base slippage (adaptive on top)
    commission_pct: float = 0.00035     # IBKR US equity commission (0.035%)
    maker_fee_bps: float = 1.5          # Exchange maker rebate/fee
    taker_fee_bps: float = 2.0          # Exchange taker fee
    borrowing_cost_annual: float = 0.005  # Short-borrow GC rate (0.5%)
    max_slippage_bps: float = 50.0      # Hard cap on adaptive slippage
    slippage_model: str = "adaptive"    # fixed_bps | adaptive | volume_based

@dataclass
class ExecutionConfig:
    """Execution layer parameters."""
    engine: str = "ibkr"      # ibkr (Interactive Brokers)
    timeout_seconds: int = 30
    max_retries: int = 3
    slippage_bps: float = 2.0  # Basis points
    use_sandbox: bool = True
    paper_trading_loop_interval_seconds: int = 10  # Loop sleep interval
    initial_capital: float = 100000.0  # Starting capital for paper/live trading
    paper_slippage_model: str = "fixed_bps"  # fixed_bps, adaptive, volume_based
    paper_commission_pct: float = 0.005  # Commission percentage (0.005% ≈ $0.005/share IBKR)

@dataclass
class BacktestConfig:
    """Backtesting parameters."""
    start_date: str = "2018-01-01"  # 8 years of US equity history
    end_date: str = "2026-01-01"
    initial_capital: float = 100000.0
    commission_bps: float = 2.0
    walk_forward_periods: int = 4
    out_of_sample_ratio: float = 0.2

@dataclass
class SecretsConfig:
    """Secrets management and rotation parameters."""
    rotation_interval_days: int = 90  # Rotate API keys every 90 days
    rotation_time_utc: str = "02:00"  # 2 AM UTC for rotation
    auto_load_from_env: bool = True  # Auto-load secrets from environment
    mask_ratio: float = 0.8  # Mask 80% of secret value in logs
    audit_trail_enabled: bool = True  # Enable audit logging for secret access
    
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
        
        # Support multiple environment variable names: EDGECORE_ENV, ENVIRONMENT, ENV
        self.env = (
            os.getenv("EDGECORE_ENV") or 
            os.getenv("ENVIRONMENT") or 
            os.getenv("ENV") or 
            "dev"
        ).lower()
        
        # Validate environment
        valid_envs = ["dev", "test", "prod"]
        if self.env not in valid_envs:
            logger.warning("invalid_environment", env=self.env, valid=valid_envs)
            self.env = "dev"
        
        config_path = Path(__file__).parent / f"{self.env}.yaml"
        
        self.strategy = StrategyConfig()
        self.trading_universe = TradingUniverseConfig()
        self.risk = RiskConfig()
        self.execution = ExecutionConfig()
        self.backtest = BacktestConfig()
        self.secrets = SecretsConfig()
        self.costs = CostConfig()
        self.scanner = ScannerConfig()
        self.raw_config = {}
        
        if config_path.exists():
            logger.info("loading_config", env=self.env, path=str(config_path))
            self._load_yaml(config_path)
        else:
            logger.warning("config_not_found", env=self.env, path=str(config_path))
        
        # Validate configuration using Pydantic schemas
        self._validate_config()
        
        # Safety check: prevent live trading unless explicitly enabled
        if self.execution.use_sandbox == False:
            if os.getenv("ENABLE_LIVE_TRADING") != "true":
                logger.warning("LIVE_TRADING_DISABLED_BY_DEFAULT")
                self.execution.use_sandbox = True  # Force sandbox mode
                logger.info("sandbox_mode_forced", reason="ENABLE_LIVE_TRADING env var not set")
        
        logger.info(
            "config_loaded",
            env=self.env,
            num_symbols=len(self.trading_universe.symbols),
            initial_capital=self.execution.initial_capital
        )
        
        self._initialized = True
    
    def _validate_config(self) -> None:
        """Validate loaded configuration using Pydantic schemas."""
        try:
            from config.schemas import RiskConfigSchema, StrategyConfigSchema
            # Validate risk config
            RiskConfigSchema(
                max_drawdown_pct=self.risk.max_drawdown_pct * 100,  # schema expects 0-100
                max_loss_per_trade=self.risk.max_risk_per_trade,
            )
            # Validate strategy config
            StrategyConfigSchema(
                entry_z_score=self.strategy.entry_z_score,
                exit_z_score=self.strategy.exit_z_score,
                lookback_window=self.strategy.lookback_window,
            )
            logger.debug("config_validation_passed")
        except ImportError:
            logger.debug("pydantic_schemas_not_available_skipping_validation")
        except Exception as exc:
            logger.error("config_validation_failed", error=str(exc)[:200])
            raise ValueError(f"Configuration validation failed: {exc}") from exc

    def _load_yaml(self, path: Path) -> None:
        """Load configuration from YAML file."""
        with open(path, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        self.raw_config = config
        
        if 'strategy' in config:
            self._apply_section(self.strategy, config['strategy'], 'strategy')
        
        if 'trading_universe' in config:
            tu = config['trading_universe']
            if 'symbols' in tu:
                self.trading_universe.symbols = tu['symbols']
            if 'max_leverage' in tu:
                self.trading_universe.max_leverage = tu['max_leverage']
        
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

    @staticmethod
    def _apply_section(target, mapping: dict, section_name: str) -> None:
        """Apply YAML key-values to a dataclass, rejecting unknown keys."""
        from dataclasses import fields as dc_fields
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
                raise ValueError(
                    f"Unknown config key '{key}' in section '{section_name}'. "
                    f"Valid keys: {sorted(known)}"
                )
    
    def reload_symbols(self, symbols: List[str] = None) -> None:
        """
        Hot-reload trading symbols without restarting the application.
        
        Args:
            symbols: List of symbols to use. If None, reload from config file.
        
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
                symbols=symbols[:5]  # Log first 5 for clarity
            )
        else:
            # Reload from YAML file
            config_path = Path(__file__).parent / f"{self.env}.yaml"
            if config_path.exists():
                old_symbols = self.trading_universe.symbols.copy()
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f) or {}
                
                if 'trading_universe' in config and 'symbols' in config['trading_universe']:
                    self.trading_universe.symbols = config['trading_universe']['symbols']
                    logger.info(
                        "symbols_reloaded_from_config",
                        env=self.env,
                        old_count=len(old_symbols),
                        new_count=len(self.trading_universe.symbols),
                        symbols=self.trading_universe.symbols[:5]  # Log first 5
                    )
                else:
                    logger.warning("no_symbols_in_config", path=str(config_path))
            else:
                logger.error("config_file_not_found", path=str(config_path))
    
    def get_symbols_for_env(self) -> List[str]:
        """Get current trading symbols for active environment."""
        return self.trading_universe.symbols
    
    def switch_environment(self, env: str) -> None:
        """
        Switch to a different environment (dev, test, prod).
        
        Args:
            env: Environment name (dev, test, or prod)
        """
        valid_envs = ["dev", "test", "prod"]
        if env not in valid_envs:
            logger.warning("invalid_environment_switch", env=env, valid=valid_envs)
            return
        
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
            )
        else:
            logger.error("config_file_not_found", path=str(config_path))
            self.env = old_env  # Revert on error

def get_settings() -> Settings:
    """Get global settings singleton."""
    return Settings()
