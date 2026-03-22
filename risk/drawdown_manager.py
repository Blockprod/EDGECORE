"""
Phase 2.4 ÔÇö Multi-Tier Drawdown Manager.

Implements a graduated response to portfolio drawdowns:

    Tier 1 (DD > 3%)  : Reduce sizing by 50%
    Tier 2 (DD > 5%)  : Close 50% of positions (weakest first)
    Tier 3 (DD > 8%)  : Close ALL positions, cooldown 10 bars
    Tier 4 (DD > 12%) : Full stop ÔÇö manual review required

Each tier escalates from the previous. The manager tracks which tier
is currently active and provides action recommendations.
"""

from dataclasses import dataclass
from enum import IntEnum

from structlog import get_logger

logger = get_logger(__name__)


class DrawdownTier(IntEnum):
    """Drawdown severity tiers."""
    NORMAL = 0
    TIER_1 = 1  # Reduce sizing
    TIER_2 = 2  # Close half
    TIER_3 = 3  # Close all + cooldown
    TIER_4 = 4  # Full stop


@dataclass
class DrawdownConfig:
    """Multi-tier drawdown thresholds."""

    tier_1_pct: float = 0.03
    """DD threshold for tier 1 (reduce sizing by 50%)."""

    tier_2_pct: float = 0.05
    """DD threshold for tier 2 (close 50% of positions)."""

    tier_3_pct: float = 0.08
    """DD threshold for tier 3 (close all + cooldown)."""

    tier_4_pct: float = 0.12
    """DD threshold for tier 4 (full stop, manual review)."""

    tier_1_sizing_mult: float = 0.50
    """Sizing multiplier in tier 1."""

    tier_3_cooldown_bars: int = 10
    """Bars to wait after tier 3 before resuming."""


@dataclass
class DrawdownAction:
    """Action recommended by the drawdown manager."""

    tier: DrawdownTier
    sizing_multiplier: float = 1.0
    """1.0 = normal, 0.5 = half size, 0.0 = no new entries."""

    close_fraction: float = 0.0
    """Fraction of positions to force-close (0.0 = none, 0.5 = half, 1.0 = all)."""

    is_halted: bool = False
    """True = no trading allowed (tier 3 cooldown or tier 4 stop)."""

    reset_peak: bool = False
    """True when tier-3 cooldown just expired: caller should reset its own HWM
    to current equity so the next evaluate() call starts fresh."""

    reason: str = ""


