"""
Performance profiling for backtest and execution engines.

Provides:
- Function-level execution time tracking
- Memory usage monitoring
- Bottleneck identification
- Performance regression detection
"""

import functools
import statistics
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable


@dataclass
class PerformanceMetric:
    """Individual performance measurement."""

    function_name: str
    execution_time_ms: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    args_signature: str | None = None
    error: str | None = None


@dataclass
class PerformanceStats:
    """Aggregated performance statistics."""

    function_name: str
    call_count: int
    total_time_ms: float
    min_time_ms: float
    max_time_ms: float
    mean_time_ms: float
    median_time_ms: float
    stdev_time_ms: float
    p95_time_ms: float
    p99_time_ms: float
    error_count: int = 0
    error_rate_pct: float = 0.0


class PerformanceProfiler:
    """Profile function execution times and identify bottlenecks."""

    def __init__(self, name: str = "default"):
        self.name = name
        self.metrics: dict[str, list[PerformanceMetric]] = {}

    def profile_function(self, func: Callable, *args: Any, **kwargs: Any) -> tuple[Any, float]:
        """
        Profile a single function call.

        Args:
            func: Function to profile
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Tuple of (result, execution_time_ms)
        """
        start_time = time.perf_counter()
        error = None
        result = None

        try:
            result = func(*args, **kwargs)
        except Exception as e:
            error = str(e)
            raise
        finally:
            end_time = time.perf_counter()
            execution_time_ms = (end_time - start_time) * 1000

            # Record metric
            func_name = func.__name__
            metric = PerformanceMetric(
                function_name=func_name,
                execution_time_ms=execution_time_ms,
                args_signature=self._get_args_signature(*args, **kwargs),
                error=error,
            )

            if func_name not in self.metrics:
                self.metrics[func_name] = []
            self.metrics[func_name].append(metric)

        return result, execution_time_ms

    def decorator(self, func: Callable) -> Callable:
        """
        Decorator to profile a function.

        Usage:
            @profiler.decorator
            def my_function():
                pass
        """

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result, _ = self.profile_function(func, *args, **kwargs)
            return result

        return wrapper

    def get_stats(self, function_name: str | None = None) -> PerformanceStats | dict[str, PerformanceStats] | None:
        """
        Get aggregated statistics for function(s).

        Args:
            function_name: Specific function name, or None for all

        Returns:
            PerformanceStats for function, or dict of all stats
        """
        if function_name:
            if function_name not in self.metrics:
                return None
            return self._calculate_stats(function_name, self.metrics[function_name])
        else:
            return {name: self._calculate_stats(name, metrics) for name, metrics in self.metrics.items()}

    def _calculate_stats(self, func_name: str, metrics: list[PerformanceMetric]) -> PerformanceStats:
        """Calculate statistics from metrics."""
        times = [m.execution_time_ms for m in metrics if m.error is None]
        errors = [m for m in metrics if m.error is not None]

        if not times:
            times = [0.0]

        total_time = sum(times)
        return PerformanceStats(
            function_name=func_name,
            call_count=len(metrics),
            total_time_ms=total_time,
            min_time_ms=min(times),
            max_time_ms=max(times),
            mean_time_ms=statistics.mean(times),
            median_time_ms=statistics.median(times),
            stdev_time_ms=statistics.stdev(times) if len(times) > 1 else 0.0,
            p95_time_ms=self._percentile(times, 0.95),
            p99_time_ms=self._percentile(times, 0.99),
            error_count=len(errors),
            error_rate_pct=(len(errors) / len(metrics) * 100) if metrics else 0.0,
        )

    @staticmethod
    def _percentile(data: list[float], percentile: float) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        return sorted_data[min(index, len(sorted_data) - 1)]

    def _get_args_signature(self, *args: Any, **kwargs: Any) -> str:
        """Create a string signature of arguments."""
        arg_types = [type(a).__name__ for a in args]
        kwarg_types = [f"{k}:{type(v).__name__}" for k, v in kwargs.items()]
        return f"({', '.join(arg_types + kwarg_types)})"

    def report(self) -> str:
        """Generate performance report."""
        if not self.metrics:
            return "No metrics recorded."

        report_lines = [f"Performance Report: {self.name}"]
        report_lines.append("=" * 80)

        stats_dict = self.get_stats()

        # get_stats() with no arg returns dict[str, PerformanceStats] | None
        if not isinstance(stats_dict, dict) or not stats_dict:
            return "No stats available."

        # Sort by total time (descending)
        sorted_stats = sorted(
            stats_dict.items(),
            key=lambda item: item[1].total_time_ms,
            reverse=True,
        )

        for name, stats in sorted_stats:
            report_lines.append(f"\n{name}:")
            report_lines.append(f"  Calls:        {stats.call_count}")
            report_lines.append(f"  Total:        {stats.total_time_ms:.2f} ms")
            report_lines.append(f"  Mean:         {stats.mean_time_ms:.2f} ms")
            report_lines.append(f"  Median:       {stats.median_time_ms:.2f} ms")
            report_lines.append(f"  Min:          {stats.min_time_ms:.2f} ms")
            report_lines.append(f"  Max:          {stats.max_time_ms:.2f} ms")
            report_lines.append(f"  StdDev:       {stats.stdev_time_ms:.2f} ms")
            report_lines.append(f"  P95:          {stats.p95_time_ms:.2f} ms")
            report_lines.append(f"  P99:          {stats.p99_time_ms:.2f} ms")
            if stats.error_count > 0:
                report_lines.append(f"  Errors:       {stats.error_count} ({stats.error_rate_pct:.1f}%)")

        return "\n".join(report_lines)

    def find_bottlenecks(self, threshold_pct: float = 10.0) -> list[tuple[str, PerformanceStats]]:
        """
        Find functions consuming > threshold% of total time.

        Args:
            threshold_pct: Percent threshold (default 10%)

        Returns:
            List of (function_name, stats) sorted by time consumed
        """
        stats_dict = self.get_stats()
        if not stats_dict or not isinstance(stats_dict, dict):
            return []
        total_time = sum(s.total_time_ms for s in stats_dict.values())

        if total_time == 0:
            return []

        bottlenecks = []
        for name, stats in stats_dict.items():
            percentage = (stats.total_time_ms / total_time) * 100
            if percentage >= threshold_pct:
                bottlenecks.append((name, stats))

        return sorted(bottlenecks, key=lambda item: item[1].total_time_ms, reverse=True)

    def reset(self) -> None:
        """Clear all metrics."""
        self.metrics = {}


