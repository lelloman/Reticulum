"""E2E Performance Benchmark Tests.

Tests that measure and establish baselines for Reticulum performance.

Test IDs:
- PERF-001: Throughput - Establish baseline KB/s
- PERF-002: RTT Latency - Measure round-trip time
- PERF-003: Large Resource - 100KB transfer time
- PERF-004: Link Setup Time - Time to ACTIVE state
- PERF-005: Announce Propagation - 4-hop announce latency
"""

import pytest
import time
import os
import sys

# Add helpers to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers.perf_utils import PerformanceMetrics, format_benchmark_report


@pytest.mark.performance
class TestThroughput:
    """Measure data transfer throughput."""

    def test_baseline_throughput(self, node_a, node_c, unique_app_name):
        """
        PERF-001: Establish baseline throughput in KB/s.

        Transfer various sizes and measure throughput.
        """
        aspects = ["perf", "throughput"]
        metrics = PerformanceMetrics("throughput")

        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        # Test different sizes
        sizes = [1000, 5000, 10000]  # 1KB, 5KB, 10KB
        throughputs = []

        for size in sizes:
            test_data = os.urandom(size)

            with metrics.time_operation(f"transfer_{size}B") as t:
                result = node_a.create_link_and_send_resource(
                    destination_hash=dest["destination_hash"],
                    app_name=unique_app_name,
                    data=test_data,
                    aspects=aspects,
                    link_timeout=15.0,
                    resource_timeout=60.0,
                )
                t.set_metadata(size=size, completed=result.get("resource_completed"))

            if result.get("resource_completed"):
                tp = metrics.measure_throughput(size, t.duration_ms)
                throughputs.append(tp)
                print(f"  {size}B: {tp['kbps']:.2f} kbps in {t.duration_ms:.1f}ms")

        # Generate report
        benchmark = metrics.get_benchmark()
        assert benchmark.count > 0, "No successful transfers"

        # Report throughput with regression guard
        if throughputs:
            avg_kbps = sum(t["kbps"] for t in throughputs) / len(throughputs)
            print(f"\nAverage throughput: {avg_kbps:.2f} kbps")
            assert avg_kbps > 0.5, f"Throughput regression: {avg_kbps:.2f} kbps < 0.5 kbps minimum"


@pytest.mark.performance
class TestLatency:
    """Measure round-trip time latency."""

    def test_rtt_measurement(self, node_a, node_c, unique_app_name):
        """
        PERF-002: Measure round-trip time (RTT).

        The link RTT is measured during establishment.
        """
        aspects = ["perf", "rtt"]
        metrics = PerformanceMetrics("rtt")

        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        rtts = []

        # Measure RTT multiple times
        for i in range(5):
            with metrics.time_operation(f"link_rtt_{i}"):
                link = node_a.create_link(
                    destination_hash=dest["destination_hash"],
                    app_name=unique_app_name,
                    aspects=aspects,
                    timeout=15.0,
                )

            if link["status"] == "ACTIVE" and link.get("rtt"):
                rtts.append(link["rtt"] * 1000)  # Convert to ms
                print(f"  Link {i}: RTT = {link['rtt']*1000:.2f} ms")

        assert len(rtts) > 0, "No RTT measurements obtained"

        avg_rtt = sum(rtts) / len(rtts)
        print(f"\nAverage RTT: {avg_rtt:.2f} ms")


@pytest.mark.performance
@pytest.mark.slow
class TestLargeResource:
    """Test large resource transfer performance."""

    def test_large_transfer_time(self, node_a, node_c, unique_app_name):
        """
        PERF-003: Measure large resource transfer time.

        This is a longer test that transfers a significant amount of data.
        Note: Limited to 100KB due to command line argument size limits
        when passing hex-encoded data via docker exec.
        """
        aspects = ["perf", "large"]
        metrics = PerformanceMetrics("large_transfer")

        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        # 100KB of random data
        data_size = 100_000
        test_data = os.urandom(data_size)

        with metrics.time_operation("large_transfer") as t:
            result = node_a.create_link_and_send_resource(
                destination_hash=dest["destination_hash"],
                app_name=unique_app_name,
                data=test_data,
                aspects=aspects,
                link_timeout=30.0,
                resource_timeout=120.0,  # 2 minutes for 100KB transfer
                compress=True,
            )
            t.set_metadata(size=data_size)

        if result.get("resource_completed"):
            tp = metrics.measure_throughput(data_size, t.duration_ms)
            print(f"\n100KB Transfer Results:")
            print(f"  Duration: {t.duration_ms/1000:.2f} seconds")
            print(f"  Throughput: {tp['kbps']:.2f} kbps ({tp['mbps']:.3f} Mbps)")
        else:
            print(f"Transfer incomplete: {result.get('resource_progress', 0):.1f}%")

        assert result.get("resource_completed"), "100KB transfer did not complete"


