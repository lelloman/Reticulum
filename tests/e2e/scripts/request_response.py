#!/usr/bin/env python3
"""Request/Response script for E2E tests.

Sends a link.request() and waits for the response.
"""

import sys
import json
import time
import RNS


def run(args: dict) -> dict:
    """
    Send a request over a link and wait for response.

    Args:
        destination_hash: Hex-encoded destination hash
        app_name: Application name
        aspects: List of aspect strings
        data_hex: Hex-encoded request data
        request_path: Request handler path (default "/echo")
        timeout: Overall timeout in seconds (default 15.0)

    Returns:
        link_id, request_sent, response_received, response_data_hex
    """
    rns = RNS.Reticulum()

    dest_hash = bytes.fromhex(args["destination_hash"])
    app_name = args["app_name"]
    aspects = args.get("aspects", [])
    if isinstance(aspects, str):
        aspects = [aspects] if aspects else []
    data = bytes.fromhex(args["data_hex"])
    request_path = args.get("request_path", "/echo")
    timeout = args.get("timeout", 15.0)

    # Request path
    if not RNS.Transport.has_path(dest_hash):
        RNS.Transport.request_path(dest_hash)
        start = time.time()
        last_request = start
        while not RNS.Transport.has_path(dest_hash):
            if time.time() - start > timeout:
                return {"error": "Path request timeout", "status": "NO_PATH"}
            if time.time() - last_request > 2.0:
                RNS.Transport.request_path(dest_hash)
                last_request = time.time()
            time.sleep(0.1)

    server_identity = RNS.Identity.recall(dest_hash)
    if server_identity is None:
        return {"error": "Could not recall identity", "status": "NO_IDENTITY"}

    server_destination = RNS.Destination(
        server_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        app_name,
        *aspects
    )

    if server_destination.hash != dest_hash:
        return {"error": "Hash mismatch", "status": "HASH_MISMATCH"}

    # Create link
    link = RNS.Link(server_destination)

    start = time.time()
    while link.status != RNS.Link.ACTIVE:
        if link.status == RNS.Link.CLOSED:
            return {"error": "Link closed", "status": "CLOSED"}
        if time.time() - start > timeout:
            link.teardown()
            return {"error": "Link timeout", "status": "TIMEOUT"}
        time.sleep(0.1)

    result = {
        "link_id": link.link_id.hex(),
        "status": "ACTIVE",
        "request_sent": False,
        "response_received": False,
        "response_data_hex": "",
    }

    # Send request
    response_state = {"received": False, "data": None, "failed": False}

    def response_callback(request_receipt):
        response_state["received"] = True
        response_state["data"] = request_receipt.response

    def failed_callback(request_receipt):
        response_state["failed"] = True

    link.request(
        request_path,
        data,
        response_callback=response_callback,
        failed_callback=failed_callback,
        timeout=min(timeout, 10.0),
    )
    result["request_sent"] = True

    # Wait for response
    start = time.time()
    while not response_state["received"] and not response_state["failed"]:
        if time.time() - start > min(timeout, 12.0):
            break
        time.sleep(0.1)

    if response_state["received"] and response_state["data"] is not None:
        result["response_received"] = True
        resp_data = response_state["data"]
        if isinstance(resp_data, bytes):
            result["response_data_hex"] = resp_data.hex()
        else:
            result["response_data_hex"] = str(resp_data).encode().hex()

    if response_state["failed"]:
        result["error"] = "Request failed"

    time.sleep(0.5)
    return result


def main():
    args = json.loads(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
    result = run(args)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
