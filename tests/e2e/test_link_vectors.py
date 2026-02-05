"""
Link protocol test vectors for Reticulum protocol conformance.

Test IDs:
  LINK-001: Link ID from LINKREQUEST hash
  LINK-002: Handshake packet sequence
  LINK-003: Link proof signature validity
  LINK-004: Derived key computation (HKDF)
  LINK-005: MTU signalling bytes
"""

import unittest
import sys
import os
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import RNS
from RNS.Cryptography import X25519PrivateKey, X25519PublicKey, hkdf
from tests.e2e.utils.vector_loader import VectorLoader
from tests.e2e.utils.protocol_checker import ProtocolChecker


class TestLinkVectors(unittest.TestCase):
    """Test link handshake protocol against known test vectors."""

    @classmethod
    def setUpClass(cls):
        cls.loader = VectorLoader()

    def test_LINK_001_link_id_computation(self):
        """LINK-001: Link ID from LINKREQUEST hash"""
        # Build a LINKREQUEST packet and compute link_id
        x25519_pub = bytes.fromhex(
            "4219d9ce29da42bc823b66b24a051c65b482f062a436bdeb3793bbfa62924930"
        )
        ed25519_pub = bytes.fromhex(
            "1cd07b674027511e73469c4edec93634c2965fdeeae8e1c50db4b912c616501b"
        )
        dest_hash = bytes.fromhex("650b5d76b6bec0390d1f8cfca5bd33f9")

        # Build LINKREQUEST packet header
        # flags: HEADER_1, no context_flag, BROADCAST, SINGLE, LINKREQUEST
        flags = ProtocolChecker.pack_flags(0, 0, 0, 0, 2)  # LINKREQUEST = 2
        hops = 0
        context = 0x00

        # Full packet
        header = struct.pack("!B", flags) + struct.pack("!B", hops) + dest_hash + bytes([context])
        payload = x25519_pub + ed25519_pub
        raw_packet = header + payload

        # Compute hashable part (used for link_id)
        # hashable_part = (flags & 0x0F) + raw[2:] for HEADER_1
        hashable_part = bytes([raw_packet[0] & 0x0F]) + raw_packet[2:]

        # Link ID is truncated hash of hashable part
        link_id = RNS.Identity.truncated_hash(hashable_part)

        # Verify link ID is 16 bytes
        self.assertEqual(len(link_id), 16, "Link ID should be 16 bytes")

        # The link_id should be deterministic for the same input
        link_id_2 = RNS.Identity.truncated_hash(hashable_part)
        self.assertEqual(link_id, link_id_2, "Link ID should be deterministic")

    def test_LINK_004_derived_key_computation(self):
        """LINK-004: Derived key computation (HKDF)"""
        # Simulate link key derivation
        prv_a = X25519PrivateKey.from_private_bytes(
            bytes.fromhex("f8953ffaf607627e615603ff1530c82c434cf87c07179dd7689ea776f30b964c")
        )
        prv_b = X25519PrivateKey.from_private_bytes(
            bytes.fromhex("d85d036245436a3c33d3228affae06721f8203bc364ee0ee7556368ac62add65")
        )

        pub_a = prv_a.public_key()
        pub_b = prv_b.public_key()

        # Shared secret from both sides
        shared_a = prv_a.exchange(pub_b)
        shared_b = prv_b.exchange(pub_a)
        self.assertEqual(shared_a, shared_b, "Shared secrets should match")

        # Link ID (simulated)
        link_id = bytes.fromhex("650b5d76b6bec0390d1f8cfca5bd33f9")

        # Derive key using HKDF (64 bytes for AES-256)
        derived_key = hkdf(
            length=64,
            derive_from=shared_a,
            salt=link_id,
            context=None
        )

        self.assertEqual(len(derived_key), 64, "Derived key should be 64 bytes for AES-256")

        # Verify HKDF is deterministic
        derived_key_2 = hkdf(
            length=64,
            derive_from=shared_a,
            salt=link_id,
            context=None
        )
        self.assertEqual(derived_key, derived_key_2, "Derived key should be deterministic")

        # Split derived key into signing and encryption keys
        signing_key = derived_key[:32]
        encryption_key = derived_key[32:]

        self.assertEqual(len(signing_key), 32, "Signing key should be 32 bytes")
        self.assertEqual(len(encryption_key), 32, "Encryption key should be 32 bytes")

    def test_LINK_005_mtu_signalling(self):
        """LINK-005: MTU signalling bytes"""
        for vector in self.loader.iter_vectors("packets", "link"):
            if "mtu" not in vector["input"]:
                continue
            if "mtu_bytes_hex" not in vector.get("expected", {}):
                continue

            with self.subTest(vector_id=vector["id"]):
                mtu = vector["input"]["mtu"]
                mode = vector["input"]["mode"]

                # Pack MTU signalling bytes
                # Format: 3 bytes, mode in high 3 bits, MTU in low 21 bits
                signalling_value = (mtu & 0x1FFFFF) + ((mode << 5) << 16)
                mtu_bytes = struct.pack(">I", signalling_value)[1:]

                expected_bytes = bytes.fromhex(vector["expected"]["mtu_bytes_hex"])
                self.assertEqual(mtu_bytes, expected_bytes,
                    f"MTU bytes mismatch for {vector['id']}: "
                    f"expected {expected_bytes.hex()}, got {mtu_bytes.hex()}")

                # Verify individual bytes if specified
                if "mtu_byte_0" in vector["expected"]:
                    self.assertEqual(mtu_bytes[0], vector["expected"]["mtu_byte_0"],
                        f"MTU byte 0 mismatch for {vector['id']}")
                if "mtu_byte_1" in vector["expected"]:
                    self.assertEqual(mtu_bytes[1], vector["expected"]["mtu_byte_1"],
                        f"MTU byte 1 mismatch for {vector['id']}")
                if "mtu_byte_2" in vector["expected"]:
                    self.assertEqual(mtu_bytes[2], vector["expected"]["mtu_byte_2"],
                        f"MTU byte 2 mismatch for {vector['id']}")

                # Verify decoding
                decoded_mtu = ((mtu_bytes[0] & 0x1F) << 16) + (mtu_bytes[1] << 8) + mtu_bytes[2]
                decoded_mode = (mtu_bytes[0] & 0xE0) >> 5

                self.assertEqual(decoded_mtu, mtu,
                    f"Decoded MTU mismatch for {vector['id']}")
                self.assertEqual(decoded_mode, mode,
                    f"Decoded mode mismatch for {vector['id']}")


