"""
Regime Change Detection using Markov Switching Model.

Detects market volatility regimes (Low/Normal/High) to improve trade signal quality
and position sizing. Tracks rolling volatility percentiles and state transitions.

Example:
    detector = RegimeDetector(
        lookback_window=20,
        low_percentile=0.33,
        high_percentile=0.67,
        min_regime_duration=1
    )

    # Feed in daily returns or spreads
    for date, returns in historical_data:
        regime_state = detector.update(date=date, spread=spread_values[date])
        if regime_state.regime == VolatilityRegime.HIGH:
            # Reduce position sizing or skip trades
            position_multiplier = 0.5
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import numpy as np


class VolatilityRegime(Enum):
    """Market volatility regime classification."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass
class RegimeState:
    """Current market regime state and metrics."""

    regime: VolatilityRegime
    """Current volatility regime: LOW, NORMAL, or HIGH"""

    volatility: float
    """Current rolling volatility (daily)"""

    percentile: float
    """Current volatility percentile (0-100)"""

    rolling_mean: float
    """Mean volatility in lookback window"""

    rolling_std: float
    """Std dev of volatility in lookback window"""

    regime_duration_bars: int
    """Number of bars in current regime"""

    timestamp: datetime
    """Time of regime state update"""

    transition_probability: float = 0.0
    """Probability of regime transition (0-1)"""

    confidence: float = 1.0
    """Confidence in current regime classification (0-1)"""

    volatility_history: list[float] = field(default_factory=list)
    """Recent volatility values for trend analysis"""


