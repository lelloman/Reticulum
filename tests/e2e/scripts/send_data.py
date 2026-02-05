#!/usr/bin/env python3
"""Send data over an established link."""

import sys
import json
import time
import RNS


def run(args: dict) -> dict:
    """
    Send data over an established link.

    Args:
        link_id: Hex-encoded link ID (required)
        data_hex: Hex-encoded data to send (required)
        timeout: Timeout in seconds for delivery proof (optional, default 5.0)

    Returns:
        sent: True if packet was sent
        delivered: True if delivery was confirmed (if timeout > 0)
    """
    rns = RNS.Reticulum()

    link_id = bytes.fromhex(args["link_id"])
    data = bytes.fromhex(args["data_hex"])
    timeout = args.get("timeout", 5.0)

    # Find the link
    link = None
    for pending_link in RNS.Transport.pending_links:
        if pending_link.link_id == link_id:
            link = pending_link
            break

    for active_link in RNS.Transport.active_links:
        if active_link.link_id == link_id:
            link = active_link
            break

    if link is None:
        return {"error": "Link not found", "sent": False}

    if link.status != RNS.Link.ACTIVE:
        return {"error": f"Link not active (status: {link.status})", "sent": False}

    # Send packet
    packet = RNS.Packet(link, data)
    receipt = packet.send()

    if receipt is None:
        return {"error": "Failed to send packet", "sent": False}

    result = {"sent": True, "delivered": False}

    # Wait for delivery confirmation if timeout > 0
    if timeout > 0:
        start = time.time()
        while receipt.status == RNS.PacketReceipt.SENT:
            if time.time() - start > timeout:
                break
            time.sleep(0.05)

        if receipt.status == RNS.PacketReceipt.DELIVERED:
            result["delivered"] = True
            result["delivery_time"] = receipt.concluded_at - receipt.sent_at if receipt.concluded_at else 0

    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing arguments"}))
        sys.exit(1)

    args = json.loads(sys.argv[1])
    result = run(args)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
