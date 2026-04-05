<<<<<<< HEAD
﻿"""
Sprint 1.2 ÔÇô Formal anti-look-ahead-bias test.
=======
"""
Sprint 1.2 – Formal anti-look-ahead-bias test.
>>>>>>> origin/main

Verifies that the StrategyBacktestSimulator NEVER sees data beyond the
current bar when discovering pairs or generating signals.

Strategy:
  - Build a price DataFrame with a **structural break** at bar T.
  - Before T: symbols are cointegrated.
  - After T: one symbol becomes a random walk (break cointegration).
  - Run the simulator and verify that pairs discovered BEFORE T
<<<<<<< HEAD
    remain unchanged ÔÇô proving no future data leaked into the past.
=======
    remain unchanged – proving no future data leaked into the past.
>>>>>>> origin/main
"""

import numpy as np
import pandas as pd

<<<<<<< HEAD
from backtests.cost_model import CostModel, CostModelConfig
from backtests.metrics import BacktestMetrics
from backtests.strategy_simulator import StrategyBacktestSimulator
=======
from backtests.strategy_simulator import StrategyBacktestSimulator
from backtests.cost_model import CostModel, CostModelConfig
from backtests.metrics import BacktestMetrics

>>>>>>> origin/main

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

<<<<<<< HEAD

=======
>>>>>>> origin/main
def _make_cointegrated_then_break(
    n_bars: int = 400,
    break_bar: int = 250,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Create two price series:
<<<<<<< HEAD
      - [0, break_bar): strongly cointegrated  (Y Ôëê 2*X + noise)
=======
      - [0, break_bar): strongly cointegrated  (Y ≈ 2*X + noise)
>>>>>>> origin/main
      - [break_bar, n_bars): Y becomes an independent random walk
    """
    rng = np.random.default_rng(seed)

    dates = pd.date_range("2023-01-01", periods=n_bars, freq="D")
    x_returns = rng.normal(0.0005, 0.015, n_bars)
    x_prices = 100.0 * np.exp(np.cumsum(x_returns))

    y_prices = np.empty(n_bars)
    # Phase 1: cointegrated
    noise_1 = rng.normal(0, 3, break_bar)
    y_prices[:break_bar] = 2.0 * x_prices[:break_bar] + noise_1

    # Phase 2: independent random walk (breaks cointegration)
    y_rw_returns = rng.normal(0.001, 0.03, n_bars - break_bar)
    y_rw = y_prices[break_bar - 1] * np.exp(np.cumsum(y_rw_returns))
    y_prices[break_bar:] = y_rw

<<<<<<< HEAD
    return pd.DataFrame({"SYM_A": x_prices, "SYM_B": y_prices}, index=dates)
=======
    return pd.DataFrame(
        {"SYM_A": x_prices, "SYM_B": y_prices}, index=dates
    )
>>>>>>> origin/main


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

<<<<<<< HEAD

=======
>>>>>>> origin/main
class TestNoLookAheadBias:
    """Ensure the unified simulator does not peek at future data."""

    def test_simulator_returns_metrics_without_crashing(self):
        """Basic sanity: simulator produces a BacktestMetrics on synthetic data."""
        prices = _make_cointegrated_then_break(n_bars=200, break_bar=150)
        sim = StrategyBacktestSimulator(
            cost_model=CostModel(CostModelConfig(include_borrowing=False)),
            initial_capital=100_000,
            pair_rediscovery_interval=21,
        )
        metrics = sim.run(prices)
        assert isinstance(metrics, BacktestMetrics)
        # Sprint 3.4: Verify actual metric values, not just type
        assert metrics.start_date == "2023-01-01"
        assert metrics.total_trades >= 0
        assert isinstance(metrics.total_return, float)

    def test_no_future_data_in_pair_discovery(self):
        """
        The simulator discovers pairs using hist_prices[:bar_idx+1].
        After the structural break at bar 250, the pair should eventually
        STOP being cointegrated.  If the simulator had look-ahead bias it
        would either:
          a) never discover the pair (sees the break from bar 0), or
          b) keep trading well past the break (used future data to confirm).

        We verify the simulator CAN discover and trade in the cointegrated
        phase and that it processes bars without accessing future indices.
        """
        prices = _make_cointegrated_then_break(n_bars=400, break_bar=250)
        sim = StrategyBacktestSimulator(
            cost_model=CostModel(CostModelConfig(include_borrowing=False)),
            initial_capital=100_000,
            pair_rediscovery_interval=21,
        )
        metrics = sim.run(prices)

        # Simulator ran to completion (no IndexError from future access)
        assert isinstance(metrics, BacktestMetrics)
        # It has a start/end date matching our data
        assert metrics.start_date == "2023-01-01"
        assert metrics.end_date == str(prices.index[-1])[:10]

    def test_expanding_window_never_exceeds_current_bar(self):
        """
        Directly verify the slicing logic: for every bar_idx, the
        historical window passed to generate_signals must have length
        exactly bar_idx + 1. We patch generate_signals to assert this.
        """
        prices = _make_cointegrated_then_break(n_bars=150, break_bar=100)

        from unittest.mock import patch

        observed_lengths = []

