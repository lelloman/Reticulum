#!/bin/bash
# Parallel E2E Test Runner for Reticulum
# Spins up N independent Docker container shards and distributes tests across them.
#
# Usage: ./tests/e2e/run_parallel.sh [N_SHARDS] [pytest_args...]
# Examples:
#   ./tests/e2e/run_parallel.sh           # 8 shards, all tests
#   ./tests/e2e/run_parallel.sh 4         # 4 shards, all tests
#   ./tests/e2e/run_parallel.sh 2 -k link # 2 shards, only link tests

set -euo pipefail

cd "$(dirname "$0")/../.."

N_SHARDS="${1:-8}"
shift || true
EXTRA_PYTEST_ARGS=("$@")

COMPOSE_FILE="tests/e2e/docker/docker-compose.yml"
SCENARIOS_DIR="tests/e2e/scenarios"

# ── Validation ──────────────────────────────────────────────────
if ! [[ "$N_SHARDS" =~ ^[0-9]+$ ]] || [ "$N_SHARDS" -lt 1 ] || [ "$N_SHARDS" -gt 250 ]; then
    echo "Error: N_SHARDS must be between 1 and 250 (got: $N_SHARDS)"
    exit 1
fi

echo "=== Parallel E2E: $N_SHARDS shards ==="

# ── Cleanup trap ────────────────────────────────────────────────
cleanup() {
    echo ""
    echo "=== Tearing down all shards ==="
    for i in $(seq 0 $((N_SHARDS - 1))); do
        SHARD=$i docker compose -f "$COMPOSE_FILE" -p "rns-e2e-$i" down -v 2>/dev/null &
    done
    wait
    echo "=== All shards torn down ==="
}
trap cleanup EXIT

# ── Build images once ───────────────────────────────────────────
echo "=== Building Docker images ==="
SHARD=0 docker compose -f "$COMPOSE_FILE" -p rns-e2e-0 build

# ── Start all shards ────────────────────────────────────────────
echo "=== Starting $N_SHARDS shards ==="
for i in $(seq 0 $((N_SHARDS - 1))); do
    SHARD=$i docker compose -f "$COMPOSE_FILE" -p "rns-e2e-$i" up -d transport node-a node-c &
done
wait

# ── Wait for all containers to be healthy ───────────────────────
echo "=== Waiting for all containers to be healthy ==="
MAX_WAIT=120
POLL_INTERVAL=3
elapsed=0

while [ $elapsed -lt $MAX_WAIT ]; do
    all_healthy=true
    for i in $(seq 0 $((N_SHARDS - 1))); do
        for role in transport node-a node-c; do
            container="rns-${role}-${i}"
            status=$(docker inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null || echo "missing")
            if [ "$status" != "healthy" ]; then
                all_healthy=false
                break 2
            fi
        done
    done

    if $all_healthy; then
        echo "All $((N_SHARDS * 3)) containers healthy after ${elapsed}s"
        break
    fi

    sleep $POLL_INTERVAL
    elapsed=$((elapsed + POLL_INTERVAL))
done

if ! $all_healthy; then
    echo "Error: Not all containers healthy after ${MAX_WAIT}s"
    echo "Unhealthy containers:"
    for i in $(seq 0 $((N_SHARDS - 1))); do
        for role in transport node-a node-c; do
            container="rns-${role}-${i}"
            status=$(docker inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null || echo "missing")
            if [ "$status" != "healthy" ]; then
                echo "  $container: $status"
            fi
        done
    done
    exit 1
fi

# ── Collect test files and distribute round-robin ───────────────
mapfile -t TEST_FILES < <(find "$SCENARIOS_DIR" -name 'test_*.py' -type f | sort)

if [ ${#TEST_FILES[@]} -eq 0 ]; then
    echo "Error: No test files found in $SCENARIOS_DIR"
    exit 1
fi

echo "=== Distributing ${#TEST_FILES[@]} test files across $N_SHARDS shards ==="

# Build per-shard file lists
declare -a SHARD_FILES
for i in $(seq 0 $((N_SHARDS - 1))); do
    SHARD_FILES[$i]=""
done

for idx in "${!TEST_FILES[@]}"; do
    shard=$((idx % N_SHARDS))
    if [ -n "${SHARD_FILES[$shard]}" ]; then
        SHARD_FILES[$shard]="${SHARD_FILES[$shard]} ${TEST_FILES[$idx]}"
    else
        SHARD_FILES[$shard]="${TEST_FILES[$idx]}"
    fi
done

# ── Launch pytest processes via docker compose run ──────────────
echo "=== Running tests ==="
declare -a PIDS
declare -a LOG_FILES
overall_exit=0

for i in $(seq 0 $((N_SHARDS - 1))); do
    files="${SHARD_FILES[$i]}"
    if [ -z "$files" ]; then
        echo "Shard $i: no test files, skipping"
        continue
    fi

    log_file="/tmp/rns-e2e-shard-${i}.log"
    LOG_FILES+=("$log_file")

    file_count=$(echo "$files" | wc -w)
    echo "Shard $i: $file_count file(s)"

    # shellcheck disable=SC2086
    SHARD=$i docker compose -f "$COMPOSE_FILE" -p "rns-e2e-$i" run --rm \
        --entrypoint "python -m pytest $files -v --tb=short -p no:cacheprovider ${EXTRA_PYTEST_ARGS[*]:-}" \
        test-runner \
        > "$log_file" 2>&1 &
    PIDS+=($!)
done

# ── Track per-shard line counts for progress reporting ──────────
declare -A LAST_LINES
for log_file in "${LOG_FILES[@]}"; do
    LAST_LINES["$log_file"]=0
done

# ── Poll for progress while waiting ────────────────────────────
any_running=true
while $any_running; do
    # Check if any PID is still alive
    any_running=false
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            any_running=true
            break
        fi
    done

    # Print new lines from each log file
    for log_file in "${LOG_FILES[@]}"; do
        shard_id=$(echo "$log_file" | grep -oP 'shard-\K[0-9]+')
        if [ -f "$log_file" ]; then
            current_lines=$(wc -l < "$log_file")
            prev=${LAST_LINES["$log_file"]}
            if [ "$current_lines" -gt "$prev" ]; then
                skip=$((prev + 1))
                tail -n +"$skip" "$log_file" | while IFS= read -r line; do
                    echo "[shard $shard_id] $line"
                done
                LAST_LINES["$log_file"]=$current_lines
            fi
        fi
    done

    if $any_running; then
        sleep 2
    fi
done

# ── Collect exit codes ──────────────────────────────────────────
for pid in "${PIDS[@]}"; do
    if ! wait "$pid"; then
        overall_exit=1
    fi
done

# ── Print summary ───────────────────────────────────────────────
echo ""
echo "=== Results ==="
for log_file in "${LOG_FILES[@]}"; do
    shard_id=$(echo "$log_file" | grep -oP 'shard-\K[0-9]+')
    echo ""
    echo "--- Shard $shard_id ---"
    # Print the pytest summary line (short results + passed/failed counts)
    grep -E '(PASSED|FAILED|ERROR|passed|failed|error)' "$log_file" | tail -3
done

echo ""
if [ $overall_exit -eq 0 ]; then
    echo "=== All shards PASSED ==="
else
    echo "=== Some shards FAILED ==="
    echo "Full logs at: /tmp/rns-e2e-shard-*.log"
fi

exit $overall_exit
