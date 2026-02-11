"""Tests for real-time latency monitoring system."""

import pytest
import time
from datetime import datetime

from monitoring.latency import (
    LatencyMonitor,
    LatencyTracker,
    LatencyContext,
    initialize_global_latency_monitor,
    get_global_latency_monitor,
)
from common.types import LatencyBudget


class TestLatencyTracker:
    """Test LatencyTracker class."""
    
    def test_tracker_creation(self):
        """Test creating latency tracker."""
        tracker = LatencyTracker("test_operation")
        
        assert tracker.operation == "test_operation"
        assert len(tracker.measurements) == 0
    
    def test_start_and_end(self):
        """Test starting and ending timing."""
        tracker = LatencyTracker("operation_1")
        
        start_time = tracker.start()
        assert start_time > 0
        
        time.sleep(0.05)
        duration = tracker.end(
            component_source="client",
            component_dest="server",
            success=True,
        )
        
        assert duration >= 50  # At least 50ms
        assert len(tracker.measurements) == 1
    
    def test_multiple_measurements(self):
        """Test recording multiple measurements."""
        tracker = LatencyTracker("api_call")
        
        for i in range(5):
            tracker.start(task_id=i)
            time.sleep(0.01)
            duration = tracker.end(task_id=i)
            assert duration >= 10
        
        assert len(tracker.measurements) == 5
    
    def test_get_latencies(self):
        """Test retrieving latencies."""
        tracker = LatencyTracker("operation")
        
        for i in range(10):
            tracker.start(task_id=i)
            time.sleep(0.005 + i * 0.001)  # Variable sleep
            tracker.end(task_id=i, success=i % 2 == 0)  # Half successful
        
        all_latencies = tracker.get_latencies(success_only=False)
        success_latencies = tracker.get_latencies(success_only=True)
        
        assert len(all_latencies) == 10
        assert len(success_latencies) == 5
    
    def test_calculate_metrics(self):
        """Test metric calculation."""
        tracker = LatencyTracker("test_op")
        
        # Record some measurements
        for i in range(20):
            tracker.start(task_id=i)
            time.sleep(0.01 + i * 0.001)
            tracker.end(task_id=i)
        
        metrics = tracker.calculate_metrics()
        
        assert metrics is not None
        assert "min_ms" in metrics
        assert "max_ms" in metrics
        assert "mean_ms" in metrics
        assert "median_ms" in metrics
        assert "p95_ms" in metrics
        assert "p99_ms" in metrics
        assert metrics["total_measurements"] == 20
        assert metrics["success_rate_pct"] == 100.0


class TestLatencyMonitor:
    """Test LatencyMonitor class."""
    
    def test_monitor_creation(self):
        """Test creating monitor."""
        monitor = LatencyMonitor("trading_service")
        
        assert monitor.service_name == "trading_service"
        assert len(monitor.trackers) == 0
    
    def test_start_and_end_operation(self):
        """Test starting and ending operation."""
        monitor = LatencyMonitor("service")
        
        tracker = monitor.start_operation("order_submission")
        assert tracker is not None
        
        time.sleep(0.02)
        duration = monitor.end_operation("order_submission")
        
        assert duration >= 20
    
    def test_record_direct_measurement(self):
        """Test recording direct measurements."""
        monitor = LatencyMonitor("service")
        
        monitor.record_measurement(
            operation="api_call",
            latency_ms=42.5,
            component_source="client",
            component_dest="server",
            success=True,
        )
        
        metrics = monitor.get_metrics("api_call")
        assert metrics is not None
        assert metrics["min_ms"] == 42.5
        assert metrics["max_ms"] == 42.5
    
    def test_set_sla_budget(self):
        """Test setting SLA budget."""
        monitor = LatencyMonitor("service")
        
        budget: LatencyBudget = {
            "operation": "critical_operation",
            "p95_target_ms": 100.0,
            "p99_target_ms": 250.0,
            "alert_threshold_ms": 300.0,
        }
        
        monitor.set_sla_budget(budget)
        
        assert "critical_operation" in monitor.budgets
        assert monitor.budgets["critical_operation"]["p95_target_ms"] == 100.0
    
    def test_sla_violation_alert(self):
        """Test SLA violation detection."""
        monitor = LatencyMonitor("service")
        
        budget: LatencyBudget = {
            "operation": "fast_operation",
            "p95_target_ms": 50.0,
            "p99_target_ms": 100.0,
            "alert_threshold_ms": 150.0,
        }
        monitor.set_sla_budget(budget)
        
        # Record a measurement that violates SLA
        monitor.record_measurement(
            operation="fast_operation",
            latency_ms=200.0,  # Exceeds threshold
        )
        
        alerts = monitor.get_alerts("fast_operation")
        assert len(alerts) > 0
        assert alerts[0]["latency_ms"] == 200.0
    
    def test_get_all_metrics(self):
        """Test getting metrics for all operations."""
        monitor = LatencyMonitor("service")
        
        for op in ["op_1", "op_2", "op_3"]:
            for _ in range(5):
                monitor.record_measurement(op, latency_ms=10.0 + np.random.randn() * 2)
        
        all_metrics = monitor.get_all_metrics()
        
        assert len(all_metrics) == 3
        assert "op_1" in all_metrics
        assert "op_2" in all_metrics
        assert "op_3" in all_metrics
    
    def test_get_summary(self):
        """Test getting monitor summary."""
        monitor = LatencyMonitor("trading_system")
        
        # Record some operations
        for i in range(10):
            monitor.record_measurement(f"operation_{i}", latency_ms=10.0 + i * 1.0)
        
        # Set SLA budget for one operation
        budget: LatencyBudget = {
            "operation": "operation_5",
            "p95_target_ms": 10.0,
            "p99_target_ms": 20.0,
            "alert_threshold_ms": 25.0,
        }
        monitor.set_sla_budget(budget)
        
        # This should trigger alert
        monitor.record_measurement("operation_5", latency_ms=30.0)
        
        summary = monitor.get_summary()
        
        assert summary["service_name"] == "trading_system"
        assert summary["operations_monitored"] >= 10
        assert summary["total_measurements"] >= 10
        assert summary["total_alerts"] >= 1


