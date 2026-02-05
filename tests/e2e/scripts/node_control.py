#!/usr/bin/env python3
"""
Node control script - executed via docker exec to control RNS nodes.

This script provides a unified interface for all node operations,
delegating to specific command handlers.
"""

import sys
import json
import argparse


def main():
    parser = argparse.ArgumentParser(description="RNS node control")
    parser.add_argument("command", help="Command to execute")
    parser.add_argument("args", nargs="?", default="{}", help="JSON arguments")

    args = parser.parse_args()

    try:
        cmd_args = json.loads(args.args)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON arguments: {e}"}))
        sys.exit(1)

    # Import command handlers
    if args.command == "create_destination":
        from scripts.create_destination import run
    elif args.command == "announce":
        from scripts.announce import run
    elif args.command == "create_link":
        from scripts.create_link import run
    elif args.command == "send_data":
        from scripts.send_data import run
    elif args.command == "send_resource":
        from scripts.send_resource import run
    elif args.command == "wait_condition":
        from scripts.wait_condition import run
    else:
        print(json.dumps({"error": f"Unknown command: {args.command}"}))
        sys.exit(1)

    try:
        result = run(cmd_args)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
