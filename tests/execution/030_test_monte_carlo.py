"""Tests for Monte Carlo order book simulation."""

from datetime import datetime

import numpy as np

from execution.monte_carlo import (
    MonteCarloOrderBookSimulator,
    MonteCarloSimulation,
    PricePath,
    analyze_risk_metrics,
    create_correlated_simulations,
)


class TestPricePath:
    """Test PricePath class."""

    def test_price_path_creation(self):
        """Test creating a price path."""
        prices = np.array([100.0, 101.0, 102.5, 101.8])
        volumes = np.array([1.0, 1.1, 1.2, 1.0])
        spreads = np.array([0.0005, 0.0005, 0.0006, 0.0005])
        returns = np.array([0.0, 0.01, 0.0148, -0.0068])

        path = PricePath(
            symbol="AAPL",
            prices=prices,
            volumes=volumes,
            spreads=spreads,
            returns=returns,
        )

        assert path.get_final_price() == 101.8
        assert len(path.prices) == 4

    def test_price_path_max_drawdown(self):
        """Test maximum drawdown calculation."""
        prices = np.array([100.0, 110.0, 105.0, 95.0])
        volumes = np.array([1.0, 1.0, 1.0, 1.0])
        spreads = np.array([0.0005] * 4)
        returns = np.array([0.0, 0.1, -0.0454, -0.0952])

        path = PricePath(
            symbol="AAPL",
            prices=prices,
            volumes=volumes,
            spreads=spreads,
            returns=returns,
        )

        mdd = path.get_max_drawdown()
        assert mdd < 0  # Should be negative
        assert mdd > -0.5  # But not catastrophic

    def test_price_path_realized_volatility(self):
        """Test realized volatility calculation."""
        prices = np.array([100.0, 101.0, 102.5, 101.8, 103.2])
        volumes = np.array([1.0] * 5)
        spreads = np.array([0.0005] * 5)
        returns = np.diff(np.log(prices))
        returns = np.concatenate([[0.0], returns])

        path = PricePath(
            symbol="AAPL",
            prices=prices,
            volumes=volumes,
            spreads=spreads,
            returns=returns,
        )

        vol = path.get_volatility_realized()
        assert vol > 0
        assert vol < 2.0  # Reasonable volatility


class TestMonteCarloSimulation:
    """Test MonteCarloSimulation class."""

    def test_simulation_creation(self):
        """Test creating simulation results."""
        config = {
            "num_simulations": 100,
            "time_steps": 10,
            "price_drift_bps": 0.0,
            "volatility_annual_pct": 20.0,
            "jump_probability": 0.0,
            "jump_size_std": 0.0,
            "volume_scaling": 1.0,
        }

        prices = np.array([100.0] * 11)
        volumes = np.ones(11)
        spreads = np.full(11, 0.0005)
        returns = np.zeros(11)

        paths = [
            PricePath(
                symbol="AAPL",
                prices=prices,
                volumes=volumes,
                spreads=spreads,
                returns=returns,
            )
            for _ in range(10)
        ]

        sim = MonteCarloSimulation(  # type: ignore[call-arg, arg-type]
            symbol="AAPL",
            config=config,  # type: ignore[arg-type]
            paths=paths,
            initial_price=100.0,
            generated_at=datetime.now(),
        )

        assert sim.symbol == "AAPL"
        assert len(sim.paths) == 10
        assert sim.initial_price == 100.0

    def test_simulation_get_price_matrix(self):
        """Test extracting price matrix."""
        config = {
            "num_simulations": 5,
            "time_steps": 5,
            "price_drift_bps": 0.0,
            "volatility_annual_pct": 20.0,
            "jump_probability": 0.0,
            "jump_size_std": 0.0,
            "volume_scaling": 1.0,
        }

        prices = np.array([100.0] * 6)
        volumes = np.ones(6)
        spreads = np.full(6, 0.0005)
        returns = np.zeros(6)

        paths = [
            PricePath(
                symbol="AAPL",
                prices=prices,
                volumes=volumes,
                spreads=spreads,
                returns=returns,
            )
            for _ in range(5)
        ]

        sim = MonteCarloSimulation(  # type: ignore[call-arg, arg-type]
            symbol="AAPL",
            config=config,  # type: ignore[arg-type]
            paths=paths,
            initial_price=100.0,
            generated_at=datetime.now(),
        )

        matrix = sim.get_price_matrix()
        assert matrix.shape == (5, 6)

    def test_simulation_statistics(self):
        """Test extracting statistics."""
        config = {
            "num_simulations": 100,
            "time_steps": 10,
            "price_drift_bps": 10.0,  # Positive drift
            "volatility_annual_pct": 15.0,
            "jump_probability": 0.0,
            "jump_size_std": 0.0,
            "volume_scaling": 1.0,
        }

        # Create paths with different end prices
        prices_list = [np.linspace(100.0, 101.0 + i * 0.1, 11) for i in range(100)]

        paths = []
        for prices in prices_list:
            volumes = np.ones(len(prices))
            spreads = np.full(len(prices), 0.0005)
            returns = np.concatenate([[0.0], np.diff(np.log(prices))])

            paths.append(
                PricePath(
                    symbol="AAPL",
                    prices=prices,
                    volumes=volumes,
                    spreads=spreads,
                    returns=returns,
                )
            )

        sim = MonteCarloSimulation(  # type: ignore[call-arg, arg-type]
            symbol="AAPL",
            config=config,  # type: ignore[arg-type]
            paths=paths,
            initial_price=100.0,
            generated_at=datetime.now(),
        )

        stats = sim.get_statistics()

        assert "symbol" in stats
        assert "num_simulations" in stats
        assert "percentile_50" in stats
        assert stats["percentile_50"] > 100.0  # Drift should raise prices
        assert stats["percentile_95"] > stats["percentile_50"]


