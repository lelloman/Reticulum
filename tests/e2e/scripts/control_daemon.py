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
import channel_messaging
import buffer_stream
import request_response

# Persistent state: keep references to prevent GC
_destinations = {}  # hash_hex -> (destination, identity)
_active_links = []
_received_data = []
_link_closed_events = []


def _handle_serve_destination(args):
    """
    Non-blocking version of serve_destination.

    Unlike serve_destination.py which loops forever, this creates the
    destination and returns immediately. The daemon process itself keeps
    everything alive.

    Supports optional modes:
        channel_mode: Set up channel echo server (TestMessage -> EchoMessage)
        buffer_mode: Set up buffer echo server (stream 0 -> stream 1)
        request_handler_mode: Register request handler on destination
        proof_strategy: PROVE_NONE, PROVE_APP, or PROVE_ALL (default)
    """
    aspects = args.get("aspects", [])
    if isinstance(aspects, str):
        aspects = [aspects] if aspects else []

    channel_mode = args.get("channel_mode", False)
    buffer_mode = args.get("buffer_mode", False)
    request_handler_mode = args.get("request_handler_mode", False)
    proof_strategy = args.get("proof_strategy", "PROVE_ALL")

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
        link.set_link_closed_callback(_link_closed)
        link.set_resource_strategy(RNS.Link.ACCEPT_ALL)
        link.set_resource_started_callback(_resource_started)
        link.set_resource_concluded_callback(_resource_concluded)

        if channel_mode:
            _setup_channel_echo(link)
        elif buffer_mode:
            _setup_buffer_echo(link)
        else:
            link.set_packet_callback(_packet_received)

    dest.set_link_established_callback(link_established)

    # Set proof strategy
    if proof_strategy == "PROVE_NONE":
        dest.set_proof_strategy(RNS.Destination.PROVE_NONE)
    elif proof_strategy == "PROVE_APP":
        dest.set_proof_strategy(RNS.Destination.PROVE_APP)
        dest.set_proof_requested_callback(_proof_requested)
    else:
        dest.set_proof_strategy(RNS.Destination.PROVE_ALL)

    # Register request handler if requested
    if request_handler_mode:
        request_path = args.get("request_path", "/echo")

        def request_handler(path, data, request_id, link_id, remote_identity, requested_at):
            _received_data.append({
                "type": "request",
                "path": path,
                "size": len(data) if data else 0,
                "data_hex": data.hex() if data else "",
                "timestamp": time.time(),
            })
            return b"Echo:" + (data if data else b"")

        dest.register_request_handler(
            request_path,
            response_generator=request_handler,
            allow=RNS.Destination.ALLOW_ALL,
        )

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


def _proof_requested(destination, packet):
    """Callback for PROVE_APP strategy."""
    _received_data.append({
        "type": "proof_requested",
        "destination_hash": destination.hash.hex(),
        "timestamp": time.time(),
    })
    return True


def _setup_channel_echo(link):
    """Set up channel echo server on a link: TestMessage -> EchoMessage."""
    import channel_messaging

    channel = link.get_channel()
    channel.register_message_type(channel_messaging.TestMessage)
    channel.register_message_type(channel_messaging.EchoMessage)

    def message_handler(message):
        _received_data.append({
            "type": "channel_message",
            "msg_type": message.MSGTYPE,
            "size": len(message.data) if hasattr(message, "data") else 0,
            "data_hex": message.data.hex() if hasattr(message, "data") else "",
            "timestamp": time.time(),
        })
        # Echo back as EchoMessage
        if isinstance(message, channel_messaging.TestMessage):
            reply = channel_messaging.EchoMessage()
            reply.data = message.data
            channel.send(reply)

    channel.add_message_handler(message_handler)


def _setup_buffer_echo(link):
    """Set up buffer echo server on a link: read stream 0, write stream 1."""
    import RNS.Buffer as Buffer

    channel = link.get_channel()

    def ready_callback(ready_bytes):
        data = reader.read(ready_bytes)
        if data:
            _received_data.append({
                "type": "buffer_data",
                "size": len(data),
                "data_hex": data.hex(),
                "timestamp": time.time(),
            })
            writer.write(data)
            writer.flush()

    reader = Buffer.create_reader(0, channel, ready_callback)
    writer = Buffer.create_writer(1, channel)

    # Store references to prevent GC
    link._buffer_reader = reader
    link._buffer_writer = writer


def _link_closed(link):
    _link_closed_events.append({
        "link_id": link.link_id.hex(),
        "reason": str(link.teardown_reason) if hasattr(link, "teardown_reason") else "unknown",
        "timestamp": time.time(),
    })
    if link in _active_links:
        _active_links.remove(link)


def _packet_received(message, packet):
    _received_data.append({"type": "packet", "size": len(message), "data_hex": message.hex()})


def _resource_started(resource):
    pass


def _resource_concluded(resource):
    if resource.status == RNS.Resource.COMPLETE:
        _received_data.append({"type": "resource", "size": len(resource.data), "data_hex": resource.data.hex()})


def _handle_get_received_data(args):
    """Return received data, optionally filtered by type and/or cleared."""
    data_type = args.get("type")
    clear = args.get("clear", False)
    if data_type:
        result = [d for d in _received_data if d.get("type") == data_type]
    else:
        result = list(_received_data)
    if clear:
        _received_data.clear()
    return result


def _handle_clear_received_data(args):
    """Clear all received data."""
    _received_data.clear()
    return {"cleared": True}


def _handle_get_link_events(args):
    """Return link closed events."""
    return list(_link_closed_events)


def _handle_get_active_links(args):
    """Return active links with their status."""
    result = []
    for link in _active_links:
        result.append({
            "link_id": link.link_id.hex(),
            "status": link.status,
        })
    return result


def _handle_close_link(args):
    """Close a link by link_id hex."""
    link_id_hex = args.get("link_id")
    if not link_id_hex:
        return {"error": "link_id required"}

    link_id = bytes.fromhex(link_id_hex)

    # Search in daemon's tracked links
    for link in _active_links:
        if link.link_id == link_id:
            link.teardown()
            return {"closed": True, "link_id": link_id_hex}

    # Search in Transport's active links
    for link in RNS.Transport.active_links:
        if link.link_id == link_id:
            link.teardown()
            return {"closed": True, "link_id": link_id_hex}

    return {"error": f"Link {link_id_hex} not found", "closed": False}


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
    "channel_messaging": lambda args: channel_messaging.run(args),
    "buffer_stream": lambda args: buffer_stream.run(args),
    "request_response": lambda args: request_response.run(args),
    "get_received_data": _handle_get_received_data,
    "clear_received_data": _handle_clear_received_data,
    "get_link_events": _handle_get_link_events,
    "get_active_links": _handle_get_active_links,
    "close_link": _handle_close_link,
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