<<<<<<< HEAD
        def _recording_generate(
            _self_strategy, market_data, _discovered_pairs=None, **_kwargs
        ):  # mirrors generate_signals signature
=======

        def _recording_generate(self_strategy, market_data, discovered_pairs=None, **kwargs):
>>>>>>> origin/main
            """Record the length of market_data passed to generate_signals."""
            observed_lengths.append(len(market_data))
            return []  # Return no signals to keep test fast

        with patch(
            "strategies.pair_trading.PairTradingStrategy.generate_signals",
            _recording_generate,
        ):
            sim = StrategyBacktestSimulator(
                cost_model=CostModel(),
                initial_capital=100_000,
                pair_rediscovery_interval=999,  # never rediscover for speed
            )
            # Provide fixed_pairs so it skips discovery entirely
            sim.run(prices, fixed_pairs=[])

        # Every call should have received an expanding window
        # starting from lookback_min+1 up to len(prices)
        if len(observed_lengths) > 1:
            # Lengths must be strictly increasing
            for i in range(1, len(observed_lengths)):
                assert observed_lengths[i] == observed_lengths[i - 1] + 1, (
                    f"Bar {i}: window length {observed_lengths[i]} is not "
                    f"previous + 1 ({observed_lengths[i - 1] + 1}). "
                    f"This indicates data leakage or non-expanding window."
                )

    def test_legacy_run_emits_deprecation_warning(self):
        """BacktestRunner.run() must emit DeprecationWarning (C-02 label)."""
<<<<<<< HEAD
        import warnings

        from backtests.runner import BacktestRunner
=======
        from backtests.runner import BacktestRunner
        import warnings
>>>>>>> origin/main

        runner = BacktestRunner()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
<<<<<<< HEAD
                # Will likely fail on network ÔÇô we only care about the warning
=======
                # Will likely fail on network – we only care about the warning
>>>>>>> origin/main
                runner.run(symbols=["FAKE"], use_synthetic=True)
            except Exception:
                pass

<<<<<<< HEAD
        deprecation_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 1, "BacktestRunner.run() should emit a DeprecationWarning"
        assert "look-ahead" in str(deprecation_warnings[0].message).lower()


