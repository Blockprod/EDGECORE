"""
Monitoring and alerting system for EDGECORE trading.

Provides:
- Real-time trading alerts
- Critical event notifications
- Dashboard status reporting
- Alert categorization and routing
- Integration hooks for external services (Slack, email, etc)
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Callable

from structlog import get_logger

logger = get_logger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"


class AlertCategory(Enum):
    """Alert categories for routing and filtering."""
    EQUITY = "equity"
    POSITION = "position"
    ORDER = "order"
    RISK = "risk"
    BROKER = "broker"
    SYSTEM = "system"
    RECONCILIATION = "reconciliation"
    PERFORMANCE = "performance"


@dataclass
class Alert:
    """Individual alert record."""
    alert_id: str
    severity: AlertSeverity
    category: AlertCategory
    title: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any] = field(default_factory=dict)
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None
    
    def __post_init__(self):
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=UTC)

    def acknowledge(self, username: str = "system") -> None:
        """Mark alert as acknowledged."""
        self.acknowledged_at = datetime.now(UTC)
        self.acknowledged_by = username
    
    def resolve(self) -> None:
        """Mark alert as resolved."""
        self.resolved_at = datetime.now(UTC)
    
    def is_acknowledged(self) -> bool:
        """Check if alert has been acknowledged."""
        return self.acknowledged_at is not None
    
    def is_resolved(self) -> bool:
        """Check if alert has been resolved."""
        return self.resolved_at is not None
    
    def age_seconds(self) -> float:
        """Get alert age in seconds."""
        return (datetime.now(UTC) - self.timestamp).total_seconds()
    
    def to_dict(self) -> dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.value,
            "category": self.category.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "acknowledged": self.is_acknowledged(),
            "resolved": self.is_resolved()
        }


class AlertManager:
    """
    Central alert management system.
    
    Responsibilities:
    1. Create and track alerts
    2. Route alerts to external handlers
    3. Acknowledge and resolve alerts
    4. Provide alert history and statistics
    5. Dashboard status generation
    """
    
    def __init__(self, max_alert_history: int = 10000):
        """
        Initialize alert manager.
        
        Args:
            max_alert_history: Maximum alerts to keep in memory
        
        Raises:
            ValueError: If max_alert_history is invalid
        """
        if max_alert_history < 100:
            raise ValueError(f"max_alert_history must be >= 100, got {max_alert_history}")
        
        self.max_alert_history = max_alert_history
        self.alerts: dict[str, Alert] = {}
        self.alert_counter: int = 0
        self.handlers: dict[AlertSeverity, list[Callable]] = {
            severity: [] for severity in AlertSeverity
        }
        self.category_handlers: dict[AlertCategory, list[Callable]] = {
            category: [] for category in AlertCategory
        }
        
        logger.info("alert_manager_initialized", max_history=max_alert_history)
    
    def create_alert(
        self,
        severity: AlertSeverity,
        category: AlertCategory,
        title: str,
        message: str,
        data: dict[str, Any] | None = None
    ) -> Alert:
        """
        Create and dispatch a new alert.
        
        Args:
            severity: Alert severity level
            category: Alert category for routing
            title: Short alert title
            message: Detailed alert message
            data: Optional metadata dict
        
        Returns:
            Created Alert object
        
        Raises:
            ValueError: If inputs are invalid
        """
        if not title or len(title) > 200:
            raise ValueError(f"Title must be 1-200 chars, got: {title}")
        
        if not message or len(message) > 2000:
            raise ValueError(f"Message must be 1-2000 chars, got: {message}")
        
        self.alert_counter += 1
        alert_id = f"alert_{datetime.now(UTC).timestamp()}_{self.alert_counter}"
        
        alert = Alert(
            alert_id=alert_id,
            severity=severity,
            category=category,
            title=title,
            message=message,
            data=data or {}
        )
        
        self.alerts[alert_id] = alert
        
        # Enforce max history
        if len(self.alerts) > self.max_alert_history:
            self._prune_alerts()
        
        logger.info(
            "alert_created",
            alert_id=alert_id,
            severity=severity.value,
            category=category.value,
            title=title
        )
        
        # Dispatch to handlers
        self._dispatch_alert(alert)
        
        return alert
    
    def _dispatch_alert(self, alert: Alert) -> None:
        """Dispatch alert to registered handlers."""
        # Dispatch to severity handlers
        for handler in self.handlers.get(alert.severity, []):
            try:
                handler(alert)
            except Exception as e:
                logger.error("handler_exception", error=str(e), alert_id=alert.alert_id)
        
        # Dispatch to category handlers
        for handler in self.category_handlers.get(alert.category, []):
            try:
                handler(alert)
            except Exception as e:
                logger.error("handler_exception", error=str(e), alert_id=alert.alert_id)
    
    def register_severity_handler(
        self,
        severity: AlertSeverity,
        handler: Callable[[Alert], None]
    ) -> None:
        """
        Register handler for alerts of specific severity.
        
        Args:
            severity: Alert severity to handle
            handler: Callable that receives Alert object
        
        Raises:
            ValueError: If handler is not callable
        """
        if not callable(handler):
            raise ValueError("Handler must be callable")
        
        self.handlers[severity].append(handler)
        logger.info("severity_handler_registered", severity=severity.value)
    
    def register_category_handler(
        self,
        category: AlertCategory,
        handler: Callable[[Alert], None]
    ) -> None:
        """
        Register handler for alerts of specific category.
        
        Args:
            category: Alert category to handle
            handler: Callable that receives Alert object
        
        Raises:
            ValueError: If handler is not callable
        """
        if not callable(handler):
            raise ValueError("Handler must be callable")
        
        self.category_handlers[category].append(handler)
        logger.info("category_handler_registered", category=category.value)
    
    def acknowledge_alert(self, alert_id: str, username: str = "system") -> Alert:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert to acknowledge
            username: User acknowledging
        
        Returns:
            Updated Alert object
        
        Raises:
            KeyError: If alert not found
        """
        if alert_id not in self.alerts:
            raise KeyError(f"Alert {alert_id} not found")
        
        alert = self.alerts[alert_id]
        alert.acknowledge(username)
        
        logger.info("alert_acknowledged", alert_id=alert_id, username=username)
        return alert
    
    def resolve_alert(self, alert_id: str) -> Alert:
        """
        Mark an alert as resolved.
        
        Args:
            alert_id: Alert to resolve
        
        Returns:
            Updated Alert object
        
        Raises:
            KeyError: If alert not found
        """
        if alert_id not in self.alerts:
            raise KeyError(f"Alert {alert_id} not found")
        
        alert = self.alerts[alert_id]
        alert.resolve()
        
        logger.info("alert_resolved", alert_id=alert_id)
        return alert
    
    def get_alert(self, alert_id: str) -> Alert:
        """
        Get specific alert by ID.
        
        Args:
            alert_id: Alert ID to retrieve
        
        Returns:
            Alert object
        
        Raises:
            KeyError: If alert not found
        """
        if alert_id not in self.alerts:
            raise KeyError(f"Alert {alert_id} not found")
        return self.alerts[alert_id]
    
    def get_active_alerts(
        self,
        severity: AlertSeverity | None = None,
        category: AlertCategory | None = None
    ) -> list[Alert]:
        """
        Get active (unresolved) alerts, optionally filtered.
        
        Args:
            severity: Optional filter by severity
            category: Optional filter by category
        
        Returns:
            List of active Alert objects
        """
        active = [a for a in self.alerts.values() if not a.is_resolved()]
        
        if severity:
            active = [a for a in active if a.severity == severity]
        
        if category:
            active = [a for a in active if a.category == category]
        
        return sorted(active, key=lambda a: a.timestamp, reverse=True)
    
    def get_unacknowledged_alerts(self) -> list[Alert]:
        """Get all unacknowledged alerts."""
        return [a for a in self.alerts.values() if not a.is_acknowledged()]
    
    def get_critical_alerts(self) -> list[Alert]:
        """Get all unresolved critical-severity alerts."""
        return self.get_active_alerts(severity=AlertSeverity.CRITICAL)
    
    def get_alert_statistics(self) -> dict[str, Any]:
        """
        Get statistics on alerts.
        
        Returns:
            Dict with alert counts by severity/category/status
        """
        stats = {
            "total_alerts": len(self.alerts),
            "active_count": 0,
            "unacknowledged_count": 0,
            "critical_count": 0,
            "by_severity": {},
            "by_category": {}
        }
        
        # Count by severity and category
        for severity in AlertSeverity:
            stats["by_severity"][severity.value] = 0
        for category in AlertCategory:
            stats["by_category"][category.value] = 0
        
        # Count alerts
        for alert in self.alerts.values():
            if not alert.is_resolved():
                stats["active_count"] += 1
            if not alert.is_acknowledged():
                stats["unacknowledged_count"] += 1
            if alert.severity == AlertSeverity.CRITICAL and not alert.is_resolved():
                stats["critical_count"] += 1
            
            stats["by_severity"][alert.severity.value] += 1
            stats["by_category"][alert.category.value] += 1
        
        return stats
    
    def get_dashboard_status(self) -> dict[str, Any]:
        """
        Generate dashboard status JSON.
        
        Returns:
            Dict suitable for real-time dashboard display
        """
        active = self.get_active_alerts()
        critical = self.get_critical_alerts()
        
        # Determine overall status
        if critical:
            overall_status = "CRITICAL"
        elif next((a for a in active if a.severity == AlertSeverity.ERROR), None):
            overall_status = "ERROR"
        elif next((a for a in active if a.severity == AlertSeverity.WARNING), None):
            overall_status = "WARNING"
        else:
            overall_status = "OK"
        
        # Recent alerts (last 24 hours)
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        recent = [a for a in active if a.timestamp > cutoff]
        
        return {
            "overall_status": overall_status,
            "timestamp": datetime.now(UTC).isoformat(),
            "active_alert_count": len(active),
            "critical_count": len(critical),
            "unacknowledged_count": len(self.get_unacknowledged_alerts()),
            "recent_alerts": [a.to_dict() for a in recent[:10]],
            "statistics": self.get_alert_statistics()
        }
    
    def _prune_alerts(self) -> None:
        """Remove oldest alerts when history limit reached."""
        alerts_list = sorted(self.alerts.values(), key=lambda a: a.timestamp)
        
        # Keep max history - 1000 to have some headroom
        to_remove = len(self.alerts) - (self.max_alert_history - 1000)
        
        if to_remove > 0:
            for alert in alerts_list[:to_remove]:
                del self.alerts[alert.alert_id]
            
            logger.info("alerts_pruned", removed_count=to_remove)
    
    def export_alerts_json(self, alert_ids: list[str] | None = None) -> str:
        """
        Export alerts as JSON for external systems.
        
        Args:
            alert_ids: Optional list of specific alerts to export
        
        Returns:
            JSON string of alerts
        """
        if alert_ids:
            alerts_to_export = [self.alerts[aid] for aid in alert_ids if aid in self.alerts]
        else:
            alerts_to_export = list(self.alerts.values())
        
        alert_dicts = [a.to_dict() for a in alerts_to_export]
        return json.dumps(alert_dicts, indent=2)


