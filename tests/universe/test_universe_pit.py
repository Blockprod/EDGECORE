"""
C-01 — Point-in-time (PIT) universe tests.

Validates that UniverseManager correctly filters symbols based on
date_in / date_out from universe_history.csv, eliminating survivorship bias
in backtests.
"""

from __future__ import annotations

import io
import textwrap

import pandas as pd
import pytest

from universe.manager import UniverseManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CSV_CONTENT = textwrap.dedent("""\
    symbol,sector,date_in,date_out
    AAPL,technology,2000-01-01,
    MSFT,technology,2000-01-01,
    LMAN,financials,2000-01-01,2010-06-30
    GONE,energy,2000-01-01,2005-12-31
    FUTURE,healthcare,2015-01-01,
""")


def _make_manager_with_csv(csv_text: str) -> UniverseManager:
    """Build a UniverseManager with a custom in-memory CSV (no auto-load)."""
    mgr = UniverseManager(
        symbols=["AAPL", "MSFT", "LMAN", "GONE", "FUTURE"],
        sector_map={
            "AAPL": "technology",
            "MSFT": "technology",
            "LMAN": "financials",
            "GONE": "energy",
            "FUTURE": "healthcare",
        },
    )
    mgr.load_constituents_csv(io.StringIO(csv_text))
    return mgr


# ---------------------------------------------------------------------------
# Tests: load_constituents_csv
# ---------------------------------------------------------------------------


class TestLoadConstituentsCsv:
    def test_loads_successfully(self):
        mgr = _make_manager_with_csv(_CSV_CONTENT)
        assert mgr._history_df is not None
        assert len(mgr._history_df) == 5

    def test_history_df_columns(self):
        mgr = _make_manager_with_csv(_CSV_CONTENT)
        assert mgr._history_df is not None
        expected = {"symbol", "sector", "date_in", "date_out"}
        assert expected.issubset(set(mgr._history_df.columns))

    def test_date_in_is_datetime(self):
        mgr = _make_manager_with_csv(_CSV_CONTENT)
        assert mgr._history_df is not None
        assert pd.api.types.is_datetime64_any_dtype(mgr._history_df["date_in"])

    def test_date_out_is_datetime_or_nat(self):
        mgr = _make_manager_with_csv(_CSV_CONTENT)
        assert mgr._history_df is not None
        # All date_out values are either NaT or datetime
        for val in mgr._history_df["date_out"]:
            assert pd.isna(val) or isinstance(val, pd.Timestamp)

    def test_missing_required_column_raises(self):
        bad_csv = "symbol,sector\nAAPL,technology\n"
        mgr = UniverseManager(symbols=["AAPL"], sector_map={"AAPL": "technology"})
        with pytest.raises(ValueError, match="missing columns"):
            mgr.load_constituents_csv(io.StringIO(bad_csv))

    def test_symbol_uppercased(self):
        csv = "symbol,sector,date_in,date_out\naapl,technology,2000-01-01,\n"
        mgr = UniverseManager(symbols=["AAPL"], sector_map={"AAPL": "technology"})
        mgr.load_constituents_csv(io.StringIO(csv))
        assert mgr._history_df is not None
        assert "AAPL" in set(mgr._history_df["symbol"])


# ---------------------------------------------------------------------------
# Tests: get_symbols_as_of
# ---------------------------------------------------------------------------


class TestGetSymbolsAsOf:
    def test_active_symbol_included(self):
        mgr = _make_manager_with_csv(_CSV_CONTENT)
        syms = mgr.get_symbols_as_of("2008-01-01")
        assert "AAPL" in syms
        assert "MSFT" in syms

    def test_delisted_symbol_excluded_after_date_out(self):
        mgr = _make_manager_with_csv(_CSV_CONTENT)
        # GONE was delisted 2005-12-31
        syms_before = mgr.get_symbols_as_of("2005-01-01")
        syms_after = mgr.get_symbols_as_of("2006-01-01")
        assert "GONE" in syms_before
        assert "GONE" not in syms_after

    def test_delisted_on_exact_date_out_excluded(self):
        mgr = _make_manager_with_csv(_CSV_CONTENT)
        # date_out = 2005-12-31 → excluded on that date (date_out > ts is False)
        syms = mgr.get_symbols_as_of("2005-12-31")
        assert "GONE" not in syms

    def test_future_symbol_excluded_before_date_in(self):
        mgr = _make_manager_with_csv(_CSV_CONTENT)
        # FUTURE listed 2015-01-01
        syms = mgr.get_symbols_as_of("2014-12-31")
        assert "FUTURE" not in syms

    def test_future_symbol_included_on_date_in(self):
        mgr = _make_manager_with_csv(_CSV_CONTENT)
        syms = mgr.get_symbols_as_of("2015-01-01")
        assert "FUTURE" in syms

    def test_symbol_excluded_after_delisting(self):
        mgr = _make_manager_with_csv(_CSV_CONTENT)
        # LMAN active up to 2010-06-30
        syms_active = mgr.get_symbols_as_of("2010-01-01")
        syms_delisted = mgr.get_symbols_as_of("2010-07-01")
        assert "LMAN" in syms_active
        assert "LMAN" not in syms_delisted

    def test_manually_excluded_symbol_not_returned(self):
        mgr = _make_manager_with_csv(_CSV_CONTENT)
        mgr.exclude_symbol("AAPL", reason="test")
        syms = mgr.get_symbols_as_of("2008-01-01")
        assert "AAPL" not in syms

    def test_returns_list_of_strings(self):
        mgr = _make_manager_with_csv(_CSV_CONTENT)
        syms = mgr.get_symbols_as_of("2008-01-01")
        assert isinstance(syms, list)
        assert all(isinstance(s, str) for s in syms)

    def test_empty_date_range(self):
        """Very early date → no symbols yet listed."""
        mgr = _make_manager_with_csv(_CSV_CONTENT)
        syms = mgr.get_symbols_as_of("1990-01-01")
        assert len(syms) == 0


