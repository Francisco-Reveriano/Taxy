#!/usr/bin/env bash
#
# Start the full Tax.AI stack: FastAPI backend + Vite frontend.
# Tracing is built-in — spans are written to backend/traces/ automatically.
#
# Run from the project root:  bash scripts/start.sh
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PIDS=()

cleanup() {
  echo ""
  echo "Shutting down Tax.AI..."
  for pid in ${PIDS[@]+"${PIDS[@]}"}; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null
  echo "All processes stopped."
}
trap cleanup EXIT INT TERM

# ── 1. Python virtual environment ────────────────────────────────────────────

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  echo "[backend]  Activated .venv"
else
  echo "[backend]  ERROR: .venv not found. Run:  python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

# ── 2. Environment file ─────────────────────────────────────────────────────

if [ ! -f ".env" ]; then
  echo "[config]   WARNING: .env not found. Copying from .env.example — fill in your API keys."
  cp .env.example .env
fi

# ── 3. FastAPI backend ───────────────────────────────────────────────────────

echo "[backend]  Starting FastAPI on http://localhost:8000 ..."
python -m backend.main &
PIDS+=($!)

# Wait briefly for the backend to bind its port
sleep 2

# ── 4. Vite frontend ────────────────────────────────────────────────────────

if [ -d "frontend/node_modules" ]; then
  echo "[frontend] Starting Vite on http://localhost:5173 ..."
  npm run dev --prefix frontend &
  PIDS+=($!)
else
  echo "[frontend] node_modules missing. Installing..."
  npm install --prefix frontend
  echo "[frontend] Starting Vite on http://localhost:5173 ..."
  npm run dev --prefix frontend &
  PIDS+=($!)
fi

# ── Ready ────────────────────────────────────────────────────────────────────

echo ""
echo "========================================"
echo "  Tax.AI is running"
echo "  Frontend : http://localhost:5173"
echo "  Backend  : http://localhost:8000"
echo "  API docs : http://localhost:8000/docs"
echo "  Traces   : http://localhost:8000/api/traces"
echo "========================================"
echo "  Press Ctrl+C to stop all services"
echo "========================================"
echo ""

wait
