"""
Tests for performance profiling (Phase 4).

Covers:
- Function timing and metrics collection
- Statistical aggregation
- Bottleneck detection
- Decorator usage
- Context manager timing
"""

# pyright: reportUnusedVariable=false, reportAttributeAccessIssue=false, reportOptionalSubscript=false, reportOptionalIterable=false

import time

import pytest

from monitoring.profiler import (
    PerformanceMetric,
<<<<<<< HEAD
    PerformanceProfiler,
=======
>>>>>>> origin/main
    TimingContext,
    get_global_profiler,
    reset_global_profiler,
    time_block,
)

# ============================================================================
# PERFORMANCE PROFILER TESTS
# ============================================================================


class TestPerformanceProfiler:
    """Test PerformanceProfiler for function timing."""

    def test_profiler_creation(self) -> None:
        """Test profiler instantiation."""
        profiler = PerformanceProfiler("test")
        assert profiler.name == "test"
        assert len(profiler.metrics) == 0

    def test_profile_single_function(self) -> None:
        """Test profiling a single function call."""
        profiler = PerformanceProfiler("test")

        def simple_function() -> int:
            return 42

        result, time_ms = profiler.profile_function(simple_function)

        assert result == 42
        assert time_ms > 0
        assert "simple_function" in profiler.metrics

    def test_profile_slow_function(self) -> None:
        """Test profiling captures execution time."""
        profiler = PerformanceProfiler("test")

        def slow_function() -> None:
            time.sleep(0.01)  # 10ms

        result, time_ms = profiler.profile_function(slow_function)

        assert time_ms >= 10.0  # At least 10ms

    def test_profile_function_with_arguments(self) -> None:
        """Test profiling function with arguments."""
        profiler = PerformanceProfiler("test")

        def add_numbers(a: float, b: float) -> float:
            return a + b

        result, time_ms = profiler.profile_function(add_numbers, 5.0, 3.0)

        assert result == 8.0
        assert time_ms > 0

    def test_profile_function_exception(self) -> None:
        """Test profiling captures function exceptions."""
        profiler = PerformanceProfiler("test")

        def failing_function() -> None:
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            profiler.profile_function(failing_function)

        # Error should be recorded
        assert "failing_function" in profiler.metrics
        metrics = profiler.metrics["failing_function"]
        assert len(metrics) == 1
        assert metrics[0].error is not None

    def test_decorator_basic(self) -> None:
        """Test decorator basic functionality."""
        profiler = PerformanceProfiler("test")

        @profiler.decorator
        def decorated_func() -> str:
            return "hello"

        result = decorated_func()

        assert result == "hello"
        assert "decorated_func" in profiler.metrics

    def test_decorator_with_arguments(self) -> None:
        """Test decorator preserves function arguments."""
        profiler = PerformanceProfiler("test")

        @profiler.decorator
        def multiply(a: int, b: int) -> int:
            return a * b

        result = multiply(3, 4)

        assert result == 12
        assert "multiply" in profiler.metrics

    def test_multiple_calls_aggregation(self) -> None:
        """Test profiler aggregates multiple calls."""
        profiler = PerformanceProfiler("test")

        def sample_func() -> int:
            return 1

        for _ in range(5):
            profiler.profile_function(sample_func)

        metrics = profiler.metrics["sample_func"]
        assert len(metrics) == 5

    def test_get_stats_single_function(self) -> None:
        """Test getting statistics for single function."""
        profiler = PerformanceProfiler("test")

        def test_func() -> None:
            time.sleep(0.001)

        for _ in range(3):
            profiler.profile_function(test_func)

        stats = profiler.get_stats("test_func")

        assert stats is not None
        assert stats.call_count == 3
        assert stats.mean_time_ms > 0
        assert stats.min_time_ms > 0
        assert stats.max_time_ms > 0
        assert stats.median_time_ms > 0

    def test_get_stats_all_functions(self) -> None:
        """Test getting statistics for all functions."""
        profiler = PerformanceProfiler("test")

        def func_a() -> None:
            pass

        def func_b() -> None:
            pass

        profiler.profile_function(func_a)
        profiler.profile_function(func_b)

        all_stats = profiler.get_stats()

        assert isinstance(all_stats, dict)
        assert "func_a" in all_stats
        assert "func_b" in all_stats

    def test_stats_percentiles(self) -> None:
        """Test percentile calculations in stats."""
        profiler = PerformanceProfiler("test")

        def varying_func() -> None:
            # Create varying times
            pass

        # Create calls with roughly increasing times
        for i in range(100):
            profiler.metrics.setdefault("varying_func", []).append(
                PerformanceMetric(
                    function_name="varying_func",
                    execution_time_ms=float(i),
                )
            )

        stats = profiler.get_stats("varying_func")

        assert stats is not None
        assert stats.p95_time_ms > stats.mean_time_ms
        assert stats.p99_time_ms > stats.p95_time_ms
        assert stats.min_time_ms <= stats.median_time_ms <= stats.max_time_ms

    def test_report_generation(self) -> None:
        """Test report generation."""
        profiler = PerformanceProfiler("test")

        def func_a() -> None:
            pass

        profiler.profile_function(func_a)

        report = profiler.report()

        assert "Performance Report" in report
        assert "func_a" in report
        assert "Calls" in report
        assert "Total" in report
        assert "Mean" in report

    def test_find_bottlenecks(self) -> None:
        """Test bottleneck detection."""
        profiler = PerformanceProfiler("test")

        # Add metrics simulating bottleneck
        for i in range(10):
            if i < 5:
                # Fast function
                profiler.metrics.setdefault("fast_func", []).append(PerformanceMetric("fast_func", 1.0))
            else:
                # Slow function
                profiler.metrics.setdefault("slow_func", []).append(PerformanceMetric("slow_func", 50.0))

        bottlenecks = profiler.find_bottlenecks(threshold_pct=20.0)

        # Slow function should be detected as bottleneck
        assert len(bottlenecks) > 0
        assert any(name == "slow_func" for name, _ in bottlenecks)

    def test_reset_profiler(self) -> None:
        """Test resetting profiler."""
        profiler = PerformanceProfiler("test")

        def sample_func() -> None:
            pass

        profiler.profile_function(sample_func)
        assert len(profiler.metrics) > 0

        profiler.reset()
        assert len(profiler.metrics) == 0

    def test_error_handling_in_stats(self) -> None:
        """Test error rate tracking in stats."""
        profiler = PerformanceProfiler("test")

        # Add successful calls
        for _ in range(8):
            profiler.metrics.setdefault("test_func", []).append(PerformanceMetric("test_func", 1.0))

        # Add failed calls
        for _ in range(2):
            profiler.metrics.setdefault("test_func", []).append(PerformanceMetric("test_func", 0.5, error="Test error"))

        stats = profiler.get_stats("test_func")

        assert stats is not None
        assert stats.call_count == 10
        assert stats.error_count == 2
        assert stats.error_rate_pct == 20.0


