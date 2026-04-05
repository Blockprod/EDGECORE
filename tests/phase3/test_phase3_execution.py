"""
Phase 3 Tests ÔÇö Fr├®quence & Ex├®cution Algorithmique
====================================================
Tests for the 3 modules introduced in Phase 3:
  3.1 IntradayLoader (5-min bar loading + synthetic generation)
  3.2 IntradaySignalEngine (fast MR + gap reversion + volume profile)
  3.3 AlgoExecutor TWAP/VWAP (order slicing with impact model)
"""

from typing import cast

import numpy as np
import pandas as pd
import pytest

from data.intraday_loader import IntradayLoader
from execution.algo_executor import (
    AlgoConfig,
    AlgoResult,
    AlgoType,
    TWAPExecutor,
    VWAPExecutor,
    create_algo_executor,
)
from signal_engine.intraday_signals import (
    GapReversionSignal,
    IntradayMeanReversionSignal,
    IntradaySignalEngine,
    IntradaySignalResult,
    VolumeProfileSignal,
)

# ===================================================================
# 3.1: IntradayLoader ÔÇö Synthetic Intraday Data Generation
# ===================================================================


class TestIntradayLoader:
    """Test synthetic intraday data generation from daily prices."""

    @pytest.fixture
    def daily_prices(self):
        """Create sample daily close prices for 2 symbols over 60 days."""
        np.random.seed(42)
        n = 60
        dates = pd.bdate_range("2025-01-01", periods=n)
        a = 100 + np.cumsum(np.random.randn(n) * 0.5)
        b = 200 + np.cumsum(np.random.randn(n) * 0.8)
        return pd.DataFrame({"AAPL": a, "MSFT": b}, index=dates)

    def test_generate_synthetic_returns_dataframe(self, daily_prices):
        intraday = IntradayLoader.generate_synthetic_intraday(daily_prices)
        assert isinstance(intraday, pd.DataFrame)
        assert len(intraday) > 0

    def test_synthetic_has_correct_columns(self, daily_prices):
        intraday = IntradayLoader.generate_synthetic_intraday(daily_prices)
        assert "AAPL" in intraday.columns
        assert "MSFT" in intraday.columns

    def test_synthetic_bars_per_day(self, daily_prices):
        intraday = IntradayLoader.generate_synthetic_intraday(daily_prices, bars_per_day=78)
        # Each trading day after the first generates 78 intraday bars
        # 59 days (all except first) ├ù 78 bars = 4602 bars expected
        expected = (len(daily_prices) - 1) * 78
        assert len(intraday) == expected

    def test_synthetic_timestamps_are_intraday(self, daily_prices):
        intraday = IntradayLoader.generate_synthetic_intraday(daily_prices)
        # First bar should be at 9:30 AM
        first_ts = cast(pd.Timestamp, intraday.index[0])
        assert first_ts.hour == 9
        assert first_ts.minute == 30

    def test_synthetic_prices_are_positive(self, daily_prices):
        intraday = IntradayLoader.generate_synthetic_intraday(daily_prices)
        # All prices should be positive (no negative artifacts)
        assert (intraday > 0).all().all()

    def test_empty_input(self):
        df = pd.DataFrame()
        result = IntradayLoader.generate_synthetic_intraday(df)
        assert isinstance(result, pd.DataFrame)


# ===================================================================
# 3.2: IntradaySignalEngine ÔÇö Intraday Signal Generators
# ===================================================================


class TestIntradayMeanReversionSignal:
    """Fast z-score on 5-min spread."""

    def test_score_in_range(self):
        np.random.seed(42)
        spread = pd.Series(np.cumsum(np.random.randn(30) * 0.01))
        sig = IntradayMeanReversionSignal(lookback=15)
        score = sig.compute_score(spread)
        assert -1.0 <= score <= 1.0

    def test_high_z_gives_nonzero_score(self):
        # Spread that shoots up ÔåÆ should get negative score (sell)
        spread = pd.Series([0.0] * 20 + [0.0, 0.0, 0.0, 0.0, 0.5])
        sig = IntradayMeanReversionSignal(lookback=15, scale=2.0)
        score = sig.compute_score(spread)
        assert score < 0  # sell signal

    def test_zero_vol_returns_zero(self):
        spread = pd.Series([1.0] * 20)
        sig = IntradayMeanReversionSignal(lookback=15)
        score = sig.compute_score(spread)
        assert score == 0.0

    def test_insufficient_data_returns_zero(self):
        spread = pd.Series([1.0, 2.0, 3.0])
        sig = IntradayMeanReversionSignal(lookback=15)
        score = sig.compute_score(spread)
        assert score == 0.0

    def test_lookback_validation(self):
        with pytest.raises(ValueError):
            IntradayMeanReversionSignal(lookback=3)


