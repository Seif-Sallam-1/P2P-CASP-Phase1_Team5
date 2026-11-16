#!/usr/bin/env bash
# Peer-to-Peer Content-Addressable Chunk Streaming Protocol - Phase 1 baseline.
# Runs unit/integration tests, then 4 CONCURRENT clients against one server.
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
HOST="127.0.0.1"
PORT=5001
NUM_CLIENTS=4

mkdir -p logs
RUNTIME_LOG_DIR="$(mktemp -d)"   # duplicate per-process logs go here, not into evidence logs
export CASP_LOG_DIR="$RUNTIME_LOG_DIR"
export PYTHONIOENCODING="utf-8"

echo "===================================================="
echo " Peer-to-Peer Content-Addressable Chunk Streaming Protocol"
echo " Phase 1 Baseline Local Test - $NUM_CLIENTS concurrent clients"
echo "===================================================="

echo
echo "[1/3] Running unit and integration tests..."
"$PYTHON" -m unittest discover -s tests -v

echo
echo "[2/3] Starting UDP server on $HOST:$PORT..."
rm -f logs/baseline_server.log logs/baseline_client_*.log

"$PYTHON" server.py --host "$HOST" --port "$PORT" > logs/baseline_server.log &
SERVER_PID=$!

cleanup() {
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    rm -rf "$RUNTIME_LOG_DIR"
}
trap cleanup EXIT

for _ in $(seq 1 50); do
    grep -q "listening" logs/baseline_server.log 2>/dev/null && break
    kill -0 "$SERVER_PID" 2>/dev/null || break
    sleep 0.1
done

if ! kill -0 "$SERVER_PID" 2>/dev/null || ! grep -q "listening" logs/baseline_server.log; then
    echo "ERROR: Server did not start."
    cat logs/baseline_server.log
    exit 1
fi
echo "Server started successfully."

echo
echo "[3/3] Running INIT and DATA exchanges for $NUM_CLIENTS concurrent clients..."

CLIENT_PIDS=()
for i in $(seq 1 "$NUM_CLIENTS"); do
    "$PYTHON" client.py \
        --host "$HOST" --port "$PORT" \
        --peer-id "$i" \
        --name "baseline-peer-$i" \
        --message "Baseline DATA test from Client $i" \
        > "logs/baseline_client_$i.log" &
    CLIENT_PIDS+=("$!")
done

FAILED=0
for i in $(seq 1 "$NUM_CLIENTS"); do
    if wait "${CLIENT_PIDS[$((i-1))]}"; then
        echo "Client $i: exit code 0"
    else
        echo "Client $i: FAILED (non-zero exit code)"
        FAILED=1
    fi
done

echo
echo "===================================================="
echo " TEST RESULTS"
echo "===================================================="
for i in $(seq 1 "$NUM_CLIENTS"); do
    echo
    echo "----- Client $i Log -----"
    cat "logs/baseline_client_$i.log"
    if ! grep -q "Communication completed successfully" "logs/baseline_client_$i.log"; then
        echo "FAILED: Client $i did not complete successfully."
        FAILED=1
    fi
done

INIT_COUNT=$(grep -c "INIT received" logs/baseline_server.log || true)
DATA_COUNT=$(grep -c "DATA received" logs/baseline_server.log || true)
echo
echo "----- Server Validation -----"
echo "INIT messages received: $INIT_COUNT / $NUM_CLIENTS"
echo "DATA messages received: $DATA_COUNT / $NUM_CLIENTS"
[[ "$INIT_COUNT" -ge "$NUM_CLIENTS" ]] || { echo "FAILED: missing INIT messages."; FAILED=1; }
[[ "$DATA_COUNT" -ge "$NUM_CLIENTS" ]] || { echo "FAILED: missing DATA messages."; FAILED=1; }

if [[ "$FAILED" -ne 0 ]]; then
    echo
    echo "FAILED: $NUM_CLIENTS-Client Baseline Test. Check logs/ for details."
    exit 1
fi

echo
echo "SUCCESS: $NUM_CLIENTS-Client Concurrent Baseline Test Passed."
echo "Evidence logs:"
echo " - logs/baseline_server.log"
for i in $(seq 1 "$NUM_CLIENTS"); do
    echo " - logs/baseline_client_$i.log"
done
