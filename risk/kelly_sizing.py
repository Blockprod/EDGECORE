<<<<<<< HEAD
﻿"""
=======
"""
>>>>>>> origin/main
Institutional position sizing via fractional Kelly criterion.

Phase 0.2 of the EDGECORE Institutional Roadmap.

The Kelly criterion computes the optimal fraction of capital to risk
on a bet given the probability of winning and the win/loss ratio.
Institutional practitioners use a fraction of Kelly (typically 1/4)
to reduce variance of outcomes.

Usage::

    sizer = KellySizer()
    alloc_pct = sizer.compute_allocation(
        win_rate=0.625,
        avg_win=500.0,
        avg_loss=300.0,
        current_equity=100_000,
    )
"""

from dataclasses import dataclass
<<<<<<< HEAD

=======
from typing import Dict, Optional
>>>>>>> origin/main
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class KellySizerConfig:
    """Configuration for Kelly-based position sizing."""

<<<<<<< HEAD
    kelly_fraction: float = 0.25  # Quarter-Kelly (institutional standard)
    max_position_pct: float = 10.0  # Max 10% of equity per pair
    min_position_pct: float = 2.0  # Min 2% (below this, skip the trade)
    max_sector_pct: float = 25.0  # Max 25% gross exposure per sector
    max_gross_leverage: float = 2.0  # Max 200% gross leverage
    max_loss_per_trade_nav_pct: float = 0.75  # Max 0.75% of NAV loss per trade
    default_allocation_pct: float = 8.0  # Fallback when no trade history
=======
    kelly_fraction: float = 0.25           # Quarter-Kelly (institutional standard)
    max_position_pct: float = 10.0         # Max 10% of equity per pair
    min_position_pct: float = 2.0          # Min 2% (below this, skip the trade)
    max_sector_pct: float = 25.0           # Max 25% gross exposure per sector
    max_gross_leverage: float = 2.0        # Max 200% gross leverage
    max_loss_per_trade_nav_pct: float = 0.75  # Max 0.75% of NAV loss per trade
    default_allocation_pct: float = 8.0    # Fallback when no trade history
>>>>>>> origin/main


class KellySizer:
    """Fractional Kelly position sizer with institutional risk limits."""

<<<<<<< HEAD
    def __init__(self, config: KellySizerConfig | None = None):
=======
    def __init__(self, config: Optional[KellySizerConfig] = None):
>>>>>>> origin/main
        self.config = config or KellySizerConfig()
        # Rolling trade history for adaptive Kelly
        self._trade_history: list = []
        self._max_history = 100

    def record_trade(self, pnl: float) -> None:
        """Record a completed trade PnL for adaptive Kelly computation."""
        self._trade_history.append(pnl)
        if len(self._trade_history) > self._max_history:
            self._trade_history.pop(0)

    def _compute_kelly_fraction(
        self,
<<<<<<< HEAD
        win_rate: float | None = None,
        avg_win: float | None = None,
        avg_loss: float | None = None,
=======
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
>>>>>>> origin/main
    ) -> float:
        """Compute raw Kelly fraction f* = (p*b - q) / b.

        If win_rate/avg_win/avg_loss not provided, estimates from
        trade history. Returns 0 if insufficient data or negative edge.
        """
        if win_rate is not None and avg_win is not None and avg_loss is not None:
            p = win_rate
            q = 1.0 - p
            if avg_loss <= 0:
                return 0.0
            b = avg_win / avg_loss
            kelly = (p * b - q) / b
            return max(kelly, 0.0)

        # Estimate from trade history
        if len(self._trade_history) < 10:
<<<<<<< HEAD
            logger.warning(
                "kelly_sizer_insufficient_history",
                n_trades=len(self._trade_history),
                min_required=10,
                using_fallback_pct=self.config.default_allocation_pct,
            )
=======
>>>>>>> origin/main
            return self.config.default_allocation_pct / 100.0

        wins = [t for t in self._trade_history if t > 0]
        losses = [t for t in self._trade_history if t <= 0]

        if not wins or not losses:
            return self.config.default_allocation_pct / 100.0

        p = len(wins) / len(self._trade_history)
        q = 1.0 - p
        avg_w = sum(wins) / len(wins)
        avg_l = abs(sum(losses) / len(losses))

        if avg_l <= 0:
            return 0.0

        b = avg_w / avg_l
        kelly = (p * b - q) / b
<<<<<<< HEAD
        return float(max(kelly, 0.0))
=======
        return max(kelly, 0.0)
>>>>>>> origin/main

    def compute_allocation(
        self,
        current_equity: float,
<<<<<<< HEAD
        win_rate: float | None = None,
        avg_win: float | None = None,
        avg_loss: float | None = None,
        sector: str | None = None,
        sector_exposure: dict[str, float] | None = None,
=======
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
        sector: Optional[str] = None,
        sector_exposure: Optional[Dict[str, float]] = None,
>>>>>>> origin/main
        current_gross_exposure: float = 0.0,
    ) -> float:
        """Compute position allocation as % of equity.

        Returns allocation percentage (e.g. 8.0 for 8%).
        Returns 0.0 if the trade should be skipped (limits breached).
        """
        # 1. Raw Kelly
        raw_kelly = self._compute_kelly_fraction(win_rate, avg_win, avg_loss)

        # 2. Apply fractional Kelly
        alloc_fraction = raw_kelly * self.config.kelly_fraction

        # 3. Convert to percentage
        alloc_pct = alloc_fraction * 100.0

        # 4. Clamp to [min, max] position limits
        if alloc_pct < self.config.min_position_pct:
            alloc_pct = self.config.min_position_pct
        alloc_pct = min(alloc_pct, self.config.max_position_pct)

        # 5. Sector concentration limit
        if sector and sector_exposure:
            current_sector_pct = sector_exposure.get(sector, 0.0)
            remaining_sector = self.config.max_sector_pct - current_sector_pct
            if remaining_sector <= 0:
                logger.debug(
                    "kelly_rejected_sector_limit",
                    sector=sector,
                    current_pct=f"{current_sector_pct:.1f}%",
                    limit=f"{self.config.max_sector_pct:.1f}%",
                )
                return 0.0
            alloc_pct = min(alloc_pct, remaining_sector)

        # 6. Gross leverage limit
        if current_equity > 0:
            proposed_notional = current_equity * alloc_pct / 100.0
            new_gross = current_gross_exposure + proposed_notional
            if new_gross / current_equity > self.config.max_gross_leverage:
<<<<<<< HEAD
                available = self.config.max_gross_leverage * current_equity - current_gross_exposure
                if available <= 0:
                    logger.debug(
                        "kelly_rejected_leverage_limit",
                        gross_leverage=f"{new_gross / current_equity:.2f}",
=======
                available = (
                    self.config.max_gross_leverage * current_equity
                    - current_gross_exposure
                )
                if available <= 0:
                    logger.debug(
                        "kelly_rejected_leverage_limit",
                        gross_leverage=f"{new_gross/current_equity:.2f}",
>>>>>>> origin/main
                        limit=f"{self.config.max_gross_leverage:.1f}",
                    )
                    return 0.0
                alloc_pct = min(alloc_pct, available / current_equity * 100.0)

        return alloc_pct

    def compute_nav_stop_price_distance(
        self,
        notional: float,
        current_equity: float,
    ) -> float:
        """Compute max loss allowed per trade as fraction of notional.

        Ensures that the worst-case loss on this trade does not exceed
        max_loss_per_trade_nav_pct of the portfolio NAV.

        Returns the stop-loss as a fraction of notional (e.g. 0.075 = 7.5%).
        """
        if notional <= 0 or current_equity <= 0:
            return 0.07  # fallback

        max_loss_dollars = current_equity * self.config.max_loss_per_trade_nav_pct / 100.0
        stop_pct = max_loss_dollars / notional
        # Floor at 1% to avoid hyper-tight stops
        return max(stop_pct, 0.01)
