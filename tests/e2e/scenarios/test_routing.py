"""E2E Multi-hop Routing Tests.

Tests that verify routing through the transport node.

Test IDs:
- E2E-ROUTE-001: Path discovery via transport
- E2E-ROUTE-002: Announce propagation via transport
- E2E-ROUTE-003: Multi-hop data delivery
"""

import pytest
import time


class TestRoutingE2E:
    """Test multi-hop routing via transport node."""

    def test_path_discovery_via_transport(self, node_a, node_c, transport_node, unique_app_name):
        """
        E2E-ROUTE-001: Path discovery across transport.

        node-a requests path to node-c destination,
        transport node forwards the request.

        Topology:
        node-a <--TCP--> transport <--TCP--> node-c

        node-a and node-c have no direct connection.
        """
        # Create and announce destination on node-c (doesn't need to accept links)
        dest = node_c.create_destination(
            app_name=unique_app_name,
            aspects=["routing", "discovery"],
            announce=True,
        )

        # Check that node-a can find path via transport
        result = node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        assert result["path_found"] is True
        # Should be at least 1 hop (through transport)
        # Exact hop count depends on network topology
        assert result["hops"] >= 1

    def test_announce_propagation_via_transport(self, node_a, node_c, transport_node, unique_app_name):
        """
        E2E-ROUTE-002: Announce propagates through transport to remote nodes.

        When node-a announces, node-c should receive it via transport.
        """
        # Create and announce destination on node-a
        dest = node_a.create_destination(
            app_name=unique_app_name,
            aspects=["routing", "announce"],
            announce=True,
        )

        # Verify node-c received the announce (has path)
        result = node_c.wait_for_path(dest["destination_hash"], timeout=15.0)
        assert result["path_found"] is True

    def test_multihop_data_delivery(self, node_a, node_c, transport_node, unique_app_name):
        """
        E2E-ROUTE-003: Data delivery across multiple hops.

        Send data from node-a to node-c through transport node.
        """
        aspects = ["routing", "data"]

        # Start destination server on node-c
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        # Create link and send data in one operation
        test_data = b"Multi-hop message through transport!"
        result = node_a.create_link_and_send(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            data=test_data,
            aspects=aspects,
            link_timeout=15.0,
            data_timeout=5.0,
        )

        assert result["status"] == "ACTIVE"
        assert result["data_sent"] is True

    def test_transport_node_connectivity(self, node_a, node_c, transport_node, unique_app_name):
        """
        Verify both endpoint nodes can communicate with transport.

        This is a sanity check for the test environment.
        """
        aspects = ["routing", "transport"]

        # Start destination server on transport
        dest_transport = transport_node.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        # Both nodes should find path to transport
        result_a = node_a.wait_for_path(dest_transport["destination_hash"], timeout=15.0)
        assert result_a["path_found"] is True

        result_c = node_c.wait_for_path(dest_transport["destination_hash"], timeout=15.0)
        assert result_c["path_found"] is True

    def test_bidirectional_routing(self, node_a, node_c, unique_app_name):
        """
        Routing works in both directions through transport.

        Create destinations on both nodes and verify bidirectional reachability.
        """
        aspects_a = ["routing", "bidir", "a"]
        aspects_c = ["routing", "bidir", "c"]

        # Start destination servers on both endpoint nodes
        dest_a = node_a.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects_a,
            announce=True,
        )

        dest_c = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects_c,
            announce=True,
        )

        node_a.wait_for_path(dest_c["destination_hash"], timeout=15.0)
        node_c.wait_for_path(dest_a["destination_hash"], timeout=15.0)

        # A can reach C
        link_a_to_c = node_a.create_link(
            destination_hash=dest_c["destination_hash"],
            app_name=unique_app_name,
            aspects=aspects_c,
            timeout=15.0,
        )
        assert link_a_to_c["status"] == "ACTIVE"

        # C can reach A
        link_c_to_a = node_c.create_link(
            destination_hash=dest_a["destination_hash"],
            app_name=unique_app_name,
            aspects=aspects_a,
            timeout=15.0,
        )
        assert link_c_to_a["status"] == "ACTIVE"
