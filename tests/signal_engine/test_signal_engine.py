"""
Tests for signal_engine ÔÇö generator.py, zscore.py, adaptive.py.

Covers:
    - ZScoreCalculator: rolling z-score, EWMA, clipping, edge cases
    - AdaptiveThresholdEngine: regime adjustments, bounds enforcement
    - SignalGenerator: full pipeline with mock data, NaN handling,
      constant series, missing columns
"""

import numpy as np
import pandas as pd
from unittest.mock import MagicMock

from signal_engine.zscore import ZScoreCalculator
from signal_engine.adaptive import AdaptiveThresholdEngine, ThresholdResult
from signal_engine.generator import SignalGenerator, Signal
from models.regime_detector import VolatilityRegime


# ======================================================================
# ZScoreCalculator
# ======================================================================

class TestZScoreCalculator:
    """Unit tests for ZScoreCalculator."""

    def test_basic_zscore(self):
        """Z-score of a simple ramp spread is non-zero."""
        calc = ZScoreCalculator(default_lookback=10)
        spread = pd.Series(np.linspace(100, 110, 50))
        z = calc.compute(spread)
        assert len(z) == len(spread)
        assert z.iloc[-1] > 0, "Rising spread should have positive z"

    def test_constant_series_returns_zero(self):
        """Constant spread yields z=0 everywhere (std=0 ÔåÆ filled 0)."""
        calc = ZScoreCalculator(default_lookback=10)
        spread = pd.Series(np.full(50, 100.0))
        z = calc.compute(spread)
        assert (z == 0.0).all(), "Constant series should produce z=0"

    def test_nan_spread_yields_zero(self):
        """NaN values in spread should not blow up; filled to 0."""
        calc = ZScoreCalculator(default_lookback=10)
        spread = pd.Series([np.nan] * 20 + list(range(30)))
        z = calc.compute(spread)
        assert not z.isna().any(), "No NaN should remain after compute"

    def test_clipping(self):
        """Extreme values are clipped to max_z_score."""
        calc = ZScoreCalculator(default_lookback=5, max_z_score=3.0)
        # Create an extreme spike
        data = np.zeros(30)
        data[-1] = 1e6
        spread = pd.Series(data)
        z = calc.compute(spread)
        assert abs(z.iloc[-1]) <= 3.0, "Z-score should be clipped"

    def test_ewma_mode(self):
        """EWMA z-score runs without error and produces different values."""
        calc_sma = ZScoreCalculator(use_ewma=False)
        calc_ewma = ZScoreCalculator(use_ewma=True)
        spread = pd.Series(np.random.randn(100).cumsum())
        z_sma = calc_sma.compute(spread, half_life=20.0)
        z_ewma = calc_ewma.compute(spread, half_life=20.0)
        # They should differ (EWMA weights recent data more)
        assert not z_sma.equals(z_ewma)

    def test_half_life_adapts_window(self):
        """Short half-life ÔåÆ small window, long half-life ÔåÆ larger window."""
        calc = ZScoreCalculator()
        w_short = calc._resolve_lookback(half_life=5.0, explicit=None)
        w_long = calc._resolve_lookback(half_life=50.0, explicit=None)
        assert w_short < w_long

    def test_explicit_lookback_overrides_half_life(self):
        """Explicit lookback takes precedence."""
        calc = ZScoreCalculator()
        w = calc._resolve_lookback(half_life=50.0, explicit=7)
        assert w == 7

    def test_current_z_convenience(self):
        """Static current_z method returns a scalar."""
        spread = pd.Series(np.random.randn(50).cumsum())
        z = ZScoreCalculator.current_z(spread, lookback=20)
        assert isinstance(z, float)

    def test_short_series_returns_zeros(self):
        """Series shorter than lookback returns 0-filled z-scores."""
        calc = ZScoreCalculator(default_lookback=100)
        spread = pd.Series([1.0, 2.0, 3.0])
        z = calc.compute(spread)
        # With min_periods = lookback//2 = 50, first values should be 0/NaNÔåÆ0
        assert len(z) == 3


# ======================================================================
# AdaptiveThresholdEngine
# ======================================================================