class TestGapReversionSignal:
    """Overnight gap detection and reversion signal."""

    def test_no_gap_returns_zero(self):
        spread = pd.Series([1.0, 1.001, 0.999, 1.002, 1.0])
        sig = GapReversionSignal(gap_threshold=0.005)
        score = sig.compute_score(spread, bars_since_open=2)
        # Small gap ÔåÆ below threshold ÔåÆ 0
        assert score == 0.0

    def test_outside_window_returns_zero(self):
        spread = pd.Series([1.0, 1.5, 1.3, 1.4])
        sig = GapReversionSignal(reversion_bars=24)
        score = sig.compute_score(spread, bars_since_open=30)
        assert score == 0.0

    def test_score_in_range(self):
        np.random.seed(42)
        spread = pd.Series([1.0] + list(np.random.randn(20) * 0.05 + 1.0))
        sig = GapReversionSignal(gap_threshold=0.001, scale=0.01)
        score = sig.compute_score(spread, bars_since_open=5)
        assert -1.0 <= score <= 1.0

    def test_empty_spread_returns_zero(self):
        spread = pd.Series([1.0])
        sig = GapReversionSignal()
        score = sig.compute_score(spread, bars_since_open=0)
        assert score == 0.0


class TestVolumeProfileSignal:
    """Volume-weighted spread confirmation."""

    @pytest.fixture
    def volume_data(self):
        np.random.seed(42)
        n = 30
        vol_a = pd.Series(np.random.randint(1000, 10000, n).astype(float))
        vol_b = pd.Series(np.random.randint(1000, 10000, n).astype(float))
        return vol_a, vol_b

    def test_score_in_range(self, volume_data):
        np.random.seed(42)
        spread = pd.Series(np.cumsum(np.random.randn(30) * 0.01))
        vol_a, vol_b = volume_data
        sig = VolumeProfileSignal(lookback=20, volume_threshold=1.0)
        score = sig.compute_score(spread, vol_a, vol_b)
        assert -1.0 <= score <= 1.0

    def test_low_volume_returns_zero(self, volume_data):  # noqa: ARG002 — fixture dep not used; volumes constructed locally
        _ = volume_data  # fixture dependency declared for test isolation
        spread = pd.Series(np.random.randn(30) * 0.01)
        vol_a = pd.Series([100.0] * 30)  # constant low ÔåÆ ratio = 1.0
        vol_b = pd.Series([100.0] * 30)
        sig = VolumeProfileSignal(lookback=20, volume_threshold=1.5)
        score = sig.compute_score(spread, vol_a, vol_b)
        assert score == 0.0  # volume ratio < threshold

    def test_insufficient_data_returns_zero(self):
        spread = pd.Series([1.0, 2.0])
        vol_a = pd.Series([100.0, 200.0])
        vol_b = pd.Series([150.0, 250.0])
        sig = VolumeProfileSignal(lookback=20)
        score = sig.compute_score(spread, vol_a, vol_b)
        assert score == 0.0


class TestIntradaySignalEngine:
    """Composite intraday signal engine."""

    def test_compute_returns_result(self):
        np.random.seed(42)
        spread = pd.Series(np.cumsum(np.random.randn(30) * 0.01))
        engine = IntradaySignalEngine(mr_lookback=15)
        result = engine.compute(spread, bars_since_open=5)
        assert isinstance(result, IntradaySignalResult)

    def test_composite_in_range(self):
        np.random.seed(42)
        spread = pd.Series(np.cumsum(np.random.randn(30) * 0.01))
        engine = IntradaySignalEngine(mr_lookback=15)
        result = engine.compute(spread, bars_since_open=5)
        assert -1.0 <= result.composite_intraday <= 1.0

    def test_with_volume(self):
        np.random.seed(42)
        n = 30
        spread = pd.Series(np.cumsum(np.random.randn(n) * 0.01))
        vol_a = pd.Series(np.random.randint(1000, 10000, n).astype(float))
        vol_b = pd.Series(np.random.randint(1000, 10000, n).astype(float))
        engine = IntradaySignalEngine(mr_lookback=15, vol_lookback=20)
        result = engine.compute(spread, bars_since_open=5, volume_a=vol_a, volume_b=vol_b)
        assert isinstance(result.volume_score, float)


