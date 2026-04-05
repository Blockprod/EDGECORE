"""Distributed tracing system for monitoring execution flow.

Provides OpenTelemetry-like tracing capabilities for order execution:
- Trace span creation and tracking
- Context propagation across async operations
- Performance metrics collection
- Event logging within spans
- Hierarchical span relationships
"""

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import logging
from contextlib import contextmanager
import json
import logging
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from common.types import TraceContext, TraceLevel

logger = logging.getLogger(__name__)


@dataclass
class TraceEvent:
    """Single event logged within a trace span."""
    
    timestamp: datetime
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    level: TraceLevel = TraceLevel.INFO
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "name": self.name,
            "attributes": self.attributes,
            "level": self.level.value,
        }


@dataclass
class Span:
    """Internal span representation."""
    
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    start_time: datetime
    end_time: datetime | None = None
    status: str = "UNSET"
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[TraceEvent] = field(default_factory=list)
    level: TraceLevel = TraceLevel.INFO
    
    def add_event(self, name: str, attributes: dict[str, Any] | None = None, level: TraceLevel = TraceLevel.INFO) -> None:
        """Add event to span."""
        event = TraceEvent(
            timestamp=datetime.now(),
            name=name,
            attributes=attributes or {},
            level=level,
        )
        self.events.append(event)
    
    def set_attribute(self, key: str, value: Any) -> None:
        """Set span attribute."""
        self.attributes[key] = value
    
    def end(self, status: str = "OK") -> None:
        """End the span."""
        self.end_time = datetime.now()
        self.status = status
    
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        if self.end_time is None:
            return (datetime.now() - self.start_time).total_seconds() * 1000
        return (self.end_time - self.start_time).total_seconds() * 1000
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms(),
            "status": self.status,
            "attributes": self.attributes,
            "events": [e.to_dict() for e in self.events],
            "level": self.level.value,
        }


class TraceCollector:
    """Collects and aggregates trace spans."""
    
    def __init__(self, service_name: str):
        """
        Initialize collector.
        
        Args:
            service_name: Name of the service being traced
        """
        self.service_name = service_name
        self.spans: dict[str, Span] = {}
        self.traces: dict[str, list[Span]] = {}  # trace_id -> list of spans
    
    def add_span(self, span: Span) -> None:
        """Add completed span."""
        self.spans[span.span_id] = span
        
        if span.trace_id not in self.traces:
            self.traces[span.trace_id] = []
        self.traces[span.trace_id].append(span)
    
    def get_trace(self, trace_id: str) -> list[Span] | None:
        """Get all spans for a trace."""
        return self.traces.get(trace_id)
    
    def get_span(self, span_id: str) -> Span | None:
        """Get a single span by ID."""
        return self.spans.get(span_id)
    
    def get_statistics(self, trace_id: str) -> dict[str, Any]:
        """Get statistics for a trace."""
        spans = self.traces.get(trace_id, [])
        
        if not spans:
            return {}
        
        durations = [s.duration_ms() for s in spans if s.end_time]
        errors = [s for s in spans if s.status == "ERROR"]
        
        return {
            "trace_id": trace_id,
            "num_spans": len(spans),
            "total_duration_ms": sum(durations),
            "avg_span_duration_ms": sum(durations) / len(durations) if durations else 0,
            "min_span_duration_ms": min(durations) if durations else 0,
            "max_span_duration_ms": max(durations) if durations else 0,
            "total_errors": len(errors),
            "error_rate_pct": (len(errors) / len(spans)) * 100 if spans else 0,
            "operations": [s.name for s in spans],
        }
    
    def export_json(self) -> str:
        """Export all traces as JSON."""
        export_data = {
            "service": self.service_name,
            "traces": {
                trace_id: [s.to_dict() for s in spans]
                for trace_id, spans in self.traces.items()
            },
        }
        return json.dumps(export_data, indent=2)