class RegimeDetector:
    """
    Detects market volatility regimes using rolling windows and percentile thresholds.

    Classifies price action into three regimes based on rolling volatility:
    - LOW: Calm markets, tight spreads, fewer opportunities
    - NORMAL: Standard volatility, good trading conditions
    - HIGH: Volatile markets, wider spreads, higher execution risk

    Uses Markov-style state persistence to reduce false signals and distinguish
    genuine regime changes from transient volatility spikes.

    Attributes:
        lookback_window: Number of periods for rolling volatility window
        low_percentile: Threshold below which regime is LOW (default: 0.33 = 33rd percentile)
        high_percentile: Threshold above which regime is HIGH (default: 0.67 = 67th percentile)
        min_regime_duration: Minimum bars to stay in regime before transition
        use_log_returns: Whether to use log returns vs simple returns for vol calc
    """

    def __init__(
        self,
        lookback_window: int = 20,
        low_percentile: float = 0.33,
        high_percentile: float = 0.67,
        min_regime_duration: int = 1,
        use_log_returns: bool = False,
        instant_transition_percentile: float = 99.0,
        adaptive_window: bool = False,
        min_window: int = 20,
        max_window: int = 120,
    ):
        """
        Initialize regime detector.

        Args:
            lookback_window: Number of bars for rolling volatility (default 20)
            low_percentile: Volatility percentile threshold for LOW regime (default 0.33)
            high_percentile: Volatility percentile threshold for HIGH regime (default 0.67)
            min_regime_duration: Minimum bars before regime transition (default 1)
            use_log_returns: Use log returns instead of simple returns (default False)
            instant_transition_percentile: Vol spike percentile for instant transition (default 99.0)
            adaptive_window: When True, vary the effective lookback between min_window and
                max_window based on recent realized volatility. High vol → shorter window
                (fast response); low vol → longer window (stable estimates). (default False)
            min_window: Minimum effective window when adaptive_window=True (default 20)
            max_window: Maximum effective window when adaptive_window=True (default 120)
        """
        self.lookback_window = lookback_window
        self.low_percentile = low_percentile
        self.high_percentile = high_percentile
        self.min_regime_duration = min_regime_duration
        self.use_log_returns = use_log_returns
        self.instant_transition_percentile = instant_transition_percentile

        # Adaptive window configuration (C-09)
        self.adaptive_window = adaptive_window
        self.min_window = min_window
        self.max_window = max_window
        self.current_effective_window: int = lookback_window

        # Volatility tracking — deque sized for the maximum history we may ever need
        _maxlen = max(max_window, lookback_window) if adaptive_window else lookback_window
        self.volatility_history: deque = deque(maxlen=_maxlen)
        self.spread_history: deque = deque(maxlen=_maxlen)

        # Regime tracking
        self.current_regime = VolatilityRegime.NORMAL
        self.current_regime_start_bar = 0
        self.bars_processed = 0
        self.regime_transitions: list[tuple[int, VolatilityRegime, VolatilityRegime]] = []
        self.regime_change_signals: list[str] = []

        # Instant transition tracking
        self.instant_transition_count: int = 0

        # State history
        self.state_history: list[RegimeState] = []
        self.last_state: RegimeState | None = None

    def update(self, spread: float, returns: float | None = None, date: datetime | None = None) -> RegimeState:
        """
        Update regime detector with new price/spread data.

        Args:
            spread: Current spread value (or price change)
            returns: Optional: Daily log/simple returns (auto-calculated if not provided)
            date: Optional: Timestamp for state

        Returns:
            RegimeState object with current regime and metrics
        """
        timestamp = date or datetime.now()

        # Calculate returns from spread changes if not provided
        if returns is None:
            if len(self.spread_history) > 0:
                prev_spread = self.spread_history[-1]
                # Avoid division by zero; use absolute change if prev spreads near zero
                if abs(prev_spread) > 1e-10:
                    returns = (
                        np.log(abs(spread / prev_spread))
                        if self.use_log_returns
                        else (spread - prev_spread) / abs(prev_spread)
                    )
                else:
                    returns = spread - prev_spread
            else:
                returns = 0.0

        # Store spread
        self.spread_history.append(spread)

        # Calculate volatility (rolling std of returns)
        if len(self.spread_history) > 1:
            # Calculate returns for all adjacent pairs in window
            recent_returns = []
            for i in range(len(self.spread_history) - 1):
                prev_val = self.spread_history[i]
                curr_val = self.spread_history[i + 1]

                if abs(prev_val) > 1e-10:
                    ret = (
                        np.log(abs(curr_val / prev_val))
                        if self.use_log_returns
                        else (curr_val - prev_val) / abs(prev_val)
                    )
                else:
                    ret = curr_val - prev_val
                recent_returns.append(ret)

            volatility = float(np.std(recent_returns)) if recent_returns else 0.0
        else:
            volatility = abs(returns) if returns else 0.0

        self.volatility_history.append(volatility)

        # Determine regime based on percentiles
        new_regime = self._determine_regime()

        # Check for regime transition (respect min duration, unless instant transition)
        if new_regime != self.current_regime:
            bars_in_regime = self.bars_processed - self.current_regime_start_bar

            # Check for instant transition: vol spike > Nth percentile
            instant = self._check_instant_transition()

            if instant or bars_in_regime >= self.min_regime_duration:
                # Transition allowed
                self.regime_transitions.append((self.bars_processed, self.current_regime, new_regime))
                transition_type = "INSTANT" if instant else "normal"
                self.regime_change_signals.append(
                    f"Transition at bar {self.bars_processed}: "
                    f"{self.current_regime.value} -> {new_regime.value} ({transition_type})"
                )
                if instant:
                    self.instant_transition_count += 1
                self.current_regime = new_regime
                self.current_regime_start_bar = self.bars_processed

        # Build state object
        state = self._build_regime_state(timestamp)
        self.state_history.append(state)
        self.last_state = state

        self.bars_processed += 1

        return state

    def _check_instant_transition(self) -> bool:
        """
        Check if current volatility warrants an instant regime transition,
        bypassing the min_regime_duration check.

        Returns True if current volatility exceeds the instant_transition_percentile
        (default 99th percentile) of historical volatility.
        """
        if len(self.volatility_history) < 5:
            return False

        vol_array = np.array(list(self.volatility_history))
        current_vol = vol_array[-1]
        threshold = np.percentile(vol_array, self.instant_transition_percentile)

        return bool(current_vol >= threshold)

    def _compute_adaptive_window(self) -> int:
        """
        Compute effective lookback window based on recent realized volatility.

        High vol → min_window (respond quickly to fast-moving regimes).
        Low vol  → max_window (stable estimates, reduce noise).

        Returns:
            Effective window in [min_window, max_window].
        """
        n = len(self.volatility_history)
        if n < self.min_window:
            return max(2, n)

        vol_array = np.array(list(self.volatility_history))

        # Short-term realized vol: mean of last 5 bars (or all available)
        short_lookback = min(5, n)
        recent_vol = float(np.mean(vol_array[-short_lookback:]))

        # Percentile rank of recent vol within full history (0=lowest, 1=highest)
        vol_percentile = float((vol_array < recent_vol).sum() / n)

        # Linear mapping: high percentile → min_window; low percentile → max_window
        effective = int(round(self.max_window - (self.max_window - self.min_window) * vol_percentile))
        return max(self.min_window, min(self.max_window, effective))

    def _determine_regime(self) -> VolatilityRegime:
        """Determine regime based on current volatility and historical percentiles."""
        if len(self.volatility_history) < 2:
            return VolatilityRegime.NORMAL

        vol_array = np.array(list(self.volatility_history))

        if self.adaptive_window:
            effective = self._compute_adaptive_window()
            self.current_effective_window = effective
            vol_array = vol_array[-effective:]

        current_vol = vol_array[-1]

        # Calculate percentile thresholds
        low_threshold = np.percentile(vol_array, self.low_percentile * 100)
        high_threshold = np.percentile(vol_array, self.high_percentile * 100)

        # Classify regime
        if current_vol <= low_threshold:
            return VolatilityRegime.LOW
        elif current_vol >= high_threshold:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.NORMAL

    def _build_regime_state(self, timestamp: datetime) -> RegimeState:
        """Build detailed regime state object."""
        vol_array = np.array(list(self.volatility_history))

        if len(vol_array) > 0:
            rolling_mean = float(np.mean(vol_array))
            rolling_std = float(np.std(vol_array))
            current_vol = float(vol_array[-1])

            # Calculate percentile
            percentile = float((vol_array < current_vol).sum() / len(vol_array) * 100)
        else:
            rolling_mean = 0.0
            rolling_std = 0.0
            current_vol = 0.0
            percentile = 50.0

        # Calculate regime duration
        regime_duration = self.bars_processed - self.current_regime_start_bar

        # Calculate transition probability (higher vol variance = higher transition risk)
        if rolling_std > 0:
            transition_prob = min(1.0, rolling_std / (rolling_mean + 1e-10))
        else:
            transition_prob = 0.0

        # Calculate confidence (based on how far from threshold)
        confidence = self._calculate_confidence()

        return RegimeState(
            regime=self.current_regime,
            volatility=current_vol,
            percentile=percentile,
            rolling_mean=rolling_mean,
            rolling_std=rolling_std,
            regime_duration_bars=regime_duration,
            timestamp=timestamp,
            transition_probability=transition_prob,
            confidence=confidence,
            volatility_history=list(vol_array[-5:]) if len(vol_array) > 0 else [],
        )

    def _calculate_confidence(self) -> float:
        """Calculate confidence in current regime classification (0-1)."""
        if len(self.volatility_history) < 2:
            return 0.5

        vol_array = np.array(list(self.volatility_history))

        # Use the same adaptive slice as _determine_regime for consistency
        if self.adaptive_window:
            vol_array = vol_array[-self.current_effective_window :]

        current_vol = vol_array[-1]

        # Percentiles for regime boundaries
        low_threshold = np.percentile(vol_array, self.low_percentile * 100)
        high_threshold = np.percentile(vol_array, self.high_percentile * 100)

        vol_range = high_threshold - low_threshold
        if vol_range < 1e-10:
            return 0.8  # Very uniform volatility

        # Confidence inversely related to distance from thresholds
        if self.current_regime == VolatilityRegime.LOW:
            # Distance from low_threshold
            confidence = 1.0 - (current_vol - low_threshold) / (vol_range + 1e-10)
        elif self.current_regime == VolatilityRegime.HIGH:
            # Distance from high_threshold
            confidence = 1.0 - (high_threshold - current_vol) / (vol_range + 1e-10)
        else:  # NORMAL
            # Distance from center of range
            mid = (low_threshold + high_threshold) / 2
            confidence = 1.0 - abs(current_vol - mid) / (vol_range / 2 + 1e-10)

        return max(0.0, min(1.0, confidence))

    def get_position_multiplier(self, regime: VolatilityRegime | None = None) -> float:
        """
        Get position sizing multiplier based on regime volatility.

        Position sizing degrades gracefully in high volatility:
        - LOW regime: 1.0x (full size)
        - NORMAL regime: 1.0x (full size)
        - HIGH regime: 0.5x (half size due to wider spreads, slippage)

        Args:
            regime: Regime to check (uses current if None)

        Returns:
            Position multiplier (0.5 - 1.0)
        """
        check_regime = regime or self.current_regime

        if check_regime == VolatilityRegime.HIGH:
            return 0.5
        elif check_regime == VolatilityRegime.LOW:
            return 1.0
        else:  # NORMAL
            return 1.0

    def get_entry_threshold_multiplier(self, regime: VolatilityRegime | None = None) -> float:
        """
        Get z-score entry threshold multiplier based on regime.

        Entry thresholds increase in high volatility to filter out false signals:
        - LOW regime: 1.0x (standard thresholds)
        - NORMAL regime: 1.0x (standard thresholds)
        - HIGH regime: 1.2x (higher threshold = harder to enter = fewer false signals)

        Args:
            regime: Regime to check (uses current if None)

        Returns:
            Threshold multiplier (1.0 - 1.2)
        """
        check_regime = regime or self.current_regime

        if check_regime == VolatilityRegime.HIGH:
            return 1.2
        else:
            return 1.0

    def get_exit_threshold_multiplier(self, regime: VolatilityRegime | None = None) -> float:
        """
        Get z-score exit threshold multiplier based on regime.

        Exit thresholds decrease in low volatility (mean revert faster):
        - LOW regime: 0.9x (exit faster in calm markets)
        - NORMAL regime: 1.0x (standard thresholds)
        - HIGH regime: 1.0x (standard thresholds, let trends run)

        Args:
            regime: Regime to check (uses current if None)

        Returns:
            Threshold multiplier (0.9 - 1.0)
        """
        check_regime = regime or self.current_regime

        if check_regime == VolatilityRegime.LOW:
            return 0.9
        else:
            return 1.0

    def get_regime_stats(self) -> dict:
        """Get summary statistics of regime history and volatility patterns."""
        if not self.state_history:
            return {
                "total_bars": 0,
                "regime_transitions": 0,
                "current_regime": None,
                "low_regime_bars": 0,
                "normal_regime_bars": 0,
                "high_regime_bars": 0,
                "avg_volatility": 0.0,
                "max_volatility": 0.0,
                "min_volatility": 0.0,
            }

        # Count regime time
        regime_counts = {VolatilityRegime.LOW: 0, VolatilityRegime.NORMAL: 0, VolatilityRegime.HIGH: 0}

        volatilities = []
        for state in self.state_history:
            regime_counts[state.regime] += 1
            volatilities.append(state.volatility)

        return {
            "total_bars": len(self.state_history),
            "regime_transitions": len(self.regime_transitions),
            "current_regime": self.current_regime.value,
            "regime_duration_bars": self.state_history[-1].regime_duration_bars if self.state_history else 0,
            "low_regime_bars": regime_counts[VolatilityRegime.LOW],
            "normal_regime_bars": regime_counts[VolatilityRegime.NORMAL],
            "high_regime_bars": regime_counts[VolatilityRegime.HIGH],
            "avg_volatility": float(np.mean(volatilities)) if volatilities else 0.0,
            "max_volatility": float(np.max(volatilities)) if volatilities else 0.0,
            "min_volatility": float(np.min(volatilities)) if volatilities else 0.0,
            "current_volatility": self.state_history[-1].volatility if self.state_history else 0.0,
            "adaptive_window": self.adaptive_window,
            "current_effective_window": self.current_effective_window,
        }

    def reset(self):
        """Reset detector to initial state."""
        self.volatility_history.clear()
        self.spread_history.clear()
        self.current_regime = VolatilityRegime.NORMAL
        self.current_regime_start_bar = 0
        self.bars_processed = 0
        self.regime_transitions.clear()
        self.regime_change_signals.clear()
        self.state_history.clear()
        self.last_state = None
        self.instant_transition_count = 0
        self.current_effective_window = self.lookback_window


__all__ = ["VolatilityRegime", "RegimeState", "RegimeDetector"]
