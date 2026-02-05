"""Pytest fixtures for E2E Docker tests."""

import pytest
import subprocess
import time
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.docker_exec import NodeInterface
from helpers.fixtures import (
    CONTAINER_TRANSPORT,
    CONTAINER_NODE_A,
    CONTAINER_NODE_C,
)


# ============================================================
# Pytest Markers Configuration
# ============================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "chaos: tests that require network chaos injection (tc/netem)")
    config.addinivalue_line("markers", "performance: performance benchmark tests")
    config.addinivalue_line("markers", "security: security and adversarial tests")
    config.addinivalue_line("markers", "cli: CLI tool integration tests")
    config.addinivalue_line("markers", "concurrent: concurrent operations tests")
    config.addinivalue_line("markers", "advanced: advanced features tests")
    config.addinivalue_line("markers", "topology_chain: tests requiring chain topology (A → T1 → T2 → D)")
    config.addinivalue_line("markers", "topology_ring: tests requiring ring topology (redundant paths)")
    config.addinivalue_line("markers", "topology_mesh: tests requiring mesh topology (5 nodes)")


def _check_container_running(container: str) -> bool:
    """Check if a container is running."""
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", container],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _check_container_healthy(container: str) -> bool:
    """Check if a container is healthy."""
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Health.Status}}", container],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "healthy"


@pytest.fixture(scope="session")
def docker_env():
    """
    Ensure Docker Compose environment is up and healthy.

    This fixture verifies all required containers are running.
    It does NOT start them - use `make test-e2e-docker-up` first.
    """
    containers = [CONTAINER_TRANSPORT, CONTAINER_NODE_A, CONTAINER_NODE_C]

    for container in containers:
        if not _check_container_running(container):
            pytest.fail(
                f"Container {container} is not running. "
                "Start the environment with: make test-e2e-docker-up"
            )

    # Wait for all containers to be healthy
    max_wait = 30
    start = time.time()
    while time.time() - start < max_wait:
        all_healthy = all(_check_container_healthy(c) for c in containers)
        if all_healthy:
            break
        time.sleep(1)
    else:
        unhealthy = [c for c in containers if not _check_container_healthy(c)]
        pytest.fail(f"Containers not healthy after {max_wait}s: {unhealthy}")

    yield

    # No teardown - leave containers running for inspection


@pytest.fixture
def node_a(docker_env) -> NodeInterface:
    """Interface to node-a container."""
    return NodeInterface(CONTAINER_NODE_A)


@pytest.fixture
def node_c(docker_env) -> NodeInterface:
    """Interface to node-c container."""
    return NodeInterface(CONTAINER_NODE_C)


@pytest.fixture
def transport_node(docker_env) -> NodeInterface:
    """Interface to transport container."""
    return NodeInterface(CONTAINER_TRANSPORT)


@pytest.fixture
def all_nodes(node_a, node_c, transport_node) -> dict:
    """Dictionary of all node interfaces."""
    return {
        "node_a": node_a,
        "node_c": node_c,
        "transport": transport_node,
    }


@pytest.fixture
def unique_app_name(request) -> str:
    """Generate a unique app name for each test."""
    # Use test name + timestamp to avoid collisions
    test_name = request.node.name.replace("[", "_").replace("]", "_")
    return f"e2e_{test_name}_{int(time.time() * 1000) % 100000}"
