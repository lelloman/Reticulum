"""E2E Resource Transfer Tests.

Tests that verify resource (large data) transfers between nodes.

Test IDs:
- E2E-RES-001: Small resource (< MTU)
- E2E-RES-002: Large resource (multi-segment)
- E2E-RES-003: Compressed resource
"""

import pytest
import time
import os


class TestResourceE2E:
    """Test resource transfers between nodes."""

    def test_small_resource_transfer(self, node_a, node_c, unique_app_name):
        """
        E2E-RES-001: Transfer a small resource (< MTU) over a link.

        Small resources should transfer in a single segment.
        """
        aspects = ["resource", "small"]

        # Start destination server
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=10.0)

        # Send small resource (100 bytes) using combined link+resource operation
        small_data = b"A" * 100

        result = node_a.create_link_and_send_resource(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            data=small_data,
            aspects=aspects,
            link_timeout=15.0,
            resource_timeout=15.0,
        )

        assert result["status"] == "ACTIVE"
        assert result["resource_sent"] is True
        assert result["resource_completed"] is True

    def test_medium_resource_transfer(self, node_a, node_c, unique_app_name):
        """
        E2E-RES-002: Transfer a medium resource (multi-segment).

        Resources larger than MTU (500 bytes) require segmentation.
        """
        aspects = ["resource", "medium"]

        # Start destination server
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=10.0)

        # Send medium resource (5KB)
        medium_data = b"B" * 5000

        result = node_a.create_link_and_send_resource(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            data=medium_data,
            aspects=aspects,
            link_timeout=15.0,
            resource_timeout=30.0,
        )

        assert result["status"] == "ACTIVE"
        assert result["resource_sent"] is True
        assert result["resource_completed"] is True

    def test_resource_with_compression(self, node_a, node_c, unique_app_name):
        """
        E2E-RES-003: Transfer a compressible resource.

        Repeated data should compress well, resulting in faster transfer.
        """
        aspects = ["resource", "compressed"]

        # Start destination server
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=10.0)

        # Send compressible data (repeated pattern)
        # 10KB of repeated pattern should compress very well
        compressible_data = (b"Hello World! " * 100) * 8  # ~10KB

        result = node_a.create_link_and_send_resource(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            data=compressible_data,
            aspects=aspects,
            link_timeout=15.0,
            resource_timeout=30.0,
            compress=True,
        )

        assert result["status"] == "ACTIVE"
        assert result["resource_sent"] is True
        assert result["resource_completed"] is True

    def test_resource_without_compression(self, node_a, node_c, unique_app_name):
        """
        Resource transfer without compression.
        """
        aspects = ["resource", "nocompress"]

        # Start destination server
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=10.0)

        # Send data without compression
        data = b"C" * 2000

        result = node_a.create_link_and_send_resource(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            data=data,
            aspects=aspects,
            link_timeout=15.0,
            resource_timeout=30.0,
            compress=False,
        )

        assert result["status"] == "ACTIVE"
        assert result["resource_sent"] is True
        assert result["resource_completed"] is True

    @pytest.mark.slow
    def test_large_resource_transfer(self, node_a, node_c, unique_app_name):
        """
        Transfer a larger resource (50KB).

        This test is marked slow as it may take longer to complete.
        """
        aspects = ["resource", "large"]

        # Start destination server
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=10.0)

        # Send large resource (50KB)
        large_data = os.urandom(50000)

        result = node_a.create_link_and_send_resource(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            data=large_data,
            aspects=aspects,
            link_timeout=15.0,
            resource_timeout=60.0,
            compress=True,
        )

        assert result["status"] == "ACTIVE"
        assert result["resource_sent"] is True
        assert result["resource_completed"] is True
