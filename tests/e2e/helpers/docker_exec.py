"""Execute Python scripts inside RNS containers via docker exec."""

import subprocess
import json
import os
import time
from typing import Optional


def exec_on_node(container: str, script: str, args: dict, timeout: int = 30) -> dict:
    """
    Execute a control script on an RNS node container.

    Args:
        container: Container name (e.g., "rns-node-a")
        script: Script name (e.g., "create_destination")
        args: Arguments to pass as JSON
        timeout: Command timeout in seconds

    Returns:
        JSON result from script

    Raises:
        RuntimeError: If script execution fails
    """
    cmd = [
        "docker", "exec", container,
        "python", f"/app/scripts/{script}.py",
        json.dumps(args)
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )

    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else "Unknown error"
        # Try to parse JSON error from stdout
        if result.stdout:
            try:
                error_data = json.loads(result.stdout)
                if "error" in error_data:
                    error_msg = error_data["error"]
            except json.JSONDecodeError:
                pass
        raise RuntimeError(f"Script {script} failed on {container}: {error_msg}")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response from {script}: {result.stdout[:200]}")


class NodeInterface:
    """High-level interface to control an RNS node."""

    def __init__(self, container: str):
        """
        Initialize node interface.

        Args:
            container: Docker container name (e.g., "rns-node-a")
        """
        self.container = container

    def create_destination(
        self,
        app_name: str,
        aspects: Optional[list] = None,
        identity_hex: Optional[str] = None,
        announce: bool = False,
        app_data: Optional[str] = None,
        register_handler: bool = False,
    ) -> dict:
        """
        Create a destination on this node.

        Note: This creates a short-lived destination that won't accept links.
        Use start_destination_server() if you need to accept incoming links.

        Args:
            app_name: Application name
            aspects: List of aspect strings
            identity_hex: Hex-encoded identity to reuse
            announce: Whether to announce the destination
            app_data: App data to include in announce
            register_handler: Whether to register a link handler

        Returns:
            dict with destination_hash, identity_hex, name
        """
        return exec_on_node(self.container, "create_destination", {
            "app_name": app_name,
            "aspects": aspects or [],
            "identity_hex": identity_hex,
            "announce": announce,
            "app_data": app_data,
            "register_handler": register_handler,
        })

    def start_destination_server(
        self,
        app_name: str,
        aspects: Optional[list] = None,
        announce: bool = True,
        app_data: Optional[str] = None,
    ) -> dict:
        """
        Start a destination server that accepts incoming links.

        This starts a background process that keeps the destination alive.
        The process runs until the container is stopped or killed.

        Args:
            app_name: Application name
            aspects: List of aspect strings
            announce: Whether to announce the destination (default True)
            app_data: App data to include in announce

        Returns:
            dict with destination_hash, identity_hex, name
        """
        args = {
            "app_name": app_name,
            "aspects": aspects or [],
            "announce": announce,
            "app_data": app_data,
        }

        # Use bash -c with background execution
        # The server prints JSON to stdout before going into its loop
        args_json = json.dumps(args).replace('"', '\\"')
        cmd = [
            "docker", "exec", self.container,
            "bash", "-c",
            f'python /app/scripts/serve_destination.py "{args_json}" &'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        # The output should contain the JSON with destination info
        output = result.stdout.strip()

        # Wait a moment to ensure the server is running and announce propagates
        time.sleep(1.0)

        try:
            # Find the JSON line in output
            for line in output.split('\n'):
                line = line.strip()
                if line.startswith('{'):
                    return json.loads(line)
            raise ValueError(f"No JSON found in output: {output}")
        except (json.JSONDecodeError, ValueError) as e:
            raise RuntimeError(f"Failed to parse destination server output: {output[:200]}. Error: {e}")

    def announce(
        self,
        destination_hash: str,
        app_data: Optional[str] = None,
    ) -> dict:
        """
        Announce a destination.

        Args:
            destination_hash: Hex-encoded destination hash
            app_data: Optional app data to include

        Returns:
            dict with announced status
        """
        return exec_on_node(self.container, "announce", {
            "destination_hash": destination_hash,
            "app_data": app_data,
        })

    def create_link(
        self,
        destination_hash: str,
        app_name: str,
        aspects: Optional[list] = None,
        timeout: float = 10.0,
    ) -> dict:
        """
        Create a link to a remote destination.

        Args:
            destination_hash: Hex-encoded destination hash
            app_name: Application name used by the destination
            aspects: List of aspect strings used by the destination
            timeout: Link establishment timeout in seconds

        Returns:
            dict with link_id, status, rtt
        """
        return exec_on_node(self.container, "create_link", {
            "destination_hash": destination_hash,
            "app_name": app_name,
            "aspects": aspects or [],
            "timeout": timeout,
        }, timeout=int(timeout) + 5)

    def send_data(
        self,
        link_id: str,
        data: bytes,
        timeout: float = 5.0,
    ) -> dict:
        """
        Send data over an established link.

        NOTE: This method requires the link to exist in the same process,
        which is not the case with our script-based approach.
        Use create_link_and_send() instead, or send data as part of the
        link creation with create_link(..., data=...).

        Args:
            link_id: Hex-encoded link ID
            data: Data to send (bytes or str)
            timeout: Delivery confirmation timeout

        Returns:
            dict with sent, delivered status
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        return exec_on_node(self.container, "send_data", {
            "link_id": link_id,
            "data_hex": data.hex(),
            "timeout": timeout,
        }, timeout=int(timeout) + 5)

    def create_link_and_send(
        self,
        destination_hash: str,
        app_name: str,
        data: bytes,
        aspects: Optional[list] = None,
        link_timeout: float = 10.0,
        data_timeout: float = 5.0,
    ) -> dict:
        """
        Create a link and send data in one operation.

        This is the recommended way to send data, as it keeps the link
        alive in the same process.

        Args:
            destination_hash: Hex-encoded destination hash
            app_name: Application name used by the destination
            data: Data to send
            aspects: List of aspect strings used by the destination
            link_timeout: Link establishment timeout
            data_timeout: Data delivery timeout

        Returns:
            dict with link_id, status, data_sent, data_delivered
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        return exec_on_node(self.container, "create_link", {
            "destination_hash": destination_hash,
            "app_name": app_name,
            "aspects": aspects or [],
            "timeout": link_timeout,
            "data_hex": data.hex(),
            "data_timeout": data_timeout,
        }, timeout=int(link_timeout) + int(data_timeout) + 10)

    def send_resource(
        self,
        link_id: str,
        data: bytes,
        timeout: float = 30.0,
        compress: bool = True,
    ) -> dict:
        """
        Send a resource over an established link.

        NOTE: This method requires the link to exist in the same process,
        which is not the case with our script-based approach.
        Use create_link_and_send_resource() instead.

        Args:
            link_id: Hex-encoded link ID
            data: Data to send
            timeout: Transfer timeout in seconds
            compress: Whether to compress the data

        Returns:
            dict with sent, completed, progress
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        return exec_on_node(self.container, "send_resource", {
            "link_id": link_id,
            "data_hex": data.hex(),
            "timeout": timeout,
            "compress": compress,
        }, timeout=int(timeout) + 10)

    def create_link_and_send_resource(
        self,
        destination_hash: str,
        app_name: str,
        data: bytes,
        aspects: Optional[list] = None,
        link_timeout: float = 10.0,
        resource_timeout: float = 30.0,
        compress: bool = True,
    ) -> dict:
        """
        Create a link and send a resource in one operation.

        This is the recommended way to send resources, as it keeps the link
        alive in the same process.

        Args:
            destination_hash: Hex-encoded destination hash
            app_name: Application name used by the destination
            data: Resource data to send
            aspects: List of aspect strings used by the destination
            link_timeout: Link establishment timeout
            resource_timeout: Resource transfer timeout
            compress: Whether to compress the resource

        Returns:
            dict with link_id, status, resource_sent, resource_completed
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        return exec_on_node(self.container, "create_link", {
            "destination_hash": destination_hash,
            "app_name": app_name,
            "aspects": aspects or [],
            "timeout": link_timeout,
            "resource_hex": data.hex(),
            "resource_timeout": resource_timeout,
            "resource_compress": compress,
        }, timeout=int(link_timeout) + int(resource_timeout) + 10)

    def wait_for_path(
        self,
        destination_hash: str,
        timeout: float = 10.0,
    ) -> dict:
        """
        Wait for a path to a destination.

        Args:
            destination_hash: Hex-encoded destination hash
            timeout: Wait timeout in seconds

        Returns:
            dict with path_found, hops
        """
        return exec_on_node(self.container, "wait_condition", {
            "condition": "path",
            "destination_hash": destination_hash,
            "timeout": timeout,
        }, timeout=int(timeout) + 5)

    def wait_for_announce(
        self,
        destination_hash: Optional[str] = None,
        timeout: float = 10.0,
    ) -> dict:
        """
        Wait to receive an announce.

        Args:
            destination_hash: Optional specific destination to wait for
            timeout: Wait timeout in seconds

        Returns:
            dict with announce_received, destination_hash, app_data
        """
        return exec_on_node(self.container, "wait_condition", {
            "condition": "announce",
            "destination_hash": destination_hash,
            "timeout": timeout,
        }, timeout=int(timeout) + 5)

    def wait_for_link(
        self,
        destination_hash: str,
        timeout: float = 10.0,
    ) -> dict:
        """
        Wait for a link to be established to a local destination.

        Args:
            destination_hash: Hex-encoded destination hash
            timeout: Wait timeout in seconds

        Returns:
            dict with link_established, link_id
        """
        return exec_on_node(self.container, "wait_condition", {
            "condition": "link",
            "destination_hash": destination_hash,
            "timeout": timeout,
        }, timeout=int(timeout) + 5)
