#!/usr/bin/env python3
"""Execute RNS CLI tools and return structured results."""

import sys
import json
import subprocess


def run(args: dict) -> dict:
    """
    Execute an RNS CLI command.

    Args:
        command: CLI command name (rnstatus, rnpath, rnprobe, rncp, rnid, rnx, rnir)
        cli_args: List of command-line arguments
        timeout: Command timeout in seconds (default 30)
        capture_stderr: Whether to include stderr in output (default True)

    Returns:
        returncode: Exit code of the command
        stdout: Standard output
        stderr: Standard error (if capture_stderr)
        success: True if returncode == 0
    """
    command = args["command"]
    cli_args = args.get("cli_args", [])
    timeout = args.get("timeout", 30)
    capture_stderr = args.get("capture_stderr", True)

    # Build full command
    cmd = [command] + cli_args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        response = {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "success": result.returncode == 0,
        }

        if capture_stderr:
            response["stderr"] = result.stderr

        return response

    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "success": False,
            "error": "timeout"
        }
    except FileNotFoundError:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command not found: {command}",
            "success": False,
            "error": "not_found"
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "success": False,
            "error": "exception"
        }


def main():
    args = json.loads(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
    result = run(args)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
