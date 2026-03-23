"""
Portfolio Allocator ÔÇö Position sizing and capital allocation.

Determines how much capital to allocate to each pair trade based on:
    1. Equal-weight allocation (simplest)
    2. Volatility-inverse sizing (allocate more to lower-vol spreads)
    3. Kelly criterion sizing (optimal growth rate)
    4. Signal-strength weighting

Also enforces a portfolio heat limit ÔÇö the total risk budget
across all open positions cannot exceed a configurable ceiling.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum

from structlog import get_logger

logger = get_logger(__name__)


class SizingMethod(Enum):
    """Position sizing method."""

    EQUAL_WEIGHT = "equal_weight"
    VOLATILITY_INVERSE = "volatility_inverse"
    KELLY = "kelly"
    SIGNAL_WEIGHTED = "signal_weighted"


@dataclass
class AllocationResult:
    """Capital allocation recommendation for one pair."""

    pair_key: str
    notional: float
    fraction_of_equity: float
    sizing_method: SizingMethod
    details: dict[str, float]


class PortfolioAllocator:
    """
    Determines the notional size for each pair trade.

    Usage::

        allocator = PortfolioAllocator(
            equity=100_000,
            max_pairs=10,
            max_allocation_pct=0.30,
        )
        result = allocator.allocate(
            pair_key="AAPL_MSFT",
            signal_strength=0.8,
            spread_vol=0.02,
        )
        # result.notional ÔåÆ 30_000 (30% of 100k)
    """

    def __init__(
        self,
        equity: float = 100_000.0,
        max_pairs: int = 10,
        max_allocation_pct: float = 0.30,
        sizing_method: SizingMethod = SizingMethod.VOLATILITY_INVERSE,
        max_portfolio_heat: float = 0.95,
        min_vol_floor: float = 0.001,
    ):
        self.equity = equity
        self.max_pairs = max_pairs
        self.max_allocation_pct = max_allocation_pct
        self.sizing_method = sizing_method
        self.max_portfolio_heat = max_portfolio_heat
        # C-07: floor for spread_vol used in vol-inverse sizing (avoids division by zero)
        self.min_vol_floor = max(min_vol_floor, 1e-9)

        # Track current allocations
        self._allocations: dict[str, float] = {}
        self._lock = threading.Lock()  # T3-02: guard concurrent check-then-write on heat

        logger.info(
            "portfolio_allocator_initialized",
            equity=equity,
            max_pairs=max_pairs,
            max_alloc=f"{max_allocation_pct:.0%}",
            method=sizing_method.value,
        )

    # ------------------------------------------------------------------
    # Allocation
    # ------------------------------------------------------------------

    def allocate(
        self,
        pair_key: str,
        signal_strength: float = 1.0,
        spread_vol: float | None = None,
        half_life: float | None = None,
        win_rate: float | None = None,
        avg_win_loss_ratio: float | None = None,
    ) -> AllocationResult:
        """
        Compute allocation for a single pair.

        Args:
            pair_key: Pair identifier.
            signal_strength: Signal confidence (0ÔÇô1).
            spread_vol: Spread daily volatility (for vol-inverse sizing).
            half_life: Spread half-life (for sizing heuristics).
            win_rate: Historical win rate (for Kelly sizing).
            avg_win_loss_ratio: Average win/loss ratio (for Kelly sizing).

        Returns:
            AllocationResult with recommended notional.
        """
        # Guard: equity must be positive to avoid silent zero-allocation
        if self.equity <= 0:
            raise ValueError(f"Cannot allocate with equity={self.equity:.2f}. Equity must be positive.")

        details: dict[str, float] = {}

        if self.sizing_method == SizingMethod.EQUAL_WEIGHT:
            frac = min(1.0 / self.max_pairs, self.max_allocation_pct)
            details["base_fraction"] = frac

        elif self.sizing_method == SizingMethod.VOLATILITY_INVERSE:
            # Use min_vol_floor to avoid division by zero and to model
            # very low-vol spreads as a bounded-size position.
            eff_vol = max(spread_vol, self.min_vol_floor) if spread_vol is not None else None
            if eff_vol is not None and eff_vol > 0:
                # Target vol contribution
                target_vol = 0.02  # 2% daily vol budget per pair
                frac = min(target_vol / eff_vol, self.max_allocation_pct)
            else:
                frac = min(1.0 / self.max_pairs, self.max_allocation_pct)
            details["spread_vol"] = spread_vol or 0.0

        elif self.sizing_method == SizingMethod.KELLY:
            frac = self._kelly_fraction(win_rate, avg_win_loss_ratio)
            details["kelly_raw"] = frac
            frac = min(frac, self.max_allocation_pct)  # half-Kelly cap
            if half_life is not None:
                details["half_life"] = half_life
                # Very short half-life → reduce size (mean-reversion decays quickly)
                if half_life < 5.0:
                    frac *= max(0.5, half_life / 10.0)

        elif self.sizing_method == SizingMethod.SIGNAL_WEIGHTED:
            base = min(1.0 / self.max_pairs, self.max_allocation_pct)
            frac = base * signal_strength
            details["signal_strength"] = signal_strength

        else:
            frac = min(1.0 / self.max_pairs, self.max_allocation_pct)

        # Portfolio heat check (T3-02: atomic under lock)
        with self._lock:
            current_heat = sum(self._allocations.values())
            if current_heat + frac > self.max_portfolio_heat:
                frac = max(0, self.max_portfolio_heat - current_heat)

            notional = frac * self.equity
            self._allocations[pair_key] = frac

        return AllocationResult(
            pair_key=pair_key,
            notional=notional,
            fraction_of_equity=frac,
            sizing_method=self.sizing_method,
            details=details,
        )

    def release(self, pair_key: str) -> None:
        """Release allocation when a position is closed."""
        with self._lock:
            self._allocations.pop(pair_key, None)

    def update_equity(self, equity: float) -> None:
        """Update equity for sizing calculations."""
        self.equity = equity

    # ------------------------------------------------------------------
    # Kelly
    # ------------------------------------------------------------------

    @staticmethod
    def _kelly_fraction(
        win_rate: float | None,
        wl_ratio: float | None,
    ) -> float:
        """
        Half-Kelly criterion: f* = (p * b - q) / b / 2

        where p = win rate, q = 1-p, b = avg win / avg loss.
        """
        if win_rate is None or wl_ratio is None:
            return 0.10  # conservative fallback

        p = max(0.01, min(0.99, win_rate))
        q = 1.0 - p
        b = max(0.01, wl_ratio)

        kelly = (p * b - q) / b
        half_kelly = max(0.0, kelly / 2.0)
        return min(half_kelly, 0.25)  # never more than 25%

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def current_heat(self) -> float:
        """Total allocated fraction of equity."""
        with self._lock:
            return sum(self._allocations.values())

    @property
    def available_capacity(self) -> float:
        """Remaining capacity before heat limit."""
        with self._lock:
            return max(0, self.max_portfolio_heat - sum(self._allocations.values()))

    @property
    def allocated_pairs(self) -> dict[str, float]:
        with self._lock:
            return dict(self._allocations)
