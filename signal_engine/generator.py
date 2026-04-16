"""
Signal Generator ÔÇö Unified signal generation pipeline.

**This is the single entry point for all signal generation.**

Pipeline:
    Market Data ÔåÆ Spread Model ÔåÆ Z-Score ÔåÆ Adaptive Threshold
    ÔåÆ Regime Filter ÔåÆ Stationarity Check ÔåÆ Signal

Both backtesting and live trading call ``SignalGenerator.generate()``
to ensure zero divergence between back-tested and live behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd
from structlog import get_logger

from models.markov_regime import MarkovRegimeDetector
from models.regime_detector import RegimeDetector, VolatilityRegime
from models.spread import SpreadModel
from models.stationarity_monitor import StationarityMonitor
from models.structural_break import StructuralBreakDetector
from signal_engine.adaptive import AdaptiveThresholdEngine
from signal_engine.combiner import SignalCombiner, SignalSource
from signal_engine.momentum import MomentumOverlay
from signal_engine.zscore import ZScoreCalculator

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
        strength: Signal confidence 0.0ÔÇô1.0.
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
    exit_threshold: float = 0.5  # P1-06: was 0.0 — unreachable in float; aligned with config exit_z_score
    regime: VolatilityRegime = VolatilityRegime.NORMAL
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


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
        zscore_calc: ZScoreCalculator | None = None,
        threshold_engine: AdaptiveThresholdEngine | None = None,
        regime_detector: RegimeDetector | MarkovRegimeDetector | None = None,
        stationarity_monitor: StationarityMonitor | None = None,
        momentum_overlay: MomentumOverlay | None = None,
    ):
        self.zscore_calc = zscore_calc or ZScoreCalculator()
        from config.settings import get_settings as _get_settings_gen

        _settings = _get_settings_gen()
        # P1-06: read entry/exit z-scores from config so adaptive engine is aligned with global settings
        _strat = _settings.strategy
        self.threshold_engine = threshold_engine or AdaptiveThresholdEngine(
            base_entry=_strat.entry_z_score,
            base_exit=_strat.exit_z_score,
        )
        if regime_detector is not None:
            self.regime_detector: RegimeDetector | MarkovRegimeDetector = regime_detector
        else:
            if _settings.signal_combiner.use_markov_regime:
                self.regime_detector = MarkovRegimeDetector()
            else:
                self.regime_detector = RegimeDetector()
        self.stationarity_monitor = stationarity_monitor or StationarityMonitor()
        self.momentum_overlay = momentum_overlay  # None = disabled
        # P1-04: weighted combiner for documented formula composite = 0.70×z + 0.30×mom
        _scfg = _settings.signal_combiner
        self._signal_combiner = SignalCombiner(
            sources=[
                SignalSource("zscore", weight=_scfg.zscore_weight),
                SignalSource("momentum", weight=_scfg.momentum_weight),
            ],
            entry_threshold=_scfg.entry_threshold,
            exit_threshold=_scfg.exit_threshold,
        )

        # Internal state
        self._spread_models: dict[str, SpreadModel] = {}
        self._spreads: dict[str, pd.Series] = {}
        self._break_detectors: dict[str, StructuralBreakDetector] = {}
        # P2-01: cooldown counter per pair after structural break detection.
        # Key = pair_key, value = remaining bars to suppress signals.
        self._break_cooldown: dict[str, int] = {}
        self._current_disp_idx: float | None = None  # C-09: latest dispersion index

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        market_data: pd.DataFrame,
        active_pairs: list[tuple[str, str, float, float]],
        active_positions: dict[str, dict] | None = None,
    ) -> list[Signal]:
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

        # C-09: Evict spread models for pairs no longer active.
        # Prevents unbounded memory growth on long-running bots with pair rotation.
        active_keys = {f"{s1}_{s2}" for s1, s2, *_ in active_pairs}
        stale_keys = set(self._spread_models) - active_keys
        for k in stale_keys:
            del self._spread_models[k]
            self._spreads.pop(k, None)
            self._break_detectors.pop(k, None)
        if stale_keys:
            logger.info("spread_models_evicted", count=len(stale_keys))

        signals: list[Signal] = []

        # C-02: Dispersion filter — block new entries in highly correlated markets
        _block_entries = False
        _disp_idx: float | None = None
        try:
            from config.settings import get_settings as _get_settings_gen2

            _regime_cfg = _get_settings_gen2().regime
            if _regime_cfg.dispersion_filter_enabled and len(active_pairs) >= 3:
                _lookback = _regime_cfg.dispersion_filter_lookback
                _min_idx = _regime_cfg.dispersion_filter_min_index
                _syms = list({s for p in active_pairs for s in (p[0], p[1]) if s in market_data.columns})
                if len(_syms) >= 3 and len(market_data) >= _lookback:
                    _ret = market_data[_syms].iloc[-_lookback:].pct_change().dropna()
                    _corr = _ret.corr()
                    _upper = [_corr.iloc[i, j] for i in range(len(_syms)) for j in range(i + 1, len(_syms))]
                    _disp_idx = float(pd.Series(_upper).std())
                    self._current_disp_idx = _disp_idx  # C-09: persist for _process_pair
                    if _disp_idx < _min_idx:
                        _block_entries = True
                        logger.info(
                            "dispersion_filter_blocking_entries",
                            dispersion_index=round(_disp_idx, 4),
                            min_required=_min_idx,
                            n_pairs=len(active_pairs),
                        )
        except Exception:
            pass  # Never break signal generation for the dispersion filter

        for sym1, sym2, _pval, hl in active_pairs:
            pair_key = f"{sym1}_{sym2}"

            try:
                sig = self._process_pair(
                    pair_key,
                    sym1,
                    sym2,
                    hl,
                    market_data,
                    active_positions,
                )
                if sig is not None:
                    if _block_entries and sig.side in ("long", "short"):
                        continue  # C-02: dispersion filter blocked entry
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
        active_positions: dict[str, dict],
    ) -> Signal | None:
        """Run the full signal pipeline for a single pair."""
        y = pd.Series(market_data[sym1])
        x = pd.Series(market_data[sym2])

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
        is_stationary, adf_pval = self.stationarity_monitor.check(spread, pair_key=pair_key)
        if not is_stationary:
            # If holding a position in a non-stationary spread ÔåÆ exit
            if pair_key in active_positions:
                return Signal(
                    pair_key=pair_key,
                    side="exit",
                    strength=1.0,
                    reason=f"Stationarity lost (ADF p={adf_pval:.3f})",
                )
            return None
        # 3b. Structural break check (CUSUM + recursive β stability)
        if pair_key not in self._break_detectors:
            self._break_detectors[pair_key] = StructuralBreakDetector()
        has_break, break_details = self._break_detectors[pair_key].check(residuals=spread, y=y, x=x)
        if has_break:
            # P2-01: start/reset cooldown on confirmed break
            try:
                from config.settings import get_settings as _gs_sb

                _cooldown_bars = _gs_sb().strategy.structural_break_cooldown_bars
            except Exception:
                _cooldown_bars = 10
            _both_criteria = break_details.get("cusum_break") and break_details.get("beta_break")
            self._break_cooldown[pair_key] = _cooldown_bars
            # P2-03: log pair suspension
            logger.warning(
                "pair_suspended",
                pair=pair_key,
                reason="structural_break",
                cusum_break=break_details.get("cusum_break"),
                beta_break=break_details.get("beta_break"),
                cooldown_bars=_cooldown_bars,
                both_criteria=_both_criteria,
            )
            if pair_key in active_positions:
                return Signal(
                    pair_key=pair_key,
                    side="exit",
                    strength=1.0,
                    reason=(
                        f"structural_break "
                        f"(cusum={break_details.get('cusum_break')}, "
                        f"beta={break_details.get('beta_break')})"
                    ),
                )
            return None
        # P2-01: decrement cooldown — block entry signals during cooldown period
        if pair_key in self._break_cooldown and self._break_cooldown[pair_key] > 0:
            self._break_cooldown[pair_key] -= 1
            logger.info(
                "pair_in_cooldown",
                pair=pair_key,
                bars_remaining=self._break_cooldown[pair_key],
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

        # 6b. C-09: Dispersion-adaptive threshold ramp
        try:
            if self._current_disp_idx is not None:
                from config.settings import get_settings as _get_settings_disp

                _dc = _get_settings_disp().regime
                thresh = self.threshold_engine.apply_dispersion_adjustment(
                    thresh,
                    disp_idx=self._current_disp_idx,
                    ideal_disp=_dc.dispersion_ideal_index,
                    min_disp=_dc.dispersion_filter_min_index,
                    max_adj=_dc.dispersion_max_entry_adj,
                )
        except Exception:
            pass  # Never break signal generation for dispersion threshold adj
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
            _z_norm = min(abs(current_z) / 3.0, 1.0)

            if current_z > thresh.entry_threshold:
                side = "short"
                # P1-04: composite = z_weight×z + m_weight×mom (documented formula)
                # Directional convention: negative composite = short leg A
                if self.momentum_overlay is not None:
                    m_result = self.momentum_overlay.adjust_signal_strength(
                        side=side,
                        raw_strength=_z_norm,
                        prices_a=y,
                        prices_b=x,
                    )
                    _composite = self._signal_combiner.combine(
                        {"zscore": -_z_norm, "momentum": m_result.momentum_score}
                    )
                    strength = abs(_composite.composite_score)
                    mom_tag = f" [mom:{'C' if m_result.confirms_signal else 'X'}]"
                else:
                    strength = _z_norm
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
                # P1-04: composite = z_weight×z + m_weight×mom (documented formula)
                # Directional convention: positive composite = long leg A
                if self.momentum_overlay is not None:
                    m_result = self.momentum_overlay.adjust_signal_strength(
                        side=side,
                        raw_strength=_z_norm,
                        prices_a=y,
                        prices_b=x,
                    )
                    _composite = self._signal_combiner.combine(
                        {"zscore": +_z_norm, "momentum": m_result.momentum_score}
                    )
                    strength = abs(_composite.composite_score)
                    mom_tag = f" [mom:{'C' if m_result.confirms_signal else 'X'}]"
                else:
                    strength = _z_norm
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

    def get_spread(self, pair_key: str) -> pd.Series | None:
        """Return the latest spread series for a pair."""
        return self._spreads.get(pair_key)

    def get_spread_model(self, pair_key: str) -> SpreadModel | None:
        """Return the spread model for a pair."""
        return self._spread_models.get(pair_key)

    @property
    def current_regime(self) -> VolatilityRegime:
        """Return the current volatility regime."""
        return self.regime_detector.current_regime
