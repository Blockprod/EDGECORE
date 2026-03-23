"""
Input validation framework for EDGECORE trading system.

Centralizes all validation logic for:
- Trading symbols (format, existence)
- Position sizes (bounds checking)
- Equity (sanity checks)
- Volatility (realistic ranges)
- Configuration (schema validation)
"""

import math
import re
from contextlib import contextmanager
from typing import Any

from structlog import get_logger

logger = get_logger(__name__)


class ValidationError(ValueError):
    """Base validation error."""

    pass


class ConfigError(ValidationError):
    """Configuration validation error."""

    pass


class SymbolError(ValidationError):
    """Symbol validation error."""

    pass


class EquityError(ValidationError):
    """Equity validation error."""

    pass


class VolatilityError(ValidationError):
    """Volatility validation error."""

    pass


def validate_symbol(symbol: str) -> None:
    """
    Validate trading symbol format.

    Args:
        symbol: Trading symbol (e.g., "AAPL")

    Raises:
        SymbolError: If symbol is invalid
    """
    if not isinstance(symbol, str):
        raise SymbolError(f"Symbol must be string, got {type(symbol)}")

    if not symbol.strip():
        raise SymbolError("Symbol cannot be empty")

    # Accept US equity tickers (1-5 uppercase letters, e.g. AAPL, MSFT)
    # or pair identifiers (e.g. MSFT/AAPL)
    sym_upper = symbol.upper()
    is_equity_ticker = re.match(r"^[A-Z]{1,5}$", sym_upper) is not None
    is_pair = re.match(r"^[A-Z0-9]+/[A-Z0-9]+$", sym_upper) is not None
    if not is_equity_ticker and not is_pair:
        raise SymbolError(
            f"Symbol '{symbol}' must be a US equity ticker (e.g. 'AAPL') "
            f"or a trading pair in 'BASE/QUOTE' format (e.g. 'MSFT')"
        )

    if is_pair:
        parts = symbol.split("/")
        if len(parts) != 2:
            raise SymbolError(f"Symbol must have exactly 2 parts, got {len(parts)}")
        if len(parts[0]) < 2 or len(parts[0]) > 10:
            raise SymbolError(f"Base currency too short/long: {parts[0]}")
        if len(parts[1]) < 2 or len(parts[1]) > 10:
            raise SymbolError(f"Quote currency too short/long: {parts[1]}")

    logger.debug("symbol_validated", symbol=symbol)


def validate_position_size(position_size: float, min_size: float = 0.0001, max_size: float = 1_000_000.0) -> None:
    """
    Validate position size.

    Args:
        position_size: Size of position (in units)
        min_size: Minimum allowed size
        max_size: Maximum allowed size

    Raises:
        ValidationError: If position size is invalid
    """
    if not isinstance(position_size, (int, float)):
        raise ValidationError(f"Position size must be numeric, got {type(position_size)}")

    if math.isnan(position_size):
        raise ValidationError("Position size cannot be NaN")

    if math.isinf(position_size):
        raise ValidationError("Position size cannot be infinite")

    if position_size < min_size:
        raise ValidationError(f"Position size {position_size} below minimum {min_size}")

    if position_size > max_size:
        raise ValidationError(f"Position size {position_size} exceeds maximum {max_size}")

    logger.debug("position_size_validated", position_size=position_size)


def validate_equity(equity: float, min_equity: float = 100.0, max_equity: float = 1_000_000_000.0) -> None:
    """
    Validate account equity.

    Args:
        equity: Current equity value
        min_equity: Minimum plausible equity (sanity check)
        max_equity: Maximum plausible equity (sanity check)

    Raises:
        EquityError: If equity is invalid
    """
    if not isinstance(equity, (int, float)):
        raise EquityError(f"Equity must be numeric, got {type(equity)}")

    if math.isnan(equity):
        raise EquityError("Equity cannot be NaN")

    if math.isinf(equity):
        raise EquityError("Equity cannot be infinite")

    if equity <= 0:
        raise EquityError(f"Equity must be positive, got {equity}")

    if equity < min_equity:
        raise EquityError(
            f"Equity {equity} suspiciously low (< {min_equity}). Possible data corruption or broker API error."
        )

    if equity > max_equity:
        raise EquityError(
            f"Equity {equity} suspiciously high (> {max_equity}). Possible data corruption or broker API error."
        )

    logger.debug("equity_validated", equity=equity)


def validate_volatility(volatility: float, min_vol: float = 0.0001, max_vol: float = 10.0) -> None:
    """
    Validate volatility metric.

    Args:
        volatility: Volatility estimate (annualized, in %)
        min_vol: Minimum plausible volatility
        max_vol: Maximum plausible volatility

    Raises:
        VolatilityError: If volatility is invalid
    """
    if not isinstance(volatility, (int, float)):
        raise VolatilityError(f"Volatility must be numeric, got {type(volatility)}")

    if math.isnan(volatility):
        raise VolatilityError("Volatility cannot be NaN")

    if math.isinf(volatility):
        raise VolatilityError("Volatility cannot be infinite")

    if volatility <= 0:
        raise VolatilityError(f"Volatility must be positive, got {volatility}")

    if volatility < min_vol:
        raise VolatilityError(f"Volatility {volatility} implausibly low (< {min_vol}). Possible calculation error.")

    if volatility > max_vol:
        raise VolatilityError(
            f"Volatility {volatility} implausibly high (> {max_vol}). Possible data corruption or calculation error."
        )

    logger.debug("volatility_validated", volatility=volatility)