# ============================================================================
# TIMING CONTEXT TESTS
# ============================================================================


class TestTimingContext:
    """Test TimingContext for code block timing."""

    def test_context_manager_basic(self) -> None:
        """Test basic context manager usage."""
        profiler = PerformanceProfiler("test")

        with TimingContext("test_block", profiler) as ctx:
            time.sleep(0.001)

        assert ctx.elapsed_ms > 0
        assert "test_block" in profiler.metrics

    def test_context_manager_timing_accuracy(self) -> None:
        """Test context manager timing accuracy."""
        profiler = PerformanceProfiler("test")

        with TimingContext("slow_block", profiler):
            time.sleep(0.010)

        metrics = profiler.metrics["slow_block"]
        assert metrics[0].execution_time_ms >= 10.0

    def test_nested_context_managers(self) -> None:
        """Test nested context managers."""
        profiler = PerformanceProfiler("test")

        with TimingContext("outer", profiler):
            time.sleep(0.001)
            with TimingContext("inner", profiler):
                time.sleep(0.001)

        assert "outer" in profiler.metrics
        assert "inner" in profiler.metrics

    def test_context_manager_with_exception(self) -> None:
        """Test context manager handles exceptions properly."""
        profiler = PerformanceProfiler("test")

        try:
            with TimingContext("failing_block", profiler):
                time.sleep(0.001)
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should still record timing
        assert "failing_block" in profiler.metrics
        assert profiler.metrics["failing_block"][0].execution_time_ms > 0

    def test_time_block_helper(self) -> None:
        """Test time_block helper function."""
        profiler = PerformanceProfiler("test")

        with time_block("helper_block", profiler):
            time.sleep(0.001)

        assert "helper_block" in profiler.metrics
        assert profiler.metrics["helper_block"][0].execution_time_ms > 0

    def test_multiple_blocks_same_name(self) -> None:
        """Test multiple timing blocks with same name aggregate."""
        profiler = PerformanceProfiler("test")

        for _ in range(3):
            with TimingContext("repeated_block", profiler):
                time.sleep(0.001)

        metrics = profiler.metrics["repeated_block"]
        assert len(metrics) == 3


