"""Tests for monitoring and alerting system."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from monitoring.alerter import (
    Alert,
    AlertCategory,
    AlertManager,
    AlertSeverity,
    alert_equity_drop,
    alert_order_timeout,
    alert_position_limit_breach,
    alert_reconciliation_failure,
)


class TestAlertRecord:
    """Test Alert record properties."""

    def test_create_alert_record(self):
        """Test creating alert record."""
        alert = Alert(
            alert_id="alert_1",
            severity=AlertSeverity.WARNING,
            category=AlertCategory.EQUITY,
            title="Test Alert",
            message="This is a test alert",
        )

        assert alert.alert_id == "alert_1"
        assert alert.severity == AlertSeverity.WARNING
        assert not alert.is_acknowledged()
        assert not alert.is_resolved()

    def test_alert_acknowledge(self):
        """Test acknowledging an alert."""
        alert = Alert(
            alert_id="alert_1",
            severity=AlertSeverity.WARNING,
            category=AlertCategory.EQUITY,
            title="Test",
            message="Test",
        )

        alert.acknowledge("user1")

        assert alert.is_acknowledged()
        assert alert.acknowledged_by == "user1"

    def test_alert_resolve(self):
        """Test resolving an alert."""
        alert = Alert(
            alert_id="alert_1",
            severity=AlertSeverity.WARNING,
            category=AlertCategory.EQUITY,
            title="Test",
            message="Test",
        )

        alert.resolve()

        assert alert.is_resolved()

    def test_alert_age_seconds(self):
        """Test alert age calculation."""
        now = datetime.now(UTC)
        old_time = now - timedelta(seconds=60)

        alert = Alert(
            alert_id="alert_1",
            severity=AlertSeverity.WARNING,
            category=AlertCategory.EQUITY,
            title="Test",
            message="Test",
            timestamp=old_time,
        )

        age = alert.age_seconds()
        assert 58 < age < 62  # Allow 2 second margin

    def test_alert_to_dict(self):
        """Test alert conversion to dictionary."""
        alert = Alert(
            alert_id="alert_1",
            severity=AlertSeverity.CRITICAL,
            category=AlertCategory.POSITION,
            title="Position Limit",
            message="Max positions exceeded",
            data={"current": 5, "max": 3},
        )

        alert_dict = alert.to_dict()

        assert alert_dict["alert_id"] == "alert_1"
        assert alert_dict["severity"] == "critical"
        assert alert_dict["category"] == "position"
        assert alert_dict["data"]["current"] == 5


class TestAlertManagerInit:
    """Test alert manager initialization."""

    def test_init_with_defaults(self):
        """Test manager initialization with defaults."""
        manager = AlertManager()

        assert manager.max_alert_history == 10000
        assert len(manager.alerts) == 0

    def test_init_with_custom_max_history(self):
        """Test manager with custom max history."""
        manager = AlertManager(max_alert_history=5000)

        assert manager.max_alert_history == 5000

    def test_init_with_invalid_max_history(self):
        """Test that invalid max history raises error."""
        with pytest.raises(ValueError):
            AlertManager(max_alert_history=50)


class TestAlertCreation:
    """Test alert creation."""

    def test_create_alert_basic(self):
        """Test creating a basic alert."""
        manager = AlertManager()

        alert = manager.create_alert(
            severity=AlertSeverity.WARNING,
            category=AlertCategory.EQUITY,
            title="Equity Alert",
            message="Equity has changed",
        )

        assert alert.severity == AlertSeverity.WARNING
        assert alert.category == AlertCategory.EQUITY
        assert alert.alert_id in manager.alerts

    def test_create_alert_with_data(self):
        """Test creating alert with metadata."""
        manager = AlertManager()

        alert = manager.create_alert(
            severity=AlertSeverity.CRITICAL,
            category=AlertCategory.POSITION,
            title="Position Limit",
            message="Exceeded limit",
            data={"current": 5, "max": 3},
        )

        assert alert.data["current"] == 5
        assert alert.data["max"] == 3

    def test_create_alert_invalid_title(self):
        """Test that invalid title raises error."""
        manager = AlertManager()

        with pytest.raises(ValueError):
            manager.create_alert(
                severity=AlertSeverity.WARNING,
                category=AlertCategory.EQUITY,
                title="",  # Empty title
                message="Test",
            )

    def test_create_alert_invalid_message(self):
        """Test that invalid message raises error."""
        manager = AlertManager()

        with pytest.raises(ValueError):
            manager.create_alert(
                severity=AlertSeverity.WARNING,
                category=AlertCategory.EQUITY,
                title="Test",
                message="",  # Empty message
            )

    def test_create_alert_title_too_long(self):
        """Test that too-long title raises error."""
        manager = AlertManager()

        with pytest.raises(ValueError):
            manager.create_alert(
                severity=AlertSeverity.WARNING,
                category=AlertCategory.EQUITY,
                title="x" * 201,  # > 200 chars
                message="Test",
            )

    def test_create_alert_message_too_long(self):
        """Test that too-long message raises error."""
        manager = AlertManager()

        with pytest.raises(ValueError):
            manager.create_alert(
                severity=AlertSeverity.WARNING,
                category=AlertCategory.EQUITY,
                title="Test",
                message="x" * 2001,  # > 2000 chars
            )


class TestAlertHandlers:
    """Test alert handler registration and dispatch."""

    def test_register_severity_handler(self):
        """Test registering handler for severity."""
        manager = AlertManager()

        called = []

        def handler(alert: Alert) -> None:
            called.append(alert)

        manager.register_severity_handler(AlertSeverity.CRITICAL, handler)

        alert = manager.create_alert(
            severity=AlertSeverity.CRITICAL, category=AlertCategory.EQUITY, title="Critical", message="Test"
        )

        assert len(called) == 1
        assert called[0].alert_id == alert.alert_id

    def test_register_category_handler(self):
        """Test registering handler for category."""
        manager = AlertManager()

        called = []

        def handler(alert: Alert) -> None:
            called.append(alert)

        manager.register_category_handler(AlertCategory.ORDER, handler)

        manager.create_alert(
            severity=AlertSeverity.WARNING, category=AlertCategory.ORDER, title="Order Alert", message="Test"
        )

        assert len(called) == 1

    def test_register_invalid_handler(self):
        """Test that non-callable handler raises error."""
        manager = AlertManager()

        with pytest.raises(ValueError):
            manager.register_severity_handler(AlertSeverity.WARNING, "not callable")  # pyright: ignore[reportArgumentType]


class TestAlertRetrieval:
    """Test alert retrieval and filtering."""

    def test_get_alert_by_id(self):
        """Test getting alert by ID."""
        manager = AlertManager()

        alert = manager.create_alert(
            severity=AlertSeverity.WARNING, category=AlertCategory.EQUITY, title="Test", message="Test"
        )

        retrieved = manager.get_alert(alert.alert_id)
        assert retrieved.alert_id == alert.alert_id

    def test_get_nonexistent_alert(self):
        """Test that getting nonexistent alert raises error."""
        manager = AlertManager()

        with pytest.raises(KeyError):
            manager.get_alert("nonexistent")

    def test_get_active_alerts(self):
        """Test getting active alerts."""
        manager = AlertManager()

        alert1 = manager.create_alert(
            severity=AlertSeverity.WARNING, category=AlertCategory.EQUITY, title="Alert 1", message="Test"
        )

        alert2 = manager.create_alert(
            severity=AlertSeverity.CRITICAL, category=AlertCategory.ORDER, title="Alert 2", message="Test"
        )

        # Resolve one alert
        manager.resolve_alert(alert1.alert_id)

        active = manager.get_active_alerts()

        assert len(active) == 1
        assert active[0].alert_id == alert2.alert_id

    def test_get_active_alerts_by_severity(self):
        """Test filtering active alerts by severity."""
        manager = AlertManager()

        manager.create_alert(
            severity=AlertSeverity.WARNING, category=AlertCategory.EQUITY, title="Warning", message="Test"
        )

        manager.create_alert(
            severity=AlertSeverity.CRITICAL, category=AlertCategory.ORDER, title="Critical", message="Test"
        )

        critical = manager.get_active_alerts(severity=AlertSeverity.CRITICAL)

        assert len(critical) == 1
        assert critical[0].severity == AlertSeverity.CRITICAL

    def test_get_unacknowledged_alerts(self):
        """Test getting unacknowledged alerts."""
        manager = AlertManager()

        alert1 = manager.create_alert(
            severity=AlertSeverity.WARNING, category=AlertCategory.EQUITY, title="Test 1", message="Test"
        )

        alert2 = manager.create_alert(
            severity=AlertSeverity.WARNING, category=AlertCategory.EQUITY, title="Test 2", message="Test"
        )

        manager.acknowledge_alert(alert1.alert_id)

        unack = manager.get_unacknowledged_alerts()

        assert len(unack) == 1
        assert unack[0].alert_id == alert2.alert_id

    def test_get_critical_alerts(self):
        """Test getting critical alerts."""
        manager = AlertManager()

        manager.create_alert(
            severity=AlertSeverity.WARNING, category=AlertCategory.EQUITY, title="Warning", message="Test"
        )

        critical_alert = manager.create_alert(
            severity=AlertSeverity.CRITICAL, category=AlertCategory.ORDER, title="Critical", message="Test"
        )

        critical = manager.get_critical_alerts()

        assert len(critical) == 1
        assert critical[0].alert_id == critical_alert.alert_id


class TestAlertStatistics:
    """Test alert statistics."""

    def test_get_alert_statistics(self):
        """Test getting alert statistics."""
        manager = AlertManager()

        manager.create_alert(
            severity=AlertSeverity.WARNING, category=AlertCategory.EQUITY, title="Test 1", message="Test"
        )

        manager.create_alert(
            severity=AlertSeverity.CRITICAL, category=AlertCategory.ORDER, title="Test 2", message="Test"
        )

        stats = manager.get_alert_statistics()

        assert stats["total_alerts"] == 2
        assert stats["active_count"] == 2
        assert stats["by_severity"]["warning"] == 1
        assert stats["by_severity"]["critical"] == 1


class TestDashboardStatus:
    """Test dashboard status generation."""

    def test_get_dashboard_status_ok(self):
        """Test dashboard status when all OK."""
        manager = AlertManager()

        status = manager.get_dashboard_status()

        assert status["overall_status"] == "OK"
        assert status["active_alert_count"] == 0
        assert status["critical_count"] == 0

    def test_get_dashboard_status_warning(self):
        """Test dashboard status with warnings."""
        manager = AlertManager()

        manager.create_alert(
            severity=AlertSeverity.WARNING,
            category=AlertCategory.EQUITY,
            title="Low Equity",
            message="Equity dropped 5%",
        )

        status = manager.get_dashboard_status()

        assert status["overall_status"] == "WARNING"
        assert status["active_alert_count"] == 1

    def test_get_dashboard_status_critical(self):
        """Test dashboard status with critical alerts."""
        manager = AlertManager()

        manager.create_alert(
            severity=AlertSeverity.CRITICAL, category=AlertCategory.POSITION, title="Critical Issue", message="Test"
        )

        status = manager.get_dashboard_status()

        assert status["overall_status"] == "CRITICAL"
        assert status["critical_count"] == 1


class TestAlertExport:
    """Test alert export functionality."""

    def test_export_alerts_json(self):
        """Test exporting alerts as JSON."""
        manager = AlertManager()

        alert = manager.create_alert(
            severity=AlertSeverity.WARNING, category=AlertCategory.EQUITY, title="Test Alert", message="Test message"
        )

        json_str = manager.export_alerts_json()
        alerts_list = json.loads(json_str)

        assert len(alerts_list) > 0
        assert alerts_list[0]["alert_id"] == alert.alert_id
        assert alerts_list[0]["title"] == "Test Alert"


class TestAlertGenerators:
    """Test alert generator functions."""

    def test_alert_equity_drop_triggered(self):
        """Test equity drop alert is triggered."""
        manager = AlertManager()

        alert = alert_equity_drop(
            manager,
            current_equity=95000.0,
            previous_equity=100000.0,
            threshold_pct=1.0,  # 5% drop > 1% threshold
        )

        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING
        assert alert.data["drop_pct"] == 5.0

    def test_alert_equity_drop_critical(self):
        """Test equity drop alert is CRITICAL for large drops."""
        manager = AlertManager()

        alert = alert_equity_drop(
            manager,
            current_equity=88000.0,  # 12% drop
            previous_equity=100000.0,
            threshold_pct=1.0,
        )

        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL

    def test_alert_equity_drop_not_triggered(self):
        """Test equity drop alert not triggered."""
        manager = AlertManager()

        alert = alert_equity_drop(
            manager,
            current_equity=99000.0,  # 1% drop
            previous_equity=100000.0,
            threshold_pct=5.0,  # Need 5% drop
        )

        assert alert is None

    def test_alert_reconciliation_failure(self):
        """Test reconciliation failure alert."""
        manager = AlertManager()

        alert = alert_reconciliation_failure(manager, divergence_count=3, equity_diff_pct=0.8)

        assert alert is not None
        assert alert.category == AlertCategory.RECONCILIATION
        assert "3 divergences" in alert.message

    def test_alert_position_limit_breach(self):
        """Test position limit breach alert."""
        manager = AlertManager()

        alert = alert_position_limit_breach(manager, current_positions=5, max_positions=5)

        assert alert is not None
        assert alert.category == AlertCategory.POSITION
        assert "5/5" in alert.message

    def test_alert_order_timeout(self):
        """Test order timeout alert."""
        manager = AlertManager()

        alert = alert_order_timeout(manager, order_id="order_123", symbol="AAPL", timeout_seconds=300.0)

        assert alert is not None
        assert alert.category == AlertCategory.ORDER
        assert "order_123" in alert.message
        assert "AAPL" in alert.message


class TestAlertIntegration:
    """Integration tests for alert workflows."""

    def test_complete_alert_workflow(self):
        """Test complete alert workflow."""
        manager = AlertManager()

        # Create multiple alerts
        alert1 = manager.create_alert(
            severity=AlertSeverity.INFO, category=AlertCategory.EQUITY, title="Info", message="Informational"
        )

        alert2 = manager.create_alert(
            severity=AlertSeverity.CRITICAL, category=AlertCategory.POSITION, title="Critical", message="Critical issue"
        )

        # Acknowledge one
        manager.acknowledge_alert(alert1.alert_id, "operator")
        assert manager.get_alert(alert1.alert_id).is_acknowledged()

        # Resolve one
        manager.resolve_alert(alert2.alert_id)
        assert manager.get_alert(alert2.alert_id).is_resolved()

        # Check dashboard
        status = manager.get_dashboard_status()
        assert status["active_alert_count"] == 1  # Only alert1 still active

