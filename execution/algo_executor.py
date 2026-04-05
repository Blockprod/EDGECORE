<<<<<<< HEAD
﻿"""
Phase 3.3 ��� Algorithmic Execution (TWAP / VWAP).
=======
"""
Phase 3.3 — Algorithmic Execution (TWAP / VWAP).
>>>>>>> origin/main

Splits large orders into time-sliced child orders to reduce market
impact.  Integrates with the existing ``BaseExecutionEngine`` for
actual order submission.

Two algorithms:
<<<<<<< HEAD
1. **TWAP** ��� Time-Weighted Average Price: equal-sized slices at
   regular intervals.
2. **VWAP** ��� Volume-Weighted Average Price: slices weighted by
=======
1. **TWAP** — Time-Weighted Average Price: equal-sized slices at
   regular intervals.
2. **VWAP** — Volume-Weighted Average Price: slices weighted by
>>>>>>> origin/main
   historical intraday volume profile.

Participation-rate constraint: each slice must not exceed
``max_participation`` % of the bar's expected volume.

For *backtesting*, the AlgoExecutor simulates the fill process
by reporting an estimated fill price that accounts for market
impact spread across slices.
"""

from __future__ import annotations

<<<<<<< HEAD
from dataclasses import dataclass, field
from enum import Enum
=======
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
>>>>>>> origin/main

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

<<<<<<< HEAD

=======
>>>>>>> origin/main
class AlgoType(Enum):
    TWAP = "TWAP"
    VWAP = "VWAP"


@dataclass
class AlgoConfig:
    """Configuration for algorithmic execution."""

    algo_type: AlgoType = AlgoType.TWAP
    num_slices: int = 10
    interval_minutes: int = 5
    max_participation: float = 0.05  # Max 5% of bar volume
    urgency: float = 0.5  # 0 = passive, 1 = aggressive
    # Backtest impact model
    impact_bps: float = 2.0  # Estimated market impact per slice (bps)


# ---------------------------------------------------------------------------
# Slice results
# ---------------------------------------------------------------------------

<<<<<<< HEAD

=======
>>>>>>> origin/main
@dataclass
class SliceFill:
    """Result of a single child order slice."""

    slice_idx: int
    target_qty: float
    filled_qty: float
    fill_price: float
<<<<<<< HEAD
    timestamp: pd.Timestamp | None = None
=======
    timestamp: Optional[pd.Timestamp] = None
>>>>>>> origin/main
    participation_rate: float = 0.0


@dataclass
class AlgoResult:
    """Aggregate result of an algo execution."""

    algo_type: AlgoType
    symbol: str
    side: str  # "BUY" or "SELL"
    total_target_qty: float
    total_filled_qty: float = 0.0
    avg_fill_price: float = 0.0
<<<<<<< HEAD
    slices: list[SliceFill] = field(default_factory=list)
=======
    slices: List[SliceFill] = field(default_factory=list)
>>>>>>> origin/main
    estimated_impact_bps: float = 0.0
    status: str = "PENDING"  # PENDING, PARTIAL, FILLED, CANCELLED


# ---------------------------------------------------------------------------
# TWAP Executor
# ---------------------------------------------------------------------------

<<<<<<< HEAD

=======
>>>>>>> origin/main
class TWAPExecutor:
    """Time-Weighted Average Price execution algorithm.

    Splits the order into ``num_slices`` equal-sized child orders
    spaced at ``interval_minutes`` apart.

    Usage (live)::

        twap = TWAPExecutor(config=AlgoConfig(num_slices=10))
        result = twap.execute(
            symbol="AAPL", side="BUY", total_qty=1000,
            execution_engine=engine,
        )

    Usage (backtest)::

        result = twap.simulate(
            symbol="AAPL", side="BUY", total_qty=1000,
            current_price=150.0, adv=500_000,
        )
    """

<<<<<<< HEAD
    def __init__(self, config: AlgoConfig | None = None):
=======
    def __init__(self, config: Optional[AlgoConfig] = None):
>>>>>>> origin/main
        self.config = config or AlgoConfig(algo_type=AlgoType.TWAP)

    def simulate(
        self,
        symbol: str,
        side: str,
        total_qty: float,
        current_price: float,
        adv: float = 1_000_000,
    ) -> AlgoResult:
        """Simulate TWAP execution for backtesting.

        Estimates the average fill price including market impact
        spread across slices.

        Args:
            symbol: Ticker symbol.
            side: "BUY" or "SELL".
            total_qty: Total shares to execute.
            current_price: Current market price.
            adv: Average daily volume (shares).

        Returns:
            AlgoResult with simulated fills.
        """
        n = self.config.num_slices
        slice_qty = total_qty / n

        # Participation rate: compare slice qty to per-slice expected volume
<<<<<<< HEAD
        # ADV / bars_per_day ��� per-bar volume
        bars_per_day = 78  # 6.5h +� 12 bars/h
=======
        # ADV / bars_per_day ≈ per-bar volume
        bars_per_day = 78  # 6.5h × 12 bars/h
>>>>>>> origin/main
        expected_bar_vol = adv / bars_per_day
        participation = slice_qty / expected_bar_vol if expected_bar_vol > 0 else 1.0

        # Cap participation
        if participation > self.config.max_participation:
            slice_qty = expected_bar_vol * self.config.max_participation
            logger.info(
                "twap_participation_capped",
                symbol=symbol,
                original_slice=total_qty / n,
                capped_slice=slice_qty,
                participation=self.config.max_participation,
            )

<<<<<<< HEAD
        slices: list[SliceFill] = []
=======
        slices: List[SliceFill] = []
>>>>>>> origin/main
        cumulative_qty = 0.0
        cumulative_cost = 0.0

        for i in range(n):
            actual_qty = min(slice_qty, total_qty - cumulative_qty)
            if actual_qty <= 0:
                break

            # Temporary market impact: Almgren-Chriss inspired
            # impact = eta * sigma * (qty / ADV)^0.6
            # Simplified: each slice shifts price by impact_bps
            frac_done = (i + 1) / n
            impact_multiplier = self.config.impact_bps * 1e-4 * np.sqrt(frac_done)

            if side == "BUY":
                fill_price = current_price * (1 + impact_multiplier)
            else:
                fill_price = current_price * (1 - impact_multiplier)

<<<<<<< HEAD
            slices.append(
                SliceFill(
                    slice_idx=i,
                    target_qty=actual_qty,
                    filled_qty=actual_qty,
                    fill_price=fill_price,
                    participation_rate=participation,
                )
            )
=======
            slices.append(SliceFill(
                slice_idx=i,
                target_qty=actual_qty,
                filled_qty=actual_qty,
                fill_price=fill_price,
                participation_rate=participation,
            ))
>>>>>>> origin/main

            cumulative_qty += actual_qty
            cumulative_cost += actual_qty * fill_price

        avg_price = cumulative_cost / cumulative_qty if cumulative_qty > 0 else current_price
        total_impact = abs(avg_price - current_price) / current_price * 10_000  # bps

        result = AlgoResult(
            algo_type=AlgoType.TWAP,
            symbol=symbol,
            side=side,
            total_target_qty=total_qty,
            total_filled_qty=cumulative_qty,
            avg_fill_price=avg_price,
            slices=slices,
            estimated_impact_bps=total_impact,
            status="FILLED" if cumulative_qty >= total_qty * 0.99 else "PARTIAL",
        )

        logger.debug(
            "twap_simulated",
            symbol=symbol,
            side=side,
            qty=total_qty,
            avg_price=f"{avg_price:.4f}",
            impact_bps=f"{total_impact:.2f}",
            slices=len(slices),
        )
        return result


# ---------------------------------------------------------------------------
# VWAP Executor
# ---------------------------------------------------------------------------

# Default US equity intraday volume profile (normalised to sum=1)
# 78 bars: 9:30-16:00 ET, 5-min intervals
# Characteristic U-shape: high volume at open/close, lower midday
_DEFAULT_VOLUME_PROFILE = None  # Lazy-initialized


def _get_default_volume_profile(n_bars: int = 78) -> np.ndarray:
    """Generate a U-shaped intraday volume profile."""
    global _DEFAULT_VOLUME_PROFILE
    if _DEFAULT_VOLUME_PROFILE is not None and len(_DEFAULT_VOLUME_PROFILE) == n_bars:
        return _DEFAULT_VOLUME_PROFILE

    t = np.linspace(0, 1, n_bars)
    # U-shape: higher at open and close
    profile = 1.0 + 1.5 * np.exp(-10 * t) + 2.0 * np.exp(-10 * (1 - t))
    profile /= profile.sum()
    _DEFAULT_VOLUME_PROFILE = profile
<<<<<<< HEAD
    return np.asarray(profile, dtype=float)
=======
    return profile
>>>>>>> origin/main


class VWAPExecutor:
    """Volume-Weighted Average Price execution algorithm.

    Distributes the order across time slices weighted by the expected
    intraday volume profile (U-shaped by default: more at open/close).

    Usage::

        vwap = VWAPExecutor(config=AlgoConfig(algo_type=AlgoType.VWAP))
        result = vwap.simulate(
            symbol="AAPL", side="BUY", total_qty=1000,
            current_price=150.0, adv=500_000,
        )
    """

    def __init__(
        self,
<<<<<<< HEAD
        config: AlgoConfig | None = None,
        volume_profile: np.ndarray | None = None,
=======
        config: Optional[AlgoConfig] = None,
        volume_profile: Optional[np.ndarray] = None,
>>>>>>> origin/main
    ):
        self.config = config or AlgoConfig(algo_type=AlgoType.VWAP)
        self._custom_profile = volume_profile

    def _get_profile(self) -> np.ndarray:
        """Get volume profile, sliced to num_slices."""
        if self._custom_profile is not None:
            return self._custom_profile

        full_profile = _get_default_volume_profile(78)
        n = self.config.num_slices
        if n >= 78:
            return full_profile

        # Resample profile to num_slices bins
        indices = np.linspace(0, 77, n + 1).astype(int)
<<<<<<< HEAD
        profile = np.array([full_profile[indices[i] : indices[i + 1]].sum() for i in range(n)])
=======
        profile = np.array([
            full_profile[indices[i]:indices[i + 1]].sum()
            for i in range(n)
        ])
>>>>>>> origin/main
        profile /= profile.sum()
        return profile

    def simulate(
        self,
        symbol: str,
        side: str,
        total_qty: float,
        current_price: float,
        adv: float = 1_000_000,
    ) -> AlgoResult:
        """Simulate VWAP execution for backtesting.

        Each slice size is proportional to the historical volume profile.

        Args:
            symbol: Ticker symbol.
            side: "BUY" or "SELL".
            total_qty: Total shares to execute.
            current_price: Current market price.
            adv: Average daily volume (shares).

        Returns:
            AlgoResult with simulated fills.
        """
        profile = self._get_profile()
        n = len(profile)

        bars_per_day = 78
        expected_bar_vol = adv / bars_per_day

<<<<<<< HEAD
        slices: list[SliceFill] = []
=======
        slices: List[SliceFill] = []
>>>>>>> origin/main
        cumulative_qty = 0.0
        cumulative_cost = 0.0

        for i in range(n):
            slice_qty = total_qty * profile[i]

            # Participation cap: slice must not exceed max_participation of
            # the bar's expected volume (weighted by profile)
            bar_expected = expected_bar_vol * profile[i] * n
            participation = slice_qty / bar_expected if bar_expected > 0 else 1.0

            if participation > self.config.max_participation:
                slice_qty = bar_expected * self.config.max_participation

            actual_qty = min(slice_qty, total_qty - cumulative_qty)
            if actual_qty <= 0:
                break

            # Market impact: scaled by volume at this time of day
            # Low-volume midday slices have higher impact per share
            vol_weight = profile[i] * n  # >1 means high volume period
            impact_scale = 1.0 / max(vol_weight, 0.3)  # Higher impact when volume is low
<<<<<<< HEAD
            impact_multiplier = self.config.impact_bps * 1e-4 * impact_scale * np.sqrt((i + 1) / n)
=======
            impact_multiplier = (
                self.config.impact_bps * 1e-4
                * impact_scale
                * np.sqrt((i + 1) / n)
            )
>>>>>>> origin/main

            if side == "BUY":
                fill_price = current_price * (1 + impact_multiplier)
            else:
                fill_price = current_price * (1 - impact_multiplier)

<<<<<<< HEAD
            slices.append(
                SliceFill(
                    slice_idx=i,
                    target_qty=actual_qty,
                    filled_qty=actual_qty,
                    fill_price=fill_price,
                    participation_rate=participation,
                )
            )
=======
            slices.append(SliceFill(
                slice_idx=i,
                target_qty=actual_qty,
                filled_qty=actual_qty,
                fill_price=fill_price,
                participation_rate=participation,
            ))
>>>>>>> origin/main

            cumulative_qty += actual_qty
            cumulative_cost += actual_qty * fill_price

        avg_price = cumulative_cost / cumulative_qty if cumulative_qty > 0 else current_price
        total_impact = abs(avg_price - current_price) / current_price * 10_000

        result = AlgoResult(
            algo_type=AlgoType.VWAP,
            symbol=symbol,
            side=side,
            total_target_qty=total_qty,
            total_filled_qty=cumulative_qty,
            avg_fill_price=avg_price,
            slices=slices,
            estimated_impact_bps=total_impact,
            status="FILLED" if cumulative_qty >= total_qty * 0.99 else "PARTIAL",
        )

        logger.debug(
            "vwap_simulated",
            symbol=symbol,
            side=side,
            qty=total_qty,
            avg_price=f"{avg_price:.4f}",
            impact_bps=f"{total_impact:.2f}",
            slices=len(slices),
        )
        return result


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

<<<<<<< HEAD

def create_algo_executor(
    algo_type: str = "TWAP",
    config: AlgoConfig | None = None,
=======
def create_algo_executor(
    algo_type: str = "TWAP",
    config: Optional[AlgoConfig] = None,
>>>>>>> origin/main
) -> TWAPExecutor | VWAPExecutor:
    """Factory to create an algo executor by name.

    Args:
        algo_type: "TWAP" or "VWAP".
        config: Optional configuration override.

    Returns:
        TWAPExecutor or VWAPExecutor instance.
    """
    algo_type_upper = algo_type.upper()
    if algo_type_upper == "TWAP":
        cfg = config or AlgoConfig(algo_type=AlgoType.TWAP)
        return TWAPExecutor(config=cfg)
    elif algo_type_upper == "VWAP":
        cfg = config or AlgoConfig(algo_type=AlgoType.VWAP)
        return VWAPExecutor(config=cfg)
    else:
        raise ValueError(f"Unknown algo type: {algo_type}. Use 'TWAP' or 'VWAP'.")


__all__ = [
    "AlgoType",
    "AlgoConfig",
    "SliceFill",
    "AlgoResult",
    "TWAPExecutor",
    "VWAPExecutor",
    "create_algo_executor",
]
