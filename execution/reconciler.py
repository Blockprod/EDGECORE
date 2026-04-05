"""
Broker reconciliation system for EDGECORE trading.

Ensures broker state matches internal tracking:
- Account equity validation
- Position reconciliation
- Order status verification
- Divergence detection and logging
- Automatic recovery procedures
"""

<<<<<<< HEAD
=======
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from structlog import get_logger
from enum import Enum
>>>>>>> origin/main
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from structlog import get_logger

logger = get_logger(__name__)


class ReconciliationStatus(Enum):
    """Reconciliation result status."""

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"


@dataclass
class ReconciliationDivergence:
    """Record of a detected divergence between broker and internal state."""

    type: str  # "equity", "position", "order"
    severity: str  # "low", "medium", "high"
    description: str
    broker_value: Any
    internal_value: Any
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolution: str | None = None
    resolved_at: datetime | None = None


@dataclass
class ReconciliationReport:
    """Full reconciliation report."""

    status: ReconciliationStatus
    timestamp: datetime
    equity_match: bool
    equity_broker: float
    equity_internal: float
    equity_diff_pct: float
    positions_match: bool
    positions_count_broker: int
    positions_count_internal: int
    orders_match: bool
    divergences: list[ReconciliationDivergence]
    recovery_actions: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class BrokerReconciler:
    """
    Reconciliation engine for broker-internal state consistency.

    Responsibilities:
    1. Daily startup reconciliation
    2. Position tracking verification
    3. Equity balance validation
    4. Order status consistency
    5. Divergence detection and logging
    6. Automatic recovery procedures
    """

    def __init__(
        self,
        internal_equity: float,
        internal_positions: dict[str, dict[str, Any]] | None = None,
        internal_orders: dict[str, dict[str, Any]] | None = None,
        equity_tolerance_pct: float = 0.01,
        position_tolerance_units: float = 0.1,
    ):
        """
        Initialize reconciler with internal state.

        Args:
            internal_equity: Current internal equity value
            internal_positions: dict of symbol -> position details
            internal_orders: dict of order_id -> order details
            equity_tolerance_pct: Acceptable equity mismatch percentage (default 0.01=0.01%)
            position_tolerance_units: Acceptable position size difference

        Raises:
            ValueError: If equity is invalid or tolerance is out of range
        """
        if internal_equity <= 0:
            raise ValueError(f"Internal equity must be positive, got {internal_equity}")
        if not (0 < equity_tolerance_pct < 100):
            raise ValueError(f"Equity tolerance must be 0-100%, got {equity_tolerance_pct}")
        if position_tolerance_units < 0:
            raise ValueError(f"Position tolerance cannot be negative, got {position_tolerance_units}")

        self.internal_equity = internal_equity
        self.internal_positions = internal_positions or {}
        self.internal_orders = internal_orders or {}
        self.equity_tolerance_pct = equity_tolerance_pct
        self.position_tolerance_units = position_tolerance_units

        self.divergences: list[ReconciliationDivergence] = []
        self.last_reconciliation: ReconciliationReport | None = None

        logger.info(
            "reconciler_initialized",
            equity=internal_equity,
            positions_count=len(self.internal_positions),
            orders_count=len(self.internal_orders),
        )

    def reconcile_equity(self, broker_equity: float) -> tuple[bool, float]:
        """
        Verify equity matches between broker and internal tracking.

        Args:
            broker_equity: Current equity reported by broker

        Returns:
            Tuple of (matches: bool, diff_pct: float)

        Raises:
            ValueError: If broker_equity is invalid
        """
        if broker_equity <= 0 or math.isnan(broker_equity) or math.isinf(broker_equity):
            raise ValueError(f"Invalid broker equity: {broker_equity}")

        diff = abs(broker_equity - self.internal_equity)
        diff_pct = (diff / self.internal_equity) * 100
        matches = diff_pct <= self.equity_tolerance_pct

        if not matches:
            divergence = ReconciliationDivergence(
                type="equity",
                severity="high" if diff_pct > 1.0 else "medium",
                description=f"Equity mismatch: {diff_pct:.4f}% difference",
                broker_value=broker_equity,
                internal_value=self.internal_equity,
            )
            self.divergences.append(divergence)
            logger.warning(
                "equity_divergence_detected",
                diff_pct=diff_pct,
                broker_equity=broker_equity,
                internal_equity=self.internal_equity,
            )
        else:
            logger.info("equity_reconciliation_ok", equity=broker_equity)

        return matches, diff_pct

    def reconcile_positions(self, broker_positions: dict[str, dict[str, Any]]) -> tuple[bool, list[str]]:
        """
        Verify positions match between broker and internal tracking.

        Args:
            broker_positions: dict of symbol -> position details from broker

        Returns:
            Tuple of (matches: bool, inconsistencies: list[str])

        Raises:
            ValueError: If positions data is invalid
        """
        if not isinstance(broker_positions, dict):
            raise ValueError(f"Broker positions must be dict, got {type(broker_positions)}")

        inconsistencies = []

        # Check for positions in internal but not in broker
        for symbol, internal_pos in self.internal_positions.items():
            if symbol not in broker_positions:
                inconsistencies.append(f"Position {symbol} missing on broker")
                divergence = ReconciliationDivergence(
                    type="position",
                    severity="high",
                    description=f"Internal position {symbol} missing on broker",
                    broker_value=None,
                    internal_value=internal_pos,
                )
                self.divergences.append(divergence)

        # Check for positions in broker but not in internal (CRITICAL - unknown positions)
        for symbol, broker_pos in broker_positions.items():
            if symbol not in self.internal_positions:
                inconsistencies.append(f"Unknown position {symbol} on broker")
                divergence = ReconciliationDivergence(
                    type="position",
                    severity="high",
                    description=f"Unknown position on broker: {symbol}",
                    broker_value=broker_pos,
                    internal_value=None,
                )
                self.divergences.append(divergence)

        # Check for position sizes that don't match
        for symbol, broker_pos in broker_positions.items():
            if symbol in self.internal_positions:
                internal_size = self.internal_positions[symbol].get("size", 0)
                broker_size = broker_pos.get("size", 0)
                diff = abs(broker_size - internal_size)

                if diff > self.position_tolerance_units:
                    inconsistencies.append(f"Position {symbol}: broker={broker_size}, internal={internal_size}")
                    divergence = ReconciliationDivergence(
                        type="position",
                        severity="medium",
                        description=f"Position size mismatch for {symbol}: diff={diff}",
                        broker_value=broker_pos,
                        internal_value=self.internal_positions[symbol],
                    )
                    self.divergences.append(divergence)

        matches = len(inconsistencies) == 0

        if matches:
            logger.info("positions_reconciliation_ok", positions_count=len(broker_positions))
        else:
            logger.warning("positions_divergence_detected", inconsistencies=inconsistencies)

        return matches, inconsistencies

    def reconcile_orders(self, broker_orders: dict[str, dict[str, Any]]) -> tuple[bool, list[str]]:
        """
        Verify pending orders match between broker and internal tracking.

        Args:
            broker_orders: dict of order_id -> order details from broker

        Returns:
            Tuple of (matches: bool, inconsistencies: list[str])

        Raises:
            ValueError: If orders data is invalid
        """
        if not isinstance(broker_orders, dict):
            raise ValueError(f"Broker orders must be dict, got {type(broker_orders)}")

        inconsistencies = []

        # Check for orders in internal but not in broker (may have filled)
        for order_id, internal_order in self.internal_orders.items():
            if order_id not in broker_orders:
                # This might be expected if order filled
                status = internal_order.get("status")
                if status not in ["filled", "cancelled"]:
                    inconsistencies.append(f"Order {order_id} missing on broker but status is {status}")

        # Check for orders in broker but not in internal
        for order_id, broker_order in broker_orders.items():
            if order_id not in self.internal_orders:
                inconsistencies.append(f"Unknown order {order_id} found on broker")
                divergence = ReconciliationDivergence(
                    type="order",
                    severity="medium",
                    description=f"Unknown order on broker: {order_id}",
                    broker_value=broker_order,
                    internal_value=None,
                )
                self.divergences.append(divergence)

        matches = len(inconsistencies) == 0

        if matches:
            logger.info("orders_reconciliation_ok", orders_count=len(broker_orders))
        else:
            logger.warning("orders_divergence_detected", inconsistencies=inconsistencies)

        return matches, inconsistencies

    def full_reconciliation(
        self,
        broker_equity: float,
        broker_positions: dict[str, dict[str, Any]],
        broker_orders: dict[str, dict[str, Any]],
    ) -> ReconciliationReport:
        """
        Perform complete broker-internal reconciliation.

        Args:
            broker_equity: Current equity from broker
            broker_positions: Current positions from broker
            broker_orders: Current orders from broker

        Returns:
            ReconciliationReport with full details

        Raises:
             ValueError: If any input is invalid
        """
