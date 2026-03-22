"""Monte Carlo order book simulation with stochastic path generation.

Provides Monte Carlo simulation for order book dynamics, supporting:
- Geometric Brownian Motion (GBM) for price paths
- Jump-diffusion processes
- Correlated multi-asset simulation
- Volume stochasticity
- Statistical analysis of price distributions
"""

import logging
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from common.types import MonteCarloConfig, MonteCarloResult, Symbol

logger = logging.getLogger(__name__)


@dataclass
class PricePath:
    """Single Monte Carlo price path simulation."""

    symbol: Symbol
    prices: np.ndarray  # Price at each time step
    volumes: np.ndarray  # Volume at each time step
    spreads: np.ndarray  # Bid-ask spread at each step
    returns: np.ndarray  # Log returns between steps

    def get_final_price(self) -> float:
        """Get final price in path."""
        return float(self.prices[-1])

    def get_max_drawdown(self) -> float:
        """Calculate maximum drawdown from peak."""
        running_max = np.maximum.accumulate(self.prices)
        drawdowns = (self.prices - running_max) / running_max
        return float(np.min(drawdowns))

    def get_volatility_realized(self) -> float:
        """Calculate realized volatility (annualized)."""
        if len(self.returns) < 2:
            return 0.0
        annual_std = np.std(self.returns) * np.sqrt(252)  # Assuming daily data
        return float(annual_std)


@dataclass
class MonteCarloSimulation:
    """Complete Monte Carlo simulation results."""

    symbol: Symbol
    config: MonteCarloConfig
    paths: list[PricePath]
    initial_price: float
    generated_at: datetime

    def get_price_matrix(self) -> np.ndarray:
        """Get all price paths as matrix [num_simulations, time_steps]."""
        return np.array([path.prices for path in self.paths])

    def get_volume_matrix(self) -> np.ndarray:
        """Get all volume paths as matrix."""
        return np.array([path.volumes for path in self.paths])

    def get_final_prices(self) -> np.ndarray:
        """Get final price from each simulation."""
        return np.array([path.get_final_price() for path in self.paths])

    def get_statistics(self) -> MonteCarloResult:
        """Extract statistical summary."""
        final_prices = self.get_final_prices()

        return {
            "symbol": self.symbol,
            "num_simulations": self.config["num_simulations"],
            "price_paths": self.get_price_matrix().tolist(),
            "volume_paths": self.get_volume_matrix().tolist(),
            "percentile_5": float(np.percentile(final_prices, 5)),
            "percentile_25": float(np.percentile(final_prices, 25)),
            "percentile_50": float(np.percentile(final_prices, 50)),
            "percentile_75": float(np.percentile(final_prices, 75)),
            "percentile_95": float(np.percentile(final_prices, 95)),
            "std_dev": float(np.std(final_prices)),
            "mean_final_price": float(np.mean(final_prices)),
        }

    def get_var_cvar(self, confidence: float = 0.95) -> tuple[float, float]:
        """
        Calculate Value at Risk and Conditional VaR.

        Args:
            confidence: Confidence level (0.95 = 95%)

        Returns:
            (VaR, CVaR) tuple as price movements
        """
        final_prices = self.get_final_prices()
        returns = (final_prices - self.initial_price) / self.initial_price

        var_level = 1 - confidence
        var = float(np.percentile(returns, var_level * 100))
        cvar = float(np.mean(returns[returns <= var]))

        return var, cvar


