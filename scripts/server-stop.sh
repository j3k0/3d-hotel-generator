#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$PROJECT_ROOT/.server.pid"
PORT_FILE="$PROJECT_ROOT/.server.port"

if [ ! -f "$PID_FILE" ]; then
    echo "Server is not running (no PID file)"
    exit 0
fi

SERVER_PID=$(cat "$PID_FILE")
PORT=$(cat "$PORT_FILE" 2>/dev/null || echo "unknown")

if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "Server was not running (stale PID $SERVER_PID). Cleaning up."
    rm -f "$PID_FILE" "$PORT_FILE"
    exit 0
fi

# Graceful shutdown
kill "$SERVER_PID"

# Wait up to 5 seconds for process to exit
for i in $(seq 1 10); do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        break
    fi
    sleep 0.5
done

# Force kill if still running
if kill -0 "$SERVER_PID" 2>/dev/null; then
    kill -9 "$SERVER_PID" 2>/dev/null || true
fi

rm -f "$PID_FILE" "$PORT_FILE"
echo "Server stopped (was PID $SERVER_PID on port $PORT)"
