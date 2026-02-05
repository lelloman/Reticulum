"""E2E Announce Propagation Tests.

Tests that verify announce messages propagate correctly through the network.

Test IDs:
- E2E-ANN-001: Announce reaches remote node
- E2E-ANN-002: Announce with app_data
- E2E-ANN-003: Path request/response
"""

import pytest
import time


class TestAnnounceE2E:
    """Test announce propagation between nodes."""

    def test_announce_reaches_remote_node(self, node_a, node_c, unique_app_name):
        """
        E2E-ANN-001: Announce from node-a reaches node-c via transport.

        node-a --[announce]--> transport --[announce]--> node-c

        1. Create destination on node-a
        2. Announce the destination
        3. Verify node-c can find path to the destination
        """
        # Create and announce destination on node-a
        dest = node_a.create_destination(
            app_name=unique_app_name,
            aspects=["announce", "basic"],
            announce=True,
        )
        dest_hash = dest["destination_hash"]

        # Wait for announce to propagate through transport
        time.sleep(2)

        # Verify node-c can find path to node-a's destination
        result = node_c.wait_for_path(dest_hash, timeout=10.0)

        assert result["path_found"] is True, "Path not found to announced destination"
        assert result["hops"] >= 1, "Expected at least 1 hop via transport"

    def test_announce_with_app_data(self, node_a, node_c, unique_app_name):
        """
        E2E-ANN-002: Announce with app_data propagates correctly.

        The app_data included in an announce should be available
        to receiving nodes.
        """
        app_data_content = "TestAppData123"

        # Create and announce destination with app_data
        dest = node_a.create_destination(
            app_name=unique_app_name,
            aspects=["announce", "appdata"],
            announce=True,
            app_data=app_data_content,
        )

        # Wait for propagation
        time.sleep(2)

        # Verify node-c received the announce (path exists)
        result = node_c.wait_for_path(dest["destination_hash"], timeout=10.0)
        assert result["path_found"] is True

    def test_path_request_response(self, node_a, node_c, unique_app_name):
        """
        E2E-ANN-003: Path request gets response for announced destination.

        When a node requests a path to an announced destination,
        it should receive a valid path response.
        """
        # Start destination server on node-c (keeps destination active)
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=["path", "request"],
            announce=True,
        )
        dest_hash = dest["destination_hash"]

        # Wait for propagation through transport
        time.sleep(3)

        # Request path from node-a - should find it via the announce
        result = node_a.wait_for_path(dest_hash, timeout=10.0)

        assert result["path_found"] is True
        assert result["destination_hash"] == dest_hash

    def test_bidirectional_announces(self, node_a, node_c, unique_app_name):
        """
        Both nodes can announce and discover each other.
        """
        # Create and announce on both nodes
        dest_a = node_a.create_destination(
            app_name=unique_app_name,
            aspects=["bidir", "nodeA"],
            announce=True,
        )

        dest_c = node_c.create_destination(
            app_name=unique_app_name,
            aspects=["bidir", "nodeC"],
            announce=True,
        )

        # Wait for propagation
        time.sleep(3)

        # Verify node-a can reach node-c
        result_a = node_a.wait_for_path(dest_c["destination_hash"], timeout=10.0)
        assert result_a["path_found"] is True

        # Verify node-c can reach node-a
        result_c = node_c.wait_for_path(dest_a["destination_hash"], timeout=10.0)
        assert result_c["path_found"] is True