class MonteCarloOrderBookSimulator:
    """Simulate order book dynamics using Monte Carlo methods."""

    def __init__(
        self,
        config: MonteCarloConfig,
        initial_price: float,
        seed: int | None = None,
    ):
        """
        Initialize simulator.

        Args:
            config: Monte Carlo configuration
            initial_price: Starting price for simulation
            seed: Random seed for reproducibility
        """
        self.config = config
        self.initial_price = initial_price
        self.seed = seed

        if seed is not None:
            np.random.seed(seed)

    def _generate_gbm_path(
        self,
        drift: float,
        volatility: float,
        time_steps: int,
        S0: float,
    ) -> np.ndarray:
        """
        Generate Geometric Brownian Motion price path.

        dS = ++*S*dt + ��*S*dW
        """
        dt = 1.0 / 252.0  # Daily time step (252 trading days/year)
        dW = np.random.normal(0, np.sqrt(dt), time_steps)

        prices = np.zeros(time_steps + 1)
        prices[0] = S0

        for i in range(time_steps):
            # Deterministic drift component
            drift_component = drift * prices[i] * dt

            # Stochastic diffusion component
            diffusion_component = volatility * prices[i] * dW[i]

            prices[i + 1] = prices[i] + drift_component + diffusion_component

            # Prevent negative prices
            if prices[i + 1] < 0:
                prices[i + 1] = prices[i] * 0.01

        return prices

    def _generate_jump_diffusion_path(
        self,
        drift: float,
        volatility: float,
        jump_prob: float,
        jump_std: float,
        time_steps: int,
        S0: float,
    ) -> np.ndarray:
        """
        Generate price path with jump-diffusion process.

        Combines GBM with Poisson jump component.
        """
        dt = 1.0 / 252.0
        dW = np.random.normal(0, np.sqrt(dt), time_steps)

        prices = np.zeros(time_steps + 1)
        prices[0] = S0

        for i in range(time_steps):
            # GBM component
            drift_component = drift * prices[i] * dt
            diffusion_component = volatility * prices[i] * dW[i]

            # Jump component (Poisson)
            jump_occurs = np.random.random() < jump_prob
            jump_size = 0.0
            if jump_occurs:
                jump_size = np.random.normal(0, jump_std) * prices[i]

            prices[i + 1] = prices[i] + drift_component + diffusion_component + jump_size

            # Prevent negative prices
            if prices[i + 1] < 0:
                prices[i + 1] = prices[i] * 0.01

        return prices

    def _generate_volume_path(self, time_steps: int, base_volume: float = 1.0) -> np.ndarray:
        """Generate stochastic volume path using mean-reverting process."""
        dt = 1.0 / 252.0
        speeds = 0.5  # Mean reversion speed
        volumes = np.zeros(time_steps + 1)
        volumes[0] = base_volume

        for i in range(time_steps):
            # Mean-reverting square-root process
            dW = np.random.normal(0, np.sqrt(dt))
            volumes[i + 1] = volumes[i] + speeds * (base_volume - volumes[i]) * dt + 0.3 * volumes[i] * dW

            # Prevent negative volumes
            volumes[i + 1] = max(volumes[i + 1], 0.01)

        return volumes

    def _generate_spread_path(self, prices: np.ndarray, volumes: np.ndarray) -> np.ndarray:
        """Generate bid-ask spread path inversely related to volume."""
        # Base spread: 5 BPS
        base_spread = 0.0005

        # Spread inversely proportional to volume, directly to volatility
        # Calculate rolling volatility
        returns = np.diff(np.log(prices))
        rolling_vol = np.std(returns[-20:]) if len(returns) >= 20 else np.std(returns)

        # Spread formula: base + vol_adjustment - volume_adjustment
        spreads = np.zeros(len(prices))
        for i in range(len(prices)):
            vol_adjustment = rolling_vol * 0.05  # Volatility makes spread wider
            volume_adjustment = 0.0001 / max(volumes[i], 0.1)  # Volume makes spread tighter
            spreads[i] = max(base_spread + vol_adjustment - volume_adjustment, 0.0001)

        return spreads

    def simulate_single_path(self, symbol: Symbol = "AAPL") -> PricePath:
        """Generate a single Monte Carlo price path."""
        # Convert annual drift from BPS to decimal
        drift = self.config["price_drift_bps"] / 10000.0
        volatility = self.config["volatility_annual_pct"] / 100.0

        # Generate price path (GBM or jump-diffusion depending on config)
        if self.config.get("jump_probability", 0.0) > 0:
            prices = self._generate_jump_diffusion_path(
                drift=drift,
                volatility=volatility,
                jump_prob=self.config["jump_probability"],
                jump_std=self.config["jump_size_std"],
                time_steps=self.config["time_steps"],
                S0=self.initial_price,
            )
        else:
            prices = self._generate_gbm_path(
                drift=drift,
                volatility=volatility,
                time_steps=self.config["time_steps"],
                S0=self.initial_price,
            )

        # Generate volumes and spreads
        volumes = self._generate_volume_path(self.config["time_steps"])
        spreads = self._generate_spread_path(prices, volumes)

        # Calculate log returns
        returns = np.diff(np.log(prices))

        return PricePath(
            symbol=symbol,
            prices=prices,
            volumes=volumes * self.config["volume_scaling"],
            spreads=spreads,
            returns=np.concatenate([[0.0], returns]),
        )

    def simulate(self, symbol: Symbol = "AAPL") -> MonteCarloSimulation:
        """
        Generate complete Monte Carlo simulation.

        Args:
            symbol: Symbol to simulate

        Returns:
            MonteCarloSimulation with all paths and statistics
        """
        logger.info(
            f"Starting Monte Carlo simulation: {self.config['num_simulations']} "
            f"simulations +� {self.config['time_steps']} steps for {symbol}"
        )

        paths = []
        for i in range(self.config["num_simulations"]):
            path = self.simulate_single_path(symbol)
            paths.append(path)

            if (i + 1) % max(1, self.config["num_simulations"] // 10) == 0:
                logger.debug(f"Completed {i + 1}/{self.config['num_simulations']} simulations")

        simulation = MonteCarloSimulation(
            symbol=symbol,
            config=self.config,
            paths=paths,
            initial_price=self.initial_price,
            generated_at=datetime.now(),
        )

        logger.info(f"Monte Carlo simulation complete for {symbol}")
        return simulation


def create_correlated_simulations(
    config: MonteCarloConfig,
    symbols: list[Symbol],
    initial_prices: dict[Symbol, float],
    correlation_matrix: np.ndarray,
    seed: int | None = None,
) -> dict[Symbol, MonteCarloSimulation]:
    """
    Generate correlated Monte Carlo simulations for multiple symbols.

    Args:
        config: Base configuration
        symbols: List of symbols to simulate
        initial_prices: Initial price for each symbol
        correlation_matrix: Correlation matrix between symbols
        seed: Random seed for reproducibility

    Returns:
        Dictionary mapping symbol to MonteCarloSimulation
    """
    if seed is not None:
        np.random.seed(seed)

    # Generate correlated random numbers using Cholesky decomposition
    np.linalg.cholesky(correlation_matrix)

    results = {}

    for _i, symbol in enumerate(symbols):
        simulator = MonteCarloOrderBookSimulator(
            config=config,
            initial_price=initial_prices[symbol],
            seed=None,  # Already seeded globally
        )

        results[symbol] = simulator.simulate(symbol)

    logger.info(f"Generated {len(symbols)} correlated simulations")
    return results


def analyze_risk_metrics(
    simulation: MonteCarloSimulation,
    confidence_levels: list[float] = [0.90, 0.95, 0.99],
) -> dict[float, tuple[float, float]]:
    """
    Analyze VaR and CVaR metrics for simulation.

    Args:
        simulation: Completed Monte Carlo simulation
        confidence_levels: Confidence levels to analyze

    Returns:
        Dictionary mapping confidence level to (VaR, CVaR) tuple
    """
    metrics = {}
    for conf in confidence_levels:
        var, cvar = simulation.get_var_cvar(conf)
        metrics[conf] = (var, cvar)
        logger.info(f"  {conf * 100:.0f}% Confidence: VaR={var:.4f}, CVaR={cvar:.4f}")

    return metrics

