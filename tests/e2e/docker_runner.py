#!/usr/bin/env python3
"""
Docker E2E Test Runner

This script manages the Docker-based E2E test environment and runs tests.

Usage:
    python -m tests.e2e.docker_runner [options]

Options:
    --up            Start the Docker environment only
    --down          Stop the Docker environment
    --run           Run tests (environment must be up)
    --full          Full test cycle: up, run tests, down
    --logs          Show container logs
    -v, --verbose   Verbose output
"""

import argparse
import subprocess
import sys
import time
import os

DOCKER_COMPOSE_DIR = os.path.join(os.path.dirname(__file__), "docker")
CONTAINERS = ["rns-transport", "rns-node-a", "rns-node-c"]


def run_cmd(cmd, check=True, capture=False):
    """Run a command and return result."""
    print(f"+ {' '.join(cmd)}")
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True, check=check)
    return subprocess.run(cmd, check=check)


def docker_compose(*args):
    """Run docker compose command."""
    cmd = ["docker", "compose", "-f", os.path.join(DOCKER_COMPOSE_DIR, "docker-compose.yml")]
    cmd.extend(args)
    return run_cmd(cmd)


def check_container_healthy(container):
    """Check if a container is healthy."""
    result = run_cmd(
        ["docker", "inspect", "-f", "{{.State.Health.Status}}", container],
        check=False,
        capture=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "healthy"


def wait_for_healthy(timeout=60):
    """Wait for all containers to become healthy."""
    print(f"Waiting for containers to become healthy (timeout: {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        all_healthy = all(check_container_healthy(c) for c in CONTAINERS)
        if all_healthy:
            print("All containers healthy!")
            return True
        time.sleep(2)
        print(".", end="", flush=True)
    print("\nTimeout waiting for containers to become healthy")
    return False


def do_up(args):
    """Start the Docker environment."""
    print("Building and starting Docker environment...")
    docker_compose("build")
    docker_compose("up", "-d", "transport", "node-a", "node-c")

    if not wait_for_healthy():
        print("ERROR: Containers did not become healthy")
        do_logs(args)
        return False

    # Show status
    for container in CONTAINERS:
        print(f"\n=== {container} status ===")
        run_cmd(["docker", "exec", container, "rnstatus"], check=False)

    return True


def do_down(args):
    """Stop the Docker environment."""
    print("Stopping Docker environment...")
    docker_compose("down", "-v")


def do_run(args):
    """Run the tests."""
    print("Running E2E tests...")
    pytest_args = ["python", "-m", "pytest", "tests/e2e/scenarios/", "-v", "--tb=short"]
    if args.verbose:
        pytest_args.append("-s")
    return run_cmd(pytest_args, check=False).returncode == 0


def do_logs(args):
    """Show container logs."""
    docker_compose("logs", "--tail=100")


def do_full(args):
    """Full test cycle."""
    try:
        if not do_up(args):
            return False

        success = do_run(args)

        return success
    finally:
        do_down(args)


def main():
    parser = argparse.ArgumentParser(description="Docker E2E Test Runner")
    parser.add_argument("--up", action="store_true", help="Start Docker environment")
    parser.add_argument("--down", action="store_true", help="Stop Docker environment")
    parser.add_argument("--run", action="store_true", help="Run tests")
    parser.add_argument("--full", action="store_true", help="Full test cycle")
    parser.add_argument("--logs", action="store_true", help="Show container logs")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Default to full if no action specified
    if not any([args.up, args.down, args.run, args.full, args.logs]):
        args.full = True

    success = True

    if args.up:
        success = do_up(args)
    elif args.down:
        do_down(args)
    elif args.run:
        success = do_run(args)
    elif args.full:
        success = do_full(args)
    elif args.logs:
        do_logs(args)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
