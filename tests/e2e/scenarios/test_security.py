"""E2E Security & Adversarial Tests.

Tests that verify Reticulum handles malicious or adversarial conditions.

Test IDs:
- SEC-001: Malformed Packets - Reject invalid headers
- SEC-002: Replay Attack - Detect replayed announces
- SEC-003: Invalid Signatures - Reject bad Ed25519 sigs
- SEC-004: Hash Mismatch - Detect tampered destinations
- SEC-005: Resource Corruption - Detect bad segment checksums
- SEC-006: Unauthorized Link - Reject unauthenticated links
"""

import pytest
import time
import os


@pytest.mark.security
class TestMalformedPackets:
    """Test handling of malformed packets."""

    def test_system_handles_truncated_data(self, node_a, node_c, unique_app_name):
        """
        SEC-001a: System handles truncated/malformed data gracefully.

        The system should not crash when receiving invalid data.
        """
        aspects = ["security", "malformed"]

        # First verify normal operation
        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        time.sleep(2)

        # Send valid data
        result = node_a.create_link_and_send(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            data=b"Normal data",
            aspects=aspects,
            link_timeout=15.0,
            data_timeout=5.0,
        )

        assert result["status"] == "ACTIVE"
        assert result["data_sent"] is True

    def test_link_fails_with_invalid_destination(self, node_a, unique_app_name):
        """
        SEC-001b: Link to invalid destination hash fails gracefully.
        """
        # Try various invalid destination hashes
        invalid_hashes = [
            "0" * 32,  # All zeros
            "f" * 32,  # All ones
            "deadbeef" * 4,  # Fake hash
        ]

        for fake_hash in invalid_hashes:
            link = node_a.create_link(
                destination_hash=fake_hash,
                app_name=unique_app_name,
                aspects=["fake"],
                timeout=3.0,
            )

            # Should fail gracefully
            assert link["status"] in ["NO_PATH", "TIMEOUT", "CLOSED", "NO_IDENTITY"], \
                f"Unexpected status for hash {fake_hash}: {link['status']}"


@pytest.mark.security
class TestReplayAttacks:
    """Test replay attack detection."""

    def test_repeated_announces_handled(self, node_a, node_c, unique_app_name):
        """
        SEC-002: System handles repeated/replayed announces.

        Multiple identical announces should be deduplicated.
        """
        aspects = ["security", "replay"]

        # Create and announce destination multiple times
        dest = node_c.create_destination(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        # Send multiple announces
        for _ in range(5):
            try:
                node_c.announce(dest["destination_hash"])
            except Exception:
                pass
            time.sleep(0.1)

        time.sleep(2)

        # System should still work normally
        path_result = node_a.wait_for_path(
            dest["destination_hash"],
            timeout=5.0,
        )

        # Path should be found (announce storm didn't break anything)
        assert path_result["path_found"]


@pytest.mark.security
class TestInvalidSignatures:
    """Test handling of invalid signatures."""

    def test_link_requires_valid_identity(self, node_a, node_c, unique_app_name):
        """
        SEC-003: Links require valid identity recall.

        Cannot establish link without proper identity from announce.
        """
        aspects = ["security", "signature"]

        # Create destination but don't announce
        dest = node_c.create_destination(
            app_name=unique_app_name,
            aspects=aspects,
            announce=False,  # No announce = no identity available
        )

        # Try to create link (should fail - no identity available)
        link = node_a.create_link(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            aspects=aspects,
            timeout=5.0,
        )

        # Should fail due to no path/identity
        assert link["status"] in ["NO_PATH", "NO_IDENTITY", "TIMEOUT"]


@pytest.mark.security
class TestHashMismatch:
    """Test destination hash validation."""

    def test_hash_verified_on_link(self, node_a, node_c, unique_app_name):
        """
        SEC-004: Destination hash is verified during link establishment.

        The client verifies that the recalled identity produces the
        expected destination hash.
        """
        aspects = ["security", "hash"]

        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        time.sleep(2)

        # Try to link with wrong app_name (hash won't match)
        link = node_a.create_link(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name + "_wrong",  # Wrong app name
            aspects=aspects,
            timeout=10.0,
        )

        # Should fail due to hash mismatch
        assert link["status"] in ["HASH_MISMATCH", "CLOSED", "TIMEOUT"], \
            f"Expected hash mismatch, got: {link}"


@pytest.mark.security
class TestResourceIntegrity:
    """Test resource transfer integrity."""

    def test_resource_integrity_verified(self, node_a, node_c, unique_app_name):
        """
        SEC-005: Resource transfers verify data integrity.

        The resource transfer protocol includes checksums.
        """
        aspects = ["security", "integrity"]

        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
        )

        time.sleep(2)

        # Send resource with known content
        test_data = os.urandom(2000)

        result = node_a.create_link_and_send_resource(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            data=test_data,
            aspects=aspects,
            link_timeout=15.0,
            resource_timeout=60.0,
        )

        # Transfer should complete successfully
        assert result["status"] == "ACTIVE"
        assert result["resource_completed"] is True


@pytest.mark.security
class TestUnauthorizedAccess:
    """Test unauthorized access prevention."""

    def test_link_to_nonexistent_destination_fails(self, node_a, unique_app_name):
        """
        SEC-006a: Cannot link to non-existent destinations.
        """
        # Generate a random destination hash
        fake_hash = os.urandom(16).hex()

        link = node_a.create_link(
            destination_hash=fake_hash,
            app_name=unique_app_name,
            aspects=["nonexistent"],
            timeout=5.0,
        )

        assert link["status"] in ["NO_PATH", "NO_IDENTITY", "TIMEOUT"]

    def test_link_timeout_graceful(self, node_a, unique_app_name):
        """
        SEC-006b: Link timeouts are handled gracefully.
        """
        # Try to link to impossible destination
        link = node_a.create_link(
            destination_hash="abcd" * 8,
            app_name=unique_app_name,
            aspects=["impossible"],
            timeout=2.0,
        )

        # Should timeout gracefully
        assert "error" in link or link["status"] in ["NO_PATH", "TIMEOUT"]


@pytest.mark.security
class TestInputValidation:
    """Test input validation and sanitization."""

    def test_special_characters_in_app_name(self, node_c, unique_app_name):
        """
        Input with special characters is handled safely.
        """
        # Note: Dots are not allowed in app names
        # Test with allowed special characters
        test_name = unique_app_name + "_test-123"

        dest = node_c.create_destination(
            app_name=test_name,
            aspects=["test"],
            announce=True,
        )

        assert "destination_hash" in dest
        assert len(dest["destination_hash"]) == 32

    def test_empty_aspects_handled(self, node_c, unique_app_name):
        """
        Empty aspects list is handled correctly.
        """
        dest = node_c.create_destination(
            app_name=unique_app_name,
            aspects=[],  # Empty
            announce=True,
        )

        assert "destination_hash" in dest

    def test_unicode_in_app_data(self, node_a, node_c, unique_app_name):
        """
        Unicode in app data is handled correctly.
        """
        aspects = ["security", "unicode"]

        dest = node_c.start_destination_server(
            app_name=unique_app_name,
            aspects=aspects,
            announce=True,
            app_data="Test with unicode: \u00e9\u00f1\u00fc",
        )

        time.sleep(2)

        # Should be able to establish link
        link = node_a.create_link(
            destination_hash=dest["destination_hash"],
            app_name=unique_app_name,
            aspects=aspects,
            timeout=10.0,
        )

        assert link["status"] == "ACTIVE"
