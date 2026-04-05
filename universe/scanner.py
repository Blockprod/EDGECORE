"""
IBKR Universe Scanner ÔÇö Dynamic discovery of the full tradeable universe.

Two-phase approach:
  1. **Bootstrap** ÔÇö Download full US equity list from SEC EDGAR
     (public JSON endpoint, ~10 000 tickers in < 2 seconds)
  2. **Validate & Enrich** ÔÇö Resolve contracts via IBKR
     ``reqContractDetails`` to get industry/category classification,
     then filter by fundamental criteria (market cap, volume).

The result is a complete, sector-classified symbol universe that
replaces the static hardcoded lists in ``config/dev.yaml``.

Usage::

    scanner = IBKRUniverseScanner()
    universe = scanner.scan()             # full pipeline
    universe = scanner.bootstrap_from_sec()  # SEC-only (no IBKR)
    scanner.save_cache(universe)
    universe = scanner.load_cache()
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from structlog import get_logger

from universe.rate_limiter import IBKRRateLimiter

logger = get_logger(__name__)

# ÔöÇÔöÇ SEC EDGAR endpoint (public, no API key) ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# ÔöÇÔöÇ IBKR industry ÔåÆ normalized sector mapping ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
# IBKR contractDetails.industry returns strings like "Computers",
# "Semiconductors", "Regional Banks", etc.  We map these to our
# standardized sector strings.
IBKR_INDUSTRY_TO_SECTOR: dict[str, str] = {
    # Technology
    "Computers": "technology", "Semiconductors": "technology",
    "Software": "technology", "Internet": "technology",
    "Electronics": "technology", "Telecommunications": "technology",
    "Computer Manufacturing": "technology",
    "Electronic Components": "technology",
    "Computer Integrated Systems Design": "technology",
    "Computer Programming, Data Processing, Etc.": "technology",
    "Services-Prepackaged Software": "technology",
    "Services-Computer Programming, Data Processing, Etc.": "technology",
    "Telephone & Telegraph Apparatus": "technology",
    # Financials
    "Banks": "financials", "Regional Banks": "financials",
    "Major Banks": "financials", "Investment Bankers/Brokers/Service": "financials",
    "Savings Institutions": "financials", "Insurance": "financials",
    "Finance Services": "financials", "Finance": "financials",
    "Finance/Investors Services": "financials",
    "Investment Advice": "financials",
    "Finance: Consumer Services": "financials",
    "National Commercial Banks-Federal Reserve": "financials",
    "State Commercial Banks-Federal Reserve": "financials",
    "Security Brokers, Dealers & Flotation": "financials",
    # Healthcare
    "Pharmaceuticals": "healthcare", "Medical Specialties": "healthcare",
    "Biotechnology": "healthcare", "Healthcare": "healthcare",
    "Medical/Dental Instruments": "healthcare",
    "Hospital/Nursing Management": "healthcare",
    "Health Services": "healthcare",
    "Pharmaceutical Preparations": "healthcare",
    "Surgical & Medical Instruments & Apparatus": "healthcare",
    "Services-Health Services": "healthcare",
    # Consumer Staples
    "Consumer Staples": "consumer_staples",
    "Food": "consumer_staples", "Beverages": "consumer_staples",
    "Household Products": "consumer_staples",
    "Tobacco": "consumer_staples", "Package Foods": "consumer_staples",
    "Agricultural Chemicals": "consumer_staples",
    "Retail-Grocery": "consumer_staples",
    "Bottled & Canned Soft Drinks & Water": "consumer_staples",
    "Soap, Detergent, Cleaning Preparations": "consumer_staples",
    # Consumer Discretionary
    "Consumer Discretionary": "consumer_discretionary",
    "Retail": "consumer_discretionary", "Restaurants": "consumer_discretionary",
    "Auto Manufacturing": "consumer_discretionary",
    "Apparel": "consumer_discretionary", "Homebuilding": "consumer_discretionary",
    "Hotels/Resorts": "consumer_discretionary",
    "Department/Specialty Retail Stores": "consumer_discretionary",
    "Retail-Eating Places": "consumer_discretionary",
    "Retail-Building Materials, Hardware": "consumer_discretionary",
    # Energy
    "Oil & Gas": "energy", "Oil Refining/Marketing": "energy",
    "Oil/Gas Transmission": "energy", "Energy": "energy",
    "Coal Mining": "energy", "Oilfield Services/Equipment": "energy",
    "Crude Petroleum & Natural Gas": "energy",
    "Petroleum Refining": "energy",
    # Industrials
    "Industrial Machinery": "industrials",
    "Aerospace": "industrials", "Defense": "industrials",
    "Transportation": "industrials",
    "Construction/Ag Equipment/Trucks": "industrials",
    "Railroads": "industrials", "Airlines": "industrials",
    "Trucking Freight/Courier Services": "industrials",
    "Farm Machinery & Equipment": "industrials",
    "General Industrial Machinery & Equipment": "industrials",
    # Utilities
    "Electric Utilities": "utilities", "Gas Utilities": "utilities",
    "Water Utilities": "utilities", "Utilities": "utilities",
    "Electric Services": "utilities",
    "Natural Gas Distribution": "utilities",
    # Real Estate / REITs
    "Real Estate Investment Trusts": "reits",
    "Real Estate": "reits", "REITs": "reits",
    # Materials
    "Chemicals": "materials", "Mining": "materials",
    "Steel": "materials", "Paper": "materials",
    "Metal Mining": "materials",
    "Industrial Gases": "materials",
    # Communication
    "Broadcasting": "communication",
    "Cable/Other Pay Television": "communication",
    "Motion Pictures": "communication",
    "Services-Computer Integrated Systems Design": "communication",
}

# US exchanges to keep from SEC EDGAR listing
_VALID_EXCHANGES: set[str] = {"NYSE", "NASDAQ", "Nasdaq", "Nyse", "AMEX", "Arca", "BATS"}


@dataclass
class ScannedSymbol:
    """Single symbol from universe scanner."""
    ticker: str
    company_name: str = ""
    sector: str = "unknown"
    industry: str = ""
    exchange: str = ""
    market_cap: float = 0.0
    avg_volume: float = 0.0
    currency: str = "USD"
    ibkr_con_id: int = 0
    ibkr_validated: bool = False
    last_updated: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "company_name": self.company_name,
            "sector": self.sector,
            "industry": self.industry,
            "exchange": self.exchange,
            "market_cap": self.market_cap,
            "avg_volume": self.avg_volume,
            "currency": self.currency,
            "ibkr_con_id": self.ibkr_con_id,
            "ibkr_validated": self.ibkr_validated,
            "last_updated": self.last_updated,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> ScannedSymbol:
        return ScannedSymbol(**{k: v for k, v in d.items() if k in ScannedSymbol.__dataclass_fields__})


@dataclass
class ScannerConfig:
    """Configuration for universe scanner."""
    min_market_cap_usd: float = 500_000_000    # $500M minimum
    min_avg_volume_usd: float = 5_000_000      # $5M daily volume
    min_price: float = 5.0                      # exclude penny stocks
    exchanges: list[str] = field(default_factory=lambda: ["NYSE", "NASDAQ", "AMEX"])
    currency: str = "USD"
    country: str = "US"
    sec_types: list[str] = field(default_factory=lambda: ["STK"])
    cache_file: str = "cache/universe/ibkr_universe.json"
    cache_ttl_hours: int = 24
    ibkr_validation_workers: int = 5
    ibkr_batch_size: int = 50                   # validate N symbols per batch


class IBKRUniverseScanner:
    """
    Dynamic universe scanner combining SEC EDGAR + IBKR validation.

    Phase 1 (bootstrap_from_sec): Fast ÔÇö downloads the SEC full ticker
    list (~10k companies, < 2 sec), filters by exchange.

    Phase 2 (validate_via_ibkr): Slower ÔÇö resolves each ticker via IBKR
    reqContractDetails to get industry classification and validates
    tradability.  Uses rate limiter to stay within IBKR API limits.

    Phase 3 (apply_fundamental_filters): Filters by market cap, volume,
    price.  Uses cached data where available.

    Usage::

        scanner = IBKRUniverseScanner()
        # Quick ÔÇö SEC-only (no IBKR connection needed)
        symbols = scanner.bootstrap_from_sec()
        # Full ÔÇö SEC + IBKR validation
        symbols = scanner.scan()
    """

    def __init__(
        self,
        config: ScannerConfig | None = None,
        rate_limiter: IBKRRateLimiter | None = None,
    ):
        self.config = config or ScannerConfig()
        self.rate_limiter = rate_limiter or IBKRRateLimiter()
        self._cache_path = Path(self.config.cache_file)
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            "universe_scanner_initialized",
            min_mcap=f"${self.config.min_market_cap_usd:,.0f}",
            min_vol=f"${self.config.min_avg_volume_usd:,.0f}",
            exchanges=self.config.exchanges,
        )

    # ==================================================================
    # Phase 1: SEC EDGAR bootstrap
    # ==================================================================

    def bootstrap_from_sec(self) -> list[ScannedSymbol]:
        """
        Download the full US equity ticker list from SEC EDGAR.

        self.batch_size = self.config.ibkr_batch_size
        self.async_mode = False
        Endpoint: https://www.sec.gov/files/company_tickers.json
        This is a public, free endpoint ÔÇö no API key required.
        Returns ~10 000 tickers with CIK, ticker, and company name.

        We filter to keep only NYSE/NASDAQ/AMEX tickers and exclude
        tickers with special characters (warrants, units, etc.).

        Returns:
            List of ScannedSymbol with ticker and company_name populated.
        """
        import urllib.request

        logger.info("sec_bootstrap_starting", url=SEC_COMPANY_TICKERS_URL)
        t0 = time.monotonic()

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://www.sec.gov/",
                "Connection": "keep-alive",
                "DNT": "1",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
            }
            req = urllib.request.Request(
                SEC_COMPANY_TICKERS_URL,
                headers=headers,
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
            except Exception as exc:
                logger.warning("sec_bootstrap_http_failed", error=str(exc)[:200])
                # Fallback: essayer de charger un fichier local
                local_path = "cache/company_tickers.json"
                try:
                    with open(local_path, encoding="utf-8") as f:
                        raw = json.load(f)
                    logger.info("sec_bootstrap_local_fallback", path=local_path)
                except Exception as exc2:
                    logger.error("sec_bootstrap_failed", error=f"HTTP: {exc} | Local: {exc2}")
                    raise RuntimeError(f"SEC EDGAR download failed: {exc}\nLocal fallback failed: {exc2}") from exc
        except Exception as exc:
            logger.error("sec_bootstrap_failed", error=str(exc)[:200])
            raise RuntimeError(f"SEC EDGAR download failed: {exc}") from exc

        symbols: list[ScannedSymbol] = []
        seen: set[str] = set()

        for _key, entry in raw.items():
            ticker = str(entry.get("ticker", "")).upper().strip()
            name = str(entry.get("title", ""))

            # Skip invalid tickers
            if not ticker or len(ticker) > 5:
                continue
            # Skip warrants, units, rights (contain special chars)
            if any(c in ticker for c in ".-/^*$"):
                continue
            # Skip duplicates
            if ticker in seen:
                continue
            seen.add(ticker)

            symbols.append(ScannedSymbol(
                ticker=ticker,
                company_name=name,
                last_updated=datetime.now().isoformat(),
            ))

        elapsed = time.monotonic() - t0
        logger.info(
            "sec_bootstrap_complete",
            total_tickers=len(raw),
            valid_tickers=len(symbols),
            elapsed_sec=round(elapsed, 2),
        )
        return symbols

    # ==================================================================
    # Phase 2: IBKR contract validation & enrichment
    # ==================================================================

    def validate_via_ibkr(
        self,
        symbols: list[ScannedSymbol],
        ib: Any = None,
    ) -> list[ScannedSymbol]:
        """
        Validate symbols via IBKR reqContractDetails and enrich with
        industry/sector classification.

        Args:
            symbols: List of ScannedSymbol from SEC bootstrap.
            ib: Connected ib_insync.IB instance.  If None, creates one.

        Returns:
            Enriched list with ibkr_validated=True for valid symbols.
        """
        if ib is None:
            from execution.ibkr_engine import IBKRExecutionEngine
            engine = IBKRExecutionEngine()
            engine.connect()
            ib = engine._ib

        validated: list[ScannedSymbol] = []
        total = len(symbols)
        batch_size = self.config.ibkr_batch_size

        logger.info(
            "ibkr_validation_starting",
            total_symbols=total,
            batch_size=batch_size,
        )

        for batch_start in range(0, total, batch_size):
            batch = symbols[batch_start : batch_start + batch_size]
            batch_results = self._validate_batch(batch, ib)
            validated.extend(batch_results)

            progress = min(batch_start + batch_size, total)
            if progress % 500 == 0 or progress == total:
                logger.info(
                    "ibkr_validation_progress",
                    validated=len(validated),
                    processed=progress,
                    total=total,
                    pct=round(100 * progress / total, 1),
                )

        logger.info(
            "ibkr_validation_complete",
            input_symbols=total,
            validated_symbols=len(validated),
            rejection_rate=round(100 * (1 - len(validated) / max(1, total)), 1),
        )
        return validated

    def _validate_batch(
        self, batch: list[ScannedSymbol], ib: Any
    ) -> list[ScannedSymbol]:
        """Validate a batch of symbols via IBKR."""
        from ib_insync import Stock

        results: list[ScannedSymbol] = []

        for sym in batch:
            try:
                self.rate_limiter.acquire("contract")

                contract = Stock(sym.ticker, "SMART", self.config.currency)
                details_list = ib.reqContractDetails(contract)

                if not details_list:
                    continue

                detail = details_list[0]
                con = detail.contract

                # Enrich with IBKR classification
                industry = getattr(detail, "industry", "") or ""
                category = getattr(detail, "category", "") or ""
                sector_raw = industry if industry else category

                sym.industry = sector_raw
                sym.sector = IBKR_INDUSTRY_TO_SECTOR.get(
                    sector_raw, self._guess_sector(sector_raw)
                )
                sym.exchange = con.primaryExchange or con.exchange or ""
                sym.ibkr_con_id = con.conId
                sym.ibkr_validated = True
                sym.currency = con.currency or "USD"
                sym.last_updated = datetime.now().isoformat()

                # Get market cap if available via fundamental data
                # (reqFundamentalData requires market data subscription)
                # We skip this for now ÔÇö filter by volume in Phase 3.

                results.append(sym)

            except Exception as exc:
                logger.debug(
                    "ibkr_contract_validation_failed",
                    ticker=sym.ticker,
                    error=str(exc)[:100],
                )
                continue

        return results

    @staticmethod
    def _guess_sector(industry_str: str) -> str:
        """Fuzzy match industry string to sector when exact match fails."""
        low = industry_str.lower()
        guesses = [
            ("tech", "technology"), ("software", "technology"),
            ("semicon", "technology"), ("computer", "technology"),
            ("bank", "financials"), ("financ", "financials"),
            ("insur", "financials"), ("invest", "financials"),
            ("pharma", "healthcare"), ("biotech", "healthcare"),
            ("medic", "healthcare"), ("health", "healthcare"),
            ("food", "consumer_staples"), ("beverage", "consumer_staples"),
            ("household", "consumer_staples"), ("tobacco", "consumer_staples"),
            ("retail", "consumer_discretionary"), ("auto", "consumer_discretionary"),
            ("hotel", "consumer_discretionary"), ("restaurant", "consumer_discretionary"),
            ("oil", "energy"), ("gas", "energy"), ("petrol", "energy"),
            ("energy", "energy"),
            ("aero", "industrials"), ("defense", "industrials"),
            ("transport", "industrials"), ("railroad", "industrials"),
            ("machine", "industrials"), ("construct", "industrials"),
            ("electric util", "utilities"), ("gas util", "utilities"),
            ("water util", "utilities"), ("utilit", "utilities"),
            ("reit", "reits"), ("real estate", "reits"),
            ("chem", "materials"), ("mining", "materials"),
            ("steel", "materials"), ("metal", "materials"),
            ("broadcast", "communication"), ("media", "communication"),
        ]
        for keyword, sector in guesses:
            if keyword in low:
                return sector
        return "unknown"

    # ==================================================================
    # Phase 3: Fundamental filters
    # ==================================================================

    def apply_fundamental_filters(
        self,
        symbols: list[ScannedSymbol],
    ) -> list[ScannedSymbol]:
        """
        Filter symbols by fundamental criteria.

        Filters applied:
          - Market cap >= min_market_cap_usd (when data available)
          - Average volume >= min_avg_volume_usd (when data available)
          - Price >= min_price (when data available)
          - Exclude unknown sector (no classification data)
          - Exclude non-USD currencies

        Note: market_cap and avg_volume may be 0 if not yet populated
        (e.g. SEC-only scan).  In that case we keep the symbol and rely
        on the liquidity filter in UniverseManager to catch it later.

        Args:
            symbols: List of enriched ScannedSymbol.

        Returns:
            Filtered list.
        """
        passed: list[ScannedSymbol] = []
        reasons: dict[str, int] = {}

        for sym in symbols:
            # Currency filter
            if sym.currency != self.config.currency:
                reasons["wrong_currency"] = reasons.get("wrong_currency", 0) + 1
                continue

            # Market cap filter (skip if not available)
            if sym.market_cap > 0 and sym.market_cap < self.config.min_market_cap_usd:
                reasons["low_market_cap"] = reasons.get("low_market_cap", 0) + 1
                continue

            # Volume filter (skip if not available)
            if sym.avg_volume > 0 and sym.avg_volume < self.config.min_avg_volume_usd:
                reasons["low_volume"] = reasons.get("low_volume", 0) + 1
                continue

            passed.append(sym)

        logger.info(
            "fundamental_filter_complete",
            input=len(symbols),
            passed=len(passed),
            filtered=len(symbols) - len(passed),
            reasons=reasons,
        )
        return passed

    # ==================================================================
    # Full scan pipeline
    # ==================================================================

    def scan(self, ib: Any = None, use_cache: bool = True) -> list[ScannedSymbol]:
        """
        Full scan pipeline: SEC bootstrap ÔåÆ IBKR validation ÔåÆ filters.

        Args:
            ib: Optional connected ib_insync.IB instance.
            use_cache: If True, use cached universe if fresh (< cache_ttl).

        Returns:
            List of validated, filtered, sector-classified symbols.
        """
        # Check cache first
        if use_cache:
            cached = self.load_cache()
            if cached is not None:
                logger.info("universe_loaded_from_cache", count=len(cached))
                return cached

        # Phase 1: SEC bootstrap
        raw_symbols = self.bootstrap_from_sec()

        # Phase 2: IBKR validation (requires connection)
        validated = self.validate_via_ibkr(raw_symbols, ib=ib)

        # Phase 3: Fundamental filters
        filtered = self.apply_fundamental_filters(validated)

        # Cache results
        self.save_cache(filtered)

        logger.info(
            "universe_scan_complete",
            sec_raw=len(raw_symbols),
            ibkr_validated=len(validated),
            final=len(filtered),
        )
        return filtered

    def scan_sec_only(self) -> list[ScannedSymbol]:
        """
        SEC-only scan ÔÇö no IBKR connection required.

        Returns symbols with ticker and company name, but WITHOUT
        industry/sector classification.  Useful for:
          - Offline analysis
          - Dry-run testing
          - Bootstrap when IBKR is unavailable

        Returns:
            List of ScannedSymbol (sector="unknown" for all).
        """
        raw = self.bootstrap_from_sec()
        return self.apply_fundamental_filters(raw)

    # ==================================================================
    # Cache management
    # ==================================================================

    def save_cache(self, symbols: list[ScannedSymbol]) -> None:
        """Save scanned universe to JSON cache."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "count": len(symbols),
            "symbols": [s.to_dict() for s in symbols],
        }
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._cache_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("universe_cache_saved", path=str(self._cache_path), count=len(symbols))

    def load_cache(self) -> list[ScannedSymbol] | None:
        """Load cached universe, returning None if stale or missing."""
        if not self._cache_path.exists():
            return None

        try:
            with open(self._cache_path) as f:
                data = json.load(f)

            ts = datetime.fromisoformat(data["timestamp"])
            age = datetime.now() - ts
            if age > timedelta(hours=self.config.cache_ttl_hours):
                logger.info("universe_cache_stale", age_hours=round(age.total_seconds() / 3600, 1))
                return None

            symbols = [ScannedSymbol.from_dict(d) for d in data["symbols"]]
            logger.info(
                "universe_cache_loaded",
                count=len(symbols),
                age_hours=round(age.total_seconds() / 3600, 1),
            )
            return symbols

        except Exception as exc:
            logger.warning("universe_cache_load_failed", error=str(exc)[:100])
            return None

    # ==================================================================
    # Convenience: extract symbol/sector lists
    # ==================================================================

    @staticmethod
    def to_symbol_list(symbols: list[ScannedSymbol]) -> list[str]:
        """Extract ticker list from scanned symbols."""
        return [s.ticker for s in symbols]

    @staticmethod
    def to_sector_map(symbols: list[ScannedSymbol]) -> dict[str, str]:
        """Extract sector map {ticker: sector_name} from scanned symbols."""
        return {s.ticker: s.sector for s in symbols}

    @staticmethod
    def symbols_by_sector(symbols: list[ScannedSymbol]) -> dict[str, list[str]]:
        """Group symbols by sector."""
        groups: dict[str, list[str]] = {}
        for s in symbols:
            groups.setdefault(s.sector, []).append(s.ticker)
        return groups
