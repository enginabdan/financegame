#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

PY314_BIN="/Users/engin/.local/python-3.14.3/bin/python3.14"
BACKEND_VENV="$BACKEND_DIR/.venv314"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-4173}"

if [[ ! -x "$PY314_BIN" ]]; then
  echo "[error] Python 3.14 binary not found at: $PY314_BIN"
  exit 1
fi

if [[ ! -d "$BACKEND_VENV" ]]; then
  echo "[setup] Creating backend virtualenv (.venv314)..."
  "$PY314_BIN" -m venv "$BACKEND_VENV"
  source "$BACKEND_VENV/bin/activate"
  pip install -r "$BACKEND_DIR/requirements.txt"
else
  source "$BACKEND_VENV/bin/activate"
fi

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "[warn] .env file not found at project root."
  echo "[warn] Copy .env.example to .env and fill required keys."
fi

cleanup() {
  echo
  echo "[shutdown] Stopping dev servers..."
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
}

trap cleanup INT TERM EXIT

echo "[start] Backend: http://127.0.0.1:$BACKEND_PORT"
(
  cd "$BACKEND_DIR"
  exec "$BACKEND_VENV/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$BACKEND_PORT"
) &
BACKEND_PID=$!

echo "[start] Frontend: http://127.0.0.1:$FRONTEND_PORT"
(
  cd "$FRONTEND_DIR"
  exec python3 -m http.server "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

echo "[ready] Student:  http://127.0.0.1:$FRONTEND_PORT"
echo "[ready] Teacher:  http://127.0.0.1:$FRONTEND_PORT/teacher.html"
echo "[ready] API:      http://127.0.0.1:$BACKEND_PORT"
echo "[info] Press Ctrl+C to stop both servers."

wait
