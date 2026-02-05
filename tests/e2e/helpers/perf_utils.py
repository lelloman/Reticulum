"""Performance measurement utilities for E2E tests."""

import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import statistics


@dataclass
class TimingResult:
    """Result of a timing measurement."""

    name: str
    duration_ms: float
    success: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Aggregated benchmark results."""

    name: str
    samples: List[float]
    unit: str = "ms"

    @property
    def count(self) -> int:
        return len(self.samples)

    @property
    def mean(self) -> float:
        if not self.samples:
            return 0.0
        return statistics.mean(self.samples)

    @property
    def median(self) -> float:
        if not self.samples:
            return 0.0
        return statistics.median(self.samples)

    @property
    def stdev(self) -> float:
        if len(self.samples) < 2:
            return 0.0
        return statistics.stdev(self.samples)

    @property
    def min(self) -> float:
        if not self.samples:
            return 0.0
        return min(self.samples)

    @property
    def max(self) -> float:
        if not self.samples:
            return 0.0
        return max(self.samples)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "count": self.count,
            "mean": self.mean,
            "median": self.median,
            "stdev": self.stdev,
            "min": self.min,
            "max": self.max,
            "unit": self.unit,
            "samples": self.samples,
        }


class PerformanceMetrics:
    """Utility class for collecting performance metrics."""

    def __init__(self, name: str = "benchmark"):
        self.name = name
        self.timings: List[TimingResult] = []
        self._start_time: Optional[float] = None

    def start(self) -> None:
        """Start a timing measurement."""
        self._start_time = time.perf_counter()

    def stop(self, name: str, success: bool = True, **metadata) -> TimingResult:
        """
        Stop timing and record result.

        Args:
            name: Name for this measurement
            success: Whether the operation succeeded
            **metadata: Additional metadata to record

        Returns:
            TimingResult with duration in milliseconds
        """
        if self._start_time is None:
            raise ValueError("Timer not started")

        duration_ms = (time.perf_counter() - self._start_time) * 1000
        self._start_time = None

        result = TimingResult(
            name=name,
            duration_ms=duration_ms,
            success=success,
            metadata=metadata,
        )
        self.timings.append(result)
        return result

    def time_operation(self, name: str):
        """
        Context manager for timing an operation.

        Usage:
            with metrics.time_operation("my_op") as t:
                do_something()
            print(t.duration_ms)
        """
        return _TimingContext(self, name)

    def measure_throughput(
        self, bytes_transferred: int, duration_ms: float
    ) -> Dict[str, float]:
        """
        Calculate throughput metrics.

        Args:
            bytes_transferred: Number of bytes transferred
            duration_ms: Duration in milliseconds

        Returns:
            Dict with throughput in various units
        """
        if duration_ms <= 0:
            return {"bytes_per_sec": 0, "kbps": 0, "mbps": 0}

        bytes_per_sec = (bytes_transferred / duration_ms) * 1000
        kbps = (bytes_per_sec * 8) / 1000
        mbps = kbps / 1000

        return {
            "bytes_per_sec": bytes_per_sec,
            "kbps": kbps,
            "mbps": mbps,
        }

    def get_benchmark(self, filter_name: Optional[str] = None) -> BenchmarkResult:
        """
        Get aggregated benchmark results.

        Args:
            filter_name: Optional filter to only include timings with this name

        Returns:
            BenchmarkResult with aggregated statistics
        """
        timings = self.timings
        if filter_name:
            timings = [t for t in timings if t.name == filter_name]

        successful = [t for t in timings if t.success]
        samples = [t.duration_ms for t in successful]

        return BenchmarkResult(
            name=filter_name or self.name,
            samples=samples,
        )

    def reset(self) -> None:
        """Clear all recorded timings."""
        self.timings.clear()
        self._start_time = None


class _TimingContext:
    """Context manager for timing operations."""

    def __init__(self, metrics: PerformanceMetrics, name: str):
        self.metrics = metrics
        self.name = name
        self.result: Optional[TimingResult] = None
        self._success = True
        self._metadata: Dict[str, Any] = {}

    def __enter__(self):
        self.metrics.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._success = False
            self._metadata["error"] = str(exc_val)
        # Remove 'success' from metadata if present to avoid duplicate kwarg
        metadata = {k: v for k, v in self._metadata.items() if k != "success"}
        self.result = self.metrics.stop(
            self.name, success=self._success, **metadata
        )
        return False  # Don't suppress exceptions

    @property
    def duration_ms(self) -> float:
        if self.result:
            return self.result.duration_ms
        return 0.0

    def set_metadata(self, **kwargs) -> None:
        """Set metadata to include in the result."""
        self._metadata.update(kwargs)


def format_benchmark_report(results: List[BenchmarkResult]) -> str:
    """
    Format benchmark results as a human-readable report.

    Args:
        results: List of benchmark results

    Returns:
        Formatted string report
    """
    lines = ["=" * 60, "Performance Benchmark Report", "=" * 60, ""]

    for r in results:
        lines.extend([
            f"Benchmark: {r.name}",
            "-" * 40,
            f"  Samples: {r.count}",
            f"  Mean:    {r.mean:.2f} {r.unit}",
            f"  Median:  {r.median:.2f} {r.unit}",
            f"  Stdev:   {r.stdev:.2f} {r.unit}",
            f"  Min:     {r.min:.2f} {r.unit}",
            f"  Max:     {r.max:.2f} {r.unit}",
            "",
        ])

    lines.append("=" * 60)
    return "\n".join(lines)
