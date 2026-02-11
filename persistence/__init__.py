"""
Persistent state management for EDGECORE trading system.

Provides:
- Append-only audit trail for all trades
- Equity snapshots for reconciliation
- Crash recovery and state reconstruction
"""

from .audit_trail import AuditTrail, recover_positions_from_trail

__all__ = ["AuditTrail", "recover_positions_from_trail"]