@pytest.mark.performance
class TestLinkSetupTime:
    """Measure link establishment time."""

    def test_link_setup_duration(self, node_a, node_c, unique_app_name):
        """
        PERF-004: Measure time from link request to ACTIVE state.
        """
        aspects = ["perf", "setup"]
        metrics = PerformanceMetrics("link_setup")

        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        setup_times = []

        for i in range(5):
            with metrics.time_operation(f"link_setup_{i}") as t:
                link = node_a.create_link(
                    destination_hash=dest["destination_hash"],
                    app_name=unique_app_name,
                    aspects=aspects,
                    timeout=15.0,
                )

            if link["status"] == "ACTIVE":
                setup_times.append(t.duration_ms)
                print(f"  Link {i}: Setup time = {t.duration_ms:.2f} ms")

            time.sleep(0.5)

        assert len(setup_times) >= 3, "Too few successful link setups"

        benchmark = metrics.get_benchmark()
        avg_ms = benchmark.mean
        print(f"\nLink Setup Time Statistics:")
        print(f"  Mean: {avg_ms:.2f} ms")
        print(f"  Min:  {benchmark.min:.2f} ms")
        print(f"  Max:  {benchmark.max:.2f} ms")
        assert avg_ms < 10000, f"Link setup regression: {avg_ms:.0f}ms avg > 10000ms limit"


@pytest.mark.performance
class TestAnnouncePropagation:
    """Measure announce propagation time."""

    def test_announce_propagation_latency(self, node_a, node_c, unique_app_name):
        """
        PERF-005: Measure time for announce to propagate.

        Creates destination with announce on node_c and measures time until
        node_a discovers the path. The measurement includes a small overhead
        from the background process startup, but propagation dominates.
        """
        aspects = ["perf", "announce", "propagation"]
        metrics = PerformanceMetrics("announce_propagation")

        propagation_times = []

        for i in range(3):
            test_name = f"{unique_app_name}_{i}"
            aspects_i = aspects + [f"iter{i}"]

            # Measure time from destination+announce creation to path discovery.
            # The announce is sent inside start_destination_server, so we
            # measure from when the server is up until node_a sees the path.
            with metrics.time_operation(f"propagation_{i}") as t:
                dest = node_c.start_destination_server(
                    app_name=test_name,
                    aspects=aspects_i,
                    announce=True,
                )

                # Wait for path on node_a
                path_result = node_a.wait_for_path(
                    dest["destination_hash"],
                    timeout=10.0,
                )

                if not path_result.get("path_found"):
                    t.set_metadata(success=False)
                    continue

            propagation_times.append(t.duration_ms)
            print(f"  Announce {i}: Propagation = {t.duration_ms:.2f} ms")

        if propagation_times:
            avg = sum(propagation_times) / len(propagation_times)
            print(f"\nAverage Propagation Time: {avg:.2f} ms")

        assert len(propagation_times) >= 1, "No successful propagation measurements"
        if propagation_times:
            avg_prop = sum(propagation_times) / len(propagation_times)
            assert avg_prop < 8000, f"Announce propagation regression: {avg_prop:.0f}ms avg > 8000ms limit"


@pytest.mark.performance
class TestBenchmarkReport:
    """Generate comprehensive benchmark report."""

    def test_full_benchmark_suite(self, node_a, node_c, unique_app_name):
        """
        Run a comprehensive benchmark and generate report.

        This test combines multiple measurements into a single report.
        """
        aspects = ["perf", "full"]
        metrics = PerformanceMetrics("full_benchmark")

        # Setup
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )
        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        # 1. Link setup
        for i in range(3):
            with metrics.time_operation("link_setup"):
                link = node_a.create_link(
                    destination_hash=dest["destination_hash"],
                    app_name=unique_app_name,
                    aspects=aspects,
                    timeout=15.0,
                )
            time.sleep(0.3)

        # 2. Small data transfer
        for i in range(3):
            test_data = b"X" * 500
            with metrics.time_operation("small_transfer"):
                result = node_a.create_link_and_send(
                    destination_hash=dest["destination_hash"],
                    app_name=unique_app_name,
                    data=test_data,
                    aspects=aspects,
                    link_timeout=10.0,
                    data_timeout=5.0,
                )
            time.sleep(0.3)

        # 3. Resource transfer
        for i in range(2):
            test_data = os.urandom(2000)
            with metrics.time_operation("resource_transfer"):
                result = node_a.create_link_and_send_resource(
                    destination_hash=dest["destination_hash"],
                    app_name=unique_app_name,
                    data=test_data,
                    aspects=aspects,
                    link_timeout=15.0,
                    resource_timeout=30.0,
                )
            time.sleep(0.5)

        # Generate report
        from helpers.perf_utils import BenchmarkResult

        results = [
            metrics.get_benchmark("link_setup"),
            metrics.get_benchmark("small_transfer"),
            metrics.get_benchmark("resource_transfer"),
        ]

        report = format_benchmark_report(results)
        print("\n" + report)

        # Verify we got data
        total_samples = sum(r.count for r in results)
        assert total_samples >= 5, f"Too few benchmark samples: {total_samples}"
