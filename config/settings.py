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
    exit_z_score: float = 0.0   # Exit threshold
    min_correlation: float = 0.7  # Min correlation for pairs
    max_half_life: int = 60  # Max half-life (days) for spread mean reversion

@dataclass
class TradingUniverseConfig:
    """Trading universe configuration (which symbols to trade)."""
    symbols: list = field(default_factory=lambda: [
        "BTC/USDT", "ETH/USDT",  # Default: just top 2 if config not available
    ])

@dataclass
class RiskConfig:
    """Risk management parameters."""
    max_risk_per_trade: float = 0.005  # 0.5% of equity
    max_concurrent_positions: int = 10
    max_daily_loss_pct: float = 0.02  # 2% daily loss kill-switch
    max_consecutive_losses: int = 3
    volatility_percentile_threshold: float = 1.5  # Regime break detection
    position_sizing_method: str = "volatility"  # volatility or kelly
    max_leverage: float = 3.0  # Maximum portfolio leverage (3x = 300% total exposure)

@dataclass
class ExecutionConfig:
    """Execution layer parameters."""
    engine: str = "ccxt"  # ccxt or ibkr
    exchange: str = "binance"
    timeout_seconds: int = 30
    max_retries: int = 3
    slippage_bps: float = 5.0  # Basis points
    use_sandbox: bool = True
    paper_trading_loop_interval_seconds: int = 10  # Loop sleep interval
    initial_capital: float = 100000.0  # Starting capital for paper/live trading
    paper_slippage_model: str = "fixed_bps"  # fixed_bps, adaptive, volume_based
    paper_commission_pct: float = 0.1  # Commission percentage (0.1%)

@dataclass
class BacktestConfig:
    """Backtesting parameters."""
    start_date: str = "2022-01-01"
    end_date: str = "2024-01-01"
    initial_capital: float = 100000.0
    commission_bps: float = 2.0
    walk_forward_periods: int = 4  # Monthly rebalance
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
        self.raw_config = {}
        
        if config_path.exists():
            logger.info("loading_config", env=self.env, path=str(config_path))
            self._load_yaml(config_path)
        else:
            logger.warning("config_not_found", env=self.env, path=str(config_path))
        
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
    
    def _load_yaml(self, path: Path) -> None:
        """Load configuration from YAML file."""
        with open(path, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        self.raw_config = config
        
        if 'strategy' in config:
            for key, value in config['strategy'].items():
                setattr(self.strategy, key, value)
        
        if 'trading_universe' in config:
            if 'symbols' in config['trading_universe']:
                self.trading_universe.symbols = config['trading_universe']['symbols']
        
        if 'risk' in config:
            for key, value in config['risk'].items():
                setattr(self.risk, key, value)
        
        if 'execution' in config:
            for key, value in config['execution'].items():
                setattr(self.execution, key, value)
        
        if 'backtest' in config:
            for key, value in config['backtest'].items():
                setattr(self.backtest, key, value)
        
        if 'secrets' in config:
            for key, value in config['secrets'].items():
                setattr(self.secrets, key, value)
    
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
            settings.reload_symbols(["BTC/USDT", "ETH/USDT"])
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
