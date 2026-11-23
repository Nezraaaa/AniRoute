#!/usr/bin/env bash
# AniRoute for a phone on the same Wi-Fi (macOS / Linux / Git Bash).
#   bash scripts/start-lan.sh
# Starts the API (this computer only) and the web app in LAN mode over https; the phone only needs port 5173.
# Run scripts/start.sh once first so the packages are installed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -x .venv/bin/python ]; then PY=.venv/bin/python
elif [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
else echo "Run scripts/start.sh once first (it installs the packages)."; exit 1; fi

"$PY" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!
(cd frontend && npm run lan) &
WEB_PID=$!
trap 'kill $API_PID $WEB_PID 2>/dev/null' EXIT INT TERM

sleep 5
echo ""
echo "On your phone (same Wi-Fi), open one of these:"
( (command -v ipconfig >/dev/null && ipconfig getifaddr en0) || hostname -I 2>/dev/null | tr ' ' '\n' ) | grep -E '^[0-9]+\.' | sed 's|^\(.*\)$|  https://\1:5173|' || true
echo "First visit: accept the certificate warning once, then allow camera and location."
echo "Press Ctrl+C to stop."
wait
