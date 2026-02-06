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
    --topology      Topology to use: star (default), chain, ring, mesh, all
    -v, --verbose   Verbose output
"""

import argparse
import subprocess
import sys
import time
import os

DOCKER_COMPOSE_DIR = os.path.join(os.path.dirname(__file__), "docker")
SHARD = os.environ.get("SHARD", "0")

TOPOLOGY_CONFIG = {
    "star": {
        "compose": "docker-compose.yml",
        "services": ["transport", "node-a", "node-c"],
        "containers": [f"rns-transport-{SHARD}", f"rns-node-a-{SHARD}", f"rns-node-c-{SHARD}"],
    },
    "chain": {
        "compose": "docker-compose.chain.yml",
        "services": ["transport", "transport-2", "node-a", "node-d", "chain-link"],
        "containers": [f"rns-transport-{SHARD}", f"rns-transport-2-{SHARD}", f"rns-node-a-{SHARD}", f"rns-node-d-{SHARD}", f"rns-chain-link-{SHARD}"],
    },
    "ring": {
        "compose": "docker-compose.ring.yml",
        "services": ["transport", "transport-2", "node-a", "node-c"],
        "containers": [f"rns-transport-{SHARD}", f"rns-transport-2-{SHARD}", f"rns-node-a-{SHARD}", f"rns-node-c-{SHARD}"],
    },
    "mesh": {
        "compose": "docker-compose.mesh.yml",
        "services": ["transport", "node-a", "node-b", "node-c", "node-d", "node-e"],
        "containers": [f"rns-transport-{SHARD}", f"rns-node-a-{SHARD}", f"rns-node-b-{SHARD}", f"rns-node-c-{SHARD}", f"rns-node-d-{SHARD}", f"rns-node-e-{SHARD}"],
    },
}


def run_cmd(cmd, check=True, capture=False, env=None):
    """Run a command and return result."""
    print(f"+ {' '.join(cmd)}")
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True, check=check, env=env)
    return subprocess.run(cmd, check=check, env=env)


def docker_compose(compose_file, *args):
    """Run docker compose command."""
    cmd = ["docker", "compose", "-f", os.path.join(DOCKER_COMPOSE_DIR, compose_file), "-p", f"rns-e2e-{SHARD}"]
    cmd.extend(args)
    env = os.environ.copy()
    env["SHARD"] = SHARD
    return run_cmd(cmd, env=env)


def check_container_healthy(container):
    """Check if a container is healthy."""
    result = run_cmd(
        ["docker", "inspect", "-f", "{{.State.Health.Status}}", container],
        check=False,
        capture=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "healthy"


def wait_for_healthy(containers, timeout=60):
    """Wait for all containers to become healthy."""
    print(f"Waiting for containers to become healthy (timeout: {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        all_healthy = all(check_container_healthy(c) for c in containers)
        if all_healthy:
            print("All containers healthy!")
            return True
        time.sleep(2)
        print(".", end="", flush=True)
    print("\nTimeout waiting for containers to become healthy")
    return False


def get_topology_config(args):
    """Get the topology configuration for the current args."""
    return TOPOLOGY_CONFIG[args.topology]


def do_up(args):
    """Start the Docker environment."""
    config = get_topology_config(args)
    compose_file = config["compose"]

    if not args.no_build:
        print(f"Building Docker images ({args.topology} topology)...")
        docker_compose(compose_file, "build")
    else:
        print("Skipping build (--no-build)")

    print(f"Starting Docker environment ({args.topology} topology)...")
    docker_compose(compose_file, "up", "-d", *config["services"])

    if not wait_for_healthy(config["containers"]):
        print("ERROR: Containers did not become healthy")
        do_logs(args)
        return False

    # Show status
    for container in config["containers"]:
        print(f"\n=== {container} status ===")
        run_cmd(["docker", "exec", container, "rnstatus"], check=False)

    return True


def do_down(args):
    """Stop the Docker environment."""
    config = get_topology_config(args)
    print(f"Stopping Docker environment ({args.topology} topology)...")
    docker_compose(config["compose"], "down", "-v")


def do_run(args):
    """Run the tests."""
    topology = args.topology
    print(f"Running E2E tests ({topology} topology)...")

    env = os.environ.copy()
    env["TOPOLOGY"] = topology
    env.setdefault("SHARD", SHARD)

    pytest_args = ["python", "-m", "pytest", "tests/e2e/scenarios/", "-v", "--tb=short", "-p", "no:cacheprovider"]

    if topology == "star":
        pytest_args.extend(["-m", "not (topology_chain or topology_ring or topology_mesh)"])
    else:
        pytest_args.extend(["-m", f"topology_{topology}"])

    if args.verbose:
        pytest_args.append("-s")

    return subprocess.run(pytest_args, env=env, check=False).returncode == 0


def do_logs(args):
    """Show container logs."""
    config = get_topology_config(args)
    docker_compose(config["compose"], "logs", "--tail=100")


def do_full(args):
    """Full test cycle."""
    try:
        if not do_up(args):
            return False

        success = do_run(args)

        return success
    finally:
        do_down(args)


def do_all(args):
    """Run all topologies sequentially."""
    results = {}
    for topology in ["star", "chain", "ring", "mesh"]:
        print(f"\n{'='*60}")
        print(f"  Running topology: {topology}")
        print(f"{'='*60}\n")

        args.topology = topology
        success = do_full(args)
        results[topology] = success

        if not success:
            print(f"\nWARNING: {topology} topology tests failed")

    print(f"\n{'='*60}")
    print("  Results Summary")
    print(f"{'='*60}")
    for topo, success in results.items():
        status = "PASS" if success else "FAIL"
        print(f"  {topo:10s} {status}")

    return all(results.values())


def main():
    parser = argparse.ArgumentParser(description="Docker E2E Test Runner")
    parser.add_argument("--up", action="store_true", help="Start Docker environment")
    parser.add_argument("--down", action="store_true", help="Stop Docker environment")
    parser.add_argument("--run", action="store_true", help="Run tests")
    parser.add_argument("--full", action="store_true", help="Full test cycle")
    parser.add_argument("--logs", action="store_true", help="Show container logs")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--no-build", action="store_true", help="Skip Docker image build")
    parser.add_argument(
        "--topology",
        choices=["star", "chain", "ring", "mesh", "all"],
        default="star",
        help="Topology to use (default: star)",
    )

    args = parser.parse_args()

    # Default to full if no action specified
    if not any([args.up, args.down, args.run, args.full, args.logs]):
        args.full = True

    # Handle "all" topology specially
    if args.topology == "all":
        if args.up or args.down or args.run or args.logs:
            print("ERROR: --topology all only works with --full (or default)")
            sys.exit(1)
        success = do_all(args)
        sys.exit(0 if success else 1)

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
