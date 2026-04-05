"""
Corporate actions provider — splits and dividends (IBKR-native).

Responsibilities:
- Detect corporate events (splits, dividends) by comparing IBKR
  ADJUSTED_LAST vs TRADES price series: when the two series diverge
  above a threshold on a given bar, that bar is flagged as an ex-date.
- Cache results to disk (data/cache/corporate_actions/) to avoid
  repeated network calls (TTL = 7 days).
- Mark ex-dates in a prices DataFrame so that downstream components
  (EventDrivenBacktester, etc.) can skip entries on those bars.

Detection algorithm::

    adj_ret  = ADJUSTED_LAST.pct_change()
    raw_ret  = TRADES.pct_change()
    exdate   = |adj_ret - raw_ret| > threshold_pct

The default threshold is 0.5 % (0.005).  Dividends typically diverge by
≥ 0.5 % of stock price; stock splits cause much larger divergence.

Usage::

    from data.corporate_actions import CorporateActionsProvider

    provider = CorporateActionsProvider()
    exdates  = provider.get_exdates("AAPL", "2020-01-01", "2024-01-01")
    prices_marked = provider.mark_exdates(prices_df, ["AAPL", "MSFT"])
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from structlog import get_logger

if TYPE_CHECKING:
    from execution.ibkr_engine import IBGatewaySync

logger = get_logger(__name__)

_CACHE_DIR = Path("data/cache/corporate_actions")
_CACHE_TTL_DAYS = 7  # Re-fetch after 7 days
_DEFAULT_DURATION = "11 Y"  # Max IBKR daily history window


def _cache_path(symbol: str) -> Path:
    return _CACHE_DIR / f"{symbol.upper()}.json"


def _load_cache(symbol: str) -> dict | None:
    """Return cached corporate-action data if fresh, else None."""
    p = _cache_path(symbol)
    if not p.exists():
        return None
    try:
        payload: dict = json.loads(p.read_text(encoding="utf-8"))
        fetched_on = date.fromisoformat(payload.get("fetched_on", "2000-01-01"))
        if (date.today() - fetched_on).days > _CACHE_TTL_DAYS:
            return None
        return payload
    except Exception as exc:
        logger.warning("corporate_actions_cache_read_failed", symbol=symbol, error=str(exc)[:120])
        return None


def _save_cache(symbol: str, exdates: list[str]) -> None:
    """Persist corporate-action data to disk cache."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_on": date.today().isoformat(),
        "splits": [],  # reserved — detection is unified via divergence
        "exdates": exdates,
    }
    try:
        _cache_path(symbol).write_text(json.dumps(payload), encoding="utf-8")
    except Exception as exc:
        logger.warning("corporate_actions_cache_write_failed", symbol=symbol, error=str(exc)[:120])


