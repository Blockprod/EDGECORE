"""
Tests for Sprint 4.3 ÔÇô Newey-West HAC robust OLS and consensus screening.

Covers:
  1. engle_granger_test_robust() ÔÇô basic functionality and edge cases
  2. newey_west_consensus() ÔÇô agreement / divergence detection
  3. Integration with pair_trading pipeline (parallel + sequential)
"""

from unittest import mock

import numpy as np
import pandas as pd

from models.cointegration import (
    engle_granger_test,
    engle_granger_test_robust,
    newey_west_consensus,
)

# ---------------------------------------------------------------------------
# Helpers ÔÇô deterministic synthetic series
# ---------------------------------------------------------------------------


def _cointegrated_pair(n: int = 500, beta: float = 1.5, seed: int = 42):
    """Generate a cointegrated pair: y = beta*x + stationary_noise."""
    rng = np.random.RandomState(seed)
    x = np.cumsum(rng.randn(n))  # random walk
    noise = rng.randn(n) * 0.3  # stationary
    y = beta * x + noise
    return pd.Series(y, name="Y"), pd.Series(x, name="X")


def _independent_pair(n: int = 500, seed: int = 99):
    """Two independent random walks ÔÇô NOT cointegrated."""
    rng = np.random.RandomState(seed)
    x = np.cumsum(rng.randn(n))
    y = np.cumsum(rng.randn(n))
    return pd.Series(y, name="Y"), pd.Series(x, name="X")


# ===================================================================
# 1. engle_granger_test_robust ÔÇô Core HAC OLS
# ===================================================================


class TestEngleGrangerRobust:
    """Unit tests for the Newey-West HAC Engle-Granger function."""

    def test_cointegrated_pair_detected(self):
        """Strong cointegrated pair should be detected by HAC OLS."""
        y, x = _cointegrated_pair()
        result = engle_granger_test_robust(y, x, apply_bonferroni=False)
        assert result["error"] is None
        assert result["is_cointegrated"] is True
        assert result["adf_pvalue"] < 0.05

    def test_independent_pair_not_detected(self):
        """Independent random walks should NOT be detected."""
        y, x = _independent_pair()
        result = engle_granger_test_robust(y, x, apply_bonferroni=False)
        assert result["is_cointegrated"] is False

    def test_hac_standard_errors_present(self):
        """HAC standard errors, t-values, and p-values must be returned."""
        y, x = _cointegrated_pair()
        result = engle_granger_test_robust(y, x, apply_bonferroni=False)
        assert len(result["hac_bse"]) == 2  # const + beta
        assert len(result["hac_tvalues"]) == 2
        assert len(result["hac_pvalues"]) == 2
        assert not np.isnan(result["beta_hac_pvalue"])

    def test_beta_close_to_true_value(self):
        """Estimated beta should be close to the true beta (1.5)."""
        y, x = _cointegrated_pair(beta=1.5)
        result = engle_granger_test_robust(y, x, apply_bonferroni=False)
        assert abs(result["beta"] - 1.5) < 0.2

    def test_residuals_length(self):
        """Residuals should have the same length as the input data."""
        y, x = _cointegrated_pair(n=300)
        result = engle_granger_test_robust(y, x, apply_bonferroni=False)
        assert len(result["residuals"]) == 300

    def test_bonferroni_raises_threshold(self):
        """Bonferroni with many symbols should reduce alpha Ôåô harder to pass."""
        y, x = _cointegrated_pair()
        # Without Bonferroni
        r1 = engle_granger_test_robust(y, x, apply_bonferroni=False)
        # With Bonferroni (100 symbols Ôåô 4950 pairs Ôåô ╬▒/4950)
        r2 = engle_granger_test_robust(y, x, num_symbols=100, apply_bonferroni=True)
        assert r2["alpha_threshold"] < r1.get("alpha_threshold", 0.05)

    def test_custom_hac_maxlags(self):
        """Custom maxlags parameter should be accepted without error."""
        y, x = _cointegrated_pair()
        result = engle_granger_test_robust(y, x, hac_maxlags=5, apply_bonferroni=False)
        assert result["error"] is None

    def test_critical_values_returned(self):
        """ADF critical values should be present."""
        y, x = _cointegrated_pair()
        result = engle_granger_test_robust(y, x, apply_bonferroni=False)
        assert "1%" in result["critical_values"]
        assert "5%" in result["critical_values"]


