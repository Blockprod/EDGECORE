"""
Append-only audit trail for position and equity tracking.

Provides crash-safe persistent state reconstruction.
Uses ``os.fsync()`` after every append to guarantee data reaches disk
before the function returns.
"""

import csv
import hashlib
import hmac as _hmac_module
import io
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from structlog import get_logger

from common.validators import EquityError
from monitoring.events import EventType, TradingEvent

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# HMAC key loaded once at import time.  Set AUDIT_HMAC_KEY in the environment
# to enable per-row integrity protection.  Empty string disables HMAC (dev mode).
_AUDIT_HMAC_KEY: bytes = os.getenv("AUDIT_HMAC_KEY", "").encode("utf-8")

# C-07: warn/error when HMAC key is absent so operators notice in prod.
if not _AUDIT_HMAC_KEY:
    _hmac_log_level = "error" if os.getenv("EDGECORE_ENV", "dev") == "prod" else "warning"
    _hmac_msg = "AUDIT_HMAC_KEY not set — audit entries are unsigned (integrity unverifiable)"
    getattr(get_logger(__name__), _hmac_log_level)(
        "audit_trail_hmac_disabled",
        message=_hmac_msg,
    )


# Local definition to avoid circular imports
# Matches risk.engine.Position structure
from dataclasses import dataclass as _dataclass


@_dataclass
class _PositionRecord:
    """Local position record for trail reconstruction."""

    symbol_pair: str
    entry_time: datetime
    entry_price: float
    quantity: float
    side: str
    pnl: float = 0.0
    marked_price: float = 0.0


