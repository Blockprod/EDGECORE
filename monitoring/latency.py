"""Real-time latency measurement and monitoring system.

Tracks latency for operations across components:
- Event-based timing with high precision
- Percentile calculations (p50, p95, p99, p99.9)
- SLA budget tracking
- Alert generation for threshold violations
"""

import logging
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from common.types import LatencyBudget, LatencyMetrics

logger = logging.getLogger(__name__)


@dataclass
class LatencyMeasurement_Internal:
    """Internal latency measurement."""

    operation: str
    component_source: str
    component_dest: str
    latency_ms: float
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    metadata: dict = field(default_factory=dict)


class LatencyTracker:
    """Tracks latency for individual operations."""

    def __init__(self, operation: str):
        """
        Initialize tracker.

        Args:
            operation: Operation name
        """
        self.operation = operation
        self.measurements: list[LatencyMeasurement_Internal] = []
        self.start_times: dict[int, float] = {}  # Thread/task ID -> start time
        self.errors: list[str] = []

    def start(self, task_id: int | None = None) -> float:
        """
        Start timing.

        Args:
            task_id: Optional task identifier

        Returns:
            Start time (for reference)
        """
        task_id = task_id or id(self)
        start_time = time.time() * 1000  # Convert to ms
        self.start_times[task_id] = start_time
        return start_time

    def end(
        self,
        task_id: int | None = None,
        component_source: str = "unknown",
        component_dest: str = "unknown",
        success: bool = True,
        metadata: dict | None = None,
    ) -> float:
        """
        End timing and record measurement.

        Args:
            task_id: Task identifier (must match start())
            component_source: Source component
            component_dest: Destination component
            success: Whether operation succeeded
            metadata: Additional metadata

        Returns:
            Duration in milliseconds
        """
        task_id = task_id or id(self)

        if task_id not in self.start_times:
            raise ValueError(f"No start time for task {task_id}")

        end_time = time.time() * 1000
        latency_ms = end_time - self.start_times[task_id]

        # Record measurement
        measurement = LatencyMeasurement_Internal(
            operation=self.operation,
            component_source=component_source,
            component_dest=component_dest,
            latency_ms=latency_ms,
            success=success,
            metadata=metadata or {},
        )

        self.measurements.append(measurement)
        del self.start_times[task_id]

        return latency_ms

    def get_latencies(self, success_only: bool = True) -> list[float]:
        """
        Get all recorded latencies.

        Args:
            success_only: Only include successful measurements

        Returns:
            List of latency values in milliseconds
        """
        if success_only:
            return [m.latency_ms for m in self.measurements if m.success]
        return [m.latency_ms for m in self.measurements]

    def calculate_metrics(self, success_only: bool = True) -> LatencyMetrics | None:
        """
        Calculate aggregate metrics.

        Args:
            success_only: Only include successful measurements

        Returns:
            LatencyMetrics or None if no measurements
        """
        latencies = self.get_latencies(success_only=success_only)

        if not latencies:
            return None

        self.measurements if not success_only else [m for m in self.measurements if m.success]
        sum(1 for m in self.measurements if not m.success)

        return {
            "operation": self.operation,
            "total_measurements": len(latencies),
            "min_ms": float(min(latencies)),
            "max_ms": float(max(latencies)),
            "mean_ms": float(statistics.mean(latencies)),
            "median_ms": float(statistics.median(latencies)),
            "p95_ms": float(np.percentile(latencies, 95)) if len(latencies) > 1 else float(max(latencies)),
            "p99_ms": float(np.percentile(latencies, 99)) if len(latencies) > 1 else float(max(latencies)),
            "p99_9_ms": float(np.percentile(latencies, 99.9)) if len(latencies) > 1 else float(max(latencies)),
            "stdev_ms": float(statistics.stdev(latencies)) if len(latencies) > 1 else 0.0,
            "success_rate_pct": ((len(latencies) / len(self.measurements)) * 100) if self.measurements else 100.0,
        }


