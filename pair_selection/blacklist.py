"""
Dynamic pair blacklist ÔÇö ├ëtape 3 (post-v27 correction).

Tracks consecutive losses per pair. After ``max_consecutive_losses``
losses in a row, the pair enters a cooldown for ``cooldown_days``
calendar days.  During cooldown all new entries for the pair are blocked.

State can optionally be persisted to JSON for cross-run survival.

Usage (simulator integration)::

    blacklist = PairBlacklist(max_consecutive_losses=2, cooldown_days=30)

    # After each trade closes:
    blacklist.record_outcome(pair_key, pnl=trade_pnl, date=bar_date)

    # Before each entry:
    if blacklist.is_blocked(pair_key, date=bar_date):
        continue  # skip entry
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class _PairState:
    """Internal bookkeeping for one pair."""
    consecutive_losses: int = 0
    blacklisted_on: str | None = None   # ISO date string or None
    cooldown_until: str | None = None   # ISO date string or None
    total_losses: int = 0
    total_wins: int = 0


class PairBlacklist:
    """Dynamic pair blacklist with consecutive-loss cooldown.

    Parameters
    ----------
    max_consecutive_losses : int
        How many consecutive losses trigger the blacklist (default 2).
    cooldown_days : int
        How many calendar days the pair stays blocked (default 30).
    persist_path : str | Path | None
        If set, state is saved/loaded from this JSON file.
    enabled : bool
        Master switch.  When False, ``is_blocked`` always returns False
        and ``record_outcome`` is a no-op.
    """

    def __init__(
        self,
        max_consecutive_losses: int = 2,
        cooldown_days: int = 30,
        persist_path: str | None = None,
        enabled: bool = True,
    ):
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_days = cooldown_days
        self.persist_path = Path(persist_path) if persist_path else None
        self.enabled = enabled
        self._pairs: dict[str, _PairState] = {}

        if self.persist_path and self.persist_path.exists():
            self._load()

    # ÔöÇÔöÇ Public API ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

    def record_outcome(self, pair_key: str, pnl: float, trade_date: date) -> None:
        """Record a closed trade outcome for *pair_key*.

        If the loss counter reaches the threshold the pair is blacklisted
        for ``cooldown_days`` starting from *trade_date*.
        """
        if not self.enabled:
            return

        state = self._pairs.setdefault(pair_key, _PairState())

        if pnl < 0:
            state.consecutive_losses += 1
            state.total_losses += 1
        else:
            # A win resets the consecutive counter
            state.consecutive_losses = 0
            state.total_wins += 1

        if (
            state.consecutive_losses >= self.max_consecutive_losses
            and state.blacklisted_on is None
        ):
            state.blacklisted_on = trade_date.isoformat()
            cooldown_end = trade_date + timedelta(days=self.cooldown_days)
            state.cooldown_until = cooldown_end.isoformat()
            logger.info(
                "pair_blacklisted",
                pair=pair_key,
                consecutive_losses=state.consecutive_losses,
                cooldown_until=state.cooldown_until,
            )

        if self.persist_path:
            self._save()

    def is_blocked(self, pair_key: str, check_date: date) -> bool:
        """Return True if *pair_key* is currently blacklisted."""
        if not self.enabled:
            return False

        state = self._pairs.get(pair_key)
        if state is None or state.cooldown_until is None:
            return False

        cooldown_end = date.fromisoformat(state.cooldown_until)
        if check_date < cooldown_end:
            return True

        # Cooldown expired ÔÇö rehabilitate the pair
        logger.info(
            "pair_cooldown_expired",
            pair=pair_key,
            cooldown_ended=state.cooldown_until,
        )
        state.consecutive_losses = 0
        state.blacklisted_on = None
        state.cooldown_until = None

        if self.persist_path:
            self._save()
        return False

    def get_blocked_pairs(self, check_date: date) -> list[str]:
        """Return list of currently blocked pair keys."""
        return [k for k in self._pairs if self.is_blocked(k, check_date)]

    def get_stats(self) -> dict:
        """Return summary statistics for monitoring."""
        return {
            pair: {
                "consecutive_losses": s.consecutive_losses,
                "total_losses": s.total_losses,
                "total_wins": s.total_wins,
                "blacklisted_on": s.blacklisted_on,
                "cooldown_until": s.cooldown_until,
            }
            for pair, s in self._pairs.items()
        }

    def reset(self) -> None:
        """Clear all state (useful for test teardown)."""
        self._pairs.clear()
        if self.persist_path and self.persist_path.exists():
            self.persist_path.unlink()

    # ÔöÇÔöÇ Persistence ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

    def _save(self) -> None:
        if self.persist_path is None:
            return
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for pair, s in self._pairs.items():
            data[pair] = {
                "consecutive_losses": s.consecutive_losses,
                "blacklisted_on": s.blacklisted_on,
                "cooldown_until": s.cooldown_until,
                "total_losses": s.total_losses,
                "total_wins": s.total_wins,
            }
        with open(self.persist_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load(self) -> None:
        if self.persist_path is None or not self.persist_path.exists():
            return
        try:
            with open(self.persist_path, encoding="utf-8") as f:
                data = json.load(f)
            for pair, d in data.items():
                self._pairs[pair] = _PairState(
                    consecutive_losses=d.get("consecutive_losses", 0),
                    blacklisted_on=d.get("blacklisted_on"),
                    cooldown_until=d.get("cooldown_until"),
                    total_losses=d.get("total_losses", 0),
                    total_wins=d.get("total_wins", 0),
                )
            logger.debug(
                "pair_blacklist_loaded",
                path=str(self.persist_path),
                pairs=len(self._pairs),
            )
        except Exception as exc:
            logger.warning(
                "pair_blacklist_load_failed",
                path=str(self.persist_path),
                error=str(exc),
            )