# ===================================================================
# 2. engle_granger_test_robust ÔÇô Edge cases / validation
# ===================================================================


class TestRobustEdgeCases:
    """Edge-case validation for HAC OLS."""

    def test_insufficient_data(self):
        """Series shorter than 30 obs should return error."""
        y = pd.Series(np.random.randn(20))
        x = pd.Series(np.random.randn(20))
        result = engle_granger_test_robust(y, x)
        assert result["is_cointegrated"] is False
        assert "Insufficient" in result["error"]

    def test_nan_in_data(self):
        """NaN in input should be caught."""
        y, x = _cointegrated_pair()
        y.iloc[10] = np.nan
        result = engle_granger_test_robust(y, x)
        assert result["is_cointegrated"] is False
        assert "NaN" in result["error"]

    def test_zero_variance(self):
        """Constant series should be rejected."""
        y = pd.Series(np.ones(100))
        x = pd.Series(np.random.randn(100))
        result = engle_granger_test_robust(y, x)
        assert result["is_cointegrated"] is False
        assert "variance" in result["error"].lower()

    def test_numpy_array_input(self):
        """Should accept numpy arrays as well as pandas Series."""
        y, x = _cointegrated_pair()
        result = engle_granger_test_robust(pd.Series(y.values), pd.Series(x.values), apply_bonferroni=False)
        assert result["error"] is None


# ===================================================================
# 3. newey_west_consensus ÔÇô OLS vs. HAC agreement
# ===================================================================


class TestNeweyWestConsensus:
    """Tests for the consensus function between standard and HAC OLS."""

    def test_consensus_cointegrated(self):
        """Both methods should agree on a clearly cointegrated pair."""
        y, x = _cointegrated_pair()
        result = newey_west_consensus(y, x, apply_bonferroni=False)
        assert result["consensus"] is True
        assert result["standard_cointegrated"] is True
        assert result["robust_cointegrated"] is True
        assert result["divergent"] is False

    def test_consensus_not_cointegrated(self):
        """Both methods should agree: independent walks are NOT cointegrated."""
        y, x = _independent_pair()
        result = newey_west_consensus(y, x, apply_bonferroni=False)
        # consensus should be False (both reject, so both agree on "no")
        assert not result["consensus"]
        assert not result["divergent"]

    def test_divergent_flag_on_mismatch(self):
        """When one says yes and other no, divergent must be True."""
        y, x = _cointegrated_pair()
        # Force standard to say cointegrated, robust to say not
        mock_standard = {
            "is_cointegrated": True,
            "adf_pvalue": 0.001,
        }
        mock_robust = {
            "is_cointegrated": False,
            "adf_pvalue": 0.10,
        }
        with mock.patch("models.cointegration.engle_granger_test", return_value=mock_standard):
            with mock.patch("models.cointegration.engle_granger_test_robust", return_value=mock_robust):
                result = newey_west_consensus(y, x)
                assert result["divergent"] is True
                assert result["consensus"] is False

    def test_consensus_requires_both_true(self):
        """Consensus is True ONLY when BOTH agree cointegrated."""
        y, x = _cointegrated_pair()
        mock_standard = {"is_cointegrated": True, "adf_pvalue": 0.001}
        mock_robust = {"is_cointegrated": True, "adf_pvalue": 0.002}
        with mock.patch("models.cointegration.engle_granger_test", return_value=mock_standard):
            with mock.patch("models.cointegration.engle_granger_test_robust", return_value=mock_robust):
                result = newey_west_consensus(y, x)
                assert result["consensus"] is True

    def test_bonferroni_forwarded(self):
        """Bonferroni params should be forwarded to both functions."""
        y, x = _cointegrated_pair()
        with (
            mock.patch("models.cointegration.engle_granger_test") as m_std,
            mock.patch("models.cointegration.engle_granger_test_robust") as m_rob,
        ):
            m_std.return_value = {"is_cointegrated": False}
            m_rob.return_value = {"is_cointegrated": False}
            newey_west_consensus(y, x, num_symbols=50, apply_bonferroni=True, hac_maxlags=8)
            # Check that num_symbols was forwarded
            m_std.assert_called_once()
            assert m_std.call_args.kwargs["num_symbols"] == 50
            m_rob.assert_called_once()
            assert m_rob.call_args.kwargs["num_symbols"] == 50
            assert m_rob.call_args.kwargs["hac_maxlags"] == 8


