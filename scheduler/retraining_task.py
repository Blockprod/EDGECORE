"""Periodic hedge-ratio re-estimation task (C-07 + C-10).

Runs ``ModelRetrainingManager.reestimate_hedge_ratios()`` every
``interval_bars`` trading bars (default: 14 ≈ 2 weeks).

C-10: Adaptive frequency based on market regime:
  - LOW volatility  : interval × 2 (pairs stable, less retraining needed)
  - NORMAL          : nominal interval
  - HIGH volatility : interval ÷ 2, minimum 7 bars (cointegration degrades faster)

KillSwitch guard: skipped automatically when the kill-switch is active.
"""

from __future__ import annotations

import pandas as pd
from structlog import get_logger

from models.model_retraining import ModelRetrainingManager

logger = get_logger(__name__)

# Minimum interval regardless of regime adjustment
_MIN_INTERVAL_BARS = 7


class RetrainingTask:
    """Periodic hedge-ratio re-estimation task.

    Usage::

        task = RetrainingTask(interval_bars=14)

        # In the trading loop — pass None for kill_switch if unavailable.
        updated_ratios = task.maybe_run(
            current_bar=self._iteration,
            price_data=market_data,
            active_pairs=[(s1, s2) for s1, s2, *_ in self._active_pairs],
            kill_switch=self._kill_switch,
            regime_detector=self.regime_detector,  # optional C-10
        )
        if updated_ratios:
            logger.info("hedge_ratios_updated", count=len(updated_ratios))
    """

    def __init__(self, interval_bars: int = 14) -> None:
        self._base_interval = max(_MIN_INTERVAL_BARS, interval_bars)
        self._manager = ModelRetrainingManager(
            reestimation_frequency_days=interval_bars,
        )
        self._last_run_bar: int = -(interval_bars + 1)  # ensure first tick triggers

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def maybe_run(
        self,
        current_bar: int,
        price_data: pd.DataFrame,
        active_pairs: list[tuple[str, str]],
        kill_switch: object | None = None,
        regime_detector: object | None = None,
    ) -> dict[str, tuple[float, float]] | None:
        """Run re-estimation if interval has elapsed and KillSwitch is inactive.

        C-10: The effective interval is adjusted by the current regime:
            LOW    → ``base_interval × 2``
            NORMAL → ``base_interval``
            HIGH   → ``base_interval ÷ 2``, min ``_MIN_INTERVAL_BARS``

        Args:
            current_bar: Current bar/iteration counter.
            price_data: Multi-bar price DataFrame (OHLCV, columns = symbols).
            active_pairs: List of ``(symbol1, symbol2)`` tuples to reestimate.
            kill_switch: Optional KillSwitch instance.  Skipped if active.
            regime_detector: Optional RegimeDetector / MarkovRegimeDetector.
                When provided, adjusts retraining frequency by regime (C-10).

        Returns:
            Dict of ``pair_key -> (new_hedge_ratio, p_value)`` on success,
            ``None`` if skipped.
        """
        # C-10: Compute effective interval from current regime
        effective_interval = self._effective_interval(regime_detector)

        if current_bar - self._last_run_bar < effective_interval:
            return None

        if kill_switch is not None and getattr(kill_switch, "is_active", False):
            logger.info(
                "retraining_skipped_kill_switch_active",
                current_bar=current_bar,
                next_due=self._last_run_bar + effective_interval,
            )
            return None

        if not active_pairs or price_data is None or price_data.empty:
            self._last_run_bar = current_bar
            return None

        logger.info(
            "retraining_starting",
            current_bar=current_bar,
            pairs_count=len(active_pairs),
            effective_interval_bars=effective_interval,
            base_interval_bars=self._base_interval,
        )

        result = self._manager.reestimate_hedge_ratios(price_data, active_pairs)

        self._last_run_bar = current_bar

        logger.info(
            "retraining_report",
            pairs_reestimated=len(result),
            current_bar=current_bar,
            next_due=current_bar + effective_interval,
            effective_interval_bars=effective_interval,
        )

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _effective_interval(self, regime_detector: object | None) -> int:
        """Compute the effective retraining interval adjusted by market regime (C-10)."""
        if regime_detector is None:
            return self._base_interval

        try:
            from models.regime_detector import VolatilityRegime
            regime = getattr(regime_detector, "current_regime", None)
            if regime is None:
                return self._base_interval
            if regime == VolatilityRegime.LOW:
                return self._base_interval * 2
            if regime == VolatilityRegime.HIGH:
                return max(_MIN_INTERVAL_BARS, self._base_interval // 2)
        except Exception:
            pass  # Defensive: any failure → nominal interval

        return self._base_interval