# Common alert generators for trading system

def alert_equity_drop(
    alert_manager: AlertManager,
    current_equity: float,
    previous_equity: float,
    threshold_pct: float = 5.0
) -> Alert | None:
    """
    Create alert for significant equity drop.
    
    Args:
        alert_manager: AlertManager instance
        current_equity: Current equity
        previous_equity: Previous equity
        threshold_pct: Threshold percentage drop
    
    Returns:
        Alert if triggered, None otherwise
    """
    drop_pct = ((previous_equity - current_equity) / previous_equity) * 100
    
    if drop_pct > threshold_pct:
        return alert_manager.create_alert(
            severity=AlertSeverity.CRITICAL if drop_pct > 10.0 else AlertSeverity.WARNING,
            category=AlertCategory.EQUITY,
            title=f"Equity Drop: {drop_pct:.2f}%",
            message=f"Equity dropped from {previous_equity} to {current_equity}",
            data={"drop_pct": drop_pct, "from": previous_equity, "to": current_equity}
        )
    return None


def alert_reconciliation_failure(
    alert_manager: AlertManager,
    divergence_count: int,
    equity_diff_pct: float
) -> Alert | None:
    """
    Create alert for broker reconciliation failure.
    
    Args:
        alert_manager: AlertManager instance
        divergence_count: Number of divergences detected
        equity_diff_pct: Equity mismatch percentage
    
    Returns:
        Alert if triggered, None otherwise
    """
    if divergence_count > 0 or equity_diff_pct > 0.5:
        severity = AlertSeverity.CRITICAL if equity_diff_pct > 1.0 else AlertSeverity.WARNING
        
        return alert_manager.create_alert(
            severity=severity,
            category=AlertCategory.RECONCILIATION,
            title="Broker Reconciliation Failure",
            message=f"{divergence_count} divergences detected, equity diff {equity_diff_pct:.4f}%",
            data={"divergences": divergence_count, "equity_diff_pct": equity_diff_pct}
        )
    return None