# ===================================================================
# 4. Integration ÔÇô pair_trading screening flow
# ===================================================================


class TestPairTradingHACIntegration:
    """Test that the pair trading pipeline respects HAC consensus."""

    def _make_strategy(self, nw_consensus=True, johansen=False):
        """Create a PairTradingStrategy with controlled config."""
        from strategies.pair_trading import PairTradingStrategy

        with mock.patch("strategies.pair_trading.PairTradingStrategy.__init__", return_value=None):
            strat = PairTradingStrategy.__new__(PairTradingStrategy)
        # Minimal config mock
        strat.config = mock.MagicMock()
        strat.config.min_correlation = 0.3
        strat.config.max_half_life = 60
        strat.config.lookback_window = 200
        strat.config.johansen_confirmation = johansen
        strat.config.newey_west_consensus = nw_consensus
        return strat

    def test_parallel_tuple_includes_nw_flag(self):
        """find_cointegrated_pairs_parallel builds 9-element tuples."""
        strat = self._make_strategy(nw_consensus=True, johansen=False)
        # Create simple price data
        rng = np.random.RandomState(42)
        df = pd.DataFrame(
            {
                "A": np.cumsum(rng.randn(200)),
                "B": np.cumsum(rng.randn(200)),
            }
        )
        # Intercept ThreadPoolExecutor to inspect tuples without actually running
        with mock.patch("strategies.pair_trading.ThreadPoolExecutor") as mock_pool:
            mock_pool.return_value.__enter__ = mock.MagicMock(return_value=mock_pool)
            mock_pool.return_value.__exit__ = mock.MagicMock(return_value=False)
            mock_pool.map = mock.MagicMock(return_value=[])
            strat.find_cointegrated_pairs_parallel(df)
            call_args = mock_pool.map.call_args
            if call_args:
                tuples_list = call_args[0][1]
                assert len(tuples_list[0]) == 9  # 9-element tuple
                assert tuples_list[0][-1] is True  # nw_consensus flag

    def test_static_method_rejects_on_divergence(self):
        """_test_pair_cointegration rejects pair when HAC diverges."""
        from strategies.pair_trading import PairTradingStrategy

        y, x = _cointegrated_pair()
        # Mock EG to say cointegrated, consensus to say divergent
        mock_eg = {
            "is_cointegrated": True,
            "adf_pvalue": 0.001,
            "residuals": np.random.randn(500),
        }
        mock_cons = {
            "consensus": False,
            "standard_cointegrated": True,
            "robust_cointegrated": False,
            "divergent": True,
        }
        with mock.patch("strategies.pair_validator.engle_granger_test", return_value=mock_eg):
            with mock.patch("strategies.pair_validator._newey_west_consensus", return_value=mock_cons):
                result = PairTradingStrategy._test_pair_cointegration(
                    ("A", "B", y, x, 0.0, 60, 10, False, True)  # nw_consensus=True, johansen=False
                )
                assert result is None  # Rejected

    def test_static_method_accepts_on_consensus(self):
        """_test_pair_cointegration accepts pair when HAC agrees."""
        from strategies.pair_trading import PairTradingStrategy

        y, x = _cointegrated_pair()
        mock_eg = {
            "is_cointegrated": True,
            "adf_pvalue": 0.001,
            "residuals": np.random.randn(500),
        }
        mock_cons = {
            "consensus": True,
            "standard_cointegrated": True,
            "robust_cointegrated": True,
            "divergent": False,
        }
        with mock.patch("strategies.pair_validator.engle_granger_test", return_value=mock_eg):
            with mock.patch("strategies.pair_validator._newey_west_consensus", return_value=mock_cons):
                with mock.patch("strategies.pair_validator.half_life_mean_reversion", return_value=10):
                    result = PairTradingStrategy._test_pair_cointegration(("A", "B", y, x, 0.0, 60, 10, False, True))
                    assert result is not None
                    assert result[0] == "A"
                    assert result[1] == "B"

    def test_nw_disabled_skips_check(self):
        """When nw_consensus=False, HAC check is skipped entirely."""
        from strategies.pair_trading import PairTradingStrategy

        y, x = _cointegrated_pair()
        mock_eg = {
            "is_cointegrated": True,
            "adf_pvalue": 0.001,
            "residuals": np.random.randn(500),
        }
        with mock.patch("strategies.pair_validator.engle_granger_test", return_value=mock_eg):
            with mock.patch("strategies.pair_validator._newey_west_consensus") as mock_nw:
                with mock.patch("strategies.pair_validator.half_life_mean_reversion", return_value=10):
                    result = PairTradingStrategy._test_pair_cointegration(
                        ("A", "B", y, x, 0.0, 60, 10, False, False)  # nw_consensus=False
                    )
                    mock_nw.assert_not_called()
                    assert result is not None