# Global profiler instance
_global_profiler = PerformanceProfiler("global")


def profile(func: Callable) -> Callable:
    """Global profiler decorator."""
    return _global_profiler.decorator(func)


def get_global_profiler() -> PerformanceProfiler:
    """Get global profiler instance."""
    return _global_profiler


def reset_global_profiler() -> None:
    """Reset global profiler."""
    _global_profiler.reset()


@dataclass
class TimingContext:
    """Context manager for timing code blocks."""

    name: str
    profiler: PerformanceProfiler = field(default_factory=lambda: _global_profiler)
    start_time: float = field(default=0.0)
    end_time: float = field(default=0.0)

    def __enter__(self) -> "TimingContext":
        """Start timing."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop timing and record."""
        self.end_time = time.perf_counter()
        duration_ms = (self.end_time - self.start_time) * 1000

        # Record as if it were a function call
        metric = PerformanceMetric(
            function_name=self.name,
            execution_time_ms=duration_ms,
        )

        if self.name not in self.profiler.metrics:
            self.profiler.metrics[self.name] = []
        self.profiler.metrics[self.name].append(metric)

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self.end_time > 0:
            return (self.end_time - self.start_time) * 1000
        return 0.0


# Global timing context
def time_block(name: str, profiler: PerformanceProfiler | None = None) -> "TimingContext":
    """Create a timing context for a code block."""
    if profiler is None:
        profiler = _global_profiler
    return TimingContext(name, profiler)
