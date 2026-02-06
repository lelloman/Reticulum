#!/usr/bin/env python3
"""Send an announce for a destination."""

import sys
import json
import RNS


def run(args: dict) -> dict:
    """
    Announce a destination.

    Args:
        destination_hash: Hex-encoded destination hash (required)
        app_data: Optional app data to include

    Returns:
        announced: True if successful
    """
    rns = RNS.Reticulum()

    dest_hash = bytes.fromhex(args["destination_hash"])

    # Find destination in local destinations
    dest = None
    for d in RNS.Transport.destinations:
        if d.hash == dest_hash:
            dest = d
            break

    if dest is None:
        return {"error": "Destination not found locally"}

    # Send announce
    app_data = args.get("app_data")
    if app_data:
        if isinstance(app_data, str):
            app_data = app_data.encode("utf-8")
        dest.announce(app_data=app_data)
    else:
        dest.announce()

    return {
        "announced": True,
        "destination_hash": dest.hash.hex(),
    }


def main():
    args = json.loads(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
    result = run(args)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
