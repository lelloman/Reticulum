"""
Packet encoding test vectors for Reticulum protocol conformance.

Test IDs:
  PKT-001: DATA packet HEADER_1 encoding
  PKT-002: DATA packet HEADER_2 encoding
  PKT-003: ANNOUNCE packet encoding
  PKT-004: LINKREQUEST packet encoding
  PKT-005: PROOF packet encoding
  PKT-006: Flags byte bit packing
  PKT-007: Destination hash computation
"""

import unittest
import sys
import os
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import RNS
from tests.e2e.utils.vector_loader import VectorLoader
from tests.e2e.utils.protocol_checker import ProtocolChecker


class TestPacketVectors(unittest.TestCase):
    """Test packet encoding against known test vectors."""

    @classmethod
    def setUpClass(cls):
        cls.loader = VectorLoader()

    def test_PKT_001_header1_encoding(self):
        """PKT-001: HEADER_1 packet encoding"""
        for vector in self.loader.iter_vectors("packets", "header"):
            if vector["input"]["header_type"] != 0:
                continue

            with self.subTest(vector_id=vector["id"]):
                # Build flags byte
                flags = ProtocolChecker.pack_flags(
                    vector["input"]["header_type"],
                    vector["input"]["context_flag"],
                    vector["input"]["transport_type"],
                    vector["input"]["dest_type"],
                    vector["input"]["packet_type"]
                )

                self.assertEqual(flags, vector["expected"]["flags"],
                    f"Flags mismatch for {vector['id']}")

                # Verify binary representation
                expected_binary = vector["expected"]["flags_binary"]
                actual_binary = f"{flags:08b}"
                self.assertEqual(actual_binary, expected_binary,
                    f"Binary flags mismatch for {vector['id']}")

                # Build and verify full packet if expected
                if "packet_hex" in vector["expected"]:
                    hops = vector["input"]["hops"]
                    dest_hash = bytes.fromhex(vector["input"]["destination_hash_hex"])
                    context = vector["input"]["context"]
                    payload = bytes.fromhex(vector["input"].get("payload_hex", ""))

                    packet = (
                        struct.pack("!B", flags) +
                        struct.pack("!B", hops) +
                        dest_hash +
                        bytes([context]) +
                        payload
                    )

                    expected_packet = bytes.fromhex(vector["expected"]["packet_hex"])
                    self.assertEqual(packet, expected_packet,
                        f"Packet mismatch for {vector['id']}")

                    if "total_length" in vector["expected"]:
                        self.assertEqual(len(packet), vector["expected"]["total_length"],
                            f"Packet length mismatch for {vector['id']}")

    def test_PKT_002_header2_encoding(self):
        """PKT-002: HEADER_2 packet encoding"""
        for vector in self.loader.iter_vectors("packets", "header"):
            if vector["input"]["header_type"] != 1:
                continue

            with self.subTest(vector_id=vector["id"]):
                flags = ProtocolChecker.pack_flags(
                    vector["input"]["header_type"],
                    vector["input"]["context_flag"],
                    vector["input"]["transport_type"],
                    vector["input"]["dest_type"],
                    vector["input"]["packet_type"]
                )

                self.assertEqual(flags, vector["expected"]["flags"],
                    f"Flags mismatch for {vector['id']}")

                if "header_hex" in vector["expected"]:
                    hops = vector["input"]["hops"]
                    transport_id = bytes.fromhex(vector["input"]["transport_id_hex"])
                    dest_hash = bytes.fromhex(vector["input"]["destination_hash_hex"])
                    context = vector["input"]["context"]

                    header = (
                        struct.pack("!B", flags) +
                        struct.pack("!B", hops) +
                        transport_id +
                        dest_hash +
                        bytes([context])
                    )

                    expected_header = bytes.fromhex(vector["expected"]["header_hex"])
                    self.assertEqual(header, expected_header,
                        f"Header mismatch for {vector['id']}")

    def test_PKT_004_linkrequest_encoding(self):
        """PKT-004: LINKREQUEST packet encoding"""
        for vector in self.loader.iter_vectors("packets", "link"):
            with self.subTest(vector_id=vector["id"]):
                if "x25519_pub_hex" in vector["input"] and "ed25519_pub_hex" in vector["input"]:
                    x25519_pub = bytes.fromhex(vector["input"]["x25519_pub_hex"])
                    ed25519_pub = bytes.fromhex(vector["input"]["ed25519_pub_hex"])

                    payload = x25519_pub + ed25519_pub

                    if "mtu" in vector["input"]:
                        mtu = vector["input"]["mtu"]
                        mode = vector["input"]["mode"]
                        # Pack MTU signalling bytes
                        mtu_bytes = struct.pack(">I", (mtu & 0x1FFFFF) + ((mode << 5) << 16))[1:]
                        payload += mtu_bytes

                        if "mtu_bytes_hex" in vector["expected"]:
                            self.assertEqual(mtu_bytes, bytes.fromhex(vector["expected"]["mtu_bytes_hex"]),
                                f"MTU bytes mismatch for {vector['id']}")

                    if "payload_hex" in vector["expected"]:
                        self.assertEqual(payload, bytes.fromhex(vector["expected"]["payload_hex"]),
                            f"Payload mismatch for {vector['id']}")

                    if "payload_length" in vector["expected"]:
                        self.assertEqual(len(payload), vector["expected"]["payload_length"],
                            f"Payload length mismatch for {vector['id']}")

    def test_PKT_005_lrproof_encoding(self):
        """PKT-005: LRPROOF packet encoding"""
        for vector in self.loader.iter_vectors("packets", "link"):
            if "signature_hex" not in vector["input"]:
                continue

            with self.subTest(vector_id=vector["id"]):
                signature = bytes.fromhex(vector["input"]["signature_hex"])
                x25519_pub = bytes.fromhex(vector["input"]["x25519_pub_hex"])

                payload = signature + x25519_pub

                if "payload_hex" in vector["expected"]:
                    self.assertEqual(payload, bytes.fromhex(vector["expected"]["payload_hex"]),
                        f"Payload mismatch for {vector['id']}")

                if "payload_length" in vector["expected"]:
                    self.assertEqual(len(payload), vector["expected"]["payload_length"],
                        f"Payload length mismatch for {vector['id']}")

    def test_PKT_006_flags_packing(self):
        """PKT-006: Flags byte bit packing"""
        test_cases = [
            # (header_type, context_flag, transport_type, dest_type, packet_type, expected)
            (0, 0, 0, 0, 0, 0b00000000),  # DATA to SINGLE via BROADCAST
            (0, 0, 0, 0, 1, 0b00000001),  # ANNOUNCE
            (0, 0, 0, 0, 2, 0b00000010),  # LINKREQUEST
            (0, 0, 0, 0, 3, 0b00000011),  # PROOF
            (0, 0, 0, 1, 0, 0b00000100),  # GROUP destination
            (0, 0, 0, 2, 0, 0b00001000),  # PLAIN destination
            (0, 0, 0, 3, 0, 0b00001100),  # LINK destination
            (0, 0, 1, 0, 0, 0b00010000),  # TRANSPORT type
            (0, 1, 0, 0, 0, 0b00100000),  # context_flag set
            (1, 0, 0, 0, 0, 0b01000000),  # HEADER_2
            (1, 0, 1, 0, 1, 0b01010001),  # HEADER_2, TRANSPORT, ANNOUNCE
            (0, 1, 0, 3, 0, 0b00101100),  # context_flag, LINK dest
        ]

        for ht, cf, tt, dt, pt, expected in test_cases:
            with self.subTest(ht=ht, cf=cf, tt=tt, dt=dt, pt=pt):
                result = ProtocolChecker.pack_flags(ht, cf, tt, dt, pt)
                self.assertEqual(result, expected,
                    f"Flags packing error: got {result:08b}, expected {expected:08b}")

    def test_PKT_007_destination_hash(self):
        """PKT-007: Destination hash computation"""
        for vector in self.loader.iter_vectors("packets", "announce"):
            if "name_hash_hex" not in vector["input"]:
                continue
            if "identity_hash_hex" not in vector["input"]:
                continue
            if "destination_hash_hex" not in vector["expected"]:
                continue

            with self.subTest(vector_id=vector["id"]):
                name_hash = bytes.fromhex(vector["input"]["name_hash_hex"])
                identity_hash = bytes.fromhex(vector["input"]["identity_hash_hex"])
                expected_dest_hash = bytes.fromhex(vector["expected"]["destination_hash_hex"])

                # destination_hash = truncated_hash(name_hash + identity_hash)
                computed = RNS.Identity.truncated_hash(name_hash + identity_hash)

                self.assertEqual(computed, expected_dest_hash,
                    f"Destination hash mismatch for {vector['id']}: "
                    f"expected {expected_dest_hash.hex()}, got {computed.hex()}")


