#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$PROJECT_ROOT/.server.pid"
PORT_FILE="$PROJECT_ROOT/.server.port"
LOG_FILE="$PROJECT_ROOT/server.log"
DEFAULT_PORT=8000

# Check for already-running server
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        PORT=$(cat "$PORT_FILE" 2>/dev/null || echo "$DEFAULT_PORT")
        echo "Server already running (PID $OLD_PID) at http://localhost:$PORT"
        exit 0
    fi
    # Stale PID file — clean up
    rm -f "$PID_FILE" "$PORT_FILE"
fi

# Find a free port starting from DEFAULT_PORT
PORT=$DEFAULT_PORT
while python3 -c "import socket; s=socket.socket(); s.settimeout(0.1); s.connect(('127.0.0.1',$PORT)); s.close()" 2>/dev/null; do
    PORT=$((PORT + 1))
done

# Start uvicorn in background with auto-reload
cd "$PROJECT_ROOT"
nohup uvicorn hotel_generator.api:app --host 0.0.0.0 --port "$PORT" --reload \
    > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

# Write state files
echo "$SERVER_PID" > "$PID_FILE"
echo "$PORT" > "$PORT_FILE"

echo "Server started (PID $SERVER_PID)"
echo "  URL:  http://localhost:$PORT"
echo "  Logs: $LOG_FILE"
