"""
ProtocolChecker - Utilities for validating protocol conformance.

Provides helper functions and assertions for checking that packets,
handshakes, and other protocol elements conform to the Reticulum
specification.
"""

import struct
import RNS


class ProtocolChecker:
    """
    Protocol conformance checking utilities.
    """

    # Constants from Reticulum protocol
    TRUNCATED_HASHLENGTH = 128  # bits
    KEYSIZE = 512  # bits (256 encryption + 256 signing)
    SIGLENGTH = 512  # bits
    NAME_HASH_LENGTH = 80  # bits
    MTU = 500  # bytes
    TOKEN_OVERHEAD = 48  # bytes

    # Packet types
    PACKET_DATA = 0x00
    PACKET_ANNOUNCE = 0x01
    PACKET_LINKREQUEST = 0x02
    PACKET_PROOF = 0x03

    # Header types
    HEADER_1 = 0x00
    HEADER_2 = 0x01

    # Destination types
    DEST_SINGLE = 0x00
    DEST_GROUP = 0x01
    DEST_PLAIN = 0x02
    DEST_LINK = 0x03

    # Transport types
    TRANSPORT_BROADCAST = 0x00
    TRANSPORT_TRANSPORT = 0x01

    @staticmethod
    def check_packet_header(raw, expected=None):
        """
        Validate packet header structure.

        :param raw: Raw packet bytes
        :param expected: Optional dict with expected values
        :returns: Dict with parsed header and any validation errors
        """
        result = {
            "valid": True,
            "errors": [],
            "parsed": {}
        }

        if len(raw) < 19:  # Minimum HEADER_1 size
            result["valid"] = False
            result["errors"].append(f"Packet too short: {len(raw)} < 19 bytes")
            return result

        flags = raw[0]
        hops = raw[1]

        parsed = {
            "flags": flags,
            "hops": hops,
            "header_type": (flags & 0b01000000) >> 6,
            "context_flag": (flags & 0b00100000) >> 5,
            "transport_type": (flags & 0b00010000) >> 4,
            "dest_type": (flags & 0b00001100) >> 2,
            "packet_type": (flags & 0b00000011)
        }

        DST_LEN = ProtocolChecker.TRUNCATED_HASHLENGTH // 8

        if parsed["header_type"] == ProtocolChecker.HEADER_1:
            if len(raw) < 2 + DST_LEN + 1:
                result["valid"] = False
                result["errors"].append(f"HEADER_1 packet too short: {len(raw)} bytes")
            else:
                parsed["destination_hash"] = raw[2:2+DST_LEN]
                parsed["context"] = raw[2+DST_LEN]
                parsed["payload"] = raw[2+DST_LEN+1:]
        else:  # HEADER_2
            if len(raw) < 2 + 2*DST_LEN + 1:
                result["valid"] = False
                result["errors"].append(f"HEADER_2 packet too short: {len(raw)} bytes")
            else:
                parsed["transport_id"] = raw[2:2+DST_LEN]
                parsed["destination_hash"] = raw[2+DST_LEN:2+2*DST_LEN]
                parsed["context"] = raw[2+2*DST_LEN]
                parsed["payload"] = raw[2+2*DST_LEN+1:]

        result["parsed"] = parsed

        # Validate against expected values if provided
        if expected:
            for key, exp_val in expected.items():
                if key in parsed:
                    actual = parsed[key]
                    if isinstance(exp_val, bytes) and isinstance(actual, bytes):
                        if actual != exp_val:
                            result["valid"] = False
                            result["errors"].append(
                                f"{key} mismatch: expected {exp_val.hex()}, got {actual.hex()}"
                            )
                    elif actual != exp_val:
                        result["valid"] = False
                        result["errors"].append(
                            f"{key} mismatch: expected {exp_val}, got {actual}"
                        )

        return result

    @staticmethod
    def check_announce_packet(raw):
        """
        Validate announce packet structure.

        Announce format:
        public_key(64) + name_hash(10) + random_hash(10) + [ratchet(32)] + signature(64) + [app_data]

        :param raw: Payload bytes (after header)
        :returns: Dict with parsed announce and validation errors
        """
        result = {
            "valid": True,
            "errors": [],
            "parsed": {}
        }

        keysize = ProtocolChecker.KEYSIZE // 8  # 64 bytes
        name_hash_len = ProtocolChecker.NAME_HASH_LENGTH // 8  # 10 bytes
        sig_len = ProtocolChecker.SIGLENGTH // 8  # 64 bytes
        ratchet_size = 32  # bytes

        min_size = keysize + name_hash_len + 10 + sig_len  # 148 bytes minimum
        if len(raw) < min_size:
            result["valid"] = False
            result["errors"].append(f"Announce too short: {len(raw)} < {min_size} bytes")
            return result

        parsed = {}
        parsed["public_key"] = raw[:keysize]
        parsed["name_hash"] = raw[keysize:keysize+name_hash_len]
        parsed["random_hash"] = raw[keysize+name_hash_len:keysize+name_hash_len+10]

        # Check if there's a ratchet (determined by context_flag in header)
        # For now, we'll try to detect based on size
        remaining = raw[keysize+name_hash_len+10:]

        if len(remaining) >= ratchet_size + sig_len:
            # Might have ratchet
            parsed["has_ratchet"] = True
            parsed["ratchet"] = remaining[:ratchet_size]
            parsed["signature"] = remaining[ratchet_size:ratchet_size+sig_len]
            if len(remaining) > ratchet_size + sig_len:
                parsed["app_data"] = remaining[ratchet_size+sig_len:]
        elif len(remaining) >= sig_len:
            parsed["has_ratchet"] = False
            parsed["signature"] = remaining[:sig_len]
            if len(remaining) > sig_len:
                parsed["app_data"] = remaining[sig_len:]
        else:
            result["valid"] = False
            result["errors"].append(f"Invalid announce: insufficient data for signature")

        result["parsed"] = parsed
        return result

    @staticmethod
    def check_linkrequest_packet(raw):
        """
        Validate LINKREQUEST packet structure.

        LINKREQUEST format:
        X25519_pub(32) + Ed25519_pub(32) + [mtu_signalling(3)]

        :param raw: Payload bytes (after header)
        :returns: Dict with parsed linkrequest and validation errors
        """
        result = {
            "valid": True,
            "errors": [],
            "parsed": {}
        }

        ECPUBSIZE = 64  # 32 + 32
        MTU_SIZE = 3

        if len(raw) != ECPUBSIZE and len(raw) != ECPUBSIZE + MTU_SIZE:
            result["valid"] = False
            result["errors"].append(
                f"Invalid LINKREQUEST size: {len(raw)} (expected {ECPUBSIZE} or {ECPUBSIZE+MTU_SIZE})"
            )
            return result

        parsed = {}
        parsed["x25519_pub"] = raw[:32]
        parsed["ed25519_pub"] = raw[32:64]

        if len(raw) == ECPUBSIZE + MTU_SIZE:
            parsed["has_mtu_signalling"] = True
            mtu_bytes = raw[64:67]
            # MTU is 21 bits, mode is 3 bits in the high byte
            mtu_value = (mtu_bytes[0] << 16) + (mtu_bytes[1] << 8) + mtu_bytes[2]
            parsed["mtu"] = mtu_value & 0x1FFFFF
            parsed["mode"] = (mtu_bytes[0] & 0xE0) >> 5
        else:
            parsed["has_mtu_signalling"] = False

        result["parsed"] = parsed
        return result

    @staticmethod
    def check_lrproof_packet(raw):
        """
        Validate link request proof (LRPROOF) packet structure.

        LRPROOF format:
        signature(64) + X25519_pub(32) + [mtu_signalling(3)]

        :param raw: Payload bytes
        :returns: Dict with parsed proof and validation errors
        """
        result = {
            "valid": True,
            "errors": [],
            "parsed": {}
        }

        SIG_LEN = 64
        PUB_LEN = 32
        MTU_SIZE = 3

        expected_sizes = [SIG_LEN + PUB_LEN, SIG_LEN + PUB_LEN + MTU_SIZE]
        if len(raw) not in expected_sizes:
            result["valid"] = False
            result["errors"].append(
                f"Invalid LRPROOF size: {len(raw)} (expected {expected_sizes})"
            )
            return result

        parsed = {}
        parsed["signature"] = raw[:SIG_LEN]
        parsed["x25519_pub"] = raw[SIG_LEN:SIG_LEN+PUB_LEN]

        if len(raw) == SIG_LEN + PUB_LEN + MTU_SIZE:
            parsed["has_mtu_signalling"] = True
            mtu_bytes = raw[SIG_LEN+PUB_LEN:SIG_LEN+PUB_LEN+MTU_SIZE]
            mtu_value = (mtu_bytes[0] << 16) + (mtu_bytes[1] << 8) + mtu_bytes[2]
            parsed["mtu"] = mtu_value & 0x1FFFFF
            parsed["mode"] = (mtu_bytes[0] & 0xE0) >> 5
        else:
            parsed["has_mtu_signalling"] = False

        result["parsed"] = parsed
        return result

    @staticmethod
    def check_channel_envelope(raw):
        """
        Validate channel envelope structure.

        Envelope format:
        msgtype(2) + sequence(2) + length(2) + data

        :param raw: Raw envelope bytes
        :returns: Dict with parsed envelope and validation errors
        """
        result = {
            "valid": True,
            "errors": [],
            "parsed": {}
        }

        if len(raw) < 6:
            result["valid"] = False
            result["errors"].append(f"Envelope too short: {len(raw)} < 6 bytes")
            return result

        msgtype, sequence, length = struct.unpack(">HHH", raw[:6])

        parsed = {
            "msgtype": msgtype,
            "sequence": sequence,
            "length": length,
            "data": raw[6:]
        }

        if len(parsed["data"]) != length:
            result["valid"] = False
            result["errors"].append(
                f"Data length mismatch: header says {length}, actual is {len(parsed['data'])}"
            )

        result["parsed"] = parsed
        return result

    @staticmethod
    def pack_flags(header_type, context_flag, transport_type, dest_type, packet_type):
        """
        Pack header flags byte.

        :returns: Packed flags byte
        """
        return (
            (header_type << 6) |
            (context_flag << 5) |
            (transport_type << 4) |
            (dest_type << 2) |
            packet_type
        )

    @staticmethod
    def compute_destination_hash(name_hash, identity_hash):
        """
        Compute destination hash from name hash and identity hash.

        destination_hash = truncated_hash(name_hash + identity_hash)

        :param name_hash: Name hash bytes
        :param identity_hash: Identity hash bytes
        :returns: Destination hash bytes
        """
        hash_material = name_hash + identity_hash
        return RNS.Identity.truncated_hash(hash_material)

    @staticmethod
    def compute_link_id(linkrequest_hashable_part):
        """
        Compute link ID from LINKREQUEST hashable part.

        link_id = truncated_hash(linkrequest_hashable_part)

        :param linkrequest_hashable_part: Hashable part of LINKREQUEST packet
        :returns: Link ID bytes
        """
        return RNS.Identity.truncated_hash(linkrequest_hashable_part)