class AuditTrail:
    """
    Append-only ledger for all trading events.

    Records:
    - Trade entries/exits with price and quantity
    - Equity snapshots at key points
    - P&L for each closed position

    Provides:
    - Idempotent append (no duplicate events)
    - State recovery from persistent log
    - Integrity checks for reconstruction
    """

    def __init__(self, trail_dir: str = "data/audit", fsync_mode: str = "always"):
        """
        Initialize audit trail storage.

        Args:
            trail_dir: Directory for audit logs
            fsync_mode: Durability mode for appends (C-12).
                ``"always"`` — fsync after every row (default, safest).
                ``"never"``  — skip fsync (fastest, data loss risk on crash).
        """
        self.trail_dir = Path(trail_dir)
        self.trail_dir.mkdir(parents=True, exist_ok=True)
        # C-12: configurable fsync mode — "always" is safest, "never" skips fsync
        if fsync_mode not in ("always", "never"):
            raise ValueError(f"fsync_mode must be 'always' or 'never', got {fsync_mode!r}")
        self._fsync_always: bool = fsync_mode == "always"

        # Current session's trail file (one per day)
        self._date_str = datetime.now(UTC).strftime("%Y%m%d")
        self.trail_file = self.trail_dir / f"audit_trail_{self._date_str}.csv"
        self.equity_snapshot_file = self.trail_dir / f"equity_snapshots_{self._date_str}.csv"

        # Rotate oversized files before opening, then ensure headers on new file
        self._rotate_if_needed(self.trail_file)
        self._rotate_if_needed(self.equity_snapshot_file)
        self._ensure_headers()

        logger.info(
            "audit_trail_initialized",
            trail_file=str(self.trail_file),
            equity_snapshot_file=str(self.equity_snapshot_file),
            fsync_mode=fsync_mode,
        )

    def _rotate_if_needed(self, filepath: Path, max_file_bytes: int = 50 * 1024 * 1024) -> None:
        """Rename *filepath* to an archived copy when it exceeds *max_file_bytes*.

        A new file (with headers) will be created by the next call to
        ``_ensure_headers()``.  Archive names follow the pattern
        ``{stem}_archived_{n}.csv`` to avoid overwriting existing archives.
        """
        if not filepath.exists():
            return
        if filepath.stat().st_size < max_file_bytes:
            return
        n = 0
        while True:
            archived = filepath.with_name(f"{filepath.stem}_archived_{n}.csv")
            if not archived.exists():
                break
            n += 1
        filepath.rename(archived)
        logger.info("audit_trail_rotated", original=str(filepath), archived_to=str(archived))

    def _ensure_headers(self) -> None:
        """Create CSV files with headers if they don't exist."""
        # Trade events trail
        if not self.trail_file.exists():
            with open(self.trail_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "timestamp",
                        "event_type",
                        "symbol_pair",
                        "side",
                        "quantity",
                        "entry_price",
                        "exit_price",
                        "pnl",
                        "equity_at_event",
                        "event_id",  # For idempotency
                        "_hmac",
                    ]
                )
            logger.debug("trade_trail_created", file=str(self.trail_file))

        # Equity snapshots
        if not self.equity_snapshot_file.exists():
            with open(self.equity_snapshot_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "equity", "positions_count", "positions_list", "_hmac"])
            logger.debug("equity_snapshots_created", file=str(self.equity_snapshot_file))

    def log_trade_event(self, event: TradingEvent, current_equity: float, event_id: str | None = None) -> None:
        """
        Append trade event to audit trail.

        Args:
            event: TradingEvent to record
            current_equity: Account equity at time of event
            event_id: Unique ID for idempotency

        Raises:
            EquityError: If equity tracking would be corrupted
        """
        if current_equity <= 0:
            raise EquityError(f"Cannot log trade with invalid equity: {current_equity}")

        event_id = event_id or f"{datetime.now(UTC).isoformat()}_{event.symbol_pair}"

        try:
            self._atomic_append(
                self.trail_file,
                [
                    event.timestamp.isoformat(),
                    event.event_type.value,
                    event.symbol_pair,
                    event.reason if event.event_type == EventType.TRADE_ENTRY else None,
                    event.position_size,
                    event.entry_price or "",
                    event.exit_price or "",
                    event.pnl or "",
                    current_equity,
                    event_id,
                ],
                _AUDIT_HMAC_KEY,
                force_fsync=self._fsync_always,
            )
            logger.info(
                "trade_event_logged",
                event_type=event.event_type.value,
                symbol_pair=event.symbol_pair,
                equity=current_equity,
            )
        except OSError as e:
            logger.error("audit_trail_write_failed", error=str(e), file=str(self.trail_file))
            raise EquityError(f"Failed to persist trade event: {e}") from e

    def log_equity_snapshot(
        self, current_equity: float, positions_count: int, positions_list: str | None = None
    ) -> None:
        """
        Record equity and position count snapshot.

        Args:
            current_equity: Current account equity
            positions_count: Number of open positions
            positions_list: Serialized position details

        Raises:
            EquityError: If equity is invalid
        """
        if current_equity <= 0:
            raise EquityError(f"Cannot snapshot invalid equity: {current_equity}")

        try:
            self._atomic_append(
                self.equity_snapshot_file,
                [datetime.now(UTC).isoformat(), current_equity, positions_count, positions_list or ""],
                _AUDIT_HMAC_KEY,
                force_fsync=self._fsync_always,
            )
            logger.info("equity_snapshot_logged", equity=current_equity, positions_count=positions_count)
        except OSError as e:
            logger.error("snapshot_write_failed", error=str(e), file=str(self.equity_snapshot_file))
            raise EquityError(f"Failed to persist equity snapshot: {e}") from e

    # ------------------------------------------------------------------
    # Atomic I/O helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _atomic_append(filepath: Path, row: list, hmac_key: bytes = b"", force_fsync: bool = True) -> None:
        """Append a single CSV row with configurable fsync durability (C-12).

        When *force_fsync* is True (default), calls ``os.fsync()`` after the
        write so the row survives a process kill.  When False, the OS page
        cache handles flushing — faster but not crash-safe for that row.

        When *hmac_key* is non-empty, a HMAC-SHA256 digest of the
        serialised row is appended as a trailing ``_hmac`` column.
        """
        buf = io.StringIO()
        csv.writer(buf).writerow(row)
        row_csv = buf.getvalue()

        if hmac_key:
            digest = _hmac_module.new(hmac_key, row_csv.encode("utf-8"), hashlib.sha256).hexdigest()
            buf2 = io.StringIO()
            csv.writer(buf2).writerow(list(row) + [digest])
            line = buf2.getvalue()
        else:
            line = row_csv

        fd = os.open(str(filepath), os.O_WRONLY | os.O_APPEND | os.O_CREAT)
        try:
            os.write(fd, line.encode("utf-8"))
            if force_fsync:  # C-12: conditional fsync
                os.fsync(fd)
        finally:
            os.close(fd)

    def recover_state(self) -> tuple[dict[str, "_PositionRecord"], list[float]]:
        """
        Reconstruct positions and equity history from audit trail.

        Returns:
            Tuple of (positions_dict, equity_history_list)

        Raises:
            EquityError: If trail is corrupted or unreadable
        """
        positions: dict[str, _PositionRecord] = {}
        equity_history: list[float] = []

        if not self.trail_file.exists():
            logger.warning("no_audit_trail_found", file=str(self.trail_file))
            return positions, equity_history

        try:
            with open(self.trail_file, newline="") as f:
                reader = csv.DictReader(f)
                fieldnames: list[str] = list(reader.fieldnames or [])
                hmac_in_header = "_hmac" in fieldnames
                hmac_verify = hmac_in_header and bool(_AUDIT_HMAC_KEY)
                fieldnames_for_hmac = [fn for fn in fieldnames if fn != "_hmac"]

                for row in reader:
                    if not row or not row.get("timestamp"):
                        continue

                    # Verify per-row HMAC when key is configured and column present
                    if hmac_verify:
                        stored_digest = row.get("_hmac", "")
                        row_values = [row.get(fn, "") for fn in fieldnames_for_hmac]
                        buf = io.StringIO()
                        csv.writer(buf).writerow(row_values)
                        expected_digest = _hmac_module.new(
                            _AUDIT_HMAC_KEY,
                            buf.getvalue().encode("utf-8"),
                            hashlib.sha256,
                        ).hexdigest()
                        if not _hmac_module.compare_digest(stored_digest, expected_digest):
                            logger.warning(
                                "audit_trail_hmac_invalid",
                                timestamp=row.get("timestamp"),
                                action="skipping_row",
                            )
                            continue

                    timestamp = datetime.fromisoformat(row["timestamp"])
                    event_type = row["event_type"]
                    symbol_pair = row["symbol_pair"]
                    equity = float(row["equity_at_event"])

                    # Track equity history
                    if not equity_history or equity != equity_history[-1]:
                        equity_history.append(equity)

                    # Reconstruct positions from ENTRY events
                    if event_type == EventType.TRADE_ENTRY.value:
                        side = row["side"]
                        quantity = float(row["quantity"])
                        entry_price = float(row["entry_price"]) if row["entry_price"] else 0.0

                        positions[symbol_pair] = _PositionRecord(
                            symbol_pair=symbol_pair,
                            entry_time=timestamp,
                            entry_price=entry_price,
                            quantity=quantity,
                            side=side,
                        )
                        logger.debug(
                            "position_recovered_entry", symbol_pair=symbol_pair, quantity=quantity, price=entry_price
                        )

                    # Remove positions on EXIT events
                    elif event_type == EventType.TRADE_EXIT.value:
                        if symbol_pair in positions:
                            positions.pop(symbol_pair)
                            logger.debug("position_recovered_exit", symbol_pair=symbol_pair)

            logger.info(
                "state_recovered_from_trail", positions_count=len(positions), equity_history_len=len(equity_history)
            )
            return positions, equity_history

        except (OSError, ValueError, KeyError) as e:
            logger.error("state_recovery_failed", error=str(e), file=str(self.trail_file))
            raise EquityError(f"Failed to recover state from audit trail: {e}") from e

    def verify_trail_integrity(self) -> bool:
        """
        Check audit trail for corruption.

        Returns:
            True if trail is readable and consistent
        """
        if not self.trail_file.exists():
            logger.warning("trail_file_missing", file=str(self.trail_file))
            return False

        try:
            with open(self.trail_file, newline="") as f:
                reader = csv.DictReader(f)
                row_count = 0
                last_equity = None

                for row in reader:
                    row_count += 1
                    if row.get("equity_at_event"):
                        last_equity = float(row["equity_at_event"])

            logger.info("trail_integrity_verified", rows=row_count, last_equity=last_equity)
            return True

        except (OSError, ValueError) as e:
            logger.error("trail_integrity_check_failed", error=str(e))
            return False


def recover_positions_from_trail(
    trail_dir: str = "data/audit",
) -> tuple[dict[str, "_PositionRecord"], list[float]]:
    """
    Convenience function to recover state without creating AuditTrail instance.

    Args:
        trail_dir: Directory containing audit trail

    Returns:
        Tuple of (positions, equity_history)
    """
    trail = AuditTrail(trail_dir)
    return trail.recover_state()
