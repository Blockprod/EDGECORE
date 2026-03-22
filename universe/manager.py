"""
Universe Manager ÔÇö Manages the tradeable symbol universe.

Responsibilities:
    - Load symbols from configuration (config/dev.yaml)
    - Classify symbols by sector for intra-sector pair matching
    - Apply liquidity and delisting filters
    - Provide filtered universe snapshots per bar
    - Support dynamic symbol rotation (add/remove at runtime)
    - Dynamic refresh from IBKRUniverseScanner

Usage::

    mgr = UniverseManager()
    snapshot = mgr.get_snapshot(volume_data={"AAPL": 50e6, "MSFT": 80e6})
    candidate_pairs = mgr.generate_candidate_pairs(snapshot)

    # Dynamic refresh from scanner
    from universe.scanner import IBKRUniverseScanner
    scanner = IBKRUniverseScanner()
    mgr.refresh_from_scanner(scanner.scan_sec_only())
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union

import pandas as pd
from structlog import get_logger

from data.delisting_guard import DelistingGuard
from data.liquidity_filter import LiquidityConfig, LiquidityFilter

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Sector classification
# ---------------------------------------------------------------------------

class Sector(Enum):
    """
    Equity sector classification for pair grouping.

    .. deprecated::
        Use plain strings (``"technology"``, ``"financials"``, etc.)
        instead of enum members.  The enum is kept for backward
        compatibility but the manager now works with strings internally.
    """
    TECHNOLOGY = "technology"
    FINANCIALS = "financials"
    HEALTHCARE = "healthcare"
    CONSUMER_STAPLES = "consumer_staples"
    CONSUMER_DISCRETIONARY = "consumer_discretionary"
    ENERGY = "energy"
    INDUSTRIALS = "industrials"
    UTILITIES = "utilities"
    REITS = "reits"
    MATERIALS = "materials"
    COMMUNICATION = "communication"
    UNKNOWN = "unknown"


def _normalize_sector(value: Union[str, Sector]) -> str:
    """Convert Sector enum or string to normalized sector string."""
    if isinstance(value, Sector):
        return value.value
    return str(value).lower().strip()


# Canonical sector mapping for the default US large-cap universe.
# Uses plain strings ÔÇö compatible with both run_backtest.py and Sector enum.
DEFAULT_SECTOR_MAP: dict[str, str] = {
    # Technology (Mega Cap)
    "AAPL": "technology", "MSFT": "technology",
    "GOOGL": "technology", "META": "technology",
    "NVDA": "technology", "AMD": "technology",
    "INTC": "technology", "AVGO": "technology",
    "CRM": "technology", "ADBE": "technology",
    # Technology / Semiconductors (Mid-Cap)
    "MRVL": "technology", "ON": "technology",
    "MCHP": "technology", "QCOM": "technology",
    "TXN": "technology", "AMAT": "technology",
    "LRCX": "technology", "KLAC": "technology",
    # Financials (Mega Cap)
    "JPM": "financials", "BAC": "financials",
    "GS": "financials", "MS": "financials",
    "WFC": "financials", "C": "financials",
    "BLK": "financials", "SCHW": "financials",
    # Financials - Regional Banks
    "USB": "financials", "PNC": "financials",
    "TFC": "financials", "RF": "financials",
    "CFG": "financials", "HBAN": "financials",
    "KEY": "financials",
    # Healthcare / Pharma (Mega Cap)
    "JNJ": "healthcare", "PFE": "healthcare",
    "UNH": "healthcare", "MRK": "healthcare",
    "ABBV": "healthcare", "LLY": "healthcare",
    "TMO": "healthcare", "ABT": "healthcare",
    # Healthcare / Biotech (Mid-Cap)
    "GILD": "healthcare", "REGN": "healthcare",
    "BIIB": "healthcare", "VRTX": "healthcare",
    "BMY": "healthcare", "ZTS": "healthcare",
    "MCK": "healthcare",
    # Healthcare Services
    "CVS": "healthcare", "CI": "healthcare",
    "HUM": "healthcare", "ELV": "healthcare",
    "CNC": "healthcare",
    # Consumer Staples
    "KO": "consumer_staples", "PEP": "consumer_staples",
    "PG": "consumer_staples", "CL": "consumer_staples",
    "WMT": "consumer_staples", "COST": "consumer_staples",
    # Consumer Discretionary / Retail
    "TGT": "consumer_discretionary", "LOW": "consumer_discretionary",
    "HD": "consumer_discretionary", "ROST": "consumer_discretionary",
    "TJX": "consumer_discretionary", "DLTR": "consumer_discretionary",
    "DG": "consumer_discretionary",
    # Energy
    "XOM": "energy", "CVX": "energy",
    "COP": "energy", "SLB": "energy",
    "EOG": "energy",
    "VLO": "energy", "MPC": "energy",
    "PSX": "energy", "DVN": "energy",
    "HAL": "energy", "BKR": "energy",
    # Industrials
    "CAT": "industrials", "DE": "industrials",
    "HON": "industrials", "GE": "industrials",
    "RTX": "industrials", "LMT": "industrials",
    "MMM": "industrials", "EMR": "industrials",
    "ITW": "industrials", "ROK": "industrials",
    "CMI": "industrials", "PH": "industrials",
    # Communication / Media
    "CMCSA": "communication", "DIS": "communication",
    "NFLX": "communication", "FOXA": "communication",
    "VZ": "communication", "T": "communication",
    # Utilities
    "NEE": "utilities", "DUK": "utilities",
    "SO": "utilities", "D": "utilities",
    # REITs
    "PLD": "reits", "AMT": "reits",
    "SPG": "reits",
    # --- ETFs Sectoriels ---
    "XLK": "technology", "SMH": "technology",
    "XLF": "financials", "KRE": "financials",
    "XLE": "energy",
    "XLV": "healthcare", "XBI": "healthcare", "IBB": "healthcare",
    "XLI": "industrials",
    "XLU": "utilities",
    "XLP": "consumer_staples",
    "XLB": "materials",
    "XLC": "communication",
    "XLRE": "reits", "IYR": "reits",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class UniverseSnapshot:
    """Point-in-time view of the tradeable universe."""
    symbols: list[str]
    sector_groups: dict[str, list[str]]   # sector_name -> symbols
    excluded: dict[str, str]              # symbol -> exclusion reason
    timestamp: pd.Timestamp
    total_candidates: int

    @property
    def active_count(self) -> int:
        return len(self.symbols)

    @property
    def exclusion_count(self) -> int:
        return len(self.excluded)

    def symbols_in_sector(self, sector: Union[str, Sector]) -> list[str]:
        """Return symbols belonging to *sector*."""
        key = _normalize_sector(sector)
        return self.sector_groups.get(key, [])


# ---------------------------------------------------------------------------
# UniverseManager
# ---------------------------------------------------------------------------

class UniverseManager:
    """
    Central manager for the tradeable symbol universe.

    Orchestrates:
        1. Symbol loading from config or dynamic scanner
        2. Liquidity filtering (min 24h volume)
        3. Delisting guard (exclude at-risk tickers)
        4. Sector classification (string-based)
        5. Dynamic rotation (runtime add/exclude/restore)
        6. Refresh from IBKRUniverseScanner

    Sector types are unified as plain strings (e.g. ``"technology"``).
    The ``Sector`` enum is accepted for backward compatibility and
    automatically converted.

    Usage::

        mgr = UniverseManager()
        snapshot = mgr.get_snapshot(volume_data=vol_dict)
        pairs = mgr.generate_candidate_pairs(snapshot)
    """

    def __init__(
        self,
        symbols: list[str] | None = None,
        sector_map: dict[str, Union[str, Sector]] | None = None,
        min_volume_24h_usd: float = 5_000_000.0,
        cross_sector_pairs: bool = False,
    ):
        """
        Args:
            symbols: Override list.  If *None*, loads from config.
            sector_map: Override sector classification.  Accepts both
                ``Dict[str, str]`` and ``Dict[str, Sector]``.
            min_volume_24h_usd: Minimum daily USD volume for eligibility.
            cross_sector_pairs: If *True*, generates all pair combinations.
                If *False* (default), restricts to intra-sector pairs.
        """
        if symbols is None:
            from config.settings import get_settings
            symbols = get_settings().trading_universe.symbols

        self._all_symbols: list[str] = list(symbols)

        # Normalize sector_map: convert Sector enum values to strings
        raw_map = sector_map if sector_map is not None else dict(DEFAULT_SECTOR_MAP)
        self._sector_map: dict[str, str] = {
            k: _normalize_sector(v) for k, v in raw_map.items()
        }

        self._manually_excluded: set[str] = set()
        self._cross_sector = cross_sector_pairs

        self.liquidity_filter = LiquidityFilter(
            LiquidityConfig(min_volume_24h_usd=min_volume_24h_usd)
        )
        self.delisting_guard = DelistingGuard()

        logger.info(
            "universe_manager_initialized",
            total_symbols=len(self._all_symbols),
            sectors=len(set(self._sector_map.get(s, "unknown") for s in self._all_symbols)),
            cross_sector=cross_sector_pairs,
        )

    # ------------------------------------------------------------------
    # Snapshot generation
    # ------------------------------------------------------------------

    def get_snapshot(
        self,
        volume_data: dict[str, float] | None = None,
        price_data: dict[str, pd.Series] | None = None,
        timestamp: pd.Timestamp | None = None,
    ) -> UniverseSnapshot:
        """
        Generate a filtered universe snapshot.

        Args:
            volume_data: symbol -> 24h USD volume.
            price_data: symbol -> price Series (used for delisting guard).
            timestamp: Snapshot timestamp (defaults to now).

        Returns:
            UniverseSnapshot with active symbols and exclusion reasons.
        """
        ts = timestamp or pd.Timestamp.now()
        excluded: dict[str, str] = {}
        active: list[str] = []

        for sym in self._all_symbols:
            # Manual exclusion
            if sym in self._manually_excluded:
                excluded[sym] = "manually_excluded"
                continue

            # Liquidity check
            if volume_data is not None:
                vol = volume_data.get(sym, 0.0)
                if vol < self.liquidity_filter.config.min_volume_24h_usd:
                    excluded[sym] = f"illiquid (vol=${vol:,.0f})"
                    continue

            # Delisting guard
            if price_data is not None and sym in price_data:
                safe, reason = self.delisting_guard.is_safe(sym, price_data[sym])
                if not safe:
                    excluded[sym] = f"delisting_risk ({reason})"
                    continue

            active.append(sym)

        # Build sector groups (string keys)
        sector_groups: dict[str, list[str]] = {}
        for sym in active:
            sector = self._sector_map.get(sym, "unknown")
            sector_groups.setdefault(sector, []).append(sym)

        snapshot = UniverseSnapshot(
            symbols=active,
            sector_groups=sector_groups,
            excluded=excluded,
            timestamp=ts,
            total_candidates=len(self._all_symbols),
        )

        logger.info(
            "universe_snapshot",
            active=snapshot.active_count,
            excluded=snapshot.exclusion_count,
            sectors=len(sector_groups),
        )
        return snapshot

    # ------------------------------------------------------------------
    # Pair candidate generation
    # ------------------------------------------------------------------

    def generate_candidate_pairs(
        self,
        snapshot: UniverseSnapshot,
    ) -> list[tuple[str, str]]:
        """
        Generate candidate pairs for cointegration testing.

        By default only intra-sector pairs are generatedÔÇöhigher a-priori
        probability of genuine economic cointegration.

        Args:
            snapshot: Current universe snapshot.

        Returns:
            Sorted list of (symbol1, symbol2) tuples.
        """
        pairs: list[tuple[str, str]] = []
        if self._cross_sector:
            syms = sorted(snapshot.symbols)
            for i, s1 in enumerate(syms):
                for s2 in syms[i + 1:]:
                    pairs.append((s1, s2))
        else:
            for _sector, syms in snapshot.sector_groups.items():
                syms_sorted = sorted(syms)
                for i, s1 in enumerate(syms_sorted):
                    for s2 in syms_sorted[i + 1:]:
                        pairs.append((s1, s2))

        logger.info(
            "candidate_pairs_generated",
            count=len(pairs),
            mode="cross_sector" if self._cross_sector else "intra_sector",
        )
        return pairs

    # ------------------------------------------------------------------
    # Dynamic rotation helpers
    # ------------------------------------------------------------------

    def exclude_symbol(self, symbol: str, reason: str = "manual") -> None:
        """Manually exclude a symbol from the universe."""
        self._manually_excluded.add(symbol)
        logger.warning("symbol_excluded", symbol=symbol, reason=reason)

    def restore_symbol(self, symbol: str) -> None:
        """Restore a previously excluded symbol."""
        self._manually_excluded.discard(symbol)
        logger.info("symbol_restored", symbol=symbol)

    def add_symbol(self, symbol: str, sector: Union[str, Sector] = "unknown") -> None:
        """Dynamically add a symbol to the universe."""
        if symbol not in self._all_symbols:
            self._all_symbols.append(symbol)
            self._sector_map[symbol] = _normalize_sector(sector)
            logger.info("symbol_added", symbol=symbol, sector=self._sector_map[symbol])

    # ------------------------------------------------------------------
    # Dynamic refresh from scanner
    # ------------------------------------------------------------------

    def refresh_from_scanner(
        self,
        scanned_symbols: list,
        merge: bool = True,
    ) -> int:
        """
        Refresh the universe from IBKRUniverseScanner results.

        Args:
            scanned_symbols: List of ``ScannedSymbol`` from scanner.
            merge: If True, merge into existing universe (keep manually
                added symbols).  If False, replace entirely.

        Returns:
            Number of new symbols added.
        """
        from universe.scanner import ScannedSymbol

        new_count = 0

        if not merge:
            self._all_symbols.clear()
            self._sector_map.clear()

        existing = set(self._all_symbols)

        for sym in scanned_symbols:
            if not isinstance(sym, ScannedSymbol):
                continue
            ticker = sym.ticker.upper()
            if ticker not in existing:
                self._all_symbols.append(ticker)
                existing.add(ticker)
                new_count += 1
            # Always update sector classification (scanner may have fresher data)
            self._sector_map[ticker] = sym.sector

        logger.info(
            "universe_refreshed_from_scanner",
            new_symbols=new_count,
            total_symbols=len(self._all_symbols),
            sectors=len(set(self._sector_map.values())),
            mode="merge" if merge else "replace",
        )
        return new_count

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_active_symbols(self) -> list[str]:
        """Return symbols not manually excluded (for live trading runner)."""
        return [s for s in self._all_symbols if s not in self._manually_excluded]

    def get_symbols(
        self,
        as_of_date: Union[str, pd.Timestamp] | None = None,
    ) -> list[str]:
        """Return active symbols, optionally filtered by a historical date.

        .. warning::
            When *as_of_date* is provided the universe map is still the
            **current** (static) DEFAULT_SECTOR_MAP that contains only
            companies that survive to today.  Backtests using this list for
            historical periods are subject to survivorship bias.
            A point-in-time constituents file (``universe/constituents_history.csv``)
            would eliminate this limitation.

        Args:
            as_of_date: Historical date string (``"YYYY-MM-DD"``) or
                ``pd.Timestamp``.  When supplied a ``WARNING`` is emitted to
                alert back-testers of the potential bias.

        Returns:
            List of active (non-excluded) symbol strings.
        """
        symbols = self.get_active_symbols()
        if as_of_date is not None:
            logger.warning(
                "universe_survivorship_bias_possible",
                as_of_date=str(as_of_date),
                symbol_count=len(symbols),
                note=(
                    "Universe is static (current survivors only). "
                    "Symbols that delisted or merged before as_of_date are not excluded. "
                    "Sharpe ratios from backtests may be over-estimated. "
                    "Provide universe/constituents_history.csv for point-in-time filtering."
                ),
            )
        return symbols

    @property
    def all_symbols(self) -> list[str]:
        """Full symbol list (including manually excluded)."""
        return list(self._all_symbols)

    @property
    def sector_map(self) -> dict[str, str]:
        """Sector map as plain strings (unified format)."""
        return dict(self._sector_map)

    def get_sector_map_as_enum(self) -> dict[str, Sector]:
        """Backward-compat: return sector map with Sector enum values."""
        result: dict[str, Sector] = {}
        for sym, sec_str in self._sector_map.items():
            try:
                result[sym] = Sector(sec_str)
            except ValueError:
                result[sym] = Sector.UNKNOWN
        return result
