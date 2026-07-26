#!/usr/bin/env bash

set -e

#repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "quant anomalies dashboard:"

PYTHON_CMD="python3"
if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_CMD="$PROJECT_ROOT/.venv/bin/python"
fi

cleanup() {
    echo ""
    echo "stopping servers..."
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT SIGINT SIGTERM

echo "Starting FastAPI backend on http://127.0.0.1:8000..."
$PYTHON_CMD -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
sleep 2

echo "frontend dashboard: http://localhost:5173"
echo "backend api: http://127.0.0.1:8000"
echo "interactive docs: http://127.0.0.1:8000/docs"
echo "press ctrl + c to stop"

npm run dev --prefix frontend
