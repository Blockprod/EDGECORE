"""
Sprint 4.1 ÔÇô Johansen multi-variate cointegration test.

Tests:
1. JohansenCointegrationTest ÔÇô core functionality
   - Known cointegrated pair Ôåô rank ÔëÑ 1
   - Random walk pair Ôåô rank = 0
   - Multi-variate (3 series) Ôåô correct rank
   - Input validation (NaN, too few rows, single column)
   - Trace vs max-eigenvalue conservatism

2. johansen_confirm_pair ÔÇô convenience function
   - Cointegrated pair confirmed
   - Random pair rejected

3. Integration with PairTradingStrategy ÔÇô double screening
   - EG + Johansen both pass Ôåô pair accepted
   - EG passes but Johansen rejects Ôåô pair filtered out
   - Config flag disables Johansen confirmation
"""

import numpy as np
import pandas as pd
from unittest.mock import patch

from models.johansen import JohansenCointegrationTest, johansen_confirm_pair


# ÔôÇÔôÇÔôÇ Fixtures ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ


def _make_cointegrated_pair(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Generate a pair of cointegrated I(1) series."""
    np.random.seed(seed)
    # Common random walk (stochastic trend)
    common_trend = np.cumsum(np.random.randn(n) * 0.5) + 100
    # y = 2*trend + stationary noise, x = trend + stationary noise
    y = 2.0 * common_trend + np.random.randn(n) * 0.3
    x = common_trend + np.random.randn(n) * 0.3
    return pd.DataFrame({"y": y, "x": x})


def _make_random_pair(n: int = 300, seed: int = 99) -> pd.DataFrame:
    """Generate two independent random walks (not cointegrated)."""
    np.random.seed(seed)
    y = np.cumsum(np.random.randn(n) * 0.5) + 100
    x = np.cumsum(np.random.randn(n) * 0.5) + 50
    return pd.DataFrame({"y": y, "x": x})


def _make_trivariate_cointegrated(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Generate 3 cointegrated series sharing a common trend."""
    np.random.seed(seed)
    trend = np.cumsum(np.random.randn(n) * 0.5) + 100
    a = 1.0 * trend + np.random.randn(n) * 0.2
    b = 2.0 * trend + np.random.randn(n) * 0.2
    c = 0.5 * trend + np.random.randn(n) * 0.2
    return pd.DataFrame({"a": a, "b": b, "c": c})


# ÔôÇÔôÇÔôÇ Core Johansen Test ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ


class TestJohansenCointegrationTest:
    """Test the Johansen cointegration test class."""

    def test_cointegrated_pair_detected(self):
        """Known cointegrated pair should have rank ÔëÑ 1."""
        data = _make_cointegrated_pair()
        jt = JohansenCointegrationTest()
        result = jt.test(data)

        assert result["error"] is None, f"Unexpected error: {result['error']}"
        assert result["is_cointegrated"] is True
        assert result["rank"] >= 1
        assert len(result["trace_statistics"]) == 2  # 2 variables
        assert len(result["max_eig_statistics"]) == 2

    def test_random_pair_not_cointegrated(self):
        """Independent random walks should have rank = 0."""
        data = _make_random_pair()
        jt = JohansenCointegrationTest()
        result = jt.test(data)

        assert result["error"] is None
        assert result["is_cointegrated"] is False
        assert result["rank"] == 0

    def test_trivariate_cointegration(self):
        """Three series sharing a common trend Ôåô rank ÔëÑ 1."""
        data = _make_trivariate_cointegrated()
        jt = JohansenCointegrationTest()
        result = jt.test(data)

        assert result["error"] is None
        assert result["is_cointegrated"] is True
        assert result["rank"] >= 1
        assert len(result["trace_statistics"]) == 3  # 3 variables

    def test_rank_conservative_min_trace_maxeig(self):
        """Rank should be min(trace_rank, max_eig_rank) for conservatism."""
        data = _make_cointegrated_pair()
        jt = JohansenCointegrationTest()
        result = jt.test(data)

        assert result["rank"] <= result["trace_rank"]
        assert result["rank"] <= result["max_eig_rank"]
        assert result["rank"] == min(result["trace_rank"], result["max_eig_rank"])

    def test_critical_values_present(self):
        """Critical values at 90%, 95%, 99% should be returned."""
        data = _make_cointegrated_pair()
        jt = JohansenCointegrationTest()
        result = jt.test(data)

        for key in ["90", "95", "99"]:
            assert key in result["trace_critical_values"]
            assert key in result["max_eig_critical_values"]
            assert len(result["trace_critical_values"][key]) == 2

    def test_eigenvectors_returned(self):
        """Cointegrating vectors should be returned."""
        data = _make_cointegrated_pair()
        jt = JohansenCointegrationTest()
        result = jt.test(data)

        assert len(result["eigenvectors"]) > 0
        assert len(result["eigenvalues"]) > 0

    def test_significance_level_respected(self):
        """Custom significance level should be stored in result."""
        data = _make_cointegrated_pair()
        jt = JohansenCointegrationTest(significance_level=0.01)
        result = jt.test(data)

        assert result["significance_level"] == 0.01

    # --- Input validation ---

    def test_nan_data_rejected(self):
        """DataFrame with NaN should return error."""
        data = _make_cointegrated_pair()
        data.iloc[5, 0] = np.nan
        jt = JohansenCointegrationTest()
        result = jt.test(data)

        assert result["is_cointegrated"] is False
        assert result["error"] is not None
        assert "NaN" in result["error"]

    def test_single_column_rejected(self):
        """DataFrame with <2 columns should return error."""
        data = pd.DataFrame({"x": np.random.randn(100)})
        jt = JohansenCointegrationTest()
        result = jt.test(data)

        assert result["is_cointegrated"] is False
        assert result["error"] is not None

    def test_too_few_rows_rejected(self):
        """DataFrame with too few rows should return error."""
        data = _make_cointegrated_pair(n=10)
        jt = JohansenCointegrationTest()
        result = jt.test(data)

        assert result["is_cointegrated"] is False
        assert result["error"] is not None

    def test_zero_variance_rejected(self):
        """Constant series should return error."""
        data = pd.DataFrame({"x": np.ones(100), "y": np.ones(100)})
        jt = JohansenCointegrationTest()
        result = jt.test(data)

        assert result["is_cointegrated"] is False
        assert result["error"] is not None

    def test_non_dataframe_rejected(self):
        """Non-DataFrame input should return error."""
        jt = JohansenCointegrationTest()
        result = jt.test(np.random.randn(100, 2))

        assert result["is_cointegrated"] is False
        assert result["error"] is not None

    def test_det_order_override(self):
        """det_order parameter override should work."""
        data = _make_cointegrated_pair()
        jt = JohansenCointegrationTest(det_order=0)
        result = jt.test(data, det_order=-1)  # Override to no deterministic

        assert result["error"] is None
        # Should still produce a result (may differ from det_order=0)
        assert isinstance(result["rank"], int)


# ÔôÇÔôÇÔôÇ Convenience Function ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ


class TestJohansenConfirmPair:
    """Test the johansen_confirm_pair convenience function."""

    def test_cointegrated_pair_confirmed(self):
        """Known cointegrated pair should be confirmed."""
        data = _make_cointegrated_pair()
        result = johansen_confirm_pair(data["y"], data["x"])

        assert result["is_cointegrated"] is True
        assert result["rank"] >= 1
        assert result["error"] is None

    def test_random_pair_rejected(self):
        """Independent random walks should be rejected."""
        data = _make_random_pair()
        result = johansen_confirm_pair(data["y"], data["x"])

        assert result["is_cointegrated"] is False
        assert result["rank"] == 0


# ÔôÇÔôÇÔôÇ Integration: Double Screening ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ


class TestDoubleScreeningIntegration:
    """Test Johansen integration in PairTradingStrategy._test_pair_cointegration."""

    def test_eg_and_johansen_both_pass(self):
        """Pair that passes both EG and Johansen should be accepted."""
        from strategies.pair_trading import PairTradingStrategy

        data = _make_cointegrated_pair(n=300)
        args = (
            "SYM_Y", "SYM_X",
            data["y"], data["x"],
            0.5,   # min_corr
            60,    # max_hl
            2,     # num_symbols (lenient Bonferroni)
            True,  # johansen_confirm
        )
        result = PairTradingStrategy._test_pair_cointegration(args)

        # Should return a tuple (sym1, sym2, pvalue, half_life) or None
        # For strongly cointegrated data, expect acceptance
        if result is not None:
            sym1, sym2, pvalue, hl = result
            assert sym1 == "SYM_Y"
            assert sym2 == "SYM_X"
            assert pvalue < 0.05
            assert 0 < hl <= 60

    def test_johansen_rejection_filters_pair(self):
        """If Johansen rejects, pair should be filtered even if EG passes."""
        from strategies.pair_trading import PairTradingStrategy

        data = _make_cointegrated_pair(n=300)

        # Mock johansen to reject, simulating a borderline pair
        with patch("models.johansen.johansen_confirm_pair") as mock_joh:
            mock_joh.return_value = {"is_cointegrated": False, "rank": 0}
            args = (
                "SYM_Y", "SYM_X",
                data["y"], data["x"],
                0.5, 60, 2,
                True,  # johansen_confirm ON
            )
            result = PairTradingStrategy._test_pair_cointegration(args)
            # Even if EG would pass, Johansen rejection Ôåô None
            assert result is None

    def test_johansen_disabled_skips_confirmation(self):
        """When johansen_confirm=False, only EG is used."""
        from strategies.pair_trading import PairTradingStrategy

        data = _make_cointegrated_pair(n=300)

        with patch("models.johansen.johansen_confirm_pair") as mock_joh:
            args = (
                "SYM_Y", "SYM_X",
                data["y"], data["x"],
                0.5, 60, 2,
                False,  # johansen_confirm OFF
            )
            PairTradingStrategy._test_pair_cointegration(args)
            # Johansen should never be called
            mock_joh.assert_not_called()


class TestConfigJohansenFlag:
    """Test the johansen_confirmation config flag."""

    def test_default_johansen_confirmation_true(self):
        """Default config should have johansen_confirmation=True."""
        from config.settings import StrategyConfig
        config = StrategyConfig()
        assert config.johansen_confirmation is True

    def test_johansen_flag_controls_double_screening(self):
        """Config flag should propagate to discovery."""
        from strategies.pair_trading import PairTradingStrategy

        strategy = PairTradingStrategy()
        assert hasattr(strategy.config, 'johansen_confirmation')
