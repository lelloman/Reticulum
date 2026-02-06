#!/usr/bin/env python3
"""Network chaos injection utilities for resilience testing.

Uses tc (traffic control) and netem to simulate network conditions.
These utilities are designed to run inside Docker containers.
"""

import subprocess
import sys
import json


class NetworkChaos:
    """Network chaos injection for testing resilience."""

    # Default interface for Docker containers
    DEFAULT_INTERFACE = "eth0"

    @staticmethod
    def _run_tc(args: list, check: bool = True) -> dict:
        """Run a tc command."""
        cmd = ["tc"] + args
        result = subprocess.run(cmd, capture_output=True, text=True)

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }

    @classmethod
    def add_packet_loss(cls, percent: int, interface: str = None) -> dict:
        """
        Add packet loss to the network interface.

        Args:
            percent: Packet loss percentage (0-100)
            interface: Network interface (default: eth0)

        Returns:
            dict with success status
        """
        iface = interface or cls.DEFAULT_INTERFACE

        # First try to add, if fails try to change existing rule
        result = cls._run_tc([
            "qdisc", "add", "dev", iface, "root",
            "netem", "loss", f"{percent}%"
        ], check=False)

        if not result["success"] and "File exists" in result["stderr"]:
            # Rule exists, change it instead
            result = cls._run_tc([
                "qdisc", "change", "dev", iface, "root",
                "netem", "loss", f"{percent}%"
            ])

        return result

    @classmethod
    def add_latency(cls, ms: int, jitter: int = 0, interface: str = None) -> dict:
        """
        Add latency to the network interface.

        Args:
            ms: Delay in milliseconds
            jitter: Jitter in milliseconds (optional)
            interface: Network interface (default: eth0)

        Returns:
            dict with success status
        """
        iface = interface or cls.DEFAULT_INTERFACE

        args = [
            "qdisc", "add", "dev", iface, "root",
            "netem", "delay", f"{ms}ms"
        ]

        if jitter > 0:
            args.append(f"{jitter}ms")

        result = cls._run_tc(args, check=False)

        if not result["success"] and "File exists" in result["stderr"]:
            args[1] = "change"  # Change 'add' to 'change'
            result = cls._run_tc(args)

        return result

    @classmethod
    def add_packet_corruption(cls, percent: int, interface: str = None) -> dict:
        """
        Add packet corruption to the network interface.

        Args:
            percent: Corruption percentage (0-100)
            interface: Network interface (default: eth0)

        Returns:
            dict with success status
        """
        iface = interface or cls.DEFAULT_INTERFACE

        result = cls._run_tc([
            "qdisc", "add", "dev", iface, "root",
            "netem", "corrupt", f"{percent}%"
        ], check=False)

        if not result["success"] and "File exists" in result["stderr"]:
            result = cls._run_tc([
                "qdisc", "change", "dev", iface, "root",
                "netem", "corrupt", f"{percent}%"
            ])

        return result

    @classmethod
    def add_packet_duplication(cls, percent: int, interface: str = None) -> dict:
        """
        Add packet duplication to the network interface.

        Args:
            percent: Duplication percentage (0-100)
            interface: Network interface (default: eth0)

        Returns:
            dict with success status
        """
        iface = interface or cls.DEFAULT_INTERFACE

        result = cls._run_tc([
            "qdisc", "add", "dev", iface, "root",
            "netem", "duplicate", f"{percent}%"
        ], check=False)

        if not result["success"] and "File exists" in result["stderr"]:
            result = cls._run_tc([
                "qdisc", "change", "dev", iface, "root",
                "netem", "duplicate", f"{percent}%"
            ])

        return result

    @classmethod
    def add_bandwidth_limit(cls, rate: str, interface: str = None) -> dict:
        """
        Limit bandwidth on the network interface.

        Args:
            rate: Bandwidth limit (e.g., "1mbit", "100kbit")
            interface: Network interface (default: eth0)

        Returns:
            dict with success status
        """
        iface = interface or cls.DEFAULT_INTERFACE

        result = cls._run_tc([
            "qdisc", "add", "dev", iface, "root",
            "tbf", "rate", rate, "burst", "32kbit", "latency", "400ms"
        ], check=False)

        if not result["success"] and "File exists" in result["stderr"]:
            result = cls._run_tc([
                "qdisc", "change", "dev", iface, "root",
                "tbf", "rate", rate, "burst", "32kbit", "latency", "400ms"
            ])

        return result

    @classmethod
    def clear(cls, interface: str = None) -> dict:
        """
        Clear all network chaos rules.

        Args:
            interface: Network interface (default: eth0)

        Returns:
            dict with success status
        """
        iface = interface or cls.DEFAULT_INTERFACE

        return cls._run_tc([
            "qdisc", "del", "dev", iface, "root"
        ], check=False)

    @classmethod
    def get_status(cls, interface: str = None) -> dict:
        """
        Get current tc qdisc status.

        Args:
            interface: Network interface (default: eth0)

        Returns:
            dict with status information
        """
        iface = interface or cls.DEFAULT_INTERFACE

        result = cls._run_tc(["qdisc", "show", "dev", iface])
        result["interface"] = iface

        return result


def run(args: dict) -> dict:
    """
    Execute a network chaos operation.

    Args:
        operation: One of 'packet_loss', 'latency', 'corruption',
                   'duplication', 'bandwidth', 'clear', 'status'
        interface: Network interface (optional, default: eth0)
        Additional args depend on operation

    Returns:
        dict with operation result
    """
    operation = args.get("operation")
    interface = args.get("interface")

    if operation == "packet_loss":
        percent = args.get("percent", 10)
        return NetworkChaos.add_packet_loss(percent, interface)

    elif operation == "latency":
        ms = args.get("ms", 100)
        jitter = args.get("jitter", 0)
        return NetworkChaos.add_latency(ms, jitter, interface)

    elif operation == "corruption":
        percent = args.get("percent", 5)
        return NetworkChaos.add_packet_corruption(percent, interface)

    elif operation == "duplication":
        percent = args.get("percent", 5)
        return NetworkChaos.add_packet_duplication(percent, interface)

    elif operation == "bandwidth":
        rate = args.get("rate", "1mbit")
        return NetworkChaos.add_bandwidth_limit(rate, interface)

    elif operation == "clear":
        return NetworkChaos.clear(interface)

    elif operation == "status":
        return NetworkChaos.get_status(interface)

    else:
        return {"error": f"Unknown operation: {operation}", "success": False}


def main():
    args = json.loads(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
    result = run(args)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
