#!/usr/bin/env python3
"""Control script for advanced RNS features testing."""

import sys
import json
import time
import RNS


def test_ratchets(args: dict) -> dict:
    """
    Test ratchet functionality.

    Args:
        app_name: Application name
        aspects: List of aspect strings
        timeout: Test timeout

    Returns:
        dict with ratchet test results
    """
    import os
    import tempfile

    rns = RNS.Reticulum()

    app_name = args["app_name"]
    aspects = args.get("aspects", [])

    # Create identity
    identity = RNS.Identity()

    # Create destination
    destination = RNS.Destination(
        identity,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        app_name,
        *aspects
    )

    # Enable ratchets with a temporary file path
    ratchets_path = os.path.join(tempfile.gettempdir(), f"ratchets_{destination.hash.hex()}")

    try:
        destination.enable_ratchets(ratchets_path)
        ratchets_enabled = True
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to enable ratchets: {e}",
            "ratchets_enabled": False,
        }

    # Get current ratchet ID if available
    ratchet_id = RNS.Identity.current_ratchet_id(destination.hash)

    return {
        "success": True,
        "destination_hash": destination.hash.hex(),
        "ratchets_enabled": ratchets_enabled,
        "ratchet_id": ratchet_id.hex() if ratchet_id else None,
        "ratchets_path": ratchets_path,
    }


def test_request_handler(args: dict) -> dict:
    """
    Test request/response pattern.

    Args:
        app_name: Application name
        aspects: List of aspect strings
        serve: Whether to run as server

    Returns:
        dict with request handler test results
    """
    rns = RNS.Reticulum()

    app_name = args["app_name"]
    aspects = args.get("aspects", [])

    identity = RNS.Identity()

    destination = RNS.Destination(
        identity,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        app_name,
        *aspects
    )

    # Register a request handler
    request_received = {"count": 0, "data": None}

    def request_handler(path, data, request_id, link_id, remote_identity, requested_at):
        request_received["count"] += 1
        request_received["data"] = data
        return b"Response: " + data

    destination.register_request_handler(
        "/test",
        response_generator=request_handler,
        allow=RNS.Destination.ALLOW_ALL,
    )

    destination.announce()

    return {
        "success": True,
        "destination_hash": destination.hash.hex(),
        "identity_hex": identity.get_private_key().hex(),
        "request_handler_registered": True,
    }


def test_proof_strategy(args: dict) -> dict:
    """
    Test different proof strategies.

    Args:
        app_name: Application name
        aspects: List of aspect strings
        strategy: PROVE_NONE, PROVE_APP, PROVE_ALL

    Returns:
        dict with proof strategy results
    """
    rns = RNS.Reticulum()

    app_name = args["app_name"]
    aspects = args.get("aspects", [])
    strategy = args.get("strategy", "PROVE_ALL")

    identity = RNS.Identity()

    destination = RNS.Destination(
        identity,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        app_name,
        *aspects
    )

    # Set proof strategy
    if strategy == "PROVE_NONE":
        destination.set_proof_strategy(RNS.Destination.PROVE_NONE)
    elif strategy == "PROVE_APP":
        destination.set_proof_strategy(RNS.Destination.PROVE_APP)
    else:
        destination.set_proof_strategy(RNS.Destination.PROVE_ALL)

    return {
        "success": True,
        "destination_hash": destination.hash.hex(),
        "proof_strategy": strategy,
    }


def test_group_destination(args: dict) -> dict:
    """
    Test GROUP destination type.

    Args:
        app_name: Application name
        aspects: List of aspect strings
        group_key_hex: Optional pre-shared key

    Returns:
        dict with group destination results
    """
    rns = RNS.Reticulum()

    app_name = args["app_name"]
    aspects = args.get("aspects", [])

    # Create a GROUP destination (pre-shared key)
    destination = RNS.Destination(
        None,  # No identity for GROUP
        RNS.Destination.IN,
        RNS.Destination.GROUP,
        app_name,
        *aspects
    )

    return {
        "success": True,
        "destination_hash": destination.hash.hex(),
        "type": "GROUP",
    }


def test_link_identification(args: dict) -> dict:
    """
    Test link identification functionality.

    Args:
        destination_hash: Hex-encoded destination hash
        app_name: Application name
        aspects: List of aspect strings
        timeout: Link timeout

    Returns:
        dict with link identification results
    """
    rns = RNS.Reticulum()

    dest_hash = bytes.fromhex(args["destination_hash"])
    app_name = args["app_name"]
    aspects = args.get("aspects", [])
    timeout = args.get("timeout", 15.0)

    # Request path
    if not RNS.Transport.has_path(dest_hash):
        RNS.Transport.request_path(dest_hash)
        start = time.time()
        while not RNS.Transport.has_path(dest_hash):
            if time.time() - start > timeout:
                return {"error": "Path timeout", "success": False}
            time.sleep(0.1)

    # Recall identity
    server_identity = RNS.Identity.recall(dest_hash)
    if server_identity is None:
        return {"error": "Could not recall identity", "success": False}

    # Create outgoing destination
    server_destination = RNS.Destination(
        server_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        app_name,
        *aspects
    )

    # Create link
    link = RNS.Link(server_destination)

    # Wait for active
    start = time.time()
    while link.status != RNS.Link.ACTIVE:
        if link.status == RNS.Link.CLOSED:
            return {"error": "Link closed", "success": False}
        if time.time() - start > timeout:
            return {"error": "Link timeout", "success": False}
        time.sleep(0.1)

    # Create an identity for identification
    local_identity = RNS.Identity()

    # State tracking
    identification_result = {"identified": False, "identity_hash": None}

    def identification_callback(link, identity):
        identification_result["identified"] = True
        identification_result["identity_hash"] = identity.hash.hex() if identity else None

    link.set_remote_identified_callback(identification_callback)

    # Identify with our local identity
    link.identify(local_identity)

    # Wait for identification
    time.sleep(1.0)

    return {
        "success": True,
        "link_id": link.link_id.hex(),
        "local_identity_hash": local_identity.hash.hex(),
        "identification_sent": True,
    }


def run(args: dict) -> dict:
    """
    Execute an advanced feature test.

    Args:
        operation: Test operation to run
        Additional args depend on operation
    """
    operation = args.get("operation")

    if operation == "ratchets":
        return test_ratchets(args)
    elif operation == "request_handler":
        return test_request_handler(args)
    elif operation == "proof_strategy":
        return test_proof_strategy(args)
    elif operation == "group_destination":
        return test_group_destination(args)
    elif operation == "link_identification":
        return test_link_identification(args)
    else:
        return {"error": f"Unknown operation: {operation}", "success": False}


def main():
    args = json.loads(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
    result = run(args)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
