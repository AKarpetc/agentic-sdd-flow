#!/usr/bin/env bash
# Pins the Roslyn navigator to a project's solution: bind-roslyn.sh <project-name-or-path>
set -euo pipefail

BIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.agentic-sdd-flow}"; mkdir -p "$DATA"
POINTER="$DATA/roslyn-solution"

# shellcheck source=./roslyn-resolve.sh
source "$BIN/roslyn-resolve.sh"

if [[ $# -lt 1 ]]; then
    current="(none — auto-discovery)"
    [[ -f "$POINTER" ]] && current="$(cat "$POINTER")"
    echo "usage: bind-roslyn.sh <project-name-or-path>"
    echo "currently pinned: $current"
    exit 1
fi

if ! sln="$(roslyn_resolve_solution "$ROOT" "$1")"; then
    echo "error: $sln" >&2
    exit 1
fi

printf '%s\n' "$sln" > "$POINTER"
echo "pinned: $sln"
echo "now reconnect the server: /mcp -> cwm-roslyn-navigator -> reconnect"