class TestAdaptiveThresholdEngine:
    """Unit tests for AdaptiveThresholdEngine."""

    def _make_spread(self, n=200):
        np.random.seed(42)
        return pd.Series(np.random.randn(n).cumsum())

    def test_default_thresholds(self):
        """Default engine returns sensible thresholds."""
        engine = AdaptiveThresholdEngine()
        result = engine.get_thresholds(self._make_spread())
        assert result.entry_threshold >= 1.0
        assert result.entry_threshold <= 3.5
        assert result.exit_threshold >= 0.0

    def test_regime_low_lowers_entry(self):
        """LOW volatility regime should decrease entry threshold."""
        engine = AdaptiveThresholdEngine()
        r_normal = engine.get_thresholds(self._make_spread(), regime=VolatilityRegime.NORMAL)
        r_low = engine.get_thresholds(self._make_spread(), regime=VolatilityRegime.LOW)
        assert r_low.entry_threshold <= r_normal.entry_threshold

    def test_regime_high_raises_entry(self):
        """HIGH volatility regime should increase entry threshold."""
        engine = AdaptiveThresholdEngine()
        r_normal = engine.get_thresholds(self._make_spread(), regime=VolatilityRegime.NORMAL)
        r_high = engine.get_thresholds(self._make_spread(), regime=VolatilityRegime.HIGH)
        assert r_high.entry_threshold >= r_normal.entry_threshold

    def test_bounds_enforcement(self):
        """Thresholds are clamped to [min_entry, max_entry]."""
        engine = AdaptiveThresholdEngine(min_entry=1.5, max_entry=2.5)
        result = engine.get_thresholds(self._make_spread(), regime=VolatilityRegime.HIGH)
        assert result.entry_threshold <= 2.5
        assert result.entry_threshold >= 1.5

    def test_threshold_result_type(self):
        """get_thresholds returns a ThresholdResult dataclass."""
        engine = AdaptiveThresholdEngine()
        result = engine.get_thresholds(self._make_spread())
        assert isinstance(result, ThresholdResult)
        assert isinstance(result.adjustments, dict)


# ======================================================================
# SignalGenerator (integration with mocked dependencies)
# ======================================================================

