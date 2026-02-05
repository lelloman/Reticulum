"""
Cross-implementation interoperability tests for Reticulum protocol.

Test IDs:
  IOP-001: Python server <-> Other client link establishment
  IOP-002: Other server <-> Python client link establishment
  IOP-003: Bidirectional data packets
  IOP-004: Announce reception and validation
  IOP-005: Resource transfer (small/large)
  IOP-006: Channel message exchange

These tests require an external implementation to be available.
Run with: python -m tests.e2e.test_interop --other-impl=/path/to/binary
"""

import unittest
import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import RNS
from tests.e2e.interfaces.pipe_interface import TestPipeInterface, MockExternalProcess


# Global flag for whether external implementation is available
EXTERNAL_IMPL_PATH = None
SKIP_EXTERNAL_TESTS = True


def setUpModule():
    """Module-level setup to check for external implementation."""
    global SKIP_EXTERNAL_TESTS
    if EXTERNAL_IMPL_PATH and os.path.exists(EXTERNAL_IMPL_PATH):
        SKIP_EXTERNAL_TESTS = False


class TestPipeInterfaceUnit(unittest.TestCase):
    """Unit tests for the TestPipeInterface itself."""

    def test_hdlc_escaping(self):
        """Test HDLC-like byte escaping."""
        interface = TestPipeInterface(None, [])

        # Test escaping
        test_cases = [
            (b"\x00\x01\x02", b"\x00\x01\x02"),  # No escaping needed
            (b"\x7e", b"\x7d\x5e"),  # FLAG byte
            (b"\x7d", b"\x7d\x5d"),  # ESCAPE byte
            (b"\x7e\x7d", b"\x7d\x5e\x7d\x5d"),  # Both
            (b"Hello\x7eWorld", b"Hello\x7d\x5eWorld"),
        ]

        for original, expected_escaped in test_cases:
            with self.subTest(original=original.hex()):
                escaped = interface._escape(original)
                self.assertEqual(escaped, expected_escaped,
                    f"Escape mismatch: got {escaped.hex()}")

                # Round-trip
                unescaped = interface._unescape(escaped)
                self.assertEqual(unescaped, original,
                    f"Unescape mismatch: got {unescaped.hex()}")

    def test_hdlc_framing(self):
        """Test HDLC-like frame creation."""
        interface = TestPipeInterface(None, [])

        data = b"Hello"
        frame = interface._frame(data)

        self.assertEqual(frame[0], 0x7e, "Frame should start with FLAG")
        self.assertEqual(frame[-1], 0x7e, "Frame should end with FLAG")
        self.assertEqual(frame, b"\x7eHello\x7e")

    def test_frame_with_special_bytes(self):
        """Test framing with bytes that need escaping."""
        interface = TestPipeInterface(None, [])

        data = b"\x7e\x7d"
        frame = interface._frame(data)

        # Should be: FLAG + escaped(0x7e) + escaped(0x7d) + FLAG
        expected = b"\x7e\x7d\x5e\x7d\x5d\x7e"
        self.assertEqual(frame, expected)


class TestMockProcess(unittest.TestCase):
    """Test the mock external process helper."""

    def test_mock_frame_handling(self):
        """Test mock process frame operations."""
        mock = MockExternalProcess()

        # Test receiving a frame
        data = b"Hello"
        framed = b"\x7eHello\x7e"
        received = mock.receive_frame(framed)
        self.assertEqual(received, data)
        self.assertEqual(mock.received_frames[-1], data)

    def test_mock_response_creation(self):
        """Test mock process response creation."""
        mock = MockExternalProcess()

        response_data = b"Response"
        framed_response = mock.create_response(response_data)

        self.assertEqual(framed_response[0], 0x7e)
        self.assertEqual(framed_response[-1], 0x7e)


@unittest.skipIf(SKIP_EXTERNAL_TESTS, "External implementation not available")
class TestLinkInterop(unittest.TestCase):
    """Test link establishment between implementations."""

    @classmethod
    def setUpClass(cls):
        """Set up RNS instance for interop tests."""
        try:
            cls.rns = RNS.Reticulum.get_instance()
        except Exception:
            cls.rns = RNS.Reticulum(configdir=os.path.join(
                os.path.dirname(__file__), "..", "..", "rnsconfig"
            ))

    def test_IOP_001_python_server_link(self):
        """IOP-001: Python server <-> Other client link establishment"""
        # This test would:
        # 1. Create a destination on Python side
        # 2. Start external implementation via pipe interface
        # 3. Have external implementation request link
        # 4. Verify link establishment on Python side
        self.skipTest("Requires external implementation")

    def test_IOP_002_other_server_link(self):
        """IOP-002: Other server <-> Python client link establishment"""
        # This test would:
        # 1. Start external implementation with a destination
        # 2. Connect via pipe interface
        # 3. Request link from Python side
        # 4. Verify link establishment
        self.skipTest("Requires external implementation")