# ===================================================================
# 3.3: AlgoExecutor ÔÇö TWAP and VWAP Order Slicing
# ===================================================================


class TestTWAPExecutor:
    """TWAP order simulation."""

    def test_simulate_returns_result(self):
        twap = TWAPExecutor()
        result = twap.simulate("AAPL", "BUY", 1000, 150.0, adv=1_000_000)
        assert isinstance(result, AlgoResult)
        assert result.algo_type == AlgoType.TWAP

    def test_fills_all_quantity(self):
        twap = TWAPExecutor(AlgoConfig(num_slices=5, max_participation=1.0))
        result = twap.simulate("AAPL", "BUY", 1000, 150.0, adv=1e6)
        assert result.total_filled_qty == pytest.approx(1000)
        assert result.status == "FILLED"

    def test_buy_impact_increases_price(self):
        twap = TWAPExecutor(AlgoConfig(impact_bps=10.0))
        result = twap.simulate("AAPL", "BUY", 1000, 150.0, adv=1e6)
        assert result.avg_fill_price > 150.0

    def test_sell_impact_decreases_price(self):
        twap = TWAPExecutor(AlgoConfig(impact_bps=10.0))
        result = twap.simulate("AAPL", "SELL", 1000, 150.0, adv=1e6)
        assert result.avg_fill_price < 150.0

    def test_slices_count(self):
        twap = TWAPExecutor(AlgoConfig(num_slices=8, max_participation=1.0))
        result = twap.simulate("AAPL", "BUY", 1000, 150.0, adv=1e6)
        assert len(result.slices) == 8

    def test_impact_is_in_bps(self):
        twap = TWAPExecutor(AlgoConfig(impact_bps=5.0))
        result = twap.simulate("AAPL", "BUY", 1000, 150.0, adv=1e6)
        assert result.estimated_impact_bps >= 0
        assert result.estimated_impact_bps < 50  # reasonable upper bound

    def test_participation_cap(self):
        config = AlgoConfig(num_slices=5, max_participation=0.01)
        twap = TWAPExecutor(config)
        result = twap.simulate("AAPL", "BUY", 100000, 150.0, adv=50000)
        # Large order relative to ADV ÔåÆ quantity should be reduced
        # Total filled should be less than target due to participation cap
        assert result.total_filled_qty < 100000


class TestVWAPExecutor:
    """VWAP order simulation."""

    def test_simulate_returns_result(self):
        vwap = VWAPExecutor()
        result = vwap.simulate("MSFT", "BUY", 500, 300.0, adv=2e6)
        assert isinstance(result, AlgoResult)
        assert result.algo_type == AlgoType.VWAP

    def test_fills_quantity(self):
        config = AlgoConfig(algo_type=AlgoType.VWAP, num_slices=10, max_participation=1.0)
        vwap = VWAPExecutor(config)
        result = vwap.simulate("MSFT", "BUY", 500, 300.0, adv=2e6)
        assert result.total_filled_qty == pytest.approx(500, rel=0.01)

    def test_buy_impact(self):
        vwap = VWAPExecutor(AlgoConfig(algo_type=AlgoType.VWAP, impact_bps=10.0))
        result = vwap.simulate("MSFT", "BUY", 500, 300.0, adv=2e6)
        assert result.avg_fill_price > 300.0

    def test_sell_impact(self):
        vwap = VWAPExecutor(AlgoConfig(algo_type=AlgoType.VWAP, impact_bps=10.0))
        result = vwap.simulate("MSFT", "SELL", 500, 300.0, adv=2e6)
        assert result.avg_fill_price < 300.0

    def test_custom_volume_profile(self):
        profile = np.array([0.3, 0.2, 0.1, 0.1, 0.3])
        vwap = VWAPExecutor(
            config=AlgoConfig(algo_type=AlgoType.VWAP, num_slices=5, max_participation=1.0),
            volume_profile=profile,
        )
        result = vwap.simulate("MSFT", "BUY", 500, 300.0, adv=2e6)
        assert len(result.slices) == 5


class TestAlgoFactory:
    """Factory function tests."""

    def test_create_twap(self):
        executor = create_algo_executor("TWAP")
        assert isinstance(executor, TWAPExecutor)

    def test_create_vwap(self):
        executor = create_algo_executor("VWAP")
        assert isinstance(executor, VWAPExecutor)

    def test_case_insensitive(self):
        executor = create_algo_executor("twap")
        assert isinstance(executor, TWAPExecutor)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            create_algo_executor("UNKNOWN")