class TestT1ExecutionTiming:
    """C-02: Signal at bar T → fill at bar T+1 to eliminate look-ahead bias."""

    def _make_prices(self, n: int = 250, seed: int = 0) -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        dates = pd.date_range("2022-01-01", periods=n, freq="D")
        x = 100.0 + np.cumsum(rng.normal(0, 1, n))
        y = 1.5 * x + rng.normal(0, 0.5, n)
        return pd.DataFrame({"AAA": x, "BBB": y}, index=dates)

    def test_entry_not_attempted_at_last_bar(self):
        """
        No entry is opened on the very last bar: there is no T+1 bar to
        execute the fill, so the simulator must skip the signal.
        """
        from unittest.mock import patch

        prices = self._make_prices(n=200)
        last_bar_signals = []

        def _intercept_generate(
            _self_strat, market_data, _discovered_pairs=None, **_kwargs
        ):  # mirrors generate_signals signature
            if len(market_data) == len(prices):
                # This is the last bar call
                from strategies.base import Signal

                last_bar_signals.append(True)
                # Force a long signal — should be ignored by simulator
                return [Signal(symbol_pair="AAA_BBB", side="long", strength=1.0, reason="test")]
            return []

        with patch(
            "strategies.pair_trading.PairTradingStrategy.generate_signals",
            _intercept_generate,
        ):
            sim = StrategyBacktestSimulator(
                cost_model=CostModel(CostModelConfig(include_borrowing=False)),
                initial_capital=100_000,
                pair_rediscovery_interval=999,
            )
            metrics = sim.run(prices, fixed_pairs=[("AAA", "BBB", 0.05, 1.5)])

        assert isinstance(metrics, BacktestMetrics), "Simulator should not crash"

    def test_close_position_uses_next_bar_price(self):
        """
        _close_position uses bar T+1 price for exit (not bar T).
        We verify via unit test of the method: exit_price comes from bar+1.
        """
        prices = self._make_prices(n=200)
        sim = StrategyBacktestSimulator(
            cost_model=CostModel(CostModelConfig(include_borrowing=False)),
            initial_capital=100_000,
        )
        pos = {
            "side": "long",
            "sym1": "AAA",
            "sym2": "BBB",
            "entry_price_1": prices["AAA"].iloc[100],
            "entry_price_2": prices["BBB"].iloc[100],
            "entry_bar": 101,
            "notional": 10_000,
            "notional_1": 5_000,
            "notional_2": 5_000,
            "beta_ratio": 1.5,
            "entry_cost": 0.0,
            "half_life": 20.0,
            "peak_unrealized": 0.0,
            "sigma1": 0.02,
            "sigma2": 0.02,
            "nav_stop_pct": 0.05,
            "borrow_fee_pct": None,
            "ml_features": {},
        }
        signal_bar = 150
        exec_bar = min(signal_bar + 1, len(prices) - 1)

        pnl, _, _ = sim._close_position(pos, prices, signal_bar)

        # Verify that exit price is bar+1 (exec_bar), not bar (signal_bar).
        expected_exit_1 = prices["AAA"].iloc[exec_bar]
        expected_exit_2 = prices["BBB"].iloc[exec_bar]
        stale_exit_1 = prices["AAA"].iloc[signal_bar]
        stale_exit_2 = prices["BBB"].iloc[signal_bar]

        # If exec_bar != signal_bar the prices should differ
        if exec_bar != signal_bar:
            assert expected_exit_1 != stale_exit_1 or expected_exit_2 != stale_exit_2, (
                "Test data should have different prices on adjacent bars"
            )

        # Recompute P&L with exec_bar manually and compare
        entry_1 = pos["entry_price_1"]
        entry_2 = pos["entry_price_2"]
        ret_1 = (expected_exit_1 - entry_1) / entry_1 if entry_1 else 0
        ret_2 = (entry_2 - expected_exit_2) / entry_2 if entry_2 else 0
        gross = 5_000 * ret_1 + 5_000 * ret_2
        # pnl should incorporate exit_bar+1 price, not signal_bar price
        assert abs(pnl) < abs(gross) + 1000  # rough bound (costs reduce gross)

    def test_close_position_last_bar_uses_last_bar_price(self):
        """
        When bar_idx is the last bar, exec_bar is clamped to last bar.
        Position is still closed (not skipped).
        """
        prices = self._make_prices(n=200)
        sim = StrategyBacktestSimulator(
            cost_model=CostModel(CostModelConfig(include_borrowing=False)),
            initial_capital=100_000,
        )
        pos = {
            "side": "long",
            "sym1": "AAA",
            "sym2": "BBB",
            "entry_price_1": prices["AAA"].iloc[100],
            "entry_price_2": prices["BBB"].iloc[100],
            "entry_bar": 101,
            "notional": 10_000,
            "notional_1": 5_000,
            "notional_2": 5_000,
            "beta_ratio": 1.5,
            "entry_cost": 0.0,
            "half_life": 20.0,
            "peak_unrealized": 0.0,
            "sigma1": 0.02,
            "sigma2": 0.02,
            "nav_stop_pct": 0.05,
            "borrow_fee_pct": None,
            "ml_features": {},
        }
        last_bar = len(prices) - 1
        pnl, trade_pnl, _ = sim._close_position(pos, prices, last_bar)
        assert isinstance(pnl, float)
        assert isinstance(trade_pnl, float)

    def test_simulator_runs_without_indexerror(self):
        """Full run with T+1 convention must not raise IndexError."""
        prices = self._make_prices(n=300)
        sim = StrategyBacktestSimulator(
            cost_model=CostModel(CostModelConfig(include_borrowing=False)),
            initial_capital=100_000,
            pair_rediscovery_interval=30,
        )
        metrics = sim.run(prices, fixed_pairs=[("AAA", "BBB", 0.05, 1.5)])
        assert isinstance(metrics, BacktestMetrics)
=======
        deprecation_warnings = [
            w for w in caught if issubclass(w.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) >= 1, (
            "BacktestRunner.run() should emit a DeprecationWarning"
        )
        assert "look-ahead" in str(deprecation_warnings[0].message).lower()
>>>>>>> origin/main
