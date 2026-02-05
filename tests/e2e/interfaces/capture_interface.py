"""
TestCaptureInterface - Wire-level packet capture interface for E2E testing.

This interface captures all packets at the wire level for protocol verification.
It can be used to validate that packets are correctly encoded/decoded according
to the Reticulum protocol specification.
"""

import time
import threading
import RNS
from RNS.Interfaces.Interface import Interface


class TestCaptureInterface(Interface):
    """
    A test interface that captures all packets for verification.

    This interface intercepts packets at the wire level, allowing tests to
    verify exact byte sequences match the protocol specification.
    """

    IN  = True
    OUT = True

    def __init__(self, owner, name="TestCaptureInterface"):
        super().__init__()
        self.owner = owner
        self.name = name
        self.online = True
        self.bitrate = 1000000000  # 1 Gbps virtual interface

        # Capture storage
        self.outgoing_packets = []
        self.incoming_packets = []
        self._lock = threading.Lock()

        # Statistics
        self.packets_sent = 0
        self.packets_received = 0

    def process_outgoing(self, raw):
        """
        Called when a packet is about to be transmitted.
        Captures the raw bytes and metadata before transmission.
        """
        with self._lock:
            metadata = self._extract_metadata(raw)
            capture_entry = {
                "timestamp": time.time(),
                "raw": raw,
                "length": len(raw),
                "metadata": metadata
            }
            self.outgoing_packets.append(capture_entry)
            self.packets_sent += 1
            self.txb += len(raw)

    def process_incoming(self, raw):
        """
        Called when a packet is received.
        Captures the raw bytes and metadata, then forwards to the owner.
        """
        with self._lock:
            metadata = self._extract_metadata(raw)
            capture_entry = {
                "timestamp": time.time(),
                "raw": raw,
                "length": len(raw),
                "metadata": metadata
            }
            self.incoming_packets.append(capture_entry)
            self.packets_received += 1
            self.rxb += len(raw)

        # Forward to transport layer
        RNS.Transport.inbound(raw, self)

    def inject_packet(self, raw):
        """
        Inject a packet as if it was received from the network.
        Useful for testing packet parsing and handling.

        :param raw: Raw packet bytes to inject
        """
        self.process_incoming(raw)

    def send_raw(self, raw):
        """
        Send raw bytes through this interface, capturing them.

        :param raw: Raw bytes to send
        """
        self.process_outgoing(raw)

    def _extract_metadata(self, raw):
        """
        Extract protocol metadata from raw packet bytes.

        Parses the packet header to extract:
        - flags (header_type, context_flag, transport_type, dest_type, packet_type)
        - hops
        - destination_hash
        - transport_id (for HEADER_2)
        - context

        :param raw: Raw packet bytes
        :returns: Dictionary with extracted metadata
        """
        if len(raw) < 3:
            return {"error": "Packet too short"}

        metadata = {}

        try:
            flags = raw[0]
            hops = raw[1]

            # Parse flags byte
            # Bit layout: HH_CF_TT_DD_PP
            # HH = header_type (bits 6-7)
            # CF = context_flag (bit 5)
            # TT = transport_type (bit 4)
            # DD = dest_type (bits 2-3)
            # PP = packet_type (bits 0-1)
            metadata["flags"] = flags
            metadata["header_type"] = (flags & 0b01000000) >> 6
            metadata["context_flag"] = (flags & 0b00100000) >> 5
            metadata["transport_type"] = (flags & 0b00010000) >> 4
            metadata["dest_type"] = (flags & 0b00001100) >> 2
            metadata["packet_type"] = (flags & 0b00000011)
            metadata["hops"] = hops

            # Truncated hash length in bytes (128 bits = 16 bytes)
            DST_LEN = RNS.Reticulum.TRUNCATED_HASHLENGTH // 8

            if metadata["header_type"] == 0:  # HEADER_1
                if len(raw) >= 2 + DST_LEN + 1:
                    metadata["destination_hash"] = raw[2:2+DST_LEN]
                    metadata["context"] = raw[2+DST_LEN]
                    metadata["payload_start"] = 2 + DST_LEN + 1
                    if len(raw) > metadata["payload_start"]:
                        metadata["payload_length"] = len(raw) - metadata["payload_start"]
            else:  # HEADER_2
                if len(raw) >= 2 + 2*DST_LEN + 1:
                    metadata["transport_id"] = raw[2:2+DST_LEN]
                    metadata["destination_hash"] = raw[2+DST_LEN:2+2*DST_LEN]
                    metadata["context"] = raw[2+2*DST_LEN]
                    metadata["payload_start"] = 2 + 2*DST_LEN + 1
                    if len(raw) > metadata["payload_start"]:
                        metadata["payload_length"] = len(raw) - metadata["payload_start"]

            # Add human-readable type names
            metadata["packet_type_name"] = self._packet_type_name(metadata["packet_type"])
            metadata["dest_type_name"] = self._dest_type_name(metadata["dest_type"])
            metadata["context_name"] = self._context_name(metadata.get("context"))

        except Exception as e:
            metadata["error"] = str(e)

        return metadata

    def _packet_type_name(self, packet_type):
        """Get human-readable packet type name."""
        names = {
            0x00: "DATA",
            0x01: "ANNOUNCE",
            0x02: "LINKREQUEST",
            0x03: "PROOF"
        }
        return names.get(packet_type, f"UNKNOWN({packet_type})")

    def _dest_type_name(self, dest_type):
        """Get human-readable destination type name."""
        names = {
            0x00: "SINGLE",
            0x01: "GROUP",
            0x02: "PLAIN",
            0x03: "LINK"
        }
        return names.get(dest_type, f"UNKNOWN({dest_type})")

    def _context_name(self, context):
        """Get human-readable context name."""
        if context is None:
            return None
        names = {
            0x00: "NONE",
            0x01: "RESOURCE",
            0x02: "RESOURCE_ADV",
            0x03: "RESOURCE_REQ",
            0x04: "RESOURCE_HMU",
            0x05: "RESOURCE_PRF",
            0x06: "RESOURCE_ICL",
            0x07: "RESOURCE_RCL",
            0x08: "CACHE_REQUEST",
            0x09: "REQUEST",
            0x0A: "RESPONSE",
            0x0B: "PATH_RESPONSE",
            0x0C: "COMMAND",
            0x0D: "COMMAND_STATUS",
            0x0E: "CHANNEL",
            0xFA: "KEEPALIVE",
            0xFB: "LINKIDENTIFY",
            0xFC: "LINKCLOSE",
            0xFD: "LINKPROOF",
            0xFE: "LRRTT",
            0xFF: "LRPROOF"
        }
        return names.get(context, f"UNKNOWN({context})")

    def get_capture_log(self):
        """
        Get the complete capture log as a JSON-serializable structure.

        :returns: Dictionary with outgoing and incoming packet captures
        """
        with self._lock:
            return {
                "outgoing": [
                    {
                        "timestamp": p["timestamp"],
                        "raw_hex": p["raw"].hex(),
                        "length": p["length"],
                        "metadata": self._serialize_metadata(p["metadata"])
                    }
                    for p in self.outgoing_packets
                ],
                "incoming": [
                    {
                        "timestamp": p["timestamp"],
                        "raw_hex": p["raw"].hex(),
                        "length": p["length"],
                        "metadata": self._serialize_metadata(p["metadata"])
                    }
                    for p in self.incoming_packets
                ],
                "statistics": {
                    "packets_sent": self.packets_sent,
                    "packets_received": self.packets_received,
                    "bytes_sent": self.txb,
                    "bytes_received": self.rxb
                }
            }

    def _serialize_metadata(self, metadata):
        """
        Convert metadata to JSON-serializable format.
        Converts bytes to hex strings.
        """
        result = {}
        for key, value in metadata.items():
            if isinstance(value, bytes):
                result[key] = value.hex()
            else:
                result[key] = value
        return result

    def clear_captures(self):
        """Clear all captured packets."""
        with self._lock:
            self.outgoing_packets = []
            self.incoming_packets = []

    def get_last_outgoing(self, n=1):
        """
        Get the last N outgoing packets.

        :param n: Number of packets to return
        :returns: List of capture entries
        """
        with self._lock:
            return self.outgoing_packets[-n:] if n <= len(self.outgoing_packets) else self.outgoing_packets[:]

    def get_last_incoming(self, n=1):
        """
        Get the last N incoming packets.

        :param n: Number of packets to return
        :returns: List of capture entries
        """
        with self._lock:
            return self.incoming_packets[-n:] if n <= len(self.incoming_packets) else self.incoming_packets[:]

    def find_packets_by_type(self, packet_type, direction="both"):
        """
        Find all packets of a specific type.

        :param packet_type: Packet type constant (DATA, ANNOUNCE, LINKREQUEST, PROOF)
        :param direction: "outgoing", "incoming", or "both"
        :returns: List of matching capture entries
        """
        results = []
        with self._lock:
            if direction in ("outgoing", "both"):
                for p in self.outgoing_packets:
                    if p["metadata"].get("packet_type") == packet_type:
                        results.append(("outgoing", p))
            if direction in ("incoming", "both"):
                for p in self.incoming_packets:
                    if p["metadata"].get("packet_type") == packet_type:
                        results.append(("incoming", p))
        return results

    def find_packets_by_context(self, context, direction="both"):
        """
        Find all packets with a specific context.

        :param context: Context constant
        :param direction: "outgoing", "incoming", or "both"
        :returns: List of matching capture entries
        """
        results = []
        with self._lock:
            if direction in ("outgoing", "both"):
                for p in self.outgoing_packets:
                    if p["metadata"].get("context") == context:
                        results.append(("outgoing", p))
            if direction in ("incoming", "both"):
                for p in self.incoming_packets:
                    if p["metadata"].get("context") == context:
                        results.append(("incoming", p))
        return results

    def wait_for_packets(self, count, direction="outgoing", timeout=5.0):
        """
        Wait for a specific number of packets to be captured.

        :param count: Number of packets to wait for
        :param direction: "outgoing" or "incoming"
        :param timeout: Maximum time to wait in seconds
        :returns: True if count reached, False if timeout
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self._lock:
                current = len(self.outgoing_packets) if direction == "outgoing" else len(self.incoming_packets)
                if current >= count:
                    return True
            time.sleep(0.01)
        return False

    def __str__(self):
        return f"TestCaptureInterface[{self.name}]"
