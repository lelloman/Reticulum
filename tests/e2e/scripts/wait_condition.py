#!/usr/bin/env python3
"""Wait for a condition to be met on this RNS node."""

import sys
import json
import time
import RNS


def run(args: dict) -> dict:
    """
    Wait for a condition to be met.

    Args:
        condition: Type of condition (required)
            - "path": Wait for path to destination
            - "announce": Wait to receive an announce
            - "link": Wait for link to be established
        destination_hash: Hex-encoded destination hash (for path/announce conditions)
        timeout: Timeout in seconds (optional, default 10.0)

    Returns:
        condition_met: True if condition was met within timeout
        Additional fields depending on condition type
    """
    rns = RNS.Reticulum()

    condition = args["condition"]
    timeout = args.get("timeout", 10.0)

    if condition == "path":
        return _wait_for_path(args, timeout)
    elif condition == "announce":
        return _wait_for_announce(args, timeout)
    elif condition == "link":
        return _wait_for_link(args, timeout)
    else:
        return {"error": f"Unknown condition: {condition}"}


def _wait_for_path(args: dict, timeout: float) -> dict:
    """Wait for a path to a destination."""
    dest_hash = bytes.fromhex(args["destination_hash"])

    # Request path if we don't have it
    if not RNS.Transport.has_path(dest_hash):
        RNS.Transport.request_path(dest_hash)

    start = time.time()
    last_request = start
    while not RNS.Transport.has_path(dest_hash):
        if time.time() - start > timeout:
            return {
                "condition_met": False,
                "path_found": False,
                "error": "Timeout waiting for path"
            }
        # Re-request periodically in case the first request was too early
        if time.time() - last_request > 2.0:
            RNS.Transport.request_path(dest_hash)
            last_request = time.time()
        time.sleep(0.1)

    # Get path info
    hops = RNS.Transport.hops_to(dest_hash)

    return {
        "condition_met": True,
        "path_found": True,
        "hops": hops,
        "destination_hash": dest_hash.hex(),
    }


def _wait_for_announce(args: dict, timeout: float) -> dict:
    """Wait to receive an announce from a destination."""
    dest_hash_hex = args.get("destination_hash")

    received_announce = {"received": False, "hash": None, "app_data": None}

    class AnnounceHandler:
        def __init__(self):
            self.aspect_filter = None

        def received_announce(self, destination_hash, announced_identity, app_data):
            if dest_hash_hex is None or destination_hash.hex() == dest_hash_hex:
                received_announce["received"] = True
                received_announce["hash"] = destination_hash.hex()
                if app_data:
                    try:
                        received_announce["app_data"] = app_data.decode("utf-8")
                    except:
                        received_announce["app_data"] = app_data.hex()

    handler = AnnounceHandler()
    RNS.Transport.register_announce_handler(handler)

    start = time.time()
    while not received_announce["received"]:
        if time.time() - start > timeout:
            RNS.Transport.deregister_announce_handler(handler)
            return {
                "condition_met": False,
                "announce_received": False,
                "error": "Timeout waiting for announce"
            }
        time.sleep(0.1)

    RNS.Transport.deregister_announce_handler(handler)

    return {
        "condition_met": True,
        "announce_received": True,
        "destination_hash": received_announce["hash"],
        "app_data": received_announce["app_data"],
    }


def _wait_for_link(args: dict, timeout: float) -> dict:
    """Wait for a link to be established to this node."""
    dest_hash_hex = args.get("destination_hash")

    established_link = {"link": None}

    # Find destination
    dest = None
    if dest_hash_hex:
        dest_hash = bytes.fromhex(dest_hash_hex)
        for d in RNS.Transport.destinations:
            if d.hash == dest_hash:
                dest = d
                break

        if dest is None:
            return {"error": "Destination not found locally"}

    def link_established(link):
        established_link["link"] = link

    if dest:
        dest.set_link_established_callback(link_established)

    start = time.time()
    while established_link["link"] is None:
        if time.time() - start > timeout:
            return {
                "condition_met": False,
                "link_established": False,
                "error": "Timeout waiting for link"
            }
        time.sleep(0.1)

    link = established_link["link"]
    return {
        "condition_met": True,
        "link_established": True,
        "link_id": link.link_id.hex(),
    }


def main():
    args = json.loads(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
    result = run(args)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