def alert_position_limit_breach(
    alert_manager: AlertManager,
    current_positions: int,
    max_positions: int
) -> Alert | None:
    """
    Create alert for position limit breach.
    
    Args:
        alert_manager: AlertManager instance
        current_positions: Current open positions
        max_positions: Maximum allowed positions
    
    Returns:
        Alert if triggered, None otherwise
    """
    if current_positions >= max_positions:
        return alert_manager.create_alert(
            severity=AlertSeverity.WARNING,
            category=AlertCategory.POSITION,
            title="Position Limit Reached",
            message=f"Current positions: {current_positions}/{max_positions}",
            data={"current": current_positions, "max": max_positions}
        )
    return None


def alert_order_timeout(
    alert_manager: AlertManager,
    order_id: str,
    symbol: str,
    timeout_seconds: float
) -> Alert:
    """
    Create alert for order timeout.
    
    Args:
        alert_manager: AlertManager instance
        order_id: Order that timed out
        symbol: Trading pair
        timeout_seconds: How long it was pending
    
    Returns:
        Alert
    """
    return alert_manager.create_alert(
        severity=AlertSeverity.ERROR,
        category=AlertCategory.ORDER,
        title=f"Order Timeout: {order_id}",
        message=f"Order {order_id} pending for {timeout_seconds:.0f}s on {symbol}",
        data={"order_id": order_id, "symbol": symbol, "timeout_seconds": timeout_seconds}
    )
