"""Malicious interface for security testing.

This interface allows injection of malformed or adversarial packets
for testing Reticulum's security and error handling.

NOTE: This is for testing purposes only. Do not use in production.
"""

import RNS
from RNS.Interfaces.Interface import Interface
import os
import time
import threading
from typing import Optional, Callable, List, Any


class MaliciousInterface(Interface):
    """
    An interface that can inject malformed packets for security testing.

    This interface doesn't connect to any real network - it's used for
    testing how the protocol handles malicious or malformed data.
    """

    def __init__(
        self,
        owner: Any,
        name: str = "MaliciousInterface",
        target_interface: Optional[Interface] = None,
    ):
        """
        Initialize the malicious interface.

        Args:
            owner: The Reticulum instance
            name: Interface name
            target_interface: Optional real interface to intercept/modify
        """
        super().__init__()

        self.owner = owner
        self.name = name
        self.target_interface = target_interface

        self.online = True
        self.OUT = True
        self.IN = True

        self.bitrate = 1000000  # 1 Mbps virtual

        # Packet capture for analysis
        self.captured_packets: List[bytes] = []
        self.inject_queue: List[bytes] = []

        # Callbacks for packet events
        self.on_packet_captured: Optional[Callable[[bytes], None]] = None
        self.on_packet_injected: Optional[Callable[[bytes], None]] = None

        # Modification rules
        self.corruption_rate = 0.0
        self.replay_mode = False
        self.replay_delay = 0.0

    def process_incoming(self, data: bytes):
        """Process incoming data as if received from network."""
        self.captured_packets.append(data)

        if self.on_packet_captured:
            self.on_packet_captured(data)

        # Pass to Transport for processing
        RNS.Transport.inbound(data, self)

    def process_outgoing(self, data: bytes):
        """Process outgoing data."""
        # Apply corruption if enabled
        if self.corruption_rate > 0 and os.urandom(1)[0] < self.corruption_rate * 255:
            data = self._corrupt_packet(data)

        if self.target_interface:
            self.target_interface.process_outgoing(data)

    def inject_packet(self, data: bytes, delay: float = 0.0):
        """
        Inject a packet into the receive path.

        Args:
            data: Raw packet data to inject
            delay: Delay in seconds before injection
        """
        def do_inject():
            if delay > 0:
                time.sleep(delay)
            self.process_incoming(data)
            if self.on_packet_injected:
                self.on_packet_injected(data)

        if delay > 0:
            thread = threading.Thread(target=do_inject)
            thread.daemon = True
            thread.start()
        else:
            do_inject()

    def inject_malformed_packet(self, malformation_type: str) -> bytes:
        """
        Inject a malformed packet for testing.

        Args:
            malformation_type: Type of malformation:
                - "truncated": Packet cut short
                - "oversized": Packet too large
                - "zero": All zeros
                - "random": Random garbage
                - "invalid_header": Bad header flags
                - "invalid_hash": Corrupted hash

        Returns:
            The malformed packet data
        """
        if malformation_type == "truncated":
            # Very short packet (less than minimum header)
            data = os.urandom(4)

        elif malformation_type == "oversized":
            # Packet larger than MTU
            data = os.urandom(1000)

        elif malformation_type == "zero":
            # All zeros
            data = bytes(100)

        elif malformation_type == "random":
            # Random garbage
            data = os.urandom(200)

        elif malformation_type == "invalid_header":
            # Start with invalid flags
            data = bytes([0xFF, 0xFF]) + os.urandom(50)

        elif malformation_type == "invalid_hash":
            # Valid-looking structure but corrupted hash
            # Packet structure: [flags][hops][dest_hash][context][data]
            data = bytes([0x00, 0x01])  # flags, hops
            data += bytes(16)  # fake destination hash (all zeros)
            data += bytes([0x00])  # context
            data += os.urandom(30)  # payload

        else:
            data = os.urandom(50)

        self.inject_packet(data)
        return data

    def replay_captured(self, index: int = -1, count: int = 1):
        """
        Replay a previously captured packet.

        Args:
            index: Index of packet to replay (-1 for most recent)
            count: Number of times to replay
        """
        if not self.captured_packets:
            return

        packet = self.captured_packets[index]

        for _ in range(count):
            self.inject_packet(packet, delay=self.replay_delay)

    def _corrupt_packet(self, data: bytes) -> bytes:
        """Apply random corruption to packet data."""
        if not data:
            return data

        data_list = list(data)
        # Flip a random bit
        pos = os.urandom(1)[0] % len(data_list)
        data_list[pos] ^= (1 << (os.urandom(1)[0] % 8))

        return bytes(data_list)

    def clear_captures(self):
        """Clear captured packets."""
        self.captured_packets.clear()


def create_malformed_announce(
    destination_hash: Optional[bytes] = None,
    corruption_type: str = "random"
) -> bytes:
    """
    Create a malformed announce packet for testing.

    Args:
        destination_hash: Optional destination hash to include
        corruption_type: Type of corruption to apply

    Returns:
        Malformed announce packet data
    """
    # Basic announce structure attempt
    # This is intentionally malformed

    if corruption_type == "invalid_signature":
        # Valid-looking announce with bad signature
        data = bytes([0x01, 0x00])  # Announce flags
        data += destination_hash or os.urandom(16)
        data += os.urandom(32)  # Bad public key
        data += os.urandom(64)  # Bad signature
        return data

    elif corruption_type == "truncated":
        return os.urandom(8)

    elif corruption_type == "oversized":
        return os.urandom(1000)

    else:
        return os.urandom(100)


def create_malformed_link_request(
    destination_hash: Optional[bytes] = None,
) -> bytes:
    """
    Create a malformed link request for testing.

    Args:
        destination_hash: Optional destination hash

    Returns:
        Malformed link request packet
    """
    # Link request with invalid structure
    data = bytes([0x40, 0x00])  # Link request flags
    data += destination_hash or os.urandom(16)
    data += os.urandom(16)  # Bad link ID
    data += os.urandom(32)  # Bad ephemeral key

    return data
