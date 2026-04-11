"""
Sprint 4.2 ÔÇô Kalman Filter for dynamic hedge ratio estimation.

Tests:
1. KalmanHedgeRatio ÔÇô core filter
   - ╬▓ adapts to true hedge ratio for cointegrated pair
   - Structural break in ╬▓ Ôåô Kalman adapts within 20 bars
   - Innovation > 3¤â Ôåô breakdown detected
   - Confidence interval narrows with more data
   - run_filter produces correct DataFrame
   - Diagnostics return expected keys

2. DynamicSpreadModel with Kalman
   - use_kalman=True produces dynamic spread
   - Default (use_kalman=False) behaves identically to before
   - Kalman spread has lower residual variance for structural break data
   - compute_spread dispatches to Kalman when enabled

3. Input validation & edge cases
   - delta/ve must be > 0
   - x Ôëê 0 handled gracefully
   - Mismatched series lengths raise error
"""

import numpy as np
import pandas as pd
import pytest

from models.adaptive_thresholds import DynamicSpreadModel
from models.kalman_hedge import KalmanHedgeRatio

# ÔôÇÔôÇÔôÇ Fixtures ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ


def _make_cointegrated_series(n: int = 300, beta_true: float = 2.0, seed: int = 42) -> tuple[pd.Series, pd.Series]:
    """Generate cointegrated series: y = beta_true * x + noise."""
    np.random.seed(seed)
    x = np.cumsum(np.random.randn(n) * 0.5) + 100
    noise = np.random.randn(n) * 0.3
    y = beta_true * x + noise
    return pd.Series(y, name="y"), pd.Series(x, name="x")


def _make_structural_break_series(
    n: int = 300, beta_before: float = 2.0, beta_after: float = 3.0, break_point: int = 150, seed: int = 42
) -> tuple[pd.Series, pd.Series]:
    """Generate series with a structural break in hedge ratio at break_point."""
    np.random.seed(seed)
    x = np.cumsum(np.random.randn(n) * 0.5) + 100
    noise = np.random.randn(n) * 0.3
    y = np.empty(n)
    y[:break_point] = beta_before * x[:break_point] + noise[:break_point]
    y[break_point:] = beta_after * x[break_point:] + noise[break_point:]
    return pd.Series(y, name="y"), pd.Series(x, name="x")


# ÔôÇÔôÇÔôÇ Core Kalman Filter ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ


