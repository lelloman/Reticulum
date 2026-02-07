#!/usr/bin/env python3
"""Establish a link to a remote destination and optionally send data or resources."""

import sys
import json
import time
import RNS


def run(args: dict) -> dict:
    """
    Create a link to a remote destination.

    Args:
        destination_hash: Hex-encoded destination hash (required)
        app_name: Application name used by the destination (required)
        aspects: List of aspect strings used by the destination (optional)
        timeout: Timeout in seconds (optional, default 10.0)
        data_hex: Optional hex-encoded data to send after link is established
        data_timeout: Timeout for data delivery (optional, default 5.0)
        resource_hex: Optional hex-encoded resource data to send
        resource_timeout: Timeout for resource transfer (optional, default 30.0)
        resource_compress: Whether to compress resource (optional, default True)

    Returns:
        link_id: Hex-encoded link ID if successful
        status: Link status
        data_sent: True if data was sent (if data_hex provided)
        data_delivered: True if delivery confirmed
        resource_sent: True if resource was initiated
        resource_completed: True if resource transfer completed
    """
    rns = RNS.Reticulum()

    dest_hash = bytes.fromhex(args["destination_hash"])
    app_name = args["app_name"]
    aspects = args.get("aspects", [])
    if isinstance(aspects, str):
        aspects = [aspects] if aspects else []
    timeout = args.get("timeout", 10.0)
    data_hex = args.get("data_hex")
    data_timeout = args.get("data_timeout", 5.0)
    resource_hex = args.get("resource_hex")
    resource_timeout = args.get("resource_timeout", 30.0)
    resource_compress = args.get("resource_compress", True)

    # Request path if needed
    if not RNS.Transport.has_path(dest_hash):
        RNS.Transport.request_path(dest_hash)
        # Wait for path, re-requesting periodically
        start = time.time()
        last_request = start
        while not RNS.Transport.has_path(dest_hash):
            if time.time() - start > timeout:
                return {"error": "Path request timeout", "status": "NO_PATH"}
            if time.time() - last_request > 2.0:
                RNS.Transport.request_path(dest_hash)
                last_request = time.time()
            time.sleep(0.1)

    # Recall the server identity from the announce
    server_identity = RNS.Identity.recall(dest_hash)
    if server_identity is None:
        return {"error": "Could not recall identity for destination", "status": "NO_IDENTITY"}

    # Create destination for link with the SAME app_name and aspects
    # that the server uses. This is required because the destination hash
    # is computed from identity + app_name + aspects.
    server_destination = RNS.Destination(
        server_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        app_name,
        *aspects
    )

    # Verify the hash matches what we expected
    if server_destination.hash != dest_hash:
        return {
            "error": f"Hash mismatch: expected {dest_hash.hex()}, got {server_destination.hash.hex()}",
            "status": "HASH_MISMATCH"
        }

    # Create link
    link = RNS.Link(server_destination)

    # Wait for link to become active
    start = time.time()
    while link.status != RNS.Link.ACTIVE:
        if link.status == RNS.Link.CLOSED:
            reason = "unknown"
            if link.teardown_reason == RNS.Link.TIMEOUT:
                reason = "timeout"
            elif link.teardown_reason == RNS.Link.DESTINATION_CLOSED:
                reason = "destination_closed"
            elif link.teardown_reason == RNS.Link.INITIATOR_CLOSED:
                reason = "initiator_closed"
            return {"error": f"Link closed: {reason}", "status": "CLOSED"}
        if time.time() - start > timeout:
            link.teardown()
            return {"error": "Link establishment timeout", "status": "TIMEOUT"}
        time.sleep(0.1)

    result = {
        "link_id": link.link_id.hex(),
        "status": "ACTIVE",
        "rtt": link.rtt if link.rtt else 0,
    }

    # Identify if requested
    if args.get("identify", False):
        local_identity = RNS.Identity()
        link.identify(local_identity)
        time.sleep(0.1)
        result["identification_sent"] = True
        result["local_identity_hash"] = local_identity.hash.hex()

    # Send data if provided
    if data_hex:
        data = bytes.fromhex(data_hex)
        packet = RNS.Packet(link, data)
        receipt = packet.send()

        if receipt is None:
            result["data_sent"] = False
            result["data_error"] = "Failed to send packet"
        else:
            result["data_sent"] = True
            result["data_delivered"] = False

            # Wait for delivery confirmation
            if data_timeout > 0:
                start = time.time()
                while receipt.status == RNS.PacketReceipt.SENT:
                    if time.time() - start > data_timeout:
                        break
                    time.sleep(0.05)

                if receipt.status == RNS.PacketReceipt.DELIVERED:
                    result["data_delivered"] = True

    # Send resource if provided
    if resource_hex:
        # Brief delay to let the server's link_established callback
        # register ACCEPT_ALL and resource_concluded before the advertisement
        # arrives.  On the responder side the callback runs synchronously
        # in the transport thread, but the RTT packet may still be in transit.
        time.sleep(0.5)
        resource_data = bytes.fromhex(resource_hex)

        # Track resource progress
        resource_state = {"progress": 0, "completed": False, "failed": False}

        def progress_callback(resource):
            resource_state["progress"] = resource.get_progress() * 100

        def concluded_callback(resource):
            if resource.status == RNS.Resource.COMPLETE:
                resource_state["completed"] = True
            else:
                resource_state["failed"] = True

        # Create and send resource
        resource = RNS.Resource(
            resource_data,
            link,
            progress_callback=progress_callback,
            callback=concluded_callback,
            auto_compress=resource_compress
        )

        result["resource_sent"] = True
        result["resource_completed"] = False
        result["resource_progress"] = 0

        # Wait for completion
        start = time.time()
        while not resource_state["completed"] and not resource_state["failed"]:
            if time.time() - start > resource_timeout:
                result["resource_error"] = "Resource transfer timeout"
                break
            time.sleep(0.1)

        result["resource_completed"] = resource_state["completed"]
        result["resource_progress"] = resource_state["progress"]

        if resource_state["failed"]:
            result["resource_error"] = "Resource transfer failed"

    return result


def main():
    args = json.loads(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
    result = run(args)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