class LatencyMonitor:
    """Monitor latency across multiple operations."""

    def __init__(self, service_name: str):
        """
        Initialize monitor.

        Args:
            service_name: Name of monitored service
        """
        self.service_name = service_name
        self.trackers: dict[str, LatencyTracker] = defaultdict(lambda: LatencyTracker(""))
        self.budgets: dict[str, LatencyBudget] = {}
        self.alerts: list[dict] = []

    def start_operation(self, operation: str, task_id: int | None = None) -> LatencyTracker:
        """
        Start tracking an operation.

        Args:
            operation: Operation name
            task_id: Optional task identifier

        Returns:
            LatencyTracker for this operation
        """
        if operation not in self.trackers:
            self.trackers[operation] = LatencyTracker(operation)

        tracker = self.trackers[operation]
        tracker.start(task_id)

        return tracker

    def end_operation(
        self,
        operation: str,
        task_id: int | None = None,
        component_source: str = "unknown",
        component_dest: str = "unknown",
        success: bool = True,
    ) -> float:
        """
        End operation tracking.

        Args:
            operation: Operation name
            task_id: Task identifier
            component_source: Source component
            component_dest: Destination component
            success: Whether operation succeeded

        Returns:
            Duration in milliseconds
        """
        tracker = self.trackers[operation]
        latency = tracker.end(
            task_id=task_id,
            component_source=component_source,
            component_dest=component_dest,
            success=success,
        )

        # Check SLA
        self._check_sla(operation, latency)

        return latency

    def record_measurement(
        self,
        operation: str,
        latency_ms: float,
        component_source: str = "unknown",
        component_dest: str = "unknown",
        success: bool = True,
    ) -> None:
        """
        Record a direct measurement.

        Args:
            operation: Operation name
            latency_ms: Measured latency
            component_source: Source component
            component_dest: Destination component
            success: Whether operation succeeded
        """
        if operation not in self.trackers:
            self.trackers[operation] = LatencyTracker(operation)

        # Create measurement directly
        measurement = LatencyMeasurement_Internal(
            operation=operation,
            component_source=component_source,
            component_dest=component_dest,
            latency_ms=latency_ms,
            success=success,
        )

        self.trackers[operation].measurements.append(measurement)
        self._check_sla(operation, latency_ms)

    def set_sla_budget(self, budget: LatencyBudget) -> None:
        """
        Set SLA budget for operation.

        Args:
            budget: LatencyBudget specification
        """
        self.budgets[budget["operation"]] = budget
        logger.info(f"Set SLA budget for {budget['operation']}: p95={budget['p95_target_ms']}ms")

    def _check_sla(self, operation: str, latency_ms: float) -> None:
        """Check if measurement violates SLA."""
        if operation not in self.budgets:
            return

        budget = self.budgets[operation]

        if latency_ms > budget["alert_threshold_ms"]:
            alert = {
                "operation": operation,
                "latency_ms": latency_ms,
                "threshold_ms": budget["alert_threshold_ms"],
                "timestamp": datetime.now(),
                "severity": "warning" if latency_ms < budget["p99_target_ms"] else "error",
            }
            self.alerts.append(alert)

            severity = alert["severity"]
            logger.warning(f"ÔÜá´©Å  SLA alert ({severity}): {operation} took {latency_ms:.1f}ms")

    def get_metrics(self, operation: str) -> LatencyMetrics | None:
        """
        Get metrics for operation.

        Args:
            operation: Operation name

        Returns:
            LatencyMetrics or None
        """
        if operation not in self.trackers:
            return None

        return self.trackers[operation].calculate_metrics()

    def get_all_metrics(self) -> dict[str, LatencyMetrics]:
        """Get metrics for all operations."""
        metrics = {}
        for operation, tracker in self.trackers.items():
            op_metrics = tracker.calculate_metrics()
            if op_metrics:
                metrics[operation] = op_metrics
        return metrics

    def get_alerts(self, operation: str | None = None) -> list[dict]:
        """
        Get recent alerts.

        Args:
            operation: Optional operation name filter

        Returns:
            List of alert dictionaries
        """
        if operation:
            return [a for a in self.alerts if a["operation"] == operation]
        return self.alerts

    def get_summary(self) -> dict:
        """Get summary of all operations."""
        all_metrics = self.get_all_metrics()

        return {
            "service_name": self.service_name,
            "operations_monitored": len(all_metrics),
            "total_measurements": sum(m["total_measurements"] for m in all_metrics.values()),
            "total_alerts": len(self.alerts),
            "operations": all_metrics,
            "recent_alerts": self.alerts[-10:],  # Last 10 alerts
        }


# Global monitor instance
_global_monitor: LatencyMonitor | None = None


def initialize_global_latency_monitor(service_name: str) -> LatencyMonitor:
    """Initialize global latency monitor."""
    global _global_monitor
    _global_monitor = LatencyMonitor(service_name)
    logger.info(f"Initialized global latency monitor for {service_name}")
    return _global_monitor


def get_global_latency_monitor() -> LatencyMonitor:
    """Get global latency monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = LatencyMonitor("default-service")
    return _global_monitor


class LatencyContext:
    """Context manager for latency tracking."""

    def __init__(
        self,
        operation: str,
        component_source: str = "unknown",
        component_dest: str = "unknown",
    ):
        """
        Initialize context.

        Args:
            operation: Operation name
            component_source: Source component
            component_dest: Destination component
        """
        self.operation = operation
        self.component_source = component_source
        self.component_dest = component_dest
        self.start_time = None

    def __enter__(self):
        """Start latency tracking."""
        self.start_time = time.time() * 1000
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End latency tracking."""
        monitor = get_global_latency_monitor()
        end_time = time.time() * 1000
        latency_ms = end_time - (self.start_time or 0.0)

        success = exc_type is None
        monitor.record_measurement(
            operation=self.operation,
            latency_ms=latency_ms,
            component_source=self.component_source,
            component_dest=self.component_dest,
            success=success,
        )

        if success:
            logger.debug(f"ÔÅ▒´©Å  {self.operation}: {latency_ms:.2f}ms")
        else:
            logger.error(f"ÔØî {self.operation} failed: {latency_ms:.2f}ms")