class TestPacketParsing(unittest.TestCase):
    """Test packet parsing using ProtocolChecker."""

    def test_parse_header1_packet(self):
        """Parse HEADER_1 packet structure"""
        # Simple DATA packet
        packet = bytes.fromhex("0000650b5d76b6bec0390d1f8cfca5bd33f90048656c6c6f")

        result = ProtocolChecker.check_packet_header(packet)

        self.assertTrue(result["valid"])
        self.assertEqual(result["parsed"]["header_type"], 0)
        self.assertEqual(result["parsed"]["packet_type"], 0)
        self.assertEqual(result["parsed"]["dest_type"], 0)
        self.assertEqual(result["parsed"]["destination_hash"],
            bytes.fromhex("650b5d76b6bec0390d1f8cfca5bd33f9"))
        self.assertEqual(result["parsed"]["context"], 0)
        self.assertEqual(result["parsed"]["payload"], b"Hello")

    def test_parse_header2_packet(self):
        """Parse HEADER_2 packet structure"""
        header = bytes.fromhex(
            "51031469e89450c361b253aefb0c606b6111"
            "650b5d76b6bec0390d1f8cfca5bd33f900"
        )

        result = ProtocolChecker.check_packet_header(header)

        self.assertTrue(result["valid"])
        self.assertEqual(result["parsed"]["header_type"], 1)
        self.assertEqual(result["parsed"]["packet_type"], 1)  # ANNOUNCE
        self.assertEqual(result["parsed"]["transport_type"], 1)  # TRANSPORT
        self.assertEqual(result["parsed"]["hops"], 3)
        self.assertEqual(result["parsed"]["transport_id"],
            bytes.fromhex("1469e89450c361b253aefb0c606b6111"))
        self.assertEqual(result["parsed"]["destination_hash"],
            bytes.fromhex("650b5d76b6bec0390d1f8cfca5bd33f9"))

    def test_parse_linkrequest(self):
        """Parse LINKREQUEST packet payload"""
        payload = bytes.fromhex(
            "4219d9ce29da42bc823b66b24a051c65b482f062a436bdeb3793bbfa62924930"
            "1cd07b674027511e73469c4edec93634c2965fdeeae8e1c50db4b912c616501b"
        )

        result = ProtocolChecker.check_linkrequest_packet(payload)

        self.assertTrue(result["valid"])
        self.assertEqual(result["parsed"]["x25519_pub"],
            bytes.fromhex("4219d9ce29da42bc823b66b24a051c65b482f062a436bdeb3793bbfa62924930"))
        self.assertEqual(result["parsed"]["ed25519_pub"],
            bytes.fromhex("1cd07b674027511e73469c4edec93634c2965fdeeae8e1c50db4b912c616501b"))
        self.assertFalse(result["parsed"]["has_mtu_signalling"])

    def test_parse_linkrequest_with_mtu(self):
        """Parse LINKREQUEST packet with MTU signalling"""
        payload = bytes.fromhex(
            "4219d9ce29da42bc823b66b24a051c65b482f062a436bdeb3793bbfa62924930"
            "1cd07b674027511e73469c4edec93634c2965fdeeae8e1c50db4b912c616501b"
            "2001f4"  # MTU=500, mode=1
        )

        result = ProtocolChecker.check_linkrequest_packet(payload)

        self.assertTrue(result["valid"])
        self.assertTrue(result["parsed"]["has_mtu_signalling"])
        self.assertEqual(result["parsed"]["mtu"], 500)
        self.assertEqual(result["parsed"]["mode"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
