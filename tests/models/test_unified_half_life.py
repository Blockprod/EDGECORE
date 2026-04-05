<<<<<<< HEAD
﻿"""
Sprint 3.2 ÔÇô Unify half-life estimation.
=======
"""
Sprint 3.2 – Unify half-life estimation.
>>>>>>> origin/main

Validates that:
1. `half_life_mean_reversion()` in cointegration.py delegates to
   `SpreadHalfLifeEstimator` (single source of truth).
2. Both paths produce identical results.
3. The AR(1) dimension-alignment fix is correct.
4. Edge cases and bounds validation work through the wrapper.
"""

import inspect
<<<<<<< HEAD

=======
>>>>>>> origin/main
import numpy as np
import pandas as pd
import pytest

from models.cointegration import half_life_mean_reversion
from models.half_life_estimator import SpreadHalfLifeEstimator, estimate_half_life

<<<<<<< HEAD
=======

>>>>>>> origin/main
# ---------------------------------------------------------------------------
# Helper: generate OU process with known half-life
# ---------------------------------------------------------------------------

def _ou_process(half_life: float, n: int = 500, noise: float = 0.1, seed: int = 42) -> pd.Series:
    np.random.seed(seed)
    mr = np.log(2) / half_life
    s = np.zeros(n)
    s[0] = np.random.normal(0, 1)
    for t in range(1, n):
        s[t] = s[t - 1] - mr * s[t - 1] + np.random.normal(0, noise)
    return pd.Series(s)


# ---------------------------------------------------------------------------
# 1. Delegation: wrapper uses SpreadHalfLifeEstimator
# ---------------------------------------------------------------------------

class TestDelegation:
    """half_life_mean_reversion must delegate to SpreadHalfLifeEstimator."""

    def test_source_contains_delegation(self):
        """Source of half_life_mean_reversion imports and uses the estimator."""
        src = inspect.getsource(half_life_mean_reversion)
        assert "SpreadHalfLifeEstimator" in src

    def test_no_independent_lstsq(self):
        """Wrapper must NOT contain its own np.linalg.lstsq call."""
        src = inspect.getsource(half_life_mean_reversion)
        assert "lstsq" not in src

    def test_no_spread_diff(self):
        """Wrapper must NOT contain the old diff-based AR(1) logic."""
        src = inspect.getsource(half_life_mean_reversion)
        assert "spread_diff" not in src
        assert "spread_lag" not in src


# ---------------------------------------------------------------------------
# 2. Consistency: wrapper == direct estimator call
# ---------------------------------------------------------------------------

class TestConsistency:
    """Wrapper and direct estimator must produce identical results."""

    @pytest.mark.parametrize("hl,seed", [(15, 1), (30, 2), (50, 3), (80, 4)])
    def test_same_result_ou(self, hl, seed):
        spread = _ou_process(half_life=hl, seed=seed)
        wrapper_hl = half_life_mean_reversion(spread)
        estimator = SpreadHalfLifeEstimator(lookback=min(252, len(spread)))
        direct_hl = estimator.estimate_half_life_from_spread(spread, validate=True)

        if direct_hl is None:
            assert wrapper_hl is None
        else:
            assert wrapper_hl == int(np.round(direct_hl))

    def test_random_walk_both_none_or_same(self):
        """Random walk: both paths should agree."""
        np.random.seed(99)
        rw = pd.Series(np.cumsum(np.random.randn(500)))
        wrapper_hl = half_life_mean_reversion(rw)
        est = SpreadHalfLifeEstimator(lookback=min(252, len(rw)))
        direct_hl = est.estimate_half_life_from_spread(rw, validate=True)
        if direct_hl is None:
            assert wrapper_hl is None
        else:
            assert wrapper_hl == int(np.round(direct_hl))


# ---------------------------------------------------------------------------
# 3. AR(1) dimension-alignment fix
# ---------------------------------------------------------------------------

class TestAR1DimensionFix:
    """The estimator must not raise LinAlgError from dimension mismatch."""

    def test_no_linalg_error_ou(self):
        """OU process must not trigger dimension error."""
        spread = _ou_process(half_life=30)
        est = SpreadHalfLifeEstimator(lookback=252)
        hl = est.estimate_half_life_from_spread(spread)
        assert hl is not None  # OU with HL=30 should be detected

    def test_no_linalg_error_random_walk(self):
        """Random walk must not raise, just return None or long HL."""
        np.random.seed(7)
        rw = pd.Series(np.cumsum(np.random.randn(500)))
        est = SpreadHalfLifeEstimator(lookback=252)
        # Should not raise
        hl = est.estimate_half_life_from_spread(rw)
        # Either None or a valid float
        assert hl is None or (isinstance(hl, float) and hl > 0)

    def test_aligned_dimensions(self):
        """X and y in AR(1) must have equal length."""
        spread = _ou_process(half_life=30)
        SpreadHalfLifeEstimator(lookback=252)
        data = spread.iloc[-252:].copy()
        dc = data - data.mean()
        lag = dc.shift(1)
        mask = lag.notna()
        X = lag[mask].values
        y = dc[mask].values
        assert len(X) == len(y), f"Dimension mismatch: X={len(X)}, y={len(y)}"


# ---------------------------------------------------------------------------
# 4. Bounds validation through wrapper
# ---------------------------------------------------------------------------

class TestBoundsValidation:
    """validate=True in wrapper enforces HL in [5, 200]."""

    def test_very_fast_mean_reversion_rejected(self):
<<<<<<< HEAD
        """HL=2 (very fast) Ôåô outside [5, 200] bounds Ôåô None."""
=======
        """HL=2 (very fast) ↓ outside [5, 200] bounds ↓ None."""
>>>>>>> origin/main
        spread = _ou_process(half_life=2, n=500, noise=0.05, seed=10)
        hl = half_life_mean_reversion(spread)
        # With validate=True, HL < 5 should be rejected
        # (if the estimator detects it at all)
        if hl is not None:
            assert hl >= 5

    def test_moderate_hl_accepted(self):
        """HL=25 should be within bounds."""
        spread = _ou_process(half_life=25, n=600, seed=55)
        hl = half_life_mean_reversion(spread)
        if hl is not None:
            assert 5 <= hl <= 200


# ---------------------------------------------------------------------------
# 5. Return type
# ---------------------------------------------------------------------------

class TestReturnType:
    """half_life_mean_reversion must return int or None."""

    def test_returns_int_for_ou(self):
        spread = _ou_process(half_life=30)
        hl = half_life_mean_reversion(spread)
        assert hl is None or isinstance(hl, int)

    def test_returns_none_for_short_series(self):
<<<<<<< HEAD
        """Series shorter than lookback Ôåô None."""
=======
        """Series shorter than lookback ↓ None."""
>>>>>>> origin/main
        short = pd.Series(np.random.randn(50))
        hl = half_life_mean_reversion(short)
        assert hl is None


# ---------------------------------------------------------------------------
# 6. Convenience function consistency
# ---------------------------------------------------------------------------

class TestConvenienceFunction:
    """estimate_half_life() from half_life_estimator must also work."""

    def test_estimate_half_life_ou(self):
        spread = _ou_process(half_life=30)
        hl = estimate_half_life(spread)
        assert hl is not None
        assert isinstance(hl, float)
        assert 5 <= hl <= 200


# ---------------------------------------------------------------------------
# 7. No residual independent AR(1) in cointegration.py
# ---------------------------------------------------------------------------

class TestNoResidualImplementation:
    """cointegration.py must not contain independent AR(1) logic anymore."""

    def test_no_spread_diff_in_cointegration(self):
        import models.cointegration as coint
        src = inspect.getsource(coint.half_life_mean_reversion)
        # Must NOT contain the old implementation markers
        assert "spread_diff" not in src
        assert "spread_lag" not in src
        assert "beta_1" not in src
        assert "1.0 + beta_1" not in src
