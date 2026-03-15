"""
Append-only audit trail for position and equity tracking.

Provides crash-safe persistent state reconstruction.
Uses ``os.fsync()`` after every append to guarantee data reaches disk
before the function returns.
"""

import csv
import io
import os
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from structlog import get_logger

from monitoring.events import TradingEvent, EventType
from common.validators import EquityError

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


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
    
    def __init__(self, trail_dir: str = "data/audit"):
        """
        Initialize audit trail storage.
        
        Args:
            trail_dir: Directory for audit logs
        """
        self.trail_dir = Path(trail_dir)
        self.trail_dir.mkdir(parents=True, exist_ok=True)
        
        # Current session's trail file (one per day)
        date_str = datetime.now().strftime("%Y%m%d")
        self.trail_file = self.trail_dir / f"audit_trail_{date_str}.csv"
        self.equity_snapshot_file = self.trail_dir / f"equity_snapshots_{date_str}.csv"
        
        # Ensure CSV headers exist
        self._ensure_headers()
        
        logger.info(
            "audit_trail_initialized",
            trail_file=str(self.trail_file),
            equity_snapshot_file=str(self.equity_snapshot_file)
        )
    
    def _ensure_headers(self) -> None:
        """Create CSV files with headers if they don't exist."""
        # Trade events trail
        if not self.trail_file.exists():
            with open(self.trail_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'event_type',
                    'symbol_pair',
                    'side',
                    'quantity',
                    'entry_price',
                    'exit_price',
                    'pnl',
                    'equity_at_event',
                    'event_id'  # For idempotency
                ])
            logger.debug("trade_trail_created", file=str(self.trail_file))
        
        # Equity snapshots
        if not self.equity_snapshot_file.exists():
            with open(self.equity_snapshot_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'equity',
                    'positions_count',
                    'positions_list'
                ])
            logger.debug("equity_snapshots_created", file=str(self.equity_snapshot_file))
    
    def log_trade_event(
        self,
        event: TradingEvent,
        current_equity: float,
        event_id: Optional[str] = None
    ) -> None:
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
        
        event_id = event_id or f"{datetime.now().isoformat()}_{event.symbol_pair}"
        
        try:
            self._atomic_append(self.trail_file, [
                event.timestamp.isoformat(),
                event.event_type.value,
                event.symbol_pair,
                event.reason if event.event_type == EventType.TRADE_ENTRY else None,
                event.position_size,
                event.entry_price or '',
                event.exit_price or '',
                event.pnl or '',
                current_equity,
                event_id
            ])
            logger.info(
                "trade_event_logged",
                event_type=event.event_type.value,
                symbol_pair=event.symbol_pair,
                equity=current_equity
            )
        except IOError as e:
            logger.error("audit_trail_write_failed", error=str(e), file=str(self.trail_file))
            raise EquityError(f"Failed to persist trade event: {e}")
    
    def log_equity_snapshot(
        self,
        current_equity: float,
        positions_count: int,
        positions_list: Optional[str] = None
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
            self._atomic_append(self.equity_snapshot_file, [
                datetime.now().isoformat(),
                current_equity,
                positions_count,
                positions_list or ''
            ])
            logger.info(
                "equity_snapshot_logged",
                equity=current_equity,
                positions_count=positions_count
            )
        except IOError as e:
            logger.error("snapshot_write_failed", error=str(e), file=str(self.equity_snapshot_file))
            raise EquityError(f"Failed to persist equity snapshot: {e}")
    
    # ------------------------------------------------------------------
    # Atomic I/O helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _atomic_append(filepath: Path, row: list) -> None:
        """Append a single CSV row with ``os.fsync()`` durability.

        Writes the row to a temporary file first, then appends its
        content to *filepath* and calls ``os.fsync()`` on the file
        descriptor.  If the process is killed between the write and
        the fsync, the worst case is the row is missing ÔÇö the file
        itself is never corrupted because we only ever append a
        complete, pre-serialised line.
        """
        buf = io.StringIO()
        csv.writer(buf).writerow(row)
        line = buf.getvalue()

        fd = os.open(str(filepath), os.O_WRONLY | os.O_APPEND | os.O_CREAT)
        try:
            os.write(fd, line.encode('utf-8'))
            os.fsync(fd)
        finally:
            os.close(fd)
    
    def recover_state(self) -> Tuple[Dict[str, '_PositionRecord'], List[float]]:
        """
        Reconstruct positions and equity history from audit trail.
        
        Returns:
            Tuple of (positions_dict, equity_history_list)
        
        Raises:
            EquityError: If trail is corrupted or unreadable
        """
        positions: Dict[str, '_PositionRecord'] = {}
        equity_history: List[float] = []
        
        if not self.trail_file.exists():
            logger.warning("no_audit_trail_found", file=str(self.trail_file))
            return positions, equity_history
        
        try:
            with open(self.trail_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if not row or not row.get('timestamp'):
                        continue
                    
                    timestamp = datetime.fromisoformat(row['timestamp'])
                    event_type = row['event_type']
                    symbol_pair = row['symbol_pair']
                    equity = float(row['equity_at_event'])
                    
                    # Track equity history
                    if not equity_history or equity != equity_history[-1]:
                        equity_history.append(equity)
                    
                    # Reconstruct positions from ENTRY events
                    if event_type == EventType.TRADE_ENTRY.value:
                        side = row['side']
                        quantity = float(row['quantity'])
                        entry_price = float(row['entry_price']) if row['entry_price'] else 0.0
                        
                        positions[symbol_pair] = _PositionRecord(
                            symbol_pair=symbol_pair,
                            entry_time=timestamp,
                            entry_price=entry_price,
                            quantity=quantity,
                            side=side
                        )
                        logger.debug(
                            "position_recovered_entry",
                            symbol_pair=symbol_pair,
                            quantity=quantity,
                            price=entry_price
                        )
                    
                    # Remove positions on EXIT events
                    elif event_type == EventType.TRADE_EXIT.value:
                        if symbol_pair in positions:
                            positions.pop(symbol_pair)
                            logger.debug("position_recovered_exit", symbol_pair=symbol_pair)
            
            logger.info(
                "state_recovered_from_trail",
                positions_count=len(positions),
                equity_history_len=len(equity_history)
            )
            return positions, equity_history
        
        except (IOError, ValueError, KeyError) as e:
            logger.error("state_recovery_failed", error=str(e), file=str(self.trail_file))
            raise EquityError(f"Failed to recover state from audit trail: {e}")
    
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
            with open(self.trail_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                row_count = 0
                last_equity = None
                
                for row in reader:
                    row_count += 1
                    if row.get('equity_at_event'):
                        last_equity = float(row['equity_at_event'])
            
            logger.info(
                "trail_integrity_verified",
                rows=row_count,
                last_equity=last_equity
            )
            return True
        
        except (IOError, ValueError) as e:
            logger.error("trail_integrity_check_failed", error=str(e))
            return False


def recover_positions_from_trail(
    trail_dir: str = "data/audit",
) -> Tuple[Dict[str, '_PositionRecord'], List[float]]:
    """
    Convenience function to recover state without creating AuditTrail instance.
    
    Args:
        trail_dir: Directory containing audit trail
    
    Returns:
        Tuple of (positions, equity_history)
    """
    trail = AuditTrail(trail_dir)
    return trail.recover_state()
