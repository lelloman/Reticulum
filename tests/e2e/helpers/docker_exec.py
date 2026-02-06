"""Execute Python scripts inside RNS containers via a persistent control daemon."""

import subprocess
import json
import time
import threading
import queue
from typing import Optional


class _DaemonConnection:
    """
    Wraps a persistent ``docker exec -i`` subprocess running control_daemon.py.

    Uses a background reader thread + queue.Queue for timeout-safe response reading.
    Auto-detects a dead daemon (process exited) so callers can restart.
    """

    def __init__(self, container: str):
        self.container = container
        self._proc = None
        self._queue = None
        self._reader_thread = None
        self._lock = threading.Lock()
        self._start()

    def _start(self):
        """Launch the daemon subprocess and wait for the ready signal."""
        self._proc = subprocess.Popen(
            [
                "docker", "exec", "-i", self.container,
                "python", "/app/scripts/control_daemon.py",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self._queue = queue.Queue()
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True
        )
        self._reader_thread.start()

        # Wait for the {"status": "ready"} line
        try:
            ready = self._queue.get(timeout=30)
        except queue.Empty:
            self.shutdown()
            raise RuntimeError(
                f"Daemon on {self.container} did not become ready within 30s"
            )

        if "error" in ready:
            self.shutdown()
            raise RuntimeError(
                f"Daemon on {self.container} failed to start: {ready['error']}"
            )

    def _reader_loop(self):
        """Background thread that reads lines from stdout into the queue."""
        try:
            for line in self._proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    # Skip non-JSON lines (e.g. RNS log output)
                    continue
                self._queue.put(obj)
        except (ValueError, OSError):
            # Pipe closed
            pass

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def send_command(self, command: str, args: dict, timeout: int = 30) -> dict:
        """
        Send a command to the daemon and return the response.

        Raises RuntimeError if the daemon is dead or the command times out.
        """
        with self._lock:
            if not self.alive:
                raise RuntimeError(f"Daemon on {self.container} is not running")

            request = json.dumps({"command": command, "args": args}) + "\n"
            try:
                self._proc.stdin.write(request)
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                raise RuntimeError(
                    f"Daemon on {self.container} pipe broken: {e}"
                )

            try:
                response = self._queue.get(timeout=timeout)
            except queue.Empty:
                raise RuntimeError(
                    f"Daemon on {self.container} timed out after {timeout}s "
                    f"for command '{command}'"
                )

            return response

    def shutdown(self):
        """Kill the daemon subprocess."""
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.stdin.close()
            except OSError:
                pass
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                self._proc.kill()
        self._proc = None


# ============================================================
# Daemon pool: one connection per container
# ============================================================

_daemon_pool: dict[str, _DaemonConnection] = {}
_pool_lock = threading.Lock()


def _get_daemon(container: str) -> _DaemonConnection:
    """Get or create a daemon connection for the given container."""
    with _pool_lock:
        conn = _daemon_pool.get(container)
        if conn is not None and conn.alive:
            return conn
        # Dead or missing – create a new one
        if conn is not None:
            conn.shutdown()
        conn = _DaemonConnection(container)
        _daemon_pool[container] = conn
        return conn


def _invalidate_daemon(container: str):
    """Shut down and remove the daemon connection for a container."""
    with _pool_lock:
        conn = _daemon_pool.pop(container, None)
        if conn is not None:
            conn.shutdown()


def shutdown_all_daemons():
    """Shut down all daemon connections. Called at end of test session."""
    with _pool_lock:
        for conn in _daemon_pool.values():
            conn.shutdown()
        _daemon_pool.clear()


# ============================================================
# exec_on_node – routes through daemon
# ============================================================

def exec_on_node(container: str, script: str, args: dict, timeout: int = 30) -> dict:
    """
    Execute a control script on an RNS node container via the persistent daemon.

    Args:
        container: Container name (e.g., "rns-node-a")
        script: Script/command name (e.g., "create_destination")
        args: Arguments to pass as JSON
        timeout: Command timeout in seconds

    Returns:
        JSON result from script

    Raises:
        RuntimeError: If script execution fails
    """
    daemon = _get_daemon(container)

    try:
        response = daemon.send_command(script, args, timeout=timeout)
    except RuntimeError:
        # Daemon may have died – invalidate and retry once
        _invalidate_daemon(container)
        daemon = _get_daemon(container)
        response = daemon.send_command(script, args, timeout=timeout)

    # Unwrap the daemon protocol.
    # Daemon-level errors (script crashed with exception) have "error" + "traceback".
    # Script-level errors (e.g. {"error": "Timeout waiting for path"}) are wrapped
    # in {"result": {...}} and passed through to the caller unchanged.
    if "error" in response and "result" not in response:
        error_msg = response["error"]
        tb = response.get("traceback", "")
        raise RuntimeError(f"Script {script} failed on {container}: {error_msg}\n{tb}")

    return response.get("result", response)


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

        Uses the persistent daemon to keep the destination alive across
        commands. No background process is needed.

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

        result = exec_on_node(self.container, "serve_destination", args, timeout=15)

        # Wait a moment to ensure the announce propagates
        time.sleep(1.0)

        return result

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
        identify: bool = False,
    ) -> dict:
        """
        Create a link to a remote destination.

        Args:
            destination_hash: Hex-encoded destination hash
            app_name: Application name used by the destination
            aspects: List of aspect strings used by the destination
            timeout: Link establishment timeout in seconds
            identify: Whether to send identity after link is active

        Returns:
            dict with link_id, status, rtt
        """
        args = {
            "destination_hash": destination_hash,
            "app_name": app_name,
            "aspects": aspects or [],
            "timeout": timeout,
        }
        if identify:
            args["identify"] = True
        return exec_on_node(self.container, "create_link", args,
                            timeout=int(timeout) + 5)

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

    # ========== CLI Tool Methods ==========

    def run_cli(
        self,
        command: str,
        cli_args: Optional[list] = None,
        timeout: int = 30,
    ) -> dict:
        """
        Execute an RNS CLI command on this node.

        Args:
            command: CLI command name (rnstatus, rnpath, rnprobe, rncp, rnid, rnx, rnir)
            cli_args: List of command-line arguments
            timeout: Command timeout in seconds

        Returns:
            dict with returncode, stdout, stderr, success
        """
        return exec_on_node(self.container, "run_cli", {
            "command": command,
            "cli_args": cli_args or [],
            "timeout": timeout,
        }, timeout=timeout + 5)

    def rnstatus(self, cli_args: Optional[list] = None, timeout: int = 30) -> dict:
        """Run rnstatus command."""
        return self.run_cli("rnstatus", cli_args or [], timeout)

    def rnpath(self, cli_args: Optional[list] = None, timeout: int = 30) -> dict:
        """Run rnpath command."""
        return self.run_cli("rnpath", cli_args or [], timeout)

    def rnprobe(self, destination_hash: str, timeout: int = 30) -> dict:
        """
        Run rnprobe command to probe a destination.

        Args:
            destination_hash: Hex-encoded destination hash to probe
            timeout: Command timeout
        """
        return self.run_cli("rnprobe", [destination_hash], timeout)

    def rnid(self, cli_args: Optional[list] = None, timeout: int = 30) -> dict:
        """Run rnid command."""
        return self.run_cli("rnid", cli_args or [], timeout)

    def rnir(self, cli_args: Optional[list] = None, timeout: int = 30) -> dict:
        """Run rnir command."""
        return self.run_cli("rnir", cli_args or [], timeout)

    # ========== File Operations (direct docker exec) ==========

    def create_file(self, path: str, content: bytes, timeout: int = 10) -> dict:
        """
        Create a file in the container.

        Args:
            path: Absolute path for the file
            content: File contents (bytes or str)

        Returns:
            dict with success status
        """
        if isinstance(content, str):
            content = content.encode("utf-8")

        # Use base64 to safely transfer binary content
        import base64
        content_b64 = base64.b64encode(content).decode("ascii")

        cmd = [
            "docker", "exec", self.container,
            "python", "-c",
            f"import base64; open('{path}', 'wb').write(base64.b64decode('{content_b64}'))"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        return {
            "success": result.returncode == 0,
            "path": path,
            "error": result.stderr if result.returncode != 0 else None,
        }

    def read_file(self, path: str, timeout: int = 10) -> dict:
        """
        Read a file from the container.

        Args:
            path: Absolute path to the file

        Returns:
            dict with content (bytes as hex), success status
        """
        cmd = [
            "docker", "exec", self.container,
            "python", "-c",
            f"import sys; data = open('{path}', 'rb').read(); print(data.hex())"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        if result.returncode == 0:
            content_hex = result.stdout.strip()
            return {
                "success": True,
                "content_hex": content_hex,
                "content": bytes.fromhex(content_hex),
            }
        else:
            return {
                "success": False,
                "error": result.stderr,
            }

    def delete_file(self, path: str, timeout: int = 10) -> dict:
        """
        Delete a file from the container.

        Args:
            path: Absolute path to the file

        Returns:
            dict with success status
        """
        cmd = [
            "docker", "exec", self.container,
            "python", "-c",
            f"import os; os.remove('{path}')"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        return {
            "success": result.returncode == 0,
            "error": result.stderr if result.returncode != 0 else None,
        }

    def file_exists(self, path: str, timeout: int = 10) -> bool:
        """Check if a file exists in the container."""
        cmd = [
            "docker", "exec", self.container,
            "python", "-c",
            f"import os; exit(0 if os.path.exists('{path}') else 1)"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0

    # ========== Daemon Control Methods ==========

    def restart_rnsd(self, timeout: int = 30) -> dict:
        """
        Restart the rnsd daemon by restarting the Docker container.

        Uses `docker restart` so rnsd (PID 1) is cleanly restarted
        without needing an init wrapper.

        Returns:
            dict with success status
        """
        # Invalidate daemon connection before restarting
        _invalidate_daemon(self.container)

        restart_cmd = ["docker", "restart", self.container]
        result = subprocess.run(restart_cmd, capture_output=True, text=True, timeout=timeout)

        if result.returncode != 0:
            return {"success": False, "error": result.stderr}

        # Wait for container to become healthy
        start = time.time()
        while time.time() - start < timeout:
            check_cmd = [
                "docker", "inspect", "-f", "{{.State.Health.Status}}", self.container
            ]
            check = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
            if check.stdout.strip() == "healthy":
                return {"success": True}
            time.sleep(1)

        return {"success": False, "error": "Container did not become healthy after restart"}

    def stop_rnsd(self, timeout: int = 10) -> dict:
        """
        Stop the rnsd daemon by stopping the Docker container.

        Returns:
            dict with success status
        """
        _invalidate_daemon(self.container)

        cmd = ["docker", "stop", self.container]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        return {
            "success": result.returncode == 0,
            "error": result.stderr if result.returncode != 0 else None,
        }

    def start_rnsd(self, timeout: int = 30) -> dict:
        """
        Start the rnsd daemon by starting the Docker container.

        Returns:
            dict with success status
        """
        cmd = ["docker", "start", self.container]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            return {"success": False, "error": result.stderr}

        # Wait for container to become healthy
        start = time.time()
        while time.time() - start < timeout:
            check_cmd = [
                "docker", "inspect", "-f", "{{.State.Health.Status}}", self.container
            ]
            check = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
            if check.stdout.strip() == "healthy":
                return {"success": True}
            time.sleep(1)

        return {"success": False, "error": "Container did not become healthy after start"}

    def is_rnsd_running(self, timeout: int = 10) -> bool:
        """Check if rnsd is running on this node."""
        cmd = [
            "docker", "inspect", "-f", "{{.State.Health.Status}}", self.container
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip() == "healthy"

    # ========== Network Chaos Methods ==========

    def exec_command(self, command: str, timeout: int = 30) -> dict:
        """
        Execute an arbitrary command on this node.

        Args:
            command: Shell command to execute

        Returns:
            dict with returncode, stdout, stderr
        """
        cmd = [
            "docker", "exec", self.container,
            "bash", "-c", command
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0,
        }
