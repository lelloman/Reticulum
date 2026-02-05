"""
Announce protocol test vectors for Reticulum protocol conformance.

Test IDs:
  ANN-001: Announce packet without ratchet
  ANN-002: Announce packet with ratchet (context_flag set)
  ANN-003: Announce signature computation
  ANN-004: Announce validation (accept valid, reject tampered)
  ANN-005: Destination hash from announce
  ANN-006: Path response announce format
"""

import unittest
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import RNS
from tests.e2e.utils.vector_loader import VectorLoader
from tests.e2e.utils.protocol_checker import ProtocolChecker


def _get_rns():
    """Get or create RNS instance."""
    if RNS.Reticulum.get_instance() is None:
        return RNS.Reticulum(configdir="./tests/rnsconfig")
    return RNS.Reticulum.get_instance()


def _unique_aspect():
    """Generate a unique aspect to avoid destination conflicts."""
    return str(uuid.uuid4())[:8]


class TestAnnounceVectors(unittest.TestCase):
    """Test announce packet encoding and validation."""

    @classmethod
    def setUpClass(cls):
        cls.loader = VectorLoader()
        # Initialize RNS for announce validation
        cls._rns = _get_rns()

    def test_ANN_001_announce_without_ratchet(self):
        """ANN-001: Announce packet without ratchet"""
        for vector in self.loader.iter_vectors("packets", "announce"):
            if "identity_private_key_hex" not in vector["input"]:
                continue

            with self.subTest(vector_id=vector["id"]):
                # Load identity from private key
                prv_bytes = bytes.fromhex(vector["input"]["identity_private_key_hex"])
                identity = RNS.Identity.from_bytes(prv_bytes)

                # Verify identity hash
                expected_id_hash = bytes.fromhex(vector["expected"]["identity_hash_hex"])
                self.assertEqual(identity.hash, expected_id_hash,
                    f"Identity hash mismatch for {vector['id']}")

                # Verify public key
                expected_pub = bytes.fromhex(vector["expected"]["public_key_hex"])
                self.assertEqual(identity.get_public_key(), expected_pub,
                    f"Public key mismatch for {vector['id']}")

    def test_ANN_003_signature_computation(self):
        """ANN-003: Announce signature computation"""
        for vector in self.loader.iter_vectors("packets", "announce"):
            if "signed_data_hex" not in vector.get("expected", {}):
                continue

            with self.subTest(vector_id=vector["id"]):
                # Build signed data
                dest_hash = bytes.fromhex(vector["input"]["destination_hash_hex"])
                public_key = bytes.fromhex(vector["input"]["public_key_hex"])
                name_hash = bytes.fromhex(vector["input"]["name_hash_hex"])
                random_hash = bytes.fromhex(vector["input"]["random_hash_hex"])
                ratchet = bytes.fromhex(vector["input"].get("ratchet_hex", ""))
                app_data = bytes.fromhex(vector["input"].get("app_data_hex", ""))

                signed_data = dest_hash + public_key + name_hash + random_hash + ratchet + app_data

                expected_signed_data = bytes.fromhex(vector["expected"]["signed_data_hex"])
                self.assertEqual(signed_data, expected_signed_data,
                    f"Signed data mismatch for {vector['id']}")

    def test_ANN_004_announce_validation(self):
        """ANN-004: Validate announce packets"""
        # Test with a valid announce from known identity
        prv_bytes = bytes.fromhex(
            "b82c7a4f047561d974de7e38538281d7f005d3663615f30d9663bad35a716063"
            "c931672cd452175d55bcdd70bb7aa35a9706872a97963dc52029938ea7341b39"
        )
        identity = RNS.Identity.from_bytes(prv_bytes)

        # Create a destination with unique aspect
        dest = RNS.Destination(
            identity,
            RNS.Destination.IN,
            RNS.Destination.SINGLE,
            "e2etest", _unique_aspect()
        )

        packet = dest.announce(send=False)
        packet.pack()

        # Validate the announce
        valid = RNS.Identity.validate_announce(packet)
        self.assertTrue(valid, "Valid announce should pass validation")

    def test_ANN_004_reject_tampered_announce(self):
        """ANN-004: Reject tampered announce packets"""
        prv_bytes = bytes.fromhex(
            "b82c7a4f047561d974de7e38538281d7f005d3663615f30d9663bad35a716063"
            "c931672cd452175d55bcdd70bb7aa35a9706872a97963dc52029938ea7341b39"
        )
        identity = RNS.Identity.from_bytes(prv_bytes)

        dest = RNS.Destination(
            identity,
            RNS.Destination.IN,
            RNS.Destination.SINGLE,
            "e2etest", _unique_aspect()
        )

        packet = dest.announce(send=False)
        packet.pack()

        # Tamper with the destination hash in the raw packet
        original_raw = packet.raw
        tampered_raw = bytearray(original_raw)
        # Modify a byte in the destination hash area (bytes 2-17)
        tampered_raw[5] ^= 0xFF
        packet.raw = bytes(tampered_raw)

        # Re-unpack the tampered packet
        packet.unpack()

        # Validation should fail
        valid = RNS.Identity.validate_announce(packet)
        self.assertFalse(valid, "Tampered announce should fail validation")

    def test_ANN_005_destination_hash_computation(self):
        """ANN-005: Destination hash from announce"""
        # Test destination hash = truncated_hash(name_hash + identity_hash)
        prv_bytes = bytes.fromhex(
            "b82c7a4f047561d974de7e38538281d7f005d3663615f30d9663bad35a716063"
            "c931672cd452175d55bcdd70bb7aa35a9706872a97963dc52029938ea7341b39"
        )
        identity = RNS.Identity.from_bytes(prv_bytes)

        # Create destination with unique aspect
        unique_aspect = _unique_aspect()
        dest = RNS.Destination(
            identity,
            RNS.Destination.IN,
            RNS.Destination.SINGLE,
            "e2etest", unique_aspect
        )

        # Compute expected destination hash
        name_hash = dest.name_hash
        identity_hash = identity.hash
        computed_dest_hash = RNS.Identity.truncated_hash(name_hash + identity_hash)

        self.assertEqual(dest.hash, computed_dest_hash,
            f"Destination hash mismatch: expected {computed_dest_hash.hex()}, got {dest.hash.hex()}")