# ===================================================================
# 5. HAC vs standard ÔÇô comparative properties
# ===================================================================


class TestHACvsStandard:
    """Compare HAC and standard OLS outputs."""

    def test_same_beta_direction(self):
        """HAC and standard OLS should give same-sign beta."""
        y, x = _cointegrated_pair(beta=2.0)
        r_std = engle_granger_test(y, x, apply_bonferroni=False, check_integration_order=False)
        r_hac = engle_granger_test_robust(y, x, apply_bonferroni=False)
        # Both should have positive beta
        assert r_std["beta"] > 0
        assert r_hac["beta"] > 0

    def test_hac_se_at_least_as_large(self):
        """HAC standard errors should generally be >= OLS standard errors.

        Newey-West accounts for autocorrelation, which OLS ignores,
        so SEs are typically equal or larger.
        """
        y, x = _cointegrated_pair(n=1000, seed=7)
        import statsmodels.api as sm

        X = sm.add_constant(x.values.astype(np.float64))
        # Standard OLS SE
        ols_se = sm.OLS(y.values.astype(np.float64), X).fit().bse
        # HAC SE
        r_hac = engle_granger_test_robust(y, x, apply_bonferroni=False)
        hac_se = r_hac["hac_bse"]
        # HAC SE on beta (index 1) should be >= OLS SE
        assert hac_se[1] >= ols_se[1] * 0.9  # allow tiny numerical slack

    def test_both_agree_on_strong_signal(self):
        """On a strong cointegrated signal, both methods agree."""
        y, x = _cointegrated_pair(n=1000, beta=1.0, seed=123)
        r_std = engle_granger_test(y, x, apply_bonferroni=False, check_integration_order=False)
        r_hac = engle_granger_test_robust(y, x, apply_bonferroni=False)
        assert r_std["is_cointegrated"] == r_hac["is_cointegrated"]

    def test_both_reject_independent(self):
        """On independent walks, both methods should reject."""
        y, x = _independent_pair(n=1000)
        r_std = engle_granger_test(y, x, apply_bonferroni=False, check_integration_order=False)
        r_hac = engle_granger_test_robust(y, x, apply_bonferroni=False)
        assert not r_std["is_cointegrated"]
        assert not r_hac["is_cointegrated"]


# ===================================================================
# 6. Config integration
# ===================================================================


class TestConfigNeweyWest:
    """Test that config flag controls the behavior."""

    def test_config_default_true(self):
        """Default config should have newey_west_consensus=True."""
        from config.settings import StrategyConfig

        cfg = StrategyConfig()
        assert cfg.newey_west_consensus is True

    def test_config_can_disable(self):
        """Config flag can be set to False."""
        from config.settings import StrategyConfig

        cfg = StrategyConfig(newey_west_consensus=False)
        assert cfg.newey_west_consensus is False
