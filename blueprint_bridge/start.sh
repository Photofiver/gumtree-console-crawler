#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
STATE_DIR="$HOME/.local/state/blueprint-bridge"
mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"
if [[ -f "$STATE_DIR/server.pid" ]] && kill -0 "$(cat "$STATE_DIR/server.pid")" 2>/dev/null; then
  echo "Blueprint bridge already running"
  exit 0
fi
nohup python -m blueprint_bridge.server >"$STATE_DIR/server.log" 2>&1 </dev/null &
echo "$!" >"$STATE_DIR/server.pid"
echo "Blueprint remote browser is starting: http://localhost:8765"
echo "Open the forwarded port 8765 in your Codespaces PORTS panel; leave its visibility PRIVATE."