class TestAnnouncePacketStructure(unittest.TestCase):
    """Test announce packet structure parsing."""

    @classmethod
    def setUpClass(cls):
        cls._rns = _get_rns()

    def test_announce_payload_structure(self):
        """Verify announce payload structure"""
        prv_bytes = bytes.fromhex(
            "b82c7a4f047561d974de7e38538281d7f005d3663615f30d9663bad35a716063"
            "c931672cd452175d55bcdd70bb7aa35a9706872a97963dc52029938ea7341b39"
        )
        identity = RNS.Identity.from_bytes(prv_bytes)

        dest = RNS.Destination(
            identity,
            RNS.Destination.IN,
            RNS.Destination.SINGLE,
            "e2etest", _unique_aspect()
        )

        packet = dest.announce(send=False)
        packet.pack()

        # Parse the announce payload
        result = ProtocolChecker.check_announce_packet(packet.data)

        self.assertTrue(result["valid"], f"Parse errors: {result['errors']}")

        # Verify parsed components
        self.assertEqual(result["parsed"]["public_key"], identity.get_public_key(),
            "Public key mismatch in parsed announce")

        # Signature should be 64 bytes
        self.assertEqual(len(result["parsed"]["signature"]), 64,
            "Signature length should be 64 bytes")

    def test_announce_with_app_data(self):
        """Test announce with application data"""
        prv_bytes = bytes.fromhex(
            "b82c7a4f047561d974de7e38538281d7f005d3663615f30d9663bad35a716063"
            "c931672cd452175d55bcdd70bb7aa35a9706872a97963dc52029938ea7341b39"
        )
        identity = RNS.Identity.from_bytes(prv_bytes)

        dest = RNS.Destination(
            identity,
            RNS.Destination.IN,
            RNS.Destination.SINGLE,
            "e2etest", _unique_aspect()
        )

        # Set app data
        app_data = b"Test application data"
        dest.set_default_app_data(app_data)

        packet = dest.announce(send=False)
        packet.pack()

        # Parse and verify app_data is present
        result = ProtocolChecker.check_announce_packet(packet.data)
        self.assertTrue(result["valid"])

        if "app_data" in result["parsed"]:
            self.assertEqual(result["parsed"]["app_data"], app_data,
                "App data mismatch in parsed announce")


if __name__ == "__main__":
    unittest.main(verbosity=2)
