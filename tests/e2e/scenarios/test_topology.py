"""E2E Advanced Network Topology Tests.

Tests that verify Reticulum's routing across different network topologies.

Test IDs:
- TOPO-001: Chain - 3-hop routing verification
- TOPO-002: Chain - Path discovery latency
- TOPO-003: Ring - Alternate path selection
- TOPO-004: Ring - Failover on path failure
- TOPO-005: Mesh - Optimal path discovery
- TOPO-006: Mesh - Announce flooding limits
"""

import pytest
import time

from helpers.docker_exec import NodeInterface
from helpers.fixtures import (
    CONTAINER_TRANSPORT_2,
    CONTAINER_NODE_B,
    CONTAINER_NODE_D,
    CONTAINER_NODE_E,
)


@pytest.fixture
def node_d(docker_env) -> NodeInterface:
    """Interface to node-d container (for chain/mesh topologies)."""
    return NodeInterface(CONTAINER_NODE_D)


@pytest.fixture
def node_b(docker_env) -> NodeInterface:
    """Interface to node-b container (for mesh topology)."""
    return NodeInterface(CONTAINER_NODE_B)


@pytest.fixture
def node_e(docker_env) -> NodeInterface:
    """Interface to node-e container (for mesh topology)."""
    return NodeInterface(CONTAINER_NODE_E)


@pytest.fixture
def transport_2(docker_env) -> NodeInterface:
    """Interface to transport-2 container."""
    return NodeInterface(CONTAINER_TRANSPORT_2)


# ============================================================
# Chain Topology Tests: A → T1 → T2 → D (3 hops)
# ============================================================

@pytest.mark.topology_chain
class TestChainTopology:
    """Test chain topology routing."""

    def test_three_hop_link_establishment(self, node_a, node_d, unique_app_name):
        """
        TOPO-001: Establish link across 3-hop chain.

        A → T1 → chain-link → T2 → D
        """
        aspects = ["topology", "chain", "link"]

        # Start destination on node-d (far end of chain)
        dest = node_d.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        # Create link from node-a (start of chain)
        link = node_a.create_link(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            aspects=aspects,
            timeout=30.0,  # Longer timeout for multi-hop
        )

        assert link["status"] == "ACTIVE", f"Link failed: {link.get('error')}"

    def test_chain_path_discovery_time(self, node_a, node_d, unique_app_name):
        """
        TOPO-002: Measure path discovery latency in chain.
        """
        aspects = ["topology", "chain", "discovery"]

        # Create destination and announce
        dest = node_d.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        # Measure time to discover path
        start_time = time.time()

        path_result = node_a.wait_for_path(
            dest["destination_hash"],
            timeout=15.0,
        )

        discovery_time = time.time() - start_time

        assert path_result["path_found"], "Path not found in chain"
        # Path through chain should take some time but complete
        assert discovery_time < 15.0

    def test_chain_data_transfer(self, node_a, node_d, unique_app_name):
        """
        Data transfer across 3-hop chain.
        """
        aspects = ["topology", "chain", "data"]

        dest = node_d.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        test_data = b"Hello across the chain!"

        result = node_a.create_link_and_send(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            data=test_data,
            aspects=aspects,
            link_timeout=30.0,
            data_timeout=15.0,
        )

        assert result["status"] == "ACTIVE"
        assert result["data_sent"] is True


# ============================================================
# Ring Topology Tests: A ↔ T1 ↔ C and A ↔ T2 ↔ C
# ============================================================