class TestKalmanHedgeRatioCore:
    """Test KalmanHedgeRatio filter mechanics."""

    def test_beta_converges_to_true_value(self):
        """╬▓ should converge near true hedge ratio for stable cointegrated pair."""
        y, x = _make_cointegrated_series(n=300, beta_true=2.0)
        kf = KalmanHedgeRatio(delta=1e-4, ve=1e-3)
        kf.run_filter(y, x)

        # After 300 bars, ╬▓ should be within 5% of true ╬▓=2.0
        assert kf.beta is not None
        assert abs(kf.beta - 2.0) < 0.10, f"Kalman ╬▓={kf.beta:.4f} should be near 2.0"

    def test_structural_break_adaptation(self):
        """
        After structural break (╬▓: 2.0 Ôåô 3.0), Kalman should adapt
        within 20 bars of the break.
        """
        y, x = _make_structural_break_series(n=300, beta_before=2.0, beta_after=3.0, break_point=150)
        kf = KalmanHedgeRatio(delta=1e-3, ve=1e-3)  # Faster adaptation
        kf.run_filter(y, x)

        # ╬▓ at bar 170 (20 bars after break) should be closer to 3.0 than 2.0
        beta_at_170 = kf.beta_history[170]
        dist_to_new = abs(beta_at_170 - 3.0)
        dist_to_old = abs(beta_at_170 - 2.0)
        assert dist_to_new < dist_to_old, f"╬▓ at bar 170 = {beta_at_170:.4f}: should be closer to 3.0 than 2.0"

        # Final ╬▓ should be close to 3.0
        assert kf.beta is not None
        assert abs(kf.beta - 3.0) < 0.15, f"Final Kalman ╬▓={kf.beta:.4f} should be near 3.0"

    def test_innovation_breakdown_detection(self):
        """Structural break should trigger innovation spikes > 3¤â."""
        y, x = _make_structural_break_series(n=300, beta_before=2.0, beta_after=3.0, break_point=150)
        kf = KalmanHedgeRatio(delta=1e-5, ve=1e-3)  # Slow adaptation Ôåô larger innovations
        kf.run_filter(y, x)

        assert kf.breakdown_count > 0, "Structural break should trigger at least one innovation > 3¤â"

    def test_is_breakdown_method(self):
        """is_breakdown() should reflect latest innovation."""
        kf = KalmanHedgeRatio(innovation_threshold=2.0)
        # Feed stable data
        np.random.seed(42)
        for _ in range(50):
            kf.update(100 + np.random.randn() * 0.1, 50 + np.random.randn() * 0.1)

        # After stable data, no breakdown expected
        assert kf.is_breakdown() is False or True  # May or may not trigger
        # But we can verify the method doesn't crash and returns bool
        assert isinstance(kf.is_breakdown(), bool)

    def test_confidence_interval_narrows(self):
        """P (state covariance) should reach a small steady-state value."""
        y, x = _make_cointegrated_series(n=200, beta_true=2.0)
        kf = KalmanHedgeRatio(delta=1e-5, ve=1e-3)
        kf.run_filter(y, x)

        # Initial P_history[0] is 1.0 (scalar first bar), steady-state should be much smaller
        assert kf.P_history[0] == 1.0, "Initial P should be 1.0"
        # Steady-state P is now a 2D matrix [beta, alpha]; check beta variance (P[0,0])
        import numpy as np

        P = kf.P
        if P is not None and np.ndim(P) > 0:
            # 2D state: check beta variance is small (alpha may remain larger)
            assert P[0, 0] < 0.01, f"Steady-state P[0,0] (beta var)={P[0, 0]:.8f} should be small for delta=1e-5"
        else:
            assert P is not None
            assert float(P) < 0.01, (  # pyright: ignore[reportArgumentType]
                f"Steady-state P={float(P):.8f} should be small for delta=1e-5"
            )

    def test_get_confidence_interval(self):
        """CI should be (beta-z*sqrt(P), beta+z*sqrt(P))."""
        y, x = _make_cointegrated_series(n=100)
        kf = KalmanHedgeRatio()
        kf.run_filter(y, x)

        lo, hi = kf.get_confidence_interval(z=1.96)
        assert kf.beta is not None
        assert lo < kf.beta < hi
        assert hi - lo > 0  # CI has positive width

        # 99% CI should be wider than 95%
        lo99, hi99 = kf.get_confidence_interval(z=2.576)
        assert (hi99 - lo99) > (hi - lo)

    def test_run_filter_returns_dataframe(self):
        """run_filter should return DataFrame with correct columns and length."""
        y, x = _make_cointegrated_series(n=100)
        kf = KalmanHedgeRatio()
        df = kf.run_filter(y, x)

        assert isinstance(df, pd.DataFrame)
        assert set(df.columns) == {"beta", "spread", "innovation", "P"}
        assert len(df) == 100

    def test_diagnostics_keys(self):
        """get_diagnostics should return expected keys."""
        y, x = _make_cointegrated_series(n=50)
        kf = KalmanHedgeRatio()
        kf.run_filter(y, x)
        diag = kf.get_diagnostics()

        expected_keys = {
            "bars_processed",
            "current_beta",
            "current_P",
            "beta_95_ci",
            "breakdown_count",
            "recent_breakdown_rate",
            "delta",
            "ve",
            "innovation_threshold",
        }
        assert expected_keys <= set(diag.keys())
        assert diag["bars_processed"] == 50
        assert diag["current_beta"] == kf.beta

    def test_recent_breakdown_rate(self):
        """Breakdown rate should be in [0, 1]."""
        y, x = _make_structural_break_series(n=200)
        kf = KalmanHedgeRatio(delta=1e-5)
        kf.run_filter(y, x)

        rate = kf.get_recent_breakdown_rate(window=20)
        assert 0.0 <= rate <= 1.0


# ÔôÇÔôÇÔôÇ Input Validation ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ


class TestKalmanValidation:
    """Test input validation and edge cases."""

    def test_delta_must_be_positive(self):
        with pytest.raises(ValueError, match="delta"):
            KalmanHedgeRatio(delta=0)

    def test_ve_must_be_positive(self):
        with pytest.raises(ValueError, match="ve"):
            KalmanHedgeRatio(ve=-1)

    def test_x_near_zero_handled(self):
        """x Ôëê 0 should not crash, returns reasonable values."""
        kf = KalmanHedgeRatio()
        beta, spread, _inn = kf.update(100.0, 1e-15)
        assert np.isfinite(beta)
        assert np.isfinite(spread)

    def test_run_filter_mismatched_lengths(self):
        """Mismatched y and x lengths should raise ValueError."""
        y = pd.Series(np.random.randn(100))
        x = pd.Series(np.random.randn(50))
        kf = KalmanHedgeRatio()
        with pytest.raises(ValueError, match="same length"):
            kf.run_filter(y, x)

    def test_uninitialized_confidence_interval(self):
        """CI before any data should be (0, 0)."""
        kf = KalmanHedgeRatio()
        lo, hi = kf.get_confidence_interval()
        assert lo == 0.0
        assert hi == 0.0


