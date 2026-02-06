#!/usr/bin/env python3
"""
Run a client session that can create links and send data.

This script creates a link to a destination and keeps it alive
to allow sending data through it. Commands are read from stdin.
"""

import sys
import json
import time
import signal
import threading
import RNS

# Active links in this session
active_links = {}
link_lock = threading.Lock()


def run(args: dict):
    """
    Create a link and optionally send data.

    Args:
        destination_hash: Hex-encoded destination hash (required)
        app_name: Application name (required)
        aspects: List of aspect strings (optional)
        timeout: Timeout in seconds (optional, default 15.0)
        data_hex: Optional hex-encoded data to send after link is established
        keep_alive: If True, keep session running for more commands (default False)
    """
    rns = RNS.Reticulum()

    dest_hash = bytes.fromhex(args["destination_hash"])
    app_name = args["app_name"]
    aspects = args.get("aspects", [])
    if isinstance(aspects, str):
        aspects = [aspects] if aspects else []
    timeout = args.get("timeout", 15.0)
    data_hex = args.get("data_hex")
    keep_alive = args.get("keep_alive", False)

    # Request path if needed
    if not RNS.Transport.has_path(dest_hash):
        RNS.Transport.request_path(dest_hash)
        start = time.time()
        while not RNS.Transport.has_path(dest_hash):
            if time.time() - start > timeout:
                print(json.dumps({"error": "Path request timeout", "status": "NO_PATH"}), flush=True)
                return
            time.sleep(0.1)

    # Recall the server identity
    server_identity = RNS.Identity.recall(dest_hash)
    if server_identity is None:
        print(json.dumps({"error": "Could not recall identity", "status": "NO_IDENTITY"}), flush=True)
        return

    # Create destination
    server_destination = RNS.Destination(
        server_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        app_name,
        *aspects
    )

    # Verify hash
    if server_destination.hash != dest_hash:
        print(json.dumps({
            "error": f"Hash mismatch",
            "status": "HASH_MISMATCH",
            "expected": dest_hash.hex(),
            "got": server_destination.hash.hex()
        }), flush=True)
        return

    # Create link
    link = RNS.Link(server_destination)

    # Wait for link
    start = time.time()
    while link.status != RNS.Link.ACTIVE:
        if link.status == RNS.Link.CLOSED:
            reason = "unknown"
            if link.teardown_reason == RNS.Link.TIMEOUT:
                reason = "timeout"
            elif link.teardown_reason == RNS.Link.DESTINATION_CLOSED:
                reason = "destination_closed"
            print(json.dumps({"error": f"Link closed: {reason}", "status": "CLOSED"}), flush=True)
            return
        if time.time() - start > timeout:
            link.teardown()
            print(json.dumps({"error": "Link timeout", "status": "TIMEOUT"}), flush=True)
            return
        time.sleep(0.1)

    link_id = link.link_id.hex()

    # Store link
    with link_lock:
        active_links[link_id] = link

    result = {
        "link_id": link_id,
        "status": "ACTIVE",
        "rtt": link.rtt if link.rtt else 0,
    }

    # Send initial data if provided
    if data_hex:
        data = bytes.fromhex(data_hex)
        send_result = _send_data(link, data, timeout=5.0)
        result["data_sent"] = send_result.get("sent", False)
        result["data_delivered"] = send_result.get("delivered", False)

    print(json.dumps(result), flush=True)

    if not keep_alive:
        # Brief delay to ensure data is sent
        time.sleep(0.5)
        return

    # Keep-alive mode: read commands from stdin
    def signal_handler(sig, frame):
        print(json.dumps({"status": "shutdown"}), flush=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            cmd = json.loads(line.strip())

            if cmd.get("action") == "send":
                data = bytes.fromhex(cmd["data_hex"])
                send_result = _send_data(link, data, timeout=cmd.get("timeout", 5.0))
                print(json.dumps(send_result), flush=True)
            elif cmd.get("action") == "close":
                link.teardown()
                print(json.dumps({"status": "closed"}), flush=True)
                break
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)

        time.sleep(0.1)


def _send_data(link, data: bytes, timeout: float = 5.0) -> dict:
    """Send data over a link."""
    if link.status != RNS.Link.ACTIVE:
        return {"error": f"Link not active", "sent": False}

    packet = RNS.Packet(link, data)
    receipt = packet.send()

    if receipt is None:
        return {"error": "Failed to send", "sent": False}

    result = {"sent": True, "delivered": False}

    if timeout > 0:
        start = time.time()
        while receipt.status == RNS.PacketReceipt.SENT:
            if time.time() - start > timeout:
                break
            time.sleep(0.05)

        if receipt.status == RNS.PacketReceipt.DELIVERED:
            result["delivered"] = True

    return result


def main():
    args = json.loads(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
    run(args)


if __name__ == "__main__":
    main()
