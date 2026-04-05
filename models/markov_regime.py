"""
Markov-Switching Regime Detector ÔÇô Phase 3 (addresses audit ┬º2.6).

Problem
-------
The original ``RegimeDetector`` classifies volatility into LOW/NORMAL/HIGH
using **fixed percentile thresholds** on a rolling window.  This is a
classification, not a detection model ÔÇô it cannot estimate:

  * Transition probabilities between regimes.
  * The probability of *being in* a given regime at any point (filtering).
  * Expected regime duration.

A proper Hidden Markov Model (HMM) achieves all of the above while still
being fast enough for bar-by-bar execution.

Solution
--------
A 3-state Gaussian HMM fitted on rolling volatility (or returns) via
the BaumÔÇôWelch (EM) algorithm.  States are ordered by their emission
mean Ôåô mapped to LOW / NORMAL / HIGH.

The detector maintains the **same public API** as ``RegimeDetector``
(``update()``, ``get_position_multiplier()``, ``get_entry_threshold_multiplier()``,
``get_exit_threshold_multiplier()``), so it is a **drop-in replacement**.

Fitting is done in two modes:

1. **Warm-up** (first ``min_fit_obs`` bars): Accumulates observations,
   then fits the HMM once enough data is available.
2. **Online** (subsequent bars): Runs Viterbi/forward on the latest
   observation using the already-fitted parameters.  The model can
   optionally **refit** every ``refit_interval`` bars for adaptivity.

Dependencies: ``hmmlearn`` (pip install hmmlearn).  Falls back to the
legacy percentile detector if ``hmmlearn`` is not installed.

DECISION 2026-03-22 (C-09): MarkovRegimeDetector is RETAINED as an optional
drop-in replacement for RegimeDetector, gated by
``signal_combiner.use_markov_regime`` (default: False).
It is NOT dead code — it is disabled by default in prod for stability and
enabled explicitly via config for research/live A/B.
Tests: tests/phase4/test_phase4_signals.py (concordance, hmm_available).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
from structlog import get_logger

# Re-use the canonical types from the existing detector
from models.regime_detector import RegimeState, VolatilityRegime

logger = get_logger(__name__)

# ÔôÇÔôÇ Optional HMM import ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
GaussianHMM: Any = None  # pre-init; overwritten if hmmlearn is available
try:
    from hmmlearn.hmm import GaussianHMM  # pyright: ignore[reportMissingTypeStubs]

    _HMM_AVAILABLE = True
except ImportError:
    _HMM_AVAILABLE = False
    logger.warning(
        "hmmlearn_not_installed",
        msg="pip install hmmlearn for Markov regime detection; falling back to percentile detector",
    )


@dataclass
class MarkovRegimeConfig:
    """Tuning knobs for the Markov-switching detector."""

    n_states: int = 3
    """Number of hidden states (LOW / NORMAL / HIGH)."""

    min_fit_obs: int = 100
    """Minimum observations before the first HMM fit."""

    refit_interval: int = 50
    """Re-fit the HMM every N bars to adapt to structural changes.
    Set to 0 to disable periodic refitting."""

    lookback_window: int = 252
    """Maximum window of observations used for fitting (rolling)."""

    covariance_type: str = "full"
    """HMM covariance type: 'full', 'diag', 'spherical', 'tied'."""

    n_iter: int = 50
    """Max EM iterations per fit."""

    # Fallback percentile thresholds (used before HMM fit or if hmmlearn missing)
    low_percentile: float = 0.33
    high_percentile: float = 0.67

    min_regime_duration: int = 1
    """Minimum bars in a regime before allowing transition."""


class MarkovRegimeDetector:
    """
    HMM-based regime detector ÔÇô drop-in replacement for ``RegimeDetector``.

    Public API matches ``RegimeDetector`` exactly so that existing code
    (``PairTradingStrategy``, ``AdaptiveThresholdCalculator``) works
    without changes.
    """

    def __init__(
        self,
        lookback_window: int = 252,
        low_percentile: float = 0.33,
        high_percentile: float = 0.67,
        min_regime_duration: int = 1,
        config: MarkovRegimeConfig | None = None,
        **_kwargs: Any,
    ):
        cfg = config or MarkovRegimeConfig(
            lookback_window=lookback_window,
            low_percentile=low_percentile,
            high_percentile=high_percentile,
            min_regime_duration=min_regime_duration,
        )
        self.config = cfg

        # Accept and ignore extra kwargs that the old constructor had
        # (e.g. use_log_returns, instant_transition_percentile)
        self.lookback_window = cfg.lookback_window
        self.low_percentile = cfg.low_percentile
        self.high_percentile = cfg.high_percentile
        self.min_regime_duration = cfg.min_regime_duration

        # Observation buffer
        self._obs: deque = deque(maxlen=cfg.lookback_window)
        self._spread_history: deque = deque(maxlen=cfg.lookback_window)

        # HMM model (fitted lazily)
        self._model: Any | None = None  # GaussianHMM when fitted
        self._state_order: np.ndarray | None = None  # maps HMM state Ôåô regime idx
        self._is_fitted: bool = False
        self._bars_since_fit: int = 0

        # Regime tracking (same fields as RegimeDetector)
        self.current_regime = VolatilityRegime.NORMAL
        self.current_regime_start_bar = 0
        self.bars_processed = 0
        self.regime_transitions: list[tuple[int, VolatilityRegime, VolatilityRegime]] = []
        self.regime_change_signals: list[str] = []
        self.instant_transition_count: int = 0
        self.state_history: list[RegimeState] = []
        self.last_state: RegimeState | None = None
        self.volatility_history: deque = deque(maxlen=cfg.lookback_window)

        # Transition matrix (populated after fit)
        self.transition_matrix: np.ndarray | None = None

        logger.info(
            "markov_regime_detector_initialized",
            n_states=cfg.n_states,
            min_fit_obs=cfg.min_fit_obs,
            refit_interval=cfg.refit_interval,
            hmm_available=_HMM_AVAILABLE,
        )

    # ÔôÇÔôÇ Core public API (matches RegimeDetector) ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

    def update(
        self,
        spread: float,
        returns: float | None = None,
        date: datetime | None = None,
    ) -> RegimeState:
        """Update with a new bar and return the current regime state."""
        timestamp = date or datetime.now()

        # Compute volatility proxy (absolute return)
        if returns is None:
            if len(self._spread_history) > 0:
                prev = self._spread_history[-1]
                returns = (spread - prev) / max(abs(prev), 1e-10)
            else:
                returns = 0.0

        returns_val: float = float(returns) if returns is not None else 0.0
        self._spread_history.append(spread)
        # Use signed returns — HMM can distinguish bull/bear/sideways regimes
        self._obs.append(returns_val)
        self.volatility_history.append(abs(returns_val))

        # ÔôÇÔôÇ Attempt HMM fit / refit ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
        n = len(self._obs)
        if _HMM_AVAILABLE and n >= self.config.min_fit_obs:
            need_fit = not self._is_fitted or (
                self.config.refit_interval > 0 and self._bars_since_fit >= self.config.refit_interval
            )
            if need_fit:
                self._fit_hmm()

        # ÔôÇÔôÇ Determine regime ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ
        new_regime = self._predict_regime()

        # Transition logic
        if new_regime != self.current_regime:
            bars_in = self.bars_processed - self.current_regime_start_bar
            if bars_in >= self.min_regime_duration:
                self.regime_transitions.append((self.bars_processed, self.current_regime, new_regime))
                self.regime_change_signals.append(
                    f"Transition at bar {self.bars_processed}: {self.current_regime.value} -> {new_regime.value}"
                )
                self.current_regime = new_regime
                self.current_regime_start_bar = self.bars_processed

        # Build state
        state = self._build_state(timestamp)
        self.state_history.append(state)
        self.last_state = state
        self.bars_processed += 1
        self._bars_since_fit += 1

        return state

    def get_position_multiplier(self, regime: VolatilityRegime | None = None) -> float:
        r = regime or self.current_regime
        return 0.5 if r == VolatilityRegime.HIGH else 1.0

    def get_entry_threshold_multiplier(self, regime: VolatilityRegime | None = None) -> float:
        r = regime or self.current_regime
        return 1.2 if r == VolatilityRegime.HIGH else 1.0

    def get_exit_threshold_multiplier(self, regime: VolatilityRegime | None = None) -> float:
        r = regime or self.current_regime
        return 0.9 if r == VolatilityRegime.LOW else 1.0

    def get_regime_stats(self) -> dict:
        counts = {VolatilityRegime.LOW: 0, VolatilityRegime.NORMAL: 0, VolatilityRegime.HIGH: 0}
        vols = []
        for s in self.state_history:
            counts[s.regime] += 1
            vols.append(s.volatility)
        return {
            "total_bars": len(self.state_history),
            "regime_transitions": len(self.regime_transitions),
            "current_regime": self.current_regime.value,
            "regime_duration_bars": self.state_history[-1].regime_duration_bars if self.state_history else 0,
            "low_regime_bars": counts[VolatilityRegime.LOW],
            "normal_regime_bars": counts[VolatilityRegime.NORMAL],
            "high_regime_bars": counts[VolatilityRegime.HIGH],
            "avg_volatility": float(np.mean(vols)) if vols else 0.0,
            "max_volatility": float(np.max(vols)) if vols else 0.0,
            "min_volatility": float(np.min(vols)) if vols else 0.0,
            "current_volatility": self.state_history[-1].volatility if self.state_history else 0.0,
            "transition_matrix": self.transition_matrix.tolist() if self.transition_matrix is not None else None,
            "is_hmm_fitted": self._is_fitted,
        }

    def reset(self):
        self._obs.clear()
        self._spread_history.clear()
        self.volatility_history.clear()
        self._model = None
        self._state_order = None
        self._is_fitted = False
        self._bars_since_fit = 0
        self.current_regime = VolatilityRegime.NORMAL
        self.current_regime_start_bar = 0
        self.bars_processed = 0
        self.regime_transitions.clear()
        self.regime_change_signals.clear()
        self.state_history.clear()
        self.last_state = None
        self.instant_transition_count = 0
        self.transition_matrix = None

    # ÔôÇÔôÇ HMM internals ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

    def _fit_hmm(self) -> None:
        """Fit the GaussianHMM on the current observation buffer."""
        try:
            obs = np.array(list(self._obs), dtype=np.float64).reshape(-1, 1)
            n = len(obs)

            model = GaussianHMM(
                n_components=self.config.n_states,
                covariance_type=self.config.covariance_type,
                n_iter=self.config.n_iter,
                random_state=42,
            )
            model.fit(obs)

            # Map states by ascending emission mean:
            # lowest mean ÔåÆ LOW/bearish, middle ÔåÆ NORMAL, highest ÔåÆ HIGH/bullish
            # Works with signed returns: negative mean = bearish regime
            means = model.means_.flatten()
            self._state_order = np.argsort(means)  # index 0=lowest mean = LOW
            self._model = model
            self._is_fitted = True
            self._bars_since_fit = 0
            self.transition_matrix = model.transmat_.copy()

            logger.info(
                "markov_hmm_fitted",
                n_obs=n,
                means=[float(means[i]) for i in self._state_order],
                converged=model.monitor_.converged,
            )
        except Exception as e:
            logger.warning("markov_hmm_fit_failed", error=str(e))

    def _predict_regime(self) -> VolatilityRegime:
        """Predict the current regime for the latest observation."""
        if self._is_fitted and self._model is not None:
            return self._predict_hmm()
        return self._fallback_percentile()

    def _predict_hmm(self) -> VolatilityRegime:
        """Use the fitted HMM to predict the regime."""
        try:
            # Use last N observations for prediction context
            context_len = min(len(self._obs), 20)
            obs = np.array(list(self._obs))[-context_len:].reshape(-1, 1)
            assert self._model is not None
            _model = self._model
            hidden_states = _model.predict(obs)
            raw_state = hidden_states[-1]  # latest

            # Map to ordered regime
            regime_idx = int(np.where(self._state_order == raw_state)[0][0])
            regime_map = {0: VolatilityRegime.LOW, 1: VolatilityRegime.NORMAL, 2: VolatilityRegime.HIGH}
            return regime_map.get(regime_idx, VolatilityRegime.NORMAL)
        except Exception:
            return self._fallback_percentile()

    def _fallback_percentile(self) -> VolatilityRegime:
        """Legacy percentile-based classification as fallback."""
        if len(self._obs) < 2:
            return VolatilityRegime.NORMAL
        arr = np.array(list(self._obs))
        current = arr[-1]
        lo = np.percentile(arr, self.low_percentile * 100)
        hi = np.percentile(arr, self.high_percentile * 100)
        if current <= lo:
            return VolatilityRegime.LOW
        elif current >= hi:
            return VolatilityRegime.HIGH
        return VolatilityRegime.NORMAL

    def _build_state(self, timestamp: datetime) -> RegimeState:
        arr = np.array(list(self._obs))
        current_vol = float(arr[-1]) if len(arr) else 0.0
        rolling_mean = float(np.mean(arr)) if len(arr) else 0.0
        rolling_std = float(np.std(arr)) if len(arr) else 0.0
        percentile = float((arr < current_vol).sum() / max(len(arr), 1) * 100)

        # Transition probability from HMM matrix if available
        if self.transition_matrix is not None and self._state_order is not None:
            regime_to_idx = {VolatilityRegime.LOW: 0, VolatilityRegime.NORMAL: 1, VolatilityRegime.HIGH: 2}
            r_idx = regime_to_idx.get(self.current_regime, 1)
            raw = self._state_order[r_idx]
            # P(leaving current state) = 1 - P(staying)
            transition_prob = float(1.0 - float(self.transition_matrix[raw, raw]))
        else:
            transition_prob = rolling_std / (rolling_mean + 1e-10) if rolling_mean > 0 else 0.0

        confidence = self._calc_confidence(arr, current_vol)

        return RegimeState(
            regime=self.current_regime,
            volatility=current_vol,
            percentile=percentile,
            rolling_mean=rolling_mean,
            rolling_std=rolling_std,
            regime_duration_bars=self.bars_processed - self.current_regime_start_bar,
            timestamp=timestamp,
            transition_probability=min(1.0, transition_prob),
            confidence=confidence,
            volatility_history=list(arr[-5:]) if len(arr) else [],
        )

    def _calc_confidence(self, arr: np.ndarray, current_vol: float) -> float:
        if len(arr) < 2:
            return 0.5
        lo = np.percentile(arr, self.low_percentile * 100)
        hi = np.percentile(arr, self.high_percentile * 100)
        rng = hi - lo
        if rng < 1e-10:
            return 0.8
        if self.current_regime == VolatilityRegime.LOW:
            return float(max(0, min(1, 1.0 - (current_vol - lo) / rng)))
        elif self.current_regime == VolatilityRegime.HIGH:
            return float(max(0, min(1, 1.0 - (hi - current_vol) / rng)))
        mid = (lo + hi) / 2
        return float(max(0, min(1, 1.0 - abs(current_vol - mid) / (rng / 2))))

    # ÔôÇÔôÇ Extra: regime-specific insights ÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇÔôÇ

    def get_expected_regime_duration(self) -> float | None:
        """Expected bars remaining in the current regime (from transition matrix)."""
        if self.transition_matrix is None or self._state_order is None:
            return None
        regime_to_idx = {VolatilityRegime.LOW: 0, VolatilityRegime.NORMAL: 1, VolatilityRegime.HIGH: 2}
        r_idx = regime_to_idx.get(self.current_regime, 1)
        raw = self._state_order[r_idx]
        p_stay = float(self.transition_matrix[raw, raw])
        if p_stay >= 1.0:
            return float("inf")
        return 1.0 / (1.0 - p_stay)

    def get_regime_probabilities(self) -> dict[str, float] | None:
        """Stationary distribution: long-run probability of each regime."""
        if self.transition_matrix is None or self._state_order is None:
            return None
        try:
            # Solve ¤ÇT = ¤Ç with ╬ú¤Ç = 1
            A = self.transition_matrix.T - np.eye(self.config.n_states)
            A[-1, :] = 1.0
            b = np.zeros(self.config.n_states)
            b[-1] = 1.0
            pi = np.linalg.solve(A, b)
            regimes = [VolatilityRegime.LOW, VolatilityRegime.NORMAL, VolatilityRegime.HIGH]
            return {regimes[i].value: float(pi[self._state_order[i]]) for i in range(self.config.n_states)}
        except Exception:
            return None


__all__ = [
    "MarkovRegimeConfig",
    "MarkovRegimeDetector",
]
