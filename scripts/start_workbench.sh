#!/usr/bin/env bash
# One-click launcher for GitHub AI Video Generator Workbench
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "=== GitHub AI Video Generator Launcher ==="
"$DIR/.venv/bin/python3" "$DIR/scripts/server_manager.py"