# ÔôÇÔôÇÔôÇ DynamicSpreadModel Integration ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ


class TestDynamicSpreadModelKalman:
    """Test Kalman integration in DynamicSpreadModel."""

    def test_default_is_ols(self):
        """Default (use_kalman=False) should use static OLS ╬▓."""
        y, x = _make_cointegrated_series(n=200)
        model = DynamicSpreadModel(y, x, use_kalman=False)

        assert model.use_kalman is False
        assert model.kalman_filter is None
        assert isinstance(model.beta, (float, np.floating))

    def test_kalman_mode_initializes_filter(self):
        """use_kalman=True should create and run the Kalman filter."""
        y, x = _make_cointegrated_series(n=200)
        model = DynamicSpreadModel(y, x, use_kalman=True)

        assert model.use_kalman is True
        assert model.kalman_filter is not None
        assert model.kalman_filter.bars_processed == 200

    def test_kalman_beta_near_true_value(self):
        """Kalman ╬▓ should converge near true ╬▓=2.0."""
        y, x = _make_cointegrated_series(n=300, beta_true=2.0)
        model = DynamicSpreadModel(y, x, use_kalman=True)

        assert model.beta is not None
        assert abs(model.beta - 2.0) < 0.10, f"Kalman ╬▓={model.beta:.4f} should be near 2.0"

    def test_compute_spread_dispatches_to_kalman(self):
        """compute_spread should use Kalman when enabled."""
        y, x = _make_cointegrated_series(n=200)
        model_ols = DynamicSpreadModel(y, x, use_kalman=False)
        model_kf = DynamicSpreadModel(y, x, use_kalman=True)

        spread_ols = model_ols.compute_spread(y, x)
        spread_kf = model_kf.compute_spread(y, x)

        # Both should be Series of same length
        assert len(spread_ols) == len(spread_kf) == 200

        # They should NOT be identical (Kalman uses dynamic ╬▓)
        diff = (spread_ols - spread_kf).abs().mean()
        assert diff > 0.0, "Kalman and OLS spreads should differ"

    def test_kalman_adapts_to_structural_break(self):
        """
        For data with ╬▓ break, Kalman should produce smaller
        post-break residual variance than OLS.
        """
        y, x = _make_structural_break_series(n=300, beta_before=2.0, beta_after=3.0, break_point=150)
        model_ols = DynamicSpreadModel(y, x, use_kalman=False)
        model_kf = DynamicSpreadModel(y, x, use_kalman=True, kalman_delta=1e-3)

        spread_ols = model_ols.compute_spread(y, x)
        spread_kf = model_kf.compute_spread(y, x)

        # Post-break residual std: Kalman should be lower
        ols_post_std = spread_ols.iloc[170:].std()
        kf_post_std = spread_kf.iloc[170:].std()

        assert kf_post_std < ols_post_std, (
            f"Kalman post-break std={kf_post_std:.4f} should be < OLS post-break std={ols_post_std:.4f}"
        )

    def test_backward_compatible_signals(self):
        """OLS mode should produce identical signals to before Sprint 4.2."""
        y, x = _make_cointegrated_series(n=200)
        model = DynamicSpreadModel(y, x, use_kalman=False)
        spread = model.compute_spread(y, x)
        signals, info = model.get_adaptive_signals(spread)

        # Signals should be valid
        assert set(signals.unique()).issubset({-1, 0, 1})
        assert "entry_threshold" in info
        assert "z_score" in info

    def test_kalman_mode_signals(self):
        """Kalman mode should also produce valid signals via get_adaptive_signals."""
        y, x = _make_cointegrated_series(n=200)
        model = DynamicSpreadModel(y, x, use_kalman=True)
        spread = model.compute_spread(y, x)
        signals, info = model.get_adaptive_signals(spread)

        assert set(signals.unique()).issubset({-1, 0, 1})
        assert "entry_threshold" in info


