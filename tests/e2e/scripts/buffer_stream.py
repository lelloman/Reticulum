#!/usr/bin/env python3
"""Buffer/Stream script for E2E tests.

Writes data via Buffer API and optionally reads echo back.
"""

import sys
import json
import time
import RNS
import RNS.Buffer as Buffer


def run(args: dict) -> dict:
    """
    Write data via Buffer and optionally read echo back.

    Args:
        destination_hash: Hex-encoded destination hash
        app_name: Application name
        aspects: List of aspect strings
        data_hex: Hex-encoded data to write
        stream_id: Writer stream ID (reader uses stream_id + 1)
        expect_echo: Whether to read echo back (default True)
        timeout: Overall timeout in seconds (default 15.0)

    Returns:
        link_id, status, bytes_written, bytes_received, received_hex
    """
    rns = RNS.Reticulum()

    dest_hash = bytes.fromhex(args["destination_hash"])
    app_name = args["app_name"]
    aspects = args.get("aspects", [])
    if isinstance(aspects, str):
        aspects = [aspects] if aspects else []
    data = bytes.fromhex(args["data_hex"])
    stream_id = args.get("stream_id", 0)
    expect_echo = args.get("expect_echo", True)
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
        "bytes_written": 0,
        "bytes_received": 0,
        "received_hex": "",
    }

    # Set up channel and buffers
    channel = link.get_channel()

    # Client writes on stream_id, server echoes on stream_id + 1
    writer = Buffer.create_writer(stream_id, channel)

    received_data = bytearray()

    if expect_echo:
        def ready_callback(ready_bytes):
            chunk = reader.read(ready_bytes)
            if chunk:
                received_data.extend(chunk)

        reader = Buffer.create_reader(stream_id + 1, channel, ready_callback)

    # Write data in chunks to respect channel flow control
    chunk_size = 200  # Stay well under MTU
    offset = 0
    while offset < len(data):
        chunk = data[offset:offset + chunk_size]
        writer.write(chunk)
        writer.flush()
        offset += len(chunk)
        result["bytes_written"] = offset
        time.sleep(0.1)  # Small delay for flow control

    # Signal we're done writing
    writer.close()

    # Wait for echo data
    if expect_echo:
        start = time.time()
        while len(received_data) < len(data):
            if time.time() - start > min(timeout, 15.0):
                break
            time.sleep(0.1)

        result["bytes_received"] = len(received_data)
        result["received_hex"] = bytes(received_data).hex()

    time.sleep(0.5)
    return result


def main():
    args = json.loads(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
    result = run(args)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
