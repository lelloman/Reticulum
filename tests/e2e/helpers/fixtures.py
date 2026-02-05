"""Shared test fixtures and utilities."""

import os

# Container names - Standard star topology
CONTAINER_TRANSPORT = "rns-transport"
CONTAINER_NODE_A = "rns-node-a"
CONTAINER_NODE_C = "rns-node-c"

# Container names - Extended topologies
CONTAINER_TRANSPORT_2 = "rns-transport-2"
CONTAINER_NODE_B = "rns-node-b"
CONTAINER_NODE_D = "rns-node-d"
CONTAINER_NODE_E = "rns-node-e"
CONTAINER_CHAIN_LINK = "rns-chain-link"

# Fixed test identities for reproducibility
# These are test-only keys - DO NOT use in production
FIXED_IDENTITIES = {
    "test_identity_1": {
        # Generated for testing purposes only
        "private_key": "f8953ffaf607627e615603ff1530c82c434cf87c07179dd7689ea776f30b964c",
        "public_key": "d85d036245436a3c33d3228affae06721f8203bc364ee0ee7556368ac62add65",
    },
    "test_identity_2": {
        "private_key": "a1b2c3d4e5f6071809a0b1c2d3e4f506172839404a5b6c7d8e9f0a1b2c3d4e5f",
        "public_key": "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
    },
}


def get_container_name(node: str) -> str:
    """Get container name for a node identifier."""
    mapping = {
        "transport": CONTAINER_TRANSPORT,
        "transport-2": CONTAINER_TRANSPORT_2,
        "transport_2": CONTAINER_TRANSPORT_2,
        "node-a": CONTAINER_NODE_A,
        "node_a": CONTAINER_NODE_A,
        "a": CONTAINER_NODE_A,
        "node-b": CONTAINER_NODE_B,
        "node_b": CONTAINER_NODE_B,
        "b": CONTAINER_NODE_B,
        "node-c": CONTAINER_NODE_C,
        "node_c": CONTAINER_NODE_C,
        "c": CONTAINER_NODE_C,
        "node-d": CONTAINER_NODE_D,
        "node_d": CONTAINER_NODE_D,
        "d": CONTAINER_NODE_D,
        "node-e": CONTAINER_NODE_E,
        "node_e": CONTAINER_NODE_E,
        "e": CONTAINER_NODE_E,
        "chain-link": CONTAINER_CHAIN_LINK,
    }
    return mapping.get(node.lower(), node)


def get_results_dir() -> str:
    """Get the results directory path."""
    return os.environ.get("RESULTS_DIR", "/results")