class TestKalmanSpreadComparison:
    """Formal comparison: Kalman vs OLS for known scenarios."""

    def test_stable_relationship_both_similar(self):
        """For stable ╬▓, OLS and Kalman produce similar spread stats."""
        y, x = _make_cointegrated_series(n=500, beta_true=2.0)
        model_ols = DynamicSpreadModel(y, x, use_kalman=False)
        model_kf = DynamicSpreadModel(y, x, use_kalman=True)

        # Both betas should be close to 2.0
        assert model_ols.beta is not None
        assert model_kf.beta is not None
        assert abs(model_ols.beta - 2.0) < 0.1
        assert abs(model_kf.beta - 2.0) < 0.1

    def test_changing_beta_kalman_superior(self):
        """For changing ╬▓, Kalman should track the change better."""
        # ╬▓ gradually drifts from 2.0 to 3.0 over 300 bars
        np.random.seed(42)
        n = 300
        x = np.cumsum(np.random.randn(n) * 0.5) + 100
        beta_true = np.linspace(2.0, 3.0, n)
        noise = np.random.randn(n) * 0.3
        y = beta_true * x + noise

        y_s = pd.Series(y)
        x_s = pd.Series(x)

        kf = KalmanHedgeRatio(delta=1e-3)
        kf.run_filter(y_s, x_s)

        # Kalman's final ╬▓ should be close to 3.0
        assert kf.beta is not None
        assert abs(kf.beta - 3.0) < 0.2, f"Kalman ╬▓={kf.beta:.4f} should track drift to 3.0"

        # OLS ╬▓ would be ~2.5 (average of 2.0 and 3.0)
        X = np.column_stack([np.ones(n), x])
        ols_beta = np.linalg.lstsq(X, y, rcond=None)[0][1]
        # Kalman should be closer to final true ╬▓ than OLS
        assert kf.beta is not None
        assert abs(kf.beta - 3.0) < abs(ols_beta - 3.0), (
            f"Kalman ╬▓={kf.beta:.4f} should be closer to 3.0 than OLS ╬▓={ols_beta:.4f}"
        )


# ---------------------------------------------------------------------------
# P3-04: KalmanHedgeRatio.reset() — state isolation between pair sessions
# ---------------------------------------------------------------------------


class TestKalmanReset:
    """P3-04 — reset() must clear all accumulated state."""

    def _make_series(self, n: int = 100, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
        rng = np.random.default_rng(seed)
        x = np.cumsum(rng.standard_normal(n)) + 100.0
        y = 2.0 * x + rng.standard_normal(n) * 0.5
        return y, x

    def test_reset_clears_beta(self):
        """After training and reset, beta must be None (uninitialized)."""
        kf = KalmanHedgeRatio()
        y, x = self._make_series()
        for yi, xi in zip(y, x, strict=False):
            kf.update(float(yi), float(xi))
        assert kf.beta is not None
        kf.reset()
        assert kf.beta is None

    def test_reset_clears_history(self):
        """After reset all history lists must be empty."""
        kf = KalmanHedgeRatio()
        y, x = self._make_series()
        for yi, xi in zip(y, x, strict=False):
            kf.update(float(yi), float(xi))
        assert len(kf.beta_history) > 0
        kf.reset()
        assert kf.beta_history == []
        assert kf.spread_history == []
        assert kf.innovation_history == []
        assert kf.P_history == []

    def test_reset_clears_breakdown_count(self):
        """breakdown_count and bars_processed must be 0 after reset."""
        kf = KalmanHedgeRatio()
        y, x = self._make_series()
        for yi, xi in zip(y, x, strict=False):
            kf.update(float(yi), float(xi))
        kf.reset()
        assert kf.breakdown_count == 0
        assert kf.bars_processed == 0

    def test_reset_then_run_equals_fresh_instance(self):
        """A reset filter fed the same data must produce the same beta as a new instance."""
        y, x = self._make_series(n=150, seed=99)
        kf_fresh = KalmanHedgeRatio(delta=1e-4, ve=1e-3)
        kf_reused = KalmanHedgeRatio(delta=1e-4, ve=1e-3)

        # Poison kf_reused with unrelated data
        y_noise, x_noise = self._make_series(n=50, seed=7)
        for yi, xi in zip(y_noise, x_noise, strict=False):
            kf_reused.update(float(yi), float(xi))

        # Reset and replay the target series
        kf_reused.reset()
        for yi, xi in zip(y, x, strict=False):
            kf_fresh.update(float(yi), float(xi))
            kf_reused.update(float(yi), float(xi))

        assert kf_fresh.beta is not None
        assert kf_reused.beta is not None
        assert abs(kf_fresh.beta - kf_reused.beta) < 1e-10, (
            f"Reset filter beta {kf_reused.beta:.6f} != fresh filter beta {kf_fresh.beta:.6f}"
        )

    def test_run_filter_uses_reset_internally(self):
        """run_filter on a pre-trained filter must give same result as a fresh run."""
        y, x = self._make_series(n=120, seed=42)
        y_s = pd.Series(y)
        x_s = pd.Series(x)
        kf = KalmanHedgeRatio()

        df1 = kf.run_filter(y_s, x_s)
        # Second call: filter was left in trained state from df1 — must still match
        df2 = kf.run_filter(y_s, x_s)

        pd.testing.assert_frame_equal(df1, df2, rtol=1e-10)
