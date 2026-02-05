#!/usr/bin/env python3
"""Create a destination on this RNS node."""

import sys
import json
import time
import RNS


def run(args: dict) -> dict:
    """
    Create a destination on this node.

    Args:
        app_name: Application name (required)
        aspects: List of aspect strings (optional)
        identity_hex: Hex-encoded identity bytes to use (optional)
        announce: Whether to announce the destination (optional, default False)
        app_data: App data to include in announce (optional)
        register_handler: Whether to register a link handler (optional)

    Returns:
        destination_hash: Hex-encoded destination hash
        identity_hex: Hex-encoded identity (for reuse)
    """
    # Initialize RNS (connects to running rnsd)
    rns = RNS.Reticulum()

    # Create or load identity
    if "identity_hex" in args and args["identity_hex"]:
        identity = RNS.Identity.from_bytes(bytes.fromhex(args["identity_hex"]))
    else:
        identity = RNS.Identity()

    # Get aspects
    aspects = args.get("aspects", [])
    if isinstance(aspects, str):
        aspects = [aspects] if aspects else []

    # Create destination
    dest = RNS.Destination(
        identity,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        args["app_name"],
        *aspects
    )

    # Register link handler if requested
    if args.get("register_handler", False):
        dest.set_link_established_callback(_link_established)

    # Optionally announce
    if args.get("announce", False):
        app_data = args.get("app_data")
        if app_data:
            if isinstance(app_data, str):
                app_data = app_data.encode("utf-8")
            dest.announce(app_data=app_data)
        else:
            dest.announce()
        # Brief delay to ensure announce is queued with shared instance
        time.sleep(0.5)

    # Return result
    return {
        "destination_hash": dest.hash.hex(),
        "identity_hex": identity.get_private_key().hex() + identity.get_public_key().hex(),
        "name": dest.name,
    }


def _link_established(link):
    """Callback when a link is established."""
    RNS.log(f"Link established: {link.link_id.hex()}")
    link.set_packet_callback(_packet_received)


def _packet_received(message, packet):
    """Callback when a packet is received on a link."""
    RNS.log(f"Packet received: {len(message)} bytes")


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing arguments"}))
        sys.exit(1)

    args = json.loads(sys.argv[1])
    result = run(args)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