class DrawdownManager:
    """
    Multi-tier drawdown management with graduated response.

    Usage::

        dm = DrawdownManager()

        # Each bar:
        action = dm.evaluate(current_equity, peak_equity)
        if action.sizing_multiplier < 1.0:
            alloc *= action.sizing_multiplier
        if action.close_fraction > 0:
            # close weakest N positions
        if action.is_halted:
            # skip all entries
    """

    def __init__(self, config: DrawdownConfig | None = None):
        self.config = config or DrawdownConfig()
        self._current_tier = DrawdownTier.NORMAL
        self._cooldown_remaining: int = 0
        self._tier_4_triggered: bool = False
        self._peak_equity: float = 0.0
        self._positions_closed_in_tier2: bool = False
        logger.info(
            "drawdown_manager_initialized",
            tiers=f"T1={self.config.tier_1_pct:.0%}, T2={self.config.tier_2_pct:.0%}, "
                  f"T3={self.config.tier_3_pct:.0%}, T4={self.config.tier_4_pct:.0%}",
        )

    def evaluate(
        self,
        current_equity: float,
        peak_equity: float,
    ) -> DrawdownAction:
        """Evaluate current drawdown and return recommended action.

        Args:
            current_equity: Current portfolio NAV.
            peak_equity: High-water mark NAV.

        Returns:
            DrawdownAction with tier, sizing_multiplier, close_fraction, is_halted.
        """
        if peak_equity <= 0:
            return DrawdownAction(tier=DrawdownTier.NORMAL)

        # Track peak
        if peak_equity > self._peak_equity:
            self._peak_equity = peak_equity

        dd = (peak_equity - current_equity) / peak_equity

        # Cooldown handling (tier 3 aftereffect)
        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1
            if self._cooldown_remaining == 0:
                self._current_tier = DrawdownTier.NORMAL
                self._positions_closed_in_tier2 = False
                # Reset internal peak to current equity post-cooldown.
                # Also signal the caller to reset its own HWM via reset_peak=True,
                # otherwise the caller's HWM stays at the pre-DD peak and tier3
                # re-triggers immediately on the very next evaluate() call.
                self._peak_equity = current_equity
                logger.info(
                    "drawdown_cooldown_expired",
                    new_peak=round(current_equity, 2),
                )
                return DrawdownAction(
                    tier=DrawdownTier.NORMAL,
                    sizing_multiplier=1.0,
                    close_fraction=0.0,
                    is_halted=False,
                    reset_peak=True,
                    reason="TIER_3_COOLDOWN_EXPIRED: peak reset, resuming normal trading",
                )
            return DrawdownAction(
                tier=DrawdownTier.TIER_3,
                sizing_multiplier=0.0,
                close_fraction=1.0,
                is_halted=True,
                reason=f"TIER_3_COOLDOWN: {self._cooldown_remaining} bars remaining",
            )

        # Tier 4 - full stop (latching ÔÇö requires manual reset)
        if self._tier_4_triggered:
            return DrawdownAction(
                tier=DrawdownTier.TIER_4,
                sizing_multiplier=0.0,
                close_fraction=1.0,
                is_halted=True,
                reason=f"TIER_4_FULL_STOP: DD={dd:.2%}",
            )

        if dd >= self.config.tier_4_pct:
            self._tier_4_triggered = True
            self._current_tier = DrawdownTier.TIER_4
            logger.warning(
                "drawdown_tier4_full_stop",
                drawdown=f"{dd:.2%}",
                threshold=f"{self.config.tier_4_pct:.0%}",
            )
            return DrawdownAction(
                tier=DrawdownTier.TIER_4,
                sizing_multiplier=0.0,
                close_fraction=1.0,
                is_halted=True,
                reason=f"TIER_4_FULL_STOP: DD={dd:.2%} > {self.config.tier_4_pct:.0%}",
            )

        # Tier 3 - close all + cooldown
        if dd >= self.config.tier_3_pct:
            if self._current_tier < DrawdownTier.TIER_3:
                self._cooldown_remaining = self.config.tier_3_cooldown_bars
                self._current_tier = DrawdownTier.TIER_3
                logger.warning(
                    "drawdown_tier3_triggered",
                    drawdown=f"{dd:.2%}",
                    threshold=f"{self.config.tier_3_pct:.0%}",
                    cooldown=self.config.tier_3_cooldown_bars,
                )
            return DrawdownAction(
                tier=DrawdownTier.TIER_3,
                sizing_multiplier=0.0,
                close_fraction=1.0,
                is_halted=True,
                reason=f"TIER_3: DD={dd:.2%} > {self.config.tier_3_pct:.0%}",
            )

        # Tier 2 - close 50% of positions
        if dd >= self.config.tier_2_pct:
            if self._current_tier < DrawdownTier.TIER_2:
                self._current_tier = DrawdownTier.TIER_2
                self._positions_closed_in_tier2 = False
                logger.warning(
                    "drawdown_tier2_triggered",
                    drawdown=f"{dd:.2%}",
                    threshold=f"{self.config.tier_2_pct:.0%}",
                )
            close_frac = 0.5 if not self._positions_closed_in_tier2 else 0.0
            if close_frac > 0:
                self._positions_closed_in_tier2 = True
            return DrawdownAction(
                tier=DrawdownTier.TIER_2,
                sizing_multiplier=self.config.tier_1_sizing_mult,
                close_fraction=close_frac,
                is_halted=False,
                reason=f"TIER_2: DD={dd:.2%} > {self.config.tier_2_pct:.0%}",
            )

        # Tier 1 - reduce sizing
        if dd >= self.config.tier_1_pct:
            if self._current_tier < DrawdownTier.TIER_1:
                self._current_tier = DrawdownTier.TIER_1
                logger.info(
                    "drawdown_tier1_triggered",
                    drawdown=f"{dd:.2%}",
                    threshold=f"{self.config.tier_1_pct:.0%}",
                )
            return DrawdownAction(
                tier=DrawdownTier.TIER_1,
                sizing_multiplier=self.config.tier_1_sizing_mult,
                close_fraction=0.0,
                is_halted=False,
                reason=f"TIER_1: DD={dd:.2%} > {self.config.tier_1_pct:.0%}",
            )

        # Normal
        if self._current_tier != DrawdownTier.NORMAL:
            self._current_tier = DrawdownTier.NORMAL
            self._positions_closed_in_tier2 = False
            logger.info("drawdown_returned_to_normal", drawdown=f"{dd:.2%}")

        return DrawdownAction(tier=DrawdownTier.NORMAL)

    def reset(self) -> None:
        """Reset all state (e.g. between walk-forward windows)."""
        self._current_tier = DrawdownTier.NORMAL
        self._cooldown_remaining = 0
        self._tier_4_triggered = False
        self._peak_equity = 0.0
        self._positions_closed_in_tier2 = False

    @property
    def current_tier(self) -> DrawdownTier:
        return self._current_tier

    @property
    def is_tier4_latched(self) -> bool:
        return self._tier_4_triggered


__all__ = [
    "DrawdownManager",
    "DrawdownConfig",
    "DrawdownAction",
    "DrawdownTier",
]
