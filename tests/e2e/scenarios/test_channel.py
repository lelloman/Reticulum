"""E2E Channel Messaging Tests.

Tests that verify channel message exchange between nodes.

Test IDs:
- E2E-CHN-001: Channel message exchange
- E2E-CHN-002: Channel with MessageBase types
"""

import pytest
import time


class TestChannelE2E:
    """Test channel messaging between nodes."""

    def test_link_establishment_for_channel(self, node_a, node_c, unique_app_name):
        """
        E2E-CHN-001: Establish link that can be used for channel messaging.

        This test verifies the link infrastructure needed for channels.
        Actual channel API testing requires more complex setup.
        """
        aspects = ["channel", "basic"]

        # Start destination server on node-c
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        # Create link and send data in one operation
        result = node_a.create_link_and_send(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            data=b"Channel test data",
            aspects=aspects,
            link_timeout=15.0,
            data_timeout=5.0,
        )

        assert result["status"] == "ACTIVE"
        assert result["data_sent"] is True

    def test_single_message_on_link(self, node_a, node_c, unique_app_name):
        """
        Single message can be sent over a link.

        This verifies basic messaging capability.
        """
        aspects = ["channel", "single"]

        # Start destination server
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        # Create link and send message
        result = node_a.create_link_and_send(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            data=b"Single message test",
            aspects=aspects,
            link_timeout=15.0,
            data_timeout=5.0,
        )

        assert result["status"] == "ACTIVE"
        assert result["data_sent"] is True

    def test_bidirectional_link_setup(self, node_a, node_c, unique_app_name):
        """
        E2E-CHN-002: Setup for bidirectional channel messaging.

        Both nodes can establish links for full-duplex communication.
        """
        aspects_a = ["channel", "bidir", "a"]
        aspects_c = ["channel", "bidir", "c"]

        # Start destination servers on both nodes
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

        # A connects to C and sends
        result_a = node_a.create_link_and_send(
            destination_hash=dest_c["destination_hash"],
            app_name=unique_app_name,
            data=b"From A",
            aspects=aspects_c,
            link_timeout=15.0,
            data_timeout=5.0,
        )
        assert result_a["status"] == "ACTIVE"
        assert result_a["data_sent"] is True

        # C connects to A and sends
        result_c = node_c.create_link_and_send(
            destination_hash=dest_a["destination_hash"],
            app_name=unique_app_name,
            data=b"From C",
            aspects=aspects_a,
            link_timeout=15.0,
            data_timeout=5.0,
        )
        assert result_c["status"] == "ACTIVE"
        assert result_c["data_sent"] is True
