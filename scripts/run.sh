#!/usr/bin/env bash
# scripts/run.sh

set -e

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "$script_dir/.." && pwd)"

cd "$project_root"

echo "launching application..."

# 1. Virtualenv setup
if [ ! -d "$project_root/.venv" ]; then
    echo "creating virtual environment in .venv..."
    python3 -m venv "$project_root/.venv"
fi

python_cmd="$project_root/.venv/bin/python"

# 2. Dependency & build sync
echo "syncing python backend dependencies..."
$python_cmd -m pip install -q -r backend/requirements.txt

echo "syncing node frontend dependencies..."
npm install --prefix frontend --quiet

echo "building frontend assets..."
npm run build --prefix frontend

# 3. Process cleanup handler
cleanup() {
    echo ""
    echo "stopping servers..."
    if [ -n "$backend_pid" ]; then
        kill "$backend_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT SIGINT SIGTERM

# 4. Clear any stale process on port 8000
if command -v fuser &>/dev/null; then
    fuser -k 8000/tcp 2>/dev/null || true
elif command -v lsof &>/dev/null; then
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
fi

# 5. Start FastAPI backend (log to /tmp/backend.log to keep terminal clean)
echo "starting backend on http://127.0.0.1:8000..."
$python_cmd -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 > /tmp/backend.log 2>&1 &
backend_pid=$!

# 6. Wait for backend to complete initial market data cache warm-up
echo "waiting for backend market data engine to warm up..."
backend_ready=0
for i in {1..25}; do
    status=$(curl -s http://127.0.0.1:8000/api/engine/status 2>/dev/null || true)
    if echo "$status" | grep -q '"warm":true'; then
        backend_ready=1
        break
    elif echo "$status" | grep -q '"ok":true'; then
        # Backend is up, still warming up assets
        echo "backend online, caching market assets ($i/25)..."
    fi
    sleep 1
done

if [ "$backend_ready" -eq 1 ]; then
    echo "backend is online"
else
    echo "backend started on http://127.0.0.1:8000"
fi

echo ""
echo "app running:"
echo "frontend: http://localhost:5173"
echo "backend api: http://127.0.0.1:8000"
echo "docs: http://127.0.0.1:8000/docs"
echo "press ctrl+c to stop servers."
echo ""

# 7. Start Vite frontend dev server
npm run dev --prefix frontend
