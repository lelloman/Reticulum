"""
Resource transfer test vectors for Reticulum protocol conformance.

Test IDs:
  RES-001: Resource advertisement msgpack format
  RES-002: Resource hashmap computation
  RES-003: Resource part request format
  RES-004: Resource proof format
  RES-005: Compressed resource handling
  RES-006: Small resource transfer (< 1 segment)
  RES-007: Multi-segment resource transfer
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import RNS
from RNS.vendor import umsgpack
from tests.e2e.utils.vector_loader import VectorLoader


class TestResourceVectors(unittest.TestCase):
    """Test resource transfer protocol against known test vectors."""

    @classmethod
    def setUpClass(cls):
        cls.loader = VectorLoader()

    def test_RES_001_flags_encoding(self):
        """RES-001: Resource advertisement flags encoding"""
        for vector in self.loader.iter_vectors("resource", "advertisement"):
            if "encrypted" not in vector["input"]:
                continue

            with self.subTest(vector_id=vector["id"]):
                e = 1 if vector["input"]["encrypted"] else 0
                c = 1 if vector["input"]["compressed"] else 0
                s = 1 if vector["input"]["split"] else 0
                u = 1 if vector["input"]["is_request"] else 0
                p = 1 if vector["input"]["is_response"] else 0
                x = 1 if vector["input"]["has_metadata"] else 0

                # Flags layout: x_p_u_s_c_e
                flags = x << 5 | p << 4 | u << 3 | s << 2 | c << 1 | e

                self.assertEqual(flags, vector["expected"]["flags"],
                    f"Flags mismatch for {vector['id']}: expected {vector['expected']['flags']}, got {flags}")

    def test_RES_001_flags_decoding(self):
        """RES-001: Resource advertisement flags decoding"""
        test_cases = [
            (0x01, True, False, False, False, False, False),
            (0x03, True, True, False, False, False, False),
            (0x2F, True, True, True, True, False, True),
        ]

        for flags, encrypted, compressed, split, is_request, is_response, has_metadata in test_cases:
            with self.subTest(flags=flags):
                e = (flags & 0x01) == 0x01
                c = ((flags >> 1) & 0x01) == 0x01
                s = ((flags >> 2) & 0x01) == 0x01
                u = ((flags >> 3) & 0x01) == 0x01
                p = ((flags >> 4) & 0x01) == 0x01
                x = ((flags >> 5) & 0x01) == 0x01

                self.assertEqual(e, encrypted, f"Encrypted flag mismatch for flags={flags}")
                self.assertEqual(c, compressed, f"Compressed flag mismatch for flags={flags}")
                self.assertEqual(s, split, f"Split flag mismatch for flags={flags}")
                self.assertEqual(u, is_request, f"Is_request flag mismatch for flags={flags}")
                self.assertEqual(p, is_response, f"Is_response flag mismatch for flags={flags}")
                self.assertEqual(x, has_metadata, f"Has_metadata flag mismatch for flags={flags}")

    def test_RES_002_map_hash_computation(self):
        """RES-002: Resource hashmap computation"""
        # Map hash = full_hash(data + random_hash)[:4]
        data = b"Hello World"
        random_hash = bytes.fromhex("12345678")

        map_hash = RNS.Identity.full_hash(data + random_hash)[:4]

        self.assertEqual(len(map_hash), 4, "Map hash should be 4 bytes")

        # Verify it's deterministic
        map_hash_2 = RNS.Identity.full_hash(data + random_hash)[:4]
        self.assertEqual(map_hash, map_hash_2, "Map hash should be deterministic")

    def test_RES_003_advertisement_msgpack(self):
        """RES-003: Resource advertisement msgpack structure"""
        # Create a sample advertisement dictionary
        adv = {
            "t": 1024,  # Transfer size
            "d": 2048,  # Data size
            "n": 3,     # Number of parts
            "h": bytes(32),  # Resource hash
            "r": bytes(4),   # Random hash
            "o": bytes(32),  # Original hash
            "i": 1,     # Segment index
            "l": 1,     # Total segments
            "q": None,  # Request ID
            "f": 0x01,  # Flags (encrypted)
            "m": bytes(12),  # Hashmap (3 parts * 4 bytes)
        }

        # Pack and unpack
        packed = umsgpack.packb(adv)
        unpacked = umsgpack.unpackb(packed)

        self.assertEqual(unpacked["t"], adv["t"])
        self.assertEqual(unpacked["d"], adv["d"])
        self.assertEqual(unpacked["n"], adv["n"])
        self.assertEqual(unpacked["f"], adv["f"])
        self.assertEqual(unpacked["i"], adv["i"])
        self.assertEqual(unpacked["l"], adv["l"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
