#!/usr/bin/env bash
# AniRoute one-command start (macOS / Linux / Git Bash).
#   bash scripts/start.sh
# First run: creates .venv, installs CPU PyTorch + backend packages and frontend packages.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -x .venv/bin/python ]; then PY=.venv/bin/python
elif [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
else
  echo "Creating Python virtual environment (.venv)..."
  python3 -m venv .venv
  PY=.venv/bin/python
fi

if ! "$PY" -c "import ultralytics, cv2, fastapi, multipart" 2>/dev/null; then
  echo "Installing backend packages (first run downloads about 300 MB)..."
  "$PY" -m pip install --upgrade pip
  "$PY" -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
  "$PY" -m pip install -r backend/requirements.txt
fi

[ -d frontend/node_modules ] || (cd frontend && npm ci)
[ -f frontend/.env ] || cp frontend/.env.example frontend/.env

"$PY" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!
(cd frontend && npm run dev -- --port 5173) &
WEB_PID=$!
trap 'kill $API_PID $WEB_PID 2>/dev/null' EXIT INT TERM

sleep 4
echo "AniRoute is running: http://127.0.0.1:5173  (API http://127.0.0.1:8000). Press Ctrl+C to stop."
(command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:5173) || (command -v open >/dev/null && open http://127.0.0.1:5173) || true
wait
