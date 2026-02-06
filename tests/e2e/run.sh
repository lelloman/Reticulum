#!/bin/bash
# E2E Test Runner for Reticulum (single shard)
# Usage: ./tests/e2e/run.sh [test_pattern]
# Examples:
#   ./tests/e2e/run.sh              # Run all tests
#   ./tests/e2e/run.sh resource     # Run only resource tests
#   ./tests/e2e/run.sh test_link    # Run only link tests

set -e

cd "$(dirname "$0")/../.."

export SHARD=0
PROJECT="rns-e2e-0"

TEST_PATTERN="${1:-}"

echo "=== Building Docker images ==="
make test-e2e-docker-build

echo "=== Starting test environment (shard $SHARD) ==="
make test-e2e-docker-up

cleanup() {
    echo "=== Tearing down environment ==="
    make test-e2e-docker-down
}
trap cleanup EXIT

echo "=== Running E2E tests ==="
if [ -n "$TEST_PATTERN" ]; then
    SHARD=$SHARD docker compose -f tests/e2e/docker/docker-compose.yml -p "$PROJECT" run --rm \
        --entrypoint "python -m pytest tests/e2e/scenarios/ -v --tb=short -k $TEST_PATTERN" \
        test-runner
else
    SHARD=$SHARD docker compose -f tests/e2e/docker/docker-compose.yml -p "$PROJECT" run --rm \
        --entrypoint "python -m pytest tests/e2e/scenarios/ -v --tb=short" \
        test-runner
fi

echo "=== Done ==="