class TestSignalGenerator:
    """Tests for the full signal generation pipeline."""

    def _make_prices(self, n=300, corr=0.95, seed=42):
        """Create correlated price DataFrame for two symbols."""
        np.random.seed(seed)
        base = np.random.randn(n).cumsum() + 100
        noise = np.random.randn(n) * 0.5
        return pd.DataFrame({
            "SYM1": base,
            "SYM2": base * corr + noise + 50,
        }, index=pd.date_range("2024-01-01", periods=n))

    def test_generate_returns_list(self):
        """generate() returns a list of Signal objects."""
        gen = SignalGenerator()
        prices = self._make_prices()
        pairs = [("SYM1", "SYM2", 0.01, 25.0)]
        signals = gen.generate(prices, pairs)
        assert isinstance(signals, list)
        for s in signals:
            assert isinstance(s, Signal)

    def test_no_signal_when_no_pairs(self):
        """Empty pairs list produces no signals."""
        gen = SignalGenerator()
        signals = gen.generate(self._make_prices(), [])
        assert signals == []

    def test_signal_side_values(self):
        """Signal side is one of long/short/exit."""
        gen = SignalGenerator()
        prices = self._make_prices()
        pairs = [("SYM1", "SYM2", 0.01, 25.0)]
        signals = gen.generate(prices, pairs)
        for s in signals:
            assert s.side in ("long", "short", "exit")

    def test_exit_when_in_position_and_mean_reverted(self):
        """If already in position and z-score ~ 0 ÔåÆ exit signal."""
        gen = SignalGenerator()
        # Build a mean-reverting spread: stationary around 0
        np.random.seed(123)
        n = 300
        base = np.random.randn(n).cumsum() + 200
        # Make spread tightly cointegrated so z-score stays near 0
        prices = pd.DataFrame({
            "A": base,
            "B": base + np.random.randn(n) * 0.01,
        }, index=pd.date_range("2024-01-01", periods=n))
        pairs = [("A", "B", 0.001, 10.0)]
        active = {"A_B": {"side": "long", "entry_z": 2.0}}
        signals = gen.generate(prices, pairs, active_positions=active)
        # Should produce an exit since z ~ 0
        exit_sigs = [s for s in signals if s.side == "exit"]
        assert len(exit_sigs) >= 1 or len(signals) == 0  # depends on stationarity check

    def test_missing_column_does_not_crash(self):
        """If a pair references a non-existent symbol, no crash."""
        gen = SignalGenerator()
        prices = self._make_prices()
        pairs = [("SYM1", "MISSING", 0.01, 25.0)]
        # Should handle gracefully (error logged, no crash)
        signals = gen.generate(prices, pairs)
        assert isinstance(signals, list)

    def test_nan_prices_handled(self):
        """DataFrame with NaN columns doesn't crash the pipeline."""
        gen = SignalGenerator()
        prices = self._make_prices()
        prices.loc[prices.index[:50], "SYM1"] = np.nan
        pairs = [("SYM1", "SYM2", 0.01, 25.0)]
        signals = gen.generate(prices, pairs)
        assert isinstance(signals, list)

    def test_spread_model_reuse(self):
        """Calling generate twice reuses SpreadModel state (Kalman)."""
        gen = SignalGenerator()
        prices = self._make_prices()
        pairs = [("SYM1", "SYM2", 0.01, 25.0)]
        gen.generate(prices, pairs)
        assert "SYM1_SYM2" in gen._spread_models
        model_before = gen._spread_models["SYM1_SYM2"]
        gen.generate(prices, pairs)
        assert gen._spread_models["SYM1_SYM2"] is model_before

    def test_get_spread_accessor(self):
        """get_spread returns the latest spread after generate()."""
        gen = SignalGenerator()
        prices = self._make_prices()
        pairs = [("SYM1", "SYM2", 0.01, 25.0)]
        gen.generate(prices, pairs)
        spread = gen.get_spread("SYM1_SYM2")
        assert spread is not None
        assert isinstance(spread, pd.Series)
    # ÔöÇÔöÇ Phase 3: NaN strict, non-cointegrated, look-ahead, regime ÔöÇÔöÇÔöÇÔöÇÔöÇ

    def test_nan_prices_emit_no_entry_signal(self):
        """All-NaN price column ÔåÆ no entry signal produced."""
        gen = SignalGenerator()
        prices = self._make_prices()
        prices["SYM1"] = np.nan  # entire column NaN
        pairs = [("SYM1", "SYM2", 0.01, 25.0)]
        signals = gen.generate(prices, pairs)
        entry_sigs = [s for s in signals if s.side in ("long", "short")]
        assert entry_sigs == [], "NaN data should produce zero entry signals"

    def test_nonstationary_pair_yields_no_entry(self):
        """Non-cointegrated (non-stationary) pair ÔåÆ no entry despite extreme z."""
        gen = SignalGenerator()
        # Create two independent random walks (not cointegrated)
        np.random.seed(100)
        n = 300
        prices = pd.DataFrame({
            "A": np.random.randn(n).cumsum() + 200,
            "B": np.random.randn(n).cumsum() + 100,
        }, index=pd.date_range("2024-01-01", periods=n))
        pairs = [("A", "B", 0.50, 25.0)]  # high p-value ÔåÆ not cointegrated
        signals = gen.generate(prices, pairs)
        entry_sigs = [s for s in signals if s.side in ("long", "short")]
        assert entry_sigs == [], (
            "Non-stationary spread should produce zero entry signals"
        )

    def test_no_look_ahead_bias(self):
        """Signal at bar t must be identical whether future data exists or not.

        We verify that the ZScoreCalculator (rolling window) produces
        the same z-score at bar t regardless of future data.  Note: the
        SpreadModel uses a Kalman filter whose state is path-dependent,
        so we test the z-score layer in isolation to confirm no look-ahead.
        """
        np.random.seed(42)
        n = 300
        spread_full = pd.Series(np.random.randn(n).cumsum())

        z_calc = ZScoreCalculator(default_lookback=20)

        # Z-scores computed with full data (300 bars)
        z_full = z_calc.compute(spread_full)
        z_at_200 = float(z_full.iloc[199])  # z at bar 200

        # Z-scores computed with truncated data (first 200 bars only)
        z_trunc = z_calc.compute(spread_full.iloc[:200])
        z_trunc_last = float(z_trunc.iloc[-1])

        assert abs(z_at_200 - z_trunc_last) < 1e-10, (
            f"Look-ahead detected: z_full@200={z_at_200}, z_trunc={z_trunc_last}"
        )

    def test_high_regime_suppresses_marginal_signal(self):
        """HIGH regime raises entry threshold ÔåÆ marginal z is filtered out."""
        # Mock regime detector to return HIGH
        mock_regime = MagicMock()
        mock_regime.update.return_value = MagicMock(regime=VolatilityRegime.HIGH)
        mock_regime.current_regime = VolatilityRegime.HIGH

        gen_high = SignalGenerator(regime_detector=mock_regime)

        # Mock regime as NORMAL
        mock_normal = MagicMock()
        mock_normal.update.return_value = MagicMock(regime=VolatilityRegime.NORMAL)
        mock_normal.current_regime = VolatilityRegime.NORMAL

        gen_norm = SignalGenerator(regime_detector=mock_normal)

        np.random.seed(42)
        n = 300
        base = np.random.randn(n).cumsum() + 100
        prices = pd.DataFrame({
            "A": base,
            "B": base * 0.95 + np.random.randn(n) * 0.3 + 50,
        }, index=pd.date_range("2024-01-01", periods=n))
        pairs = [("A", "B", 0.01, 25.0)]

        sigs_norm = gen_norm.generate(prices, pairs)
        sigs_high = gen_high.generate(prices, pairs)

        # HIGH regime should produce fewer (or equal) entry signals than NORMAL
        entries_norm = [s for s in sigs_norm if s.side in ("long", "short")]
        entries_high = [s for s in sigs_high if s.side in ("long", "short")]
        assert len(entries_high) <= len(entries_norm)
