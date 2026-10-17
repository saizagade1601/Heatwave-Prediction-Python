#!/bin/bash
# HeatGuard AI for macOS / Linux - double-click (mac) or run ./START_DASHBOARD_mac_linux.command
cd "$(dirname "$0")"
if [ ! -f ".venv/setup_done.txt" ]; then
  echo "First-time setup: installing libraries (1-3 minutes)..."
  python3 -m venv .venv || { echo "Install Python 3 from https://www.python.org/downloads/"; exit 1; }
  .venv/bin/python -m pip install -r requirements.txt && echo done > .venv/setup_done.txt
fi
nohup .venv/bin/python server.py > server.log 2>&1 &
echo "HeatGuard AI is opening at http://localhost:5000"