class CorporateActionsProvider:
    """
    Detects corporate events (splits + dividends) from IBKR historical data.

    Strategy: compare daily returns of ADJUSTED_LAST vs TRADES price series.
    When the two series diverge by more than *threshold_pct* on a single bar,
    a corporate event is inferred for that date.

    Zero external dependencies — uses the same IBKR connection as live trading.

    Parameters
    ----------
    engine : IBGatewaySync or None
        Optional injected IBKR gateway.  If None, a dedicated connection
        (client_id = 5001) is created lazily on first use.
    threshold_pct : float
        Minimum return divergence to flag a bar as an ex-date (default 0.005).
    use_cache : bool
        Whether to use the disk cache (default True).
        Set to False in tests for deterministic behaviour.
    """

    _DEDICATED_CLIENT_ID = 5001

    def __init__(
        self,
        engine: IBGatewaySync | None = None,
        threshold_pct: float = 0.005,
        use_cache: bool = True,
    ) -> None:
        self._engine = engine
        self._threshold_pct = threshold_pct
        self._use_cache = use_cache
        self._owns_engine = engine is None  # True → we may create it lazily

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_exdates(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> list[pd.Timestamp]:
        """
        Return all corporate-event ex-dates for *symbol* in [start, end].

        Returns an empty list if IBKR is unavailable or no events detected.
        """
        all_exdates = self._fetch(symbol)

        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)

        result = sorted({ts for ts in all_exdates if start_ts <= ts <= end_ts})
        logger.debug(
            "corporate_actions_exdates",
            symbol=symbol,
            count=len(result),
            start=start_date,
            end=end_date,
        )
        return result

    def mark_exdates(
        self,
        prices_df: pd.DataFrame,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Add an ``is_exdate`` boolean column to *prices_df*.

        A bar is marked ``True`` if any symbol in *symbols* has a corporate
        event on that date.  Used by EventDrivenBacktester to suppress new
        entries on structurally unstable bars.

        Parameters
        ----------
        prices_df : pd.DataFrame
            Index = DatetimeIndex, columns = symbol names.
        symbols : list[str] or None
            Symbols to check.  Defaults to all columns in *prices_df*.

        Returns
        -------
        pd.DataFrame
            The original DataFrame with an additional ``is_exdate`` column.
        """
        if symbols is None:
            symbols = list(prices_df.columns)

        if prices_df.empty:
            prices_df = prices_df.copy()
            prices_df["is_exdate"] = False
            return prices_df

        start_date = str(prices_df.index.min())[:10]
        end_date = str(prices_df.index.max())[:10]

        all_exdates: set[pd.Timestamp] = set()
        for sym in symbols:
            for ts in self.get_exdates(sym, start_date, end_date):
                all_exdates.add(ts.normalize())

        prices_df = prices_df.copy()
        prices_df["is_exdate"] = prices_df.index.normalize().map(lambda d: d in all_exdates)  # type: ignore[arg-type]
        logger.info(
            "corporate_actions_marked",
            total_exdate_bars=int(prices_df["is_exdate"].sum()),
            symbols_checked=len(symbols),
        )
        return prices_df

    # ------------------------------------------------------------------
    # Internal fetch logic
    # ------------------------------------------------------------------

    def _fetch(self, symbol: str) -> list[pd.Timestamp]:
        """Return all corporate-event timestamps for symbol (cache → IBKR)."""
        if self._use_cache:
            cached = _load_cache(symbol)
            if cached is not None:
                return [pd.Timestamp(d) for d in cached.get("exdates", [])]

        exdates = self._detect_from_ibkr(symbol)

        if self._use_cache:
            _save_cache(
                symbol=symbol,
                exdates=[str(ts.date()) for ts in exdates],
            )

        return exdates

    def _ensure_engine(self) -> IBGatewaySync | None:
        """Return (or lazily create) the IBKR gateway engine."""
        if self._engine is not None:
            return self._engine

        try:
            from execution.ibkr_engine import IBGatewaySync as _IBGatewaySync  # noqa: PLC0415

            self._engine = _IBGatewaySync(client_id=self._DEDICATED_CLIENT_ID)
        except Exception as exc:
            logger.warning(
                "corporate_actions_engine_init_failed",
                error=str(exc)[:200],
                hint="IBKR Gateway not available — corporate action detection disabled",
            )
            self._engine = None

        return self._engine

    def _detect_from_ibkr(self, symbol: str) -> list[pd.Timestamp]:
        """
        Detect corporate-event ex-dates by comparing ADJUSTED_LAST vs TRADES.

        For each daily bar, computes::

            divergence = |pct_change(ADJUSTED_LAST) - pct_change(TRADES)|

        If divergence > threshold_pct, the bar is flagged as an ex-date.
        A dividend or split causes the adjusted series to be retroactively
        rescaled, producing a one-day step-change in return space on the
        event date.

        Returns an empty list (with a warning) if IBKR is unavailable.
        """
        engine = self._ensure_engine()
        if engine is None:
            return []

        try:
            adj_bars = engine.get_historical_data(
                symbol=symbol,
                duration=_DEFAULT_DURATION,
                bar_size="1 day",
                what_to_show="ADJUSTED_LAST",
            )
            raw_bars = engine.get_historical_data(
                symbol=symbol,
                duration=_DEFAULT_DURATION,
                bar_size="1 day",
                what_to_show="TRADES",
            )
        except Exception as exc:
            logger.warning(
                "corporate_actions_ibkr_fetch_failed",
                symbol=symbol,
                error=str(exc)[:200],
            )
            return []

        if not adj_bars or not raw_bars:
            logger.warning(
                "corporate_actions_empty_bars",
                symbol=symbol,
                adj_count=len(adj_bars) if adj_bars else 0,
                raw_count=len(raw_bars) if raw_bars else 0,
            )
            return []

        # bar.date format for daily bars with formatDate=1: "YYYYMMDD"
        adj = pd.Series(
            {pd.Timestamp(b.date): float(b.close) for b in adj_bars if b.close not in (None, -1.0)},
            dtype=float,
        ).sort_index()
        raw = pd.Series(
            {pd.Timestamp(b.date): float(b.close) for b in raw_bars if b.close not in (None, -1.0)},
            dtype=float,
        ).sort_index()

        if adj.empty or raw.empty:
            return []

        common_idx = adj.index.intersection(raw.index)
        if len(common_idx) < 2:
            return []

        adj = adj.loc[common_idx]
        raw = raw.loc[common_idx]

        ret_adj = adj.pct_change()
        ret_raw = raw.pct_change()
        divergence = (ret_adj - ret_raw).abs().dropna()

        exdates = [ts.normalize() for ts in divergence[divergence > self._threshold_pct].index]

        logger.info(
            "corporate_actions_detected",
            symbol=symbol,
            events_found=len(exdates),
            threshold_pct=self._threshold_pct,
            source="ibkr_adjusted_last_vs_trades",
        )
        return exdates