class TestMonteCarloOrderBookSimulator:
    """Test MonteCarloOrderBookSimulator."""

    def test_simulator_initialization(self):
        """Test simulator creation."""
        config = {
            "num_simulations": 10,
            "time_steps": 5,
            "price_drift_bps": 0.0,
            "volatility_annual_pct": 20.0,
            "jump_probability": 0.0,
            "jump_size_std": 0.0,
            "volume_scaling": 1.0,
        }

        simulator = MonteCarloOrderBookSimulator(  # type: ignore[arg-type]
            config=config,  # type: ignore[arg-type]
            initial_price=100.0,
            seed=42,
        )

        assert simulator.config == config
        assert simulator.initial_price == 100.0
        assert simulator.seed == 42

    def test_gbm_path_generation(self):
        """Test Geometric Brownian Motion path generation."""
        config = {
            "num_simulations": 1,
            "time_steps": 100,
            "price_drift_bps": 0.0,
            "volatility_annual_pct": 10.0,
            "jump_probability": 0.0,
            "jump_size_std": 0.0,
            "volume_scaling": 1.0,
        }

        simulator = MonteCarloOrderBookSimulator(  # type: ignore[arg-type]
            config=config,  # type: ignore[arg-type]
            initial_price=100.0,
            seed=42,
        )

        path = simulator.simulate_single_path("AAPL")

        assert path.symbol == "AAPL"
        assert len(path.prices) == config["time_steps"] + 1
        assert path.prices[0] == 100.0
        assert all(p > 0 for p in path.prices)  # No negative prices

    def test_jump_diffusion_path_generation(self):
        """Test jump-diffusion process."""
        config = {
            "num_simulations": 1,
            "time_steps": 100,
            "price_drift_bps": 0.0,
            "volatility_annual_pct": 10.0,
            "jump_probability": 0.1,  # 10% chance per step
            "jump_size_std": 0.05,
            "volume_scaling": 1.0,
        }

        simulator = MonteCarloOrderBookSimulator(  # type: ignore[arg-type]
            config=config,  # type: ignore[arg-type]
            initial_price=100.0,
            seed=42,
        )

        path = simulator.simulate_single_path("AAPL")

        assert path.symbol == "AAPL"
        assert len(path.prices) == config["time_steps"] + 1
        assert all(p > 0 for p in path.prices)

    def test_volume_path_generation(self):
        """Test stochastic volume generation."""
        config = {
            "num_simulations": 1,
            "time_steps": 50,
            "price_drift_bps": 0.0,
            "volatility_annual_pct": 15.0,
            "jump_probability": 0.0,
            "jump_size_std": 0.0,
            "volume_scaling": 10.0,
        }

        simulator = MonteCarloOrderBookSimulator(  # type: ignore[arg-type]
            config=config,  # type: ignore[arg-type]
            initial_price=100.0,
        )

        path = simulator.simulate_single_path()

        assert len(path.volumes) == config["time_steps"] + 1
        assert all(v > 0 for v in path.volumes)
        # Volume should scale approximately with volume_scaling
        assert path.volumes.mean() > 1.0

    def test_full_simulation(self):
        """Test complete Monte Carlo simulation."""
        config = {
            "num_simulations": 50,
            "time_steps": 10,
            "price_drift_bps": 5.0,
            "volatility_annual_pct": 20.0,
            "jump_probability": 0.0,
            "jump_size_std": 0.0,
            "volume_scaling": 1.0,
        }

        simulator = MonteCarloOrderBookSimulator(  # type: ignore[arg-type]
            config=config,  # type: ignore[arg-type]
            initial_price=100.0,
            seed=42,
        )

        sim = simulator.simulate("AAPL")

        assert sim.symbol == "AAPL"
        assert len(sim.paths) == 50
        assert sim.initial_price == 100.0

    def test_reproducibility_with_seed(self):
        """Test that same seed produces same results."""
        config = {
            "num_simulations": 10,
            "time_steps": 20,
            "price_drift_bps": 0.0,
            "volatility_annual_pct": 15.0,
            "jump_probability": 0.0,
            "jump_size_std": 0.0,
            "volume_scaling": 1.0,
        }

        sim1 = MonteCarloOrderBookSimulator(config=config, initial_price=100.0, seed=123)  # type: ignore[arg-type]
        result1 = sim1.simulate()

        sim2 = MonteCarloOrderBookSimulator(config=config, initial_price=100.0, seed=123)  # type: ignore[arg-type]
        result2 = sim2.simulate()

        prices1 = result1.get_price_matrix()
        prices2 = result2.get_price_matrix()

        np.testing.assert_array_almost_equal(prices1, prices2)