class DistributedTracer:
    """Main distributed tracing system."""
    
    def __init__(self, service_name: str, default_level: TraceLevel = TraceLevel.INFO):
        """
        Initialize tracer.
        
        Args:
            service_name: Name of service being traced
            default_level: Default trace level
        """
        self.service_name = service_name
        self.default_level = default_level
        self.collector = TraceCollector(service_name)
        
        # Stack of active spans (for context)
        self._active_traces: dict[int, Span] = {}  # thread_id -> current span
        self._trace_stack: dict[int, list[Span]] = {}  # thread_id -> span stack
    
    def start_trace(self, name: str, attributes: dict[str, Any] | None = None) -> TraceContext:
        """
        Start a new trace (root span).
        
        Args:
            name: Operation name
            attributes: Initial attributes
        
        Returns:
            TraceContext with trace_id and span_id
        """
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None,
            name=name,
            start_time=datetime.now(),
            level=self.default_level,
        )
        
        if attributes:
            span.attributes.update(attributes)
        
        self._active_traces[id(span)] = span
        
        context: TraceContext = {
            "trace_id": trace_id,
            "span_id": span_id,
            "timestamp": datetime.now(),
            "source": self.service_name,
        }
        
        logger.debug(f"Started trace {trace_id} with span {span_id}")
        return context
    
    def start_span(
        self,
        trace_id: str,
        name: str,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        """
        Start a child span.
        
        Args:
            trace_id: Parent trace ID
            name: Operation name
            parent_span_id: Parent span ID (if None, becomes root)
            attributes: Initial attributes
        
        Returns:
            New Span object
        """
        span_id = str(uuid.uuid4())
        
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            start_time=datetime.now(),
            level=self.default_level,
        )
        
        if attributes:
            span.attributes.update(attributes)
        
        logger.debug(f"Started span {span_id} in trace {trace_id}")
        return span
    
    def end_span(self, span: Span, status: str = "OK") -> None:
        """
        End a span and collect it.
        
        Args:
            span: Span to end
            status: Final status (OK, ERROR, etc)
        """
        span.end(status)
        self.collector.add_span(span)
        
        logger.debug(f"Ended span {span.span_id} with status {status}")
    
    @contextmanager
    def trace_operation(
        self,
        name: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
        level: TraceLevel = TraceLevel.INFO,
    ):
        """
        Context manager for tracing an operation.
        
        Args:
            name: Operation name
            trace_id: Use existing trace (if None, creates new)
            parent_span_id: Parent span ID
            attributes: Initial attributes
            level: Trace level
        
        Yields:
            Span object
        """
        # Create or use trace
        if trace_id is None:
            context = self.start_trace(name, attributes)
            trace_id = context["trace_id"]
            span_id = context["span_id"]
        else:
            span_id = str(uuid.uuid4())
        
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            start_time=datetime.now(),
            level=level,
        )
        
        if attributes:
            span.attributes.update(attributes)
        
        try:
            yield span
            span.status = "OK"
        except Exception as e:
            span.status = "ERROR"
            span.add_event(
                "exception",
                {"error": str(e), "type": type(e).__name__},
                level=TraceLevel.ERROR,
            )
            raise
        finally:
            self.end_span(span, span.status)
    
    def get_trace_json(self, trace_id: str) -> str:
        """Get trace as JSON."""
        spans = self.collector.get_trace(trace_id)
        if not spans:
            return "{}"
        
        data = {
            "trace_id": trace_id,
            "spans": [s.to_dict() for s in spans],
        }
        return json.dumps(data, indent=2)
    
    def get_statistics(self, trace_id: str) -> dict[str, Any]:
        """Get trace statistics."""
        return self.collector.get_statistics(trace_id)


# Global tracer instance
_global_tracer: DistributedTracer | None = None


def initialize_global_tracer(service_name: str, level: TraceLevel = TraceLevel.INFO) -> DistributedTracer:
    """Initialize global tracer."""
    global _global_tracer
    _global_tracer = DistributedTracer(service_name, level)
    logger.info(f"Initialized global tracer for {service_name}")
    return _global_tracer


def get_global_tracer() -> DistributedTracer:
    """Get global tracer instance."""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = DistributedTracer("default-service")
    return _global_tracer


def trace(name: str, attributes: dict[str, Any] | None = None):
    """
    Decorator for tracing a function.
    
    Args:
        name: Trace name (defaults to function name)
        attributes: Initial attributes
    
    Usage:
        @trace("my_operation")
        def my_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        trace_name = name or func.__name__
        
        def wrapper(*args, **kwargs):
            tracer = get_global_tracer()
            with tracer.trace_operation(trace_name, attributes=attributes or {}):
                return func(*args, **kwargs)
        
        return wrapper
    
    return decorator
