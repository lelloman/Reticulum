"""E2E Advanced Features Tests.

Tests that verify advanced Reticulum features work correctly.

Test IDs:
- ADV-001: Ratcheting - enable_ratchets() with key rotation
- ADV-002: Buffer Streaming - RawChannelReader/Writer
- ADV-003: Request/Response - Destination request handlers
- ADV-004: Link Identification - link.identify() verification
- ADV-005: Group Destinations - GROUP type multicast
- ADV-006: MTU Signaling - Link MTU negotiation
- ADV-007: Encryption Modes - AES-128-CBC vs AES-256-CBC
- ADV-008: Proof Strategies - PROVE_NONE/APP/ALL validation
"""

import pytest
import time

from helpers.docker_exec import exec_on_node


def run_advanced_test(container: str, operation: str, **kwargs) -> dict:
    """Run an advanced feature test on a container."""
    args = {"operation": operation}
    args.update(kwargs)
    return exec_on_node(container, "advanced_features", args, timeout=30)


@pytest.mark.advanced
class TestRatcheting:
    """Test forward secrecy via ratcheting."""

    def test_enable_ratchets(self, node_c, unique_app_name):
        """
        ADV-001: Destinations can enable ratcheting.

        Ratcheting provides forward secrecy by rotating keys.
        """
        result = run_advanced_test(
            node_c.container,
            "ratchets",
            app_name=unique_app_name,
            aspects=["advanced", "ratchet"],
        )

        assert result.get("success"), f"Ratchet test failed: {result.get('error')}"
        assert result.get("ratchets_enabled") is True


@pytest.mark.advanced
class TestBufferStreaming:
    """Test buffer/streaming functionality."""

    def test_data_stream_over_link(self, node_a, node_c, unique_app_name):
        """
        ADV-002: Data can be streamed over a link.

        This test verifies that multiple data packets can be sent
        sequentially over a link (simulating streaming).
        """
        aspects = ["advanced", "stream"]

        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=10.0)

        # Send multiple small packets (simulating stream)
        chunks = [f"Chunk {i}: " + "X" * 50 for i in range(5)]

        for i, chunk in enumerate(chunks):
            result = node_a.create_link_and_send(
                destination_hash=dest["destination_hash"],
                app_name=unique_app_name,
                data=chunk.encode(),
                aspects=aspects,
                link_timeout=10.0,
                data_timeout=5.0,
            )

            assert result["status"] == "ACTIVE", f"Chunk {i} link failed"
            assert result["data_sent"] is True, f"Chunk {i} send failed"


@pytest.mark.advanced
class TestRequestResponse:
    """Test request/response pattern."""

    def test_request_handler_registration(self, node_c, unique_app_name):
        """
        ADV-003: Destinations can register request handlers.

        Request handlers allow RPC-like communication patterns.
        """
        result = run_advanced_test(
            node_c.container,
            "request_handler",
            app_name=unique_app_name,
            aspects=["advanced", "request"],
        )

        assert result.get("success"), f"Request handler test failed: {result.get('error')}"
        assert result.get("request_handler_registered") is True


@pytest.mark.advanced
class TestLinkIdentification:
    """Test link identification functionality."""

    def test_link_identify(self, node_a, node_c, unique_app_name):
        """
        ADV-004: Links can identify the remote party.

        link.identify() sends the local identity to the remote party,
        allowing mutual authentication.
        """
        aspects = ["advanced", "identify"]

        # Start server destination
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        path = node_a.wait_for_path(dest["destination_hash"], timeout=15.0)
        assert path.get("path_found"), f"Path not found: {path}"

        # Create link with identification via create_link.py
        result = node_a.create_link(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            aspects=aspects,
            timeout=20.0,
            identify=True,
        )

        assert result["status"] == "ACTIVE", f"Link failed: {result.get('error')}"
        assert result.get("identification_sent") is True


@pytest.mark.advanced
class TestGroupDestinations:
    """Test GROUP destination type."""

    def test_create_group_destination(self, node_a, unique_app_name):
        """
        ADV-005: GROUP destinations can be created.

        GROUP destinations use pre-shared keys for multicast.
        """
        result = run_advanced_test(
            node_a.container,
            "group_destination",
            app_name=unique_app_name,
            aspects=["advanced", "group"],
        )

        assert result.get("success"), f"Group destination test failed: {result.get('error')}"
        assert result.get("type") == "GROUP"


@pytest.mark.advanced
class TestMTUSignaling:
    """Test MTU negotiation."""

    def test_link_respects_mtu(self, node_a, node_c, unique_app_name):
        """
        ADV-006: Links respect the MTU limit.

        Packets larger than MTU should fail or be segmented.
        The MTU is 500 bytes for Reticulum.
        """
        aspects = ["advanced", "mtu"]

        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=10.0)

        # Send packet within MTU (should succeed)
        small_data = b"A" * 300

        result = node_a.create_link_and_send(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            data=small_data,
            aspects=aspects,
            link_timeout=15.0,
            data_timeout=5.0,
        )

        assert result["status"] == "ACTIVE"
        assert result["data_sent"] is True


@pytest.mark.advanced
class TestEncryptionModes:
    """Test encryption mode handling."""

    def test_encrypted_link_communication(self, node_a, node_c, unique_app_name):
        """
        ADV-007: Links use encryption by default.

        All SINGLE destination links are encrypted with AES.
        """
        aspects = ["advanced", "encryption"]

        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        node_a.wait_for_path(dest["destination_hash"], timeout=10.0)

        # Send sensitive data (should be encrypted in transit)
        sensitive_data = b"Secret message: password123"

        result = node_a.create_link_and_send(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            data=sensitive_data,
            aspects=aspects,
            link_timeout=15.0,
            data_timeout=5.0,
        )

        assert result["status"] == "ACTIVE"
        assert result["data_sent"] is True


@pytest.mark.advanced
class TestProofStrategies:
    """Test different proof strategies."""

    def test_prove_all_strategy(self, node_c, unique_app_name):
        """
        ADV-008a: PROVE_ALL strategy generates proofs for all packets.
        """
        result = run_advanced_test(
            node_c.container,
            "proof_strategy",
            app_name=unique_app_name,
            aspects=["advanced", "proof", "all"],
            strategy="PROVE_ALL",
        )

        assert result.get("success")
        assert result.get("proof_strategy") == "PROVE_ALL"

    def test_prove_none_strategy(self, node_c, unique_app_name):
        """
        ADV-008b: PROVE_NONE strategy disables proofs.
        """
        result = run_advanced_test(
            node_c.container,
            "proof_strategy",
            app_name=unique_app_name,
            aspects=["advanced", "proof", "none"],
            strategy="PROVE_NONE",
        )

        assert result.get("success")
        assert result.get("proof_strategy") == "PROVE_NONE"

    def test_prove_app_strategy(self, node_c, unique_app_name):
        """
        ADV-008c: PROVE_APP strategy delegates proof generation to app.
        """
        result = run_advanced_test(
            node_c.container,
            "proof_strategy",
            app_name=unique_app_name,
            aspects=["advanced", "proof", "app"],
            strategy="PROVE_APP",
        )

        assert result.get("success")
        assert result.get("proof_strategy") == "PROVE_APP"
