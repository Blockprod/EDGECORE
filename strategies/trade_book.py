"""
Strategy-level active trade tracker for PairTradingStrategy.

Provides :class:`StrategyTradeBook`, a typed wrapper around the
``active_trades`` dictionary used by :class:`~strategies.pair_trading.PairTradingStrategy`.

Why a dedicated module?
- Centralises the semantic API for opening and closing logical positions at the
  strategy signal layer (before execution).
- Mirrors :class:`~backtests.order_book.SimulatedOrderBook` at the strategy
  level, making the two-layer position model explicit:
  * StrategyTradeBook — "does the strategy *think* it's in this trade?"
  * SimulatedOrderBook — "what positions does the backtest *account* for?"
- Makes the contract explicit: every entry goes through :meth:`open`, every
  close through :meth:`close` (or the backward-compatible :meth:`pop` /
  ``del`` syntax that existing code relies on).
"""

from __future__ import annotations

from typing import Iterator


class StrategyTradeBook:
    """
    Tracks logical active positions at the strategy signal layer.

    Acts as a typed, dict-compatible replacement for ``active_trades: Dict[str, dict]``
    in :class:`~strategies.pair_trading.PairTradingStrategy`.
    Exposes the full dict interface (``__getitem__``, ``__setitem__``,
    ``__delitem__``, ``pop``, ``keys``, ``values``, ``items``,
    ``__contains__``, ``__len__``, ``__iter__``) so it can be used as a
    drop-in replacement with no changes to call sites.

    New semantic methods (preferred in new code):
    - :meth:`open`  – record that the strategy entered a trade.
    - :meth:`close` – record that the strategy exited a trade.
    - :meth:`is_active` – check whether a pair is currently tracked.
    - :meth:`as_dict` – return a plain dict snapshot (e.g. for JSON logging).
    """

    def __init__(self) -> None:
        self._trades: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Semantic trade lifecycle API
    # ------------------------------------------------------------------

    def open(self, pair_key: str, trade: dict) -> None:
        """Record a new active trade for *pair_key*."""
        self._trades[pair_key] = trade

    def close(self, pair_key: str) -> dict | None:
        """Remove and return the trade for *pair_key*, or ``None`` if absent."""
        return self._trades.pop(pair_key, None)

    def is_active(self, pair_key: str) -> bool:
        """Return ``True`` if *pair_key* is currently tracked as an active trade."""
        return pair_key in self._trades

    def as_dict(self) -> dict[str, dict]:
        """Return a shallow copy of the underlying trade dictionary.

        Use this when you need a plain :class:`dict` (e.g. for JSON logging or
        passing to external functions that expect a raw dict).
        """
        return dict(self._trades)

    # ------------------------------------------------------------------
    # Backward-compatible dict interface
    # ------------------------------------------------------------------

    def get(self, pair_key: str) -> dict | None:
        """Return the trade dict for *pair_key* without removing it, or ``None``."""
        return self._trades.get(pair_key)

    def pop(self, pair_key: str, default=None):
        """Remove *pair_key* if present, returning its value (or *default*)."""
        return self._trades.pop(pair_key, default)

    def keys(self) -> list[str]:  # type: ignore[override]
        return list(self._trades.keys())

    def values(self) -> list[dict]:  # type: ignore[override]
        return list(self._trades.values())

    def items(self) -> list[tuple[str, dict]]:  # type: ignore[override]
        return list(self._trades.items())

    def __len__(self) -> int:
        return len(self._trades)

    def __contains__(self, pair_key: object) -> bool:
        return pair_key in self._trades

    def __iter__(self) -> Iterator[str]:
        return iter(list(self._trades.keys()))

    def __getitem__(self, pair_key: str) -> dict:
        return self._trades[pair_key]

    def __setitem__(self, pair_key: str, trade: dict) -> None:
        """Backward-compatible direct assignment (prefer :meth:`open`)."""
        self._trades[pair_key] = trade

    def __delitem__(self, pair_key: str) -> None:
        """Backward-compatible ``del active_trades[pair_key]`` (prefer :meth:`close`)."""
        del self._trades[pair_key]

    def __bool__(self) -> bool:
        return bool(self._trades)

    def clear(self) -> None:
        """Remove all active trades (backward-compatible with dict.clear())."""
        self._trades.clear()


__all__ = ["StrategyTradeBook"]
