#!/usr/bin/env python3
"""Send a resource over an established link."""

import sys
import json
import time
import RNS


# Global to track resource progress
_resource_progress = {}


def run(args: dict) -> dict:
    """
    Send a resource over an established link.

    Args:
        link_id: Hex-encoded link ID (required)
        data_hex: Hex-encoded data to send (required)
        timeout: Timeout in seconds (optional, default 30.0)
        compress: Whether to compress (optional, default True)

    Returns:
        sent: True if resource was initiated
        completed: True if transfer completed
        progress: Final progress percentage
    """
    rns = RNS.Reticulum()

    link_id = bytes.fromhex(args["link_id"])
    data = bytes.fromhex(args["data_hex"])
    timeout = args.get("timeout", 30.0)
    compress = args.get("compress", True)

    # Find the link
    link = None
    for active_link in RNS.Transport.active_links:
        if active_link.link_id == link_id:
            link = active_link
            break

    if link is None:
        return {"error": "Link not found", "sent": False}

    if link.status != RNS.Link.ACTIVE:
        return {"error": f"Link not active (status: {link.status})", "sent": False}

    # Track progress
    resource_id = link_id.hex()
    _resource_progress[resource_id] = {"progress": 0, "completed": False, "failed": False}

    def progress_callback(resource):
        _resource_progress[resource_id]["progress"] = resource.get_progress() * 100

    def concluded_callback(resource):
        if resource.status == RNS.Resource.COMPLETE:
            _resource_progress[resource_id]["completed"] = True
        else:
            _resource_progress[resource_id]["failed"] = True

    # Create and send resource
    resource = RNS.Resource(
        data,
        link,
        progress_callback=progress_callback,
        callback=concluded_callback,
        compress=compress
    )

    result = {"sent": True, "completed": False, "progress": 0}

    # Wait for completion
    start = time.time()
    while not _resource_progress[resource_id]["completed"] and not _resource_progress[resource_id]["failed"]:
        if time.time() - start > timeout:
            result["error"] = "Resource transfer timeout"
            break
        time.sleep(0.1)

    result["completed"] = _resource_progress[resource_id]["completed"]
    result["progress"] = _resource_progress[resource_id]["progress"]

    if _resource_progress[resource_id]["failed"]:
        result["error"] = "Resource transfer failed"

    # Cleanup
    del _resource_progress[resource_id]

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
