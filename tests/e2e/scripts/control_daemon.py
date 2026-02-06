#!/usr/bin/env python3
"""
Persistent control daemon for E2E tests.

Initializes RNS once and accepts JSON commands on stdin, dispatching to
existing script run() functions. This eliminates per-operation overhead
of docker exec + Python startup + RNS init.

Protocol:
  - On startup, prints: {"status": "ready"}
  - Reads one JSON line from stdin: {"command": "...", "args": {...}}
  - Writes one JSON line to stdout: {"result": ...} or {"error": "..."}
  - Loops until stdin is closed or "shutdown" command received.
"""

import sys
import json
import time
import signal
import traceback

import RNS

# Import script modules for dispatch
import create_destination
import announce
import create_link
import wait_condition
import run_cli
import network_chaos
import advanced_features
import send_data
import send_resource

# Persistent state: keep references to prevent GC
_destinations = {}  # hash_hex -> (destination, identity)
_active_links = []
_received_data = []


def _handle_serve_destination(args):
    """
    Non-blocking version of serve_destination.

    Unlike serve_destination.py which loops forever, this creates the
    destination and returns immediately. The daemon process itself keeps
    everything alive.
    """
    aspects = args.get("aspects", [])
    if isinstance(aspects, str):
        aspects = [aspects] if aspects else []

    identity = RNS.Identity()

    dest = RNS.Destination(
        identity,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        args["app_name"],
        *aspects
    )

    # Set up link handler
    def link_established(link):
        _active_links.append(link)
        link.set_packet_callback(_packet_received)
        link.set_link_closed_callback(_link_closed)
        link.set_resource_strategy(RNS.Link.ACCEPT_ALL)
        link.set_resource_started_callback(_resource_started)
        link.set_resource_concluded_callback(_resource_concluded)

    dest.set_link_established_callback(link_established)
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

    # Store reference to prevent GC
    hash_hex = dest.hash.hex()
    _destinations[hash_hex] = (dest, identity)

    return {
        "destination_hash": hash_hex,
        "identity_hex": identity.get_private_key().hex() + identity.get_public_key().hex(),
        "name": dest.name,
        "status": "running",
    }


def _link_closed(link):
    if link in _active_links:
        _active_links.remove(link)


def _packet_received(message, packet):
    _received_data.append({"type": "packet", "size": len(message), "data_hex": message.hex()})


def _resource_started(resource):
    pass


def _resource_concluded(resource):
    if resource.status == RNS.Resource.COMPLETE:
        _received_data.append({"type": "resource", "size": len(resource.data), "data_hex": resource.data.hex()})


# Command dispatch table
COMMANDS = {
    "create_destination": lambda args: create_destination.run(args),
    "serve_destination": _handle_serve_destination,
    "announce": lambda args: announce.run(args),
    "create_link": lambda args: create_link.run(args),
    "wait_condition": lambda args: wait_condition.run(args),
    "run_cli": lambda args: run_cli.run(args),
    "network_chaos": lambda args: network_chaos.run(args),
    "advanced_features": lambda args: advanced_features.run(args),
    "send_data": lambda args: send_data.run(args),
    "send_resource": lambda args: send_resource.run(args),
}


def _patch_reticulum_reinit():
    """
    Patch RNS.Reticulum so subsequent calls from script run() functions
    don't raise OSError("Attempt to reinitialise Reticulum").

    RNS enforces a single-instance pattern. Since the daemon already
    initialized RNS, we make the constructor a no-op for future calls.
    """
    RNS.Reticulum.__init__ = lambda self, *a, **kw: None


def main():
    # Initialize RNS once
    rns = RNS.Reticulum()

    # Patch so script run() functions don't crash on RNS.Reticulum()
    _patch_reticulum_reinit()

    # Signal readiness
    print(json.dumps({"status": "ready"}), flush=True)

    # Ignore SIGTERM/SIGINT gracefully - let stdin closing drive shutdown
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid JSON: {e}"}), flush=True)
            continue

        command = request.get("command")
        args = request.get("args", {})

        if command == "shutdown":
            print(json.dumps({"status": "shutdown"}), flush=True)
            break

        handler = COMMANDS.get(command)
        if handler is None:
            print(json.dumps({"error": f"Unknown command: {command}"}), flush=True)
            continue

        try:
            result = handler(args)
            print(json.dumps({"result": result}), flush=True)
        except Exception as e:
            print(json.dumps({
                "error": str(e),
                "traceback": traceback.format_exc(),
            }), flush=True)


if __name__ == "__main__":
    main()
