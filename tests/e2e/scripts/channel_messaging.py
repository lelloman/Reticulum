#!/usr/bin/env python3
"""Channel messaging script for E2E tests.

Defines TestMessage/EchoMessage types and sends/receives channel messages
over a link.
"""

import sys
import json
import time
import RNS
import RNS.Channel as Channel


class TestMessage(Channel.MessageBase):
    """Test message type for sending data."""
    MSGTYPE = 0x0001

    def __init__(self):
        self.data = b""

    def pack(self) -> bytes:
        return self.data

    def unpack(self, raw: bytes):
        self.data = raw


class EchoMessage(Channel.MessageBase):
    """Echo reply message type."""
    MSGTYPE = 0x0002

    def __init__(self):
        self.data = b""

    def pack(self) -> bytes:
        return self.data

    def unpack(self, raw: bytes):
        self.data = raw


def run(args: dict) -> dict:
    """
    Send a channel message and optionally wait for reply.

    Args:
        destination_hash: Hex-encoded destination hash
        app_name: Application name
        aspects: List of aspect strings
        data_hex: Hex-encoded data to send as TestMessage
        wait_reply: Whether to wait for EchoMessage reply (default True)
        timeout: Overall timeout in seconds (default 15.0)

    Returns:
        link_id, status, message_sent, reply_received, reply_data_hex
    """
    rns = RNS.Reticulum()

    dest_hash = bytes.fromhex(args["destination_hash"])
    app_name = args["app_name"]
    aspects = args.get("aspects", [])
    if isinstance(aspects, str):
        aspects = [aspects] if aspects else []
    data = bytes.fromhex(args["data_hex"])
    wait_reply = args.get("wait_reply", True)
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
        "message_sent": False,
        "reply_received": False,
        "reply_data_hex": "",
    }

    # Set up channel
    channel = link.get_channel()
    channel.register_message_type(TestMessage)
    channel.register_message_type(EchoMessage)

    # Set up reply capture
    reply_state = {"received": False, "data": b""}

    def reply_handler(message):
        if isinstance(message, EchoMessage):
            reply_state["received"] = True
            reply_state["data"] = message.data

    channel.add_message_handler(reply_handler)

    # Send TestMessage
    msg = TestMessage()
    msg.data = data
    channel.send(msg)
    result["message_sent"] = True

    # Wait for reply
    if wait_reply:
        start = time.time()
        while not reply_state["received"]:
            if time.time() - start > min(timeout, 10.0):
                break
            time.sleep(0.1)

        if reply_state["received"]:
            result["reply_received"] = True
            result["reply_data_hex"] = reply_state["data"].hex()

    time.sleep(0.5)
    return result


def main():
    args = json.loads(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
    result = run(args)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
