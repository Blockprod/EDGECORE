"""
Sprint 3.3 - YAML universe cleanup & duplicate detection.

Tests:
1. No duplicate symbols in any YAML config (dev, prod, test).
2. No fixed-NAV instruments in trading universe (stat-arb incompatible).
3. No known-invalid / defunct tickers.
4. Presence of audit-date comment.
5. Programmatic duplicate detector that can run in CI.
"""

import re
from collections import Counter
from pathlib import Path

import pytest
import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"

YAML_FILES = ["dev.yaml", "prod.yaml", "test.yaml"]

# Tickers that must NEVER appear (defunct, delisted, or bankrupt)
BLACKLISTED_TICKERS = {
    "SHLDQ",  # Sears (bankrupt)
    "LTCUQ",  # defunct
    "ENRN",   # Enron (fraud / delisted)
    "LHMN",   # Lehman Brothers (bankrupt)
}

# Bond/money-market ETFs that are quasi-fixed-nav - useless for stat-arb
FIXED_NAV_TICKERS = {
    "BIL",   # SPDR 1-3 Month T-Bill ETF
    "SHV",   # iShares Short Treasury Bond ETF
    "MINT",  # PIMCO Enhanced Short Maturity ETF
    "SGOV",  # iShares 0-3 Month Treasury Bond ETF
    "GBIL",  # Goldman Sachs Treasury Access 0-1 Year ETF
}


def _load_symbols(yaml_file: str) -> list:
    """Load symbols list from a YAML config file."""
    path = CONFIG_DIR / yaml_file
    if not path.exists():
        pytest.skip(f"{yaml_file} not found")
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("trading_universe", {}).get("symbols", [])


def _find_duplicates(symbols: list) -> list:
    """Return list of symbols that appear more than once."""
    counts = Counter(symbols)
    return [sym for sym, n in counts.items() if n > 1]


# ---------------------------------------------------------------------------
# 1. No duplicates
# ---------------------------------------------------------------------------

class TestNoDuplicateSymbols:
    """Every YAML config must have zero duplicate symbols."""

    @pytest.mark.parametrize("yaml_file", YAML_FILES)
    def test_no_duplicates(self, yaml_file):
        symbols = _load_symbols(yaml_file)
        dupes = _find_duplicates(symbols)
        assert dupes == [], f"Duplicates in {yaml_file}: {dupes}"


# ---------------------------------------------------------------------------
# 2. No blacklisted tickers
# ---------------------------------------------------------------------------

class TestNoBlacklistedTickers:
    """Defunct / collapsed tokens must not appear."""

    @pytest.mark.parametrize("yaml_file", YAML_FILES)
    def test_no_blacklisted(self, yaml_file):
        symbols = set(_load_symbols(yaml_file))
        found = symbols & BLACKLISTED_TICKERS
        assert found == set(), f"Blacklisted tickers in {yaml_file}: {found}"


# ---------------------------------------------------------------------------
# 3. No fixed-NAV ETFs in prod
# ---------------------------------------------------------------------------

class TestNoFixedNavETFs:
    """Fixed-NAV ETFs are pointless in a stat-arb universe."""

    @pytest.mark.parametrize("yaml_file", ["dev.yaml", "prod.yaml"])
    def test_no_fixed_nav_etfs(self, yaml_file):
        symbols = set(_load_symbols(yaml_file))
        found = symbols & FIXED_NAV_TICKERS
        assert found == set(), f"Fixed-NAV ETFs in {yaml_file}: {found}"


# ---------------------------------------------------------------------------
# 4. Audit-date comment present
# ---------------------------------------------------------------------------

class TestAuditDateComment:
    """Each config must have a 'validated YYYY-MM-DD' comment."""

    @pytest.mark.parametrize("yaml_file", ["dev.yaml", "prod.yaml"])
    def test_has_audit_date(self, yaml_file):
        path = CONFIG_DIR / yaml_file
        content = path.read_text(encoding="utf-8")
        # Expect pattern like "validated 2026-02-13" or "audit: 2026-02-13"
        pattern = r"(?:validated|audit|cleanup)\s+\d{4}-\d{2}-\d{2}"
        assert re.search(pattern, content, re.IGNORECASE), (
            f"{yaml_file} is missing an audit-date comment (pattern: {pattern})"
        )


# ---------------------------------------------------------------------------
# 5. Symbol format validation
# ---------------------------------------------------------------------------

class TestSymbolFormat:
    """Symbols must be valid US equity tickers (uppercase letters, 1-5 chars)."""

    @staticmethod
    def _is_equity_ticker(sym: str) -> bool:
        """Return True if symbol looks like a US equity ticker."""
        return bool(re.match(r'^[A-Z]{1,5}$', sym))

    @pytest.mark.parametrize("yaml_file", YAML_FILES)
    def test_symbol_format(self, yaml_file):
        symbols = _load_symbols(yaml_file)
        if not symbols:
            return
        for sym in symbols:
            assert self._is_equity_ticker(sym), (
                f"Invalid symbol format in {yaml_file}: '{sym}' "
                "(expected equity ticker like 'AAPL', uppercase 1-5 chars)"
            )


# ---------------------------------------------------------------------------
# 6. Minimum universe size
# ---------------------------------------------------------------------------

class TestMinimumUniverseSize:
    """Production universe should have enough symbols for pair discovery."""

    def test_prod_minimum_symbols(self):
        symbols = _load_symbols("prod.yaml")
        assert len(symbols) >= 50, f"Prod has only {len(symbols)} symbols (need >= 50)"

    def test_dev_minimum_symbols(self):
        symbols = _load_symbols("dev.yaml")
        assert len(symbols) >= 20, f"Dev has only {len(symbols)} symbols (need >= 20)"

    def test_test_minimum_symbols(self):
        symbols = _load_symbols("test.yaml")
        assert len(symbols) >= 5, f"Test has only {len(symbols)} symbols (need >= 5)"


# ---------------------------------------------------------------------------
# 7. Programmatic duplicate detector (reusable utility)
# ---------------------------------------------------------------------------

class TestDuplicateDetectorUtility:
    """The _find_duplicates helper itself must work correctly."""

    def test_no_dupes(self):
        assert _find_duplicates(["A", "B", "C"]) == []

    def test_one_dupe(self):
        assert _find_duplicates(["A", "B", "A"]) == ["A"]

    def test_multiple_dupes(self):
        dupes = _find_duplicates(["A", "B", "A", "C", "B"])
        assert set(dupes) == {"A", "B"}

    def test_empty_list(self):
        assert _find_duplicates([]) == []