# ============================================================================
# GLOBAL PROFILER TESTS
# ============================================================================


class TestGlobalProfiler:
    """Test global profiler instance."""

    def test_get_global_profiler(self) -> None:
        """Test retrieving global profiler."""
        profiler = get_global_profiler()
        assert profiler is not None
        assert profiler.name == "global"

    def test_reset_global_profiler(self) -> None:
        """Test resetting global profiler."""
        reset_global_profiler()
        profiler = get_global_profiler()
        assert len(profiler.metrics) == 0

    def test_global_profiler_usage(self) -> None:
        """Test using global profiler."""
        reset_global_profiler()
        profiler = get_global_profiler()

        def sample_func() -> int:
            return 42

        profiler.profile_function(sample_func)

        assert "sample_func" in profiler.metrics


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestProfilingIntegration:
    """Integration tests for performance profiling."""

    def test_profile_complex_workflow(self) -> None:
        """Test profiling realistic workflow."""
        reset_global_profiler()
        profiler = get_global_profiler()

        @profiler.decorator
        def setup() -> dict:
            time.sleep(0.002)
            return {"initialized": True}

        @profiler.decorator
        def process(data: dict) -> dict:
            time.sleep(0.005)
            return {**data, "processed": True}

        @profiler.decorator
        def cleanup(data: dict) -> None:
            _ = len(data)  # consume data param — cleanup tracks its size
            time.sleep(0.001)

        data = setup()
        data = process(data)
        cleanup(data)

        stats_dict = profiler.get_stats()
        assert isinstance(stats_dict, dict)

        assert "setup" in stats_dict
        assert "process" in stats_dict
        assert "cleanup" in stats_dict

        setup_stats = stats_dict["setup"]
        process_stats = stats_dict["process"]
        # Process should take longer than setup (5ms vs 2ms)
        # Allow some tolerance for timing variations
        assert process_stats.mean_time_ms >= setup_stats.mean_time_ms * 0.8

    def test_bottleneck_identification(self) -> None:
        """Test identifying performance bottlenecks."""
        reset_global_profiler()
        profiler = get_global_profiler()

        @profiler.decorator
        def fast_operation() -> None:
            time.sleep(0.001)

        @profiler.decorator
        def slow_operation() -> None:
            time.sleep(0.050)

        # Call slow many times
        for _ in range(5):
            slow_operation()

        # Call fast few times
        for _ in range(2):
            fast_operation()

        bottlenecks = profiler.find_bottlenecks(threshold_pct=30.0)

        # Slow operation should be bottleneck
        assert any(name == "slow_operation" for name, _ in bottlenecks)

    def test_profiling_real_computation(self) -> None:
        """Test profiling realistic computation."""
        reset_global_profiler()
        profiler = get_global_profiler()

        @profiler.decorator
        def fibonacci(n: int) -> int:
            if n <= 1:
                return n
            return fibonacci(n - 1) + fibonacci(n - 2)

        result = fibonacci(10)

        assert result == 55
        assert "fibonacci" in profiler.metrics

        stats = profiler.get_stats("fibonacci")
        assert stats is not None
        assert stats.call_count > 1  # Multiple recursive calls
        assert stats.mean_time_ms >= 0