def validate_config(config: dict[str, Any], schema: dict | None = None) -> None:
    """
    Validate configuration dictionary.

    Args:
        config: Configuration dict to validate
        schema: Optional schema definition with type hints and constraints

    Raises:
        ConfigError: If config is invalid
    """
    if not isinstance(config, dict):
        raise ConfigError(f"Config must be dict, got {type(config)}")

    if not config:
        raise ConfigError("Config cannot be empty")

    if schema is not None:
        unknown_keys = set(config.keys()) - set(schema.keys())
        if unknown_keys:
            raise ConfigError(f"Unknown config keys not present in schema: {sorted(unknown_keys)}")

    # Basic checks
    if "strategy" in config:
        strategy = config["strategy"]
        if not isinstance(strategy, dict):
            raise ConfigError("Config.strategy must be dict")

        if "entry_z_score" in strategy:
            z = strategy["entry_z_score"]
            if not isinstance(z, (int, float)) or z <= 0:
                raise ConfigError(f"entry_z_score must be positive, got {z}")

        if "max_half_life" in strategy:
            hl = strategy["max_half_life"]
            if not isinstance(hl, int) or hl <= 0 or hl > 365:
                raise ConfigError(f"max_half_life must be 1-365 days, got {hl}")

    if "risk" in config:
        risk = config["risk"]
        if not isinstance(risk, dict):
            raise ConfigError("Config.risk must be dict")

        if "max_risk_per_trade" in risk:
            mrt = risk["max_risk_per_trade"]
            if not isinstance(mrt, (int, float)) or mrt <= 0 or mrt > 0.5:
                raise ConfigError(f"max_risk_per_trade must be 0-50%, got {mrt * 100}%")

        if "max_concurrent_positions" in risk:
            mcp = risk["max_concurrent_positions"]
            if not isinstance(mcp, int) or mcp < 1 or mcp > 1000:
                raise ConfigError(f"max_concurrent_positions must be 1-1000, got {mcp}")

        if "max_daily_loss_pct" in risk:
            mdl = risk["max_daily_loss_pct"]
            if not isinstance(mdl, (int, float)) or mdl <= 0 or mdl > 0.5:
                raise ConfigError(f"max_daily_loss_pct must be 0-50%, got {mdl * 100}%")

    if "execution" in config:
        execution = config["execution"]
        if not isinstance(execution, dict):
            raise ConfigError("Config.execution must be dict")

        if "timeout_seconds" in execution:
            ts = execution["timeout_seconds"]
            if not isinstance(ts, int) or ts < 1 or ts > 300:
                raise ConfigError(f"timeout_seconds must be 1-300, got {ts}")

    logger.debug("config_validated", keys=list(config.keys()))


@contextmanager
def SanityCheckContext(name: str = "operation"):
    """
    Context manager for grouped sanity checks.

    Usage:
        with SanityCheckContext("trade_entry"):
            validate_symbol(symbol)
            validate_position_size(size)
            validate_equity(equity)

    Args:
        name: Operation name for logging

    Raises:
        ValidationError: If any check fails
    """
    try:
        logger.debug("sanity_check_start", operation=name)
        yield
        logger.debug("sanity_check_pass", operation=name)
    except ValidationError as e:
        logger.error("sanity_check_failed", operation=name, error=str(e))
        raise
    except Exception as e:
        logger.error("sanity_check_unexpected_error", operation=name, error=str(e))
        raise ValidationError(f"{name} failed: {str(e)}") from e


# Batch validators for common scenarios


def validate_trade_entry(symbol: str, position_size: float, equity: float, volatility: float) -> None:
    """
    Validate all parameters for trade entry at once.

    Args:
        symbol: Trading symbol
        position_size: Position size
        equity: Current equity
        volatility: Volatility estimate

    Raises:
        ValidationError: If any parameter is invalid
    """
    with SanityCheckContext("trade_entry"):
        validate_symbol(symbol)
        validate_position_size(position_size)
        validate_equity(equity)
        validate_volatility(volatility)


def validate_risk_parameters(
    max_risk_per_trade: float, max_concurrent_positions: int, max_daily_loss_pct: float
) -> None:
    """
    Validate risk configuration parameters.

    Args:
        max_risk_per_trade: Max risk per trade (0-1)
        max_concurrent_positions: Max positions
        max_daily_loss_pct: Max daily loss (0-1)

    Raises:
        ValidationError: If any parameter is invalid
    """
    with SanityCheckContext("risk_parameters"):
        if not isinstance(max_risk_per_trade, (int, float)) or max_risk_per_trade <= 0 or max_risk_per_trade >= 0.5:
            raise ValidationError(f"max_risk_per_trade must be 0-50%, got {max_risk_per_trade * 100}%")

        if (
            not isinstance(max_concurrent_positions, int)
            or max_concurrent_positions < 1
            or max_concurrent_positions > 1000
        ):
            raise ValidationError(f"max_concurrent_positions must be 1-1000, got {max_concurrent_positions}")

        if not isinstance(max_daily_loss_pct, (int, float)) or max_daily_loss_pct <= 0 or max_daily_loss_pct >= 0.5:
            raise ValidationError(f"max_daily_loss_pct must be 0-50%, got {max_daily_loss_pct * 100}%")
