"""E2E Link Establishment Tests.

Tests that verify link establishment and data transfer between nodes.

Test IDs:
- E2E-LINK-001: Direct link via transport
- E2E-LINK-002: Bidirectional data
- E2E-LINK-003: Link teardown
- E2E-LINK-004: Link timeout/reconnect
"""

import pytest
import time


class TestLinkE2E:
    """Test link establishment between nodes."""

    def test_direct_link_via_transport(self, node_a, node_c, unique_app_name):
        """
        E2E-LINK-001: Establish link from node-a to node-c via transport.

        node-a --[TCP]--> transport --[TCP]--> node-c

        1. Create destination on node-c (server)
        2. Announce the destination
        3. Create link from node-a (client)
        4. Verify link becomes ACTIVE
        """
        aspects = ["link", "basic"]

        # Start destination server on node-c (stays alive to accept links)
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )
        dest_hash = dest["destination_hash"]

        node_a.wait_for_path(dest_hash, timeout=15.0)

        # Create link from node-a
        link = node_a.create_link(
            destination_hash=dest_hash,
            app_name=unique_app_name,
            aspects=aspects,
            timeout=15.0,
        )

        assert link["status"] == "ACTIVE", f"Link failed: {link.get('error', 'unknown')}"
        assert "link_id" in link
        assert len(link["link_id"]) == 32  # 16 bytes = 32 hex chars

    def test_link_data_transfer(self, node_a, node_c, unique_app_name):
        """
        E2E-LINK-002: Send data over an established link.

        After establishing a link, send a packet from node-a to node-c.
        """
        aspects = ["link", "data"]

        # Start destination server on node-c
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        # Create link and send data in one operation
        # (This is required because the link object is local to the Python process)
        test_data = b"Hello from node-a!"
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
        # Note: delivered confirmation depends on the receiver setting up proof
        # For this test, we just verify the packet was sent successfully

    def test_link_from_both_directions(self, node_a, node_c, unique_app_name):
        """
        Links can be established in both directions.

        First node-a connects to node-c, then node-c connects to node-a.
        """
        aspects_c = ["link", "bidir", "c"]
        aspects_a = ["link", "bidir", "a"]

        # Start destination servers on both nodes
        dest_c = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects_c,
            announce=True,
        )

        dest_a = node_a.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects_a,
            announce=True,
        )

        node_a.wait_for_path(dest_c["destination_hash"], timeout=15.0)
        node_c.wait_for_path(dest_a["destination_hash"], timeout=15.0)

        # Link from A to C
        link_a_to_c = node_a.create_link(
            destination_hash=dest_c["destination_hash"],
            app_name=unique_app_name,
            aspects=aspects_c,
            timeout=15.0,
        )
        assert link_a_to_c["status"] == "ACTIVE"

        # Link from C to A
        link_c_to_a = node_c.create_link(
            destination_hash=dest_a["destination_hash"],
            app_name=unique_app_name,
            aspects=aspects_a,
            timeout=15.0,
        )
        assert link_c_to_a["status"] == "ACTIVE"

        # Both links should have different IDs
        assert link_a_to_c["link_id"] != link_c_to_a["link_id"]

    def test_link_timeout_without_path(self, node_a, unique_app_name):
        """
        E2E-LINK-004: Link to non-existent destination times out gracefully.
        """
        # Try to create link to a non-existent destination
        fake_hash = "0" * 32  # 16 bytes of zeros

        link = node_a.create_link(
            destination_hash=fake_hash,
            app_name=unique_app_name,
            aspects=["fake"],
            timeout=3.0,
        )

        # Should fail with timeout or no path error
        assert link["status"] in ["NO_PATH", "TIMEOUT", "CLOSED"]
        assert "error" in link

    def test_multiple_sequential_links(self, node_a, node_c, unique_app_name):
        """
        Multiple sequential links can be established to the same destination.
        """
        aspects = ["link", "multi"]

        # Start destination server
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        # Create first link
        link1 = node_a.create_link(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            aspects=aspects,
            timeout=15.0,
        )
        assert link1["status"] == "ACTIVE"

        # Create second link (new link to same destination)
        link2 = node_a.create_link(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            aspects=aspects,
            timeout=15.0,
        )
        assert link2["status"] == "ACTIVE"

        # Links should be different
        assert link1["link_id"] != link2["link_id"]