class TestCorrelatedSimulations:
    """Test correlated multi-asset simulations."""

    def test_correlated_simulation_creation(self):
        """Test generating correlated simulations."""
        config = {
            "num_simulations": 20,
            "time_steps": 10,
            "price_drift_bps": 0.0,
            "volatility_annual_pct": 15.0,
            "jump_probability": 0.0,
            "jump_size_std": 0.0,
            "volume_scaling": 1.0,
        }

        symbols = ["AAPL", "MSFT"]
        initial_prices = {"AAPL": 100.0, "MSFT": 50.0}
        correlation_matrix = np.array([[1.0, 0.8], [0.8, 1.0]])

        results = create_correlated_simulations(
            config=config,  # type: ignore[arg-type]
            symbols=symbols,
            initial_prices=initial_prices,
            correlation_matrix=correlation_matrix,
            seed=42,
        )

        assert "AAPL" in results
        assert "MSFT" in results
        assert len(results["AAPL"].paths) == 20


class TestRiskMetrics:
    """Test risk metrics analysis."""

    def test_var_cvar_calculation(self):
        """Test VaR and CVaR calculation."""
        config = {
            "num_simulations": 100,
            "time_steps": 1,
            "price_drift_bps": 0.0,
            "volatility_annual_pct": 20.0,
            "jump_probability": 0.0,
            "jump_size_std": 0.0,
            "volume_scaling": 1.0,
        }

        # Create paths with known distribution
        paths = []
        for i in range(100):
            # Linear prices from 90 to 110
            prices = np.array([100.0, 90.0 + i])
            volumes = np.ones(2)
            spreads = np.full(2, 0.0005)
            returns = np.array([0.0, np.log(prices[1] / prices[0])])

            paths.append(
                PricePath(
                    symbol="AAPL",
                    prices=prices,
                    volumes=volumes,
                    spreads=spreads,
                    returns=returns,
                )
            )

        sim = MonteCarloSimulation(  # type: ignore[call-arg, arg-type]
            symbol="AAPL",
            config=config,  # type: ignore[arg-type]
            paths=paths,
            initial_price=100.0,
            generated_at=datetime.now(),
        )

        var, cvar = sim.get_var_cvar(confidence=0.95)

        assert isinstance(var, float)
        assert isinstance(cvar, float)
        assert var < 0  # Losses are negative

    def test_analyze_risk_metrics(self):
        """Test risk metrics analysis function."""
        config = {
            "num_simulations": 100,
            "time_steps": 5,
            "price_drift_bps": 0.0,
            "volatility_annual_pct": 15.0,
            "jump_probability": 0.0,
            "jump_size_std": 0.0,
            "volume_scaling": 1.0,
        }

        simulator = MonteCarloOrderBookSimulator(  # type: ignore[arg-type]
            config=config,  # type: ignore[arg-type]
            initial_price=100.0,
            seed=42,
        )

        sim = simulator.simulate()
        metrics = analyze_risk_metrics(sim, confidence_levels=[0.90, 0.95, 0.99])

        assert len(metrics) == 3
        assert 0.90 in metrics
        assert 0.95 in metrics
        assert 0.99 in metrics

        # VaR should increase (become more negative) with confidence
        var_90, _ = metrics[0.90]
        var_95, _ = metrics[0.95]
        var_99, _ = metrics[0.99]

        assert var_90 > var_95  # 90% VaR less severe than 95%
        assert var_95 > var_99  # etc