<<<<<<< HEAD
        start_time = datetime.now(UTC)
=======
        start_time = datetime.now(timezone.utc)
>>>>>>> origin/main
        self.divergences = []  # Reset divergences for this reconciliation

        # Reconcile each component
        equity_matches, equity_diff_pct = self.reconcile_equity(broker_equity)
        positions_matches, _position_inconsistencies = self.reconcile_positions(broker_positions)
        orders_matches, _order_inconsistencies = self.reconcile_orders(broker_orders)

        # Determine overall status
        if equity_matches and positions_matches and orders_matches:
            status = ReconciliationStatus.OK
        elif equity_diff_pct > 0.5 or any("high" in str(d.severity) for d in self.divergences):
            status = ReconciliationStatus.CRITICAL
        else:
            status = ReconciliationStatus.WARNING
<<<<<<< HEAD

        duration = (datetime.now(UTC) - start_time).total_seconds()

=======
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
>>>>>>> origin/main
        report = ReconciliationReport(
            status=status,
            timestamp=start_time,
            equity_match=equity_matches,
            equity_broker=broker_equity,
            equity_internal=self.internal_equity,
            equity_diff_pct=equity_diff_pct,
            positions_match=positions_matches,
            positions_count_broker=len(broker_positions),
            positions_count_internal=len(self.internal_positions),
            orders_match=orders_matches,
            divergences=self.divergences,
            duration_seconds=duration,
        )

        self.last_reconciliation = report

        logger.info(
            "reconciliation_complete",
            status=status.value,
            equity_match=equity_matches,
            positions_match=positions_matches,
            orders_match=orders_matches,
            divergence_count=len(self.divergences),
            duration_seconds=duration,
        )

        return report

    def get_recovery_actions(self) -> list[str]:
        """
        Suggest recovery actions based on detected divergences.

        Returns:
            List of recommended recovery actions
        """
        actions = []

        for divergence in self.divergences:
            if divergence.type == "equity":
                if divergence.severity == "high":
                    actions.append("HALT: Critical equity mismatch - manual investigation required")
                else:
                    actions.append("WARN: Equity mismatch - may need to resync")

            elif divergence.type == "position":
                if divergence.severity == "high":
                    actions.append("CLOSE: Liquidate missing position immediately")
                else:
                    actions.append("SYNC: Recheck position sizes")
<<<<<<< HEAD

            elif divergence.type == "order":
                if divergence.severity == "high":
                    actions.append("CANCEL: Stale order found on broker")

=======
            
            elif divergence.type == "order":
                if divergence.severity == "high":
                    actions.append("CANCEL: Stale order found on broker")
        
>>>>>>> origin/main
        return actions