class TestLinkHandshake(unittest.TestCase):
    """Test link handshake packet structures."""

    def test_linkrequest_structure(self):
        """Verify LINKREQUEST packet structure"""
        x25519_pub = bytes.fromhex(
            "4219d9ce29da42bc823b66b24a051c65b482f062a436bdeb3793bbfa62924930"
        )
        ed25519_pub = bytes.fromhex(
            "1cd07b674027511e73469c4edec93634c2965fdeeae8e1c50db4b912c616501b"
        )

        payload = x25519_pub + ed25519_pub
        result = ProtocolChecker.check_linkrequest_packet(payload)

        self.assertTrue(result["valid"])
        self.assertEqual(result["parsed"]["x25519_pub"], x25519_pub)
        self.assertEqual(result["parsed"]["ed25519_pub"], ed25519_pub)
        self.assertFalse(result["parsed"]["has_mtu_signalling"])

    def test_linkrequest_with_mtu_structure(self):
        """Verify LINKREQUEST packet with MTU signalling"""
        x25519_pub = bytes.fromhex(
            "4219d9ce29da42bc823b66b24a051c65b482f062a436bdeb3793bbfa62924930"
        )
        ed25519_pub = bytes.fromhex(
            "1cd07b674027511e73469c4edec93634c2965fdeeae8e1c50db4b912c616501b"
        )
        mtu_bytes = bytes.fromhex("2001f4")  # MTU=500, mode=1

        payload = x25519_pub + ed25519_pub + mtu_bytes
        result = ProtocolChecker.check_linkrequest_packet(payload)

        self.assertTrue(result["valid"])
        self.assertTrue(result["parsed"]["has_mtu_signalling"])
        self.assertEqual(result["parsed"]["mtu"], 500)
        self.assertEqual(result["parsed"]["mode"], 1)

    def test_lrproof_structure(self):
        """Verify LRPROOF packet structure"""
        signature = bytes.fromhex(
            "d2a6f0be8527261d527045dd810b543a24716b98e0400ed4c793094dffe2e66d"
            "55105919691d2c2dd3e79268b9412beec7ea8035fc277796e5eeed25139c2a0e"
        )
        x25519_pub = bytes.fromhex(
            "a6ad9609176a4c5012ae056539065be584d5dc92e78ee151dd64654ccf0cd635"
        )

        payload = signature + x25519_pub
        result = ProtocolChecker.check_lrproof_packet(payload)

        self.assertTrue(result["valid"])
        self.assertEqual(result["parsed"]["signature"], signature)
        self.assertEqual(result["parsed"]["x25519_pub"], x25519_pub)
        self.assertFalse(result["parsed"]["has_mtu_signalling"])

    def test_lrproof_with_mtu_structure(self):
        """Verify LRPROOF packet with MTU signalling"""
        signature = bytes.fromhex(
            "d2a6f0be8527261d527045dd810b543a24716b98e0400ed4c793094dffe2e66d"
            "55105919691d2c2dd3e79268b9412beec7ea8035fc277796e5eeed25139c2a0e"
        )
        x25519_pub = bytes.fromhex(
            "a6ad9609176a4c5012ae056539065be584d5dc92e78ee151dd64654ccf0cd635"
        )
        mtu_bytes = bytes.fromhex("2001f4")  # MTU=500, mode=1

        payload = signature + x25519_pub + mtu_bytes
        result = ProtocolChecker.check_lrproof_packet(payload)

        self.assertTrue(result["valid"])
        self.assertTrue(result["parsed"]["has_mtu_signalling"])
        self.assertEqual(result["parsed"]["mtu"], 500)
        self.assertEqual(result["parsed"]["mode"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
