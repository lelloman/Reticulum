"""E2E Channel Messaging Tests.

Tests that verify channel message exchange between nodes using the
actual Channel API (MessageBase subclasses).

Test IDs:
- E2E-CHN-001: Channel send/receive with echo
- E2E-CHN-002: Server-side received data verification
- E2E-CHN-003: Bidirectional channel messaging
"""

import pytest
import time


class TestChannelE2E:
    """Test channel messaging between nodes."""

    def test_link_establishment_for_channel(self, node_a, node_c, unique_app_name):
        """
        Basic sanity: link used for channels can be established.
        """
        aspects = ["channel", "basic"]

        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

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

    def test_channel_send_receive(self, node_a, node_c, unique_app_name):
        """
        E2E-CHN-001: Send TestMessage via Channel, receive EchoMessage reply.

        Server is configured with channel_mode=True, which echoes
        TestMessage.data back as EchoMessage.
        """
        aspects = ["channel", "echo"]

        # Start channel echo server on node-c
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
            channel_mode=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        test_data = b"Hello Channel API!"

        result = node_a.channel_send(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            message_data=test_data,
            aspects=aspects,
            wait_reply=True,
            timeout=15.0,
        )

        assert result["status"] == "ACTIVE", f"Link failed: {result.get('error')}"
        assert result["message_sent"] is True, "Message was not sent"
        assert result["reply_received"] is True, "No echo reply received"
        # Verify echo data matches
        assert result["reply_data_hex"] == test_data.hex(), (
            f"Echo data mismatch: expected {test_data.hex()}, got {result['reply_data_hex']}"
        )

    def test_channel_data_verified_on_server(self, node_a, node_c, unique_app_name):
        """
        E2E-CHN-002: Verify server's received data has channel_message with correct bytes.
        """
        aspects = ["channel", "verify"]

        # Clear received data first
        node_c.clear_received_data()

        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
            channel_mode=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=15.0)

        test_data = b"Verify on server side"

        result = node_a.channel_send(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            message_data=test_data,
            aspects=aspects,
            wait_reply=True,
            timeout=15.0,
        )

        assert result["status"] == "ACTIVE"
        assert result["message_sent"] is True

        # Check server-side received data
        time.sleep(1.0)
        received = node_c.get_received_data(data_type="channel_message")
        assert len(received) > 0, "No channel messages received on server"

        sent_hex = test_data.hex()
        matching = [r for r in received if r["data_hex"] == sent_hex]
        assert len(matching) > 0, (
            f"Server did not record matching channel message. "
            f"Expected: {sent_hex}, Got: {[r['data_hex'] for r in received]}"
        )

    def test_bidirectional_channel_messaging(self, node_a, node_c, unique_app_name):
        """
        E2E-CHN-003: Both nodes serve with channel_mode, both send and receive.
        """
        aspects_c = ["channel", "bidir", "c"]
        aspects_a = ["channel", "bidir", "a"]

        # Start channel servers on both nodes
        dest_c = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects_c,
            announce=True,
            channel_mode=True,
        )

        dest_a = node_a.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects_a,
            announce=True,
            channel_mode=True,
        )

        node_a.wait_for_path(dest_c["destination_hash"], timeout=15.0)
        node_c.wait_for_path(dest_a["destination_hash"], timeout=15.0)

        # A sends to C
        result_a = node_a.channel_send(
            destination_hash=dest_c["destination_hash"],
            app_name=unique_app_name,
            message_data=b"From A to C",
            aspects=aspects_c,
            wait_reply=True,
            timeout=15.0,
        )
        assert result_a["status"] == "ACTIVE"
        assert result_a["message_sent"] is True
        assert result_a["reply_received"] is True

        # C sends to A
        result_c = node_c.channel_send(
            destination_hash=dest_a["destination_hash"],
            app_name=unique_app_name,
            message_data=b"From C to A",
            aspects=aspects_a,
            wait_reply=True,
            timeout=15.0,
        )
        assert result_c["status"] == "ACTIVE"
        assert result_c["message_sent"] is True
        assert result_c["reply_received"] is True
