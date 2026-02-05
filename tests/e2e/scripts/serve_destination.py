#!/usr/bin/env python3
"""
Run a destination server that stays alive and accepts links.

This script creates a destination and keeps it alive to accept incoming links.
Output is JSON containing the destination info. The script runs until killed.
"""

import sys
import json
import time
import signal
import RNS

# Storage for received data
received_data = []
active_links = []


def run(args: dict):
    """
    Create a destination and keep it alive to accept links.

    Args:
        app_name: Application name (required)
        aspects: List of aspect strings (optional)
        announce: Whether to announce the destination (optional, default True)
        app_data: App data to include in announce (optional)
    """
    # Initialize RNS (connects to running rnsd)
    rns = RNS.Reticulum()

    # Create identity
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

    # Set up link handler
    dest.set_link_established_callback(link_established)

    # Accept all resources
    dest.set_proof_strategy(RNS.Destination.PROVE_ALL)

    # Announce if requested (default True)
    if args.get("announce", True):
        app_data = args.get("app_data")
        if app_data:
            if isinstance(app_data, str):
                app_data = app_data.encode("utf-8")
            dest.announce(app_data=app_data)
        else:
            dest.announce()
        time.sleep(0.5)  # Ensure announce is queued

    # Output destination info
    result = {
        "destination_hash": dest.hash.hex(),
        "identity_hex": identity.get_private_key().hex() + identity.get_public_key().hex(),
        "name": dest.name,
        "status": "running"
    }
    print(json.dumps(result), flush=True)

    # Set up signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print(json.dumps({"status": "shutdown", "links": len(active_links), "received": len(received_data)}), flush=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Keep running and handle events
    while True:
        time.sleep(1)


def link_established(link):
    """Callback when a link is established."""
    active_links.append(link)
    link.set_packet_callback(packet_received)
    link.set_link_closed_callback(link_closed)
    link.set_resource_strategy(RNS.Link.ACCEPT_ALL)
    link.set_resource_started_callback(resource_started)
    link.set_resource_concluded_callback(resource_concluded)


def link_closed(link):
    """Callback when a link is closed."""
    if link in active_links:
        active_links.remove(link)


def packet_received(message, packet):
    """Callback when a packet is received on a link."""
    received_data.append({"type": "packet", "size": len(message), "data_hex": message.hex()})


def resource_started(resource):
    """Callback when a resource transfer starts."""
    pass


def resource_concluded(resource):
    """Callback when a resource transfer completes."""
    if resource.status == RNS.Resource.COMPLETE:
        received_data.append({"type": "resource", "size": len(resource.data), "data_hex": resource.data.hex()})


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing arguments"}))
        sys.exit(1)

    args = json.loads(sys.argv[1])
    run(args)


if __name__ == "__main__":
    main()