class TestLatencyContext:
    """Test LatencyContext context manager."""
    
    def test_context_manager_success(self):
        """Test context manager for successful operation."""
        initialize_global_latency_monitor("test_service")
        
        with LatencyContext("test_op", "component_a", "component_b") as ctx:
            time.sleep(0.02)
        
        # Check that measurement was recorded
        monitor = get_global_latency_monitor()
        metrics = monitor.get_metrics("test_op")
        
        assert metrics is not None
        assert metrics["min_ms"] >= 20
    
    def test_context_manager_failure(self):
        """Test context manager for failed operation."""
        initialize_global_latency_monitor("test_service")
        monitor = get_global_latency_monitor()
        
        try:
            with LatencyContext("failing_op"):
                raise RuntimeError("Test error")
        except RuntimeError:
            pass
        
        # Check that failed measurement was recorded
        alerts = monitor.get_alerts("failing_op")
        # Note: alerts only recorded if SLA set, but measurement should exist
        status_ok = False
        for measurement in monitor.trackers["failing_op"].measurements:
            if not measurement.success:
                status_ok = True
        assert status_ok


class TestGlobalLatencyMonitor:
    """Test global monitor instance."""
    
    def test_initialize_global_monitor(self):
        """Test initializing global monitor."""
        monitor = initialize_global_latency_monitor("my_service")
        
        assert monitor.service_name == "my_service"
    
    def test_get_global_monitor(self):
        """Test getting global monitor."""
        initialize_global_latency_monitor("service_1")
        monitor1 = get_global_latency_monitor()
        monitor2 = get_global_latency_monitor()
        
        assert monitor1 is monitor2


class TestLatencyPercentiles:
    """Test percentile calculations."""
    
    def test_percentiles_calculation(self):
        """Test that percentiles are calculated correctly."""
        tracker = LatencyTracker("operation")
        
        # Record 100 measurements with known distribution
        latencies = list(range(1, 101))  # 1ms to 100ms
        for i, latency in enumerate(latencies):
            # Create measurement directly using the measurement class
            from monitoring.latency import LatencyMeasurement_Internal
            measurement = LatencyMeasurement_Internal(
                operation="operation",
                component_source="source",
                component_dest="dest",
                latency_ms=float(latency),
            )
            tracker.measurements.append(measurement)
        
        metrics = tracker.calculate_metrics()
        
        assert metrics is not None
        assert metrics["min_ms"] == 1.0
        assert metrics["max_ms"] == 100.0
        assert 45 < metrics["median_ms"] < 55  # Should be around 50
        assert 90 < metrics["p95_ms"] < 96
        assert 98 < metrics["p99_ms"] < 101


class TestLatencyIntegration:
    """Integration tests for latency monitoring."""
    
    def test_multi_operation_monitoring(self):
        """Test monitoring multiple operations."""
        monitor = LatencyMonitor("complex_service")
        
        operations = ["fetch_data", "process_data", "store_result"]
        
        # Set budgets
        for op in operations:
            budget: LatencyBudget = {
                "operation": op,
                "p95_target_ms": 100.0,
                "p99_target_ms": 200.0,
                "alert_threshold_ms": 250.0,
            }
            monitor.set_sla_budget(budget)
        
        # Simulate execution
        for op in operations:
            for trial in range(20):
                tracker = monitor.start_operation(op)
                time.sleep(0.01 + 0.001 * trial)
                duration = monitor.end_operation(op)
        
        # Verify all operations were tracked
        summary = monitor.get_summary()
        assert summary["operations_monitored"] == 3
        assert summary["total_measurements"] == 60
    
    def test_latency_budget_enforcement(self):
        """Test SLA budget enforcement."""
        monitor = LatencyMonitor("strict_service")
        
        budget: LatencyBudget = {
            "operation": "critical_path",
            "p95_target_ms": 10.0,
            "p99_target_ms": 20.0,
            "alert_threshold_ms": 15.0,
        }
        monitor.set_sla_budget(budget)
        
        # Record measurements within budget
        for _ in range(10):
            monitor.record_measurement("critical_path", latency_ms=5.0)
        
        # Record measurements that violate budget
        for _ in range(5):
            monitor.record_measurement("critical_path", latency_ms=20.0)
        
        alerts = monitor.get_alerts("critical_path")
        assert len(alerts) == 5  # 5 alerts for violations
    
    def test_performance_tracking(self):
        """Test tracking performance improvements."""
        monitor = LatencyMonitor("performance_service")
        
        # Simulate improvement over time
        operation = "improving_operation"
        
        # Phase 1: slow (100-110ms)
        for _ in range(50):
            monitor.record_measurement(operation, latency_ms=105.0)
        
        metrics1 = monitor.get_metrics(operation)
        mean1 = metrics1["mean_ms"]
        
        # Phase 2: improved (50-60ms)
        for _ in range(50):
            monitor.record_measurement(operation, latency_ms=55.0)
        
        metrics2 = monitor.get_metrics(operation)
        mean2 = metrics2["mean_ms"]
        
        # Overall mean should be roughly halfway
        assert mean1 > mean2


# Import numpy for random generation
try:
    import numpy as np
except ImportError:
    import random
    class np:
        @staticmethod
        def random():
            return random.random()