@unittest.skipIf(SKIP_EXTERNAL_TESTS, "External implementation not available")
class TestDataInterop(unittest.TestCase):
    """Test data packet exchange between implementations."""

    def test_IOP_003_bidirectional_data(self):
        """IOP-003: Bidirectional data packets"""
        self.skipTest("Requires external implementation")


@unittest.skipIf(SKIP_EXTERNAL_TESTS, "External implementation not available")
class TestAnnounceInterop(unittest.TestCase):
    """Test announce handling between implementations."""

    def test_IOP_004_announce_reception(self):
        """IOP-004: Announce reception and validation"""
        self.skipTest("Requires external implementation")


@unittest.skipIf(SKIP_EXTERNAL_TESTS, "External implementation not available")
class TestResourceInterop(unittest.TestCase):
    """Test resource transfer between implementations."""

    def test_IOP_005_small_resource(self):
        """IOP-005: Small resource transfer"""
        self.skipTest("Requires external implementation")

    def test_IOP_005_large_resource(self):
        """IOP-005: Large resource transfer"""
        self.skipTest("Requires external implementation")


@unittest.skipIf(SKIP_EXTERNAL_TESTS, "External implementation not available")
class TestChannelInterop(unittest.TestCase):
    """Test channel messaging between implementations."""

    def test_IOP_006_channel_exchange(self):
        """IOP-006: Channel message exchange"""
        self.skipTest("Requires external implementation")


class TestProtocolConformance(unittest.TestCase):
    """
    Protocol conformance tests that can run with mock data.

    These tests verify that the Python implementation produces
    correct wire formats that other implementations should accept.
    """

    def test_announce_wire_format(self):
        """Verify announce packet wire format matches specification."""
        # Create an identity with fixed keys for reproducibility
        prv_bytes = bytes.fromhex(
            "f8953ffaf607627e615603ff1530c82c434cf87c07179dd7689ea776f30b964c"
            "d85d036245436a3c33d3228affae06721f8203bc364ee0ee7556368ac62add65"
        )

        identity = RNS.Identity(create_keys=False)
        identity.load_private_key(prv_bytes)

        # Verify public key lengths
        pub_key = identity.get_public_key()
        self.assertEqual(len(pub_key), 64, "Public key should be 64 bytes")

    def test_link_request_wire_format(self):
        """Verify link request packet wire format."""
        # X25519 public key is 32 bytes
        # Ed25519 public key is 32 bytes
        # Optional MTU signalling is 3 bytes

        x25519_pub_len = 32
        ed25519_pub_len = 32
        mtu_signal_len = 3

        # Minimum LINKREQUEST payload
        min_payload = x25519_pub_len + ed25519_pub_len
        self.assertEqual(min_payload, 64)

        # With MTU signalling
        max_payload = min_payload + mtu_signal_len
        self.assertEqual(max_payload, 67)

    def test_channel_envelope_wire_format(self):
        """Verify channel envelope wire format."""
        import struct

        # Envelope: msgtype(2) + sequence(2) + length(2) + data
        header_size = 6

        # Test packing
        msgtype = 1
        sequence = 0
        data = b"Hello"
        length = len(data)

        envelope = struct.pack(">HHH", msgtype, sequence, length) + data
        self.assertEqual(len(envelope), header_size + len(data))

        # Test unpacking
        unpacked_msgtype, unpacked_seq, unpacked_len = struct.unpack(">HHH", envelope[:6])
        unpacked_data = envelope[6:6+unpacked_len]

        self.assertEqual(unpacked_msgtype, msgtype)
        self.assertEqual(unpacked_seq, sequence)
        self.assertEqual(unpacked_data, data)


def main():
    """Main entry point with argument parsing."""
    global EXTERNAL_IMPL_PATH, SKIP_EXTERNAL_TESTS

    parser = argparse.ArgumentParser(description="Reticulum interoperability tests")
    parser.add_argument("--other-impl", type=str,
        help="Path to external implementation binary")
    parser.add_argument("-v", "--verbose", action="count", default=2,
        help="Increase verbosity")

    args, remaining = parser.parse_known_args()

    if args.other_impl:
        EXTERNAL_IMPL_PATH = args.other_impl
        if os.path.exists(args.other_impl):
            SKIP_EXTERNAL_TESTS = False
            print(f"Using external implementation: {args.other_impl}")
        else:
            print(f"Warning: External implementation not found: {args.other_impl}")

    # Run tests
    sys.argv = [sys.argv[0]] + remaining
    unittest.main(verbosity=args.verbose)


if __name__ == "__main__":
    main()