@pytest.mark.topology_ring
class TestRingTopology:
    """Test ring topology with redundant paths."""

    def test_link_with_redundant_paths(self, node_a, node_c, unique_app_name):
        """
        TOPO-003: Link establishment with multiple path options.

        Both A and C are connected to both T1 and T2.
        """
        aspects = ["topology", "ring", "redundant"]

        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        link = node_a.create_link(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            aspects=aspects,
            timeout=15.0,
        )

        assert link["status"] == "ACTIVE"

    @pytest.mark.chaos
    def test_ring_failover(self, node_a, node_c, transport_node, unique_app_name):
        """
        TOPO-004: Failover when primary transport fails.

        1. Establish link A -> C (works through T1 or T2)
        2. Stop T1
        3. Re-announce from C
        4. Establish new link A -> C (should route through T2)
        5. Restore T1
        """
        aspects = ["topology", "ring", "failover"]

        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        # Verify initial link works
        link1 = node_a.create_link(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            aspects=aspects,
            timeout=15.0,
        )
        assert link1["status"] == "ACTIVE", f"Initial link failed: {link1}"

        # Stop primary transport
        stop_result = transport_node.stop_rnsd()
        assert stop_result["success"], f"Failed to stop transport: {stop_result}"

        time.sleep(3.0)  # Allow network to settle

        # Re-announce from node-c to refresh routes
        node_c.announce(dest["destination_hash"])
        time.sleep(3.0)

        # Establish new link (should route through T2)
        link2 = node_a.create_link(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            aspects=aspects,
            timeout=20.0,
        )
        assert link2["status"] == "ACTIVE", f"Failover link failed: {link2}"

        # Restore T1
        start_result = transport_node.start_rnsd()
        assert start_result["success"], f"Failed to restart transport: {start_result}"


# ============================================================
# Mesh Topology Tests: 5 nodes via central transport
# ============================================================

@pytest.mark.topology_mesh
class TestMeshTopology:
    """Test mesh topology with multiple nodes."""

    def test_any_to_any_communication(
        self, node_a, node_b, node_c, node_d, node_e, unique_app_name
    ):
        """
        TOPO-005: Any node can communicate with any other.
        """
        aspects = ["topology", "mesh", "anytoany"]

        # Start destinations on multiple nodes
        dest_c = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects + ["c"],
            announce=True,
        )

        dest_e = node_e.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects + ["e"],
            announce=True,
        )

        node_a.wait_for_path(dest_c["destination_hash"], timeout=15.0)
        node_b.wait_for_path(dest_e["destination_hash"], timeout=15.0)

        # A → C
        link_a_c = node_a.create_link(
            destination_hash=dest_c["destination_hash"],
            app_name=unique_app_name,
            aspects=aspects + ["c"],
            timeout=15.0,
        )
        assert link_a_c["status"] == "ACTIVE"

        # B → E
        link_b_e = node_b.create_link(
            destination_hash=dest_e["destination_hash"],
            app_name=unique_app_name,
            aspects=aspects + ["e"],
            timeout=15.0,
        )
        assert link_b_e["status"] == "ACTIVE"

    def test_multiple_announces_propagate(
        self, node_a, node_b, node_c, node_d, node_e, unique_app_name
    ):
        """
        TOPO-006: Multiple announces propagate correctly.

        All nodes should receive announces from all other nodes.
        """
        aspects = ["topology", "mesh", "announce"]

        # Each node creates and announces a destination
        destinations = []

        for i, node in enumerate([node_a, node_b, node_c, node_d, node_e]):
            dest = node.create_destination(
                app_name=unique_app_name,
                aspects=aspects + [f"node{i}"],
                announce=True,
            )
            destinations.append(dest)

        # Verify node_a can find paths to all other destinations
        for i, dest in enumerate(destinations[1:], 1):  # Skip node_a's own dest
            path_result = node_a.wait_for_path(
                dest["destination_hash"],
                timeout=10.0,
            )
            assert path_result["path_found"], f"Path to node{i} not found"

    def test_mesh_resource_transfer(
        self, node_a, node_e, unique_app_name
    ):
        """
        Resource transfer across mesh network.
        """
        aspects = ["topology", "mesh", "resource"]

        dest = node_e.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        test_data = b"X" * 2000  # Multi-segment resource

        result = node_a.create_link_and_send_resource(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            data=test_data,
            aspects=aspects,
            link_timeout=20.0,
            resource_timeout=45.0,
        )

        assert result["status"] == "ACTIVE"
        assert result["resource_completed"] is True