# ---------------------------------------------------------------------------
# Tests: get_symbols() with as_of_date
# ---------------------------------------------------------------------------


class TestGetSymbolsAsOfDate:
    def test_get_symbols_delegates_to_pit_when_csv_loaded(self):
        mgr = _make_manager_with_csv(_CSV_CONTENT)
        # GONE was delisted in 2006
        syms = mgr.get_symbols(as_of_date="2010-01-01")
        assert "GONE" not in syms

    def test_get_symbols_no_date_returns_active(self):
        mgr = _make_manager_with_csv(_CSV_CONTENT)
        syms = mgr.get_symbols()
        # Should return all non-excluded symbols regardless of CSV
        assert "AAPL" in syms

    def test_get_symbols_no_csv_no_date_returns_active(self):
        mgr = UniverseManager(
            symbols=["AAPL", "MSFT"],
            sector_map={"AAPL": "technology", "MSFT": "technology"},
        )
        # Avoid auto-loading by checking if CSV was loaded
        # (auto-load only happens if default CSV exists)
        if mgr._history_df is None:
            syms = mgr.get_symbols()
            assert "AAPL" in syms
            assert "MSFT" in syms


# ---------------------------------------------------------------------------
# Tests: survivorship bias warning (no CSV)
# ---------------------------------------------------------------------------


class TestSurvivorshipBiasWarning:
    def test_warning_emitted_when_no_csv_and_as_of_date(self):
        mgr = UniverseManager(
            symbols=["AAPL"],
            sector_map={"AAPL": "technology"},
        )
        mgr._history_df = None  # Force no history
        import structlog.testing

        with structlog.testing.capture_logs() as logs:
            mgr.get_symbols_as_of("2010-01-01")

        events = [log["event"] for log in logs]
        assert "universe_survivorship_bias_possible" in events


# ---------------------------------------------------------------------------
# Tests: auto-load from default CSV path
# ---------------------------------------------------------------------------


class TestAutoLoad:
    def test_auto_load_flag_when_csv_exists(self, tmp_path, monkeypatch):
        """When the default CSV exists, the manager loads it automatically."""
        csv_content = "symbol,sector,date_in,date_out\nAAPL,technology,2000-01-01,\n"
        csv_file = tmp_path / "universe_history.csv"
        csv_file.write_text(csv_content)

        monkeypatch.setattr("universe.manager._DEFAULT_HISTORY_CSV", csv_file)

        mgr = UniverseManager(symbols=["AAPL"], sector_map={"AAPL": "technology"})
        assert mgr._history_df is not None

    def test_no_crash_when_default_csv_missing(self, tmp_path, monkeypatch):
        """Missing default CSV: no error, history stays None."""
        monkeypatch.setattr(
            "universe.manager._DEFAULT_HISTORY_CSV",
            tmp_path / "nonexistent.csv",
        )
        mgr = UniverseManager(symbols=["AAPL"], sector_map={"AAPL": "technology"})
        assert mgr._history_df is None


# ---------------------------------------------------------------------------
# Tests: StrategyBacktestSimulator integration (smoke)
# ---------------------------------------------------------------------------


class TestSimulatorPITIntegration:
    def test_simulator_accepts_universe_manager(self):
        """StrategyBacktestSimulator can be instantiated with universe_manager."""
        from backtests.strategy_simulator import StrategyBacktestSimulator

        mgr = _make_manager_with_csv(_CSV_CONTENT)
        sim = StrategyBacktestSimulator(universe_manager=mgr)
        assert sim.universe_manager is mgr

    def test_simulator_default_universe_manager_is_none(self):
        from backtests.strategy_simulator import StrategyBacktestSimulator

        sim = StrategyBacktestSimulator()
        assert sim.universe_manager is None
