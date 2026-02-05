"""
Channel messaging test vectors for Reticulum protocol conformance.

Test IDs:
  CHN-001: Channel envelope pack format
  CHN-002: Channel envelope unpack
  CHN-003: Sequence number encoding
  CHN-004: Message type header (MSGTYPE)
  CHN-005: Buffer StreamDataMessage format
"""

import unittest
import sys
import os
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.e2e.utils.vector_loader import VectorLoader
from tests.e2e.utils.protocol_checker import ProtocolChecker


class TestChannelVectors(unittest.TestCase):
    """Test channel messaging protocol against known test vectors."""

    @classmethod
    def setUpClass(cls):
        cls.loader = VectorLoader()

    def test_CHN_001_envelope_packing(self):
        """CHN-001: Channel envelope pack format"""
        for vector in self.loader.iter_vectors("channel", "envelope"):
            if "envelope_hex" not in vector.get("expected", {}):
                continue

            with self.subTest(vector_id=vector["id"]):
                msgtype = vector["input"]["msgtype"]
                sequence = vector["input"]["sequence"]
                data = bytes.fromhex(vector["input"]["data_hex"])
                length = len(data)

                # Pack envelope: msgtype(2) + sequence(2) + length(2) + data
                envelope = struct.pack(">HHH", msgtype, sequence, length) + data

                expected = bytes.fromhex(vector["expected"]["envelope_hex"])
                self.assertEqual(envelope, expected,
                    f"Envelope mismatch for {vector['id']}: "
                    f"expected {expected.hex()}, got {envelope.hex()}")

                if "length" in vector["expected"]:
                    self.assertEqual(len(envelope), vector["expected"]["length"],
                        f"Envelope length mismatch for {vector['id']}")

    def test_CHN_002_envelope_unpacking(self):
        """CHN-002: Channel envelope unpack"""
        # Test envelope unpacking
        test_cases = [
            # (envelope_hex, expected_msgtype, expected_sequence, expected_data_hex)
            ("000100000005" + "48656c6c6f", 1, 0, "48656c6c6f"),
            ("010004d20004" + "74657374", 256, 1234, "74657374"),
            ("000100000000", 1, 0, ""),
        ]

        for envelope_hex, expected_msgtype, expected_seq, expected_data_hex in test_cases:
            with self.subTest(envelope=envelope_hex):
                envelope = bytes.fromhex(envelope_hex)

                result = ProtocolChecker.check_channel_envelope(envelope)

                self.assertTrue(result["valid"], f"Parse errors: {result['errors']}")
                self.assertEqual(result["parsed"]["msgtype"], expected_msgtype,
                    f"Msgtype mismatch")
                self.assertEqual(result["parsed"]["sequence"], expected_seq,
                    f"Sequence mismatch")
                self.assertEqual(result["parsed"]["data"], bytes.fromhex(expected_data_hex),
                    f"Data mismatch")

    def test_CHN_003_sequence_encoding(self):
        """CHN-003: Sequence number encoding"""
        # Sequence is 16-bit unsigned, big-endian
        test_cases = [
            (0, b"\x00\x00"),
            (1, b"\x00\x01"),
            (255, b"\x00\xff"),
            (256, b"\x01\x00"),
            (1234, b"\x04\xd2"),
            (65535, b"\xff\xff"),  # Max sequence
        ]

        for sequence, expected_bytes in test_cases:
            with self.subTest(sequence=sequence):
                packed = struct.pack(">H", sequence)
                self.assertEqual(packed, expected_bytes,
                    f"Sequence encoding mismatch for {sequence}")

                unpacked = struct.unpack(">H", expected_bytes)[0]
                self.assertEqual(unpacked, sequence,
                    f"Sequence decoding mismatch for {sequence}")

    def test_CHN_004_message_types(self):
        """CHN-004: Message type header validation"""
        # User message types must be < 0xF000
        # System types are >= 0xF000
        user_types = [0, 1, 255, 0x0FFF, 0xEFFF]
        system_types = [0xF000, 0xFF00, 0xFFFF]

        for msgtype in user_types:
            with self.subTest(msgtype=msgtype, type="user"):
                self.assertTrue(msgtype < 0xF000,
                    f"User message type {msgtype} should be < 0xF000")

        for msgtype in system_types:
            with self.subTest(msgtype=msgtype, type="system"):
                self.assertTrue(msgtype >= 0xF000,
                    f"System message type {msgtype} should be >= 0xF000")

    def test_CHN_005_envelope_header_size(self):
        """CHN-005: Envelope header is always 6 bytes"""
        # Header: msgtype(2) + sequence(2) + length(2) = 6 bytes
        header_size = 6

        # Verify by packing an envelope with empty data
        envelope = struct.pack(">HHH", 1, 0, 0)
        self.assertEqual(len(envelope), header_size,
            "Envelope header should be 6 bytes")


class TestChannelEnvelopeParsing(unittest.TestCase):
    """Test channel envelope parsing edge cases."""

    def test_minimum_envelope_size(self):
        """Envelope must be at least 6 bytes"""
        short_data = bytes(5)
        result = ProtocolChecker.check_channel_envelope(short_data)

        self.assertFalse(result["valid"])
        self.assertTrue(any("too short" in e.lower() for e in result["errors"]))

    def test_length_validation(self):
        """Verify length field matches actual data"""
        # Create envelope with mismatched length
        msgtype = 1
        sequence = 0
        actual_data = b"Hello"
        wrong_length = 10  # Says 10 bytes but only 5

        envelope = struct.pack(">HHH", msgtype, sequence, wrong_length) + actual_data
        result = ProtocolChecker.check_channel_envelope(envelope)

        self.assertFalse(result["valid"])
        self.assertTrue(any("mismatch" in e.lower() for e in result["errors"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
