<<<<<<< HEAD
﻿"""
Phase 2.2 ÔÇö Sector Exposure Monitor.
=======
"""
Phase 2.2 — Sector Exposure Monitor.
>>>>>>> origin/main

Tracks aggregate notional exposure per sector and enforces hard limits.
Prevents the portfolio from becoming implicitly concentrated in a single
sector, which would create correlated drawdowns during sector rotations.

The SpreadCorrelationGuard (already wired) handles pairwise spread
correlation. This module handles the *aggregate* sector dimension.
"""

from dataclasses import dataclass
<<<<<<< HEAD
=======
from typing import Dict, Optional, Tuple
>>>>>>> origin/main

from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class SectorExposureConfig:
    """Configuration for sector exposure limits."""

    max_sector_weight: float = 1.00
    """Maximum fraction of portfolio notional in any single sector.
    
    Since all pairs are intra-sector (same-sector discovery), the position
    count limit (max_sector_positions) is the primary concentration guard.
    The weight limit prevents excessive notional in one sector when
    multiple positions compound."""

    max_sector_positions: int = 4
    """Maximum number of concurrent positions involving a given sector."""


class SectorExposureMonitor:
    """
    Tracks per-sector exposure and gates new entries.

    Usage::

        sem = SectorExposureMonitor(sector_map={"AAPL": "technology", ...})

        # Before entry:
        ok, reason = sem.can_enter(pair_key, notional, portfolio_value, positions)

        # After entry / exit (or each bar):
        report = sem.get_exposure_report(positions, portfolio_value)
    """

    def __init__(
        self,
<<<<<<< HEAD
        sector_map: dict[str, str] | None = None,
        config: SectorExposureConfig | None = None,
=======
        sector_map: Optional[Dict[str, str]] = None,
        config: Optional[SectorExposureConfig] = None,
>>>>>>> origin/main
    ):
        self.config = config or SectorExposureConfig()
        self._sector_map = sector_map or {}
        logger.info(
            "sector_exposure_monitor_initialized",
            max_weight=self.config.max_sector_weight,
            max_positions=self.config.max_sector_positions,
        )

<<<<<<< HEAD
    def set_sector_map(self, sector_map: dict[str, str]) -> None:
=======
    def set_sector_map(self, sector_map: Dict[str, str]) -> None:
>>>>>>> origin/main
        """Update the symbol-to-sector mapping."""
        self._sector_map = sector_map

    def can_enter(
        self,
        pair_key: str,
        new_notional: float,
        portfolio_value: float,
<<<<<<< HEAD
        positions: dict[str, dict],
    ) -> tuple[bool, str | None]:
=======
        positions: Dict[str, dict],
    ) -> Tuple[bool, Optional[str]]:
>>>>>>> origin/main
        """Check if adding this pair would breach sector limits.

        A pair trade has two legs (one per symbol). Each leg contributes
        half the notional to its sector. For same-sector pairs both legs
        add to the same sector (full notional in that sector).

        Returns:
            (allowed: bool, reason: Optional[str])
        """
        if portfolio_value <= 0:
            return True, None

        parts = pair_key.split("_")
        if len(parts) != 2:
            return True, None

        # Map each symbol to its sector and compute per-sector added notional
        sym_sectors = {}
        for sym in parts:
            sec = self._sector_map.get(sym)
            if sec:
                sym_sectors[sym] = sec

        if not sym_sectors:
            return True, None

        # Per-leg notional = half the pair notional
        per_leg = new_notional / 2.0

        # Accumulate added notional per sector
<<<<<<< HEAD
        added_per_sector: dict[str, float] = {}
=======
        added_per_sector: Dict[str, float] = {}
>>>>>>> origin/main
        for sym, sec in sym_sectors.items():
            added_per_sector[sec] = added_per_sector.get(sec, 0.0) + per_leg

        # Current sector exposure
        sector_notional, sector_count = self._compute_sector_stats(positions)

        for sector, added in added_per_sector.items():
            current_weight = sector_notional.get(sector, 0.0) / portfolio_value
            new_weight = (sector_notional.get(sector, 0.0) + added) / portfolio_value
            if new_weight > self.config.max_sector_weight:
                reason = (
                    f"SECTOR_LIMIT: {sector} weight {new_weight:.1%} "
                    f"would exceed {self.config.max_sector_weight:.0%} "
                    f"(current: {current_weight:.1%})"
                )
                logger.info(
                    "entry_rejected_sector_exposure",
                    pair=pair_key,
                    sector=sector,
                    current_weight=round(current_weight, 3),
                    new_weight=round(new_weight, 3),
                    limit=self.config.max_sector_weight,
                )
                return False, reason

            # Position count check
            cur_count = sector_count.get(sector, 0)
            if cur_count >= self.config.max_sector_positions:
<<<<<<< HEAD
                reason = f"SECTOR_LIMIT: {sector} has {cur_count} positions (max {self.config.max_sector_positions})"
=======
                reason = (
                    f"SECTOR_LIMIT: {sector} has {cur_count} positions "
                    f"(max {self.config.max_sector_positions})"
                )
>>>>>>> origin/main
                logger.info(
                    "entry_rejected_sector_position_count",
                    pair=pair_key,
                    sector=sector,
                    count=cur_count,
                    limit=self.config.max_sector_positions,
                )
                return False, reason

        return True, None

    def get_exposure_report(
        self,
<<<<<<< HEAD
        positions: dict[str, dict],
        portfolio_value: float,
    ) -> dict[str, dict[str, float]]:
=======
        positions: Dict[str, dict],
        portfolio_value: float,
    ) -> Dict[str, Dict[str, float]]:
>>>>>>> origin/main
        """Return per-sector exposure summary.

        Returns:
            Dict[sector, {"notional": float, "weight": float, "positions": int}]
        """
        sector_notional, sector_count = self._compute_sector_stats(positions)
        report = {}
        for sector in set(list(sector_notional.keys()) + list(sector_count.keys())):
            notional = sector_notional.get(sector, 0.0)
            report[sector] = {
                "notional": round(notional, 2),
                "weight": round(notional / portfolio_value, 4) if portfolio_value > 0 else 0.0,
                "positions": sector_count.get(sector, 0),
            }
        return report

<<<<<<< HEAD
    def _compute_sector_stats(self, positions: dict[str, dict]) -> tuple[dict[str, float], dict[str, int]]:
        """Aggregate notional and position count per sector."""
        sector_notional: dict[str, float] = {}
        sector_count: dict[str, int] = {}

        for _pair_key, pos in positions.items():
=======
    def _compute_sector_stats(
        self, positions: Dict[str, dict]
    ) -> Tuple[Dict[str, float], Dict[str, int]]:
        """Aggregate notional and position count per sector."""
        sector_notional: Dict[str, float] = {}
        sector_count: Dict[str, int] = {}

        for pair_key, pos in positions.items():
>>>>>>> origin/main
            sym1, sym2 = pos.get("sym1", ""), pos.get("sym2", "")
            notional = pos.get("notional", 0.0)

            for sym in (sym1, sym2):
                sec = self._sector_map.get(sym)
                if sec:
                    sector_notional[sec] = sector_notional.get(sec, 0.0) + notional / 2.0
                    sector_count[sec] = sector_count.get(sec, 0) + 1

        return sector_notional, sector_count


__all__ = ["SectorExposureMonitor", "SectorExposureConfig"]
