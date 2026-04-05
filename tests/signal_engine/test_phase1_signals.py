<<<<<<< HEAD
﻿"""
=======
"""
>>>>>>> origin/main
Tests for Phase 1 signal engines:
    - OUSignalGenerator (1.1)
    - CrossSectionalMomentum (1.2)
    - VolatilityRegimeSignal (1.3)
    - SignalCombiner wiring (1.4)
"""

import numpy as np
import pandas as pd
import pytest

<<<<<<< HEAD
from signal_engine.combiner import SignalCombiner, SignalSource
from signal_engine.cross_sectional import CrossSectionalMomentum
from signal_engine.ou_signal import OUSignalGenerator
from signal_engine.vol_signal import VolatilityRegimeSignal

# ===========================================================================
# SECTION 1 ÔÇö OUSignalGenerator
=======
from signal_engine.ou_signal import OUSignalGenerator, OUParams
from signal_engine.cross_sectional import CrossSectionalMomentum
from signal_engine.vol_signal import VolatilityRegimeSignal
from signal_engine.combiner import SignalCombiner, SignalSource


# ===========================================================================
# SECTION 1 — OUSignalGenerator
>>>>>>> origin/main
# ===========================================================================

class TestOUSignalGenerator:
    """Tests for OU parameter estimation and signal computation."""

    def _make_ou_spread(self, n=300, theta=0.1, mu=0.0, sigma=0.5, seed=42):
        """Generate a synthetic OU process."""
        rng = np.random.RandomState(seed)
        x = np.zeros(n)
        dt = 1.0
        for i in range(1, n):
            x[i] = x[i-1] + theta * (mu - x[i-1]) * dt + sigma * rng.randn() * np.sqrt(dt)
        return pd.Series(x)

    def test_basic_ou_estimation(self):
        """OU params are estimated correctly for a synthetic OU process."""
        spread = self._make_ou_spread(n=500, theta=0.1, mu=0.0, sigma=0.5)
        ou = OUSignalGenerator(lookback=200)
        params = ou.estimate_params(spread)
        assert params is not None
        assert params.theta > 0
        assert 0.01 < params.theta < 0.5  # reasonable range
        assert abs(params.mu) < 2.0

    def test_half_life_positive(self):
        """Half-life is positive and reasonable."""
        spread = self._make_ou_spread(n=500, theta=0.1)
        ou = OUSignalGenerator(lookback=200)
        params = ou.estimate_params(spread)
        assert params is not None
        assert params.half_life > 0
        assert params.half_life < 100

    def test_non_stationary_returns_none(self):
        """Random walk (no mean-reversion) returns None."""
        rng = np.random.RandomState(42)
        random_walk = pd.Series(np.cumsum(rng.randn(300)))
        ou = OUSignalGenerator(lookback=200)
        params = ou.estimate_params(random_walk)
        # Random walk theta ~ 0, should return None or very small theta
        if params is not None:
            assert params.theta < 0.05

    def test_score_range(self):
        """Score is in [-1, 1]."""
        spread = self._make_ou_spread(n=500, theta=0.1, mu=0.0)
        ou = OUSignalGenerator()
        score = ou.compute_score(spread)
        assert -1.0 <= score <= 1.0

    def test_score_sign_reflects_position(self):
        """Score is positive when spread < mu (expect up), negative when > mu."""
        spread = self._make_ou_spread(n=500, theta=0.15, mu=0.0, sigma=0.3)
        ou = OUSignalGenerator(lookback=200)
        params = ou.estimate_params(spread)
        if params is not None:
            current = float(spread.iloc[-1])
            score = ou.compute_score(spread)
            if abs(current - params.mu) > 0.1:
                # Direction check: score should have same sign as (mu - current)
                expected_sign = np.sign(params.mu - current)
                assert np.sign(score) == expected_sign or abs(score) < 0.05

    def test_short_series_returns_zero(self):
        """Very short series returns 0.0 score."""
        spread = pd.Series([1.0, 2.0, 1.5])
        ou = OUSignalGenerator()
        assert ou.compute_score(spread) == 0.0

    def test_lookback_validation(self):
        """Lookback < 10 raises ValueError."""
        with pytest.raises(ValueError, match="lookback"):
            OUSignalGenerator(lookback=5)


# ===========================================================================
<<<<<<< HEAD
# SECTION 2 ÔÇö CrossSectionalMomentum
=======
# SECTION 2 — CrossSectionalMomentum
>>>>>>> origin/main
# ===========================================================================

class TestCrossSectionalMomentum:
    """Tests for cross-sectional ranking signal."""

    def _make_prices(self, n=300, n_symbols=10, seed=42):
        """Generate synthetic prices for multiple symbols."""
        rng = np.random.RandomState(seed)
        prices = {}
        for i in range(n_symbols):
            sym = f"SYM{i}"
            # Random drift + noise
            drift = 0.001 * (i - n_symbols // 2)  # ascending drift
            returns = drift + 0.02 * rng.randn(n)
            prices[sym] = 100.0 * np.exp(np.cumsum(returns))
        return pd.DataFrame(prices)

    def test_rankings_computed(self):
        """Rankings are populated after update."""
        prices = self._make_prices()
        csm = CrossSectionalMomentum()
        csm.update_rankings(prices)
        assert len(csm.rankings) == 10

    def test_ranking_values_in_range(self):
        """All rankings are between 0 and 1 (percentile)."""
        prices = self._make_prices()
        csm = CrossSectionalMomentum()
        csm.update_rankings(prices)
        for rank in csm.rankings.values():
            assert 0.0 <= rank <= 1.0

    def test_score_range(self):
        """Score is in [-1, 1]."""
        prices = self._make_prices()
        csm = CrossSectionalMomentum()
        csm.update_rankings(prices)
        score = csm.compute_score("SYM0", "SYM9")
        assert -1.0 <= score <= 1.0

    def test_score_sign_reflects_ranking(self):
        """Higher-ranked symbol gives positive score."""
        prices = self._make_prices()
        csm = CrossSectionalMomentum()
        csm.update_rankings(prices)
<<<<<<< HEAD
        # SYM9 should have highest drift ÔåÆ highest rank
=======
        # SYM9 should have highest drift → highest rank
>>>>>>> origin/main
        score = csm.compute_score("SYM9", "SYM0")
        assert score > 0  # SYM9 > SYM0

    def test_score_symmetry(self):
        """Score(A, B) = -Score(B, A)."""
        prices = self._make_prices()
        csm = CrossSectionalMomentum()
        csm.update_rankings(prices)
        s1 = csm.compute_score("SYM3", "SYM7")
        s2 = csm.compute_score("SYM7", "SYM3")
        assert abs(s1 + s2) < 0.01

    def test_unknown_symbol_returns_zero(self):
        """Unknown symbol returns 0.0."""
        csm = CrossSectionalMomentum()
        assert csm.compute_score("AAPL", "MSFT") == 0.0

    def test_empty_prices(self):
        """Empty price DataFrame results in no rankings."""
        csm = CrossSectionalMomentum()
        csm.update_rankings(pd.DataFrame())
        assert len(csm.rankings) == 0

    def test_single_symbol_no_rankings(self):
        """Single symbol cannot be ranked."""
        csm = CrossSectionalMomentum()
        csm.update_rankings(pd.DataFrame({"SYM": [100, 101, 102]}))
        assert len(csm.rankings) == 0


# ===========================================================================
<<<<<<< HEAD
# SECTION 3 ÔÇö VolatilityRegimeSignal
=======
# SECTION 3 — VolatilityRegimeSignal
>>>>>>> origin/main
# ===========================================================================

class TestVolatilityRegimeSignal:
    """Tests for volatility compression/expansion detection."""

    def _make_spread(self, n=200, compressed=False, seed=42):
        """Generate spread with controlled volatility regime."""
        rng = np.random.RandomState(seed)
        vals = np.zeros(n)
        for i in range(1, n):
            vol = 0.5 if (i > n - 30 and compressed) else 2.0
            vals[i] = vals[i-1] + vol * rng.randn()
        return pd.Series(vals)

    def test_score_range(self):
        """Score is in [-1, 1]."""
        spread = self._make_spread()
        vol = VolatilityRegimeSignal()
        score = vol.compute_score(spread)
        assert -1.0 <= score <= 1.0

    def test_compressed_vol_positive(self):
        """Compressed vol gives positive score."""
        spread = self._make_spread(compressed=True)
        vol = VolatilityRegimeSignal()
        score = vol.compute_score(spread)
        assert score > 0

    def test_is_compressed_detection(self):
        """is_compressed returns True when vol is low."""
        spread = self._make_spread(compressed=True)
        vol = VolatilityRegimeSignal()
        assert vol.is_compressed(spread) is True

    def test_short_series_defaults(self):
        """Short series returns safe defaults."""
        spread = pd.Series([1.0, 2.0, 3.0])
        vol = VolatilityRegimeSignal()
        assert vol.compute_score(spread) == 0.0
        assert vol.is_compressed(spread) is True  # default: allow
        assert vol.is_exploding(spread) is False  # default: no alarm

    def test_vol_ratio_positive(self):
        """Vol ratio is positive when computed."""
        spread = self._make_spread()
        vol = VolatilityRegimeSignal()
        ratio = vol.compute_vol_ratio(spread)
        if ratio is not None:
            assert ratio > 0

    def test_window_validation(self):
        """Invalid windows raise ValueError."""
        with pytest.raises(ValueError, match="fast_window"):
            VolatilityRegimeSignal(fast_window=3)
        with pytest.raises(ValueError, match="slow_window"):
            VolatilityRegimeSignal(fast_window=20, slow_window=15)
        with pytest.raises(ValueError, match="exit_threshold"):
            VolatilityRegimeSignal(entry_threshold=1.5, exit_threshold=1.0)


# ===========================================================================
<<<<<<< HEAD
# SECTION 4 ÔÇö SignalCombiner Multi-Source Integration
=======
# SECTION 4 — SignalCombiner Multi-Source Integration
>>>>>>> origin/main
# ===========================================================================

class TestMultiSourceCombiner:
    """Test combiner with all Phase 1 signal sources."""

    def test_five_source_combine(self):
        """All 5 sources produce a valid composite signal."""
        combiner = SignalCombiner(
            sources=[
                SignalSource("zscore", weight=0.40),
                SignalSource("momentum", weight=0.20),
                SignalSource("ou", weight=0.20),
                SignalSource("vol_regime", weight=0.10),
                SignalSource("cross_sectional", weight=0.10),
            ],
            entry_threshold=0.35,
        )
        scores = {
            "zscore": -0.8,
            "momentum": -0.5,
            "ou": -0.7,
            "vol_regime": -0.3,
            "cross_sectional": -0.4,
        }
        result = combiner.combine(scores)
        assert result.direction == "short"
        assert result.composite_score < -0.35
        assert result.confidence == 1.0

    def test_conflicting_signals(self):
        """Conflicting signals dampen composite score."""
        combiner = SignalCombiner(
            sources=[
                SignalSource("zscore", weight=0.40),
                SignalSource("ou", weight=0.20),
                SignalSource("cross_sectional", weight=0.20),
                SignalSource("vol_regime", weight=0.20),
            ],
            entry_threshold=0.5,
        )
        scores = {
            "zscore": 0.9,           # strong long
            "ou": 0.8,               # confirms
            "cross_sectional": -0.9,  # contradicts
            "vol_regime": -0.5,       # unfavourable
        }
        result = combiner.combine(scores)
        # Composite should be dampened by contradicting signals
        assert abs(result.composite_score) < 0.9

    def test_partial_sources(self):
        """Combiner works with subset of sources."""
        combiner = SignalCombiner(
            sources=[
                SignalSource("zscore", weight=0.40),
                SignalSource("ou", weight=0.30),
                SignalSource("vol_regime", weight=0.30),
            ],
            entry_threshold=0.35,
        )
        # Only provide zscore
        result = combiner.combine({"zscore": -0.8})
        assert result.direction in ("short", "none")
        assert result.confidence < 1.0

    def test_all_agree_long(self):
        """All sources agree on long direction."""
        combiner = SignalCombiner(
            sources=[
                SignalSource("zscore", weight=0.40),
                SignalSource("ou", weight=0.20),
                SignalSource("vol_regime", weight=0.20),
                SignalSource("cross_sectional", weight=0.20),
            ],
            entry_threshold=0.35,
        )
        scores = {
            "zscore": 0.8,
            "ou": 0.7,
            "vol_regime": 0.5,
            "cross_sectional": 0.6,
        }
        result = combiner.combine(scores)
        assert result.direction == "long"
        assert result.composite_score > 0.5
