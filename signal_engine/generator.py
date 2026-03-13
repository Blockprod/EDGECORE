"""
Signal Generator — Unified signal generation pipeline.

**This is the single entry point for all signal generation.**

Pipeline:
    Market Data → Spread Model → Z-Score → Adaptive Threshold
    → Regime Filter → Stationarity Check → Signal

Both backtesting and live trading call ``SignalGenerator.generate()``
to ensure zero divergence between back-tested and live behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
from structlog import get_logger

from models.spread import SpreadModel
from models.stationarity_monitor import StationarityMonitor
from models.regime_detector import RegimeDetector, VolatilityRegime
from signal_engine.zscore import ZScoreCalculator
from signal_engine.adaptive import AdaptiveThresholdEngine
from signal_engine.momentum import MomentumOverlay

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Signal data class
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    """
    Typed trading signal emitted by the signal engine.

    Attributes:
        pair_key: Pair identifier (e.g. ``AAPL_MSFT``).
        side: ``"long"`` | ``"short"`` | ``"exit"``.
        strength: Signal confidence 0.0–1.0.
        z_score: Current z-score that triggered the signal.
        entry_threshold: Threshold used for entry decision.
        exit_threshold: Threshold used for exit decision.
        regime: Volatility regime at signal time.
        reason: Human-readable reason string.
        timestamp: Signal generation time.
    """
    pair_key: str
    side: str
    strength: float
    z_score: float = 0.0
    entry_threshold: float = 2.0
    exit_threshold: float = 0.0
    regime: VolatilityRegime = VolatilityRegime.NORMAL
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class SignalGenerator:
    """
    Unified signal generation pipeline.

    Composes:
        1. SpreadModel (hedge ratio, spread computation)
        2. ZScoreCalculator (rolling z-score)
        3. AdaptiveThresholdEngine (regime-aware thresholds)
        4. StationarityMonitor (rolling ADF guard)
        5. RegimeDetector (volatility regime classification)

    Usage::

        gen = SignalGenerator()
        signals = gen.generate(
            market_data=prices_df,
            active_pairs=[("AAPL", "MSFT", 0.01, 25)],
            active_positions={"AAPL_MSFT": {...}},
        )
    """

    def __init__(
        self,
        zscore_calc: Optional[ZScoreCalculator] = None,
        threshold_engine: Optional[AdaptiveThresholdEngine] = None,
        regime_detector: Optional[RegimeDetector] = None,
        stationarity_monitor: Optional[StationarityMonitor] = None,
        momentum_overlay: Optional[MomentumOverlay] = None,
    ):
        self.zscore_calc = zscore_calc or ZScoreCalculator()
        self.threshold_engine = threshold_engine or AdaptiveThresholdEngine()
        self.regime_detector = regime_detector or RegimeDetector()
        self.stationarity_monitor = stationarity_monitor or StationarityMonitor()
        self.momentum_overlay = momentum_overlay  # None = disabled

        # Internal state
        self._spread_models: Dict[str, SpreadModel] = {}
        self._spreads: Dict[str, pd.Series] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        market_data: pd.DataFrame,
        active_pairs: List[Tuple[str, str, float, float]],
        active_positions: Optional[Dict[str, dict]] = None,
    ) -> List[Signal]:
        """
        Generate trading signals for all active pairs.

        Args:
            market_data: Price DataFrame (columns = symbols).
            active_pairs: List of (sym1, sym2, pvalue, half_life) tuples.
            active_positions: Dict of currently held positions keyed by
                pair_key.  Used to determine exit signals.

        Returns:
            List of Signal objects.
        """
        if active_positions is None:
            active_positions = {}

        signals: List[Signal] = []

        for sym1, sym2, _pval, hl in active_pairs:
            pair_key = f"{sym1}_{sym2}"

            try:
                sig = self._process_pair(
                    pair_key, sym1, sym2, hl,
                    market_data, active_positions,
                )
                if sig is not None:
                    signals.append(sig)
            except Exception as exc:
                logger.error(
                    "signal_generation_error",
                    pair=pair_key,
                    error=str(exc),
                )
                continue

        return signals

    # ------------------------------------------------------------------
    # Internal: per-pair processing
    # ------------------------------------------------------------------

    def _process_pair(
        self,
        pair_key: str,
        sym1: str,
        sym2: str,
        half_life: float,
        market_data: pd.DataFrame,
        active_positions: Dict[str, dict],
    ) -> Optional[Signal]:
        """Run the full signal pipeline for a single pair."""
        y = market_data[sym1]
        x = market_data[sym2]

        # 1. Re-use existing spread model to preserve Kalman state;
        #    only create a new one if the pair is seen for the first time.
        if pair_key in self._spread_models:
            model = self._spread_models[pair_key]
            model.update(y, x)
        else:
            model = SpreadModel(y, x, pair_key=pair_key)
            self._spread_models[pair_key] = model

        # 2. Compute spread
        spread = model.compute_spread(y, x)
        self._spreads[pair_key] = spread

        # 3. Stationarity check
        is_stationary, adf_pval = self.stationarity_monitor.check(spread)
        if not is_stationary:
            # If holding a position in a non-stationary spread → exit
            if pair_key in active_positions:
                return Signal(
                    pair_key=pair_key,
                    side="exit",
                    strength=1.0,
                    reason=f"Stationarity lost (ADF p={adf_pval:.3f})",
                )
            return None

        # 4. Z-score
        z_series = self.zscore_calc.compute(spread, half_life=half_life)
        current_z = float(z_series.iloc[-1])

        # 5. Regime detection
        regime_state = self.regime_detector.update(
            spread=float(spread.iloc[-1]),
        )
        regime = regime_state.regime

        # 6. Adaptive thresholds
        thresh = self.threshold_engine.get_thresholds(
            spread=spread,
            half_life=half_life,
            regime=regime,
        )

        # 7. Signal logic
        in_position = pair_key in active_positions

        # EXIT signal (mean reversion reached)
        if in_position and abs(current_z) <= thresh.exit_threshold:
            return Signal(
                pair_key=pair_key,
                side="exit",
                strength=1.0,
                z_score=current_z,
                entry_threshold=thresh.entry_threshold,
                exit_threshold=thresh.exit_threshold,
                regime=regime,
                reason=f"Mean reversion at Z={current_z:.2f}",
            )

        # ENTRY signals (only if not already in position)
        if not in_position:
            strength = min(abs(current_z) / 3.0, 1.0)

            if current_z > thresh.entry_threshold:
                side = "short"
                # Apply momentum overlay if available
                if self.momentum_overlay is not None:
                    m_result = self.momentum_overlay.adjust_signal_strength(
                        side=side,
                        raw_strength=strength,
                        prices_a=y,
                        prices_b=x,
                    )
                    strength = m_result.adjusted_strength
                    mom_tag = f" [mom:{'C' if m_result.confirms_signal else 'X'}]"
                else:
                    mom_tag = ""

                return Signal(
                    pair_key=pair_key,
                    side=side,
                    strength=strength,
                    z_score=current_z,
                    entry_threshold=thresh.entry_threshold,
                    exit_threshold=thresh.exit_threshold,
                    regime=regime,
                    reason=f"Z={current_z:.2f} > {thresh.entry_threshold:.2f}{mom_tag}",
                )

            if current_z < -thresh.entry_threshold:
                side = "long"
                # Apply momentum overlay if available
                if self.momentum_overlay is not None:
                    m_result = self.momentum_overlay.adjust_signal_strength(
                        side=side,
                        raw_strength=strength,
                        prices_a=y,
                        prices_b=x,
                    )
                    strength = m_result.adjusted_strength
                    mom_tag = f" [mom:{'C' if m_result.confirms_signal else 'X'}]"
                else:
                    mom_tag = ""

                return Signal(
                    pair_key=pair_key,
                    side=side,
                    strength=strength,
                    z_score=current_z,
                    entry_threshold=thresh.entry_threshold,
                    exit_threshold=thresh.exit_threshold,
                    regime=regime,
                    reason=f"Z={current_z:.2f} < -{thresh.entry_threshold:.2f}{mom_tag}",
                )

        return None

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_spread(self, pair_key: str) -> Optional[pd.Series]:
        """Return the latest spread series for a pair."""
        return self._spreads.get(pair_key)

    def get_spread_model(self, pair_key: str) -> Optional[SpreadModel]:
        """Return the spread model for a pair."""
        return self._spread_models.get(pair_key)

    @property
    def current_regime(self) -> VolatilityRegime:
        """Return the current volatility regime."""
        return self.regime_detector.current_regime
